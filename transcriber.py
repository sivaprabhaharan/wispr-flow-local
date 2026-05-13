"""Speech-to-text transcription via faster-whisper."""

import logging
from pathlib import Path

import numpy as np

from config import MODEL_DIR, WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

logger = logging.getLogger(__name__)


class Transcriber:
    """Loads the Whisper model and transcribes audio buffers.

    ``load_model()`` is called once at startup on a background thread.
    ``transcribe()`` is called per recording on the transcription thread.
    """

    def __init__(self) -> None:
        self._model = None

    def load_model(self) -> None:
        """Load the faster-whisper model. Blocks for ~2–5 s on first call.

        Checks for a bundled model in models/<name>/model.bin first.
        Falls back to downloading from HuggingFace on first run (~150 MB).
        Raises ``RuntimeError`` with a human-readable message on failure.
        """
        from faster_whisper import WhisperModel  # deferred import for startup perf

        local_path = Path(__file__).parent / MODEL_DIR / WHISPER_MODEL
        model_bin = local_path / "model.bin"
        if local_path.is_dir() and model_bin.exists():
            model_path = str(local_path)
            logger.info("Using bundled model at %s", local_path)
        else:
            # Auto-download from HuggingFace on first run (~150 MB)
            model_path = WHISPER_MODEL
            logger.info(
                "Bundled model not found at %s — downloading '%s' from HuggingFace (~150 MB, first run only)…",
                local_path, WHISPER_MODEL,
            )

        logger.info("Loading Whisper model '%s' (%s %s)…", WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE)
        try:
            self._model = WhisperModel(
                model_path,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load Whisper model '{WHISPER_MODEL}'. "
                "If this is your first run, the model download may have failed — "
                "check your internet connection and try again. "
                f"Details: {exc}"
            ) from exc
        logger.info("Whisper model loaded")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe float32 16 kHz audio. Returns the joined transcript text."""
        if self._model is None:
            raise RuntimeError("Model not loaded — call load_model() first")
        if len(audio) == 0:
            return ""

        segments, _info = self._model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=False,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
