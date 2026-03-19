#!/bin/bash
# PreToolUse hook (matcher: Edit|Write): warn if no current task exists.
# This fires right before file modifications, catching the exact moment
# when a task should have been created.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd' 2>/dev/null)

CURRENT_DIR="$CWD/.mpm/data/current"

# No .mpm directory — not an MPM project, skip
[ ! -d "$CWD/.mpm" ] && exit 0

# Check if any current task exists
TASK_FILE=$(find "$CURRENT_DIR" -name "*.json" -print -quit 2>/dev/null)

if [ -z "$TASK_FILE" ]; then
  cat <<'EOF'
[MPM] WARNING: You are about to edit files without a current task.
Create a task first: python3 .mpm/scripts/task.py create "$SID" "title" "prompt"
(Get SID: grep "session=" /tmp/mpm-hook.log | tail -1 | sed 's/.*session=//')
EOF
fi

exit 0
