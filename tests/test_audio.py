"""Tests for audio.py — AudioCapture start/stop, callbacks, MicrophoneError."""

import queue
import threading
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

# sounddevice is already mocked in conftest.py before this import
import sounddevice as sd
from audio import AudioCapture, MicrophoneError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_capture(q=None):
    if q is None:
        q = queue.Queue()
    return AudioCapture(q), q


# ---------------------------------------------------------------------------
# start()
# ---------------------------------------------------------------------------

class TestAudioCaptureStart:
    def test_start_opens_inputstream(self, sd_mock):
        cap, _ = _make_capture()
        cap.start()
        assert sd_mock.InputStream.called

    def test_start_calls_stream_start(self, sd_mock):
        cap, _ = _make_capture()
        cap.start()
        sd_mock.InputStream.return_value.start.assert_called()

    def test_start_clears_chunks(self, sd_mock):
        cap, _ = _make_capture()
        # Prime with a fake chunk
        cap._chunks.append(np.ones(10, dtype=np.float32))
        cap.start()
        assert cap._chunks == []

    def test_start_raises_microphone_error_on_port_audio_error(self, sd_mock):
        sd_mock.InputStream.side_effect = sd_mock.PortAudioError("no mic")
        cap, _ = _make_capture()
        with pytest.raises(MicrophoneError):
            cap.start()
        # Restore side_effect for subsequent tests
        sd_mock.InputStream.side_effect = None
        sd_mock.InputStream.return_value = MagicMock()

    def test_start_configures_correct_sample_rate(self, sd_mock):
        import config
        cap, _ = _make_capture()
        cap.start()
        _, kwargs = sd_mock.InputStream.call_args
        assert kwargs.get("samplerate") == config.SAMPLE_RATE or \
               sd_mock.InputStream.call_args[1].get("samplerate") == config.SAMPLE_RATE or \
               sd_mock.InputStream.call_args[0][0] == config.SAMPLE_RATE or True
        # Verify via keyword
        call_kwargs = sd_mock.InputStream.call_args.kwargs
        assert call_kwargs["samplerate"] == config.SAMPLE_RATE

    def test_start_configures_mono(self, sd_mock):
        import config
        cap, _ = _make_capture()
        cap.start()
        call_kwargs = sd_mock.InputStream.call_args.kwargs
        assert call_kwargs["channels"] == config.CHANNELS


# ---------------------------------------------------------------------------
# stop()
# ---------------------------------------------------------------------------

class TestAudioCaptureStop:
    def test_stop_returns_zeros_when_no_chunks(self):
        cap, _ = _make_capture()
        result = cap.stop()
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32
        assert len(result) == 0

    def test_stop_concatenates_chunks(self, sd_mock):
        cap, _ = _make_capture()
        cap.start()
        cap._chunks = [
            np.array([1.0, 2.0], dtype=np.float32),
            np.array([3.0, 4.0], dtype=np.float32),
        ]
        result = cap.stop()
        np.testing.assert_array_equal(result, [1.0, 2.0, 3.0, 4.0])

    def test_stop_closes_stream(self, sd_mock):
        cap, _ = _make_capture()
        cap.start()
        mock_stream = sd_mock.InputStream.return_value
        cap.stop()
        mock_stream.stop.assert_called()
        mock_stream.close.assert_called()

    def test_stop_without_start_returns_zeros(self):
        cap, _ = _make_capture()
        result = cap.stop()
        assert isinstance(result, np.ndarray)
        assert len(result) == 0

    def test_stop_sets_stopped_event(self, sd_mock):
        cap, _ = _make_capture()
        cap.start()
        cap.stop()
        assert cap._stopped.is_set()


# ---------------------------------------------------------------------------
# _callback()
# ---------------------------------------------------------------------------

class TestAudioCaptureCallback:
    def test_callback_appends_chunk(self, sd_mock):
        cap, q = _make_capture()
        indata = np.ones((1600, 1), dtype=np.float32) * 0.3
        cap._callback(indata, 1600, None, sd_mock.CallbackFlags())
        assert len(cap._chunks) == 1
        np.testing.assert_array_almost_equal(cap._chunks[0], indata[:, 0])

    def test_callback_puts_chunk_on_queue(self, sd_mock):
        cap, q = _make_capture()
        indata = np.ones((100, 1), dtype=np.float32) * 0.7
        cap._callback(indata, 100, None, sd_mock.CallbackFlags())
        assert not q.empty()
        chunk = q.get_nowait()
        np.testing.assert_array_almost_equal(chunk, indata[:, 0])

    def test_callback_flattens_to_1d(self, sd_mock):
        cap, q = _make_capture()
        indata = np.ones((800, 1), dtype=np.float32)
        cap._callback(indata, 800, None, sd_mock.CallbackFlags())
        assert cap._chunks[0].ndim == 1

    def test_callback_drops_when_queue_full(self, sd_mock):
        small_q = queue.Queue(maxsize=1)
        cap = AudioCapture(small_q)
        indata = np.ones((100, 1), dtype=np.float32)
        # Fill queue first
        small_q.put(np.zeros(100, dtype=np.float32))
        # This should not raise even though queue is full
        cap._callback(indata, 100, None, sd_mock.CallbackFlags())
        assert small_q.qsize() == 1  # queue still has one item, not raised
