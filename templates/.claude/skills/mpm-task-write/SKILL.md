---
name: mpm-task-write
description: Create well-structured tasks with proper Outcome/Context/Verification format.
---

# Write Tasks

Create tasks that developer agents can execute autonomously.

---

## Goal assignment

Every task MUST belong to a goal. Current goals:

!`python3 .mpm/scripts/phase.py status 2>/dev/null || echo "(no phases — run /mpm-init first)"`

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
```
## Context
- File paths to read
- Existing patterns to follow
- Design tokens/components to reference (sections in DESIGN.md)
- Architecture conventions to follow (sections in ARCHITECTURE.md)

## Non-goals
What is explicitly out of scope.
```

---

## Principles

- **Outcome over process.** Describe "what"; the developer agent decides "how".
- **Be specific.** "`/health` endpoint returns `{status: 'ok'}`" > "Add health checking"
- **Check upward consistency.** Always verify the Task aligns with its Goal, Phase, and Project purpose.
- **Reference ADV documents.** Include relevant ARCHITECTURE.md conventions and DESIGN.md tokens in Context.

---

## On UI/UX Tasks

When a Task involves UI changes, `.mpm/docs/DESIGN.md` and `.mpm/docs/tokens/` must be referenced.

**Include in Context:**
- Design tokens to apply (from `.mpm/docs/tokens/`)
- Existing component patterns to reuse and their code paths
- Layout principles relevant to this Task

**If DESIGN.md is missing or incomplete:**
- Do not create UI Tasks without design criteria
- Run `/mpm-init-design` skill first

**If a Task needs tokens not yet defined in `.mpm/docs/tokens/`:**
- Create new tokens that are **aligned with existing ones** (same scale, naming convention, color palette)
- Add the new tokens to the token file in `.mpm/docs/tokens/`
- Never introduce ad-hoc values that bypass the token system

---

## On Verification

**Always check `.mpm/docs/VERIFICATION.md` first** for project-specific verification methods.

Available verification methods:

| Method | Use case | Example |
|--------|----------|---------|
| Browser automation | Dynamic UI check | Claude in Chrome, etc. |
| curl + parse | API response check | `curl -s localhost:5100/api/projects \| jq .field` |
| Run tests | Logic verification | `pytest tests/test_auth.py` |
| Script execution | Output check | `python3 script.py && echo OK` |
| File inspection | Creation/modification check | Verify file contains expected content |
| Chrome | Static visual check | `google-chrome --headless --screenshot=...` |
| User confirmation | **Last resort** | Only when above methods cannot verify |

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
