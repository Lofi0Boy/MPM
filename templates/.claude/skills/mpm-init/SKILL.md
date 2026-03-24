---
name: mpm-init
description: Initialize a new MPM project — Create foundation documents, set up Phase, Goals and Tasks.
---

# Initialize MPM Project

Before starting, briefly explain to the user what will happen:

> "To help agents work more consistently on your project, I'll walk through an initial setup.

Then proceed through the following steps **in order**. Each step must be completed before moving to the next.

At the start of each step, briefly tell the user **what this step is and why it matters** in one sentence. Do not use internal terms like "Layer" or "PPGT" — just explain in plain language.

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

## Step 3: Project Documentation

> Tell the user: "Now we'll define your project clearly so all agents share the same understanding. This goes through a structured process — product definition, strategic review, then engineering review."

Run the following skills **in order**. Each skill is a conversation — complete it fully before moving to the next.

### 3a. `/mpm-office-hour`

Product definition. Understands the problem, challenges assumptions, generates a product spec.

After completion, a product spec is saved to `.mpm/gstack/design-{datetime}.md`.

### 3b. `/mpm-plan-ceo-review`

Strategic review. Challenges scope, maps the 12-month ideal, validates premises.

After completion, a CEO plan may be saved to `.mpm/gstack/ceo-plans/`.

### 3c. `/mpm-plan-eng-review`

Engineering review. Locks in architecture, data flow, test strategy, edge cases.

### 3d. Write foundation documents

After the three reviews are complete, split the generated documents into `.mpm/docs/` foundation documents by topic. **Do NOT summarize, compress, or rewrite any content** — move sections as-is, only separating them into the correct file.

1. **`.mpm/docs/PROJECT.md`** — Product planning and design sections. Move the following sections verbatim from the office-hour product spec and CEO review:
   - Problem Statement, Demand Evidence, Status Quo, Target User & Narrowest Wedge
   - Constraints, Premises, Approaches Considered, Recommended Approach
   - Success Criteria, Open Questions, The Assignment
   - Any CEO review additions (scope expansion, strategic direction, vision)
   - Wireframe layout descriptions (if any)

2. **`.mpm/docs/ARCHITECTURE.md`** — Technical architecture sections. Move the following sections verbatim from the eng review:
   - System design, component boundaries, data flow
   - Tech stack decisions, deployment strategy
   - Test strategy, edge cases, performance considerations
   - API design, database schema, infrastructure

```bash
mkdir -p .mpm/docs
```

**Rules:**
- Every sentence from the source documents must appear in exactly one of the two files — nothing lost, nothing duplicated.
- If a section contains both product and technical content (e.g., "Recommended Approach" discusses both product rationale and implementation), keep it in PROJECT.md and add a cross-reference in ARCHITECTURE.md: `> See PROJECT.md § Recommended Approach for product rationale.`
- Preserve original headings, formatting, and wording exactly.

Present both files to the user for confirmation (not approval of content — the content was already approved during each review).

## Step 4: VERIFICATION.md

> Tell the user: "This document defines how agents can verify their own work without asking you — so they can self-check before reporting done."

### 4a. Inspect non-browser verification tools

Scan the project for available verification methods:
- Test frameworks (pytest, jest, vitest, etc.)
- API endpoints (curl targets)
- Build commands (npm run build, cargo build, etc.)
- Linters / type checkers (eslint, mypy, tsc, etc.)

### 4b. Browser verification setup (UI projects only)

**If the project has a user-facing interface (determined in Step 4):**

> Tell the user: "For UI tasks, agents need a way to visually verify their work — open pages, take screenshots, click through flows. Without this, most UI reviews will fail. Let's set up which browser tools are available."

1. **Auto-detect** available browser tools:
   - `gstack browse` — check `$CWD/.claude/skills/gstack/browse/dist/browse`, `$HOME/.claude/skills/gstack/browse/dist/browse`, `gstack-browse` in PATH
   - `google-chrome --headless` — check `which google-chrome` or `which chromium-browser`
   - Claude in Chrome (Anthropic browser extension) — cannot auto-detect, must ask
   - Playwright (`npx playwright`, `bunx playwright`) — check if installed
   - Other (Puppeteer, Cypress, Selenium, etc.)

2. **Present findings** and ask the user:
   > "I found the following browser tools: [list]. Are there others you use? Which should agents use for visual verification?"
   >
   > "Agents need to be able to: (1) open a URL, (2) take a screenshot, (3) click/interact with elements. Which tool(s) cover these?"

3. **For each selected tool, confirm exact usage**. The user must verify the commands work. Example questions:
   - "What command starts the dev server?" (e.g., `npm run dev` → `http://localhost:3000`)
   - For custom tools: "How do agents take a screenshot?", "Can agents click and interact, or only take static screenshots?"

4. **Ask the user to set priority order**: "Which browser tool should agents try first? If that one fails, which is the fallback?" Record the priority order in VERIFICATION.md.

5. **If no browser tool is available**, warn the user clearly:
   > "⚠ No browser verification tool is set up. UI tasks will require human review for every visual check, which significantly slows down the workflow. Consider setting up one (e.g., gstack browse or headless Chrome)."

### 4c. Additional verification methods

Ask the user: "Are there additional ways agents can self-verify without asking anyone?"

### 4d. Write VERIFICATION.md

Write to `.mpm/docs/VERIFICATION.md` with the following structure:

```markdown
# Verification Methods

## Test & Build
- (list of available test/build/lint commands with exact invocations)

## Browser Verification
**Start dev server**: (command and URL)
**Priority order** (try in this order):
1. (tool name) — (limitations if any)
2. (fallback tool) — (limitations if any)

- For well-known tools (Claude in Chrome, headless Chrome): tool name is sufficient — agents already know how to use them.
- For custom/third-party tools (e.g., gstack browse): include exact commands for navigate, screenshot, and interact.

## Other
- (any additional verification methods)
```

Every command in this document must be copy-pasteable — no placeholders that agents need to figure out.


## Step 5: UI/UX Foundation

> Tell the user: "If your project has a user interface, we'll set up the design system and UI plan now. If it's backend-only, we can skip this."

Ask the user: "Does this project have a user-facing interface (web, mobile, dashboard, etc.)?"

- **If yes:** Run `/mpm-init-uiux`. This creates `.mpm/docs/DESIGN.md`, `.mpm/docs/tokens/`, and `.mpm/docs/UIUX.md`, then runs `/mpm-plan-design-review` to validate the UI plan.
- **If no:** Skip this step.



## Step 6: Define Phase 1

> Tell the user: "A Phase is a milestone — a concrete, verifiable goal you want to reach. Let's define the first one."

Ask the user what they want to achieve first. Based on their answer:
1. Propose a Phase name and verifiable completion state
2. User approves or corrects

Only Phase 1 is required at init. More phases can be added later.


Then create the Phase using `phase.py`:

```bash
python3 .mpm/scripts/phase.py add "Phase Name" "Verifiable completion state description"
```

This stores the Phase in `.mpm/data/phases.json` as structured data.

## Step 7: Define Goals and Tasks for Phase 1

> Tell the user: "Now I'll break down the Phase into Goals (what users get) and Tasks (what agents build). I'll show you the full plan for review before creating anything."

### 7a. Draft Goals

Based on the Phase definition and foundation documents:
1. Draft Goal items from the user's perspective
2. Present the full Goal list to the user for review
3. User approves, corrects, or requests changes
4. **Do not create Goals until user approves**

### 7b. Draft Tasks per Goal

For each approved Goal:
1. Break down into Tasks following `/mpm-task-write` skill guidelines (single function, 1–2 evidence items)
2. Present all Tasks grouped by Goal to the user:
   - Show: title, goal (acceptance criteria), verification method
   - Show dependency order if any
3. User approves, corrects, or requests changes
4. **Do not create Tasks until user approves the full plan**

### 7c. Create Goals and Tasks

Only after user approval of both Goals and Tasks:

```bash
# Create Goals
python3 .mpm/scripts/phase.py goal-add <phase_id> "Goal description from user perspective"
```

For each Task, invoke `/mpm-task-write` — do NOT call `task.py add` directly. The skill ensures consistent structure, foundation doc references, and proper verification methods.

Show the final created list to the user.

---

Always respond in the user's language.
