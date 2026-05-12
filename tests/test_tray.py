"""Tests for tray.py — TrayIcon update_state, notify, start, stop."""

import sys
import threading
from unittest.mock import MagicMock, patch, call

import pytest

from state import AppState


# ---------------------------------------------------------------------------
# TrayIcon factory — relies on conftest.py sys.modules mocks for pystray/PIL
# ---------------------------------------------------------------------------

def _make_tray_icon(on_quit=None):
    """Instantiate TrayIcon using the conftest-mocked pystray and PIL."""
    if on_quit is None:
        on_quit = MagicMock()
    from tray import TrayIcon
    tray = TrayIcon(on_quit=on_quit)
    return tray, tray._tray, on_quit


# ---------------------------------------------------------------------------
# update_state
# ---------------------------------------------------------------------------

class TestUpdateState:
    def test_update_state_idle_sets_icon(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.IDLE)
        assert mock_tray.icon == tray._icons[AppState.IDLE]

    def test_update_state_recording_sets_icon(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.RECORDING)
        assert mock_tray.icon == tray._icons[AppState.RECORDING]

    def test_update_state_processing_sets_icon(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.PROCESSING)
        assert mock_tray.icon == tray._icons[AppState.PROCESSING]

    def test_update_state_sets_title_idle(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.IDLE)
        assert "idle" in mock_tray.title

    def test_update_state_sets_title_recording(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.RECORDING)
        assert "recording" in mock_tray.title

    def test_update_state_sets_title_processing(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.update_state(AppState.PROCESSING)
        assert "processing" in mock_tray.title

    def test_update_state_updates_current_state(self):
        tray, _, _ = _make_tray_icon()
        tray.update_state(AppState.RECORDING)
        assert tray._current_state == AppState.RECORDING


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------

class TestNotify:
    def test_notify_calls_tray_notify(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.notify("Title", "Message body")
        mock_tray.notify.assert_called_once_with("Message body", "Title")

    def test_notify_does_not_raise_on_exception(self):
        tray, mock_tray, _ = _make_tray_icon()
        mock_tray.notify.side_effect = Exception("pystray notify failed")
        # Should not propagate
        tray.notify("Oops", "Something failed")


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

class TestStart:
    def test_start_spawns_daemon_thread(self):
        tray, mock_tray, _ = _make_tray_icon()
        mock_tray.run = lambda: None  # runs and exits immediately
        tray.start()
        # Give thread a moment to spawn
        import time
        time.sleep(0.05)

    def test_start_calls_tray_run(self):
        tray, mock_tray, _ = _make_tray_icon()
        run_called = threading.Event()
        def fake_run():
            run_called.set()
        mock_tray.run = fake_run
        tray.start()
        run_called.wait(timeout=1.0)
        assert run_called.is_set()


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_stop_calls_tray_stop(self):
        tray, mock_tray, _ = _make_tray_icon()
        tray.stop()
        mock_tray.stop.assert_called_once()

    def test_stop_does_not_raise_on_exception(self):
        tray, mock_tray, _ = _make_tray_icon()
        mock_tray.stop.side_effect = Exception("already stopped")
        tray.stop()  # Should not raise


# ---------------------------------------------------------------------------
# _make_icon helper
# ---------------------------------------------------------------------------

class TestMakeIcon:
    def test_make_icon_returns_image(self):
        with patch("tray.Image") as mock_image, \
             patch("tray.ImageDraw") as mock_draw:
            mock_img = MagicMock()
            mock_image.new.return_value = mock_img
            mock_draw.Draw.return_value = MagicMock()
            from tray import _make_icon
            result = _make_icon("#4caf50")
            assert result == mock_img

    def test_make_icon_called_for_each_state(self):
        on_quit = MagicMock()
        with patch("tray._make_icon") as mock_make_icon:
            mock_make_icon.return_value = MagicMock()
            from tray import TrayIcon
            TrayIcon(on_quit=on_quit)
            # Called once per state (IDLE, RECORDING, PROCESSING)
            assert mock_make_icon.call_count == 3
