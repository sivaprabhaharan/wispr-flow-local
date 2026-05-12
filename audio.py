"""Audio capture via sounddevice InputStream."""

import logging
import queue
import threading

import numpy as np
import sounddevice as sd

from config import CHANNELS, CHUNK_DURATION, SAMPLE_RATE

logger = logging.getLogger(__name__)


class MicrophoneError(Exception):
    pass


class AudioCapture:
    """Records audio from the default microphone at 16 kHz mono.

    Chunks are placed on ``audio_q`` for concurrent consumption by
    SilenceDetector. ``stop()`` flushes the buffer and returns the complete
    recording as a single contiguous np.ndarray (float32).
    """

    def __init__(self, audio_q: queue.Queue) -> None:
        self._audio_q = audio_q
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def start(self) -> None:
        """Open the microphone stream. Raises MicrophoneError on failure."""
        self._chunks.clear()
        self._stopped.clear()
        blocksize = int(SAMPLE_RATE * CHUNK_DURATION)
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=blocksize,
                callback=self._callback,
            )
            self._stream.start()
            logger.info("AudioCapture: microphone stream started")
        except sd.PortAudioError as exc:
            raise MicrophoneError(str(exc)) from exc

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("AudioCapture callback status: %s", status)
        chunk = indata[:, 0].copy()  # flatten to 1-D float32
        with self._lock:
            self._chunks.append(chunk)
        try:
            self._audio_q.put_nowait(chunk)
        except queue.Full:
            pass

    def stop(self) -> np.ndarray:
        """Stop recording and return the complete audio buffer."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                logger.exception("Error stopping audio stream")
            self._stream = None

        self._stopped.set()

        with self._lock:
            if self._chunks:
                return np.concatenate(self._chunks)
            return np.zeros(0, dtype=np.float32)
