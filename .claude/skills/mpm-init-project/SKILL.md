---
name: mpm-init-project
description: Initialize MPM in the current project — scan, write PROJECT.md, and set up first tasks.
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

## Step 4: Define Phases

Phases are milestone-level goals with verifiable outcomes. Each phase groups related tasks.

Ask the user:
- "What are the major milestones or features you want to achieve?"
- "Let's define phases — each phase should have a clear, verifiable goal."

For each phase the user describes:
1. Clarify a **name** (short, descriptive)
2. Clarify a **goal** (must be verifiable — e.g., "Users can log in via OAuth and see their dashboard" not "Implement auth")

**Minimum 1 phase required.** Typically 2-4 phases for a new project.

Phases will be written directly into PROJECT.md in Step 6. Show the phase list to the user for confirmation before proceeding.

## Step 5: What to work on first

Discuss with the user:
- "Which phase should we start with?"
- "What's the first concrete task within that phase?"
- Help break down their answer into concrete, actionable tasks.

## Step 6: Write PROJECT.md

Write to `.mpm/docs/PROJECT.md`.

**Required structure:**
```markdown
# Project Name (MUST be in English)

First paragraph is the project description (displayed on the dashboard header).

## Phases

### First Phase Name [active] [0%]
Verifiable goal description

### Second Phase Name [0%]
Another goal description

## ... (optional sections — content can be any language)
```

The **Phases** section is required. Use `### Phase Name [active] [N%]` format. Mark the first phase as `[active]`.

**IMPORTANT:** The `# heading` (project name) MUST be written in English — MPM uses it as a machine-readable identifier. The description and body content can be in any language.

The dashboard parses:
- **`# heading`** → project display name (English required)
- **First non-empty line after `#`** (before any `##`) → description

## Step 7: Create initial future tasks

Based on the discussion in Step 5, create future tasks:
```bash
python3 .mpm/scripts/task.py add "task title" "detailed prompt"
```

Add 2-5 concrete tasks that the user can start working on immediately.
Show the task list to the user for confirmation.

Show the result to the user and save after confirmation.
Always respond in the user's language.
