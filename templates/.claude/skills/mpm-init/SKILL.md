---
name: mpm-init
description: Initialize a new MPM project — scan, define Project+Phase, create foundation documents, set up Goals and Tasks.
---

# Initialize MPM Project

Before starting, briefly explain to the user what will happen:

> "To help agents work more consistently on your project, I'll walk through an initial setup:
> Project → Phase → Architecture → Design → Verification → Goals → Tasks.
> Let's get started!"

Then proceed through the following steps **in order**. Each step must be completed before moving to the next.

---

## Step 1: Automatic project scan

Scan the following to understand the project before asking anything:

- `README.md` — project description
- `package.json` / `pyproject.toml` / `Cargo.toml` etc. — tech stack, dependencies
- Directory structure (1-2 levels deep) — project scale and layout
- `docs/` and all `.md` files in the project — existing documentation
- `CLAUDE.md`, `.claude/rules/` — existing development rules
- Recent git log (last 10 commits) — recent work direction

## Step 2: Share your understanding

Present what you've learned to the user:
- "This project appears to be ... Is that correct?"
- Share your understanding of the tech stack, modules, and current state.

## Step 3: Project name + description

1. Ask for the **project name** — used as identifier on the dashboard
2. Ask the user to **describe the project** — listen to their description and organize it into a clear paragraph. Do not force brevity; capture the essence.

Show the organized result to the user for confirmation.

## Step 4: Define Phase 1

Ask the user what they want to achieve first. Based on their answer:
1. Propose a Phase name and verifiable completion state
2. User approves or corrects

Only Phase 1 is required at init. More phases can be added later.

## Step 5: Write PROJECT.md + Phase

Write to `.mpm/docs/PROJECT.md`:

```markdown
# Project Name

Project description paragraph.
```

The dashboard parses:
- `# heading` → project display name
- First non-empty line after `#` (before any `##`) → description

**Note:** PROJECT.md only contains the project name and description. Phases are NOT written here.

Then create the Phase using `phase.py`:

```bash
python3 .mpm/scripts/phase.py add "Phase Name" "Verifiable completion state description"
```

This stores the Phase in `.mpm/data/phases.json` as structured data.

## Step 6: ARCHITECTURE.md

1. Scan the codebase — directory structure, imports, patterns, tech stack
2. Propose an architecture summary: key modules, data flow, conventions to follow
3. User approves or corrects
4. Write to `.mpm/docs/ARCHITECTURE.md`

## Step 7: DESIGN.md

1. Judge whether this project has a UI component
2. If no UI → confirm with user and skip
3. If UI exists → run `/mpm-init-design` skill

## Step 8: VERIFICATION.md

1. Inspect available verification tools in the project:
   - Test frameworks (pytest, jest, etc.)
   - API endpoints (curl targets)
   - Build commands
   - Browser tools (headless chrome, Claude in Chrome)
2. Ask the user: "Are there additional ways you can self-verify without asking anyone?"
3. Write to `.mpm/docs/VERIFICATION.md`

## Step 9: Define Goals for Phase 1

Based on the Phase definition and foundation documents:
1. Write Goal items from the user's perspective
2. Add them using `phase.py`:

```bash
python3 .mpm/scripts/phase.py goal-add <phase_id> "Goal description from user perspective"
```

3. Notify the user of the Goals

## Step 10: Create initial Tasks

Based on Goals, create Tasks using `/mpm-task-write` skill.
Show the created task list to the user.

---

Always respond in the user's language.
