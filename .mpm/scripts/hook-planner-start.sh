#!/bin/bash
# SubagentStart hook (matcher: planner)
# Deterministically injects project context + first gap directive into planner session.

set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null)

DOCS_DIR="$CWD/.mpm/docs"
SCRIPTS_DIR="$CWD/.mpm/scripts"

# --- 1. Inject project documents ---
echo "## [MPM] Project Context (auto-injected)"
echo ""

for doc in PROJECT.md ARCHITECTURE.md DESIGN.md VERIFICATION.md; do
  filepath="$DOCS_DIR/$doc"
  if [[ -f "$filepath" ]]; then
    echo "### $doc"
    cat "$filepath"
    echo ""
  else
    echo "### $doc — NOT FOUND"
    echo ""
  fi
done

# Token files
TOKEN_DIR="$DOCS_DIR/tokens"
if [[ -d "$TOKEN_DIR" ]]; then
  for tf in "$TOKEN_DIR"/*; do
    [[ -f "$tf" ]] || continue
    echo "### tokens/$(basename "$tf")"
    cat "$tf"
    echo ""
  done
fi

# --- 2. Inject status ---
echo "### Phase/Goal Status"
python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null || echo "(no phases)"
echo ""

echo "### Task Status"
python3 "$SCRIPTS_DIR/task.py" status 2>/dev/null || echo "(no tasks)"
echo ""

# --- 3. Detect first gap and output directive ---
echo "---"
echo "## [MPM] Planner Directive"
echo ""

# Check 1: PROJECT.md
if [[ ! -f "$DOCS_DIR/PROJECT.md" ]]; then
  echo "**GAP: PROJECT.md is missing.**"
  echo "→ Follow the /mpm-init skill to initialize the project."
  exit 0
fi

# Check 2: Phase defined?
PHASE_COUNT=$(python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null | grep -c "Phase:" || echo "0")
if [[ "$PHASE_COUNT" -eq 0 ]]; then
  echo "**GAP: No phases defined.**"
  echo "→ Define Phase 1 with the user using \`phase.py add\`."
  exit 0
fi

# Check 3: ARCHITECTURE.md
if [[ ! -f "$DOCS_DIR/ARCHITECTURE.md" ]]; then
  echo "**GAP: ARCHITECTURE.md is missing.**"
  echo "→ Scan the codebase, propose architecture patterns, and write ARCHITECTURE.md."
  exit 0
fi

# Check 4: DESIGN.md
if [[ ! -f "$DOCS_DIR/DESIGN.md" ]]; then
  echo "**GAP: DESIGN.md is missing.**"
  echo "→ Follow the /mpm-init-design skill to set up the design system. Skip if no UI."
  exit 0
fi

# Check 5: VERIFICATION.md
if [[ ! -f "$DOCS_DIR/VERIFICATION.md" ]]; then
  echo "**GAP: VERIFICATION.md is missing.**"
  echo "→ Inspect available verification tools, ask the user, and write VERIFICATION.md."
  exit 0
fi

# Check 6: Goals defined?
GOAL_COUNT=$(python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null | grep -c "Goal:" || echo "0")
if [[ "$GOAL_COUNT" -eq 0 ]]; then
  echo "**GAP: No goals defined for the active phase.**"
  echo "→ Write goals from the user's perspective using \`phase.py goal-add\`."
  exit 0
fi

# Check 7: Tasks sufficient?
FUTURE_COUNT=$(python3 -c "
import json
from pathlib import Path
f = Path('$CWD/.mpm/data/future.json')
tasks = json.loads(f.read_text()) if f.exists() else []
print(len(tasks))
" 2>/dev/null || echo "0")
if [[ "$FUTURE_COUNT" -eq 0 ]]; then
  echo "**GAP: No tasks in future queue.**"
  echo "→ Create tasks following the /mpm-task-write skill. Include --goal-id."
  exit 0
fi

# Check 8: Rejected tasks?
REJECTED_COUNT=$(python3 -c "
import json
from pathlib import Path
past_dir = Path('$CWD/.mpm/data/past')
count = 0
if past_dir.exists():
    for pf in past_dir.glob('*.json'):
        for t in json.loads(pf.read_text()):
            hr = t.get('human_review') or {}
            if hr.get('verdict') == 'rejected':
                count += 1
print(count)
" 2>/dev/null || echo "0")
if [[ "$REJECTED_COUNT" -gt 0 ]]; then
  echo "**GAP: $REJECTED_COUNT rejected task(s) found in past.**"
  echo "→ Follow the /mpm-recycle skill to rewrite and return them to future."
  exit 0
fi

echo "**All foundation in place.** Proceed with normal planning — review goals, create tasks as needed."
