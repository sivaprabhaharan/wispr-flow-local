"""Tests for state.py — StateManager transitions and thread safety."""

import threading
import time

import pytest

from state import AppState, StateManager


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_state_is_idle():
    sm = StateManager()
    assert sm.state == AppState.IDLE


# ---------------------------------------------------------------------------
# transition_to_recording
# ---------------------------------------------------------------------------

def test_transition_idle_to_recording_succeeds():
    sm = StateManager()
    result = sm.transition_to_recording()
    assert result is True
    assert sm.state == AppState.RECORDING


def test_transition_recording_to_recording_fails():
    sm = StateManager()
    sm.transition_to_recording()
    result = sm.transition_to_recording()
    assert result is False
    assert sm.state == AppState.RECORDING


def test_transition_processing_to_recording_fails():
    sm = StateManager()
    sm.transition_to_recording()
    sm.transition_to_processing()
    result = sm.transition_to_recording()
    assert result is False
    assert sm.state == AppState.PROCESSING


# ---------------------------------------------------------------------------
# transition_to_processing
# ---------------------------------------------------------------------------

def test_transition_to_processing():
    sm = StateManager()
    sm.transition_to_recording()
    sm.transition_to_processing()
    assert sm.state == AppState.PROCESSING


def test_transition_idle_to_processing_is_unconditional():
    """transition_to_processing is unconditional — works from any state."""
    sm = StateManager()
    sm.transition_to_processing()
    assert sm.state == AppState.PROCESSING


# ---------------------------------------------------------------------------
# transition_to_idle
# ---------------------------------------------------------------------------

def test_transition_to_idle_from_processing():
    sm = StateManager()
    sm.transition_to_recording()
    sm.transition_to_processing()
    sm.transition_to_idle()
    assert sm.state == AppState.IDLE


def test_transition_to_idle_from_recording():
    sm = StateManager()
    sm.transition_to_recording()
    sm.transition_to_idle()
    assert sm.state == AppState.IDLE


def test_transition_to_idle_from_idle():
    sm = StateManager()
    sm.transition_to_idle()
    assert sm.state == AppState.IDLE


# ---------------------------------------------------------------------------
# Direct state setter
# ---------------------------------------------------------------------------

def test_state_setter():
    sm = StateManager()
    sm.state = AppState.PROCESSING
    assert sm.state == AppState.PROCESSING


# ---------------------------------------------------------------------------
# Full lifecycle round-trip
# ---------------------------------------------------------------------------

def test_full_state_lifecycle():
    sm = StateManager()
    assert sm.state == AppState.IDLE
    assert sm.transition_to_recording() is True
    assert sm.state == AppState.RECORDING
    sm.transition_to_processing()
    assert sm.state == AppState.PROCESSING
    sm.transition_to_idle()
    assert sm.state == AppState.IDLE


# ---------------------------------------------------------------------------
# Thread safety — concurrent transition_to_recording attempts
# ---------------------------------------------------------------------------

def test_concurrent_transition_to_recording_only_one_succeeds():
    sm = StateManager()
    results = []
    barrier = threading.Barrier(10)

    def try_record():
        barrier.wait()
        results.append(sm.transition_to_recording())

    threads = [threading.Thread(target=try_record) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one thread should have succeeded
    assert results.count(True) == 1
    assert results.count(False) == 9
    assert sm.state == AppState.RECORDING
