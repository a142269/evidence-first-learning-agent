# Learning Toolbox Layout Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the learning toolbox visually consistent with the other student pages through warm colors, disciplined spacing, aligned cards, and reliable responsive behavior.

**Architecture:** Keep all feature logic and markup intact. Consolidate the page-local CSS in `EvidenceView.vue` into one coherent token layer, remove the late `!important` override block, and protect the intended layout with a source-level regression test.

**Tech Stack:** Vue 3 SFC, scoped CSS, Node.js assertion tests, Vite, TypeScript

---

### Task 1: Lock the visual contract

**Files:**
- Create: `frontend/tests/evidenceLayoutPolish.test.mjs`

- [ ] Add assertions for warm paper background, controlled max width, 20px grid gutters, 24px opaque cards, mobile single-column behavior, and absence of the conflicting `!important` override layer.
- [ ] Run `node frontend/tests/evidenceLayoutPolish.test.mjs` and confirm it fails because the current page still uses the cool background and late override block.

### Task 2: Consolidate toolbox colors and layout

**Files:**
- Modify: `frontend/src/views/EvidenceView.vue`

- [ ] Reuse global warm paper and orange tokens in the page-local design variables.
- [ ] Normalize page width, hero spacing, section rhythm, card padding, borders, and surface colors.
- [ ] Remove the duplicate glassmorphism override block and keep interaction feedback free of layout-shifting scale effects.
- [ ] Preserve the 12-column desktop grid and one-column mobile collapse.

### Task 3: Verify the result

**Files:**
- Test: `frontend/tests/evidenceLayoutPolish.test.mjs`

- [ ] Run the new regression test and the existing frontend source tests.
- [ ] Run `npm run build` from `frontend` and confirm type checking and production bundling succeed.
- [ ] Inspect the page at desktop and mobile widths for overflow, uneven card alignment, and inconsistent spacing.
