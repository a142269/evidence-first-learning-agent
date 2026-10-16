import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/PathView.vue"), "utf8");
const insightsApi = readFileSync(join(__dirname, "../src/api/insights.ts"), "utf8");
const assessmentApi = readFileSync(join(__dirname, "../src/api/assessment.ts"), "utf8");
const pathApi = readFileSync(join(__dirname, "../src/api/learning_path.ts"), "utf8");

assert.match(source, /item\.label\s*\?\?/, "strategy cards should prefer the Chinese label");
assert.match(source, /q\.question\?\.stem/, "recommended questions should prefer the Chinese stem");
assert.match(source, /q\.kp_name/, "recommended questions should use the Chinese knowledge-point name");
assert.match(source, /ACTION_LABELS/, "internal strategy actions should use a centralized Chinese map");
assert.match(source, /BLOOM_LABELS/, "Bloom values should use a centralized Chinese map");
assert.match(source, /SIGNAL_VALUE_LABELS/, "adaptive signal values should be shown in Chinese");
assert.match(source, /RESOURCE_TYPE_LABELS/, "recommended resource types should be shown in Chinese");
assert.match(source, /addAssessmentRecord/, "answers and tasks should persist assessment events");
assert.match(source, /refreshLearningLoop/, "learning events should refresh the complete learning loop");
assert.match(source, /item\.value === false/, "partial refresh failures should be surfaced to the learner");
assert.match(source, /goalEditorOpen/, "the path page should expose a lightweight goal editor");
assert.match(source, /学习调整建议/, "the adjustment panel should use student-facing Chinese wording");
assert.match(source, /strategy\?\.strategy\.replan_recommended/, "replanning should require a recommendation");
assert.match(source, /applyAdaptiveStrategy\(userId\.value, false, course\.value\)/, "confirmed replanning must not force an adjustment and must preserve course scope");
assert.doesNotMatch(source, /String\(item\.title \?\? item\.action/, "internal action codes must not be rendered directly");

assert.match(insightsApi, /export interface PathGenerationConstraints/, "path constraints should be typed");
assert.match(insightsApi, /constraints\?: PathGenerationConstraints/, "path responses should expose applied constraints");
assert.match(
  insightsApi,
  /getAdaptiveStrategy\(userId: string, course = "artificial_intelligence"\)/,
  "adaptive strategy requests should default to the active AI course",
);
assert.match(
  insightsApi,
  /applyAdaptiveStrategy\([\s\S]*course = "artificial_intelligence"[\s\S]*\{[\s\S]*force,[\s\S]*course,/,
  "applying an adaptive strategy should preserve the course scope",
);
assert.match(
  source,
  /getPersonalizationChain\(userId\.value, course\.value\)/,
  "the path personalization chain should use the selected course",
);
assert.match(assessmentApi, /external_id\?: string/, "assessment events should support idempotency keys");

assert.match(pathApi, /getStageContent/, "learning path API should expose real stage content loading");
assert.match(pathApi, /stages\/\$\{encodeURIComponent\(stageId\)\}\/content/, "stage content should come from the backend endpoint");
assert.match(source, /normalizeStage/, "all persisted path stages should normalize kp_ids into displayable content fields");
assert.match(source, /loadStageContent/, "clicking a roadmap stage should load its real learning content");
assert.match(source, /v-for="item in selectedStageContent"/, "expanded roadmap stage should render backend learning items");
assert.match(source, /stageContentLoading/, "stage content should expose a loading state");
assert.match(source, /stageContentError/, "stage content should expose an error state");
assert.match(
  source,
  /class="path-task-card"[\s\S]*class="path-roadmap-card"/,
  "today tasks should appear above the roadmap",
);
assert.doesNotMatch(source, /class="path-agent-card"/, "the multi-agent collaboration card should be removed");
assert.doesNotMatch(source, /多智能体协同工作机制/, "the removed multi-agent panel title should not remain");

console.log("✅ pathLearningLoop.test.mjs — all assertions passed");
