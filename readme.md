# Asynchronous Human & AI — Spec-driven task queue system for AI coding agents

## AHA Solves What

I was running multiple Claude Code sessions. Every time one finished, it wanted my attention — while I was mid-thought on something else.
Context-switching was killing my focus.

So I tried batching tasks, but the results were a mess — broken UI/UX, buggy code, contradictory decisions. I spent more time finding where it went wrong than doing actual work.

So I combined two strategies:

- **Spec-driven development** — Architecture, design, and verification specs that every task is planned, built, and reviewed against. AI agents stay consistent because they share a single source of truth.
- **Task queue system** — A queue of tasks that AI agents process automatically, collecting results into a review queue. I come back when *I'm* ready, not when Claude demands attention.

The spec-driven system is based on [GStack](https://github.com/nicholasgriffintn/gstack) by Garry Tan (CEO of Y Combinator) and [Next Level Builder's ui-ux-pro-max skill](https://github.com/anthropics/claude-code-templates/tree/main/ui-ux-pro-max) for UI/UX specs.

```
 You                                     AHA Planner                    AHA Developer
─────                                    ───────────                    ─────────────
Tell what to build           →       Create specs & tasks
                                                              →   Dev → Auto-review → Next
...work on another project...                                     Dev → Auto-review → Fix → Next
...do your actual work...                                         Dev → Auto-review → Next
...be there for someone you love...                               Dev → Auto-review → Next
Come back when ready                                          →   Review queue waiting for you
```

## Prerequisites

- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Windows: [Git for Windows](https://git-scm.com/downloads/win) required for Claude Code hook execution

## Installation

```bash
cd <your-project-dir>
git clone --depth 1 https://github.com/Lofi0Boy/AHA.git _aha_tmp
cp -r _aha_tmp/templates/.aha _aha_tmp/templates/.claude .
rm -rf _aha_tmp
```

To uninstall, remove `.aha/` and `aha-` prefixed files from `.claude/`.

## Usage

Two sessions recommended (Planner ↔ Developer) for parallel work.

### 1. Init

```bash
# Planner Session
claude --agent aha-planner /aha-init
```

Create and elaborate foundation docs (`PROJECT.md`, `ARCHITECTURE.md`, `DESIGN.md`, `VERIFICATION.md`).
Then generate phases, goals, and tasks from the specs.

Takes ~30 min, but 10x payoff.

### 2. Auto-next

```bash
# Developer Session
claude --dangerously-skip-permissions /aha-autonext  # skip permissions for unattended execution
```

Pop task → dev → auto-review → next. Repeats until the queue is empty.
Failed reviews get fixed immediately. 

New tasks added mid-run are picked up automatically.

### 3. Human review

```bash
# Planner session
/aha-human-review
```

Review completed tasks at your own pace. Approve, reject, or discard.

Rejected tasks are automatically rewritten and pushed back to the task queue — the running `/aha-autonext` picks them up without restart.

Shows the review queue, then walks through each task — summary, evidence, and verification instructions for UI tasks.

```
> /aha-human-review

Review queue: 2 task(s)

  [1] [pass] Drag-and-drop task reordering [UI]
  [2] [needs-input] Add WebSocket error handling

┌──────────────────── Agent: Pass ────────────────────┐
│                                                     │
│ Drag-and-drop task reordering [UI]                  │
│ Drag-and-drop reordering for task cards             │
│                                                     │
├────────────────────── Result ───────────────────────┤
│                                                     │
│ Functional PASS. Cards reorder correctly.           │
│ Code follows ARCHITECTURE.md patterns.              │
│                                                     │
├───────────────────── Evidence ──────────────────────┤
│                                                     │
│ >> .aha/data/reviews/dragdrop.png                   │
│ $ curl -s localhost:5100/api/tasks                  │
│ > 200 OK, 5 tasks returned                          │
│                                                     │
└─────────────────────────────────────────────────────┘

● UI task — check localhost:8080 to verify visually.
  Screenshots: .aha/data/reviews/dragdrop.png
```

## Foundation Documents

Created during `/aha-init`, continuously updated by the planner as the project evolves.

| Document | Location | Description |
|----------|----------|-------------|
| `PROJECT.md` | `.aha/docs/` | Problem statement, demand evidence, target user, narrowest wedge, constraints, premises, recommended approach, success criteria. |
| `ARCHITECTURE.md` | `.aha/docs/` | System design, component boundaries, data flow, tech stack, API design, database schema, test strategy, edge cases, performance considerations. |
| `DESIGN.md` | `.aha/docs/` | Aesthetic direction, typography (display/body/data/code fonts), color palette (primary/secondary/semantic/dark mode), spacing scale, layout grid, motion system, border-radius hierarchy. |
| `tokens/` | `.aha/docs/tokens/` | Design token code files (CSS/JS/JSON per tech stack) — concrete values for colors, spacing, typography, motion. |
| `UIUX.md` | `.aha/docs/` | Screen inventory, navigation structure, interaction states per feature (loading/empty/error/success), user journey, responsive strategy, accessibility. |
| `VERIFICATION.md` | `.aha/docs/` | Test/build/lint commands, browser verification tools (headless Chrome, etc.) with priority order, dev server URL. Every command copy-pasteable. |
| `FEEDBACK_HISTORY.md` | `.aha/data/` | Accumulated rejection/needs-input comments from human review. Auto-appended on reject and needs-input. |

## PPGT Hierarchy

AHA organizes work in four levels. Each level provides context and constraints for the level below.

```
Project (PROJECT.md)
  └─ Phase (phases.json)
       └─ Goal (phases.json)
            └─ Task (future/current/review/past)
```

| Level | What | Who creates |
|-------|------|-------------|
| **Project** | Name, vision, target user | Planner + Human (`/aha-init`) |
| **Phase** | Milestone with verifiable completion | Planner proposes, human approves |
| **Goal** | User-facing capability within a phase | Planner proposes, human approves |
| **Task** | Atomic work unit for a dev agent | Planner proposes, human approves (`/aha-task-write`) |

Every task links to a goal via `parent_goal`. Phase progress = completed tasks / total tasks.

Track progress with `/aha-project-progress`:

```
> /aha-project-progress

┌─ AHA Project Progress ─────────────────────────────────────┐
│                                                            │
│  [x] done  [~] in progress  [?] review  [ ] pending       │
│                                                            │
│  Phase 1. MVP Dashboard [active]                           │
│  ######--------------  29%                                 │
│                                                            │
│  ├─ Goal 1. Task board with drag-and-drop                  │
│  │  ##########----------  50%                              │
│  │  [x] Create task card component                         │
│  │  [?] Drag-and-drop task reordering                      │
│  │                                                         │
│  ├─ Goal 2. Real-time status updates                       │
│  │  #######-------------  33%                              │
│  │  [x] Set up Flask server with SocketIO                  │
│  │  [~] Add WebSocket event broadcasting                   │
│  │  [ ] Add WebSocket connection indicator                 │
│  │                                                         │
│  ├─ Goal 3. Human review interface                         │
│  │  --------------------  0%                              │
│  │  [ ] Implement review card expand/collapse              │
│  │  [ ] Add approve/reject/discard buttons                 │
│  ──────────────────────────────────────────────────────────│
│  Phase 2. Multi-project Support --------------------  0%  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Role | Model | Skills |
|-------|------|-------|--------|
| **Planner** | Plan, review with human, maintain project consistency. Create/update foundation docs, break down phases → goals → tasks, review completed tasks with human, recycle rejected tasks. | Opus | `aha-init`, `aha-init-uiux`, `aha-office-hour`, `aha-plan-ceo-review`, `aha-plan-eng-review`, `aha-plan-design-review`, `aha-task-write`, `aha-recycle`, `aha-human-review` |
| **Developer** | Execute tasks, write code. Pop from queue, work, fill result. Hooks block editing without a task and auto-trigger review/autonext on stop. | Inherited | `aha-autonext`, `aha-next`, `aha-task-write` |
| **Reviewer** | Independent quality check. Spawned as read-only subagent inside developer session. High bar — assumes human will reject 90% of "looks fine" work. Must provide evidence (curl, tests, screenshots). Pass → human review queue, fail → dev fixes immediately, 3x fail → escalate to human. | Inherited | `aha-review-functional`, `aha-review-code`, `aha-review-uiux` |

## Skills

### Planning

| Skill | Description |
|-------|-------------|
| `/aha-init` | Full project setup. Runs office-hour → CEO review → eng review → writes foundation docs → defines phases, goals, tasks. |
| `/aha-office-hour` | Product definition through structured questioning. Startup mode: 6 forcing questions (demand reality, status quo, desperate specificity, narrowest wedge, observation, future-fit). Builder mode: design thinking brainstorm. Outputs a product spec. |
| `/aha-plan-ceo-review` | Strategic review. Challenges scope, finds the 10-star product, validates premises. 4 modes: scope expansion, selective expansion, hold scope, scope reduction. |
| `/aha-plan-eng-review` | Engineering review. Locks in architecture, data flow, test strategy, edge cases, performance. Interactive — walks through issues one by one with opinionated recommendations. |
| `/aha-task-write` | Create well-structured tasks. Enforces single-function granularity, 1-2 evidence items per task, dependency ordering. Prompts must be self-contained with foundation doc references. |

### Design

| Skill | Description |
|-------|-------------|
| `/aha-init-uiux` | UI/UX foundation setup. Competitive research, proposes aesthetic/typography/color/spacing/motion as one coherent system, generates preview page, writes `DESIGN.md` + `tokens/` + `UIUX.md`. |
| `/aha-plan-design-review` | Design plan review. Rates each dimension 0-10, explains what would make it a 10, fixes the plan. Reviews `UIUX.md` against `DESIGN.md` and tokens. |
| `/aha-ui-ux-pro-max` | UI/UX design intelligence. 50+ styles, 161 color palettes, 57 font pairings, 99 UX guidelines, 25 chart types across 10 tech stacks. Searchable database with priority-based recommendations. |

### Development

| Skill | Description |
|-------|-------------|
| `/aha-next` | Pop and execute the next task from the queue. |
| `/aha-autonext` | Auto-process tasks until queue is empty. Supports filters: `--top N`, `--goal <ref>`, `--phase <ref>`. Pre-flight verifies all tools from `VERIFICATION.md` work before starting. |

### Review

| Skill | Description |
|-------|-------------|
| `/aha-review-functional` | Does it actually work? Run verification methods from `VERIFICATION.md`, test unhappy paths, check for silent errors. |
| `/aha-review-code` | Code quality — architecture compliance against `ARCHITECTURE.md`, DRY, security, error handling, complexity. |
| `/aha-review-uiux` | Design system compliance against `DESIGN.md`/tokens, UX guideline check via `aha-ui-ux-pro-max`, browser-based visual verification. UI tasks only. |
| `/aha-human-review` | Process review queue with the human. Show tasks one by one, discuss, approve/reject/discard. Rejected tasks are immediately rewritten and recycled back to the queue. |

### Utility

| Skill | Description |
|-------|-------------|
| `/aha-recycle` | Rewrite rejected tasks from past with rejection context and push back to the queue. For dashboard use — in-session rejections are handled automatically by `/aha-human-review`. |
| `/aha-project-progress` | Show project progress — phases, goals, tasks with status indicators and progress bars. |

## Task Lifecycle

```
                                    Planner creates task
                                           │
                                           ▼
                                    ┌──────────┐
                                    │  future   │  ← queue (.aha/data/future.json)
                                    └────┬─────┘
                                         │ pop
                                         ▼
                                    ┌──────────┐
                                ┌──▶│   dev    │  ← working (.aha/data/current/{session}.json)
                                │   └────┬─────┘
                                │        │ fill result + changes (auto-transition)
                                │        ▼
                                │   ┌──────────────┐
                                │   │ agent-review  │  ← reviewer subagent spawns
                                │   └──┬───┬───┬───┘
                                │      │   │   │
                                │  fail│   │   │ pass / needs-input / modified
                                │      │   │   │
                                └──────┘   │   ▼
                                      3x   │  ┌──────────────┐
                                     fail  │  │ human-review  │  ← review queue (.aha/data/review/{id}.json)
                                           │  └──┬───┬───┬───┘
                                           │     │   │   │
                                           └─────┘   │   │
                                                     │   │
                                    ┌────────────────┤   │
                                    │                │   │
                                approve          reject  discard
                                    │                │   │
                                    ▼                ▼   ▼
                                ┌──────┐         ┌──────┐
                                │ past │         │ past │  ← done (.aha/data/past/{date}.json)
                                └──────┘         └──┬───┘
                                                    │ reject only
                                                    ▼
                                              recycle → future
```

| Status | Location | Meaning |
|--------|----------|---------|
| `future` | `future.json` | Queued, waiting to be picked up |
| `dev` | `current/{session}.json` | Developer working |
| `agent-review` | `current/{session}.json` | Reviewer verifying (dev blocked) |
| `human-review` | `review/{task_id}.json` | Awaiting human decision (dev freed) |
| `past` | `past/{date}.json` | Done (approved, rejected, or discarded) |

### Key transitions

- **dev → agent-review**: Auto-triggered when `result` + `changes` are both filled via `task.py update`.
- **agent-review → dev**: Reviewer verdict `fail` — dev fixes immediately in the same session.
- **agent-review → human-review**: Reviewer verdict `pass`/`needs-input`/`modified` — task moves from `current/` to `review/`, dev is freed for next task.
- **3x fail → human-review**: Hook escalates after 3 failed review attempts.
- **human reject → recycle → future**: `/aha-human-review` rewrites the task prompt and pushes back to queue.

## Harnessing Strategy

LLMs are non-deterministic — they may ignore instructions, skip steps, or drift. AHA splits control into two layers:

**Deterministic (hooks + scripts — guaranteed)**

| What | How |
|------|-----|
| Block editing without a task | `hook-pretool-task-check.sh` — PreToolUse hook blocks Edit/Write if no `current/{session}.json` exists. `.aha/` and `.claude/` paths exempt. |
| Auto-transition dev → agent-review | `task.py update` — when both `result` and `changes` are filled, status flips automatically. |
| Trigger reviewer on stop | `hook-review.sh` — Stop hook detects `agent-review` status, blocks with "SendMessage to @aha-reviewer". |
| 3x review fail → escalate | `hook-review.sh` — tracks review attempts via marker file, calls `task.py escalate` after 3 failures. |
| Auto-next queue progression | `hook-autonext-stop.sh` — Stop hook feeds next task prompt when current task is done and `autonext-state.json` exists. |
| Max iteration guard | `hook-autonext-stop.sh` — auto-fills result after N iterations without completion, triggers reviewer. |
| Planner gap detection | `hook-planner-start.sh` — SessionStart hook scans for missing foundation docs, injects directive. |
| Rejected task detection | `hook-planner-start.sh` — counts rejected tasks in past, directs planner to run `/aha-recycle`. |
| Task context injection | `hook-task-reminder.sh` — UserPromptSubmit hook shows current task title/goal/status every turn. |
| Project init check | `hook-init-check.sh` — SessionStart hook prompts `/aha-init` if `PROJECT.md` missing. |
| File locking | `task.py` — `fcntl.flock` on all `future.json` operations to prevent concurrent access corruption. |
| Schema enforcement | `task.py` / `phase.py` — all fields exist from creation, only valid transitions allowed. |
| Feedback logging | `task.py complete` — auto-appends rejection/needs-input comments to `FEEDBACK_HISTORY.md`. |
| Reviewer is read-only | `aha-reviewer` agent — `disallowedTools: Edit, Write, Agent`. Cannot modify code. |

**Non-deterministic (agents + skills — best effort)**

| What | Defense if ignored |
|------|-------------------|
| Agent follows skill instructions | None — inherent LLM limitation. |
| Dev spawns reviewer when told | Stop hook re-triggers on every stop until review happens. |
| Reviewer runs all applicable review skills | May skip a review type — human review catches it. |
| Planner writes good task prompts | Reviewer + human review catches bad output. |
| Quality of review judgments | Human review is the final gate. |

### Defense Table

| Failure | Defense |
|---------|---------|
| Dev edits without task | `hook-pretool-task-check.sh` BLOCKS Edit/Write |
| Dev doesn't spawn reviewer | `hook-review.sh` re-triggers on every Stop |
| Dev skips review via `task.py complete` | `task.py` enforces: only `review/` → past |
| Reviewer doesn't call `task.py review` | Marker file tracks attempts, escalates after 3 |
| Reviewer passes bad work | Human review catches it |
| 3x reviewer fail | `hook-review.sh` escalates to human-review |
| Planner misses rejected tasks | `hook-planner-start.sh` detects and directs |
| Dev stops mid-autonext | `hook-autonext-stop.sh` blocks and feeds next task |
| Concurrent queue access | `fcntl.flock` on all `future.json` operations |
| Agent ignores skill steps | No defense (inherent LLM limitation) |

## File Structure

```
.aha/
├── data/
│   ├── future.json              # Task queue
│   ├── current/                 # One task per session
│   ├── review/                  # Awaiting human review
│   ├── past/                    # Completed tasks by date
│   ├── phases.json              # Phase/Goal hierarchy
│   ├── reviews/                 # Reviewer screenshots
│   ├── autonext-state.json      # Auto-next runtime state
│   └── FEEDBACK_HISTORY.md      # Rejection/needs-input log
├── docs/
│   ├── PROJECT.md
│   ├── ARCHITECTURE.md
│   ├── DESIGN.md
│   ├── UIUX.md
│   ├── VERIFICATION.md
│   └── tokens/                  # Design token code files
└── scripts/
    ├── task.py                  # Task operations (pop, add, update, review, complete, recycle, etc.)
    ├── phase.py                 # Phase/Goal operations
    ├── hook-planner-start.sh    # Planner context + gap directive
    ├── hook-review.sh           # Trigger reviewer on agent-review
    ├── hook-autonext-stop.sh    # Auto-next queue progression
    ├── hook-pretool-task-check.sh  # Block edits without task
    ├── hook-task-reminder.sh    # Show current task every turn
    ├── hook-init-check.sh       # Check PROJECT.md exists
    └── hook-notify.sh           # Dashboard status updates

.claude/
├── agents/
│   ├── aha-planner.md
│   ├── aha-developer.md
│   └── aha-reviewer.md
├── skills/
│   ├── aha-init/
│   ├── aha-init-uiux/
│   ├── aha-office-hour/
│   ├── aha-plan-ceo-review/
│   ├── aha-plan-eng-review/
│   ├── aha-plan-design-review/
│   ├── aha-task-write/
│   ├── aha-next/
│   ├── aha-autonext/
│   ├── aha-review-functional/
│   ├── aha-review-code/
│   ├── aha-review-uiux/
│   ├── aha-human-review/
│   ├── aha-recycle/
│   ├── aha-ui-ux-pro-max/
│   └── aha-project-progress/
└── settings.json                # Hook definitions
```



## License

MIT
