# Wispr Flow Local

A fully offline, privacy-first, system-wide voice-to-text daemon for Windows.

Hold **Alt+Space** to record, release to transcribe. Text is inserted at the active cursor — no cloud, no clipboard contamination.

## Requirements

- Windows 10 / 11 (64-bit)
- Python 3.11 or 3.12
- Microsoft Visual C++ Redistributable 2015–2022

## Setup

```bash
pip install -r requirements.txt
```

Place bundled Whisper `base` model files in `models/base/`:
```
models/
└── base/
    ├── model.bin
    ├── config.json
    ├── tokenizer.json
    └── vocabulary.txt
```

If no bundled model is present, the model will be downloaded on first run (requires network).

## Run

```bash
python main.py
```

A system tray icon (green circle) confirms the app is running and the hotkey is active.

## Usage

| Action | Result |
|--------|--------|
| Hold Alt+Space | Recording starts (red dot overlay appears) |
| Release Alt+Space | Recording stops; transcription begins |
| 4 seconds of silence | Recording auto-stops |
| Tray → Quit | Exits the application |

## Logs

`%APPDATA%\WisprFlowLocal\wispr.log` (rotating, max 5 MB × 3 backups)

## Architecture

See [DESIGN.md](DESIGN.md) for full architecture documentation.
