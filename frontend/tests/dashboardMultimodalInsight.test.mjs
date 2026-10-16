import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/DashboardView.vue"), "utf8");

assert.match(source, /薄弱知识点 · 多模态修复推送/, "薄弱知识点卡应明确展示多模态修复定位");
assert.match(source, /多模态修复序列/, "薄弱知识点卡应展示资源使用顺序");
assert.match(source, /currentRecommendationModes/, "薄弱知识点卡应从后端推荐的资源类型构建多模态组合");
assert.match(source, /查看此知识点的多模态资源/, "薄弱知识点卡应提供可执行的资源入口");
assert.match(source, /视觉化错因回放/, "错题洞察应呈现可视化错因回放");
assert.match(source, /多模态修复包/, "错题洞察应呈现多模态修复资源");
assert.match(source, /变式验证与回写/, "错题洞察应连接变式练习与画像回写");
assert.match(source, /图解定位错因/, "错题洞察应明确闭环的第一步");
assert.match(source, /代码\/交互演练/, "错题洞察应明确代码或交互演练环节");

console.log("dashboardMultimodalInsight.test.mjs - all assertions passed");
