"""Global hotkey listener using pynput."""

import logging
import threading
from typing import Callable

from pynput import keyboard

from config import HOTKEY

logger = logging.getLogger(__name__)


class HotkeyRegistrationError(Exception):
    pass


class HotkeyListener:
    """Listens for a global hotkey and fires press/release callbacks.

    Runs the pynput message pump on a dedicated daemon thread so the main
    thread and transcription thread never block the Windows keyboard hook.
    A blocked hook thread drops key-release events, causing stuck recording.
    """

    def __init__(self, on_press: Callable, on_release: Callable) -> None:
        self._on_press = on_press
        self._on_release = on_release
        self._listener: keyboard.GlobalHotKeys | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Spawn the daemon thread and register the hotkey."""
        try:
            # pynput GlobalHotKeys supports on_activate but not separate
            # press/release. We use Listener instead to capture key state.
            self._listener = _PressReleaseListener(
                hotkey_str=HOTKEY,
                on_press_cb=self._on_press,
                on_release_cb=self._on_release,
            )
            self._thread = threading.Thread(
                target=self._listener.run, daemon=True, name="hook_thread"
            )
            self._thread.start()
            logger.info("Hotkey listener started (%s)", HOTKEY)
        except Exception as exc:
            raise HotkeyRegistrationError(
                f"Could not register hotkey {HOTKEY}: {exc}"
            ) from exc

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        logger.info("Hotkey listener stopped")


class _PressReleaseListener:
    """Internal: bridges pynput Listener to press/release callbacks for Alt+Space."""

    def __init__(
        self,
        hotkey_str: str,
        on_press_cb: Callable,
        on_release_cb: Callable,
    ) -> None:
        self._on_press_cb = on_press_cb
        self._on_release_cb = on_release_cb
        self._alt_held = False
        self._space_held = False
        self._triggered = False
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )

    def run(self) -> None:
        with self._listener:
            self._listener.join()

    def stop(self) -> None:
        self._listener.stop()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._alt_held = True
            elif key == keyboard.Key.space:
                self._space_held = True

            if self._alt_held and self._space_held and not self._triggered:
                self._triggered = True
                self._on_press_cb()
        except Exception:
            logger.exception("Error in hotkey on_press")

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
                self._alt_held = False
            elif key == keyboard.Key.space:
                self._space_held = False

            if self._triggered and (not self._alt_held or not self._space_held):
                self._triggered = False
                self._on_release_cb()
        except Exception:
            logger.exception("Error in hotkey on_release")
