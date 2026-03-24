---
name: mpm-review-uiux
description: UI/UX unified review — design system compliance, mpm-ui-ux-pro-max guideline check, and browser-based visual verification. UI tasks only.
---

# UI/UX Review

> **Review context (injected by reviewer):**
> - **Task fields** — `goal` (acceptance criteria), `prompt` (context + non-goals), `verification` (how to check). These define what was requested. Judge against them exactly.
> - **`.mpm/docs/VERIFICATION.md`** — project-specific verification tools and exact commands. Use the **Browser Verification** section for navigation, screenshots, and interaction throughout this review.
> - **`.mpm/docs/DESIGN.md`** + **`.mpm/docs/tokens/`** — project design system. Primary criteria for visual judgment.
> - **`.mpm/docs/UIUX.md`** — UI structure, screen flows, interaction states, user journey. Check if the implementation matches the screens, states, and flows defined here.
> - **`.mpm/docs/PROJECT.md`** — product vision and target users. UX must serve them.

Three pillars:
1. Project design system compliance (DESIGN.md + tokens/)
2. Professional UX standards (/mpm-ui-ux-pro-max guidelines)
3. Browser-based visual verification (VERIFICATION.md tools)

---

## 0. Setup: Browser tool

Use the exact commands from VERIFICATION.md's **Browser Verification** section for all browsing operations in this review.

If no browser tool is configured → you can only do code-level checks. Note this limitation in the verdict.

---

## 1. DESIGN.md + tokens/ alignment

The injected foundation docs include DESIGN.md and token files. Judge the implementation against them.

### 1a. Token compliance

**No hardcoded values allowed.** Scan changed files:

```bash
# Hardcoded colors
git diff --name-only | xargs grep -n '#[0-9a-fA-F]\{3,8\}' 2>/dev/null | head -20

# Hardcoded pixel values (excluding border: 1px, 0px)
git diff --name-only | xargs grep -n '[^0-9]px' 2>/dev/null | grep -vE 'border.*1px|0px' | head -20

# Hardcoded font families
git diff --name-only | xargs grep -n 'font-family' 2>/dev/null | head -10
```

For each finding: compare against token values in `.mpm/docs/tokens/`. Hardcoded values that should be tokens → FAIL.

### 1b. Design direction alignment

Compare the implementation against DESIGN.md:

| DESIGN.md section | Check |
|-------------------|-------|
| **Aesthetic Direction** | Does the overall feel match? |
| **Typography** | Specified fonts used? Correct roles (heading vs body)? |
| **Color** | Primary, secondary, semantic colors match? |
| **Spacing** | Base unit and density match? |
| **Layout** | Grid approach, max content width, border-radius scale? |
| **Motion** | Easing and duration within specified ranges? |

### 1c. Visual consistency

Take screenshots using the browser tool from VERIFICATION.md and compare with existing pages:
- Does this page look like it belongs to the same app?
- Consistent header/footer/navigation style?
- Same spacing rhythm as other pages?
- Same button/card/form component styles?

### 1d. Component patterns

- New components: do they follow existing vocabulary from DESIGN.md?
- Reused components: are they used consistently (same props/variants)?
- No ad-hoc one-off styles that bypass the design system

### 1e. AI slop detection

**Instant FAIL if any of these patterns appear:**

1. Purple/violet/indigo gradient backgrounds
2. 3-column feature grid with icons in colored circles
3. Icons in colored circles as section decoration
4. Centered everything with uniform spacing
5. Uniform bubbly border-radius on every element
6. Decorative blobs, floating circles, wavy SVG dividers
7. Emoji as design elements
8. Colored left-border on cards
9. Generic hero copy ("Welcome to [X]", "Unlock the power of...")
10. Cookie-cutter section rhythm (hero → 3 features → testimonials → pricing → CTA)

---

## 2. /mpm-ui-ux-pro-max guideline alignment

Invoke `/mpm-ui-ux-pro-max` to load professional UX standards. Then judge the implementation against them.

Focus areas (do NOT duplicate what's already in DESIGN.md — only check what the design system doesn't cover):

### 2a. Accessibility (CRITICAL)
Judge against mpm-ui-ux-pro-max Priority 1 rules. Key checks:
- Contrast ratios (4.5:1 normal text, 3:1 large text)
- Focus states visible for keyboard navigation
- ARIA labels on icon-only buttons
- Form inputs have visible labels (not just placeholder)
- Touch targets ≥ 44px
- Screen reader focus order matches visual order

### 2b. Interaction quality
Judge against mpm-ui-ux-pro-max Priority 2 rules. Key checks:
- Every clickable element has feedback (hover, press, loading)
- State coverage: empty, loading, error, success, partial — all exist
- No hover-only interactions (must work on touch)
- Micro-interaction timing (150-300ms with native easing)

### 2c. Responsive behavior
Judge against mpm-ui-ux-pro-max Priority 5 rules. Take mobile + tablet screenshots:
- No horizontal scroll on mobile
- Text readable without zooming (≥ 16px body on mobile)
- Content priority makes sense (most important first)
- Safe areas respected

### 2d. Edge cases
Test with:
- Long text (47-char name, 200-char description)
- Zero results / empty state
- Special characters (`<script>`, `"quotes"`, emoji)
- Rapid clicks (double-click submit)
- Back button behavior

### 2e. Pre-delivery checklist
Run the mpm-ui-ux-pro-max pre-delivery checklist against the implementation. Any failure → FAIL.

---

## 3. Browser-based evidence collection

**Screenshots are mandatory.** No screenshots = automatic FAIL.

Using the browser tool from VERIFICATION.md, capture:

1. **Desktop** (1400×900) — main state
2. **Mobile** (375×812) — responsive check
3. **Key interactions** — hover states, form submissions, error states, empty states

Save all screenshots to `.mpm/data/reviews/{task-id}-*.png`.

If the browser tool supports interaction (click, fill, etc.), do a full walkthrough:
- Click every button, fill every form, trigger every state
- First impression: can you understand what this page does in 3 seconds?
- Is there a clear primary action?

---

## Return format

```
UIUX REVIEW: PASS/FAIL

Design System:
  Token compliance: PASS/FAIL — [count] violations
  DESIGN.md alignment: PASS/FAIL — [mismatches]
  AI slop: PASS/FAIL — [which patterns]
  Visual consistency: PASS/FAIL

UX Standards (mpm-ui-ux-pro-max):
  Accessibility: PASS/FAIL — [issues]
  Interaction: PASS/FAIL — [issues]
  Responsive: PASS/FAIL — [issues]
  Edge cases: PASS/FAIL — [issues]
  Pre-delivery: PASS/FAIL — [checklist failures]

Issues:
- [issue 1: what's wrong + file:line or screenshot + how to fix]
- [issue 2: ...]

Screenshots:
- .mpm/data/reviews/{task-id}-desktop.png
- .mpm/data/reviews/{task-id}-mobile.png
- .mpm/data/reviews/{task-id}-interaction.png
```
