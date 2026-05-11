# Ambiguity Analysis
**PRD:** Local Privacy-First Voice-to-Text for Windows (Wispr Flow Local)  
**Leg:** wfl-leg-osrny  
**Reviewer:** polecat onyx  
**Date:** 2026-05-11

---

## Summary

This review identifies unclear language, underspecified behaviors, and internally contradictory requirements in the PRD. These are not missing features — they are places where two reasonable engineers reading the same document would make different implementation decisions, or where the document says something that conflicts with something else it says.

---

## Ambiguous Terms

### A1 — "Any foreground app" (Goal 1)
> "Alt+Space global hotkey starts recording from any foreground app."

"Any" is unachievable and almost certainly not intended. The constraints section explicitly notes that UAC-elevated windows will block `SendInput`, and enterprise environments may block global hooks. "Any" conflicts with these known exceptions.

**Ambiguity:** Does "any" mean "all apps on Windows without exception" (impossible) or "all standard user-mode apps" (achievable)? The PRD never reconciles this.

**Suggested fix:** Replace "any" with "any standard user-mode foreground app" and add a parenthetical noting elevated-window limitations.

---

### A2 — "Approach Whisper `base` or `small` model accuracy" (Goal 2)
> "approach Whisper `base` or `small` model accuracy — target ≥ 90% word accuracy"

"Approach" is doing two jobs here:
1. Saying the accuracy should be *near* one of these models
2. Implying the app *uses* one of these models

If `faster-whisper` **is** the implementation using the `base` model, the phrasing "approach base accuracy" is circular — you'd exactly achieve it, not approach it. If it's saying the app should achieve accuracy *similar to* what cloud Whisper achieves on the same models, that's a different claim.

**Ambiguity:** Is the 90% target independent of which model is used, or is it specific to `base`? Does running `small` give a higher target? Open Question #2 (which model to use) is unresolved, so the accuracy target is floating.

---

### A3 — "Typical dictation" (Goal 2)
> "≥ 90% word accuracy on typical dictation (prose, commands, names)"

"Commands" is ambiguous in a voice-to-text context: does it mean voice commands (excluded in Non-Goals) or shell/code commands (e.g., "git commit dash m")? "Names" is also vague — proper nouns? Contact names? Place names? Technical identifiers?

**Ambiguity:** The parenthetical expands rather than constrains the term. Two engineers would test on very different corpora.

---

### A4 — "No clipboard required" (Goal 4)
> "Inserted text appears in the *active* window — works in IDEs, browsers, Outlook, Notepad, WSL terminals. No clipboard required."

The Rough Approach and Open Questions both discuss a clipboard fallback (OQ #4). The goal says "no clipboard required" which could mean:
1. The primary path does not use the clipboard (clipboard is optional/fallback only)
2. The app never uses the clipboard under any circumstances

These interpretations lead to different implementations. If interpretation (2) is correct, the clipboard fallback discussion in OQ #4 is moot — but then elevated windows have no injection path at all.

**Contradiction:** The goal implies clipboard is forbidden; the open questions suggest it's an acceptable fallback.

---

### A5 — "Basic sentence-end punctuation" (Goal 6)
> "Basic sentence-end punctuation added where Whisper leaves gaps."

"Basic" is undefined. "Sentence-end" could mean only periods, or it could include question marks and exclamation marks. "Where Whisper leaves gaps" is undefined — Whisper already adds some punctuation; "gaps" implies post-processing fills what Whisper missed, but the threshold for "gap" is unspecified.

**Ambiguity:** Three undefined terms in one sentence. OQ #7 (additive vs. replacement) is directly related but unresolved.

---

### A6 — "Clear, minimal" (Goal 7)
> "Clear, minimal visual indicator of recording state"

"Clear" and "minimal" are subjective and potentially contradictory — maximizing clarity often means more prominent UI; minimizing UI often reduces clarity. No design reference, mockup, or behavioral spec is given.

**Ambiguity:** Unresolvable without a design decision. Two designers would produce entirely different overlays.

---

### A7 — "Minimal RAM footprint (< 500 MB with model loaded)" (Goal 8)
> "App runs as background process, minimal RAM footprint (< 500 MB with model loaded)."

500 MB is not "minimal" by most definitions — it's a ceiling. "Minimal" implies the app should use as little RAM as possible, but the parenthetical sets only an upper bound. These are different engineering objectives.

**Ambiguity:** Is the requirement "use as little RAM as possible" (optimisation goal) or "use less than 500 MB" (hard constraint)? The word "minimal" implies the former; the parenthetical specifies the latter.

---

### A8 — "Configurable silence timeout" (Goal 10)
> "Auto-stops recording after configurable silence timeout."

"Configurable" implies a user-facing setting. But the tray menu (U6) only lists "model info, adjust hotkey, or quit." There is no mention of a silence-timeout control in the UI, yet Goal 10 says it's configurable.

**Contradiction:** Goal 10 promises configurability; U6 describes a tray menu that doesn't include it. Is the setting in a config file? A separate settings panel? These are different implementation choices.

---

## Underspecified Behaviors

### U1 — Hold-to-Record vs. Toggle (OQ #3 presented as resolved)
Goal 1 says: "Same hotkey (or hotkey release) stops recording."

The phrase "or hotkey release" smuggles in a hold-to-record model, but the main clause "same hotkey stops recording" implies a toggle. These are different interaction models. The parenthetical reads as a hedge, not a decision. OQ #3 asks for confirmation of push-to-talk — this question exists because the goal text is itself ambiguous.

---

### U2 — Filler Removal Scope
> "um", "uh", "like", "you know" stripped before insertion.

It is not specified whether:
- Only exact standalone matches are stripped (e.g., "I like you" would NOT strip "like")
- Or whether the filler list applies to any occurrence (which would incorrectly strip "like" in normal usage)

This is a significant behavioral ambiguity. A naive implementation strips "like" everywhere; a correct one only strips it when used as a filler (requires context or heuristic).

---

### U3 — "Works in … WSL terminals" (Goal 4)
WSL (Windows Subsystem for Linux) terminals present a unique injection challenge: the terminal emulator (Windows Terminal, ConEmu, etc.) intercepts keyboard events differently than native Windows apps. Whether `SendInput` works reliably in WSL terminals depends on the terminal emulator, not WSL itself.

**Ambiguity:** Listing "WSL terminals" as a target without qualification implies a guarantee that may be impossible to deliver uniformly. It's unclear whether this means the Windows Terminal host process (feasible) or the Linux process inside WSL (not accessible via `SendInput`).

---

### U4 — "Zero network calls" (Goal 9)
> "Zero network calls. No API keys. Works offline."

"Zero network calls" is a strong guarantee. However:
- Does this apply to the Python runtime (which may phone home for package updates)?
- Does this apply to the PyInstaller-packaged app only?
- Does automatic update checking (if added) violate this requirement?
- Does telemetry/crash reporting violate this, or is telemetry excluded by definition?

"Zero network calls" as written is an architectural constraint that must be actively enforced, but the scope (which process? which component?) is undefined.

---

### U5 — "Polished text" (User Story U1)
> "Polished text appears at cursor in the open file."

"Polished" is used in the problem statement and user stories but never defined. It appears to mean "filler-removed + auto-punctuated," but it could also imply capitalization correction, grammar fixing, or other transformations. The scope of "polishing" is undefined.

---

## Internal Contradictions

### C1 — Privacy Goal vs. Packaging Reality
The PRD's core value proposition is "nothing leaves the device." However:
- The app requires Microsoft Visual C++ redistributable (Constraint section) — this is typically installed via a Microsoft-hosted installer, which requires an internet connection
- PyInstaller packaging may bundle the redistributable, eliminating the network call — but this is not stated

**Contradiction:** A first-install experience that requires downloading a runtime from Microsoft's servers contradicts "works offline" (Goal 9) and "100% local" framing unless the redistributable is fully bundled.

---

### C2 — "Background process" vs. Tray Icon Visibility
Goal 8 calls the app a "background process." U6 describes tray icon management. A tray icon is not invisible — it is a foreground UI element in the taskbar notification area. The term "background process" conflicts with having an interactive tray icon.

**Minor contradiction:** Likely a terminology choice ("background" meaning "not the active window"), but it creates confusion when reasoning about process model and Windows service vs. user-mode process distinctions.

---

### C3 — "No clipboard required" vs. Clipboard Fallback
(See A4 above.) This is the most significant internal contradiction: a stated goal that explicitly excludes clipboard use, alongside an open question that treats clipboard as an acceptable fallback. One of these must be resolved as authoritative.

---

### C4 — Silence Detection as Both Goal and Open Question
Goal 10 states silence detection is a feature with a "configurable" timeout. OQ #5 asks what the target silence duration is and whether configurability is needed in MVP. The goal treats configurability as settled; the open question treats it as unresolved.

**Contradiction:** If OQ #5 is genuinely open, Goal 10's wording should be conditional ("if configurable timeout is included…"), not declarative.

---

## Recommended Clarifications (Priority Order)

| Priority | Item |
|----------|------|
| P0 | Resolve "no clipboard required" vs. clipboard fallback (A4 / C3) — pick one |
| P0 | Resolve hold-to-record vs. toggle (U1) — rewrite Goal 1 to be unambiguous |
| P0 | Resolve Goal 10 vs. OQ #5 (C4) — decide configurability, update goal wording |
| P1 | Define "filler word stripping" scope — standalone only or any occurrence (U2) |
| P1 | Replace "any foreground app" with a scoped claim (A1) |
| P1 | Define "basic sentence-end punctuation" with examples (A5) |
| P1 | Reconcile "minimal RAM" language — optimisation goal or hard cap (A7) |
| P2 | Clarify "approach Whisper accuracy" — is it the model itself or a comparative benchmark (A2) |
| P2 | Clarify "WSL terminals" — Windows Terminal host or WSL process (U3) |
| P2 | Clarify scope of "zero network calls" — app binary only or full install lifecycle (U4) |
| P2 | Define "polished text" explicitly in the Goals section (U5) |
