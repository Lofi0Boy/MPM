# MPM Task System

This project uses the MPM task system. Tasks are tracked via files in `.mpm/data/`.

---

## File Structure

```
.mpm/data/
├── future.json             # Queued tasks (front = highest priority)
├── current/                # Active tasks (one per session)
│   └── {session_id}.json
└── past/
    └── YYMMDD.json         # Completed/postponed/discarded tasks
```

## Task Schema

All locations use the same schema. Fields are filled progressively:

```json
{
  "id": "unique_id",
  "title": "One-line summary",
  "prompt": "Detailed task instruction",
  "goal": "Verifiable acceptance criteria — WHAT must be true (fill on current entry)",
  "approach": "How to accomplish (fill on current entry)",
  "verification": "HOW will you check the goal is met (fill on current entry)",
  "result": "Actual outcome (fill on completion)",
  "memo": "Notes (fill on completion)",
  "status": "queued | active | success | postpone | modified | discard",
  "created": "YYMMDDHHmm",
  "session_id": "Claude Code session ID (fill on current entry)",
  "parent_id": "Original task ID (when re-created from postpone/modified)"
}
```

## Session ID

Get the current session ID from the hook log:
```bash
grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//'
```

## Workflow

### 1. Start a task

**From queue:** Pop from the front (index 0) of `future.json` and save to `current/{session_id}.json`.

**From conversation:** If there is no current task and the user requests work that involves code changes, immediately create a current task. Do this BEFORE starting the actual work.

```bash
# Get session ID, then create
SID=$(grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//')
python3 .mpm/scripts/task.py create "$SID" "title" "prompt"
python3 .mpm/scripts/task.py update "$SID" goal "..."
python3 .mpm/scripts/task.py update "$SID" approach "..."
python3 .mpm/scripts/task.py update "$SID" verification "..."
```

**How to judge "work that involves code changes":**
- YES → create task: "Change the border color", "Add this feature", "Fix this bug"
- YES → create task: User starts with a question but then says "OK do it" — create task before first edit
- NO → no task: "How does this work?", "What's the next task?", "Why is this error happening?"

Fill `goal`, `approach`, `verification`, set `status` to `active`, set `session_id`.

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

Example — title: "Dashboard live refresh"
- goal: "JSON changes in future/current/past reflected on dashboard within 2s without manual refresh"
- verification: "Edit a task JSON via task.py, then curl /api/projects and confirm the change appears in response"

Bad verification: "Ask user to check the UI" (when you could take a screenshot or curl the API)
Good verification: "Take headless Chrome screenshot and visually confirm layout. curl /api/projects to verify data."

### 2. Do the work

Work normally. No need to update the task file mid-work.

### 3. Complete the work

When done, fill the `result` field with the actual outcome including verification results.

Also fill `memo` with a brief summary of ALL work done during the session — the task may have started as "Fix border color" but the conversation may have led to additional changes. The memo captures what actually happened, not just the original goal.

### 4. Agent review

The Stop hook will detect that `result` is filled and instruct you to spawn the `@reviewer` subagent.

The reviewer is an independent agent with fresh context — it reads the task, project documents, and verifies your work from scratch.

- **pass** → task moves to `human-review` status
- **fail** → reviewer returns issues → fix them in the same session → reviewer is triggered again on next stop (max 3 attempts)
- **needs-input** → task moves to `human-review` with a question for the user
- **modified** → task moves to `human-review` with explanation of what changed

After 3 failed reviews, the task is moved to past as `needs-revision`.

### 5. Human review

Tasks in `human-review` status are displayed on the dashboard with the reviewer's summary and evidence (screenshots, logs). The human can:

- **Approve** → task moves to past as `success`
- **Reject** + comment → task moves to past as `rejected`

Rejected tasks are picked up by the Planner agent, which creates a new corrective task in future.

### 6. Postpone/discard

At any point, the user can:
- "Later" / defer → `postpone` → move to past + create new card in future
- "Cancel" / "drop" → `discard` → move to past

## Rules

- **All task JSON operations must go through `task.py`** — never read/write `.mpm/data/` JSON files directly. Available commands: `pop`, `create`, `complete`, `add`, `update`, `status`.
- Always pop from the **front** (index 0) of future.json.
- Append new tasks to the **back** of future.json.
- Move to past **immediately** when a result is confirmed — not on a date boundary.
- Only one task per session in current.
- Always respond to the user in their language.
