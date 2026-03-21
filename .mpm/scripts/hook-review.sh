#!/bin/bash
# MPM Stop Hook — Reviewer
# When a task has a result but hasn't been reviewed, injects a 3-stage review prompt.
# Stages: 1) Functionality  2) UI/UX  3) Code Review
# References: PROJECT.md, DESIGN.md, VERIFICATION.md

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

# --- Gather context ---
GOAL=$(jq -r '.goal // "N/A"' "$CURRENT_FILE")
VERIFICATION=$(jq -r '.verification // "N/A"' "$CURRENT_FILE")
RESULT=$(jq -r '.result // "N/A"' "$CURRENT_FILE")
MEMO=$(jq -r '.memo // ""' "$CURRENT_FILE")
TITLE=$(jq -r '.title // "?"' "$CURRENT_FILE")

GIT_DIFF=$(git diff --stat HEAD 2>/dev/null || echo "(no git changes)")

# Check for project docs
DESIGN_NOTE=""
if [[ -f ".mpm/docs/DESIGN.md" ]]; then
  DESIGN_NOTE="DESIGN.md exists — read .mpm/docs/DESIGN.md for UI/UX criteria."
else
  DESIGN_NOTE="DESIGN.md not found — skip UI/UX stage or use general best practices."
fi

VERIFY_NOTE=""
if [[ -f ".mpm/docs/VERIFICATION.md" ]]; then
  VERIFY_NOTE="Read .mpm/docs/VERIFICATION.md for project-specific verification methods."
fi

# Mark as reviewed
touch "$REVIEWED_FLAG"

# --- Build review prompt ---
PROMPT="## 🔍 REVIEW: ${TITLE}

You are now in REVIEWER mode. Do NOT modify any code. Only verify and judge.

### Context Documents
- Read \`.mpm/docs/PROJECT.md\` for project vision and phase goals.
- ${DESIGN_NOTE}
- ${VERIFY_NOTE}

### Task Info
**Goal:**
${GOAL}

**Verification Method:**
${VERIFICATION}

**Developer's Result:**
${RESULT}

**Changed Files:**
${GIT_DIFF}

---

### Stage 1: Functionality Check
- Compare each goal item against the result. Is every item satisfied?
- Execute the verification methods listed above (curl, file check, script, etc.) and report actual results.
- Check for unintended changes in the diff — files that shouldn't have been modified.

### Stage 2: UI/UX Check
Skip if the task has no UI changes.
- Does the change follow the design principles in DESIGN.md?
- Are existing component patterns and design tokens used correctly?
- Is the visual result consistent with the rest of the project?
- Take a screenshot if possible to verify visual correctness.

### Stage 3: Code Review
- Is the code clean and consistent with existing patterns?
- Are there any security concerns, performance issues, or unnecessary complexity?
- Does the change respect the project architecture?

---

### Verdict
- If ALL stages pass: Say '✅ Review passed', then run \`python3 .mpm/scripts/task.py complete \${CLAUDE_SESSION_ID} success\` to move the task to past.
- If ANY stage fails: List what failed, which stage, and why. Fix it or suggest a follow-up task. Do NOT complete the task.

Do NOT modify code during review. Only read, verify, and report."

jq -n --arg p "$PROMPT" \
  '{decision:"block", reason:$p, systemMessage:"🔍 Reviewer: 3-stage verification in progress"}'
exit 0
