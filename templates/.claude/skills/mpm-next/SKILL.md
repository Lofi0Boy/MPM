---
name: mpm-next
description: Pick up the next task from the future queue and start working on it.
disable-model-invocation: true
allowed-tools: Bash(python3 *)
---

# Start Next Task

1. Run the pop command:
   ```bash
   python3 .mpm/scripts/task.py pop ${CLAUDE_SESSION_ID}
   ```
2. If the queue is empty, inform the user.
3. Read the popped task from `.mpm/data/current/${CLAUDE_SESSION_ID}.json`.
4. Read the task: `goal` and `verification` are already set by planner. Also refer to the project foundation docs injected at session start (PROJECT.md, ARCHITECTURE.md, DESIGN.md, UIUX.md, VERIFICATION.md) for context.
5. Fill in `approach` — your plan for how to implement:
   ```bash
   python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} approach "..."
   ```
6. Begin working on the task.

When work is complete, fill result, changes, and memo:
```bash
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} result "..."
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} changes "file:lines (what changed), ..."
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} memo "..."
```

This automatically transitions status `dev` → `agent-review`. The hooks handle review and next steps automatically.

Always respond in the user's language.
