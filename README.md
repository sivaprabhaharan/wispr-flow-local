# Wispr Flow Local

A fully offline, privacy-first, system-wide voice-to-text daemon for Windows.

Hold **Alt+Space** to record, release to transcribe. Text is inserted at the active cursor — no cloud, no clipboard contamination, no telemetry.

## Requirements

- Windows 10 / 11 (64-bit)
- Python 3.11 or 3.12
- Microsoft Visual C++ Redistributable 2015–2022

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sivaprabhaharan/wispr-flow-local.git
cd wispr-flow-local
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or install as a package (adds the `wispr-flow-local` console script):

```bash
pip install -e .
```

### 3. Place the Whisper model (optional)

On first run, the app **automatically downloads** the `base` Whisper model from HuggingFace (~150 MB). This requires a one-time internet connection and takes 1–5 minutes depending on your connection speed.

Alternatively, place pre-downloaded `faster-whisper` `base` model files in `models/base/` to skip the download:

```
models/
└── base/
    ├── model.bin
    ├── config.json
    ├── tokenizer.json
    └── vocabulary.txt
```

Download manually from: https://huggingface.co/Systran/faster-whisper-base/tree/main

## Running

```bash
python main.py
```

Or, if installed as a package:

```bash
wispr-flow-local
```

A green circle appears in the system tray confirming the app is running and the hotkey is active.

## Usage

| Action | Result |
|--------|--------|
| Hold **Alt+Space** | Recording starts — a red dot overlay appears on screen |
| Release **Alt+Space** | Recording stops; transcription begins (yellow overlay) |
| 4 seconds of silence | Recording auto-stops even if hotkey is still held |
| 120 seconds elapsed | Hard cap — recording stops automatically |
| Overlay disappears | Transcribed text has been injected at the cursor |
| Tray → **Quit** | Exits the application cleanly |

### Text injection

Transcribed text is injected via Windows `SendInput` (Unicode keystrokes) directly into the active window — the clipboard is not modified. If `SendInput` fails (e.g. a read-only or elevated-privilege window), the app falls back to clipboard paste (`Ctrl+V`) silently. If both methods fail, a tray balloon notification appears: *"Text could not be inserted — target window may be read-only."*

### Filler word removal

Common filler words (`um`, `uh`, `like`, `you know`, etc.) are stripped from the transcript automatically before injection.

## Logs

`%APPDATA%\WisprFlowLocal\wispr.log` — rotating log, max 5 MB × 3 backups.

## Development Setup

### Install dev dependencies

The project uses `pytest` for testing. Install the runtime dependencies first:

```bash
pip install -r requirements.txt
pip install pytest
```

### Running tests

```bash
pytest tests/
```

The test suite mocks all hardware and platform dependencies (microphone, keyboard hooks, Windows API, tray icon, tkinter) so it runs on any OS — including Linux and macOS CI — without physical hardware or a display.

Run with verbose output:

```bash
pytest tests/ -v
```

Run a single test file:

```bash
pytest tests/test_injector.py -v
```

### Project structure

```
wispr-flow-local/
├── main.py            # App orchestrator and entry point
├── config.py          # Central constants (hotkey, model, timeouts)
├── state.py           # AppState enum + thread-safe StateManager
├── hotkey.py          # pynput keyboard hook (push-to-talk)
├── audio.py           # sounddevice microphone capture
├── silence.py         # RMS VAD silence detector
├── transcriber.py     # faster-whisper local transcription
├── postprocessor.py   # Filler removal + auto-punctuation
├── injector.py        # SendInput / clipboard text injection
├── overlay.py         # Frameless always-on-top tkinter overlay
├── tray.py            # pystray system-tray icon
├── models/            # Whisper model weights (not committed)
├── tests/             # pytest test suite
├── pyproject.toml     # Package metadata and build config
├── requirements.txt   # Pinned runtime dependencies
├── DESIGN.md          # Architecture reference
├── REVIEW.md          # Post-implementation bug review
└── CHANGELOG.md       # Release history
```

## Architecture

See [DESIGN.md](DESIGN.md) for the full architecture documentation, including the component diagram, inter-thread communication model, state machine, and per-module API contracts.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
