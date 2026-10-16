import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(join(__dirname, "../src/views/DashboardView.vue"), "utf8");
const model = readFileSync(join(__dirname, "../src/views/dashboard/dashboardChartModel.ts"), "utf8");
const timeline = source.slice(source.indexOf("学习行为时间线"), source.indexOf("db-main-grid"));
const errorChart = source.slice(source.indexOf("function renderErrorPie"), source.indexOf("function renderAssessTrend"));
const forecastChart = source.slice(source.indexOf("function renderForecast"), source.indexOf("function renderErrorPie"));
const matrixChart = source.slice(source.indexOf("function renderMistakeMatrix"), source.indexOf("watch([masteryView"));

assert.match(model, /export function localizeDashboardLabel/, "大屏应提供统一的中文标签映射");
for (const [key, label] of [
  ["concept_confusion", "概念混淆"],
  ["careless", "粗心失误"],
  ["conceptual_misunderstanding", "概念理解偏差"],
  ["calculation_error", "计算错误"],
  ["application_transfer", "迁移应用困难"],
  ["careless_error", "审题疏忽"],
  ["memory_gap", "知识记忆缺口"],
  ["incomplete_answer", "作答不完整"],
  ["improving", "上升"],
  ["document", "文档"],
]) {
  assert.match(model, new RegExp(`${key}:\\s*"${label}"`), `应把 ${key} 映射为 ${label}`);
}

assert.match(source, /localizeDashboardLabel\(item\.name\)/, "错因图表应显示中文标签");
assert.match(source, /localizeDashboardLabel\(evt\.error_type\)/, "错题时间线应显示中文错因");
assert.match(model, /export function localizeKnowledgePointLabel/, "BKT 左轴应提供知识点中文名映射");
assert.match(model, /AI_001:\s*"人工智能概述"/, "AI_001 应显示中文知识点名称");
assert.match(model, /CODE_002:\s*"深度学习框架（PyTorch）"/, "CODE_002 应显示中文知识点名称");
assert.match(model, /"ml_fundamentals\/gradient_descent":\s*"批量梯度下降与随机梯度下降"/, "层级知识点 ID 应显示中文名称");
assert.match(model, /"cnn\/batch_norm":\s*"批归一化（BatchNorm）"/, "CNN 层级知识点应显示中文名称");
assert.match(source, /label:\s*localizeKnowledgePointLabel\(name/, "BKT 左轴应使用中文知识点名称");
assert.match(source, /seriesName === "掌握度"/, "BKT 悬浮框应读取掌握度系列而不是背景轨道");
assert.match(source, /matrix\.knowledgePoints\.map\(\(kpId\) => localizeKnowledgePointLabel\(kpId\)\)/, "错因矩阵纵轴应显示中文知识点名称");
assert.match(source, /localizeKnowledgePointLabel\(wp\.kp_id\)/, "AI 洞察薄弱点应显示中文名称");
assert.match(model, /export function localizeLearningMaterialTitle/, "AI 推荐资料应提供英文标题中文兜底");
assert.match(source, /localizeLearningMaterialTitle\(m\.title\)/, "AI 洞察应显示中文资料标题");
assert.match(model, /doc:\s*"文档"/, "DOC 资料类型应显示为文档");
assert.match(source, /\.db-area-insights\s*>\s*\.db-panel\s*\{[^}]*height:\s*100%/s, "AI 洞察面板应填满网格行以对齐精准推送底边");
assert.match(timeline, /evt\.question/, "错题时间线应展示后端返回的题目摘要");
assert.match(timeline, /evt\.resolved\s*\?\s*'已解决'\s*:\s*'待复习'/, "错题时间线应显示解决状态");
assert.doesNotMatch(source, /`D\$\{p\.day\}`/, "预测横轴不应显示普通英文 Day 缩写");

assert.match(model, /forecast:\s*"#4F46E5"/, "预测图应使用独立蓝紫色");
assert.match(model, /errors:\s*\["#FDBA74",\s*"#FB923C",\s*"#F97316",\s*"#EF4444",\s*"#B91C1C"\]/, "错因图应使用珊瑚橙到深红色阶");
assert.match(model, /score:\s*\[/, "成绩图应使用独立靛紫色阶");
assert.match(model, /rhythm:\s*\[/, "星期节奏应使用独立蓝绿色阶");
assert.match(model, /matrix:\s*\[/, "错因矩阵应使用独立顺序蓝色阶");
assert.match(errorChart, /type:\s*"scatter"/, "错因分布应改为气泡散点图");
assert.match(errorChart, /symbolSize:\s*\([^)]*\)\s*=>/, "气泡大小应由错题数量驱动");
assert.doesNotMatch(errorChart, /type:\s*"bar"/, "错因分布不应继续使用重复的横向柱状图");
assert.match(model, /export function buildOrganicBubbleLayout/, "气泡图应提供稳定的自然错位布局");
assert.match(errorChart, /buildOrganicBubbleLayout\(visible\)/, "错因气泡不应继续使用规则网格坐标");
assert.doesNotMatch(errorChart, /index\s*%\s*columns/, "气泡横坐标不应按固定列整齐排列");
assert.match(forecastChart, /DASHBOARD_CHART_COLORS\.forecastBand/, "预测置信区域应使用独立淡紫蓝色");
assert.match(matrixChart, /DASHBOARD_CHART_COLORS\.matrix/, "错因矩阵应读取独立蓝色阶");

assert.match(model, /export function buildRisingForecastCurve/, "forecast model should expose a monotonic display curve");
assert.match(forecastChart, /const displayForecast = buildRisingForecastCurve\(fc\)/, "forecast chart should use the rising display curve");
assert.match(forecastChart, /data:\s*displayForecast/, "forecast line should read the rising display data");
assert.match(forecastChart, /min:\s*forecastAxis\.min/, "forecast axis should zoom to the meaningful mastery range");

console.log("dashboardChineseTimeline.test.mjs - all assertions passed");
