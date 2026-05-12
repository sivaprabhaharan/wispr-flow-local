"""Tests for transcriber.py — model loading and transcription."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from transcriber import Transcriber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_whisper_model(segments=None):
    """Return a mock WhisperModel whose transcribe() yields ``segments``."""
    if segments is None:
        segments = []
    mock_model = MagicMock()
    # faster_whisper returns (segments_generator, info); segments are objects with .text
    def make_segment(text):
        s = MagicMock()
        s.text = text
        return s
    mock_model.transcribe.return_value = (
        [make_segment(t) for t in segments],
        MagicMock(),
    )
    return mock_model


# ---------------------------------------------------------------------------
# load_model
# ---------------------------------------------------------------------------

class TestTranscriberLoadModel:
    def test_load_model_calls_whisper_model(self, tmp_path):
        """load_model() instantiates WhisperModel with the correct path or name."""
        t = Transcriber()
        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_cls)}):
            # Patch Path.exists to return True so local path is used
            with patch("pathlib.Path.exists", return_value=True):
                t.load_model()
        mock_cls.assert_called_once()

    def test_load_model_falls_back_to_name_when_path_missing(self):
        t = Transcriber()
        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_cls)}):
            with patch("pathlib.Path.exists", return_value=False):
                t.load_model()
        # Model name (not path) should be passed when local dir missing
        call_args = mock_cls.call_args
        import config
        assert call_args[0][0] == config.WHISPER_MODEL

    def test_load_model_uses_config_device_and_compute(self):
        import config
        t = Transcriber()
        mock_cls = MagicMock()
        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_cls)}):
            with patch("pathlib.Path.exists", return_value=True):
                t.load_model()
        call_kwargs = mock_cls.call_args.kwargs
        assert call_kwargs.get("device") == config.WHISPER_DEVICE
        assert call_kwargs.get("compute_type") == config.WHISPER_COMPUTE

    def test_load_model_uses_model_dir_from_config(self):
        """load_model() builds path using config.MODEL_DIR (not hardcoded 'models')."""
        import config
        t = Transcriber()
        mock_cls = MagicMock()
        captured_path = []
        def capture(*args, **kwargs):
            captured_path.append(args[0])
            return MagicMock()
        mock_cls.side_effect = capture
        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_cls)}):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("transcriber.MODEL_DIR", "custom_models"):
                    t.load_model()
        assert "custom_models" in captured_path[0]


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------

class TestTranscriberTranscribe:
    def test_transcribe_raises_if_model_not_loaded(self):
        t = Transcriber()
        audio = np.zeros(1600, dtype=np.float32)
        with pytest.raises(RuntimeError, match="Model not loaded"):
            t.transcribe(audio)

    def test_transcribe_empty_audio_returns_empty_string(self):
        t = Transcriber()
        t._model = _mock_whisper_model(segments=["Hello"])
        result = t.transcribe(np.zeros(0, dtype=np.float32))
        assert result == ""

    def test_transcribe_joins_segment_texts(self):
        t = Transcriber()
        t._model = _mock_whisper_model(segments=["Hello", "world"])
        audio = np.ones(1600, dtype=np.float32) * 0.1
        result = t.transcribe(audio)
        assert result == "Hello world"

    def test_transcribe_single_segment(self):
        t = Transcriber()
        t._model = _mock_whisper_model(segments=["The quick brown fox."])
        audio = np.ones(1600, dtype=np.float32) * 0.1
        result = t.transcribe(audio)
        assert result == "The quick brown fox."

    def test_transcribe_no_segments_returns_empty(self):
        t = Transcriber()
        t._model = _mock_whisper_model(segments=[])
        audio = np.ones(1600, dtype=np.float32) * 0.1
        result = t.transcribe(audio)
        assert result == ""

    def test_transcribe_strips_segment_whitespace(self):
        t = Transcriber()
        t._model = _mock_whisper_model(segments=["  Hello  ", "  world  "])
        audio = np.ones(1600, dtype=np.float32) * 0.1
        result = t.transcribe(audio)
        assert result == "Hello world"

    def test_transcribe_passes_correct_params(self):
        t = Transcriber()
        t._model = _mock_whisper_model()
        audio = np.ones(1600, dtype=np.float32) * 0.1
        t.transcribe(audio)
        call_kwargs = t._model.transcribe.call_args.kwargs
        assert call_kwargs.get("language") == "en"
        assert call_kwargs.get("beam_size") == 5
        assert call_kwargs.get("vad_filter") is False
