# PRD: Local Privacy-First Voice-to-Text for Windows (Wispr Flow Local)

## Problem Statement

Power users on Windows who dictate frequently are forced to choose between cloud-dependent voice tools (Wispr Flow, which is macOS-only; Whisper API-based tools) or clunky alternatives that require switching apps or don't insert text at the cursor. Privacy-sensitive users (developers, lawyers, journalists, executives) cannot use cloud STT because their content leaves the device.

There is no Windows app today that:
- Activates system-wide with a hotkey (speak *anywhere* the cursor is)
- Transcribes fully locally with high accuracy (Whisper-class quality)
- Inserts polished text at the cursor without clipboard hacks
- Runs silently in the tray with zero UI friction

**For whom:** Windows power users who dictate heavily — developers in editors, writers in Word/Obsidian, professionals in web apps — and who want Wispr Flow's UX with zero cloud dependency.

**Why now:** `faster-whisper` (CTranslate2-optimised Whisper) makes local Whisper viable on consumer CPUs/GPUs in near-real-time. The core building blocks exist; no one has assembled them into a polished Windows UX.

---

## Goals

1. **Activation**: Alt+Space global hotkey starts recording from any foreground app. Same hotkey (or hotkey release) stops recording.
2. **Transcription accuracy**: On English speech, approach Whisper `base` or `small` model accuracy — target ≥ 90% word accuracy on typical dictation (prose, commands, names).
3. **Latency**: ≤ 3 seconds from speech end to text-at-cursor on a mid-range PC (Core i5 / no dedicated GPU). Faster on GPU.
4. **Text injection**: Inserted text appears in the *active* window — works in IDEs, browsers, Outlook, Notepad, WSL terminals. No clipboard required.
5. **Filler word removal**: "um", "uh", "like", "you know" stripped before insertion.
6. **Auto-punctuation**: Basic sentence-end punctuation added where Whisper leaves gaps.
7. **Recording overlay**: Clear, minimal visual indicator of recording state (idle / recording / processing).
8. **System tray daemon**: App runs as background process, minimal RAM footprint (< 500 MB with model loaded).
9. **100% local**: Zero network calls. No API keys. Works offline.
10. **Silence detection**: Auto-stops recording after configurable silence timeout.

---

## Non-Goals

*Explicitly out of scope for MVP:*

- macOS or Linux support
- Languages other than English
- Real-time (word-by-word) streaming output — batch transcription after stop is acceptable
- Speaker diarisation / multiple speakers
- Voice commands / app control (this is transcription only, not a voice assistant)
- Cloud fallback mode
- Custom vocabulary / fine-tuned models
- Punctuation editing UI or transcript review screen
- Integration with specific apps (e.g., Zoom, Teams, Slack) beyond generic text injection
- Mobile companion app
- Paid licensing / SaaS features

---

## User Stories / Scenarios

**U1 — Developer dictating a code comment**
> Dev is in VS Code. Presses Alt+Space, says "slash slash TODO: refactor this method to handle edge cases", releases hotkey. Polished text appears at cursor in the open file.

**U2 — Writer drafting in Obsidian**
> Writer presses Alt+Space, dictates a paragraph. App strips "um"s, adds sentence punctuation, inserts text at cursor. Writer continues typing where they left off.

**U3 — Email in Outlook Web (browser)**
> User is composing an email in Chrome. Alt+Space activates recording. Speech is transcribed and injected at the cursor in the textarea — no clipboard involved.

**U4 — Silence auto-stop**
> User forgets to release the hotkey. After 2 seconds of silence, recording stops and transcription begins automatically.

**U5 — Privacy-conscious professional**
> Lawyer dictates confidential client notes. Knows with certainty nothing leaves the machine because there is no network dependency.

**U6 — System tray management**
> User right-clicks the tray icon to see model info, adjust hotkey, or quit the app.

---

## Constraints

**Technical:**
- Must work on Windows 10 and Windows 11 (64-bit)
- Python runtime (likely packaged with PyInstaller or similar for distribution)
- `faster-whisper` requires Microsoft Visual C++ redistributable — affects packaging
- `SendInput` via ctypes is the most reliable way to inject keystrokes without requiring accessibility permissions; clipboard approach is fallback
- Global hotkey registration via `pynput` or `keyboard` library; may conflict with other apps' hotkeys
- `sounddevice` requires PortAudio — needs to ship with the binary
- Model files (faster-whisper `base` or `small`) are 150–300 MB — affects installer size
- Tkinter overlay must float above other windows (`wm_attributes -topmost`)

**Business / scope:**
- MVP: single developer, no external funding → keep scope tight
- English-only simplifies punctuation and filler-word logic significantly
- No installer signing → Windows SmartScreen warnings; users may need to click through

**Timeline:**
- Unknown; no hard deadline stated

---

## Open Questions

1. **Hotkey configurability**: Is Alt+Space fixed for MVP, or does the user need to change it? (Conflicts with Windows IME on some systems.)
2. **Model selection**: Which Whisper model for MVP — `tiny` (fast, less accurate), `base` (balanced), `small` (slower, better)? Does the user want model selection in the tray menu?
3. **Hold-to-record vs toggle**: Is Alt+Space a hold-to-record (push-to-talk) or a toggle? The brief says "stop on hotkey release" — confirm this is push-to-talk.
4. **Text injection method**: Primary = `SendInput` (keystrokes). Is clipboard paste an acceptable fallback for apps that block keystroke injection (e.g., some game launchers, admin-elevated windows)?
5. **Silence detection threshold**: What's the target silence duration before auto-stop? (2s? 3s?) Is configurable silence threshold needed in MVP?
6. **Filler word list**: Is the filler list hardcoded ("um", "uh", "like", "you know", "so", "basically") or user-configurable in MVP?
7. **Auto-punctuation approach**: Whisper already infers some punctuation. Is post-processing punctuation additive (fill gaps) or a full replacement pass?
8. **GPU support**: Should faster-whisper's CUDA path be enabled if a GPU is detected, or CPU-only for MVP simplicity?
9. **Packaging**: Standalone `.exe` installer? Or just a zipped Python environment? Who are the expected users — developers comfortable with pip, or non-technical?
10. **Error states**: What happens if microphone access is denied? If no mic is found? Should the app show a notification?
11. **Concurrent recording prevention**: What if user triggers hotkey while a previous transcription is still processing?

---

## Rough Approach

**Architecture: single-process daemon**

```
[pynput global hotkey listener]
        ↓ (Alt+Space pressed)
[sounddevice audio capture thread]
        ↓ (audio buffer, on stop/silence)
[faster-whisper transcription]
        ↓ (transcript string)
[post-processor: filler removal + punctuation]
        ↓ (clean text)
[SendInput text injection via ctypes]
        + [tkinter overlay: recording/processing states]
        + [pystray tray icon + menu]
```

**Key implementation bets:**
- `faster-whisper` with `int8` quantisation on CPU should hit ~1–2× real-time on a modern Core i5 for `base` model — acceptable latency for typical 5–10s dictation bursts
- `ctypes.windll.user32.SendInput` with `INPUT_KEYBOARD` events for character-by-character injection is the most portable injection approach; `pyautogui.typewrite` is a higher-level fallback
- Tkinter `Toplevel` with `overrideredirect=True` + `-topmost True` for a frameless always-on-top overlay
- `sounddevice.InputStream` for low-latency audio capture; VAD (webrtcvad or simple RMS threshold) for silence detection
- All state managed in a single `App` class; threading with `queue.Queue` between capture and transcription

**Open risks:**
- UAC-elevated windows will block `SendInput` from a non-elevated process — may need a workaround or user docs
- pynput global hooks may require specific Windows permissions in some enterprise environments
- PyInstaller packaging with faster-whisper + CUDA dependencies is known to be finicky
- First run is slow (model warm-up); need a splash or tray status indicator
