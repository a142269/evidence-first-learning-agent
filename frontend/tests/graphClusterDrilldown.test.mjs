import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/GraphView.vue"), "utf8");

assert.match(
  source,
  /function openCluster\(cluster: GraphCluster\)[\s\S]*?nodeFilter\.value = "all";[\s\S]*?chapterFocus\.value = null;[\s\S]*?viewMode\.value = "explore";/,
  "opening a cluster should clear course-level filters that can hide cluster members",
);

assert.match(
  source,
  /const visibleNodesList = computed\(\(\) => \{[\s\S]*?if \(activeCluster\.value\) return sourceNodes;/,
  "cluster drilldown should render every filtered cluster member instead of tree-root reachability only",
);

console.log("graphClusterDrilldown.test.mjs - all assertions passed");
