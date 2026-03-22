---
name: mpm-autonext
description: Automatically work through selected future tasks — work, self-verify, and move to next after review.
disable-model-invocation: true
allowed-tools: Bash(python3 *), Bash(google-chrome *), Bash(curl *)
---

# MPM Auto-Next

Automatically process tasks from the future queue. Each task: pop → work → self-verify → fill result → agent review → next.
Human review happens asynchronously — dev does not wait for it.

## Arguments

- **(no args)**: Process all future tasks until future.json is empty.
- `--top N`: Process only the top N tasks (highest priority = front of queue).

## Setup

```bash
SID=$(grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//')

MODE=${1:---all}

cat > .mpm/data/autonext-state.json << STATEEOF
{
  "session_id": "$SID",
  "max_iterations": 3,
  "task_iteration": 0,
  "tasks_completed": 0,
  "mode": "$MODE",
  "started_at": "$(date -Iseconds)"
}
STATEEOF
echo "🚀 MPM Auto-Next activated"
```

## Workflow

1. Pop the next task:
   ```bash
   python3 .mpm/scripts/task.py pop ${CLAUDE_SESSION_ID}
   ```

2. Read the task and fill `goal`, `approach`, `verification`.
   - **goal**: verifiable acceptance criteria (checklist)
   - **verification**: HOW to check — prefer self-verification:
     - `/chrome` — interact with live pages (click, type, scroll, read console). Best for UI verification
     - `google-chrome --headless --screenshot=...` — quick static visual checks
     - `curl -s URL | grep/jq ...` — API responses, HTML content
     - Run tests, check files, execute scripts
     - Ask user ONLY when genuinely impossible

3. Do the work.

4. Self-verify using the method you specified.
   - If verification **passes**: fill `result` and `memo` via `task.py update`. This auto-transitions to `agent-review`.
   - If verification **fails**: fix and retry. The Stop hook will track iterations.

5. The Stop hook triggers the reviewer agent. The reviewer independently verifies your work.
   - **pass** → task moves to `review/` for human-review. Dev is freed.
   - **fail** → task returns to `dev`, fix issues and update result again.

6. After reviewer passes, current/ is empty. The Stop hook pops the next task from future.

7. Human reviews completed tasks in `review/` asynchronously — dev does not wait.

## Rules

- **NEVER manually delete `autonext-state.json`** — the Stop hook manages the lifecycle.
- **NEVER call `task.py complete`** — only humans move tasks to past.
- After filling result, just end your response normally. The Stop hook handles review and queue progression.
- Only the user should cancel autonext (by deleting the state file or saying "stop").

## Cancellation

The **user** can stop the auto-next loop at any time by deleting the state file:
```bash
rm .mpm/data/autonext-state.json
```

Always respond in the user's language.
