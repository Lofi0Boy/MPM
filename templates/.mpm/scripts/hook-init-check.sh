#!/bin/bash
# SessionStart hook: check if MPM is initialized in this project.
# If PROJECT.md doesn't exist, prompt the user to run /mpm-init.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd' 2>/dev/null)

# Check if .mpm directory exists but PROJECT.md is missing
if [ -d "$CWD/.mpm" ] && [ ! -f "$CWD/.mpm/docs/PROJECT.md" ]; then
  cat <<'INITEOF'
[MPM] This project hasn't been initialized yet.
Spawn @planner to run /mpm-init and set up your project.
INITEOF
  exit 0
fi

# PROJECT.md exists — normal session
exit 0
