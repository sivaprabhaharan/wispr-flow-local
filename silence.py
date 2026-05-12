"""Silence detector: RMS VAD + timeout, enforces MAX_RECORDING_S cap."""

import logging
import queue
import threading
import time

import numpy as np

from config import MAX_RECORDING_S, SILENCE_RMS_THRESHOLD, SILENCE_TIMEOUT

logger = logging.getLogger(__name__)


def rms(chunk: np.ndarray) -> float:
    return float(np.sqrt(np.mean(chunk ** 2)))


class SilenceDetector:
    """Monitors ``audio_q`` and sets ``stop_event`` on silence or time limit.

    Designed to run on its own thread. When ``stop_event`` is set the owning
    App stops the AudioCapture and moves to PROCESSING state.
    """

    def __init__(self, audio_q: queue.Queue, stop_event: threading.Event) -> None:
        self._audio_q = audio_q
        self._stop_event = stop_event

    def run(self) -> None:
        """Blocking loop — call on a dedicated thread."""
        silence_start: float | None = None
        record_start = time.monotonic()

        while not self._stop_event.is_set():
            # Enforce absolute recording cap
            if time.monotonic() - record_start >= MAX_RECORDING_S:
                logger.info("SilenceDetector: MAX_RECORDING_S reached, stopping")
                self._stop_event.set()
                return

            try:
                chunk: np.ndarray = self._audio_q.get(timeout=0.2)
            except queue.Empty:
                continue

            energy = rms(chunk)
            if energy < SILENCE_RMS_THRESHOLD:
                if silence_start is None:
                    silence_start = time.monotonic()
                elif time.monotonic() - silence_start >= SILENCE_TIMEOUT:
                    logger.info("SilenceDetector: %.1fs silence, stopping", SILENCE_TIMEOUT)
                    self._stop_event.set()
                    return
            else:
                silence_start = None  # reset on any speech chunk
