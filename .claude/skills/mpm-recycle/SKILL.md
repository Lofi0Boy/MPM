---
name: mpm-recycle
description: Scan past for rejected tasks, rewrite their prompts with rejection context, and return them to future queue.
---

# Recycle Rejected Tasks

Scan past for tasks rejected by human review, rewrite their prompts incorporating rejection feedback and history, then return them to the future queue for another attempt.

## Step 1: Find rejected tasks

```bash
python3 .mpm/scripts/task.py rejected
```

If none found, inform the user and stop.

## Step 2: For each rejected task

1. Read the full task details from past (the `rejected` command shows id, title, rejection comment)
2. Read the relevant past file to get the full task object — especially:
   - `prompt` (original instruction)
   - `result` (what was actually done)
   - `agent_reviews` (what reviewer found)
   - `human_review.comment` (why human rejected)
   - `parent_goal` (which goal this serves)

3. Read project documents for context:
   - `.mpm/docs/PROJECT.md`
   - `.mpm/docs/ARCHITECTURE.md`
   - `.mpm/docs/DESIGN.md`

## Step 3: Rewrite the prompt

Craft a new, improved prompt that incorporates:

```
## Outcome
[Rewrite the original outcome, adjusted based on rejection feedback]

## Context
- [Original context, if any]
- Previous attempt result: [summary of what was done]
- Rejection reason: [human's comment]
- Reviewer findings: [relevant agent review notes]

## Verification
[Same or improved verification methods]

## Non-goals
[Clarify scope based on what went wrong]
```

**Key principle:** The new prompt should be **more specific** than the original. Use the rejection reason to narrow scope, clarify requirements, or fix misunderstandings. The developer who picks this up has NO context from the previous attempt — the prompt must be self-contained.

## Step 4: Recycle via task.py

```bash
python3 .mpm/scripts/task.py recycle <task_id> "<new_prompt>"
```

This removes the rejected task from past and creates a fresh task in future with the rewritten prompt.

## Step 5: Confirm

Show the user what was recycled and the new prompt summary.

---

Always respond in the user's language.
