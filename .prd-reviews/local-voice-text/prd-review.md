# PRD Review: Local Privacy-First Voice-to-Text for Windows (Wispr Flow Local)

**Synthesized review across 6 dimensions**  
**Source reviews:** ambiguity, feasibility, missing-requirements, requirements, scope, stakeholders  
**Date:** 2026-05-11

---

## Executive Summary

The PRD describes a coherent, buildable product. The core concept — a local Whisper-powered voice-to-text daemon with a global hotkey and text injection — is technically sound and the privacy value proposition is genuine. However, the PRD is **not implementation-ready**: eleven open questions block architectural decisions, three internal contradictions must be resolved before code is written, and several missing requirements would surface as user-facing failures late in development.

**The five highest-priority issues across all dimensions:**

1. **Clipboard vs. no-clipboard contradiction** — Goal 4 says "no clipboard required"; OQ #4 treats clipboard as an acceptable fallback. One must be authoritative.
2. **Hold-to-record vs. toggle is unresolved** — OQ #3 is framed as unresolved yet Goal 1 is written as if it's decided. This changes the entire hotkey listener implementation.
3. **Accuracy/latency goals are mutually exclusive on target hardware** — `base` at int8 on a Core i5 takes 5–10s for a 5-second clip. The ≤3s latency goal and ≥90% accuracy goal cannot both be met on the stated hardware without bounding clip duration.
4. **Text injection failure UX is undefined** — what the user sees when `SendInput` fails (elevated windows, read-only fields) is unspecified in Goals, Error States, or User Stories.
5. **Model delivery is unspecified** — bundled in installer vs. downloaded on first run has direct consequences for installer size, offline-first claim, and licensing compliance.

---

## Critical Findings by Dimension

### 1. Ambiguity

**Most severe contradictions:**

| ID | Issue | Impact |
|----|-------|--------|
| C3 / A4 | "No clipboard required" (Goal 4) vs. clipboard fallback in OQ #4 | Architecture, injection module |
| U1 | "Same hotkey (or hotkey release) stops recording" smuggles hold-to-record and toggle into one sentence | Hotkey listener, state machine |
| C4 | Goal 10 declares configurable silence timeout as settled; OQ #5 treats it as open | Settings surface, silence module |

**Additional ambiguities requiring resolution before implementation:**

- "Any foreground app" (Goal 1) conflicts with UAC elevation limits stated in Constraints — should read "any standard user-mode foreground app"
- "Approach Whisper `base` or `small` model accuracy" is circular if `faster-whisper` *is* the base model implementation
- "Zero network calls" (Goal 9) scope is undefined — does it apply to the installer? The Python runtime? Update checks?
- "Configurable silence timeout" (Goal 10) implies a UI surface; tray menu spec (U6) has no such control

**Recommended P0 resolutions:**
1. Replace "no clipboard required" with explicit policy: primary path = SendInput, fallback = clipboard paste with user notification
2. Rewrite Goal 1 to state unambiguously: push-to-talk (hold) OR toggle — pick one
3. Close Goal 10 / OQ #5 jointly: define the default timeout value and confirm whether it appears in config file or tray UI

---

### 2. Technical Feasibility

**Verdict: Feasible in architecture, risky in integration. Four prerequisites must be resolved before implementation begins.**

| Risk | Severity | Detail |
|------|----------|--------|
| UAC elevation / text injection | HIGH | UIPI blocks `SendInput` from non-elevated → elevated windows. Developers run elevated tools constantly. Clipboard paste is the only viable fallback; it must be the documented fallback, not a silent one. |
| CPU latency | HIGH | `base` model at int8 on Core i5: ~1.5–2.5× real-time. A 5s clip takes 7–12s — exceeds the 3s goal. `tiny` meets the goal; `small` does not. The PRD must resolve the accuracy/latency tradeoff. |
| PyInstaller + CTranslate2 packaging | MEDIUM-HIGH | Native DLL dispatch (AVX/AVX2 kernels), MKL thread count failures, `_MEIPASS` path issues. Spike packaging in sprint 1 — not sprint 3. Consider pip-installable package as alternative for developer persona. |
| Global hotkey reliability | MEDIUM | `pynput`'s `WH_KEYBOARD_LL` must pump Windows messages; if the hook thread is blocked during transcription, key-release events are dropped. Use a dedicated hook thread. Alt+Space conflicts with Windows system menu and IME on CJK systems. |
| Tkinter overlay z-order | MEDIUM | `-topmost True` does not guarantee visibility above DirectX fullscreen windows. `win32gui` with `WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW` is more reliable and avoids Tkinter threading complexity. |

**Prerequisites (must precede implementation):**

| # | Prerequisite | Blocks |
|---|-------------|--------|
| P1 | Decide injection strategy: SendInput primary, clipboard fallback, or run-as-admin | Injection module architecture |
| P2 | Benchmark `base`, `tiny` on reference hardware; commit to model | Latency goal, model selection |
| P3 | Spike PyInstaller with CTranslate2 + PortAudio in sprint 1 | Distribution format |
| P4 | Resolve default hotkey — Alt+Space conflicts are significant | UX, hotkey module |

---

### 3. Missing Requirements

**Requirements absent from the PRD that would cause user-facing failures or design pivots if discovered late:**

**P0 — Must add before implementation:**

| ID | Missing Requirement |
|----|-------------------|
| MF1 | Model delivery: bundled vs. first-run download; progress indicator; error handling for interrupted download |
| MF2 | Warm-up UX: what user sees during model load; whether hotkey is disabled until model is ready; what happens if hotkey pressed during warm-up |
| MF8 | Hotkey registration failure: silent failure vs. tray notification vs. fallback hotkey |
| MF9 | `SendInput` failure UX (elevated window): does it fail silently, show a notification, or fall back to clipboard? |
| MNF3 | Autostart on login: the PRD describes a system tray daemon but never states whether it starts on login — a core user expectation for tray apps |

**P1 — Must add before first release:**

| ID | Missing Requirement |
|----|-------------------|
| MF6 | Crash recovery: what happens if the app crashes mid-recording |
| MF7 | Multiple microphone devices: selection, disconnect during recording |
| MF10 | Clipboard contamination: if clipboard fallback is used, save and restore prior clipboard contents |
| UA3 | Microphone permission detection: proactive check, not just error state on failure |
| UA5 | Injection failure detection: notify user if text was not inserted (focus was in read-only field) |
| UA6 | Maximum recording duration: no cap is defined; long dictation or stuck recordings will buffer indefinitely |

**P2 — Important but deferrable:**

- MNF4: Windows sleep/resume behavior (audio device reset)
- MNF5: Multi-monitor / high-DPI overlay positioning
- MNF1: Security — model file integrity check; audio buffer zeroing after transcription
- MNF2: Log rotation and size limits
- MF4: Newline/paragraph injection policy
- MF5: App update mechanism (especially important given privacy stance — no silent updater)

---

### 4. Requirements Completeness

**Overall completeness: Moderate. Functional enough to start; insufficient to ship.**

**Goals with unacceptable acceptance criteria gaps:**

| Goal | Gap | Needed |
|------|-----|--------|
| 1 — Activation | No target app list; hold vs. toggle unresolved | Define minimum app list (VS Code, Chrome, Notepad, Outlook Web, Windows Terminal); close OQ #3 |
| 2 — Accuracy | No reference corpus; "typical dictation" subjective | Define 20–30 sentence test corpus; specify model for measurement |
| 3 — Latency | Reference hardware underspecified; measurement start point ambiguous | "Intel Core i5-10th gen, 8 GB RAM, SSD"; clarify clock start (recording stop vs. silence detection) |
| 6 — Auto-punctuation | "Gaps" undefined; OQ #7 unresolved | Close OQ #7; lock to single rule (append period if transcript ends without terminal punctuation) |
| 7 — Recording overlay | No position, size, dismissal spec | Specify position (bottom-right), no-focus-steal requirement, disappears N seconds after insertion |
| 10 — Silence detection | "Configurable" without UI spec; OQ #5 unresolved | Close OQ #5: hardcode 2s for MVP; expose in config file for v1.1 |

**Open questions that block implementation (must close before sprint 1):**

OQ 1 (hotkey configurability), OQ 2 (model selection), OQ 3 (push-to-talk vs. toggle), OQ 4 (clipboard fallback), OQ 5 (silence timeout), OQ 6 (filler word list), OQ 7 (auto-punctuation approach), OQ 10 (mic error states), OQ 11 (concurrent recording prevention)

---

### 5. Scope

**Verdict: Core product is well-scoped. Two Goals and three Open Questions represent avoidable scope creep.**

**Recommended cuts for MVP:**

| Feature | Recommendation | Rationale |
|---------|---------------|-----------|
| Goal 5 — Filler word removal | Cut to v1.1 | False positives ("like" as filler vs. normal usage); Whisper already omits many fillers; OQ #6 unresolved |
| Goal 6 — Auto-punctuation post-processing | Cut to v1.1; rely on Whisper native output | Whisper already predicts punctuation; additive pass risks double-punctuation; replacement pass risks overwriting correct output |
| GPU support (OQ #8) | CPU-only for MVP | CUDA packaging is "known to be finicky" (PRD's own words); GPU is a v1.1 enhancement |
| Hotkey configurability (OQ #1) | Resolve as fixed Alt+Space for MVP | Config UI requires settings surface, conflict detection, persistence |
| Model selection in tray (OQ #2) | Resolve as fixed `base` for MVP | Model swapping requires download management, disk accounting, UX |
| Configurable silence threshold (OQ #5) | Resolve as hardcoded 2s for MVP | Config implies settings surface |

**Critical scope tension — accuracy vs. latency on target hardware:**

The PRD asserts both ≥90% WER (requires `base`/`small`) and ≤3s latency on Core i5 (achievable only with `tiny`). These goals are incompatible as stated.

**Resolution (recommended):** Scope the latency target to clips ≤5s in duration. For clips ≤5s, `base` int8 on Core i5 is borderline-feasible (5–10s transcription time means longer clips exceed the goal). Honest statement: "≤3s for clips ≤5s; latency scales linearly beyond that." This is achievable without changing the architecture.

**Recommended MVP feature set:**

**In:** Global hotkey (Alt+Space, fixed) · Local Whisper `base` model (CPU, int8) · SendInput + clipboard fallback · System tray daemon + tray menu · Recording overlay (3 states) · Silence auto-stop (2s hardcoded) · 100% offline, zero telemetry

**Out (MVP):** Filler word removal · Auto-punctuation post-processing · GPU support · Hotkey configurability · Model selection UI · Configurable silence threshold

---

### 6. Stakeholders

**Verdict: Primary audience (privacy-conscious power users) is well-understood. Three actor groups are missing and could block adoption.**

**Missing actor: Enterprise IT / Security Teams**

This is a potential adoption blocker, not a future consideration:

- `pynput`'s global keyboard hook (`WH_KEYBOARD_LL`) matches the behavioral signature of a keylogger. EDR products (CrowdStrike, Defender for Endpoint) will flag or quarantine the app without IT whitelisting. This is a hard constraint, not an open risk.
- Unsigned binaries are not deployable in managed enterprise environments. EV code signing (~$400–700/year) is required for enterprise adoption.
- Many enterprise line-of-business apps run elevated — making SendInput injection non-functional for a significant share of enterprise use cases.
- **Recommendation:** Either explicitly add Enterprise IT to Non-Goals (and accept the limitation) or commit to code signing before v1.0.

**Missing actor: Accessibility users**

This is both an ethical gap and a product risk:

- Push-to-talk (hold key) physically excludes users with motor disabilities — the exact users most motivated to use voice input.
- Alt+Space conflicts with NVDA (NonVisual Desktop Access) screen reader hotkeys.
- The Tkinter overlay with `overrideredirect=True` is invisible to screen readers.
- **Recommendation:** Toggle mode must be an MVP option, not a v1.1 afterthought. Add an audio cue (brief tone) for recording state. Document NVDA/JAWS conflict.

**Missing actor: Privacy-focused users (underspecified)**

The PRD claims "nothing leaves the device" but doesn't back this up architecturally:

- No explicit no-telemetry / no-crash-reporting commitment in Goals (only implied by "100% local")
- No model file integrity check
- No audio buffer zeroing requirement after transcription
- No statement on whether auto-update makes network calls
- **Recommendation:** Add explicit "Zero network calls includes: no telemetry, no crash reporting, no auto-update checks" to Goal 9. Add model checksum verification as a P2 constraint.

**Model licensing (largely clear, one risk):**

Whisper weights are MIT-licensed — commercial use and bundling are permitted. One risk: if the app downloads models from Hugging Face Hub at first run, Hugging Face's ToS (attribution, anti-scraping) applies. **Recommendation:** Either bundle the model in the installer (clean, simple, offline-first) or document the download source and applicable terms.

---

## Consolidated Resolution Checklist

**Must resolve before sprint 1 (P0):**

- [ ] OQ #3: Push-to-talk vs. toggle — rewrite Goal 1 to be unambiguous
- [ ] OQ #4 / A4 / C3: Clipboard policy — define primary path + fallback explicitly
- [ ] OQ #5 / C4: Silence timeout — close as 2s hardcoded for MVP; update Goal 10 wording
- [ ] OQ #2: Model selection — close as `base` CPU int8 for MVP
- [ ] Accuracy/latency reconciliation — define latency target as applying to clips ≤5s
- [ ] MF1/MF2: Model delivery and warm-up UX
- [ ] MF9: `SendInput` failure UX (elevated windows, read-only fields)
- [ ] MNF3: Autostart on login — include or explicitly exclude

**Must resolve before first release (P1):**

- [ ] OQ #1: Hotkey configurability — close as fixed Alt+Space for MVP
- [ ] OQ #6: Filler word list — cut Goal 5 for MVP or lock to 3 unambiguous fillers
- [ ] OQ #7: Auto-punctuation — cut Goal 6 for MVP or lock to single rule
- [ ] OQ #10 / OQ #11: Mic error states + concurrent recording prevention
- [ ] Accessibility: toggle mode as MVP option; audio cue for recording state
- [ ] Enterprise: decide code signing or add Enterprise IT to Non-Goals
- [ ] Goal 2: Define accuracy test corpus and measurement methodology
- [ ] Goal 3: Define reference hardware and latency measurement protocol
- [ ] MF7: Multi-microphone device selection
- [ ] MF10: Clipboard save/restore on fallback path
- [ ] UA6: Maximum recording duration

**Engineering prerequisites before implementation:**

1. Spike PyInstaller packaging with CTranslate2 + PortAudio (sprint 1)
2. Benchmark `base` and `tiny` on reference Core i5 hardware
3. Prototype hotkey hook on dedicated message-pump thread under transcription load
4. Confirm Alt+Space behavior with CJK IME enabled
