import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const homeSource = readFileSync(new URL("../src/views/HomeView.vue", import.meta.url), "utf8");
const orbitSource = readFileSync(new URL("../src/components/base/OrbitDiagram.vue", import.meta.url), "utf8");

// 首页恢复为 Doeee-doja 原始版本：orbit 使用纯 scale 缩放，无页面级平移补偿
assert.match(
  homeSource,
  /\.orbit-shell\s+:deep\(\.agent-map\)\s*\{[^}]*transform:\s*scale\(0\.53\);/s,
);
assert.doesNotMatch(orbitSource, /translateX\(36px\)/);

console.log("Home orbit diagram keeps the original page-scoped scale styling.");
