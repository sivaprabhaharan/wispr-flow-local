"""Frameless always-on-top recording state overlay (tkinter)."""

import logging
import queue
import tkinter as tk
from typing import Optional

from state import AppState

logger = logging.getLogger(__name__)

_BG = "#1e1e1e"
_RED = "#e53935"
_BLUE = "#1e88e5"
_WHITE = "#ffffff"
_GREY = "#9e9e9e"


class Overlay:
    """Small status overlay in the bottom-right corner of the primary screen.

    State changes are delivered via ``state_q`` and polled by the tkinter
    ``after()`` loop — never from another thread directly.
    """

    def __init__(self, root: tk.Tk, state_q: queue.Queue) -> None:
        self._root = root
        self._state_q = state_q
        self._win: Optional[tk.Toplevel] = None
        self._pulse_job: Optional[str] = None
        self._pulse_alpha = 0.85
        self._pulse_dir = -1

    def start(self) -> None:
        """Begin polling the state queue."""
        self._poll()

    def _poll(self) -> None:
        try:
            while True:
                state: AppState = self._state_q.get_nowait()
                self._apply_state(state)
        except queue.Empty:
            pass
        self._root.after(100, self._poll)

    def _apply_state(self, state: AppState) -> None:
        if state == AppState.IDLE:
            self._hide()
        elif state == AppState.RECORDING:
            self._show_recording()
        elif state == AppState.PROCESSING:
            self._show_processing()

    def _hide(self) -> None:
        self._cancel_pulse()
        if self._win is not None:
            self._win.destroy()
            self._win = None

    def _make_window(self) -> tk.Toplevel:
        win = tk.Toplevel(self._root)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", 0.85)
        win.configure(bg=_BG)
        win.focus_set()  # tkinter needs this to receive events, but we avoid steal
        win.focus_force()
        # don't steal focus from other windows
        win.wm_attributes("-toolwindow", True)
        return win

    def _position_window(self, win: tk.Toplevel, width: int, height: int) -> None:
        from config import OVERLAY_MARGIN
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        x = screen_w - width - OVERLAY_MARGIN
        y = screen_h - height - OVERLAY_MARGIN - 40  # above taskbar approx
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _show_recording(self) -> None:
        self._cancel_pulse()
        if self._win is not None:
            self._win.destroy()
        win = self._make_window()
        frame = tk.Frame(win, bg=_BG, padx=12, pady=8)
        frame.pack()
        canvas = tk.Canvas(frame, width=16, height=16, bg=_BG, highlightthickness=0)
        canvas.create_oval(2, 2, 14, 14, fill=_RED, outline="")
        canvas.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(frame, text="Recording…", fg=_WHITE, bg=_BG, font=("Segoe UI", 10)).pack(side=tk.LEFT)
        self._position_window(win, 160, 44)
        self._win = win
        self._pulse_alpha = 0.85
        self._pulse_dir = -1
        self._pulse()

    def _show_processing(self) -> None:
        self._cancel_pulse()
        if self._win is not None:
            self._win.destroy()
        win = self._make_window()
        frame = tk.Frame(win, bg=_BG, padx=12, pady=8)
        frame.pack()
        tk.Label(frame, text="⏳ Processing…", fg=_GREY, bg=_BG, font=("Segoe UI", 10)).pack()
        self._position_window(win, 160, 44)
        self._win = win

    def _pulse(self) -> None:
        if self._win is None:
            return
        self._pulse_alpha += self._pulse_dir * 0.05
        if self._pulse_alpha <= 0.4:
            self._pulse_dir = 1
        elif self._pulse_alpha >= 0.95:
            self._pulse_dir = -1
        try:
            self._win.wm_attributes("-alpha", max(0.4, min(0.95, self._pulse_alpha)))
        except Exception:
            return
        self._pulse_job = self._root.after(80, self._pulse)

    def _cancel_pulse(self) -> None:
        if self._pulse_job is not None:
            self._root.after_cancel(self._pulse_job)
            self._pulse_job = None
