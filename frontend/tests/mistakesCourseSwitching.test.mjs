import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const apiSource = readFileSync(join(__dirname, "../src/api/mistakes.ts"), "utf8");
const viewSource = readFileSync(join(__dirname, "../src/views/MistakesView.vue"), "utf8");

assert.match(apiSource, /course\?: string;/, "错题记录应携带可选课程归属");
assert.match(apiSource, /getMistakesHeatmap\(userId: string, course = ""\)/, "热力图 API 应支持课程参数");
assert.match(apiSource, /listMistakes\(userId: string, category = "", limit = 50, course = ""\)/, "错题列表 API 应支持课程参数");
assert.match(apiSource, /getMistakeInsights\(userId: string, course = ""\)/, "AI 诊断 API 应支持课程参数");

for (const course of ["全部课程", "人工智能", "Python"]) {
  assert.ok(viewSource.includes(course), `课程切换器缺少选项：${course}`);
}
assert.match(viewSource, /class="mk-course-switcher"/, "错题本标题区应提供课程切换器");
assert.match(viewSource, /const activeCourse = ref/, "错题本应维护页面级课程范围");
assert.match(viewSource, /router\.replace\([\s\S]*course/, "切换课程后应同步 URL 查询参数");
assert.match(viewSource, /listMistakes\(uid, "", 100, activeCourse\.value\)/, "错题列表应按课程请求");
assert.match(viewSource, /getMistakesHeatmap\(uid, activeCourse\.value\)/, "热力图应按课程请求");
assert.match(viewSource, /getMistakeInsights\(userId\.value, activeCourse\.value\)/, "AI 诊断应按课程请求");
assert.match(viewSource, /watch\(activeCourse/, "课程变化后应重新加载错题数据");
assert.match(
  viewSource,
  /watch\(activeCourse[\s\S]*mistakes\.value = \[\]/,
  "切换课程时应立即清空上一课程错题，避免旧数据残留",
);
assert.match(
  viewSource,
  /results\[0\]\.status === "fulfilled"[\s\S]*else \{[\s\S]*mistakes\.value = \[\]/,
  "新课程列表请求失败时也应清空上一课程错题",
);
assert.match(viewSource, /courseLabel\(m\.course\)/, "错题卡片应显示课程标签");
assert.match(
  viewSource,
  /item\.id === itemId \|\| item\.kp_id === itemId/,
  "最近复习记录应同时支持按错题 ID 和知识点 ID 匹配真实题目",
);
assert.match(
  viewSource,
  /const mistake = findReviewMistake\(entry\.item_id\)/,
  "最近复习记录应使用匹配到的真实错题名称",
);

console.log("mistakes course switching tests passed");
