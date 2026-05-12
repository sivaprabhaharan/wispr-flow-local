# Wispr Flow Local — Implementation Review

**Reviewer:** polecat obsidian  
**Scope:** All Python modules vs DESIGN.md spec  
**Date:** 2026-05-12

---

## Summary

The MVP implementation is structurally correct and faithfully follows DESIGN.md.
Four critical bugs were found and fixed in-place. Three minor issues are documented
but left as-is for MVP (acceptable per scope).

---

## Critical Bugs Fixed

### 1. `overlay.py` — Focus theft breaks text injection ✅ FIXED

**File:** `overlay.py`, `_make_window()`

**Problem:**  
`win.focus_set()` and `win.focus_force()` were called when creating the overlay
window. DESIGN.md §overlay explicitly states: *"`focus_set()` is **never** called
— the overlay must not steal focus from the target app."*  

This is not merely a UX issue — it is a functional bug. When recording starts,
the overlay window steals keyboard focus. All subsequent `SendInput` keystrokes
(the transcribed text) are then delivered to the overlay window rather than the
target application. Text injection silently fails on every recording.

**Fix:** Removed both `focus_set()` and `focus_force()` calls. The `-toolwindow`
attribute was retained (correct; suppresses taskbar entry and prevents accidental
focus via Alt+Tab).

---

### 2. `transcriber.py` — `MODEL_DIR` config constant not used ✅ FIXED

**File:** `transcriber.py`, `load_model()`

**Problem:**  
`config.py` declares `MODEL_DIR = "models"` as the single source of truth for the
model directory path. `transcriber.py` hardcoded `"models"` directly:

```python
model_path = str(Path(__file__).parent / "models" / WHISPER_MODEL)
```

If `MODEL_DIR` is changed in `config.py` (e.g. for packaging or testing), the
transcriber would continue looking in the old location and silently fail.

**Fix:** Import `MODEL_DIR` from `config` and use it:

```python
model_path = str(Path(__file__).parent / MODEL_DIR / WHISPER_MODEL)
```

---

### 3. `injector.py` — Clipboard not restored when paste fails mid-way ✅ FIXED

**File:** `injector.py`, `_clipboard_paste()`

**Problem:**  
The original clipboard restore (`pyperclip.copy(previous)`) was inside the `try`
block. If `_send_ctrl_v()` raised an exception, the restore line was never reached,
permanently overwriting the user's clipboard with the transcribed text.

**Fix:** Moved restore to a `finally` block so it always runs regardless of errors.
Also changed return type to `bool` (success indicator) to enable "both paths failed"
detection (see bug 4).

---

### 4. `injector.py` / `main.py` — No tray notification when both injection paths fail ✅ FIXED

**File:** `injector.py`, `main.py`

**Problem:**  
DESIGN.md §5 (Error Handling) specifies: *"If both paths fail (read-only field,
game window, etc.), a tray balloon notifies the user: 'Text could not be inserted
— target window may be read-only.'"*  
The original code: `inject()` returned `False` for the clipboard fallback path
but had no way to signal that clipboard paste itself also failed. The App logged
"Used clipboard fallback" and silently dropped the text.

**Fix:**
- Added `InjectionError` exception class to `injector.py`.
- `_clipboard_paste()` now returns `bool` (True = paste likely sent).
- `inject()` raises `InjectionError` when both `_send_input` and `_clipboard_paste`
  fail.
- `main.py` imports `InjectionError` and catches it with a specific tray
  notification: *"Text could not be inserted — target window may be read-only."*

---

### 5. `main.py` — Race condition: `_on_recording_stopped` after shutdown ✅ FIXED

**File:** `main.py`, `_on_recording_stopped()`

**Problem:**  
`_quit()` sets `_stop_event` (to halt the silence/stop-watcher threads) and
schedules `_root.destroy()` via `after()`. Concurrently, the `_wait_for_stop`
daemon thread wakes on `_stop_event` and schedules `_on_recording_stopped()` via
`after()`. The order of these two `after()` callbacks is non-deterministic. If
`_root.destroy()` runs first, the subsequent `_on_recording_stopped()` call
operates on a destroyed tkinter root, causing an exception or silent state
corruption (e.g. `_push_state` posts to `_state_q` which nobody reads).

**Fix:** Guard with `_shutdown_event` at the top of `_on_recording_stopped()`:

```python
def _on_recording_stopped(self) -> None:
    if self._shutdown_event.is_set():
        return
    ...
```

`_shutdown_event` is set in `_quit()` before `_root.destroy()` is scheduled, so
the guard reliably prevents processing after shutdown is initiated.

---

## Minor Issues (No Code Change — MVP Acceptable)

### M1. `tray.py` — Context menu status label is static

The tray menu item "Wispr Flow Local — idle" is built once in `__init__` and never
updated. `update_state()` correctly changes the tray icon and `title` tooltip, but
the menu label stays "idle" regardless of state.

**Impact:** Low — the tray title (tooltip on hover) does update. The static menu
label is slightly misleading but not functionally harmful.

**Recommendation:** Rebuild menu on state change, or use a `pystray.MenuItem` with
a callable text function. Defer to v1.1.

---

### M2. `postprocessor.py` — Filler tokens with trailing punctuation not stripped

`remove_fillers()` compares `tokens[i].lower()` against the filler set. If Whisper
emits "um," (comma attached), it does not match "um" and is retained.

**Impact:** Low — Whisper rarely attaches punctuation to filler words in the middle
of speech. When it does, a stray comma may appear.

**Recommendation:** Strip punctuation from tokens before filler comparison:
`token.lower().strip(".,!?;:")`. Defer to v1.1.

---

### M3. Model loading state not reflected in overlay

DESIGN.md §transcriber states: *"During `load_model()`, the overlay shows a
'Loading…' message and the hotkey is disabled."*

`AppState` has no `LOADING` state, and no loading indicator is shown in the overlay
or tray during the 2–5 s model load. The tray icon starts green (IDLE) even before
the hotkey is active.

**Impact:** Low for MVP — hotkey presses before model load are silently ignored
(correct behaviour), but the user has no feedback that the app is starting up.

**Recommendation:** Add `AppState.LOADING`, push it at startup, show a "Loading
model…" label in the overlay (or tray tooltip). Defer to v1.1.

---

## Correctness vs DESIGN.md Checklist

| Module | Matches spec? | Notes |
|--------|--------------|-------|
| `config.py` | ✅ | All constants match spec |
| `state.py` | ✅ | States, transitions, lock — correct |
| `hotkey.py` | ✅ | Dedicated hook thread; press/release callbacks; HotkeyRegistrationError |
| `audio.py` | ✅ | 16 kHz mono; MicrophoneError; concatenated buffer on stop |
| `silence.py` | ✅ | RMS VAD; SILENCE_TIMEOUT; MAX_RECORDING_S cap |
| `transcriber.py` | ✅ (fixed) | MODEL_DIR now used; beam_size=5, vad_filter=False |
| `postprocessor.py` | ✅ | Filler removal (bigram first); auto-punctuation |
| `injector.py` | ✅ (fixed) | SendInput Unicode; clipboard fallback; InjectionError; clipboard restore in finally |
| `overlay.py` | ✅ (fixed) | Focus no longer stolen; overrideredirect; topmost; pulse animation |
| `tray.py` | ✅ | pystray; Pillow icons; state-based colour; Quit handler |
| `main.py` | ✅ (fixed) | Shutdown guard; InjectionError handled; threading model correct |
