#!/bin/bash
# Outputs current task status to stdout so Claude sees it as context each turn.
# Used in UserPromptSubmit hook.

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd' 2>/dev/null)

CURRENT_DIR="$CWD/.mpm/data/current"

if [ ! -d "$CURRENT_DIR" ]; then
  echo "[MPM Task] No current task. If user requests code changes, spawn @planner to create tasks."
  exit 0
fi

TASK_FILE=$(find "$CURRENT_DIR" -name "*.json" -print -quit 2>/dev/null)

if [ -z "$TASK_FILE" ]; then
  echo "[MPM Task] No current task. If user requests code changes, spawn @planner to create tasks."
  exit 0
fi

TITLE=$(jq -r '.title // "untitled"' "$TASK_FILE" 2>/dev/null)
GOAL=$(jq -r '.goal // "not set"' "$TASK_FILE" 2>/dev/null)
STATUS=$(jq -r '.status // "unknown"' "$TASK_FILE" 2>/dev/null)

cat <<EOF
[MPM Task] Current: "$TITLE" ($STATUS)
  Goal: $GOAL
  → If this is a continuation of the current task, keep working.
  → If this is a NEW task, finish the current one first (fill result+memo via task.py update).
EOF
