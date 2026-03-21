#!/bin/bash
# MPM Stop Hook — Trigger Reviewer Agent
# When a task has a result but hasn't been reviewed, instructs dev to spawn @reviewer subagent.

set -euo pipefail

HOOK_INPUT=$(cat)
HOOK_SESSION=$(echo "$HOOK_INPUT" | jq -r '.session_id // ""')

SID="$HOOK_SESSION"
CURRENT_FILE=".mpm/data/current/${SID}.json"

# No current task → pass through
if [[ ! -f "$CURRENT_FILE" ]]; then
  exit 0
fi

CURRENT_RESULT=$(jq -r '.result // ""' "$CURRENT_FILE")
CURRENT_STATUS=$(jq -r '.status // ""' "$CURRENT_FILE")

# No result yet (task still in progress) → pass through
if [[ -z "$CURRENT_RESULT" ]]; then
  exit 0
fi

# Already in human-review → check reviews were actually recorded
if [[ "$CURRENT_STATUS" == "human-review" ]]; then
  REVIEW_COUNT=$(jq '(.reviews // []) | length' "$CURRENT_FILE")
  if [[ "$REVIEW_COUNT" -eq 0 ]]; then
    # Status is human-review but no reviews recorded — reset and re-trigger
    python3 -c "
import json; p='$CURRENT_FILE'
t=json.load(open(p)); t['status']='active'
json.dump(t,open(p,'w'),ensure_ascii=False,indent=2)
" 2>/dev/null
    # Fall through to trigger reviewer again
  else
    exit 0
  fi
fi

# Check if last review was a pass (already reviewed successfully)
LAST_REVIEW_STATUS=$(jq -r '(.reviews // [])[-1].status // ""' "$CURRENT_FILE")
if [[ "$LAST_REVIEW_STATUS" == "pass" ]] || [[ "$LAST_REVIEW_STATUS" == "needs-input" ]] || [[ "$LAST_REVIEW_STATUS" == "modified" ]]; then
  exit 0
fi

# Check review iteration count
REVIEW_COUNT=$(jq '(.reviews // []) | map(select(.by == "agent")) | length' "$CURRENT_FILE")
MAX_REVIEWS=3

if [[ "$REVIEW_COUNT" -ge "$MAX_REVIEWS" ]]; then
  # Max review iterations reached — move to needs-revision
  python3 .mpm/scripts/task.py complete "$SID" needs-revision --memo "Failed agent review $MAX_REVIEWS times" 2>/dev/null || true
  jq -n '{decision:"block", reason:"Agent review failed 3 times. Task moved to needs-revision in past. Moving on.", systemMessage:"❌ Review failed — needs-revision"}'
  exit 0
fi

TITLE=$(jq -r '.title // "?"' "$CURRENT_FILE")

PROMPT="## 🔍 Agent Review Required: ${TITLE}

Your task result is ready. Now spawn the reviewer agent to independently verify your work.

Run: Use the Agent tool to spawn the 'reviewer' subagent. It will read the task, project documents, and verify independently.

If the reviewer returns **fail**: fix the issues it identified, update the result, then the reviewer will be triggered again on next stop.
If the reviewer returns **pass/needs-input/modified**: the task moves to human-review.

Review iteration: $((REVIEW_COUNT + 1))/${MAX_REVIEWS}"

jq -n --arg p "$PROMPT" \
  '{decision:"block", reason:$p, systemMessage:"🔍 Spawn @reviewer to verify your work"}'
exit 0
