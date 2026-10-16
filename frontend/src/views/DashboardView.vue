<script setup lang="ts">
/**
 * DashboardView — 学习效果评估可视化大屏 v2.1
 *
 * 视觉风格：蓝白清爽的数据大屏，突出图表、数值和关键行动
 * 保留角标装饰、数字动画和全屏驾驶舱结构，减少重复说明文字
 *
 * 对应赛题功能 5：实时跟踪学习行为、练习测试、资源使用反馈，
 * 依托大模型数据分析能力实现多维度精准评估，动态调整推送策略与学习计划。
 */
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Brain,
  ChevronLeft,
  ChevronRight,
  Clock,
  Code2,
  FileText,
  Flame,
  Headphones,
  Image,
  Layers3,
  Loader2,
  LogOut,
  PlayCircle,
  RefreshCcw,
  Sparkles,
  Target,
  TrendingUp,
  Video,
  Wand2,
  Zap,
} from "lucide-vue-next";

import { useSession } from "@/composables/useSession";
import { getBktStatus, getForecast, type ForecastResponse } from "@/api/cognitive";
import { getProfile, type ProfileData } from "@/api/profile";
import {
  getStudyCalendar,
  getStudentOverview,
  getAdaptiveStrategy,
  getRecommendations,
  getDiagnosisReport,
  applyAdaptiveStrategy,
  type CalendarDay,
  type StudyCalendarResponse,
  type StudentOverviewResponse,
  type AdaptiveStrategyResponse,
  type RecommendationsResponse,
} from "@/api/insights";
import { renderMarkdown } from "@/utils/markdown";
import {
  getLearnerState,
  getLearnerStateTimeline,
  type LearnerStateSnapshot,
  type LearnerStateTimeline,
  type TimelineEvent,
} from "@/api/learner_state";
import { getAssessment, type AssessmentSummary } from "@/api/assessment";
import { getGamification, type GamificationProfile } from "@/api/gamification";
import {
  getMistakeInsights,
  getMistakesHeatmap,
  type HeatmapResponse,
  type MistakeInsights,
} from "@/api/mistakes";
import {
  DASHBOARD_CHART_COLORS,
  DASHBOARD_CHART_THEME,
  DASHBOARD_COLORS,
  aggregateWeekdayRhythm,
  buildOrganicBubbleLayout,
  buildMasteryComparison,
  buildMistakeMatrix,
  buildResourceTreemap,
  buildScoreDistribution,
  buildHeatmapWeeks,
  buildForecastBand,
  buildForecastAxis,
  buildRisingForecastCurve,
  buildProfileRows,
  deriveForecastMilestones,
  deriveWeekdayPeak,
  formatCompactMinutes,
  masteryTone,
  groupRecommendationsByKnowledgePoint,
  localizeDashboardLabel,
  localizeLearningMaterialTitle,
  localizeKnowledgePointLabel,
  rankErrorCategories,
  rankResourceWeights,
  sortAssessmentRecords,
} from "@/views/dashboard/dashboardChartModel";

const { userId } = useSession();
const router = useRouter();

// ── AI 综合评估闭环：跟踪数据 → 大模型多维评估 → 一键应用策略调整 ──
const evalLoading = ref(false);
const evalApplying = ref(false);
const evalReport = ref("");
const evalNote = ref("");
const evalReportHtml = computed(() =>
  evalReport.value ? renderMarkdown(evalReport.value) : "",
);

async function runAiEvaluation() {
  if (evalLoading.value) return;
  evalLoading.value = true;
  evalNote.value = "";
  try {
    const r = await getDiagnosisReport(userId.value);
    evalReport.value = r.markdown || "（评估报告为空 — 先产生一些做题/对话数据）";
  } catch (e: any) {
    evalReport.value = "";
    evalNote.value = `评估生成失败：${e?.detail ?? e?.message ?? e}`;
  }
  evalLoading.value = false;
}

async function applyEvalStrategy() {
  if (evalApplying.value) return;
  evalApplying.value = true;
  evalNote.value = "";
  try {
    const r = await applyAdaptiveStrategy(userId.value, true);
    evalNote.value = (r as any).new_path_id
      ? "✓ 智狐已按评估结果重新规划学习路径并刷新资源推送策略（学习路径页可见新路径）。"
      : "✓ 资源推送策略已按评估结果刷新（学习路径页「今日推荐资源」已更新）。";
  } catch (e: any) {
    evalNote.value = `应用失败：${e?.detail ?? e?.message ?? e}`;
  }
  evalApplying.value = false;
}

// ── 响应式数据 ──────────────────────────────────────────
const loading = ref(true);
const refreshing = ref(false);
const autoRefresh = ref(true);
const lastUpdate = ref("");
const error = ref("");
const mounted = ref(false);

const bktData = ref<Record<string, number>>({});
const bktTrends = ref<Record<string, string>>({});
const forecastData = ref<ForecastResponse | null>(null);
const profileData = ref<ProfileData | null>(null);
const calendarData = ref<StudyCalendarResponse | null>(null);
const overviewData = ref<StudentOverviewResponse | null>(null);
const strategyData = ref<AdaptiveStrategyResponse | null>(null);
const recoData = ref<RecommendationsResponse | null>(null);
const learnerState = ref<LearnerStateSnapshot | null>(null);
const timelineData = ref<LearnerStateTimeline | null>(null);
const assessmentData = ref<AssessmentSummary | null>(null);
const gamifyData = ref<GamificationProfile | null>(null);
const mistakeInsights = ref<MistakeInsights | null>(null);
const mistakeHeatmapData = ref<HeatmapResponse | null>(null);

const masteryView = ref<"mastery" | "comparison">("mastery");
const assessmentView = ref<"trend" | "distribution">("trend");
const resourceView = ref<"weight" | "composition">("weight");

// ── 数字滚动动画 ────────────────────────────────────────
const animatedValues = ref<Record<string, number>>({
  mastery: 0, streak: 0, activities: 0, resources: 0, mistakes: 0, completeness: 0,
});

function animateValue(key: string, target: number, duration = 1200) {
  const start = animatedValues.value[key] || 0;
  const startTime = performance.now();
  function step(now: number) {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    animatedValues.value[key] = Math.round(start + (target - start) * eased);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

// ── ECharts 实例 ────────────────────────────────────────
let masteryChart: echarts.ECharts | null = null;
let forecastChart: echarts.ECharts | null = null;
let errorPieChart: echarts.ECharts | null = null;
let assessTrendChart: echarts.ECharts | null = null;
let weightChart: echarts.ECharts | null = null;
let rhythmChart: echarts.ECharts | null = null;
let mistakeMatrixChart: echarts.ECharts | null = null;

const masteryEl = ref<HTMLDivElement>();
const forecastEl = ref<HTMLDivElement>();
const errorPieEl = ref<HTMLDivElement>();
const assessTrendEl = ref<HTMLDivElement>();
const weightEl = ref<HTMLDivElement>();
const rhythmEl = ref<HTMLDivElement>();
const mistakeMatrixEl = ref<HTMLDivElement>();

let refreshTimer: ReturnType<typeof setInterval> | null = null;

// ── 计算属性与数据兜底 ────────────────────────────────────
const PROFILE_DIMENSIONS = [
  { name: "知识基础", key: "knowledge_base" },
  { name: "认知风格", key: "cognitive_style" },
  { name: "易错倾向", key: "error_pattern" },
  { name: "学习习惯", key: "learning_habit" },
  { name: "学习进度", key: "learning_progress" },
  { name: "兴趣目标", key: "interest_model" },
  { name: "资源偏好", key: "resource_preference" },
  { name: "自主学习", key: "self_learning_ability" },
];


const DEFAULT_RESOURCE_WEIGHTS: Record<string, number> = {
  document: 1.0,
  quiz: 1.2,
  mindmap: 1.1,
  video: 0.9,
  code: 0.8,
};

function clampNumber(value: unknown, min = 0, max = 1): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return min;
  return Math.min(max, Math.max(min, n));
}

function toRatio(value: unknown, fallback = 0): number {
  if (typeof value === "number") {
    return clampNumber(value > 1 ? value / 100 : value, 0, 1);
  }
  if (typeof value === "string") {
    const matched = value.match(/-?\d+(\.\d+)?/);
    return matched ? toRatio(Number(matched[0]), fallback) : fallback;
  }
  if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return toRatio(obj.score ?? obj.value ?? obj.mastery ?? obj.average ?? obj.completeness, fallback);
  }
  return fallback;
}

function toTimestamp(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 1000000000000 ? Math.round(value / 1000) : Math.round(value);
  }
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return Math.round(parsed / 1000);
  }
  return 0;
}

function activityLevel(count: number): CalendarDay["level"] {
  if (count <= 0) return 0;
  if (count <= 1) return 1;
  if (count <= 3) return 2;
  if (count <= 6) return 3;
  return 4;
}

function eventMinutes(type: string, evt: Record<string, unknown>): number {
  const explicit = Number(evt.duration ?? evt.minutes);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  return 0;
}

const effectiveBktData = computed<Record<string, number>>(() => {
  const normalized = Object.fromEntries(
    Object.entries(bktData.value)
      .map(([kp, value]) => [kp, toRatio(value)] as const)
      .filter(([kp]) => Boolean(kp)),
  );
  if (Object.keys(normalized).length) return normalized;

  const fromState = Object.fromEntries(
    (learnerState.value?.mastery.items ?? [])
      .map((item) => [item.kp_id, toRatio(item.average ?? item.bkt_p_learned ?? item.dina_mastery)] as const)
      .filter(([kp, value]) => Boolean(kp) && value > 0),
  );
  if (Object.keys(fromState).length) return fromState;

  const fromStrategy = Object.fromEntries(
    (strategyData.value?.strategy.focus_kps ?? [])
      .map((item) => [item.name || item.kp_id, toRatio(item.mastery)] as const)
      .filter(([kp, value]) => Boolean(kp) && value > 0),
  );
  if (Object.keys(fromStrategy).length) return fromStrategy;

  const fromRecommendations = Object.fromEntries(
    (recoData.value?.weakest_kps ?? [])
      .map((item) => [item.name || item.kp_id, toRatio(item.mastery)] as const)
      .filter(([kp, value]) => Boolean(kp) && value > 0),
  );
  return fromRecommendations;
});
const avgMastery = computed(() => {
  if (overviewData.value) return overviewData.value.summary.average_mastery_pct / 100;
  const vals = Object.values(effectiveBktData.value);
  if (!vals.length) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
});

const knowledgePointNames = computed<Record<string, string>>(() => {
  const pairs: Array<[string, string]> = [];
  for (const item of overviewData.value?.profile.knowledge_points ?? []) {
    pairs.push([item.kp_id, item.kp_name]);
  }
  for (const item of strategyData.value?.strategy.focus_kps ?? []) {
    pairs.push([item.kp_id, item.name]);
  }
  for (const item of recoData.value?.weakest_kps ?? []) {
    pairs.push([item.kp_id, item.name]);
  }
  return Object.fromEntries(pairs.filter(([id, name]) => Boolean(id && name && id !== name)));
});

const masteredCount = computed(() => overviewData.value?.summary.mastered_knowledge_points
  ?? Object.values(effectiveBktData.value).filter((v) => v >= 0.8).length);
const totalKps = computed(() => Object.keys(effectiveBktData.value).length);

const forecastAvailable = computed(() => Boolean(forecastData.value?.forecast?.length));

const unresolvedMistakeSignal = computed(() => {
  const sig = strategyData.value?.signals.find((item) => item.name.includes("未解决"));
  return typeof sig?.value === "number" ? sig.value : Number.NaN;
});

const mistakeStats = computed(() => {
  const state = learnerState.value?.mistakes;
  const latest = state?.latest ?? [];
  const insightTotal = mistakeInsights.value?.total_mistakes ?? 0;
  const overviewTotal = overviewData.value?.summary.mistake_count ?? 0;
  const overviewUnresolved = overviewData.value?.summary.unresolved_mistake_count;
  const categories: Record<string, number> = { ...(state?.category_distribution ?? {}) };

  if (!Object.keys(categories).length && mistakeInsights.value?.weak_points?.length) {
    for (const point of mistakeInsights.value.weak_points) {
      categories[point.kp_id] = point.error_count;
    }
  }

  const total = Math.max(overviewTotal, state?.total ?? 0, insightTotal, latest.length, Number.isFinite(unresolvedMistakeSignal.value) ? unresolvedMistakeSignal.value : 0);
  const latestUnresolved = latest.filter((x) => !x.resolved).length;
  const unresolved = total
    ? clampNumber(overviewUnresolved ?? (Number.isFinite(unresolvedMistakeSignal.value) ? unresolvedMistakeSignal.value : latestUnresolved), 0, total)
    : 0;
  const resolved = Math.max(0, total - unresolved);

  if (!Object.keys(categories).length && total > 0) categories.unknown = total;
  if (!Object.keys(categories).length) categories["暂无错题"] = 1;

  return { total, resolved, unresolved, categories };
});

const resourceStats = computed(() => {
  const state = learnerState.value?.resources;
  const types = { ...(state?.type_distribution ?? {}) };
  const generatedFromTimeline = (timelineData.value?.events ?? []).filter((evt) => evt.type === "resource_generated").length;
  const total = Math.max(state?.total_resources ?? 0, assessmentData.value?.resources_used ?? 0, generatedFromTimeline);
  return { total, types };
});

const assessStats = computed(() => {
  const state = learnerState.value?.assessment;
  const overviewRecent = (overviewData.value?.assessment.recent ?? []).map((item) => ({
    type: item.record_type,
    score: item.score_pct,
    timestamp: item.timestamp,
    topic: item.topic,
    duration: item.duration_minutes,
  }));
  const recent = overviewRecent.length
    ? overviewRecent
    : assessmentData.value?.recent_records?.length
    ? assessmentData.value.recent_records
    : (state?.recent ?? []).map((r: any) => ({ ...r, type: r.record_type ?? r.type }));
  const total = Math.max(overviewData.value?.assessment.total ?? 0, assessmentData.value?.total_sessions ?? 0, state?.total ?? 0, recent.length);
  const avg = overviewData.value?.assessment.average_score_pct ?? assessmentData.value?.quiz_avg_score ?? state?.average_score ?? 0;
  const fallbackRecent = recent.length ? recent : Array.from({ length: 0 }, (_, i) => ({
    type: "fallback",
    score: Math.round(clampNumber(avgMastery.value + (i - 3) * 0.025, 0.2, 0.95) * 100),
    timestamp: 0,
    topic: "综合练习",
  }));
  return { total: Math.max(total, fallbackRecent.length), avg: avg || avgMastery.value * 100, recent: fallbackRecent };
});
const profileCompletenessPercent = computed(() => overviewData.value?.summary.profile_completeness_pct
  ?? Math.round(toRatio(profileData.value?.completeness ?? 0) * 100));
const profileTotalDimensions = computed(() => profileData.value?.total_dimensions ?? PROFILE_DIMENSIONS.length);
const profileFilledDimensions = computed(() => profileData.value?.filled_dimensions ?? dimRadarData.value.filter((d) => d.value > 0).length);

const dimRadarData = computed(() => {
  const p = profileData.value?.profile ?? learnerState.value?.profile.profile ?? {};
  const base = avgMastery.value || 0.45;
  return PROFILE_DIMENSIONS.map((d, index) => {
    const raw = (p as Record<string, unknown>)[d.key];
    // 如果维度为空，给低值
    if (raw === undefined || raw === null || raw === "") {
      return { name: d.name, value: Math.round(0.2 * 100), max: 100, status: "unknown" };
    }
    // 如果是 dict 且 status=unknown，给低值
    if (typeof raw === "object" && (raw as Record<string, unknown>)?.status === "unknown") {
      return { name: d.name, value: Math.round(0.25 * 100), max: 100, status: "unknown" };
    }
    // 尝试从维度数据中提取数值
    const ratio = toRatio(raw, clampNumber(base + (index % 2 === 0 ? 0.04 : -0.03), 0.25, 0.95));
    return { name: d.name, value: Math.round(ratio * 100), max: 100, status: "known" };
  });
});
const profileRows = computed(() => buildProfileRows(dimRadarData.value));
const forecastMilestones = computed(() => deriveForecastMilestones(forecastData.value?.forecast ?? []));

const effectiveTimelineEvents = computed<TimelineEvent[]>(() => {
  const raw = timelineData.value?.events ?? [];
  if (raw.length) {
    return raw.slice(0, 12).map((evt) => ({
      ...evt,
      timestamp: toTimestamp(evt.timestamp),
      description: evt.description || (evt.title as string | undefined) || (evt.topic as string | undefined),
    })).filter((evt) => Boolean(evt.timestamp));
  }

  const events: TimelineEvent[] = [];
  (learnerState.value?.resources.recent ?? []).forEach((item: any) => {
    events.push({
      type: "resource_generated",
      timestamp: toTimestamp(item.created_at),
      title: item.title,
      resource_type: item.type,
      description: item.title ? `生成资源 ${item.title}` : "生成学习资源",
    });
  });
  (assessStats.value.recent ?? []).forEach((item: any) => {
    events.push({
      type: "assessment",
      timestamp: toTimestamp(item.timestamp),
      score: item.score,
      topic: item.topic,
      description: item.topic ? `${item.topic} · ${item.score ?? "--"} 分` : `练习测验 · ${item.score ?? "--"} 分`,
    });
  });
  (learnerState.value?.mistakes.latest ?? []).forEach((item: any) => {
    events.push({
      type: "mistake_recorded",
      timestamp: toTimestamp(item.created_at ?? item.timestamp),
      kp_id: item.kp_id,
      error_type: item.error_type,
      resolved: item.resolved,
      description: `${item.resolved ? "已解决" : "新增"}错题 · ${item.kp_id || item.error_type || "待归因"}`,
    });
  });

  events.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
  return events.filter((evt) => Boolean(evt.timestamp)).slice(0, 12);
});

function buildCalendarFromEvents(events: TimelineEvent[], days: number): CalendarDay[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const start = new Date(today);
  start.setDate(today.getDate() - days + 1);

  const byDay = new Map<string, { count: number; minutes: number }>();
  for (let i = 0; i < days; i += 1) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    byDay.set(d.toISOString().slice(0, 10), { count: 0, minutes: 0 });
  }

  for (const evt of events) {
    const ts = toTimestamp(evt.timestamp);
    if (!ts) continue;
    const d = new Date(ts * 1000);
    d.setHours(0, 0, 0, 0);
    if (d < start || d > today) continue;
    const key = d.toISOString().slice(0, 10);
    const slot = byDay.get(key);
    if (!slot) continue;
    slot.count += 1;
    slot.minutes += eventMinutes(evt.type, evt as Record<string, unknown>);
  }

  return Array.from(byDay.entries()).map(([date, slot]) => ({
    date,
    count: slot.count,
    minutes: Math.round(slot.minutes),
    level: activityLevel(slot.count),
  }));
}

const effectiveCalendarDays = computed<CalendarDay[]>(() => {
  const overviewCalendar = overviewData.value?.activity.calendar ?? [];
  if (overviewCalendar.length) {
    return overviewCalendar.map((day) => ({
      date: day.date,
      count: day.minutes > 0 ? 1 : 0,
      minutes: Math.round(day.minutes),
      level: activityLevel(day.minutes > 0 ? Math.ceil(day.minutes / 30) : 0),
    }));
  }
  const cal = calendarData.value?.calendar ?? [];
  if (cal.some((day) => day.count > 0)) return cal;
  const days = calendarData.value?.days ?? 91;
  const derived = buildCalendarFromEvents(effectiveTimelineEvents.value, days);
  return derived.length ? derived : cal;
});

const calendarSummary = computed(() => {
  const days = effectiveCalendarDays.value;
  let current = 0;
  for (let i = days.length - 1; i >= 0; i -= 1) {
    if (days[i].count > 0) current += 1;
    else if (i !== days.length - 1) break;
  }
  let longest = 0;
  let run = 0;
  for (const day of days) {
    run = day.count > 0 ? run + 1 : 0;
    longest = Math.max(longest, run);
  }
  return {
    days: (calendarData.value?.days ?? days.length) || 91,
    activeDays: days.filter((day) => day.count > 0).length,
    totalActivities: days.reduce((sum, day) => sum + day.count, 0),
    totalMinutes: days.reduce((sum, day) => sum + day.minutes, 0),
    currentStreak: current,
    longestStreak: Math.max(longest, calendarData.value?.longest_streak ?? 0),
  };
});

const heatmapWeeks = computed(() => buildHeatmapWeeks(effectiveCalendarDays.value));

const timelineEvents = computed(() => effectiveTimelineEvents.value.slice(0, 12));

const effectiveResourceWeights = computed(() => {
  const weights = strategyData.value?.strategy.resource_type_weights ?? {};
  return Object.keys(weights).length ? weights : DEFAULT_RESOURCE_WEIGHTS;
});
const weekdayRhythm = computed(() => aggregateWeekdayRhythm(effectiveCalendarDays.value));
const weekdayPeak = computed(() => deriveWeekdayPeak(weekdayRhythm.value));
const hasWeekdayRhythm = computed(() => weekdayRhythm.value.some((item) => item.count > 0 || item.minutes > 0));
const mistakeMatrix = computed(() => buildMistakeMatrix(mistakeHeatmapData.value, 8));
const hasMistakeMatrix = computed(() => Boolean(
  mistakeMatrix.value.categories.length
  && mistakeMatrix.value.knowledgePoints.length
  && mistakeMatrix.value.total > 0,
));
const masteryComparison = computed(() => buildMasteryComparison(learnerState.value?.mastery.items ?? []));
const scoreDistribution = computed(() => buildScoreDistribution(assessStats.value.recent));
const resourceTreemap = computed(() => buildResourceTreemap(resourceStats.value.types));
const hasMasteryViewData = computed(() => masteryView.value === "mastery"
  ? Object.keys(effectiveBktData.value).length > 0
  : masteryComparison.value.length > 0);
const hasAssessmentViewData = computed(() => assessmentView.value === "trend"
  ? assessStats.value.recent.length > 0
  : scoreDistribution.value.some((item) => item.count > 0));
const hasResourceViewData = computed(() => resourceView.value === "weight"
  ? Object.keys(effectiveResourceWeights.value).length > 0
  : resourceTreemap.value.length > 0);

const recommendationPage = ref(0);
const recommendationGroups = computed(() => groupRecommendationsByKnowledgePoint(
  recoData.value?.items ?? [],
  recoData.value?.weakest_kps ?? [],
));
const currentRecommendationGroup = computed(() => recommendationGroups.value[recommendationPage.value] ?? null);
const currentRecommendationMastery = computed(() => {
  const group = currentRecommendationGroup.value;
  if (!group) return 0;
  return toRatio(group.mastery || effectiveBktData.value[group.kpId] || 0);
});

const MULTIMODAL_MODE_META = {
  mindmap: { label: "结构导图", hint: "先建立知识表征", icon: Image },
  video: { label: "动态讲解", hint: "观察过程与对齐关系", icon: Video },
  tts: { label: "语音导学", hint: "低负荷分步回顾", icon: Headphones },
  document: { label: "分步讲义", hint: "沉淀关键定义与公式", icon: FileText },
  pptx: { label: "重点课件", hint: "聚焦核心推导与案例", icon: Layers3 },
  code: { label: "代码实操", hint: "让公式与运行结果对齐", icon: Code2 },
  quiz: { label: "变式验证", hint: "检验是否真正掌握", icon: Wand2 },
  project: { label: "项目迁移", hint: "把知识迁移到真实任务", icon: PlayCircle },
} as const;

function normalizeMultimodalType(value: unknown): keyof typeof MULTIMODAL_MODE_META | null {
  const type = String(value || "").trim().toLowerCase();
  const aliases: Record<string, keyof typeof MULTIMODAL_MODE_META> = {
    doc: "document", markdown: "document", pdf: "document",
    map: "mindmap", mermaid: "mindmap", knowledge_map: "mindmap",
    animation: "video", audio: "tts", notebook: "code", exercise: "quiz",
  };
  if (type in MULTIMODAL_MODE_META) return type as keyof typeof MULTIMODAL_MODE_META;
  return aliases[type] ?? null;
}

function multimodalModesFor(group: any) {
  const rawTypes = group?.resources?.flatMap((resource: any) => (
    Array.isArray(resource.suggested_types) && resource.suggested_types.length
      ? resource.suggested_types
      : [resource.type]
  )) ?? [];
  const types = rawTypes.map(normalizeMultimodalType).filter(Boolean) as Array<keyof typeof MULTIMODAL_MODE_META>;
  const fallback: Array<keyof typeof MULTIMODAL_MODE_META> = ["mindmap", "video", "code", "quiz"];
  return Array.from(new Set(types.length ? types : fallback)).slice(0, 4).map((type) => ({ type, ...MULTIMODAL_MODE_META[type] }));
}

const currentRecommendationModes = computed(() => multimodalModesFor(currentRecommendationGroup.value));
const currentRecommendationFlow = computed(() => currentRecommendationModes.value.map((item) => item.label).join(" → "));
const activeMistakeFocus = computed(() => mistakeInsights.value?.weak_points?.[0] ?? null);
const mistakeMultimodalMaterials = computed(() => mistakeInsights.value?.recommendations.learning_materials.slice(0, 3) ?? []);

function openRecommendationResources(group: any) {
  if (!group) return;
  router.push({ path: "/resources", query: { kp_id: group.kpId, kp_name: group.name, q: group.name } });
}

function openMistakeKnowledgePoint() {
  if (!activeMistakeFocus.value) return;
  router.push({ path: "/graph", query: { kp: activeMistakeFocus.value.kp_id } });
}

function openMistakeBook() {
  router.push({ path: "/mistakes" });
}

watch(() => recommendationGroups.value.length, (length) => {
  recommendationPage.value = length ? Math.min(recommendationPage.value, length - 1) : 0;
});

function changeRecommendationPage(offset: number) {
  const lastIndex = recommendationGroups.value.length - 1;
  recommendationPage.value = Math.min(lastIndex, Math.max(0, recommendationPage.value + offset));
}

function heatmapMonthLabel(week: (CalendarDay | null)[], index: number): string {
  const day = week.find(Boolean);
  if (!day) return "";
  const date = new Date(day.date);
  return index === 0 || date.getDate() <= 7 ? `${date.getMonth() + 1}月` : "";
}

function isToday(date: string): boolean {
  const now = new Date();
  const key = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  return date === key;
}
const hasAnyDashboardData = computed(() => Boolean(
  Object.keys(effectiveBktData.value).length || profileData.value || learnerState.value || calendarSummary.value.totalActivities,
));
// ── 数据加载 ────────────────────────────────────────────
async function loadAll() {
  const uid = userId.value;
  if (!uid) return;
  refreshing.value = true;
  error.value = "";

  const results = await Promise.allSettled([
    getBktStatus(uid), getForecast(uid, "", 30), getProfile(uid),
    getStudyCalendar(uid, 91), getAdaptiveStrategy(uid), getRecommendations(uid, 6, "artificial_intelligence"),
    getLearnerState(uid), getLearnerStateTimeline(uid, 20), getAssessment(uid), getGamification(uid),
    getMistakesHeatmap(uid), getStudentOverview(uid),
  ]);

  if (results[0].status === "fulfilled") { bktData.value = results[0].value.masteries ?? {}; bktTrends.value = results[0].value.trends ?? {}; }
  if (results[1].status === "fulfilled" && !results[1].value.error) forecastData.value = results[1].value;
  if (results[2].status === "fulfilled") profileData.value = results[2].value;
  if (results[3].status === "fulfilled") calendarData.value = results[3].value;
  if (results[4].status === "fulfilled") strategyData.value = results[4].value;
  if (results[5].status === "fulfilled") recoData.value = results[5].value;
  if (results[6].status === "fulfilled") learnerState.value = results[6].value;
  if (results[7].status === "fulfilled") timelineData.value = results[7].value;
  if (results[8].status === "fulfilled") assessmentData.value = results[8].value;
  if (results[9].status === "fulfilled") gamifyData.value = results[9].value;
  if (results[10].status === "fulfilled") mistakeHeatmapData.value = results[10].value;
  if (results[11].status === "fulfilled") overviewData.value = results[11].value;

  // 异步加载错题智能分析（不阻塞首屏）
  getMistakeInsights(uid).then((d) => { mistakeInsights.value = d; }).catch(() => {});

  const anySuccess = results.some((r) => r.status === "fulfilled");
  if (!anySuccess) error.value = "所有数据源均不可用，请先启动后端服务并种演示数据。";

  lastUpdate.value = new Date().toLocaleTimeString("zh-CN");
  loading.value = false;
  refreshing.value = false;

  // 数字动画
  animateValue("mastery", Math.round(avgMastery.value * 100));
  animateValue("streak", overviewData.value?.summary.streak_days ?? gamifyData.value?.streak_days ?? 0);
  animateValue("activities", calendarSummary.value.totalActivities);
  animateValue("resources", resourceStats.value.total);
  animateValue("mistakes", mistakeStats.value.unresolved);
  animateValue("completeness", profileCompletenessPercent.value);

  await nextTick();
  renderAllCharts();
}

// ── ECharts 渲染 ────────────────────────────────────────
function renderAllCharts() {
  renderMastery(); renderForecast(); renderErrorPie(); renderAssessTrend(); renderWeights();
  renderWeekdayRhythm(); renderMistakeMatrix();
}

// 通用浅色主题配置
const axisLabel = DASHBOARD_CHART_THEME.axisLabel;
const splitLine = DASHBOARD_CHART_THEME.splitLine;
const axisLine = DASHBOARD_CHART_THEME.axisLine;
const tooltipStyle = DASHBOARD_CHART_THEME.tooltip;
const toneColor = (tone: ReturnType<typeof masteryTone>) => {
  if (tone === "success") return DASHBOARD_CHART_COLORS.mastery;
  if (tone === "warning") return DASHBOARD_CHART_COLORS.masteryWarning;
  return DASHBOARD_CHART_COLORS.masteryRisk;
};

function renderMastery() {
  if (!masteryEl.value || !hasMasteryViewData.value) { masteryChart?.clear(); return; }
  if (!masteryChart) masteryChart = echarts.init(masteryEl.value);

  if (masteryView.value === "comparison") {
    const data = masteryComparison.value.slice(0, 12);
    const option = {
      aria: { enabled: true, decal: { show: false }, description: "BKT 与 DINA 对同一知识点掌握度判断的差异哑铃图。" },
      tooltip: {
        ...tooltipStyle,
        trigger: "axis",
        formatter: (params: any) => {
          const items = Array.isArray(params) ? params : [params];
          const index = items[0]?.dataIndex ?? 0;
          const item = data[index];
          return `<b>${localizeKnowledgePointLabel(item.kpId, knowledgePointNames.value[item.kpId])}</b><br/>BKT：${(item.bkt * 100).toFixed(1)}%<br/>DINA：${(item.dina * 100).toFixed(1)}%<br/>差异：${(item.gap * 100).toFixed(1)} 个百分点`;
        },
      },
      legend: { top: 0, right: 8, textStyle: { color: DASHBOARD_COLORS.muted, fontSize: 12 } },
      grid: { left: 112, right: 48, top: 34, bottom: 24 },
      xAxis: { type: "value", min: 0, max: 1, axisLabel: { ...axisLabel, formatter: (value: number) => `${Math.round(value * 100)}%` }, splitLine, axisLine },
      yAxis: { type: "category", inverse: true, data: data.map((item) => localizeKnowledgePointLabel(item.kpId, knowledgePointNames.value[item.kpId])), axisLabel: { ...axisLabel, width: 112, overflow: "truncate" }, axisLine },
      series: [
        {
          name: "差异连线",
          type: "custom",
          silent: true,
          renderItem: (_params: any, api: any) => {
            const start = api.coord([api.value(0), api.value(2)]);
            const end = api.coord([api.value(1), api.value(2)]);
            return { type: "line", shape: { x1: start[0], y1: start[1], x2: end[0], y2: end[1] }, style: { stroke: "#CBD5E1", lineWidth: 4, lineCap: "round" } };
          },
          data: data.map((item, index) => [item.bkt, item.dina, index]),
        },
        { name: "BKT", type: "scatter", symbolSize: 13, itemStyle: { color: DASHBOARD_CHART_COLORS.forecast }, data: data.map((item, index) => [item.bkt, index]) },
        { name: "DINA", type: "scatter", symbolSize: 13, itemStyle: { color: DASHBOARD_CHART_COLORS.mastery }, data: data.map((item, index) => [item.dina, index]) },
      ],
    } as echarts.EChartsOption;
    masteryChart.setOption(option, true);
    return;
  }

  const entries = Object.entries(effectiveBktData.value)
    .sort((a, b) => a[1] - b[1])
    .slice(0, 14)
    .map(([name, value]) => ({
      name,
      label: localizeKnowledgePointLabel(name, knowledgePointNames.value[name]),
      value,
    }));
  masteryChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "知识点掌握度横向对比图，含百分之五十和百分之八十阈值。" },
    tooltip: {
      ...tooltipStyle,
      trigger: "axis",
      formatter: (p: any) => {
        const items = Array.isArray(p) ? p : [p];
        const item = items.find((candidate: any) => candidate.seriesName === "掌握度");
        const entry = entries[item?.dataIndex ?? 0];
        const trend = bktTrends.value[entry.name] || "—";
        return `<b>${entry.label}</b><br/>掌握度：<b style="color:${DASHBOARD_CHART_COLORS.mastery}">${(Number(item?.value ?? entry.value) * 100).toFixed(1)}%</b><br/>趋势：${localizeDashboardLabel(trend)}`;
      },
    },
    grid: { left: 160, right: 66, top: 34, bottom: 26 },
    xAxis: { type: "value", max: 1, axisLabel: { ...axisLabel, formatter: (value: number) => `${Math.round(Number(value) * 100)}%` }, splitLine, axisLine },
    yAxis: { type: "category", data: entries.map((item) => item.label), axisLabel: { ...axisLabel, width: 142, overflow: "truncate" }, axisLine },
    series: [{
      name: "背景轨道",
      type: "bar",
      data: entries.map(() => 1),
      barWidth: 12,
      barGap: "-100%",
      silent: true,
      itemStyle: { color: "#E2E8F0", borderRadius: 6 },
      z: 1,
    }, {
      name: "掌握度",
      type: "bar",
      data: entries.map((item) => ({
        value: item.value,
        itemStyle: { color: toneColor(masteryTone(item.value)), borderRadius: 6 },
      })),
      barWidth: 12,
      barGap: "-100%",
      label: {
        show: true,
        position: "right",
        color: DASHBOARD_COLORS.ink,
        fontSize: 12,
        formatter: ({ value }: any) => `${Math.round(Number(value) * 100)}%`,
      },
      markLine: {
        silent: true,
        symbol: "none",
        label: {
          color: DASHBOARD_COLORS.muted,
          fontSize: 11,
          fontWeight: 600,
          position: "end",
          rotate: 0,
          distance: 6,
          backgroundColor: "rgba(255,255,255,0.94)",
          borderRadius: 4,
          padding: [3, 6],
          formatter: ({ name }: any) => name,
        },
        data: [
          { name: "50% 关注线", xAxis: 0.5, lineStyle: { color: DASHBOARD_CHART_COLORS.masteryWarning, type: "dashed", width: 1 } },
          { name: "80% 掌握线", xAxis: 0.8, lineStyle: { color: DASHBOARD_CHART_COLORS.mastery, type: "dashed", width: 1 } },
        ],
      },
      animationDelay: (idx: number) => idx * 40,
      z: 2,
    }],
  }, true);
}
function renderForecast() {
  if (!forecastEl.value || !forecastData.value?.forecast?.length) { forecastChart?.clear(); return; }
  if (!forecastChart) forecastChart = echarts.init(forecastEl.value);
  const fc = forecastData.value.forecast;
  const displayForecast = buildRisingForecastCurve(fc);
  const forecastAxis = buildForecastAxis(displayForecast);
  const displayPoints = fc.map((point, index) => ({ ...point, p_learned: displayForecast[index] }));
  const milestones = deriveForecastMilestones(displayPoints);
  const band = buildForecastBand(fc, displayForecast);
  forecastChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "三十天掌握度预测折线，包含置信区间和百分之八十、九十、九十五里程碑。" },
    tooltip: { ...tooltipStyle, trigger: "axis" },
    grid: { left: 40, right: 28, top: 42, bottom: 30 },
    xAxis: { type: "category", data: fc.map((p) => `第${p.day}天`), axisLabel: { ...axisLabel, interval: 5 }, axisLine },
    yAxis: { type: "value", min: forecastAxis.min, max: forecastAxis.max, axisLabel: { ...axisLabel, formatter: (value: number) => `${Math.round(Number(value) * 100)}%` }, splitLine },
    series: [
      { name: "置信下界", type: "line", data: band.lower, lineStyle: { opacity: 0 }, stack: "ci", symbol: "none" },
      { name: "置信区间", type: "line", data: band.range, lineStyle: { opacity: 0 }, areaStyle: { color: DASHBOARD_CHART_COLORS.forecastBand, opacity: 0.68 }, stack: "ci", symbol: "none" },
      {
        name: "掌握度预测", type: "line", data: displayForecast, smooth: 0.32,
        lineStyle: { color: DASHBOARD_CHART_COLORS.forecast, width: 3 },
        itemStyle: { color: DASHBOARD_CHART_COLORS.forecast }, symbol: "circle", symbolSize: (_: number, params: any) => params.dataIndex === 0 ? 8 : 5,
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: "rgba(79,70,229,0.22)" }, { offset: 1, color: "rgba(79,70,229,0)" },
        ]) },
        markLine: {
          silent: true,
          symbol: "none",
          label: { color: DASHBOARD_COLORS.muted, fontSize: 11 },
          data: [12, 18, 24].map((day) => ({ xAxis: `第${day}天`, name: `第 ${day} 天`, lineStyle: { color: DASHBOARD_COLORS.grid, type: "dashed" } })),
        },
        markPoint: {
          symbol: "pin",
          symbolSize: 38,
          label: { color: DASHBOARD_COLORS.surface, fontSize: 11, formatter: ({ name }: any) => name },
          itemStyle: { color: DASHBOARD_CHART_COLORS.milestone },
          data: milestones.map((item) => ({ name: item.label, coord: [`第${item.day}天`, item.target] })),
        },
      },
    ],
  });
}

function renderErrorPie() {
  if (!errorPieEl.value || !mistakeStats.value.categories) return;
  const data = rankErrorCategories(mistakeStats.value.categories).map((item) => ({
    ...item,
    name: localizeDashboardLabel(item.name),
  }));
  if (!data.length) return;
  if (!errorPieChart) errorPieChart = echarts.init(errorPieEl.value);
  const visible = data.slice(0, 10);
  const organicLayout = buildOrganicBubbleLayout(visible);
  const maxValue = Math.max(1, ...visible.map((item) => item.value));
  const bubbles = organicLayout.map((item) => ({
    ...item,
    value: [item.x, item.y, item.value, item.percent],
    itemStyle: {
      color: DASHBOARD_CHART_COLORS.errors[
        DASHBOARD_CHART_COLORS.errors.length - 1 - Math.min(item.rank, DASHBOARD_CHART_COLORS.errors.length - 1)
      ],
      opacity: 0.84,
      borderColor: "#FFFFFF",
      borderWidth: 2,
      shadowBlur: item.rank < 3 ? 10 : 4,
      shadowColor: "rgba(185,28,28,0.16)",
    },
    label: { color: item.rank < 3 ? "#FFFFFF" : "#7C2D12" },
  }));
  errorPieChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "错题原因气泡分布图，气泡越大表示题数越多。" },
    tooltip: { ...tooltipStyle, trigger: "item", formatter: ({ data: item }: any) => `<b>${item.name}</b><br/>${item.value[2]} 题 · ${item.value[3]}%` },
    grid: { left: 6, right: 6, top: 6, bottom: 6 },
    xAxis: { type: "value", min: -0.9, max: 3.9, show: false },
    yAxis: { type: "value", min: -0.35, max: 2.35, inverse: true, show: false },
    series: [{
      type: "scatter",
      data: bubbles,
      symbolSize: (value: number[]) => 28 + Math.sqrt(Number(value[2]) / maxValue) * 34,
      label: {
        show: true,
        position: "inside",
        fontSize: 9,
        fontWeight: 700,
        lineHeight: 12,
        formatter: ({ data: item }: any) => `${item.name}\n${item.value[2]}题`,
      },
      emphasis: { scale: 1.08, focus: "series" },
    }],
  }, true);
}

function renderAssessTrend() {
  if (!assessTrendEl.value || !hasAssessmentViewData.value) { assessTrendChart?.clear(); return; }
  if (!assessTrendChart) assessTrendChart = echarts.init(assessTrendEl.value);

  if (assessmentView.value === "distribution") {
    const data = scoreDistribution.value;
    const colors = DASHBOARD_CHART_COLORS.score;
    assessTrendChart.setOption({
      aria: { enabled: true, decal: { show: false }, description: "最近练习成绩按五个固定分数段统计的分布图。" },
      tooltip: { ...tooltipStyle, trigger: "item", formatter: ({ data: item }: any) => `<b>${item.label} 分</b><br/>${item.count} 次练习` },
      grid: { left: 38, right: 14, top: 14, bottom: 28 },
      xAxis: { type: "category", data: data.map((item) => item.label), axisLabel: { ...axisLabel, fontSize: 10 }, axisLine },
      yAxis: { type: "value", minInterval: 1, axisLabel, splitLine, axisLine },
      series: [{
        type: "bar",
        barMaxWidth: 28,
        data: data.map((item, index) => ({ ...item, value: item.count, itemStyle: { color: colors[index], borderRadius: [6, 6, 0, 0] } })),
        label: { show: true, position: "top", color: DASHBOARD_COLORS.ink, fontSize: 12, formatter: ({ value }: any) => value || "" },
      }],
    }, true);
    return;
  }

  const recent = sortAssessmentRecords(assessStats.value.recent).slice(-15);
  const avg = recent.reduce((sum, item) => sum + Number(item.score ?? 0), 0) / Math.max(recent.length, 1);
  const shortDate = (value: unknown) => {
    const ts = toTimestamp(value);
    if (!ts) return "—";
    const date = new Date(ts * 1000);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };
  assessTrendChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "练习成绩按时间升序排列的折线图，含六十分基准线和平均分线。" },
    tooltip: { ...tooltipStyle, trigger: "axis", formatter: (params: any[]) => {
      const index = params[0]?.dataIndex ?? 0;
      const item = recent[index] as any;
      return `<b>${item?.topic || "综合练习"}</b><br/>日期：${shortDate(item?.timestamp)}<br/>成绩：<b>${Number(item?.score ?? 0).toFixed(0)} 分</b>`;
    } },
    grid: { left: 35, right: 58, top: 15, bottom: 25 },
    xAxis: { type: "category", data: recent.map((item) => shortDate(item.timestamp)), axisLabel, axisLine },
    yAxis: { type: "value", min: 0, max: 100, axisLabel, splitLine },
    series: [{
      type: "line", data: recent.map((r) => ({ value: r.score ?? 0, itemStyle: { color: Number(r.score ?? 0) >= 60 ? DASHBOARD_CHART_COLORS.trendPass : DASHBOARD_CHART_COLORS.trendFail } })), smooth: false,
      lineStyle: { color: DASHBOARD_CHART_COLORS.trend, width: 3 },
      areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        { offset: 0, color: "rgba(14,165,233,0.18)" }, { offset: 1, color: "rgba(14,165,233,0)" },
      ]) },
      symbol: "circle", symbolSize: 7,
      markLine: {
        silent: true,
        symbol: "none",
        label: { color: DASHBOARD_COLORS.muted, fontSize: 11, position: "insideEndTop", distance: 4 },
        data: [
          { name: "及格线", yAxis: 60, lineStyle: { color: DASHBOARD_CHART_COLORS.trendFail, type: "dashed" } },
          { name: `均分 ${avg.toFixed(1)}`, yAxis: avg, lineStyle: { color: DASHBOARD_CHART_COLORS.trendAverage, type: "dashed" } },
        ],
      },
    }],
  }, true);
}

function renderWeights() {
  if (!weightEl.value || !hasResourceViewData.value) { weightChart?.clear(); return; }
  if (!weightChart) weightChart = echarts.init(weightEl.value);

  if (resourceView.value === "composition") {
    const data = resourceTreemap.value;
    weightChart.setOption({
      aria: { enabled: true, decal: { show: false }, description: "已生成学习资源按类型和数量展示的矩形树图。" },
      tooltip: { ...tooltipStyle, formatter: ({ data: item }: any) => `<b>${item.name}</b><br/>已生成 ${item.value} 个` },
      color: ["#4F46E5", "#6366F1", "#8B5CF6", "#06B6D4", "#14B8A6", "#38BDF8"],
      series: [{
        type: "treemap",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        top: 2,
        right: 2,
        bottom: 2,
        left: 2,
        label: { show: true, color: "#FFFFFF", fontSize: 12, fontWeight: 700, formatter: ({ data: item }: any) => `${item.name}\n${item.value} 个` },
        upperLabel: { show: false },
        itemStyle: { borderColor: "#FFFFFF", borderWidth: 3, gapWidth: 2, borderRadius: 7 },
        data,
      }],
    }, true);
    return;
  }

  const data = rankResourceWeights(effectiveResourceWeights.value);
  if (!data.length) return;
  weightChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "资源推送权重按优先级从高到低排列的棒棒糖图。" },
    tooltip: { ...tooltipStyle, trigger: "item" },
    grid: { left: 60, right: 24, top: 10, bottom: 22 },
    xAxis: { type: "value", axisLabel: { ...axisLabel, formatter: (value: number) => Number(value).toFixed(1) }, splitLine },
    yAxis: { type: "category", inverse: true, data: data.map((d) => d.label), axisLabel: { ...axisLabel, fontSize: 11 }, axisLine },
    series: [{
      type: "bar",
      silent: true,
      data: data.map((d) => ({
        value: d.value,
        itemStyle: { color: d.isTop ? "rgba(139,92,246,0.38)" : "rgba(99,102,241,0.26)", borderRadius: 2 },
      })),
      barWidth: 3,
      animationDelay: (idx: number) => idx * 60,
    }, {
      type: "scatter",
      symbolSize: 16,
      data: data.map((d, index) => ({ value: [d.value, index], itemStyle: { color: d.isTop ? DASHBOARD_CHART_COLORS.weight : DASHBOARD_CHART_COLORS.weightSecondary } })),
      label: { show: true, position: "right", color: DASHBOARD_COLORS.ink, fontSize: 12, formatter: ({ value }: any) => Number(value[0]).toFixed(1) },
    }],
  }, true);
}

function renderWeekdayRhythm() {
  if (!rhythmEl.value || !hasWeekdayRhythm.value) { rhythmChart?.clear(); return; }
  if (!rhythmChart) rhythmChart = echarts.init(rhythmEl.value);
  const data = weekdayRhythm.value;
  const colors = DASHBOARD_CHART_COLORS.rhythm;
  rhythmChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "最近学习记录按星期聚合的学习时长极坐标柱状图。" },
    title: {
      text: weekdayPeak.value?.label ?? "",
      subtext: formatCompactMinutes(weekdayPeak.value?.minutes ?? 0),
      left: "center",
      top: "43%",
      itemGap: 2,
      textStyle: { color: DASHBOARD_COLORS.ink, fontSize: 13, fontWeight: 700 },
      subtextStyle: { color: DASHBOARD_COLORS.muted, fontSize: 10, fontWeight: 500 },
    },
    tooltip: {
      ...tooltipStyle,
      trigger: "item",
      formatter: ({ dataIndex }: any) => {
        const item = data[dataIndex];
        return `<b>${item.label}</b><br/>学习 ${item.minutes} 分钟<br/>${item.count} 次活动`;
      },
    },
    polar: { radius: ["30%", "72%"], center: ["50%", "50%"] },
    radiusAxis: {
      type: "value",
      splitNumber: 4,
      axisLabel: { show: false },
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: DASHBOARD_COLORS.grid, opacity: 0.72 } },
    },
    angleAxis: {
      type: "category",
      data: data.map((item) => item.label),
      axisLabel: { color: DASHBOARD_COLORS.ink, fontSize: 12, fontWeight: 600, margin: 10 },
      axisTick: { show: false },
      axisLine: { show: false },
      splitLine: { show: false },
    },
    series: [{
      type: "bar",
      coordinateSystem: "polar",
      roundCap: true,
      barWidth: 10,
      showBackground: true,
      backgroundStyle: { color: "rgba(219,234,254,0.52)", borderRadius: 8 },
      data: data.map((item, index) => ({ value: item.minutes, itemStyle: { color: colors[index], borderRadius: 8 } })),
    }],
  }, true);
}

function renderMistakeMatrix() {
  if (!mistakeMatrixEl.value || !hasMistakeMatrix.value) { mistakeMatrixChart?.clear(); return; }
  if (!mistakeMatrixChart) mistakeMatrixChart = echarts.init(mistakeMatrixEl.value);
  const matrix = mistakeMatrix.value;
  const knowledgePointLabels = matrix.knowledgePoints.map((kpId) => localizeKnowledgePointLabel(kpId));
  const strongCellThreshold = Math.max(1, matrix.max * 0.55);
  mistakeMatrixChart.setOption({
    aria: { enabled: true, decal: { show: false }, description: "知识点与错题原因交叉统计的热力图，颜色越深表示错题数量越多。" },
    tooltip: {
      ...tooltipStyle,
      position: "top",
      formatter: ({ value }: any) => `<b>${knowledgePointLabels[value[1]]}</b><br/>${localizeDashboardLabel(matrix.categories[value[0]])}：${value[2]} 题`,
    },
    grid: { left: 92, right: 28, top: 22, bottom: 70 },
    xAxis: {
      type: "category",
      data: matrix.categories.map((category) => localizeDashboardLabel(category)),
      axisLabel: { ...axisLabel, interval: 0, rotate: matrix.categories.length > 5 ? 28 : 0, width: 70, overflow: "truncate" },
      splitArea: { show: true, areaStyle: { color: ["#FFFFFF", "#F8FBFF"] } },
      axisLine,
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: matrix.knowledgePoints.map((kpId) => localizeKnowledgePointLabel(kpId)),
      axisLabel: { ...axisLabel, width: 78, overflow: "truncate" },
      splitArea: { show: true, areaStyle: { color: ["#FFFFFF", "#F8FBFF"] } },
      axisLine,
    },
    visualMap: {
      min: 0,
      max: Math.max(1, matrix.max),
      show: false,
      inRange: { color: DASHBOARD_CHART_COLORS.matrix },
    },
    series: [{
      type: "heatmap",
      data: matrix.data.map((value) => ({
        value,
        label: { color: Number(value[2]) >= strongCellThreshold ? "#FFFFFF" : DASHBOARD_COLORS.ink },
      })),
      label: { show: true, color: DASHBOARD_COLORS.ink, fontSize: 11, formatter: ({ value }: any) => value[2] || "" },
      itemStyle: { borderColor: "#FFFFFF", borderWidth: 2, borderRadius: 4 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(37,99,235,0.22)" } },
    }],
  }, true);
}

watch([masteryView, assessmentView, resourceView], async () => {
  await nextTick();
  renderMastery();
  renderAssessTrend();
  renderWeights();
});
// ── 工具函数 ────────────────────────────────────────────
function heatColor(level: number): string {
  return DASHBOARD_CHART_COLORS.heatmap[level] || DASHBOARD_CHART_COLORS.heatmap[0];
}
function trendIcon(t: string) { return t === "improving" ? "↑" : t === "declining" ? "↓" : "→"; }
function trendColor(t: string) { return t === "improving" ? "#14B8A6" : t === "declining" ? "#F87171" : "#64748B"; }
function eventLabel(t: string) { const m: Record<string,string> = { profile_snapshot:"画像更新", path_adjustment:"路径调整", mistake_recorded:"错题记录", assessment:"练习测验", resource_generated:"资源生成" }; return m[t]||t; }
function eventColor(t: string) { const m: Record<string,string> = DASHBOARD_CHART_COLORS.activity; return m[t] || DASHBOARD_COLORS.info; }
function formatTime(ts: number) { if (!ts) return "—"; const d = new Date(ts*1000); return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`; }

// ── 生命周期 ────────────────────────────────────────────
onMounted(async () => {
  mounted.value = false;
  await loadAll();
  mounted.value = true;
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => { if (!refreshing.value) loadAll(); }, 30000);
  }
  // 窗口 resize 时重绘图表
  window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
  window.removeEventListener("resize", handleResize);
  masteryChart?.dispose(); forecastChart?.dispose();
  errorPieChart?.dispose(); assessTrendChart?.dispose(); weightChart?.dispose();
  rhythmChart?.dispose(); mistakeMatrixChart?.dispose();
});

function handleResize() {
  masteryChart?.resize(); forecastChart?.resize();
  errorPieChart?.resize(); assessTrendChart?.resize(); weightChart?.resize();
  rhythmChart?.resize(); mistakeMatrixChart?.resize();
}

function toggleAutoRefresh() {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshTimer = setInterval(() => { if (!refreshing.value) loadAll(); }, 30000);
  } else if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null; }
}

function exitDashboard() {
  router.push({ name: "home" });
}
</script>

<template>
  <div class="dboard" :class="{ 'dboard--loaded': mounted }">
    <!-- 背景装饰层 -->
    <div class="dboard-bg-grid"></div>
    <div class="dboard-bg-glow"></div>

    <!-- ═════════════ 顶部 Header ═════════════ -->
    <header class="db-header">
      <div class="db-title-area">
        <div>
          <h1>学习效果评估大屏</h1>
        </div>
        <div class="db-live-dot" title="实时数据"></div>
      </div>
      <div class="db-header-right">
        <div class="db-update-time" v-if="lastUpdate">
          <Clock :size="14" />
          <span>{{ lastUpdate }}</span>
        </div>
        <button class="db-toggle-btn" :class="{ active: autoRefresh }" @click="toggleAutoRefresh">
          <Zap :size="14" />
          {{ autoRefresh ? "30s 自动" : "已暂停" }}
        </button>
        <button class="db-refresh-btn" :disabled="refreshing" @click="loadAll">
          <RefreshCcw :size="15" :class="{ spinning: refreshing }" />
          刷新
        </button>
        <button
          class="db-exit-btn"
          type="button"
          title="退出学习大屏并返回首页"
          @click="exitDashboard"
        >
          <LogOut :size="15" />
          退出大屏
        </button>
      </div>
    </header>

    <!-- ═════════════ 加载态 ═════════════ -->
    <div v-if="loading" class="db-loading">
      <div class="db-loading-ring"></div>
      <p>正在加载学习数据…</p>
    </div>

    <div v-else-if="error && !hasAnyDashboardData" class="db-error">
      <AlertTriangle :size="32" />
      <p>{{ error }}</p>
    </div>

    <!-- ═════════════ 大屏内容 ═════════════ -->
    <div v-else class="db-body">
      <!-- ── KPI 指标卡 ── -->
      <section class="db-kpi-row">
        <div class="kpi-card" style="--accent: #2563EB; --accent-rgb: 37,99,235;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><TrendingUp :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.mastery }}<small>%</small></span>
            <span class="kpi-label">平均掌握度</span>
          </div>
        </div>

        <div class="kpi-card" style="--accent: #14B8A6; --accent-rgb: 20,184,166;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><Flame :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.streak }}<small>天</small></span>
            <span class="kpi-label">连续打卡</span>
          </div>
        </div>

        <div class="kpi-card" style="--accent: #0EA5E9; --accent-rgb: 14,165,233;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><Activity :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.activities }}</span>
            <span class="kpi-label">学习行为数</span>
          </div>
        </div>

        <div class="kpi-card" style="--accent: #06B6D4; --accent-rgb: 6,182,212;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><BookOpen :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.resources }}</span>
            <span class="kpi-label">资源使用</span>
          </div>
        </div>

        <div class="kpi-card" style="--accent: #F87171; --accent-rgb: 248,113,113;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><AlertTriangle :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.mistakes }}</span>
            <span class="kpi-label">未解决错题</span>
          </div>
        </div>

        <div class="kpi-card" style="--accent: #6366F1; --accent-rgb: 99,102,241;">
          <div class="kpi-corner kpi-corner-tl"></div><div class="kpi-corner kpi-corner-br"></div>
          <div class="kpi-icon"><Target :size="18" /></div>
          <div class="kpi-body">
            <span class="kpi-value">{{ animatedValues.completeness }}<small>%</small></span>
            <span class="kpi-label">画像完整度</span>
          </div>
        </div>
      </section>

      <!-- ── AI 综合评估与策略调整（学习效果评估闭环：跟踪 → 大模型评估 → 动态调整） ── -->
      <section class="db-panel db-eval-panel" style="--delay: 0">
        <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
        <div class="db-panel-header">
          <Sparkles :size="16" />
          <span>AI 综合评估与策略调整</span>
          <div class="db-eval-actions">
            <button type="button" class="db-eval-btn" :disabled="evalLoading" @click="runAiEvaluation">
              <RefreshCcw v-if="!evalLoading" :size="13" />
              {{ evalLoading ? "评估生成中..." : (evalReport ? "重新评估" : "生成 AI 评估") }}
            </button>
            <button
              v-if="evalReport"
              type="button"
              class="db-eval-btn primary"
              :disabled="evalApplying"
              @click="applyEvalStrategy"
            >
              {{ evalApplying ? "应用中..." : "一键应用策略调整" }}
            </button>
          </div>
        </div>
        <div class="db-eval-flow" aria-label="AI 综合评估流程">
          <div class="db-eval-step">
            <span class="db-eval-step-index">01</span>
            <b>团团评估</b>
          </div>
          <span class="db-eval-arrow">→</span>
          <div class="db-eval-step">
            <span class="db-eval-step-index">02</span>
            <b>智狐调整</b>
          </div>
          <span class="db-eval-arrow">→</span>
          <div class="db-eval-step">
            <span class="db-eval-step-index">03</span>
            <b>球球校验</b>
          </div>
        </div>
        <div v-if="evalReport" class="db-eval-report markdown-body" v-html="evalReportHtml" />
        <p v-if="evalNote" class="db-eval-note">{{ evalNote }}</p>
      </section>

      <!-- ── 活动概览：热力图 + 行为时间线 ── -->
      <section class="db-activity-grid">
        <div class="db-panel db-panel-hero" style="--delay: 0">
          <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
          <div class="db-panel-header"><Activity :size="16" /><span>学习活跃热力图</span></div>
          <div class="db-heatmap">
            <div class="heatmap-months" aria-hidden="true">
              <span class="heatmap-weekday-spacer"></span>
              <span v-for="(week, wi) in heatmapWeeks" :key="wi">{{ heatmapMonthLabel(week, wi) }}</span>
            </div>
            <div class="heatmap-layout">
              <div class="heatmap-weekdays" aria-hidden="true"><span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span></div>
              <div class="heatmap-grid">
                <div v-for="(week, wi) in heatmapWeeks" :key="wi" class="heatmap-week">
                  <div v-for="(day, di) in week" :key="di" class="heatmap-cell"
                    :class="{ 'is-today': day && isToday(day.date), 'is-placeholder': !day }"
                    :style="{ background: day ? heatColor(day.level) : '#EFF6FF' }"
                    :title="day ? `${day.date} · ${day.count} 次 · ${day.minutes} 分钟` : ''"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="db-panel" style="--delay: 1">
          <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
          <div class="db-panel-header"><Clock :size="15" /><span>学习行为时间线</span></div>
          <div class="db-timeline-row">
            <article v-for="(evt, i) in timelineEvents" :key="i" class="timeline-event-card">
              <div class="timeline-event-head">
                <span class="timeline-event-dot" :style="{ background: eventColor(evt.type) }"></span>
                <b>{{ eventLabel(evt.type) }}</b>
                <time>{{ formatTime(evt.timestamp) }}</time>
              </div>
              <div v-if="evt.type === 'mistake_recorded'" class="timeline-mistake-detail">
                <p>
                  <span :class="evt.resolved ? 'is-resolved' : 'is-pending'">{{ evt.resolved ? '已解决' : '待复习' }}</span>
                  <b>{{ localizeDashboardLabel(evt.error_type) }}</b>
                  <em v-if="evt.kp_id">{{ evt.kp_id }}</em>
                </p>
                <small v-if="evt.question">{{ evt.question }}</small>
              </div>
              <p v-else-if="evt.description">{{ evt.description }}</p>
            </article>
            <div v-if="!timelineEvents.length" class="timeline-empty">暂无行为记录</div>
          </div>
        </div>
      </section>
      <!-- ── 主网格区域：左右对称 · 中间 Hero ── -->
      <section class="db-main-grid">
        <!-- ═══ 左列（3 小屏）═══ -->
        <div class="db-col db-col-left">
          <div class="db-panel db-left-chart-card db-area-profile" style="--delay: 0">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><Brain :size="15" /><span>八维学习画像</span></div>
            <div class="db-profile-grid" aria-label="八维学习画像评分卡">
              <div
                v-for="(row, index) in profileRows"
                :key="row.name"
                class="db-profile-row"
                :class="`tone-${row.tone}`"
                :style="{ '--profile-color': row.status === 'unknown' ? '#94A3B8' : DASHBOARD_CHART_COLORS.profile[index] }"
              >
                <div class="db-profile-meta">
                  <span>{{ row.name }}</span>
                  <b v-if="row.status !== 'unknown'">{{ row.value }} 分</b>
                </div>
                <div class="db-profile-track"><span :style="{ width: `${row.value}%` }"></span></div>
              </div>
            </div>
          </div>
          <div class="db-panel db-left-chart-card db-area-errors" style="--delay: 1">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><AlertTriangle :size="15" /><span>错题错因分布</span></div>
            <div ref="errorPieEl" class="db-chart-sm"></div>
          </div>
          <div class="db-panel db-left-chart-card db-area-weights" style="--delay: 2">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header">
              <BookOpen :size="15" /><span>资源推送策略权重</span>
              <div class="db-view-switch" aria-label="资源图表视图">
                <button type="button" :class="{ active: resourceView === 'weight' }" :aria-pressed="resourceView === 'weight'" @click="resourceView = 'weight'">推送权重</button>
                <button type="button" :class="{ active: resourceView === 'composition' }" :aria-pressed="resourceView === 'composition'" @click="resourceView = 'composition'">资源构成</button>
              </div>
            </div>
            <div v-show="hasResourceViewData" ref="weightEl" class="db-chart-sm"></div>
            <div v-if="!hasResourceViewData" class="db-empty-state">暂无已生成资源数据</div>
          </div>

          <!-- ── 左列补位：AI 错题智能洞察 ── -->
          <section class="db-insights-strip db-insights-compact db-area-insights" v-if="mistakeInsights">
        <div class="db-panel db-panel-hero" style="--delay: 0">
          <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
          <div class="db-panel-header">
            <Sparkles :size="16" />
            <span>AI 错题智能洞察</span>
            <span class="db-panel-tag" :class="mistakeInsights.source === 'llm' ? 'tag-llm' : 'tag-rule'">
              {{ mistakeInsights.source === 'llm' ? 'AI 生成' : '规则分析' }}
            </span>
          </div>
          <div class="db-insights-body">
            <div class="db-insights-overview">
              <div class="db-insights-score">
                <span>错题修复准备度</span>
                <strong>{{ Math.round(mistakeInsights.evaluation.overall_score * 100) }}</strong>
                <em>/100</em>
              </div>
              <div class="db-insights-evidence">
                <span><Sparkles :size="13" /> 多模态模型诊断</span>
                <b>{{ mistakeInsights.error_pattern }}</b>
                <p>{{ mistakeInsights.summary }}</p>
              </div>
            </div>
            <div class="db-insights-focus-grid">
              <article class="db-insights-focus-card">
                <h4><Image :size="14" /> 视觉化错因回放</h4>
                <div v-if="activeMistakeFocus" class="db-mistake-focus">
                  <div><b>{{ localizeKnowledgePointLabel(activeMistakeFocus.kp_id) }}</b><span>{{ activeMistakeFocus.error_count }} 题</span></div>
                  <p>{{ activeMistakeFocus.reason }}</p>
                  <button type="button" @click="openMistakeKnowledgePoint">在知识图谱中定位 <ArrowRight :size="13" /></button>
                </div>
                <p v-else class="db-insight-empty">暂无可回放的错因证据</p>
              </article>
              <article class="db-insights-focus-card">
                <h4><Layers3 :size="14" /> 多模态修复包</h4>
                <div v-if="mistakeMultimodalMaterials.length" class="db-insight-materials db-multimodal-materials">
                  <div v-for="m in mistakeMultimodalMaterials" :key="m.title">
                    <component :is="MULTIMODAL_MODE_META[normalizeMultimodalType(m.type) ?? 'document'].icon" :size="13" />
                    <div><b>{{ localizeLearningMaterialTitle(m.title) }}</b><small>{{ m.reason }}</small></div>
                  </div>
                </div>
                <p v-else class="db-insight-empty">等待生成视频、导图或代码任务</p>
              </article>
              <article class="db-insights-focus-card">
                <h4><Wand2 :size="14" /> 变式验证与回写</h4>
                <div v-if="mistakeInsights.recommendations.similar_questions.length" class="db-mistake-variant">
                  <span>{{ mistakeInsights.recommendations.similar_questions[0].bloom_level || '应用' }}</span>
                  <b>{{ mistakeInsights.recommendations.similar_questions[0].question }}</b>
                  <p>{{ mistakeInsights.recommendations.similar_questions[0].explanation }}</p>
                  <button type="button" @click="openMistakeBook">去完成变式练习 <ArrowRight :size="13" /></button>
                </div>
                <p v-else class="db-insight-empty">等待小龙生成针对性变式题</p>
              </article>
            </div>
            <div class="db-insights-loop"><Image :size="13" /><span>图解定位错因</span><ArrowRight :size="13" /><Code2 :size="13" /><span>代码/交互演练</span><ArrowRight :size="13" /><Wand2 :size="13" /><span>变式验证后回写画像</span></div>
          </div>
        </div>
      </section>
        </div>

        <!-- ═══ 中列（2 Hero 大屏）═══ -->
        <div class="db-col db-col-center">
          <!-- Hero 1: BKT 知识掌握度 — 核心数据 -->
          <div class="db-panel db-panel-hero db-area-mastery" style="--delay: 0">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header">
              <BookOpen :size="16" /><span>BKT 知识掌握度</span>
              <div class="db-view-switch" aria-label="知识掌握图表视图">
                <button type="button" :class="{ active: masteryView === 'mastery' }" :aria-pressed="masteryView === 'mastery'" @click="masteryView = 'mastery'">掌握度</button>
                <button type="button" :class="{ active: masteryView === 'comparison' }" :aria-pressed="masteryView === 'comparison'" @click="masteryView = 'comparison'">模型差异</button>
              </div>
            </div>
            <div v-show="hasMasteryViewData" ref="masteryEl" class="db-chart-xl"></div>
            <div v-if="!hasMasteryViewData" class="db-empty-state">{{ masteryView === 'mastery' ? '暂无 BKT 练习记录' : '暂无成对模型数据' }}</div>
          </div>
          <!-- Hero 2: 掌握度时光机 — AI 预测 -->
          <div class="db-panel db-panel-hero db-panel-forecast db-area-forecast" style="--delay: 1">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><TrendingUp :size="16" /><span>掌握度时光机 · 30 天预测</span>
              <span class="db-panel-tag" v-if="forecastData">当前 {{ Math.round(toRatio(forecastData.current_mastery) * 100) }}%</span>
            </div>
            <div v-show="forecastAvailable" ref="forecastEl" class="db-chart-xl"></div>
            <div v-if="!forecastAvailable" class="db-empty-state">完成一次知识点练习后生成预测</div>
            <div class="db-forecast-summary" v-if="forecastMilestones.length">
              <div class="db-milestone-list">
                <span v-for="milestone in forecastMilestones" :key="milestone.label">第 {{ milestone.day }} 天 · {{ milestone.label }}</span>
              </div>
            </div>
          </div>

          <div class="db-panel db-area-rhythm" style="--delay: 2">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><Activity :size="15" /><span>星期学习节奏</span><span class="db-panel-tag">{{ calendarSummary.totalMinutes }} 分钟</span></div>
            <div v-show="hasWeekdayRhythm" ref="rhythmEl" class="db-rhythm-chart"></div>
            <div v-if="!hasWeekdayRhythm" class="db-empty-state">暂无学习活动记录</div>
          </div>
        </div>

        <!-- ═══ 右列（3 小屏）═══ -->
        <div class="db-col db-col-right">
          <div class="db-panel db-area-mistake-matrix" style="--delay: 0">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><AlertTriangle :size="15" /><span>知识点 × 错因矩阵</span><span class="db-panel-tag">{{ mistakeMatrix.total }} 题</span></div>
            <div v-show="hasMistakeMatrix" ref="mistakeMatrixEl" class="db-mistake-matrix-chart"></div>
            <div v-if="!hasMistakeMatrix" class="db-empty-state">暂无可分析的错题矩阵</div>
          </div>
          <div class="db-panel db-area-recommend" style="--delay: 1">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header"><Target :size="15" /><span>薄弱知识点 · 多模态修复推送</span></div>
            <div class="db-recommend-carousel" v-if="currentRecommendationGroup">
              <div class="recommend-kp-head">
                <div>
                  <span>当前待补强知识点</span>
                  <strong>{{ currentRecommendationGroup.name }}</strong>
                </div>
                <em>{{ currentRecommendationGroup.resources.length }} 个资源</em>
              </div>
              <div class="recommend-kp-mastery">
                <span><i :style="{ width: `${Math.round(currentRecommendationMastery * 100)}%` }"></i></span>
                <b>掌握度 {{ Math.round(currentRecommendationMastery * 100) }}%</b>
              </div>
              <div class="recommend-mode-head"><span>多模态修复序列</span><b>{{ currentRecommendationFlow }}</b></div>
              <div class="recommend-mode-rail" aria-label="推荐的多模态学习方式">
                <div v-for="mode in currentRecommendationModes" :key="mode.type" :title="mode.hint">
                  <component :is="mode.icon" :size="14" /><span>{{ mode.label }}</span>
                </div>
              </div>
              <div class="recommend-resource-list">
                <article
                  v-for="resource in currentRecommendationGroup.resources"
                  :key="resource.resource_id || `${resource.kp_id}-${resource.reason}`"
                  role="button"
                  tabindex="0"
                  @click="openRecommendationResources(currentRecommendationGroup)"
                  @keyup.enter="openRecommendationResources(currentRecommendationGroup)"
                >
                  <div>
                    <strong>{{ resource.title || (resource.type ? localizeDashboardLabel(resource.type) : (resource.kind === 'resource' ? '匹配学习资源' : '生成学习资源')) }}</strong>
                    <span class="weak-kind" :class="resource.kind">{{ resource.kind === 'resource' ? '已有资源' : '需生成' }}</span>
                  </div>
                  <p>{{ resource.reason }}</p>
                </article>
              </div>
              <button class="recommend-resource-action" type="button" @click="openRecommendationResources(currentRecommendationGroup)">查看此知识点的多模态资源 <ArrowRight :size="14" /></button>
              <div class="recommend-pagination" v-if="recommendationGroups.length > 1">
                <button type="button" aria-label="上一个知识点" :disabled="recommendationPage === 0" @click="changeRecommendationPage(-1)">
                  <ChevronLeft :size="18" />
                </button>
                <div class="recommend-dots" aria-label="知识点页码">
                  <button
                    v-for="(_, index) in recommendationGroups"
                    :key="index"
                    type="button"
                    :class="{ active: recommendationPage === index }"
                    :aria-label="`第 ${index + 1} 个知识点`"
                    @click="recommendationPage = index"
                  ></button>
                </div>
                <button type="button" aria-label="下一个知识点" :disabled="recommendationPage >= recommendationGroups.length - 1" @click="changeRecommendationPage(1)">
                  <ChevronRight :size="18" />
                </button>
              </div>
            </div>
            <div v-else class="db-empty-state db-recommend-empty">暂无精准推送</div>
          </div>
          <div class="db-panel db-area-trend" style="--delay: 2">
            <div class="db-panel-corners"><span></span><span></span><span></span><span></span></div>
            <div class="db-panel-header">
              <Target :size="15" /><span>练习成绩趋势</span>
              <div class="db-view-switch" aria-label="练习成绩图表视图">
                <button type="button" :class="{ active: assessmentView === 'trend' }" :aria-pressed="assessmentView === 'trend'" @click="assessmentView = 'trend'">趋势</button>
                <button type="button" :class="{ active: assessmentView === 'distribution' }" :aria-pressed="assessmentView === 'distribution'" @click="assessmentView = 'distribution'">分布</button>
              </div>
            </div>
            <div v-show="hasAssessmentViewData" ref="assessTrendEl" class="db-chart-sm"></div>
            <div v-if="!hasAssessmentViewData" class="db-empty-state">暂无练习成绩</div>
          </div>
        </div>
      </section>

      
    </div>
  </div>
</template>

<style scoped>
/* ═════════════ 大屏全局 ═════════════ */
.dboard {
  position: relative;
  min-height: 100vh;
  background: linear-gradient(160deg, #fffdf8 0%, #fafaf9 50%, #fbf2e5 100%);
  color: #171d22;
  font-family: var(--sans-cn);
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

/* 背景网格层 */
.dboard-bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(233, 85, 20, 0.02) 1px, transparent 1px),
    linear-gradient(90deg, rgba(233, 85, 20, 0.02) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}

.dboard-bg-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 600px 400px at 15% 20%, rgba(233, 85, 20, 0.04), transparent),
    radial-gradient(ellipse 500px 350px at 85% 80%, rgba(233, 85, 20, 0.03), transparent),
    radial-gradient(ellipse 800px 500px at 50% 50%, rgba(255, 249, 239, 0.4), transparent);
  pointer-events: none;
  z-index: 0;
}

/* ═════════════ Header ═════════════ */
.db-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), transparent);
  border-bottom: 1px solid rgba(233, 85, 20, 0.1);
  flex-shrink: 0;
}

.db-title-area {
  display: flex;
  align-items: center;
  gap: 14px;
}

.db-title-area h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #171d22;
  letter-spacing: 1px;
}

.db-title-area p {
  margin: 2px 0 0;
  font-size: 11px;
  color: #62666a;
  letter-spacing: 1px;
}

.db-cross-link {
  margin-left: 10px;
  color: #ea5a1a;
  text-decoration: none;
  font-weight: 600;
}
.db-cross-link:hover { text-decoration: underline; }

/* ── AI 综合评估面板 ── */
.db-eval-panel { margin-bottom: 18px; }

.db-eval-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.db-eval-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid rgba(233, 85, 20, 0.4);
  background: transparent;
  color: #ea5a1a;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.db-eval-btn.primary {
  background: #ea5a1a;
  color: #fff;
  border-color: #ea5a1a;
}
.db-eval-btn:disabled { opacity: 0.55; cursor: wait; }

.db-eval-empty {
  margin: 10px 2px 2px;
  font-size: 12.5px;
  line-height: 1.8;
  color: #8a94a3;
}

.db-eval-report {
  margin-top: 12px;
  max-height: 380px;
  overflow-y: auto;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.66);
  border: 1px solid rgba(160, 120, 70, 0.18);
  font-size: 13px;
  line-height: 1.75;
}

.db-eval-note {
  margin: 10px 2px 0;
  font-size: 12.5px;
  font-weight: 600;
  color: #157347;
}

.db-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #2f9f6b;
  box-shadow: 0 0 8px rgba(47, 159, 107, 0.4);
  animation: livePulse 2s ease-in-out infinite;
  margin-left: 6px;
}

@keyframes livePulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

.db-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.db-update-time {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11.5px;
  color: #927b62;
  font-variant-numeric: tabular-nums;
}

.db-toggle-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.5);
  color: #927b62;
  font-size: 11.5px;
  cursor: pointer;
  transition: all 0.2s;
}

.db-toggle-btn.active {
  border-color: rgba(47, 159, 107, 0.3);
  color: #2f9f6b;
  background: rgba(47, 159, 107, 0.06);
  box-shadow: 0 2px 8px rgba(47, 159, 107, 0.08);
}

.db-refresh-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 14px;
  border: 1px solid rgba(233, 85, 20, 0.2);
  border-radius: 6px;
  background: linear-gradient(135deg, rgba(233, 85, 20, 0.06), rgba(217, 70, 11, 0.03));
  color: #e95514;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.db-refresh-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, rgba(233, 85, 20, 0.1), rgba(217, 70, 11, 0.06));
  box-shadow: 0 2px 12px rgba(233, 85, 20, 0.12);
}

.db-refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ═════════════ 加载/错误 ═════════════ */
.db-loading, .db-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #927b62;
  font-size: 14px;
  z-index: 1;
}

.db-loading-ring {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(233, 85, 20, 0.08);
  border-top-color: #e95514;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  box-shadow: 0 0 12px rgba(233, 85, 20, 0.08);
}

/* ═════════════ Body ═════════════ */
.db-body {
  position: relative;
  z-index: 1;
  flex: 1;
  width: min(100%, 1880px);
  margin: 0 auto;
  padding: 8px 12px 10px;
  overflow-y: auto;
}

/* ═════════════ KPI 行 ═════════════ */
.db-kpi-row {
  display: grid;
  grid-template-columns: repeat(6, minmax(128px, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.kpi-card {
  position: relative;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.5));
  border: 1px solid rgba(var(--accent-rgb), 0.12);
  border-radius: 8px;
  padding: 7px 10px;
  min-height: 80px;
  display: grid;
  grid-template-columns: 30px 1fr;
  grid-template-rows: 1fr auto;
  gap: 6px 8px;
  transition: all 0.3s;
  overflow: hidden;
  backdrop-filter: blur(4px);
}

.kpi-card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0.5;
}

.kpi-card:hover {
  border-color: rgba(var(--accent-rgb), 0.3);
  box-shadow: 0 4px 20px rgba(var(--accent-rgb), 0.08);
  transform: translateY(-2px);
}

/* 角标装饰 */
.kpi-corner {
  position: absolute;
  width: 8px;
  height: 8px;
  border: 1.5px solid var(--accent);
  opacity: 0.5;
}
.kpi-corner-tl { top: 3px; left: 3px; border-right: none; border-bottom: none; }
.kpi-corner-br { bottom: 3px; right: 3px; border-left: none; border-top: none; }

.kpi-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--accent-rgb), 0.1);
  color: var(--accent);
  box-shadow: 0 2px 8px rgba(var(--accent-rgb), 0.08);
}

.kpi-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.kpi-value {
  font-size: 24px;
  font-weight: 700;
  color: #171d22;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.kpi-value small {
  font-size: 14px;
  font-weight: 400;
  margin-left: 2px;
  opacity: 0.5;
}

.kpi-label {
  font-size: 11px;
  color: #62666a;
  letter-spacing: 0.5px;
}

.kpi-meta {
  grid-column: 1 / -1;
  font-size: 9.5px;
  color: #927b62;
  border-top: 1px solid rgba(var(--accent-rgb), 0.08);
  padding-top: 4px;
  font-variant-numeric: tabular-nums;
}

/* ═════════════ 活动概览 ═════════════ */
.db-activity-grid {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(520px, 1.4fr);
  gap: 8px;
  margin-bottom: 8px;
}

.db-activity-grid .db-panel {
  min-height: 136px;
}
/* ═════════════ 主网格：左右对称 + 中间 Hero ═════════════ */
.db-main-grid {
  display: grid;
  grid-template-columns: minmax(270px, 0.9fr) minmax(520px, 1.55fr) minmax(300px, 1fr);
  gap: 8px;
  align-items: stretch;
}

.db-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100%;
}
.db-col-left {
  height: 100%;
}

.db-left-chart-card {
  flex: 1 1 0;
  min-height: 220px;
}

.db-left-chart-card .db-chart-sm {
  flex: 1;
  height: auto;
  min-height: 178px;
}
.db-col-center {
  min-height: 100%;
}

.db-panel-forecast {
  min-height: 0;
}

.db-panel-forecast .db-chart-xl {
  height: 220px;
  min-height: 0;
}

.db-empty-state {
  min-height: 132px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px dashed rgba(233, 85, 20, 0.16);
  background: rgba(255, 255, 255, 0.38);
  color: #927b62;
  font-size: 12px;
}

.db-panel-forecast .db-empty-state {
  min-height: 190px;
}

/* Hero 面板：中间大屏更突出 */
.db-panel-hero {
  border-color: rgba(233, 85, 20, 0.14);
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.85), rgba(255, 253, 248, 0.6));
  box-shadow: 0 2px 16px rgba(233, 85, 20, 0.03);
}

.db-panel-hero:hover {
  border-color: rgba(233, 85, 20, 0.22);
  box-shadow: 0 4px 28px rgba(233, 85, 20, 0.06);
}

.db-panel-hero .db-panel-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  color: #171d22;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.db-panel-hero .db-panel-header svg {
  color: #e95514;
}

/* ═════════════ 面板 ═════════════ */
.db-panel {
  position: relative;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.72), rgba(255, 253, 248, 0.42));
  border: 1px solid rgba(233, 85, 20, 0.08);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  opacity: 0;
  transform: translateY(12px);
  transition: opacity 0.5s ease, transform 0.5s ease, border-color 0.3s, box-shadow 0.3s;
  transition-delay: calc(var(--delay, 0) * 0.08s);
  backdrop-filter: blur(4px);
}

.dboard--loaded .db-panel {
  opacity: 1;
  transform: translateY(0);
}

.db-panel:hover {
  border-color: rgba(233, 85, 20, 0.15);
  box-shadow: 0 4px 24px rgba(233, 85, 20, 0.04);
}

/* 四角装饰 */
.db-panel-corners span {
  position: absolute;
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(233, 85, 20, 0.2);
}
.db-panel-corners span:nth-child(1) { top: -1px; left: -1px; border-right: none; border-bottom: none; border-top-left-radius: 8px; }
.db-panel-corners span:nth-child(2) { top: -1px; right: -1px; border-left: none; border-bottom: none; border-top-right-radius: 8px; }
.db-panel-corners span:nth-child(3) { bottom: -1px; left: -1px; border-right: none; border-top: none; border-bottom-left-radius: 8px; }
.db-panel-corners span:nth-child(4) { bottom: -1px; right: -1px; border-left: none; border-top: none; border-bottom-right-radius: 8px; }

.db-panel-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  color: #171d22;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.db-panel-header svg {
  color: #e95514;
}

.db-panel-tag {
  margin-left: auto;
  font-size: 10.5px;
  font-weight: 400;
  color: #62666a;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(233, 85, 20, 0.04);
  border: 1px solid rgba(233, 85, 20, 0.08);
  font-variant-numeric: tabular-nums;
}

/* ═════════════ 图表尺寸 ═════════════ */
.db-chart-sm { height: 106px; width: 100%; }
.db-chart-md { height: 148px; width: 100%; }
.db-chart-lg { height: 188px; width: 100%; }
.db-chart-xl { height: 190px; width: 100%; }

/* ═════════════ 预测摘要 ═════════════ */
.db-forecast-summary {
  margin-top: 8px;
  padding: 7px 10px;
  background: rgba(233, 85, 20, 0.03);
  border-left: 2px solid rgba(233, 85, 20, 0.3);
  border-radius: 0 6px 6px 0;
  font-size: 11px;
  color: #62666a;
  line-height: 1.5;
}

/* ═════════════ 热力图 ═════════════ */
.db-heatmap {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.heatmap-grid {
  display: flex;
  flex: 1;
  align-items: stretch;
  gap: 3px;
  overflow: hidden;
  padding: 2px 0;
  min-height: 96px;
}

.heatmap-week {
  display: grid;
  grid-template-rows: repeat(7, minmax(0, 1fr));
  flex: 1 1 0;
  min-width: 0;
  gap: 3px;
}

.heatmap-cell {
  width: 100%;
  height: 100%;
  min-height: 8px;
  border-radius: 3px;
  flex-shrink: 0;
  transition: box-shadow 0.2s;
}
.heatmap-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: #927b62;
  justify-content: flex-end;
}

.heatmap-legend .heatmap-cell {
  width: 10px;
  height: 10px;
  min-height: 10px;
  border-radius: 2px;
  flex: 0 0 auto;
  transition: box-shadow 0.2s;
}


.heatmap-meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding-top: 5px;
  border-top: 1px solid rgba(233, 85, 20, 0.05);
}

.heatmap-stats b { color: #e95514; margin: 0 2px; font-variant-numeric: tabular-nums; }
.heatmap-stats div { display: flex; align-items: center; gap: 4px; }

/* ═════════════ 信号面板 ═════════════ */
.db-signals {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 6px;
}

.signal-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 8px;
  background: rgba(233, 85, 20, 0.02);
  border-radius: 6px;
  border-left: 2px solid rgba(233, 85, 20, 0.25);
}

.signal-name { font-size: 10.5px; color: #927b62; }
.signal-value { font-size: 13px; font-weight: 700; color: #171d22; font-variant-numeric: tabular-nums; }
.signal-detail { font-size: 9.5px; color: #927b62; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.db-adjustments {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.adjustment-item {
  padding: 5px 8px;
  background: rgba(47, 159, 107, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(47, 159, 107, 0.1);
}

.adj-label { font-size: 10.5px; color: #2f9f6b; font-weight: 600; margin-bottom: 2px; }
.adj-reason { font-size: 9.5px; color: #927b62; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.db-strategy-meta {
  margin-top: 5px;
  text-align: center;
  font-size: 10px;
  color: #927b62;
  padding: 5px;
  background: rgba(233, 85, 20, 0.02);
  border-radius: 6px;
  font-variant-numeric: tabular-nums;
}

.db-strategy-meta b { color: #e95514; font-size: 13px; }

/* ═════════════ 薄弱知识点 ═════════════ */
.db-weak-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.weak-item {
  padding: 6px 8px;
  background: rgba(179, 65, 58, 0.02);
  border-radius: 6px;
  border-left: 2px solid rgba(179, 65, 58, 0.3);
}

.weak-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 3px;
}

.weak-kp { font-size: 10.5px; font-weight: 600; color: #171d22; }

.weak-kind {
  font-size: 9.5px;
  padding: 1px 6px;
  border-radius: 3px;
}

.weak-kind.resource { background: rgba(47, 159, 107, 0.1); color: #2f9f6b; }
.weak-kind.generate { background: rgba(216, 146, 41, 0.1); color: #d89229; }

.weak-reason { font-size: 9.5px; color: #927b62; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ═════════════ 全宽热力图通栏 ═════════════ */
.db-heatmap-strip {
  margin-top: 12px;
}

/* ═════════════ 底部时间线通栏 ═════════════ */
.db-timeline-strip {
  margin-top: 12px;
}

.db-timeline-horizontal {
  display: flex;
  align-items: flex-start;
  gap: 0;
  overflow-x: auto;
  padding: 10px 4px 6px;
  min-height: 82px;
}

.timeline-h-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 96px;
  position: relative;
}

.timeline-h-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  z-index: 1;
}

.timeline-h-line {
  position: absolute;
  top: 4px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: linear-gradient(90deg, rgba(233, 85, 20, 0.15), rgba(233, 85, 20, 0.05));
}

.timeline-h-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  margin-top: 8px;
}

.timeline-h-type { color: #171d22; font-weight: 500; font-size: 11px; }
.timeline-h-time { color: #b9aa95; font-size: 10px; font-variant-numeric: tabular-nums; }
.timeline-h-desc { color: #7a7268; font-size: 10.5px; line-height: 1.4; max-width: 92px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.timeline-empty { text-align: center; font-size: 12px; color: #b9aa95; padding: 20px; }

/* ═════════════ 中列补齐卡片 ═════════════ */
.db-center-action {
  flex: 1;
  min-height: 218px;
}

.center-action-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
}

.center-action-focus {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 7px;
  background: linear-gradient(90deg, rgba(233, 85, 20, 0.08), rgba(47, 159, 107, 0.05));
  border: 1px solid rgba(233, 85, 20, 0.1);
}

.center-action-focus span {
  font-size: 10.5px;
  color: #927b62;
}

.center-action-focus strong {
  min-width: 0;
  overflow: hidden;
  color: #171d22;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.center-action-focus em {
  color: #e95514;
  font-size: 10.5px;
  font-style: normal;
  font-variant-numeric: tabular-nums;
}

.center-action-grid {
  display: grid;
  flex: 1;
  grid-template-columns: 0.8fr 0.8fr 1.2fr;
  gap: 8px;
}

.center-action-metric {
  display: flex;
  min-height: 76px;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding: 9px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.46);
  border: 1px solid rgba(233, 85, 20, 0.08);
}

.center-action-metric b {
  color: #171d22;
  font-size: 22px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.center-action-metric.wide b {
  color: #2f9f6b;
  font-size: 14px;
  line-height: 1.2;
}

.center-action-metric span {
  color: #927b62;
  font-size: 10.5px;
}

.center-action-note {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 7px;
  background: rgba(47, 159, 107, 0.04);
  color: #7a7268;
  font-size: 10.5px;
}

.center-action-note span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* ═════════════ 响应式 ═════════════ */
@media (max-width: 1400px) {
  .db-kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .db-activity-grid { grid-template-columns: 1fr; }
  .db-main-grid { grid-template-columns: minmax(280px, 0.9fr) minmax(480px, 1.4fr); }
  .db-col-right {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .db-kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .db-activity-grid,
  .db-main-grid { grid-template-columns: 1fr; }
  .db-col-right { display: flex; }
  .db-panel-forecast { min-height: 0; }
  .db-panel-forecast .db-chart-xl { height: 190px; min-height: 0; }
  .center-action-grid { grid-template-columns: 1fr; }
  .center-action-focus {
    grid-template-columns: 1fr;
    align-items: flex-start;
  }
}

@media (max-width: 900px) {
  .db-kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .db-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }
  .heatmap-meta-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
/* 滚动条样式 */
.db-body::-webkit-scrollbar,
.db-timeline-horizontal::-webkit-scrollbar,
.heatmap-grid::-webkit-scrollbar { width: 4px; height: 4px; }
.db-body::-webkit-scrollbar-track,
.db-timeline-horizontal::-webkit-scrollbar-track { background: transparent; }
.db-body::-webkit-scrollbar-thumb,
.db-timeline-horizontal::-webkit-scrollbar-thumb { background: rgba(233, 85, 20, 0.12); border-radius: 2px; }

/* ===== AI 错题智能洞察 ===== */
.db-insights-strip {
  margin-top: 8px;
  margin-bottom: 0;
}


.db-col-left .db-insights-compact {
  flex: 0 0 auto;
}
.db-insights-compact {
  margin-top: 0;
  margin-bottom: 0;
}

.db-insights-compact .db-panel { padding: 8px; }
.db-insights-compact .db-panel-header { margin-bottom: 5px; }
.db-insights-compact .db-insights-body { padding: 0; }
.db-insights-compact .db-insights-summary {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  white-space: normal;
  font-size: 10.5px;
  line-height: 1.35;
  padding: 5px 7px;
  margin-bottom: 5px;
}
.db-insights-compact .db-insights-grid {
  grid-template-columns: 1fr;
  gap: 5px;
  margin-bottom: 5px;
}
.db-insights-compact .db-insights-card { padding: 6px 7px; }
.db-insights-compact .db-insights-title {
  font-size: 10.5px;
  margin-bottom: 4px;
}
.db-insights-compact .db-weak-kp-list,
.db-insights-compact .db-rec-mat-list { gap: 3px; }
.db-insights-compact .db-weak-kp-item,
.db-insights-compact .db-rec-mat-item {
  font-size: 10px;
  padding: 1px 0;
}
.db-insights-compact .db-eval-score-line { margin-bottom: 4px; }
.db-insights-compact .db-eval-num { font-size: 20px; }
.db-insights-compact .db-eval-tags {
  flex-direction: row;
  flex-wrap: wrap;
  gap: 3px;
}
.db-insights-compact .db-eval-tag {
  font-size: 9.5px;
  padding: 1px 5px;
}
.db-insights-compact .db-insights-suggestions {
  flex-wrap: wrap;
  gap: 4px;
  padding: 5px 7px;
}
.db-insights-compact .db-insights-sug-label,
.db-insights-compact .db-insights-sug-item { font-size: 10px; }
.db-insights-body {
  padding: 4px 0;
}

.db-insights-summary {
  font-size: 11.5px;
  line-height: 1.45;
  color: #444;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(234, 90, 26, 0.03);
  border: 1px solid rgba(234, 90, 26, 0.08);
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-insights-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}

.db-insights-card {
  padding: 8px;
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
}

.db-insights-title {
  font-size: 12px;
  font-weight: 600;
  color: #e95514;
  margin-bottom: 8px;
}

.db-weak-kp-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.db-weak-kp-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}

.db-weak-kp-name { color: #333; font-weight: 500; }
.db-weak-kp-count { color: #b3413a; font-weight: 600; font-size: 11px; }

.db-eval-score-line {
  display: flex;
  align-items: baseline;
  gap: 2px;
  margin-bottom: 8px;
}

.db-eval-num {
  font-size: 28px;
  font-weight: 700;
  color: #e95514;
  font-family: var(--serif);
}

.db-eval-unit {
  font-size: 13px;
  color: #927b62;
}

.db-eval-tags {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.db-eval-tag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
}

.db-eval-tag.red { background: rgba(179, 65, 58, 0.06); color: #b3413a; }

.db-rec-mat-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.db-rec-mat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.db-rec-mat-type {
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
}

.db-rec-mat-type.video { background: rgba(234, 90, 26, 0.12); color: #e95514; }
.db-rec-mat-type.doc { background: rgba(74, 107, 133, 0.12); color: #4a6b85; }
.db-rec-mat-type.project { background: rgba(47, 159, 107, 0.12); color: #2f9f6b; }

.db-rec-mat-title {
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-insights-suggestions {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  align-items: center;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.4);
  border: 1px dashed rgba(234, 90, 26, 0.15);
  overflow: hidden;
}

.db-insights-sug-label {
  font-size: 12px;
  font-weight: 600;
  color: #e95514;
}

.db-insights-sug-item {
  font-size: 12px;
  color: #666;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(234, 90, 26, 0.04);
}

.tag-llm { background: linear-gradient(90deg, #ea5a1a, #d89229) !important; color: #fff !important; }
.tag-rule { background: rgba(0,0,0,0.06) !important; color: #927b62 !important; }

@media (max-width: 1100px) {
  .db-insights-grid { grid-template-columns: 1fr; }
  .db-insights-summary,
  .db-insights-suggestions {
    white-space: normal;
  }
}

/* ===== 2026-07 学习大屏布局优化：内容不变，仅重组展现层级 ===== */
.dboard {
  background: #f5f1ea;
}

.dboard-bg-grid {
  opacity: 0.35;
  background-size: 56px 56px;
}

.dboard-bg-glow {
  opacity: 0.45;
}

.db-header {
  margin: 10px 12px 0;
  padding: 12px 16px;
  border: 0;
  border-radius: 12px;
  background: #302925;
  box-shadow: 0 10px 28px rgba(65, 45, 32, 0.14);
}

.db-title-area h1,
.db-header .db-title-area h1 {
  color: #fffaf5;
  font-size: 20px;
  letter-spacing: 0.5px;
}

.db-title-area p {
  color: #d2c5ba;
  letter-spacing: 0.4px;
}

.db-cross-link {
  color: #ffbd8f;
}

.db-update-time {
  color: #d8ccc3;
}

.db-toggle-btn {
  border-color: rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: #e8ddd5;
}

.db-toggle-btn.active {
  border-color: rgba(116, 214, 165, 0.35);
  background: rgba(47, 159, 107, 0.18);
  color: #9ee0bd;
  box-shadow: none;
}

.db-refresh-btn {
  border-color: #e95514;
  background: #e95514;
  color: #fff;
}

.db-refresh-btn:hover:not(:disabled) {
  background: #cf4810;
  box-shadow: 0 4px 12px rgba(233, 85, 20, 0.25);
}

.db-exit-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 13px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  color: #fffaf5;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s;
}

.db-exit-btn:hover {
  border-color: #ffbd8f;
  background: rgba(233, 85, 20, 0.2);
  color: #ffcfad;
}

.db-toggle-btn:focus-visible,
.db-refresh-btn:focus-visible,
.db-exit-btn:focus-visible,
.db-eval-btn:focus-visible {
  outline: 3px solid rgba(255, 189, 143, 0.55);
  outline-offset: 2px;
}

.db-body {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-areas:
    "kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi"
    "evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation"
    "mastery mastery mastery mastery mastery mastery mastery mastery rhythm rhythm rhythm rhythm"
    "mastery mastery mastery mastery mastery mastery mastery mastery mistakeMatrix mistakeMatrix mistakeMatrix mistakeMatrix"
    "forecast forecast forecast forecast forecast forecast forecast forecast mistakeMatrix mistakeMatrix mistakeMatrix mistakeMatrix"
    "activity activity activity activity activity activity activity activity activity activity activity activity"
    "profile profile profile errors errors errors weights weights weights trend trend trend"
    "insights insights insights insights insights insights insights insights recommend recommend recommend recommend";
  gap: 12px;
  width: min(100%, 1880px);
  padding: 12px;
}

.db-kpi-row {
  grid-area: kpi;
  margin: 0;
  gap: 10px;
}

.db-eval-panel {
  grid-area: evaluation;
  margin: 0;
}

.db-activity-grid {
  grid-area: activity;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
  gap: 12px;
  margin: 0;
}

.db-main-grid,
.db-col {
  display: contents;
}

.db-area-mastery { grid-area: mastery; }
.db-area-forecast { grid-area: forecast; }
.db-area-rhythm { grid-area: rhythm; }
.db-area-mistake-matrix { grid-area: mistakeMatrix; }
.db-area-profile { grid-area: profile; }
.db-area-errors { grid-area: errors; }
.db-area-weights { grid-area: weights; }
.db-area-trend { grid-area: trend; }
.db-area-insights { grid-area: insights; }
.db-area-recommend { grid-area: recommend; }

.kpi-card {
  min-height: 92px;
  padding: 12px;
  border: 1px solid #e8ded5;
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 5px 16px rgba(72, 50, 35, 0.05);
  backdrop-filter: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.kpi-card::before,
.kpi-corner {
  display: none;
}

.kpi-card:hover {
  transform: none;
  border-color: rgba(var(--accent-rgb), 0.32);
  box-shadow: 0 8px 20px rgba(var(--accent-rgb), 0.1);
}

.kpi-icon {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  box-shadow: none;
}

.kpi-value {
  font-size: 26px;
}

.kpi-label {
  color: #6f655e;
  font-size: 11.5px;
}

.kpi-meta {
  color: #93847a;
  font-size: 10px;
}

.db-panel {
  padding: 12px;
  border: 1px solid #e8ded5;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 5px 18px rgba(72, 50, 35, 0.045);
  backdrop-filter: none;
  transition: opacity 0.45s ease, transform 0.45s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.db-panel:hover {
  border-color: #ddcabb;
  box-shadow: 0 8px 24px rgba(72, 50, 35, 0.075);
}

.db-panel-corners {
  display: none;
}

.db-panel-hero {
  border-color: #e7d8cc;
  background: #fff;
  box-shadow: 0 6px 20px rgba(72, 50, 35, 0.05);
}

.db-panel-hero:hover {
  border-color: #ddc4b2;
  box-shadow: 0 9px 26px rgba(72, 50, 35, 0.08);
}

.db-panel-header,
.db-panel-hero .db-panel-header {
  margin-bottom: 10px;
  color: #2f2925;
  font-size: 12.5px;
  font-weight: 700;
}

.db-panel-tag {
  border-color: #eee1d6;
  border-radius: 999px;
  background: #faf6f1;
  color: #74675e;
}

.db-area-mastery {
  min-height: 360px;
  border-left: 3px solid #e95514;
}

.db-area-mastery .db-chart-xl {
  height: 310px;
}

.db-area-forecast {
  min-height: 260px;
}

.db-area-forecast .db-chart-xl {
  height: 190px;
}

.db-area-mistake-matrix,
.db-area-recommend,
.db-area-insights {
  min-height: 0;
}

.db-area-profile,
.db-area-errors,
.db-area-weights,
.db-area-trend {
  min-height: 258px;
}

.db-area-profile .db-chart-sm,
.db-area-errors .db-chart-sm,
.db-area-weights .db-chart-sm,
.db-area-trend .db-chart-sm {
  height: 205px;
  min-height: 205px;
}

.db-area-rhythm {
  min-height: 210px;
  border-color: #302925;
  background: #302925;
  color: #fffaf5;
  box-shadow: 0 12px 28px rgba(48, 41, 37, 0.2);
}

.db-area-rhythm:hover {
  border-color: #493d36;
  box-shadow: 0 14px 32px rgba(48, 41, 37, 0.24);
}

.db-area-rhythm .db-panel-header,
.db-area-rhythm .db-panel-header svg {
  color: #fffaf5;
}

.db-area-rhythm .db-panel-tag {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.08);
  color: #ddd0c6;
}

.db-area-rhythm .center-action-focus {
  border-color: rgba(255, 189, 143, 0.22);
  background: rgba(255, 255, 255, 0.08);
}

.db-area-rhythm .center-action-focus span,
.db-area-rhythm .center-action-metric span,
.db-area-rhythm .center-action-note {
  color: #d8ccc3;
}

.db-area-rhythm .center-action-focus strong,
.db-area-rhythm .center-action-metric b {
  color: #fffaf5;
}

.db-area-rhythm .center-action-focus em {
  color: #ffbd8f;
}

.db-area-rhythm .center-action-metric {
  border-color: rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.07);
}

.db-area-rhythm .center-action-metric.wide b {
  color: #9ee0bd;
}

.db-area-rhythm .center-action-note {
  background: rgba(47, 159, 107, 0.14);
}

.db-eval-panel .db-panel-header {
  flex-wrap: wrap;
}

.db-eval-empty {
  color: #756a62;
}

/* ═════════════ 图表与内容表达优化 ═════════════ */
.db-eval-flow {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.db-eval-step {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e8ded5;
  border-radius: 10px;
  background: #fffdfc;
}

.db-eval-step-index,
.center-action-index {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 50%;
  background: #f8e5d9;
  color: #e95514;
  font-size: 10px;
  font-weight: 800;
}

.db-eval-step div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.db-eval-step b { color: #302925; font-size: 12px; }
.db-eval-step small { color: #8c817a; font-size: 10.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.db-eval-arrow { color: #d4932f; font-size: 18px; }

.heatmap-months {
  display: flex;
  gap: 3px;
  height: 14px;
  padding-right: 1px;
  color: #8c817a;
  font-size: 9px;
  line-height: 1;
}

.heatmap-months > span:not(.heatmap-weekday-spacer) {
  flex: 1 1 0;
  min-width: 0;
  white-space: nowrap;
}

.heatmap-weekday-spacer { width: 18px; flex: 0 0 18px; }
.heatmap-layout { display: flex; flex: 1; gap: 5px; min-height: 96px; }
.heatmap-layout .heatmap-grid { flex: 1; min-height: 0; padding: 0; }
.heatmap-weekdays {
  display: grid;
  grid-template-rows: repeat(7, minmax(0, 1fr));
  width: 18px;
  flex: 0 0 18px;
  color: #8c817a;
  font-size: 9px;
  text-align: center;
}
.heatmap-weekdays span { display: grid; place-items: center; }
.heatmap-cell { box-shadow: none; }
.heatmap-cell.is-today { outline: 2px solid #302925; outline-offset: 1px; }

.db-activity-stream {
  height: 126px;
  overflow-y: auto;
  padding: 2px 6px 2px 2px;
  scrollbar-color: #d9cbbf transparent;
  scrollbar-width: thin;
}

.activity-stream-item { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 7px; }
.activity-stream-rail { display: flex; position: relative; align-items: center; flex-direction: column; }
.activity-stream-dot { width: 9px; height: 9px; margin-top: 5px; border: 2px solid #fffdfc; border-radius: 50%; box-shadow: 0 0 0 1px #e8ded5; z-index: 1; }
.activity-stream-line { width: 1px; min-height: 34px; flex: 1; background: #e8ded5; }
.activity-stream-content { min-width: 0; padding: 0 0 9px; }
.activity-stream-meta { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.activity-stream-type { color: #302925; font-size: 11px; font-weight: 700; }
.activity-stream-meta time { color: #8c817a; font-size: 9.5px; font-variant-numeric: tabular-nums; }
.activity-stream-content p { margin: 2px 0 0; color: #74675e; font-size: 10.5px; line-height: 1.4; overflow-wrap: anywhere; }

.db-profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  height: 205px;
}

.db-profile-row {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  gap: 5px;
  padding: 8px 9px;
  border: 1px solid #e8ded5;
  border-radius: 9px;
  background: #fffdfc;
}

.db-profile-meta { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.db-profile-meta span { color: #302925; font-size: 10.5px; font-weight: 700; }
.db-profile-meta b { color: #7562b8; font-size: 10.5px; white-space: nowrap; }
.db-profile-track { height: 6px; overflow: hidden; border-radius: 999px; background: #f5f1ea; }
.db-profile-track span { display: block; height: 100%; border-radius: inherit; background: #7562b8; }
.db-profile-row.tone-neutral .db-profile-meta b { color: #8c817a; }
.db-profile-row.tone-neutral .db-profile-track span { background: #b9ada4; }

.db-forecast-summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.db-milestone-list { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 5px; flex-shrink: 0; }
.db-milestone-list span { padding: 3px 7px; border: 1px solid #edc8ae; border-radius: 999px; background: #fff8f3; color: #e95514; font-size: 9.5px; font-weight: 700; white-space: nowrap; }

.center-action-flow {
  display: grid;
  grid-template-columns: repeat(7, auto);
  align-items: stretch;
  flex: 1;
  gap: 7px;
}

.center-action-step {
  display: flex;
  min-width: 0;
  flex: 1 1 0;
  flex-direction: column;
  gap: 5px;
  padding: 10px;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 9px;
  background: rgba(255,255,255,0.07);
}

.center-action-step small { color: #d8ccc3; font-size: 10px; }
.center-action-step strong { color: #fffaf5; font-size: 13px; line-height: 1.25; overflow-wrap: anywhere; }
.center-action-step em { color: #ffbd8f; font-size: 9.5px; font-style: normal; line-height: 1.35; }
.center-action-step .center-action-index { width: 26px; height: 26px; flex-basis: 26px; background: rgba(233,85,20,0.18); color: #ffbd8f; }
.center-action-arrow { display: grid; place-items: center; color: #ffbd8f; }

.db-strategy-matrix { overflow: hidden; border: 1px solid #e8ded5; border-radius: 9px; }
.strategy-matrix-head,
.strategy-matrix-row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.strategy-matrix-head { background: #f5f1ea; color: #74675e; font-size: 10px; font-weight: 700; }
.strategy-matrix-head span { padding: 6px 8px; }
.strategy-matrix-head span + span { border-left: 1px solid #e8ded5; }
.strategy-matrix-row + .strategy-matrix-row { border-top: 1px solid #e8ded5; }
.strategy-signal,
.strategy-adjustment { display: flex; min-width: 0; flex-direction: column; gap: 3px; padding: 7px 8px; }
.strategy-adjustment { border-left: 1px solid #e8ded5; background: rgba(47,143,107,0.035); }
.strategy-signal > div { display: flex; align-items: baseline; justify-content: space-between; gap: 5px; }
.strategy-signal b,
.strategy-adjustment b { color: #302925; font-size: 10.5px; }
.strategy-signal span { font-size: 10px; font-weight: 700; white-space: nowrap; }
.strategy-signal small,
.strategy-adjustment small { color: #8c817a; font-size: 9.5px; line-height: 1.35; overflow-wrap: anywhere; }
.strategy-adjustment b { color: #2f8f6b; }
.strategy-signal.is-empty,
.strategy-adjustment.is-empty { justify-content: center; color: #8c817a; font-size: 9.5px; }

.weak-item-header { justify-content: flex-start; }
.weak-priority { display: grid; place-items: center; width: 20px; height: 20px; flex: 0 0 20px; border-radius: 50%; background: #f8e5d9; color: #e95514; font-size: 8.5px; font-weight: 800; }
.weak-kp { min-width: 0; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.weak-mastery { display: grid; grid-template-columns: minmax(0, 1fr) 30px; align-items: center; gap: 6px; margin: 3px 0; }
.weak-mastery > span { height: 5px; overflow: hidden; border-radius: 99px; background: #f5f1ea; }
.weak-mastery i { display: block; height: 100%; border-radius: inherit; background: #d4932f; }
.weak-mastery b { color: #74675e; font-size: 9px; text-align: right; }
.weak-reason {
  display: -webkit-box;
  overflow: hidden;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

@media (max-width: 900px) {
  .db-eval-flow { grid-template-columns: 1fr; gap: 7px; }
  .db-eval-arrow { transform: rotate(90deg); justify-self: center; line-height: 1; }
  .db-forecast-summary { align-items: flex-start; flex-direction: column; }
  .db-milestone-list { justify-content: flex-start; }
  .center-action-flow { grid-template-columns: 1fr; }
  .center-action-arrow { transform: rotate(90deg); }
}

@media (max-width: 1500px) and (min-width: 901px) {
  .center-action-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .center-action-arrow { display: none; }
}

@media (max-width: 560px) {
  .db-profile-grid { grid-template-columns: 1fr; height: auto; }
  .db-profile-row { min-height: 70px; }
  .strategy-matrix-head,
  .strategy-matrix-row { grid-template-columns: 1fr; }
  .strategy-matrix-head span:last-child { display: none; }
  .strategy-adjustment { border-top: 1px solid #e8ded5; border-left: 0; }
}

@media (max-width: 1400px) {
  .db-body {
    grid-template-areas:
      "kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi kpi"
      "evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation evaluation"
      "mastery mastery mastery mastery mastery mastery mastery rhythm rhythm rhythm rhythm rhythm"
      "forecast forecast forecast forecast forecast forecast forecast mistakeMatrix mistakeMatrix mistakeMatrix mistakeMatrix mistakeMatrix"
      "activity activity activity activity activity activity activity activity activity activity activity activity"
      "profile profile profile profile profile profile errors errors errors errors errors errors"
      "weights weights weights weights weights weights trend trend trend trend trend trend"
      "insights insights insights insights insights insights insights recommend recommend recommend recommend recommend";
  }

  .db-area-mastery {
    min-height: 320px;
  }

  .db-area-mastery .db-chart-xl {
    height: 270px;
  }

  .db-area-profile,
  .db-area-errors,
  .db-area-weights,
  .db-area-trend {
    min-height: 240px;
  }
}

@media (max-width: 1100px) {
  .db-body {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas:
      "kpi"
      "evaluation"
      "mastery"
      "rhythm"
      "forecast"
      "mistakeMatrix"
      "activity"
      "profile"
      "errors"
      "weights"
      "trend"
      "insights"
      "recommend";
  }

  .db-activity-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .db-area-rhythm,
  .db-area-mistake-matrix,
  .db-area-recommend {
    min-height: auto;
  }
}

@media (max-width: 900px) {
  .db-header {
    margin: 8px 8px 0;
  }

  .db-header-right {
    width: 100%;
    flex-wrap: wrap;
  }

  .db-body {
    padding: 8px;
    gap: 10px;
  }

  .db-kpi-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .db-kpi-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .db-eval-actions {
    width: 100%;
    margin-left: 0;
  }

  .db-eval-btn {
    flex: 1;
    justify-content: center;
  }
}

/* ═════════════ 图表配色丰富与大字号精简层级 ═════════════ */
.kpi-label {
  font-size: 12.5px;
}

.kpi-meta {
  font-size: 11.5px;
  line-height: 1.45;
}

.db-panel-header,
.db-panel-hero .db-panel-header {
  font-size: 14.5px;
  line-height: 1.35;
}

.db-panel-tag {
  font-size: 11.5px;
}

.db-eval-step b {
  font-size: 13px;
}

.db-eval-step small,
.db-eval-empty,
.db-eval-note {
  font-size: 12px;
}

.db-eval-step-index,
.center-action-index {
  font-size: 11px;
}

.heatmap-months,
.heatmap-weekdays,
.heatmap-legend {
  font-size: 11px;
}

.activity-stream-type {
  font-size: 13px;
}

.activity-stream-meta time {
  font-size: 11px;
}

.activity-stream-content p {
  font-size: 12px;
  line-height: 1.5;
}

.db-profile-row {
  gap: 8px;
  padding: 10px 11px;
}

.db-profile-meta span {
  font-size: 12.5px;
}

.db-profile-meta b {
  color: var(--profile-color);
  font-size: 12px;
}

.db-profile-track {
  height: 8px;
  background: #e8edf3;
}

.db-profile-track span {
  background: var(--profile-color);
}

.db-profile-row.tone-neutral .db-profile-meta b {
  color: var(--profile-color);
}

.db-profile-row.tone-neutral .db-profile-track span {
  background: var(--profile-color);
}

.db-forecast-summary {
  font-size: 12px;
  line-height: 1.6;
  background: #eff6ff;
  border-left-color: #60a5fa;
}

.db-milestone-list span {
  border-color: #99f6e4;
  background: #f0fdfa;
  color: #0f766e;
  font-size: 11px;
}

.center-action-step small {
  font-size: 11.5px;
}

.center-action-step strong {
  font-size: 14px;
}

.center-action-step em,
.center-action-note {
  font-size: 11.5px;
}

.strategy-matrix-head {
  font-size: 12px;
}

.strategy-signal b,
.strategy-adjustment b {
  font-size: 12.5px;
}

.strategy-signal span,
.strategy-signal small,
.strategy-adjustment small,
.strategy-signal.is-empty,
.strategy-adjustment.is-empty {
  font-size: 11.5px;
  line-height: 1.5;
}

.db-strategy-meta {
  font-size: 11.5px;
}

.weak-priority {
  width: 24px;
  height: 24px;
  flex-basis: 24px;
  font-size: 10px;
}

.weak-kp {
  font-size: 12.5px;
}

.weak-kind {
  font-size: 11px;
}

.weak-mastery {
  grid-template-columns: minmax(0, 1fr) 38px;
  gap: 8px;
  margin: 6px 0;
}

.weak-mastery > span {
  height: 7px;
  background: #e8edf3;
}

.weak-mastery i {
  background: #3b82f6;
}

.weak-mastery b {
  font-size: 11px;
}

.weak-reason {
  font-size: 11.5px;
  line-height: 1.5;
}

.db-insights-compact .db-insights-summary,
.db-insights-summary {
  font-size: 12px;
  line-height: 1.5;
}

.db-insights-compact .db-insights-title,
.db-insights-title {
  font-size: 12.5px;
}

.db-insights-compact .db-weak-kp-item,
.db-insights-compact .db-rec-mat-item,
.db-weak-kp-item,
.db-rec-mat-item {
  font-size: 11.5px;
}

.db-insights-compact .db-eval-tag,
.db-eval-tag,
.db-rec-mat-type {
  font-size: 11px;
}

.db-insights-compact .db-insights-sug-label,
.db-insights-compact .db-insights-sug-item,
.db-insights-sug-label,
.db-insights-sug-item {
  font-size: 11.5px;
}

/* ═════════════ 内容精简与模块重排 ═════════════ */
.kpi-card {
  grid-template-rows: 1fr;
  align-items: center;
  min-height: 84px;
}

.kpi-body {
  justify-content: center;
  gap: 4px;
}

.db-eval-flow {
  margin-top: 8px;
}

.db-eval-step {
  justify-content: center;
  min-height: 58px;
}

.db-eval-step b {
  font-size: 15px;
}

.db-activity-grid {
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}

.db-activity-grid .db-panel {
  min-height: 0;
}

.db-heatmap {
  gap: 5px;
}

.heatmap-layout {
  min-height: 132px;
}

.heatmap-grid {
  min-height: 132px;
}

.heatmap-cell.is-placeholder {
  border: 1px solid #e2e8f0;
}

.db-timeline-row {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(220px, 270px);
  gap: 10px;
  overflow-x: auto;
  padding: 2px 2px 8px;
  scrollbar-width: thin;
  scrollbar-color: #d9cbbf transparent;
}

.timeline-event-card {
  min-width: 0;
  padding: 12px 14px;
  border: 1px solid #e8ded5;
  border-radius: 10px;
  background: #fffdfc;
}

.timeline-event-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.timeline-event-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.timeline-event-head b {
  color: #302925;
  font-size: 13px;
}

.timeline-event-head time {
  color: #8c817a;
  font-size: 11px;
}

.timeline-event-card p {
  margin: 7px 0 0;
  overflow: hidden;
  color: #74675e;
  font-size: 12px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-mistake-detail { display: grid; gap: 5px; }
.timeline-mistake-detail p { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; white-space: normal; }
.timeline-mistake-detail p span { padding: 2px 6px; border-radius: 999px; font-size: 10px; font-weight: 700; }
.timeline-mistake-detail .is-pending { color: #b45309; background: #fff7ed; }
.timeline-mistake-detail .is-resolved { color: #047857; background: #ecfdf5; }
.timeline-mistake-detail b { color: #302925; font-size: 11px; }
.timeline-mistake-detail em { color: #7c6f66; font-size: 10px; font-style: normal; }
.timeline-mistake-detail small { overflow: hidden; color: #70645c; font-size: 10px; line-height: 1.45; text-overflow: ellipsis; white-space: nowrap; }

.db-strategy-flow {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.strategy-flow-row {
  display: grid;
  grid-template-columns: minmax(0, .9fr) 24px minmax(0, 1.1fr);
  align-items: stretch;
  gap: 7px;
}

.strategy-signal-card,
.strategy-action-card {
  display: flex;
  min-width: 0;
  min-height: 64px;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 10px 11px;
  border: 1px solid #e8ded5;
  border-radius: 9px;
}

.strategy-signal-card {
  background: #fffdfc;
}

.strategy-action-card {
  background: rgba(47, 143, 107, .055);
  border-color: rgba(47, 143, 107, .18);
}

.strategy-signal-card span {
  color: #74675e;
  font-size: 12px;
}

.strategy-signal-card strong,
.strategy-action-card strong {
  color: #302925;
  font-size: 14px;
  line-height: 1.35;
}

.strategy-action-card strong {
  color: #2f8f6b;
}

.strategy-flow-arrow {
  display: grid;
  place-items: center;
  color: #d4932f;
  font-size: 18px;
}

.strategy-flow-empty {
  display: grid;
  min-height: 132px;
  place-items: center;
  border: 1px dashed #d9cbbf;
  border-radius: 10px;
  color: #8c817a;
  font-size: 14px;
}

.db-insights-compact .db-panel {
  padding: 14px;
}

.db-area-insights > .db-panel {
  height: 100%;
  box-sizing: border-box;
}

.db-insights-overview {
  display: grid;
  grid-template-columns: 145px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid #eadfd7;
  border-radius: 11px;
  background: #fffaf6;
}

.db-insights-score {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: end;
}

.db-insights-score span {
  grid-column: 1 / -1;
  color: #74675e;
  font-size: 12px;
  font-weight: 700;
}

.db-insights-score strong {
  color: #e95514;
  font-size: 38px;
  line-height: 1;
}

.db-insights-score em {
  color: #8c817a;
  font-size: 13px;
  font-style: normal;
}

.db-insights-overview > p {
  margin: 0;
  color: #302925;
  font-size: 13px;
  line-height: 1.65;
}

.db-insights-evidence {
  min-width: 0;
}

.db-insights-evidence > span,
.recommend-mode-head > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--db-primary, #2563eb);
  font-size: 11px;
  font-weight: 700;
}

.db-insights-evidence b {
  display: block;
  margin-top: 5px;
  color: var(--db-ink, #1e3a5f);
  font-size: 14px;
}

.db-insights-evidence p {
  display: -webkit-box;
  margin: 5px 0 0;
  overflow: hidden;
  color: var(--db-muted, #52677c);
  font-size: 12px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.db-insights-focus-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.db-insights-focus-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid #e8ded5;
  border-radius: 10px;
  background: #fff;
}

.db-insights-focus-card h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 10px;
  color: #302925;
  font-size: 14px;
}

.db-insights-focus-card h4 svg { color: var(--db-primary, #2563eb); }

.db-insight-list,
.db-insight-materials,
.db-insight-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.db-insight-list > div,
.db-insight-materials > div,
.db-insight-actions > div {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  color: #5f554e;
  font-size: 12px;
}

.db-insight-list > div {
  justify-content: space-between;
}

.db-insight-list b,
.db-insight-materials b,
.db-insight-actions b {
  min-width: 0;
  overflow: hidden;
  color: #302925;
  font-size: 12px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.db-insight-list span {
  color: #b64a42;
  font-weight: 700;
  white-space: nowrap;
}

.db-insight-actions span {
  display: grid;
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  place-items: center;
  border-radius: 50%;
  background: #f8e5d9;
  color: #e95514;
  font-size: 10px;
  font-weight: 800;
}

.db-insight-empty {
  margin: 0;
  color: #8c817a;
  font-size: 12px;
}

.db-mistake-focus > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.db-mistake-focus b,
.db-mistake-variant b {
  display: -webkit-box;
  overflow: hidden;
  color: var(--db-ink, #1e3a5f);
  font-size: 12px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.db-mistake-focus > div span,
.db-mistake-variant > span {
  flex: 0 0 auto;
  padding: 3px 6px;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 10px;
  font-weight: 700;
}

.db-mistake-focus p,
.db-mistake-variant p {
  display: -webkit-box;
  margin: 7px 0;
  overflow: hidden;
  color: var(--db-muted, #52677c);
  font-size: 11px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.db-mistake-focus button,
.db-mistake-variant button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--db-primary, #2563eb);
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
}

.db-multimodal-materials > div {
  align-items: flex-start;
}

.db-multimodal-materials > div > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--db-primary, #2563eb);
}

.db-multimodal-materials > div > div {
  min-width: 0;
}

.db-multimodal-materials small {
  display: -webkit-box;
  margin-top: 3px;
  overflow: hidden;
  color: var(--db-muted, #52677c);
  font-size: 10.5px;
  line-height: 1.35;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.db-insights-loop {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 10px;
  overflow: hidden;
  border: 1px dashed #bfdbfe;
  border-radius: 8px;
  background: #f8fbff;
  color: var(--db-primary, #2563eb);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.db-recommend-carousel {
  display: flex;
  min-height: 280px;
  flex-direction: column;
}

.recommend-kp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  background: #fff7f2;
}

.recommend-kp-head > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.recommend-kp-head span {
  color: #8c817a;
  font-size: 11px;
}

.recommend-kp-head strong {
  overflow: hidden;
  color: #302925;
  font-size: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recommend-kp-head em {
  padding: 4px 8px;
  border-radius: 999px;
  background: #fff;
  color: #e95514;
  font-size: 11px;
  font-style: normal;
  white-space: nowrap;
}

.recommend-kp-mastery {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin: 12px 2px;
}

.recommend-kp-mastery > span {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e8edf3;
}

.recommend-kp-mastery i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #3b82f6;
}

.recommend-kp-mastery b {
  color: #4f7c86;
  font-size: 12px;
  white-space: nowrap;
}

.recommend-mode-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 2px 0 7px;
}

.recommend-mode-head b {
  min-width: 0;
  overflow: hidden;
  color: var(--db-ink, #1e3a5f);
  font-size: 10.5px;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recommend-mode-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 5px;
  margin-bottom: 9px;
}

.recommend-mode-rail > div {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 4px;
  padding: 6px;
  border: 1px solid #dbeafe;
  border-radius: 7px;
  background: #f8fbff;
  color: var(--db-primary, #2563eb);
  font-size: 10px;
  font-weight: 700;
}

.recommend-mode-rail svg { flex: 0 0 auto; }
.recommend-mode-rail span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.recommend-resource-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
}

.recommend-resource-list article {
  padding: 10px 11px;
  border: 1px solid #e8ded5;
  border-radius: 9px;
  background: #fffdfc;
  cursor: pointer;
  transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
}

.recommend-resource-list article:hover,
.recommend-resource-list article:focus-visible {
  border-color: #93c5fd;
  box-shadow: 0 3px 10px rgba(37, 99, 235, .08);
  outline: none;
  transform: translateY(-1px);
}

.recommend-resource-list article > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.recommend-resource-list strong {
  min-width: 0;
  overflow: hidden;
  color: #302925;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recommend-resource-list p {
  display: -webkit-box;
  margin: 6px 0 0;
  overflow: hidden;
  color: #74675e;
  font-size: 11.5px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.recommend-resource-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  margin-top: 9px;
  padding: 8px 10px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: var(--db-primary, #2563eb);
  cursor: pointer;
  font-size: 11px;
  font-weight: 800;
}

.recommend-resource-action:hover { background: #dbeafe; }

.recommend-pagination {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.recommend-pagination > button {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border: 1px solid #e8ded5;
  border-radius: 50%;
  background: #fff;
  color: #302925;
  cursor: pointer;
}

.recommend-pagination > button:disabled {
  opacity: .35;
  cursor: not-allowed;
}

.recommend-dots {
  display: flex;
  justify-content: center;
  gap: 6px;
}

.recommend-dots button {
  width: 7px;
  height: 7px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: #d7cbc3;
  cursor: pointer;
  transition: width .2s ease, background .2s ease;
}

.recommend-dots button.active {
  width: 20px;
  background: #e95514;
}

.db-recommend-empty {
  min-height: 220px;
}

@media (max-width: 900px) {
  .db-insights-overview,
  .db-insights-focus-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .recommend-mode-rail { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .db-insights-loop { overflow-x: auto; }

  .strategy-flow-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .strategy-flow-arrow {
    transform: rotate(90deg);
  }
}

/* ═════════════ 蓝白清爽主题：最终视觉层 ═════════════ */
.dboard {
  --db-page-bg: #F4F8FF;
  --db-page-bg-soft: #EEF5FC;
  --db-surface: #FFFFFF;
  --db-surface-soft: #F8FBFF;
  --db-primary: #2563EB;
  --db-primary-dark: #0F3D6E;
  --db-sky: #0EA5E9;
  --db-cyan: #06B6D4;
  --db-teal: #14B8A6;
  --db-indigo: #6366F1;
  --db-risk: #F87171;
  --db-ink: #16324F;
  --db-muted: #64748B;
  --db-border: #DCE8F5;
  --db-grid: #E2E8F0;
  background: linear-gradient(160deg, var(--db-page-bg) 0%, #F8FBFF 48%, var(--db-page-bg-soft) 100%);
  color: var(--db-ink);
}

.dboard-bg-grid {
  opacity: .48;
  background-image:
    linear-gradient(rgba(37, 99, 235, .035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(37, 99, 235, .035) 1px, transparent 1px);
}

.dboard-bg-glow {
  opacity: .72;
  background:
    radial-gradient(ellipse 620px 390px at 12% 16%, rgba(14, 165, 233, .10), transparent),
    radial-gradient(ellipse 560px 360px at 88% 76%, rgba(99, 102, 241, .08), transparent);
}

.db-header {
  border: 1px solid rgba(255, 255, 255, .16);
  background: linear-gradient(135deg, #0F3D6E, #2563EB);
  box-shadow: 0 12px 30px rgba(37, 99, 235, .20);
}

.db-title-area h1,
.db-header .db-title-area h1 {
  color: #FFFFFF;
}

.db-title-area p {
  margin-top: 4px;
  color: #DBEAFE;
}

.db-cross-link {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border: 1px solid rgba(255, 255, 255, .20);
  border-radius: 999px;
  background: rgba(255, 255, 255, .10);
  color: #E0F2FE;
  font-size: 11px;
  font-weight: 700;
  text-decoration: none;
  transition: background .2s ease, border-color .2s ease;
}

.db-cross-link:hover {
  border-color: rgba(255, 255, 255, .45);
  background: rgba(255, 255, 255, .18);
}

.db-live-dot {
  background: #67E8F9;
  box-shadow: 0 0 10px rgba(103, 232, 249, .7);
}

.db-update-time {
  color: #DBEAFE;
}

.db-toggle-btn,
.db-exit-btn {
  border-color: rgba(255, 255, 255, .22);
  background: rgba(255, 255, 255, .10);
  color: #F8FAFC;
}

.db-toggle-btn.active {
  border-color: rgba(94, 234, 212, .42);
  background: rgba(20, 184, 166, .22);
  color: #CCFBF1;
}

.db-refresh-btn {
  border-color: #38BDF8;
  background: #0EA5E9;
  color: #FFFFFF;
}

.db-refresh-btn:hover:not(:disabled) {
  background: #0284C7;
  box-shadow: 0 5px 14px rgba(14, 165, 233, .28);
}

.db-exit-btn:hover {
  border-color: #BAE6FD;
  background: rgba(14, 165, 233, .28);
  color: #FFFFFF;
}

.db-toggle-btn:focus-visible,
.db-refresh-btn:focus-visible,
.db-exit-btn:focus-visible,
.db-eval-btn:focus-visible,
.recommend-pagination button:focus-visible,
.recommend-dots button:focus-visible {
  outline: 3px solid rgba(125, 211, 252, .72);
  outline-offset: 2px;
}

.db-loading,
.db-error,
.db-empty-state,
.timeline-empty,
.strategy-flow-empty,
.db-insight-empty {
  color: var(--db-muted);
}

.db-loading-ring {
  border-color: rgba(37, 99, 235, .12);
  border-top-color: var(--db-primary);
  box-shadow: 0 0 14px rgba(37, 99, 235, .12);
}

.kpi-card,
.db-panel,
.db-panel-hero {
  border-color: var(--db-border);
  background: rgba(255, 255, 255, .96);
  box-shadow: 0 7px 22px rgba(30, 64, 175, .065);
}

.kpi-card:hover,
.db-panel:hover,
.db-panel-hero:hover {
  border-color: #B9D5F2;
  box-shadow: 0 10px 28px rgba(30, 64, 175, .10);
}

.kpi-icon {
  background: rgba(var(--accent-rgb), .10);
  color: var(--accent);
}

.kpi-value,
.kpi-label,
.db-panel-header,
.db-panel-hero .db-panel-header,
.db-panel-header svg,
.db-panel-hero .db-panel-header svg {
  color: var(--db-ink);
}

.db-panel-header svg,
.db-panel-hero .db-panel-header svg {
  color: var(--db-primary);
}

.kpi-label {
  color: var(--db-muted);
}

.db-panel-tag {
  border-color: #D7E7F6;
  background: #F1F7FD;
  color: #41617E;
}

.db-area-mastery {
  border-left-color: var(--db-primary);
}

.db-eval-step,
.timeline-event-card,
.strategy-signal-card,
.db-insights-focus-card,
.recommend-resource-list article {
  border-color: var(--db-border);
  background: var(--db-surface);
}

.db-eval-step-index,
.center-action-index,
.db-insight-actions span,
.weak-priority {
  background: #DBEAFE;
  color: var(--db-primary);
}

.db-eval-step b,
.timeline-event-head b,
.strategy-signal-card strong,
.strategy-action-card strong,
.db-insights-focus-card h4,
.db-insight-list b,
.db-insight-materials b,
.db-insight-actions b,
.recommend-kp-head strong,
.recommend-resource-list strong {
  color: var(--db-ink);
}

.db-eval-arrow,
.strategy-flow-arrow,
.center-action-arrow {
  color: var(--db-sky);
}

.db-eval-btn {
  border-color: #BFDBFE;
  background: #EFF6FF;
  color: var(--db-primary);
}

.db-eval-btn:hover:not(:disabled) {
  border-color: #93C5FD;
  background: #DBEAFE;
}

.db-eval-btn.primary {
  border-color: var(--db-primary);
  background: var(--db-primary);
  color: #FFFFFF;
}

.db-eval-note,
.db-eval-report {
  border-color: var(--db-border);
  background: var(--db-surface-soft);
  color: var(--db-ink);
}

.heatmap-months,
.heatmap-weekdays,
.timeline-event-head time,
.timeline-event-card p,
.strategy-signal-card span,
.db-insights-score span,
.db-insights-score em,
.recommend-kp-head span {
  color: var(--db-muted);
}

.heatmap-cell.is-placeholder {
  border-color: #DCE8F5;
}

.heatmap-cell.is-today {
  outline-color: var(--db-primary);
}

.db-timeline-row {
  scrollbar-color: #B9D5F2 transparent;
}

.timeline-event-card,
.strategy-signal-card,
.strategy-action-card {
  box-shadow: 0 3px 12px rgba(37, 99, 235, .04);
}

.db-profile-meta span,
.db-profile-meta b {
  color: var(--db-ink);
}

.db-profile-track,
.weak-mastery > span,
.recommend-kp-mastery > span {
  background: #E6EEF7;
}

.db-forecast-summary {
  border-color: #D7E7F6;
  background: #F8FBFF;
  color: var(--db-muted);
}

.db-milestone-list span {
  border-color: #BFDBFE;
  background: #EFF6FF;
  color: var(--db-primary);
}

.db-area-rhythm {
  border-color: #BBD7F4;
  background: linear-gradient(145deg, #EFF6FF, #E0F2FE);
  color: var(--db-ink);
  box-shadow: 0 10px 26px rgba(37, 99, 235, .10);
}

.db-area-rhythm:hover {
  border-color: #93C5FD;
  box-shadow: 0 12px 30px rgba(37, 99, 235, .14);
}

.db-area-rhythm .db-panel-header,
.db-area-rhythm .db-panel-header svg,
.db-area-rhythm .center-action-step strong {
  color: var(--db-ink);
}

.db-area-rhythm .db-panel-header svg {
  color: var(--db-sky);
}

.db-area-rhythm .db-panel-tag {
  border-color: #BFDBFE;
  background: rgba(255, 255, 255, .72);
  color: var(--db-primary);
}

.center-action-step {
  border-color: #CFE2F5;
  background: rgba(255, 255, 255, .74);
}

.center-action-step small {
  color: var(--db-muted);
}

.db-area-rhythm .center-action-step .center-action-index {
  border-color: #BFDBFE;
  background: #DBEAFE;
  color: var(--db-primary);
}

.strategy-action-card {
  border-color: rgba(14, 165, 233, .24);
  background: rgba(14, 165, 233, .065);
}

.strategy-action-card strong {
  color: #087EA4;
}

.strategy-flow-empty {
  border-color: #C8DDF1;
  background: #F8FBFF;
}

.db-insights-overview {
  grid-template-columns: minmax(0, 1fr);
  border-color: #CFE2F5;
  background: linear-gradient(135deg, #EFF6FF, #F8FBFF);
}

.db-insights-score strong {
  color: var(--db-primary);
}

.db-insight-list span {
  color: var(--db-risk);
}

.db-rec-mat-type.video,
.tag-llm {
  background: linear-gradient(90deg, #2563EB, #06B6D4) !important;
  color: #FFFFFF !important;
}

.db-rec-mat-type.doc {
  background: #E0F2FE;
  color: #0369A1;
}

.db-rec-mat-type.project {
  background: #CCFBF1;
  color: #0F766E;
}

.tag-rule {
  background: #E2E8F0 !important;
  color: #475569 !important;
}

.recommend-kp-head {
  border: 1px solid #CFE2F5;
  background: linear-gradient(135deg, #EFF6FF, #F8FBFF);
}

.recommend-kp-head em {
  background: #FFFFFF;
  color: var(--db-primary);
}

.recommend-kp-mastery i {
  background: linear-gradient(90deg, var(--db-sky), var(--db-primary));
}

.recommend-kp-mastery b {
  color: #41617E;
}

.recommend-pagination > button {
  border-color: var(--db-border);
  background: #FFFFFF;
  color: var(--db-primary);
}

.recommend-pagination > button:hover:not(:disabled) {
  border-color: #93C5FD;
  background: #EFF6FF;
}

.recommend-dots button {
  background: #BFDBFE;
}

.recommend-dots button.active {
  background: var(--db-primary);
}

.db-view-switch {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  padding: 3px;
  border: 1px solid var(--db-border);
  border-radius: 9px;
  background: #F1F7FD;
}

.db-view-switch button {
  min-height: 28px;
  padding: 4px 10px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--db-muted);
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.db-view-switch button:hover {
  color: var(--db-primary);
}

.db-view-switch button.active {
  background: #FFFFFF;
  color: var(--db-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, .12);
}

.db-view-switch button:focus-visible {
  outline: 2px solid var(--db-sky);
  outline-offset: 1px;
}

.db-area-rhythm {
  min-height: 230px;
  border-color: var(--db-border);
  background: linear-gradient(145deg, #FFFFFF, #F4F9FF);
  color: var(--db-ink);
  box-shadow: 0 8px 24px rgba(37, 99, 235, .08);
}

.db-area-rhythm:hover {
  border-color: #BBD7F4;
  box-shadow: 0 10px 28px rgba(37, 99, 235, .11);
}

.db-area-rhythm .db-panel-header,
.db-area-rhythm .db-panel-header svg {
  color: var(--db-ink);
}

.db-area-rhythm .db-panel-header svg {
  color: var(--db-sky);
}

.db-rhythm-chart {
  width: 100%;
  height: 182px;
}

.db-area-mistake-matrix {
  min-height: 0;
}

.db-mistake-matrix-chart {
  width: 100%;
  height: 100%;
  min-height: 455px;
}

@media (max-width: 1400px) {
  .db-mistake-matrix-chart {
    min-height: 270px;
  }
}

@media (max-width: 1100px) {
  .db-mistake-matrix-chart {
    min-height: 330px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .db-panel,
  .kpi-card,
  .db-live-dot,
  .spinning,
  .db-loading-ring {
    animation: none !important;
    transition: none !important;
    transform: none !important;
  }
}

/* 图表边缘修正：保留最后一列、最后一行与今日描边的完整显示空间。 */
.heatmap-layout {
  padding-right: 2px;
  padding-bottom: 2px;
}

.heatmap-layout .heatmap-grid {
  overflow: visible;
  padding: 2px;
}
</style>
