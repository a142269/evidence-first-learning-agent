import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const viewPath = join(__dirname, "../src/views/ResourcesView.vue");
const displayPath = join(__dirname, "../src/utils/resourceDisplay.ts");
const sessionPath = join(__dirname, "../src/composables/useSession.ts");
const resourcesApiPath = join(__dirname, "../src/api/resources.ts");
const insightsApiPath = join(__dirname, "../src/api/insights.ts");

const source = readFileSync(viewPath, "utf8");

assert.doesNotMatch(source, /AgentCrew/, "资源库顶部不应再显示本页智能体分工");
assert.doesNotMatch(source, /线性代数专题资源包/, "顶部专题不应继续使用线性代数演示数据");
assert.match(source, /const learningCards = computed/, "应建立合并后的完整学习资源集合");
assert.match(source, /list = learningCards\.value/, "学习资源筛选应包含课程资源和多模态产物");
assert.match(source, /resourceTypeLabel/, "页面应使用统一资源类型中文映射");
assert.match(source, /localizeResourceText/, "页面应统一修复英文和异常历史文案");
assert.match(source, /人工智能课程资源/, "顶部应展示真实的人工智能课程");
assert.match(source, /resourceTypeLabel\(c\.name\)/, "右侧资源分类应显示中文名称");
assert.match(source, /localizeResourceText\(item\.title \|\| item\.topic/, "AI 推荐标题应中文化");
assert.match(source, /localizeResourceText\(item\.reason/, "AI 推荐原因应中文化");
assert.match(source, /function resourceIconForType/, "应提供统一资源类型图标映射");
assert.match(source, /resourceIconForType\(t\.key\)/, "顶部类型筛选应显示对应图标");
assert.match(source, /resourceIconForType\(card\.artifactType \|\| card\.resourceType \|\| card\.kind\)/, "资源卡片应显示对应图标");
assert.match(source, /resourceIconForType\(c\.name\)/, "右侧资源分类应显示对应图标");
assert.match(source, /resourceIconForType\(previewCard\.artifactType \|\| previewCard\.resourceType\)/, "预览类型标签应显示对应图标");

assert.equal(existsSync(displayPath), true, "应提供集中式资源显示中文化模块");
const displaySource = readFileSync(displayPath, "utf8");

for (const expected of [
  "mermaid_png",
  "思维导图图片",
  "pptx",
  "演示文稿",
  "mp3",
  "音频",
  "tutoring",
  "辅导答疑",
  "tutor_agent",
  "辅导教师",
  "evaluator_agent",
  "学习评估员",
  "resource_generator",
  "资源生成助手",
  "What is gradient descent?",
  "什么是梯度下降？",
  "Use Socratic questions to help",
  "使用苏格拉底式提问进行引导",
  "??",
  "问题待补充",
]) {
  assert.ok(displaySource.includes(expected), `显示中文化模块缺少映射：${expected}`);
}

assert.match(source, /listCourses/, "资源库应从后端加载真实课程列表");
assert.match(source, /class="course-switcher"/, "资源库顶部应提供课程切换器");
assert.match(source, /setCourse/, "课程切换器应更新共享会话课程");
// 当前源码依据：frontend/src/views/ResourcesView.vue:1273/1279 —— refresh() 先把
// course.value 快照进 requestedCourse 再发请求，配合 refreshSequence 丢弃过期响应，
// 所以资源请求携带的是快照变量而不是 course.value 本身。
assert.match(source, /const requestedCourse = course\.value;/, "资源刷新应快照当前课程");
assert.match(source, /course:\s*requestedCourse/, "资源请求应携带当前课程");
assert.match(source, /getRecommendations\(userId\.value,\s*4,\s*course\.value\)/, "AI 推荐请求应携带当前课程");
assert.match(source, /Python 程序设计课程资源/, "Python 课程应显示动态课程标题");
assert.match(source, /watch\(course,[\s\S]*refresh\(\)[\s\S]*loadRecommendations\(\)/, "切换课程后应刷新资源与推荐");
assert.match(source, /artifactCourse[\s\S]*course\.value/, "多模态产物应按当前课程筛选");
// 当前源码依据：frontend/src/views/ResourcesView.vue:615-619（resources 卡片区）与
// 657-663（artifacts 卡片区）—— 现在只有"明确标注了课程"的条目才做课程隔离，
// 未写 course 元数据的历史资源/产物保持可见，否则接口有数据也会被前端筛成空白。
// 原断言要求 return resourceCourse === course.value / return artifactCourse === course.value
// 属旧版"未标注即隐藏"实现，已被上述行为替代。
assert.match(
  source,
  /return !resourceCourse \|\| resourceCourse === course\.value;/,
  "资源卡片区应只在条目带课程标记时做课程隔离，历史无标记资源仍可见",
);
assert.match(
  source,
  /const courseMatches = !artifactCourse \|\| artifactCourse === course\.value;/,
  "产物卡片区应只在条目带课程标记时做课程隔离，历史无标记产物仍可见",
);
assert.match(
  source,
  /return courseMatches && artifact\.exists !== false && artifact\.download_ready !== false;/,
  "失效产物不应进入卡片区，同时保留课程隔离判断",
);

const sessionSource = readFileSync(sessionPath, "utf8");
assert.match(sessionSource, /COURSE_STORAGE_KEY/, "当前课程应持久化到本地存储");
assert.match(sessionSource, /function setCourse/, "会话状态应提供课程更新方法");

const resourcesApiSource = readFileSync(resourcesApiPath, "utf8");
assert.match(resourcesApiSource, /course\?: string/, "资源列表 API 应接受课程参数");

const insightsApiSource = readFileSync(insightsApiPath, "utf8");
assert.match(insightsApiSource, /getRecommendations\(userId: string, limit = 6, course = ""\)/, "推荐 API 应接受课程参数");
assert.match(insightsApiSource, /course,/, "推荐 API 应将课程传给后端");

console.log("resourcesRealDataChinese tests passed");
