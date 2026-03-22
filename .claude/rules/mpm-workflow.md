# MPM Task System

This project uses the MPM task system. Tasks are tracked via files in `.mpm/data/`.

---

## File Structure

```
.mpm/data/
├── future.json             # Queued tasks (front = highest priority)
├── current/                # Tasks in progress (one per session)
│   └── {session_id}.json
├── review/                 # Tasks awaiting human review
│   └── {task_id}.json
└── past/
    └── YYMMDD.json         # Completed tasks
```

## Task Schema

All locations use the same schema. All fields exist from creation, progressively filled:

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

### Field lifecycle

| Field | When filled | By whom |
|-------|-------------|---------|
| `id`, `title`, `prompt`, `created` | Task creation | Planner (add) or Dev (create) |
| `parent_goal` | Task creation | Planner |
| `session_id` | Pop | Dev (pop) |
| `goal`, `approach`, `verification` | Dev start | Dev |
| `result`, `memo` | Dev done | Dev |
| `agent_reviews` | Agent review | Reviewer (appended) |
| `human_review` | Human review | Human (dashboard) |

## Status Flow

```
future → dev → agent-review → human-review → past
```

| Status | Location | Meaning |
|--------|----------|---------|
| `future` | future.json | Queued, waiting |
| `dev` | current/ | Developer working |
| `agent-review` | current/ | Reviewer verifying |
| `human-review` | review/ | Waiting for human approval (dev is freed) |
| `past` | past/ | Done |

### Status transitions

| From | To | Trigger | File move |
|------|------|---------|-----------|
| `future` | `dev` | `task.py pop` | future.json → current/ |
| `dev` | `agent-review` | `task.py update result` (auto) | stays in current/ |
| `agent-review` | `human-review` | `task.py review pass/needs-input/modified` | current/ → review/ |
| `agent-review` | `dev` | `task.py review fail` | stays in current/ |
| `agent-review` | `human-review` | `task.py escalate` (3x fail) | current/ → review/ |
| `human-review` | `past` | `task.py complete` (human only) | review/ → past/ |

### Review results

**agent_reviews** — array, appended each review cycle:
```json
{"verdict": "pass|fail|needs-input|modified", "summary": "...", "evidence": "...", "at": "..."}
```

**human_review** — object, filled once at final judgment:
```json
{"verdict": "success|rejected|postpone|discard", "comment": "...", "at": "..."}
```

## Session ID

Get the current session ID from the hook log:
```bash
grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//'
```

## Workflow

### 1. Start a task

**From queue:** Pop from the front (index 0) of `future.json`.

**From conversation:** If there is no current task and the user requests work that involves code changes, **do NOT create a task yourself**. Instead, spawn the `@planner` subagent to analyze the request and create properly scoped tasks.

The Planner will:
- Break down large requests into small, independently verifiable tasks
- Add them to future.json in priority order
- You then `pop` the first one and start working

**How to judge "work that involves code changes":**
- YES → spawn @planner: "Change the border color", "Add this feature", "Fix this bug"
- YES → spawn @planner: User starts with a question but then says "OK do it" — before first edit
- NO → no task needed: "How does this work?", "What's the next task?", "Why is this error happening?"

After planner finishes, pop the first task:
```bash
python3 .mpm/scripts/task.py pop ${CLAUDE_SESSION_ID}
```

Then fill `goal`, `approach`, `verification` via `task.py update`.

**goal = WHAT** must be true (verifiable acceptance criteria, as a checklist).
**verification = HOW** you will check each goal item.

Available verification methods (prefer self-verification when possible):
- **curl + parse**: `curl -s URL | grep/jq ...` — for API responses, served HTML content
- **Run tests**: `pytest`, `npm test`, etc.
- **Script execution**: run the modified code and check output
- **File inspection**: verify generated/modified files contain expected content
- **Headless Chrome screenshot**: `google-chrome --headless --screenshot=...` — for quick static visual checks
- **Browser automation** (e.g. Claude in Chrome): interact with live pages if available
- **Ask user**: ONLY when the above methods genuinely cannot verify (e.g., subjective design quality)

### 2. Do the work

Work normally. No need to update the task file mid-work.

### 3. Fill result

When done, fill `result` and `memo` via `task.py update`:
```bash
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} result "..."
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} memo "..."
```

**Filling `result` automatically transitions status: `dev` → `agent-review`.**

`memo` captures ALL work done during the session — not just the original goal.

### 4. Agent review

The Stop hook detects `agent-review` status and instructs you to spawn the `@reviewer` subagent.

The reviewer is an independent agent with fresh context — it reads the task, project documents, and verifies your work from scratch.

- **pass** → task moves to `review/` (human-review), dev is freed
- **fail** → status back to `dev` (fix issues, update result to re-trigger)
- **needs-input** → task moves to `review/` with question for human
- **modified** → task moves to `review/` with explanation

After 3 failed reviews, the task is escalated to `review/` via `task.py escalate`.

### 5. Human review

Tasks in `review/` are displayed on the dashboard with the reviewer's summary and evidence. The human reviews asynchronously — dev does not wait. The human can:

- **Approve** → `task.py complete <task_id> success` → past
- **Reject** + comment → `task.py complete <task_id> rejected` → past

Rejected tasks are picked up by the Planner agent, which creates a new corrective task in future.

### 6. Postpone/discard

Only from `review/` (human-review status), the human can:
- **Postpone** → `task.py complete <task_id> postpone` → past + new card in future
- **Discard** → `task.py complete <task_id> discard` → past

## Rules

- **All task JSON operations must go through `task.py`** — never read/write `.mpm/data/` JSON files directly.
- **Dev never calls `task.py complete`** — only humans (via dashboard) move tasks to past.
- Always pop from the **front** (index 0) of future.json.
- Append new tasks to the **back** of future.json.
- Only one task per session in current.
- Always respond to the user in their language.
