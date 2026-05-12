"""Tests for config.py — constant types and values."""

import config


def test_hotkey_is_string():
    assert isinstance(config.HOTKEY, str)
    assert config.HOTKEY  # non-empty


def test_sample_rate():
    assert config.SAMPLE_RATE == 16_000


def test_channels_mono():
    assert config.CHANNELS == 1


def test_chunk_duration_positive():
    assert isinstance(config.CHUNK_DURATION, float)
    assert config.CHUNK_DURATION > 0


def test_silence_timeout_positive():
    assert isinstance(config.SILENCE_TIMEOUT, float)
    assert config.SILENCE_TIMEOUT > 0


def test_silence_rms_threshold_positive():
    assert isinstance(config.SILENCE_RMS_THRESHOLD, float)
    assert config.SILENCE_RMS_THRESHOLD > 0


def test_max_recording_positive():
    assert isinstance(config.MAX_RECORDING_S, int)
    assert config.MAX_RECORDING_S > 0


def test_max_recording_exceeds_silence_timeout():
    assert config.MAX_RECORDING_S > config.SILENCE_TIMEOUT


def test_whisper_model_is_string():
    assert isinstance(config.WHISPER_MODEL, str)
    assert config.WHISPER_MODEL


def test_whisper_device_is_string():
    assert isinstance(config.WHISPER_DEVICE, str)


def test_whisper_compute_is_string():
    assert isinstance(config.WHISPER_COMPUTE, str)


def test_filler_words_is_set():
    assert isinstance(config.FILLER_WORDS, set)
    assert len(config.FILLER_WORDS) > 0


def test_filler_words_are_lowercase():
    for word in config.FILLER_WORDS:
        assert word == word.lower(), f"Filler word {word!r} is not lowercase"


def test_overlay_position_is_string():
    assert isinstance(config.OVERLAY_POSITION, str)


def test_overlay_margin_positive():
    assert isinstance(config.OVERLAY_MARGIN, int)
    assert config.OVERLAY_MARGIN >= 0


def test_model_dir_is_string():
    assert isinstance(config.MODEL_DIR, str)
    assert config.MODEL_DIR
