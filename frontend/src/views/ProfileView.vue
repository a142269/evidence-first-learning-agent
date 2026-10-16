<script setup lang="ts">
/**
 * 学习画像 Dashboard（v6 视觉重构版）
 *
 * 保留功能：
 *   - 顶部 5 项核心指标（基于原有 4 项 + 新增「近 7 日提升」）
 *   - 8 维画像维度树（左侧保留为侧栏「画像速览」mini 列表）
 *   - 特征抽取证据链（侧栏「画像档案」展示）
 *   - 画像更新队列（弹窗 / 「最近更新」列表）
 *   - 版本对比 + 驱动动作（融入 AI 个性化建议卡）
 *   - 画像时光机、AI 诊断、证据溯源、画像预测等增强功能
 *   - 学习诊断报告抽屉
 *
 * 视觉风格：按运营图重设 dashboard 排版，左主右栏 + 卡片化布局
 */
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Activity, AlertTriangle, ArrowRight, BookOpen, Brain, Check, CheckCircle2,
  ChevronDown, ChevronRight, Clock, Compass, Download, ExternalLink, FileText,
  FlaskConical, GitBranch, Layers, Library, Lightbulb, LineChart,
  Loader2, MessageCircle, Pause, Play, RefreshCcw, ShieldAlert, ShieldCheck,
  Sparkles, Target, TrendingUp, Trophy, Users, X, Zap,
} from "lucide-vue-next";
import { Radar } from "vue-chartjs";
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(RadialLinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

import ArtCard from "@/components/companion/ArtCard.vue";
import SectionTitle from "@/components/companion/SectionTitle.vue";
import MarkdownBlock from "@/components/shared/MarkdownBlock.vue";
import { getLearnerPartner } from "@/constants/companion";
import { useSession } from "@/composables/useSession";
import { getAuthSession } from "@/utils/auth";
import { fetchCockpit } from "@/api/cockpit";
import { getAssessment, type AssessmentSummary } from "@/api/assessment";
import { getMistakesHeatmap, getMistakeInsights, type HeatmapResponse, type MistakeInsights } from "@/api/mistakes";
import { getGamification, addXp, unlockAchievement, dailyCheckin, type GamificationProfile } from "@/api/gamification";
import { getBktStatus, type BktStatus } from "@/api/cognitive";
import {
  getProfile,
  getProfileHistory,
  resetProfile,
  type ProfileData,
  type ProfileSnapshot,
} from "@/api/profile";
import {
  getDiagnosisReport,
  getRecommendations,
  getAdaptiveStrategy,
  getPeerComparison,
  getStudentOverview,
  getPersonalizationChain,
  type DiagnosisReportResponse,
  type RecommendationItem,
  type AdaptiveStrategyResponse,
  type PeerComparisonResponse,
  type PersonalizationChainResponse,
  type StudentOverviewResponse,
} from "@/api/insights";
import {
  getLearnerStateRecommendation,
  type LearnerStateRecommendation,
} from "@/api/learner_state";
import { localizeKnowledgePointLabel } from "@/views/dashboard/dashboardChartModel";
import { escapeHtml, renderMarkdown } from "@/utils/markdown";

const { userId, course } = useSession();
const router = useRouter();
const displayName = computed(() => getAuthSession()?.displayName || "杜同学");
const learnerPartner = computed(() => getLearnerPartner(userId.value, displayName.value));

const learnerArchetypeLabel = computed(() => {
  const p = profileData.value?.profile ?? {};
  const style = p.cognitive_style;
  if (typeof style === "string" && style.trim()) return style;
  if (style && typeof style === "object" && style.preference) return style.preference;
  return "AI 工程师学习路径";
});

// ============ 加载状态 ============
const loading = ref(true);
const resetting = ref(false);
const checkingIn = ref(false);
const checkinMsg = ref("");
const unlockingAch = ref(false);
const achMsg = ref("");
const profileData = ref<ProfileData | null>(null);
const snapshots = ref<ProfileSnapshot[]>([]);
const gamify = ref<GamificationProfile | null>(null);
const bkt = ref<BktStatus>({ user_id: "", masteries: {} });
const heatmap = ref<HeatmapResponse | null>(null);
const mistakeInsights = ref<MistakeInsights | null>(null);
const loadingInsights = ref(false);
const assessment = ref<AssessmentSummary | null>(null);
const recoItems = ref<RecommendationItem[]>([]);
const strategy = ref<AdaptiveStrategyResponse | null>(null);
const learnerReco = ref<LearnerStateRecommendation | null>(null);
const cockpitLedger = ref<any>(null);
const peerComparison = ref<PeerComparisonResponse | null>(null);
const overview = ref<StudentOverviewResponse | null>(null);

// ===== 学习者类型徽章 =====
const personalizationChain = ref<PersonalizationChainResponse | null>(null);
const currentWeaknesses = computed(() =>
  (personalizationChain.value?.bkt_summary.weakest ?? []).slice(0, 3).map((item, index) => ({
    ...item,
    rank: index + 1,
    masteryPct: Math.round(Number(item.mastery ?? 0) * 100),
  })),
);
const primaryWeakness = computed(() => currentWeaknesses.value[0] ?? null);
const archetypeBadge = computed(() => {
  if (!personalizationChain.value?.archetype) return null;
  const a = personalizationChain.value.archetype;
  return {
    code: a.code || "",
    archetype: a.archetype || a.name || "—",
    nickname: a.nickname || "",
    description: a.description || "",
    studyStrategy: a.study_strategy || a.strategy || "",
    color: archetypeColor(a.code || ""),
    cognitiveStyle: personalizationChain.value?.cognitive_style || "",
  };
});

function archetypeColor(code: string): string {
  const colors: Record<string, string> = {
    high_achiever: "#10b981",
    effort_outcome_gap: "#f59e0b",
    rhythm_broken: "#ef4444",
    habit_breakdown: "#dc2626",
    social_exploration_low: "#84a9b2",
    lifestyle_first: "#c6815d",
    stable_average: "#3b82f6",
    fast_convergence: "#06b6d4",
    stuck: "#f97316",
  };
  return colors[code] || "#ea5a1a";
}

// ============ 功能 1：画像时光机 ============
const timeMachineOpen = ref(false);
const diagnosisOpen = ref(false);
const archiveOpen = ref(false);
const currentSnapshotIndex = ref(0);
const isPlaying = ref(false);
const playInterval = ref<number | null>(null);

const historySnapshots = computed(() => {
  return snapshots.value.map((s, idx) => ({
    index: idx,
    version: s.version,
    timestamp: s.created_at,
    profile: s.profile,
    changedKeys: s.changed_keys || [],
  })).reverse();
});

const timeMachineProfile = computed(() => {
  const snap = historySnapshots.value[currentSnapshotIndex.value];
  return snap?.profile ?? {};
});

function playTimeMachine() {
  if (isPlaying.value) { pauseTimeMachine(); return; }
  isPlaying.value = true;
  playInterval.value = window.setInterval(() => {
    if (currentSnapshotIndex.value < historySnapshots.value.length - 1) {
      currentSnapshotIndex.value++;
    } else {
      currentSnapshotIndex.value = 0;
    }
  }, 1500);
}

function pauseTimeMachine() {
  isPlaying.value = false;
  if (playInterval.value) { clearInterval(playInterval.value); playInterval.value = null; }
}

function seekSnapshot(index: number) { currentSnapshotIndex.value = index; }
function closeTimeMachine() {
  pauseTimeMachine();
  timeMachineOpen.value = false;
  currentSnapshotIndex.value = 0;
}

// ============ AI 诊断结论（侧栏画像结论 / 风险 / 个性化建议 用） ============
const aiDiagnosis = computed(() => {
  const p = profile.value;
  const diagnoses: Array<{ type: "good" | "warn" | "info"; title: string; content: string; action?: string }> = [];

  const weakKps = Object.entries(bkt.value.masteries || {}).filter(([, v]) => v < 0.55);
  if (weakKps.length > 0) {
    diagnoses.push({
      type: "warn",
      title: "知识基础有薄弱点",
      content: `检测到 ${weakKps.length} 个知识点掌握度低于 55%，建议加强练习。`,
      action: "去练习",
    });
  } else if (Object.keys(bkt.value.masteries || {}).length > 0) {
    diagnoses.push({ type: "good", title: "知识基础扎实", content: "当前追踪的知识点掌握度良好，继续保持！" });
  }

  if (heatmap.value?.total_mistakes && heatmap.value.total_mistakes > 5) {
    diagnoses.push({
      type: "warn", title: "错题需要复习",
      content: `累计 ${heatmap.value.total_mistakes} 道错题，建议定期复习巩固。`,
      action: "去复习",
    });
  }

  if (assessment.value?.total_sessions) {
    const avgScore = assessment.value.quiz_avg_score ?? 0;
    if (avgScore >= 80) {
      diagnoses.push({ type: "good", title: "练习成绩优秀", content: `平均得分 ${avgScore} 分，学习效果显著。` });
    } else if (avgScore < 60) {
      diagnoses.push({
        type: "warn", title: "练习成绩待提升",
        content: `平均得分 ${avgScore} 分，建议调整学习策略。`, action: "查看建议",
      });
    }
  }

  const selfLearn = p.self_learning_ability?.self_learning ?? {};
  if (selfLearn.initiative === "高" && selfLearn.problem_solving === "强") {
    diagnoses.push({
      type: "good", title: "自主学习能力突出",
      content: "学习主动性强，问题解决能力优秀，适合挑战更高难度内容。",
    });
  }
  return diagnoses;
});

// ============ 能力雷达图 + 顶部「近 7 日趋势」数据 ============

function toPercent(value: number | undefined, invert = false): number {
  const normalized = Math.max(0, Math.min(1, Number(value ?? 0)));
  return Math.round((invert ? 1 - normalized : normalized) * 100);
}

function profileScore(value: any): number {
  const raw = typeof value === "number" ? value : value?.score;
  const score = Number(raw);
  return Number.isFinite(score) ? toPercent(score) : 0;
}

function hasProfileScore(value: any): boolean {
  if (value?.status === "unknown") return false;
  const raw = typeof value === "number" ? value : value?.score;
  return raw !== null && raw !== "" && Number.isFinite(Number(raw));
}

function mapPeerDimensions(source: Record<string, number> | undefined) {
  return {
    knowledge_base: toPercent(source?.knowledge_base),
    cognitive_style: toPercent(source?.cognitive_style),
    error_pattern: toPercent(source?.weak_points, true),
    learning_habit: toPercent(source?.time_management),
    learning_progress: toPercent(source?.learning_goal),
    interest_model: toPercent(source?.interaction_pattern),
    resource_preference: toPercent(source?.learning_preference),
    self_learning_ability: toPercent(source?.self_efficacy),
  };
}

const userRadarData = computed(() => {
  if (peerComparison.value?.dimensions) {
    return mapPeerDimensions(peerComparison.value.dimensions);
  }
  const p = profile.value;
  const masteries = bkt.value.masteries || {};
  const avgMastery = Object.values(masteries).length
    ? Object.values(masteries).reduce((a, b) => a + b, 0) / Object.values(masteries).length
    : profileScore(p.knowledge_base) / 100;
  const measuredErrorScore = hasProfileScore(p.error_pattern)
    ? 100 - profileScore(p.error_pattern)
    : assessment.value?.total_sessions && heatmap.value
      ? Math.max(0, 100 - heatmap.value.total_mistakes * 5)
      : 0;
  return {
    knowledge_base: Math.round(avgMastery * 100),
    cognitive_style: profileScore(p.cognitive_style),
    error_pattern: measuredErrorScore,
    learning_habit: profileScore(p.learning_habit),
    learning_progress: profileScore(p.learning_progress),
    interest_model: profileScore(p.interest_model),
    resource_preference: profileScore(p.resource_preference),
    self_learning_ability: calculateSelfLearningAbility(p.self_learning_ability),
  };
});

function calculateSelfLearningAbility(selfLearn: any): number {
  if (!selfLearn) return 0;
  const sl = selfLearn.self_learning ?? selfLearn;
  if (sl.status === "unknown") return 0;
  if (Number.isFinite(Number(sl.score))) return toPercent(Number(sl.score));
  let score = 50;
  if (sl.problem_solving === "强") score += 15;
  if (sl.problem_solving === "弱") score -= 15;
  if (sl.reflection === "强") score += 10;
  if (sl.initiative === "高") score += 15;
  if (sl.initiative === "低") score -= 10;
  if (sl.time_management === "优秀") score += 10;
  return Math.min(100, Math.max(0, score));
}

const trendSeries = computed(() => {
  const grouped = new Map<string, { timestamp: number; total: number; count: number }>();
  for (const item of overview.value?.assessment.recent ?? []) {
    if (!Number.isFinite(item.timestamp) || !Number.isFinite(item.score_pct)) continue;
    const key = item.display_date || new Date(item.timestamp * 1000).toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
    const current = grouped.get(key) ?? { timestamp: item.timestamp, total: 0, count: 0 };
    current.timestamp = Math.max(current.timestamp, item.timestamp);
    current.total += item.score_pct;
    current.count += 1;
    grouped.set(key, current);
  }
  const values = [...grouped.entries()]
    .map(([label, value]) => ({ label, timestamp: value.timestamp, value: Math.round(value.total / value.count) }))
    .sort((a, b) => a.timestamp - b.timestamp)
    .slice(-7);
  const points = values.map((item, index) => ({
    ...item,
    x: values.length === 1 ? 290 : 40 + index * (500 / Math.max(1, values.length - 1)),
    y: 180 - Math.max(0, Math.min(100, item.value)) * 1.28,
  }));
  const first = values[0]?.value ?? 0;
  const latest = values[values.length - 1]?.value ?? 0;
  const delta = latest - first;
  return {
    hasData: values.length >= 2,
    points,
    linePoints: points.map((point) => `${point.x},${point.y}`).join(" "),
    fillPoints: points.length >= 2
      ? `${points[0].x},180 ${points.map((point) => `${point.x},${point.y}`).join(" ")} ${points[points.length - 1].x},180`
      : "",
    summary: values.length >= 2
      ? `最新 ${latest}% · 较首期 ${delta >= 0 ? "+" : ""}${delta} 分`
      : "暂无可对比的真实测评数据",
  };
});

const radarChartData = computed(() => ({
  labels: DIMENSION_KEYS.map(k => DIMENSION_META[k].label),
  datasets: [
    {
      label: "我的画像",
      data: DIMENSION_KEYS.map(k => userRadarData.value[k as keyof typeof userRadarData.value]),
      backgroundColor: "rgba(230, 90, 26, 0.18)",
      borderColor: "#E65A1A",
      pointBackgroundColor: "#E65A1A",
      pointBorderColor: "#fff",
      pointHoverBackgroundColor: "#fff",
      pointHoverBorderColor: "#E65A1A",
    },
  ],
}));

const radarChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      min: 0, max: 100,
      ticks: { stepSize: 20, font: { size: 10 }, color: "#94a3b8", backdropColor: "transparent" },
      grid: { color: "rgba(148, 163, 184, 0.25)" },
      angleLines: { color: "rgba(148, 163, 184, 0.35)" },
      pointLabels: { font: { size: 11, weight: "bold" as const }, color: "#1f2937" },
    },
  },
  plugins: {
    legend: { position: "bottom" as const, labels: { padding: 14, usePointStyle: true, font: { size: 12 } } },
  },
};

// 雷达图派生统计（避免模板直接索引的 TS 问题）
type UserRadar = Record<"knowledge_base" | "cognitive_style" | "error_pattern" | "learning_habit" | "learning_progress" | "interest_model" | "resource_preference" | "self_learning_ability", number>;
const radarLeadCount = computed(() => DIMENSION_KEYS.filter((k) => (userRadarData.value as UserRadar)[k as keyof UserRadar] >= 70).length);
const radarLagCount = computed(() => DIMENSION_KEYS.filter((k) => (userRadarData.value as UserRadar)[k as keyof UserRadar] < 60).length);
const radarAvgScore = computed(() => Math.round(DIMENSION_KEYS.reduce((s, k) => s + (userRadarData.value as UserRadar)[k as keyof UserRadar], 0) / DIMENSION_KEYS.length));

// ============ 顶部 5 项指标 ============
const dashboardMetrics = computed(() => {
  const avgMasteryPct = overview.value?.summary.average_mastery_pct ?? (() => {
    const arr = Object.values(bkt.value.masteries || {});
    if (!arr.length) return 0;
    return Math.round((arr.reduce((a, b) => a + b, 0) / arr.length) * 100);
  })();

  const sessions = assessment.value?.total_sessions || 0;
  const activeDays = overview.value?.activity.active_days_30d ?? 0;
  const activity = Math.min(100, Math.round((activeDays / 30) * 100));
  const goalStability = toPercent(
    Number(overview.value?.profile.dimensions.learning_goal?.score)
      || peerComparison.value?.dimensions.learning_goal,
  );
  const groupMessages = overview.value?.collaboration.message_count
    ?? peerComparison.value?.metrics.group_messages_30d
    ?? 0;
  const collaboration = Math.min(100, Math.round((groupMessages / 12) * 100));
  const weeklyLift = overview.value?.assessment.week_score_change_pct
    ?? peerComparison.value?.metrics.weekly_lift;
  const trendValue = weeklyLift == null
    ? "—"
    : `${weeklyLift >= 0 ? "+" : ""}${weeklyLift.toFixed(1)}`;

  return [
    {
      key: "activity",
      label: "学习活跃度",
      value: String(activity),
      unit: "",
      sub: "活跃度较高",
      icon: Activity,
      bgColor: "#fff7ed",
      fgColor: "#E65A1A",
      delta: `${activeDays} 个活跃日`,
    },
    {
      key: "mastery",
      label: "知识掌握度",
      value: String(avgMasteryPct),
      unit: "%",
      sub: avgMasteryPct >= 70 ? "中等偏上" : avgMasteryPct >= 55 ? "中等" : "待提升",
      icon: BookOpen,
      bgColor: "#eff6ff",
      fgColor: "#2563eb",
    },
    {
      key: "goal",
      label: "目标稳定性",
      value: String(goalStability),
      unit: "%",
      sub: goalStability >= 70 ? "目标清晰" : goalStability > 0 ? "目标待加强" : "暂无数据",
      icon: Target,
      bgColor: "#fff0e7",
      fgColor: "#b94f32",
    },
    {
      key: "collab",
      label: "协作参与度",
      value: String(collaboration),
      unit: "%",
      sub: groupMessages > 0 ? `近30日 ${groupMessages} 条互动` : "近30日暂无互动",
      icon: Users,
      bgColor: "#f0fdf4",
      fgColor: "#16a34a",
    },
    {
      key: "trend",
      label: "近7日提升",
      value: trendValue,
      unit: weeklyLift == null ? "" : "分",
      sub: weeklyLift == null ? "暂无两周对比数据" : weeklyLift >= 0 ? "较上周提升" : "较上周回落",
      icon: TrendingUp,
      bgColor: "#fff7ed",
      fgColor: "#E65A1A",
      positive: weeklyLift != null && weeklyLift >= 0,
    },
  ];
});

// ============ 证据溯源 ============
const evidenceModalOpen = ref(false);
const selectedEvidence = ref<{ field: string; value: string; source: any } | null>(null);

function openEvidenceSource(fieldKey: string, fieldValue: string, sourceType: string) {
  selectedEvidence.value = {
    field: fieldKey,
    value: fieldValue,
    source: {
      type: sourceType,
      timestamp: Date.now() / 1000,
      details: getEvidenceDetails(fieldKey, sourceType),
    },
  };
  evidenceModalOpen.value = true;
}

function getEvidenceDetails(fieldKey: string, sourceType: string) {
  const details: Record<string, string> = {
    chat: "从 AI 对话中通过自然语言处理技术抽取",
    bkt: "基于贝叶斯知识追踪模型的概率计算",
    mistake: "从错题记录中统计分析得出",
    practice: "从练习行为数据中聚合分析",
    recommendation: "从推荐系统的匹配结果中关联",
  };
  return details[sourceType] || "系统自动分析生成";
}

function closeEvidenceModal() { evidenceModalOpen.value = false; selectedEvidence.value = null; }

// ============ 画像预测 ============
const predictionOpen = ref(false);

const futurePredictions = computed(() => {
  const predictions: Array<{ dim: string; label: string; current: string; predicted: string; days: number; confidence: number }> = [];
  const p = profile.value;

  const weakKps = Object.entries(bkt.value.masteries || {}).filter(([, v]) => v < 0.7);
  if (weakKps.length > 0) {
    predictions.push({
      dim: "knowledge_base", label: "知识基础",
      current: `${weakKps.length} 个薄弱知识点`,
      predicted: "薄弱知识点减少 50%", days: 7, confidence: 75,
    });
  }
  if (heatmap.value?.total_mistakes && heatmap.value.total_mistakes > 3) {
    predictions.push({
      dim: "error_pattern", label: "易错倾向",
      current: `${heatmap.value.total_mistakes} 道错题`,
      predicted: "错题模式更清晰，针对性练习推荐", days: 3, confidence: 85,
    });
  }
  if (assessment.value?.total_sessions) {
    const sessionsPerWeek = assessment.value.total_sessions;
    if (sessionsPerWeek >= 3) {
      predictions.push({
        dim: "learning_progress", label: "学习进度",
        current: `${assessment.value.total_sessions} 次练习`,
        predicted: "进入下一阶段学习", days: 14, confidence: 70,
      });
    }
  }
  const selfLearn = p.self_learning_ability?.self_learning ?? {};
  if (selfLearn.initiative === "中" || selfLearn.initiative === "一般") {
    predictions.push({
      dim: "self_learning_ability", label: "自主学习能力",
      current: "学习主动性一般",
      predicted: "主动性提升，开始自主探索", days: 10, confidence: 60,
    });
  }
  return predictions;
});

// ============ 8 维画像 ============
const DIMENSION_META: Record<string, { label: string; icon: any; color: string; desc: string }> = {
  knowledge_base: { label: "知识基础", icon: BookOpen, color: "#3b82f6", desc: "BKT 模型追踪的知识点掌握度" },
  cognitive_style: { label: "认知风格", icon: Brain, color: "#84a9b2", desc: "推理偏好与抽象接受度" },
  error_pattern: { label: "易错倾向", icon: ShieldAlert, color: "#ef4444", desc: "错题集中出现的薄弱点" },
  learning_habit: { label: "学习习惯", icon: Activity, color: "#10b981", desc: "学习节奏与活跃时段" },
  learning_progress: { label: "学习进度", icon: TrendingUp, color: "#f59e0b", desc: "当前学习阶段与状态" },
  interest_model: { label: "兴趣目标", icon: Target, color: "#c6815d", desc: "学习目标与动机" },
  resource_preference: { label: "资源偏好", icon: Library, color: "#06b6d4", desc: "偏好的学习资源类型与格式" },
  self_learning_ability: { label: "自主学习能力", icon: Lightbulb, color: "#f97316", desc: "自主学习、问题解决与反思能力" },
};
const DIMENSION_KEYS = Object.keys(DIMENSION_META);
const LEGACY_DIMENSION_MAP: Record<string, string> = {
  learning_preference: "resource_preference",
  weak_points: "error_pattern",
  learning_goal: "interest_model",
  time_management: "self_learning_ability",
  self_efficacy: "self_learning_ability",
  interaction_pattern: "self_learning_ability",
};

function canonicalDimensionKey(key: string): string {
  return LEGACY_DIMENSION_MAP[key] ?? key;
}

const DIMENSION_COLORS: Record<string, string> = {
  knowledge_base: "#6d9fc7", cognitive_style: "#84a9b2", error_pattern: "#d95f4f",
  learning_habit: "#68ad8e", learning_progress: "#d2aa4d", interest_model: "#c6815d",
  resource_preference: "#06b6d4", self_learning_ability: "#f97316",
};

function humanizeKpName(raw: string): string {
  const map: Record<string, string> = {
    "AI_001": "CNN 基础概念", "AI_002": "RNN 时序建模", "AI_003": "注意力机制",
    "AI_004": "迁移学习", "AI_005": "梯度消失 / 爆炸",
    "kp_001": "线性代数核心概念", "kp_002": "概率论基础", "kp_003": "决策树算法",
    "kp_004": "NLP 基础", "kp_005": "数据处理与清洗",
  };
  return map[raw] ?? raw.replace(/[_-]/g, " ");
}

function masteryLabel(pct: number): { text: string; status: "good" | "mid" | "weak" | "unknown" } {
  if (pct >= 75) return { text: "已掌握", status: "good" };
  if (pct >= 55) return { text: "待加强", status: "mid" };
  if (pct > 0) return { text: "薄弱", status: "weak" };
  return { text: "未知", status: "unknown" };
}

function getStatusColor(status: "good" | "mid" | "weak" | "unknown"): string {
  const colors = { good: "#16a34a", mid: "#f59e0b", weak: "#ef4444", unknown: "#94a3b8" };
  return colors[status] || colors.unknown;
}

// ============ 顶部统计卡 ============
const stats = computed(() => {
  const version = snapshots.value[0]?.version ?? 1;
  const featureNodes = DIMENSION_KEYS.length + Object.keys(bkt.value.masteries || {}).length;
  const evidenceCount = countEvidence();
  const pendingCount = updateQueue.value.filter((i) => i.status === "pending").length;
  let chatCount = snapshots.value.length;
  const practiceCount = assessment.value?.total_sessions ? 1 : 0;
  const bktCount = Object.keys(bkt.value.masteries || {}).length > 0 ? 1 : 0;
  return {
    version, featureNodes, evidenceCount, pendingCount,
    chatCount, practiceCount, bktCount,
    isNewVersion: version === 1 && snapshots.value.length <= 1,
  };
});

function countEvidence(): number {
  let n = 0;
  if (snapshots.value.length) n += snapshots.value.length;
  if (heatmap.value?.total_mistakes) n += 1;
  if (assessment.value?.total_sessions) n += 1;
  if (Object.keys(bkt.value.masteries || {}).length) n += 1;
  if (cockpitLedger.value?.total_claims) n += cockpitLedger.value.total_claims;
  return n;
}

// ============ 画像对象 + 维度树 ============
interface TreeNode {
  key: string; label: string; icon: any; color: string;
  children: Array<{ key: string; label: string; tagText: string; tagStatus: "good" | "mid" | "weak" | "unknown" }>;
}

const profile = computed(() => profileData.value?.profile ?? {});

const profileTree = computed<TreeNode[]>(() => {
  const p = profile.value;
  return DIMENSION_KEYS.map((key) => {
    const meta = DIMENSION_META[key];
    const raw = p[key];
    const children: TreeNode["children"] = [];

    if (key === "knowledge_base") {
      const entries = Object.entries(bkt.value.masteries || {});
      const top = entries.sort((a, b) => b[1] - a[1]).slice(0, 5);
      if (top.length) {
        for (const [kp, val] of top) {
          const ml = masteryLabel(Math.round(val * 100));
          children.push({ key: kp, label: humanizeKpName(kp), tagText: ml.text, tagStatus: ml.status });
        }
      } else {
        children.push({ key: "level", label: "整体水平", tagText: "待采集", tagStatus: "unknown" });
      }
    } else if (key === "error_pattern") {
      const topics = raw?.topics ?? raw?.weak_topics ?? [];
      if (topics.length) {
        for (const t of topics.slice(0, 4)) {
          children.push({ key: t, label: humanizeKpName(t), tagText: "薄弱", tagStatus: "weak" });
        }
      } else {
        children.push({ key: "pattern", label: "错因模式", tagText: raw?.pattern ?? "待采集", tagStatus: "unknown" });
      }
    } else if (key === "cognitive_style") {
      children.push({ key: "primary", label: "推理偏好", tagText: raw?.primary ?? raw?.style ?? "待采集", tagStatus: "unknown" });
      children.push({ key: "abstraction", label: "抽象接受度", tagText: raw?.abstraction ?? raw?.level ?? "待采集", tagStatus: "unknown" });
    } else if (key === "learning_habit") {
      children.push({ key: "mode", label: "学习节奏", tagText: raw?.mode ?? raw?.rhythm ?? "待采集", tagStatus: "unknown" });
      children.push({ key: "peak", label: "活跃时段", tagText: raw?.peak_time ?? raw?.best_time ?? "待采集", tagStatus: "unknown" });
    } else if (key === "learning_progress") {
      children.push({ key: "stage", label: "当前阶段", tagText: raw?.stage ?? raw?.target ?? "待采集", tagStatus: "unknown" });
      children.push({ key: "status", label: "学习状态", tagText: raw?.status ?? "待采集", tagStatus: "unknown" });
    } else if (key === "interest_model") {
      const goals = raw?.goals ?? raw?.target ?? [];
      const goalStr = Array.isArray(goals) ? goals.join("、") : String(goals || "待采集");
      children.push({ key: "goals", label: "兴趣目标", tagText: goalStr || "待采集", tagStatus: "unknown" });
      children.push({ key: "motivation", label: "学习动机", tagText: raw?.motivation ?? raw?.recent_interest ?? "待采集", tagStatus: "unknown" });
    } else if (key === "resource_preference") {
      children.push({ key: "format", label: "偏好格式", tagText: raw?.format ?? raw?.preferred_format ?? raw?.mode ?? "待采集", tagStatus: "unknown" });
      children.push({ key: "difficulty", label: "难度偏好", tagText: raw?.difficulty ?? raw?.depth ?? raw?.pace ?? "待采集", tagStatus: "unknown" });
      children.push({ key: "source_type", label: "行为证据", tagText: "待采集行为反馈", tagStatus: "unknown" });
    } else if (key === "self_learning_ability") {
      const selfLearn = raw?.self_learning ?? raw ?? {};
      const confidence = Number(selfLearn.confidence);
      children.push({ key: "confidence", label: "自我效能", tagText: Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : "待采集", tagStatus: "unknown" });
      children.push({ key: "reflection", label: "反思能力", tagText: selfLearn.reflection ?? "待采集", tagStatus: selfLearn.reflection === "强" ? "good" : selfLearn.reflection === "弱" ? "weak" : "unknown" });
      children.push({ key: "initiative", label: "学习主动性", tagText: selfLearn.initiative ?? "待采集", tagStatus: selfLearn.initiative === "高" ? "good" : selfLearn.initiative === "低" ? "weak" : "unknown" });
      children.push({ key: "time_management", label: "时间管理", tagText: selfLearn.time_management ?? selfLearn.best_time ?? "待采集", tagStatus: "unknown" });
    }

    return { key, label: meta.label, icon: meta.icon, color: meta.color, children };
  });
});

const expandedDims = ref<Set<string>>(new Set(DIMENSION_KEYS));
function toggleDim(key: string) {
  const s = new Set(expandedDims.value);
  s.has(key) ? s.delete(key) : s.add(key);
  expandedDims.value = s;
}

// 维度树点击：展开/收起 + 选中维度 + 切到证据溯源 Tab
function toggleDimAndSelect(key: string) {
  toggleDim(key);
  selectDimAndSwitch(key);
}

// ============ 中间：证据链（增强版） ============
interface EvidenceSource {
  type: string; label: string; detail: string;
  icon: any; strength: "high" | "medium" | "low";
}
interface EvidenceChain {
  fieldKey: string; fieldLabel: string; extractedValue: string;
  relatedDimensions: string[]; lastComputedAt: string;
  sources: EvidenceSource[]; confidence: "high" | "medium" | "low"; confidencePct: number;
}

const selectedDim = ref("error_pattern");
function selectDim(key: string) { selectedDim.value = key; }

// ===== 常驻分析 Tab =====
type ProfileTab = "diagnosis" | "evidence" | "timemachine" | "prediction";
const profileTab = ref<ProfileTab>("evidence");
const PROFILE_TABS: Array<{ key: ProfileTab; label: string; icon: any }> = [];

// 点击维度时：选中维度 + 切到证据溯源 Tab
function selectDimAndSwitch(key: string) {
  selectedDim.value = key;
  profileTab.value = "evidence";
}

const currentEvidence = computed<EvidenceChain>(() => {
  const key = selectedDim.value;
  const meta = DIMENSION_META[key];
  const raw = profile.value[key];
  const sources: EvidenceSource[] = [];

  const lastChange = snapshots.value.find((s) => s.changed_keys?.includes(key));
  if (lastChange) {
    sources.push({
      type: "chat", label: "AI 对话抽取",
      detail: `版本 V${lastChange.version}，来源 ${lastChange.source}`,
      icon: MessageCircle, strength: "high",
    });
  }
  if (key === "knowledge_base" || key === "error_pattern") {
    const weak = Object.entries(bkt.value.masteries || {})
      .filter(([, v]) => v < 0.55).sort((a, b) => a[1] - b[1]).slice(0, 3);
    if (weak.length) {
      sources.push({
        type: "bkt", label: "BKT 掌握度",
        detail: weak.map(([kp, v]) => `${humanizeKpName(kp)}: ${Math.round(v * 100)}%`).join("，") + "，知识点掌握度偏低",
        icon: TrendingUp, strength: "high",
      });
    }
  }
  if (key === "error_pattern" && heatmap.value) {
    const topKp = heatmap.value.matrix
      .map((r) => ({ kp: r.kp_id, total: r.total as number }))
      .sort((a, b) => b.total - a.total)[0];
    if (topKp) {
      sources.push({
        type: "mistake", label: "错题记录",
        detail: `${humanizeKpName(topKp.kp)} 共 ${topKp.total} 道错题，正确率偏低`,
        icon: ShieldAlert, strength: "medium",
      });
    }
  }
  if (key === "learning_progress" || key === "knowledge_base") {
    if (assessment.value?.total_sessions) {
      sources.push({
        type: "practice", label: "练习行为",
        detail: `共 ${assessment.value.total_sessions} 次练习，平均 ${assessment.value.quiz_avg_score ?? 0} 分`,
        icon: Activity, strength: "medium",
      });
    }
  }
  if (recoItems.value.length) {
    const related = recoItems.value.filter((r) => r.kind === "generate" || r.topic?.includes(key)).slice(0, 5);
    if (related.length) {
      sources.push({
        type: "recommendation", label: "推荐结果",
        detail: `${related.length}/${recoItems.value.length} 条推荐内容与该薄弱点相关，推荐命中率较高`,
        icon: Sparkles, strength: "medium",
      });
    }
  }
  const confidence = sources.length >= 3 ? "high" : sources.length >= 2 ? "medium" : "low";
  const confidencePct = sources.length >= 3 ? 85 : sources.length >= 2 ? 60 : 30;
  const relatedDims: string[] = [];
  if (key === "error_pattern") relatedDims.push("知识基础");
  if (key === "knowledge_base") relatedDims.push("易错倾向");
  const lastTs = lastChange?.created_at ?? snapshots.value[0]?.created_at ?? Date.now() / 1000;
  return {
    fieldKey: key, fieldLabel: meta?.label ?? key,
    extractedValue: formatDimValue(raw),
    relatedDimensions: relatedDims, lastComputedAt: fmtTime(lastTs),
    sources, confidence, confidencePct,
  };
});

function formatDimValue(raw: any): string {
  if (!raw) return "暂无数据";
  if (typeof raw === "string") return raw;
  if (raw.topics) return raw.topics.map((t: string) => humanizeKpName(t)).join("、");
  if (raw.goals) return Array.isArray(raw.goals) ? raw.goals.join("、") : String(raw.goals);
  if (raw.level) return raw.level;
  if (raw.score !== undefined) return String(raw.score);
  return JSON.stringify(raw).slice(0, 80);
}

const confidenceMeta: Record<string, { text: string; color: string; bg: string }> = {
  high: { text: "高", color: "#16a34a", bg: "#dcfce7" },
  medium: { text: "中", color: "#ea580c", bg: "#fff7ed" },
  low: { text: "低", color: "#94a3b8", bg: "#f1f5f9" },
};

const strengthMeta: Record<string, { text: string; color: string; bg: string }> = {
  high: { text: "高", color: "#16a34a", bg: "#dcfce7" },
  medium: { text: "中", color: "#ea580c", bg: "#fff7ed" },
  low: { text: "中", color: "#94a3b8", bg: "#f1f5f9" },
};

// ============ 更新队列 ============
interface UpdateItem {
  id: string; version: number; fieldKey: string; fieldLabel: string;
  changeType: "added" | "updated"; oldValue: string; newValue: string;
  source: string; timestamp: number; status: "pending" | "confirmed" | "ignored";
}

const updateQueue = ref<UpdateItem[]>([]);

function buildUpdateQueue(snaps: ProfileSnapshot[]): UpdateItem[] {
  const items: UpdateItem[] = [];
  for (let i = 0; i < snaps.length - 1; i++) {
    const cur = snaps[i];
    const prev = snaps[i + 1];
    for (const rawKey of cur.changed_keys || []) {
      const key = canonicalDimensionKey(rawKey);
      if (!DIMENSION_META[key]) continue;
      const oldVal = prev.profile?.[key];
      const newVal = cur.profile?.[key];
      items.push({
        id: `upd-${cur.version}-${key}`,
        version: cur.version,
        fieldKey: key,
        fieldLabel: DIMENSION_META[key]?.label ?? key,
        changeType: oldVal ? "updated" : "added",
        oldValue: formatDimValue(oldVal),
        newValue: formatDimValue(newVal),
        source: cur.source,
        timestamp: cur.created_at,
        status: "pending",
      });
    }
  }
  return items;
}

function confirmUpdate(id: string) {
  const item = updateQueue.value.find((i) => i.id === id);
  if (item) item.status = "confirmed";
}
function ignoreUpdate(id: string) {
  const item = updateQueue.value.find((i) => i.id === id);
  if (item) item.status = "ignored";
}

function fmtTime(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const recentUpdates = computed(() => {
  const items: Array<{ time: string; action: string; dotColor: string }> = [];
  const seen = new Set<string>();
  for (let i = 0; i < Math.min(snapshots.value.length, 6); i++) {
    const snap = snapshots.value[i];
    if (!snap) continue;
    const keys = [...new Set((snap.changed_keys ?? []).map(canonicalDimensionKey).filter((key) => DIMENSION_META[key]))];
    for (const key of keys) {
      const eventKey = `${snap.version}:${key}`;
      if (seen.has(eventKey)) continue;
      seen.add(eventKey);
      items.push({
        time: fmtTime(snap.created_at),
        action: i === 0
          ? `识别${DIMENSION_META[key]?.label ?? key}：${formatDimValue(snap.profile?.[key])}`
          : `更新${DIMENSION_META[key]?.label ?? key}：${formatDimValue(snap.profile?.[key])}`,
        dotColor: i === 0 ? "#16a34a" : i < 3 ? "#2563eb" : "#94a3b8",
      });
    }
  }
  return items;
});

// ============ 驱动动作 ============
interface DrivenAction {
  type: "resource" | "review" | "strategy";
  title: string; reason: string;
  triggerField: string; triggerFieldLabel: string; sourceBasis: string;
  actionLabel: string; actionUrl?: string;
}

const drivenActions = computed<DrivenAction[]>(() => {
  const actions: DrivenAction[] = [];
  const seen = new Set<string>();
  for (const item of recoItems.value.slice(0, 3)) {
    const triggerKey = item.kind === "generate" ? "error_pattern" : "knowledge_base";
    const action = {
      type: "resource",
      title: item.title ?? item.topic ?? "推荐资源",
      reason: item.reason,
      triggerField: triggerKey,
      triggerFieldLabel: DIMENSION_META[triggerKey]?.label ?? triggerKey,
      sourceBasis: item.kind === "generate" ? "BKT 掌握度低 + 推荐结果匹配" : "知识路径推荐 + 学习目标对齐",
      actionLabel: item.kind === "generate" ? "生成资源" : "去学习",
      actionUrl: item.kind === "resource" ? `/resources?id=${item.resource_id}` : `/resources?q=${item.topic}`,
    } as DrivenAction;
    const key = `${action.title}|${action.reason}`.trim().toLowerCase();
    if (!seen.has(key)) {
      seen.add(key);
      actions.push(action);
    }
  }
  if (learnerReco.value?.overdue_reviews) {
    actions.push({
      type: "review",
      title: `${learnerReco.value.overdue_reviews} 道错题到期复习`,
      reason: learnerReco.value.why ?? "SM-2 间隔重复算法调度",
      triggerField: "error_pattern",
      triggerFieldLabel: "易错倾向",
      sourceBasis: "错题记录 + 知识树节点薄弱",
      actionLabel: "去复习",
      actionUrl: "/mistakes",
    });
  }
  if (strategy.value?.adjustments?.length) {
    for (const adj of strategy.value.adjustments.slice(0, 2)) {
      actions.push({
        type: "strategy",
        title: adj.label, reason: adj.reason,
        triggerField: "interest_model", triggerFieldLabel: "学习目标",
        sourceBasis: "学习路径推荐 + 自适应策略引擎",
        actionLabel: "应用策略",
      });
    }
  }
  return actions;
});

// ============ Dashboard 派生：行为洞察（5 卡） ============
const behaviorInsights = computed(() => {
  const activity = overview.value?.activity;
  const collaboration = overview.value?.collaboration;
  const review = overview.value?.review;
  const peak = [...(activity?.hour_distribution ?? [])].sort((a, b) => b.minutes - a.minutes)[0];
  const preference = profile.value.resource_preference ?? overview.value?.profile.dimensions.learning_preference ?? {};
  const selfRegulation = profile.value.self_learning_ability ?? {};
  const selfRegulationScore = Number(selfRegulation.score);
  const topMistake = overview.value?.mistake_types?.[0];
  const reviewGains = (review?.recent ?? [])
    .map((item) => Number(item.after_mastery_pct) - Number(item.before_mastery_pct))
    .filter((gain) => Number.isFinite(gain));
  const averageReviewGain = reviewGains.length
    ? reviewGains.reduce((sum, gain) => sum + gain, 0) / reviewGains.length
    : null;
  const weeklyMinutes = activity?.this_week_minutes ?? 0;
  const weeklyChange = activity?.week_over_week_pct ?? 0;
  return [
    {
      key: "rhythm", icon: Clock, bg: "#fff7ed", fg: "#E65A1A",
      title: "学习节奏", bigText: `${activity?.active_days_30d ?? 0} 个活跃日`,
      sub: `本周 ${(weeklyMinutes / 60).toFixed(1)} 小时，环比 ${weeklyChange >= 0 ? "+" : ""}${weeklyChange}%`,
      meta: "近 30 日",
    },
    {
      key: "peak", icon: Sparkles, bg: "#fff7df", fg: "#c6815d",
      title: "专注时段", bigText: peak ? `${String(peak.hour).padStart(2, "0")}:00 高峰` : "暂无时段数据",
      sub: peak ? `累计学习 ${Math.round(peak.minutes)} 分钟` : "完成学习活动后生成",
      meta: peak ? "活动最集中" : "暂无数据",
      highlight: true,
    },
    {
      key: "resource", icon: FlaskConical, bg: "#eff6ff", fg: "#2563eb",
      title: "资源偏好", bigText: String(preference.mode ?? preference.format ?? preference.preferred_format ?? "待采集"),
      sub: String(preference.depth ?? preference.pace ?? "来自对话画像的偏好"),
      meta: "待采集行为反馈",
    },
    {
      key: "interact", icon: MessageCircle, bg: "#f0fdf4", fg: "#16a34a",
      title: "互动频率", bigText: `${collaboration?.message_count ?? 0} 条协作消息`,
      sub: `提问 ${collaboration?.question_count ?? 0} 次 · 相近阶段同伴 ${collaboration?.similar_stage_peer_count ?? 0} 人`,
      meta: (collaboration?.message_count ?? 0) > 0 ? "已有互动" : "暂无互动",
    },
    {
      key: "review", icon: CheckCircle2, bg: "#ecfdf5", fg: "#059669",
      title: "复习效能", bigText: averageReviewGain == null ? "待采集" : `平均增益 ${averageReviewGain >= 0 ? "+" : ""}${averageReviewGain.toFixed(1)} 分`,
      sub: `完成率 ${review?.completion_rate_pct ?? 0}% · 今日到期 ${review?.due_today ?? 0} 项`,
      meta: reviewGains.length ? `基于最近 ${reviewGains.length} 次复习前后测` : "完成复习后生成增益",
    },
    {
      key: "self-regulation", icon: Lightbulb, bg: "#fff7ed", fg: "#ea580c",
      title: "自我调节", bigText: Number.isFinite(selfRegulationScore) ? `${Math.round(selfRegulationScore * 100)}%` : "待采集",
      sub: selfRegulation.confidence != null ? `自我效能 ${Math.round(Number(selfRegulation.confidence) * 100)}%` : "结合计划执行与自我效能动态更新",
      meta: selfRegulation.best_time ? `高效时段 ${selfRegulation.best_time}` : "画像证据",
    },
    {
      key: "error-mechanism", icon: ShieldAlert, bg: "#fef2f2", fg: "#dc2626",
      title: "主要错因", bigText: topMistake?.label ?? "暂无错因数据",
      sub: topMistake ? `累计 ${topMistake.count} 次，建议观察重复发生率` : "完成练习后自动归因",
      meta: topMistake ? "来自真实错题记录" : "待采集",
    },
  ];
});

// ============ Dashboard 派生：知识掌握分布（带图片样式的进度条） ============
const knowledgeItems = computed(() => {
  return (overview.value?.profile.knowledge_points ?? []).slice(0, 8).map((item) => ({
    id: item.kp_id,
    name: item.kp_name,
    pct: Math.round(item.mastery_pct),
  })).map((it) => ({
    ...it,
    status: it.pct >= 75 ? "good" : it.pct >= 55 ? "mid" : "weak",
    label: it.pct >= 75 ? "良好" : it.pct >= 55 ? "中等" : "薄弱",
    color: it.pct >= 75 ? "#16a34a" : it.pct >= 55 ? "#f59e0b" : "#ef4444",
  }));
});

// ============ 侧栏派生：画像结论 / 风险提醒 / 个性化建议 / 学习档案 ============
const conclusionList = computed(() => {
  const items: Array<{ text: string; tag: "good" | "warn" }> = [];
  for (const strength of overview.value?.profile.strengths ?? []) {
    items.push({ text: `${strength.kp_name} 掌握度 ${Math.round(strength.mastery_pct)}%，属于当前优势`, tag: "good" });
  }
  if ((overview.value?.activity.active_days_30d ?? 0) > 0) {
    items.push({ text: `近 30 日活跃 ${overview.value?.activity.active_days_30d ?? 0} 天`, tag: "good" });
  }
  if ((overview.value?.collaboration.message_count ?? 0) > 0) {
    items.push({ text: `已产生 ${overview.value?.collaboration.message_count ?? 0} 条协作消息`, tag: "good" });
  }
  return items.slice(0, 5);
});

const riskList = computed(() => {
  const items: Array<{ text: string; tag: "warn" }> = currentWeaknesses.value.map((item) => ({
    text: `${item.name}当前掌握度 ${item.masteryPct}%，建议按薄弱度优先补强`,
    tag: "warn",
  }));
  const mistakeCount = heatmap.value?.total_mistakes ?? 0;
  if (mistakeCount > 0) {
    items.push({ text: `当前累计 ${mistakeCount} 道错题，建议优先完成复盘`, tag: "warn" });
  }
  const negativeSignal = strategy.value?.signals.find((signal) =>
    String(signal.value).includes("declining") || String(signal.value).includes("下降"),
  );
  if (negativeSignal?.detail) items.push({ text: negativeSignal.detail, tag: "warn" });
  return items.length ? items.slice(0, 5) : [{ text: "当前暂无显著学习风险", tag: "warn" }];
});

const adviceList = computed(() => {
  const items: Array<{ text: string; tag: "good" }> = [];
  const seen = new Set<string>();
  const append = (text: string) => {
    const normalized = text.trim().replace(/\s+/g, " ").toLowerCase();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    items.push({ text, tag: "good" });
  };
  if (primaryWeakness.value) {
    append(`优先补强「${primaryWeakness.value.name}」：先看图文讲解，再完成专项练习与案例复盘`);
  }
  for (const adjustment of strategy.value?.adjustments ?? []) {
    append(`${adjustment.label}：${adjustment.reason}`);
  }
  for (const recommendation of recoItems.value) {
    if (recommendation.reason) append(recommendation.reason);
  }
  return items.length ? items.slice(0, 5) : [{ text: "完成一次测评后将生成个性化建议", tag: "good" }];
});

const archiveItems = computed(() => {
  return [
    { label: "加入平台时间", value: overview.value?.profile.registered_date || "暂无记录" },
    { label: "累计学习时长", value: `${((overview.value?.activity.total_minutes ?? 0) / 60).toFixed(1)} 小时` },
    { label: "累计测评次数", value: `${overview.value?.assessment.total ?? 0} 次` },
    { label: "累计提问次数", value: `${overview.value?.collaboration.question_count ?? 0} 次` },
    { label: "画像快照", value: `${overview.value?.profile.snapshot_count ?? 0} 份` },
  ];
});

// ============ 报告抽屉 ============
const report = ref<DiagnosisReportResponse | null>(null);
const reportOpen = ref(false);
const reportLoading = ref(false);
const reportError = ref("");

async function openReport() {
  if (reportLoading.value) return;
  reportLoading.value = true;
  reportError.value = "";
  try {
    report.value = await getDiagnosisReport(userId.value);
    if (!report.value?.markdown?.trim()) {
      throw new Error("报告内容为空，请完成一次学习或测评后重试");
    }
    reportOpen.value = true;
  } catch (e: any) {
    reportError.value = `报告生成失败：${e?.detail ?? e?.message ?? String(e)}`;
  } finally {
    reportLoading.value = false;
  }
}

function reportHtmlDocument(): string {
  if (!report.value) return "";
  const title = `学习诊断报告 · ${report.value.nickname}`;
  const generatedDate = report.value.generated_at.slice(0, 10);
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(title)}</title>
  <style>
    :root { color-scheme: light; font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif; color: #241d18; background: #f6f1e9; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 32px 18px; }
    main { width: min(900px, 100%); margin: 0 auto; padding: 42px 48px; background: #fff; border: 1px solid #e6ddd1; border-radius: 18px; box-shadow: 0 18px 50px rgba(63, 43, 27, .10); }
    header { padding-bottom: 20px; margin-bottom: 26px; border-bottom: 2px solid #ed6a2c; }
    header h1 { margin: 0 0 8px; font-size: 28px; }
    header p { margin: 0; color: #75685d; font-size: 13px; }
    h1, h2, h3, h4 { color: #2b2119; line-height: 1.35; }
    h2 { margin-top: 30px; padding-bottom: 8px; border-bottom: 1px solid #eee5db; }
    p, li { line-height: 1.8; }
    blockquote { margin: 18px 0; padding: 12px 16px; border-left: 4px solid #ed6a2c; background: #fff7ef; }
    table { width: 100%; border-collapse: collapse; margin: 18px 0; }
    th, td { padding: 10px 12px; border: 1px solid #e6ddd1; text-align: left; }
    th { background: #fff7ef; }
    pre { overflow: auto; padding: 16px; border-radius: 10px; background: #1e2430; color: #edf2f7; }
    code { font-family: Consolas, "SFMono-Regular", monospace; }
    @media print { body { padding: 0; background: #fff; } main { width: 100%; padding: 0; border: 0; box-shadow: none; } }
    @media (max-width: 640px) { main { padding: 26px 20px; } }
  </style>
</head>
<body>
  <main>
    <header><h1>${escapeHtml(title)}</h1><p>生成日期：${escapeHtml(generatedDate)} · 焦点知识点：${escapeHtml(report.value.focus_kp_id || "综合学习")}</p></header>
    ${renderMarkdown(report.value.markdown)}
  </main>
</body>
</html>`;
}

function createReportUrl(): string {
  return URL.createObjectURL(new Blob([reportHtmlDocument()], { type: "text/html;charset=utf-8" }));
}

function openReportInNewWindow() {
  if (!report.value) return;
  reportError.value = "";
  const url = createReportUrl();
  const opened = window.open(url, "_blank");
  if (!opened) {
    reportError.value = "浏览器阻止了新窗口，请允许弹窗，或使用“下载 HTML”后打开。";
  } else {
    opened.opener = null;
  }
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

function downloadReport() {
  if (!report.value) return;
  const url = createReportUrl();
  const a = document.createElement("a");
  a.href = url;
  a.download = `学习诊断报告_${report.value.nickname}_${report.value.generated_at.slice(0, 10)}.html`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

async function handleResetProfile() {
  if (resetting.value) return;
  if (!window.confirm("确定重置学习画像？对话中会重新构建。")) return;
  resetting.value = true;
  try {
    await resetProfile(userId.value);
    await load();
  } catch { /* 后端不可用 */ }
  resetting.value = false;
}

async function handleCheckin() {
  if (checkingIn.value) return;
  checkingIn.value = true;
  checkinMsg.value = "";
  try {
    const r = await dailyCheckin(userId.value);
    checkinMsg.value = `签到成功！连续 ${r.streak_days} 天 · +${r.bonus_xp} XP · 当前等级 ${r.level}`;
    await load();
  } catch (e: any) {
    checkinMsg.value = `签到失败：${e?.detail ?? e?.message ?? e}`;
  }
  checkingIn.value = false;
  setTimeout(() => (checkinMsg.value = ""), 4000);
}

async function handleUnlockAchievement() {
  if (unlockingAch.value) return;
  const key = window.prompt("输入要解锁的成就 Key（如 first_quiz, streak_7 等）：");
  if (!key) return;
  unlockingAch.value = true;
  achMsg.value = "";
  try {
    await unlockAchievement(userId.value, key.trim());
    achMsg.value = `成就「${key}」已解锁！`;
    await load();
  } catch (e: any) {
    achMsg.value = `解锁失败：${e?.detail ?? e?.message ?? e}`;
  }
  unlockingAch.value = false;
  setTimeout(() => (achMsg.value = ""), 4000);
}

function handleImproveProfile() {
  router.push({ path: "/chat", query: { topic: "学习画像完善" } });
}

async function load() {
  loading.value = true;
  const uid = userId.value;
  try {
    const [pd, hist] = await Promise.all([
      getProfile(uid).catch(() => null),
      getProfileHistory(uid, 20).catch(() => ({ snapshots: [] as ProfileSnapshot[] })),
    ]);
    profileData.value = pd;
    snapshots.value = hist?.snapshots ?? [];
  } catch { /* 保留默认 */ }
  void fetchCockpit(uid)
    .then((cockpit) => { cockpitLedger.value = cockpit?.ledger ?? null; })
    .catch(() => { cockpitLedger.value = null; });
  const results = await Promise.allSettled([
    getBktStatus(uid), getMistakesHeatmap(uid), getAssessment(uid),
    getGamification(uid), getRecommendations(uid, 5, course.value), getAdaptiveStrategy(uid, course.value),
    getLearnerStateRecommendation(uid), getPersonalizationChain(uid, course.value), getPeerComparison(uid),
    getStudentOverview(uid, course.value),
  ]);
  if (results[0].status === "fulfilled") bkt.value = results[0].value;
  if (results[1].status === "fulfilled") heatmap.value = results[1].value;
  if (results[2].status === "fulfilled") assessment.value = results[2].value;
  if (results[3].status === "fulfilled") gamify.value = results[3].value;
  if (results[4].status === "fulfilled") recoItems.value = results[4].value.items ?? [];
  if (results[5].status === "fulfilled") strategy.value = results[5].value;
  if (results[6].status === "fulfilled") learnerReco.value = results[6].value.recommendation;
  if (results[7].status === "fulfilled") personalizationChain.value = results[7].value;
  if (results[8].status === "fulfilled") peerComparison.value = results[8].value;
  if (results[9].status === "fulfilled") overview.value = results[9].value;
  updateQueue.value = buildUpdateQueue(snapshots.value);
  loading.value = false;

  // 异步加载错题智能分析（不阻塞首屏）
  loadMistakeInsights(uid);
}

async function loadMistakeInsights(uid: string) {
  loadingInsights.value = true;
  try {
    mistakeInsights.value = await getMistakeInsights(uid);
  } catch {
    // 静默失败
  }
  loadingInsights.value = false;
}

onMounted(load);
</script>

<template>
  <div class="profile-dashboard companion-page">
    <!-- ============ 暖色画像 Hero ============ -->
    <section class="pd-warm-hero pd-edu-hero pd-brutal-hero pd-eco-hero">
      <div class="pd-hero-topline">
        <div class="pd-header-titles">
          <span class="pd-hero-kicker"><Sparkles :size="14" />持续成长画像</span>
          <h1>我的 <span>成长</span> 画像</h1>
          <p>让每一次学习、练习与协作沉淀为清晰可见的成长轨迹。</p>
        </div>
        <div class="pd-header-actions">
          <button class="pd-ghost-btn" type="button" :disabled="loading" @click="load">
            <RefreshCcw :size="14" :class="{ spin: loading }" />刷新
          </button>
          <button class="pd-ghost-btn" type="button" :disabled="reportLoading" @click="openReport">
            <Loader2 v-if="reportLoading" :size="14" class="spin" />
            <FileText v-else :size="14" />查看报告
          </button>
          <button class="pd-primary-btn" type="button" :disabled="resetting" @click="handleImproveProfile">
            完善画像 <ArrowRight :size="14" />
          </button>
        </div>
      </div>

      <p v-if="reportError" class="pd-toast" role="alert">{{ reportError }}</p>

      <div class="pd-hero-grid">
        <div class="pd-hero-identity">
          <div v-if="loading" class="pd-loading"><Loader2 :size="22" class="spin" /></div>
          <template v-else>
            <div class="pd-avatar pd-avatar-large">
              <img
                v-if="learnerPartner.avatar"
                :src="learnerPartner.avatar"
                :alt="learnerPartner.name"
                class="pd-avatar-img"
              />
              <span v-else class="pd-avatar-fallback" :style="{ background: learnerPartner.accent }">
                {{ learnerPartner.name.slice(0, 1) }}
              </span>
            </div>
            <div class="pd-learner-meta">
              <span class="pd-hero-label">你的成长档案</span>
              <strong>{{ learnerPartner.name }}</strong>
              <small>{{ learnerArchetypeLabel }}</small>
            </div>
          </template>
        </div>

        <div class="pd-hero-progress pd-hero-learning-card">
          <div class="pd-hero-progress-head">
            <span><BookOpen :size="14" /> 学习影响力</span>
            <span class="pd-hero-version">V{{ stats.version }}</span>
          </div>
          <strong>{{ radarAvgScore }}<small>%</small></strong>
          <div class="pd-hero-progress-bar"><span :style="{ transform: `scaleX(${radarAvgScore / 100})` }" /></div>
          <p>继续学习与练习，AI 会实时更新能力画像</p>
        </div>
      </div>

      <div :class="['pd-hero-footer', { 'without-badge': loading || !archetypeBadge }]">
        <div v-if="!loading && archetypeBadge" class="pd-hero-badge" :style="{ '--badge-color': archetypeBadge.color }">
          <div class="pd-hero-badge-icon"><Sparkles :size="16" /></div>
          <div>
            <span>学习者类型</span>
            <strong>{{ archetypeBadge.archetype }}</strong>
          </div>
          <span v-if="archetypeBadge.cognitiveStyle" class="pd-hero-badge-style"><Brain :size="13" />{{ archetypeBadge.cognitiveStyle }}</span>
        </div>

        <!-- ============ 5 大核心指标（纳入画像总览框） ============ -->
        <section class="pd-metrics" aria-label="五项核心学习指标">
          <div v-for="m in dashboardMetrics" :key="m.key" class="pd-metric-card">
            <div class="pd-metric-icon" :style="{ background: m.bgColor }">
              <component :is="m.icon" :size="20" :style="{ color: m.fgColor }" />
            </div>
            <div class="pd-metric-body">
              <small>{{ m.label }}</small>
              <strong :style="{ color: m.fgColor }">{{ m.value }}<span class="pd-unit">{{ m.unit }}</span></strong>
              <span class="pd-metric-sub">{{ m.sub }}</span>
            </div>
            <span v-if="m.delta" class="pd-metric-delta">{{ m.delta }}</span>
          </div>
        </section>
      </div>
    </section>
    <p v-if="checkinMsg" class="pd-toast">{{ checkinMsg }}</p>
    <p v-if="achMsg" class="pd-toast">{{ achMsg }}</p>

    <!-- ============ 主区域 + 侧栏 双栏布局 ============ -->
    <div class="pd-grid">
      <!-- ============ 主区域 ============ -->
      <main class="pd-main">

        <!-- ===== 画像维度：能力雷达 + 画像速览 ===== -->
        <ArtCard class="pd-section pd-dimension-filter">
          <SectionTitle title="画像维度" sub="能力分布与八维画像特征">
            <template #action><Layers :size="16" /></template>
          </SectionTitle>
          <div class="pd-dimension-workbench">
            <section class="pd-dimension-radar" aria-label="能力雷达图">
              <div class="pd-dimension-panel-head">
                <div>
                  <strong>能力雷达图</strong>
                  <span>八维能力画像 · 实时趋势</span>
                </div>
                <Compass :size="17" />
              </div>
              <div class="pd-radar-wrap">
                <Radar :data="radarChartData" :options="radarChartOptions" />
              </div>
              <div class="pd-radar-foot">
                <span class="pd-radar-tag orange">优势维度 {{ radarLeadCount }} 个</span>
                <span class="pd-radar-tag">待提升 {{ radarLagCount }} 个</span>
                <span class="pd-radar-tag gray">综合评分 {{ radarAvgScore }} 分</span>
              </div>
            </section>

            <section class="pd-dimension-overview" aria-label="画像速览">
              <div class="pd-dimension-panel-head">
                <div>
                  <strong>画像速览</strong>
                  <span>V{{ stats.version }} · {{ DIMENSION_KEYS.length }} 维特征</span>
                </div>
                <Layers :size="17" />
              </div>
              <div class="pd-mini-tree">
                <div v-for="node in profileTree" :key="node.key" class="pd-mini-node" :style="{ '--node-color': node.color }">
                  <button type="button" class="pd-mini-head" @click="toggleDimAndSelect(node.key)">
                    <span class="pd-mini-icon-wrap"><component :is="node.icon" :size="14" /></span>
                    <span class="pd-mini-label">{{ node.label }}</span>
                    <span class="pd-mini-count">{{ node.children.length }}</span>
                    <component :is="expandedDims.has(node.key) ? ChevronDown : ChevronRight" :size="12" class="pd-mini-toggle" />
                  </button>
                  <transition name="expand">
                    <div v-show="expandedDims.has(node.key)" class="pd-mini-children">
                      <div v-for="child in node.children.slice(0, 3)" :key="child.key" class="pd-mini-leaf" :class="child.tagStatus">
                        <span class="dot" :style="{ background: getStatusColor(child.tagStatus) }" />
                        <span class="leaf-l">{{ child.label }}</span>
                        <span class="leaf-t" :class="child.tagStatus" :style="child.tagStatus !== 'unknown' ? { background: getStatusColor(child.tagStatus) + '20', color: getStatusColor(child.tagStatus) } : {}">{{ child.tagText }}</span>
                      </div>
                      <div v-if="node.children.length > 3" class="pd-mini-more">+ 还有 {{ node.children.length - 3 }} 项</div>
                    </div>
                  </transition>
                </div>
              </div>
            </section>
          </div>

          <section class="pd-dimension-evidence" aria-label="证据溯源">
            <div class="pd-dimension-panel-head pd-evidence-heading">
              <div>
                <strong>证据溯源</strong>
                <span>当前维度的字段值、可信度与原始来源</span>
              </div>
              <GitBranch :size="17" />
            </div>
            <div class="pd-evidence-layout">
              <div class="pd-evidence-field">
                <div class="evd-row">
                  <span class="lab">当前维度</span>
                  <span class="val orange">{{ DIMENSION_META[selectedDim]?.label ?? selectedDim }}</span>
                </div>
                <div class="evd-row">
                  <span class="lab">当前字段值</span>
                  <span class="val">{{ currentEvidence.extractedValue }}</span>
                </div>
                <div class="evd-row">
                  <span class="lab">可信度</span>
                  <span class="val">{{ confidenceMeta[currentEvidence.confidence].text }}</span>
                  <div class="pd-conf-bar">
                    <div class="pd-conf-fill" :style="{ transform: `scaleX(${currentEvidence.confidencePct / 100})`, background: confidenceMeta[currentEvidence.confidence].color }" />
                  </div>
                  <span class="val">{{ currentEvidence.confidencePct }}%</span>
                </div>
                <div class="evd-row">
                  <span class="lab">最后计算</span>
                  <span class="val">{{ currentEvidence.lastComputedAt }}</span>
                </div>
              </div>
              <div class="pd-evidence-sources">
                <h4>证据来源</h4>
                <div v-if="currentEvidence.sources.length" class="pd-source-list">
                  <div v-for="(src, i) in currentEvidence.sources" :key="i" class="pd-source-card">
                    <span class="pd-source-icon" :style="{ background: strengthMeta[src.strength].bg }">
                      <component :is="src.icon" :size="14" :style="{ color: strengthMeta[src.strength].color }" />
                    </span>
                    <div class="pd-source-body">
                      <div class="pd-source-head">
                        <strong>{{ src.label }}</strong>
                        <span class="pd-source-type">{{ src.type }}</span>
                        <span class="pd-source-strength" :style="{ color: strengthMeta[src.strength].color, background: strengthMeta[src.strength].bg }">{{ strengthMeta[src.strength].text }}</span>
                      </div>
                      <p>{{ src.detail }}</p>
                    </div>
                  </div>
                </div>
                <div v-else class="pd-empty-state">
                  <GitBranch :size="26" />
                  <p>暂无证据来源</p>
                  <span>去群聊对话或完成练习后可生成证据。</span>
                </div>
              </div>
            </div>
          </section>
        </ArtCard>

        <!-- ===== 独立 AI 画像工具 ===== -->
        <ArtCard class="pd-section pd-ai-toolbox">
          <SectionTitle title="AI 画像工具" sub="诊断、回溯与趋势预测">
            <template #action><Sparkles :size="16" /></template>
          </SectionTitle>
          <div class="pd-ai-tools-grid">
            <button type="button" class="pd-ai-tool pd-ai-tool-diagnosis" @click="diagnosisOpen = true">
              <span class="pd-ai-tool-icon"><Brain :size="20" /></span>
              <span class="pd-ai-tool-copy"><strong>AI 诊断</strong><small>识别优势、风险与改进方向</small></span>
              <span v-if="aiDiagnosis.length" class="pd-tool-badge">{{ aiDiagnosis.length }}</span>
              <ArrowRight :size="16" class="pd-ai-tool-arrow" />
            </button>
            <button type="button" class="pd-ai-tool pd-ai-tool-timemachine" @click="timeMachineOpen = true">
              <span class="pd-ai-tool-icon"><Clock :size="20" /></span>
              <span class="pd-ai-tool-copy"><strong>画像时光机</strong><small>回看画像版本与能力演变</small></span>
              <span v-if="historySnapshots.length > 1" class="pd-tool-badge">{{ historySnapshots.length }}</span>
              <ArrowRight :size="16" class="pd-ai-tool-arrow" />
            </button>
            <button type="button" class="pd-ai-tool pd-ai-tool-prediction" @click="predictionOpen = true">
              <span class="pd-ai-tool-icon"><TrendingUp :size="20" /></span>
              <span class="pd-ai-tool-copy"><strong>画像预测</strong><small>预测未来能力与学习趋势</small></span>
              <ArrowRight :size="16" class="pd-ai-tool-arrow" />
            </button>
          </div>
        </ArtCard>

        <!-- ===== 5 个常驻 Tab 导航 + 内容区 ===== -->
        <ArtCard v-if="false" class="pd-section pd-tabs-legacy">
          <div class="pd-tabs-nav">
            <button
              v-for="tab in PROFILE_TABS"
              :key="tab.key"
              type="button"
              :class="['pd-tab-btn', { active: profileTab === tab.key }]"
              @click="profileTab = tab.key"
            >
              <component :is="tab.icon" :size="14" />
              <span>{{ tab.label }}</span>
            </button>
          </div>

          <div class="pd-tab-content">
            <!-- Tab 1: AI 诊断 -->
            <div v-if="profileTab === 'diagnosis'" class="pd-tab-panel">
              <div class="pd-diagnosis-grid">
                <section class="pd-diagnosis-panel">
                  <h4>当前问题</h4>
                  <ul class="pd-bullet-list danger">
                    <li v-for="(r, i) in riskList" :key="i">
                      <span class="dot" />
                      <span>{{ r.text }}</span>
                    </li>
                  </ul>
                </section>
                <section class="pd-diagnosis-panel">
                  <h4>优势亮点</h4>
                  <ul class="pd-bullet-list">
                    <li v-for="(c, i) in conclusionList" :key="i" :class="c.tag">
                      <span class="dot" />
                      <span>{{ c.text }}</span>
                    </li>
                  </ul>
                </section>
                <section class="pd-diagnosis-panel">
                  <h4>改进建议</h4>
                  <ul class="pd-bullet-list check">
                    <li v-for="(a, i) in adviceList" :key="i">
                      <Check :size="13" class="pd-check-icon" />
                      <span>{{ a.text }}</span>
                    </li>
                  </ul>
                </section>
                <section class="pd-diagnosis-panel">
                  <h4>模型诊断</h4>
                  <div v-if="aiDiagnosis.length" class="pd-diagnosis-cards">
                    <article v-for="d in aiDiagnosis" :key="d.title" :class="['pd-diagnosis-card', d.type]">
                      <strong>{{ d.title }}</strong>
                      <p>{{ d.content }}</p>
                    </article>
                  </div>
                  <div v-else class="pd-empty-state">
                    <Brain :size="26" />
                    <p>暂无模型诊断</p>
                    <span>完成更多练习或群聊后会自动生成。</span>
                  </div>
                </section>
              </div>
            </div>

            <!-- Tab 2: 证据溯源 -->
            <div v-if="profileTab === 'evidence'" class="pd-tab-panel">
              <div class="pd-evidence-layout">
                <div class="pd-evidence-field">
                  <div class="evd-row">
                    <span class="lab">当前维度</span>
                    <span class="val orange">{{ DIMENSION_META[selectedDim]?.label ?? selectedDim }}</span>
                  </div>
                  <div class="evd-row">
                    <span class="lab">当前字段值</span>
                    <span class="val">{{ currentEvidence.extractedValue }}</span>
                  </div>
                  <div class="evd-row">
                    <span class="lab">可信度</span>
                    <span class="val">{{ confidenceMeta[currentEvidence.confidence].text }}</span>
                    <div class="pd-conf-bar">
                      <div class="pd-conf-fill" :style="{ transform: `scaleX(${currentEvidence.confidencePct / 100})`, background: confidenceMeta[currentEvidence.confidence].color }" />
                    </div>
                    <span class="val">{{ currentEvidence.confidencePct }}%</span>
                  </div>
                  <div class="evd-row">
                    <span class="lab">最后计算</span>
                    <span class="val">{{ currentEvidence.lastComputedAt }}</span>
                  </div>
                </div>
                <div class="pd-evidence-sources">
                  <h4>证据来源</h4>
                  <div v-if="currentEvidence.sources.length" class="pd-source-list">
                    <div v-for="(src, i) in currentEvidence.sources" :key="i" class="pd-source-card">
                      <span class="pd-source-icon" :style="{ background: strengthMeta[src.strength].bg }">
                        <component :is="src.icon" :size="14" :style="{ color: strengthMeta[src.strength].color }" />
                      </span>
                      <div class="pd-source-body">
                        <div class="pd-source-head">
                          <strong>{{ src.label }}</strong>
                          <span class="pd-source-type">{{ src.type }}</span>
                          <span class="pd-source-strength" :style="{ color: strengthMeta[src.strength].color, background: strengthMeta[src.strength].bg }">{{ strengthMeta[src.strength].text }}</span>
                        </div>
                        <p>{{ src.detail }}</p>
                      </div>
                    </div>
                  </div>
                  <div v-else class="pd-empty-state">
                    <GitBranch :size="26" />
                    <p>暂无证据来源</p>
                    <span>去群聊对话或完成练习后可生成证据。</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab 3: 画像时光机 -->
            <div v-if="profileTab === 'timemachine'" class="pd-tab-panel">
              <div class="tm-controls">
                <button class="pd-play-btn" @click="playTimeMachine">
                  <Play v-if="!isPlaying" :size="16" />
                  <Pause v-else :size="16" />
                  {{ isPlaying ? '暂停' : '播放' }}演变
                </button>
                <div class="tm-timeline">
                  <div v-for="(snap, idx) in historySnapshots" :key="idx"
                       class="tm-timeline-point"
                       :class="{ active: currentSnapshotIndex === idx, passed: currentSnapshotIndex > idx }"
                       @click="seekSnapshot(idx)">
                    <span class="tm-point-dot" />
                    <span class="tm-point-label">V{{ snap.version }}</span>
                    <span class="tm-point-time">{{ fmtTime(snap.timestamp) }}</span>
                  </div>
                </div>
              </div>
              <div class="tm-preview">
                <h4>V{{ historySnapshots[currentSnapshotIndex]?.version ?? 1 }} 画像状态</h4>
                <div class="tm-changes" v-if="historySnapshots[currentSnapshotIndex]?.changedKeys?.length">
                  <span class="tm-change-tag">本次更新：</span>
                  <span v-for="key in historySnapshots[currentSnapshotIndex].changedKeys" :key="key" class="tm-change-item">
                    {{ DIMENSION_META[key]?.label ?? key }}
                  </span>
                </div>
                <div class="tm-dims-grid">
                  <div v-for="dim in DIMENSION_KEYS" :key="dim" class="tm-dim-card"
                       :style="{ borderColor: DIMENSION_COLORS[dim] }">
                    <component :is="DIMENSION_META[dim].icon" :size="16" :style="{ color: DIMENSION_COLORS[dim] }" />
                    <span class="tm-dim-label">{{ DIMENSION_META[dim].label }}</span>
                    <span class="tm-dim-value">{{ formatDimValue(timeMachineProfile[dim]) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Tab 5: 画像预测 -->
            <div v-if="profileTab === 'prediction'" class="pd-tab-panel">
              <div class="pred-intro">
                <Sparkles :size="16" />
                <span>根据你的学习节奏和当前画像状态，AI 预测未来变化趋势</span>
              </div>
              <div class="pred-list">
                <div v-for="(pred, idx) in futurePredictions" :key="idx" class="pred-card">
                  <div class="pred-head">
                    <span class="pred-dim" :style="{ color: DIMENSION_COLORS[pred.dim] }">{{ pred.label }}</span>
                    <span class="pred-days">{{ pred.days }} 天后</span>
                  </div>
                  <div class="pred-timeline">
                    <div class="pred-point">
                      <span class="pred-dot" />
                      <span class="pred-lab">当前</span>
                      <span class="pred-val">{{ pred.current }}</span>
                    </div>
                    <div class="pred-arrow">→</div>
                    <div class="pred-point">
                      <span class="pred-dot" style="background: var(--eco-green);" />
                      <span class="pred-lab">预测</span>
                      <span class="pred-val highlight">{{ pred.predicted }}</span>
                    </div>
                  </div>
                  <div class="pred-confidence">
                    <span>置信度</span>
                    <div class="pred-bar"><div class="pred-fill" :style="{ transform: `scaleX(${pred.confidence / 100})` }" /></div>
                    <span>{{ pred.confidence }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="!futurePredictions.length" class="pred-empty">
                <p>数据积累不足，暂时无法生成预测</p>
                <span>继续学习，AI 将为你预测画像演变趋势</span>
              </div>
            </div>
          </div>
        </ArtCard>

        <!-- 学习行为洞察（5 卡） -->
        <ArtCard class="pd-section">
          <SectionTitle title="学习行为洞察" sub="节奏 · 时段 · 偏好 · 互动 · 复盘">
            <template #action><Activity :size="16" /></template>
          </SectionTitle>
          <div class="pd-insights">
            <div v-for="ins in behaviorInsights" :key="ins.key" class="pd-insight-card">
              <div class="pd-insight-icon" :style="{ background: ins.bg }">
                <component :is="ins.icon" :size="18" :style="{ color: ins.fg }" />
              </div>
              <small>{{ ins.title }}</small>
              <strong>{{ ins.bigText }}</strong>
              <span class="pd-insight-sub" v-if="ins.sub">{{ ins.sub }}</span>
              <span class="pd-insight-meta">{{ ins.meta }}</span>
            </div>
          </div>
        </ArtCard>

        <!-- 知识掌握分布 -->
        <ArtCard class="pd-section">
          <SectionTitle title="知识掌握分布" :sub="`Top ${knowledgeItems.length} 知识点实时掌握度`">
            <template #action><Layers :size="16" /></template>
          </SectionTitle>
          <div class="pd-knowledge">
            <div v-for="k in knowledgeItems" :key="k.id" class="pd-knowledge-row">
              <span class="pd-knowledge-name">{{ k.name }}</span>
              <div class="pd-bar">
                <div class="pd-bar-fill" :style="{ transform: `scaleX(${k.pct / 100})`, background: k.color }" />
              </div>
              <span class="pd-knowledge-pct">{{ k.pct }}%</span>
              <span class="pd-knowledge-tag" :style="{ color: k.color, background: k.color + '15' }">{{ k.label }}</span>
            </div>
          </div>
        </ArtCard>

        <!-- AI 错题智能洞察 -->
        <ArtCard class="pd-section pd-mistake-insight-card">
          <SectionTitle title="AI 错题智能洞察" sub="大模型分析错题模式 · 推荐练习与资料">
            <template #action>
              <component :is="loadingInsights ? Loader2 : Sparkles" :size="16" :class="{ spin: loadingInsights }" />
            </template>
          </SectionTitle>

          <div v-if="loadingInsights && !mistakeInsights" class="pd-insights-loading">
            <Loader2 :size="20" class="spin" />
            <span>正在分析错题数据…</span>
          </div>

          <div v-else-if="mistakeInsights" class="pd-mistake-ai">
            <!-- 总结 -->
            <div class="pd-ai-summary">
              <div class="pd-ai-badge" :class="mistakeInsights.source === 'llm' ? 'llm' : 'rule'">
                {{ mistakeInsights.source === 'llm' ? 'AI 生成' : '规则分析' }}
              </div>
              <p>{{ mistakeInsights.summary }}</p>
            </div>

            <!-- 薄弱知识点 + 评估 -->
            <div class="pd-ai-row">
              <div class="pd-ai-col">
                <small class="pd-ai-label">薄弱知识点</small>
                <div v-for="wp in mistakeInsights.weak_points" :key="wp.kp_id" class="pd-weak-kp">
                  <span class="pd-weak-name">{{ localizeKnowledgePointLabel(wp.kp_id) }}</span>
                  <span class="pd-weak-count">{{ wp.error_count }} 题</span>
                  <span class="pd-weak-reason">{{ wp.reason }}</span>
                </div>
                <div v-if="!mistakeInsights.weak_points.length" class="pd-ai-empty">暂无薄弱知识点</div>
              </div>

              <div class="pd-ai-col">
                <small class="pd-ai-label">学习评估</small>
                <div class="pd-eval-score">
                  <div class="pd-eval-ring" :style="{ '--pct': mistakeInsights.evaluation.overall_score * 100 + '%' }">
                    <span>{{ Math.round(mistakeInsights.evaluation.overall_score * 100) }}</span>
                    <small>/100</small>
                  </div>
                  <div class="pd-eval-tags">
                    <span v-for="s in mistakeInsights.evaluation.strengths" :key="s" class="pd-eval-tag green"><span class="pd-tag-mark" aria-hidden="true"></span>{{ s }}</span>
                    <span v-for="w in mistakeInsights.evaluation.weaknesses" :key="w" class="pd-eval-tag red"><span class="pd-tag-mark" aria-hidden="true"></span>{{ w }}</span>
                  </div>
                </div>
                <div class="pd-eval-suggestions">
                  <small class="pd-ai-label">改进建议</small>
                  <div v-for="(s, i) in mistakeInsights.evaluation.suggestions" :key="i" class="pd-suggestion-item">
                    <span class="pd-suggestion-num">{{ i + 1 }}</span>
                    <span>{{ s }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 推荐类似题 -->
            <div v-if="mistakeInsights.recommendations.similar_questions.length" class="pd-ai-section">
              <small class="pd-ai-label">推荐练习题</small>
              <div class="pd-rec-questions">
                <div v-for="(q, i) in mistakeInsights.recommendations.similar_questions" :key="i" class="pd-rec-q">
                  <div class="pd-rec-q-head">
                    <span class="pd-rec-bloom">{{ q.bloom_level || `题${i+1}` }}</span>
                    <span v-if="q.source_kp" class="pd-rec-kp">{{ q.source_kp }}</span>
                  </div>
                  <p class="pd-rec-q-text">{{ q.question }}</p>
                  <details>
                    <summary>查看答案与解析</summary>
                    <p class="pd-rec-q-answer"><b>答案：</b>{{ q.answer }}</p>
                    <p v-if="q.explanation" class="pd-rec-q-expl"><b>解析：</b>{{ q.explanation }}</p>
                  </details>
                </div>
              </div>
            </div>

            <!-- 推荐学习资料 -->
            <div v-if="mistakeInsights.recommendations.learning_materials.length" class="pd-ai-section">
              <small class="pd-ai-label">推荐学习资料</small>
              <div class="pd-rec-materials">
                <a
                  v-for="(m, i) in mistakeInsights.recommendations.learning_materials"
                  :key="i"
                  :href="m.url.startsWith('http') ? m.url : undefined"
                  :target="m.url.startsWith('http') ? '_blank' : undefined"
                  class="pd-rec-mat"
                >
                  <span class="pd-rec-mat-type" :class="m.type">{{ m.type }}</span>
                  <div class="pd-rec-mat-body">
                    <strong>{{ m.title }}</strong>
                    <small>{{ m.reason }}</small>
                  </div>
                </a>
              </div>
            </div>
          </div>

          <div v-else class="pd-insights-loading">
            <span>错题分析不可用，请先记录错题</span>
          </div>
        </ArtCard>
      </main>

      <!-- ============ 侧栏 ============ -->
      <aside class="pd-aside pd-profile-companion">
        <!-- 趋势总览：放在侧栏顶部，平衡左右内容高度 -->
        <ArtCard class="pd-side-card pd-side-trend-card">
          <SectionTitle title="近 7 日趋势" :sub="trendSeries.summary">
            <template #action><LineChart :size="16" /></template>
          </SectionTitle>
          <div v-if="trendSeries.hasData" class="pd-trend-wrap">
            <svg viewBox="0 0 560 210" class="pd-trend-svg" role="img" aria-label="知识掌握趋势">
              <defs>
                <linearGradient id="lineWarm" x1="0" x2="1">
                  <stop offset="0%" stop-color="#f3b347" />
                  <stop offset="100%" stop-color="#ea5a1a" />
                </linearGradient>
                <linearGradient id="fillWarm" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stop-color="#ea5a1a" stop-opacity="0.22" />
                  <stop offset="100%" stop-color="#ea5a1a" stop-opacity="0" />
                </linearGradient>
              </defs>
              <line v-for="y in [50, 92, 134]" :key="y" x1="40" :y1="y" x2="540" :y2="y" stroke="#e8e6e1" stroke-dasharray="3 3" />
              <polygon :points="trendSeries.fillPoints" fill="url(#fillWarm)" />
              <polyline :points="trendSeries.linePoints" fill="none" stroke="url(#lineWarm)" stroke-width="3" stroke-linejoin="round" />
              <g v-for="point in trendSeries.points" :key="point.timestamp">
                <circle :cx="point.x" :cy="point.y" r="4" fill="#fff" stroke="#ea5a1a" stroke-width="2" />
              </g>
              <g class="pd-trend-axis">
                <text v-for="point in trendSeries.points" :key="point.timestamp" :x="point.x" y="200" text-anchor="middle">{{ point.label }}</text>
              </g>
              <g class="pd-trend-axis">
                <text x="6" y="54" font-size="10" fill="#94a3b8">100%</text>
                <text x="6" y="96" font-size="10" fill="#94a3b8">75%</text>
                <text x="6" y="138" font-size="10" fill="#94a3b8">50%</text>
                <text x="6" y="180" font-size="10" fill="#94a3b8">25%</text>
                <text x="6" y="210" font-size="10" fill="#94a3b8">0%</text>
              </g>
            </svg>
          </div>
          <div v-else class="pd-empty-state pd-trend-empty">
            <LineChart :size="24" />
            <p>暂无真实测评趋势</p>
            <span>完成至少两次测评后自动生成</span>
          </div>
        </ArtCard>

        <!-- 画像结论 -->
        <ArtCard class="pd-side-card">
          <SectionTitle title="画像结论" sub="整体评估 · 核心亮点">
            <template #action><Lightbulb :size="16" /></template>
          </SectionTitle>
          <ul class="pd-bullet-list">
            <li v-for="(c, i) in conclusionList" :key="i" :class="c.tag">
              <span class="dot" />
              <span>{{ c.text }}</span>
            </li>
          </ul>
        </ArtCard>

        <!-- 风险提醒 -->
        <ArtCard class="pd-side-card pd-current-weakness-card">
          <SectionTitle title="当前薄弱知识点" sub="BKT 实时诊断 · 随学随新">
            <template #action><Target :size="16" /></template>
          </SectionTitle>
          <div v-if="currentWeaknesses.length" class="pd-current-weakness-list">
            <article v-for="item in currentWeaknesses" :key="item.kp_id" class="pd-current-weakness-item">
              <span class="pd-weak-rank">{{ item.rank }}</span>
              <div class="pd-weak-copy">
                <div><strong>{{ item.name }}</strong><b>{{ item.masteryPct }}%</b></div>
                <div class="pd-weak-track"><span :style="{ width: `${item.masteryPct}%` }" /></div>
              </div>
            </article>
          </div>
          <p v-else class="pd-side-empty">完成一次课程练习后，将生成实时薄弱点排序。</p>
          <router-link v-if="primaryWeakness" to="/path" class="pd-side-more">
            查看个性化补强路径 <ArrowRight :size="12" />
          </router-link>
        </ArtCard>

        <!-- 风险提醒 -->
        <ArtCard class="pd-side-card">
          <SectionTitle title="风险提醒" sub="需要关注的薄弱环节">
            <template #action><AlertTriangle :size="16" /></template>
          </SectionTitle>
          <ul class="pd-bullet-list danger">
            <li v-for="(r, i) in riskList" :key="i">
              <span class="dot" />
              <span>{{ r.text }}</span>
            </li>
          </ul>
        </ArtCard>

        <!-- 个性化建议 -->
        <ArtCard class="pd-side-card">
          <SectionTitle title="个性化建议" sub="画像驱动 · 推荐执行">
            <template #action><Check :size="16" /></template>
          </SectionTitle>
          <ul class="pd-bullet-list check">
            <li v-for="(a, i) in adviceList" :key="i">
              <Check :size="13" class="pd-check-icon" />
              <span>{{ a.text }}</span>
            </li>
          </ul>
          <router-link to="/chat" class="pd-side-more">
            查看完整建议 <ArrowRight :size="12" />
          </router-link>
        </ArtCard>

        <!-- 学习档案 -->
        <ArtCard class="pd-side-card">
          <SectionTitle title="学习档案" sub="长期学习数据沉淀">
            <template #action><FileText :size="16" /></template>
          </SectionTitle>
          <ul class="pd-archive-list">
            <li v-for="(a, i) in archiveItems" :key="i">
              <span class="pd-archive-label">{{ a.label }}</span>
              <span class="pd-archive-value">{{ a.value }}</span>
            </li>
          </ul>
          <button type="button" class="pd-side-more pd-side-more-btn" @click="archiveOpen = true">
            查看完整档案 <ArrowRight :size="12" />
          </button>
        </ArtCard>

        <!-- 最近更新 -->
        <ArtCard class="pd-side-card">
          <SectionTitle title="最近更新" :sub="`待确认 ${stats.pendingCount} 条`">
            <template #action><Clock :size="16" /></template>
          </SectionTitle>
          <ul class="pd-recent">
            <li v-if="!recentUpdates.length">
              <CheckCircle2 :size="14" class="pd-recent-ok" />
              <span>暂无待确认画像更新</span>
            </li>
            <li v-for="(ru, i) in recentUpdates.slice(0, 5)" :key="i">
              <span class="dot" :style="{ background: ru.dotColor }" />
              <span class="t">{{ ru.time }}</span>
              <span class="a">{{ ru.action }}</span>
            </li>
          </ul>
          <div v-if="updateQueue.length" class="pd-side-more" @click="$router.push('/profile#queue')">
            查看更新队列 ({{ updateQueue.length }}) <ArrowRight :size="12" />
          </div>
        </ArtCard>

        <ArtCard class="pd-side-card pd-driven-action-card">
          <SectionTitle title="画像驱动学习动作" sub="每条动作由画像字段触发">
            <template #action><Zap :size="16" /></template>
          </SectionTitle>
          <div class="pd-driven">
            <div v-for="(act, i) in drivenActions.slice(0, 4)" :key="i" class="pd-driven-card" :class="act.type">
              <div class="pd-driven-icon">
                <component :is="act.type === 'resource' ? BookOpen : act.type === 'review' ? CheckCircle2 : Zap" :size="16" />
              </div>
              <div class="pd-driven-body">
                <strong>{{ act.title }}</strong>
                <span class="pd-driven-trigger">触发字段：{{ act.triggerFieldLabel }} = {{ formatDimValue(profile[act.triggerField]) }}</span>
                <p>{{ act.reason }}</p>
                <span class="pd-driven-source">来源依据：{{ act.sourceBasis }}</span>
              </div>
              <router-link v-if="act.actionUrl" class="pd-driven-btn" :to="act.actionUrl">
                {{ act.actionLabel }} <ArrowRight :size="12" />
              </router-link>
              <button v-else class="pd-driven-btn" type="button">{{ act.actionLabel }}</button>
            </div>
            <div v-if="!drivenActions.length" class="pd-empty-state">
              <Target :size="28" />
              <p>暂无驱动动作</p>
              <span>去群聊对话生成画像后查看</span>
            </div>
          </div>
        </ArtCard>
      </aside>
    </div>
  </div>

  <!-- ============ 报告抽屉 ============ -->
  <div v-if="reportOpen && report" class="pd-mask" @click.self="reportOpen = false">
    <div class="pd-drawer">
      <header>
        <FileText :size="17" />
        <div class="pd-drawer-title">
          <strong>学习诊断报告 · {{ report.nickname }}</strong>
          <small>焦点：{{ report.focus_kp_id }} · 生成耗时 {{ report.duration_ms }}ms</small>
        </div>
        <div class="pd-report-actions">
          <button class="pd-ghost-btn" type="button" @click="openReportInNewWindow">
            <ExternalLink :size="14" />新窗口打开
          </button>
          <button class="pd-ghost-btn" type="button" @click="downloadReport">
            <Download :size="14" />下载 HTML
          </button>
        </div>
        <button type="button" class="pd-close" aria-label="关闭" @click="reportOpen = false">
          <X :size="17" />
        </button>
      </header>
      <p v-if="reportError" class="pd-drawer-error" role="alert">{{ reportError }}</p>
      <div class="pd-drawer-body">
        <MarkdownBlock :content="report.markdown" />
      </div>
    </div>
  </div>

  <!-- ============ AI 诊断弹窗 ============ -->
  <div v-if="diagnosisOpen" class="pd-mask" @click.self="diagnosisOpen = false">
    <div class="pd-modal wide">
      <header>
        <Brain :size="18" style="color: #E65A1A;" />
        <div>
          <strong>AI 诊断</strong>
          <small>基于知识掌握、错题、练习与画像字段的综合判断</small>
        </div>
        <button type="button" class="pd-close" @click="diagnosisOpen = false"><X :size="17" /></button>
      </header>
      <div class="pd-modal-body">
        <div class="pd-diagnosis-grid">
          <section class="pd-diagnosis-panel">
            <h4>当前问题</h4>
            <ul class="pd-bullet-list danger">
              <li v-for="(r, i) in riskList" :key="i">
                <span class="dot" />
                <span>{{ r.text }}</span>
              </li>
            </ul>
          </section>
          <section class="pd-diagnosis-panel">
            <h4>优势亮点</h4>
            <ul class="pd-bullet-list">
              <li v-for="(c, i) in conclusionList" :key="i">
                <span class="dot" />
                <span>{{ c.text }}</span>
              </li>
            </ul>
          </section>
          <section class="pd-diagnosis-panel">
            <h4>改进建议</h4>
            <ul class="pd-bullet-list check">
              <li v-for="(a, i) in adviceList" :key="i">
                <Check :size="13" class="pd-check-icon" />
                <span>{{ a.text }}</span>
              </li>
            </ul>
          </section>
          <section class="pd-diagnosis-panel">
            <h4>模型诊断</h4>
            <div v-if="aiDiagnosis.length" class="pd-diagnosis-cards">
              <article v-for="d in aiDiagnosis" :key="d.title" :class="['pd-diagnosis-card', d.type]">
                <strong>{{ d.title }}</strong>
                <p>{{ d.content }}</p>
              </article>
            </div>
            <div v-else class="pd-empty-state">
              <Brain :size="26" />
              <p>暂无模型诊断</p>
              <span>完成更多练习或群聊后会自动生成。</span>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>

  <!-- ============ 学习档案弹窗 ============ -->
  <div v-if="archiveOpen" class="pd-mask" @click.self="archiveOpen = false">
    <div class="pd-modal">
      <header>
        <FileText :size="18" style="color: #2563eb;" />
        <div>
          <strong>完整学习档案</strong>
          <small>长期学习数据沉淀与画像证据概览</small>
        </div>
        <button type="button" class="pd-close" @click="archiveOpen = false"><X :size="17" /></button>
      </header>
      <div class="pd-modal-body">
        <ul class="pd-archive-list pd-archive-list-modal">
          <li v-for="(a, i) in archiveItems" :key="i">
            <span class="pd-archive-label">{{ a.label }}</span>
            <span class="pd-archive-value">{{ a.value }}</span>
          </li>
          <li>
            <span class="pd-archive-label">画像版本</span>
            <span class="pd-archive-value">V{{ stats.version }}</span>
          </li>
          <li>
            <span class="pd-archive-label">特征节点</span>
            <span class="pd-archive-value">{{ stats.featureNodes }} 个</span>
          </li>
          <li>
            <span class="pd-archive-label">证据来源</span>
            <span class="pd-archive-value">{{ stats.evidenceCount }} 条</span>
          </li>
          <li>
            <span class="pd-archive-label">待确认更新</span>
            <span class="pd-archive-value">{{ stats.pendingCount }} 条</span>
          </li>
        </ul>
      </div>
    </div>
  </div>

  <!-- ============ 时光机弹窗 ============ -->
  <div v-if="timeMachineOpen" class="pd-mask" @click.self="closeTimeMachine">
    <div class="pd-modal wide">
      <header>
        <Clock :size="18" style="color: var(--eco-earth);" />
        <div>
          <strong>画像时光机</strong>
          <small>回放画像从 V0 到 V{{ stats.version }} 的演变过程</small>
        </div>
        <button type="button" class="pd-close" @click="closeTimeMachine"><X :size="17" /></button>
      </header>
      <div class="pd-modal-body">
        <div class="tm-controls">
          <button class="pd-play-btn" @click="playTimeMachine">
            <Play v-if="!isPlaying" :size="16" />
            <Pause v-else :size="16" />
            {{ isPlaying ? '暂停' : '播放' }}演变
          </button>
          <div class="tm-timeline">
            <div v-for="(snap, idx) in historySnapshots" :key="idx"
                 class="tm-timeline-point"
                 :class="{ active: currentSnapshotIndex === idx, passed: currentSnapshotIndex > idx }"
                 @click="seekSnapshot(idx)">
              <span class="tm-point-dot" />
              <span class="tm-point-label">V{{ snap.version }}</span>
              <span class="tm-point-time">{{ fmtTime(snap.timestamp) }}</span>
            </div>
          </div>
        </div>
        <div class="tm-preview">
          <h4>V{{ historySnapshots[currentSnapshotIndex]?.version ?? 1 }} 画像状态</h4>
          <div class="tm-changes" v-if="historySnapshots[currentSnapshotIndex]?.changedKeys?.length">
            <span class="tm-change-tag">本次更新：</span>
            <span v-for="key in historySnapshots[currentSnapshotIndex].changedKeys" :key="key" class="tm-change-item">
              {{ DIMENSION_META[key]?.label ?? key }}
            </span>
          </div>
          <div class="tm-dims-grid">
            <div v-for="dim in DIMENSION_KEYS" :key="dim" class="tm-dim-card"
                 :style="{ borderColor: DIMENSION_COLORS[dim] }">
              <component :is="DIMENSION_META[dim].icon" :size="16" :style="{ color: DIMENSION_COLORS[dim] }" />
              <span class="tm-dim-label">{{ DIMENSION_META[dim].label }}</span>
              <span class="tm-dim-value">{{ formatDimValue(timeMachineProfile[dim]) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ============ 证据溯源弹窗 ============ -->
  <div v-if="evidenceModalOpen" class="pd-mask" @click.self="closeEvidenceModal">
    <div class="pd-modal">
      <header>
        <GitBranch :size="18" style="color: #f59e0b;" />
        <div>
          <strong>证据溯源</strong>
          <small>字段级原始数据来源追踪</small>
        </div>
        <button type="button" class="pd-close" @click="closeEvidenceModal"><X :size="17" /></button>
      </header>
      <div class="pd-modal-body">
        <div v-if="selectedEvidence" class="evd-detail">
          <div class="evd-row">
            <span class="lab">字段</span>
            <span class="val">{{ DIMENSION_META[selectedEvidence.field]?.label ?? selectedEvidence.field }}</span>
          </div>
          <div class="evd-row">
            <span class="lab">当前值</span>
            <span class="val orange">{{ selectedEvidence.value }}</span>
          </div>
          <div class="evd-row">
            <span class="lab">来源类型</span>
            <span class="val">{{ selectedEvidence.source.type }}</span>
          </div>
          <div class="evd-row">
            <span class="lab">抽取方式</span>
            <span class="val">{{ selectedEvidence.source.details }}</span>
          </div>
          <div class="evd-row">
            <span class="lab">更新时间</span>
            <span class="val">{{ fmtTime(selectedEvidence.source.timestamp) }}</span>
          </div>
          <div class="evd-actions">
            <button class="pd-btn primary" @click="$router.push('/chat')">
              <MessageCircle :size="14" /> 查看原始对话
            </button>
            <button class="pd-btn" @click="closeEvidenceModal">关闭</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ============ 画像预测弹窗 ============ -->
  <div v-if="predictionOpen" class="pd-mask" @click.self="predictionOpen = false">
    <div class="pd-modal wide">
      <header>
        <TrendingUp :size="18" style="color: var(--eco-green);" />
        <div>
          <strong>画像预测</strong>
          <small>基于当前学习轨迹的 AI 趋势预测</small>
        </div>
        <button type="button" class="pd-close" @click="predictionOpen = false"><X :size="17" /></button>
      </header>
      <div class="pd-modal-body">
        <div class="pred-intro">
          <Sparkles :size="16" />
          <span>根据你的学习节奏和当前画像状态，AI 预测未来变化趋势</span>
        </div>
        <div class="pred-list">
          <div v-for="(pred, idx) in futurePredictions" :key="idx" class="pred-card">
            <div class="pred-head">
              <span class="pred-dim" :style="{ color: DIMENSION_COLORS[pred.dim] }">{{ pred.label }}</span>
              <span class="pred-days">{{ pred.days }} 天后</span>
            </div>
            <div class="pred-timeline">
              <div class="pred-point">
                <span class="pred-dot" />
                <span class="pred-lab">当前</span>
                <span class="pred-val">{{ pred.current }}</span>
              </div>
              <div class="pred-arrow">→</div>
              <div class="pred-point">
                <span class="pred-dot" style="background: var(--eco-green);" />
                <span class="pred-lab">预测</span>
                <span class="pred-val highlight">{{ pred.predicted }}</span>
              </div>
            </div>
            <div class="pred-confidence">
              <span>置信度</span>
              <div class="pred-bar"><div class="pred-fill" :style="{ transform: `scaleX(${pred.confidence / 100})` }" /></div>
              <span>{{ pred.confidence }}%</span>
            </div>
          </div>
        </div>
        <div v-if="!futurePredictions.length" class="pred-empty">
          <p>数据积累不足，暂时无法生成预测</p>
          <span>继续学习，AI 将为你预测画像演变趋势</span>
        </div>
      </div>
    </div>
  </div>

</template>

<style scoped>
/* ==========================================================================
   全局工具
   ========================================================================== */
.spin { animation: pd-spin 1s linear infinite; }
@keyframes pd-spin { to { transform: rotate(360deg); } }

.pd-loading {
  display: flex; justify-content: center; align-items: center;
  padding: 28px 0; color: var(--muted); font-size: 13px;
}

.text-success { color: #16a34a; font-weight: 600; }
.text-danger { color: #ef4444; font-weight: 600; }

/* ==========================================================================
   页面容器
   ========================================================================== */
.profile-dashboard {
  background: #fafaf9;
  padding: 24px 28px 40px;
  border-radius: 14px;
  min-height: calc(100vh - 120px);
}

/* ==========================================================================
   顶部 Header
   ========================================================================== */
.pd-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 20px; margin-bottom: 22px; flex-wrap: wrap;
}
.pd-header-titles h1 {
  margin: 0 0 4px; font-size: 22px; font-weight: 700;
  color: var(--ink); letter-spacing: -0.01em;
}
.pd-header-titles p {
  margin: 0; font-size: 13px; color: var(--muted); line-height: 1.4;
  max-width: 480px;
}
.pd-header-actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }

.pd-primary-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
  background: #E65A1A; color: #fff; border: none; cursor: pointer;
  transition: background 0.15s;
}
.pd-primary-btn:hover { background: #cc4d15; }

.pd-ghost-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 7px 12px; border-radius: 8px; font-size: 12.5px;
  border: 1px solid #e8e6e1; background: #fff; color: var(--ink);
  cursor: pointer; transition: border-color 0.15s;
}
.pd-ghost-btn:hover { border-color: #d6cfc0; }
.pd-ghost-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.pd-ghost-btn.danger:hover { border-color: #fca5a5; color: #dc2626; }

.pd-toast {
  margin: 0 0 10px;
  padding: 8px 14px;
  border-radius: 10px;
  background: var(--orange-50, #fff7ed);
  border: 1px solid var(--orange-200, #fed7aa);
  font-size: 12.5px;
  color: var(--orange-600, #ea5a1a);
  line-height: 1.6;
}

/* ==========================================================================
   5 大指标卡（图片风格）
   ========================================================================== */
.pd-metrics {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 12px; margin-bottom: 20px;
}
.pd-metric-card {
  position: relative;
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px; border-radius: 12px;
  background: #fff; border: 1px solid #eeeae3;
  min-height: 72px;
  transition: border-color 0.15s;
}
.pd-metric-card:hover {
  border-color: #d6cfc0;
}
.pd-metric-icon {
  flex-shrink: 0;
  width: 32px; height: 32px;
  border-radius: 8px;
  display: grid; place-items: center;
}
.pd-metric-body { flex: 1; min-width: 0; }
.pd-metric-body small {
  display: block; font-size: 12px; color: var(--muted);
  font-weight: 500; margin-bottom: 2px;
}
.pd-metric-body strong {
  display: block; font-size: 22px; font-weight: 700;
  letter-spacing: -0.02em; line-height: 1.1; margin-bottom: 2px;
}
.pd-unit { font-size: 13px; margin-left: 1px; font-weight: 500; opacity: 0.7; }
.pd-metric-sub { display: block; font-size: 11px; color: var(--muted); }
.pd-metric-delta {
  position: absolute; top: 10px; right: 12px;
  font-size: 11px; padding: 1px 6px; border-radius: 4px;
  background: #f0fdf4; color: #16a34a; font-weight: 600;
}

/* ==========================================================================
   主+侧双栏
   ========================================================================== */
.pd-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
}
.pd-main, .pd-aside { display: flex; flex-direction: column; gap: 14px; min-width: 0; }

.pd-current-weakness-list { display: grid; gap: 10px; }
.pd-current-weakness-item { display: flex; align-items: center; gap: 10px; }
.pd-weak-rank {
  display: grid;
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  place-items: center;
  border-radius: 50%;
  background: #fff0e8;
  color: #d94f12;
  font-size: 12px;
  font-weight: 800;
}
.pd-weak-copy { flex: 1; min-width: 0; }
.pd-weak-copy > div:first-child { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
.pd-weak-copy b { color: #d94f12; }
.pd-weak-track { height: 5px; margin-top: 6px; overflow: hidden; border-radius: 999px; background: #f1ebe7; }
.pd-weak-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #f6a15f, #e85918); }
.pd-side-empty { margin: 0; color: #8b817b; font-size: 12px; line-height: 1.6; }

/* ==========================================================================
   通用 section / half-card 占位
   ========================================================================== */
.pd-section, .pd-half-card, .pd-learner-card, .pd-side-card { padding: 16px 18px; }

/* ==========================================================================
   学习者信息卡
   ========================================================================== */
.pd-learner { display: flex; flex-direction: column; gap: 18px; }
.pd-learner-hero {
  display: flex; align-items: center; gap: 14px;
}
.pd-avatar { flex-shrink: 0; }
.pd-avatar-img {
  width: 48px; height: 48px; border-radius: 12px;
  object-fit: cover; display: block;
}
.pd-avatar-fallback {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #fff;
  font-family: var(--serif);
  font-size: 22px;
  font-weight: 800;
}
.pd-avatar-large .pd-avatar-fallback {
  width: 94px;
  height: 94px;
  border: 4px solid #fff;
  border-radius: 8px;
  font-size: 38px;
  box-shadow: 0 10px 24px rgba(53, 107, 130, 0.18);
}
.pd-learner-meta strong {
  display: block; font-size: 16px; color: var(--ink); margin-bottom: 2px;
}
.pd-learner-meta small { display: block; font-size: 12px; color: var(--muted); }

/* ==========================================================================
   能力雷达 + 趋势
   ========================================================================== */
.pd-radar-wrap {
  height: 280px;
  margin-top: 6px;
}
.pd-radar-foot {
  display: flex; gap: 8px; flex-wrap: wrap;
  margin-top: 8px; padding-top: 12px; border-top: 1px dashed #e8e6e1;
}
.pd-radar-tag {
  font-size: 12px; padding: 4px 10px; border-radius: 999px;
  background: #fafaf9; color: var(--ink); font-weight: 500;
  border: 1px solid #e8e6e1;
}
.pd-radar-tag.orange { background: #fff7ed; color: #E65A1A; border-color: #fed7aa; }
.pd-radar-tag.gray { background: #f4f3f0; color: var(--muted); }

.pd-trend-wrap { padding: 4px 0 0; }
.pd-trend-svg { width: 100%; height: 220px; display: block; }
.pd-trend-axis text { fill: #94a3b8; font-size: 10px; }
.pd-side-trend-card .pd-trend-svg { height: 190px; }

/* ==========================================================================
   学习行为洞察 5 卡
   ========================================================================== */
.pd-insights {
  display: grid; grid-template-columns: repeat(5, 1fr);
  gap: 12px; margin-top: 6px;
}
.pd-insight-card {
  background: #fff;
  border: 1px solid #eeeae3;
  border-radius: 12px;
  padding: 14px;
  display: flex; flex-direction: column; gap: 4px;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.pd-insight-card:hover {
  border-color: #d6cfc0;
}
.pd-insight-icon {
  width: 36px; height: 36px; border-radius: 10px;
  display: grid; place-items: center;
  margin-bottom: 4px;
}
.pd-insight-card small {
  font-size: 11.5px; color: var(--muted); font-weight: 500;
}
.pd-insight-card strong {
  display: block; font-size: 14px; font-weight: 700; color: var(--ink);
  line-height: 1.35;
}
.pd-insight-sub {
  display: block; font-size: 11.5px; color: #807a70;
  line-height: 1.5; margin-top: 2px;
}
.pd-insight-meta {
  display: inline-block; font-size: 11px;
  padding: 2px 8px; border-radius: 4px;
  background: #f4f3f0; color: var(--muted); margin-top: 4px;
  font-weight: 500; align-self: flex-start;
}

/* ==========================================================================
   知识掌握分布
   ========================================================================== */
.pd-knowledge { display: flex; flex-direction: column; gap: 12px; margin-top: 6px; }
.pd-knowledge-row {
  display: grid;
  grid-template-columns: 110px 1fr 56px 56px;
  align-items: center; gap: 14px;
}
.pd-knowledge-name { font-size: 13.5px; color: var(--ink); font-weight: 500; }
.pd-bar {
  height: 8px; background: #f4f3f0; border-radius: 999px;
  overflow: hidden; position: relative;
}
.pd-bar-fill { width: 100%; height: 100%; border-radius: 999px; transform-origin: left center; transition: transform 0.32s ease; }
.pd-knowledge-pct {
  font-size: 13.5px; font-weight: 700; color: var(--ink); text-align: right;
}
.pd-knowledge-tag {
  font-size: 11px; padding: 3px 10px; border-radius: 6px;
  text-align: center; font-weight: 600;
}

/* ==========================================================================
   AI 个性化建议
   ========================================================================== */
.pd-suggestions {
  display: flex; flex-direction: column; gap: 12px;
  margin-top: 6px;
}
.pd-suggestion-card {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; border-radius: 12px;
  background: #fafaf9; border: 1px solid #eeeae3;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.pd-suggestion-card:hover {
  border-color: #d6cfc0;
}
.pd-suggestion-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: grid; place-items: center; flex-shrink: 0;
}
.pd-suggestion-body { flex: 1; min-width: 0; }
.pd-suggestion-body strong {
  display: block; font-size: 14px; color: var(--ink); margin-bottom: 2px; font-weight: 700;
}
.pd-suggestion-body span {
  display: block; font-size: 12.5px; color: var(--muted);
}
.pd-suggestion-btn {
  display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0;
  padding: 7px 16px; border-radius: 8px; font-size: 12.5px; font-weight: 600;
  background: #fff7ed; color: #E65A1A; border: 1px solid #fed7aa;
  text-decoration: none; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.pd-suggestion-btn:hover {
  background: #E65A1A; color: #fff; border-color: #E65A1A;
}

.pd-driven { display: flex; flex-direction: column; gap: 10px; }
.pd-driven-card {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 12px 14px; border-radius: 10px;
  background: #fafaf9; border: 1px solid #eeeae3;
}
.pd-driven-icon {
  width: 32px; height: 32px; border-radius: 8px;
  display: grid; place-items: center; flex-shrink: 0;
  background: #fff; border: 1px solid #e8e6e1;
}
.pd-driven-card.resource .pd-driven-icon { background: #eff6ff; color: #2563eb; border-color: #dbeafe; }
.pd-driven-card.review .pd-driven-icon { background: #f0fdf4; color: #16a34a; border-color: #bbf7d0; }
.pd-driven-card.strategy .pd-driven-icon { background: #fff7ed; color: #ea580c; border-color: #fed7aa; }
.pd-driven-body { flex: 1; min-width: 0; }
.pd-driven-body strong {
  display: block; font-size: 13px; color: var(--ink); margin-bottom: 3px; font-weight: 700;
}
.pd-driven-trigger {
  display: block; font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #fff7ed; color: #c2410c; font-weight: 500;
  display: inline-block; margin-bottom: 4px;
}
.pd-driven-body p { margin: 4px 0; font-size: 12px; color: var(--muted); line-height: 1.45; }
.pd-driven-source {
  display: inline-block; font-size: 11px; color: #807a70;
  padding: 2px 8px; background: #f4f3f0; border-radius: 4px;
}
.pd-driven-btn {
  display: inline-flex; align-items: center; gap: 4px; flex-shrink: 0;
  padding: 6px 12px; border-radius: 7px; font-size: 11.5px; font-weight: 600;
  background: #E65A1A; color: #fff; border: 0;
  text-decoration: none; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
  margin-top: 2px;
}
.pd-driven-btn:hover { background: #cc4d15; }

.pd-empty-state {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 36px 0; color: var(--muted); text-align: center;
}
.pd-empty-state p { margin: 0; font-size: 14px; color: var(--ink); }

/* ==========================================================================
   侧栏 - bullet list (画像结论 / 风险提醒 / 个性化建议)
   ========================================================================== */
.pd-bullet-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; margin-top: 6px; }
.pd-bullet-list li {
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 13px; color: var(--ink); line-height: 1.5;
}
.pd-bullet-list .dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: #16a34a; margin-top: 6px;
}
.pd-bullet-list.warn .dot { background: #ea580c; }
.pd-bullet-list.danger .dot { background: #ef4444; }

.pd-bullet-list.danger li .dot { background: #ef4444; }

.pd-check-icon { color: #16a34a; margin-top: 3px; flex-shrink: 0; }

.pd-side-more {
  display: inline-flex; align-items: center; gap: 4px;
  margin-top: 14px; font-size: 12px; font-weight: 600;
  color: #E65A1A; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}
.pd-side-more:hover { gap: 8px; }
.pd-side-more-btn {
  background: transparent; border: 0; padding: 0; font: inherit;
}

.pd-archive-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0; margin-top: 6px; }
.pd-archive-list li {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 0; border-bottom: 1px dashed #eeeae3;
  font-size: 13px;
}
.pd-archive-list li:last-child { border-bottom: 0; }
.pd-archive-label { color: var(--muted); }
.pd-archive-value { color: var(--ink); font-weight: 600; }
.pd-archive-list-modal li { padding: 12px 0; }

.pd-diagnosis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.pd-diagnosis-panel {
  border: 1px solid #eeeae3;
  border-radius: 12px;
  background: #fff;
  padding: 14px;
}
.pd-diagnosis-panel h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--ink);
}
.pd-diagnosis-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pd-diagnosis-card {
  border-radius: 10px;
  border: 1px solid #eeeae3;
  background: #fafaf9;
  padding: 10px 12px;
}
.pd-diagnosis-card strong {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--ink);
}
.pd-diagnosis-card p {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--muted);
}
.pd-diagnosis-card.good { border-color: #bbf7d0; background: #f0fdf4; }
.pd-diagnosis-card.warn { border-color: #fed7aa; background: #fff7ed; }

/* ==========================================================================
   侧栏 - 画像速览 mini tree
   ========================================================================== */
.pd-mini-tree { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
.pd-mini-node {
  border-radius: 8px; transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
  border: 1px solid transparent;
}
.pd-mini-node:hover { border-color: var(--node-color); background: #fafaf9; }
.pd-mini-head {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 8px; cursor: pointer; border-radius: 8px;
}
.pd-mini-icon-wrap {
  width: 22px; height: 22px; border-radius: 6px;
  display: grid; place-items: center; flex-shrink: 0;
  background: var(--node-color); color: #fff;
}
.pd-mini-label { font-size: 12.5px; font-weight: 600; color: var(--ink); flex: 1; }
.pd-mini-count {
  font-size: 10px; padding: 1px 6px; border-radius: 999px;
  background: #f4f3f0; color: var(--muted); font-weight: 600;
}
.pd-mini-toggle { color: var(--muted); }
.pd-mini-children { padding: 2px 0 6px 30px; }
.pd-mini-leaf {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px; font-size: 12px; border-radius: 6px;
}
.pd-mini-leaf .dot { width: 6px; height: 6px; flex-shrink: 0; margin-top: 0; }
.leaf-l { color: var(--ink); flex: 1; }
.leaf-t {
  font-size: 10.5px; padding: 1px 8px; border-radius: 4px;
  font-weight: 600;
}
.leaf-t.unknown { background: #f4f3f0; color: var(--muted); }
.pd-mini-more {
  padding: 4px 8px 0; font-size: 11px; color: var(--muted);
}

/* ==========================================================================
8 维概览卡片 + 5 Tab 常驻导航
========================================================================== */
.pd-dim-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 10px;
}
.pd-dim-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #eeeae3;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: border-color .15s;
}
.pd-dim-card:hover {
  border-color: #d6cfc0;
}
.pd-dim-card.active {
  border-color: var(--dim-color, #e65a1a);
  background: #fafaf9;
}
.pd-dim-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  flex-shrink: 0;
  color: var(--dim-color, #6b7280);
}
.pd-dim-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.pd-dim-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}
.pd-dim-desc {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pd-tabs-card { padding-bottom: 6px; }
.pd-tabs-nav {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.pd-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border: 0;
  background: transparent;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color .15s, border-color .15s;
}
.pd-tab-btn:hover { color: #e65a1a; }
.pd-tab-btn.active {
  color: #e65a1a;
  border-bottom-color: #e65a1a;
}

.pd-tab-content { min-height: 200px; }
.pd-tab-panel { animation: pd-fade-in .2s ease; }
@keyframes pd-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 证据溯源 Tab 内部布局 */
.pd-evidence-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 18px;
}
.pd-evidence-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
}
.pd-evidence-field .evd-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.pd-evidence-field .evd-row .lab { color: #6b7280; min-width: 70px; }
.pd-evidence-field .evd-row .val { font-weight: 600; color: #1f2937; }
.pd-evidence-field .evd-row .val.orange { color: #e65a1a; }
.pd-conf-bar {
  flex: 1;
  height: 8px;
  border-radius: 4px;
  background: #e5e7eb;
  overflow: hidden;
  min-width: 60px;
}
.pd-conf-fill { width: 100%; height: 100%; border-radius: 4px; transform-origin: left center; transition: transform .24s ease; }

.pd-evidence-sources h4 { margin: 0 0 10px; font-size: 14px; color: #1f2937; }
.pd-source-list { display: flex; flex-direction: column; gap: 8px; }
.pd-source-card {
  display: flex;
  gap: 10px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
}
.pd-source-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  flex-shrink: 0;
}
.pd-source-body { flex: 1; min-width: 0; }
.pd-source-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.pd-source-head strong { font-size: 13px; color: #1f2937; }
.pd-source-type {
  font-size: 11px;
  color: #6b7280;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f1f5f9;
}
.pd-source-strength {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  margin-left: auto;
}
.pd-source-body p { margin: 0; font-size: 12px; color: #4b5563; line-height: 1.5; }

@media (max-width: 1100px) {
  .pd-dim-grid { grid-template-columns: 1fr; }
  .pd-evidence-layout { grid-template-columns: 1fr; }
  .pd-grid { grid-template-columns: 1fr; }
  .pd-metrics { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .pd-dim-grid { grid-template-columns: 1fr; }
  .pd-metrics { grid-template-columns: 1fr; }
}

/* ==========================================================================
侧栏 - 深度工具
========================================================================== */
.pd-tools { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.pd-tool {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 12px; border-radius: 10px;
  background: #fafaf9; border: 1px solid #eeeae3;
  font-size: 13px; font-weight: 500; color: var(--ink);
  cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease; text-align: left;
  position: relative;
}
.pd-tool:hover { border-color: #fbcfa3; background: #fff7ed; color: #E65A1A; }
.pd-tool-badge {
  position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  background: #ef4444; color: #fff; font-size: 10px; font-weight: 700;
  padding: 1px 7px; border-radius: 999px;
}

/* ==========================================================================
   侧栏 - 最近更新
   ========================================================================== */
.pd-recent { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.pd-recent li {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px;
}
.pd-recent li .dot { width: 6px; height: 6px; flex-shrink: 0; margin-top: 0; }
.pd-recent .t { color: var(--muted); font-size: 11px; flex-shrink: 0; min-width: 64px; }
.pd-recent .a { color: var(--ink); flex: 1; }
.pd-recent-ok { color: #16a34a; flex-shrink: 0; }

/* ==========================================================================
   展开动画
   ========================================================================== */
.expand-enter-active, .expand-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; overflow: hidden; }
.expand-enter-from, .expand-leave-to { opacity: 0; transform: translateY(-4px); }
.expand-enter-to, .expand-leave-from { opacity: 1; transform: translateY(0); }

/* ==========================================================================
   报告抽屉
   ========================================================================== */
.pd-mask {
  position: fixed; inset: 0; z-index: 90;
  background: rgba(25, 21, 17, 0.4); display: flex; justify-content: flex-end;
}
.pd-drawer {
  width: min(640px, 94vw); height: 100%; background: #fff;
  box-shadow: 0 8px 32px rgba(0,0,0,0.15); display: flex; flex-direction: column;
}
.pd-drawer header {
  display: flex; align-items: center; gap: 12px; padding: 14px 18px;
  border-bottom: 1px solid #e8e6e1; color: #E65A1A;
}
.pd-drawer-title { flex: 1; min-width: 0; }
.pd-drawer header strong { display: block; font-size: 14.5px; color: var(--ink); }
.pd-drawer header small { font-size: 11px; color: var(--muted); }
.pd-report-actions { display: flex; align-items: center; gap: 8px; }
.pd-drawer-error {
  margin: 0; padding: 10px 18px; border-bottom: 1px solid #fed7aa;
  background: #fff7ed; color: #c2410c; font-size: 12px; line-height: 1.5;
}
.pd-close {
  display: grid; place-items: center; width: 30px; height: 30px;
  border-radius: 9px; color: var(--muted); border: 0; background: transparent; cursor: pointer;
}
.pd-close:hover { background: #fafaf9; }
.pd-drawer-body { flex: 1; overflow-y: auto; padding: 18px 22px 40px; }
@media (max-width: 640px) {
  .pd-drawer header { flex-wrap: wrap; }
  .pd-drawer-title { flex: 1 1 220px; }
  .pd-report-actions { order: 3; width: 100%; }
  .pd-report-actions .pd-ghost-btn { flex: 1; justify-content: center; }
}

/* ==========================================================================
   5 大弹窗通用
   ========================================================================== */
.pd-modal {
  width: min(540px, 94vw); max-height: 90vh;
  background: #fff; border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
  display: flex; flex-direction: column; overflow: hidden;
  margin: auto;
}
.pd-modal.wide { width: min(740px, 94vw); }
.pd-modal header {
  display: flex; align-items: center; gap: 12px;
  padding: 16px 20px; border-bottom: 1px solid #e8e6e1;
}
.pd-modal header > div { flex: 1; min-width: 0; }
.pd-modal header strong { display: block; font-size: 15px; color: var(--ink); }
.pd-modal header small { font-size: 12px; color: var(--muted); }
.pd-modal-body { flex: 1; overflow-y: auto; padding: 20px; }

/* ==========================================================================
   时光机
   ========================================================================== */
.tm-controls { margin-bottom: 20px; }
.pd-play-btn {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 8px;
  background: var(--eco-green); color: #fff; border: none; font-weight: 600; font-size: 13px;
  cursor: pointer; margin-bottom: 16px; transition: background 0.15s;
}
.pd-play-btn:hover { background: var(--eco-green-dark); }
.tm-timeline { display: flex; gap: 8px; overflow-x: auto; padding: 8px 0; }
.tm-timeline-point {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 8px 12px; border-radius: 8px; cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease; min-width: 70px;
  border: 2px solid transparent;
}
.tm-timeline-point:hover { background: #fafaf9; }
.tm-timeline-point.active { background: var(--eco-sage); border-color: var(--eco-green); }
.tm-timeline-point.passed .tm-point-dot { background: var(--eco-green); }
.tm-point-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: #d1d5db; transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, background 0.2s ease, color 0.2s ease;
}
.tm-timeline-point.active .tm-point-dot {
  background: var(--eco-green); box-shadow: 0 0 0 4px rgba(232, 111, 71, 0.2);
}
.tm-point-label { font-size: 12px; font-weight: 600; color: var(--ink); }
.tm-point-time { font-size: 10px; color: var(--muted); }

.tm-preview h4 { font-size: 14px; color: var(--ink); margin: 0 0 12px; }
.tm-changes {
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px;
  margin-bottom: 16px; padding: 12px;
  background: #fafaf9; border-radius: 8px;
}
.tm-change-tag { font-size: 12px; color: var(--muted); }
.tm-change-item {
  padding: 4px 10px; background: var(--eco-sage); color: var(--eco-green-dark);
  font-size: 12px; font-weight: 500; border-radius: 4px;
}
.tm-dims-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
.tm-dim-card {
  display: flex; flex-direction: column; gap: 4px;
  padding: 12px; background: #fff;
  border: 1px solid color-mix(in srgb, currentColor 24%, #e8e6e1);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
  border-radius: 8px;
}
.tm-dim-label { font-size: 12px; color: var(--muted); }
.tm-dim-value { font-size: 13px; font-weight: 600; color: var(--ink); }

/* ==========================================================================
   雷达图大屏
   ========================================================================== */
.pd-radar-large { height: 320px; margin-bottom: 18px; }
.pd-radar-stats {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
  padding: 16px; background: #fafaf9; border-radius: 10px;
}
.pd-radar-stat {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
}
.pd-radar-stat .lab { font-size: 12px; color: var(--muted); }
.pd-radar-stat .val { font-size: 18px; font-weight: 700; color: var(--ink); }
.pd-radar-stat .val.orange { color: #E65A1A; }

/* ==========================================================================
   证据溯源
   ========================================================================== */
.evd-detail { display: flex; flex-direction: column; gap: 14px; }
.evd-row {
  display: flex; flex-direction: column; gap: 4px;
  padding: 12px; background: #fafaf9; border-radius: 8px;
}
.evd-row .lab { font-size: 12px; color: var(--muted); }
.evd-row .val { font-size: 14px; color: var(--ink); }
.evd-row .val.orange { color: #E65A1A; font-weight: 600; }
.evd-actions { display: flex; gap: 10px; margin-top: 4px; }
.pd-btn {
  flex: 1; padding: 10px; border-radius: 8px;
  font-size: 13px; font-weight: 600; cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease; border: 1px solid #e8e6e1;
  background: #fff; color: var(--ink);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.pd-btn:hover { background: #f4f3f0; }
.pd-btn.primary { background: #E65A1A; color: #fff; border-color: #E65A1A; }
.pd-btn.primary:hover { background: #cc4d15; }

/* ==========================================================================
   画像预测
   ========================================================================== */
.pred-intro {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--eco-sage) 0%, #fff0e7 100%);
  border-radius: 8px; margin-bottom: 16px;
  color: var(--eco-green-dark); font-size: 13px;
}
.pred-intro svg { color: var(--eco-green); }
.pred-list { display: flex; flex-direction: column; gap: 12px; }
.pred-card {
  padding: 14px; background: #fff;
  border: 1px solid #e8e6e1; border-radius: 10px;
}
.pred-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.pred-dim { font-size: 14px; font-weight: 700; }
.pred-days {
  font-size: 11.5px; color: var(--muted); padding: 3px 10px;
  background: #f4f3f0; border-radius: 4px;
}
.pred-timeline {
  display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
}
.pred-point {
  display: flex; flex-direction: column; gap: 3px; flex: 1;
}
.pred-dot { width: 10px; height: 10px; border-radius: 50%; background: #d1d5db; }
.pred-lab { font-size: 11px; color: #9ca3af; }
.pred-val { font-size: 13px; color: var(--ink); }
.pred-val.highlight { color: var(--eco-green-dark); font-weight: 600; }
.pred-arrow { color: #d1d5db; font-size: 18px; }

.pred-confidence {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: var(--muted);
}
.pred-bar { flex: 1; height: 6px; background: #e8e6e1; border-radius: 3px; overflow: hidden; }
.pred-fill {
  width: 100%; height: 100%; border-radius: 3px;
  background: linear-gradient(90deg, var(--eco-green) 0%, var(--eco-earth) 100%);
  transform-origin: left center;
  transition: transform 0.32s ease;
}

.pred-empty {
  text-align: center; padding: 36px 0;
  color: var(--muted);
}
.pred-empty p { font-size: 14px; margin-bottom: 6px; color: var(--ink); }
.pred-empty span { font-size: 12px; }

/* ==========================================================================
   响应式
   ========================================================================== */
@media (max-width: 1380px) {
  .pd-grid { grid-template-columns: minmax(0, 1fr) 320px; }
  .pd-metrics { grid-template-columns: repeat(5, 1fr); gap: 10px; }
}
@media (max-width: 1280px) {
  .profile-dashboard { padding: 22px 18px 36px; }
  .pd-grid { grid-template-columns: 1fr; }
  .pd-aside { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px; }
  .pd-metrics { grid-template-columns: repeat(5, 1fr); }
  .pd-insights { grid-template-columns: repeat(3, 1fr); }
  .pd-learner-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 1100px) {
  .pd-aside { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .pd-metrics { grid-template-columns: repeat(2, 1fr); }
  .pd-insights { grid-template-columns: 1fr; }
  .pd-knowledge-row { grid-template-columns: 84px 1fr 50px; }
  .pd-knowledge-tag { display: none; }
}
@media (max-width: 640px) {
  .profile-dashboard { padding: 16px; }
  .pd-metrics { grid-template-columns: 1fr; }
  .pd-header { flex-direction: column; align-items: flex-start; }
}

/* ===== AI 错题智能洞察 ===== */
.pd-insights-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 24px;
  color: var(--muted);
  font-size: 13px;
}

.pd-mistake-ai {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pd-ai-summary {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(234, 90, 26, 0.04);
  border: 1px solid rgba(234, 90, 26, 0.12);
}

.pd-ai-summary p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--ink);
  flex: 1;
}

.pd-ai-badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.pd-ai-badge.llm {
  background: linear-gradient(90deg, #ea5a1a, #d89229);
  color: #fff;
}

.pd-ai-badge.rule {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

.pd-ai-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.pd-ai-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pd-ai-label {
  font-size: 12px;
  color: var(--orange-600);
  font-weight: 600;
  margin-bottom: 2px;
}

.pd-weak-kp {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--paper);
  border: 1px solid var(--neutral-200);
  flex-wrap: wrap;
}

.pd-weak-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink);
}

.pd-weak-count {
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 4px;
  background: rgba(179, 65, 58, 0.1);
  color: var(--status-error);
  font-weight: 600;
}

.pd-weak-reason {
  font-size: 11.5px;
  color: var(--muted);
  flex-basis: 100%;
}

.pd-ai-empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--neutral-400);
}

.pd-eval-score {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: 10px;
  background: var(--paper);
  border: 1px solid var(--neutral-200);
}

.pd-eval-ring {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: conic-gradient(var(--orange-500) var(--pct), var(--neutral-200) 0);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
}

.pd-eval-ring::before {
  content: "";
  position: absolute;
  inset: 5px;
  border-radius: 50%;
  background: var(--paper);
}

.pd-eval-ring span {
  position: relative;
  font-size: 16px;
  font-weight: 700;
  color: var(--orange-600);
}

.pd-eval-ring small {
  position: relative;
  font-size: 9px;
  color: var(--neutral-400);
}

.pd-eval-tags {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.pd-eval-tag {
  font-size: 11.5px;
  padding: 2px 8px;
  border-radius: 4px;
}

.pd-eval-tag.green {
  background: rgba(47, 159, 107, 0.1);
  color: var(--status-running);
}

.pd-eval-tag.red {
  background: rgba(179, 65, 58, 0.08);
  color: var(--status-error);
}

.pd-eval-suggestions {
  margin-top: 4px;
}

.pd-suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 0;
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.5;
}

.pd-suggestion-num {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--orange-50);
  color: var(--orange-600);
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pd-ai-section {
  border-top: 1px dashed var(--neutral-200);
  padding-top: 12px;
}

.pd-rec-questions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pd-rec-q {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--neutral-200);
  background: var(--paper);
}

.pd-rec-q-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.pd-rec-bloom {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10.5px;
  font-weight: 600;
  background: rgba(47, 159, 107, 0.1);
  color: var(--status-running);
}

.pd-rec-kp {
  font-size: 11px;
  color: var(--muted);
}

.pd-rec-q-text {
  margin: 0 0 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ink);
}

.pd-rec-q details summary {
  cursor: pointer;
  font-size: 11.5px;
  color: var(--orange-600);
}

.pd-rec-q-answer,
.pd-rec-q-expl {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--neutral-700);
}

.pd-rec-materials {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.pd-rec-mat {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid var(--neutral-200);
  background: var(--paper);
  text-decoration: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
  cursor: pointer;
}

.pd-rec-mat:hover {
  border-color: var(--orange-300);
  box-shadow: 0 2px 8px rgba(234, 90, 26, 0.08);
}

.pd-rec-mat-type {
  flex-shrink: 0;
  padding: 2px 7px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.pd-rec-mat-type.video { background: rgba(234, 90, 26, 0.12); color: var(--orange-600); }
.pd-rec-mat-type.doc { background: rgba(74, 107, 133, 0.12); color: #4a6b85; }
.pd-rec-mat-type.project { background: rgba(47, 159, 107, 0.12); color: var(--status-running); }

.pd-rec-mat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.pd-rec-mat-body strong {
  font-size: 12.5px;
  color: var(--ink);
  line-height: 1.4;
}

.pd-rec-mat-body small {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
}

@media (max-width: 1100px) {
  .pd-ai-row { grid-template-columns: 1fr; }
  .pd-rec-materials { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 640px) {
  .pd-rec-materials { grid-template-columns: 1fr; }
}

/* ===== Impeccable profile polish: calmer dashboard, stronger hierarchy ===== */
.profile-dashboard {
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 250, 245, 0.98) 0%, rgba(250, 250, 249, 0.98) 36%, #fafaf9 100%),
    repeating-linear-gradient(90deg, rgba(234, 90, 26, 0.05) 0 1px, transparent 1px 92px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
}

.profile-dashboard::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 190px;
  background: linear-gradient(110deg, transparent 0%, rgba(255, 255, 255, 0.78) 42%, transparent 62%);
  transform: translateX(-16%);
  opacity: 0.56;
  pointer-events: none;
}

.profile-dashboard > .pd-header,
.profile-dashboard > .pd-toast,
.profile-dashboard > .pd-metrics,
.profile-dashboard > .pd-grid {
  position: relative;
  z-index: 1;
}

.pd-header {
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid rgba(229, 212, 190, 0.86);
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.96), rgba(255, 247, 237, 0.82));
  box-shadow: 0 14px 30px rgba(78, 55, 34, 0.06);
}

.pd-header-titles h1 {
  font-size: 24px;
}

.pd-primary-btn,
.pd-ghost-btn,
.pd-suggestion-btn,
.pd-driven-btn,
.pd-tool,
.pd-btn,
.pd-rec-mat {
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease, color 0.18s ease;
}

.pd-primary-btn:hover,
.pd-suggestion-btn:hover,
.pd-driven-btn:hover,
.pd-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(234, 90, 26, 0.14);
}

.pd-ghost-btn:hover,
.pd-tool:hover,
.pd-rec-mat:hover {
  transform: translateY(-1px);
}

.pd-metric-card {
  background: linear-gradient(180deg, #fffdf8, #fff8f1);
  border-color: rgba(229, 212, 190, 0.88);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.pd-metric-card:hover {
  transform: translateY(-2px);
  border-color: rgba(234, 90, 26, 0.22);
  box-shadow: 0 12px 26px rgba(78, 55, 34, 0.08);
}

.pd-metric-icon,
.pd-dim-icon,
.pd-driven-icon,
.pd-suggestion-icon,
.pd-insight-icon {
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.76);
}

.profile-dashboard .pd-section,
.profile-dashboard .pd-half-card,
.profile-dashboard .pd-learner-card,
.profile-dashboard .pd-side-card {
  border: 1px solid rgba(229, 212, 190, 0.82);
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(255, 250, 246, 0.92));
  box-shadow: 0 14px 30px rgba(78, 55, 34, 0.055);
}

.profile-dashboard .pd-learner-card {
  background:
    linear-gradient(140deg, rgba(255, 247, 237, 0.92), rgba(255, 253, 248, 0.96) 46%, rgba(240, 253, 244, 0.5));
}

.pd-avatar-img {
  border: 1px solid rgba(234, 90, 26, 0.18);
  box-shadow: 0 8px 18px rgba(78, 55, 34, 0.1);
}

.pd-insight-card,
.pd-suggestion-card,
.pd-dim-card,
.pd-rec-q,
.pd-eval-score,
.pd-weak-kp {
  background: linear-gradient(180deg, #fffdf8, #fffaf5);
  border-color: rgba(229, 212, 190, 0.84);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.pd-insight-card:hover,
.pd-suggestion-card:hover,
.pd-dim-card:hover,
.pd-rec-q:hover,
.pd-weak-kp:hover {
  transform: translateY(-2px);
  border-color: rgba(234, 90, 26, 0.2);
  box-shadow: 0 10px 22px rgba(78, 55, 34, 0.07);
}

.pd-dim-card.active {
  background: color-mix(in srgb, var(--dim-color, #e65a1a) 8%, #fffdf8);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--dim-color, #e65a1a) 16%, transparent);
}

.pd-tabs-nav {
  gap: 6px;
  border-bottom-color: rgba(229, 212, 190, 0.9);
}

.pd-tab-btn {
  border-radius: 8px 8px 0 0;
}

.pd-tab-btn:hover,
.pd-tab-btn.active {
  background: rgba(255, 247, 237, 0.72);
}

.pd-eval-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid transparent;
}

.pd-eval-tag.green { border-color: rgba(47, 159, 107, 0.16); }
.pd-eval-tag.red { border-color: rgba(179, 65, 58, 0.16); }

.pd-tag-mark {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 12%, transparent);
}

/* ===========================================================================
   Warm exploration redesign
   ========================================================================== */
.profile-dashboard {
  --pd-coral: #e96f51;
  --pd-coral-strong: #cf563c;
  --pd-peach: #ffe2d6;
  --pd-honey: #f4bd61;
  --pd-mint: #68ad8e;
  --pd-sky: #6d9fc7;
  --pd-ink: #373449;
  --pd-copy: #605d6d;
  --pd-border: #eaded8;
  --pd-surface: #fffdfb;
  --pd-page: #fff8f4;
  --pd-shadow: 0 12px 28px rgba(82, 62, 54, 0.08);
  position: relative;
  overflow: hidden;
  padding: 26px 28px 42px;
  border-radius: 8px;
  background: var(--pd-page);
  color: var(--pd-ink);
}

.profile-dashboard::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 220px;
  pointer-events: none;
  background: rgba(233, 111, 81, 0.035);
  border-bottom: 1px solid rgba(233, 111, 81, 0.08);
}

.profile-dashboard > * {
  position: relative;
  z-index: 1;
}

.pd-warm-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  margin-bottom: 16px;
  padding: 24px;
  overflow: hidden;
  border: 1px solid #edc6b8;
  border-radius: 8px;
  background: #fff3ed;
  box-shadow: var(--pd-shadow);
  animation: pd-warm-rise 360ms ease-out both;
}

.pd-warm-hero::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  width: 132px;
  height: 100%;
  pointer-events: none;
  background: #f8d9cc;
  clip-path: polygon(42% 0, 100% 0, 100% 100%, 0 100%);
  opacity: 0.48;
}

.pd-hero-topline,
.pd-hero-grid,
.pd-hero-badge {
  position: relative;
  z-index: 1;
}

.pd-hero-topline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.pd-header-titles h1 {
  margin: 6px 0 5px;
  color: var(--pd-ink);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.08;
  letter-spacing: 0;
}

.pd-header-titles p {
  max-width: 560px;
  color: var(--pd-copy);
  font-size: 13px;
}

.pd-hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--pd-coral-strong);
  font-size: 12px;
  font-weight: 700;
}

.pd-header-actions {
  position: relative;
  z-index: 2;
  flex-wrap: nowrap;
}

.pd-primary-btn,
.pd-ghost-btn {
  min-height: 36px;
  border-radius: 8px;
  transition: color 180ms ease, background 180ms ease, border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.pd-primary-btn {
  padding-inline: 15px;
  background: var(--pd-coral);
  box-shadow: 0 7px 16px rgba(207, 86, 60, 0.18);
}

.pd-primary-btn:hover {
  background: var(--pd-coral-strong);
  transform: translateY(-1px);
}

.pd-ghost-btn {
  border-color: #e4cfc6;
  background: rgba(255, 253, 251, 0.88);
  color: var(--pd-ink);
}

.pd-ghost-btn:hover {
  border-color: #d9aa99;
  background: #fff;
}

.pd-primary-btn:focus-visible,
.pd-ghost-btn:focus-visible,
.pd-dim-card:focus-visible,
.pd-tab-btn:focus-visible,
.pd-tool:focus-visible,
.pd-side-more:focus-visible {
  outline: 3px solid rgba(109, 159, 199, 0.38);
  outline-offset: 2px;
}

.pd-hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(240px, 0.65fr);
  gap: 20px;
  align-items: stretch;
}

.pd-hero-identity,
.pd-hero-progress {
  min-height: 132px;
  border: 1px solid rgba(218, 172, 153, 0.72);
  border-radius: 8px;
  background: rgba(255, 253, 251, 0.88);
}

.pd-hero-identity {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 20px;
}

.pd-avatar-large .pd-avatar-img {
  width: 82px;
  height: 82px;
  border: 4px solid #fff;
  border-radius: 8px;
  box-shadow: 0 8px 18px rgba(82, 62, 54, 0.14);
}

.pd-hero-label {
  display: block;
  margin-bottom: 5px;
  color: var(--pd-coral-strong);
  font-size: 11px;
  font-weight: 700;
}

.pd-hero-identity .pd-learner-meta strong {
  margin-bottom: 5px;
  color: var(--pd-ink);
  font-size: 23px;
  line-height: 1.15;
}

.pd-hero-identity .pd-learner-meta small {
  color: var(--pd-copy);
  font-size: 13px;
}

.pd-hero-progress {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 18px 20px;
}

.pd-hero-progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--pd-copy);
  font-size: 12px;
  font-weight: 600;
}

.pd-hero-version {
  padding: 3px 8px;
  border: 1px solid #edc6b8;
  border-radius: 999px;
  background: #fff5ef;
  color: var(--pd-coral-strong);
}

.pd-hero-progress > strong {
  margin: 7px 0 6px;
  color: var(--pd-coral-strong);
  font-size: 38px;
  line-height: 1;
}

.pd-hero-progress > strong small {
  margin-left: 2px;
  font-size: 16px;
}

.pd-hero-progress-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #f1ddd5;
}

.pd-hero-progress-bar span {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: left;
  border-radius: inherit;
  background: var(--pd-coral);
  transition: transform 300ms ease-out;
}

.pd-hero-progress p {
  margin: 8px 0 0;
  color: var(--pd-copy);
  font-size: 11px;
}

.pd-hero-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  width: fit-content;
  max-width: 100%;
  padding: 9px 12px;
  border: 1px solid color-mix(in srgb, var(--badge-color) 34%, #eaded8);
  border-radius: 8px;
  background: #fffdfb;
}

.pd-hero-badge-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--badge-color) 14%, white);
  color: var(--badge-color);
}

.pd-hero-badge > div:nth-child(2) span,
.pd-hero-badge > div:nth-child(2) strong {
  display: block;
}

.pd-hero-badge > div:nth-child(2) span {
  color: var(--pd-copy);
  font-size: 10px;
}

.pd-hero-badge > div:nth-child(2) strong {
  color: var(--pd-ink);
  font-size: 13px;
}

.pd-hero-badge-style {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-left: 6px;
  color: var(--badge-color);
  font-size: 11px;
  font-weight: 600;
}

.pd-metrics {
  gap: 10px;
  margin-bottom: 18px;
}

.pd-metric-card {
  min-width: 0;
  min-height: 88px;
  padding: 15px;
  border-color: var(--pd-border);
  border-radius: 8px;
  background: var(--pd-surface);
  box-shadow: 0 7px 18px rgba(82, 62, 54, 0.045);
  animation: pd-warm-rise 360ms ease-out both;
  transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.pd-metric-card:nth-child(2) { animation-delay: 45ms; border-top: 3px solid var(--pd-honey); }
.pd-metric-card:nth-child(3) { animation-delay: 90ms; border-top: 3px solid var(--pd-mint); }
.pd-metric-card:nth-child(4) { animation-delay: 135ms; border-top: 3px solid var(--pd-sky); }
.pd-metric-card:nth-child(5) { animation-delay: 180ms; border-top: 3px solid #9579b8; }
.pd-metric-card:first-child { border-top: 3px solid var(--pd-coral); }

.pd-metric-card:hover {
  border-color: #d9c3ba;
  box-shadow: 0 11px 22px rgba(82, 62, 54, 0.09);
  transform: translateY(-2px);
}

.pd-metric-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
}

.pd-metric-body strong {
  font-size: 21px;
  letter-spacing: 0;
}

.pd-grid {
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
}

.pd-section,
.pd-half-card,
.pd-side-card {
  border: 1px solid var(--pd-border);
  border-radius: 8px;
  background: var(--pd-surface);
  box-shadow: 0 8px 20px rgba(82, 62, 54, 0.045);
}

.pd-dimension-filter {
  overflow: hidden;
  background: #fffaf7;
}

.pd-dim-grid {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  overflow-x: auto;
  padding: 2px 2px 8px;
  scrollbar-width: thin;
}

.pd-dim-card {
  flex: 0 0 154px;
  min-height: 68px;
  padding: 10px;
  border: 1px solid var(--pd-border);
  border-radius: 8px;
  background: #fff;
  color: var(--pd-ink);
  cursor: pointer;
  transition: color 190ms ease, background 190ms ease, border-color 190ms ease, box-shadow 190ms ease, transform 190ms ease;
}

.pd-dim-card:hover {
  border-color: color-mix(in srgb, var(--dim-color) 42%, #eaded8);
  box-shadow: 0 7px 14px rgba(82, 62, 54, 0.07);
  transform: translateY(-2px);
}

.pd-dim-card.active {
  border-color: var(--dim-color);
  background: color-mix(in srgb, var(--dim-color) 9%, white);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--dim-color) 30%, transparent);
}

.pd-dim-icon {
  border-radius: 8px;
  background: color-mix(in srgb, var(--dim-color) 12%, white);
}

.pd-dim-label {
  color: var(--pd-ink);
  font-weight: 700;
}

.pd-dim-desc {
  color: var(--pd-copy);
}

.pd-tabs-card {
  padding-top: 12px;
}

.pd-tabs-nav {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  overflow: hidden;
  border: 1px solid var(--pd-border);
  border-radius: 8px;
  background: #f8efea;
}

.pd-tab-btn {
  min-width: 0;
  min-height: 38px;
  border-radius: 6px;
  cursor: pointer;
  transition: color 190ms ease, background 190ms ease, box-shadow 190ms ease;
}

.pd-tab-btn.active {
  background: #fff;
  color: var(--pd-coral-strong);
  box-shadow: 0 3px 10px rgba(82, 62, 54, 0.08);
}

.pd-profile-companion {
  align-self: start;
  gap: 0;
  overflow: hidden;
  padding: 8px;
  border: 1px solid #e4d2ca;
  border-radius: 8px;
  background: #f8e9e2;
}

.pd-profile-companion .pd-side-card {
  border-color: transparent;
  border-bottom-color: #ead8d0;
  border-radius: 0;
  box-shadow: none;
}

.pd-profile-companion .pd-side-card:first-child {
  border-radius: 6px 6px 0 0;
}

.pd-profile-companion .pd-side-card:last-child {
  border-bottom-color: transparent;
  border-radius: 0 0 6px 6px;
}

.pd-tool {
  border-radius: 8px;
  cursor: pointer;
}

@keyframes pd-warm-rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1100px) {
  .pd-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .pd-profile-companion {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .pd-profile-companion .pd-side-card,
  .pd-profile-companion .pd-side-card:first-child,
  .pd-profile-companion .pd-side-card:last-child {
    border: 1px solid #ead8d0;
    border-radius: 6px;
  }
}

@media (max-width: 760px) {
  .profile-dashboard {
    padding: 18px 16px 32px;
  }

  .pd-warm-hero {
    padding: 18px;
  }

  .pd-hero-topline,
  .pd-hero-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .pd-hero-topline {
    flex-direction: column;
  }

  .pd-header-actions {
    width: 100%;
  }

  .pd-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pd-profile-companion {
    grid-template-columns: minmax(0, 1fr);
  }

  .pd-tabs-nav {
    display: flex;
    overflow-x: auto;
  }

  .pd-tab-btn {
    flex: 0 0 132px;
  }
}

@media (max-width: 640px) {
  .profile-dashboard {
    padding-inline: 12px;
  }

  .pd-warm-hero {
    gap: 14px;
    padding: 16px;
  }

  .pd-header-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pd-header-actions .pd-primary-btn {
    grid-column: 1 / -1;
    justify-content: center;
  }

  .pd-header-actions .pd-ghost-btn {
    justify-content: center;
  }

  .pd-hero-identity {
    align-items: flex-start;
    min-height: 0;
    padding: 15px;
  }

  .pd-avatar-large .pd-avatar-img {
    width: 64px;
    height: 64px;
  }

  .pd-hero-identity .pd-learner-meta strong {
    font-size: 19px;
  }

  .pd-hero-badge {
    align-items: flex-start;
    width: 100%;
  }

  .pd-hero-badge-style {
    margin-left: auto;
  }

  .pd-metrics {
    display: flex;
    overflow-x: auto;
    padding-bottom: 8px;
    scroll-snap-type: x proximity;
  }

  .pd-metric-card {
    flex: 0 0 210px;
    scroll-snap-align: start;
  }

  .pd-section,
  .pd-half-card,
  .pd-side-card {
    padding: 14px;
  }
}

/* ===========================================================================
   Playful educational claymorphism override
   ========================================================================== */
.profile-dashboard {
  --edu-ink: #30364b;
  --edu-green: #26c96b;
  --edu-green-dark: #159a4c;
  --edu-pink: #ffaaa3;
  --edu-blue: #a8dcec;
  --edu-yellow: #ffd86d;
  --edu-purple: #c7b7ff;
  --edu-cream: #ffffff;
  --edu-white: #fffefd;
  --edu-outline: 2px solid var(--edu-ink);
  --edu-clay-shadow: 6px 6px 0 var(--edu-ink);
  background: var(--edu-cream);
  color: var(--edu-ink);
}

.profile-dashboard::before {
  display: none;
}

.pd-warm-hero {
  gap: 22px;
  margin-bottom: 20px;
  padding: 10px 4px 20px;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.pd-warm-hero::after {
  display: none;
}

.pd-hero-topline {
  align-items: center;
}

.pd-header-titles h1 {
  max-width: 620px;
  margin-top: 10px;
  color: var(--edu-ink);
  font-size: clamp(34px, 4vw, 54px);
  font-weight: 900;
  line-height: 1.04;
  letter-spacing: 0;
}

.pd-header-titles p {
  max-width: 640px;
  color: #596073;
  font-size: 14px;
  line-height: 1.75;
}

.pd-hero-kicker {
  gap: 7px;
  padding: 7px 12px;
  border: 1px solid #9edcae;
  border-radius: 999px;
  background: #bff5c5;
  color: #176a3b;
  font-size: 12px;
  font-weight: 800;
}

.pd-primary-btn,
.pd-ghost-btn {
  min-height: 40px;
  border: var(--edu-outline);
  border-radius: 8px;
  box-shadow: 3px 3px 0 var(--edu-ink);
  color: var(--edu-ink);
  font-weight: 800;
}

.pd-primary-btn {
  background: var(--edu-green);
  color: #fff;
}

.pd-primary-btn:hover {
  background: #20b95f;
  transform: translate(2px, 2px);
  box-shadow: 1px 1px 0 var(--edu-ink);
}

.pd-ghost-btn {
  background: var(--edu-white);
}

.pd-ghost-btn:hover {
  border-color: var(--edu-ink);
  background: var(--edu-blue);
  transform: translate(1px, 1px);
  box-shadow: 2px 2px 0 var(--edu-ink);
}

.pd-hero-grid {
  grid-template-columns: minmax(0, 1fr) minmax(310px, 0.82fr);
  gap: 34px;
  align-items: center;
}

.pd-hero-identity {
  min-height: 146px;
  padding: 4px 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.pd-avatar-large .pd-avatar-img {
  width: 94px;
  height: 94px;
  border: var(--edu-outline);
  border-radius: 8px;
  box-shadow: 5px 5px 0 var(--edu-pink);
}

.pd-hero-label {
  color: var(--edu-green-dark);
  font-size: 12px;
  font-weight: 900;
}

.pd-hero-identity .pd-learner-meta strong {
  color: var(--edu-ink);
  font-size: 29px;
  font-weight: 900;
}

.pd-hero-identity .pd-learner-meta small {
  color: #596073;
  font-size: 14px;
}

.pd-hero-progress {
  min-height: 170px;
  padding: 22px;
  border: var(--edu-outline);
  border-radius: 8px;
  background: var(--edu-white);
  box-shadow: var(--edu-clay-shadow);
}

.pd-hero-progress-head span:first-child {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--edu-ink);
  font-size: 13px;
  font-weight: 900;
}

.pd-hero-version {
  border: var(--edu-outline);
  background: var(--edu-blue);
  color: var(--edu-ink);
  font-weight: 900;
}

.pd-hero-progress > strong {
  color: var(--edu-green-dark);
  font-size: 43px;
  font-weight: 900;
}

.pd-hero-progress-bar {
  height: 12px;
  border: var(--edu-outline);
  background: #fff;
}

.pd-hero-progress-bar span {
  border-right: 2px solid var(--edu-ink);
  background: var(--edu-green);
}

.pd-hero-progress p {
  color: #596073;
  font-size: 12px;
}

.pd-hero-badge {
  padding: 10px 14px;
  border: var(--edu-outline);
  border-radius: 8px;
  background: var(--edu-yellow);
  box-shadow: 4px 4px 0 var(--edu-ink);
}

.pd-hero-badge-icon {
  border: 1px solid var(--edu-ink);
  background: #fff;
  color: var(--edu-ink);
}

.pd-hero-badge > div:nth-child(2) span,
.pd-hero-badge > div:nth-child(2) strong,
.pd-hero-badge-style {
  color: var(--edu-ink);
}

.pd-metrics {
  gap: 14px;
  margin-bottom: 24px;
}

.pd-metric-card {
  min-height: 96px;
  padding: 16px;
  border: var(--edu-outline);
  border-top-width: 2px !important;
  border-radius: 8px;
  background: var(--edu-white);
  box-shadow: 4px 4px 0 var(--edu-ink);
}

.pd-metric-card:nth-child(1) { background: #fff0ee; }
.pd-metric-card:nth-child(2) { background: #fff4c9; }
.pd-metric-card:nth-child(3) { background: #dff8e5; }
.pd-metric-card:nth-child(4) { background: #dff3fa; }
.pd-metric-card:nth-child(5) { background: #eee9ff; }

.pd-metric-card:hover {
  border-color: var(--edu-ink);
  box-shadow: 2px 2px 0 var(--edu-ink);
  transform: translate(2px, 2px);
}

.pd-metric-icon {
  border: 1px solid var(--edu-ink);
  border-radius: 8px;
  background: #fff !important;
}

.pd-metric-body small,
.pd-metric-sub {
  color: #596073;
}

.pd-metric-body strong {
  color: var(--edu-ink) !important;
  font-size: 23px;
  font-weight: 900;
}

.pd-metric-delta {
  border: 1px solid #176a3b;
  background: #c9f5d2;
  color: #176a3b;
}

.pd-section,
.pd-half-card,
.pd-side-card {
  border: var(--edu-outline);
  border-radius: 8px;
  background: var(--edu-white);
  box-shadow: 4px 4px 0 rgba(48, 54, 75, 0.92);
}

.pd-dimension-filter {
  background: #f0edff;
}

.pd-dim-grid {
  gap: 10px;
  padding: 4px 3px 10px;
}

.pd-dim-card {
  flex-basis: 158px;
  min-height: 74px;
  border: var(--edu-outline);
  border-radius: 8px;
  background: #fff;
  box-shadow: 3px 3px 0 var(--edu-ink);
}

.pd-dim-card:nth-child(4n + 1) { background: #fff0ee; }
.pd-dim-card:nth-child(4n + 2) { background: #fff4c9; }
.pd-dim-card:nth-child(4n + 3) { background: #dff3fa; }
.pd-dim-card:nth-child(4n + 4) { background: #dff8e5; }

.pd-dim-card:hover {
  border-color: var(--edu-ink);
  box-shadow: 1px 1px 0 var(--edu-ink);
  transform: translate(2px, 2px);
}

.pd-dim-card.active {
  border-color: var(--edu-ink);
  background: var(--edu-green);
  color: #fff;
  box-shadow: 1px 1px 0 var(--edu-ink);
  transform: translate(2px, 2px);
}

.pd-dim-card.active .pd-dim-label,
.pd-dim-card.active .pd-dim-desc {
  color: #fff;
}

.pd-dim-icon {
  border: 1px solid var(--edu-ink);
  background: #fff;
  color: var(--edu-ink);
}

.pd-dim-label {
  color: var(--edu-ink);
  font-weight: 900;
}

.pd-dim-desc {
  color: #596073;
}

.pd-tabs-card {
  background: #fff9f4;
}

.pd-tabs-nav {
  gap: 6px;
  padding: 6px;
  border: var(--edu-outline);
  background: var(--edu-blue);
  box-shadow: 3px 3px 0 var(--edu-ink);
}

.pd-tab-btn {
  border: 1px solid transparent;
  color: var(--edu-ink);
  font-weight: 800;
}

.pd-tab-btn:hover {
  border-color: var(--edu-ink);
  background: rgba(255, 255, 255, 0.62);
}

.pd-tab-btn.active {
  border-color: var(--edu-ink);
  background: #fff;
  color: var(--edu-ink);
  box-shadow: 2px 2px 0 var(--edu-ink);
}

.pd-profile-companion {
  gap: 10px;
  padding: 0;
  overflow: visible;
  border: 0;
  background: transparent;
}

.pd-profile-companion .pd-side-card,
.pd-profile-companion .pd-side-card:first-child,
.pd-profile-companion .pd-side-card:last-child {
  border: var(--edu-outline);
  border-radius: 8px;
  box-shadow: 4px 4px 0 var(--edu-ink);
}

.pd-profile-companion .pd-side-card:nth-child(4n + 1) { background: #fff0ee; }
.pd-profile-companion .pd-side-card:nth-child(4n + 2) { background: #fff4c9; }
.pd-profile-companion .pd-side-card:nth-child(4n + 3) { background: #dff3fa; }
.pd-profile-companion .pd-side-card:nth-child(4n + 4) { background: #eee9ff; }

.pd-tool,
.pd-driven-btn,
.pd-suggestion-btn,
.pd-side-more-btn {
  border: 1px solid var(--edu-ink);
  border-radius: 8px;
  background: #fff;
  color: var(--edu-ink);
  box-shadow: 2px 2px 0 var(--edu-ink);
}

.pd-tool:hover,
.pd-driven-btn:hover,
.pd-suggestion-btn:hover,
.pd-side-more-btn:hover {
  background: var(--edu-green);
  color: #fff;
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0 var(--edu-ink);
}

.pd-primary-btn:focus-visible,
.pd-ghost-btn:focus-visible,
.pd-dim-card:focus-visible,
.pd-tab-btn:focus-visible,
.pd-tool:focus-visible,
.pd-side-more:focus-visible {
  outline: 3px solid #6d5dfc;
  outline-offset: 3px;
}

@media (max-width: 760px) {
  .pd-hero-grid {
    gap: 20px;
  }

  .pd-hero-progress,
  .pd-section,
  .pd-half-card,
  .pd-side-card,
  .pd-metric-card {
    box-shadow: 3px 3px 0 var(--edu-ink);
  }
}

/* ===========================================================================
   Creative agency brutalist override
   ========================================================================== */
.profile-dashboard {
  --brutal-black: #080808;
  --brutal-red: #ff1a0a;
  --brutal-yellow: #fff500;
  --brutal-blue: #2412ff;
  --brutal-white: #ffffff;
  --brutal-gray: #f2f2f2;
  --brutal-border: 3px solid var(--brutal-black);
  --brutal-shadow: 7px 7px 0 var(--brutal-black);
  background: var(--brutal-white);
  color: var(--brutal-black);
}

.pd-brutal-hero {
  gap: 28px;
  padding-top: 16px;
  animation: pd-brutal-enter 340ms steps(5, end) both;
}

.pd-brutal-hero .pd-hero-topline {
  align-items: flex-start;
}

.pd-brutal-hero .pd-hero-kicker {
  padding: 9px 14px;
  border: var(--brutal-border);
  border-radius: 0;
  background: var(--brutal-yellow);
  color: var(--brutal-black);
  box-shadow: 5px 5px 0 var(--brutal-black);
  font-size: 12px;
  font-weight: 900;
}

.pd-brutal-hero .pd-header-titles h1 {
  max-width: 760px;
  margin: 18px 0 12px;
  color: var(--brutal-black);
  font-size: clamp(42px, 6vw, 76px);
  font-weight: 950;
  line-height: 0.98;
  text-transform: uppercase;
}

.pd-brutal-hero .pd-header-titles h1 span {
  display: inline-block;
  padding: 2px 10px 5px;
  background: var(--brutal-red);
  color: #fff;
}

.pd-brutal-hero .pd-header-titles p {
  max-width: 660px;
  color: #414141;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.7;
}

.pd-brutal-hero .pd-primary-btn,
.pd-brutal-hero .pd-ghost-btn {
  min-height: 44px;
  border: var(--brutal-border);
  border-radius: 0;
  box-shadow: 5px 5px 0 var(--brutal-black);
  font-weight: 900;
}

.pd-brutal-hero .pd-primary-btn {
  background: var(--brutal-yellow);
  color: var(--brutal-black);
}

.pd-brutal-hero .pd-ghost-btn {
  background: #fff;
  color: var(--brutal-black);
}

.pd-brutal-hero .pd-primary-btn:hover,
.pd-brutal-hero .pd-ghost-btn:hover {
  border-color: var(--brutal-black);
  background: var(--brutal-red);
  color: #fff;
  box-shadow: 2px 2px 0 var(--brutal-black);
  transform: translate(3px, 3px);
}

.pd-brutal-hero .pd-hero-grid {
  grid-template-columns: minmax(0, 0.95fr) minmax(330px, 1.05fr);
  gap: 48px;
}

.pd-brutal-hero .pd-avatar-large .pd-avatar-img {
  width: 100px;
  height: 100px;
  border: var(--brutal-border);
  border-radius: 0;
  box-shadow: 8px 8px 0 var(--brutal-red);
}

.pd-brutal-hero .pd-hero-label {
  display: inline-block;
  padding: 4px 7px;
  background: var(--brutal-black);
  color: #fff;
  font-size: 11px;
  font-weight: 900;
}

.pd-brutal-hero .pd-hero-identity .pd-learner-meta strong {
  margin-top: 8px;
  color: var(--brutal-black);
  font-size: 31px;
  font-weight: 950;
}

.pd-brutal-hero .pd-hero-identity .pd-learner-meta small {
  color: #414141;
  font-weight: 700;
}

.pd-brutal-hero .pd-hero-progress {
  min-height: 190px;
  padding: 24px;
  border: var(--brutal-border);
  border-radius: 0;
  background: var(--brutal-yellow);
  box-shadow: 10px 10px 0 var(--brutal-blue), -8px -8px 0 var(--brutal-red);
}

.pd-brutal-hero .pd-hero-progress-head span:first-child,
.pd-brutal-hero .pd-hero-progress p {
  color: var(--brutal-black);
  font-weight: 900;
}

.pd-brutal-hero .pd-hero-version {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: #fff;
  color: var(--brutal-black);
}

.pd-brutal-hero .pd-hero-progress > strong {
  color: var(--brutal-black);
  font-size: 52px;
  font-weight: 950;
}

.pd-brutal-hero .pd-hero-progress-bar {
  height: 14px;
  border: 3px solid var(--brutal-black);
  border-radius: 0;
  background: #fff;
}

.pd-brutal-hero .pd-hero-progress-bar span {
  border-right: 3px solid var(--brutal-black);
  border-radius: 0;
  background: var(--brutal-red);
}

.pd-brutal-hero .pd-hero-badge {
  padding: 11px 15px;
  border: var(--brutal-border);
  border-radius: 0;
  background: var(--brutal-blue);
  color: #fff;
  box-shadow: 6px 6px 0 var(--brutal-black);
}

.pd-brutal-hero .pd-hero-badge-icon {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: var(--brutal-yellow);
  color: var(--brutal-black);
}

.pd-brutal-hero .pd-hero-badge > div:nth-child(2) span,
.pd-brutal-hero .pd-hero-badge > div:nth-child(2) strong,
.pd-brutal-hero .pd-hero-badge-style {
  color: #fff;
}

.pd-metric-card {
  min-height: 102px;
  border: var(--brutal-border);
  border-radius: 0;
  box-shadow: var(--brutal-shadow);
}

.pd-metric-card:nth-child(1) { background: var(--brutal-red); color: #fff; }
.pd-metric-card:nth-child(2) { background: var(--brutal-yellow); }
.pd-metric-card:nth-child(3) { background: var(--brutal-blue); color: #fff; }
.pd-metric-card:nth-child(4) { background: #fff; }
.pd-metric-card:nth-child(5) { background: var(--brutal-gray); }

.pd-metric-card:hover {
  border-color: var(--brutal-black);
  box-shadow: 3px 3px 0 var(--brutal-black);
  transform: translate(4px, 4px);
}

.pd-metric-card:nth-child(1) .pd-metric-body small,
.pd-metric-card:nth-child(1) .pd-metric-body strong,
.pd-metric-card:nth-child(1) .pd-metric-sub,
.pd-metric-card:nth-child(3) .pd-metric-body small,
.pd-metric-card:nth-child(3) .pd-metric-body strong,
.pd-metric-card:nth-child(3) .pd-metric-sub {
  color: #fff !important;
}

.pd-metric-icon {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: #fff !important;
}

.pd-metric-delta {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: var(--brutal-yellow);
  color: var(--brutal-black);
}

.pd-section,
.pd-half-card,
.pd-side-card {
  border: var(--brutal-border);
  border-radius: 0;
  background: #fff;
  box-shadow: 6px 6px 0 var(--brutal-black);
}

.pd-dimension-filter {
  background: var(--brutal-yellow);
}

.pd-dim-card {
  border: var(--brutal-border);
  border-radius: 0;
  background: #fff !important;
  box-shadow: 4px 4px 0 var(--brutal-black);
}

.pd-dim-card:nth-child(3n + 2) { background: #ededed !important; }
.pd-dim-card:nth-child(3n + 3) { background: #d9d5ff !important; }

.pd-dim-card:hover {
  border-color: var(--brutal-black);
  background: var(--brutal-red) !important;
  color: #fff;
  box-shadow: 1px 1px 0 var(--brutal-black);
  transform: translate(3px, 3px);
}

.pd-dim-card.active {
  border-color: var(--brutal-black);
  background: var(--brutal-blue) !important;
  color: #fff;
  box-shadow: 1px 1px 0 var(--brutal-black);
  transform: translate(3px, 3px);
}

.pd-dim-card:hover .pd-dim-label,
.pd-dim-card:hover .pd-dim-desc,
.pd-dim-card.active .pd-dim-label,
.pd-dim-card.active .pd-dim-desc {
  color: #fff;
}

.pd-dim-icon {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: var(--brutal-yellow);
  color: var(--brutal-black);
}

.pd-tabs-card {
  background: var(--brutal-gray);
}

.pd-tabs-nav {
  border: var(--brutal-border);
  border-radius: 0;
  background: var(--brutal-black);
  box-shadow: 5px 5px 0 var(--brutal-red);
}

.pd-tab-btn {
  border-radius: 0;
  color: #fff;
  font-weight: 900;
}

.pd-tab-btn:hover {
  border-color: #fff;
  background: var(--brutal-blue);
}

.pd-tab-btn.active {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: var(--brutal-yellow);
  color: var(--brutal-black);
  box-shadow: none;
}

.pd-profile-companion {
  gap: 14px;
}

.pd-profile-companion .pd-side-card,
.pd-profile-companion .pd-side-card:first-child,
.pd-profile-companion .pd-side-card:last-child {
  border: var(--brutal-border);
  border-radius: 0;
  box-shadow: 6px 6px 0 var(--brutal-black);
}

.pd-profile-companion .pd-side-card:nth-child(4n + 1) { background: var(--brutal-red); color: #fff; }
.pd-profile-companion .pd-side-card:nth-child(4n + 2) { background: var(--brutal-yellow); }
.pd-profile-companion .pd-side-card:nth-child(4n + 3) { background: #fff; }
.pd-profile-companion .pd-side-card:nth-child(4n + 4) { background: #d9d5ff; }

.pd-profile-companion .pd-side-card:nth-child(4n + 1) :deep(.section-title),
.pd-profile-companion .pd-side-card:nth-child(4n + 1) :deep(.section-subtitle),
.pd-profile-companion .pd-side-card:nth-child(4n + 1) .pd-bullet-list,
.pd-profile-companion .pd-side-card:nth-child(4n + 1) .pd-bullet-list li {
  color: #fff;
}

.pd-tool,
.pd-driven-btn,
.pd-suggestion-btn,
.pd-side-more-btn {
  border: 2px solid var(--brutal-black);
  border-radius: 0;
  background: #fff;
  color: var(--brutal-black);
  box-shadow: 3px 3px 0 var(--brutal-black);
  font-weight: 900;
}

.pd-tool:hover,
.pd-driven-btn:hover,
.pd-suggestion-btn:hover,
.pd-side-more-btn:hover {
  background: var(--brutal-yellow);
  color: var(--brutal-black);
  box-shadow: 1px 1px 0 var(--brutal-black);
  transform: translate(2px, 2px);
}

.pd-primary-btn:focus-visible,
.pd-ghost-btn:focus-visible,
.pd-dim-card:focus-visible,
.pd-tab-btn:focus-visible,
.pd-tool:focus-visible,
.pd-side-more:focus-visible {
  outline: 4px solid var(--brutal-blue);
  outline-offset: 3px;
}

@keyframes pd-brutal-enter {
  from {
    opacity: 0;
    transform: translate(-14px, 10px);
  }
  to {
    opacity: 1;
    transform: translate(0, 0);
  }
}

@media (max-width: 760px) {
  .pd-brutal-hero .pd-hero-grid {
    gap: 28px;
  }

  .pd-brutal-hero .pd-header-titles h1 {
    font-size: clamp(38px, 13vw, 58px);
  }

  .pd-brutal-hero .pd-hero-progress {
    box-shadow: 6px 6px 0 var(--brutal-blue), -5px -5px 0 var(--brutal-red);
  }
}

/* ===========================================================================
   Sustainability platform biophilic override
   ========================================================================== */
.profile-dashboard {
  --eco-forest: #4a332b;
  --eco-green: #e86f47;
  --eco-green-dark: #b94f32;
  --eco-sage: #fff3ea;
  --eco-moss: #82957a;
  --eco-earth: #c6815d;
  --eco-sky: #84a9b2;
  --eco-cream: #ffffff;
  --eco-white: #ffffff;
  --eco-border: #eee3d8;
  --eco-copy: #6d5a51;
  --pd-card-surface: #ffffff;
  --pd-card-soft: #fffaf4;
  background: var(--eco-cream);
  color: var(--eco-forest);
}

.pd-eco-hero {
  gap: 24px;
  padding: 18px 4px 26px;
  animation: pd-eco-rise 420ms ease-out both;
}

.pd-eco-hero .pd-hero-topline {
  align-items: center;
}

.pd-eco-hero .pd-hero-kicker {
  padding: 7px 12px;
  border: 1px solid #f0cdbd;
  border-radius: 999px;
  background: var(--eco-sage);
  color: var(--eco-green-dark);
  box-shadow: none;
  font-size: 12px;
  font-weight: 700;
}

.pd-eco-hero .pd-header-titles h1 {
  max-width: 720px;
  margin: 16px 0 12px;
  color: var(--eco-forest);
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(38px, 5vw, 64px);
  font-weight: 700;
  line-height: 1.04;
  text-transform: none;
}

.pd-eco-hero .pd-header-titles h1 span {
  display: inline;
  padding: 0;
  background: transparent;
  color: var(--eco-green);
}

.pd-eco-hero .pd-header-titles p {
  max-width: 660px;
  color: var(--eco-copy);
  font-size: 15px;
  font-weight: 500;
  line-height: 1.75;
}

.pd-eco-hero .pd-primary-btn,
.pd-eco-hero .pd-ghost-btn {
  min-height: 42px;
  border-radius: 8px;
  box-shadow: none;
  font-weight: 700;
  transition: color 180ms ease, background 180ms ease, border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
}

.pd-eco-hero .pd-primary-btn {
  border: 1px solid var(--eco-green);
  background: var(--eco-green);
  color: #fff;
}

.pd-eco-hero .pd-ghost-btn {
  border: 1px solid #dfaa91;
  background: rgba(255, 255, 255, 0.78);
  color: var(--eco-green-dark);
}

.pd-eco-hero .pd-primary-btn:hover,
.pd-eco-hero .pd-ghost-btn:hover {
  border-color: var(--eco-green-dark);
  background: var(--eco-green-dark);
  color: #fff;
  box-shadow: 0 8px 18px rgba(123, 70, 47, 0.16);
  transform: translateY(-1px);
}

.pd-eco-hero .pd-hero-grid {
  grid-template-columns: minmax(0, 0.95fr) minmax(330px, 1.05fr);
  gap: 42px;
}

.pd-eco-hero .pd-avatar-large .pd-avatar-img {
  width: 94px;
  height: 94px;
  border: 4px solid #fff;
  border-radius: 8px;
  box-shadow: 0 10px 24px rgba(123, 70, 47, 0.16);
}

.pd-eco-hero .pd-hero-label {
  display: block;
  padding: 0;
  background: transparent;
  color: var(--eco-green-dark);
  font-size: 12px;
  font-weight: 700;
}

.pd-eco-hero .pd-hero-identity .pd-learner-meta strong {
  margin-top: 5px;
  color: var(--eco-forest);
  font-size: 29px;
  font-weight: 800;
}

.pd-eco-hero .pd-hero-identity .pd-learner-meta small {
  color: var(--eco-copy);
  font-weight: 500;
}

.pd-eco-hero .pd-hero-progress {
  min-height: 190px;
  padding: 24px;
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface);
  box-shadow: 0 18px 38px rgba(123, 70, 47, 0.12);
}

.pd-eco-hero .pd-hero-progress-head span:first-child {
  color: var(--eco-forest);
  font-size: 13px;
  font-weight: 700;
}

.pd-eco-hero .pd-hero-version {
  border: 1px solid #f0cdbd;
  border-radius: 999px;
  background: var(--eco-sage);
  color: var(--eco-green-dark);
}

.pd-eco-hero .pd-hero-progress > strong {
  color: var(--eco-forest);
  font-size: 48px;
  font-weight: 800;
}

.pd-eco-hero .pd-hero-progress-bar {
  height: 10px;
  border: 0;
  border-radius: 999px;
  background: #f3e5dd;
}

.pd-eco-hero .pd-hero-progress-bar span {
  border: 0;
  border-radius: 999px;
  background: var(--eco-green);
}

.pd-eco-hero .pd-hero-progress p {
  color: var(--eco-copy);
  font-weight: 500;
}

.pd-eco-hero .pd-hero-badge {
  padding: 10px 14px;
  border: 1px solid #f0cdbd;
  border-radius: 8px;
  background: var(--pd-card-soft);
  color: var(--eco-forest);
  box-shadow: none;
}

.pd-eco-hero .pd-hero-badge-icon {
  border: 0;
  border-radius: 999px;
  background: var(--eco-green);
  color: #fff;
}

.pd-eco-hero .pd-hero-badge > div:nth-child(2) span,
.pd-eco-hero .pd-hero-badge > div:nth-child(2) strong,
.pd-eco-hero .pd-hero-badge-style {
  color: var(--eco-forest);
}

.pd-metric-card {
  min-height: 94px;
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface) !important;
  color: var(--eco-forest) !important;
  box-shadow: 0 10px 26px rgba(123, 70, 47, 0.08);
}

.pd-metric-card:nth-child(1) { border-top: 3px solid var(--eco-green) !important; }
.pd-metric-card:nth-child(2) { border-top: 3px solid var(--eco-earth) !important; }
.pd-metric-card:nth-child(3) { border-top: 3px solid var(--eco-sky) !important; }
.pd-metric-card:nth-child(4) { border-top: 3px solid var(--eco-moss) !important; }
.pd-metric-card:nth-child(5) { border-top: 3px solid #d2aa4d !important; }

.pd-metric-card:hover {
  border-color: #dfbaa8;
  box-shadow: 0 14px 30px rgba(123, 70, 47, 0.13);
  transform: translateY(-2px);
}

.pd-metric-card:nth-child(1) .pd-metric-body small,
.pd-metric-card:nth-child(1) .pd-metric-body strong,
.pd-metric-card:nth-child(1) .pd-metric-sub,
.pd-metric-card:nth-child(3) .pd-metric-body small,
.pd-metric-card:nth-child(3) .pd-metric-body strong,
.pd-metric-card:nth-child(3) .pd-metric-sub,
.pd-metric-body small,
.pd-metric-body strong,
.pd-metric-sub {
  color: var(--eco-forest) !important;
}

.pd-metric-icon {
  border: 0;
  border-radius: 8px;
  background: var(--eco-sage) !important;
}

.pd-metric-delta {
  border: 0;
  border-radius: 999px;
  background: var(--eco-sage);
  color: var(--eco-green-dark);
}

.pd-section,
.pd-half-card,
.pd-side-card {
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface);
  box-shadow: 0 12px 30px rgba(123, 70, 47, 0.075);
}

.pd-dimension-filter {
  background: var(--pd-card-surface);
}

.pd-dim-card,
.pd-dim-card:nth-child(3n + 2),
.pd-dim-card:nth-child(3n + 3) {
  border: 1px solid #ead3c7;
  border-radius: 8px;
  background: var(--pd-card-surface) !important;
  box-shadow: none;
}

.pd-dim-card:hover {
  border-color: #d89a7d;
  background: #fff4ed !important;
  color: var(--eco-forest);
  box-shadow: 0 8px 18px rgba(123, 70, 47, 0.1);
  transform: translateY(-2px);
}

.pd-dim-card.active {
  border-color: var(--eco-green-dark);
  background: var(--eco-green) !important;
  color: #fff;
  box-shadow: 0 8px 18px rgba(232, 111, 71, 0.2);
  transform: translateY(-1px);
}

.pd-dim-card:hover .pd-dim-label,
.pd-dim-card:hover .pd-dim-desc {
  color: var(--eco-forest);
}

.pd-dim-card.active .pd-dim-label,
.pd-dim-card.active .pd-dim-desc {
  color: #fff;
}

.pd-dim-icon {
  border: 0;
  border-radius: 8px;
  background: var(--eco-sage);
  color: var(--eco-green-dark);
}

.pd-tabs-card {
  background: var(--pd-card-surface);
}

.pd-tabs-nav {
  border: 1px solid #efd2c4;
  border-radius: 8px;
  background: var(--pd-card-soft);
  box-shadow: none;
}

.pd-tab-btn {
  border: 1px solid transparent;
  border-radius: 7px;
  color: var(--eco-forest);
  font-weight: 700;
}

.pd-tab-btn:hover {
  border-color: #dfb59f;
  background: rgba(255, 255, 255, 0.62);
  color: var(--eco-forest);
}

.pd-tab-btn.active {
  border: 1px solid #dda78d;
  border-radius: 7px;
  background: var(--pd-card-surface);
  color: var(--eco-green-dark);
  box-shadow: 0 4px 12px rgba(123, 70, 47, 0.1);
}

.pd-profile-companion {
  gap: 12px;
}

.pd-profile-companion .pd-side-card,
.pd-profile-companion .pd-side-card:first-child,
.pd-profile-companion .pd-side-card:last-child {
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface);
  color: var(--eco-forest);
  box-shadow: 0 10px 24px rgba(123, 70, 47, 0.08);
}

.pd-profile-companion .pd-side-card:nth-child(4n + 1) { background: var(--pd-card-soft); color: var(--eco-forest); }
.pd-profile-companion .pd-side-card:nth-child(4n + 2) { background: var(--pd-card-surface); }
.pd-profile-companion .pd-side-card:nth-child(4n + 3) { background: var(--pd-card-soft); }
.pd-profile-companion .pd-side-card:nth-child(4n + 4) { background: var(--pd-card-surface); }

.pd-profile-companion .pd-side-card:nth-child(4n + 1) :deep(.section-title),
.pd-profile-companion .pd-side-card:nth-child(4n + 1) :deep(.section-subtitle),
.pd-profile-companion .pd-side-card:nth-child(4n + 1) .pd-bullet-list,
.pd-profile-companion .pd-side-card:nth-child(4n + 1) .pd-bullet-list li {
  color: var(--eco-forest);
}

.pd-tool,
.pd-driven-btn,
.pd-suggestion-btn,
.pd-side-more-btn {
  border: 1px solid #dfb7a3;
  border-radius: 8px;
  background: #fff;
  color: var(--eco-green-dark);
  box-shadow: none;
  font-weight: 700;
}

.pd-tool:hover,
.pd-driven-btn:hover,
.pd-suggestion-btn:hover,
.pd-side-more-btn:hover {
  border-color: var(--eco-green);
  background: var(--eco-green);
  color: #fff;
  box-shadow: 0 7px 16px rgba(232, 111, 71, 0.18);
  transform: translateY(-1px);
}

.pd-primary-btn:focus-visible,
.pd-ghost-btn:focus-visible,
.pd-dim-card:focus-visible,
.pd-tab-btn:focus-visible,
.pd-tool:focus-visible,
.pd-side-more:focus-visible {
  outline: 3px solid rgba(232, 111, 71, 0.42);
  outline-offset: 3px;
}

/* 画像维度工作台：能力雷达 + 画像速览 */
.pd-dimension-workbench {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(300px, 0.92fr);
  gap: 16px;
  margin-top: 14px;
}

.pd-dimension-radar,
.pd-dimension-overview {
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface);
}

.pd-dimension-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  min-height: 42px;
  color: var(--eco-green-dark);
}

.pd-dimension-panel-head > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.pd-dimension-panel-head strong {
  color: var(--eco-forest);
  font-size: 14px;
}

.pd-dimension-panel-head span {
  color: var(--eco-copy);
  font-size: 11px;
}

.pd-dimension-radar .pd-radar-wrap {
  height: 286px;
  margin-top: 4px;
}

.pd-dimension-overview .pd-mini-tree {
  max-height: 354px;
  margin-top: 8px;
  padding-right: 4px;
  overflow-y: auto;
}

.pd-dimension-overview .pd-mini-head {
  width: 100%;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
}

.pd-dimension-overview .pd-mini-head:focus-visible {
  outline: 3px solid rgba(232, 111, 71, 0.32);
  outline-offset: 1px;
}

.pd-dimension-evidence {
  grid-column: 1 / -1;
  margin-top: 16px;
  padding: 18px;
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-soft);
}

.pd-evidence-heading {
  min-height: auto;
  margin-bottom: 14px;
}

.pd-dimension-evidence .pd-evidence-layout {
  margin-top: 0;
}

.pd-dimension-evidence .pd-evidence-field,
.pd-dimension-evidence .pd-evidence-sources {
  background: var(--pd-card-surface);
}

/* 独立 AI 画像工具 */
.pd-ai-tools-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.pd-ai-tool {
  position: relative;
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  min-height: 92px;
  padding: 15px;
  border: 1px solid var(--eco-border);
  border-radius: 8px;
  background: var(--pd-card-surface);
  color: var(--eco-forest);
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
}

.pd-ai-tool:hover {
  border-color: #dda78d;
  background: var(--pd-card-soft);
  box-shadow: 0 10px 22px rgba(123, 70, 47, 0.1);
  transform: translateY(-2px);
}

.pd-ai-tool:focus-visible {
  outline: 3px solid rgba(232, 111, 71, 0.4);
  outline-offset: 3px;
}

.pd-ai-tool-icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border-radius: 8px;
  background: color-mix(in srgb, var(--eco-green) 12%, white);
  color: var(--eco-green-dark);
}

.pd-ai-tool-timemachine .pd-ai-tool-icon { background: color-mix(in srgb, #d2aa4d 14%, white); color: #9a6a19; }
.pd-ai-tool-prediction .pd-ai-tool-icon { background: color-mix(in srgb, var(--eco-sky) 14%, white); color: #527983; }

.pd-ai-tool-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
}

.pd-ai-tool-copy strong { font-size: 14px; }
.pd-ai-tool-copy small { color: var(--eco-copy); font-size: 11px; line-height: 1.45; }
.pd-ai-tool-arrow { color: var(--eco-green-dark); }

.pd-ai-tool .pd-tool-badge {
  position: absolute;
  top: 10px;
  right: 10px;
}

.pd-trend-only {
  grid-template-columns: minmax(0, 1fr);
}

.pd-trend-card {
  min-width: 0;
}

@keyframes pd-eco-rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 首屏画像总览框：对应标题、档案、影响力与学习者类型的完整区域 */
.profile-dashboard > .pd-warm-hero.pd-eco-hero {
  margin-bottom: 18px;
  padding: 28px 32px 30px;
  border: 2px solid rgba(198, 129, 93, 0.48);
  border-radius: 18px;
  background: linear-gradient(145deg, var(--pd-card-surface), var(--pd-card-soft));
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.78),
    0 16px 36px rgba(123, 70, 47, 0.1);
}

.pd-hero-footer {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(174px, 0.78fr) minmax(0, 4.22fr);
  gap: 12px;
  align-items: stretch;
  padding-top: 18px;
  border-top: 1px solid rgba(198, 129, 93, 0.22);
}

.pd-hero-footer.without-badge {
  grid-template-columns: minmax(0, 1fr);
}

.pd-hero-footer .pd-hero-badge {
  width: 100%;
  height: 100%;
  margin: 0;
  justify-content: center;
}

.pd-hero-footer .pd-metrics {
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
}

.pd-hero-footer .pd-metric-card {
  min-height: 86px;
  padding: 12px 13px;
}

@media (max-width: 1180px) {
  .pd-hero-footer {
    grid-template-columns: minmax(0, 1fr);
  }

  .pd-hero-footer .pd-hero-badge {
    width: fit-content;
    min-height: 58px;
  }
}

@media (max-width: 900px) {
  .pd-hero-footer .pd-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .pd-dimension-workbench,
  .pd-ai-tools-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .pd-dimension-radar,
  .pd-dimension-overview {
    padding: 14px;
  }

  .pd-dimension-overview .pd-mini-tree {
    max-height: none;
  }

  .profile-dashboard > .pd-warm-hero.pd-eco-hero {
    padding: 22px 18px 24px;
    border-radius: 14px;
  }

  .pd-eco-hero .pd-hero-grid {
    gap: 22px;
  }

  .pd-eco-hero .pd-header-titles h1 {
    font-size: clamp(36px, 12vw, 54px);
  }

  .pd-eco-hero .pd-hero-progress {
    box-shadow: 0 14px 28px rgba(123, 70, 47, 0.12);
  }
}

@media (max-width: 640px) {
  .pd-hero-footer .pd-metrics {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 6px;
    scroll-snap-type: x proximity;
  }

  .pd-hero-footer .pd-metric-card {
    min-width: 188px;
    scroll-snap-align: start;
  }
}

@media (prefers-reduced-motion: reduce) {
  .profile-dashboard::before,
  .pd-tab-panel,
  .pd-warm-hero,
  .pd-metric-card {
    animation: none;
  }

  .pd-primary-btn,
  .pd-ghost-btn,
  .pd-suggestion-btn,
  .pd-driven-btn,
  .pd-tool,
  .pd-btn,
  .pd-rec-mat,
  .pd-metric-card,
  .pd-insight-card,
  .pd-suggestion-card,
  .pd-dim-card,
  .pd-rec-q,
  .pd-eval-score,
  .pd-weak-kp,
  .pd-hero-progress-bar span {
    transition: none;
  }

  .pd-primary-btn:hover,
  .pd-metric-card:hover,
  .pd-dim-card:hover {
    transform: none;
  }
}
</style>
