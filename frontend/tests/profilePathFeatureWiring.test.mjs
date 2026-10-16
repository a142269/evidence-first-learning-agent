import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const profileSource = readFileSync(join(__dirname, "../src/views/ProfileView.vue"), "utf8");
const pathSource = readFileSync(join(__dirname, "../src/views/PathView.vue"), "utf8");

// ===== ProfileView 原有断言（保持兼容） =====
assert.match(
  profileSource,
  /const archiveOpen = ref\(false\)/,
  "ProfileView should open the learning archive in-page instead of linking to a missing route",
);
assert.doesNotMatch(
  profileSource,
  /to="\/profile\/archive"/,
  "ProfileView should not link to missing /profile/archive route",
);
assert.match(
  profileSource,
  /@click="handleImproveProfile"/,
  "ProfileView improve profile button should not reset the profile",
);
assert.match(
  profileSource,
  /@click="diagnosisOpen = true"/,
  "ProfileView AI diagnosis tool should open an in-page diagnosis panel",
);

// ===== PathView 原有断言（保持兼容） =====
assert.match(
  pathSource,
  /@keydown\.enter\.prevent="handleTopSearch"/,
  "PathView search input should submit on Enter",
);
assert.match(
  pathSource,
  /class="roadmap-detail-panel"/,
  "PathView roadmap card clicks should reveal stage details in a full-width panel",
);
assert.match(
  pathSource,
  /v-for="item in selectedStageContent"/,
  "PathView should render per-topic stage details",
);
assert.match(
  pathSource,
  /@click\.stop="goToResources\(item\.name\)"/,
  "PathView topic rows should link to resources",
);
assert.match(
  pathSource,
  /@click\.stop="goToChat\(item\.name\)"/,
  "PathView topic rows should link to AI chat",
);
assert.match(
  pathSource,
  /v-for="q in visibleNbqItems"/,
  "PathView should render active-learning next-best questions",
);
assert.match(
  pathSource,
  /v-for="r in visibleRecoItems"/,
  "PathView should render recommendation API items",
);
assert.match(
  pathSource,
  /v-for="s in visibleStrategyAdjustments"/,
  "PathView should render adaptive strategy adjustments",
);
assert.match(
  pathSource,
  /<AvatarStack/,
  "PathView should show partner learning activity",
);
assert.match(
  pathSource,
  /@click="openTaskDetail\(t\)"/,
  "PathView task action buttons should open an actionable in-page task detail",
);

// ===== 今日任务必须来自当前学生的真实路径数据 =====
assert.match(
  pathSource,
  /overview\.value\?\.path\.today_tasks/,
  "PathView today tasks should come from the current learner overview",
);
assert.match(
  pathSource,
  /type:\s*"task_completed"/,
  "PathView should persist task completion instead of using fixed demo tasks",
);

// 确认自动计算总时长
assert.match(
  pathSource,
  /todayTotalMinutes/,
  "PathView should auto-calculate today total minutes",
);
assert.match(
  pathSource,
  /todayTotalText/,
  "PathView should have a computed total duration text",
);
assert.match(
  pathSource,
  /预计总时长/,
  "PathView should display the total estimated duration in the UI",
);

// 确认"开始学习"按钮滚动到当前阶段
assert.match(
  pathSource,
  /scrollToCurrentStage/,
  "PathView should have a scrollToCurrentStage function for the '开始学习' button",
);
assert.match(
  pathSource,
  /@click="scrollToCurrentStage"/,
  "PathView '开始学习' button should call scrollToCurrentStage",
);

// ===== 新增：PathView 推荐资源展示上限为 5 =====
assert.match(
  pathSource,
  /recoItems\.value\.slice\(0,\s*5\)/,
  "PathView visibleRecoItems should slice recommendation API results to 5 items",
);
assert.doesNotMatch(
  pathSource,
  /模型评估与调优指南/,
  "PathView should not fill personalized recommendations with fixed demo resources",
);

// ===== 用户要求：PathView 路径概览头部不显示预计剩余时间 =====
assert.doesNotMatch(
  pathSource,
  /estimatedRemainingTime/,
  "PathView should not compute estimatedRemainingTime after removing that banner metric",
);
assert.doesNotMatch(
  pathSource,
  /预计剩余时间/,
  "PathView banner should not display estimated remaining time",
);

// ===== ProfileView 独立 AI 工具与八维工作台 =====
assert.match(profileSource, /class="pd-ai-tool pd-ai-tool-diagnosis"/, "ProfileView should expose AI diagnosis as an independent tool");
assert.match(profileSource, /class="pd-ai-tool pd-ai-tool-timemachine"/, "ProfileView should expose the profile time machine as an independent tool");
assert.match(profileSource, /class="pd-ai-tool pd-ai-tool-prediction"/, "ProfileView should expose profile prediction as an independent tool");
assert.match(profileSource, /class="pd-dimension-workbench"/, "ProfileView should integrate the eight-dimension radar and overview workbench");

// 确认维度树点击联动集成证据区
assert.match(
  profileSource,
  /toggleDimAndSelect/,
  "ProfileView should have a toggleDimAndSelect function for dimension tree clicks",
);
assert.match(
  profileSource,
  /@click="toggleDimAndSelect\(node\.key\)"/,
  "ProfileView mini tree node click should call toggleDimAndSelect",
);

// ===== 新增：证据溯源 Tab 内容 =====
assert.match(
  profileSource,
  /pd-evidence-layout/,
  "ProfileView evidence tab should have an evidence layout",
);
assert.match(
  profileSource,
  /pd-evidence-field/,
  "ProfileView evidence tab should show the current field info",
);
assert.match(
  profileSource,
  /pd-evidence-sources/,
  "ProfileView evidence tab should show evidence sources list",
);
assert.match(
  profileSource,
  /pd-source-card/,
  "ProfileView evidence tab should render source cards",
);
assert.match(
  profileSource,
  /pd-conf-bar/,
  "ProfileView evidence tab should show a confidence progress bar",
);

console.log("✅ profilePathFeatureWiring.test.mjs — all assertions passed");
