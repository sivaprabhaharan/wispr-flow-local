"""Shared fixtures and global mocks for Wispr Flow Local tests.

All hardware/platform dependencies (sounddevice, pynput, pyperclip, pystray,
PIL, faster_whisper, ctypes.windll) are mocked at module-import time so the
test suite runs on any OS without physical hardware.
"""

import ctypes
import queue
import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so tests can import source modules.
# ---------------------------------------------------------------------------
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Stub Windows-only ctypes.windll on non-Windows platforms.
# ---------------------------------------------------------------------------
if not hasattr(ctypes, "windll"):
    ctypes.windll = MagicMock()
    # SendInput: return value equal to number of inputs requested by default
    ctypes.windll.user32 = MagicMock()

# ---------------------------------------------------------------------------
# sounddevice — mock before any project module imports it.
# ---------------------------------------------------------------------------
_sd_mock = MagicMock()
_sd_mock.PortAudioError = type("PortAudioError", (Exception,), {})
# InputStream returns a mock stream that can be started/stopped
_mock_stream = MagicMock()
_sd_mock.InputStream.return_value = _mock_stream
sys.modules.setdefault("sounddevice", _sd_mock)

# ---------------------------------------------------------------------------
# pyperclip
# ---------------------------------------------------------------------------
_pyperclip_mock = MagicMock()
_pyperclip_mock.paste.return_value = "previous_clipboard"
sys.modules.setdefault("pyperclip", _pyperclip_mock)

# ---------------------------------------------------------------------------
# pynput
# ---------------------------------------------------------------------------
_pynput_mock = MagicMock()
_keyboard_mock = MagicMock()
# Concrete Key values used in hotkey.py comparisons
_keyboard_mock.Key.ctrl = "ctrl"
_keyboard_mock.Key.ctrl_l = "ctrl_l"
_keyboard_mock.Key.ctrl_r = "ctrl_r"
_keyboard_mock.Key.alt = "alt"
_keyboard_mock.Key.alt_l = "alt_l"
_keyboard_mock.Key.alt_r = "alt_r"
_keyboard_mock.Key.space = "space"
_keyboard_mock.Key.shift = "shift"
_keyboard_mock.Key.shift_l = "shift_l"
_keyboard_mock.Key.shift_r = "shift_r"
_keyboard_mock.Key.cmd = "cmd"
_keyboard_mock.Key.cmd_l = "cmd_l"
_keyboard_mock.Key.cmd_r = "cmd_r"
sys.modules.setdefault("pynput", _pynput_mock)
sys.modules.setdefault("pynput.keyboard", _keyboard_mock)

# ---------------------------------------------------------------------------
# PIL / Pillow
# ---------------------------------------------------------------------------
_pil_mock = types.ModuleType("PIL")
_pil_image_mock = MagicMock()
_pil_imagedraw_mock = MagicMock()
_pil_mock.Image = _pil_image_mock
_pil_mock.ImageDraw = _pil_imagedraw_mock
sys.modules.setdefault("PIL", _pil_mock)
sys.modules.setdefault("PIL.Image", _pil_image_mock)
sys.modules.setdefault("PIL.ImageDraw", _pil_imagedraw_mock)

# ---------------------------------------------------------------------------
# pystray
# ---------------------------------------------------------------------------
_pystray_mock = MagicMock()
_pystray_mock.Icon = MagicMock()
_pystray_mock.Menu = MagicMock()
_pystray_mock.MenuItem = MagicMock()
sys.modules.setdefault("pystray", _pystray_mock)

# ---------------------------------------------------------------------------
# faster_whisper
# ---------------------------------------------------------------------------
_faster_whisper_mock = MagicMock()
sys.modules.setdefault("faster_whisper", _faster_whisper_mock)

# ---------------------------------------------------------------------------
# tkinter — mock it entirely so overlay/main can import without a display.
# ---------------------------------------------------------------------------
try:
    import tkinter as _real_tk  # noqa: F401
except ModuleNotFoundError:
    _real_tk = None  # headless CI without tkinter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def audio_queue() -> queue.Queue:
    return queue.Queue()


@pytest.fixture()
def stop_event() -> threading.Event:
    return threading.Event()


@pytest.fixture()
def float32_silence() -> np.ndarray:
    """1600 samples of pure silence (float32 zeros)."""
    return np.zeros(1600, dtype=np.float32)


@pytest.fixture()
def float32_speech() -> np.ndarray:
    """1600 samples of high-energy audio (simulates speech)."""
    return np.ones(1600, dtype=np.float32) * 0.5


@pytest.fixture()
def sd_mock():
    """Return the module-level sounddevice mock."""
    return sys.modules["sounddevice"]


@pytest.fixture()
def pyperclip_mock():
    """Return the module-level pyperclip mock."""
    return sys.modules["pyperclip"]
