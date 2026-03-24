#!/bin/bash
# MPM Stop Hook — Trigger Reviewer Agent
# When a task is in agent-review status, instructs dev to spawn @mpm-reviewer subagent.
# Tracks spawn attempts via .reviewed marker to prevent infinite loop when reviewer
# exits without running task.py review.

set -euo pipefail

HOOK_INPUT=$(cat)
HOOK_SESSION=$(echo "$HOOK_INPUT" | jq -r '.session_id // ""')

SID="$HOOK_SESSION"
CURRENT_FILE=".mpm/data/current/${SID}.json"

# No current task → pass through
if [[ ! -f "$CURRENT_FILE" ]]; then
  exit 0
fi

CURRENT_STATUS=$(jq -r '.status // ""' "$CURRENT_FILE")

# Only act on agent-review status
if [[ "$CURRENT_STATUS" != "agent-review" ]]; then
  exit 0
fi

# Check last review verdict — if already passed, skip
LAST_VERDICT=$(jq -r '(.agent_reviews // [])[-1].verdict // ""' "$CURRENT_FILE")
if [[ "$LAST_VERDICT" == "pass" ]] || [[ "$LAST_VERDICT" == "needs-input" ]] || [[ "$LAST_VERDICT" == "modified" ]]; then
  exit 0
fi

# Track total attempts: actual reviews + spawn attempts without review
REVIEW_COUNT=$(jq '(.agent_reviews // []) | length' "$CURRENT_FILE")
MARKER_FILE=".mpm/data/current/${SID}.reviewed"
SPAWN_COUNT=0
if [[ -f "$MARKER_FILE" ]]; then
  SPAWN_COUNT=$(cat "$MARKER_FILE")
fi

MAX_REVIEWS=3
TOTAL_ATTEMPTS=$((REVIEW_COUNT > SPAWN_COUNT ? REVIEW_COUNT : SPAWN_COUNT))

if [[ "$TOTAL_ATTEMPTS" -ge "$MAX_REVIEWS" ]]; then
  # Max attempts — escalate to human-review via task.py
  python3 .mpm/scripts/task.py escalate "$SID" 2>/dev/null || true
  rm -f "$MARKER_FILE"
  jq -n '{decision:"block", reason:"Agent review failed/timed out 3 times. Task escalated to human-review for manual judgment.", systemMessage:"⚠️ Review failed 3x — escalated to human"}'
  exit 0
fi

# Increment spawn counter
echo $((SPAWN_COUNT + 1)) > "$MARKER_FILE"

TITLE=$(jq -r '.title // "?"' "$CURRENT_FILE")

PROMPT="## 🔍 Agent Review Required: ${TITLE}

Your task result is ready. Now spawn the reviewer agent to independently verify your work.

Run: Use the Agent tool to spawn the 'reviewer' subagent. It will read the task, project documents, and verify independently.

If the reviewer returns **fail**: fix the issues it identified, update the result, then the reviewer will be triggered again on next stop.
If the reviewer returns **pass/needs-input/modified**: the task moves to review/ for human-review.

Review attempt: $((TOTAL_ATTEMPTS + 1))/${MAX_REVIEWS}"

jq -n --arg p "$PROMPT" \
  '{decision:"block", reason:$p, systemMessage:"🔍 Spawn @mpm-reviewer to verify your work"}'
exit 0
