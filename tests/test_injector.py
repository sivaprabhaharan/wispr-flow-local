"""Tests for injector.py — TextInjector SendInput, clipboard fallback, InjectionError."""

import ctypes
import sys
from unittest.mock import MagicMock, patch, call

import pytest

from injector import InjectionError, INPUT, TextInjector


# ---------------------------------------------------------------------------
# Struct layout
# ---------------------------------------------------------------------------

class TestInputStructSize:
    def test_input_struct_is_40_bytes(self):
        """ctypes.sizeof(INPUT) must equal 40 — Windows requires this on 64-bit.

        Without padding _INPUT_UNION to MOUSEINPUT's 32 bytes, ctypes reports 32
        and SendInput rejects every call (returns 0).
        """
        assert ctypes.sizeof(INPUT) == 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_injector():
    return TextInjector()


def _patch_send_input_success(injector):
    """Patch _send_input to always return True."""
    injector._send_input = MagicMock(return_value=True)


def _patch_send_input_fail(injector):
    """Patch _send_input to always return False."""
    injector._send_input = MagicMock(return_value=False)


def _patch_clipboard_paste_success(injector):
    injector._clipboard_paste = MagicMock(return_value=True)


def _patch_clipboard_paste_fail(injector):
    injector._clipboard_paste = MagicMock(return_value=False)


# ---------------------------------------------------------------------------
# inject() — high level
# ---------------------------------------------------------------------------

class TestInject:
    def test_empty_text_returns_true_without_any_input(self):
        inj = _make_injector()
        inj._send_input = MagicMock()
        result = inj.inject("")
        assert result is True
        inj._send_input.assert_not_called()

    def test_send_input_success_returns_true(self):
        inj = _make_injector()
        _patch_send_input_success(inj)
        result = inj.inject("hello")
        assert result is True

    def test_send_input_fail_uses_clipboard_fallback(self):
        inj = _make_injector()
        _patch_send_input_fail(inj)
        _patch_clipboard_paste_success(inj)
        result = inj.inject("hello")
        assert result is False
        inj._clipboard_paste.assert_called_once_with("hello")

    def test_both_fail_raises_injection_error(self):
        inj = _make_injector()
        _patch_send_input_fail(inj)
        _patch_clipboard_paste_fail(inj)
        with pytest.raises(InjectionError):
            inj.inject("hello")

    def test_send_input_success_does_not_call_clipboard(self):
        inj = _make_injector()
        _patch_send_input_success(inj)
        inj._clipboard_paste = MagicMock()
        inj.inject("hello")
        inj._clipboard_paste.assert_not_called()


# ---------------------------------------------------------------------------
# _send_input() — Windows SendInput path
# ---------------------------------------------------------------------------

class TestSendInput:
    def test_send_input_returns_false_when_windll_unavailable(self):
        inj = _make_injector()
        with patch.object(ctypes, "windll", None, create=True):
            # Should return False, not raise
            result = inj._send_input("hello")
            assert result is False

    def test_send_input_returns_false_on_exception(self):
        inj = _make_injector()
        with patch("ctypes.windll") as mock_windll:
            mock_windll.user32.SendInput.side_effect = OSError("access denied")
            result = inj._send_input("hello")
            assert result is False

    def test_send_input_success_when_windll_returns_correct_count(self):
        inj = _make_injector()
        with patch("ctypes.windll") as mock_windll:
            # For "hi" (2 chars × 2 events each = 4 inputs)
            mock_windll.user32.SendInput.return_value = 4
            result = inj._send_input("hi")
            assert result is True

    def test_send_input_true_when_sendinput_returns_n(self):
        """_send_input must return True when SendInput returns exactly n inputs sent."""
        inj = _make_injector()
        with patch("ctypes.windll") as mock_windll:
            # Single char → 2 events (key-down + key-up)
            mock_windll.user32.SendInput.return_value = 2
            result = inj._send_input("a")
            assert result is True

    def test_send_input_failure_when_windll_returns_wrong_count(self):
        inj = _make_injector()
        with patch("ctypes.windll") as mock_windll:
            mock_windll.user32.SendInput.return_value = 0
            result = inj._send_input("hi")
            assert result is False


# ---------------------------------------------------------------------------
# _clipboard_paste() — clipboard fallback
# ---------------------------------------------------------------------------

class TestClipboardPaste:
    def test_clipboard_paste_copies_text_then_restores(self, pyperclip_mock):
        pyperclip_mock.paste.return_value = "original"
        pyperclip_mock.copy.reset_mock()

        inj = _make_injector()
        inj._send_ctrl_v = MagicMock()

        inj._clipboard_paste("new text")

        # Should copy new text, then restore original
        calls = pyperclip_mock.copy.call_args_list
        assert calls[0] == call("new text")
        assert calls[-1] == call("original")

    def test_clipboard_paste_restores_even_on_ctrl_v_error(self, pyperclip_mock):
        pyperclip_mock.paste.return_value = "original"
        pyperclip_mock.copy.reset_mock()

        inj = _make_injector()
        inj._send_ctrl_v = MagicMock(side_effect=RuntimeError("ctrl+v failed"))

        inj._clipboard_paste("new text")

        # Restore must still happen (finally block)
        calls = pyperclip_mock.copy.call_args_list
        restore_calls = [c for c in calls if c == call("original")]
        assert len(restore_calls) >= 1, "Clipboard should be restored even on error"

    def test_clipboard_paste_returns_true_on_success(self, pyperclip_mock):
        inj = _make_injector()
        inj._send_ctrl_v = MagicMock()
        result = inj._clipboard_paste("hello")
        assert result is True

    def test_clipboard_paste_returns_false_on_exception(self, pyperclip_mock):
        """Returns False when pyperclip.copy(text) itself raises (before success=True)."""
        inj = _make_injector()
        inj._send_ctrl_v = MagicMock()

        # copy(text) raises immediately so success is never set to True
        def copy_raiser(text):
            if text == "hello":
                raise RuntimeError("copy write failed")
        pyperclip_mock.copy.side_effect = copy_raiser
        result = inj._clipboard_paste("hello")
        assert result is False
        pyperclip_mock.copy.side_effect = None

    def test_clipboard_paste_handles_pyperclip_paste_error(self, pyperclip_mock):
        pyperclip_mock.paste.side_effect = RuntimeError("no clipboard")
        inj = _make_injector()
        inj._send_ctrl_v = MagicMock()
        # Should not raise — previous clipboard defaults to ""
        result = inj._clipboard_paste("hello")
        pyperclip_mock.paste.side_effect = None
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# InjectionError
# ---------------------------------------------------------------------------

class TestInjectionError:
    def test_is_exception(self):
        assert issubclass(InjectionError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(InjectionError):
            raise InjectionError("test")
