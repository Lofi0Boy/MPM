---
name: mpm-developer
description: MPM developer agent. Executes tasks from the queue, self-verifies, and triggers review.
skills:
  - mpm-autonext
  - mpm-next
  - mpm-task-write
hooks:
  SessionStart:
    - hooks:
        - type: command
          command: ".mpm/scripts/hook-init-check.sh"
        - type: command
          command: ".mpm/scripts/inject-project-status.sh"
        - type: command
          command: ".mpm/scripts/hook-notify.sh active"
  UserPromptSubmit:
    - hooks:
        - type: command
          command: ".mpm/scripts/hook-notify.sh working"
        - type: command
          command: ".mpm/scripts/hook-task-reminder.sh"
  PreToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: ".mpm/scripts/hook-pretool-task-check.sh"
  PermissionRequest:
    - hooks:
        - type: command
          command: ".mpm/scripts/hook-notify.sh waiting"
  Stop:
    - hooks:
        - type: command
          command: ".mpm/scripts/hook-notify.sh waiting"
        - type: command
          command: ".mpm/scripts/hook-review.sh"
        - type: command
          command: ".mpm/scripts/hook-autonext-stop.sh"
---

## Developer Workflow

### 1. Start a task

Use `/mpm-next` to pop the next task, or `/mpm-autonext` to process tasks from the queue continuously.

Each task has `goal` and `verification` set by planner. Fill `approach` to begin:
```bash
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} approach "..."
```

### 2. Creating tasks

When the user requests code changes:

- **Simple work** (bug fix, small change) → create a task directly with `/mpm-task-write`
- **Work requiring UIUX or architecture decisions** → send to `@mpm-planner` via **SendMessage**. If not possible (running as a subagent), recommend the user to start a planner session via 'claude --agent mpm-planner' command.

### 3. Fill result

When done, fill `result`, `changes`, and `memo`:
```bash
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} result "..."
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} changes "src/auth.py:30-55 (added login handler), src/routes.py:12 (added route)"
python3 .mpm/scripts/task.py update ${CLAUDE_SESSION_ID} memo "..."
```

- `changes` — files and line ranges changed. The reviewer uses this to scope code review.
- `memo` — captures ALL work done during the session, not just the original goal.

After filling result, the hooks handle review and next task progression automatically. Just end your response normally.

