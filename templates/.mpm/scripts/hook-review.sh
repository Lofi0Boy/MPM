#!/bin/bash
# MPM Stop Hook — Trigger Reviewer Agent
# When a task is in agent-review status, instructs dev to send review request
# to @mpm-reviewer via SendMessage.
# Tracks attempts via .reviewed marker to prevent infinite loop.

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

# Track total attempts: actual reviews + send attempts without review
REVIEW_COUNT=$(jq '(.agent_reviews // []) | length' "$CURRENT_FILE")
MARKER_FILE=".mpm/data/current/${SID}.reviewed"
SEND_COUNT=0
if [[ -f "$MARKER_FILE" ]]; then
  SEND_COUNT=$(cat "$MARKER_FILE")
fi

MAX_REVIEWS=3
TOTAL_ATTEMPTS=$((REVIEW_COUNT > SEND_COUNT ? REVIEW_COUNT : SEND_COUNT))

if [[ "$TOTAL_ATTEMPTS" -ge "$MAX_REVIEWS" ]]; then
  python3 .mpm/scripts/task.py escalate "$SID" 2>/dev/null || true
  rm -f "$MARKER_FILE"
  jq -n '{decision:"block", reason:"Agent review failed/timed out 3 times. Task escalated to human-review.", systemMessage:"⚠️ Review failed 3x — escalated to human"}'
  exit 0
fi

# Increment send counter
echo $((SEND_COUNT + 1)) > "$MARKER_FILE"

TITLE=$(jq -r '.title // "?"' "$CURRENT_FILE")
TASK_CONTENT=$(cat "$CURRENT_FILE")

PROMPT="## Agent Review Required: ${TITLE}

Send review request to @mpm-reviewer via **SendMessage**.

Include this context in your message:
---
${TASK_CONTENT}
---

Review attempt: $((TOTAL_ATTEMPTS + 1))/${MAX_REVIEWS}"

jq -n --arg p "$PROMPT" \
  '{decision:"block", reason:$p, systemMessage:"🔍 SendMessage to @mpm-reviewer"}'

exit 0
