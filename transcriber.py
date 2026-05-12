"""Speech-to-text transcription via faster-whisper."""

import logging
from pathlib import Path

import numpy as np

from config import WHISPER_COMPUTE, WHISPER_DEVICE, WHISPER_MODEL

logger = logging.getLogger(__name__)


class Transcriber:
    """Loads the Whisper model and transcribes audio buffers.

    ``load_model()`` is called once at startup on a background thread.
    ``transcribe()`` is called per recording on the transcription thread.
    """

    def __init__(self) -> None:
        self._model = None

    def load_model(self) -> None:
        """Load the faster-whisper model. Blocks for ~2–5 s on first call."""
        from faster_whisper import WhisperModel  # deferred import for startup perf

        model_path = str(Path(__file__).parent / "models" / WHISPER_MODEL)
        if not Path(model_path).exists():
            # Fall back to downloading by name (requires network on first run)
            model_path = WHISPER_MODEL
            logger.warning(
                "Bundled model not found at %s; will attempt download", model_path
            )

        logger.info("Loading Whisper model '%s' (%s %s)…", WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE)
        self._model = WhisperModel(
            model_path,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
        )
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
