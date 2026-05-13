"""Text injection via SendInput (primary) with clipboard paste fallback."""

import ctypes
import ctypes.wintypes
import logging
import time

import pyperclip

logger = logging.getLogger(__name__)

# Windows constants
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_KEYUP = 0x0002


class InjectionError(Exception):
    """Raised when both SendInput and clipboard paste fail."""


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.wintypes.WORD),
        ("wScan", ctypes.wintypes.WORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class _INPUT_UNION(ctypes.Union):
    # Pad to MOUSEINPUT size (32 bytes) so ctypes.sizeof(INPUT) == 40 on 64-bit,
    # matching what Windows expects. Without the padding SendInput always returns 0.
    _fields_ = [
        ("ki", KEYBDINPUT),
        ("_padding", ctypes.c_uint8 * 32),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_input", _INPUT_UNION)]


class TextInjector:
    """Injects text at the active cursor position.

    Primary path: ``SendInput`` with ``KEYEVENTF_UNICODE`` (no clipboard touch).
    Fallback:     clipboard write + Ctrl+V + restore previous clipboard.
    """

    def inject(self, text: str) -> bool:
        """Inject ``text`` at the current cursor. Returns True if primary path used.

        Raises InjectionError if both SendInput and clipboard paste fail.
        """
        if not text:
            return True
        if self._send_input(text):
            logger.debug("TextInjector: SendInput succeeded")
            return True
        logger.info("TextInjector: SendInput failed, using clipboard fallback")
        if self._clipboard_paste(text):
            return False
        raise InjectionError("Both SendInput and clipboard paste failed")

    def _send_input(self, text: str) -> bool:
        """Send each character via SendInput KEYEVENTF_UNICODE. Returns success."""
        try:
            user32 = ctypes.windll.user32
            inputs = []
            for ch in text:
                scan = ord(ch)
                # key down
                ki_down = KEYBDINPUT(
                    wVk=0,
                    wScan=scan,
                    dwFlags=KEYEVENTF_UNICODE,
                    time=0,
                    dwExtraInfo=None,
                )
                inp_down = INPUT(type=INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki_down))
                inputs.append(inp_down)
                # key up
                ki_up = KEYBDINPUT(
                    wVk=0,
                    wScan=scan,
                    dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                    time=0,
                    dwExtraInfo=None,
                )
                inp_up = INPUT(type=INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki_up))
                inputs.append(inp_up)

            n = len(inputs)
            InputArray = INPUT * n
            arr = InputArray(*inputs)
            sent = user32.SendInput(n, arr, ctypes.sizeof(INPUT))
            return sent == n
        except Exception:
            logger.exception("SendInput error")
            return False

    def _clipboard_paste(self, text: str) -> bool:
        """Write text to clipboard, send Ctrl+V, then restore previous contents.

        Returns True if the paste likely succeeded, False otherwise.
        """
        try:
            previous = pyperclip.paste()
        except Exception:
            previous = ""
        success = False
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            self._send_ctrl_v()
            time.sleep(0.5)
            success = True
        except Exception:
            logger.exception("Clipboard paste error")
        finally:
            try:
                pyperclip.copy(previous)
            except Exception:
                logger.warning("Failed to restore clipboard after paste")
        return success

    def _send_ctrl_v(self) -> None:
        """Send Ctrl+V via SendInput."""
        try:
            user32 = ctypes.windll.user32
            VK_CONTROL = 0x11
            VK_V = 0x56

            def make_vk_input(vk: int, flags: int) -> INPUT:
                ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
                return INPUT(type=INPUT_KEYBOARD, _input=_INPUT_UNION(ki=ki))

            inputs = [
                make_vk_input(VK_CONTROL, 0),
                make_vk_input(VK_V, 0),
                make_vk_input(VK_V, KEYEVENTF_KEYUP),
                make_vk_input(VK_CONTROL, KEYEVENTF_KEYUP),
            ]
            n = len(inputs)
            InputArray = INPUT * n
            arr = InputArray(*inputs)
            user32.SendInput(n, arr, ctypes.sizeof(INPUT))
        except Exception:
            logger.exception("Ctrl+V SendInput error")
