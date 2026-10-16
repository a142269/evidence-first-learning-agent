<script setup lang="ts">
/**
 * PathView · 个性化学习路径
 *
 * 保留文档中描述的全部功能（路径概览/阶段化学习/今日任务/智能推荐/下一道题/自适应策略/AI一键规划），
 * 排版与样式参照设计稿：顶部学生横幅 + 横向路线图 + 近期任务 + 右侧 AI 助手。
 * 配色沿用项目原有色板：主色 --orange-500、状态绿 --status-running、中性灰 --neutral-*。
 */
import { computed, defineComponent, h, onMounted, ref } from "vue";
import {
  Check,
  Circle,
  Gauge,
  Info,
  Loader2,
  Lock,
  RefreshCcw,
  Sparkles,
  Wand2,
  Bot,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Clock,
  Target,
  GitBranch,
  Gift,
  FileText,
  ArrowRight,
  Play,
  Compass,
  FileCheck2,
  BookOpenCheck,
  MessageCircle,
  Search,
  Bell,
  Video,
  Code2,
  HelpCircle,
  TrendingUp,
  MoreHorizontal,
  Lightbulb,
  Layers,
  ClipboardList,
} from "lucide-vue-next";
import { useRouter } from "vue-router";

import { getLearnerPartner, partners } from "@/constants/companion";
import Avatar from "@/components/companion/Avatar.vue";
import AvatarStack from "@/components/companion/AvatarStack.vue";
import ArtCard from "@/components/companion/ArtCard.vue";
import ProgressRing from "@/components/companion/ProgressRing.vue";
import TodayReview from "@/components/shared/TodayReview.vue";
import { getAuthSession } from "@/utils/auth";
import { useSession } from "@/composables/useSession";
import {
  getStageContent,
  listPaths,
  updateProgress,
  type LearningPath,
  type LearningStage,
  type StageLearningItem,
} from "@/api/learning_path";
import { addAssessmentRecord, getAssessment, type AssessmentSummary } from "@/api/assessment";
import { nextBestQuestion } from "@/api/cognitive";
import {
  applyAdaptiveStrategy,
  generatePersonalPath,
  getAdaptiveStrategy,
  getStudentOverview,
  getPersonalizationChain,
  getRecommendations,
  type AdaptiveStrategyResponse,
  type PathGenerationConstraints,
  type PersonalizationChainResponse,
  type PersonalizationTag,
  type RecommendationItem,
  type StudentOverviewResponse,
} from "@/api/insights";
import { getResource } from "@/api/resources";
import { updateBkt } from "@/api/cognitive";
import { renderMarkdown } from "@/utils/markdown";

/** 轻量内嵌组件：自定义 SectionTitle（视觉对齐设计稿） */
const SectionTitleCompat = defineComponent({
  name: "SectionTitleCompat",
  props: { title: { type: String, required: true }, sub: { type: String, default: "" } },
  setup(props, { slots }) {
    return () => h("div", { class: "section-head" }, [
      h("div", { class: "section-copy" }, [
        h("h2", null, props.title),
        props.sub ? h("p", null, props.sub) : null,
      ]),
      slots.action ? h("div", { class: "section-action" }, slots.action()) : null,
    ]);
  },
});

const { userId, course } = useSession();
const router = useRouter();
const displayName = computed(() => {
  const name = getAuthSession()?.displayName || "杜同学";
  return ["演示学习者", "张三", "小明"].includes(name) ? "杜同学" : name;
});
const learnerPartner = computed(() => getLearnerPartner(userId.value, displayName.value));

const loading = ref(true);
const saving = ref(false);
const path = ref<LearningPath | null>(null);
const assessment = ref<AssessmentSummary | null>(null);
const overview = ref<StudentOverviewResponse | null>(null);
const error = ref("");

function normalizeStage(stage: any, index: number): LearningStage {
  const learningItems = Array.isArray(stage.learning_items) ? stage.learning_items : [];
  const kpIds = Array.isArray(stage.kp_ids)
    ? stage.kp_ids.map(String)
    : Array.isArray(stage.kps)
      ? stage.kps.map(String)
    : learningItems
      .map((item: any) => String(item.kp_id ?? item.id ?? ""))
      .filter(Boolean);

  return {
    ...stage,
    id: stage.id ?? index,
    title: String(stage.title ?? stage.name ?? `阶段 ${index + 1}`),
    topics: Array.isArray(stage.topics) && stage.topics.length
      ? stage.topics.map(String)
      : kpIds,
    kp_ids: kpIds,
    duration: String(stage.duration ?? (stage.duration_minutes ? `${stage.duration_minutes} 分钟` : "")),
    resources: Array.isArray(stage.resources) ? stage.resources : [],
    prerequisites: Array.isArray(stage.prerequisites) ? stage.prerequisites : [],
    assessment: String(stage.assessment ?? ""),
  };
}

const stages = computed<LearningStage[]>(() => {
  const source = path.value?.stages?.length
    ? path.value.stages
    : overview.value?.path.stages ?? [];
  return source.map(normalizeStage);
});
const selectedPathMatchesOverview = computed(() => (
  Boolean(path.value?.id && overview.value?.path.id && path.value.id === overview.value.path.id)
));
const currentStage = computed(() => path.value?.current_stage ?? overview.value?.path.current_stage ?? 0);
const overallProgress = computed(() => {
  const raw = path.value?.progress ?? overview.value?.path.progress_pct ?? 0;
  // 后端可能返回 0-1 的小数或 0-100 的整数，统一到 0-100
  const pct = raw > 1 ? raw : raw * 100;
  return Math.min(100, Math.round(pct));
});

const stageMastery = computed(() => stages.value.map((stage, idx) => {
  const overviewStage = selectedPathMatchesOverview.value ? overview.value?.path.stage_mastery[idx] : null;
  if (overviewStage) return Math.max(0, Math.min(1, overviewStage.mastery_pct / 100));
  const raw = Number((stage as any).mastery_pct ?? 0);
  return Math.max(0, Math.min(1, raw > 1 ? raw / 100 : raw));
}));
const weeklyHoursText = computed(() => ((overview.value?.activity.this_week_minutes ?? 0) / 60).toFixed(1));
const weeklyDeltaText = computed(() => `${(overview.value?.activity.week_over_week_pct ?? 0) >= 0 ? "+" : ""}${overview.value?.activity.week_over_week_pct ?? 0}%`);
const masteryPct = computed(() => Math.round(overview.value?.summary.average_mastery_pct ?? 0));
const pathUpdatedText = computed(() => overview.value?.path.updated_date || "暂无更新时间");
const isTeacherRecommendedPath = computed(() => (
  path.value?.recommended_role === "teacher"
  || path.value?.metadata?.recommended_role === "teacher"
));
const similarPeerCount = computed(() => overview.value?.collaboration.similar_stage_peer_count ?? 0);
const partnerLearners = computed(() => partners.slice(0, Math.min(4, similarPeerCount.value)));
function stageTags(stage: LearningStage): string[] {
  return ((stage as any).resource_types
    ?? (stage.resources ?? []).map((item: any) => item.type || item.title).filter(Boolean)) as string[];
}

function stageStatus(index: number): "done" | "active" | "locked" {
  if (index < currentStage.value) return "done";
  if (index === currentStage.value) return "active";
  return "locked";
}

function stageStatusText(index: number): string {
  const s = stageStatus(index);
  return s === "done" ? "已完成" : s === "active" ? "进行中" : "待学习";
}

// ----- AI 助手侧栏数据 -----
const nbqItems = ref<Array<Record<string, any>>>([]);
const recoItems = ref<RecommendationItem[]>([]);
const strategy = ref<AdaptiveStrategyResponse | null>(null);

const ACTION_LABELS: Record<string, string> = {
  daily_intensity: "调整每日练习强度",
  resource_weights: "优化资源推荐顺序",
  replan_path: "建议重新规划学习路径",
};
const BLOOM_LABELS: Record<string, string> = {
  remember: "记忆级",
  understand: "理解级",
  apply: "应用级",
  analyze: "分析级",
  evaluate: "评价级",
  create: "创造级",
};
const DIFFICULTY_LABELS: Record<string, string> = {
  easy: "基础难度",
  medium: "中等难度",
  hard: "挑战难度",
  adaptive: "自适应难度",
};
const SIGNAL_VALUE_LABELS: Record<string, string> = {
  improving: "持续提升",
  declining: "近期下滑",
  stable: "保持稳定",
  insufficient_data: "数据积累中",
};
const RESOURCE_TYPE_LABELS: Record<string, string> = {
  document: "讲解文档", doc: "讲解文档", markdown: "讲解文档", pdf: "讲解文档",
  video: "教学视频", animation: "教学动画",
  quiz: "练习题", question: "练习题", generate: "个性化生成",
  mindmap: "思维导图", code: "实操案例", notebook: "实操案例",
};

function actionLabel(item: Record<string, any>, fallback = "学习建议") {
  return String(item.label ?? item.title ?? item.message ?? ACTION_LABELS[String(item.action)] ?? fallback);
}

function bloomLabel(value: unknown) {
  const key = String(value ?? "").toLowerCase();
  return BLOOM_LABELS[key] ?? (key ? "自适应认知层级" : "");
}

function resourceTypeLabel(value: unknown, fallback = "个性化推荐") {
  return RESOURCE_TYPE_LABELS[String(value ?? "").toLowerCase()] ?? fallback;
}

async function loadNbq() {
  try {
    const r = await nextBestQuestion({ user_id: userId.value, kp_id: primaryWeaknessId.value || undefined, top_k: 3 });
    nbqItems.value = (r.questions ?? r.recommendations ?? []) as Array<Record<string, any>>;
    return true;
  } catch {
    nbqItems.value = [];
    return false;
  }
}

async function loadReco() {
  try {
    const r = await getRecommendations(userId.value, 5, course.value);
    recoItems.value = r.items ?? [];
    return true;
  } catch {
    recoItems.value = [];
    return false;
  }
}

// ----- 个性化推理链 -----
const personalizationChain = ref<PersonalizationChainResponse | null>(null);
const primaryWeaknessId = computed(() => personalizationChain.value?.bkt_summary.weakest?.[0]?.kp_id ?? "");

async function loadPersonalizationChain() {
  try {
    personalizationChain.value = await getPersonalizationChain(userId.value, course.value);
    return true;
  } catch {
    personalizationChain.value = null;
    return false;
  }
}

function chainStepColor(index: number): string {
  const colors = ["#ea5a1a", "#ef4444", "#8b5cf6", "#10b981", "#ec4899", "#f59e0b", "#3b82f6"];
  return colors[index % colors.length];
}

async function loadStrategy() {
  try {
    strategy.value = await getAdaptiveStrategy(userId.value, course.value);
    return true;
  } catch {
    strategy.value = null;
    return false;
  }
}

// ----- 加载 -----
async function load() {
  loading.value = true;
  error.value = "";
  const results = await Promise.allSettled([
    listPaths(userId.value),
    getAssessment(userId.value),
    getStudentOverview(userId.value, course.value),
  ]);
  assessment.value = results[1].status === "fulfilled" ? results[1].value : null;
  overview.value = results[2].status === "fulfilled" ? results[2].value : null;
  const availablePaths = results[0].status === "fulfilled" ? results[0].value.paths ?? [] : [];
  const pathMetadata = (item: LearningPath) => (
    item.metadata && typeof item.metadata === "object" ? item.metadata : {}
  );
  const isTeacherAssignment = (item: LearningPath) => (
    item.recommended_role === "teacher"
    || pathMetadata(item).recommended_role === "teacher"
  );
  const courseMatches = (item: LearningPath) => {
    const assignedCourse = String(item.course ?? pathMetadata(item).course ?? "").trim().toLowerCase();
    return !assignedCourse || assignedCourse === String(course.value ?? "").trim().toLowerCase();
  };
  const teacherAssignedPath = availablePaths.find((item) => isTeacherAssignment(item) && courseMatches(item));
  const preferredPathId = overview.value?.path.id;
  path.value = teacherAssignedPath
    ?? availablePaths.find((item) => item.id === preferredPathId)
    ?? [...availablePaths].sort((a, b) => Number(b.progress || 0) - Number(a.progress || 0))[0]
    ?? null;
  if (!path.value && !overview.value?.path.stages.length) {
    error.value = "暂无学习路径，请使用 AI 一键规划生成专属路线。";
  }
  const stageIndex = expandedStage.value >= 0
    ? Math.min(expandedStage.value, Math.max(stages.value.length - 1, 0))
    : Math.min(currentStage.value, Math.max(stages.value.length - 1, 0));
  expandedStage.value = stages.value.length ? stageIndex : -1;
  if (stages.value.length) void loadStageContent(stageIndex);
  loading.value = false;
  return results.every((item) => item.status === "fulfilled");
}

const loopFeedback = ref("");
const loopRefreshing = ref(false);

async function refreshLearningLoop(successMessage = "学习结果已记录，个性化推荐已更新。") {
  if (loopRefreshing.value) return;
  loopRefreshing.value = true;
  const chainReady = await loadPersonalizationChain();
  const results = await Promise.allSettled([
    load(),
    loadNbq(),
    loadReco(),
    loadStrategy(),
  ]);
  loopFeedback.value = !chainReady || results.some((item) => item.status === "rejected" || item.value === false)
    ? "学习结果已记录，部分推荐暂未刷新，请稍后重试。"
    : successMessage;
  loopRefreshing.value = false;
}

const goalEditorOpen = ref(false);
const goalSaving = ref(false);
const minTargetDate = new Date().toISOString().slice(0, 10);
const goalForm = ref<Required<PathGenerationConstraints>>({
  goal: "掌握人工智能基础并完成课程实践",
  target_date: new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10),
  daily_minutes: 60,
  interest: "",
});

const currentConstraints = computed(() => {
  const raw = path.value as Record<string, any> | null;
  return (raw?.constraints ?? raw?.metadata?.constraints ?? {}) as PathGenerationConstraints;
});
const weeklyGoalMinutes = computed(() => Math.max(15, Number(currentConstraints.value.daily_minutes || 60)) * 7);
const weeklyGoalHoursText = computed(() => (weeklyGoalMinutes.value / 60).toFixed(1));
const weeklyGoalProgress = computed(() => Math.min(
  100,
  Math.round(((overview.value?.activity.this_week_minutes ?? 0) / weeklyGoalMinutes.value) * 100),
));
const weeklyRemainingHoursText = computed(() => (
  Math.max(0, weeklyGoalMinutes.value - (overview.value?.activity.this_week_minutes ?? 0)) / 60
).toFixed(1));

function openGoalEditor() {
  const current = currentConstraints.value;
  goalForm.value = {
    goal: String(current.goal || goalForm.value.goal),
    target_date: String(current.target_date || goalForm.value.target_date),
    daily_minutes: Number(current.daily_minutes || goalForm.value.daily_minutes),
    interest: String(current.interest || ""),
  };
  goalEditorOpen.value = true;
}

async function saveLearningGoal() {
  if (goalSaving.value || !goalForm.value.goal.trim()) return;
  goalSaving.value = true;
  generateNote.value = "";
  try {
    const result = await generatePersonalPath(userId.value, 0.8, { ...goalForm.value, course: course.value });
    generateNote.value = result.feasibility?.message || "学习目标已保存，个性化路径已重新生成。";
    goalEditorOpen.value = false;
    await refreshLearningLoop("学习目标已更新，路径、任务和推荐已同步刷新。");
  } catch (e: any) {
    generateNote.value = `目标保存失败：${e?.detail ?? e?.message ?? e}`;
  }
  goalSaving.value = false;
}

onMounted(() => {
  void load();
  void loadReco();
  void loadStrategy();
  void loadPersonalizationChain().then(() => loadNbq());
});

// ----- AI 一键规划 -----
const generating = ref(false);
const generateNote = ref("");

async function handleGeneratePath(mistakeRepair = false) {
  if (generating.value) return;
  generating.value = true;
  generateNote.value = "";
  try {
    const r = await generatePersonalPath(userId.value, 0.8, {
      course: course.value,
      mistake_repair: mistakeRepair,
    });
    if (r.note === "all_mastered") {
      generateNote.value = "所有知识点均已掌握（BKT ≥ 80%），无需新路径。";
    } else {
      generateNote.value = mistakeRepair
        ? `已根据本轮错题重编 ${r.path?.stages?.length ?? 0} 阶段修复路径。`
        : `已生成 ${r.path?.stages?.length ?? 0} 阶段路径（待学 ${r.pending_kps} 个知识点）`;
      await refreshLearningLoop(mistakeRepair
        ? "错题修复路径已生成，阶段任务与多模态资源已同步更新。"
        : "专属学习路径已生成，今日任务与推荐已同步更新。");
    }
  } catch (e: any) {
    generateNote.value = `生成失败：${e?.detail ?? e?.message ?? e}`;
  }
  generating.value = false;
}

// ----- 应用自适应策略 -----
const applying = ref(false);
const applyNote = ref("");

async function handleApplyStrategy() {
  if (applying.value || !strategy.value?.strategy.replan_recommended) return;
  applying.value = true;
  applyNote.value = "";
  try {
    const r = await applyAdaptiveStrategy(userId.value, false, course.value);
    applyNote.value = r.new_path_id
      ? "已按最新评估重新规划路径并刷新推送。"
      : "已刷新推送策略。";
    recoItems.value = r.recommendations ?? recoItems.value;
    await refreshLearningLoop("调整已应用，路径、资源与下一道题已同步更新。");
  } catch (e: any) {
    applyNote.value = `应用失败：${e?.detail ?? e?.message ?? e}`;
  }
  applying.value = false;
}

async function markStageDone(index: number) {
  if (!path.value || saving.value) return;
  saving.value = true;
  try {
    const { path: updated } = await updateProgress(path.value.id, index, true);
    path.value = updated;
    loopFeedback.value = `阶段 ${index + 1} 已完成，学习进度已更新。`;
    await load();
  } catch (e: any) {
    loopFeedback.value = `阶段进度保存失败：${e?.detail ?? e?.message ?? "请稍后重试"}`;
  }
  saving.value = false;
}

// ----- 顶部任务 / 里程碑 Tab -----
type TaskTab = "task" | "milestone";
const activeTab = ref<TaskTab>("task");

interface TaskItem {
  id: string;
  title: string;
  desc: string;
  stage: string;
  due: string;
  progress: number;
  status: "进行中" | "待开始";
  icon: "doc" | "video" | "quiz";
  minutes: number;
}

const persistedTaskIds = computed(() => new Set(
  assessment.value?.completed_task_ids
    ?? (assessment.value?.recent_records ?? [])
      .filter((record) => record.type === "task_completed")
      .map((record) => String(record.metadata?.task_id ?? ""))
      .filter(Boolean),
));

function isTaskDone(taskId: string) {
  return Boolean(taskDone.value[taskId] || persistedTaskIds.value.has(taskId));
}

const taskList = computed<TaskItem[]>(() => {
  const stageLabel = `阶段${currentStage.value + 1}  ${stages.value[currentStage.value]?.title ?? ""}`;
  return (overview.value?.path.today_tasks ?? []).map((item, index) => {
    const task: TaskItem = {
      id: String(item.id ?? `task-${index + 1}`),
      title: String(item.title ?? "未命名任务"),
      desc: String(item.description ?? item.kp_name ?? ""),
      stage: String(item.stage ?? stageLabel),
      due: String(item.due_date ?? "今日"),
      progress: Number(item.progress_pct ?? (item.status === "completed" ? 100 : 0)),
      status: item.status === "completed" ? "进行中" : "待开始",
      icon: item.type === "quiz" ? "quiz" : item.type === "video" ? "video" : "doc",
      minutes: Number(item.duration_minutes ?? 0),
    };
    return isTaskDone(task.id) ? { ...task, progress: 100, status: "进行中" as const } : task;
  });
});

// 自动计算预计总时长
const todayTotalMinutes = computed(() => taskList.value.reduce((sum, t) => sum + t.minutes, 0));
const todayTotalText = computed(() => {
  const mins = todayTotalMinutes.value;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h} 小时 ${m > 0 ? m + " 分钟" : ""}`.trim() : `${m} 分钟`;
});

// "开始学习"按钮：滚动到当前阶段详情
function scrollToCurrentStage() {
  expandedStage.value = currentStage.value;
  void loadStageContent(currentStage.value);
  // 等待 DOM 更新后滚动
  requestAnimationFrame(() => {
    const panel = document.querySelector(".roadmap-detail-panel");
    if (panel) {
      panel.scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      // 若面板未展开，滚动到路线图区域
      const roadmap = document.querySelector(".path-roadmap-card");
      if (roadmap) roadmap.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
}

const milestoneList = computed<TaskItem[]>(() => (overview.value?.path.milestones ?? []).map((item, index) => ({
  id: String(item.id ?? `milestone-${index + 1}`),
  title: String(item.title ?? "未命名里程碑"),
  desc: String(item.description ?? ""),
  stage: String(item.stage ?? "学习路径"),
  due: String(item.due_date ?? ""),
  progress: item.achieved ? 100 : Number(item.progress_pct ?? 0),
  status: item.achieved ? "进行中" : "待开始",
  icon: "doc",
  minutes: 0,
})));

const sortByDueAsc = ref(false);
const displayedTasks = computed(() => {
  const source = activeTab.value === "task" ? taskList.value : milestoneList.value;
  if (!sortByDueAsc.value) return source;
  return [...source].sort((a, b) => a.due.localeCompare(b.due));
});

function taskIcon(name: TaskItem["icon"]) {
  switch (name) {
    case "doc": return FileText;
    case "video": return Play;
    case "quiz": return ClipboardList;
  }
}

function handleTaskAction(t: TaskItem) {
  if (t.icon === "quiz") {
    router.push({ path: "/playground", query: { task: t.id, topic: t.title } });
    return;
  }
  router.push({ path: "/resources", query: { q: t.title, task: t.id } });
}

// ----- 右侧 AI 学习建议 -----
const aiAdvices = computed(() => {
  const raw = strategy.value as Record<string, any> | null;
  const list = raw?.advices ?? raw?.suggestions ?? raw?.adjustments ?? raw?.actions;
  if (Array.isArray(list) && list.length) {
    const icons = [Target, Play, TrendingUp];
    return list.slice(0, 3).map((item: any, i: number) => ({
      icon: icons[i % icons.length],
      title: typeof item === "string"
        ? item
        : actionLabel(item, "学习建议"),
      desc: typeof item === "string"
        ? "来自团团（学习评估）与智狐（路径规划）的协同分析"
        : String(item.reason ?? item.desc ?? "来自团团与智狐的协同分析"),
    }));
  }
  return [];
});

type ResourceKind = "doc" | "video" | "quiz" | "code";
interface VisibleResourceItem {
  key: string;
  kind: ResourceKind;
  title: string;
  typeLabel: string;
  meta: string;
  difficulty: number;
  query: string;
}

function inferResourceKind(raw: RecommendationItem): ResourceKind {
  const typeText = `${raw.type ?? ""} ${raw.kind ?? ""}`.toLowerCase();
  if (typeText.includes("video")) return "video";
  if (typeText.includes("quiz") || typeText.includes("question") || typeText.includes("generate")) return "quiz";
  if (typeText.includes("code")) return "code";
  return "doc";
}

const visibleRecoItems = computed<VisibleResourceItem[]>(() => {
  if (recoItems.value.length) {
    return recoItems.value.slice(0, 5).map((r, index) => {
      const anyReco = r as Record<string, any>;
      // 跳转知识图谱聚焦用：kp_id 精确命中优先，其次主题名模糊匹配
      const topic = String(r.kp_id ?? r.topic ?? anyReco.title ?? anyReco.resource_id ?? "推荐资源");
      const title = String(anyReco.title ?? r.topic ?? r.kp_id ?? `推荐资源 ${index + 1}`);
      return {
        key: String(anyReco.resource_id ?? r.kp_id ?? `${r.kind}-${index}`),
        kind: inferResourceKind(r),
        title,
        typeLabel: resourceTypeLabel(r.type ?? r.kind, r.kind === "generate" ? "个性化生成" : "个性化推荐"),
        meta: String(r.reason ?? r.suggested_types?.join(" / ") ?? "基于画像与近期表现推荐"),
        difficulty: Math.min(4, Math.max(1, index + 2)),
        query: topic,
      };
    });
  }
  return [];
});

function refreshResources() {
  void loadReco();
}

function resIcon(kind: "doc" | "video" | "quiz" | "code") {
  switch (kind) {
    case "doc": return FileText;
    case "video": return Video;
    case "quiz": return FileCheck2;
    case "code": return Code2;
  }
}
function resIconClass(kind: "doc" | "video" | "quiz" | "code") {
  return `res-icon res-icon-${kind}`;
}

// ----- 动态调整 -----
const visibleNbqItems = computed(() => {
  if (nbqItems.value.length) return nbqItems.value.slice(0, 3);
  return [];
});

const visibleStrategyAdjustments = computed(() => {
  const raw = strategy.value as Record<string, any> | null;
  const list = raw?.adjustments ?? raw?.actions ?? raw?.strategy_adjustments;
  if (Array.isArray(list) && list.length) {
    return list.map((item: any) => {
      if (typeof item === "string") return { label: item, reason: "基于近期学习数据生成" };
      return {
        label: actionLabel(item, "已更新一条学习策略"),
        reason: String(item.reason ?? "基于近期学习数据生成"),
      };
    });
  }
  return [];
});

const visibleStrategySignals = computed(() => (strategy.value?.signals ?? []).slice(0, 3).map((signal) => ({
  ...signal,
  value: SIGNAL_VALUE_LABELS[String(signal.value).toLowerCase()] ?? signal.value,
})));

function questionTitle(q: Record<string, any>) {
  const stem = q.question?.stem ?? q.stem;
  const title = stem ?? q.kp_name ?? q.question?.kp_name ?? q.title ?? q.name;
  if (title) return String(title).slice(0, 48);
  return "个性化推荐练习";
}

function questionMeta(q: Record<string, any>) {
  const nested = q.question ?? {};
  const topic = q.kp_name ?? nested.kp_name ?? q.topic ?? "当前薄弱知识点";
  const bloom = bloomLabel(q.bloom ?? nested.bloom);
  const difficultyKey = String(q.difficulty ?? nested.difficulty ?? "adaptive").toLowerCase();
  const difficulty = DIFFICULTY_LABELS[difficultyKey] ?? "自适应难度";
  return [topic, bloom, difficulty].filter(Boolean).join(" · ");
}

function startQuestion(q: Record<string, any>) {
  router.push({
    path: "/playground",
    query: {
      question: String(q.id ?? q.question_id ?? q.kp_id ?? ""),
      topic: questionTitle(q),
    },
  });
}

// =====================================================
// 内联详情抽屉：AI建议 / 推荐资源 / 推荐题 / 今日任务
// 点击直接呈现内容，不再跳转到其它页面
// =====================================================
type DetailKind = "advice" | "resource" | "question" | "task";

const detailOpen = ref(false);
const detailKind = ref<DetailKind>("advice");
const detailTitle = ref("");
const detailLoading = ref(false);
const detailMarkdown = ref("");     // resource / advice 正文（Markdown）
const detailMeta = ref("");          // 副标题行

// 内联答题状态
interface InlineQuestion {
  id: string;
  stem: string;
  options: string[];
  answer: string;       // "A" 等
  explanation: string;
  kp_id: string;
  bloom?: string;
}
const detailQuestion = ref<InlineQuestion | null>(null);
const pickedOption = ref(-1);
const questionAnswered = ref(false);
const questionCorrect = ref(false);
const questionReport = ref("");

// 任务详情
const detailTask = ref<TaskItem | null>(null);
const taskDone = ref<Record<string, boolean>>({});

const detailHtml = computed(() =>
  detailMarkdown.value ? renderMarkdown(detailMarkdown.value) : "",
);

function closeDetail() {
  detailOpen.value = false;
  detailQuestion.value = null;
  detailMarkdown.value = "";
  detailTask.value = null;
  pickedOption.value = -1;
  questionAnswered.value = false;
  questionReport.value = "";
}

function optionLetter(i: number): string {
  return String.fromCharCode(65 + i);
}

// ---- AI 学习建议：点击直接展示行动方案 ----
function openAdviceDetail(a: { title: string; desc: string }) {
  detailKind.value = "advice";
  detailTitle.value = a.title;
  detailMeta.value = "来自团团（学习评估）与智狐（路径规划）的协同分析";
  detailMarkdown.value = [
    `**为什么给你这条建议**\n\n${a.desc}。`,
    `**建议的行动步骤**`,
    `1. 在当前阶段（${stages.value[currentStage.value]?.title ?? "本阶段"}）中优先完成与该建议相关的知识点；`,
    `2. 用右侧「下一道推荐题」做 2-3 道针对性练习，检验是否真正掌握；`,
    `3. 若练习正确率仍低，可在群聊 @智灵 请求专项讲解，或让阿匠生成补充讲义。`,
  ].join("\n\n");
  detailLoading.value = false;
  detailOpen.value = true;
}

// ---- 今日推荐资源：resource 直接读内容；quiz/generate 直接内联出题 ----
async function openResourceDetail(r: VisibleResourceItem) {
  detailTitle.value = r.title;
  detailMeta.value = `${r.typeLabel} · ${r.meta}`;
  detailOpen.value = true;
  detailLoading.value = true;
  detailMarkdown.value = "";
  detailQuestion.value = null;

  const raw = recoItems.value.find(
    (item) => String((item as any).resource_id ?? item.kp_id ?? "") === r.key,
  ) as Record<string, any> | undefined;

  // 题类推荐 → 直接内联出一道该知识点的题
  if (r.kind === "quiz") {
    detailKind.value = "question";
    await loadInlineQuestion(String(raw?.kp_id || r.query || ""));
    detailLoading.value = false;
    return;
  }

  // 资源类推荐 → 读取真实资源正文预览
  detailKind.value = "resource";
  const resourceId = String(raw?.resource_id || "");
  if (resourceId) {
    try {
      const { resource } = await getResource(resourceId);
      detailMarkdown.value = resource.content ||
        `**${resource.title}**\n\n（该资源为文件类产物，正文不在库内。）\n\n- 类型：${resource.type}\n- 生成者：${resource.agent_name || "AI"}\n- 推荐理由：${r.meta}`;
    } catch {
      detailMarkdown.value = `**${r.title}**\n\n推荐理由：${r.meta}\n\n> 资源正文暂不可读取（后端未启动或资源已删除）。`;
    }
  } else {
    // 演示兜底项 / 无 resource_id 的画像推荐
    detailMarkdown.value = [
      `**${r.title}**`,
      `推荐理由：${r.meta}`,
      `这是基于你的画像与掌握度生成的推荐方向。你可以：`,
      `- 在群聊对智灵说「讲解 ${r.query}」获得即时讲解；`,
      `- 让阿匠生成《${r.title}》完整讲义/PPT（群聊或 Agent 编排页）；`,
      `- 用下方按钮直接做一道该知识点的练习题。`,
    ].join("\n\n");
  }
  detailLoading.value = false;
}

// ---- 下一道推荐题：点击直接呈现题目并可作答 ----
function extractInlineQuestion(item: Record<string, any>): InlineQuestion | null {
  const q = item.question ?? item;
  if (!q || typeof q !== "object" || !q.stem) return null;
  return {
    id: String(item.question_id ?? q.id ?? item.id ?? ""),
    stem: String(q.stem),
    options: Array.isArray(q.options) ? q.options.map((o: any) => String(o)) : [],
    answer: String(q.answer || ""),
    explanation: String(q.explanation || ""),
    kp_id: String(item.kp_id || q.kp_id || "general"),
    bloom: String(item.bloom || q.bloom || ""),
  };
}

async function loadInlineQuestion(kpId = "") {
  // 先从已加载的推荐列表里找带完整题面的题
  for (const item of nbqItems.value) {
    const q = extractInlineQuestion(item as Record<string, any>);
    if (q && (!kpId || q.kp_id === kpId)) {
      detailQuestion.value = q;
      return;
    }
  }
  // 拉一次后端（可限定知识点）
  try {
    const r = await nextBestQuestion({ user_id: userId.value, kp_id: kpId || undefined, top_k: 3 });
    const list = (r.questions ?? r.recommendations ?? []) as Array<Record<string, any>>;
    for (const item of list) {
      const q = extractInlineQuestion(item);
      if (q) {
        detailQuestion.value = q;
        return;
      }
    }
  } catch { /* 下面给兜底提示 */ }
  detailQuestion.value = null;
  detailMarkdown.value = "> 题库暂时没有匹配的题目。先在错题本「导入演示」或群聊让小龙出题，产生做题数据后这里会自动推荐。";
}

async function openQuestionDetail(item: Record<string, any>) {
  detailKind.value = "question";
  detailTitle.value = questionTitle(item);
  detailMeta.value = questionMeta(item);
  detailOpen.value = true;
  detailLoading.value = true;
  detailMarkdown.value = "";
  pickedOption.value = -1;
  questionAnswered.value = false;
  questionReport.value = "";
  const inline = extractInlineQuestion(item);
  if (inline) {
    detailQuestion.value = inline;
  } else {
    await loadInlineQuestion(String(item.kp_id || ""));
  }
  detailLoading.value = false;
}

async function submitInlineAnswer(index: number) {
  const q = detailQuestion.value;
  if (!q || questionAnswered.value) return;
  pickedOption.value = index;
  questionAnswered.value = true;
  questionCorrect.value = optionLetter(index) === q.answer.toUpperCase();
  let masteryText = "";
  let eventRecorded = false;
  // 上报 BKT 掌握度并持久化测验事件，随后刷新完整学习闭环。
  try {
    const r = await updateBkt(userId.value, q.kp_id, questionCorrect.value);
    masteryText = `掌握度已更新为 ${Math.round((r.p_learned ?? 0) * 100)}%`;
  } catch {
    masteryText = "掌握度暂未更新";
  }
  try {
    await addAssessmentRecord(userId.value, {
      type: "quiz",
      score: questionCorrect.value ? 100 : 0,
      topic: q.kp_id,
      metadata: {
        question_id: q.id,
        kp_id: q.kp_id,
        bloom: q.bloom,
        correct: questionCorrect.value,
      },
    });
    eventRecorded = true;
  } catch {
    questionReport.value = `${masteryText}；答题记录保存失败，请稍后重试。`;
  }
  if (eventRecorded) {
    await refreshLearningLoop();
    questionReport.value = `${masteryText}；答题已记录，推荐内容已更新。`;
  }
}

// ---- 今日任务：点击直接呈现任务详情，可就地完成 ----
function openTaskDetail(t: TaskItem) {
  detailKind.value = "task";
  detailTitle.value = t.title;
  detailMeta.value = `${t.stage} · 预计 ${t.minutes} 分钟`;
  detailTask.value = t;
  const topics = stages.value[currentStage.value]?.topics ?? [];
  detailMarkdown.value = [
    `**任务说明**\n\n${t.desc}。`,
    topics.length ? `**本阶段知识点**\n\n${topics.map((x) => `- ${x}`).join("\n")}` : "",
    `**完成方式**\n\n学习/练习完成后点击下方「标记完成」，任务进度立即更新。`,
  ].filter(Boolean).join("\n\n");
  detailOpen.value = true;
  detailLoading.value = false;
}

async function markTaskDone() {
  if (!detailTask.value) return;
  const task = detailTask.value;
  try {
    await addAssessmentRecord(userId.value, {
      external_id: `${path.value?.id ?? "path"}:${task.id}:completed`,
      type: "task_completed",
      topic: task.title,
      duration: task.minutes,
      metadata: {
        path_id: path.value?.id ?? "",
        task_id: task.id,
        stage: task.stage,
      },
    });
    taskDone.value = { ...taskDone.value, [task.id]: true };
    closeDetail();
    await refreshLearningLoop("任务已记录，学习进度与后续推荐已更新。");
  } catch {
    loopFeedback.value = "任务记录失败，请检查网络后重试。";
  }
}

// ----- 阶段操作 -----
const expandedStage = ref(-1);
const selectedStage = computed(() => stages.value[expandedStage.value] ?? null);
const selectedStageIndex = computed(() => expandedStage.value);
const stageContentMap = ref<Record<string, StageLearningItem[]>>({});
const stageContentLoading = ref(false);
const stageContentError = ref("");
let stageContentRequest = 0;

const selectedStageContent = computed(() => {
  const stage = selectedStage.value;
  return stage ? stageContentMap.value[String(stage.id)] ?? [] : [];
});

async function loadStageContent(index: number, force = false) {
  const stage = stages.value[index];
  const pathId = path.value?.id || overview.value?.path.id;
  if (!stage || !pathId) {
    stageContentError.value = "暂无可读取的学习路径，请先生成专属路径。";
    return;
  }

  const key = String(stage.id);
  if (!force && stageContentMap.value[key]) return;

  const requestId = ++stageContentRequest;
  stageContentLoading.value = true;
  stageContentError.value = "";
  try {
    const result = await getStageContent(pathId, key, userId.value);
    if (requestId !== stageContentRequest) return;
    stageContentMap.value = {
      ...stageContentMap.value,
      [key]: result.items ?? [],
    };
  } catch {
    if (requestId === stageContentRequest) {
      stageContentError.value = "阶段学习内容加载失败，请检查后端后重试。";
    }
  } finally {
    if (requestId === stageContentRequest) stageContentLoading.value = false;
  }
}

function toggleStage(idx: number) {
  if (expandedStage.value === idx) {
    expandedStage.value = -1;
    return;
  }
  expandedStage.value = idx;
  void loadStageContent(idx);
}

function goToResources(topic: string) {
  router.push({ path: "/resources", query: { q: topic } });
}
function goToChat(topic: string) {
  router.push({
    path: "/chat",
    query: {
      compose: "1",
      topic,
      prompt: `@智灵 请围绕「${topic}」进行讲解：先说明它在当前学习路径中的位置，再结合例子解释，并给我一道即时检查题。`,
    },
  });
}

// 跳转到知识图谱页查看具体知识点
function goToKnowledgeGraph(kp: string) {
  router.push({ path: "/graph", query: { kp } });
}

// 跳转到实验室（练习）
function goToPlayground(topic: string) {
  router.push({ path: "/playground", query: { topic } });
}

// AI 学习建议点击：展开详情而不是跳群聊
const expandedAdvice = ref<number | null>(null);
function toggleAdvice(idx: number) {
  expandedAdvice.value = expandedAdvice.value === idx ? null : idx;
}

// 通知面板
const showNotifications = ref(false);
const notifications = ref([
  { id: 1, title: "智狐为你规划了新路径", desc: "基于最新评估结果，已调整阶段4的学习内容", time: "10分钟前" },
  { id: 2, title: "小龙挑战已生成3道新题", desc: "针对特征工程薄弱点，建议完成练习", time: "1小时前" },
  { id: 3, title: "智灵完成了知识点讲解", desc: "“梯度下降”讲解已生成，可查看回放", time: "3小时前" },
]);
function toggleNotifications() {
  showNotifications.value = !showNotifications.value;
}

// 顶部搜索
const topSearch = ref("");
function handleTopSearch() {
  const q = topSearch.value.trim();
  if (!q) return;
  router.push({ path: "/resources", query: { q } });
  topSearch.value = "";
}

// 顶部操作
function handleRefresh() {
  void refreshLearningLoop("学习路径与个性化推荐已刷新。");
}

// "调整路径"按钮
function handleAdjustPath() {
  void handleGeneratePath(true);
}

// ===== 学生自输入兴趣 → 智能体优化路径 =====
const studentInterest = ref("");
const optimizing = ref(false);
const optimizeNote = ref("");

async function handleOptimizeByInterest() {
  const interest = studentInterest.value.trim();
  if (!interest || optimizing.value) return;
  optimizing.value = true;
  optimizeNote.value = "";
  try {
    // 兴趣真实传给后端：写入画像（learning_preference.interests，随学随新）
    // + 记入路径 metadata + 智狐产出贴合说明
    const r = await generatePersonalPath(userId.value, 0.8, { interest, course: course.value });
    if (r.note === "all_mastered") {
      optimizeNote.value = "所有知识点均已掌握，无需新路径。";
    } else {
      const base = `智狐已根据你的兴趣「${interest}」重新规划路径，共 ${r.path?.stages?.length ?? 0} 阶段，画像同步更新`;
      optimizeNote.value = r.planner_note ? `${base}。${r.planner_note}` : base;
      studentInterest.value = "";
      await refreshLearningLoop("兴趣方向已写入画像，学习路径与资源推荐已更新。");
    }
  } catch (e: any) {
    optimizeNote.value = `优化失败：${e?.detail ?? e?.message ?? e}`;
  }
  optimizing.value = false;
}

</script>

<template>
  <div class="path-page companion-page teacher-skin">
    <!-- ====== 页面标题区 ====== -->
    <header class="path-page-head">
      <div class="path-page-title">
        <h1>个性化<span>学习路径</span></h1>
        <p>基于学生画像、学习进度与薄弱点动态规划</p>
      </div>
      <div class="path-page-actions">
        <form class="path-search" @submit.prevent="handleTopSearch">
          <Search :size="15" />
          <input v-model="topSearch" placeholder="搜索课程、资源、知识点..." aria-label="搜索" @keydown.enter.prevent="handleTopSearch" />
        </form>
        <button type="button" class="path-icon-btn" title="消息" @click="toggleNotifications">
          <Bell :size="17" /><i class="dot" />
        </button>
        <!-- 通知下拉面板 -->
        <div v-if="showNotifications" class="notification-dropdown">
          <div class="notif-head">
            <b>消息通知</b>
            <button type="button" @click="showNotifications = false">✕</button>
          </div>
          <div class="notif-list">
            <div v-for="n in notifications" :key="n.id" class="notif-item">
              <div class="notif-dot"></div>
              <div class="notif-body">
                <b>{{ n.title }}</b>
                <small>{{ n.desc }}</small>
                <span class="notif-time">{{ n.time }}</span>
              </div>
            </div>
          </div>
        </div>
        <Avatar :partner="learnerPartner" size="md" />
      </div>
    </header>

    <!-- 提示信息 -->
    <p v-if="error" class="path-hint">{{ error }}</p>
    <p v-if="generateNote" class="path-hint generated">{{ generateNote }}</p>
    <div v-if="loopFeedback" class="learning-loop-feedback">
      <Check :size="15" />
      <span>{{ loopFeedback }}</span>
      <button v-if="loopFeedback.includes('暂未刷新')" type="button" @click="handleRefresh">重试刷新</button>
    </div>

    <!-- ====== 主体两栏布局 ====== -->
    <div class="path-body">
      <!-- ====== 左侧主区 ====== -->
      <div class="path-main">
        <!-- 学生信息横幅 -->
        <ArtCard class="path-banner" deco>
          <div class="banner-id">
            <Avatar :partner="learnerPartner" size="lg" />
            <div class="banner-id-info">
              <h3>
                {{ displayName }}
                <span class="banner-major">计算机科学与技术 | 大二</span>
              </h3>
              <div class="banner-meta">
                <div><span class="meta-label">学习目标：</span><a class="meta-link">{{ currentConstraints.goal || '掌握人工智能基础' }}</a></div>
                <div><span class="meta-label">当前阶段：</span><a class="meta-link">{{ stages[currentStage]?.title || '等待生成路径' }}</a></div>
                <div><span class="meta-label">截止日期：</span><a class="meta-link">{{ currentConstraints.target_date || '尚未设置' }}</a></div>
                <div><span class="meta-label">每日时长：</span><a class="meta-link">{{ currentConstraints.daily_minutes || 60 }} 分钟</a></div>
              </div>
              <small class="banner-no-pill">学号：{{ userId }}</small>
              <small v-if="isTeacherRecommendedPath" class="banner-no-pill">老师推荐路径：{{ path?.title }}</small>
              <button type="button" class="goal-edit-btn" @click="openGoalEditor">
                <Target :size="12" />调整学习目标
              </button>
            </div>
          </div>

          <div class="banner-metric">
            <small>综合进度</small>
            <div class="banner-ring-wrap">
              <ProgressRing :value="overallProgress" :label="`${overallProgress}%`" />
              <span class="banner-trend">{{ pathUpdatedText }}</span>
            </div>
          </div>

          <div class="banner-metric banner-weekly-metric">
            <small>本周学习时长</small>
            <div class="banner-weekly-content">
              <div class="banner-time">
                <span class="banner-time-icon"><Clock :size="20" /></span>
                <b>{{ weeklyHoursText }} <em>h</em></b>
              </div>
              <span class="banner-trend">较上周 <b>{{ weeklyDeltaText }}</b></span>
              <div class="banner-weekly-goal">
                <div class="banner-weekly-goal-head">
                  <span>本周目标 {{ weeklyGoalHoursText }} h</span>
                  <b>{{ weeklyGoalProgress }}%</b>
                </div>
                <div class="banner-weekly-track">
                  <i :style="{ transform: `scaleX(${weeklyGoalProgress / 100})` }"></i>
                </div>
                <div class="banner-weekly-foot">
                  <span>已完成 {{ weeklyGoalProgress }}%</span>
                  <span>还差 {{ weeklyRemainingHoursText }} h</span>
                </div>
              </div>
            </div>
          </div>

          <div class="banner-metric">
            <small>知识掌握度</small>
            <div class="banner-ring-wrap">
              <ProgressRing :value="masteryPct" :label="`${masteryPct}%`" />
              <span class="banner-trend">已掌握 <b>{{ overview?.summary.mastered_knowledge_points ?? 0 }}</b> 个知识点</span>
            </div>
          </div>
        </ArtCard>

        <!-- 今日任务区：置于路线图上方，优先呈现当天行动 -->
        <ArtCard class="path-task-card" deco>
          <div class="task-head">
            <div class="task-head-left">
              <h3>今日任务</h3>
              <div class="task-total-hint">
                预计总时长：<strong>{{ todayTotalText }}</strong>
              </div>
              <div class="task-tabs">
                <button
                  type="button"
                  :class="['task-tab', activeTab === 'task' ? 'active' : '']"
                  @click="activeTab = 'task'"
                >
                  今日任务 <span class="task-tab-count">({{ taskList.length }})</span>
                </button>
                <button
                  type="button"
                  :class="['task-tab', activeTab === 'milestone' ? 'active' : '']"
                  @click="activeTab = 'milestone'"
                >
                  里程碑 <span class="task-tab-count">({{ milestoneList.length }})</span>
                </button>
              </div>
            </div>
            <div class="task-head-right">
              <button type="button" class="primary-btn sm" @click="scrollToCurrentStage">
                <Play :size="13" />开始学习
              </button>
              <button type="button" class="path-link-btn" @click="sortByDueAsc = !sortByDueAsc">
                <Clock :size="13" />排序
                <ChevronUp v-if="sortByDueAsc" :size="13" />
                <ChevronDown v-else :size="13" />
              </button>
            </div>
          </div>

          <div class="task-table-head">
            <span class="th-task">任务名称</span>
            <span class="th-stage">所属阶段</span>
            <span class="th-due">时长</span>
            <span class="th-progress">进度</span>
            <span class="th-op">操作</span>
          </div>

          <div class="task-table-body">
            <div v-for="t in displayedTasks" :key="t.id" class="task-row">
              <div class="td-task">
                <input type="checkbox" class="task-check" :checked="t.status === '进行中'" />
                <span class="task-info-icon">
                  <component :is="taskIcon(t.icon)" :size="14" />
                </span>
                <div class="task-info">
                  <div class="task-info-title">{{ t.title }}</div>
                  <small class="task-info-desc">{{ t.desc }}</small>
                </div>
              </div>
              <span class="td-stage">
                <span class="stage-pill">{{ t.stage }}</span>
              </span>
              <span class="td-due">{{ t.due === '今日' ? t.minutes + ' 分钟' : t.due }}</span>
              <div class="td-progress">
                <span class="progress-num">{{ t.progress }}%</span>
                <div class="progress-bar"><div class="progress-bar-fill" :style="{ transform: `scaleX(${t.progress / 100})` }"></div></div>
              </div>
              <div class="td-op">
                <!-- 点击直接呈现任务详情（内联抽屉），不跳资源库 -->
                <button type="button" class="task-action-btn" @click="openTaskDetail(t)">
                  {{ t.progress >= 100 ? '已完成' : t.progress > 0 ? '继续学习' : '开始学习' }}
                </button>
                <button type="button" class="task-more-btn" title="任务详情" @click="openTaskDetail(t)"><MoreHorizontal :size="16" /></button>
              </div>
            </div>
          </div>
        </ArtCard>

        <ArtCard class="path-roadmap-card" deco>
          <SectionTitleCompat title="学习路径路线图" sub="">
            <template #action>
              <div class="roadmap-legend">
                <span class="legend-item"><i class="legend-dot done"></i>已完成</span>
                <span class="legend-item"><i class="legend-dot active"></i>进行中</span>
                <span class="legend-item"><i class="legend-dot locked"></i>待学习</span>
              </div>
              <button type="button" class="ghost-btn sm" @click="handleRefresh" :disabled="loading">
                <RefreshCcw :size="13" />刷新
              </button>
              <button type="button" class="path-link-btn" @click="handleAdjustPath">
                <GitBranch :size="13" />调整路径
              </button>
              <button type="button" class="primary-btn sm" @click="handleGeneratePath()" :disabled="generating">
                <Loader2 v-if="generating" :size="13" class="spin" />
                <Wand2 v-else :size="13" />AI 一键规划
              </button>
            </template>
          </SectionTitleCompat>

          <!-- 标题行：标题+信息图标 -->
          <div class="roadmap-title-row">
            <h3 class="roadmap-title">
              学习路径路线图
              <span class="info-icon" title="按阶段推进，每完成一个解锁下一阶段"><Info :size="14" /></span>
            </h3>
          </div>

          <!-- 横向路线图 -->
          <div class="roadmap-timeline">
            <div
              v-for="(m, idx) in stages"
              :key="m.id"
              :class="['roadmap-stage', stageStatus(idx)]"
            >
              <!-- 连接线（最后一个不画） -->
              <div v-if="idx !== stages.length - 1" class="roadmap-line" :class="stageStatus(idx)"></div>

              <!-- 阶段圆点 + 序号 -->
              <div class="roadmap-node">
                <span v-if="stageStatus(idx) === 'done'" class="node-mark done"><Check :size="14" :stroke-width="3" /></span>
                <span v-else-if="stageStatus(idx) === 'active'" class="node-mark active">{{ idx + 1 }}</span>
                <span v-else class="node-mark locked">{{ idx + 1 }}</span>
              </div>

              <!-- 阶段卡 -->
              <div class="roadmap-card" @click="toggleStage(idx)">
                <div class="roadmap-card-head">
                  <span class="roadmap-stage-label">阶段{{ idx + 1 }}</span>
                  <span :class="['roadmap-stage-status', stageStatus(idx)]">{{ stageStatusText(idx) }}</span>
                </div>
                <h4 class="roadmap-card-title">{{ m.title }}</h4>
                <div class="roadmap-meta">
                  <div class="roadmap-meta-row">
                    <Clock :size="12" />
                    <span>预计 {{ m.duration }}</span>
                  </div>
                  <div class="roadmap-mastery">
                    <span class="mastery-label">掌握度</span>
                    <span :class="['mastery-value', stageStatus(idx)]">{{ Math.round(stageMastery[idx] * 100) }}%</span>
                  </div>
                </div>
                <div class="roadmap-bar">
                  <div class="roadmap-bar-fill" :style="{ transform: `scaleX(${stageMastery[idx]})` }"></div>
                </div>

                <!-- 资源标签（图中所见：常驻显示） -->
                <div class="roadmap-tags">
                  <span v-for="t in stageTags(m)" :key="t" class="roadmap-tag">{{ t }}</span>
                </div>

                <!-- 进行中标记 -->
                <div v-if="stageStatus(idx) === 'active'" class="roadmap-current-tag">
                  <span class="current-dot"></span>进行中
                </div>
              </div>
            </div>
          </div>

          <div v-if="selectedStage" class="roadmap-detail-panel">
            <div class="roadmap-detail-panel-head">
              <div>
                <span>阶段{{ selectedStageIndex + 1 }}</span>
                <strong>{{ selectedStage.title }}</strong>
              </div>
              <button
                v-if="stageStatus(selectedStageIndex) === 'active'"
                type="button"
                class="path-mini-btn done"
                :disabled="saving"
                @click.stop="markStageDone(selectedStageIndex)"
              >
                标记本阶段完成
              </button>
            </div>
            <div v-if="stageContentLoading" class="roadmap-content-state">
              <Loader2 :size="15" class="spin" /> 正在加载阶段学习内容...
            </div>
            <div v-else-if="stageContentError" class="roadmap-content-state error">
              <span>{{ stageContentError }}</span>
              <button type="button" class="path-mini-btn" @click="loadStageContent(selectedStageIndex, true)">重新加载</button>
            </div>
            <div v-else-if="selectedStageContent.length" class="roadmap-topic-grid">
              <article v-for="item in selectedStageContent" :key="item.kp_id" class="roadmap-topic-row">
                <div class="roadmap-topic-copy">
                  <div class="roadmap-topic-title">
                    <b>{{ item.name }}</b>
                    <span>{{ bloomLabel(item.bloom_level) }}</span>
                    <span>难度 {{ item.difficulty }}</span>
                    <span>掌握度 {{ item.mastery_pct }}%</span>
                  </div>
                  <p>{{ item.description }}</p>
                  <small>预计 {{ item.estimated_minutes }} 分钟 · {{ item.kp_id }}</small>
                </div>
                <div class="roadmap-topic-actions">
                  <button type="button" class="path-mini-btn" @click.stop="goToResources(item.name)">去学习</button>
                  <button type="button" class="path-mini-btn ghost" @click.stop="goToChat(item.name)">问AI</button>
                </div>
              </article>
            </div>
            <div v-else class="roadmap-content-state">
              该阶段暂无可展示的学习内容。
            </div>
          </div>
        </ArtCard>

        <!-- 学生自输入兴趣 → 智能体优化路径 -->
        <ArtCard class="path-interest-card" deco>
          <div class="interest-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><Compass :size="13" /></span>
              <h3>自定义学习方向</h3>
            </div>
            <small class="interest-hint">输入你的兴趣或学习方向，智狐将协同其他智能体为你重新规划路径</small>
          </div>
          <div class="interest-input-row">
            <input
              v-model="studentInterest"
              type="text"
              class="interest-input"
              placeholder="例如：我想深入学习深度学习和自然语言处理"
              @keydown.enter.prevent="handleOptimizeByInterest"
            />
            <button type="button" class="primary-btn sm" @click="handleOptimizeByInterest" :disabled="optimizing || !studentInterest.trim()">
              <Loader2 v-if="optimizing" :size="13" class="spin" />
              <Wand2 v-else :size="13" />
              智能体优化
            </button>
          </div>
          <p v-if="optimizeNote" class="path-hint generated">{{ optimizeNote }}</p>
        </ArtCard>

        <!-- ====== 个性化推理链面板 ====== -->
        <ArtCard v-if="personalizationChain" class="path-chain-card" deco>
          <div class="chain-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap" style="background:#ede9fe;color:#7c3aed"><Sparkles :size="13" /></span>
              <h3>个性化推理链</h3>
            </div>
            <span class="chain-sub">为什么这条路径适合你？以下每个环节都基于你的真实数据</span>
          </div>

          <!-- 个性化标签 -->
          <div v-if="personalizationChain.tags.length" class="chain-tags-row">
            <span
              v-for="(tag, ti) in personalizationChain.tags"
              :key="ti"
              class="chain-tag"
              :style="{ '--tag-color': tag.color }"
            >{{ tag.label }}</span>
          </div>

          <!-- 推理链步骤 -->
          <div class="chain-steps">
            <div
              v-for="(step, si) in personalizationChain.reasoning_chain"
              :key="si"
              class="chain-step"
            >
              <div class="chain-step-connector" v-if="si < personalizationChain.reasoning_chain.length - 1"></div>
              <div class="chain-step-dot" :style="{ background: chainStepColor(si) }">
                {{ si + 1 }}
              </div>
              <div class="chain-step-body">
                <div class="chain-step-label">{{ step.label }}</div>
                <div class="chain-step-detail">{{ step.detail }}</div>
              </div>
            </div>
          </div>

          <!-- BKT 概览 -->
          <div v-if="personalizationChain.bkt_summary.total_kps > 0" class="chain-bkt-row">
            <div class="chain-bkt-stat">
              <small>知识点总数</small>
              <b>{{ personalizationChain.bkt_summary.total_kps }}</b>
            </div>
            <div class="chain-bkt-stat">
              <small>已掌握</small>
              <b style="color:#10b981">{{ personalizationChain.bkt_summary.mastered_count }}</b>
            </div>
            <div class="chain-bkt-stat">
              <small>未掌握</small>
              <b style="color:#f59e0b">{{ personalizationChain.bkt_summary.total_kps - personalizationChain.bkt_summary.mastered_count }}</b>
            </div>
          </div>

          <!-- 通用 vs 个性化对比 -->
          <div class="chain-compare">
            <div class="chain-compare-col generic">
              <div class="chain-compare-head">
                <span class="chain-compare-badge generic">通用路径</span>
                <small>按课程大纲顺序</small>
              </div>
              <ul class="chain-compare-list">
                <li>按教材章节顺序推进</li>
                <li>所有知识点均需学习</li>
                <li>固定练习强度（每日 5 题）</li>
                <li>不区分认知风格</li>
              </ul>
            </div>
            <div class="chain-compare-arrow"><ArrowRight :size="18" /></div>
            <div class="chain-compare-col personal">
              <div class="chain-compare-head">
                <span class="chain-compare-badge personal">你的个性化路径</span>
                <small>基于 {{ personalizationChain.bkt_summary.mastered_count }} 个已掌握跳过 + BKT 薄弱点优先</small>
              </div>
              <ul class="chain-compare-list">
                <li v-if="personalizationChain.bkt_summary.weakest.length">
                  优先学习：{{ personalizationChain.bkt_summary.weakest.map(w => w.name + '(' + Math.round(w.mastery * 100) + '%)').join('、') }}
                </li>
                <li v-if="personalizationChain.cognitive_style">匹配认知风格：{{ personalizationChain.cognitive_style }}</li>
                <li>每日推荐 {{ personalizationChain.daily_intensity }} 题（自适应）</li>
                <li v-if="personalizationChain.archetype?.archetype">学习者类型：{{ personalizationChain.archetype.archetype }}</li>
                <li v-if="personalizationChain.replan_recommended" style="color:#f59e0b">⚠ 评估建议重新规划路径</li>
              </ul>
            </div>
          </div>
        </ArtCard>

      </div>

      <!-- ====== 右侧 AI 助手 ====== -->
      <aside class="path-side">
        <!-- AI 学习建议 -->
        <ArtCard class="side-card ai-advice-card" deco>
          <div class="side-card-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><Sparkles :size="13" /></span>
              <h3>AI学习建议</h3>
            </div>
            <button type="button" class="path-link-btn" @click="handleRefresh" :disabled="loopRefreshing">
              <Loader2 v-if="loopRefreshing" :size="11" class="spin" />刷新建议
            </button>
          </div>
          <div class="advice-list">
            <!-- 点击直接呈现完整行动方案（内联抽屉），不跳转 -->
            <button v-for="(a, i) in aiAdvices" :key="i" type="button" class="advice-item" @click="openAdviceDetail(a)">
              <span class="advice-icon">
                <component :is="a.icon" :size="14" />
              </span>
              <div class="advice-body">
                <b>{{ a.title }}</b>
                <small>{{ a.desc }}</small>
              </div>
              <ChevronRight :size="14" class="advice-arrow" />
            </button>
            <p v-if="!aiAdvices.length" class="side-empty">暂无学习建议，完成一次练习后系统会生成针对性建议。</p>
          </div>
        </ArtCard>

        <!-- 今日推荐资源 -->
        <ArtCard class="side-card ai-resource-card" deco>
          <div class="side-card-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><Lightbulb :size="13" /></span>
              <h3>今日推荐资源</h3>
            </div>
            <button type="button" class="path-link-btn" @click="refreshResources">
              <RefreshCcw :size="11" />换一换
            </button>
          </div>
          <div class="reso-list">
            <!-- 个性化标签栏 -->
            <div v-if="personalizationChain?.tags?.length" class="reso-personal-tags">
              <span
                v-for="(tag, ti) in personalizationChain.tags.slice(0, 3)"
                :key="ti"
                class="reso-personal-tag"
                :style="{ '--tag-color': tag.color }"
              >{{ tag.label }}</span>
            </div>
            <!-- 点击直接预览资源正文 / 内联出题，不跳转 -->
            <button v-for="r in visibleRecoItems" :key="r.key" type="button" class="reso-item" @click="openResourceDetail(r)">
              <span :class="resIconClass(r.kind)">
                <component :is="resIcon(r.kind)" :size="16" />
              </span>
              <div class="reso-body">
                <div class="reso-head">
                  <span class="reso-type">{{ r.typeLabel }}</span>
                  <b>{{ r.title }}</b>
                </div>
                <div class="reso-meta">
                  <span class="reso-meta-text">{{ r.meta }}</span>
                  <span class="reso-difficulty">
                    难度：
                    <span class="stars">
                      <i v-for="n in 4" :key="n" :class="['star', n <= r.difficulty ? 'on' : '']">★</i>
                    </span>
                  </span>
                </div>
                <!-- 个性化推荐理由标签 -->
                <div v-if="personalizationChain?.cognitive_style" class="reso-personalized-reason">
                  <Sparkles :size="11" />
                  <span>{{ personalizationChain.cognitive_style }}推荐</span>
                </div>
              </div>
            </button>
            <p v-if="!visibleRecoItems.length" class="side-empty">暂无匹配资源，请先完善画像或生成学习路径。</p>
          </div>
        </ArtCard>

        <!-- 下一道推荐题 -->
        <ArtCard class="side-card ai-nbq-card" deco>
          <div class="side-card-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><HelpCircle :size="13" /></span>
              <h3>下一道推荐题</h3>
            </div>
            <button type="button" class="path-link-btn" :disabled="!visibleNbqItems.length" @click="visibleNbqItems[0] && openQuestionDetail(visibleNbqItems[0])">
              开始练习 <ChevronRight :size="13" />
            </button>
          </div>
          <div class="nbq-list">
            <!-- 点击直接呈现题目并可作答（内联），不跳转 -->
            <button v-for="q in visibleNbqItems" :key="q.id ?? q.question_id ?? q.kp_id" type="button" class="nbq-item" @click="openQuestionDetail(q)">
              <span class="nbq-dot"></span>
              <span>
                <b>{{ questionTitle(q) }}</b>
                <small>{{ questionMeta(q) }}</small>
              </span>
            </button>
            <p v-if="!visibleNbqItems.length" class="side-empty">暂无推荐题，请先完成诊断或让小龙生成练习题。</p>
          </div>
        </ArtCard>

        <!-- 同伴学习动态 -->
        <ArtCard class="side-card partner-activity-card" deco>
          <div class="side-card-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><Gift :size="13" /></span>
              <h3>同伴学习动态</h3>
            </div>
            <AvatarStack :partners="partnerLearners" :limit="4" />
          </div>
          <div class="partner-activity-body">
            <p>有 {{ similarPeerCount }} 位同伴正在学习相近阶段，可进入群聊讨论当前路线。</p>
            <button type="button" class="path-link-btn" @click="goToChat('同伴学习讨论')">
              进入讨论 <ChevronRight :size="13" />
            </button>
          </div>
        </ArtCard>

        <!-- 动态调整 -->
        <ArtCard class="side-card ai-adjust-card" deco>
          <div class="side-card-head">
            <div class="side-card-title">
              <span class="side-title-icon-wrap"><Layers :size="13" /></span>
              <h3>学习调整建议</h3>
            </div>
            <button type="button" class="path-link-btn" @click="goToChat('自适应学习策略')">
              了解更多 <ChevronRight :size="13" />
            </button>
          </div>
          <div class="adjust-body">
            <div class="adjust-intro">
              <span class="adjust-avatar"><Bot :size="16" /></span>
              <p>系统已基于你最近的学习行为与练习结果，生成以下可解释调整建议</p>
            </div>
            <div v-if="visibleStrategySignals.length" class="adjust-signals">
              <div v-for="signal in visibleStrategySignals" :key="signal.name" class="adjust-signal">
                <span>{{ signal.name }}</span><b>{{ signal.value }}</b><small>{{ signal.detail }}</small>
              </div>
            </div>
            <ul class="adjust-list">
              <li v-for="s in visibleStrategyAdjustments" :key="s.label">
                <b>{{ s.label }}</b><small>{{ s.reason }}</small>
              </li>
            </ul>
            <p class="apply-note" v-if="applyNote">{{ applyNote }}</p>
            <button v-if="strategy?.strategy.replan_recommended" type="button" class="primary-btn sm full-width" @click="handleApplyStrategy" :disabled="applying">
              <Loader2 v-if="applying" :size="13" class="spin" />
              <Sparkles v-else :size="13" />
              确认应用调整
            </button>
            <p v-else class="adjust-stable">当前路径与学习状态匹配，暂不需要重新规划。</p>
            <small class="adjust-time">更新时间：{{ pathUpdatedText }}</small>
          </div>
        </ArtCard>
      </aside>
    </div>

    <!-- ===== 内联详情抽屉：建议 / 资源 / 题目 / 任务 就地呈现 ===== -->
    <div v-if="detailOpen" class="path-detail-mask" @click.self="closeDetail">
      <div class="path-detail-drawer">
        <header class="path-detail-head">
          <div>
            <b>{{ detailTitle }}</b>
            <small v-if="detailMeta">{{ detailMeta }}</small>
          </div>
          <button type="button" class="path-detail-close" @click="closeDetail">✕</button>
        </header>

        <div v-if="detailLoading" class="path-detail-loading">
          <Loader2 :size="16" class="spin" /> 加载内容...
        </div>

        <template v-else>
          <!-- 内联题目作答 -->
          <div v-if="detailKind === 'question' && detailQuestion" class="path-detail-question">
            <span v-if="detailQuestion.bloom" class="stage-pill">{{ bloomLabel(detailQuestion.bloom) }}</span>
            <p class="question-stem">{{ detailQuestion.stem }}</p>
            <div class="question-options">
              <button
                v-for="(opt, i) in detailQuestion.options"
                :key="i"
                type="button"
                :class="['question-option', {
                  picked: pickedOption === i,
                  correct: questionAnswered && optionLetter(i) === detailQuestion.answer.toUpperCase(),
                  wrong: questionAnswered && pickedOption === i && optionLetter(i) !== detailQuestion.answer.toUpperCase(),
                }]"
                :disabled="questionAnswered"
                @click="submitInlineAnswer(i)"
              >
                <em>{{ optionLetter(i) }}</em>{{ opt }}
              </button>
            </div>
            <div v-if="questionAnswered" class="question-result">
              <b :class="questionCorrect ? 'ok' : 'bad'">
                {{ questionCorrect ? "✓ 回答正确！" : `✗ 回答错误，正确答案是 ${detailQuestion.answer.toUpperCase()}` }}
              </b>
              <p v-if="detailQuestion.explanation" class="question-explain">{{ detailQuestion.explanation }}</p>
              <small v-if="questionReport">{{ questionReport }}</small>
              <button type="button" class="primary-btn sm" @click="openQuestionDetail({ kp_id: detailQuestion.kp_id })">
                再来一题
              </button>
            </div>
          </div>

          <!-- Markdown 正文（建议 / 资源 / 任务 / 无题兜底） -->
          <div v-if="detailHtml" class="path-detail-body markdown-body" v-html="detailHtml" />

          <!-- 任务操作 -->
          <div v-if="detailKind === 'task' && detailTask" class="path-detail-taskops">
            <button
              type="button"
              class="primary-btn sm"
              :disabled="isTaskDone(detailTask.id)"
              @click="markTaskDone"
            >
              {{ isTaskDone(detailTask.id) ? "✓ 已完成" : "标记完成" }}
            </button>
            <button
              v-if="detailTask.icon === 'quiz'"
              type="button"
              class="path-mini-btn"
              @click="openQuestionDetail({ kp_id: '' })"
            >
              直接做一道题
            </button>
          </div>
        </template>
      </div>
    </div>

    <!-- 学习目标轻量编辑器 -->
    <div v-if="goalEditorOpen" class="path-detail-mask goal-editor-mask" @click.self="goalEditorOpen = false">
      <form class="goal-editor-card" @submit.prevent="saveLearningGoal">
        <header class="path-detail-head">
          <div><b>调整学习目标</b><small>目标与时间约束会参与路径和今日任务规划</small></div>
          <button type="button" class="path-detail-close" @click="goalEditorOpen = false">✕</button>
        </header>
        <div class="goal-editor-fields">
          <label><span>学习目标</span><input v-model="goalForm.goal" maxlength="200" required placeholder="例如：掌握人工智能基础并完成课程实践" /></label>
          <label><span>截止日期</span><input v-model="goalForm.target_date" type="date" :min="minTargetDate" required /></label>
          <label><span>每日可用时长</span><div class="goal-minutes"><input v-model.number="goalForm.daily_minutes" type="number" min="15" max="1440" step="15" required /><em>分钟</em></div></label>
          <label><span>兴趣方向</span><input v-model="goalForm.interest" maxlength="200" placeholder="例如：自然语言处理、计算机视觉" /></label>
        </div>
        <div class="goal-editor-actions">
          <button type="button" class="ghost-btn sm" @click="goalEditorOpen = false">取消</button>
          <button type="submit" class="primary-btn sm" :disabled="goalSaving">
            <Loader2 v-if="goalSaving" :size="13" class="spin" /><Wand2 v-else :size="13" />保存并重新规划
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* =====================================================
   顶部页面标题区
   ===================================================== */
.path-page {
  padding: 28px 40px 36px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-height: 100%;
}

.path-page-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.path-page-title h1 {
  font-family: var(--serif);
  font-size: 28px;
  line-height: 1.2;
  margin: 0 0 6px;
  color: var(--neutral-900);
  font-weight: 800;
  letter-spacing: -.01em;
}
.path-page-title h1 span {
  color: var(--orange-600);
}
.path-page-title p {
  margin: 0;
  color: var(--neutral-500);
  font-size: 13px;
  line-height: 1.6;
}

.path-page-actions {
  /* 通知下拉的定位锚点：否则 dropdown 会渲染到文档底部（看起来像"点了没反应"） */
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
}
.path-search {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 36px;
  padding: 0 14px;
  width: 320px;
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  border: var(--border-soft);
  color: var(--neutral-400);
  transition: border-color .15s, box-shadow .15s;
}
.path-search:focus-within {
  border-color: var(--orange-500);
  box-shadow: 0 0 0 3px rgba(234, 90, 26, .12);
}
.path-search input {
  flex: 1;
  border: 0;
  background: transparent;
  color: var(--neutral-700);
  font-size: 13px;
}
.path-search input::placeholder { color: var(--neutral-400); }

.path-icon-btn {
  position: relative;
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  border: var(--border-soft);
  background: var(--neutral-0);
  color: var(--neutral-600);
}
.path-icon-btn:hover { background: var(--neutral-100); }
.path-icon-btn .dot {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--orange-500);
  border: 2px solid #fff;
}

/* 通用：路径链接按钮（橙色文字+图标，无背景） */
.path-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 8px;
  font-size: 12.5px;
  color: var(--orange-600);
  font-weight: 600;
  background: transparent;
  border-radius: var(--radius-sm);
  transition: background .15s, color .15s;
}
.path-link-btn:hover {
  background: var(--orange-50);
  color: var(--orange-700);
}

/* 提示信息 */
.path-hint {
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--orange-50);
  border: 1px solid var(--orange-200);
  color: var(--orange-700);
  font-size: 12.5px;
  line-height: 1.6;
}
.path-hint.generated {
  background: #f2fbf6;
  border-color: #cdecd9;
  color: var(--status-running);
}

/* =====================================================
   主体两栏布局
   ===================================================== */
.path-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) clamp(300px, 22vw, 360px);
  gap: 24px;
  align-items: start;
}
.path-main {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.path-page .path-main {
  padding: 0;
  overflow: visible;
}
.path-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}
.path-page .path-side {
  padding-top: 0;
}

/* =====================================================
   学生信息横幅
   ===================================================== */
.path-banner {
  display: grid !important;
  grid-template-columns: minmax(280px, 1.4fr) repeat(3, minmax(150px, 1fr));
  border: var(--border-soft);
  border-radius: var(--radius-lg);
  background: var(--neutral-0);
  overflow: hidden;
  box-shadow: var(--shadow-1);
  margin-bottom: 0 !important;
}
.banner-id {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 20px;
  border-right: var(--border-soft);
  min-width: 0;
}
.banner-id-info { min-width: 0; flex: 1; }
.banner-id-info h3 {
  margin: 0 0 8px;
  font-family: var(--serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--neutral-900);
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}
.banner-major {
  color: var(--neutral-500);
  font-family: var(--sans);
  font-size: 13px;
  font-weight: 500;
}
.banner-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 10px;
  font-size: 12.5px;
  flex-wrap: wrap;
}
.meta-label { color: var(--neutral-500); margin-right: 4px; }
.meta-link {
  color: var(--orange-600);
  font-weight: 600;
  cursor: pointer;
  text-decoration: none;
}
.meta-link:hover { color: var(--orange-700); text-decoration: underline; }
.banner-no-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 11px;
  font-weight: 600;
}

/* 指标单元 */
.banner-metric {
  padding: 20px;
  border-right: var(--border-soft);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.banner-metric:last-child { border-right: 0; }
.banner-metric small {
  font-size: 12px;
  color: var(--neutral-500);
  margin-bottom: 10px;
}
.banner-ring-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex: 1;
  justify-content: center;
}
.banner-time {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--neutral-900);
}
.banner-weekly-metric { justify-content: flex-start; }
.banner-weekly-content {
  width: min(100%, 190px);
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.banner-weekly-content .banner-trend { margin-bottom: 18px; }
.banner-weekly-goal { width: 100%; }
.banner-weekly-goal-head,
.banner-weekly-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 10.5px;
  color: var(--neutral-500);
}
.banner-weekly-goal-head b { color: var(--orange-600); font-size: 11px; }
.banner-weekly-track {
  height: 7px;
  margin: 7px 0 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--neutral-100);
}
.banner-weekly-track i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--orange-400), var(--orange-600));
  transform-origin: left center;
  transition: transform .25s ease;
}
.banner-weekly-foot span:last-child { color: var(--neutral-600); font-weight: 600; }
.banner-time b {
  font-family: var(--serif);
  font-size: 26px;
  font-weight: 800;
  color: var(--neutral-900);
  line-height: 1;
}
.banner-time em {
  font-style: normal;
  font-size: 14px;
  color: var(--neutral-500);
  font-weight: 600;
  margin-left: 2px;
}
.banner-time-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--orange-50);
  color: var(--orange-600);
  display: grid;
  place-items: center;
  flex: none;
}
.banner-trend {
  font-size: 11px;
  color: var(--neutral-500);
  display: flex;
  align-items: center;
  gap: 2px;
}
.banner-trend b { color: var(--status-running); font-weight: 700; }

/* =====================================================
   学习路径路线图（横向）
   ===================================================== */
.path-roadmap-card { padding: 22px 24px 24px; }

.roadmap-title-row {
  margin: 16px 0 18px;
}
.roadmap-title {
  margin: 0;
  font-family: var(--serif);
  font-size: 16px;
  font-weight: 700;
  color: var(--neutral-900);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.roadmap-title .info-icon {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--neutral-100);
  color: var(--neutral-500);
  cursor: help;
}

.roadmap-legend {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-right: 12px;
  font-size: 12px;
  color: var(--neutral-600);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.legend-dot.done { background: var(--status-running); }
.legend-dot.active { background: var(--orange-500); }
.legend-dot.locked { background: var(--neutral-400); }

.roadmap-timeline {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 16px;
  align-items: start;
}
.roadmap-stage {
  position: relative;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
}

/* 连接线 */
.roadmap-line {
  position: absolute;
  top: 18px;
  left: calc(50% + 18px);
  right: calc(-50% + 18px);
  height: 0;
  z-index: 0;
}
.roadmap-line.done {
  border-top: 2px solid var(--status-running);
}
.roadmap-line.active {
  border-top: 2px solid var(--orange-500);
}
.roadmap-line.locked {
  border-top: 2px dashed var(--neutral-300);
}

.roadmap-node {
  position: relative;
  z-index: 1;
  width: 36px;
  height: 36px;
  margin-bottom: 10px;
  display: grid;
  place-items: center;
}
.node-mark {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
  border: 2px solid var(--neutral-300);
  background: var(--neutral-100);
  color: var(--neutral-500);
  transition: all .2s;
}
.node-mark.done {
  background: var(--status-running);
  color: #fff;
  border-color: var(--status-running);
}
.node-mark.active {
  background: var(--orange-500);
  color: #fff;
  border-color: var(--orange-500);
  box-shadow: 0 0 0 4px rgba(234, 90, 26, .15);
}

.roadmap-card {
  width: 100%;
  min-height: 214px;
  background: var(--neutral-0);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  transition: border-color .15s, box-shadow .15s, transform .15s;
  text-align: left;
}
.roadmap-card:hover {
  border-color: var(--orange-300);
  box-shadow: var(--shadow-1);
}
.roadmap-stage.active .roadmap-card {
  border-color: var(--orange-500);
  background: #fff;
  box-shadow: 0 4px 14px rgba(234, 90, 26, .12);
}
.roadmap-stage.done .roadmap-card {
  background: var(--neutral-50);
  border-color: var(--neutral-200);
}
.roadmap-stage.locked .roadmap-card {
  background: var(--neutral-50);
  border-color: var(--neutral-200);
  color: var(--neutral-500);
}

.roadmap-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--neutral-500);
  font-weight: 600;
}
.roadmap-stage-label { letter-spacing: .02em; }
.roadmap-stage-status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
}
.roadmap-stage-status.done {
  background: rgba(47, 159, 107, .12);
  color: var(--status-running);
}
.roadmap-stage-status.active {
  background: var(--orange-50);
  color: var(--orange-700);
}
.roadmap-stage-status.locked {
  background: var(--neutral-100);
  color: var(--neutral-500);
}

.roadmap-card-title {
  margin: 0;
  font-family: var(--serif);
  font-size: 14px;
  font-weight: 700;
  color: var(--neutral-900);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
}

.roadmap-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--neutral-500);
  gap: 4px;
}
.roadmap-meta-row {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.mastery-label { color: var(--neutral-500); margin-right: 2px; }
.mastery-value { font-weight: 700; color: var(--neutral-700); }
.mastery-value.active { color: var(--orange-600); }
.mastery-value.done { color: var(--status-running); }
.mastery-value.locked { color: var(--neutral-400); }

.roadmap-bar {
  height: 4px;
  background: var(--neutral-100);
  border-radius: 999px;
  overflow: hidden;
  margin-top: 4px;
}
.roadmap-bar-fill {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, var(--orange-400), var(--orange-600));
  border-radius: 999px;
  transform-origin: left center;
  transition: transform .32s ease;
}
.roadmap-stage.done .roadmap-bar-fill {
  background: linear-gradient(90deg, #4ade80, var(--status-running));
}
.roadmap-stage.locked .roadmap-bar-fill {
  background: var(--neutral-200);
}

.roadmap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.roadmap-tag {
  font-size: 10.5px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-weight: 600;
}

.roadmap-current-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 10.5px;
  color: var(--orange-600);
  font-weight: 600;
  margin-top: 6px;
}
.current-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--orange-500);
  animation: pulse 1.5s ease-in-out infinite;
}
.roadmap-detail-panel {
  margin-top: 18px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--orange-100);
  background: linear-gradient(180deg, #fffaf5 0%, #fff 100%);
}
.roadmap-detail-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.roadmap-detail-panel-head div {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}
.roadmap-detail-panel-head span {
  color: var(--orange-600);
  font-size: 12px;
  font-weight: 700;
}
.roadmap-detail-panel-head strong {
  color: var(--neutral-900);
  font-size: 14px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.roadmap-topic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 10px;
}
.roadmap-topic-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--neutral-50);
  font-size: 12px;
  color: var(--neutral-700);
}
.roadmap-topic-copy {
  min-width: 0;
}
.roadmap-topic-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.roadmap-topic-title b {
  margin-right: 2px;
  color: var(--neutral-900);
  font-size: 13px;
}
.roadmap-topic-title span {
  padding: 2px 6px;
  border-radius: 999px;
  background: #fff;
  color: var(--neutral-600);
  font-size: 10px;
}
.roadmap-topic-copy p {
  display: -webkit-box;
  margin: 7px 0 5px;
  overflow: hidden;
  color: var(--neutral-700);
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.roadmap-topic-copy small {
  color: var(--neutral-500);
}
.roadmap-content-state {
  display: flex;
  min-height: 72px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: var(--radius-sm);
  background: var(--neutral-50);
  color: var(--neutral-600);
  font-size: 12px;
}
.roadmap-content-state.error {
  color: #b45309;
}
.roadmap-topic-actions {
  display: inline-flex;
  gap: 6px;
  flex: none;
  padding-top: 1px;
}
.path-mini-btn {
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid var(--orange-100);
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 11px;
  font-weight: 700;
}
.path-mini-btn.ghost {
  border-color: var(--neutral-200);
  background: #fff;
  color: var(--neutral-600);
}
.path-mini-btn.done {
  width: 100%;
  justify-content: center;
  color: var(--status-running);
  border-color: #cdecd9;
  background: #f2fbf6;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .5; transform: scale(1.2); }
}

/* =====================================================
   近期任务 / 学习里程碑
   ===================================================== */
.path-task-card { padding: 18px 20px; }
.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.task-head-left { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.task-total-hint { font-size: 13px; color: var(--neutral-500); }
.task-total-hint strong { color: var(--orange-600); font-weight: 700; }
.task-head-left h3 {
  margin: 0;
  font-family: var(--serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--neutral-900);
}
.task-tabs { display: flex; align-items: center; gap: 18px; }
.task-tab {
  position: relative;
  padding: 6px 0;
  font-size: 14px;
  color: var(--neutral-500);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.task-tab.active { color: var(--orange-600); }
.task-tab.active::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -2px;
  height: 2px;
  background: var(--orange-500);
  border-radius: 2px;
}
.task-tab-count {
  color: var(--neutral-400);
  font-weight: 500;
  font-size: 13px;
}
.task-tab.active .task-tab-count { color: var(--orange-500); }
.task-head-right { display: flex; gap: 8px; }

.task-table-head,
.task-row {
  display: grid;
  grid-template-columns: minmax(280px, 2fr) minmax(140px, 1fr) 110px 160px 130px;
  gap: 12px;
  align-items: center;
}
.task-table-head {
  height: 32px;
  font-size: 12px;
  color: var(--neutral-500);
  font-weight: 600;
  border-bottom: 1px solid var(--neutral-200);
  padding: 0 12px;
}
.task-table-body { display: flex; flex-direction: column; }
.task-row {
  padding: 14px 12px;
  border-bottom: 1px solid var(--neutral-100);
  transition: background .15s;
}
.task-row:hover { background: var(--neutral-50); }
.task-row:last-child { border-bottom: 0; }

.td-task {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
}
.task-check {
  margin-top: 3px;
  width: 14px;
  height: 14px;
  accent-color: var(--orange-500);
  flex: none;
}
.task-info-icon {
  margin-top: 3px;
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--orange-50);
  color: var(--orange-600);
  flex: none;
}
.task-info { min-width: 0; flex: 1; }
.task-info-title {
  font-size: 14px;
  color: var(--neutral-900);
  font-weight: 600;
  margin-bottom: 4px;
  line-height: 1.4;
}
.task-info-desc {
  display: block;
  font-size: 12px;
  color: var(--neutral-500);
  line-height: 1.5;
}

.stage-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.td-due { font-size: 12.5px; color: var(--neutral-600); }

.td-progress {
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 10px;
  align-items: center;
  font-size: 12.5px;
}
.progress-num { color: var(--neutral-700); font-weight: 600; font-variant-numeric: tabular-nums; }
.progress-bar {
  height: 6px;
  background: var(--neutral-100);
  border-radius: 999px;
  overflow: hidden;
}
.progress-bar-fill {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, var(--orange-400), var(--orange-600));
  border-radius: 999px;
  transform-origin: left center;
  transition: transform .32s ease;
}

.td-op { display: flex; align-items: center; gap: 6px; }
.task-action-btn {
  height: 28px;
  padding: 0 12px;
  border-radius: var(--radius-sm);
  background: var(--orange-50);
  color: var(--orange-600);
  font-weight: 600;
  font-size: 12px;
  border: 1px solid var(--orange-100);
  transition: all .15s;
}
.task-action-btn:hover {
  background: var(--orange-100);
  color: var(--orange-700);
}
.task-more-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--neutral-500);
  display: grid;
  place-items: center;
}
.task-more-btn:hover { background: var(--neutral-100); color: var(--neutral-700); }

/* =====================================================
   右侧 AI 学习建议
   ===================================================== */
.path-side .side-card { padding: 16px 18px; }
.side-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.side-card-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.side-card-title h3 {
  margin: 0;
  font-family: var(--serif);
  font-size: 15px;
  font-weight: 700;
  color: var(--neutral-900);
}
.side-title-icon-wrap {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--orange-50);
  color: var(--orange-600);
}

.advice-list { display: flex; flex-direction: column; gap: 10px; }
.advice-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 16px;
  gap: 10px;
  align-items: flex-start;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  transition: border-color .15s, background .15s;
  text-align: left;
}
.advice-item:hover {
  background: var(--orange-50);
  border-color: var(--orange-100);
}
.advice-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--orange-100);
  color: var(--orange-600);
  display: grid;
  place-items: center;
  flex: none;
}
.advice-body { min-width: 0; }
.advice-body b {
  display: block;
  font-size: 13px;
  color: var(--neutral-900);
  font-weight: 600;
  line-height: 1.4;
  margin-bottom: 4px;
}
.advice-body small {
  display: block;
  font-size: 11.5px;
  color: var(--neutral-500);
  line-height: 1.5;
}
.advice-arrow {
  color: var(--neutral-400);
  flex: none;
  margin-top: 6px;
}

/* =====================================================
   右侧 今日推荐资源
   ===================================================== */
.reso-list { display: flex; flex-direction: column; gap: 12px; }
.reso-item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 12px;
  align-items: flex-start;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  transition: border-color .15s, background .15s;
  text-align: left;
}
.reso-item:hover {
  border-color: var(--orange-200);
  background: #fff;
}
.res-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: grid;
  place-items: center;
  color: #fff;
  flex: none;
}
.res-icon-doc { background: var(--type-doc); }
.res-icon-video { background: var(--type-video); }
.res-icon-quiz { background: var(--type-quiz); }
.res-icon-code { background: var(--type-code); }

.reso-body { min-width: 0; }
.reso-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.reso-type {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.reso-head b {
  font-size: 13px;
  color: var(--neutral-900);
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.reso-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  color: var(--neutral-500);
}
.reso-meta-text {
  color: var(--neutral-500);
  font-size: 11px;
}
.reso-difficulty {
  font-size: 11px;
  color: var(--neutral-500);
  white-space: nowrap;
}
.stars { display: inline-flex; gap: 1px; margin-left: 2px; }
.star { color: var(--neutral-200); font-style: normal; font-size: 11px; }
.star.on { color: #f59e0b; }

.nbq-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.nbq-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--neutral-100);
  border-radius: var(--radius-md);
  background: var(--neutral-50);
  text-align: left;
  align-items: start;
}
.nbq-item:hover {
  border-color: var(--orange-200);
  background: #fff;
}
.nbq-dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--orange-500);
}
.nbq-item b {
  display: block;
  font-size: 13px;
  color: var(--neutral-900);
  line-height: 1.4;
}
.nbq-item small {
  display: block;
  margin-top: 4px;
  color: var(--neutral-500);
  font-size: 11.5px;
}

.partner-activity-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.partner-activity-body p {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--neutral-50);
  color: var(--neutral-700);
  font-size: 12px;
  line-height: 1.6;
}

/* =====================================================
   右侧 动态调整
   ===================================================== */
.adjust-body { display: flex; flex-direction: column; gap: 12px; }
.adjust-intro {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--orange-50);
  border: 1px solid var(--orange-100);
}
.adjust-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--orange-500);
  color: #fff;
  display: grid;
  place-items: center;
  flex: none;
}
.adjust-intro p {
  margin: 0;
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.6;
}
.adjust-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.adjust-list li {
  position: relative;
  padding: 8px 10px 8px 22px;
  border-radius: var(--radius-sm);
  background: var(--neutral-50);
  font-size: 12.5px;
  color: var(--neutral-700);
  line-height: 1.5;
}
.adjust-list li::before {
  content: "";
  position: absolute;
  left: 10px;
  top: 14px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--orange-500);
}

.apply-note {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: #f2fbf6;
  border: 1px solid #cdecd9;
  color: var(--status-running);
  font-size: 11.5px;
}
.primary-btn.full-width { width: 100%; justify-content: center; }
.adjust-time {
  display: block;
  text-align: right;
  font-size: 11px;
  color: var(--neutral-400);
}

/* =====================================================
   通用：按钮/段落/小工具
   ===================================================== */
.spin { animation: pt-spin 1s linear infinite; }
@keyframes pt-spin { to { transform: rotate(360deg); } }

.ghost-btn.sm { height: 30px; padding: 0 12px; font-size: 12.5px; }
.primary-btn.sm { height: 30px; padding: 0 12px; font-size: 12.5px; }

/* =====================================================
   内联详情抽屉
   ===================================================== */
.path-detail-mask {
  position: fixed;
  inset: 0;
  z-index: 340;
  background: rgba(30, 24, 16, 0.42);
  display: flex;
  justify-content: flex-end;
}
.path-detail-drawer {
  width: min(560px, 94vw);
  height: 100%;
  overflow-y: auto;
  background: #fff;
  box-shadow: -12px 0 40px rgba(0, 0, 0, 0.16);
  padding: 22px 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  animation: drawer-in 0.22s ease;
}
@keyframes drawer-in {
  from { transform: translateX(40px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
.path-detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.path-detail-head b { font-size: 16px; color: var(--neutral-900); }
.path-detail-head small { display: block; margin-top: 4px; color: var(--neutral-500); font-size: 12px; }
.path-detail-close {
  border: 0;
  background: transparent;
  color: var(--neutral-400);
  cursor: pointer;
  font-size: 15px;
}
.path-detail-loading {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--neutral-500);
  font-size: 13px;
  padding: 20px 0;
}
.path-detail-body {
  font-size: 13.5px;
  line-height: 1.75;
  color: var(--neutral-700);
}
.path-detail-question { display: flex; flex-direction: column; gap: 12px; }
.question-stem { margin: 0; font-size: 14.5px; font-weight: 600; line-height: 1.7; color: var(--neutral-900); }
.question-options { display: flex; flex-direction: column; gap: 8px; }
.question-option {
  display: flex;
  align-items: baseline;
  gap: 10px;
  text-align: left;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--neutral-200);
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}
.question-option:hover:not(:disabled) { border-color: var(--orange-400); background: var(--orange-50); }
.question-option em {
  font-style: normal;
  font-weight: 800;
  color: var(--orange-600);
  flex: none;
}
.question-option.correct { border-color: #2f9f6b; background: #e8f6ee; }
.question-option.wrong { border-color: #dc2626; background: #fef2f2; }
.question-result { display: flex; flex-direction: column; gap: 8px; }
.question-result b.ok { color: #157347; }
.question-result b.bad { color: #b91c1c; }
.question-explain {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--neutral-50);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--neutral-600);
}
.question-result small { color: var(--neutral-500); }
.path-detail-taskops { display: flex; gap: 10px; align-items: center; }

/* =====================================================
   通知下拉面板
   ===================================================== */
.notification-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  width: 340px;
  background: var(--neutral-0);
  border: var(--border-soft);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .12);
  z-index: 100;
  overflow: hidden;
}
.notif-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--neutral-100);
  font-size: 14px;
}
.notif-head button {
  border: 0;
  background: transparent;
  color: var(--neutral-400);
  cursor: pointer;
  font-size: 14px;
}
.notif-list { max-height: 360px; overflow-y: auto; }
.notif-item {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--neutral-50);
}
.notif-item:last-child { border-bottom: 0; }
.notif-dot {
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--orange-500);
  flex: none;
}
.notif-body { min-width: 0; }
.notif-body b {
  display: block;
  font-size: 13px;
  color: var(--neutral-900);
  margin-bottom: 4px;
}
.notif-body small {
  display: block;
  font-size: 12px;
  color: var(--neutral-500);
  line-height: 1.5;
}
.notif-time {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--neutral-400);
}

/* =====================================================
   AI 学习建议展开操作
   ===================================================== */
.advice-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  flex-wrap: wrap;
}

/* =====================================================
   学生兴趣输入
   ===================================================== */
.path-interest-card { padding: 18px 20px; }
.interest-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.interest-hint {
  font-size: 12px;
  color: var(--neutral-500);
}
.interest-input-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.interest-input {
  flex: 1;
  height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--neutral-200);
  background: var(--neutral-0);
  font-size: 13px;
  color: var(--neutral-700);
  transition: border-color .15s, box-shadow .15s;
}
.interest-input:focus {
  outline: 0;
  border-color: var(--orange-500);
  box-shadow: 0 0 0 3px rgba(234, 90, 26, .12);
}

/* =====================================================
   个性化推理链面板
   ===================================================== */
.path-chain-card {
  padding: 22px 24px;
}
.chain-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.chain-sub {
  font-size: 12px;
  color: var(--neutral-500);
}
.chain-tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}
.chain-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--tag-color, #ea5a1a);
  background: color-mix(in srgb, var(--tag-color, #ea5a1a) 12%, transparent);
  border: 1px solid color-mix(in srgb, var(--tag-color, #ea5a1a) 30%, transparent);
}
.chain-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-bottom: 18px;
}
.chain-step {
  position: relative;
  display: flex;
  gap: 14px;
  padding-bottom: 16px;
}
.chain-step-connector {
  position: absolute;
  left: 13px;
  top: 28px;
  bottom: 0;
  width: 2px;
  background: var(--neutral-200);
}
.chain-step-dot {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  z-index: 1;
}
.chain-step-body {
  flex: 1;
  padding-top: 3px;
}
.chain-step-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-800);
  margin-bottom: 3px;
}
.chain-step-detail {
  font-size: 12px;
  color: var(--neutral-500);
  line-height: 1.5;
}
.chain-bkt-row {
  display: flex;
  gap: 16px;
  margin-bottom: 18px;
  padding: 14px 16px;
  background: var(--neutral-50);
  border-radius: var(--radius-md);
}
.chain-bkt-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chain-bkt-stat small {
  font-size: 11px;
  color: var(--neutral-500);
}
.chain-bkt-stat b {
  font-size: 20px;
  font-weight: 700;
  color: var(--neutral-800);
}
.chain-compare {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.chain-compare-col {
  flex: 1;
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.chain-compare-col.generic {
  background: #f8fafc;
  border: 1px solid var(--neutral-200);
}
.chain-compare-col.personal {
  background: linear-gradient(135deg, #fff7ed 0%, #fef3c7 100%);
  border: 1px solid #fed7aa;
}
.chain-compare-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.chain-compare-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}
.chain-compare-badge.generic {
  background: var(--neutral-200);
  color: var(--neutral-600);
}
.chain-compare-badge.personal {
  background: var(--orange-500);
  color: #fff;
}
.chain-compare-head small {
  font-size: 11px;
  color: var(--neutral-500);
}
.chain-compare-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chain-compare-list li {
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.5;
  padding-left: 14px;
  position: relative;
}
.chain-compare-list li::before {
  content: "•";
  position: absolute;
  left: 0;
  color: var(--neutral-400);
}
.chain-compare-arrow {
  display: flex;
  align-items: center;
  color: var(--orange-500);
}

/* ===== 推荐资源个性化标签 ===== */
.reso-personal-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed var(--neutral-200);
}
.reso-personal-tag {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: var(--tag-color, #ea5a1a);
  background: color-mix(in srgb, var(--tag-color, #ea5a1a) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--tag-color, #ea5a1a) 25%, transparent);
}
.reso-personalized-reason {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-top: 4px;
  font-size: 11px;
  color: #8b5cf6;
}

/* ============================================================
 * teacher-skin 页级修正（配色由全局皮肤接管，这里只调排版）
 * ============================================================ */
.path-page.teacher-skin {
  /* 壳层已提供 28/24 内边距，页面不再叠加横向 padding */
  padding: 0 0 40px;
}
.path-page.teacher-skin .path-page-title h1 {
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #181612;
}
.path-page.teacher-skin .path-page-title p {
  font-size: 14px;
  color: #68635b;
}

.learning-loop-feedback {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid #b9e2c9;
  border-radius: 10px;
  background: #f0faf4;
  color: #1f7a4d;
  font-size: 12.5px;
}
.learning-loop-feedback button { margin-left: auto; color: var(--orange-600); font-weight: 700; }
.goal-edit-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-left: 8px;
  padding: 4px 8px;
  border-radius: 7px;
  background: var(--orange-50);
  color: var(--orange-700);
  font-size: 11px;
  font-weight: 700;
}
.side-empty { margin: 0; padding: 12px; border-radius: 8px; background: var(--neutral-50); color: var(--neutral-500); font-size: 12px; line-height: 1.6; }
.adjust-signals { display: grid; gap: 7px; }
.adjust-signal { display: grid; grid-template-columns: 1fr auto; gap: 3px 8px; padding: 8px 10px; border: 1px solid var(--neutral-100); border-radius: 8px; }
.adjust-signal span { color: var(--neutral-600); font-size: 11.5px; }
.adjust-signal b { color: var(--orange-700); font-size: 12px; }
.adjust-signal small { grid-column: 1 / -1; color: var(--neutral-500); font-size: 10.5px; line-height: 1.5; }
.adjust-list li b, .adjust-list li small { display: block; }
.adjust-list li small { margin-top: 3px; color: var(--neutral-500); font-size: 10.5px; }
.adjust-stable { margin: 0; padding: 9px 10px; border-radius: 8px; background: #f2fbf6; color: #24734e; font-size: 11.5px; }
.goal-editor-mask { align-items: center; justify-content: center; }
.goal-editor-card { width: min(520px, calc(100vw - 32px)); padding: 22px; border-radius: 16px; background: #fff; box-shadow: 0 24px 70px rgba(23, 28, 38, .22); }
.goal-editor-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 20px; }
.goal-editor-fields label { display: flex; flex-direction: column; gap: 7px; color: var(--neutral-700); font-size: 12px; font-weight: 700; }
.goal-editor-fields label:first-child, .goal-editor-fields label:last-child { grid-column: 1 / -1; }
.goal-editor-fields input { width: 100%; height: 38px; padding: 0 11px; border: 1px solid var(--neutral-200); border-radius: 8px; color: var(--neutral-800); background: #fff; }
.goal-editor-fields input:focus { border-color: var(--orange-500); box-shadow: 0 0 0 3px rgba(234, 90, 26, .1); outline: 0; }
.goal-minutes { display: flex; align-items: center; gap: 8px; }
.goal-minutes em { color: var(--neutral-500); font-size: 12px; font-style: normal; }
.goal-editor-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; }
</style>
