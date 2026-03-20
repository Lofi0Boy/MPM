#!/bin/bash
# MPM Stop Hook — Reviewer
# When a task has a result but hasn't been reviewed, injects a review prompt.
# Uses a flag file to track review status.

set -euo pipefail

HOOK_INPUT=$(cat)
HOOK_SESSION=$(echo "$HOOK_INPUT" | jq -r '.session_id // ""')

SID="$HOOK_SESSION"
CURRENT_FILE=".mpm/data/current/${SID}.json"
REVIEWED_FLAG=".mpm/data/current/${SID}.reviewed"

# No current task → pass through
if [[ ! -f "$CURRENT_FILE" ]]; then
  exit 0
fi

CURRENT_RESULT=$(jq -r '.result // ""' "$CURRENT_FILE")

# No result yet (task still in progress) → pass through
if [[ -z "$CURRENT_RESULT" ]]; then
  exit 0
fi

# Already reviewed → pass through
if [[ -f "$REVIEWED_FLAG" ]]; then
  exit 0
fi

# --- Inject review prompt ---
GOAL=$(jq -r '.goal // "N/A"' "$CURRENT_FILE")
VERIFICATION=$(jq -r '.verification // "N/A"' "$CURRENT_FILE")
RESULT=$(jq -r '.result // "N/A"' "$CURRENT_FILE")
TITLE=$(jq -r '.title // "?"' "$CURRENT_FILE")

# Get git diff summary
GIT_DIFF=$(git diff --stat HEAD 2>/dev/null || echo "(no git changes)")

# Mark as reviewed (so next Stop won't re-trigger)
touch "$REVIEWED_FLAG"

PROMPT="## 🔍 REVIEW: ${TITLE}

You are now in REVIEWER mode. Do NOT modify any code. Only verify and judge.

### Goal
${GOAL}

### Verification Method
${VERIFICATION}

### Developer's Result
${RESULT}

### Changed Files
${GIT_DIFF}

### Your Review Tasks
1. **Goal check**: Compare each goal item against the result. Is every item satisfied?
2. **Verification re-run**: Execute the verification methods listed above (curl, file check, etc.) and report actual results.
3. **Scope check**: Are there unintended changes in the diff? Files that shouldn't have been modified?

### After Review
- If ALL checks pass: Confirm the task is complete. Say '✅ Review passed' and end.
- If ANY check fails: List what failed and why. Suggest whether to fix now or create a follow-up task.

Do NOT modify code. Only read, verify, and report."

jq -n --arg p "$PROMPT" \
  '{decision:"block", reason:$p, systemMessage:"🔍 Reviewer: task verification in progress"}'
exit 0
