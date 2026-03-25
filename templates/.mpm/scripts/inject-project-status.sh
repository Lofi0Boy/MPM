#!/bin/bash
# inject-project-status.sh — shared project context injection
# Reads cwd and session_id from stdin JSON (works for both SessionStart and SubagentStart)

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null)

DOCS_DIR="$CWD/.mpm/docs"
SCRIPTS_DIR="$CWD/.mpm/scripts"

echo "## [MPM] Project Context"
echo ""

# --- 1. MPM workflow ---
WORKFLOW="$CWD/.mpm/mpm-workflow.md"
if [[ -f "$WORKFLOW" ]]; then
  echo "###" "mpm-workflow.md"
  cat "$WORKFLOW"
  echo ""
fi

# --- 2. Current task ---
CURRENT_FILE="$CWD/.mpm/data/current/${SESSION_ID}.json"
if [[ -n "$SESSION_ID" && -f "$CURRENT_FILE" ]]; then
  echo "###" "Current Task"
  cat "$CURRENT_FILE"
  echo ""
fi

# --- 3. Project documents ---
for filepath in "$DOCS_DIR"/*.md; do
  [[ -f "$filepath" ]] || continue
  echo "###" "$(basename "$filepath")"
  cat "$filepath"
  echo ""
done

# Token files
TOKEN_DIR="$DOCS_DIR/tokens"
if [[ -d "$TOKEN_DIR" ]]; then
  for tf in "$TOKEN_DIR"/*; do
    [[ -f "$tf" ]] || continue
    echo "###" "tokens/$(basename "$tf")"
    cat "$tf"
    echo ""
  done
fi

# --- 4. Feedback history ---
FEEDBACK="$CWD/.mpm/data/FEEDBACK_HISTORY.md"
if [[ -f "$FEEDBACK" ]]; then
  echo "###" "FEEDBACK_HISTORY.md (rejected/needs-input history)"
  cat "$FEEDBACK"
  echo ""
fi

# --- 5. Phase/Goal status ---
echo "###" "Phase/Goal Status"
python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null || echo "(no phases)"
echo ""
