"""Tests for main.py — App orchestration, state transitions, error handling."""

import queue
import threading
import time
from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

from injector import InjectionError
from state import AppState


# ---------------------------------------------------------------------------
# App factory — fully mocked UI/hardware
# ---------------------------------------------------------------------------

def _make_app():
    """Instantiate App with all hardware/UI dependencies mocked."""
    with patch("main.tk") as mock_tk, \
         patch("main.TrayIcon") as MockTray, \
         patch("main.Overlay") as MockOverlay, \
         patch("main.AudioCapture") as MockAudio, \
         patch("main.Transcriber") as MockTranscriber, \
         patch("main.PostProcessor") as MockPost, \
         patch("main.TextInjector") as MockInjector, \
         patch("main.HotkeyListener") as MockHotkey:

        mock_root = MagicMock()
        mock_tk.Tk.return_value = mock_root

        from main import App
        app = App()

        # Store mocks for assertions
        app._mock_root = mock_root
        app._mock_tray = MockTray.return_value
        app._mock_overlay = MockOverlay.return_value
        app._mock_audio = MockAudio.return_value
        app._mock_transcriber = MockTranscriber.return_value
        app._mock_post = MockPost.return_value
        app._mock_injector = MockInjector.return_value
        app._mock_hotkey = MockHotkey

        # Wire the mocks into the app instance
        app._tray = app._mock_tray
        app._overlay = app._mock_overlay
        app._audio = app._mock_audio
        app._transcriber = app._mock_transcriber
        app._post = app._mock_post
        app._injector = app._mock_injector
        app._root = mock_root

        return app


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestAppInit:
    def test_initial_state_is_idle(self):
        app = _make_app()
        assert app._state.state == AppState.IDLE

    def test_shutdown_event_not_set(self):
        app = _make_app()
        assert not app._shutdown_event.is_set()

    def test_stop_event_not_set(self):
        app = _make_app()
        assert not app._stop_event.is_set()

    def test_has_audio_queue(self):
        app = _make_app()
        assert isinstance(app._audio_q, queue.Queue)

    def test_has_state_queue(self):
        app = _make_app()
        assert isinstance(app._state_q, queue.Queue)


# ---------------------------------------------------------------------------
# _push_state
# ---------------------------------------------------------------------------

class TestPushState:
    def test_push_state_puts_on_state_queue(self):
        app = _make_app()
        app._push_state(AppState.RECORDING)
        assert not app._state_q.empty()
        assert app._state_q.get_nowait() == AppState.RECORDING

    def test_push_state_calls_tray_update(self):
        app = _make_app()
        app._push_state(AppState.RECORDING)
        app._tray.update_state.assert_called_with(AppState.RECORDING)

    def test_push_state_does_not_raise_when_queue_full(self):
        app = _make_app()
        # Fill the queue
        for _ in range(app._state_q.maxsize):
            app._state_q.put_nowait(AppState.IDLE)
        # Should not raise
        app._push_state(AppState.RECORDING)


# ---------------------------------------------------------------------------
# _on_hotkey_press
# ---------------------------------------------------------------------------

class TestOnHotkeyPress:
    def test_transitions_to_recording_from_idle(self):
        app = _make_app()
        app._audio.start = MagicMock()
        app._push_state = MagicMock()
        app._on_hotkey_press()
        assert app._state.state == AppState.RECORDING

    def test_push_recording_state_on_press(self):
        app = _make_app()
        app._audio.start = MagicMock()
        push_calls = []
        app._push_state = lambda s: push_calls.append(s)
        app._on_hotkey_press()
        assert AppState.RECORDING in push_calls

    def test_ignores_press_during_processing(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._state.transition_to_processing()
        app._audio.start = MagicMock()
        app._on_hotkey_press()
        # State should still be PROCESSING
        assert app._state.state == AppState.PROCESSING
        app._audio.start.assert_not_called()

    def test_microphone_error_notifies_tray(self):
        from audio import MicrophoneError
        app = _make_app()
        app._audio.start = MagicMock(side_effect=MicrophoneError("no mic"))
        app._on_hotkey_press()
        app._tray.notify.assert_called()
        assert app._state.state == AppState.IDLE

    def test_microphone_error_resets_state_to_idle(self):
        from audio import MicrophoneError
        app = _make_app()
        app._audio.start = MagicMock(side_effect=MicrophoneError("no mic"))
        app._on_hotkey_press()
        assert app._state.state == AppState.IDLE

    def test_drains_stale_audio_queue(self):
        app = _make_app()
        app._audio.start = MagicMock()
        # Put stale audio data
        app._audio_q.put(np.zeros(100, dtype=np.float32))
        app._audio_q.put(np.zeros(100, dtype=np.float32))
        app._on_hotkey_press()
        # Queue should be drained
        assert app._audio_q.empty()


# ---------------------------------------------------------------------------
# _on_hotkey_release
# ---------------------------------------------------------------------------

class TestOnHotkeyRelease:
    def test_sets_stop_event_during_recording(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._on_hotkey_release()
        assert app._stop_event.is_set()

    def test_ignores_release_when_idle(self):
        app = _make_app()
        app._on_hotkey_release()
        assert not app._stop_event.is_set()

    def test_ignores_release_when_processing(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._state.transition_to_processing()
        app._on_hotkey_release()
        assert not app._stop_event.is_set()


# ---------------------------------------------------------------------------
# _on_recording_stopped
# ---------------------------------------------------------------------------

class TestOnRecordingStopped:
    def test_transitions_to_processing(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._audio.stop = MagicMock(return_value=np.zeros(1600, dtype=np.float32))
        with patch.object(app, "_transcribe_and_inject"):
            app._on_recording_stopped()
            assert app._state.state == AppState.PROCESSING

    def test_shutdown_guard_prevents_processing(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._shutdown_event.set()
        app._audio.stop = MagicMock()
        app._on_recording_stopped()
        # Should return early — state unchanged
        assert app._state.state == AppState.RECORDING
        app._audio.stop.assert_not_called()

    def test_only_acts_during_recording_state(self):
        app = _make_app()
        # State is IDLE (not RECORDING)
        app._audio.stop = MagicMock()
        app._on_recording_stopped()
        app._audio.stop.assert_not_called()

    def test_launches_transcription_thread(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._audio.stop = MagicMock(return_value=np.zeros(1600, dtype=np.float32))
        with patch.object(app, "_transcribe_and_inject"):
            app._on_recording_stopped()
            assert app._transcription_thread is not None


# ---------------------------------------------------------------------------
# _transcribe_and_inject
# ---------------------------------------------------------------------------

class TestTranscribeAndInject:
    def test_transcribes_and_injects_clean_text(self):
        app = _make_app()
        app._transcriber.transcribe.return_value = "hello world"
        app._post.process.return_value = "hello world."
        app._injector.inject.return_value = True
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        app._injector.inject.assert_called_once_with("hello world.")

    def test_empty_transcript_skips_injection(self):
        app = _make_app()
        app._transcriber.transcribe.return_value = ""
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        app._injector.inject.assert_not_called()

    def test_injection_error_triggers_tray_notification(self):
        app = _make_app()
        app._transcriber.transcribe.return_value = "hello"
        app._post.process.return_value = "hello."
        app._injector.inject.side_effect = InjectionError("both paths failed")
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        app._tray.notify.assert_called()
        notify_args = app._tray.notify.call_args[0]
        assert "read-only" in notify_args[1].lower() or "could not" in notify_args[1].lower()

    def test_transcription_error_triggers_tray_notification(self):
        app = _make_app()
        app._transcriber.transcribe.side_effect = RuntimeError("transcription crashed")
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        app._tray.notify.assert_called()

    def test_always_transitions_to_idle_after_success(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._state.transition_to_processing()
        app._transcriber.transcribe.return_value = "hi"
        app._post.process.return_value = "hi."
        app._injector.inject.return_value = True
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        assert app._state.state == AppState.IDLE

    def test_always_transitions_to_idle_after_error(self):
        app = _make_app()
        app._state.transition_to_recording()
        app._state.transition_to_processing()
        app._transcriber.transcribe.side_effect = RuntimeError("crash")
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        assert app._state.state == AppState.IDLE

    def test_clipboard_fallback_logs_but_does_not_notify(self):
        app = _make_app()
        app._transcriber.transcribe.return_value = "hello"
        app._post.process.return_value = "hello."
        # inject returns False = clipboard fallback used (no InjectionError)
        app._injector.inject.return_value = False
        app._transcribe_and_inject(np.zeros(1600, dtype=np.float32))
        # Tray notify should NOT be called for clipboard fallback
        app._tray.notify.assert_not_called()


# ---------------------------------------------------------------------------
# _quit
# ---------------------------------------------------------------------------

class TestQuit:
    def test_quit_sets_stop_event(self):
        app = _make_app()
        app._hotkey = MagicMock()
        app._quit()
        assert app._stop_event.is_set()

    def test_quit_sets_shutdown_event(self):
        app = _make_app()
        app._hotkey = MagicMock()
        app._quit()
        assert app._shutdown_event.is_set()

    def test_quit_stops_hotkey(self):
        app = _make_app()
        mock_hotkey = MagicMock()
        app._hotkey = mock_hotkey
        app._quit()
        mock_hotkey.stop.assert_called_once()

    def test_quit_stops_tray(self):
        app = _make_app()
        app._hotkey = MagicMock()
        app._quit()
        app._tray.stop.assert_called()

    def test_quit_schedules_root_destroy(self):
        app = _make_app()
        app._hotkey = MagicMock()
        app._quit()
        app._root.after.assert_called()

    def test_quit_handles_none_hotkey(self):
        app = _make_app()
        app._hotkey = None
        # Should not raise
        app._quit()
