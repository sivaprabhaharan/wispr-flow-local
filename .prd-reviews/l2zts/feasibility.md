# Technical Feasibility Review: Local Privacy-First Voice-to-Text for Windows

**Leg:** wfl-leg-6iits  
**Reviewer:** polecat opal  
**PRD:** `.prd-reviews/local-voice-text/prd-draft.md`

---

## Summary Verdict

The core concept is **feasible** — each individual component exists and has been used in production software. The risk is in **integration**: several components interact in ways that create hard problems on Windows, particularly around text injection into elevated windows, PyInstaller packaging complexity, and real-world latency on CPU-only hardware. None of these are blockers per se, but each requires a deliberate mitigation strategy before MVP.

**Biggest risks ranked:**

1. UAC elevation / text injection into admin windows (hard architectural constraint)
2. CPU latency on `base`/`small` models exceeding 3s goal
3. PyInstaller packaging with faster-whisper + native deps
4. Global hotkey conflicts and reliability on Windows
5. Tkinter overlay visibility in all window contexts

---

## Risk 1 (HIGH): Text Injection into UAC-Elevated Windows

**What the PRD says:** "`SendInput` via ctypes is the most reliable way to inject keystrokes without requiring accessibility permissions."

**The real constraint:** Windows' User Interface Privilege Isolation (UIPI) blocks `SendInput` from a lower-integrity process sending input to a higher-integrity process. A non-elevated app **cannot inject keystrokes into any window running as Administrator** — this includes installers, admin-elevated terminals (PowerShell/CMD run as admin), and many developer tools (some IDEs, Docker Desktop, etc.).

**Why this matters for the target user:** The PRD's primary persona is developers. Developers frequently work in elevated terminals and elevated IDE windows. This is not an edge case — it's a core workflow for the stated audience.

**Options and trade-offs:**

| Option | Trade-off |
|--------|-----------|
| Run the app elevated (as admin) | Requires UAC prompt on every launch; `pynput` global hooks may behave differently when elevated; SmartScreen warning already present |
| Clipboard paste fallback | Overwrites clipboard, may fail in some apps (e.g., password fields), less polished UX; needs user awareness |
| Document the limitation | Honest, zero engineering cost, but material UX gap for developer persona |
| UI Automation (`IAccessible`/UIA) | More complex, not universally supported, doesn't solve UIPI fundamentally |

**Recommendation:** The PRD should make a deliberate choice here rather than leaving it as an open question. Clipboard paste is a practical fallback, but it should be the documented primary path for elevated targets, not a silent fallback. Running the daemon elevated is probably the cleanest developer-facing UX but has security implications worth acknowledging.

**Prerequisite:** Decide injection strategy before writing the injection module; refactoring later is painful.

---

## Risk 2 (HIGH): CPU Latency — 3s Goal Is Tight on `base`/`small`

**What the PRD says:** "faster-whisper with `int8` quantisation on CPU should hit ~1–2× real-time on a modern Core i5 for `base` model — acceptable latency for typical 5–10s dictation bursts."

**The math:**
- 1–2× real-time on `base` means 5–10s of audio takes 5–20s to transcribe on CPU.
- The 3s latency goal requires the transcription to finish in ≤ 3s after audio stops.
- For 5s of audio at 2× real-time, that's 10s of CPU time — well over goal.
- For `small` model, 1–2× real-time is optimistic; benchmarks suggest 3–5× real-time on typical i5 without AVX-512.

**Actual faster-whisper benchmarks (CTranslate2, int8, CPU):**
- `tiny`: ~4–6× real-time on modern CPU → 5s audio ≈ 0.8–1.2s ✓
- `base`: ~1.5–2.5× real-time → 5s audio ≈ 3–8s ⚠ borderline
- `small`: ~0.5–1× real-time → 5s audio ≈ 5–10s ✗

The 3s goal is achievable with `tiny` on CPU, and with `base` on a fast CPU (i7/Ryzen 7+). It is **not reliably achievable** with `base` on the stated target hardware ("mid-range Core i5"), and `small` is out of scope for CPU-only.

**GPU path:** With CUDA (even a GTX 1060/RTX 3060), `base` and `small` both comfortably hit <1s. The PRD lists GPU as an open question (Q8) — it should probably be a first-class feature, not an afterthought, given how much it affects the stated latency goal.

**Recommendation:**
- Target `tiny` for CPU-only MVP with honest accuracy trade-off documentation.
- Enable CUDA by default when detected — this is low-effort in faster-whisper and dramatically improves the product for GPU users.
- The latency goal should be tiered: "≤ 3s on GPU; ≤ 5s on CPU with `tiny`" is honest and achievable.

**Prerequisite:** Benchmark on actual target hardware before committing to model choice. Don't commit to `base`/`small` as the default until latency is validated.

---

## Risk 3 (MEDIUM-HIGH): PyInstaller Packaging with Native Dependencies

**What the PRD says:** "PyInstaller or similar for distribution; faster-whisper requires Microsoft Visual C++ redistributable."

**The actual packaging surface:**
- `faster-whisper` → `CTranslate2` → native `.dll`s (MKL, OpenMP, AVX-optimised kernels)
- `sounddevice` → PortAudio → `libportaudio.dll` (or bundled with the wheel on Windows)
- `pynput` → Windows hooks via ctypes (usually fine)
- `pystray` → Windows shell notification area (usually fine)
- CUDA path: `cublas64_11.dll`, `cudnn_ops_infer64_8.dll`, etc. — these are NOT redistributable in the normal sense; users need CUDA toolkit or you bundle them (~500 MB)

**Known failure modes with PyInstaller + CTranslate2:**
- `CTranslate2` uses runtime dispatch to select AVX/AVX2/AVX-512 kernels; PyInstaller may bundle only one variant, causing `Illegal instruction` on older CPUs.
- MKL thread count detection can fail in frozen environments.
- The `faster-whisper` model loading uses `ctranslate2.Translator` with a path — if PyInstaller's `_MEIPASS` path handling isn't correctly hooked, model loading fails silently or raises cryptic errors.

**Alternatives worth considering:**
- Nuitka: Better native extension handling than PyInstaller, slower compile, less community documentation
- cx_Freeze: Similar trade-offs to PyInstaller
- Distribute as a pip-installable package with a launcher script (targets developer persona well; simpler than a full frozen binary)
- Docker/WSL: Not realistic for this UX (needs system-wide hotkey)

**Recommendation:** Spike PyInstaller packaging early (sprint 1, not sprint 3). The risk of discovering packaging failure late is high. A pip-installable package is a viable alternative for the developer persona and avoids the entire frozen binary problem.

**Prerequisite:** Validate the packaging approach before finalising distribution format in the PRD.

---

## Risk 4 (MEDIUM): Global Hotkey Reliability and Conflicts

**What the PRD says:** "Global hotkey registration via `pynput` or `keyboard` library; may conflict with other apps' hotkeys."

**The deeper issues:**

- **Alt+Space is Windows' built-in shortcut** for the system menu (title bar context menu) in virtually every window. While apps can intercept it, the system hook fires first and the system menu may flicker or activate in some apps. This is a non-trivial UX issue.
- **`pynput` on Windows** uses `SetWindowsHookEx` with `WH_KEYBOARD_LL` (low-level keyboard hook). This works reliably but has known issues: the hook must be on a thread that pumps Windows messages. If the main thread is blocked (e.g., during transcription), the hook callback queue fills and events are dropped. **This is a real bug risk** for the push-to-talk model: the key-release event that stops recording could be missed if transcription is blocking the hook thread.
- **`keyboard` library** requires admin on some Windows configurations.
- **Alt+Space + Windows IME** (Japanese, Chinese, Korean input): On systems with IME enabled, Alt+Space opens the IME mode toggle. Confirmed conflict.

**Recommendation:**
- Use a dedicated thread for the keyboard hook with its own Windows message pump — don't share with the UI thread.
- Consider defaulting to a less-conflicted hotkey (e.g., `Right Ctrl` held, or `Ctrl+Shift+Space`). Alt+Space should at minimum be configurable at first launch.
- Document the IME conflict as a known issue with a workaround in the README.

**Prerequisite:** Test hotkey reliability under load (during transcription) before declaring it stable.

---

## Risk 5 (MEDIUM): Tkinter Overlay Visibility

**What the PRD says:** "Tkinter `Toplevel` with `overrideredirect=True` + `-topmost True` for a frameless always-on-top overlay."

**Issues:**
- `-topmost True` doesn't guarantee visibility above all windows. DirectX/OpenGL fullscreen apps (games), some video players, and apps that call `SetWindowPos(HWND_TOPMOST)` themselves will occlude the overlay.
- `overrideredirect=True` removes the window from the taskbar and title bar, which is correct, but it also removes Windows' default window management — the overlay can get stuck behind other topmost windows if focus changes.
- Tkinter's main loop must be running on the main thread. With a single-process daemon, threading discipline is critical: `after()` callbacks for UI updates must not block.

**This is not a hard blocker** for the target use case (text editors, browsers, IDEs — not fullscreen apps), but the PRD should narrow the supported surface area or document the limitation.

**Recommendation:** Consider a non-Tkinter overlay using `win32gui` / `ctypes` directly for a `WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW` window — lighter weight and more reliable z-order behaviour. This is more code but avoids Tkinter threading complexity.

---

## Risk 6 (LOW-MEDIUM): Model Warm-Up / First-Run Latency

**What the PRD says:** "First run is slow (model warm-up); need a splash or tray status indicator."

**The actual numbers:**
- `faster-whisper` loads and JIT-compiles kernels on first use per model. On CPU: 3–8s warm-up. On GPU: 5–15s (CUDA kernel compilation).
- The model files (150–300 MB) must be on local disk. If distributed separately or downloaded on first run, this adds a dependency on network at setup time (conflicts with "100% local" framing unless model is bundled).

**Recommendation:** Bundle the model in the installer. Show a tray tooltip "Loading model…" on startup. The PRD already notes this; just ensure it's in the requirements, not just the "open risks" list.

---

## Risk 7 (LOW): Silence Detection Accuracy

**What the PRD says:** "VAD (webrtcvad or simple RMS threshold) for silence detection."

**Trade-off:**
- `webrtcvad` is a robust option (Google's WebRTC VAD), available as a Python package. Works well for speech/non-speech discrimination.
- Simple RMS threshold is fast to implement but fragile in noisy environments (fans, HVAC, keyboard sounds may prevent auto-stop).
- `silero-vad` (PyTorch-based) is higher accuracy but adds a significant dependency.

**Recommendation:** Use `webrtcvad` as the default. It's well-tested, lightweight, and doesn't require a neural network. RMS threshold is fine as a fallback if `webrtcvad` packaging proves problematic.

---

## Prerequisites Summary

These must be resolved before implementation begins (not during):

| # | Prerequisite | Blocks |
|---|-------------|--------|
| P1 | Decide text injection strategy for elevated windows (SendInput vs clipboard vs run-as-admin) | Architecture, injection module |
| P2 | Benchmark faster-whisper on target hardware; set realistic model/latency defaults | Model selection, latency goal in PRD |
| P3 | Spike PyInstaller packaging with CTranslate2 + PortAudio | Distribution format decision |
| P4 | Decide default hotkey (Alt+Space conflicts are real) | UX, hotkey module |

---

## What Is Solid

- The overall architecture (single-process daemon with queue between capture and transcription) is sound.
- `faster-whisper` is a mature, production-quality library — the transcription core is low-risk.
- `sounddevice` + PortAudio on Windows is well-tested.
- `pystray` tray icon is reliable on Windows.
- Filler word removal via post-processing string replacement is trivial.
- Auto-punctuation via Whisper's built-in output (it already adds punctuation) is largely free — the "additive" post-processing approach is correct.
- The push-to-talk model is simpler and more reliable than always-on VAD (no continuous audio processing).

---

## Recommended PRD Clarifications

1. **P3 / Q4**: Commit to "clipboard paste is the fallback for elevated windows; document the limitation" — don't leave this open.
2. **Q2 / Q8**: Default to `tiny` for CPU-only; enable CUDA when detected; expose model selection in tray for advanced users.
3. **Q1**: Make Alt+Space configurable at first launch; document IME conflict.
4. **Q3**: Confirm push-to-talk (hold) is the UX — toggle adds state management complexity for MVP.
5. **Q9**: Target developer-friendly pip package first; frozen `.exe` as a follow-on.
6. **Q10**: Microphone error → system tray notification + tooltip; no mic found → notification on startup with link to settings.
7. **Q11**: Lock out concurrent recordings (ignore hotkey while transcription in flight); show "processing…" in overlay.
