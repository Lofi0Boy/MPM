---
name: mpm-init-project
description: Initialize MPM in the current project — scan, write PROJECT.md, and set up first tasks.
disable-model-invocation: true
---

# Initialize MPM Project

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

## Step 3: Project name + description (required)

The user MUST provide:
1. **Project name** (English) — used as machine-readable identifier on the dashboard
2. **One-line description** — displayed below the project name on the dashboard

## Step 4: What to work on first

Discuss with the user:
- "What would you like to tackle first?"
- "What's the most important thing to get done right now?"
- Help break down their answer into concrete, actionable tasks.

## Step 5: Write PROJECT.md

Write to `.mpm/docs/PROJECT.md`.

**Required structure:**
```markdown
# Project Name (MUST be in English)

First paragraph is the project description (displayed on the dashboard header).

## ... (optional sections — content can be any language)
```

**IMPORTANT:** The `# heading` (project name) MUST be written in English — MPM uses it as a machine-readable identifier. The description and body content can be in any language.

The dashboard parses:
- **`# heading`** → project display name (English required)
- **First non-empty line after `#`** (before any `##`) → description

## Step 6: Create initial future tasks

Based on the discussion in Step 4, create future tasks:
```bash
python3 .mpm/scripts/task.py add "task title" "detailed prompt"
```

Add 2-5 concrete tasks that the user can start working on immediately.
Show the task list to the user for confirmation.

Show the result to the user and save after confirmation.
Always respond in the user's language.
