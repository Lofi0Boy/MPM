# MPM — Multi Project Manager

MPM orchestrates multiple AI coding agents (Claude Code) across parallel projects, solving the problem of humans losing context when managing several AI-driven development sessions simultaneously.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    MPM Dashboard (Flask)                  │
│  Web UI: project cards, task board, terminal panels      │
│  API: /api/projects, /api/sessions, /api/refresh         │
│  Real-time: SocketIO (file watcher → project_changed)    │
└──────────────┬──────────────────────────────┬────────────┘
               │                              │
    ┌──────────▼──────────┐       ┌───────────▼───────────┐
    │   tmux sessions     │       │   .mpm/data/ (JSON)    │
    │   (per project)     │       │   future/current/      │
    │   + ttyd → xterm.js │       │   review/past/         │
    └─────────────────────┘       └────────────────────────┘
```

## Installation

```bash
# Install
uv tool install git+https://github.com/Lofi0Boy/MPM.git

# Initial setup (port, timezone, workspace)
mpm onboard

# Start dashboard
mpm dashboard

# Initialize a project
mpm init
```

---

## Agent Harnessing Strategy

MPM uses three specialized AI agents with distinct roles, controlled through a combination of **hooks** (deterministic triggers), **skills** (injected knowledge), **agent definitions** (role constraints), and **scripts** (data operations).

### The Three Agents

| Agent | Role | Can do | Cannot do |
|-------|------|--------|-----------|
| **Planner** | Define vision, break down work, maintain docs | Read all code/docs, write `.mpm/docs/`, `task.py add/status/remove`, `phase.py` | Edit source code, `task.py pop/create/update/complete/review/escalate` |
| **Developer** | Execute tasks, write code | All tools, `task.py pop/create/update` | `task.py add` (must go through planner), `task.py complete` (human only) |
| **Reviewer** | Independent quality verification | Read, Grep, Glob, Bash (read-only intent) | Edit, Write, Agent |

### Control Mechanisms

```
┌──────────────────────────────────────────────────────┐
│                  CONTROL LAYERS                       │
│                                                      │
│  Hooks (deterministic)                               │
│   └─ Shell scripts triggered by Claude Code events   │
│   └─ Can block, inject prompts, run commands         │
│   └─ Cannot be ignored by agents                     │
│                                                      │
│  Agent definitions (.claude/agents/*.md)              │
│   └─ Frontmatter: tools, model, skills, permissions  │
│   └─ Body: system prompt (behavioral guidance)       │
│   └─ Non-deterministic — agent may not follow 100%   │
│                                                      │
│  Skills (.claude/skills/*/SKILL.md)                   │
│   └─ Injected into agent context via frontmatter     │
│   └─ Procedural knowledge (step-by-step guides)      │
│   └─ Non-deterministic — agent interprets steps      │
│                                                      │
│  Rules (.claude/rules/*.md)                           │
│   └─ Always loaded into every session                │
│   └─ Shared behavioral constraints                   │
│   └─ Non-deterministic — agent may not follow 100%   │
│                                                      │
│  Scripts (.mpm/scripts/*.py, *.sh)                   │
│   └─ Deterministic data operations                   │
│   └─ task.py, phase.py: CRUD with schema enforcement │
│   └─ Agents must use these, not edit JSON directly   │
└──────────────────────────────────────────────────────┘
```

---

## Complete Lifecycle: From Init to Review

### Phase 1: Project Initialization

#### Trigger chain
```
mpm init (CLI)
  → copies templates (.mpm/, .claude/) to project
  → merges hooks into .claude/settings.json
  → registers project in ~/.mpm/config.json
  → notifies dashboard (POST /api/refresh → SocketIO project_changed)
```

#### First session
```
User opens Claude in project (or clicks "Start Project" on dashboard)
  → Dashboard: claude --agent planner "/mpm-init" [button click, deterministic]
  OR
  → SessionStart hook: hook-init-check.sh [deterministic]
    → PROJECT.md missing → outputs "run /mpm-init" message
    → Claude reads message + mpm-workflow.md rules [non-deterministic]
    → Spawns planner agent [non-deterministic]

Planner session starts:
  → planner.md body: "read all docs, check PPGT+ADV layers" [non-deterministic]
  → Finds PROJECT.md missing → follows mpm-init skill instructions [non-deterministic]
```

#### mpm-init skill flow
```
Step 1:  Scan project (README, package.json, git log)           [non-deterministic]
Step 2:  Share understanding with user                          [non-deterministic]
Step 3:  Project name + description → PROJECT.md                [user input + non-det]
Step 4:  Phase 1 definition → phase.py add                      [user input + non-det]
Step 5:  Write PROJECT.md                                       [non-deterministic]
Step 6:  ARCHITECTURE.md (AI proposes, user approves)           [non-deterministic]
Step 7:  DESIGN.md → delegates to mpm-init-design skill         [non-deterministic]
Step 8:  VERIFICATION.md (AI inspects tools, asks user)         [non-deterministic]
Step 9:  Goals → phase.py goal-add                              [non-deterministic]
Step 10: Tasks → follows mpm-task-write skill, task.py add      [non-deterministic]
```

#### mpm-init-design sub-flow
```
Option A: Reference URL → WebFetch → extract patterns → token file + DESIGN.md
Option B: User describes feeling → AI generates initial tokens
Option C: Analyze existing project code → extract/formalize tokens

Token files stored in: .mpm/docs/tokens/ (CSS/JS/JSON depending on stack)
DESIGN.md stored in: .mpm/docs/DESIGN.md (concept/rules only, not token values)
```

### Phase 2: Planning (Planner Agent)

#### Session start behavior
```
planner.md body instructs [non-deterministic]:
  1. Read all .mpm/docs/ files
  2. phase.py status
  3. task.py status
  4. Read latest past file
  5. Check for rejected tasks in past (human_review.verdict == "rejected")
     → create corrective tasks in future
  6. Check PPGT+ADV layers top-down → fill first gap found
```

#### Task creation
```
User describes feature request
  → mpm-workflow.md rules: "spawn @planner" [non-deterministic]
  → hook-pretool-task-check.sh: BLOCKS Edit/Write without task [deterministic]
  → hook-task-reminder.sh: "spawn @planner to create tasks" [deterministic message]

Planner spawned:
  → Reads project docs for context [non-deterministic]
  → Breaks request into small, verifiable tasks [non-deterministic]
  → Follows mpm-task-write skill instructions [non-deterministic]
  → task.py add --goal-id <id> for each task [deterministic script]
```

#### Foundation document maintenance
```
planner.md body instructs [non-deterministic]:
  Before creating tasks that touch a domain, re-read the relevant doc.
  If outdated or missing info → update doc BEFORE creating tasks.

  ARCHITECTURE.md: update when modules/patterns/dependencies change
  DESIGN.md: update when new component patterns or rules emerge
  Token files: update when new colors/spacing/typography needed
  VERIFICATION.md: update when tools/endpoints/processes change
```

### Phase 3: Development (Developer / Default Session)

#### Task execution
```
mpm-next skill or manual pop:
  → task.py pop ${SESSION_ID}              [deterministic: future → current, status: dev]
  → Dev reads task prompt                  [non-deterministic]
  → Dev fills goal/approach/verification   [non-deterministic]
  → Dev works on implementation            [non-deterministic]
  → Dev fills result + memo via task.py update [non-deterministic]
  → result fill auto-transitions status    [deterministic: dev → agent-review]
  → Claude stops → Stop hook fires         [deterministic]
```

#### Hooks during development
```
SessionStart:
  hook-notify.sh active          → dashboard status update [deterministic]
  hook-init-check.sh             → PROJECT.md check [deterministic]

UserPromptSubmit:
  hook-notify.sh working         → dashboard status update [deterministic]
  hook-task-reminder.sh          → shows current task or "spawn @planner" [deterministic]

PreToolUse (Edit|Write):
  hook-pretool-task-check.sh     → BLOCKS if no task [deterministic]

PermissionRequest:
  hook-notify.sh waiting         → dashboard status update [deterministic]

Stop:
  hook-notify.sh waiting         → dashboard status update [deterministic]
  hook-review.sh                 → triggers reviewer if status == agent-review [deterministic]
  hook-autonext-stop.sh          → auto-next queue management [deterministic]
```

### Phase 4: Agent Review (Reviewer Subagent)

#### Trigger
```
Dev fills result → status auto-transitions to agent-review [deterministic]
  → Claude stops → Stop hook fires [deterministic]
  → hook-review.sh checks [deterministic]:
    - status == agent-review? YES
    - last agent_reviews verdict is pass/needs-input/modified? → pass through
    - agent_reviews count >= 3? → task.py escalate (move to review/)
    - else: output block message "spawn @reviewer" [deterministic]

Dev reads block message → spawns reviewer subagent [non-deterministic]
```

#### Reviewer execution
```
Reviewer subagent (fresh context, no dev history):
  → reviewer.md body instructs [non-deterministic]:
    1. Read current task file (prompt, goal, verification, result)
    2. Read all project docs (PROJECT, ARCHITECTURE, DESIGN, VERIFICATION, tokens)
    3. phase.py status for context

  Review checklist [non-deterministic]:
    1. Functionality: does it match goal? run verification methods
    2. Usability: human perspective (formatting, contrast, readability)
    3. Design consistency: tokens match? hardcoded values?
    4. Code quality: architecture patterns? reusability? security?

  Evidence collection [non-deterministic]:
    - Screenshots → .mpm/data/reviews/
    - curl responses
    - test results

  Verdict → task.py review [deterministic]:
    pass        → current/ → review/ (human-review), dev freed
    fail        → stays in current/, status: dev (dev fixes, retry)
    needs-input → current/ → review/ (with question)
    modified    → current/ → review/ (with explanation)
```

#### Fail loop
```
Reviewer fail → status returns to dev [deterministic]
  → Dev fixes issues [non-deterministic]
  → Dev updates result → status auto-transitions to agent-review [deterministic]
  → Stop hook → hook-review.sh → reviewer spawn again [deterministic trigger]
  → Max 3 agent reviews → task.py escalate → review/ [deterministic]
```

### Phase 5: Human Review (asynchronous)

Dev and human review operate on **different timelines**. After agent-review passes, the task moves to `review/` and the dev is immediately freed to pick up the next task. Human reviews at their own pace.

#### Display
```
Dashboard watches review/ directory [deterministic]
  → Shows card with: title, reviewer summary, evidence (screenshots/logs)
  → Buttons: Approve / Reject / Postpone / Discard
```

#### Actions
```
Approve → API → task.py complete <task_id> success  → past [deterministic]
Reject + comment → API → task.py complete <task_id> rejected → past [deterministic]
Postpone → API → task.py complete <task_id> postpone → past + new card in future [deterministic]
Discard → API → task.py complete <task_id> discard → past [deterministic]

Rejected tasks:
  → Planner detects in past on next session start [non-deterministic]
  → human_review.verdict == "rejected" + human_review.comment
  → Creates corrective task in future [non-deterministic]
```

---

## Data Flow

### PPGT Hierarchy (Project → Phase → Goal → Task)

```
Project (PROJECT.md)          — human-driven, AI organizes
  └─ Phase (phases.json)      — AI proposes, human approves
       └─ Goal (phases.json)  — AI writes, human notified
            └─ Task (future/current/review/past) — AI autonomous
                  └─ parent_goal links Task → Goal for traceability
```

### ADV Foundation Documents

```
ARCHITECTURE.md  — engineering consistency (AI proposes, human approves)
DESIGN.md        — design concept/rules (human-driven for direction)
  └─ .mpm/docs/tokens/*  — actual token code files (tech-stack specific)
VERIFICATION.md  — self-verification methods (AI inspects + human input)
```

### Task State Machine

```
future (future.json, status: future)
  → dev (current/{session}.json) ─── via task.py pop
      → agent-review (current/) ─── via task.py update result (auto)
          → human-review (review/{task_id}.json) ─── via task.py review pass (dev freed)
              → past (success) ─── via human approve (task.py complete)
              → past (rejected) ─── via human reject → planner creates new task
              → past (postpone) ─── via human postpone + new card in future
              → past (discard) ─── via human discard
          → dev (current/) ─── via task.py review fail (dev fixes, retries)
          → human-review (review/) ─── via task.py escalate (3x fail)
```

### Task Schema

All fields exist from creation. Progressively filled, never added or removed:

```json
{
  "id": "unique_id",
  "title": "One-line summary",
  "prompt": "Detailed task instruction",
  "goal": null,
  "approach": null,
  "verification": null,
  "result": null,
  "memo": null,
  "status": "future",
  "agent_reviews": [],
  "human_review": null,
  "created": "YYMMDDHHmm",
  "session_id": null,
  "parent_goal": null
}
```

### File Ownership

| File | Planner | Dev | Reviewer | Human (Dashboard) |
|------|---------|-----|----------|-------------------|
| future.json | **write** (add/remove) | read + pop | — | — |
| current/*.json | — | **write** (pop/create/update) | **write** (task.py review) | — |
| review/*.json | read | — | — | **write** (task.py complete → past) |
| past/*.json | read | — | — | **write** (complete moves here) |
| phases.json | **write** (phase.py) | read | read | — |
| .mpm/docs/*.md | **write** | read | read | — |
| .mpm/docs/tokens/* | **write** | read | read | — |

---

## File Structure

```
.mpm/
├── data/
│   ├── future.json              # Task queue (Planner writes, Dev pops)
│   ├── current/                 # Tasks in progress (one per session)
│   │   └── {session_id}.json
│   ├── review/                  # Tasks awaiting human review
│   │   └── {task_id}.json
│   ├── past/                    # Completed tasks
│   │   └── YYMMDD.json
│   ├── phases.json              # Phase/Goal hierarchy
│   └── reviews/                 # Reviewer screenshots
├── docs/
│   ├── PROJECT.md               # Project name + description
│   ├── ARCHITECTURE.md          # Engineering patterns
│   ├── DESIGN.md                # Design concept/rules
│   ├── VERIFICATION.md          # Self-verification methods
│   └── tokens/                  # Design token code files
└── scripts/
    ├── task.py                  # Task CRUD (pop, create, add, update, review, escalate, complete, status, remove)
    ├── phase.py                 # Phase/Goal CRUD (add, remove, activate, goal-add, goal-done, status)
    ├── hook-init-check.sh       # SessionStart: check PROJECT.md
    ├── hook-notify.sh           # Status updates to dashboard
    ├── hook-task-reminder.sh    # UserPromptSubmit: show current task
    ├── hook-pretool-task-check.sh  # PreToolUse: BLOCK if no task
    ├── hook-review.sh           # Stop: trigger reviewer
    └── hook-autonext-stop.sh    # Stop: auto-next queue management

.claude/
├── agents/
│   ├── planner.md               # Planning agent definition
│   └── reviewer.md              # Review agent definition
├── skills/
│   ├── mpm-init/SKILL.md        # Project initialization steps
│   ├── mpm-init-design/SKILL.md # Design system setup
│   ├── mpm-task-write/SKILL.md  # Task writing guidelines
│   ├── mpm-next/SKILL.md        # Pop and execute next task
│   └── mpm-autonext/SKILL.md    # Auto-process task queue
├── rules/
│   └── mpm-workflow.md          # Shared rules (task workflow, review pipeline)
└── settings.json                # Hook definitions
```

---

## Deterministic vs Non-deterministic Summary

### Deterministic (guaranteed)
- All hook triggers (SessionStart, Stop, PreToolUse, UserPromptSubmit)
- All script operations (task.py, phase.py)
- Hook block logic (pretool-task-check BLOCKS edits without task)
- Status auto-transition: `dev` → `agent-review` when result is filled
- File move: current/ → review/ on agent-review pass (dev freed immediately)
- Review iteration counting and max enforcement (3x fail → escalate to review/)
- Task state transitions via scripts
- Dashboard API calls
- SocketIO real-time updates

### Non-deterministic (agent judgment)
- Agent following skill instructions
- Agent reading project documents at session start
- Agent spawning other agents when instructed by hooks
- Agent running verification methods
- Reviewer executing task.py review command
- Planner detecting rejected tasks in past
- Quality of review judgments

### Defenses for non-deterministic failures
| Failure | Defense |
|---------|---------|
| Dev edits without task | hook-pretool-task-check.sh BLOCKS Edit/Write [deterministic] |
| Dev doesn't spawn reviewer | hook-review.sh re-triggers on every Stop [deterministic] |
| Dev tries to skip review (task.py complete) | task.py enforces: only review/ → past [deterministic] |
| Reviewer doesn't run task.py review | hook detects agent-review status persists → re-triggers [deterministic] |
| Reviewer passes bad work | Human review catches it |
| 3x reviewer fail | task.py escalate → review/ for human judgment [deterministic] |
| Planner misses rejected tasks | No defense (relies on planner.md instructions) |
| Agent ignores skill steps | No defense (inherent LLM limitation) |
