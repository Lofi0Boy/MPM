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
- `--goal <ref>`: Process only tasks belonging to the specified goal. Accepts goal ID, index in active phase (e.g. `2`), or `phase.goal` index (e.g. `1.2`).
- `--phase <ref>`: Process only tasks within the specified phase. Accepts phase ID or index (e.g. `1`).

## Setup

```bash
SID=$(grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//')

# Parse arguments: --top N, --goal <id>, --phase <id>
MODE="--all"
GOAL_FILTER=""
PHASE_FILTER=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --top) MODE="--top $2"; shift 2 ;;
    --goal) GOAL_FILTER="$2"; shift 2 ;;
    --phase) PHASE_FILTER="$2"; shift 2 ;;
    *) shift ;;
  esac
done

cat > .mpm/data/autonext-state.json << STATEEOF
{
  "session_id": "$SID",
  "max_iterations": 3,
  "task_iteration": 0,
  "tasks_completed": 0,
  "mode": "$MODE",
  "goal_filter": "$GOAL_FILTER",
  "phase_filter": "$PHASE_FILTER",
  "started_at": "$(date -Iseconds)"
}
STATEEOF
echo "MPM Auto-Next activated"
```

## Pre-flight: Verify tools work

Before processing any tasks, confirm that all verification tools from the injected VERIFICATION.md actually work.

1. For each tool listed, run a quick smoke test:
   - **Test/Build**: run the command and confirm it exits successfully (e.g., `npm test`, `pytest --co -q`)
   - **Browser tools**: run the exact commands from VERIFICATION.md's Browser Verification section to confirm the tool works and can reach the dev server
   - **Dev server**: confirm it's running or start it, verify the URL responds
   - **Linters/type checkers**: run and confirm they exit without error
3. Report results to the user:
   - **All pass** → proceed to workflow
   - **Any fail** → tell the user which tool failed and how, ask how to fix or whether to proceed without it. **Do not start tasks until the user confirms.**

## Workflow

1. Pop the next task (pass filter from autonext-state.json if set):
   ```bash
   # Read filters from state
   GOAL=$(python3 -c "import json; s=json.load(open('.mpm/data/autonext-state.json')); print(s.get('goal_filter',''))" 2>/dev/null)
   PHASE=$(python3 -c "import json; s=json.load(open('.mpm/data/autonext-state.json')); print(s.get('phase_filter',''))" 2>/dev/null)
   POP_ARGS=""
   [ -n "$GOAL" ] && POP_ARGS="--goal $GOAL"
   [ -n "$PHASE" ] && POP_ARGS="--phase $PHASE"
   python3 .mpm/scripts/task.py pop ${CLAUDE_SESSION_ID} $POP_ARGS
   ```

2. Read the task. `goal` and `verification` are already set by planner. Fill `approach`.
   - If `verification` is empty or missing: refer to the injected VERIFICATION.md and choose the appropriate verification methods for this task. Fill `verification` via `task.py update` before starting work.

3. Do the work.

4. Self-verify using the method you specified.
   - If verification **passes**: fill `result`, `changes`, and `memo` via `task.py update`. This auto-transitions to `agent-review`.
   - If verification **fails**: fix and retry. The Stop hook will track iterations.

5. After filling result, the hooks handle review and next task progression automatically.

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
