#!/bin/bash
# SubagentStart hook (matcher: planner) + SessionStart router target
# Deterministically injects project context + gap directive into planner session.

set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null)

DOCS_DIR="$CWD/.mpm/docs"
SCRIPTS_DIR="$CWD/.mpm/scripts"

# --- 1. Inject project documents ---
echo "## [MPM] Project Context (auto-injected)"
echo ""

for filepath in "$DOCS_DIR"/*.md; do
  [[ -f "$filepath" ]] || continue
  echo "### $(basename "$filepath")"
  cat "$filepath"
  echo ""
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

# --- Feedback history ---
FEEDBACK="$DOCS_DIR/FEEDBACK.md"
if [[ -f "$FEEDBACK" ]]; then
  echo "### FEEDBACK.md (human review history)"
  cat "$FEEDBACK"
  echo ""
fi

# --- 2. Inject status ---
echo "### Phase/Goal Status"
python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null || echo "(no phases)"
echo ""

echo "### Task Status"
python3 "$SCRIPTS_DIR/task.py" status 2>/dev/null || echo "(no tasks)"
echo ""

# --- 3. Detect ALL gaps and output directive ---
echo "---"
echo "## [MPM] Planner Directive"
echo ""

GAPS=""

# Foundation docs
[[ ! -f "$DOCS_DIR/PROJECT.md" ]] && GAPS="${GAPS}PROJECT.md, "
[[ ! -f "$DOCS_DIR/ARCHITECTURE.md" ]] && GAPS="${GAPS}ARCHITECTURE.md, "
[[ ! -f "$DOCS_DIR/DESIGN.md" ]] && GAPS="${GAPS}DESIGN.md, "
[[ ! -f "$DOCS_DIR/VERIFICATION.md" ]] && GAPS="${GAPS}VERIFICATION.md, "

# Phase
PHASE_COUNT=$(python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null | grep -c "Phase:" || echo "0")
[[ "$PHASE_COUNT" -eq 0 ]] && GAPS="${GAPS}Phase, "

# Goals
GOAL_COUNT=$(python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null | grep -c "\[" || echo "0")
[[ "$GOAL_COUNT" -eq 0 ]] && GAPS="${GAPS}Goals, "

# Tasks
FUTURE_COUNT=$(python3 -c "
import json
from pathlib import Path
f = Path('$CWD/.mpm/data/future.json')
tasks = json.loads(f.read_text()) if f.exists() else []
print(len(tasks))
" 2>/dev/null || echo "0")
[[ "$FUTURE_COUNT" -eq 0 ]] && GAPS="${GAPS}Tasks, "

# Strip trailing comma+space
GAPS="${GAPS%, }"

# Rejected tasks (separate from init)
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

if [[ -n "$GAPS" ]]; then
  echo "**Foundation gaps: ${GAPS}**"
  echo "→ Run /mpm-init to fill missing items. Guide the user through each gap."
  echo ""
fi

if [[ "$REJECTED_COUNT" -gt 0 ]]; then
  echo "**$REJECTED_COUNT rejected task(s) in past.**"
  echo "→ Run /mpm-recycle to rewrite and return them to future."
  echo ""
fi

if [[ -z "$GAPS" ]] && [[ "$REJECTED_COUNT" -eq 0 ]]; then
  echo "**All foundation in place.** Proceed with normal planning — review goals, create tasks as needed."
fi
