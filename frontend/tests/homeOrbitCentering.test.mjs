import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const homeSource = readFileSync(new URL("../src/views/HomeView.vue", import.meta.url), "utf8");
const loginSource = readFileSync(new URL("../src/views/LoginView.vue", import.meta.url), "utf8");
const orbitSource = readFileSync(new URL("../src/components/base/OrbitDiagram.vue", import.meta.url), "utf8");

// 当前源码依据：轨道图现由登录页挂载（frontend/src/views/LoginView.vue:8、355），
// HomeView 不再内嵌轨道图，也就没有 .orbit-shell :deep(.agent-map) 页面级缩放块
//（原断言的 scale(0.53) 只存在于旧首页设计，本工作树全仓无 scale(0. 匹配）。
// 保留的不变量是：轨道图自身不带页面级平移补偿。
assert.doesNotMatch(homeSource, /OrbitDiagram/, "首页不再承载轨道图组件");
assert.match(loginSource, /import OrbitDiagram from "@\/components\/base\/OrbitDiagram\.vue";/, "轨道图应由登录页挂载");
assert.doesNotMatch(orbitSource, /translateX\(36px\)/, "轨道图不应带页面级平移补偿");

console.log("orbit diagram lives on the login page without page-level pan compensation.");
