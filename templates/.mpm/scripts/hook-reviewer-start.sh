#!/bin/bash
# SubagentStart hook (matcher: reviewer)
# Injects task content, project docs, phase status, and git diff into reviewer context.

set -euo pipefail

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // "."' 2>/dev/null)
PARENT_SESSION=$(echo "$INPUT" | jq -r '.session_id // ""' 2>/dev/null)

DOCS_DIR="$CWD/.mpm/docs"
SCRIPTS_DIR="$CWD/.mpm/scripts"
CURRENT_FILE="$CWD/.mpm/data/current/${PARENT_SESSION}.json"

echo "## [MPM] Reviewer Context (auto-injected)"
echo ""

# --- 1. Task being reviewed ---
if [[ -f "$CURRENT_FILE" ]]; then
  echo "### Current Task"
  cat "$CURRENT_FILE"
  echo ""
else
  echo "### Current Task — NOT FOUND"
  echo ""
fi

# --- 2. Project documents ---
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
  echo "### FEEDBACK.md (human review history — learn from past judgments)"
  cat "$FEEDBACK"
  echo ""
fi

# --- 3. Phase/Goal status ---
echo "### Phase/Goal Status"
python3 "$SCRIPTS_DIR/phase.py" status 2>/dev/null || echo "(no phases)"
echo ""

# --- 4. Git diff (changes during this task) ---
echo "### Git Diff (uncommitted changes)"
cd "$CWD"
DIFF=$(git diff 2>/dev/null || echo "(no git)")
STAGED=$(git diff --cached 2>/dev/null || echo "")
if [[ -n "$DIFF" ]] || [[ -n "$STAGED" ]]; then
  if [[ -n "$STAGED" ]]; then
    echo "#### Staged"
    echo '```'
    echo "$STAGED"
    echo '```'
    echo ""
  fi
  if [[ -n "$DIFF" ]]; then
    echo "#### Unstaged"
    echo '```'
    echo "$DIFF"
    echo '```'
  fi
else
  echo "(no uncommitted changes — check recent commits)"
  echo '```'
  git log --oneline -5 2>/dev/null || echo "(no git history)"
  echo '```'
fi
echo ""

# --- 5. Browse tool discovery ---
B=""
[ -x "$CWD/.claude/skills/gstack/browse/dist/browse" ] && B="$CWD/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.claude/skills/gstack/browse/dist/browse" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.local/share/gstack/browse/dist/browse" ] && B="$HOME/.local/share/gstack/browse/dist/browse"
[ -z "$B" ] && command -v gstack-browse >/dev/null 2>&1 && B="$(command -v gstack-browse)"

if [[ -n "$B" ]]; then
  echo "### Browse Tool"
  echo "Binary: $B"
  echo "Use as: \$B goto <url>, \$B screenshot <path>, \$B click <selector>, \$B console --errors"
  echo ""
fi

# --- 6. Other project files the reviewer may want to read ---
echo "### Additional files you may want to read"
echo "These are project-specific files that may be relevant to your review:"
find "$CWD" -name "*.md" -not -path "*/.mpm/*" -not -path "*/.claude/*" -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/.venv/*" -not -path "*/venv/*" 2>/dev/null | head -10
echo ""
