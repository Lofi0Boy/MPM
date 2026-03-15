# MPM — Architecture

---

## 1. System Overview

MPM is a Python daemon that orchestrates multiple Claude Code CLI sessions, one per managed project. It is the control plane for the entire MpmWorkspace.

```
User
  ↕ (CLI / Web Dashboard / Telegram)
[MPM Daemon]
  ↕ (stdin/stdout, --resume session)
[PM Agent — Claude Code, cwd: MpmWorkspace/]
  ↕ (spawn/communicate)
[Sub-project Agents — Claude Code, cwd: ./project/]
  ↕ (local file system)
[Project files, git, logs]
```

---

## 2. Directory Structure

```
MPM/
├── README.md
├── CLAUDE.md
├── docs/
│   ├── ARCHITECTURE.md         # This document
│   ├── ROADMAP.md
│   └── handoff/
├── daemon/                     # Core orchestration process
│   ├── main.py                 # Entry point
│   ├── orchestrator.py         # Sub-agent lifecycle management
│   ├── verifier.py             # Task result verification
│   └── state.py                # In-memory + disk state store
├── data/
│   └── ideas.json              # Post-it notes storage (position, color, project)
├── dashboard/                  # Web UI
│   ├── server.py               # Flask server — project + ideas APIs
│   ├── projects.py             # ROADMAP/handoff parser
│   └── templates/index.html    # Board UI + post-it notes overlay
└── gateway/                    # I/O multiplexer
    ├── telegram.py             # Telegram bridge
    └── multiplexer.py          # Routes CLI I/O to channels
```

---

## 3. Agent Session Model

### One session per project
Each managed project has exactly one Claude Code CLI session, spawned at daemon startup and kept alive.

```python
sessions = {
    "saksak-kimchi": ClaudeSession(cwd="./saksak-kimchi", session_id="..."),
    "JHomelab_server": ClaudeSession(cwd="./JHomelab_server", session_id="..."),
    "JHomelab_app": ClaudeSession(cwd="./JHomelab_app", session_id="..."),
}
```

### Session lifecycle
```
Daemon start
  → spawn claude (cwd: project/)    ← reads CLAUDE.md + docs (one time)
  → work tasks via --resume
  → context compaction triggered
      → handoff auto-written (per CLAUDE.md rules)
      → session terminated
      → new session spawned          ← reads handoff, picks up context
  → continue
```

Context compaction is the natural session reset trigger. No separate timer or counter needed — Claude Code's own compaction event drives the cycle.

---

## 4. PM Agent

The PM Agent is also a Claude Code CLI session, running with `cwd: MpmWorkspace/`. It has access to all project files and documentation.

Responsibilities:
- Read ROADMAP.md of all projects to determine next tasks
- Decide which sub-project agents to spawn and with what instructions
- Evaluate sub-agent results and determine next action
- Write handoffs and update ROADMAP.md autonomously when outcome is clear
- Escalate to user when input is required

The PM Agent is not always queried — the Python daemon manages state. The PM Agent is consulted when judgment is needed (task planning, result evaluation, escalation decisions).

---

## 5. Parallel Sub-Agent Execution

Sub-project agents run in parallel. The daemon handles completions as they arrive.

```python
async def orchestrate(tasks: dict[str, str]):
    futures = {
        project: asyncio.create_task(session.send(task))
        for project, task in tasks.items()
    }
    for coro in asyncio.as_completed(futures.values()):
        project, result = await coro
        await evaluate_and_dispatch(project, result)
```

`evaluate_and_dispatch`:
- Clear success → update ROADMAP/handoff autonomously → queue next task
- Ambiguous → escalate to PM Agent for judgment
- User input required → notify via configured channel

---

## 6. Task Result Verification

Verification method depends on task type:

| Task Type | Verification Method |
|-----------|-------------------|
| Code changes | `git log`, `git diff`, test run output |
| API integration | Live API call + response log |
| UI changes | Headless Chrome screenshot (Playwright) |
| Running service | Health check endpoint, log tail |
| Build | Exit code + stdout parse |

---

## 7. User Communication Channels

CLI is the single source of truth. Other channels are views or I/O bridges on top of it.

```
Claude CLI stdout
      ↓
[I/O Multiplexer]
  ↙              ↘
Web Dashboard    Telegram Bridge
(renders output) (output → Telegram message)
                 (Telegram reply → stdin injection)
```

Channel routing:
- Telegram toggle (on/off per user preference)
- Web Dashboard always active (renders all CLI output)
- Telegram bridge only active when toggled on

---

## 8. State Management

The Python daemon owns all runtime state. State is held in memory and persisted to disk for crash recovery.

```python
@dataclass
class DaemonState:
    sessions: dict[str, SessionInfo]     # Per-project session IDs and status
    running_tasks: dict[str, TaskInfo]   # Active tasks per project
    pending: list[PendingDecision]       # Items awaiting user input
```

Persisted to `daemon/state.json` on every state change.
