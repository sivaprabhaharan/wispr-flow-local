# Stakeholder Analysis: Wispr Flow Local (PRD Review)

**Issue:** wfl-leg-fi67a  
**Reviewer:** polecat quartz  
**PRD:** `.prd-reviews/local-voice-text/prd-draft.md`

---

## Summary

The PRD identifies its primary audience well (power-user dictators, privacy-conscious professionals), but several actor groups with distinct needs and conflicts are absent or underdeveloped. The four areas flagged for review — privacy-focused users, enterprise IT, model licensing, and accessibility — each surface real tensions that could block adoption or cause post-launch friction.

---

## 1. Privacy-Focused Users

**Who they are:** The PRD names lawyers, journalists, developers, and executives — but treats "local = private" as self-evident. Privacy-focused users scrutinize that claim.

### Unconsidered needs

| Need | Why it matters |
|------|---------------|
| Verifiable localness | Sophisticated users won't take "no network calls" on faith. They want auditable code or network monitoring confirmation. A closed-source binary provides no assurance. |
| No telemetry / crash reporting | Many "local" apps phone home for analytics or auto-update checks. If this app does that, it violates the privacy promise even if transcription is local. |
| Secure model storage | Model files at rest in a known path could be tampered with. Users in sensitive environments may need checksum verification. |
| Auto-update concerns | Auto-update mechanisms make network calls by definition. Privacy users often disable them — the PRD must decide: no auto-update, or opt-in only. |
| Memory residency | Transcribed text may linger in process memory. Power users in high-security environments (air-gapped systems) want to know when buffers are cleared. |

### Conflicts

- **Privacy vs. convenience:** Cloud fallback would improve accuracy on difficult audio; the PRD correctly excludes it, but the friction of lower accuracy (local Whisper vs. cloud API) may frustrate users who thought local would be equally good.
- **Open-source vs. product control:** Privacy users trust auditable code. If the app is closed-source, the privacy promise is marketing, not architecture. The PRD does not address distribution model.
- **Crash reporting:** If the developer adds Sentry or similar (a natural impulse when debugging), that silently breaks the privacy guarantee. Must be an explicit never-do.

---

## 2. Enterprise IT / Security Teams

**Who they are:** IT administrators, security officers, and compliance teams at organisations where the primary users (lawyers, healthcare workers, executives) are employed. They were not mentioned at all in the PRD.

### Unconsidered needs

| Need | Why it matters |
|------|---------------|
| Code signing | Unsigned binaries trigger Windows SmartScreen. Enterprise AV/EDR tools (CrowdStrike, Defender for Endpoint) routinely block or quarantine unsigned executables. The PRD acknowledges SmartScreen warnings but only from a UX angle — IT will not approve deployment of an unsigned app. |
| Global keyboard hook = keylogger flag | `pynput` and `keyboard` register a global low-level keyboard hook. Every major EDR product flags global keyboard hooks as a keylogger pattern. IT security teams will block or alert on this. |
| No centralized deployment path | No MSI / SCCM / Intune package is mentioned. Enterprise users can't self-install on managed machines. This effectively locks out enterprise unless IT builds their own packaging. |
| Policy conflicts | Alt+Space is used by some enterprise tools (Windows IME, certain KVM switches, GoToMeeting/Zoom overlays). The PRD notes the conflict exists but doesn't provide a resolution path. |
| Elevated-process injection | The PRD mentions UAC-elevated windows blocking `SendInput` as an "open risk." In enterprise environments, many line-of-business apps run elevated. This is a showstopper for large segments of enterprise use. |
| Compliance documentation | HIPAA-covered healthcare orgs, SOC 2-compliant tech companies, and legal firms need a data processing statement. "It's local" is not a compliance artefact — it needs to be a documented, auditable claim. |

### Conflicts

- **Single-developer scope vs. enterprise requirements:** Code signing costs money (EV cert ≈ $400–700/year); MSI packaging takes time. These conflict with the "MVP: single developer, no external funding" constraint. The PRD must explicitly state whether enterprise is a future goal or a non-goal.
- **Security tools vs. functionality:** There is no known workaround for EDR products that block global keyboard hooks. The app fundamentally cannot work in some enterprise environments without IT whitelisting. This should be surfaced as a hard constraint, not an open risk.

---

## 3. Model Licensing

**Who they are:** The developer as distributor, and downstream users in commercial contexts. Model licensing affects what the developer can legally do.

### Current state

The PRD selects `faster-whisper` (MIT-licensed wrapper around CTranslate2) running OpenAI Whisper model weights. OpenAI released Whisper weights under the **MIT license**, which permits commercial use and redistribution. This is generally favourable.

### Unconsidered issues

| Issue | Detail |
|-------|--------|
| Bundling model weights in installer | The installer size note (150–300 MB) implies bundling. MIT permits this, but the license file must be shipped with the weights. If models are downloaded at first run instead, the download source (OpenAI CDN vs. Hugging Face Hub) has its own terms. |
| Hugging Face Hub ToS | If the app auto-downloads models from HF Hub at first run, it invokes HF's Terms of Service, which include restrictions on automated scraping and require attribution. First-run model download is not a neutral technical choice. |
| Future model versions | OpenAI could release future Whisper variants under a more restrictive license (as they have with other products). The PRD ties architecture to faster-whisper but doesn't address how model updates are managed. |
| Commercial use ambiguity | If this app is ever monetized (sold, subscription, freemium), the MIT license still permits it — but OpenAI's *API* terms (not applicable here, but easily confused) do not. If users or journalists ask "can this be used commercially?", the developer needs a clear answer ready. |
| Third-party model variants | Users may want to swap in fine-tuned Whisper variants (e.g., for medical vocabulary). Fine-tuned models may carry different licenses. The PRD's non-goal of custom models avoids this for MVP, but the architecture should not make it impossible to support later. |

### Conflicts

- **Bundled model vs. download-on-first-run:** Bundling simplifies UX but balloons installer size and may require shipping license files. Download-on-first-run is lighter but breaks offline-first use (Goal 9: 100% local, works offline) and requires internet on setup. These goals are in tension.
- **Model size vs. accuracy goal:** The 90% WER target may require `small` (300 MB) rather than `base` (150 MB). Open Question 2 in the PRD is unresolved; resolving it has direct licensing/distribution implications.

---

## 4. Accessibility Users

**Who they are:** Users with motor disabilities (for whom voice input is a primary interface), users with visual impairments, and users with speech differences. This is ironic: the app IS an accessibility tool, yet its own UI may not be accessible.

### Unconsidered needs

| Need | Why it matters |
|------|---------------|
| Push-to-talk requires sustained key hold | Alt+Space as a hold-to-record mechanism requires the user to maintain continuous key pressure. Users with motor disabilities (tremor, limited hand strength, one-handed input) may be the most motivated users of voice input, but push-to-talk physically excludes them. |
| Hotkey conflicts with AT software | NVDA (NonVisual Desktop Access), JAWS, and Windows Narrator each define their own global hotkeys. Alt+Space is used by NVDA. Users relying on both a screen reader and this app face an irreconcilable conflict. |
| Visual-only recording indicator | The recording overlay is the only state indicator. Users with visual impairments won't know the app is recording. An audio cue (brief tone) or system notification fallback is absent from the design. |
| Screen reader incompatibility of overlay | A `Tkinter Toplevel` with `overrideredirect=True` removes the window from the accessibility tree. Screen readers cannot detect or describe this overlay. The tray menu may also be inaccessible depending on implementation. |
| Non-standard speech patterns | Users with speech impediments (stuttering, dysarthria) have measurably lower Whisper accuracy. The 90% WER target is benchmarked against "typical dictation" — it degrades significantly for non-standard speech. The PRD should acknowledge this limitation. |
| Toggle vs. push-to-talk | Toggle mode (press to start, press to stop) is far more accessible than push-to-talk. Open Question 3 in the PRD asks about this but frames it as UX preference, not accessibility requirement. |

### Conflicts

- **Minimal UI vs. accessibility:** The design philosophy is "zero UI friction" and "silent tray." Accessible UI requires describable states, keyboard navigation, and screen-reader hooks — the opposite of invisible. These goals conflict.
- **Accuracy expectations:** The 90% WER target could be stated with a qualification that accuracy degrades for non-standard speech — setting expectations and avoiding ableist assumption that all dictation input is the same.
- **Push-to-talk as default:** If push-to-talk ships as the only mode (per the current spec), it excludes a significant segment of exactly the users most likely to need voice input. Toggle mode should be at minimum an MVP option, not a future goal.

---

## 5. Additional Unconsidered Actors

### App developers / ISVs (indirect)
Apps that block keystroke injection (elevated processes, game launchers, some Electron apps, admin tools) will produce silent failures — text simply won't appear. The end user blames Wispr Flow Local, not the target app. The PRD acknowledges this risk but doesn't define error UX: the user must know *why* injection failed and what to do (e.g., "use clipboard fallback" or "run as administrator").

### Regulated industry professionals (under-specified)
The lawyer scenario in U5 is underdeveloped. HIPAA-covered healthcare professionals, SOC 2-scoped enterprise users, and legal professionals with attorney-client privilege obligations need:
- A data handling statement (even one sentence: "no data ever leaves this device")
- Clarity that RAM buffers are not persisted to disk after transcription
- No hidden temp files written during transcription

These aren't technical blockers, but their absence makes procurement impossible for regulated industries — a significant segment of the target market.

---

## Recommended Actions for PRD

| Priority | Action |
|----------|--------|
| 🔴 High | Add accessibility requirements: toggle mode as MVP option, audio feedback for recording state, confirm NVDA/JAWS hotkey conflict and offer hotkey reconfiguration |
| 🔴 High | Resolve model distribution strategy (bundle vs. download) before architecture commits to installer design |
| 🔴 High | Add explicit no-telemetry / no-network commitment to Goals section (not just implied by "100% local") |
| 🟡 Medium | Add Enterprise IT to Non-Goals or commit to code signing — do not leave it ambiguous |
| 🟡 Medium | Document global keyboard hook security implications and provide IT administrator guidance |
| 🟡 Medium | Add failure UX for injection failures (elevated window, blocked app) — not just an open risk |
| 🟢 Low | Add one-paragraph data handling statement for regulated industry users |
| 🟢 Low | Clarify licensing provenance (MIT Whisper weights + CTranslate2) in project README at launch |
