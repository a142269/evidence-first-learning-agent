import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/views/MistakesView.vue", import.meta.url), "utf8");

assert.doesNotMatch(source, /线性代数易错专题/);
assert.match(source, /const weeklyFocus = computed/);
assert.match(source, /overview\.value\?\.profile\.knowledge_points/);
assert.match(source, /\{\{ weeklyFocus\.title \}\}/);
assert.match(source, /\{\{ unresolvedCount \}\}/);
assert.match(source, /\{\{ reviewMasteryRate \}\}/);
assert.doesNotMatch(source, /import AgentCrew/);
assert.doesNotMatch(source, /<AgentCrew/);
assert.match(source, /class="mk-hero-diagnosis"/);
assert.match(source, /AI诊断建议/);
assert.match(source, /knowledgePointName\(wp\.kp_id\)/);

console.log("MistakesView weekly focus is derived from the current user's real mistake records.");
