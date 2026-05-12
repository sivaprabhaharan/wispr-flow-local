"""Application state machine for Wispr Flow Local."""

import threading
from enum import Enum


class AppState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


class StateManager:
    """Thread-safe state holder with transition guard."""

    def __init__(self) -> None:
        self._state = AppState.IDLE
        self._lock = threading.Lock()

    @property
    def state(self) -> AppState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, new_state: AppState) -> None:
        with self._lock:
            self._state = new_state

    def transition_to_recording(self) -> bool:
        """Attempt IDLE → RECORDING. Returns True on success, False if not IDLE."""
        with self._lock:
            if self._state != AppState.IDLE:
                return False
            self._state = AppState.RECORDING
            return True

    def transition_to_processing(self) -> None:
        """RECORDING → PROCESSING (unconditional)."""
        with self._lock:
            self._state = AppState.PROCESSING

    def transition_to_idle(self) -> None:
        """Any → IDLE."""
        with self._lock:
            self._state = AppState.IDLE
