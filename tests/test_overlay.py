"""Tests for overlay.py — state polling, show/hide, pulse animation."""

import queue
import threading
import time
from unittest.mock import MagicMock, patch, call

import pytest

from state import AppState


# ---------------------------------------------------------------------------
# We need a mock tkinter root to avoid requiring a display.
# ---------------------------------------------------------------------------

def _make_overlay():
    """Return an Overlay instance with a fully mocked tkinter root."""
    # Import here so conftest path setup has run first
    with patch("overlay.tk") as mock_tk, \
         patch("overlay.tk.Tk"), \
         patch("overlay.tk.Toplevel"), \
         patch("overlay.tk.Frame"), \
         patch("overlay.tk.Label"), \
         patch("overlay.tk.Canvas"):
        from overlay import Overlay
        mock_root = MagicMock()
        state_q = queue.Queue()
        ov = Overlay(mock_root, state_q)
        return ov, mock_root, state_q


# ---------------------------------------------------------------------------
# _apply_state
# ---------------------------------------------------------------------------

class TestApplyState:
    def test_idle_calls_hide(self):
        ov, root, _ = _make_overlay()
        ov._hide = MagicMock()
        ov._apply_state(AppState.IDLE)
        ov._hide.assert_called_once()

    def test_recording_calls_show_recording(self):
        ov, root, _ = _make_overlay()
        ov._show_recording = MagicMock()
        ov._apply_state(AppState.RECORDING)
        ov._show_recording.assert_called_once()

    def test_processing_calls_show_processing(self):
        ov, root, _ = _make_overlay()
        ov._show_processing = MagicMock()
        ov._apply_state(AppState.PROCESSING)
        ov._show_processing.assert_called_once()


# ---------------------------------------------------------------------------
# _hide
# ---------------------------------------------------------------------------

class TestHide:
    def test_hide_destroys_window(self):
        ov, root, _ = _make_overlay()
        mock_win = MagicMock()
        ov._win = mock_win
        ov._hide()
        mock_win.destroy.assert_called_once()

    def test_hide_sets_win_to_none(self):
        ov, root, _ = _make_overlay()
        ov._win = MagicMock()
        ov._hide()
        assert ov._win is None

    def test_hide_cancels_pulse(self):
        ov, root, _ = _make_overlay()
        ov._cancel_pulse = MagicMock()
        ov._hide()
        ov._cancel_pulse.assert_called_once()

    def test_hide_when_no_window_does_not_raise(self):
        ov, root, _ = _make_overlay()
        ov._win = None
        ov._hide()  # Should not raise


# ---------------------------------------------------------------------------
# _poll
# ---------------------------------------------------------------------------

class TestPoll:
    def test_poll_processes_state_from_queue(self):
        ov, root, state_q = _make_overlay()
        ov._apply_state = MagicMock()
        state_q.put(AppState.RECORDING)
        ov._poll()
        ov._apply_state.assert_called_with(AppState.RECORDING)

    def test_poll_processes_multiple_states(self):
        ov, root, state_q = _make_overlay()
        ov._apply_state = MagicMock()
        state_q.put(AppState.RECORDING)
        state_q.put(AppState.PROCESSING)
        state_q.put(AppState.IDLE)
        ov._poll()
        assert ov._apply_state.call_count == 3

    def test_poll_schedules_next_poll_via_after(self):
        ov, root, state_q = _make_overlay()
        ov._apply_state = MagicMock()
        ov._poll()
        root.after.assert_called()

    def test_poll_empty_queue_does_not_call_apply(self):
        ov, root, state_q = _make_overlay()
        ov._apply_state = MagicMock()
        # Empty queue
        ov._poll()
        ov._apply_state.assert_not_called()


# ---------------------------------------------------------------------------
# _pulse — alpha animation
# ---------------------------------------------------------------------------

class TestPulse:
    def test_pulse_decreases_alpha_when_direction_is_negative(self):
        ov, root, _ = _make_overlay()
        mock_win = MagicMock()
        ov._win = mock_win
        ov._pulse_alpha = 0.85
        ov._pulse_dir = -1
        ov._pulse()
        assert ov._pulse_alpha < 0.85

    def test_pulse_increases_alpha_when_direction_is_positive(self):
        ov, root, _ = _make_overlay()
        mock_win = MagicMock()
        ov._win = mock_win
        ov._pulse_alpha = 0.4
        ov._pulse_dir = 1
        ov._pulse()
        assert ov._pulse_alpha > 0.4

    def test_pulse_reverses_at_lower_bound(self):
        ov, root, _ = _make_overlay()
        mock_win = MagicMock()
        ov._win = mock_win
        ov._pulse_alpha = 0.41  # just above lower bound threshold 0.4
        ov._pulse_dir = -1
        ov._pulse()
        assert ov._pulse_dir == 1  # direction reversed

    def test_pulse_reverses_at_upper_bound(self):
        ov, root, _ = _make_overlay()
        mock_win = MagicMock()
        ov._win = mock_win
        ov._pulse_alpha = 0.94  # just below upper bound threshold 0.95
        ov._pulse_dir = 1
        ov._pulse()
        assert ov._pulse_dir == -1  # direction reversed

    def test_pulse_does_nothing_when_no_window(self):
        ov, root, _ = _make_overlay()
        ov._win = None
        # Should return without doing anything
        ov._pulse()
        root.after.assert_not_called()


# ---------------------------------------------------------------------------
# _cancel_pulse
# ---------------------------------------------------------------------------

class TestCancelPulse:
    def test_cancel_pulse_cancels_scheduled_job(self):
        ov, root, _ = _make_overlay()
        ov._pulse_job = "job_handle"
        ov._cancel_pulse()
        root.after_cancel.assert_called_with("job_handle")

    def test_cancel_pulse_clears_job(self):
        ov, root, _ = _make_overlay()
        ov._pulse_job = "job_handle"
        ov._cancel_pulse()
        assert ov._pulse_job is None

    def test_cancel_pulse_no_op_when_no_job(self):
        ov, root, _ = _make_overlay()
        ov._pulse_job = None
        ov._cancel_pulse()  # Should not raise
        root.after_cancel.assert_not_called()


# ---------------------------------------------------------------------------
# _make_window — focus theft prevention
# ---------------------------------------------------------------------------

class TestMakeWindow:
    def test_make_window_never_calls_focus_set(self):
        ov, root, _ = _make_overlay()
        with patch("overlay.tk.Toplevel") as MockToplevel:
            mock_win = MagicMock()
            MockToplevel.return_value = mock_win
            ov._make_window()
            mock_win.focus_set.assert_not_called()
            mock_win.focus_force.assert_not_called()

    def test_make_window_sets_overrideredirect(self):
        ov, root, _ = _make_overlay()
        with patch("overlay.tk.Toplevel") as MockToplevel:
            mock_win = MagicMock()
            MockToplevel.return_value = mock_win
            ov._make_window()
            mock_win.overrideredirect.assert_called_with(True)

    def test_make_window_sets_topmost(self):
        ov, root, _ = _make_overlay()
        with patch("overlay.tk.Toplevel") as MockToplevel:
            mock_win = MagicMock()
            MockToplevel.return_value = mock_win
            ov._make_window()
            # Check -topmost was set via wm_attributes
            calls = mock_win.wm_attributes.call_args_list
            topmost_set = any("-topmost" in str(c) for c in calls)
            assert topmost_set
