"""System tray icon using pystray + Pillow-generated icons."""

import logging
import threading
from typing import Callable

from PIL import Image, ImageDraw

from state import AppState

logger = logging.getLogger(__name__)

_ICON_SIZE = 64
_COLORS = {
    AppState.IDLE: "#4caf50",       # green
    AppState.RECORDING: "#e53935",  # red
    AppState.PROCESSING: "#1e88e5", # blue
}
_LABELS = {
    AppState.IDLE: "idle",
    AppState.RECORDING: "recording",
    AppState.PROCESSING: "processing",
}


def _make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin], fill=color)
    return img


class TrayIcon:
    """System tray icon that reflects AppState via coloured circle icons.

    pystray runs its own internal thread; ``start()`` is non-blocking.
    """

    def __init__(self, on_quit: Callable) -> None:
        import pystray  # deferred import

        self._on_quit = on_quit
        self._icons = {state: _make_icon(color) for state, color in _COLORS.items()}
        self._current_state = AppState.IDLE

        self._tray = pystray.Icon(
            name="WisprFlowLocal",
            icon=self._icons[AppState.IDLE],
            title="Wispr Flow Local — idle",
            menu=self._build_menu(),
        )

    def _build_menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem("Wispr Flow Local — idle", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                f"Model: Whisper base (CPU)", None, enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit_handler),
        )

    def _quit_handler(self, icon, item) -> None:
        self._tray.stop()
        self._on_quit()

    def start(self) -> None:
        """Start the tray icon on a daemon thread (non-blocking)."""
        t = threading.Thread(target=self._tray.run, daemon=True, name="tray_thread")
        t.start()
        logger.info("TrayIcon started")

    def update_state(self, state: AppState) -> None:
        self._current_state = state
        self._tray.icon = self._icons[state]
        self._tray.title = f"Wispr Flow Local — {_LABELS[state]}"

    def notify(self, title: str, message: str) -> None:
        """Show a balloon notification (Windows only)."""
        try:
            self._tray.notify(message, title)
        except Exception:
            logger.warning("Tray notify failed: %s — %s", title, message)

    def stop(self) -> None:
        try:
            self._tray.stop()
        except Exception:
            pass
