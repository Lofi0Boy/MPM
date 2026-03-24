---
name: mpm-task-write
description: Create well-structured tasks with proper Outcome/Context/Verification format.
---

# Write Tasks

Create tasks that developer agents can execute autonomously.

---

## Goal assignment

Every task MUST belong to a goal. Current goals:

!`python3 .mpm/scripts/phase.py status`

Choose the appropriate goal and include `--goal-id <id>` when calling `task.py add`.

**If no suitable goal exists:** Create one first with `phase.py goal-add <phase_id> "title"`.

**NEVER write .mpm/data/ JSON files directly.** Always use `task.py add`.

---

## Task structure

**Fields set by planner (via task.py add):**
- `title` — one-line summary
- `prompt` — context, non-goals, and any additional instructions
- `goal` — verifiable acceptance criteria (WHAT must be true)
- `verification` — executable verification methods (HOW to check)
- `parent_goal` — which phase goal this serves (via --goal-id)

**Prompt content (context for dev):**

Before writing the prompt, **read all documents in `.mpm/docs/`** and extract sections relevant to this task. If `FEEDBACK.md` exists, check for past rejection patterns related to this task's area — avoid repeating mistakes that led to rejections.

```
## Context
- File paths to read (specific files the dev agent should read before starting)
- Architecture conventions to follow (cite specific sections from ARCHITECTURE.md)
- Existing patterns to follow (reference actual code patterns in the codebase)
- [UI tasks only] Design system constraints (cite DESIGN.md sections + token file paths)
- [UI tasks only] UI structure and flow context (cite UIUX.md — which screen, expected states, navigation flow)

## Non-goals
What is explicitly out of scope.
```

**The prompt must be self-contained.** A dev agent reading only the prompt (without foundation docs) should have enough context to start working. Don't say "follow ARCHITECTURE.md" — say "follow the error handling pattern in ARCHITECTURE.md §Error Handling: use named exceptions, never catch-all."

---

## Task granularity

A task must be a **single function** verifiable with **1–2 evidence items**.

### Split triggers — if ANY of these apply, split into multiple tasks:

| Trigger | Example |
|---------|---------|
| Evidence ≥ 3 | "API returns OK, screenshot matches, config file updated" → 3 tasks |
| Separate file areas ≥ 2 | "Change backend handler AND update frontend component" → 2 tasks |
| AND-connected requirements | "Add auth middleware and add rate limiting" → 2 tasks |
| Goal has multiple verbs | "Create endpoint, write migration, update docs" → 3 tasks |

### How to split

1. Each sub-task gets its own `task.py add` call
2. Add tasks **in dependency order** (first dependency = first in queue)
3. If task B depends on task A's output, state it in B's Context: `"Depends on: <A's title>. Read <file A modifies> for context."`
4. Each sub-task must be independently verifiable — never "verify together with task X"

### Example

**Before (too big):**
> "Add user profile page with API endpoint, database migration, and frontend component"

**After (split):**
1. "Add user profile DB migration" — evidence: migration runs, table exists
2. "Add GET /api/profile endpoint" — evidence: `curl` returns profile JSON
3. "Add profile page frontend component" — evidence: screenshot shows profile

---

## Principles

- **Outcome over process.** Describe "what"; the developer agent decides "how".
- **Be specific.** "`/health` endpoint returns `{status: 'ok'}`" > "Add health checking"
- **Check upward consistency.** Always verify the Task aligns with its Goal, Phase, and Project purpose. Read PROJECT.md to confirm the task serves the product vision.
- **Ground in foundation docs.** Every task prompt must cite specific sections from `.mpm/docs/` documents — not just mention them generically.

---

## On UI/UX Tasks

When a Task involves UI changes, `.mpm/docs/DESIGN.md`, `.mpm/docs/tokens/`, and `.mpm/docs/UIUX.md` must be referenced.

**Include in Context:**
- Design tokens to apply (cite specific token names from `.mpm/docs/tokens/`)
- Existing component patterns to reuse and their code paths
- Layout principles relevant to this Task (cite DESIGN.md sections)
- Which screen this task belongs to, expected interaction states, and navigation flow (cite UIUX.md sections)

**Include in prompt — dev agent instructions:**
- "Follow `/mpm-ui-ux-pro-max` skill UX guidelines for interaction patterns, accessibility, and animation."
- "Before marking done, run through the pre-delivery checklist in `/mpm-ui-ux-pro-max` skill."

**If DESIGN.md or UIUX.md is missing or incomplete:**
- Do not create UI Tasks without design and UI/UX criteria
- Run `/mpm-init-uiux` skill first

**If a Task needs tokens not yet defined in `.mpm/docs/tokens/`:**
- Create new tokens that are **aligned with existing ones** (same scale, naming convention, color palette)
- Add the new tokens to the token file in `.mpm/docs/tokens/`
- Never introduce ad-hoc values that bypass the token system

---

## On Verification

**Always check `.mpm/docs/VERIFICATION.md` first** for project-specific verification methods.

**Bad:** "Verify the feature works correctly"
**Good:** "`curl -s localhost:5100/api/sessions | jq length` is 1 or more, and screenshot shows the terminal panel"

---

## Command

```bash
python3 .mpm/scripts/task.py add "task title" "## Context
- File paths to read
- Existing patterns to follow

## Non-goals
..." --goal "verifiable acceptance criteria" --verification "curl/test/screenshot commands" --goal-id <goal_id>
```

Note: `goal` and `verification` are now **separate fields**, not part of the prompt. The prompt contains Context and Non-goals only.

---

Always respond in the user's language.
