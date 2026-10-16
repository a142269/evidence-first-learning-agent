import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const pathSource = readFileSync(join(__dirname, "../src/views/PathView.vue"), "utf8");

assert.match(
  pathSource,
  /grid-template-columns:\s*minmax\(0,\s*1fr\)\s+clamp\(300px,\s*22vw,\s*360px\)/,
  "PathView should use a stable two-column grid so left and right cards align at the top",
);
assert.match(
  pathSource,
  /grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(170px,\s*1fr\)\)/,
  "Roadmap stages should expand across the available width instead of leaving blank space",
);
const activeCardRule = pathSource.match(/\.roadmap-stage\.active \.roadmap-card \{[\s\S]*?\n\}/)?.[0] ?? "";
assert.doesNotMatch(
  activeCardRule,
  /transform:\s*scale/,
  "Active roadmap cards should not scale because it breaks alignment and creates uneven spacing",
);
assert.match(
  pathSource,
  /class="roadmap-detail-panel"/,
  "Expanded stage details should live in a full-width panel instead of stretching one stage card",
);
assert.match(
  pathSource,
  /v-for="item in selectedStageContent"/,
  "Expanded stage details should render backend-resolved learning items in the full-width panel",
);
assert.match(
  pathSource,
  /\.roadmap-card-title[\s\S]*?line-height:\s*1\.35[\s\S]*?min-height:\s*38px/,
  "Roadmap card titles should have stable height for long labels like 综合实战",
);
assert.doesNotMatch(
  pathSource,
  /class="side-card ai-suggestion-card"/,
  "PathView right-side AI advice card should not reuse the global ai-suggestion-card class because it creates a nested two-layer layout",
);
assert.match(
  pathSource,
  /class="side-card ai-advice-card"/,
  "PathView right-side AI advice card should use a page-local class name",
);
assert.doesNotMatch(
  pathSource,
  /预计剩余时间|estimatedRemainingTime|基于剩余阶段估算/,
  "PathView learner banner should not show the estimated remaining time block",
);

assert.match(pathSource, /weeklyGoalHoursText/, "Weekly study card should show the learner's weekly goal");
assert.match(pathSource, /weeklyGoalProgress/, "Weekly study card should visualize goal completion");
assert.match(pathSource, /weeklyRemainingHoursText/, "Weekly study card should show remaining hours");
assert.match(pathSource, /class="banner-weekly-goal"/, "Weekly study card should include a compact progress section");
