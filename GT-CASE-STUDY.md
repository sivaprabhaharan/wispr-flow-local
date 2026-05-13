# Building Software with an AI Workforce: A Gas Town Case Study

**How we used Steve Yegge's multi-agent orchestration system to build a voice-to-text app — from idea to shipped code — without writing a single line ourselves.**

---

## The Setup

Imagine handing a software project to a team of AI agents that plan it, design it, implement it, review it, test it, and submit it for merge — autonomously, in sequence, with persistent state and version control at every step.

That's Gas Town (GT). And we tried it.

This article documents our experience using GT to build **Wispr Flow Local** — a fully offline, privacy-first voice-to-text daemon for Windows. The app listens for a push-to-talk hotkey (Alt+Space), records audio, transcribes it using a local Whisper model, and injects the text directly at the cursor. No cloud, no clipboard contamination, no telemetry.

We started with nothing but an idea. Gas Town ended with 11 Python modules, a full test suite with 197 passing tests, a post-implementation code review, and a CHANGELOG. This is how it happened.

---

## What Is Gas Town?

[Gas Town](https://github.com/gastownhall/gastown) is Steve Yegge's open-source multi-agent orchestration system. The core insight behind it is deceptively simple: **AI agents work best when they have a clear job, a bounded scope, and a real filesystem to operate in.**

GT isn't a prompt chain. It isn't a chat interface. It's closer to a software engineering organisation — with roles, work tracking, merge queues, and Git at the centre of everything.

### The Mental Model

Think of it as a small engineering team:

| GT Concept | Human Analogy |
|---|---|
| **Mayor** | Engineering manager — coordinates everything, boots rigs |
| **Polecat** | Individual engineer — does the actual work in a Git worktree |
| **Rig** | A project / repo — each project has its own rig |
| **Convoy** | A tracked objective — like an epic or sprint goal |
| **Formula** | A reusable workflow template — like a runbook |
| **Bead** | A unit of work — like a Jira ticket |
| **Sling** | The command that assigns a bead to a polecat |
| **Wisp** | A molecule instance — a formula being executed |
| **Refinery** | The merge bot — processes the merge queue |
| **Witness** | A watchdog — monitors polecat health |

Let's unpack a few of these.

---

## GT Concepts in Depth

### Mayor

The Mayor is the central coordinator. It runs as a persistent daemon (in a tmux session), watching for signals, dispatching work to polecats, and maintaining the global state of all rigs. You start the Mayor once:

```bash
gt mayor start
```

Everything else flows from there.

### Polecat

A Polecat is the unit of AI execution. Each polecat is an isolated Copilot CLI session running in its own Git worktree. When you sling a bead to a polecat, it:

1. Creates a fresh branch off master
2. Reads its assignment from the bead
3. Does the work (writing code, running commands, etc.)
4. Commits the result
5. Submits an MR (merge request) to the merge queue
6. Goes idle, ready for the next assignment

Multiple polecats can work in parallel. Each has a name (`obsidian`, `quartz`, `jasper`, `onyx`) and runs completely independently.

### Beads

Beads are tracked via [beads (bd)](https://github.com/bevrin/beads) — a lightweight JSONL-backed issue tracker. Every piece of work in GT is a bead. Beads have:

- A unique ID (`wfl-wfs-7kptc`)
- A type (`task`, `mr`, `convoy`, `molecule`)
- Status (`OPEN`, `IN_PROGRESS`, `CLOSED`)
- Dependencies (`→ depends on`, `← blocks`)
- Notes and args attached by the agent

This gives you a full audit trail of what each agent did and why.

### Convoy

A Convoy is a tracked objective that groups related beads. Think of it as the "wrapper" around a multi-step workflow. Our shiny formula created convoy `hq-wf-4txva` which tracked all 5 steps of the build.

### Formula (Molecule)

Formulas are reusable workflow templates. They define a sequence of steps, each becoming a bead. GT ships with built-in formulas:

- **`mol-idea-to-plan`** — takes a product idea, generates a PRD and 6-dimension review
- **`shiny`** — "Engineer in a Box": design → implement → review → test → submit
- **`mol-polecat-work`** — wraps any task in a polecat work loop

Formulas are themselves defined as beads (molecules), making them composable and versioned.

### Sling

`gt sling` is the workhorse command. It assigns a bead to a rig (and optionally a specific polecat) and kicks off execution:

```bash
gt sling <bead-id> <rig> --force --agent copilot -a "<instructions>"
```

The `-a` argument is freeform text appended to the agent's system prompt. This is where you inject context, constraints, and directions.

### Refinery

The Refinery is the automated merge bot. It runs as its own Copilot CLI session and watches the merge queue. When a polecat submits an MR, the refinery:

1. Checks out the branch
2. Verifies it's safe to merge
3. Merges to master
4. Cleans up the branch
5. Runs `gt mq post-merge` to close the MR bead

This mimics a CI/CD pipeline, but driven by an AI agent rather than YAML.

### Witness

The Witness is the health watchdog. It monitors polecat sessions and nudges them if they go idle. This handles the common failure mode where an agent gets stuck waiting for input.

---

## The Project: Building Wispr Flow Local

### Why This Project?

[Wispr Flow](https://wisprflow.ai) is a commercial voice-to-text app. We wanted to build a local-first clone — same push-to-talk UX, but running entirely on-device using [faster-whisper](https://github.com/SYSTRAN/faster-whisper). No API calls, no cloud sync, no subscription.

It's the kind of project that would normally take a week for a competent Python developer: a few hundred lines across a handful of modules, some Windows API calls, a system tray icon, and a local ML model. Exactly the right scope to validate GT.

### Step 0: The Setup Journey (and the Honest Account)

Before we could run a single formula, we had to get GT running. This took longer than expected — not because GT is hard, but because of our environment.

**First attempt: Windows native**

GT is built in Go and requires Dolt (a SQL database for structured state) and `beads` for issue tracking. Installing these on Windows was straightforward. Building GT from source (`go build ./cmd/gt`) worked first time.

But running the full stack on Windows revealed friction: shell path assumptions, line ending issues, and most critically — the corporate TLS interceptor (PwC's proxy strips and re-signs all HTTPS traffic). Every `gh` CLI call, every `copilot` API request, every Go module download needed the corporate CA certificate injected.

**Second attempt: Docker**

We containerised the whole GT stack. This gave us a clean Linux environment and solved the TLS problem once we baked the corp cert into the image. But we hit a new problem: **Dolt desync**.

GT uses two layers of state: `beads` writes to JSONL files, while Dolt provides a SQL query layer over those files. The two need to stay in sync. In Docker with bind mounts (Windows NTFS ↔ Linux), the file notification events that trigger Dolt's sync were unreliable. Agents would write a bead, then `gt hook` couldn't find it because Dolt was stale.

We wrote monitoring scripts (`auto-dolt-fix.sh`) to force-sync Dolt every few seconds. It helped, but the deeper issue was Docker Desktop itself — after a few hours of load, the Docker daemon started returning 500 errors on its named pipe. It crashed entirely, and no amount of restarts fixed it.

**Third attempt: WSL2 native — the one that worked**

The winning approach: run GT natively inside WSL2 Ubuntu, with the GT workspace at `/mnt/c/gt` (the Windows `C:\gt` directory accessed via WSL2's NTFS mount).

```bash
# Install all prerequisites in WSL2
sudo apt-get install -y git sqlite3 nodejs npm
# Install Go, beads, dolt, Copilot CLI, build gt from source
```

No Docker. No bind mount hacks. No daemon crashes. WSL2's Linux kernel handles the filesystem events cleanly, Dolt stays in sync, and the Copilot CLI runs natively with full terminal support.

The one remaining friction: **Copilot CLI's trust prompt**. Every new polecat session starts in a new Git worktree path, and Copilot asks:

```
Do you trust the files in this folder?
  1. Yes
  2. Yes, and remember this folder for future sessions
  3. No
```

This dialog blocks the agent — it can't proceed until a human clicks through. We handled it by sending keystrokes to the tmux pane:

```bash
tmux -L gt-82deb2 send-keys -t wfl-obsidian Down Enter
# "Down" selects option 2 (remember), "Enter" confirms
```

This became our standard "accept trust" ritual before each formula step.

---

## The Shiny Formula: Engineer in a Box

With GT running in WSL2, we launched the `shiny` formula — GT's flagship end-to-end development workflow. Shiny runs five sequential steps, each as a separate bead dispatched to a polecat.

### Step 1: Design (wfl-wfs-pjvt2)

We created a design bead with this instruction:

```
Design Wispr Flow Local MVP. Read the PRD. Create DESIGN.md with:
full component architecture, module breakdown with APIs, data flow
diagram (ASCII), state machine, dependency table, file structure.
```

Polecat `quartz` picked it up, read the PRD we'd generated with `mol-idea-to-plan`, and produced **DESIGN.md** — 579 lines, 24KB of architecture documentation covering:

- Component diagram (ASCII)
- 10-module breakdown with per-module API contracts
- Inter-thread communication model via `queue.Queue` and `threading.Event`
- AppState enum and state machine transitions
- Complete dependency table with version pins
- File structure

Human time spent: accepting one trust prompt and one Copilot device auth.

### Step 2: Implement (wfl-wfs-7kptc)

With DESIGN.md merged to master, we slung the implement bead:

```
Implement Wispr Flow Local MVP following DESIGN.md architecture.
Read DESIGN.md first. Create all 10 modules: config.py, state.py,
hotkey_listener.py, audio_capture.py, silence_detector.py,
transcriber.py, post_processor.py, text_injector.py, overlay.py,
tray.py, plus main.py orchestrator.
```

Polecat `obsidian` churned for about 8 minutes, producing **47.5KB of output**. What it built:

| File | Lines | Purpose |
|---|---|---|
| `main.py` | ~200 | Orchestrator, tkinter mainloop, thread coordination |
| `overlay.py` | ~120 | Frameless always-on-top tkinter overlay |
| `injector.py` | ~110 | Windows SendInput + clipboard fallback |
| `hotkey.py` | ~100 | pynput global keyboard hook |
| `tray.py` | ~80 | pystray system tray icon |
| `audio.py` | ~70 | sounddevice microphone capture |
| `transcriber.py` | ~57 | faster-whisper integration |
| `silence.py` | ~55 | RMS-based voice activity detection |
| `postprocessor.py` | ~40 | Filler word removal |
| `state.py` | ~35 | Thread-safe state machine |
| `config.py` | ~25 | Central constants |

Plus `requirements.txt`, `pyproject.toml`, `README.md`, and `models/base/.gitkeep`.

The polecat ran `gt done --pre-verified --target master`, which pushed the branch to the merge queue. The Refinery processed it, merged to master, and pushed to GitHub — all automatically.

### Step 3: Review (wfl-wfs-e3psw)

The review bead asked a polecat to read DESIGN.md and all Python modules, check correctness, and fix critical bugs in-place.

What obsidian found after **30KB of analysis**:

1. **Focus-stealing in `overlay.py`** — the overlay was calling `root.lift()` and `root.focus_force()`, which steals keyboard focus from the active window. This would break text injection entirely, because the target window loses focus before SendInput fires.

2. **MODEL_DIR path issue** — `transcriber.py` was checking `Path(model_path).exists()` which returns `True` for the directory even when `model.bin` is absent, preventing the auto-download fallback from triggering. (We hit this exact bug when testing.)

3. **Missing try/finally in `injector.py`** — clipboard contents were saved before paste injection but not restored in a `finally` block. A mid-injection exception would leave garbage on the user's clipboard permanently.

4. **No tray notification when both injection methods fail** — DESIGN.md specified a tray balloon notification as the last-resort failure signal, but the architecture made it impossible for `injector.py` to signal back to the tray.

5. **Race condition in `_quit()`** — the shutdown sequence could call `overlay.destroy()` before the tkinter mainloop had finished processing queued callbacks.

The polecat fixed all five bugs in-place and committed: `fix: review MVP implementation, fix 5 critical bugs`.

### Step 4: Test (wfl-wfs-eztje)

The test bead was the most impressive step. Instructions:

```
Write comprehensive tests for Wispr Flow Local MVP using pytest.
Mock all hardware dependencies (microphone, keyboard, display).
Test state transitions, silence detection, post-processing rules,
error handling paths.
```

Obsidian installed pytest (`sudo apt-get install -y python3-pytest`), wrote 12 test files, ran them, fixed failures, and iterated — all autonomously. Final result: **197 tests passing**, covering:

- State machine transitions (all valid and invalid paths)
- Silence detection threshold logic
- Filler word removal edge cases  
- `SendInput` failure → clipboard fallback path
- Overlay show/hide lifecycle
- Tray icon creation and menu callbacks
- Model load failure handling
- Thread shutdown sequencing

The entire test suite runs without a microphone, display, or Windows — all hardware is mocked via `sys.modules` patching in `conftest.py`.

### Step 5: Submit (wfl-wfs-jkqf6)

The final step polished the project for release:

- Created `CHANGELOG.md` with a complete record of all work done across steps 1–4
- Expanded `README.md` with installation instructions, usage guide, development setup, and project structure
- Verified `pyproject.toml` metadata (`name`, `version = "0.1.0"`, console script entry point)
- Committed and submitted

Total GT pipeline wall-clock time: **~3 hours** (including setup, trust prompts, and Refinery processing). Agent compute time across all steps: roughly 25 minutes of active Claude Sonnet 4.6 inference.

---

## What the Polecats Actually Produced

The complete output, merged to master on GitHub:

```
wispr-flow-local/
├── main.py            # 200 lines — orchestrator, App class, mainloop
├── config.py          # 25 lines  — hotkey, timeouts, model settings
├── state.py           # 35 lines  — AppState enum, thread-safe StateManager
├── hotkey.py          # 100 lines — pynput push-to-talk listener
├── audio.py           # 70 lines  — sounddevice capture, MicrophoneError
├── silence.py         # 55 lines  — RMS VAD, configurable threshold
├── transcriber.py     # 57 lines  — faster-whisper, auto-download fallback
├── postprocessor.py   # 40 lines  — filler removal, punctuation
├── injector.py        # 110 lines — SendInput + clipboard, try/finally
├── overlay.py         # 120 lines — tkinter frameless overlay, no focus-steal
├── tray.py            # 80 lines  — pystray tray icon, quit handler
├── tests/
│   ├── conftest.py    # shared fixtures, sys.modules hardware mocks
│   ├── test_config.py
│   ├── test_state.py
│   ├── test_audio.py
│   ├── test_silence.py
│   ├── test_hotkey.py
│   ├── test_transcriber.py
│   ├── test_postprocessor.py
│   ├── test_injector.py
│   ├── test_overlay.py
│   ├── test_tray.py
│   └── test_main.py   # 332 lines
├── DESIGN.md          # 579 lines — full architecture spec
├── REVIEW.md          # post-implementation bug analysis
├── CHANGELOG.md       # release history
├── README.md          # install, usage, dev setup
├── requirements.txt   # pinned deps
└── pyproject.toml     # package metadata, entry point
```

Every file was written by a polecat. We wrote zero production code.

---

## Challenges and Honest Assessment

### What Worked Well

**The formula abstraction is genuinely powerful.** Being able to say "run the shiny formula on this rig" and have a coherent design → implement → review → test → submit pipeline execute autonomously is remarkable. The polecats respected the DESIGN.md spec, read prior steps' output, and built on each other's work correctly.

**Git as the coordination layer is brilliant.** Because all work is backed by Git branches and merge queues, you always have a clear record of what each agent did. Branches are named after beads (`polecat/obsidian/wfl-wfs-7kptc@mp2l6lfy`), so you can trace any commit back to the exact bead, formula step, and agent session that produced it.

**The review step found real bugs.** The focus-stealing overlay bug would have caused a complete failure of the core feature. The clipboard `finally` block was a real crash risk. Automated code review as a first-class formula step is a pattern every team should adopt.

**197 tests, zero effort.** Writing a comprehensive test suite for a project of this scale would take a developer a day or two. The polecat did it in under 15 minutes of wall time, including installing pytest, mocking all hardware dependencies, iterating on failures, and hitting 100% pass rate.

### What Was Hard

**The trust prompt problem.** Copilot CLI's folder trust dialog blocks execution every time a polecat starts in a new worktree path. GT has a `trustedFolders` config in `~/.copilot/settings.json` that's supposed to handle this, but it only prefix-matches and the worktree paths are deeply nested. We ended up scripting tmux keystrokes to accept every trust prompt. This is a fixable issue — Copilot CLI's trust logic needs to match on parent directories — but it was a recurring friction.

**Dolt desync in Docker.** The GT state layer (JSONL beads + Dolt SQL) requires reliable filesystem notifications for sync. Docker on Windows (bind mounts over NTFS) doesn't provide these reliably. We spent several hours debugging "issue not found" errors that were caused by Dolt being 5–10 seconds stale. Solution: don't use Docker. Run natively in WSL2 instead.

**The Refinery needs babysitting.** The Refinery is itself a Copilot CLI session that processes merge queues. If it dies (or hits its own trust prompt), MRs sit in "ready" state indefinitely. We had to manually run `gt mq post-merge` and cherry-pick commits several times. In a production GT setup, the Refinery needs to be more resilient — either auto-restarting or replaced with a simpler deterministic merge script.

**Agent state sync warnings are noisy.** Every sling produces warnings like:
```
⚠ Warning: SetAgentState attempt 1 failed, retrying in 425ms: issue not found
```
These are benign (the agent proceeds anyway) but add visual noise and confusion. Understanding which warnings to ignore vs. act on takes experience.

**No parallelism in shiny.** The shiny formula is sequential by design — implement waits for design, review waits for implement. This is correct for a causal dependency chain, but GT supports parallel polecats and we didn't explore that. For projects where steps are independent (e.g. multiple services), GT's multi-polecat capability could dramatically compress timelines.

---

## Lessons Learned

### 1. Invest in the design bead

The implement polecat's quality was directly proportional to the quality of DESIGN.md. Because we gave the design step thorough instructions (ASCII diagrams, per-module API contracts, state machine, dependency table), the implementation was coherent and architecturally sound on the first pass. If you give GT a vague design spec, you'll get vague code.

### 2. WSL2 is the right runtime environment (on Windows)

Docker adds too many layers between GT and the filesystem. Native Linux or WSL2 is the correct GT runtime. If you're on a Mac or Linux machine, you have the ideal environment out of the box.

### 3. The `-a` argument is your steering wheel

When you sling a bead, the `-a` flag appends to the agent's instructions. This is your primary lever for quality control. Be specific about what to read, what to create, what constraints apply, and what "done" looks like. Vague instructions produce vague output.

### 4. The Refinery is optional — you can merge manually

If the Refinery is unreliable in your environment, skip it. The polecat's work is on a branch. You can review the diff, cherry-pick to master, and push manually in 30 seconds. GT doesn't require the Refinery — it just automates a step you'd do anyway.

### 5. Beads are your audit trail

Every step of the project is recorded as a bead with notes, timestamps, and commit references. `bd show <bead-id>` gives you a full picture of what an agent did and why. This is surprisingly valuable for debugging and retrospectives.

### 6. Trust the review step

We almost skipped the review step, thinking "the implement polecat already did a good job." Don't. The five bugs the review polecat found — particularly the focus-stealing overlay — would have been hard to diagnose at runtime. The review step is cheap (10–15 minutes) and disproportionately valuable.

---

## How to Adopt GT in Your Team

Gas Town is not a research prototype. It's an opinionated, working system. Here's a practical path to adoption:

### Start with `mol-idea-to-plan`

Before writing any code, run GT's PRD formula on your next feature. Give it a one-paragraph description of what you want to build. It will produce:

1. A structured PRD with problem statement, user stories, and constraints
2. A 6-dimension review (requirements, gaps, ambiguity, feasibility, scope, stakeholders)

This is useful even if you never run another GT formula. The quality of the PRD output consistently surprises people.

### Use `shiny` for greenfield features

For new modules, services, or tools where you start from a blank file, shiny is the right formula. The design → implement → review → test flow produces genuinely production-quality output for well-scoped features.

### Set your agent to Claude Sonnet 4.5+ / GPT-4.1+

GT works with any Copilot CLI-compatible model. We used Claude Sonnet 4.6. The quality of output scales with model quality — use the best model your budget allows for the implement and review steps.

### Keep bead descriptions concrete

The bead description is what the polecat reads. Write it like a ticket: specific acceptance criteria, references to design docs, explicit constraints. "Implement the audio capture module per section 3.2 of DESIGN.md, using sounddevice, 16kHz mono, 100ms chunks" is far better than "write the audio module."

### Run GT on a Linux box or WSL2

Set up a dedicated WSL2 instance (or a small Linux VM) as your GT environment. Keep it running. The initial setup (install Go, beads, dolt, Copilot CLI, build gt) takes about 20 minutes with the install script. After that, starting a rig for a new project is a two-command operation.

---

## Conclusion

Gas Town represents a qualitative shift in how we can approach software development. It's not autocomplete. It's not a chatbot that writes functions on demand. It's an engineering organisation — with roles, process, version control, and accountability — where the engineers happen to be AI agents.

What struck us most wasn't the code quality (which was good) or the speed (which was impressive). It was the **coherence**. The review step read the implementation and caught bugs that were real. The test step read both the design and the implementation and wrote tests that reflected the actual architecture. The submit step read everything and wrote accurate documentation. Each polecat built on the work of the previous one, without us doing anything except accepting trust prompts.

The friction is real — the trust prompts, the Dolt sync quirks, the need for a stable WSL2 environment. But these are solvable infrastructure problems, not fundamental limitations of the approach.

The fundamental approach — persistent AI agents with Git-backed state, formula-driven workflows, and a merge queue for coordination — is sound. Gas Town is worth your team's attention.

---

## Appendix: Key Commands Reference

```bash
# Boot GT for a project
cd /mnt/c/gt
gt mayor start
gt rig boot wispr_flow_local

# Run the PRD formula
gt sling <prd-bead> wispr_flow_local --agent copilot -a "Product idea: ..."

# Sling the shiny formula
gt sling <bead-id> wispr_flow_local --force --agent copilot -a "<instructions>"

# Accept polecat trust prompt
tmux -L gt-82deb2 send-keys -t wfl-<polecat> Down Enter

# Check bead status
bd show <bead-id>
bd list --type task

# Check merge queue
gt mq list wispr_flow_local

# Manual post-merge (if Refinery is slow)
gt mq post-merge wispr_flow_local <mr-id>

# Check polecat output
tmux -L gt-82deb2 capture-pane -t wfl-obsidian -p -S -100
```

---

## References

- [Gas Town on GitHub](https://github.com/gastownhall/gastown)
- [Welcome to Gas Town — Steve Yegge](https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04)
- [Wispr Flow Local — source repo](https://github.com/sivaprabhaharan/wispr-flow-local)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [beads issue tracker](https://github.com/bevrin/beads)

---

*Written by Siva Jayakumar — based on a real GT session using GitHub Copilot CLI (Claude Sonnet 4.6).*
