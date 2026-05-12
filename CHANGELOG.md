# Changelog

All notable changes to Wispr Flow Local are documented in this file.

---

## [0.1.0] — 2026-05-12

### Added

#### Core MVP Implementation
- **`config.py`** — Central constants: hotkey combo (`Alt+Space`), Whisper model settings (`base`, CPU int8, beam_size=5), silence timeout (4 s), max recording cap (120 s), model directory, log path, audio sample rate (16 kHz), and filler word list.
- **`state.py`** — `AppState` enum (`IDLE`, `RECORDING`, `TRANSCRIBING`) with thread-safe `StateManager` (lock-guarded transitions, `push_state` queue).
- **`hotkey.py`** — Dedicated `pynput` keyboard-hook thread; press/release callbacks; `HotkeyRegistrationError` on failure.
- **`audio.py`** — 16 kHz mono `sounddevice.InputStream` capture; `MicrophoneError` on device failure; concatenated numpy buffer returned on stop.
- **`silence.py`** — RMS-based VAD; auto-stops recording after `SILENCE_TIMEOUT` seconds of quiet or `MAX_RECORDING_S` cap.
- **`transcriber.py`** — `faster-whisper` local transcription; loads `base` model from `MODEL_DIR`; `vad_filter=False`; returns plain text string.
- **`postprocessor.py`** — Filler word removal (bigram-first); appends terminal period when auto-punctuation is enabled.
- **`injector.py`** — `SendInput` Unicode keystroke injection (primary path); clipboard paste as silent fallback; `InjectionError` raised when both paths fail; clipboard always restored in `finally` block.
- **`overlay.py`** — Frameless, always-on-top tkinter window showing recording state (idle / recording / transcribing); pulse animation; never steals keyboard focus (`focus_set` not called).
- **`tray.py`** — `pystray` system-tray icon; Pillow-drawn coloured circle (green=idle, red=recording, yellow=transcribing); state-based colour updates; Quit menu item.
- **`main.py`** — Central `App` orchestrator: wires all components, manages inter-thread queues, handles clean shutdown with `_shutdown_event` guard.

#### Architecture
- Fully offline — zero network calls, no telemetry, no auto-update.
- Push-to-talk model: hold **Alt+Space** → record; release → transcribe & inject.
- All components communicate via `queue.Queue` across dedicated threads.
- Rotating log file at `%APPDATA%\WisprFlowLocal\wispr.log` (5 MB × 3 backups).

#### Tests
- Comprehensive `pytest` test suite covering all modules (`tests/`).
- `conftest.py` stubs all hardware/platform dependencies (sounddevice, pynput, pyperclip, pystray, PIL, faster-whisper, ctypes.windll) so the suite runs on any OS without physical hardware.
- Test files: `test_config.py`, `test_state.py`, `test_hotkey.py`, `test_audio.py`, `test_silence.py`, `test_transcriber.py`, `test_postprocessor.py`, `test_injector.py`, `test_overlay.py`, `test_tray.py`, `test_main.py`.

#### Packaging
- `pyproject.toml` with `setuptools` build backend; console-scripts entry point `wispr-flow-local = main:main`.
- `requirements.txt` pinning all runtime dependencies.

### Fixed (during review — same release)

1. **`overlay.py`** — Removed `focus_set()` / `focus_force()` calls that stole keyboard focus from the target application, causing silent text-injection failure on every recording.
2. **`transcriber.py`** — `load_model()` now uses the `MODEL_DIR` config constant instead of a hardcoded `"models"` string, so path changes in `config.py` propagate correctly.
3. **`injector.py`** — Moved clipboard restore to a `finally` block so the user's clipboard is always recovered even when `_send_ctrl_v()` raises an exception.
4. **`injector.py` / `main.py`** — Added `InjectionError` exception; `inject()` now raises it when both `SendInput` and clipboard paste fail; `main.py` catches it and shows a tray balloon notification (*"Text could not be inserted — target window may be read-only."*).
5. **`main.py`** — Added `_shutdown_event` guard in `_on_recording_stopped()` to prevent processing on a destroyed tkinter root when shutdown and the stop-watcher thread race.

### Design Document
- `DESIGN.md` — Full architecture reference: component diagram, inter-thread communication, state machine, error handling strategy, and per-module API contracts.
- `REVIEW.md` — Post-implementation review: all five critical bugs identified and fixed; three minor deferred items documented for v1.1.
