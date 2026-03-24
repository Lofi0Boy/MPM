---
name: mpm-recycle
description: Scan past for rejected tasks, collect rejection context, and invoke /mpm-task-write to create improved replacement tasks.
---

# Recycle Rejected Tasks

Scan past for tasks rejected by human review, collect rejection context, then delegate to `/mpm-task-write` for proper task creation.

## Step 1: Find rejected tasks

```bash
python3 .mpm/scripts/task.py rejected
```

If none found, inform the user and stop.

## Step 2: For each rejected task, collect context

1. Read the full task details from past:
   - `prompt` (original instruction)
   - `result` (what was actually done)
   - `agent_reviews` (what reviewer found)
   - `human_review.comment` (why human rejected)
   - `parent_goal` (which goal this serves)

2. Summarize the rejection context:
   ```
   Previous attempt: [what was done]
   Rejection reason: [human's comment]
   Reviewer findings: [relevant agent review notes]
   What went wrong: [your analysis]
   ```

## Step 3: Invoke /mpm-task-write

Pass the rejection context to `/mpm-task-write` as additional input. Tell it:
- The original task title and goal
- The rejection context from Step 2
- The `parent_goal` (so the new task stays under the same goal)

`/mpm-task-write` will handle reading foundation docs, writing the prompt, setting goal/verification, and calling `task.py add`.

## Step 4: Remove the rejected task

After the new task is created:

```bash
python3 .mpm/scripts/task.py recycle <task_id> "<new_prompt>"
```

## Step 5: Confirm

Show the user what was recycled and the new task summary.

---

Always respond in the user's language.
