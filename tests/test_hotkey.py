"""Tests for hotkey.py — _PressReleaseListener state machine and HotkeyListener."""

import sys
import threading
from unittest.mock import MagicMock, patch, call

import pytest

# pynput is mocked in conftest.py; import keyboard mock
import pynput.keyboard as keyboard_mock

from hotkey import HotkeyListener, HotkeyRegistrationError, _PressReleaseListener


# ---------------------------------------------------------------------------
# _PressReleaseListener — internal press/release state machine
# ---------------------------------------------------------------------------

class TestPressReleaseListener:
    """Tests for _PressReleaseListener using the mocked keyboard module."""

    def setup_method(self):
        self.on_press_cb = MagicMock()
        self.on_release_cb = MagicMock()
        # Patch keyboard.Listener to avoid actual input hook
        with patch("hotkey.keyboard.Listener"):
            self.listener = _PressReleaseListener(
                hotkey_str="<alt>+<space>",
                on_press_cb=self.on_press_cb,
                on_release_cb=self.on_release_cb,
            )

    def _press_alt(self):
        self.listener._on_press(keyboard_mock.Key.alt)

    def _press_space(self):
        self.listener._on_press(keyboard_mock.Key.space)

    def _release_alt(self):
        self.listener._on_release(keyboard_mock.Key.alt)

    def _release_space(self):
        self.listener._on_release(keyboard_mock.Key.space)

    def test_alt_then_space_triggers_on_press(self):
        self._press_alt()
        self._press_space()
        self.on_press_cb.assert_called_once()

    def test_space_without_alt_does_not_trigger(self):
        self._press_space()
        self.on_press_cb.assert_not_called()

    def test_alt_without_space_does_not_trigger(self):
        self._press_alt()
        self.on_press_cb.assert_not_called()

    def test_trigger_only_fires_once_while_held(self):
        self._press_alt()
        self._press_space()
        # Simulate key repeat (press again while held)
        self._press_alt()
        self._press_space()
        self.on_press_cb.assert_called_once()

    def test_release_alt_fires_on_release_cb(self):
        self._press_alt()
        self._press_space()
        self._release_alt()
        self.on_release_cb.assert_called_once()

    def test_release_space_fires_on_release_cb(self):
        self._press_alt()
        self._press_space()
        self._release_space()
        self.on_release_cb.assert_called_once()

    def test_on_release_not_called_if_never_triggered(self):
        self._release_alt()
        self.on_release_cb.assert_not_called()

    def test_alt_l_triggers_hotkey(self):
        self.listener._on_press(keyboard_mock.Key.alt_l)
        self._press_space()
        self.on_press_cb.assert_called_once()

    def test_alt_r_triggers_hotkey(self):
        self.listener._on_press(keyboard_mock.Key.alt_r)
        self._press_space()
        self.on_press_cb.assert_called_once()

    def test_triggered_resets_after_release_so_second_press_works(self):
        # First activation
        self._press_alt()
        self._press_space()
        self.on_press_cb.assert_called_once()
        # Release
        self._release_alt()
        self.on_release_cb.assert_called_once()
        # Second activation
        self._press_alt()
        self._press_space()
        assert self.on_press_cb.call_count == 2

    def test_exception_in_press_cb_does_not_propagate(self):
        self.on_press_cb.side_effect = RuntimeError("boom")
        # Should not raise
        self._press_alt()
        self._press_space()

    def test_exception_in_release_cb_does_not_propagate(self):
        self.on_release_cb.side_effect = RuntimeError("boom")
        self._press_alt()
        self._press_space()
        # Should not raise
        self._release_space()


# ---------------------------------------------------------------------------
# HotkeyListener
# ---------------------------------------------------------------------------

class TestHotkeyListener:
    def test_start_spawns_daemon_thread(self):
        on_press = MagicMock()
        on_release = MagicMock()

        with patch("hotkey.keyboard.Listener"), \
             patch("hotkey._PressReleaseListener") as MockPRL:
            MockPRL.return_value.run = MagicMock()  # run does nothing
            listener = HotkeyListener(on_press=on_press, on_release=on_release)
            listener.start()
            assert listener._thread is not None
            assert listener._thread.daemon is True

    def test_start_raises_hotkey_registration_error_on_exception(self):
        on_press = MagicMock()
        on_release = MagicMock()

        with patch("hotkey._PressReleaseListener", side_effect=Exception("fail")):
            listener = HotkeyListener(on_press=on_press, on_release=on_release)
            with pytest.raises(HotkeyRegistrationError):
                listener.start()

    def test_stop_joins_thread(self):
        on_press = MagicMock()
        on_release = MagicMock()

        with patch("hotkey.keyboard.Listener"), \
             patch("hotkey._PressReleaseListener") as MockPRL:
            # Make run() exit immediately
            MockPRL.return_value.run = lambda: None
            MockPRL.return_value.stop = MagicMock()
            listener = HotkeyListener(on_press=on_press, on_release=on_release)
            listener.start()
            listener.stop()
            assert listener._thread is None
            assert listener._listener is None
