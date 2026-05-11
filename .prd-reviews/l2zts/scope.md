# Scope Analysis: Wispr Flow Local (PRD Review)

**Issue:** wfl-leg-ycz4a  
**Reviewer:** polecat quartz  
**PRD:** `.prd-reviews/local-voice-text/prd-draft.md`

---

## Summary

The PRD has a well-defined Non-Goals section, but several features in the Goals list belong there for MVP. Two Goals (filler word removal, auto-punctuation) add post-processing complexity with modest user value, and several Open Questions reveal latent scope expansion (model selection UI, configurable hotkeys, configurable thresholds). The core product is simple and strong; the risk is shipping with marginal features that delay launch or introduce bugs.

---

## MVP Core: What Stays

These six capabilities constitute the actual product. Everything else is additive.

| Goal | Feature | Why it's MVP |
|------|---------|--------------|
| 1 | Global hotkey (Alt+Space, **fixed**) | The entire UX gesture — non-negotiable |
| 2, 9 | Local Whisper transcription, offline | The privacy promise and the product |
| 3 | ≤3s latency on mid-range CPU | Without this, UX is broken |
| 4 | Text injection at active cursor | The output — non-negotiable |
| 7 | Recording overlay (idle/recording/processing) | User must know system state |
| 8 | System tray daemon, <500MB RAM | Background operation model |
| 10 | Silence auto-stop (**fixed** threshold) | Prevents runaway recordings |

---

## Cut for MVP

### Goal 5 — Filler Word Removal

**Recommendation: Cut. Ship as v1.1.**

**Why it's in scope creep territory:**
- Requires a post-processing pass after transcription with a hardcoded or configurable word list.
- Open Question 6 (hardcoded vs. user-configurable list) is unanswered — if configurable, it implies a settings UI. If hardcoded, it's arbitrary.
- Whisper already omits many fillers contextually (it predicts likely text, not verbatim audio). The incremental value over raw Whisper output is smaller than it appears.
- False positives exist: "like" is a filler in "I was like, tired" but not in "I like this approach." A naive removal pass will corrupt content.
- This is a differentiating feature worth having eventually, but shipping a buggy filler remover is worse than not shipping one.

**If kept:** Scope must be locked to a hardcoded list of unambiguous fillers only (`um`, `uh`, `uh-huh`). `like`, `you know`, `so`, `basically` are context-dependent and must be excluded.

---

### Goal 6 — Auto-Punctuation Post-Processing

**Recommendation: Cut. Rely on Whisper's native output.**

**Why it's in scope creep territory:**
- Whisper already predicts punctuation using its language model. The native output includes sentence-ending periods, commas, and question marks for most typical dictation.
- Building a separate punctuation pass (Open Question 7: additive vs. replacement?) requires either a rules engine or another ML model — both are significant scope.
- An additive pass risks double-punctuation. A replacement pass risks overwriting correct Whisper output.
- "Basic sentence-end punctuation added where Whisper leaves gaps" sounds minimal but is undefined: what are the rules? How are gaps detected? This is under-specified and risky.

**If kept:** Scope must be locked to a single rule: append a period if the transcript ends without terminal punctuation. Nothing more.

---

### GPU Support (Open Question 8)

**Recommendation: CPU-only for MVP. GPU is v1.1.**

**Why:**
- CUDA support via `faster-whisper` requires shipping CUDA DLLs or requiring user to have CUDA installed. PyInstaller packaging with CUDA is "known to be finicky" (PRD's own words).
- GPU detection logic adds code complexity and a new failure mode (detected but unusable GPU).
- The latency goal (≤3s on Core i5) is achievable with `int8`-quantized `base` model on CPU — the PRD's own rough approach section states "~1–2× real-time on a modern Core i5."
- GPU is a meaningful performance enhancement for users with capable hardware, but it is not required for the product to work.

**OQ8 resolution:** CPU-only for MVP. Detect and use GPU in v1.1 once packaging is stable.

---

## Resolve Now: Open Questions That Are Scope Decisions

These Open Questions are not design questions — they are undecided scope. Leaving them open invites feature creep during implementation.

### OQ1 — Hotkey Configurability

**Resolve as:** Fixed `Alt+Space` for MVP. No configuration UI.

Configurable hotkeys require a settings surface (tray submenu or settings window), input validation, conflict detection, and persistence. This is non-trivial UI scope. The IME conflict (noted in OQ1) can be documented in the README as a known limitation.

### OQ2 — Model Selection in Tray

**Resolve as:** Fixed to `base` model for MVP. No model selection UI.

Model selection requires: UI, download management, model swapping without restart, and disk space accounting. The `base` model (≈150MB) hits the accuracy target for typical dictation on a Core i5 within the latency budget. `small` can be offered in v1.1 if users report accuracy issues.

### OQ5 — Configurable Silence Threshold

**Resolve as:** Hardcoded 2-second threshold for MVP.

Configurable silence threshold implies a settings surface and persisted preference. Hardcode 2s. Expose configuration in v1.1 if user feedback demands it.

### OQ6 — Configurable Filler Word List

**Moot:** Filler word removal is cut (see above). If filler removal is retained, hardcode the list.

---

## Latent Tension: Accuracy vs. Latency Goals Are Mutually Exclusive on the Target Hardware

**The PRD asserts both:**
- Goal 2: ≥90% word accuracy → requires `base` or `small` model
- Goal 3: ≤3s latency on Core i5 → requires `tiny` or `base` model

The "rough approach" states `base` at `int8` runs at ~1–2× real-time on a Core i5. For a 5-second dictation clip, that's 5–10 seconds of transcription time — **exceeding the 3-second target**. For a 10-second clip (typical dictation paragraph), the gap is worse.

This is not an edge case; it is the common case. The PRD does not acknowledge this tension. It must be resolved before implementation:

**Option A:** Accept that the latency target applies to short clips (≤3s speech) only. Document this.  
**Option B:** Use `tiny` model, accept lower accuracy, and adjust the 90% WER target to ~85%.  
**Option C:** Use `base` on GPU (requires reconsidering OQ8 for latency-sensitive users).

**Recommendation:** Option A — define the latency target as applying to clips of 5 seconds or less, and add a note that longer dictation has proportionally higher latency. This is honest and achievable without changing architecture.

---

## Scope Creep Risk Register

| Risk | Trigger | Mitigation |
|------|---------|------------|
| Filler removal bugs ship | OQ6 left open, feature kept | Cut filler removal OR lock to 3 unambiguous fillers |
| Model selection UI added mid-build | OQ2 left open | Resolve as fixed `base` model now |
| Settings window scope grows | OQ1 (hotkey) + OQ5 (silence) left open | Resolve both as hardcoded for MVP |
| GPU packaging breaks installer | OQ8 left open | CPU-only for MVP, document as known limitation |
| Punctuation pass introduces regressions | Goal 6 kept and under-specified | Cut Goal 6, rely on Whisper native output |
| Accuracy/latency conflict surprises late | Goals 2 and 3 unreconciled | Define latency target scope (clips ≤5s) before first test |

---

## Recommended MVP Feature Set (Final)

**In:**
- Global hotkey (Alt+Space, fixed)
- Local Whisper `base` model transcription (CPU, `int8`)
- Text injection via `SendInput` + clipboard fallback
- System tray daemon + tray menu (model info, quit)
- Recording overlay (3 states: idle / recording / processing)
- Silence auto-stop (2s hardcoded)
- 100% offline, no telemetry

**Out (MVP):**
- Filler word removal
- Auto-punctuation post-processing
- GPU support
- Hotkey configurability
- Model selection UI
- Configurable silence threshold

**Latency target clarification needed:**
- ≤3s applies to clips ≤5s in duration on Core i5 with `base` int8 CPU

This scope yields a shippable, coherent product. The cuts are all additive features — none removes core value. Each cut item is a clear candidate for v1.1.
