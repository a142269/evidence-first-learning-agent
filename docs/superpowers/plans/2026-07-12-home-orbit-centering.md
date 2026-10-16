# Home Orbit Centering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Center the six-role collaboration diagram visually within the right side of the home-page Hero.

**Architecture:** Keep the shared `OrbitDiagram` geometry unchanged and apply a page-scoped 36px horizontal compensation to the diagram inside `HomeView.vue`. Add a small source-level regression test to ensure the offset remains local to the home page, then verify the Vue/TypeScript production build.

**Tech Stack:** Vue 3 single-file components, scoped CSS, Node.js assertions, Vite, vue-tsc

---

### Task 1: Center the Home-Page Orbit Diagram

**Files:**
- Create: `frontend/tests/homeOrbitCentering.test.mjs`
- Modify: `frontend/src/views/HomeView.vue:380-386`

- [ ] **Step 1: Write the failing regression test**

Create `frontend/tests/homeOrbitCentering.test.mjs`:

```js
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const homeSource = readFileSync(new URL("../src/views/HomeView.vue", import.meta.url), "utf8");
const orbitSource = readFileSync(new URL("../src/components/base/OrbitDiagram.vue", import.meta.url), "utf8");

assert.match(
  homeSource,
  /\.orbit-shell\s+:deep\(\.agent-map\)\s*\{[^}]*transform:\s*translateX\(36px\)\s+scale\(0\.53\);/s,
);
assert.doesNotMatch(orbitSource, /translateX\(36px\)/);

console.log("Home orbit diagram has a page-scoped 36px centering compensation.");
```

- [ ] **Step 2: Run the regression test and verify it fails**

Run: `node tests/homeOrbitCentering.test.mjs`

Expected: FAIL with an assertion showing that `HomeView.vue` does not yet contain `translateX(36px) scale(0.53)`.

- [ ] **Step 3: Apply the minimal page-scoped style change**

In `frontend/src/views/HomeView.vue`, update the existing `.orbit-shell :deep(.agent-map)` rule:

```css
.orbit-shell :deep(.agent-map) {
  width: 900px;
  height: 570px;
  margin: 0;
  transform: translateX(36px) scale(0.53);
  transform-origin: top left;
}
```

- [ ] **Step 4: Run the regression test and verify it passes**

Run: `node tests/homeOrbitCentering.test.mjs`

Expected: PASS and output `Home orbit diagram has a page-scoped 36px centering compensation.`

- [ ] **Step 5: Build the frontend**

Run: `npm run build`

Expected: `vue-tsc --noEmit` and `vite build` finish successfully with exit code 0.

- [ ] **Step 6: Visually verify the home page**

Open the local home page at the desktop viewport used in the supplied screenshot. Confirm that the diagram's visual center aligns with the center of the right Hero panel, its scale and vertical position remain unchanged, and no labels or avatars are clipped.

- [ ] **Step 7: Review the focused diff**

Run: `git diff --check -- frontend/src/views/HomeView.vue frontend/tests/homeOrbitCentering.test.mjs`

Expected: exit code 0 with no whitespace errors. Confirm the diff contains only the new regression test and the one transform declaration change; do not include unrelated existing `HomeView.vue` edits in a commit.
