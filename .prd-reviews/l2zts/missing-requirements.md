# Missing Requirements Review
**PRD:** Local Privacy-First Voice-to-Text for Windows (Wispr Flow Local)  
**Leg:** wfl-leg-36pgk  
**Reviewer:** polecat onyx  
**Date:** 2026-05-11

---

## Summary

This review identifies requirements not present in the PRD — gaps, unstated assumptions, missing edge cases, and overlooked scenarios that could cause design pivots or user-facing failures if discovered late. These are distinct from the acceptance criteria gaps noted in the completeness review; they are things the PRD does not mention at all.

---

## Missing Functional Requirements

### MF1 — First-Run Experience / Model Download
The PRD states model files are 150–300 MB but does not specify how they are delivered. If bundled in the installer, the installer is 300+ MB with no model-size tradeoff. If downloaded on first run, the app needs:
- A progress indicator during download
- Error handling for interrupted downloads (partial file)
- Offline-first users cannot use the app until download completes
- A decision: is the app usable at all before the model is present?

**None of this is specified.**

### MF2 — Model Warm-Up / Cold Start
The PRD mentions "First run is slow (model warm-up)" in Open Risks but does not define:
- What the user sees during warm-up (tray spinner? tooltip?)
- Whether the hotkey is disabled until the model is ready
- Whether warm-up happens at app launch or on first recording attempt
- What happens if the user presses the hotkey during warm-up

**The warm-up UX is entirely unspecified.**

### MF3 — Output Text Encoding / Language Handling
Even in English-only mode, speech can contain:
- Special characters (em-dash, ellipsis, curly quotes) that Whisper may output
- Numbers in digit form vs. word form ("three" vs. "3")
- URLs, email addresses, code identifiers (`camelCase`, `snake_case`)
- Emoji or symbols in surrounding text that could confuse `SendInput`

No policy is defined for how the post-processor should handle these cases.

### MF4 — Newline / Paragraph Injection
How does the app handle dictated paragraph breaks? If a user says "new line" or "new paragraph," should the app inject `\n` or `\r\n`? This is a common dictation pattern with no mention in the PRD. Different target apps expect different line endings.

### MF5 — App Update Mechanism
There is no mention of how the app updates itself. Given no cloud dependency is a core value, a silent auto-updater would conflict with the privacy stance. But with no updater, users on old versions get no bug fixes. This decision has security and UX implications and is unaddressed.

### MF6 — Crash Recovery / Restart Behavior
What happens if the app crashes mid-recording? Does the partial audio get transcribed? Does the app restart automatically? Does it show a notification? No crash or restart behavior is defined.

### MF7 — Multiple Microphone Devices
The PRD assumes a single default microphone. Missing:
- What if the user has multiple audio input devices (headset + built-in mic)?
- Is the input device selectable in the tray menu or config?
- What if the preferred device is disconnected while recording?

### MF8 — Hotkey Conflicts / Registration Failure
The PRD mentions hotkey conflicts in constraints but does not specify what the app does when registration fails (e.g., another app already owns Alt+Space):
- Silent failure? (user can't record, doesn't know why)
- Tray notification?
- Fallback hotkey?
- Does the app start at all, or refuse to launch?

### MF9 — Accessibility and Elevated-Window Injection
The PRD notes that UAC-elevated windows block `SendInput` from non-elevated processes, but does not define the user-facing behavior:
- Does the app silently fail? Show a notification?
- Is there a fallback (clipboard paste) in this case?
- If clipboard fallback is used, does it restore the previous clipboard contents?

### MF10 — Clipboard Contamination
If the clipboard fallback path is used (OQ #4), the user's clipboard contents are overwritten. There is no requirement to save and restore the prior clipboard contents, even though this is a significant UX regression for users who had something copied.

---

## Missing Non-Functional Requirements

### MNF1 — Security / Process Isolation
A keylogger-like process (global hotkey + keyboard injection) is a high-value attack surface. The PRD does not address:
- Code signing (mentioned only as "users may need to click through SmartScreen")
- Integrity of the model file (no checksum/verification requirement)
- Whether the audio buffer is zeroed after transcription (in-memory privacy)
- Whether the app logs keystrokes or transcripts anywhere (even to a local file)

### MNF2 — Disk Usage / Log Rotation
No requirement for disk footprint beyond the model size. If the app logs errors (implied by error states in OQ #10), log files must not grow unboundedly. No log rotation or size limit is defined.

### MNF3 — Startup at Login (Autostart)
The app is described as a "system tray daemon" but there is no requirement for autostart on Windows login. Users who expect it to be always-available need it in the startup registry or Task Scheduler. This is a common expectation for tray apps and is entirely absent from the PRD.

### MNF4 — Windows Power Events (Sleep/Hibernate/Resume)
Audio devices are often reset on system resume from sleep. The PRD does not define behavior when:
- The system sleeps during recording (audio device disappears mid-capture)
- The system resumes and the audio device reattaches
- The hotkey listener survives sleep/resume cycles

### MNF5 — Multi-Monitor / High-DPI Displays
The overlay (Goal 7) must render correctly on:
- Multi-monitor setups (which monitor does it appear on?)
- High-DPI / 4K displays (DPI scaling; Tkinter has known issues here)
- Mixed-DPI setups (primary monitor at 100%, secondary at 150%)

No display or DPI requirements are defined.

### MNF6 — Screen Reader / Accessibility Compatibility
No accessibility requirement exists. The overlay and tray icon provide no accessibility metadata. For the target user (developer, journalist) this may be low priority, but it is entirely unaddressed.

---

## Unstated Assumptions

### UA1 — Single User / Single Session
The PRD implicitly assumes a single Windows user session. Behavior on multi-session machines (Remote Desktop, Fast User Switching) is undefined. In particular:
- Can two users run the app simultaneously?
- Does the model load per-session or is it shared?
- Does a hotkey registered in one session bleed into another?

### UA2 — English-Language OS
The PRD targets English speech but assumes nothing about the OS locale. A user running Windows in Japanese with an English-speech workflow is a real case (developers in non-English markets). The filler-word list and punctuation logic may behave differently based on OS locale settings.

### UA3 — Always-On Microphone Permission
The PRD assumes microphone access is granted. Windows 10/11 privacy settings can block microphone access per-app. OQ #10 touches this but only as an error state — there is no requirement for the app to detect microphone permission status proactively and guide the user to the Settings page.

### UA4 — Whisper's Output Is Plain Text
Whisper can output SRT/VTT format, timestamps, and token probabilities depending on the API flags used. The PRD assumes plain text output from `faster-whisper` but does not specify which output mode is requested or how to handle unexpected structured output.

### UA5 — User Is Actively Using the Foreground Window
Text injection assumes the focus is in a text input field. If the user has a read-only pane focused (e.g., a PDF viewer, a locked cell in Excel, a terminal with no active command), the text is silently discarded. No requirement exists to detect injection failure and notify the user.

### UA6 — Dictation Burst Duration
The latency goal (≤ 3s) applies to "typical 5–10s dictation bursts" (from the Rough Approach section). This is an undeclared assumption. Users may dictate 30–60 second passages. The app must either:
- Stream chunks to the transcriber (adds complexity)
- Buffer the full recording and process after stop (latency grows linearly)
- Set a maximum recording duration

No maximum duration, chunking strategy, or long-dictation behavior is specified.

---

## Missing Edge Cases in User Stories

### U1 (Developer in VS Code) — Code Dictation
VS Code may intercept Alt+Space for its own command palette or extension hotkeys. No story covers hotkey conflict resolution from the user's perspective.

### U3 (Browser / Outlook Web) — Textarea Focus Loss
If the user activates recording while focus is in a textarea, but focus shifts (e.g., a browser notification grabs focus) before injection, the text goes to the wrong target. No story or requirement addresses focus validation before injection.

### U4 (Silence Auto-Stop) — Background Noise
If the user is in a noisy environment, RMS-based silence detection may never trigger. The recording runs indefinitely. No maximum recording duration is defined, and no requirement exists for handling sustained ambient noise.

### U6 (Tray Icon) — Tray Overflow
On Windows, the system tray can overflow into a hidden area. The app's tray icon may not be visible by default. No requirement addresses discoverability or user onboarding to the tray icon.

---

## Recommended Additions to PRD

| Priority | Item | Section |
|----------|------|---------|
| P0 | Define model delivery method (bundled vs. downloaded) and first-run UX | Goals / Constraints |
| P0 | Specify warm-up behavior and hotkey-during-warm-up handling | Goals |
| P0 | Define behavior on `SendInput` failure (elevated window, read-only field) | Goals / Error States |
| P0 | Add autostart-on-login as a requirement (or explicitly exclude it) | Goals / Non-Goals |
| P1 | Define maximum recording duration and long-dictation strategy | Goals |
| P1 | Specify clipboard save/restore if clipboard fallback is used | Goals |
| P1 | Define hotkey registration failure behavior | Error States |
| P1 | Add multi-microphone device selection | Goals |
| P1 | Specify Windows sleep/resume behavior | Constraints |
| P2 | Add model file integrity check | Constraints |
| P2 | Define log policy (location, rotation, max size) | Constraints |
| P2 | Specify overlay behavior on multi-monitor / high-DPI | Goals |
| P2 | Address "number words vs. digits" output policy | Goals |
| P2 | Define newline injection behavior | Goals |
