---
name: mpm-review-functional
description: Verify that the implementation actually works. Run verification methods, test unhappy paths, check for silent errors.
---

# Functional Review

> **Review context (injected by reviewer):**
> - **Task fields** — `goal` (acceptance criteria), `prompt` (context + non-goals), `verification` (how to check). These define what was requested. Judge against them exactly.
> - **`.mpm/docs/VERIFICATION.md`** — project-specific verification tools and exact commands. Use these, do not guess commands.
> - **`.mpm/docs/PROJECT.md`** — product vision and target users. A feature that "works" but contradicts the product direction is a FAIL.

## Do not trust the dev's claim. Run everything yourself.

### 1. Run task verification

Execute every verification method from the task's `verification` field and from `VERIFICATION.md`. Record pass/fail for each.

### 2. Test unhappy paths

For each feature the task implements, test:
- **Bad input**: empty string, null, wrong type, too long, special characters
- **Missing data**: what happens when the data doesn't exist?
- **Error conditions**: network timeout, server error, permission denied
- **Concurrent access**: if applicable, what happens with simultaneous requests?

### 3. Verify data flow

If the task involves data persistence:
- Create → verify it's stored
- Read → verify it returns the right data
- Update → verify the change persists
- Delete → verify it's actually gone

## Cannot verify → needs-input

If a verification step requires a tool or credential you don't have (auth tokens, API keys, external services, browser tool), do NOT skip it or pass anyway. Return `FUNCTIONAL REVIEW: NEEDS-INPUT` and list exactly what you couldn't verify and why.

## Return format

```
FUNCTIONAL REVIEW: PASS/FAIL
Issues:
- [issue 1: what's wrong + where + how to fix]
- [issue 2: ...]
Evidence:
- [curl output, test results, screenshots, etc.]
```
