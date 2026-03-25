# MPM Workflow

## 1. Project Lifecycle

```mermaid
flowchart TD
    subgraph init["/init"]
        OH["/office-hour"] -->|product spec| CEO["/plan-ceo-review"]
        CEO -->|strategic plan| ENG["/plan-eng-review"]
        ENG -->|architecture| UIUX{UI project?}
        UIUX -->|yes| INITUIUX["/init-uiux"]
        INITUIUX --> DR["/plan-design-review"]
        UIUX -->|no| FDOCS
        DR --> FDOCS[Foundation Docs]
    end

    FDOCS -->|"PROJECT, ARCHITECTURE, DESIGN, UIUX, VERIFICATION.md"| PHASE[Phase / Goal]
    PHASE --> TW["/task-write"]

    subgraph task["Task Lifecycle"]
        direction TD
        POP["/next · /autonext · /recycle"] -->|pop| DEV["developer"]
        DEV -->|"result + memo"| REV

        subgraph REV["reviewer _(auto-invoked by hook)_"]
            RF["/review-functional"]
            RC["/review-code"]
            RU["/review-uiux"]
        end

        REV -->|fail| DEV
        REV -->|pass| HR["/human-review"]
        HR -->|approve| DONE["Done (past)"]
        HR -->|reject| RECYCLE["/recycle"]
    end

    TW -->|Task| POP
    RECYCLE -->|"rewrite Task"| TW
    DONE -->|"next phase"| OH

    style init fill:#f0f0f0,stroke:#999,stroke-dasharray:5 5
    style task fill:#f0f0f0,stroke:#999,stroke-dasharray:5 5
    style REV fill:#e8e8e8,stroke:#888
```

## 2. Agents

| Agent | Role | Execution |
|-------|------|-----------|
| **Planner** | Foundation docs, phase/goal management, task creation | `claude --agent mpm-planner` |
| **Developer** | Task execution: pop, implement, fill result | `claude --agent mpm-developer` |
| **Reviewer** | Independent verification (functional, code, uiux) | Auto-invoked by hook via SendMessage — no manual invocation needed |
| **Human** | Final judgment: approve / reject / discard | Via dashboard or `/human-review` |

**Parallel execution recommended.** Run planner and developer as separate `--agent` sessions to maintain clear context separation — mixing planning and development in one session leads to context pollution for both humans and AI.

## 3. Skills Reference

| Skill | Agent | Description |
|-------|-------|-------------|
| `/init` | Planner | Full project initialization (runs sub-skills below) |
| `/office-hour` | Planner | Product definition — forcing questions, product spec |
| `/plan-ceo-review` | Planner | Strategic review — scope, vision, premises |
| `/plan-eng-review` | Planner | Engineering review — architecture, tests, edge cases |
| `/plan-design-review` | Planner | Design plan review — rates and fixes UIUX.md |
| `/init-uiux` | Planner | UI/UX foundation — DESIGN.md, tokens, UIUX.md |
| `/task-write` | Planner, Developer | Create well-structured tasks |
| `/recycle` | Planner | Rewrite rejected tasks and return to queue |
| `/next` | Developer | Pop and start the next task |
| `/autonext` | Developer | Continuously process tasks from queue |
| `/review-functional` | Reviewer | Run verification, test unhappy paths |
| `/review-code` | Reviewer | Architecture compliance, DRY, security |
| `/review-uiux` | Reviewer | Design system + UX standards + visual verification |
| `/human-review` | Human | Final approval, rejection, or discard |

## 4. `.mpm/` Structure

```
.mpm/
├── mpm-workflow.md              # This file
├── docs/                        # Foundation documents
│   ├── PROJECT.md               # Product vision, target users, success criteria
│   ├── ARCHITECTURE.md          # System design, patterns, conventions
│   ├── DESIGN.md                # Visual design system
│   ├── UIUX.md                  # UI structure, screen flows, interaction states
│   ├── VERIFICATION.md          # Verification tools and commands
│   └── tokens/                  # Design tokens (colors, typography, spacing)
├── data/
│   ├── future.json              # Queued tasks
│   ├── current/                 # Tasks in progress (one per session)
│   ├── review/                  # Tasks awaiting human review
│   ├── past/                    # Completed tasks (YYMMDD.json)
│   └── FEEDBACK_HISTORY.md      # Rejected/needs-input review comments
├── gstack/                      # Product specs, sketches, CEO/eng plans
│   ├── design-*.md
│   ├── sketches/
│   └── ceo-plans/
└── scripts/
    ├── task.py                  # Task CRUD and lifecycle management
    ├── phase.py                 # Phase and goal management
    ├── inject-project-status.sh # Shared context injection (SessionStart hook)
    └── hook-*.sh                # Lifecycle hooks
```

## 5. Rules

- **All task operations go through `task.py`** — never read/write `.mpm/data/` JSON directly.
- **All task creation uses `/task-write`** — never write task fields manually.
- **Developer never calls `task.py complete`** — only humans move tasks to past.
- Use `${CLAUDE_SESSION_ID}` for session identification — do NOT parse log files.
- Append new tasks to the **back** of future.json.
- One task per session in current.
- Always respond in the user's language.
