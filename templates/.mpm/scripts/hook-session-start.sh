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

  # Token files
  TOKEN_DIR="$DOCS/tokens"
  if [ -d "$TOKEN_DIR" ]; then
    for tf in "$TOKEN_DIR"/*; do
      [ -f "$tf" ] || continue
      output+="
--- tokens/$(basename "$tf") ---
$(cat "$tf")
"
    done
  fi

  if [ -n "$output" ]; then
    echo "[MPM Project Context]"
    echo "$output"
  fi
fi