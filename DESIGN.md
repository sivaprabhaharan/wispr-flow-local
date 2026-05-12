# Wispr Flow Local — Architecture Design

**Version:** MVP  
**Target Platform:** Windows 10 / 11 (64-bit)  
**Runtime:** Python 3.11+  

---

## 1. Problem & Scope

Wispr Flow Local is a fully offline, privacy-first, system-wide voice-to-text daemon for
Windows. The user holds **Alt+Space** (push-to-talk), dictates, and the transcribed text
is inserted at the active cursor — with no cloud dependency, no clipboard contamination,
and minimal UI friction.

**MVP feature set:**
- Push-to-talk (hold Alt+Space → record; release → transcribe & inject)
- Local transcription via `faster-whisper` (`base` model, CPU int8)
- 4-second silence auto-stop
- Filler word removal (hardcoded list)
- Auto-punctuation (append terminal period if missing)
- Text injection via `SendInput`; clipboard paste as silent fallback
- Frameless always-on-top recording overlay (3 states)
- System tray icon + context menu
- 100% offline — zero network calls, no telemetry, no auto-update

---

## 2. Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          App (main.py)                          │
│                  Central orchestrator / state machine           │
└────┬────────────┬───────────────┬───────────────┬──────────────┘
     │            │               │               │
     ▼            ▼               ▼               ▼
┌─────────┐  ┌─────────┐   ┌──────────┐   ┌───────────┐
│ Hotkey  │  │ Audio   │   │  Tray    │   │  Overlay  │
│Listener │  │Capture  │   │  Icon    │   │ (tkinter) │
│(pynput) │  │(sound-  │   │(pystray) │   │           │
│         │  │ device) │   │          │   │           │
└────┬────┘  └────┬────┘   └──────────┘   └───────────┘
     │            │
     │            ▼
     │      ┌──────────┐
     │      │ Silence  │
     │      │Detector  │
     │      │ (RMS VAD)│
     │      └────┬─────┘
     │           │ (audio buffer on stop)
     └───────────┤
                 ▼
          ┌────────────┐
          │Transcriber │
          │(faster-    │
          │ whisper)   │
          └─────┬──────┘
                │ (raw transcript)
                ▼
          ┌────────────┐
          │    Post    │
          │ Processor  │
          │(filler +   │
          │ punct.)    │
          └─────┬──────┘
                │ (clean text)
                ▼
          ┌────────────┐
          │   Text     │
          │ Injector   │
          │(SendInput  │
          │ → clipbd.) │
          └────────────┘
```

### Inter-thread Communication

All components run on separate threads and communicate via `queue.Queue`:

| Queue | Producer | Consumer | Contents |
|-------|----------|----------|----------|
| `audio_q` | AudioCapture | SilenceDetector | `np.ndarray` chunks (float32, mono, 16 kHz) |
| `transcript_q` | Transcriber | App | `str` (raw transcript) |
| `state_q` | App | Overlay / TrayIcon | `AppState` enum value |

A threading `Event` (`stop_event`) is set when recording should cease (hotkey release or silence).

---

## 3. Module Breakdown

### `state.py` — Application State Machine

```python
class AppState(Enum):
    IDLE       = "idle"
    RECORDING  = "recording"
    PROCESSING = "processing"
```

Transitions:
```
IDLE ──(hotkey press)──► RECORDING ──(release/silence)──► PROCESSING ──(done)──► IDLE
                                      └──(error)──────────────────────────────────────┘
```

No concurrent recordings: if a hotkey press arrives during `PROCESSING`, it is ignored.

---

### `config.py` — Configuration Constants

```python
HOTKEY          = "<alt>+<space>"
SAMPLE_RATE     = 16_000          # Hz — faster-whisper expects 16 kHz
CHANNELS        = 1               # Mono
CHUNK_DURATION  = 0.1             # seconds per audio chunk
SILENCE_TIMEOUT = 4.0             # seconds of silence before auto-stop
SILENCE_RMS_THRESHOLD = 0.01      # RMS energy below this = silence
MAX_RECORDING_S = 60              # Safety cap — force-stop after 60s
WHISPER_MODEL   = "base"
WHISPER_DEVICE  = "cpu"
WHISPER_COMPUTE = "int8"
FILLER_WORDS    = {
    "um", "uh", "like", "you know", "so", "basically",
    "actually", "literally", "right",
}
OVERLAY_POSITION = "bottom-right"  # corner placement
OVERLAY_MARGIN   = 24              # px from screen edge
MODEL_DIR        = "models"        # relative to app root; bundled at install time
```

---

### `hotkey.py` — Global Hotkey Listener

**Library:** `pynput.keyboard.GlobalHotKeys` (runs a `WH_KEYBOARD_LL` Windows hook).

**Design constraints:**
- The hook pump runs on a **dedicated daemon thread** so the main thread and transcription
  thread never block the message loop. A blocked hook thread on Windows drops key-release
  events, causing stuck recording state.
- Only one callback pair is registered: press → `on_press`, release → `on_release`.
- pynput's `GlobalHotKeys` context manager handles thread lifecycle.

```python
class HotkeyListener:
    def __init__(self, on_press: Callable, on_release: Callable): ...
    def start(self) -> None: ...   # spawns daemon thread
    def stop(self) -> None: ...
```

**Failure mode:** If registration fails (permission denied, hotkey already claimed by another
app), a `HotkeyRegistrationError` is raised during `start()`. The App catches this, logs the
error, notifies the user via a tray balloon, and continues running without hotkey support.

---

### `audio.py` — Audio Capture

**Library:** `sounddevice.InputStream`

**Design:**
- Opens default input device at 16 kHz mono on `start()`.
- Each callback appends a chunk (`np.float32` array) to a shared list; a background thread
  drains it into `audio_q`.
- `stop()` flushes the remainder, signals `stop_event`, and returns the complete audio buffer
  as a single `np.ndarray`.

```python
class AudioCapture:
    def start(self) -> None: ...
    def stop(self) -> np.ndarray: ...   # blocks until flush complete
```

**Failure modes:**
- No microphone found → `sounddevice.PortAudioError` → propagate as `MicrophoneError`.
- Microphone disconnected during recording → `sounddevice` raises in callback → caught,
  recording stopped, user notified via tray balloon.
- Microphone permission denied on Windows → same as above.

---

### `silence.py` — Silence Detector

**Algorithm:** RMS energy threshold on 100 ms windows.

```python
def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk ** 2)))
```

A rolling timer is started when `rms(chunk) < SILENCE_RMS_THRESHOLD`. If silence persists for
`SILENCE_TIMEOUT` seconds, `stop_event` is set — triggering `AudioCapture.stop()`.

The detector also enforces `MAX_RECORDING_S`: after 60 seconds of continuous recording
(regardless of silence), recording is force-stopped.

```python
class SilenceDetector:
    def __init__(self, audio_q: Queue, stop_event: Event): ...
    def run(self) -> None: ...   # blocking; called on its own thread
```

---

### `transcriber.py` — Speech-to-Text

**Library:** `faster-whisper` (CTranslate2 backend)

```python
class Transcriber:
    def __init__(self): ...
    def load_model(self) -> None: ...   # called at startup; blocks ~2–5s
    def transcribe(self, audio: np.ndarray) -> str: ...
```

**Model loading:**
- `WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)`
- Model files are **bundled** in `models/base/` (no network calls at runtime).
- During `load_model()`, the overlay shows a "Loading…" message and the hotkey is disabled.
- Once loaded, the tray icon transitions to `IDLE` state and the hotkey is activated.

**Transcription:**
- `model.transcribe(audio, language="en", beam_size=5, vad_filter=False)`
- Returns an iterator of segments; joined into a single string.
- Runs on a dedicated `transcription_thread` (not the main thread) to avoid blocking the UI.

**Latency notes:**
- `base` int8 on Core i5: ~1.0–1.5× real-time. A 5s clip takes ~5–8s end-to-end.
- Latency goal (≤3s) applies to clips ≤5s; longer clips scale linearly.

---

### `postprocessor.py` — Text Cleanup

Two sequential passes applied to the raw Whisper transcript:

#### Pass 1: Filler Word Removal
Token-level: split on whitespace, drop tokens whose lowercase form appears in `FILLER_WORDS`.
Handles multi-word fillers ("you know") via sliding bigram check before single-token check.

```python
def remove_fillers(text: str) -> str: ...
```

#### Pass 2: Auto-Punctuation
Rule: if the final non-whitespace character is **not** a terminal punctuation mark (`.`, `!`,
`?`, `:`, `;`, `…`), append `.`. This is additive — it never removes Whisper's own punctuation.

```python
def add_terminal_punctuation(text: str) -> str: ...
```

```python
class PostProcessor:
    def process(self, raw: str) -> str:
        return add_terminal_punctuation(remove_fillers(raw))
```

---

### `injector.py` — Text Injection

**Primary path: `SendInput` via `ctypes`**

Uses `ctypes.windll.user32.SendInput` with `INPUT_KEYBOARD` events to synthesise keystrokes
character by character (Unicode input via `KEYEVENTF_UNICODE`). This works in standard
user-mode windows without requiring elevated privileges.

**Fallback path: Clipboard paste**

When `SendInput` fails (detected by comparing character count, or when the target window has
`WS_EX_TOPMOST | WS_EX_LAYERED` traits typical of elevated processes), the injector:
1. Saves the current clipboard contents.
2. Writes the transcribed text to the clipboard.
3. Sends `Ctrl+V` via `SendInput`.
4. Restores the original clipboard contents after a 500 ms delay.

The fallback is silent (no user notification) to avoid interrupting flow; the text still
appears. If both paths fail (read-only field, game window, etc.), a tray balloon notifies the
user: *"Text could not be inserted — target window may be read-only."*

```python
class TextInjector:
    def inject(self, text: str) -> bool: ...   # True = success, False = fallback used
    def _send_input(self, text: str) -> bool: ...
    def _clipboard_paste(self, text: str) -> None: ...
```

**`pyautogui` role:** `pyautogui.typewrite` is available as a last-resort debug fallback
(character-by-character with OS-level delay) but is **not** used in the production path due to
its slower rate and QWERTY layout dependency.

---

### `overlay.py` — Recording State Overlay

**Library:** `tkinter` (`Toplevel` window)

A small frameless always-on-top window in the bottom-right corner of the primary screen.

| State | Appearance |
|-------|-----------|
| `IDLE` | Hidden (withdrawn) |
| `RECORDING` | Red pulsing dot + "Recording…" label |
| `PROCESSING` | Spinner + "Processing…" label |

**Implementation notes:**
- `overrideredirect(True)` removes window decorations.
- `wm_attributes("-topmost", True)` keeps it above most windows.
- `wm_attributes("-alpha", 0.85)` for slight transparency.
- `focus_set()` is **never** called — the overlay must not steal focus from the target app.
- `after()` loop on the tkinter main thread handles state changes from `state_q`.
- Window is destroyed and re-created on each RECORDING start to avoid z-order stacking issues.

**Known limitation:** `-topmost True` does not guarantee visibility above DirectX exclusive
fullscreen applications. Accepted as a known limitation for MVP; `win32gui` with
`WS_EX_LAYERED | WS_EX_TOOLWINDOW` can be adopted in v1.1.

---

### `tray.py` — System Tray Icon

**Library:** `pystray` + `Pillow`

Three icon images (idle / recording / processing) are generated programmatically via `Pillow`
at startup (coloured circles on transparent background) and cached as `PIL.Image` objects.

**Context menu:**
```
Wispr Flow Local — idle       (status label, disabled)
─────────────────────────────
Model: Whisper base (CPU)     (disabled)
─────────────────────────────
Quit
```

The tray icon updates its image by calling `pystray.Icon.icon = <new PIL.Image>` when the
`AppState` changes.

```python
class TrayIcon:
    def start(self) -> None: ...   # non-blocking; pystray runs its own thread
    def update_state(self, state: AppState) -> None: ...
    def stop(self) -> None: ...
```

---

### `main.py` — App Orchestrator

Owns the main thread (runs tkinter's `mainloop()`). All other components run as daemon threads.

**Startup sequence:**
1. Create `TrayIcon`, show "Loading…" state.
2. Launch `Transcriber.load_model()` on background thread.
3. On model load complete: activate `HotkeyListener`, update tray to `IDLE`.
4. Start `tkinter` mainloop.

**Recording flow (state transitions):**
```
on_hotkey_press():
    if state != IDLE: return          # ignore during PROCESSING
    state = RECORDING
    stop_event.clear()
    AudioCapture.start()
    SilenceDetector.run() on thread   # watches audio_q, sets stop_event on silence
    update UI → RECORDING

on_hotkey_release() or silence detected:
    audio = AudioCapture.stop()
    state = PROCESSING
    update UI → PROCESSING
    raw = Transcriber.transcribe(audio)   # on transcription_thread
    clean = PostProcessor.process(raw)
    TextInjector.inject(clean)
    state = IDLE
    update UI → IDLE
```

**Shutdown:**
- Tray "Quit" → `stop_event.set()`, join all threads, `root.destroy()`.

---

## 4. Data Flow: Hotkey to Text Insertion

```
┌──────────────────────────────────────────────────────────────────┐
│  User holds Alt+Space                                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │  HotkeyListener     │  pynput WH_KEYBOARD_LL hook
                │  on_press() fires   │  (dedicated hook thread)
                └──────────┬──────────┘
                           │  state: IDLE → RECORDING
                           │
          ┌────────────────▼────────────────┐
          │  AudioCapture.start()           │  sounddevice.InputStream
          │  Opens default mic, 16 kHz mono │  callback → audio_q
          └────────────────┬────────────────┘
                           │  np.float32 chunks → audio_q
                           │
          ┌────────────────▼────────────────┐
          │  SilenceDetector.run()          │  separate thread
          │  RMS per chunk vs threshold     │  4s timeout → stop_event
          └────────────────┬────────────────┘
                           │
          ┌────────────────▼────────────────┐
          │  AudioCapture.stop()            │  triggered by hotkey
          │  Returns full np.ndarray buffer │  release OR silence
          └────────────────┬────────────────┘
                           │  state: RECORDING → PROCESSING
                           │
          ┌────────────────▼────────────────┐
          │  Transcriber.transcribe()       │  faster-whisper
          │  base model, int8, CPU, en      │  transcription_thread
          └────────────────┬────────────────┘
                           │  raw str
                           │
          ┌────────────────▼────────────────┐
          │  PostProcessor.process()        │
          │  1. remove_fillers()            │
          │  2. add_terminal_punctuation()  │
          └────────────────┬────────────────┘
                           │  clean str
                           │
          ┌────────────────▼────────────────┐
          │  TextInjector.inject()          │
          │  Primary: SendInput (Unicode)   │
          │  Fallback: clipboard paste+Ctrl+V│
          └────────────────┬────────────────┘
                           │  state: PROCESSING → IDLE
                           ▼
               Text appears at active cursor
```

---

## 5. Error Handling

| Error Condition | Detection | Response |
|-----------------|-----------|----------|
| No microphone found | `sounddevice.PortAudioError` on `start()` | Tray balloon: "No microphone found. Check audio settings." State stays IDLE. |
| Microphone disconnected mid-recording | Exception in `sounddevice` callback | Stop recording, discard buffer, tray balloon: "Microphone disconnected." State → IDLE. |
| Microphone permission denied | Same as above on Windows | Tray balloon: "Microphone access denied. Check Windows privacy settings." |
| Hotkey registration fails | `Exception` in `HotkeyListener.start()` | Tray balloon: "Hotkey Alt+Space could not be registered — may conflict with another app." App continues; tray right-click menu still works. |
| Model files missing | `FileNotFoundError` in `load_model()` | Fatal: show error dialog, exit. Message: "Model files not found. Please reinstall." |
| Transcription error | Exception in `transcribe()` | Log error, tray balloon: "Transcription failed." State → IDLE. No text injected. |
| SendInput fails | Return value from `SendInput` == 0 | Fall through to clipboard paste path silently. |
| Both injection paths fail | After clipboard paste attempt also fails | Tray balloon: "Text could not be inserted — target window may be read-only." |
| Concurrent recording attempt | Hotkey press during PROCESSING state | Silently ignored (no UI disruption). |
| Stuck recording (60s cap) | `SilenceDetector` MAX_RECORDING_S timer | Force-stop recording and proceed to transcription. |
| UAC-elevated target window | `SendInput` blocked by UIPI | Handled by clipboard fallback path above. |

**Logging:** All errors are written to `%APPDATA%\WisprFlowLocal\wispr.log` with rotating file
handler (max 5 MB, 3 backups). No log is sent anywhere; log file is local only.

---

## 6. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `faster-whisper` | 1.2.1 | Local Whisper transcription (CTranslate2 backend) |
| `sounddevice` | 0.5.5 | Audio capture via PortAudio |
| `pynput` | 1.8.1 | Global hotkey listener (WH_KEYBOARD_LL hook) |
| `pyautogui` | 0.9.54 | Debug/last-resort text injection fallback |
| `pystray` | 0.19.5 | Windows system tray icon |
| `Pillow` | 12.2.0 | Icon image generation for tray |
| `pyperclip` | 1.11.0 | Clipboard read/write for fallback injection path |
| `numpy` | 2.4.4 | Audio buffer manipulation |

**Standard library used:** `ctypes` (SendInput), `tkinter` (overlay), `threading`, `queue`,
`logging`, `enum`, `pathlib`

**Runtime requirements (Windows):**
- Microsoft Visual C++ Redistributable 2015–2022 (required by CTranslate2)
- PortAudio DLL (bundled by `sounddevice` wheel on Windows)

**Python version:** 3.11 or 3.12 (required for `faster-whisper` 1.x on Windows)

### `requirements.txt`

```
faster-whisper==1.2.1
sounddevice==0.5.5
pynput==1.8.1
pyautogui==0.9.54
pystray==0.19.5
Pillow==12.2.0
pyperclip==1.11.0
numpy==2.4.4
```

---

## 7. Project File Structure

```
wispr_flow_local/
│
├── main.py               # Entry point; App class; tkinter mainloop
├── state.py              # AppState enum; state transition guard
├── config.py             # All configuration constants (single source of truth)
│
├── hotkey.py             # HotkeyListener — pynput global hotkey
├── audio.py              # AudioCapture — sounddevice InputStream
├── silence.py            # SilenceDetector — RMS VAD + timeout
├── transcriber.py        # Transcriber — faster-whisper model load + inference
├── postprocessor.py      # PostProcessor — filler removal + auto-punctuation
├── injector.py           # TextInjector — SendInput + clipboard fallback
├── overlay.py            # Overlay — tkinter frameless topmost window
├── tray.py               # TrayIcon — pystray + Pillow icon generation
│
├── models/
│   └── base/             # Bundled faster-whisper base model files
│       ├── model.bin
│       ├── config.json
│       ├── tokenizer.json
│       └── vocabulary.txt
│
├── assets/               # Source images (optional; icons generated via Pillow at runtime)
│
├── requirements.txt      # Pinned production dependencies
├── README.md             # User-facing setup and usage guide
└── DESIGN.md             # This document
```

---

## 8. Threading Model

```
Main thread (tkinter mainloop)
│
├── hook_thread         — pynput GlobalHotKeys message pump (daemon)
├── silence_thread      — SilenceDetector.run() (daemon; per-recording lifecycle)
├── transcription_thread— Transcriber.transcribe() (daemon; per-recording lifecycle)
└── tray_thread         — pystray event loop (daemon)
```

All inter-thread communication uses `queue.Queue` (thread-safe) or `threading.Event`.
No shared mutable state outside of the protected `AppState` (guarded by `threading.Lock`).

---

## 9. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| Push-to-talk (hold, not toggle) | Matches hook spec; lower risk of runaway recording |
| Dedicated hook thread | Prevents transcription load from dropping key-release events |
| RMS silence detection (not WebRTC VAD) | Zero extra dependencies; sufficient for typical dictation |
| `base` model, CPU int8 | Balances accuracy vs. latency on target hardware; `tiny` too inaccurate, `small` too slow |
| Bundled model files | Guarantees offline-first; avoids Hugging Face ToS; no first-run download spinner |
| `SendInput` with Unicode flag | Most portable injection; works in browsers, IDEs, Outlook Web |
| Clipboard fallback with save/restore | Handles UAC-elevated windows; restores prior clipboard to avoid contamination |
| Pillow-generated tray icons | No static asset files needed; icons adapt to any DPI |
| tkinter overlay (not win32gui) | Avoids pywin32 dependency for MVP; accepted z-order limitation documented |
| Single-process daemon | Simpler IPC; sufficient for MVP; no socket/pipe complexity |

---

## 10. Out of Scope (MVP)

- GPU / CUDA transcription path
- Hotkey configurability (settings UI)
- Model selection UI in tray
- Configurable silence threshold
- Real-time streaming transcription
- Languages other than English
- PyInstaller packaging spike (separate engineering task)
- Code signing (required for enterprise; v1.0 release blocker)
- Auto-start on login (Windows startup registry entry)
- macOS / Linux support
