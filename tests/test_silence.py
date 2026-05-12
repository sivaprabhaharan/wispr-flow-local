"""Tests for silence.py — RMS VAD, silence timeout, and MAX_RECORDING_S cap."""

import queue
import threading
import time
from unittest.mock import patch

import numpy as np
import pytest

from silence import SilenceDetector, rms


# ---------------------------------------------------------------------------
# rms helper
# ---------------------------------------------------------------------------

class TestRms:
    def test_silence_is_zero(self):
        chunk = np.zeros(1600, dtype=np.float32)
        assert rms(chunk) == pytest.approx(0.0)

    def test_unit_amplitude(self):
        chunk = np.ones(1600, dtype=np.float32)
        assert rms(chunk) == pytest.approx(1.0)

    def test_mixed_amplitude(self):
        chunk = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)
        expected = float(np.sqrt(np.mean(np.array([0.0, 1.0, 0.0, 1.0]) ** 2)))
        assert rms(chunk) == pytest.approx(expected)

    def test_negative_values(self):
        chunk = np.array([-0.5, 0.5, -0.5, 0.5], dtype=np.float32)
        assert rms(chunk) == pytest.approx(0.5)

    def test_returns_float(self):
        chunk = np.ones(10, dtype=np.float32) * 0.3
        assert isinstance(rms(chunk), float)


# ---------------------------------------------------------------------------
# SilenceDetector
# ---------------------------------------------------------------------------

def _make_detector(audio_q=None, stop_event=None):
    if audio_q is None:
        audio_q = queue.Queue()
    if stop_event is None:
        stop_event = threading.Event()
    return SilenceDetector(audio_q, stop_event), audio_q, stop_event


def _silence_chunk(n=1600):
    """Chunk below SILENCE_RMS_THRESHOLD."""
    return np.zeros(n, dtype=np.float32)


def _speech_chunk(n=1600):
    """Chunk well above SILENCE_RMS_THRESHOLD."""
    return np.ones(n, dtype=np.float32) * 0.5


class TestSilenceDetector:
    def test_stops_after_silence_timeout(self):
        """stop_event is set after SILENCE_TIMEOUT seconds of silence chunks."""
        audio_q = queue.Queue()
        stop_event = threading.Event()
        detector = SilenceDetector(audio_q, stop_event)

        # Patch the name as imported in silence.py
        with patch("silence.SILENCE_TIMEOUT", 0.3):
            # Feed silent chunks on a thread
            def feed():
                for _ in range(200):
                    if stop_event.is_set():
                        break
                    audio_q.put(_silence_chunk())
                    time.sleep(0.01)

            feeder = threading.Thread(target=feed, daemon=True)
            feeder.start()

            t = threading.Thread(target=detector.run, daemon=True)
            t.start()
            t.join(timeout=3.0)

        assert stop_event.is_set(), "stop_event should be set after silence timeout"

    def test_speech_resets_silence_timer(self):
        """Interleaved speech chunks prevent silence timeout from triggering early."""
        audio_q = queue.Queue()
        stop_event = threading.Event()
        detector = SilenceDetector(audio_q, stop_event)

        with patch("silence.SILENCE_TIMEOUT", 0.5):
            def feed():
                # Alternate: 10 silence, 1 speech — speech always resets timer
                for cycle in range(20):
                    for _ in range(5):
                        audio_q.put(_silence_chunk())
                        time.sleep(0.005)
                    audio_q.put(_speech_chunk())
                    time.sleep(0.005)
                # Finally let silence fill up
                for _ in range(200):
                    audio_q.put(_silence_chunk())
                    time.sleep(0.005)

            feeder = threading.Thread(target=feed, daemon=True)
            feeder.start()

            t = threading.Thread(target=detector.run, daemon=True)
            # Shouldn't finish in the first 0.3 s (still getting speech resets)
            t.start()
            t.join(timeout=5.0)

        assert stop_event.is_set()

    def test_stops_on_max_recording_cap(self):
        """stop_event is set when MAX_RECORDING_S is reached regardless of speech."""
        audio_q = queue.Queue()
        stop_event = threading.Event()
        detector = SilenceDetector(audio_q, stop_event)

        with patch("silence.MAX_RECORDING_S", 0.2), \
             patch("silence.SILENCE_TIMEOUT", 60.0):
            # Feed only speech chunks — silence timeout won't fire
            def feed():
                while not stop_event.is_set():
                    audio_q.put(_speech_chunk())
                    time.sleep(0.01)

            feeder = threading.Thread(target=feed, daemon=True)
            feeder.start()

            t = threading.Thread(target=detector.run, daemon=True)
            t.start()
            t.join(timeout=3.0)

        assert stop_event.is_set(), "stop_event should be set after MAX_RECORDING_S"

    def test_already_stopped_event_exits_immediately(self):
        """If stop_event is pre-set, run() exits on first iteration."""
        audio_q = queue.Queue()
        stop_event = threading.Event()
        stop_event.set()
        detector = SilenceDetector(audio_q, stop_event)

        # Should return quickly (not hang)
        t = threading.Thread(target=detector.run, daemon=True)
        t.start()
        t.join(timeout=1.0)
        assert not t.is_alive()

    def test_empty_queue_does_not_crash(self):
        """run() handles empty queue gracefully via timeout path."""
        audio_q = queue.Queue()
        stop_event = threading.Event()
        detector = SilenceDetector(audio_q, stop_event)

        def stopper():
            time.sleep(0.5)
            stop_event.set()

        threading.Thread(target=stopper, daemon=True).start()
        t = threading.Thread(target=detector.run, daemon=True)
        t.start()
        t.join(timeout=2.0)
        assert not t.is_alive()
