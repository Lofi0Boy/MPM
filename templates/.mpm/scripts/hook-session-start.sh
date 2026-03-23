#!/bin/bash
# SessionStart hook: inject project docs + browse tool path into context.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd' 2>/dev/null)
DOCS="$CWD/.mpm/docs"

# --- 1. Project documents ---
if [ -d "$DOCS" ]; then
  output=""
  for filepath in "$DOCS"/*.md; do
    [ -f "$filepath" ] || continue
    filename=$(basename "$filepath")
    content=$(cat "$filepath")
    output+="
--- $filename ---
$content
"
  done

  if [ -n "$output" ]; then
    echo "[MPM Project Context]"
    echo "$output"
  fi
fi

# --- 2. Browse tool discovery ---
B=""
[ -n "$CWD" ] && [ -x "$CWD/.claude/skills/gstack/browse/dist/browse" ] && B="$CWD/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.claude/skills/gstack/browse/dist/browse" ] && B="$HOME/.claude/skills/gstack/browse/dist/browse"
[ -z "$B" ] && [ -x "$HOME/.local/share/gstack/browse/dist/browse" ] && B="$HOME/.local/share/gstack/browse/dist/browse"
[ -z "$B" ] && command -v gstack-browse >/dev/null 2>&1 && B="$(command -v gstack-browse)"

if [ -n "$B" ]; then
  echo "[MPM Browse Tool]"
  echo "Browse binary found: $B"
  echo "Use as: $B goto <url>, $B screenshot <path>, $B click <selector>, $B console --errors"
fi
