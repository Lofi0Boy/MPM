#!/bin/bash
# SessionStart hook: check if MPM is initialized in this project.
# If PROJECT.md doesn't exist, prompt the user to run /mpm-init-project.

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd' 2>/dev/null)

# Check if .mpm directory exists but PROJECT.md is missing
if [ -d "$CWD/.mpm" ] && [ ! -f "$CWD/.mpm/docs/PROJECT.md" ]; then
  cat <<'EOF'
[MPM] This project hasn't been initialized yet.
Run /mpm-init-project to set up your project name, description, and first tasks.
EOF
  exit 0
fi

# PROJECT.md exists — normal session
exit 0
