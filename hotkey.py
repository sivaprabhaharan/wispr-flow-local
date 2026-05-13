"""Global hotkey listener using pynput."""

import logging
import threading
from typing import Callable

from pynput import keyboard

from config import HOTKEY

logger = logging.getLogger(__name__)

# Map pynput modifier key names to the set of Key objects that represent them
_MODIFIER_MAP: dict[str, tuple] = {
    "ctrl":  (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r),
    "alt":   (keyboard.Key.alt,  keyboard.Key.alt_l,  keyboard.Key.alt_r),
    "shift": (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r),
    "cmd":   (keyboard.Key.cmd,  keyboard.Key.cmd_l,  keyboard.Key.cmd_r),
    "super": (keyboard.Key.cmd,  keyboard.Key.cmd_l,  keyboard.Key.cmd_r),
}

# Map special key names to pynput Key enum values
_SPECIAL_KEY_MAP: dict[str, keyboard.Key] = {
    "space":  keyboard.Key.space,
    "tab":    keyboard.Key.tab,
    "enter":  keyboard.Key.enter,
    "esc":    keyboard.Key.esc,
    "delete": keyboard.Key.delete,
    "backspace": keyboard.Key.backspace,
}


def _parse_hotkey(hotkey_str: str) -> tuple[list[tuple], keyboard.Key | keyboard.KeyCode]:
    """Parse a hotkey string like '<ctrl>+<space>' into (modifier_groups, trigger_key).

    Returns:
        modifier_groups: list of tuples, each containing the Key variants for one modifier
        trigger_key: the final (non-modifier) key
    Raises:
        ValueError: if the hotkey string is malformed or unrecognised
    """
    parts = [p.strip("<>").lower() for p in hotkey_str.split("+")]
    if len(parts) < 2:
        raise ValueError(f"Hotkey must have at least one modifier and one key: {hotkey_str!r}")

    modifier_groups: list[tuple] = []
    trigger_key = None

    for part in parts:
        if part in _MODIFIER_MAP:
            modifier_groups.append(_MODIFIER_MAP[part])
        elif part in _SPECIAL_KEY_MAP:
            trigger_key = _SPECIAL_KEY_MAP[part]
        elif len(part) == 1:
            trigger_key = keyboard.KeyCode.from_char(part)
        else:
            # Try matching a named pynput Key (e.g. "f1", "home")
            pynput_key = getattr(keyboard.Key, part, None)
            if pynput_key is not None:
                trigger_key = pynput_key
            else:
                raise ValueError(f"Unrecognised key in hotkey string: {part!r}")

    if trigger_key is None:
        raise ValueError(f"No trigger key found in hotkey string: {hotkey_str!r}")
    if not modifier_groups:
        raise ValueError(f"No modifier keys found in hotkey string: {hotkey_str!r}")

    return modifier_groups, trigger_key


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
        self._listener: _PressReleaseListener | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Spawn the daemon thread and register the hotkey."""
        try:
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
    """Internal: drives pynput Listener and fires callbacks when the configured hotkey
    is held (on_press_cb) and released (on_release_cb).

    Parses HOTKEY dynamically so any modifier+key combo works without code changes.
    """

    def __init__(
        self,
        hotkey_str: str,
        on_press_cb: Callable,
        on_release_cb: Callable,
    ) -> None:
        self._on_press_cb = on_press_cb
        self._on_release_cb = on_release_cb
        self._triggered = False

        self._modifier_groups, self._trigger_key = _parse_hotkey(hotkey_str)
        # Track held state per modifier group and for the trigger key
        self._mods_held: list[bool] = [False] * len(self._modifier_groups)
        self._trigger_held = False

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
            for i, group in enumerate(self._modifier_groups):
                if key in group:
                    self._mods_held[i] = True

            if key == self._trigger_key:
                self._trigger_held = True

            if all(self._mods_held) and self._trigger_held and not self._triggered:
                self._triggered = True
                self._on_press_cb()
        except Exception:
            logger.exception("Error in hotkey on_press")

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        try:
            for i, group in enumerate(self._modifier_groups):
                if key in group:
                    self._mods_held[i] = False

            if key == self._trigger_key:
                self._trigger_held = False

            if self._triggered and (not all(self._mods_held) or not self._trigger_held):
                self._triggered = False
                self._on_release_cb()
        except Exception:
            logger.exception("Error in hotkey on_release")
