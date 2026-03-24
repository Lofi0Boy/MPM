#!/bin/bash
# SessionStart hook: route to agent-specific hooks based on agent_type.

INPUT=$(cat)
AGENT=$(echo "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null)

if [ "$AGENT" = "mpm-planner" ]; then
  echo "$INPUT" | exec .mpm/scripts/hook-planner-start.sh
fi
