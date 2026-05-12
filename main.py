"""Wispr Flow Local — main orchestrator / entry point.

Runs the tkinter mainloop on the main thread. All other components live on
daemon threads and communicate via queue.Queue and threading.Event.
"""

import logging
import logging.handlers
import pathlib
import queue
import sys
import threading
import tkinter as tk

from audio import AudioCapture, MicrophoneError
from config import MODEL_DIR
from hotkey import HotkeyListener, HotkeyRegistrationError
from injector import TextInjector
from overlay import Overlay
from postprocessor import PostProcessor
from silence import SilenceDetector
from state import AppState, StateManager
from tray import TrayIcon
from transcriber import Transcriber

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    log_dir = pathlib.Path.home() / "AppData" / "Roaming" / "WisprFlowLocal"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wispr.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root_logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root_logger.addHandler(console)


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

class App:
    """Central orchestrator — owns state machine, coordinates all components."""

    def __init__(self) -> None:
        self._state = StateManager()

        # Queues
        self._audio_q: queue.Queue = queue.Queue(maxsize=1000)
        self._state_q: queue.Queue = queue.Queue(maxsize=50)

        # Threading
        self._stop_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._silence_thread: threading.Thread | None = None
        self._transcription_thread: threading.Thread | None = None

        # Components
        self._audio = AudioCapture(self._audio_q)
        self._transcriber = Transcriber()
        self._post = PostProcessor()
        self._injector = TextInjector()
        self._hotkey: HotkeyListener | None = None

        # UI
        self._root = tk.Tk()
        self._root.withdraw()  # hide root window; only overlay and tray are visible
        self._overlay = Overlay(self._root, self._state_q)
        self._tray = TrayIcon(on_quit=self._quit)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the application. Blocks until the user quits."""
        self._tray.start()
        self._overlay.start()

        # Load model on background thread; hotkey enabled after load
        load_thread = threading.Thread(
            target=self._load_model, daemon=True, name="model_load_thread"
        )
        load_thread.start()

        try:
            self._root.mainloop()
        except KeyboardInterrupt:
            self._quit()

    def _load_model(self) -> None:
        try:
            self._transcriber.load_model()
            self._root.after(0, self._on_model_loaded)
        except FileNotFoundError:
            logger.critical("Model files missing — cannot start")
            self._root.after(0, lambda: self._fatal_error(
                "Model files not found. Please reinstall Wispr Flow Local."
            ))
        except Exception:
            logger.exception("Model load failed")
            self._root.after(0, lambda: self._fatal_error(
                "Failed to load Whisper model. Check wispr.log for details."
            ))

    def _on_model_loaded(self) -> None:
        logger.info("Model loaded; activating hotkey")
        self._start_hotkey()
        self._push_state(AppState.IDLE)

    def _start_hotkey(self) -> None:
        self._hotkey = HotkeyListener(
            on_press=self._on_hotkey_press,
            on_release=self._on_hotkey_release,
        )
        try:
            self._hotkey.start()
        except HotkeyRegistrationError as exc:
            logger.error("Hotkey registration failed: %s", exc)
            self._tray.notify(
                "Wispr Flow Local",
                "Hotkey Alt+Space could not be registered — may conflict with another app.",
            )

    # ------------------------------------------------------------------
    # Hotkey callbacks (called from hook_thread)
    # ------------------------------------------------------------------

    def _on_hotkey_press(self) -> None:
        if not self._state.transition_to_recording():
            return  # silently ignore during PROCESSING
        logger.info("Hotkey pressed — starting recording")
        self._stop_event.clear()
        # Drain stale audio queue entries
        while not self._audio_q.empty():
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break
        try:
            self._audio.start()
        except MicrophoneError as exc:
            logger.error("Microphone error: %s", exc)
            self._state.transition_to_idle()
            self._push_state(AppState.IDLE)
            self._tray.notify("Wispr Flow Local", f"Microphone error: {exc}")
            return

        self._push_state(AppState.RECORDING)

        # Launch silence detector on its own thread
        self._silence_thread = threading.Thread(
            target=self._run_silence_detector, daemon=True, name="silence_thread"
        )
        self._silence_thread.start()

        # Watch for stop_event to trigger recording stop
        watcher = threading.Thread(
            target=self._wait_for_stop, daemon=True, name="stop_watcher"
        )
        watcher.start()

    def _on_hotkey_release(self) -> None:
        if self._state.state != AppState.RECORDING:
            return
        logger.info("Hotkey released — stopping recording")
        self._stop_event.set()

    def _run_silence_detector(self) -> None:
        detector = SilenceDetector(self._audio_q, self._stop_event)
        detector.run()

    def _wait_for_stop(self) -> None:
        """Wait for stop_event then hand off to transcription."""
        self._stop_event.wait()
        self._root.after(0, self._on_recording_stopped)

    # ------------------------------------------------------------------
    # Recording → Processing pipeline (scheduled on main/tkinter thread)
    # ------------------------------------------------------------------

    def _on_recording_stopped(self) -> None:
        if self._state.state != AppState.RECORDING:
            return
        self._state.transition_to_processing()
        self._push_state(AppState.PROCESSING)

        audio_buffer = self._audio.stop()

        self._transcription_thread = threading.Thread(
            target=self._transcribe_and_inject,
            args=(audio_buffer,),
            daemon=True,
            name="transcription_thread",
        )
        self._transcription_thread.start()

    def _transcribe_and_inject(self, audio) -> None:
        try:
            raw = self._transcriber.transcribe(audio)
            logger.info("Transcript (raw): %r", raw)
            if raw:
                clean = self._post.process(raw)
                logger.info("Transcript (clean): %r", clean)
                success = self._injector.inject(clean)
                if not success:
                    logger.info("Used clipboard fallback for injection")
        except Exception as exc:
            logger.exception("Transcription/injection error")
            self._tray.notify("Wispr Flow Local", f"Transcription failed: {exc}")
        finally:
            self._state.transition_to_idle()
            self._push_state(AppState.IDLE)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _push_state(self, state: AppState) -> None:
        try:
            self._state_q.put_nowait(state)
            self._tray.update_state(state)
        except queue.Full:
            pass

    def _quit(self) -> None:
        logger.info("Shutdown requested")
        self._stop_event.set()
        self._shutdown_event.set()
        if self._hotkey is not None:
            self._hotkey.stop()
        self._audio.stop()
        self._tray.stop()
        self._root.after(0, self._root.destroy)

    def _fatal_error(self, message: str) -> None:
        import tkinter.messagebox as mb
        mb.showerror("Wispr Flow Local — Fatal Error", message)
        self._root.destroy()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _setup_logging()
    logger.info("Wispr Flow Local starting…")
    App().run()
    logger.info("Wispr Flow Local exited")
