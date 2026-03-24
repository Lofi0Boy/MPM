#!/bin/bash
# MPM Auto-Next Stop Hook
# When autonext is active, blocks session exit and feeds next task prompt.
# Respects the review pipeline — never bypasses agent-review or human-review.
# After agent-review pass, task moves to review/ and current/ is freed — autonext pops next.

set -euo pipefail

HOOK_INPUT=$(cat)
STATE_FILE=".mpm/data/autonext-state.json"

# No active autonext → allow exit
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Session isolation
STATE_SESSION=$(jq -r '.session_id // ""' "$STATE_FILE")
HOOK_SESSION=$(echo "$HOOK_INPUT" | jq -r '.session_id // ""')
if [[ -n "$STATE_SESSION" ]] && [[ "$STATE_SESSION" != "$HOOK_SESSION" ]]; then
  exit 0
fi

MAX_ITER=$(jq -r '.max_iterations // 3' "$STATE_FILE")
TASK_ITER=$(jq -r '.task_iteration // 0' "$STATE_FILE")
TASKS_DONE=$(jq -r '.tasks_completed // 0' "$STATE_FILE")

SID="$HOOK_SESSION"
CURRENT_FILE=".mpm/data/current/${SID}.json"
HAS_CURRENT="false"
CURRENT_STATUS=""
if [[ -f "$CURRENT_FILE" ]]; then
  HAS_CURRENT="true"
  CURRENT_STATUS=$(jq -r '.status // ""' "$CURRENT_FILE")
fi

# --- Task is in agent-review → let hook-review.sh handle it ---
if [[ "$CURRENT_STATUS" == "agent-review" ]]; then
  exit 0
fi

# --- Task in dev, no result yet → iteration tracking ---
if [[ "$HAS_CURRENT" == "true" ]] && [[ "$CURRENT_STATUS" == "dev" ]]; then
  CURRENT_RESULT=$(jq -r '.result // ""' "$CURRENT_FILE")

  if [[ -z "$CURRENT_RESULT" ]]; then
    NEW_TASK_ITER=$((TASK_ITER + 1))

    if [[ $NEW_TASK_ITER -ge $MAX_ITER ]]; then
      # Max iterations — fill result and let review pipeline handle it
      python3 .mpm/scripts/task.py update "$SID" result "(auto-failed: max $MAX_ITER iterations reached)" 2>/dev/null || true
      python3 .mpm/scripts/task.py update "$SID" memo "Max $MAX_ITER iterations reached without completing verification." 2>/dev/null || true
      # status is now agent-review (auto-transitioned by update result)
      # hook-review.sh will trigger reviewer on next stop

      TMPF="${STATE_FILE}.tmp.$$"
      jq --argjson ti 0 '.task_iteration = $ti' "$STATE_FILE" > "$TMPF"
      mv "$TMPF" "$STATE_FILE"

      jq -n '{decision:"block", reason:"Max iterations reached. Result filled, reviewer will be triggered.", systemMessage:"🔄 Auto-Next | Max iterations → reviewer"}'
      exit 0
    fi

    # Not at max — continue working
    TMPF="${STATE_FILE}.tmp.$$"
    jq --argjson ti "$NEW_TASK_ITER" '.task_iteration = $ti' "$STATE_FILE" > "$TMPF"
    mv "$TMPF" "$STATE_FILE"

    PROMPT="Continue working on the current task. Iteration $NEW_TASK_ITER/$MAX_ITER.
Self-verify your work using the verification method specified in the task.
If verification passes: fill result and memo via task.py update.
If verification fails: fix the issues and try again."

    jq -n --arg p "$PROMPT" --argjson ti "$NEW_TASK_ITER" --argjson mi "$MAX_ITER" \
      '{decision:"block", reason:$p, systemMessage:("🔄 Auto-Next | Task iteration " + ($ti|tostring) + "/" + ($mi|tostring))}'
    exit 0
  fi

  # Dev has result but status is still dev — shouldn't happen (update auto-transitions)
  exit 0
fi

# --- No current task → agent-review passed, task moved to review/, ready for next ---
if [[ "$HAS_CURRENT" == "false" ]]; then
  TASKS_DONE=$((TASKS_DONE + 1))

  TMPF="${STATE_FILE}.tmp.$$"
  jq --argjson ti 0 --argjson td "$TASKS_DONE" \
    '.task_iteration = $ti | .tasks_completed = $td' "$STATE_FILE" > "$TMPF"
  mv "$TMPF" "$STATE_FILE"

  # Check if future has tasks
  FUTURE_LEN=$(python3 -c "
import json
tasks = json.load(open('.mpm/data/future.json'))
print(len(tasks))
" 2>/dev/null || echo "0")

  if [[ "$FUTURE_LEN" -eq 0 ]]; then
    MODE=$(jq -r '.mode // "--all"' "$STATE_FILE")
    if [[ "$MODE" != "--all" ]] && [[ "$MODE" != "" ]]; then
      echo "✅ MPM Auto-Next complete ($TASKS_DONE tasks processed). No more tasks."
      rm "$STATE_FILE"
      rm -f ".mpm/data/current/${SID}.reviewer-id"
      rm -f ".mpm/data/current/${SID}.reviewed"
      exit 0
    fi
    # Default mode — future is empty, done
    echo "✅ MPM Auto-Next complete ($TASKS_DONE tasks processed). No more tasks."
    rm "$STATE_FILE"
    rm -f ".mpm/data/current/${SID}.reviewer-id"
    rm -f ".mpm/data/current/${SID}.reviewed"
    exit 0
  fi

  # Clean up review markers from previous task (keep reviewer-id for reuse across tasks)
  rm -f ".mpm/data/current/${SID}.reviewed"

  # Feed next task
  PROMPT="Pop the next task: python3 .mpm/scripts/task.py pop $SID
The task already has goal and verification set by the planner. Read them carefully.
Fill approach, do the work, self-verify using the task's verification methods, then fill result+memo.
Use available verification methods (headless Chrome screenshots, curl, tests, file inspection).
Only ask the user when self-verification is genuinely impossible.
Max $MAX_ITER iterations per task."

  jq -n --arg p "$PROMPT" --argjson td "$TASKS_DONE" --argjson fl "$FUTURE_LEN" \
    '{decision:"block", reason:$p, systemMessage:("🔄 Auto-Next | Done: " + ($td|tostring) + " | Future: " + ($fl|tostring))}'
  exit 0
fi

exit 0
