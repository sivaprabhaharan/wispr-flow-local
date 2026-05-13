"""Configuration constants — single source of truth for Wispr Flow Local."""

HOTKEY = "<ctrl>+<space>"

SAMPLE_RATE = 16_000          # Hz — faster-whisper expects 16 kHz
CHANNELS = 1                  # Mono
CHUNK_DURATION = 0.1          # seconds per audio chunk
SILENCE_TIMEOUT = 4.0         # seconds of silence before auto-stop
SILENCE_RMS_THRESHOLD = 0.01  # RMS energy below this = silence
MAX_RECORDING_S = 60          # safety cap — force-stop after 60 s

WHISPER_MODEL = "base"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE = "int8"

FILLER_WORDS = {
    "um", "uh", "like", "you know", "so", "basically",
    "actually", "literally", "right",
}

OVERLAY_POSITION = "bottom-right"  # corner placement
OVERLAY_MARGIN = 24                # px from screen edge
MODEL_DIR = "models"               # relative to app root; bundled at install time
