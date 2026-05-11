# Requirements Completeness Review
**PRD:** Local Privacy-First Voice-to-Text for Windows (Wispr Flow Local)  
**Leg:** wfl-leg-tqxgi  
**Reviewer:** polecat onyx  
**Date:** 2026-05-11

---

## Summary

The PRD has strong problem framing, clear non-goals, and good user stories. However, several goals lack measurable acceptance criteria, and a number of open questions represent unresolved requirements (not optional polish) that block implementation decisions. Overall completeness: **moderate** — functional enough to start, but insufficient to ship without resolving key ambiguities.

---

## Goals with Missing or Weak Acceptance Criteria

### Goal 1 — Activation
> "Alt+Space global hotkey starts recording from any foreground app."

**Gap:** "Any foreground app" is untested by definition without a target app list. No acceptance criterion defines what % of apps must work, or which apps are in-scope for MVP verification.

**Needed:** Define a minimum target app list (e.g., VS Code, Chrome, Notepad, Outlook Web, Windows Terminal) and state that hotkey activation must work in all of them. Also: hold-to-record vs. toggle is still an open question (OQ #3) — this is a core UX decision that must be resolved before implementation.

---

### Goal 2 — Transcription Accuracy
> "≥ 90% word accuracy on typical dictation (prose, commands, names)."

**Gap:** No reference test set or benchmark is defined. "Typical dictation" is subjective. There is no acceptance test (e.g., a specific corpus, sentence list, or test methodology).

**Needed:** Define a representative test corpus (even 20–30 sentences covering prose, technical terms, and names). State whether 90% WER is measured on `base`, `small`, or both. Specify whether filler words count toward WER before or after post-processing.

---

### Goal 3 — Latency
> "≤ 3 seconds from speech end to text-at-cursor on a mid-range PC (Core i5 / no dedicated GPU)."

**Gap:** "Mid-range PC" is not precisely specified (which Core i5 generation? RAM? Storage speed?). The measurement point is ambiguous: does the 3s clock start at recording stop signal or at silence detection cutoff?

**Needed:** Specify a reference test machine (e.g., "Intel Core i5-10th gen, 8 GB RAM, SSD"). Clarify start/stop timing for the latency measurement. Define what model size this applies to.

---

### Goal 5 — Filler Word Removal
> "'um', 'uh', 'like', 'you know' stripped before insertion."

**Gap:** Open Question #6 is unresolved: is the filler list hardcoded or user-configurable? The acceptance criterion as written implies hardcoded but does not confirm. No acceptance test is defined (e.g., a test phrase containing each filler word).

**Needed:** Close OQ #6. State the exact hardcoded list if not configurable. Define a simple acceptance test ("given input containing X, output should not contain X").

---

### Goal 6 — Auto-punctuation
> "Basic sentence-end punctuation added where Whisper leaves gaps."

**Gap:** "Basic sentence-end punctuation" and "where Whisper leaves gaps" are both undefined. No criteria for what constitutes a gap, what punctuation is added, or when auto-punctuation should NOT fire (e.g., mid-sentence dictation). Open Question #7 (additive vs. replacement) is unresolved.

**Needed:** Close OQ #7. Define "basic punctuation" (period only? comma? question mark?). Provide example inputs/outputs. Define when auto-punctuation should not apply.

---

### Goal 7 — Recording Overlay
> "Clear, minimal visual indicator of recording state (idle / recording / processing)."

**Gap:** No position, size, dismissal behavior, or visual spec is given. "Clear" and "minimal" are subjective. No acceptance test is defined.

**Needed:** At minimum, specify position (e.g., bottom-right corner), that it must not steal focus, and that it must disappear within N seconds of text insertion. A wireframe or pixel spec is not required but the behavioral contract should be explicit.

---

### Goal 8 — System Tray Daemon
> "App runs as background process, minimal RAM footprint (< 500 MB with model loaded)."

**Gap:** RAM limit is defined (good), but there's no CPU idle constraint, no startup time constraint, and no definition of "minimal." No measurement methodology is given (which task manager metric? private bytes?).

**Needed:** Specify idle CPU target (e.g., < 1% at rest). Clarify memory measurement (private working set). Add a startup time constraint if first-run model warm-up is user-facing.

---

### Goal 10 — Silence Detection
> "Auto-stops recording after configurable silence timeout."

**Gap:** "Configurable" implies a UI setting, but the tray menu spec (U6) only mentions model info, hotkey adjustment, and quit. No range or default is defined. Open Question #5 is unresolved.

**Needed:** Close OQ #5. State the default timeout value. Confirm whether this setting appears in the tray menu or a config file.

---

## Unresolved Open Questions That Block Implementation

The following open questions are **not optional** — they must be resolved before implementation begins:

| # | Question | Why It Blocks Implementation |
|---|----------|------------------------------|
| OQ 1 | Hotkey configurability | Determines whether a settings/config layer is needed |
| OQ 2 | Which Whisper model for MVP | Affects latency, accuracy, and installer size directly |
| OQ 3 | Push-to-talk vs. toggle | Core UX interaction; changes the hotkey listener logic |
| OQ 4 | Clipboard fallback acceptable? | Determines fallback path and required test matrix |
| OQ 5 | Silence timeout default/range | Required for Goal 10 acceptance |
| OQ 6 | Filler word list: hardcoded vs. configurable | Required for Goal 5 acceptance |
| OQ 7 | Auto-punctuation: additive vs. replacement | Required for Goal 6 acceptance |
| OQ 10 | Error states for mic denial/not found | Defines required error handling surface area |
| OQ 11 | Concurrent recording prevention | Defines required state machine behavior |

OQ 8 (GPU support) and OQ 9 (packaging format) are lower urgency but should be resolved before the first release candidate.

---

## Well-Defined Requirements (No Action Needed)

- **Goal 4 — Text injection:** Mechanism specified (`SendInput`), fallback noted (clipboard), target apps implied by user stories. Could be more explicit but is sufficient.
- **Goal 9 — 100% local:** Acceptance is binary and clear: zero outbound network calls. Easily testable.
- **Non-Goals:** Complete and unambiguous — good boundary setting.
- **User Stories U1–U6:** Concrete and sufficient to derive acceptance tests for core flows.
- **Constraints:** Well-stated technical constraints; business constraints are honest.

---

## Recommended Actions (Priority Order)

1. **Resolve OQ 3** (push-to-talk vs. toggle) — core UX, everything else depends on it.
2. **Resolve OQ 2** (model selection) — sets latency and accuracy baseline.
3. **Close OQ 5, 6, 7** (silence timeout, filler list, punctuation approach) — required to complete Goals 5, 6, 10.
4. **Add acceptance tests** for Goals 2 and 3 (accuracy corpus + latency test machine spec).
5. **Resolve OQ 10, 11** (error states, concurrent recording) — required for a complete state machine.
6. **Specify overlay behavior** (Goal 7) with at least position and dismissal rules.
7. **Resolve OQ 1, 4, 8, 9** before first release candidate.
