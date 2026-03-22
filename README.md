# MPM — Multi Project Manager

MPM orchestrates multiple AI coding agents (Claude Code) across parallel projects, solving the core problem: **humans lose context when managing several AI-driven development sessions simultaneously.**

A dashboard provides visibility, a task system provides structure, and a harnessing layer ensures agents follow predictable workflows — even when the LLM is non-deterministic.

## Installation

```bash
uv tool install git+https://github.com/Lofi0Boy/MPM.git
mpm onboard      # port, timezone, workspace
mpm dashboard    # start web UI
mpm init         # initialize a project
```

---

## Core Concepts

### PPGT Hierarchy

MPM organizes work in four levels. Each level provides context and constraints for the level below.

```
Project (PROJECT.md)
  └─ Phase (phases.json)
       └─ Goal (phases.json)
            └─ Task (future/current/review/past)
```

| Level | What it is | Who creates | Example |
|-------|-----------|-------------|---------|
| **Project** | Name + description | Human + Planner | "MPM — Multi Project Manager" |
| **Phase** | Milestone with verifiable completion | Planner proposes, human approves | "MVP Dashboard" |
| **Goal** | User-facing capability within a phase | Planner writes | "Live task board with drag-and-drop" |
| **Task** | Atomic work unit for a dev agent | Planner writes | "Add WebSocket endpoint for task updates" |

Every task links to a goal via `parent_goal`. Phase progress = completed tasks / total tasks (discard excluded).

### ADV Foundation Documents

Three documents provide consistency across all agents. Planner creates and maintains them.

| Document | Purpose | Guides |
|----------|---------|--------|
| **ARCHITECTURE.md** | Engineering patterns, modules, data flow, conventions | Dev: how to structure code |
| **DESIGN.md** + `tokens/` | Design concept, rules, and token values (CSS/JS/JSON) | Dev: how things should look |
| **VERIFICATION.md** | Available verification tools and methods | Dev + Reviewer: how to verify work |

### Task Schema

All fields exist from creation. Progressively filled, never added or removed:

```json
{
  "id": "unique_id",
  "title": "One-line summary",
  "prompt": "Context and non-goals",
  "goal": "Verifiable acceptance criteria (set by planner)",
  "approach": "How to implement (set by dev)",
  "verification": "How to verify (set by planner)",
  "result": "Actual outcome (set by dev)",
  "memo": "Session summary (set by dev)",
  "status": "future|dev|agent-review|human-review|past",
  "agent_reviews": [],
  "human_review": null,
  "created": "YYMMDDHHmm",
  "session_id": null,
  "parent_goal": "goal_id"
}
```

| Field | Set by | When |
|-------|--------|------|
| `title`, `prompt`, `goal`, `verification`, `parent_goal` | Planner | Task creation |
| `approach` | Dev | After pop |
| `result`, `memo` | Dev | After work complete |
| `agent_reviews` | Reviewer | Each review cycle (appended) |
| `human_review` | Human | Final judgment |

### Task Lifecycle

```
future ──pop──→ dev ──result──→ agent-review ──pass──→ human-review ──approve──→ past
                 ↑                   │                                    │
                 └───────fail────────┘                              reject/discard
                                     │                                    │
                                  3x fail ──escalate──→ human-review      │
                                                                          ↓
                                                                        past
```

| Status | Location | Meaning |
|--------|----------|---------|
| `future` | `future.json` | Queued, waiting to be picked up |
| `dev` | `current/{session}.json` | Developer working |
| `agent-review` | `current/{session}.json` | Reviewer verifying |
| `human-review` | `review/{task_id}.json` | Awaiting human approval (dev freed) |
| `past` | `past/YYMMDD.json` | Done |

---

## Agents

### Planner

**Role:** Define vision, break down work, maintain foundation documents.

| | Detail |
|---|---|
| Model | Opus |
| Tools | Read, Grep, Glob, restricted Bash (`task.py add/status/remove/rejected/recycle`, `phase.py`), Write, Edit, WebSearch, WebFetch |
| Cannot | Edit source code, `task.py pop/create/update/complete/review` |
| Skills | mpm-init, mpm-init-design, mpm-task-write, mpm-recycle |
| maxTurns | 30 |

**Session start (deterministic):** `hook-planner-start.sh` injects all project docs, phase/task status, FEEDBACK.md, and a **gap directive** — the first missing foundation item. Planner follows the directive.

**Key responsibilities:**
- Fill foundation gaps (PROJECT → Phase → ARCH → DESIGN → VERIF → Goals → Tasks)
- Write `goal` and `verification` fields when creating tasks
- Recycle rejected tasks with rewritten prompts (`/mpm-recycle`)
- Keep ADV documents up to date as the project evolves

### Developer (default session)

**Role:** Execute tasks, write code.

| | Detail |
|---|---|
| Model | Inherited (user's default) |
| Tools | All tools |
| Cannot | `task.py add` (must go through planner), `task.py complete` (human only) |
| Skills | mpm-next, mpm-autonext |

**Workflow:** Pop a task → read pre-set `goal`/`verification` → fill `approach` → work → fill `result`/`memo` → auto-transition to `agent-review` → reviewer spawns.

**Hooks enforce:**
- No Edit/Write without a current task (block, with `.mpm/`/`.claude/` exceptions)
- "Spawn @planner" reminder on every prompt if no task exists
- Reviewer trigger on every Stop when status is `agent-review`

### Reviewer

**Role:** Independent quality verification with fresh context.

| | Detail |
|---|---|
| Model | Inherited |
| Tools | Read, Grep, Glob, restricted Bash (`task.py`, `curl`, `google-chrome`) |
| Cannot | Edit, Write, Agent (read-only) |
| maxTurns | 20 |

**Session start (deterministic):** `hook-reviewer-start.sh` injects task content, project docs, FEEDBACK.md, phase status, and git diff.

**Review checklist:**
1. Functionality — does it match goal? Run verification methods.
2. Usability — human perspective (readability, contrast, interactive elements)
3. Design consistency — tokens match? Hardcoded values?
4. Code quality — architecture patterns? Security concerns?

**Evidence required.** Must use appropriate verification methods (curl, tests, screenshots, browser automation, console logs — whatever fits the task).

**Verdicts:**
- `pass` → task moves to `review/` (human-review)
- `fail` → task returns to `dev` (dev fixes)
- `needs-input` → task moves to `review/` with question
- `modified` → task moves to `review/` with explanation

---

## Harnessing Strategy

### Control Layers

```
Deterministic (guaranteed)          Non-deterministic (agent judgment)
─────────────────────────           ──────────────────────────────────
Hooks                               Agent definitions (.claude/agents/)
  Shell scripts on lifecycle           Frontmatter: tools, model
  events. Can block, inject,           Body: behavioral guidance
  run commands. Cannot be              Agent may not follow 100%
  ignored.
                                    Skills (.claude/skills/)
Scripts (.mpm/scripts/)                Procedural knowledge
  task.py, phase.py                    Agent interprets steps
  Schema enforcement
  File locking                      Rules (.claude/rules/)
                                       Always loaded, shared constraints
```

### What is deterministic

- All hook triggers and block/pass decisions
- All `task.py`/`phase.py` operations and schema enforcement
- Status auto-transition: `dev` → `agent-review` when result is filled
- File move: `current/` → `review/` on reviewer pass (dev freed)
- Review spawn counter and 3x escalation
- Planner gap detection and directive injection
- Reviewer context injection (task, docs, git diff)
- FEEDBACK.md auto-append on human review
- File locking for concurrent access (`fcntl.flock`)

### What is non-deterministic

- Agent following skill instructions
- Agent spawning other agents when instructed by hooks
- Agent running verification methods
- Quality of review judgments
- Planner's prompt writing quality

### Defense Table

| Failure | Defense |
|---------|---------|
| Dev edits without task | `hook-pretool-task-check.sh` BLOCKS Edit/Write |
| Dev doesn't spawn reviewer | `hook-review.sh` re-triggers on every Stop |
| Dev skips review via `task.py complete` | `task.py` enforces: only `review/` → past |
| Reviewer doesn't call `task.py review` | Spawn counter tracks attempts, escalates after 3 |
| Reviewer passes bad work | Human review catches it |
| 3x reviewer fail | `task.py escalate` → `review/` for human judgment |
| Planner misses rejected tasks | `hook-planner-start.sh` detects and directs |
| Agent ignores skill steps | No defense (inherent LLM limitation) |

---

## Async Operations

### Planner ↔ Dev (async)

Designed for two separate terminals running simultaneously:

```
Terminal 1: claude --agent planner    → continuously creating tasks in future.json
Terminal 2: dev with /mpm-autonext    → continuously popping and executing tasks
```

`task.py` uses `fcntl.flock` on all `future.json` operations (`pop`, `add`, `remove`, `recycle`) to prevent corruption from concurrent access.

### Dev ↔ Reviewer (sync)

Reviewer runs as a **subagent** inside the dev session. Dev waits for the reviewer to finish. This is intentional — immediate feedback enables immediate fixes.

```
Dev fills result → agent-review → Stop hook blocks
  → Dev spawns @reviewer (blocking)
  → Reviewer: pass → task to review/, dev freed
  → Reviewer: fail → dev fixes immediately (same context)
```

### Dev ↔ Human Review (async)

After reviewer passes, the task moves from `current/` to `review/`. Dev is immediately freed to pick up the next task. Human reviews at their own pace via the dashboard.

```
Dev timeline:     [...work...] → reviewer pass → [next task] → [next task] → ...
Human timeline:                                    [...review queue...]
```

---

## Lifecycle Walkthrough

### 1. Project Init

```
mpm init (CLI)
  → copies templates (.mpm/, .claude/) to project
  → merges hooks into .claude/settings.json
  → registers project in ~/.mpm/config.json

First session → hook-init-check.sh detects missing PROJECT.md
  → Planner spawned → hook-planner-start.sh injects gap directive
  → Planner follows /mpm-init skill (10-step guided setup)
  → Result: PROJECT.md, Phase, ARCHITECTURE.md, DESIGN.md, VERIFICATION.md, Goals, Tasks
```

### 2. Planning

```
Planner session start:
  → hook-planner-start.sh injects: docs + status + FEEDBACK.md + gap directive
  → Planner follows directive (fill gaps or create tasks)

Task creation:
  → Planner runs /mpm-task-write
  → !`phase.py status` auto-injected — goals visible at skill load time
  → task.py add "title" "prompt" --goal "criteria" --verification "how" --goal-id <id>
```

### 3. Development

```
Dev runs /mpm-next or /mpm-autonext
  → task.py pop — goal and verification already set by planner
  → Dev fills approach, works, fills result + memo
  → result auto-transitions to agent-review
```

### 4. Agent Review

```
Stop hook fires → hook-review.sh detects agent-review
  → Blocks with "spawn @reviewer"
  → Dev spawns reviewer subagent
  → hook-reviewer-start.sh injects: task + docs + FEEDBACK.md + git diff
  → Reviewer checks functionality, usability, design, code quality
  → Collects evidence using appropriate verification methods
  → task.py review pass/fail/needs-input/modified
```

### 5. Human Review

```
Task in review/{task_id}.json — dashboard shows card with:
  → Title, reviewer summary, evidence (screenshots, logs)
  → Buttons: Approve / Reject / Discard

Approve  → task.py complete <id> success  → past + FEEDBACK.md
Reject   → task.py complete <id> rejected → past + FEEDBACK.md → planner recycles
Discard  → task.py complete <id> discard  → past + FEEDBACK.md (excluded from progress)
```

### 6. Feedback Loop

Every human review result is auto-appended to `.mpm/docs/FEEDBACK.md`:

```markdown
### [REJECTED] Dashboard card styling
- Date: 2026-03-22 18:30
- Goal: Apply card background/border tokens
- Comment: Insufficient color contrast
- Agent review: headless screenshot verified, curl 200 OK
```

This file is injected into both **planner** and **reviewer** sessions, enabling:
- Planner: writes more specific goals based on past rejections
- Reviewer: calibrates to human standards over time

---

## File Structure

```
.mpm/
├── data/
│   ├── future.json              # Task queue
│   ├── current/                 # Dev working (one per session)
│   ├── review/                  # Awaiting human review
│   ├── past/                    # Completed tasks by date
│   ├── phases.json              # Phase/Goal hierarchy
│   └── reviews/                 # Reviewer screenshots
├── docs/
│   ├── PROJECT.md               # Project name + description
│   ├── ARCHITECTURE.md          # Engineering patterns
│   ├── DESIGN.md                # Design concept/rules
│   ├── VERIFICATION.md          # Verification methods
│   ├── FEEDBACK.md              # Accumulated human review feedback
│   └── tokens/                  # Design token code files
└── scripts/
    ├── task.py                  # Task operations (pop, add, update, review, escalate, complete, recycle, etc.)
    ├── phase.py                 # Phase/Goal operations
    ├── hook-planner-start.sh    # SubagentStart: planner context + gap directive
    ├── hook-reviewer-start.sh   # SubagentStart: reviewer context + git diff
    ├── hook-review.sh           # Stop: trigger reviewer on agent-review
    ├── hook-autonext-stop.sh    # Stop: auto-next queue management
    ├── hook-pretool-task-check.sh  # PreToolUse: BLOCK edits without task
    ├── hook-task-reminder.sh    # UserPromptSubmit: show current task
    ├── hook-init-check.sh       # SessionStart: check PROJECT.md
    └── hook-notify.sh           # Dashboard status updates

.claude/
├── agents/
│   ├── planner.md               # Planning agent (Opus, restricted Bash, 4 skills)
│   └── reviewer.md              # Review agent (restricted Bash, maxTurns: 20)
├── skills/
│   ├── mpm-init/                # 10-step project initialization
│   ├── mpm-init-design/         # Design system setup
│   ├── mpm-task-write/          # Task writing with auto-injected goals
│   ├── mpm-next/                # Pop and execute next task
│   ├── mpm-autonext/            # Auto-process task queue
│   └── mpm-recycle/             # Recycle rejected tasks
├── rules/
│   └── mpm-workflow.md          # Task workflow rules (loaded every session)
└── settings.json                # Hook definitions
```

---

## Hook Reference

| Hook Event | Script | Trigger | Action |
|------------|--------|---------|--------|
| SessionStart | `hook-notify.sh active` | Every session | Dashboard status → active |
| SessionStart | `hook-init-check.sh` | Every session | Prompt planner if PROJECT.md missing |
| SessionStart | `hook-is-native-planner.sh` | `claude --agent planner` | Route to `hook-planner-start.sh` |
| SubagentStart | `hook-planner-start.sh` | @planner spawn | Inject docs + status + gap directive |
| SubagentStart | `hook-reviewer-start.sh` | @reviewer spawn | Inject task + docs + FEEDBACK + git diff |
| UserPromptSubmit | `hook-notify.sh working` | Every prompt | Dashboard status → working |
| UserPromptSubmit | `hook-task-reminder.sh` | Every prompt | Show current task or "spawn @planner" |
| PreToolUse | `hook-pretool-task-check.sh` | Edit\|Write | BLOCK if no task (`.mpm/`/`.claude/` exempt) |
| PermissionRequest | `hook-notify.sh waiting` | Permission needed | Dashboard status → waiting |
| Stop | `hook-notify.sh waiting` | Session stop | Dashboard status → waiting |
| Stop | `hook-review.sh` | Session stop | Trigger reviewer if `agent-review` |
| Stop | `hook-autonext-stop.sh` | Session stop | Auto-next queue management |
