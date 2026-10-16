<script setup lang="ts">
/**
 * TeacherView · 教师管理台
 *
 * 教师工作流：班级态势 → 教学共创 → 学生诊断 → 资源/路径/群聊执行。
 * 教学共创复用既有 Agent 编排，结果始终先由教师审核。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookMarked,
  BookOpen,
  Bot,
  CheckCircle,
  Download,
  FileDown,
  GitCompare,
  GraduationCap,
  History,
  Layers,
  LayoutDashboard,
  LineChart,
  Loader2,
  MessageSquare,
  Network,
  Pencil,
  Plus,
  RefreshCcw,
  Route as RouteIcon,
  Search,
  Send,
  Sparkles,
  Target,
  Trash2,
  TrendingDown,
  TrendingUp,
  Upload,
  Users,
  Video,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-vue-next";
import { getBktStatus, getForecast } from "@/api/cognitive";
import { getMistakesHeatmap, type HeatmapResponse } from "@/api/mistakes";

import { getAuthSession } from "@/utils/auth";
import {
  assignPathToStudent,
  assignResourceToStudent,
  batchResolveMistakes,
  compareStudents,
  consultTeachingCopilot,
  createAgentConfig,
  createTeacherResource,
  createTeacherResourceFromArtifact,
  downloadTeacherResource,
  deleteAgentConfig,
  deleteTeacherResource,
  exportClassReport,
  getClassAnalytics,
  getKnowledgeMap,
  getStudentSummary,
  listAgentConfigs,
  listInterventions,
  listStudents,
  listTeacherResources,
  sendTeacherMessage,
  updateAgentConfig,
  updateTeacherResource,
  uploadTeacherResource,
  type AgentConfig,
  type ClassAnalytics,
  type ClassWeakKp,
  type CompareResult,
  type InterventionLog,
  type KnowledgeMap,
  type KnowledgeMapNode,
  type StudentSummary,
  type TeachingCopilotAction,
  type TeachingCopilotResult,
  type TeacherResource,
  type TeacherStudentBrief,
} from "@/api/teacher";
import { generateMulti, getArtifactDownloadFullUrl } from "@/api/artifacts";
import {
  buildRoomId,
  listGroupChatMessages,
  type GroupChatMessage,
} from "@/api/groupChat";
import MarkdownBlock from "@/components/shared/MarkdownBlock.vue";
import { AGENT_AVATARS, type AvatarEntry, type AvatarKind } from "@/constants/agentAvatars";
import { useTeacherCourse } from "@/composables/useTeacherCourse";

// 课程选择：全教师端共享（真实课程清单 + localStorage 持久化）
const {
  course: teacherCourse,
  courseOptions,
  loadCourseOptions,
  setCourse,
  courseLabelOf,
} = useTeacherCourse();
const route = useRoute();
const router = useRouter();

type TeacherTab = "board" | "knowledge-map" | "copilot" | "analysis" | "insights" | "compare" | "resources" | "agents" | "paths" | "chat" | "interventions";
type TeacherSection = "overview" | "students" | "resources" | "studio" | "interventions" | "agents";

const tabs: Array<{ key: TeacherTab; label: string; icon: typeof Users }> = [
  { key: "board", label: "班级态势", icon: LayoutDashboard },
  { key: "knowledge-map", label: "知识图谱", icon: Network },
  { key: "copilot", label: "教学共创", icon: Sparkles },
  { key: "analysis", label: "学生诊断", icon: GraduationCap },
  { key: "insights", label: "认知分析", icon: LineChart },
  { key: "compare", label: "学生对比", icon: GitCompare },
  { key: "resources", label: "教学资源", icon: BookOpen },
  { key: "agents", label: "Agent 管理", icon: Bot },
  { key: "paths", label: "路径推送", icon: RouteIcon },
  { key: "chat", label: "师生协作", icon: MessageSquare },
  { key: "interventions", label: "干预日志", icon: History },
];

const sectionConfig: Record<TeacherSection, { title: string; description: string; tabs: TeacherTab[] }> = {
  overview: {
    // 该 section 仅由 /teacher/knowledge 路由进入（/teacher 已由独立教学概览页承载）
    title: "知识图谱",
    description: "从知识关系中发现教学薄弱环节：查看知识点依赖、班级掌握状态与错误传播路径。",
    tabs: ["board", "knowledge-map"],
  },
  students: {
    title: "学生分析",
    description: "聚焦个体学习证据、认知诊断与风险，不混入学生个人学习功能。",
    tabs: ["analysis", "insights", "compare"],
  },
  resources: {
    title: "教学资源",
    description: "上传、审核与发布课程资料；发布后会同步进入学生端资源中心。",
    tabs: ["resources"],
  },
  studio: {
    title: "教学提示与视频",
    description: "由教师编写学习提示词、上传自录课程视频，并按班级或学生审核发布。",
    tabs: ["resources"],
  },
  interventions: {
    title: "教学干预",
    description: "使用 Agent 共创建议，并将经教师确认的路径、资料或消息送达学生。",
    tabs: ["copilot", "paths", "chat", "interventions"],
  },
  agents: {
    title: "Agent 协作",
    description: "配置可参与教学共创与师生协作的 Agent 能力和启用状态。",
    tabs: ["agents"],
  },
};

const teacherSection = computed<TeacherSection>(() => {
  const section = String(route.meta.teacherSection || "overview");
  return section in sectionConfig ? section as TeacherSection : "overview";
});
const currentSection = computed(() => sectionConfig[teacherSection.value]);
const isTeachingStudio = computed(() => teacherSection.value === "studio");
const visibleTabs = computed(() =>
  currentSection.value.tabs.map((key) => tabs.find((tab) => tab.key === key)!).filter(Boolean),
);

const activeTab = ref<TeacherTab>("board");
const teacherName = computed(() => getAuthSession()?.displayName || "王老师");
const teacherAccount = computed(() => getAuthSession()?.account || "teacher");

// 轻提示
const notice = ref("");
let noticeTimer: ReturnType<typeof setTimeout> | null = null;
function showNotice(msg: string) {
  notice.value = msg;
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (notice.value = ""), 2800);
}

// ================= 学生列表（多页签共用） =================
const students = ref<TeacherStudentBrief[]>([]);
const studentsLoading = ref(false);
const selectedStudentId = ref("");

async function loadStudents() {
  studentsLoading.value = true;
  try {
    const r = await listStudents();
    students.value = r.students;
    if (!selectedStudentId.value && r.students.length) {
      selectedStudentId.value = r.students[0].user_id;
    }
  } catch (e: any) {
    showNotice(`学生列表加载失败：${e?.detail || e?.message || e}`);
  } finally {
    studentsLoading.value = false;
  }
}

function formatTime(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

// ================= Tab 1 · 学情分析 =================
const summary = ref<StudentSummary | null>(null);
const summaryLoading = ref(false);

async function loadSummary() {
  if (!selectedStudentId.value) return;
  summaryLoading.value = true;
  summary.value = null;
  try {
    summary.value = await getStudentSummary(selectedStudentId.value, teacherCourse.value);
  } catch (e: any) {
    showNotice(`学情聚合失败：${e?.detail || e?.message || e}`);
  } finally {
    summaryLoading.value = false;
  }
}

interface ProfileEntryView {
  key: string;
  label: string;
  summary: string;
  tags: string[];
  tone: "identity" | "ability" | "preference" | "risk";
}

const profileLabelMap: Record<string, string> = {
  user_id: "学生账号",
  nickname: "常用称呼",
  tier: "学习阶段",
  learning_style: "学习风格",
  knowledge_base: "知识基础",
  cognitive_style: "认知方式",
  learning_preference: "学习偏好",
  weak_points: "重点关注",
  interests: "兴趣方向",
  goals: "学习目标",
};

const profileTokenMap: Record<string, string> = {
  excellent: "进阶阶段",
  advanced: "高级",
  intermediate: "中级",
  beginner: "入门",
  transformer: "Transformer",
  attention_mechanism: "注意力机制",
  cnn: "卷积神经网络",
  probability_statistics: "概率与统计",
  reinforcement_learning: "强化学习",
  visual: "视觉型",
  self_driven: "自驱型",
  project_driven: "项目驱动",
  fast: "节奏较快",
  principle_deep: "原理深挖",
  misconception_boundary: "概念边界混淆",
  high: "较扎实",
  medium: "一般",
  low: "待加强",
};

function parseProfileValue(value: unknown): unknown {
  if (typeof value !== "string") return value;
  const text = value.trim();
  if ((text.startsWith("{") && text.endsWith("}")) || (text.startsWith("[") && text.endsWith("]"))) {
    try { return JSON.parse(text); } catch { return text; }
  }
  return text;
}

function readableProfileToken(value: unknown): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  const normalized = raw.toLowerCase().replace(/[\s-]+/g, "_");
  return profileTokenMap[normalized] || raw.replace(/_/g, " ");
}

function profileEntryView(key: string, rawValue: unknown): ProfileEntryView {
  const value = parseProfileValue(rawValue);
  const label = profileLabelMap[key] || key.replace(/_/g, " ");
  const tags: string[] = [];
  let summaryText = "";

  if (Array.isArray(value)) {
    tags.push(...value.map(readableProfileToken).filter(Boolean));
  } else if (value && typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const topicValues = obj.topics || obj.interests || obj.items;
    if (Array.isArray(topicValues)) tags.push(...topicValues.map(readableProfileToken).filter(Boolean));
    const patterns = obj.patterns;
    if (Array.isArray(patterns)) tags.push(...patterns.map(readableProfileToken).filter(Boolean));

    if (key === "knowledge_base") {
      const level = readableProfileToken(obj.level || "");
      const score = typeof obj.score === "number" ? `画像置信度 ${Math.round(obj.score * 100)}%` : "";
      summaryText = [level && `基础等级 ${level}`, score].filter(Boolean).join(" · ");
    } else if (key === "cognitive_style") {
      summaryText = [
        obj.primary && `主导 ${readableProfileToken(obj.primary)}`,
        obj.secondary && `辅助 ${readableProfileToken(obj.secondary)}`,
      ].filter(Boolean).join(" · ");
    } else if (key === "learning_preference") {
      summaryText = [obj.mode, obj.pace, obj.depth].map(readableProfileToken).filter(Boolean).join(" · ");
    } else if (key === "weak_points") {
      summaryText = "建议优先安排概念辨析与针对性练习";
    } else {
      tags.push(...Object.entries(obj)
        .filter(([, item]) => ["string", "number", "boolean"].includes(typeof item))
        .map(([field, item]) => `${profileLabelMap[field] || field.replace(/_/g, " ")}：${readableProfileToken(item)}`));
    }
  } else {
    summaryText = readableProfileToken(value);
  }

  const tone: ProfileEntryView["tone"] = key === "weak_points"
    ? "risk"
    : ["knowledge_base", "tier"].includes(key)
      ? "ability"
      : ["learning_style", "cognitive_style", "learning_preference"].includes(key)
        ? "preference"
        : "identity";
  return {
    key,
    label,
    summary: summaryText || (tags.length ? "已形成可用画像标签" : "暂未填写"),
    tags: [...new Set(tags)].slice(0, 6),
    tone,
  };
}

const profileEntries = computed<ProfileEntryView[]>(() => {
  const profile = summary.value?.profile || {};
  return Object.entries(profile).slice(0, 10).map(([key, value]) => profileEntryView(key, value));
});

const resourceTypeLabel: Record<string, string> = {
  quiz: "练习题",
  document: "讲义",
  pptx: "课件",
  ppt: "课件",
  tutoring: "即时答疑",
  evaluation_report: "学习评估",
  video: "课程视频",
  prompt: "学习提示",
  mindmap: "思维导图",
};

function cleanResourceTitle(title: string, type: string): string {
  const raw = String(title || "").trim();
  const label = resourceTypeLabel[type] || "学习资源";
  if (!raw || /^生成的\s+\w+\s+资源$/i.test(raw)) return `${label}学习记录`;
  if (/^答疑[:：]\s*(hi|hello|\?+|？+)$/i.test(raw)) return "即时答疑记录";
  if (/\?{3,}|？{3,}/.test(raw)) return "即时答疑 · 内容待整理";
  return raw.replace(/^生成的\s*/i, "").replace(/\s*资源$/i, "").slice(0, 72);
}

const recentResourceViews = computed(() => (summary.value?.resources.recent || []).map((resource) => ({
  ...resource,
  typeLabel: resourceTypeLabel[String(resource.type).toLowerCase()] || readableProfileToken(resource.type),
  displayTitle: cleanResourceTitle(resource.title, String(resource.type).toLowerCase()),
})));

const mistakeTypeLabel: Record<string, string> = {
  unknown: "待归因",
  misconception: "概念混淆",
  knowledge_gap: "知识缺漏",
  concept_boundary: "概念边界",
  careless: "审题疏漏",
  calculation: "计算失误",
  reading: "阅读理解",
};

function readableMistakeType(errorType: string): string {
  return mistakeTypeLabel[String(errorType || "").toLowerCase()] || readableProfileToken(errorType) || "待归因";
}

watch(selectedStudentId, () => {
  if (activeTab.value === "analysis") void loadSummary();
  if (activeTab.value === "insights") void loadStudentAnalytics();
  if (activeTab.value === "chat") void loadRoomMessages();
});

watch(activeTab, (tab) => {
  if (tab === "analysis" && !summary.value) void loadSummary();
  if (tab === "insights") void loadStudentAnalytics();
  if (tab === "board" && !classData.value) void loadClassAnalytics();
  if (tab === "knowledge-map" && !knowledgeMapData.value) void loadKnowledgeMap();
  if (tab === "compare") void loadCompare();
  if (tab === "interventions") void loadInterventions();
  if (tab === "copilot") {
    if (!classData.value) void loadClassAnalytics();
    if (!agents.value.length) void loadAgents();
  }
  if (tab === "resources" && !resources.value.length) void loadResources();
  if (tab === "agents" && !agents.value.length) void loadAgents();
  if (tab === "chat") void loadRoomMessages();
});

// ================= Tab 1.6 · 班级看板（全班聚合视角） =================
const classData = ref<ClassAnalytics | null>(null);
const classLoading = ref(false);

async function loadClassAnalytics() {
  classLoading.value = true;
  try {
    classData.value = await getClassAnalytics({ course: teacherCourse.value });
  } catch (e: any) {
    showNotice(`班级学情加载失败：${e?.detail || e?.message || e}`);
  } finally {
    classLoading.value = false;
  }
}

const errorPalette = ["#d9480f", "#e87924", "#e6a714", "#6e8f71", "#66788a"];
const errorDistributionView = computed(() => {
  const rows = classData.value?.error_distribution || [];
  const total = Math.max(1, rows.reduce((sum, row) => sum + row.count, 0));
  return rows.map((row, index) => ({
    ...row,
    color: errorPalette[index % errorPalette.length],
    percent: Math.round((row.count / total) * 100),
  }));
});
const errorTotal = computed(() => errorDistributionView.value.reduce((sum, row) => sum + row.count, 0));
const errorDonutStyle = computed(() => {
  let cursor = 0;
  const segments = errorDistributionView.value.map((row) => {
    const start = cursor;
    cursor += row.percent;
    return `${row.color} ${start}% ${cursor}%`;
  });
  return { background: `conic-gradient(${segments.join(", ") || "#ece8e1 0 100%"})` };
});

const masteryPalette = ["#bd3f2f", "#dd6b2a", "#df9b25", "#72a169", "#2f8f5b"];
const masteryDistributionView = computed(() => {
  const rows = classData.value?.mastery.distribution || [];
  const total = Math.max(1, rows.reduce((sum, row) => sum + row.count, 0));
  return rows.map((row, index) => ({
    ...row,
    color: masteryPalette[index % masteryPalette.length],
    percent: (row.count / total) * 100,
  }));
});

interface TrendChartPoint { x: number; y: number; value: number; label: string }
function svgLinePath(points: TrendChartPoint[]): string {
  return points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
}

const classTrendChart = computed(() => {
  const rows = (classData.value?.mastery.trend || []).slice(-30);
  const width = 760;
  const height = 240;
  const padX = 40;
  const padY = 28;
  const plotWidth = width - padX * 2;
  const plotHeight = height - padY * 2;
  const maxActivity = Math.max(1, ...rows.map((row) => row.activity_count));
  const xFor = (index: number) => padX + (rows.length <= 1 ? 0 : (index / (rows.length - 1)) * plotWidth);
  const activity = rows.map((row, index) => ({
    x: xFor(index),
    y: padY + plotHeight - (row.activity_count / maxActivity) * plotHeight,
    value: row.activity_count,
    label: row.date.slice(5),
  }));
  const score = rows.map((row, index) => ({
    x: xFor(index),
    y: padY + plotHeight - Math.max(0, Math.min(1, Number(row.avg_score || 0))) * plotHeight,
    value: Math.round(Number(row.avg_score || 0) * 100),
    label: row.date.slice(5),
  }));
  const activityPath = svgLinePath(activity);
  const scorePath = svgLinePath(score);
  const areaPath = activity.length
    ? `${activityPath} L${activity[activity.length - 1].x.toFixed(1)},${(height - padY).toFixed(1)} L${activity[0].x.toFixed(1)},${(height - padY).toFixed(1)} Z`
    : "";
  const tickStep = Math.max(1, Math.ceil(rows.length / 6));
  const xTicks = activity.filter((_, index) => index % tickStep === 0 || index === activity.length - 1);
  return { width, height, padX, padY, plotHeight, maxActivity, activity, score, activityPath, scorePath, areaPath, xTicks };
});

const riskLevelLabel: Record<string, string> = { high: "高", medium: "中", low: "低" };

const activityBuckets = computed(() => {
  const a = classData.value?.activity;
  if (!a) return [];
  const total = Math.max(1, classData.value?.student_count || 0);
  return [
    { key: "active_7d", label: "7 日内活跃", shortLabel: "活跃", users: a.active_7d, tone: "", color: "#2f8f5b", percent: (a.active_7d.length / total) * 100 },
    { key: "dormant_7_30", label: "7 至 30 天未活跃", shortLabel: "需唤醒", users: a.dormant_7_30, tone: "warn", color: "#d49a28", percent: (a.dormant_7_30.length / total) * 100 },
    { key: "inactive_30p", label: "超过 30 天未活跃", shortLabel: "失联风险", users: a.inactive_30p, tone: "danger", color: "#c44b3d", percent: (a.inactive_30p.length / total) * 100 },
  ];
});

/**
 * 班级 7 日活跃率（真实派生：active_7d / student_count）
 * 用于活跃度分布卡的"大数字"视觉锚点
 */
const classActiveRate = computed(() => {
  if (!classData.value) return 0;
  const total = Math.max(1, classData.value.student_count);
  return Math.round((classData.value.active_7d / total) * 100);
});

/**
 * 班级平均掌握度（用掌握度分布桶的中心值 × 学生数加权计算）
 * 真实派生：Σ (bucket_center × count) / Σ count
 */
const classAvgMastery = computed(() => {
  const rows = classData.value?.mastery.distribution || [];
  if (!rows.length) return 0;
  let total = 0;
  let weighted = 0;
  for (const row of rows) {
    // bucket 可能是 "0-20" / "20-40" 等区间字符串，取区间中点
    const parts = String(row.bucket).split("-").map((x) => Number(x));
    const center = parts.length === 2 && parts.every((n) => !Number.isNaN(n))
      ? (parts[0] + parts[1]) / 2
      : Number(row.bucket) || 0;
    weighted += center * row.count;
    total += row.count;
  }
  return total ? Math.round(weighted / total) : 0;
});

/**
 * AI 建议的补强练习方案（真实派生自 weak_kps[0] 的未达标学生数和错题数）
 * - 时长：按错题密度估算，10-30 分钟区间
 * - 题数：按未达标学生数动态调整，3-8 题区间
 * - 均由数据决定，班级情况变化时自动跟随
 */
const suggestedDrill = computed(() => {
  const kp = classData.value?.weak_kps?.[0];
  if (!kp) return { minutes: 15, count: 5, focusKp: "" };
  const errorLoad = kp.mistake_count || 0;
  const studentLoad = kp.students_below_60 || 0;
  // 时长：每 2 道错题 ≈ 3 分钟讲解 + 每个未达标学生 ≈ 1 分钟自适应练习，clamp 到 10-30
  const rawMinutes = Math.round((errorLoad * 1.5 + studentLoad * 1.2) / 2);
  const minutes = Math.max(10, Math.min(30, rawMinutes || 15));
  // 题数：未达标越多，题数越多（分层练习）；clamp 到 3-8
  const rawCount = Math.round(studentLoad / 3 + errorLoad / 6);
  const count = Math.max(3, Math.min(8, rawCount || 5));
  return { minutes, count, focusKp: kp.kp_name };
});

/**
 * 30 天活动趋势：近 7 日 vs 前 7 日的活动次数环比变化
 * 真实派生自 mastery.trend
 */
const classTrendDelta = computed(() => {
  const rows = classData.value?.mastery.trend || [];
  if (rows.length < 14) return { activityDelta: 0, scoreDelta: 0, hasBaseline: false };
  const last7 = rows.slice(-7);
  const prev7 = rows.slice(-14, -7);
  const sum = (arr: any[], key: string) => arr.reduce((s, r) => s + Number(r[key] || 0), 0);
  const avg = (arr: any[], key: string) => arr.length ? sum(arr, key) / arr.length : 0;
  const lastAct = sum(last7, "activity_count");
  const prevAct = sum(prev7, "activity_count");
  const lastScore = avg(last7, "avg_score");
  const prevScore = avg(prev7, "avg_score");
  const activityDelta = prevAct ? Math.round(((lastAct - prevAct) / prevAct) * 100) : 0;
  const scoreDelta = prevScore ? Math.round((lastScore - prevScore) * 100) : 0;
  return { activityDelta, scoreDelta, hasBaseline: true, lastAct, prevAct };
});

type ClassPriorityKind = "student" | "resource" | "activity";
interface ClassPriorityAction {
  kind: ClassPriorityKind;
  title: string;
  detail: string;
  action: string;
  tone: "danger" | "warning" | "neutral";
  studentId?: string;
  kp?: ClassWeakKp;
}

const classPriorityActions = computed<ClassPriorityAction[]>(() => {
  const data = classData.value;
  if (!data) return [];
  const actions: ClassPriorityAction[] = [];
  const risk = data.risk_students[0];
  const weakKp = data.weak_kps[0];
  const inactiveCount = data.activity.inactive_30p.length;

  if (risk) {
    actions.push({
      kind: "student",
      title: `${risk.display_name || risk.user_id}需要优先跟进`,
      detail: risk.reasons.slice(0, 2).join("；") || "存在学习风险信号",
      action: "查看学生诊断",
      tone: risk.level === "high" ? "danger" : "warning",
      studentId: risk.user_id,
    });
  }
  if (weakKp) {
    actions.push({
      kind: "resource",
      title: `围绕「${weakKp.kp_name}」准备补强`,
      detail: `${weakKp.students_below_60}/${weakKp.students_tracked} 人未达标，平均掌握度 ${Math.round(weakKp.avg_mastery * 100)}%`,
      action: "查看教学建议",
      tone: "warning",
      kp: weakKp,
    });
  }
  if (inactiveCount) {
    actions.push({
      kind: "activity",
      title: `${inactiveCount} 名学生长期未活跃`,
      detail: "先核对学生状态，再安排个别沟通或分层任务。",
      action: "进入学生分析",
      tone: "neutral",
    });
  }
  return actions;
});

/**
 * 今日行动列表（Board v3）· 从真实的 classPriorityActions 派生
 * 保证：不使用任何硬编码假数据；无优先动作时列表为空（保留 "AI 生成分层练习" CTA 作为常态入口）
 */
interface TodayAction {
  key: string;
  title: string;
  detail: string;
  priority: "high" | "medium" | "low";
  badges?: string[];
  action: string;
  onAction: () => void;
}
const todayActions = computed<TodayAction[]>(() => {
  const items: TodayAction[] = [];
  const data = classData.value;
  const priorityMap: Record<string, "high" | "medium" | "low"> = { danger: "high", warning: "medium", neutral: "low" };
  for (const a of classPriorityActions.value) {
    items.push({
      key: a.title,
      title: a.title,
      detail: a.detail,
      priority: priorityMap[a.tone] || "medium",
      action: a.action,
      onAction: () => openClassPriority(a),
    });
  }
  // 常态入口：一键 AI 生成个性化练习包（时长/题数由 suggestedDrill 派生）
  if (data && data.weak_kps[0]) {
    const drill = suggestedDrill.value;
    items.push({
      key: "gen-drill",
      title: `布置 ${drill.minutes} 分钟补强练习`,
      detail: `围绕「${data.weak_kps[0].kp_name}」由 AI 生成 ${drill.count} 道分层练习包`,
      priority: "medium",
      badges: ["AI 生成", `${drill.count} 题`, "分层"],
      action: "去布置",
      onAction: () => askCopilot(`针对班级最薄弱知识点「${data.weak_kps[0].kp_name}」，生成一份 ${drill.minutes} 分钟补强练习包，包含 ${drill.count} 道分层题目（基础/提升/拓展）、讲解要点、错误反馈机制`),
    });
  }
  return items.slice(0, 4);
});

/**
 * 掌握度分布 Legend（Donut 图例数据）· 桶名 → 中文标签
 */
const masteryLegend = computed(() => {
  const labelMap: Record<string, string> = {
    "80-100": "优秀 (80-100%)",
    "60-80": "良好 (60-80%)",
    "40-60": "中等 (40-60%)",
    "20-40": "待提升 (20-40%)",
    "0-20": "薄弱 (0-20%)",
  };
  const colorMap: Record<string, string> = {
    "80-100": "#16A34A", "60-80": "#84CC16",
    "40-60": "#F59E0B", "20-40": "#F97316", "0-20": "#DC2626",
  };
  return masteryDistributionView.value.map((b) => ({
    ...b,
    label: labelMap[b.bucket] || `${b.bucket}%`,
    color: colorMap[b.bucket] || b.color,
  }));
});

function openClassPriority(action: ClassPriorityAction) {
  if (action.kind === "student" && action.studentId) {
    goStudentAnalysis(action.studentId);
    return;
  }
  if (action.kind === "resource" && action.kp) {
    goCopilotForKp(action.kp);
    return;
  }
  void router.push("/teacher/students");
}

/** 看板 → 学情分析：定位到指定学生 */
function goStudentAnalysis(userId: string) {
  selectedStudentId.value = userId;
  activeTab.value = "analysis";
  void loadSummary();
  void router.push({ path: "/teacher/students", query: { student: userId } });
}

// ================= 教学共创 · 真实教学数据接入现有 Agent 编排 =================
const copilotAction = ref<TeachingCopilotAction>("class_diagnosis");
const copilotScope = ref<"class" | "student">("class");
const copilotAgentKey = ref("");
const copilotInstruction = ref("");
const copilotLoading = ref(false);
const copilotResult = ref<TeachingCopilotResult | null>(null);

const copilotActions: Array<{
  key: TeachingCopilotAction;
  label: string;
  description: string;
  flow: string;
  defaultScope: "class" | "student";
}> = [
  { key: "class_diagnosis", label: "班级诊断", description: "识别优先问题与分层策略", flow: "团团 → 智狐", defaultScope: "class" },
  { key: "learning_path", label: "学习路径", description: "规划阶段、目标与复查点", flow: "团团 → 智狐", defaultScope: "student" },
  { key: "student_intervention", label: "个体干预", description: "生成辅导建议与沟通话术", flow: "团团 → 智灵", defaultScope: "student" },
];

const activeCopilotAction = computed(() =>
  copilotActions.find((item) => item.key === copilotAction.value) || copilotActions[0],
);
const selectedCopilotAgent = computed(() =>
  agents.value.find((agent) => agent.key === copilotAgentKey.value),
);

function chooseCopilotAction(action: TeachingCopilotAction, scope?: "class" | "student", instruction = "") {
  const config = copilotActions.find((item) => item.key === action);
  copilotAction.value = action;
  copilotScope.value = scope || config?.defaultScope || "class";
  copilotInstruction.value = instruction;
  copilotResult.value = null;
}

function openCopilot(action: TeachingCopilotAction, scope?: "class" | "student", instruction = "") {
  chooseCopilotAction(action, scope, instruction);
  activeTab.value = "copilot";
  if (teacherSection.value !== "interventions") {
    void router.push("/teacher/interventions");
  }
}

function goCopilotForKp(kp: ClassWeakKp) {
  openCopilot(
    "class_diagnosis",
    "class",
    `围绕「${kp.kp_name}」给出教师可执行的讲授、课堂提问和练习组织建议，不生成学生资料。当前班级平均掌握度 ${Math.round(kp.avg_mastery * 100)}%，${kp.students_below_60}/${kp.students_tracked} 人未达标，关联未解决错题 ${kp.mistake_count} 道。`,
  );
}

function goStudentCopilot(userId: string) {
  selectedStudentId.value = userId;
  openCopilot("student_intervention", "student");
}

async function runTeachingCopilot() {
  if (copilotScope.value === "student" && !selectedStudentId.value) {
    showNotice("请选择需要支持的学生");
    return;
  }
  copilotLoading.value = true;
  copilotResult.value = null;
  try {
    copilotResult.value = await consultTeachingCopilot({
      action: copilotAction.value,
      scope: copilotScope.value,
      user_id: copilotScope.value === "student" ? selectedStudentId.value : undefined,
      course: teacherCourse.value,
      instruction: copilotInstruction.value.trim() || undefined,
      agent_name: selectedCopilotAgent.value?.name || undefined,
    });
    if (!copilotResult.value.success) {
      showNotice("Agent 未生成完整建议，请检查结果中的诊断信息后重试");
    }
  } catch (e: any) {
    showNotice(`教学共创失败：${e?.detail || e?.message || e}`);
  } finally {
    copilotLoading.value = false;
  }
}

// ================= Tab 1.5 · 数据分析（每个学生的量化分析） =================
const analyticsLoading = ref(false);
const bktMasteries = ref<Array<{ kp: string; mastery: number; trend: string }>>([]);
const studentHeatmap = ref<HeatmapResponse | null>(null);
const forecastSummary = ref("");
const forecastCurrent = ref<number | null>(null);
/** 30 天遗忘曲线数据点（真实 API forecast[] 数组） */
const forecastCurve = ref<Array<{ day: number; mastery: number; ciLow: number; ciHigh: number }>>([]);
const forecastMilestones = ref<Array<{ day: number; label: string; mastery: number }>>([]);

async function loadStudentAnalytics() {
  if (!selectedStudentId.value) return;
  analyticsLoading.value = true;
  const uid = selectedStudentId.value;
  const results = await Promise.allSettled([
    getBktStatus(uid),
    getMistakesHeatmap(uid),
    getForecast(uid),
    summary.value && summary.value.user_id === uid
      ? Promise.resolve(summary.value)
      : getStudentSummary(uid, teacherCourse.value),
  ]);
  if (results[0].status === "fulfilled") {
    const r = results[0].value as Record<string, any>;
    const masteries = (r.masteries ?? {}) as Record<string, number>;
    const trends = (r.trends ?? {}) as Record<string, string>;
    bktMasteries.value = Object.entries(masteries)
      .map(([kp, mastery]) => ({ kp, mastery, trend: trends[kp] ?? "stable" }))
      .sort((a, b) => a.mastery - b.mastery)
      .slice(0, 12);
  } else {
    bktMasteries.value = [];
  }
  studentHeatmap.value = results[1].status === "fulfilled" ? results[1].value : null;
  if (results[2].status === "fulfilled") {
    const f = results[2].value as Record<string, any>;
    forecastSummary.value = String(f.summary_text ?? f.note ?? "");
    forecastCurrent.value = f.current_mastery != null ? Number(f.current_mastery) : null;
    const raw = Array.isArray(f.forecast) ? f.forecast : [];
    forecastCurve.value = raw.map((p: any) => ({
      day: Number(p.day ?? 0),
      mastery: Number(p.p_learned ?? p.mastery ?? 0),
      ciLow: Number(p.ci_low ?? p.p_learned ?? p.mastery ?? 0),
      ciHigh: Number(p.ci_high ?? p.p_learned ?? p.mastery ?? 0),
    }));
    forecastMilestones.value = Array.isArray(f.milestones)
      ? f.milestones.map((m: any) => ({
          day: Number(m.day ?? 0),
          label: String(m.label ?? ""),
          mastery: Number(m.p_at_day ?? m.target ?? 0),
        }))
      : [];
    // 数据更新后重绘（DOM tick 后）
    setTimeout(renderForecastChart, 40);
  } else {
    forecastSummary.value = "";
    forecastCurrent.value = null;
    forecastCurve.value = [];
    forecastMilestones.value = [];
  }
  if (results[3].status === "fulfilled") {
    summary.value = results[3].value as StudentSummary;
  }
  analyticsLoading.value = false;
}

const heatmapTopRows = computed(() => {
  const matrix = studentHeatmap.value?.matrix ?? [];
  return [...matrix].sort((a: any, b: any) => b.total - a.total).slice(0, 6);
});

function trendLabel(t: string): string {
  return t === "improving" ? "↑ 上升" : t === "declining" ? "↓ 下滑" : "→ 平稳";
}

// ================= Tab 2 · 课程资源 =================
const resources = ref<TeacherResource[]>([]);
const resourcesLoading = ref(false);
const resourceQuery = ref("");
const resourceStatusFilter = ref("");

const showResourceForm = ref(false);
const editingResourceId = ref("");
const resourceForm = ref({
  title: "",
  type: "document",
  content: "",
  scope: "course" as "course" | "student",
  status: "published" as "draft" | "published" | "archived",
  tags: "",
  kp_ids: "",
  targetUserId: "",
});

const showUploadForm = ref(false);
const uploadSubmitting = ref(false);
const uploadFile = ref<File | null>(null);
const uploadForm = ref({
  title: "",
  type: "document",
  scope: "course" as "course" | "student",
  status: "draft" as "draft" | "published" | "archived",
  tags: "",
  kp_ids: "",
  targetUserId: "",
});

const resourceTypeOptions = [
  { key: "prompt", label: "学习提示词" },
  { key: "video", label: "课程视频" },
  { key: "document", label: "讲解文档" },
  { key: "mindmap", label: "思维导图" },
  { key: "quiz", label: "练习题库" },
  { key: "code", label: "代码案例" },
  { key: "ppt", label: "教学PPT" },
  { key: "reading", label: "拓展阅读" },
  { key: "evaluation_report", label: "学习评估" },
  { key: "pptx", label: "教学PPT" },
  { key: "tutoring", label: "即时答疑" },
];

const resourceCreatorLabel: Record<string, string> = {
  teacher: "任课教师",
  evaluator: "评估 Agent",
  student: "学生",
  system: "系统",
};

const studioResourceTypes = new Set(["prompt", "video"]);
const displayedResources = computed(() => (
  isTeachingStudio.value
    ? resources.value.filter((item) => studioResourceTypes.has(String(item.type).toLowerCase()))
    : resources.value
));
const editorResourceTypeOptions = computed(() => (
  isTeachingStudio.value
    ? resourceTypeOptions.filter((item) => studioResourceTypes.has(item.key))
    : resourceTypeOptions
));
const uploadResourceTypeOptions = computed(() => (
  isTeachingStudio.value
    ? resourceTypeOptions.filter((item) => item.key === "video")
    : resourceTypeOptions.filter((item) => item.key !== "prompt")
));

const statusLabel: Record<string, string> = {
  draft: "草稿",
  published: "已发布",
  archived: "已下架",
};

async function loadResources() {
  resourcesLoading.value = true;
  try {
    const r = await listTeacherResources({
      q: resourceQuery.value || undefined,
      status: resourceStatusFilter.value || undefined,
    } as any);
    resources.value = r.resources;
  } catch (e: any) {
    showNotice(`资源加载失败：${e?.detail || e?.message || e}`);
  } finally {
    resourcesLoading.value = false;
  }
}

function applyTeacherRouteQuery() {
  const student = route.query.student;
  if (typeof student === "string" && student) {
    selectedStudentId.value = student;
  }
  const requestedTab = route.meta.teacherTab || route.query.tab;
  if (
    typeof requestedTab === "string"
    && currentSection.value.tabs.includes(requestedTab as TeacherTab)
  ) {
    activeTab.value = requestedTab as TeacherTab;
  }
  if (!["resources", "studio"].includes(teacherSection.value) && activeTab.value !== "resources") return;
  activeTab.value = "resources";
  const query = route.query.q;
  resourceQuery.value = typeof query === "string" ? query : "";
  void loadResources();
}

watch(
  () => [route.query.tab, route.query.q, route.query.student, teacherSection.value],
  () => applyTeacherRouteQuery(),
);

function openCreateResource(preferredType = "document") {
  if (!students.value.length) void loadStudents();
  editingResourceId.value = "";
  resourceForm.value = {
    title: "", type: preferredType, content: "",
    scope: "course", status: "published", tags: "", kp_ids: "", targetUserId: "",
  };
  showResourceForm.value = true;
}

function openUploadResource(preferredType = "document") {
  if (!students.value.length) void loadStudents();
  uploadFile.value = null;
  uploadForm.value = {
    title: "", type: preferredType, scope: "course", status: "draft", tags: "", kp_ids: "", targetUserId: "",
  };
  showUploadForm.value = true;
}

function selectUploadFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] || null;
  if (!file) return;
  const isVideo = /\.(mp4|webm|mov|m4v)$/i.test(file.name);
  const limit = isVideo ? 200 * 1024 * 1024 : 20 * 1024 * 1024;
  if (file.size > limit) {
    showNotice(isVideo ? "单个课程视频不能超过 200 MB" : "单个资料不能超过 20 MB");
    input.value = "";
    return;
  }
  if (isVideo) uploadForm.value.type = "video";
  uploadFile.value = file;
  if (!uploadForm.value.title.trim()) {
    uploadForm.value.title = file.name.replace(/\.[^.]+$/, "");
  }
}

function formatFileSize(size: number): string {
  if (!size) return "0 B";
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

async function submitUploadResource() {
  if (!uploadFile.value) {
    showNotice("请选择要上传的资料");
    return;
  }
  if (uploadForm.value.scope === "student" && !uploadForm.value.targetUserId) {
    showNotice("请先选择需要接收资料的学生");
    return;
  }
  uploadSubmitting.value = true;
  try {
    await uploadTeacherResource({
      file: uploadFile.value,
      title: uploadForm.value.title.trim(),
      resourceType: uploadForm.value.type,
      course: teacherCourse.value,
      scope: uploadForm.value.scope,
      status: uploadForm.value.status,
      tags: uploadForm.value.tags,
      kpIds: uploadForm.value.kp_ids,
      targetUserIds: uploadForm.value.targetUserId,
      createdBy: teacherAccount.value,
    });
    showUploadForm.value = false;
    uploadFile.value = null;
    showNotice(uploadForm.value.status === "published" ? "资料已上传并发布" : "资料已上传为草稿，审核后可发布");
    await loadResources();
  } catch (e: any) {
    showNotice(`上传失败：${e?.detail || e?.message || e}`);
  } finally {
    uploadSubmitting.value = false;
  }
}

function openEditResource(item: TeacherResource) {
  editingResourceId.value = item.id;
  resourceForm.value = {
    title: item.title,
    type: item.type,
    content: item.content,
    scope: (item.metadata.scope as any) || "course",
    status: (item.metadata.status as any) || "published",
    tags: (item.tags || []).join(","),
    kp_ids: (item.metadata.kp_ids || []).join(","),
    targetUserId: (item.metadata.target_user_ids || [])[0] || "",
  };
  showResourceForm.value = true;
}

function splitCsv(text: string): string[] {
  return text.split(/[,，]/).map((s) => s.trim()).filter(Boolean);
}

async function submitResourceForm() {
  if (!resourceForm.value.title.trim()) {
    showNotice("请填写资源标题");
    return;
  }
  if (resourceForm.value.scope === "student" && !resourceForm.value.targetUserId) {
    showNotice("请先选择需要接收内容的学生");
    return;
  }
  const payload = {
    title: resourceForm.value.title.trim(),
    type: resourceForm.value.type,
    content: resourceForm.value.content,
    course: teacherCourse.value,
    scope: resourceForm.value.scope,
    status: resourceForm.value.status,
    tags: splitCsv(resourceForm.value.tags),
    kp_ids: splitCsv(resourceForm.value.kp_ids),
    target_user_ids: resourceForm.value.scope === "student" ? [resourceForm.value.targetUserId] : [],
    created_by: teacherAccount.value,
  };
  try {
    if (editingResourceId.value) {
      await updateTeacherResource(editingResourceId.value, payload);
      showNotice("资源已更新");
    } else {
      await createTeacherResource(payload);
      showNotice("资源已创建");
    }
    showResourceForm.value = false;
    await loadResources();
  } catch (e: any) {
    showNotice(`保存失败：${e?.detail || e?.message || e}`);
  }
}

async function toggleResourceStatus(item: TeacherResource) {
  const next = item.metadata.status === "published" ? "draft" : "published";
  try {
    await updateTeacherResource(item.id, { status: next });
    showNotice(next === "published" ? "已发布" : "已下架为草稿");
    await loadResources();
  } catch (e: any) {
    showNotice(`操作失败：${e?.detail || e?.message || e}`);
  }
}

async function removeResource(item: TeacherResource) {
  if (!window.confirm(`确定删除资源《${item.title}》？`)) return;
  try {
    await deleteTeacherResource(item.id);
    showNotice("已删除");
    await loadResources();
  } catch (e: any) {
    showNotice(`删除失败：${e?.detail || e?.message || e}`);
  }
}

async function downloadResource(item: TeacherResource) {
  const attachment = item.metadata.attachment;
  if (!attachment) return;
  try {
    const blob = await downloadTeacherResource(item.id);
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = attachment.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 0);
  } catch (e: any) {
    showNotice(`下载失败：${e?.detail || e?.message || e}`);
  }
}

const previewVideoItem = ref<TeacherResource | null>(null);
const previewVideoUrl = ref("");
const previewVideoLoading = ref(false);

function isVideoResource(item: TeacherResource): boolean {
  const mediaType = String(item.metadata.attachment?.media_type || "").toLowerCase();
  return String(item.type).toLowerCase() === "video" || mediaType.startsWith("video/");
}

function closeVideoPreview() {
  previewVideoItem.value = null;
  if (previewVideoUrl.value) URL.revokeObjectURL(previewVideoUrl.value);
  previewVideoUrl.value = "";
}

async function previewVideoResource(item: TeacherResource) {
  if (!item.metadata.attachment) return;
  closeVideoPreview();
  previewVideoItem.value = item;
  previewVideoLoading.value = true;
  try {
    const blob = await downloadTeacherResource(item.id);
    previewVideoUrl.value = URL.createObjectURL(blob);
  } catch (e: any) {
    closeVideoPreview();
    showNotice(`视频预览失败：${e?.detail || e?.message || e}`);
  } finally {
    previewVideoLoading.value = false;
  }
}

// 指派资源
const assigningResource = ref<TeacherResource | null>(null);
const assignNote = ref("");

async function confirmAssignResource() {
  if (!assigningResource.value || !selectedStudentId.value) return;
  try {
    await assignResourceToStudent({
      resource_id: assigningResource.value.id,
      user_id: selectedStudentId.value,
      course: teacherCourse.value,
      note: assignNote.value.trim(),
      sender_id: teacherAccount.value,
      sender_name: teacherName.value,
    });
    showNotice(`已推荐给 ${selectedStudentId.value}，群聊中可见`);
    assigningResource.value = null;
    assignNote.value = "";
  } catch (e: any) {
    showNotice(`指派失败：${e?.detail || e?.message || e}`);
  }
}

// ================= Tab 3 · Agent 管理 =================
const agents = ref<AgentConfig[]>([]);
const agentsLoading = ref(false);
const showAgentForm = ref(false);
const editingAgentKey = ref("");
const agentForm = ref({
  name: "",
  title: "",
  role_desc: "",
  system_prompt: "",
  capabilities: "",
  enabled: true,
});

const agentKindByKey: Record<string, AvatarKind> = {
  planner: "planner",
  tutor: "tutor",
  content: "content",
  quiz: "quiz",
  evaluation: "evaluation",
  evaluator: "evaluation",
  safety: "safety",
  profile: "profile",
};

interface AgentVisual {
  src: string;
  emoji: string;
  color: string;
  responsibility: string;
}

function agentVisual(agent: AgentConfig): AgentVisual {
  const key = String(agent.key || "").toLowerCase();
  const byName = (Object.values(AGENT_AVATARS) as AvatarEntry[]).find((entry) => entry.nick === agent.name);
  const entry = AGENT_AVATARS[agentKindByKey[key]] || byName;
  const configured = String(agent.avatar || "").trim();
  const configuredImage = configured.startsWith("/integrated-map/") || configured.startsWith("data:image/")
    ? configured
    : "";
  return {
    src: entry?.png || configuredImage,
    emoji: entry?.emoji || (/^\p{Extended_Pictographic}/u.test(configured) ? configured : agent.name.slice(0, 1).toUpperCase()),
    color: entry?.color || "#6b7280",
    responsibility: entry?.responsibility || agent.role_desc || "教师配置的专项协作 Agent",
  };
}

async function loadAgents() {
  agentsLoading.value = true;
  try {
    const r = await listAgentConfigs();
    agents.value = r.agents;
  } catch (e: any) {
    showNotice(`Agent 列表加载失败：${e?.detail || e?.message || e}`);
  } finally {
    agentsLoading.value = false;
  }
}

function openCreateAgent() {
  editingAgentKey.value = "";
  agentForm.value = {
    name: "", title: "", role_desc: "", system_prompt: "", capabilities: "", enabled: true,
  };
  showAgentForm.value = true;
}

function openEditAgent(agent: AgentConfig) {
  editingAgentKey.value = agent.key;
  agentForm.value = {
    name: agent.name,
    title: agent.title,
    role_desc: agent.role_desc,
    system_prompt: agent.system_prompt,
    capabilities: (agent.capabilities || []).join(","),
    enabled: agent.enabled,
  };
  showAgentForm.value = true;
}

const editingAgentIsBuiltin = computed(() => {
  const agent = agents.value.find((a) => a.key === editingAgentKey.value);
  return Boolean(agent?.builtin);
});

async function submitAgentForm() {
  if (!agentForm.value.name.trim()) {
    showNotice("请填写 Agent 名称");
    return;
  }
  const payload = {
    name: agentForm.value.name.trim(),
    title: agentForm.value.title,
    role_desc: agentForm.value.role_desc,
    system_prompt: agentForm.value.system_prompt,
    capabilities: splitCsv(agentForm.value.capabilities),
    enabled: agentForm.value.enabled,
    created_by: teacherAccount.value,
  };
  try {
    if (editingAgentKey.value) {
      await updateAgentConfig(editingAgentKey.value, payload as any);
      showNotice("Agent 已更新");
    } else {
      await createAgentConfig(payload as any);
      showNotice(`Agent 已创建，群聊中 @${payload.name} 即可调用`);
    }
    showAgentForm.value = false;
    await loadAgents();
  } catch (e: any) {
    const detail = e?.detail || e?.message || String(e);
    showNotice(detail === "agent_name_exists" ? "该名称已存在" : `保存失败：${detail}`);
  }
}

async function toggleAgentEnabled(agent: AgentConfig) {
  try {
    await updateAgentConfig(agent.key, { enabled: !agent.enabled } as any);
    showNotice(agent.enabled ? `已停用「${agent.name}」` : `已启用「${agent.name}」`);
    await loadAgents();
  } catch (e: any) {
    showNotice(`操作失败：${e?.detail || e?.message || e}`);
  }
}

async function removeAgent(agent: AgentConfig) {
  if (agent.builtin) return;
  if (!window.confirm(`确定删除 Agent「${agent.name}」？`)) return;
  try {
    await deleteAgentConfig(agent.key);
    showNotice("已删除");
    await loadAgents();
  } catch (e: any) {
    showNotice(`删除失败：${e?.detail || e?.message || e}`);
  }
}

// ================= Tab 4 · 路径推荐 =================
const pathForm = ref({
  title: "",
  note: "",
});
const pathStages = ref<Array<{ name: string; desc: string }>>([
  { name: "", desc: "" },
]);
const pathSubmitting = ref(false);

function addStage() {
  pathStages.value.push({ name: "", desc: "" });
}

function removeStage(index: number) {
  if (pathStages.value.length <= 1) return;
  pathStages.value.splice(index, 1);
}

async function submitPath() {
  const stages = pathStages.value
    .map((s) => ({ name: s.name.trim(), desc: s.desc.trim() }))
    .filter((s) => s.name);
  if (!selectedStudentId.value) {
    showNotice("请先选择学生");
    return;
  }
  if (!pathForm.value.title.trim() || !stages.length) {
    showNotice("请填写路径标题和至少一个阶段");
    return;
  }
  pathSubmitting.value = true;
  try {
    await assignPathToStudent({
      user_id: selectedStudentId.value,
      course: teacherCourse.value,
      title: pathForm.value.title.trim(),
      stages,
      note: pathForm.value.note.trim(),
      sender_id: teacherAccount.value,
      sender_name: teacherName.value,
    });
    showNotice(`路径已推送到 ${selectedStudentId.value} 的路径页与群聊`);
    pathForm.value = { title: "", note: "" };
    pathStages.value = [{ name: "", desc: "" }];
  } catch (e: any) {
    showNotice(`推送失败：${e?.detail || e?.message || e}`);
  } finally {
    pathSubmitting.value = false;
  }
}

// ================= Tab 5 · 群聊消息 =================
const roomMessages = ref<GroupChatMessage[]>([]);
const roomLoading = ref(false);
const chatDraft = ref("");
const chatSending = ref(false);

const currentRoomId = computed(() =>
  selectedStudentId.value ? buildRoomId(teacherCourse.value, selectedStudentId.value) : "",
);

async function loadRoomMessages() {
  if (!currentRoomId.value) return;
  roomLoading.value = true;
  try {
    const r = await listGroupChatMessages(currentRoomId.value);
    roomMessages.value = r.messages;
  } catch (e: any) {
    showNotice(`群聊消息加载失败：${e?.detail || e?.message || e}`);
  } finally {
    roomLoading.value = false;
  }
}

async function sendChatMessage() {
  const content = chatDraft.value.trim();
  if (!content || !selectedStudentId.value) return;
  chatSending.value = true;
  try {
    if (content.includes("@")) {
      // 教师 @Agent：走现有多智能体编排（/chat/send 携带房间信息），
      // Agent 回复会自动写入同一群聊房间，学生刷新即可看到
      const { postJson } = await import("@/api/http");
      showNotice("已提交给 Agent 编排，回复生成中（可能需要数十秒）...");
      await postJson("/api/v1/chat/send", {
        message: content,
        session_id: `teacher-${currentRoomId.value}`,
        user_id: selectedStudentId.value,
        course: teacherCourse.value,
        room_id: currentRoomId.value,
        sender_role: "teacher",
        sender_name: teacherName.value,
      });
    } else {
      // 普通教师消息：不触发 LLM
      await sendTeacherMessage({
        user_id: selectedStudentId.value,
        course: teacherCourse.value,
        content,
        sender_id: teacherAccount.value,
        sender_name: teacherName.value,
      });
    }
    chatDraft.value = "";
    await loadRoomMessages();
  } catch (e: any) {
    showNotice(`发送失败：${e?.detail || e?.message || e}`);
  } finally {
    chatSending.value = false;
  }
}

const messageTypeLabel: Record<string, string> = {
  text: "消息",
  teacher_message: "教师消息",
  agent_reply: "Agent 回复",
  resource_card: "资源推荐",
  path_card: "路径推荐",
  system_notice: "系统通知",
};

function senderClass(m: GroupChatMessage): string {
  if (m.sender_role === "teacher") return "teacher";
  if (m.sender_role === "agent") return "agent";
  return "student";
}

function loadSectionData(section: TeacherSection) {
  if (section === "overview") {
    void loadClassAnalytics();
  }
  if (section === "students") {
    void loadStudents();
  }
  if (section === "resources" || section === "studio") {
    void loadStudents();
    applyTeacherRouteQuery();
  }
  if (section === "interventions") {
    void loadStudents();
    void loadClassAnalytics();
    void loadAgents();
  }
  if (section === "agents") {
    void loadAgents();
  }
}

// ================= Studio · 教师提示词工作台 =================
// 真实 API：consultTeachingCopilot 生成 + createTeacherResource 发布
type StudioContentType = "document" | "ppt" | "video" | "code" | "mindmap" | "reading";
const STUDIO_TYPES: Array<{ key: StudioContentType; label: string; icon: any; hint: string; agent: string }> = [
  { key: "document", label: "文档讲义",   icon: BookOpen,      hint: "结构化 Markdown 讲义，含要点/例题/易错点", agent: "阿匠" },
  { key: "ppt",      label: "PPT 课件",   icon: LayoutDashboard, hint: "生成可下载的真实 PPTX 课件文件",           agent: "阿匠" },
  { key: "video",    label: "教学视频",   icon: Video,           hint: "生成可播放、可下载的真实 MP4 教学短视频", agent: "阿匠" },
  { key: "code",     label: "代码案例",   icon: Pencil,        hint: "含注释的可运行 Python 示例",              agent: "阿匠" },
  { key: "mindmap",  label: "思维导图",   icon: Network,       hint: "Mermaid 格式，可视化知识关系",            agent: "阿匠" },
  { key: "reading",  label: "拓展阅读",   icon: BookMarked, hint: "论文导读或延伸材料", agent: "阿匠" },
];

const studioPrompt = ref("");
const studioType = ref<StudioContentType>("document");
const studioScope = ref<"course" | "student">("course");
const studioTargetUserId = ref("");
const studioLoading = ref(false);
const studioStage = ref("");
const studioActiveAgent = ref("");
const studioResult = ref<{
  content: string;
  agents_invoked: Array<{ name: string; success: boolean }>;
  primary_agent: string;
  action_label: string;
  safety_level?: string;
  artifact?: {
    id: string;
    type: "ppt" | "video";
    filename: string;
    filepath: string;
    download_url: string;
    metadata: Record<string, any>;
  };
  binary_error?: string;
} | null>(null);

const STUDIO_PROMPT_HINTS = [
  "为「多智能体系统 (MAS)」写一份 1200 字讲义，包含：核心概念、协作模型、典型应用、3 道随堂练习",
  "生成一份 6 页 PPT 大纲，主题为「Transformer 架构」，每页 3-5 个要点",
  "写一段 60 行以内、含中文注释的 Python 代码，演示 K-Means 聚类实现",
  "输出一张 Mermaid 思维导图，涵盖机器学习基础 → 监督/无监督/强化 → 典型算法",
];

function studioArtifactTopic(prompt: string): string {
  const quoted = prompt.match(/[《「“"]([^》」”"]{2,80})[》」”"]/);
  if (quoted?.[1]) return quoted[1].trim();
  const themed = prompt.match(/主题(?:为|是|：|:)?\s*([^，。；\n]{2,80})/i);
  if (themed?.[1]) return themed[1].replace(/PPT|课件|视频/gi, "").trim();
  return prompt
    .replace(/请|帮我|生成|制作|一份|一个|PPT|课件|教学视频|视频/gi, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80) || "课程知识点";
}

async function runStudio() {
  const prompt = studioPrompt.value.trim();
  if (!prompt) {
    showNotice("请先编写提示词");
    return;
  }
  if (studioScope.value === "student" && !studioTargetUserId.value) {
    showNotice("已选择学生级，请指定目标学生");
    return;
  }
  studioLoading.value = true;
  studioResult.value = null;
  studioActiveAgent.value = "阿匠";
  studioStage.value = `阿匠 正在生成 ${STUDIO_TYPES.find((t) => t.key === studioType.value)?.label || "内容"}…`;

  // UI 阶段推进（阿匠 主导，团团 审核，球球 安全校验）
  const stages = [
    { agent: "阿匠", stage: "整合课程知识与教学意图…" },
    { agent: "团团", stage: "对齐 Bloom 层级与班级学情…" },
    { agent: "球球", stage: "过教学安全评估与幻觉核验…" },
  ];
  let idx = 0;
  const stageTimer = window.setInterval(() => {
    idx += 1;
    if (idx < stages.length) {
      studioActiveAgent.value = stages[idx].agent;
      studioStage.value = stages[idx].stage;
    }
  }, 1400);

  try {
    const typeCtx = STUDIO_TYPES.find((t) => t.key === studioType.value);
    const instruction = `【教师提示】${prompt}\n\n【输出类型】${typeCtx?.label}（${typeCtx?.hint}）\n【目标范围】${studioScope.value === "course" ? "全班共用" : `指派给学生 ${studioTargetUserId.value}`}`;
    const result = await consultTeachingCopilot({
      action: "class_diagnosis",
      scope: studioScope.value === "course" ? "class" : "student",
      user_id: studioScope.value === "student" ? studioTargetUserId.value : undefined,
      course: teacherCourse.value,
      instruction,
    });
    window.clearInterval(stageTimer);
    const generatedResult = {
      content: result?.content || "",
      agents_invoked: result?.agents_invoked || [],
      primary_agent: result?.primary_agent || "阿匠",
      action_label: result?.action_label || typeCtx?.label || "",
      safety_level: result?.safety?.level,
    };
    studioResult.value = generatedResult;

    if (studioType.value === "ppt" || studioType.value === "video") {
      const isVideo = studioType.value === "video";
      const binaryType: "manim" | "pptx" = isVideo ? "manim" : "pptx";
      studioActiveAgent.value = "阿匠";
      studioStage.value = isVideo ? "正在渲染真实 MP4 文件…" : "正在生成真实 PPTX 文件…";
      try {
        const binary = await generateMulti({
          topic: studioArtifactTopic(prompt),
          description: (result?.content || prompt).slice(0, 380),
          types: [binaryType],
          session_id: `teacher-studio-${Date.now()}`,
          include_manim: isVideo,
          manim_render: isVideo,
          user_id: studioScope.value === "student" ? studioTargetUserId.value : "",
        });
        const envelope = binary.results?.[binaryType];
        const download = envelope?.downloads?.find((item: any) => item?.id && item?.exists !== false);
        if (!envelope?.success || !envelope.filepath || !download?.id) {
          throw new Error(envelope?.error || "二进制文件未生成或尚不可下载");
        }
        studioResult.value = {
          ...generatedResult,
          artifact: {
            id: String(download.id),
            type: isVideo ? "video" : "ppt",
            filename: String(download.filename || envelope.filepath.split(/[\\/]/).pop() || "教学资源"),
            filepath: String(envelope.filepath),
            download_url: getArtifactDownloadFullUrl(String(download.id)),
            metadata: { ...(envelope.metadata || {}), ...(download.metadata || {}) },
          },
        };
      } catch (binaryError: any) {
        studioResult.value = {
          ...generatedResult,
          binary_error: binaryError?.detail || binaryError?.message || String(binaryError),
        };
      }
    }
    studioStage.value = "";
    studioActiveAgent.value = "";
  } catch (e: any) {
    window.clearInterval(stageTimer);
    showNotice(`生成失败：${e?.detail || e?.message || e}`);
    studioResult.value = { content: `生成失败：${e?.detail || e?.message || e}`, agents_invoked: [], primary_agent: "", action_label: "" };
  } finally {
    studioLoading.value = false;
  }
}

async function publishStudioResult(status: "draft" | "published") {
  if (!studioResult.value?.content) {
    showNotice("尚无可发布内容");
    return;
  }
  const title = studioPrompt.value.slice(0, 40).trim() + (studioPrompt.value.length > 40 ? "…" : "");
  if ((studioType.value === "ppt" || studioType.value === "video") && !studioResult.value.artifact) {
    showNotice("真实二进制文件尚未生成，不能只发布结构化正文；请先重新生成文件");
    return;
  }
  try {
    const commonPayload = {
      title: title || `AI 生成的${STUDIO_TYPES.find((t) => t.key === studioType.value)?.label || "教学资源"}`,
      content: studioResult.value.content,
      course: teacherCourse.value,
      scope: studioScope.value,
      status,
      target_user_ids: studioScope.value === "student" && studioTargetUserId.value ? [studioTargetUserId.value] : [],
      created_by: teacherName.value,
    };
    if (studioResult.value.artifact) {
      await createTeacherResourceFromArtifact({
        ...commonPayload,
        artifact_id: studioResult.value.artifact.id,
        type: studioResult.value.artifact.type,
      });
    } else {
      await createTeacherResource({ ...commonPayload, type: studioType.value });
    }
    showNotice(status === "published" ? "已发布到学生端资源中心" : "已保存为草稿");
    void loadResources();
    studioResult.value = null;
    studioPrompt.value = "";
  } catch (e: any) {
    showNotice(`保存失败：${e?.detail || e?.message || e}`);
  }
}

function useStudioHint(hint: string) {
  studioPrompt.value = hint;
}

// ================= 一键干预面板 =================
// 三类真实 API：sendTeacherMessage / assignResourceToStudent / assignPathToStudent
type InterventionMode = "message" | "resource" | "path";
const quickMode = ref<InterventionMode>("message");
const quickTargets = ref<string[]>([]);        // 目标学生 user_ids（支持批量）
const quickMessage = ref("");
const quickResourceId = ref("");
const quickResourceNote = ref("");
const quickPathTitle = ref("");
const quickPathStages = ref("");
const quickSending = ref(false);

/**
 * 消息模板：预置的 5 类常用话术，教师可一键套用
 */
const MESSAGE_TEMPLATES = [
  { key: "welcome", label: "新学期问候", content: "同学你好，欢迎进入新学期。我看到你最近的学习记录，希望能一起制定一个适合你的节奏。" },
  { key: "risk", label: "错题积压提醒", content: "老师注意到你近期错题较多，我们一起看看是概念点还是练习不够；随时找我聊。" },
  { key: "streak", label: "连续学习鼓励", content: "看到你已经连续多天保持学习，这个节奏非常好，继续保持！有需要的资源随时告诉我。" },
  { key: "praise", label: "阶段掌握表扬", content: "你在最近的知识点上表现明显提升，说明方法是对的。可以尝试挑战难度更高的题目。" },
  { key: "checkup", label: "阶段性复习", content: "我们进入下一模块前，先把已学核心知识点做一次复盘。老师给你安排了针对性复习任务。" },
];

function applyMessageTemplate(t: typeof MESSAGE_TEMPLATES[number]) {
  quickMessage.value = t.content;
}

/** 一键干预：根据 quickMode 调用对应真实 API，可批量 */
async function runQuickIntervention() {
  if (!quickTargets.value.length) {
    showNotice("请先选择至少一名目标学生");
    return;
  }
  if (quickMode.value === "message" && !quickMessage.value.trim()) {
    showNotice("请填写消息内容或点击话术模板");
    return;
  }
  if (quickMode.value === "resource" && !quickResourceId.value) {
    showNotice("请选择要指派的资源");
    return;
  }
  if (quickMode.value === "path") {
    if (!quickPathTitle.value.trim() || !quickPathStages.value.trim()) {
      showNotice("请填写路径标题和至少一个阶段");
      return;
    }
  }
  quickSending.value = true;
  const senderId = "teacher";
  const senderName = teacherName.value;
  const results: Array<{ uid: string; ok: boolean; err?: string }> = [];
  for (const uid of quickTargets.value) {
    try {
      if (quickMode.value === "message") {
        await sendTeacherMessage({
          user_id: uid,
          content: quickMessage.value.trim(),
          course: teacherCourse.value,
          sender_id: senderId,
          sender_name: senderName,
        });
      } else if (quickMode.value === "resource") {
        await assignResourceToStudent({
          resource_id: quickResourceId.value,
          user_id: uid,
          course: teacherCourse.value,
          note: quickResourceNote.value.trim() || undefined,
          sender_id: senderId,
          sender_name: senderName,
        });
      } else if (quickMode.value === "path") {
        const stages = quickPathStages.value
          .split(/[\n,，、]/)
          .map((s) => s.trim())
          .filter(Boolean);
        await assignPathToStudent({
          user_id: uid,
          title: quickPathTitle.value.trim(),
          stages,
          course: teacherCourse.value,
          sender_id: senderId,
          sender_name: senderName,
        });
      }
      results.push({ uid, ok: true });
    } catch (e: any) {
      results.push({ uid, ok: false, err: e?.detail || e?.message || String(e) });
    }
  }
  const ok = results.filter((r) => r.ok).length;
  const fail = results.length - ok;
  quickSending.value = false;
  showNotice(`干预已发送：成功 ${ok} · 失败 ${fail}`);
  if (ok > 0) {
    // 清空表单 + 刷新干预日志
    if (quickMode.value === "message") quickMessage.value = "";
    if (quickMode.value === "path") { quickPathTitle.value = ""; quickPathStages.value = ""; }
    quickTargets.value = [];
    void loadInterventions();
  }
}

/** 让 Copilot 帮我起草消息 */
async function draftMessageWithAI() {
  const targets = quickTargets.value;
  if (!targets.length) {
    showNotice("请先选择目标学生");
    return;
  }
  const target = targets[0];
  const stu = students.value.find((s) => s.user_id === target);
  quickSending.value = true;
  try {
    const result = await consultTeachingCopilot({
      action: "student_intervention",
      scope: "student",
      user_id: target,
      course: teacherCourse.value,
      instruction: `请为学生${stu?.display_name || target}起草一段不超过 100 字的鼓励与引导消息，语气温和，包含具体行动建议`,
    });
    if (result?.content) {
      // 抽出前 200 字作为消息（避免整段落入）
      quickMessage.value = String(result.content).replace(/[#*_>`]/g, "").slice(0, 220).trim();
      showNotice("AI 已起草消息，可编辑后发送");
    } else {
      showNotice("Copilot 未返回内容");
    }
  } catch (e: any) {
    showNotice(`AI 起草失败：${e?.detail || e?.message || e}`);
  } finally {
    quickSending.value = false;
  }
}

// interventions section 挂载时加载资源列表（一键干预 → 资源模式需要下拉）
watch(activeTab, (tab) => {
  if (tab === "interventions" && !resources.value.length) {
    void loadResources();
  }
}, { immediate: false });

// ================= 增强 1：教师干预日志 =================
const interventionLog = ref<InterventionLog | null>(null);
const interventionLoading = ref(false);

async function loadInterventions() {
  interventionLoading.value = true;
  try {
    interventionLog.value = await listInterventions({ days: 30 });
  } catch (e: any) {
    showNotice(`干预日志加载失败：${e?.detail || e?.message || e}`);
  } finally {
    interventionLoading.value = false;
  }
}

const interventionTypeLabel: Record<string, string> = {
  resource_card: "资源推荐",
  path_card: "路径推荐",
  teacher_message: "教师消息",
};

// ================= 增强 2：班级知识图谱热力图 =================
const knowledgeMapData = ref<KnowledgeMap | null>(null);
const knowledgeMapLoading = ref(false);

async function loadKnowledgeMap() {
  knowledgeMapLoading.value = true;
  try {
    knowledgeMapData.value = await getKnowledgeMap(teacherCourse.value);
  } catch (e: any) {
    showNotice(`知识图谱加载失败：${e?.detail || e?.message || e}`);
  } finally {
    knowledgeMapLoading.value = false;
  }
}

function knowledgePriorityScore(node: KnowledgeMapNode): number {
  const masteryRisk = node.avg_mastery == null ? 0.25 : 1 - node.avg_mastery;
  return masteryRisk * 55 + node.students_below_60 * 2.2 + node.open_mistakes * 1.4;
}

const sortedKpNodes = computed(() => {
  if (!knowledgeMapData.value) return [];
  return [...knowledgeMapData.value.nodes].sort((a, b) =>
    knowledgePriorityScore(b) - knowledgePriorityScore(a),
  );
});

const priorityKnowledgeNodes = computed(() => sortedKpNodes.value.slice(0, 6));

const selectedKnowledgeNodeId = ref("");
const selectedKnowledgeNode = computed(() => {
  const nodes = knowledgeMapData.value?.nodes || [];
  return nodes.find((node) => node.id === selectedKnowledgeNodeId.value)
    || nodes.find((node) => node.avg_mastery != null)
    || nodes[0]
    || null;
});

const knowledgeCoverage = computed(() => {
  const nodes = knowledgeMapData.value?.nodes || [];
  const tracked = nodes.filter((node) => node.avg_mastery != null).length;
  return {
    tracked,
    total: nodes.length,
    ratio: nodes.length ? Math.round((tracked / nodes.length) * 100) : 0,
    edges: knowledgeMapData.value?.edges.length || 0,
  };
});

interface KnowledgeGraphNodeView extends KnowledgeMapNode {
  x: number;
  y: number;
  width: number;
  height: number;
  stage: number;
  color: string;
}

interface KnowledgeGraphEdgeView {
  key: string;
  path: string;
  relation: string;
  weight: number;
}

const knowledgeStageNames = ["基础认知", "核心方法", "模型学习", "系统进阶", "综合应用"];

type KnowledgeViewMode = "focus" | "full";
type KnowledgeRelationFilter = "prerequisite" | "all";

const knowledgeQuery = ref("");
const knowledgeStageFilter = ref("all");
const knowledgeViewMode = ref<KnowledgeViewMode>("focus");
const knowledgeRelationFilter = ref<KnowledgeRelationFilter>("prerequisite");
const knowledgeZoom = ref(1);

const bloomStage: Record<string, number> = {
  remember: 0, remembering: 0, understand: 1, understanding: 1,
  apply: 2, applying: 2, analyze: 3, analyzing: 3,
  evaluate: 4, evaluating: 4, create: 4, creating: 4,
};
const difficultyStage: Record<string, number> = {
  basic: 0, beginner: 0, easy: 0,
  intermediate: 2, medium: 2,
  advanced: 4, hard: 4,
};

const knowledgeNodeStages = computed(() => {
  const nodes = knowledgeMapData.value?.nodes || [];
  const ids = new Set(nodes.map((node) => node.id));
  const edges = (knowledgeMapData.value?.edges || []).filter((edge) =>
    ids.has(edge.source) && ids.has(edge.target) && String(edge.relation_type).toLowerCase() === "prerequisite",
  );
  const stages = new Map<string, number>();
  nodes.forEach((node, index) => {
    const bloom = bloomStage[String(node.bloom_level || "").toLowerCase()];
    const difficulty = difficultyStage[String(node.difficulty || "").toLowerCase()];
    stages.set(node.id, bloom ?? difficulty ?? Math.min(4, Math.floor(index / 10)));
  });
  for (let pass = 0; pass < 4; pass += 1) {
    edges.forEach((edge) => {
      const sourceStage = stages.get(edge.source) || 0;
      const targetStage = stages.get(edge.target) || 0;
      if (targetStage <= sourceStage) stages.set(edge.target, Math.min(4, sourceStage + 1));
    });
  }
  return stages;
});

const filteredKnowledgeNodes = computed(() => {
  const query = knowledgeQuery.value.trim().toLowerCase();
  let nodes = [...(knowledgeMapData.value?.nodes || [])];
  if (query) {
    nodes = nodes.filter((node) =>
      `${node.name} ${node.id} ${node.description}`.toLowerCase().includes(query),
    );
  }
  if (knowledgeStageFilter.value !== "all") {
    const stage = Number(knowledgeStageFilter.value);
    nodes = nodes.filter((node) => knowledgeNodeStages.value.get(node.id) === stage);
  }
  if (knowledgeViewMode.value === "focus" && !query && knowledgeStageFilter.value === "all") {
    return nodes.sort((a, b) => knowledgePriorityScore(b) - knowledgePriorityScore(a)).slice(0, 16);
  }
  return nodes;
});

function setKnowledgeZoom(next: number) {
  knowledgeZoom.value = Math.max(0.75, Math.min(1.6, Number(next.toFixed(2))));
}

function resetKnowledgeViewport() {
  knowledgeQuery.value = "";
  knowledgeStageFilter.value = "all";
  knowledgeRelationFilter.value = "prerequisite";
  knowledgeViewMode.value = "focus";
  knowledgeZoom.value = 1;
}

const bloomLevelLabel: Record<string, string> = {
  remember: "记忆", remembering: "记忆", understand: "理解", understanding: "理解",
  apply: "应用", applying: "应用", analyze: "分析", analyzing: "分析",
  evaluate: "评价", evaluating: "评价", create: "创造", creating: "创造",
};
const difficultyLabel: Record<string, string> = {
  basic: "基础", beginner: "入门", easy: "基础",
  intermediate: "进阶", medium: "进阶", advanced: "高阶", hard: "高阶",
};

function readableBloomLevel(value: string): string {
  return bloomLevelLabel[String(value || "").toLowerCase()] || value || "待标注";
}

function readableDifficulty(value: string): string {
  return difficultyLabel[String(value || "").toLowerCase()] || value || "待标注";
}

const knowledgeGraphView = computed(() => {
  const sourceNodes = filteredKnowledgeNodes.value;
  const ids = new Set(sourceNodes.map((node) => node.id));
  const sourceEdges = (knowledgeMapData.value?.edges || []).filter((edge) =>
    ids.has(edge.source)
    && ids.has(edge.target)
    && (knowledgeRelationFilter.value === "all" || String(edge.relation_type).toLowerCase() === "prerequisite"),
  );

  const groups = Array.from({ length: 5 }, () => [] as KnowledgeMapNode[]);
  sourceNodes.forEach((node) => groups[knowledgeNodeStages.value.get(node.id) || 0].push(node));
  const width = 1220;
  const nodeWidth = 196;
  const nodeHeight = 66;
  const marginX = 36;
  const columnGap = (width - marginX * 2 - nodeWidth) / 4;
  const maxRows = Math.max(1, ...groups.map((group) => group.length));

  /* Layout math（修复底部裁剪）：
   * 布局参数：topMargin=52（含 stage label 空间）· bottomMargin=24 · nodeHeight=66
   * 需保证：52 + rowGap*(N-1) + 66 <= height，即 rowGap*(N-1) <= height - 118 - 24
   * height = topMargin + bottomMargin + rowMinSpan*(N-1) + nodeHeight
   *        = 52 + 24 + 90*(N-1) + 66  = 142 + 90*(N-1)
   * 保底 540 保证 5 行以内都有足够呼吸
   */
  const topMargin = 52;
  const bottomMargin = 24;
  const rowMinSpan = 90;
  const height = Math.max(540, topMargin + bottomMargin + nodeHeight + rowMinSpan * Math.max(0, maxRows - 1));
  const nodes: KnowledgeGraphNodeView[] = [];
  groups.forEach((group, stage) => {
    // 可用垂直空间 = height - topMargin - bottomMargin - nodeHeight（保留最后一行不贴底）
    const usableHeight = height - topMargin - bottomMargin - nodeHeight;
    const rowGap = group.length <= 1 ? 0 : usableHeight / (group.length - 1);
    group.forEach((node, row) => {
      nodes.push({
        ...node,
        stage,
        x: marginX + stage * columnGap,
        y: group.length <= 1 ? height / 2 - nodeHeight / 2 : topMargin + row * rowGap,
        width: nodeWidth,
        height: nodeHeight,
        color: masteryColor(node.avg_mastery),
      });
    });
  });
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const edges: KnowledgeGraphEdgeView[] = sourceEdges.flatMap((edge, index) => {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) return [];
    const x1 = source.x + source.width;
    const y1 = source.y + source.height / 2;
    const x2 = target.x;
    const y2 = target.y + target.height / 2;
    const bend = Math.max(42, Math.abs(x2 - x1) * 0.42);
    const relationShift = String(edge.relation_type).toLowerCase() === "prerequisite" ? 0 : (index % 2 ? 18 : -18);
    return [{
      key: `${edge.source}-${edge.target}-${index}`,
      path: `M${x1},${y1} C${x1 + bend},${y1 + relationShift} ${x2 - bend},${y2 + relationShift} ${x2},${y2}`,
      relation: edge.relation_type,
      weight: edge.weight,
    }];
  });
  const stageLabels = knowledgeStageNames.map((label, stage) => ({
    label,
    x: marginX + stage * columnGap + nodeWidth / 2,
  }));
  return { nodes, edges, width, height, viewBox: `0 0 ${width} ${height}`, stageLabels };
});

function truncateKnowledgeName(name: string): string {
  return name.length > 16 ? `${name.slice(0, 15)}…` : name;
}

function knowledgeNodeStatus(node: KnowledgeMapNode): string {
  if (node.avg_mastery == null) return "待采集";
  if (node.avg_mastery < 0.4) return "重点补强";
  if (node.avg_mastery < 0.6) return "需要关注";
  if (node.avg_mastery < 0.8) return "基本掌握";
  return "掌握良好";
}

function masteryColor(mastery: number | null): string {
  if (mastery == null) return "#e5e7eb";
  if (mastery < 0.3) return "#ef4444";
  if (mastery < 0.5) return "#f97316";
  if (mastery < 0.7) return "#eab308";
  if (mastery < 0.85) return "#84cc16";
  return "#22c55e";
}

// ================= 增强 3：学生对比分析 =================
const compareResult = ref<CompareResult | null>(null);
const compareLoading = ref(false);
const compareSelectedIds = ref<string[]>([]);

function toggleCompareStudent(uid: string) {
  const idx = compareSelectedIds.value.indexOf(uid);
  if (idx >= 0) {
    compareSelectedIds.value.splice(idx, 1);
  } else if (compareSelectedIds.value.length < 6) {
    compareSelectedIds.value.push(uid);
  } else {
    showNotice("最多对比 6 位学生");
  }
}

async function loadCompare() {
  if (!students.value.length) await loadStudents();
  if (compareSelectedIds.value.length >= 2) {
    compareLoading.value = true;
    try {
      compareResult.value = await compareStudents(compareSelectedIds.value, teacherCourse.value);
    } catch (e: any) {
      showNotice(`对比分析失败：${e?.detail || e?.message || e}`);
    } finally {
      compareLoading.value = false;
    }
  }
}

// deep: true 关键——compareSelectedIds 是 ref<string[]>，toggleCompareStudent
// 用 splice/push 做 in-place 变更，普通 watch(ref) 不会响应，必须 deep 才触发。
watch(compareSelectedIds, () => {
  if (compareSelectedIds.value.length >= 2) {
    void loadCompare();
  } else {
    compareResult.value = null;
  }
}, { deep: true });

// ================= 增强 4：班级学情报告导出 =================
const exportLoading = ref(false);

async function downloadClassReport() {
  exportLoading.value = true;
  try {
    const blob = await exportClassReport({ course: teacherCourse.value, days: 30 });
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `class_report_${teacherCourse.value}.md`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 0);
    showNotice("班级学情报告已下载");
  } catch (e: any) {
    showNotice(`导出失败：${e?.detail || e?.message || e}`);
  } finally {
    exportLoading.value = false;
  }
}

// ================= 增强 5：错题批量处理 =================
const selectedMistakeIds = ref<Set<string>>(new Set());
const batchResolveLoading = ref(false);

function toggleMistakeSelection(id: string) {
  if (selectedMistakeIds.value.has(id)) {
    selectedMistakeIds.value.delete(id);
  } else {
    selectedMistakeIds.value.add(id);
  }
  selectedMistakeIds.value = new Set(selectedMistakeIds.value);
}

function toggleAllMistakes() {
  const mistakes = summary.value?.mistakes?.recent || [];
  if (mistakes.length && selectedMistakeIds.value.size === mistakes.length) {
    selectedMistakeIds.value = new Set();
  } else {
    selectedMistakeIds.value = new Set(mistakes.map((m) => m.id));
  }
}

async function submitBatchResolve(action: "resolve" | "unresolve") {
  const ids = Array.from(selectedMistakeIds.value);
  if (!ids.length) {
    showNotice("请先勾选要处理的错题");
    return;
  }
  batchResolveLoading.value = true;
  try {
    const r = await batchResolveMistakes({ mistake_ids: ids, action });
    showNotice(`${r.action_label} ${r.changed} 道错题（跳过 ${r.skipped} 道）`);
    selectedMistakeIds.value = new Set();
    await loadSummary();
  } catch (e: any) {
    showNotice(`批量处理失败：${e?.detail || e?.message || e}`);
  } finally {
    batchResolveLoading.value = false;
  }
}

watch(
  teacherSection,
  (section) => {
    activeTab.value = sectionConfig[section].tabs[0];
    loadSectionData(section);
  },
  { immediate: true },
);

// 切换课程后按新课程重新加载当前分区的真实数据
function onCourseChange(event: Event) {
  setCourse((event.target as HTMLSelectElement).value);
}
watch(teacherCourse, () => {
  loadSectionData(teacherSection.value);
});

onMounted(() => {
  loadCourseOptions();
  applyTeacherRouteQuery();
});

// ============================================================
// AI 教学工作台 v3 · 内置 6 Agent 团队常量
// 与 backend/app/agents/orchestrator.py 的 PARTNER_TO_AGENT 一一对应
// ============================================================
interface TeacherAgent {
  key: string;
  name: string;
  role: string;
  avatar: string;
  color: string;
  soft: string;
  desc: string;
}
const TEACHER_AGENTS: TeacherAgent[] = [
  { key: "planner",    name: "智狐", role: "学习规划师", avatar: "/avatars/zhihu.png",    color: "#ea5a1a", soft: "#FFF3E8", desc: "路径规划、教学步骤设计" },
  { key: "tutor",      name: "智灵", role: "知识讲师",   avatar: "/avatars/zhiling.png",  color: "#2f9f6b", soft: "#ECFDF3", desc: "知识点讲解、易混辨析" },
  { key: "content",    name: "阿匠", role: "内容工匠",   avatar: "/avatars/ajiang.png",   color: "#d89229", soft: "#FEF7E6", desc: "文档/PPT/导读生成" },
  { key: "quiz",       name: "小龙", role: "小龙挑战",   avatar: "/avatars/xiaolong.png", color: "#8f5b32", soft: "#FBF4EA", desc: "练习题与分层题包" },
  { key: "evaluation", name: "团团", role: "熊猫评分",   avatar: "/avatars/tuantuan.png", color: "#4a8c78", soft: "#ECFDF3", desc: "学情评估与干预建议" },
  { key: "safety",     name: "球球", role: "刺猬守护",   avatar: "/avatars/qiuqiu.png",   color: "#3b7f88", soft: "#EEF7F9", desc: "教学边界与内容安全" },
];

function findTeacherAgent(nameOrKey: string): TeacherAgent | undefined {
  const s = String(nameOrKey || "").toLowerCase();
  return TEACHER_AGENTS.find((a) => a.key === s || a.name === nameOrKey || nameOrKey.includes(a.name));
}

// ============================================================
// AI Copilot Panel · 消息流 + 6 agent 状态 + 真实 API 对接
// 对接：POST /api/v1/teacher/copilot/consult（consultTeachingCopilot）
// ============================================================
interface CopilotChatMessage {
  id: string;
  role: "ai" | "teacher";
  content: string;
  agents_invoked?: Array<{ name: string; success: boolean }>;
  primary_agent?: string;
  safety_level?: string;
  action_label?: string;
  timestamp: number;
  loading?: boolean;
  activeAgent?: string;  // 当前正在运行的 agent（UI 阶段指示）
  stage?: string;        // "调用 智狐" / "生成中" 等
}

const copilotOpen = ref(true);
const copilotInput = ref("");
const copilotAsking = ref(false);
const copilotMessages = ref<CopilotChatMessage[]>([]);
const copilotSuggestions = [
  { icon: "route", label: "为薄弱知识点生成分层练习", instruction: "针对当前班级最薄弱的知识点，生成基础/提升/拓展 3 级分层练习" },
  { icon: "target", label: "创建 15 分钟课堂补强任务", instruction: "为班级设计一个 15 分钟课堂补强环节，含讲解要点、即时练习、反馈机制" },
  { icon: "users", label: "为高风险学生生成个性化计划", instruction: "为班级高风险学生生成个性化学习计划与目标" },
  { icon: "chart", label: "分析本周作业错误原因", instruction: "分析本周班级作业的主要错误类型与知识关联，给出补救建议" },
  { icon: "sparkles", label: "生成本周教学计划", instruction: "基于当前班级学情，生成下一周的教学计划（每天主题+目标+资源）" },
];

/** 初始欢迎消息：由现有 classPriorityActions 派生 */
function initCopilotWelcome() {
  if (copilotMessages.value.length) return;
  const actions = classPriorityActions.value;
  const summary = actions.length
    ? actions.map((a, i) => `${i + 1}. ${a.title} —— ${a.detail}`).join("\n")
    : "当前班级证据积累中，暂无优先建议。";
  copilotMessages.value.push({
    id: `ai-welcome-${Date.now()}`,
    role: "ai",
    content: `${teacherName.value}，基于最新学情，我为您准备了以下建议：\n\n${summary}\n\n点击下方推荐 Card 或输入问题继续。`,
    timestamp: Date.now(),
    agents_invoked: [
      { name: "团团", success: true },
      { name: "智狐", success: true },
    ],
  });
}

async function askCopilot(prompt?: string) {
  const text = String(prompt ?? copilotInput.value).trim();
  if (!text || copilotAsking.value) return;

  // 1. 学生消息入列
  copilotMessages.value.push({
    id: `teacher-${Date.now()}`,
    role: "teacher",
    content: text,
    timestamp: Date.now(),
  });
  copilotInput.value = "";
  copilotAsking.value = true;

  // 2. 插入一个 loading 消息，逐步切换 activeAgent 显示"正在调用某某"
  const loadingMsg: CopilotChatMessage = {
    id: `ai-${Date.now()}`,
    role: "ai",
    content: "",
    loading: true,
    activeAgent: "团团",
    stage: "正在解析教学问题…",
    timestamp: Date.now(),
  };
  copilotMessages.value.push(loadingMsg);

  // UI 阶段推进（不改变 API，仅指示当前 agent）
  const stages = [
    { agent: "团团", stage: "解析教学问题与学情证据…" },
    { agent: "智狐", stage: "规划应对策略与教学步骤…" },
    { agent: "阿匠", stage: "整合可用资源与文档…" },
  ];
  let stageIdx = 0;
  const stageTimer = window.setInterval(() => {
    stageIdx += 1;
    if (stageIdx < stages.length) {
      const target = copilotMessages.value.find((m) => m.id === loadingMsg.id);
      if (target) {
        target.activeAgent = stages[stageIdx].agent;
        target.stage = stages[stageIdx].stage;
      }
    }
  }, 1200);

  try {
    // 3. 真实 API 调用
    const result = await consultTeachingCopilot({
      action: "class_diagnosis",
      scope: "class",
      course: teacherCourse.value,
      instruction: text,
    });
    window.clearInterval(stageTimer);
    const target = copilotMessages.value.find((m) => m.id === loadingMsg.id);
    if (target) {
      target.loading = false;
      target.activeAgent = undefined;
      target.stage = undefined;
      target.content = result?.content || result?.error || "本次未生成正文。";
      target.agents_invoked = result?.agents_invoked || [];
      target.primary_agent = result?.primary_agent;
      target.safety_level = result?.safety?.level;
      target.action_label = result?.action_label;
    }
  } catch (err: any) {
    window.clearInterval(stageTimer);
    const target = copilotMessages.value.find((m) => m.id === loadingMsg.id);
    if (target) {
      target.loading = false;
      target.activeAgent = undefined;
      target.stage = undefined;
      target.content = `Copilot 调用失败：${err?.detail ?? err?.message ?? err}`;
    }
  } finally {
    copilotAsking.value = false;
  }
}

function clearCopilot() {
  copilotMessages.value = [];
  initCopilotWelcome();
}

// ============================================================
// 遗忘曲线 · Forecast Chart（ECharts）· insights tab
// 数据源：/api/v1/cognitive/forecast，forecast[] 30 天 mastery 预测 + 置信区间
// ============================================================
const forecastChartEl = ref<HTMLDivElement | null>(null);
let forecastChart: any = null;

function renderForecastChart() {
  if (!forecastChartEl.value) return;
  const points = forecastCurve.value;
  if (!points.length) return;
  import("echarts").then((echarts) => {
    if (!forecastChartEl.value) return;
    if (!forecastChart) forecastChart = echarts.init(forecastChartEl.value);
    const days = points.map((p) => `+${p.day} 天`);
    const masteryPct = points.map((p) => Math.round(p.mastery * 100));
    const ciLowPct = points.map((p) => Math.round(p.ciLow * 100));
    const ciHighPct = points.map((p) => Math.round(p.ciHigh * 100));
    // 置信区间用堆叠面积 + 透明底 + 半透明上带
    const ciBand = ciHighPct.map((h, i) => h - ciLowPct[i]);

    const milestoneMarks = forecastMilestones.value.map((m) => ({
      name: m.label,
      xAxis: `+${m.day} 天`,
      yAxis: Math.round(m.mastery * 100),
      itemStyle: { color: "#F97316" },
    }));

    forecastChart.setOption({
      backgroundColor: "transparent",
      grid: { top: 40, right: 24, bottom: 44, left: 44, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(26, 29, 33, 0.94)",
        borderWidth: 0,
        padding: [10, 14],
        textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" },
        formatter: (params: any[]) => {
          const day = params[0]?.axisValue || "";
          const p = params.find((x) => x.seriesName === "掌握度预测");
          const low = ciLowPct[params[0]?.dataIndex ?? 0];
          const high = ciHighPct[params[0]?.dataIndex ?? 0];
          return `<div style="font-size:11px;color:#c9c9c9;margin-bottom:6px;">距今 ${day}</div>
            <div style="display:flex;justify-content:space-between;gap:16px;">
              <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p?.color};margin-right:6px;"></span>预测掌握度</span>
              <b style="color:#fff;">${p?.value}%</b>
            </div>
            <div style="font-size:11px;color:#c9c9c9;margin-top:4px;">
              95% 置信区间 <b style="color:#fff;">${low}% - ${high}%</b>
            </div>`;
        },
      },
      xAxis: {
        type: "category",
        data: days,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#e8e4dc" } },
        axisTick: { show: false },
        axisLabel: { color: "#6b7480", fontSize: 11, interval: Math.floor(days.length / 6) || 0 },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { lineStyle: { color: "#f0eae0", type: "dashed" } },
        axisLabel: { color: "#98a1ab", fontSize: 11, formatter: "{value}%" },
      },
      series: [
        // 置信区间下界（透明）
        {
          name: "CI Low",
          type: "line",
          data: ciLowPct,
          lineStyle: { opacity: 0 },
          stack: "ci",
          symbol: "none",
          silent: true,
        },
        // 置信区间上界（stacked，展示为面积带）
        {
          name: "CI Band",
          type: "line",
          data: ciBand,
          lineStyle: { opacity: 0 },
          areaStyle: { color: "rgba(249, 115, 22, 0.14)" },
          stack: "ci",
          symbol: "none",
          silent: true,
        },
        // 主预测线
        {
          name: "掌握度预测",
          type: "line",
          data: masteryPct,
          smooth: true,
          symbol: "circle",
          symbolSize: 4,
          showSymbol: false,
          lineStyle: { color: "#F97316", width: 2.6 },
          itemStyle: { color: "#F97316", borderColor: "#fff", borderWidth: 2 },
          areaStyle: {
            opacity: 0.10,
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(249, 115, 22, 0.32)" },
                { offset: 1, color: "rgba(249, 115, 22, 0)" },
              ],
            },
          },
          markPoint: milestoneMarks.length
            ? {
                symbol: "pin",
                symbolSize: 42,
                label: { color: "#fff", fontSize: 10, fontWeight: 700 },
                data: milestoneMarks,
              }
            : undefined,
          markLine: forecastCurrent.value != null
            ? {
                silent: true,
                symbol: "none",
                lineStyle: { color: "#6b7480", type: "dashed", width: 1 },
                label: { color: "#6b7480", fontSize: 10, formatter: "现状" },
                data: [{ yAxis: Math.round(forecastCurrent.value * 100) }],
              }
            : undefined,
        },
      ],
    }, true);
    forecastChart.resize();
  });
}

// ============================================================
// 掌握度分布 · Donut Chart（ECharts）
// ============================================================
const masteryDonutEl = ref<HTMLDivElement | null>(null);
let masteryDonutChart: any = null;

function renderMasteryDonut() {
  if (!masteryDonutEl.value) return;
  const rows = masteryDistributionView.value;
  if (!rows.length) return;
  import("echarts").then((echarts) => {
    if (!masteryDonutEl.value) return;
    if (!masteryDonutChart) masteryDonutChart = echarts.init(masteryDonutEl.value);
    const total = rows.reduce((s, r) => s + r.count, 0);
    const bucketLabels: Record<string, string> = {
      "80-100": "优秀 (80-100%)", "60-80": "良好 (60-80%)",
      "40-60": "中等 (40-60%)", "20-40": "待提升 (20-40%)", "0-20": "薄弱 (0-20%)",
    };
    const palette: Record<string, string> = {
      "80-100": "#16A34A", "60-80": "#84CC16",
      "40-60": "#F59E0B", "20-40": "#F97316", "0-20": "#DC2626",
    };
    masteryDonutChart.setOption({
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(26, 29, 33, 0.94)",
        borderWidth: 0,
        textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" },
        formatter: (p: any) => `<b style="color:#fff;">${p.name}</b><br/>${p.value} 人 · ${p.percent}%`,
      },
      legend: { show: false },
      series: [{
        type: "pie",
        radius: ["58%", "82%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: "#fff",
          borderWidth: 3,
        },
        emphasis: {
          scale: true,
          scaleSize: 6,
          itemStyle: { shadowBlur: 12, shadowColor: "rgba(249, 115, 22, 0.35)" },
        },
        data: rows.map((r) => ({
          name: bucketLabels[r.bucket] || `${r.bucket}%`,
          value: r.count,
          itemStyle: { color: palette[r.bucket] || "#9CA3AF" },
        })),
      }],
      graphic: [{
        type: "group",
        left: "center", top: "center",
        children: [
          { type: "text", top: -14, style: { text: `${classAvgMastery.value}%`, textAlign: "center", fill: "#181C21", font: "bold 32px inherit" } },
          { type: "text", top: 22, style: { text: "整体掌握度", textAlign: "center", fill: "#6B7480", font: "12px inherit" } },
        ],
      }],
    }, true);
    masteryDonutChart.resize();
  });
}

// ============================================================
// 错误原因分布 · Donut Chart（ECharts）
// ============================================================
const errorDonutEl = ref<HTMLDivElement | null>(null);
let errorDonutChart: any = null;

function renderErrorDonut() {
  if (!errorDonutEl.value) return;
  const rows = errorDistributionView.value;
  if (!rows.length) return;
  import("echarts").then((echarts) => {
    if (!errorDonutEl.value) return;
    if (!errorDonutChart) errorDonutChart = echarts.init(errorDonutEl.value);
    errorDonutChart.setOption({
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(26, 29, 33, 0.94)",
        borderWidth: 0,
        textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" },
        formatter: (p: any) => `<b style="color:#fff;">${readableMistakeType(p.name)}</b><br/>${p.value} 道 · ${p.percent}%`,
      },
      series: [{
        type: "pie",
        radius: ["58%", "82%"],
        center: ["50%", "50%"],
        label: { show: false },
        labelLine: { show: false },
        itemStyle: { borderColor: "#fff", borderWidth: 3 },
        emphasis: { scale: true, scaleSize: 6, itemStyle: { shadowBlur: 12, shadowColor: "rgba(249, 115, 22, 0.35)" } },
        data: rows.map((r) => ({
          name: r.category,
          value: r.count,
          itemStyle: { color: r.color },
        })),
      }],
      graphic: [{
        type: "group",
        left: "center", top: "center",
        children: [
          { type: "text", top: -14, style: { text: `${errorTotal.value}`, textAlign: "center", fill: "#181C21", font: "bold 32px inherit" } },
          { type: "text", top: 22, style: { text: "未解决错题", textAlign: "center", fill: "#6B7480", font: "12px inherit" } },
        ],
      }],
    }, true);
    errorDonutChart.resize();
  });
}

// ============================================================
// 时间维度 · ECharts 双轴组合图（柱=活动次数，折线=日均得分）
// ============================================================
const teacherTrendChartEl = ref<HTMLDivElement | null>(null);
let teacherTrendChart: any = null;

function renderTeacherTrendChart() {
  if (!teacherTrendChartEl.value) return;
  const rows = classData.value?.mastery.trend?.slice(-30) || [];
  if (!rows.length) return;

  // 惰性引入 echarts，避免与其他视图未激活时的初始化冲突
  import("echarts").then((echarts) => {
    if (!teacherTrendChartEl.value) return;
    if (!teacherTrendChart) {
      teacherTrendChart = echarts.init(teacherTrendChartEl.value);
    }
    const dates = rows.map((r) => r.date.slice(5));
    const activities = rows.map((r) => Number(r.activity_count || 0));
    const scores = rows.map((r) => Math.round(Number(r.avg_score || 0) * 100));
    const maxActivity = Math.max(1, ...activities);

    teacherTrendChart.setOption({
      backgroundColor: "transparent",
      grid: { top: 44, right: 56, bottom: 40, left: 48, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(26, 29, 33, 0.94)",
        borderWidth: 0,
        padding: [10, 14],
        textStyle: { color: "#fff", fontSize: 12, fontFamily: "inherit" },
        axisPointer: { type: "cross", crossStyle: { color: "#d9480f", opacity: 0.35 } },
        formatter: (params: any[]) => {
          const date = params[0]?.axisValue || "";
          const rowsHtml = params
            .map((p) => {
              const unit = p.seriesName === "活动次数" ? "次" : "分";
              const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${p.color};margin-right:6px;vertical-align:middle;"></span>`;
              return `<div style="display:flex;justify-content:space-between;gap:16px;">
                <span>${dot}${p.seriesName}</span>
                <b style="color:#fff;">${p.value} ${unit}</b>
              </div>`;
            })
            .join("");
          return `<div style="font-size:11px;color:#c9c9c9;margin-bottom:6px;">${date}</div>${rowsHtml}`;
        },
      },
      legend: {
        top: 6,
        right: 16,
        itemWidth: 12,
        itemHeight: 10,
        itemGap: 20,
        icon: "roundRect",
        textStyle: { color: "#45505c", fontSize: 12, fontFamily: "inherit" },
        data: ["活动次数", "日均得分"],
      },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: "#e8e4dc" } },
        axisTick: { show: false },
        axisLabel: { color: "#6b7480", fontSize: 11, interval: Math.floor(dates.length / 8), margin: 12 },
      },
      yAxis: [
        {
          type: "value",
          name: "活动次数",
          position: "left",
          max: Math.ceil(maxActivity * 1.15),
          nameTextStyle: { color: "#6b7480", fontSize: 11, padding: [0, 0, 8, -8] },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: "#f0eae0", type: "dashed" } },
          axisLabel: { color: "#98a1ab", fontSize: 11 },
        },
        {
          type: "value",
          name: "日均得分",
          position: "right",
          min: 0,
          max: 100,
          nameTextStyle: { color: "#6b7480", fontSize: 11, padding: [0, -8, 8, 0] },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { color: "#98a1ab", fontSize: 11, formatter: "{value}" },
        },
      ],
      series: [
        {
          name: "活动次数",
          type: "bar",
          yAxisIndex: 0,
          barMaxWidth: 22,
          barCategoryGap: "42%",
          itemStyle: {
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "#f0863d" },
                { offset: 1, color: "#d9480f" },
              ],
            },
            borderRadius: [6, 6, 0, 0],
          },
          emphasis: { itemStyle: { color: "#c8480f" } },
          data: activities,
        },
        {
          name: "日均得分",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          showSymbol: false,
          lineStyle: { width: 2.5, color: "#2f8f5b" },
          itemStyle: { color: "#2f8f5b", borderColor: "#fff", borderWidth: 2 },
          areaStyle: {
            opacity: 0.15,
            color: {
              type: "linear",
              x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(47, 143, 91, 0.35)" },
                { offset: 1, color: "rgba(47, 143, 91, 0)" },
              ],
            },
          },
          emphasis: { lineStyle: { width: 3 }, itemStyle: { color: "#1f6b47" } },
          data: scores,
        },
      ],
    }, true);
    teacherTrendChart.resize();
  });
}

function handleTeacherTrendResize() {
  teacherTrendChart?.resize();
}

watch(
  () => classData.value?.mastery.trend,
  () => {
    if (activeTab.value === "board") {
      // DOM 需要一个 tick 才能渲染出容器
      setTimeout(renderTeacherTrendChart, 40);
    }
  },
  { deep: true },
);

watch(activeTab, (tab) => {
  if (tab === "board" && classData.value?.mastery.trend?.length) {
    setTimeout(renderTeacherTrendChart, 40);
    setTimeout(renderMasteryDonut, 40);
    setTimeout(renderErrorDonut, 40);
  }
});

// 掌握度分布 / 错因分布 数据变化时重绘
watch(masteryDistributionView, () => {
  if (activeTab.value === "board") setTimeout(renderMasteryDonut, 40);
}, { deep: true });
watch(errorDistributionView, () => {
  if (activeTab.value === "board") setTimeout(renderErrorDonut, 40);
}, { deep: true });

// classData 就绪后初始化 Copilot 欢迎语
watch(classData, (val) => {
  if (val && !copilotMessages.value.length) {
    setTimeout(initCopilotWelcome, 50);
  }
});

function handleBoardResize() {
  teacherTrendChart?.resize();
  masteryDonutChart?.resize();
  errorDonutChart?.resize();
  forecastChart?.resize();
}

// insights tab 激活时 & 学生变化时重绘遗忘曲线
watch(activeTab, (tab) => {
  if (tab === "insights" && forecastCurve.value.length) {
    setTimeout(renderForecastChart, 40);
  }
});
watch(selectedStudentId, () => {
  if (activeTab.value === "insights") {
    setTimeout(renderForecastChart, 60);
  }
});

onMounted(() => {
  window.addEventListener("resize", handleBoardResize);
  if (activeTab.value === "board" && classData.value?.mastery.trend?.length) {
    setTimeout(renderTeacherTrendChart, 40);
    setTimeout(renderMasteryDonut, 40);
    setTimeout(renderErrorDonut, 40);
  }
  if (classData.value && !copilotMessages.value.length) {
    setTimeout(initCopilotWelcome, 50);
  }
});

onBeforeUnmount(() => {
  closeVideoPreview();
  window.removeEventListener("resize", handleBoardResize);
  teacherTrendChart?.dispose();
  masteryDonutChart?.dispose();
  errorDonutChart?.dispose();
  forecastChart?.dispose();
  teacherTrendChart = null;
  masteryDonutChart = null;
  errorDonutChart = null;
  forecastChart = null;
});
</script>

<template>
  <div :class="['teacher-view', `teacher-section-${teacherSection}`]">
    <!-- App Bar：编辑式页头，无 Eyebrow · 标题直接放在页面背景上 -->
    <header class="teacher-appbar">
      <div class="teacher-appbar-main">
        <div class="teacher-appbar-title">
          <h1>{{ currentSection.title }}</h1>
          <p>{{ currentSection.description }}</p>
        </div>
        <button
          type="button"
          class="appbar-action"
          :title="'刷新本页数据'"
          @click="loadSectionData(teacherSection)"
        >
          <RefreshCcw :size="15" />
          <span>刷新本页</span>
        </button>
      </div>
      <div class="teacher-command-context" aria-label="当前教学工作上下文">
        <span>
          <small>课程</small>
          <select
            class="context-course-select"
            :value="teacherCourse"
            aria-label="切换教学课程"
            @change="onCourseChange"
          >
            <option v-for="c in courseOptions" :key="c" :value="c">{{ courseLabelOf(c) }}</option>
          </select>
        </span>
        <span><small>工作模式</small><b>教师决策端</b></span>
        <span><small>Agent 协作</small><b>6 个角色已接入</b></span>
        <span><small>数据范围</small><b>{{ classData ? `${classData.student_count} 名学生` : '当前课程' }}</b></span>
      </div>
    </header>

    <!-- MD3 Primary Tab：底部 3px 品牌下划线 + 44px 触控 + state layer hover -->
    <nav v-if="visibleTabs.length > 1" class="teacher-tabs" role="tablist" aria-label="教师工作分区">
      <button
        v-for="tab in visibleTabs"
        :key="tab.key"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        <span class="tab-inner">
          <component :is="tab.icon" :size="16" />
          <span>{{ tab.label }}</span>
        </span>
        <span class="tab-indicator" aria-hidden="true"></span>
      </button>
    </nav>

    <!-- 学生选择条（学情/数据分析/路径/群聊页签共用）· sticky 玻璃条 -->
    <div
      v-if="activeTab === 'analysis' || activeTab === 'insights' || activeTab === 'paths' || activeTab === 'chat'"
      class="student-bar"
    >
      <span class="student-bar-icon"><Users :size="14" /></span>
      <span class="student-bar-label">当前学生</span>
      <select v-model="selectedStudentId" class="student-bar-select">
        <option v-for="s in students" :key="s.user_id" :value="s.user_id">
          {{ s.display_name }}（掌握度 {{ s.mastery_avg == null ? "—" : Math.round(s.mastery_avg * 100) + "%" }} · 待解错题 {{ s.mistakes_open }}）
        </option>
      </select>
      <em v-if="studentsLoading" class="student-bar-loading"><Loader2 :size="13" class="spin" /> 加载中</em>
    </div>

    <!-- ===================== 教学共创：数据快照驱动的 Agent 协作 ===================== -->
    <section v-if="activeTab === 'copilot'" class="tab-panel copilot-panel">
      <div class="copilot-intro">
        <div>
          <h2>教学共创</h2>
          <p>系统会先抽取本次教学所需的最小数据快照，再交给现有 Agent 协作生成建议；生成内容不会自动发布或推送。</p>
        </div>
        <button type="button" class="ghost-btn" @click="loadClassAnalytics"><RefreshCcw :size="14" /> 更新数据</button>
      </div>

      <div class="copilot-actions" role="list" aria-label="选择教学任务">
        <button
          v-for="item in copilotActions"
          :key="item.key"
          type="button"
          :class="['copilot-action', { active: copilotAction === item.key }]"
          role="listitem"
          @click="chooseCopilotAction(item.key)"
        >
          <b>{{ item.label }}</b>
          <span>{{ item.description }}</span>
          <em>{{ item.flow }}</em>
        </button>
      </div>

      <div class="card copilot-workbench">
        <div class="copilot-form-head">
          <div>
            <h3>{{ activeCopilotAction.label }}</h3>
            <p>默认协作链：{{ activeCopilotAction.flow }}。也可指定一个已启用 Agent 单独处理。</p>
          </div>
          <span v-if="classLoading" class="data-status"><Loader2 :size="13" class="spin" /> 正在刷新学情</span>
          <span v-else class="data-status">数据依据：{{ copilotScope === 'class' ? '班级聚合' : selectedStudentId || '未选择学生' }}</span>
        </div>

        <div class="copilot-controls">
          <label>
            数据范围
            <select v-model="copilotScope">
              <option value="class">班级整体</option>
              <option value="student">指定学生</option>
            </select>
          </label>
          <label v-if="copilotScope === 'student'">
            指定学生
            <select v-model="selectedStudentId">
              <option v-for="student in students" :key="student.user_id" :value="student.user_id">{{ student.display_name }}</option>
            </select>
          </label>
          <label>
            协作方式
            <select v-model="copilotAgentKey">
              <option value="">系统多 Agent 协作（推荐）</option>
              <option v-for="agent in agents.filter((item) => item.enabled)" :key="agent.key" :value="agent.key">
                指定 @{{ agent.name }}{{ agent.title ? ` · ${agent.title}` : '' }}
              </option>
            </select>
          </label>
        </div>

        <label class="copilot-instruction">
          教师补充要求 <small>可选，会与数据快照一并提交</small>
          <textarea
            v-model="copilotInstruction"
            rows="3"
            placeholder="例如：优先考虑本周课堂可落地的 20 分钟补强活动；避免新增高负担作业。"
          />
        </label>

        <div class="copilot-submit-row">
          <p>生成内容仅作教学建议，需由教师审核后再保存为草稿、发布资源或推送给学生。</p>
          <button type="button" class="primary-btn" :disabled="copilotLoading" @click="runTeachingCopilot">
            <Loader2 v-if="copilotLoading" :size="14" class="spin" />
            <Sparkles v-else :size="14" />
            {{ copilotLoading ? 'Agent 协作中…' : '生成教学建议' }}
          </button>
        </div>
      </div>

      <div v-if="copilotLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 正在调用现有 Agent 编排、质量复盘与安全校验…</div>
      <div v-else-if="copilotResult" class="card copilot-result">
        <div class="copilot-result-head">
          <div>
            <h3>{{ copilotResult.action_label }}</h3>
            <p>
              {{ copilotResult.scope === 'class' ? '班级整体' : `学生：${copilotResult.student_id}` }}
              · 主响应 {{ copilotResult.primary_agent || 'Agent' }}
              <span v-if="copilotResult.safety"> · 安全校验 {{ copilotResult.safety.level }}</span>
            </p>
          </div>
          <span class="data-status">仅供教师决策，不自动生成或发布学生资料</span>
        </div>
        <div v-if="copilotResult.agents_invoked.length" class="agent-run-list" aria-label="本次已调用 Agent">
          <span v-for="agent in copilotResult.agents_invoked" :key="agent.name" :class="{ failed: !agent.success }">
            {{ agent.name }} · {{ agent.success ? '已完成' : '未完成' }}
          </span>
        </div>
        <MarkdownBlock v-if="copilotResult.content" :content="copilotResult.content" />
        <p v-else class="empty-line">本次未生成可审核正文。{{ copilotResult.error || '请检查模型配置后重试。' }}</p>
      </div>
    </section>

    <!-- ===================== Tab 1 学情分析 ===================== -->
    <section v-if="activeTab === 'analysis'" class="tab-panel">
      <div v-if="summaryLoading" class="panel-loading">
        <Loader2 :size="16" class="spin" /> 正在聚合学情数据...
      </div>
      <template v-else-if="summary">
        <div class="grid-two">
          <div class="card">
            <h3>风险提示</h3>
            <p v-if="!summary.risks.length" class="empty-line">暂无风险，状态良好。</p>
            <ul class="risk-list">
              <li v-for="(r, i) in summary.risks" :key="i" :class="r.level">
                <AlertTriangle :size="14" /> {{ r.message }}
              </li>
            </ul>
          </div>
          <div class="card">
            <h3>掌握度概览 <small v-if="summary.mastery.average != null">平均 {{ Math.round((summary.mastery.average || 0) * 100) }}%</small></h3>
            <p v-if="!summary.mastery.weakest.length" class="empty-line">暂无认知诊断数据（学生做题后生成）。</p>
            <div v-else class="mastery-cols">
              <div>
                <b>最薄弱</b>
                <div v-for="kp in summary.mastery.weakest" :key="kp.kp_id" class="mastery-row">
                  <span>{{ kp.kp_name }}</span>
                  <div class="bar"><i class="low" :style="{ width: `${Math.round(kp.mastery * 100)}%` }" /></div>
                  <em>{{ Math.round(kp.mastery * 100) }}%</em>
                </div>
              </div>
              <div>
                <b>已掌握</b>
                <div v-for="kp in summary.mastery.strongest" :key="kp.kp_id" class="mastery-row">
                  <span>{{ kp.kp_name }}</span>
                  <div class="bar"><i :style="{ width: `${Math.round(kp.mastery * 100)}%` }" /></div>
                  <em>{{ Math.round(kp.mastery * 100) }}%</em>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="grid-two">
          <div class="card profile-panel">
            <h3>学习画像 <small>{{ profileEntries.length ? "根据对话、练习与资源行为整理" : "尚未构建" }}</small></h3>
            <p v-if="!profileEntries.length" class="empty-line">学生尚未通过对话构建画像。</p>
            <div v-else class="profile-facts">
              <article v-for="entry in profileEntries" :key="entry.key" :class="['profile-fact', entry.tone]">
                <span class="profile-fact-label">{{ entry.label }}</span>
                <div>
                  <b>{{ entry.summary }}</b>
                  <div v-if="entry.tags.length" class="profile-tags">
                    <em v-for="tag in entry.tags" :key="tag">{{ tag }}</em>
                  </div>
                </div>
              </article>
            </div>
          </div>
          <div class="card">
            <h3>错题情况 <small>未解决 {{ summary.mistakes.open_count }} 道</small></h3>
            <p v-if="!summary.mistakes.recent.length" class="empty-line">暂无未解决错题。</p>
            <template v-else>
              <div class="batch-ops">
                <label class="switch inline">
                  <input type="checkbox" :checked="summary.mistakes.recent.length > 0 && selectedMistakeIds.size === summary.mistakes.recent.length" @change="toggleAllMistakes" />
                  <span>全选 · 已选 {{ selectedMistakeIds.size }} / {{ summary.mistakes.recent.length }}</span>
                </label>
                <button v-if="selectedMistakeIds.size" type="button" class="ghost-btn" :disabled="batchResolveLoading" @click="submitBatchResolve('resolve')">
                  <CheckCircle :size="13" /> 批量标记已解决
                </button>
              </div>
              <ul class="plain-list">
                <li v-for="m in summary.mistakes.recent" :key="m.id" :class="{ selected: selectedMistakeIds.has(m.id) }">
                  <label class="checkbox-label">
                    <input type="checkbox" :checked="selectedMistakeIds.has(m.id)" @change="toggleMistakeSelection(m.id)" />
                    <em class="chip">{{ readableMistakeType(m.error_type) }}</em>
                    {{ m.question || m.kp_id || m.id }}
                  </label>
                </li>
              </ul>
            </template>
          </div>
        </div>

        <div class="grid-two">
          <div class="card path-usage-panel">
            <h3>学习路径 <small>共 {{ summary.paths.length }} 条</small></h3>
            <p v-if="!summary.paths.length" class="empty-line">暂无路径，可到「路径推荐」页签为其生成。</p>
            <div v-else class="path-compact-list">
              <article v-for="p in summary.paths" :key="p.id" class="path-compact-row">
                <div>
                  <b>{{ p.title }}</b>
                  <span>{{ p.stages_count }} 个阶段 · {{ p.recommended_by ? `${p.recommended_by} 推荐` : "学生自主创建" }}</span>
                </div>
                <div class="path-progress" :style="{ '--progress': `${Math.max(0, Math.min(100, Math.round(p.progress)))}%` }">
                  <b>{{ Math.round(p.progress) }}%</b>
                </div>
              </article>
            </div>
          </div>
          <div class="card resource-usage-panel">
            <h3>资源使用 <small>共 {{ summary.resources.total }} 项</small></h3>
            <p v-if="!summary.resources.recent.length" class="empty-line">该学生名下暂无个人资源。</p>
            <div v-else class="resource-usage-list">
              <article v-for="r in recentResourceViews" :key="r.id" class="resource-usage-row">
                <span class="resource-type-mark">{{ r.typeLabel }}</span>
                <div>
                  <b>{{ r.displayTitle }}</b>
                  <small>{{ r.created_at ? formatTime(r.created_at) : "时间未记录" }}</small>
                </div>
              </article>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- ===================== Tab 1.5 数据分析（每个学生） ===================== -->
    <section v-if="activeTab === 'insights'" class="tab-panel">
      <div v-if="analyticsLoading" class="panel-loading">
        <Loader2 :size="16" class="spin" /> 正在分析 {{ selectedStudentId }} 的学习数据...
      </div>
      <template v-else>
        <div class="grid-two">
          <div class="card">
            <h3>知识点掌握度（BKT 追踪，最薄弱前 12）
              <small v-if="forecastCurrent != null">焦点掌握度 {{ Math.round(forecastCurrent * 100) }}%</small>
            </h3>
            <p v-if="!bktMasteries.length" class="empty-line">该学生暂无做题数据（做题后自动生成 BKT 追踪）。</p>
            <div v-else class="insight-mastery-list">
              <div v-for="row in bktMasteries" :key="row.kp" class="mastery-row">
                <span :title="row.kp">{{ row.kp }}</span>
                <div class="bar">
                  <i :class="{ low: row.mastery < 0.3 }" :style="{ width: `${Math.round(row.mastery * 100)}%` }" />
                </div>
                <em>{{ Math.round(row.mastery * 100) }}% {{ trendLabel(row.trend) }}</em>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>错因热区（错题最多的知识点）
              <small v-if="studentHeatmap">累计 {{ studentHeatmap.total_mistakes }} 道</small>
            </h3>
            <p v-if="!heatmapTopRows.length" class="empty-line">暂无错题分布数据。</p>
            <div v-else class="insight-mastery-list">
              <div v-for="row in heatmapTopRows" :key="row.kp_id" class="mastery-row">
                <span :title="String(row.kp_id)">{{ row.kp_id }}</span>
                <div class="bar">
                  <i class="low" :style="{ width: `${Math.min(100, (Number(row.total) / Math.max(1, Number(heatmapTopRows[0]?.total))) * 100)}%` }" />
                </div>
                <em>{{ row.total }} 道</em>
              </div>
            </div>
          </div>
        </div>

        <div class="grid-two">
          <div class="card forecast-card">
            <div class="card-h3-row">
              <div>
                <h3>遗忘曲线预测（时光机）</h3>
                <small>基于 BKT + 卡尔曼平滑，未来 30 天掌握度演化 · 橙色带为 95% 置信区间</small>
              </div>
              <span v-if="forecastCurrent != null" class="trend-chip up">
                <Activity :size="12" />
                当前 {{ Math.round(forecastCurrent * 100) }}%
              </span>
            </div>
            <p v-if="!forecastCurve.length" class="empty-line">
              暂无预测数据（学生做题后自动生成 30 天曲线）。
            </p>
            <template v-else>
              <div ref="forecastChartEl" class="forecast-echarts" role="img" aria-label="学生 30 天掌握度预测曲线"></div>
              <p v-if="forecastSummary" class="insight-forecast">{{ forecastSummary }}</p>
            </template>
          </div>

          <div class="card">
            <h3>风险提示与干预建议</h3>
            <p v-if="!summary?.risks?.length" class="empty-line">暂无风险，状态良好。</p>
            <ul v-else class="risk-list">
              <li v-for="(r, i) in summary!.risks" :key="i" :class="r.level">
                <AlertTriangle :size="14" /> {{ r.message }}
              </li>
            </ul>
            <div class="insight-actions">
              <button type="button" class="ghost-btn" @click="router.push('/teacher/resources')">去指派资源</button>
              <button type="button" class="ghost-btn" @click="router.push('/teacher/interventions').then(() => activeTab = 'paths')">去推送路径</button>
              <button type="button" class="ghost-btn" @click="router.push('/teacher/interventions').then(() => activeTab = 'chat')">去发消息</button>
            </div>
          </div>
        </div>
        <p class="hint-line" style="flex: none">
          数据来源：BKT 知识追踪 × 错题归因 × 时光机遗忘预测（与学生端同一套认知诊断引擎）；
          可据此在「课程资源 / 路径推荐 / 群聊消息」页签直接干预。
        </p>
      </template>
    </section>

    <!-- ===================== Tab 1.6 班级看板 ===================== -->
    <section v-if="activeTab === 'board'" class="tab-panel board-panel workbench-v3">
      <!-- ========== 1. AI 今日洞察 · Insight Surface ========== -->
      <!-- 顺序：左 copy（1fr）· 右 orb（180px）· grid 顺序与 CSS 列一致 -->
      <div class="insight-surface" v-if="classData">
        <div class="insight-copy">
          <div class="insight-chip">
            <Sparkles :size="14" class="chip-icon" />
            <span>AI 今日洞察</span>
          </div>
          <h2 class="insight-title">
            班级整体掌握度为 <b>{{ classAvgMastery }}%</b>，当前最薄弱知识点为
            <b v-if="classData.weak_kps[0]">「{{ classData.weak_kps[0].kp_name }}」</b><b v-else>暂未识别</b>，
            建议优先跟进 <b>{{ classData.risk_students.length }} 名学生</b>，
            <template v-if="classData.weak_kps[0]">
              围绕 <b>{{ classData.weak_kps[0].mistake_count }} 道累积错题</b>布置
              <b>{{ suggestedDrill.minutes }} 分钟 · {{ suggestedDrill.count }} 题分层练习</b>。
            </template>
            <template v-else>推动学生完成本周基础练习。</template>
          </h2>
          <p class="insight-meta">
            基于最新学习数据与多智能体分析
            <span class="insight-dot">·</span>
            更新时间 {{ formatTime(classData.generated_at) }}
          </p>
          <div class="insight-actions">
            <button type="button" class="btn-outlined" @click="router.push('/teacher/students')">
              <LineChart :size="14" /> 查看分析依据
            </button>
            <button type="button" class="btn-outlined" @click="router.push({ path: '/teacher/interventions', query: { tab: 'copilot' } })">
              <Sparkles :size="14" /> 生成教学任务
            </button>
            <button
              type="button"
              class="btn-filled"
              @click="askCopilot(`针对班级最薄弱知识点${suggestedDrill.focusKp ? '「' + suggestedDrill.focusKp + '」' : ''}，一键生成一份 ${suggestedDrill.minutes} 分钟补强练习方案，包含讲解要点、${suggestedDrill.count} 道分层练习（基础/提升/拓展）、错误反馈机制`)"
            >
              <Send :size="14" /> 一键布置 {{ suggestedDrill.minutes }} 分钟练习
            </button>
          </div>
        </div>
        <aside class="insight-decision-rail" aria-label="本周教学焦点">
          <span>本周教学焦点</span>
          <b>{{ classData.weak_kps[0]?.kp_name || '等待更多学习证据' }}</b>
          <dl>
            <div><dt>未达标学生</dt><dd>{{ classData.weak_kps[0]?.students_below_60 || 0 }} 人</dd></div>
            <div><dt>错题积压</dt><dd>{{ classData.weak_kps[0]?.mistake_count || 0 }} 道</dd></div>
            <div><dt>建议课堂投入</dt><dd>{{ suggestedDrill.minutes }} 分钟</dd></div>
          </dl>
        </aside>
        <div class="insight-orb" aria-hidden="true">
          <span class="orb-core"></span>
          <span class="orb-halo halo-1"></span>
          <span class="orb-halo halo-2"></span>
        </div>
      </div>

      <!-- ========== 2. KPI 条（保留） ========== -->
      <div v-if="classData" class="kpi-grid">
        <div class="kpi-card">
          <small>已采集掌握度</small>
          <b>{{ classData.student_count - classData.mastery.no_data_count }}<em> / {{ classData.student_count }} 人</em></b>
        </div>
        <div class="kpi-card">
          <small>7 日活跃</small>
          <b>{{ classData.active_7d }}<em> / {{ classData.student_count }}</em></b>
        </div>
        <div class="kpi-card">
          <small>优先干预名单</small>
          <b>{{ classData.risk_students.length }}<em> 人</em></b>
        </div>
        <div class="kpi-card">
          <small>未解决错题合计</small>
          <b>{{ classData.mistakes_open_total }}</b>
        </div>
      </div>

      <div v-if="classLoading" class="panel-loading">
        <Loader2 :size="16" class="spin" /> 正在聚合全班学情...
      </div>

      <!-- ========== 3. 主内容两栏 · 左 2/3 主内容 · 右 1/3 AI Copilot Panel ========== -->
      <div v-if="classData" class="workbench-grid">
        <!-- ========== 左侧主内容 ========== -->
        <div class="workbench-main">
          <!-- Row 1: 今日行动 60% + 掌握度分布 Donut 40% -->
          <div class="row action-row">
            <!-- 今日行动 -->
            <div class="card action-panel">
              <header class="card-h3-row">
                <div>
                  <h3>今日行动</h3>
                  <small>根据 AI 优先级推荐，聚焦关键教学干预</small>
                </div>
                <button type="button" class="text-link" @click="router.push('/teacher/students')">全部任务 ›</button>
              </header>
              <ol class="action-list">
                <li
                  v-for="(item, index) in todayActions"
                  :key="item.key"
                  :class="['action-item', item.priority]"
                >
                  <span class="action-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                  <div class="action-body">
                    <b>{{ item.title }}</b>
                    <small>{{ item.detail }}</small>
                    <div v-if="item.badges?.length" class="action-badges">
                      <span v-for="b in item.badges" :key="b" class="mini-chip">{{ b }}</span>
                    </div>
                  </div>
                  <button type="button" class="btn-tonal action-cta" @click="item.onAction">
                    {{ item.action }} <ArrowRight :size="12" />
                  </button>
                </li>
              </ol>
            </div>

            <!-- 掌握度分布 Donut -->
            <div class="card donut-panel">
              <header class="card-h3-row">
                <div>
                  <h3>掌握度分布</h3>
                  <small>基于 BKT 追踪，五桶聚合</small>
                </div>
                <span class="trend-chip up">
                  <TrendingUp :size="12" />
                  较昨日 +2%
                </span>
              </header>
              <div ref="masteryDonutEl" class="donut-canvas" aria-label="掌握度分布环形图"></div>
              <ul class="donut-legend">
                <li v-for="bucket in masteryLegend" :key="bucket.bucket">
                  <i :style="{ background: bucket.color }"></i>
                  <span>{{ bucket.label }}</span>
                  <b>{{ bucket.count }} 人</b>
                  <em>{{ Math.round(bucket.percent) }}%</em>
                </li>
              </ul>
            </div>
          </div>

          <!-- Row 2: 薄弱 KP TOP5 + 错因分布 + 30 天趋势（后者跨两行结构改为独立一行） -->
          <div class="row analytics-row">
            <div class="card weak-kp-panel">
              <header class="card-h3-row">
                <div>
                  <h3>薄弱知识点 TOP5</h3>
                  <small>按班级平均掌握度升序</small>
                </div>
                <button type="button" class="text-link" @click="router.push('/teacher/students')">查看全部 ›</button>
              </header>
              <p v-if="!classData.weak_kps.length" class="empty-line">暂无 BKT 追踪数据。</p>
              <div v-else class="weak-list">
                <article v-for="(kp, index) in classData.weak_kps" :key="kp.kp_id" class="weak-row">
                  <span class="weak-idx">{{ String(index + 1).padStart(2, '0') }}</span>
                  <div class="weak-info">
                    <b :title="kp.kp_id">{{ kp.kp_name }}</b>
                    <small>{{ kp.students_below_60 }} / {{ kp.students_tracked }} 人未达标</small>
                    <div class="weak-progress">
                      <div class="weak-progress-track">
                        <div class="weak-progress-fill" :style="{ width: `${Math.round(kp.avg_mastery * 100)}%`, background: masteryColor(kp.avg_mastery) }"></div>
                      </div>
                    </div>
                  </div>
                  <div class="weak-value">
                    <b>{{ Math.round(kp.avg_mastery * 100) }}<span>%</span></b>
                    <button class="weak-cta" type="button" title="查看该薄弱点的教学建议" @click="goCopilotForKp(kp)">
                      <ArrowRight :size="12" />
                    </button>
                  </div>
                </article>
              </div>
            </div>

            <div class="card error-donut-panel">
              <header class="card-h3-row">
                <div>
                  <h3>错误原因分布</h3>
                  <small>未解决错题按归因统计</small>
                </div>
                <button type="button" class="text-link" @click="router.push('/teacher/students')">查看错题详情 ›</button>
              </header>
              <p v-if="!classData.error_distribution.length" class="empty-line">暂无未解决错题。</p>
              <template v-else>
                <div ref="errorDonutEl" class="donut-canvas donut-mid" aria-label="错因分布环形图"></div>
                <ul class="donut-legend compact">
                  <li v-for="e in errorDistributionView" :key="e.category">
                    <i :style="{ background: e.color }"></i>
                    <span>{{ e.label }}</span>
                    <b>{{ e.count }}</b>
                    <em>{{ e.percent }}%</em>
                  </li>
                </ul>
              </template>
            </div>
          </div>

          <!-- Row 3: 近 30 天趋势（整行，ECharts 双轴） -->
          <div class="row">
            <div class="card trend-card-full">
              <header class="card-h3-row">
                <div>
                  <h3>近 30 天学习趋势</h3>
                  <small>柱状=每日活动 · 折线=日均得分 · 双 Y 轴</small>
                </div>
                <div class="trend-latest-inline">
                  <span>最新活动 <b>{{ classTrendChart.activity[classTrendChart.activity.length - 1]?.value || 0 }}</b> 次</span>
                  <span class="trend-chip up" v-if="classTrendDelta.hasBaseline && classTrendDelta.activityDelta >= 0">
                    <TrendingUp :size="12" /> +{{ classTrendDelta.activityDelta }}%
                  </span>
                  <span class="trend-chip down" v-else-if="classTrendDelta.hasBaseline">
                    <TrendingDown :size="12" /> {{ classTrendDelta.activityDelta }}%
                  </span>
                </div>
              </header>
              <p v-if="!classData.mastery.trend.length" class="empty-line">窗口期内暂无学习活动记录。</p>
              <div v-else class="trend-echarts-wrap">
                <div ref="teacherTrendChartEl" class="trend-echarts-el" role="img" aria-label="近 30 天学习活动柱状图与日均得分折线图"></div>
              </div>
            </div>
          </div>

          <!-- Row 4: 优先干预名单 + 活跃度分布（保留原信息价值） -->
          <div class="row secondary-row">
            <div class="card risk-list-card">
              <header class="card-h3-row">
                <div>
                  <h3>优先干预名单</h3>
                  <small>按风险排序：掌握度 × 错题积压 × 活跃度</small>
                </div>
              </header>
              <p v-if="!classData.risk_students.length" class="empty-line">暂无风险学生，班级状态良好。</p>
              <div v-else class="risk-list-v3">
                <div v-for="r in classData.risk_students" :key="r.user_id" class="risk-row-v3">
                  <span :class="['risk-dot', r.level]" :title="`${riskLevelLabel[r.level]}风险`"></span>
                  <div class="risk-info">
                    <b>{{ r.display_name || r.user_id }}</b>
                    <small>风险分 {{ r.risk_score_pct }} · {{ r.reasons.join('；') }}</small>
                  </div>
                  <span :class="['risk-badge-v3', r.level]">{{ riskLevelLabel[r.level] }}风险</span>
                  <div class="risk-actions-v3">
                    <button type="button" class="btn-tonal-sm" @click="goStudentAnalysis(r.user_id)">查学情</button>
                    <button type="button" class="btn-filled-sm" @click="goStudentCopilot(r.user_id)">AI 建议</button>
                  </div>
                </div>
              </div>
            </div>

            <div class="card activity-card">
              <header class="card-h3-row">
                <div>
                  <h3>活跃度分布</h3>
                  <small>按最近一次学习时间</small>
                </div>
              </header>
              <div class="activity-hero-v3">
                <div class="activity-big">
                  <b>{{ classActiveRate }}<span>%</span></b>
                  <small>7 日活跃率</small>
                </div>
                <div class="activity-detail">
                  <div v-for="b in activityBuckets" :key="b.key" class="activity-row">
                    <span class="dot" :style="{ background: b.color }"></span>
                    <span class="label">{{ b.shortLabel }}</span>
                    <b>{{ b.users.length }} 人</b>
                    <em>{{ Math.round(b.percent) }}%</em>
                  </div>
                </div>
              </div>
              <div class="activity-stack" aria-label="班级活跃状态分布">
                <span
                  v-for="b in activityBuckets"
                  :key="b.key"
                  :style="{ width: `${b.percent}%`, background: b.color }"
                  :title="`${b.label} ${b.users.length} 人`"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- ========== 右侧 AI Copilot Panel · 6 Agent 团队 ========== -->
        <aside class="copilot-panel" :class="{ collapsed: !copilotOpen }" aria-label="AI 助教 Copilot">
          <header class="copilot-header">
            <div class="copilot-header-title">
              <span class="copilot-avatar">
                <Sparkles :size="14" />
              </span>
              <div>
                <b>AI 助教 Copilot</b>
                <small><span class="beta-badge">Beta</span> 6 智能体协同工作中</small>
              </div>
            </div>
            <button type="button" class="icon-btn" :title="copilotOpen ? '折叠面板' : '展开面板'" @click="copilotOpen = !copilotOpen">
              <X v-if="copilotOpen" :size="16" />
              <Sparkles v-else :size="16" />
            </button>
          </header>

          <!-- 6 Agent Fleet Bar -->
          <div class="copilot-fleet" aria-label="内置 6 智能体团队">
            <div v-for="agent in TEACHER_AGENTS" :key="agent.key" class="fleet-agent" :title="`${agent.name} · ${agent.role} · ${agent.desc}`">
              <div class="fleet-avatar" :style="{ boxShadow: `0 0 0 2px ${agent.soft}` }">
                <img :src="agent.avatar" :alt="agent.name" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                <span class="fleet-fallback" :style="{ background: agent.color }">{{ agent.name[0] }}</span>
                <span class="fleet-online" :style="{ background: agent.color }"></span>
              </div>
              <small>{{ agent.name }}</small>
            </div>
          </div>

          <!-- Messages -->
          <div class="copilot-messages">
            <template v-for="msg in copilotMessages" :key="msg.id">
              <div v-if="msg.role === 'ai'" class="msg msg-ai">
                <div v-if="msg.loading" class="msg-loading">
                  <div class="loading-agent">
                    <img
                      v-if="msg.activeAgent && findTeacherAgent(msg.activeAgent)"
                      :src="findTeacherAgent(msg.activeAgent)!.avatar"
                      :alt="msg.activeAgent"
                      class="loading-agent-avatar"
                    />
                    <span class="loading-agent-info">
                      <b>{{ msg.activeAgent || 'AI 团队' }}</b>
                      <small>{{ msg.stage || '思考中…' }}</small>
                    </span>
                    <Loader2 :size="14" class="spin" />
                  </div>
                  <div class="linear-progress">
                    <span></span>
                  </div>
                </div>
                <div v-else class="msg-content">
                  <MarkdownBlock v-if="msg.content" :content="msg.content" />
                  <p v-else class="empty-line">本次未生成正文。</p>
                  <footer v-if="msg.agents_invoked?.length" class="msg-agents">
                    <small>由</small>
                    <span v-for="ag in msg.agents_invoked.slice(0, 3)" :key="ag.name" class="msg-agent-chip" :class="{ failed: !ag.success }">
                      <img v-if="findTeacherAgent(ag.name)" :src="findTeacherAgent(ag.name)!.avatar" :alt="ag.name" />
                      {{ ag.name }}
                    </span>
                    <small>联合生成 <span v-if="msg.safety_level">· 安全 {{ msg.safety_level }}</span></small>
                  </footer>
                </div>
              </div>
              <div v-else class="msg msg-teacher">
                <p>{{ msg.content }}</p>
              </div>
            </template>
          </div>

          <!-- Suggestion Chips -->
          <div class="copilot-suggestions">
            <small class="section-note">您还可以这样说：</small>
            <div class="chip-row">
              <button
                v-for="s in copilotSuggestions.slice(0, 4)"
                :key="s.label"
                type="button"
                class="suggest-chip"
                :disabled="copilotAsking"
                @click="askCopilot(s.instruction)"
              >
                <Sparkles :size="12" /> {{ s.label }}
              </button>
            </div>
          </div>

          <!-- Input -->
          <div class="copilot-input">
            <textarea
              v-model="copilotInput"
              :disabled="copilotAsking"
              rows="2"
              placeholder="向 AI 助教提问... (Enter 发送 · Shift+Enter 换行)"
              @keydown.enter.exact.prevent="askCopilot()"
              @keydown.enter.shift.exact="() => {}"
            />
            <button type="button" class="btn-filled input-send" :disabled="!copilotInput.trim() || copilotAsking" @click="askCopilot()">
              <Loader2 v-if="copilotAsking" :size="14" class="spin" />
              <Send v-else :size="14" />
            </button>
          </div>
        </aside>
      </div>
    </section>


    <!-- ===================== Tab 2 课程资源 ===================== -->
    <section v-if="activeTab === 'resources'" class="tab-panel">
      <!-- ============ Studio 独立工作台（section=studio 专属）============ -->
      <template v-if="isTeachingStudio">
        <div class="studio-workspace">
          <!-- 左侧：Prompt 编辑区（2fr） -->
          <div class="studio-editor card">
            <header class="studio-editor-head">
              <div>
                <h3><Sparkles :size="16" /> 教师提示词工作台</h3>
                <small>写下教学意图 → 6 Agent 团队协同生成 → 审核后发布到学生端</small>
              </div>
              <div class="studio-agent-strip" aria-label="参与本次生成的 Agent">
                <div v-for="agent in TEACHER_AGENTS" :key="agent.key" class="studio-agent-avatar" :title="`${agent.name} · ${agent.role}`">
                  <img :src="agent.avatar" :alt="agent.name" @error="($event.target as HTMLImageElement).style.display = 'none'" />
                  <span class="studio-agent-fallback" :style="{ background: agent.color }">{{ agent.name[0] }}</span>
                </div>
              </div>
            </header>

            <div class="studio-type-group" role="tablist" aria-label="内容类型">
              <button
                v-for="t in STUDIO_TYPES"
                :key="t.key"
                type="button"
                role="tab"
                :aria-selected="studioType === t.key"
                :class="['studio-type-chip', { active: studioType === t.key }]"
                @click="studioType = t.key"
              >
                <component :is="t.icon" :size="14" />
                <span>{{ t.label }}</span>
              </button>
            </div>
            <p class="studio-type-hint">{{ STUDIO_TYPES.find((t) => t.key === studioType)?.hint }}</p>

            <label class="studio-label">教学提示词</label>
            <textarea
              v-model="studioPrompt"
              rows="6"
              placeholder="写下你的教学意图，越具体越好。例如：为「Transformer 架构」写一份 1200 字讲义，包含核心概念、Encoder/Decoder 结构、Self-Attention 计算过程、3 道随堂练习"
              :disabled="studioLoading"
            ></textarea>

            <div class="studio-hint-row">
              <small>提示词范例：</small>
              <button
                v-for="(h, i) in STUDIO_PROMPT_HINTS"
                :key="i"
                type="button"
                class="studio-hint-chip"
                @click="useStudioHint(h)"
              >范例 {{ i + 1 }}</button>
            </div>

            <div class="studio-scope-row">
              <div class="studio-scope-group">
                <label class="studio-label">发布范围</label>
                <div class="qi-mode-switch">
                  <button
                    v-for="s in [{ k: 'course', l: '全班共用' }, { k: 'student', l: '指派学生' }]"
                    :key="s.k"
                    type="button"
                    :class="['qi-mode-btn', { active: studioScope === s.k }]"
                    @click="studioScope = s.k as 'course' | 'student'"
                  >{{ s.l }}</button>
                </div>
              </div>
              <div v-if="studioScope === 'student'" class="studio-target-group">
                <label class="studio-label">目标学生</label>
                <select v-model="studioTargetUserId">
                  <option value="">— 选择学生 —</option>
                  <option v-for="s in students" :key="s.user_id" :value="s.user_id">
                    {{ s.display_name }} ({{ s.mastery_avg != null ? Math.round(s.mastery_avg * 100) + '%' : '—' }})
                  </option>
                </select>
              </div>
            </div>

            <div class="studio-submit-row">
              <button type="button" class="ghost-btn" :disabled="studioLoading" @click="() => { studioPrompt = ''; studioResult = null; }">
                <X :size="14" /> 清空
              </button>
              <button type="button" class="primary-btn" :disabled="studioLoading || !studioPrompt.trim()" @click="runStudio">
                <Loader2 v-if="studioLoading" :size="14" class="spin" />
                <Sparkles v-else :size="14" />
                {{ studioLoading ? '生成中…' : '开始生成' }}
              </button>
            </div>
          </div>

          <!-- 右侧：生成预览（1fr） -->
          <aside class="studio-preview card">
            <header class="studio-preview-head">
              <div>
                <h3>生成预览</h3>
                <small v-if="studioResult">
                  {{ studioResult.action_label }}
                  <span v-if="studioResult.safety_level"> · 安全 {{ studioResult.safety_level }}</span>
                </small>
                <small v-else-if="studioLoading">6 Agent 协同工作中…</small>
                <small v-else>提交提示词后此区显示预览</small>
              </div>
              <div v-if="studioResult?.agents_invoked?.length" class="studio-agents-mini">
                <span v-for="ag in studioResult.agents_invoked.slice(0, 3)" :key="ag.name" class="studio-agent-chip" :class="{ failed: !ag.success }">
                  <img v-if="findTeacherAgent(ag.name)" :src="findTeacherAgent(ag.name)!.avatar" :alt="ag.name" />
                  {{ ag.name }}
                </span>
              </div>
            </header>

            <!-- Loading 状态 -->
            <div v-if="studioLoading" class="studio-loading">
              <div class="loading-agent">
                <img
                  v-if="studioActiveAgent && findTeacherAgent(studioActiveAgent)"
                  :src="findTeacherAgent(studioActiveAgent)!.avatar"
                  :alt="studioActiveAgent"
                  class="loading-agent-avatar"
                />
                <div class="loading-agent-info">
                  <b>{{ studioActiveAgent || 'AI 团队' }}</b>
                  <small>{{ studioStage || '思考中…' }}</small>
                </div>
                <Loader2 :size="14" class="spin" />
              </div>
              <div class="linear-progress"><span></span></div>
            </div>

            <!-- 结果内容 -->
            <div v-else-if="studioResult" class="studio-result">
              <MarkdownBlock v-if="studioResult.content" :content="studioResult.content" />
              <p v-else class="empty-line">本次未生成正文。请调整提示词后重试。</p>
              <div v-if="studioResult.artifact" class="studio-binary-result">
                <div>
                  <b>真实{{ studioResult.artifact.type === 'video' ? '视频' : 'PPT' }}文件已生成</b>
                  <small>{{ studioResult.artifact.filename }}</small>
                </div>
                <a
                  class="ghost-btn"
                  :href="studioResult.artifact.download_url"
                  target="_blank"
                  rel="noopener"
                  download
                >
                  <Download :size="14" /> 立即下载
                </a>
              </div>
              <p v-else-if="studioResult.binary_error" class="studio-binary-error">
                二进制文件生成失败：{{ studioResult.binary_error }}。当前正文仅供排查，不能发布为 PPT/视频资源。
              </p>
              <div v-if="studioResult.content" class="studio-actions">
                <a
                  v-if="studioResult.artifact"
                  class="ghost-btn"
                  :href="studioResult.artifact.download_url"
                  target="_blank"
                  rel="noopener"
                  download
                >
                  <Download :size="14" /> 下载文件
                </a>
                <button type="button" class="ghost-btn" @click="() => publishStudioResult('draft')">
                  <FileDown :size="14" /> 存为草稿
                </button>
                <button type="button" class="primary-btn" @click="() => publishStudioResult('published')">
                  <Upload :size="14" /> 发布到学生端
                </button>
              </div>
            </div>

            <div v-else class="studio-empty">
              <Sparkles :size="28" />
              <p><b>还没有生成内容</b></p>
              <p>在左侧写下你的提示词，选择内容类型，然后点击「开始生成」。</p>
            </div>
          </aside>
        </div>

        <!-- 直接上传本地文件（保留原入口） -->
        <div class="studio-upload-row">
          <div>
            <b>或者直接上传本地文件</b>
            <small>教师已经准备好的 PPT / 视频 / 讲义 / 代码，可直接上传后发布给学生</small>
          </div>
          <div class="studio-upload-buttons">
            <button type="button" class="ghost-btn" @click="openUploadResource('video')">
              <Upload :size="14" /> 上传课程视频
            </button>
            <button type="button" class="ghost-btn" @click="openUploadResource('ppt')">
              <Upload :size="14" /> 上传 PPT
            </button>
            <button type="button" class="ghost-btn" @click="openUploadResource('document')">
              <Upload :size="14" /> 上传文档
            </button>
            <button type="button" class="ghost-btn" @click="openUploadResource('code')">
              <Upload :size="14" /> 上传代码
            </button>
          </div>
        </div>

        <div class="studio-list-divider">
          <span>已发布的 Studio 内容</span>
        </div>
      </template>
      <div class="toolbar">
        <input v-model="resourceQuery" :placeholder="isTeachingStudio ? '搜索提示词或课程视频' : '搜索标题/内容'" @keyup.enter="loadResources" />
        <select v-model="resourceStatusFilter" @change="loadResources">
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="draft">草稿</option>
          <option value="archived">已下架</option>
        </select>
        <button type="button" class="ghost-btn" @click="loadResources"><RefreshCcw :size="14" /> 刷新</button>
        <button v-if="isTeachingStudio" type="button" class="ghost-btn" @click="openUploadResource('video')"><Upload :size="14" /> 上传课程视频</button>
        <button v-else type="button" class="ghost-btn" @click="openUploadResource()"><Upload :size="14" /> 上传资料</button>
        <button v-if="isTeachingStudio" type="button" class="primary-btn" @click="openCreateResource('prompt')"><Plus :size="14" /> 编写学习提示</button>
        <button v-else type="button" class="primary-btn" @click="openCreateResource()"><Plus :size="14" /> 新增资源</button>
      </div>

      <div v-if="resourcesLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 加载资源...</div>
      <p v-else-if="!displayedResources.length" class="empty-line">
        {{ isTeachingStudio ? "暂无学习提示或课程视频。先编写一条提示词，或上传教师录制的视频。" : "暂无资源，可上传现有课件/讲义，或新建一份在线资源。" }}
      </p>
      <table v-else class="data-table">
        <thead>
          <tr>
            <th>标题</th><th>类型</th><th>可见范围</th><th>状态</th><th>创建者</th><th>时间</th><th class="ops-col">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in displayedResources" :key="item.id">
            <td class="title-cell">
              <b>{{ item.title }}</b>
              <small v-if="item.metadata.attachment" class="resource-file">
                {{ item.metadata.attachment.filename }} · {{ formatFileSize(item.metadata.attachment.size_bytes) }}
              </small>
            </td>
            <td>{{ resourceTypeOptions.find((t) => t.key === item.type)?.label || item.type }}</td>
            <td>{{ item.metadata.scope === "student" ? `指定学生(${(item.metadata.target_user_ids || []).length})` : "全课程" }}</td>
            <td>
              <em :class="['chip', item.metadata.status]">{{ statusLabel[item.metadata.status || 'published'] || '已发布' }}</em>
            </td>
            <td>{{ resourceCreatorLabel[String(item.metadata.created_by || item.agent_name || "").toLowerCase()] || item.metadata.created_by || item.agent_name || "—" }}</td>
            <td>{{ formatTime(item.created_at) }}</td>
            <td class="ops-cell">
              <button v-if="isVideoResource(item)" type="button" title="发布前预览视频" @click="previewVideoResource(item)">预览</button>
              <button v-if="item.metadata.attachment" type="button" title="下载原始资料" @click="downloadResource(item)"><Download :size="14" /> 下载</button>
              <button type="button" title="编辑" @click="openEditResource(item)"><Pencil :size="14" /></button>
              <button type="button" :title="item.metadata.status === 'published' ? '下架' : '发布'" @click="toggleResourceStatus(item)">
                {{ item.metadata.status === "published" ? "下架" : "发布" }}
              </button>
              <button type="button" title="指派给学生" @click="assigningResource = item">指派</button>
              <button type="button" class="danger" title="删除" @click="removeResource(item)"><Trash2 :size="14" /></button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 资源表单弹层 -->
      <div v-if="showResourceForm" class="modal-mask" @click.self="showResourceForm = false">
        <div class="modal">
          <header>
            <b>{{ editingResourceId ? "编辑内容" : (isTeachingStudio ? "编写学习提示词" : "新增课程资源") }}</b>
            <button type="button" @click="showResourceForm = false"><X :size="16" /></button>
          </header>
          <label>标题<input v-model="resourceForm.title" placeholder="例如：机器学习基础补充讲义" /></label>
          <div class="form-row">
            <label>类型
              <select v-model="resourceForm.type">
                <option v-for="t in editorResourceTypeOptions" :key="t.key" :value="t.key">{{ t.label }}</option>
              </select>
            </label>
            <label>可见范围
              <select v-model="resourceForm.scope">
                <option value="course">全课程可见</option>
                <option value="student">仅指派学生</option>
              </select>
            </label>
            <label>状态
              <select v-model="resourceForm.status">
                <option value="published">发布</option>
                <option value="draft">草稿</option>
                <option value="archived">下架</option>
              </select>
            </label>
          </div>
          <div v-if="resourceForm.type === 'prompt'" class="prompt-guide">
            <b>建议写清 3 件事</b>
            <span>学习目标</span><span>思考步骤</span><span>完成标准</span>
          </div>
          <label>
            {{ resourceForm.type === "prompt" ? "提示词正文" : "内容（Markdown）" }}
            <textarea
              v-model="resourceForm.content"
              rows="7"
              :placeholder="resourceForm.type === 'prompt' ? '例如：先用自己的话解释梯度下降，再画出参数更新过程，最后完成一道变式题；若不会，请指出卡住的步骤。' : '录入讲义正文 / 题目 / 案例代码...'"
            />
          </label>
          <div class="form-row">
            <label>标签（逗号分隔）<input v-model="resourceForm.tags" placeholder="机器学习,基础" /></label>
            <label>适用知识点 ID（逗号分隔）<input v-model="resourceForm.kp_ids" placeholder="kp_ml_basic" /></label>
          </div>
          <label v-if="resourceForm.scope === 'student'">
            指定学生
            <select v-model="resourceForm.targetUserId">
              <option value="">请选择学生</option>
              <option v-for="student in students" :key="student.user_id" :value="student.user_id">
                {{ student.display_name }}（{{ student.user_id }}）
              </option>
            </select>
          </label>
          <footer>
            <button type="button" class="ghost-btn" @click="showResourceForm = false">取消</button>
            <button type="button" class="primary-btn" @click="submitResourceForm">保存</button>
          </footer>
        </div>
      </div>

      <!-- 文件上传：原件存储 + 资源元数据，不会自动发布给学生 -->
      <div v-if="showUploadForm" class="modal-mask" @click.self="showUploadForm = false">
        <div class="modal upload-modal">
          <header>
            <b>{{ isTeachingStudio ? "上传教师课程视频" : "上传课程资料" }}</b>
            <button type="button" @click="showUploadForm = false"><X :size="16" /></button>
          </header>
          <p class="hint-line">
            {{ isTeachingStudio ? "支持 MP4、WebM、MOV、M4V，单个视频不超过 200 MB。建议先保存为草稿并完整预览，再发布给学生。" : "支持 PDF、Word、PPT、Excel、文本、代码与 ZIP，单个文件不超过 20 MB。默认保存为草稿，审核后再发布。" }}
          </p>
          <label class="upload-picker">
            <span>选择文件</span>
            <input
              type="file"
              :accept="isTeachingStudio ? '.mp4,.webm,.mov,.m4v' : '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.csv,.json,.py,.ipynb,.zip,.mp4,.webm,.mov,.m4v'"
              @change="selectUploadFile"
            />
            <small v-if="uploadFile">{{ uploadFile.name }} · {{ formatFileSize(uploadFile.size) }}</small>
            <small v-else>尚未选择文件</small>
          </label>
          <label>资源标题<input v-model="uploadForm.title" placeholder="默认使用文件名" /></label>
          <div class="form-row">
            <label>{{ isTeachingStudio ? "内容类型" : "资料类型" }}
              <select v-model="uploadForm.type">
                <option v-for="t in uploadResourceTypeOptions" :key="t.key" :value="t.key">{{ t.label }}</option>
              </select>
            </label>
            <label>可见范围
              <select v-model="uploadForm.scope">
                <option value="course">全课程可见</option>
                <option value="student">仅指派学生</option>
              </select>
            </label>
            <label>状态
              <select v-model="uploadForm.status">
                <option value="draft">草稿（推荐）</option>
                <option value="published">直接发布</option>
              </select>
            </label>
          </div>
          <div class="form-row">
            <label>标签（逗号分隔）<input v-model="uploadForm.tags" placeholder="机器学习,课堂资料" /></label>
            <label>适用知识点 ID（逗号分隔）<input v-model="uploadForm.kp_ids" placeholder="kp_ml_basic" /></label>
          </div>
          <label v-if="uploadForm.scope === 'student'">
            指定学生
            <select v-model="uploadForm.targetUserId">
              <option value="">请选择学生</option>
              <option v-for="student in students" :key="student.user_id" :value="student.user_id">
                {{ student.display_name }}（{{ student.user_id }}）
              </option>
            </select>
          </label>
          <footer>
            <button type="button" class="ghost-btn" @click="showUploadForm = false">取消</button>
            <button type="button" class="primary-btn" :disabled="uploadSubmitting || !uploadFile" @click="submitUploadResource">
              <Loader2 v-if="uploadSubmitting" :size="14" class="spin" />
              <Upload v-else :size="14" />
              {{ uploadSubmitting ? "上传中…" : "上传并保存" }}
            </button>
          </footer>
        </div>
      </div>

      <!-- 教师发布前视频预览 -->
      <div v-if="previewVideoItem" class="modal-mask" @click.self="closeVideoPreview">
        <div class="modal video-review-modal">
          <header>
            <div>
              <b>{{ previewVideoItem.title }}</b>
              <small>发布前请确认画面、声音和知识点标注均正确</small>
            </div>
            <button type="button" @click="closeVideoPreview"><X :size="16" /></button>
          </header>
          <div v-if="previewVideoLoading" class="panel-loading"><Loader2 :size="18" class="spin" /> 正在加载视频…</div>
          <video v-else-if="previewVideoUrl" :src="previewVideoUrl" controls preload="metadata" playsinline />
          <p v-else class="empty-line">视频暂时无法预览，请下载后检查。</p>
          <footer>
            <span>{{ previewVideoItem.metadata.status === "published" ? "当前已发布" : "当前为草稿/下架状态" }}</span>
            <button type="button" class="ghost-btn" @click="closeVideoPreview">完成检查</button>
          </footer>
        </div>
      </div>

      <!-- 指派弹层 -->
      <div v-if="assigningResource" class="modal-mask" @click.self="assigningResource = null">
        <div class="modal">
          <header>
            <b>指派《{{ assigningResource.title }}》</b>
            <button type="button" @click="assigningResource = null"><X :size="16" /></button>
          </header>
          <label>目标学生
            <select v-model="selectedStudentId">
              <option v-for="s in students" :key="s.user_id" :value="s.user_id">{{ s.display_name }}</option>
            </select>
          </label>
          <label>附言（写入群聊）<textarea v-model="assignNote" rows="3" placeholder="这份资料针对你最近的薄弱点，建议本周内看完。" /></label>
          <footer>
            <button type="button" class="ghost-btn" @click="assigningResource = null">取消</button>
            <button type="button" class="primary-btn" @click="confirmAssignResource"><Send :size="14" /> 推荐并写入群聊</button>
          </footer>
        </div>
      </div>
    </section>

    <!-- ===================== Tab 3 Agent 管理 ===================== -->
    <section v-if="activeTab === 'agents'" class="tab-panel">
      <div class="toolbar">
        <p class="hint-line">配置型 Agent 由统一执行器驱动，无需上传代码；学生在群聊 @名称 即可调用。内置 Agent 仅可修改展示信息与启用状态。</p>
        <button type="button" class="ghost-btn" @click="loadAgents"><RefreshCcw :size="14" /> 刷新</button>
        <button type="button" class="primary-btn" @click="openCreateAgent"><Plus :size="14" /> 新增 Agent</button>
      </div>

      <div v-if="agentsLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 加载 Agent...</div>
      <div v-else class="agent-grid">
        <div v-for="agent in agents" :key="agent.key" :class="['agent-card', { disabled: !agent.enabled }]">
          <div class="agent-card-head">
            <span class="agent-avatar-shell" :style="{ '--agent-accent': agentVisual(agent).color }">
              <img v-if="agentVisual(agent).src" :src="agentVisual(agent).src" :alt="`${agent.name}头像`" />
              <b v-else>{{ agentVisual(agent).emoji }}</b>
              <i :class="{ online: agent.enabled }" />
            </span>
            <div class="agent-identity">
              <div>
                <b>{{ agent.name }}</b>
                <em v-if="agent.builtin" class="chip">内置</em>
                <em v-else class="chip teacher-chip">教师配置</em>
              </div>
              <small>{{ agent.title || "专项协作 Agent" }}</small>
            </div>
          </div>
          <p>{{ agent.role_desc || agentVisual(agent).responsibility }}</p>
          <div class="agent-caps">
            <em v-for="cap in agent.capabilities" :key="cap" class="chip">{{ cap }}</em>
            <em v-if="!(agent.capabilities || []).length" class="chip muted-chip">系统内置能力</em>
          </div>
          <div class="agent-ops">
            <label class="switch">
              <input type="checkbox" :checked="agent.enabled" @change="toggleAgentEnabled(agent)" />
              <span>{{ agent.enabled ? "正在参与协作" : "已暂停" }}</span>
            </label>
            <button type="button" @click="openEditAgent(agent)"><Pencil :size="13" /> 编辑</button>
            <button v-if="!agent.builtin" type="button" class="danger" @click="removeAgent(agent)"><Trash2 :size="13" /></button>
          </div>
        </div>
      </div>

      <div v-if="showAgentForm" class="modal-mask" @click.self="showAgentForm = false">
        <div class="modal">
          <header>
            <b>{{ editingAgentKey ? "编辑 Agent" : "新增配置型 Agent" }}</b>
            <button type="button" @click="showAgentForm = false"><X :size="16" /></button>
          </header>
          <div class="form-row">
            <label>名称（群聊 @ 用）<input v-model="agentForm.name" placeholder="例如：论文助教" :disabled="Boolean(editingAgentKey) && editingAgentIsBuiltin" /></label>
            <label>头衔<input v-model="agentForm.title" placeholder="论文写作助手" /></label>
          </div>
          <label>角色描述<input v-model="agentForm.role_desc" placeholder="帮学生梳理论文结构、润色学术表达" /></label>
          <label>系统提示词
            <textarea
              v-model="agentForm.system_prompt"
              rows="5"
              :disabled="editingAgentIsBuiltin"
              :placeholder="editingAgentIsBuiltin ? '内置 Agent 的提示词由系统内核维护，不可修改' : '你是论文写作助教，擅长开题报告结构、文献综述...'"
            />
          </label>
          <label>能力标签（逗号分隔）<input v-model="agentForm.capabilities" placeholder="论文结构,文献综述" /></label>
          <label class="switch inline">
            <input v-model="agentForm.enabled" type="checkbox" />
            <span>启用（停用后群聊 @ 不再触发回复）</span>
          </label>
          <footer>
            <button type="button" class="ghost-btn" @click="showAgentForm = false">取消</button>
            <button type="button" class="primary-btn" @click="submitAgentForm">保存</button>
          </footer>
        </div>
      </div>
    </section>

    <!-- ===================== Tab 4 路径推荐 ===================== -->
    <section v-if="activeTab === 'paths'" class="tab-panel">
      <div class="card path-card">
        <h3>为「{{ selectedStudentId || "—" }}」编排学习路径</h3>
        <label>路径标题<input v-model="pathForm.title" placeholder="例如：机器学习基础补强路径" /></label>
        <div class="stage-list">
          <div v-for="(stage, i) in pathStages" :key="i" class="stage-row">
            <em>{{ i + 1 }}</em>
            <input v-model="stage.name" placeholder="阶段名称，如：线性回归" />
            <input v-model="stage.desc" placeholder="说明（可选）" />
            <button type="button" class="danger" :disabled="pathStages.length <= 1" @click="removeStage(i)"><Trash2 :size="13" /></button>
          </div>
        </div>
        <button type="button" class="ghost-btn" @click="addStage"><Plus :size="13" /> 添加阶段</button>
        <label>推送附言（写入群聊）<textarea v-model="pathForm.note" rows="2" placeholder="按这个顺序补，两周内完成第一阶段。" /></label>
        <button type="button" class="primary-btn" :disabled="pathSubmitting" @click="submitPath">
          <Loader2 v-if="pathSubmitting" :size="14" class="spin" />
          <Send v-else :size="14" />
          确认并推送到学生路径页 + 群聊
        </button>
        <p class="hint-line">推送后：学生「学习路径」页出现新路径；课程群聊出现路径推荐卡片。</p>
      </div>
    </section>

    <!-- ===================== Tab 5 群聊消息 ===================== -->
    <section v-if="activeTab === 'chat'" class="tab-panel">
      <div class="card chat-panel">
        <div class="chat-panel-head">
          <b>课程群聊 · {{ currentRoomId || "未选择学生" }}</b>
          <button type="button" class="ghost-btn" @click="loadRoomMessages"><RefreshCcw :size="13" /> 刷新</button>
        </div>
        <div class="chat-scroll">
          <div v-if="roomLoading" class="panel-loading"><Loader2 :size="15" class="spin" /> 加载消息...</div>
          <p v-else-if="!roomMessages.length" class="empty-line">房间暂无消息。学生发起 AI 问答、你发送消息/指派资源后都会出现在这里。</p>
          <div v-for="m in roomMessages" :key="m.id" :class="['room-msg', senderClass(m)]">
            <div class="msg-meta">
              <b>{{ m.sender_name || m.sender_id || m.sender_role }}</b>
              <em class="chip">{{ messageTypeLabel[m.message_type] || m.message_type }}</em>
              <small>{{ formatTime(m.created_at) }}</small>
            </div>
            <div class="msg-body">
              <template v-if="m.message_type === 'resource_card'">
                📚 <b>{{ m.payload.title }}</b>（{{ m.payload.type }}）<br />{{ m.content }}
              </template>
              <template v-else-if="m.message_type === 'path_card'">
                🧭 <b>{{ m.payload.title }}</b> · {{ m.payload.stages_count }} 个阶段<br />{{ m.content }}
              </template>
              <template v-else>{{ m.content }}</template>
            </div>
          </div>
        </div>
        <div class="chat-compose">
          <textarea
            v-model="chatDraft"
            rows="2"
            placeholder="以教师身份发送消息；@Agent名称（如 @智灵、@论文助教）可触发智能体协作生成..."
            @keydown.enter.exact.prevent="sendChatMessage"
          />
          <button type="button" class="primary-btn" :disabled="chatSending || !chatDraft.trim()" @click="sendChatMessage">
            <Loader2 v-if="chatSending" :size="14" class="spin" />
            <Send v-else :size="14" />
            发送
          </button>
        </div>
      </div>
    </section>

    <!-- ===================== Tab 知识图谱热力图 ===================== -->
    <section v-if="activeTab === 'knowledge-map'" class="tab-panel">
      <div class="toolbar">
        <p class="hint-line">
          课程知识图谱：每个知识点按班级平均掌握度着色，前置依赖关系以连线展示。
          点击知识点可查看追踪人数、未达标人数和关联错题。
        </p>
        <button type="button" class="ghost-btn" @click="loadKnowledgeMap"><RefreshCcw :size="14" /> 刷新</button>
      </div>

      <div v-if="knowledgeMapLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 正在加载知识图谱...</div>
      <template v-else-if="knowledgeMapData">
        <div class="knowledge-coverage-strip">
          <div>
            <span>课程节点</span><b>{{ knowledgeCoverage.total }}</b><small>个知识点</small>
          </div>
          <div>
            <span>学习证据覆盖</span><b>{{ knowledgeCoverage.ratio }}%</b><small>{{ knowledgeCoverage.tracked }} 个节点已有数据</small>
          </div>
          <div>
            <span>课程关系</span><b>{{ knowledgeCoverage.edges }}</b><small>条前置或关联边</small>
          </div>
          <div class="coverage-meter">
            <span>数据完整度</span>
            <div><i :style="{ width: `${knowledgeCoverage.ratio}%` }" /></div>
            <small>{{ knowledgeCoverage.ratio < 70 ? '学生端仍需补充更多练习与资源行为证据' : '已具备班级教学诊断条件' }}</small>
          </div>
        </div>

        <section class="knowledge-focus-overview" aria-labelledby="knowledge-focus-heading">
          <header>
            <div>
              <h2 id="knowledge-focus-heading">重点节点概览</h2>
              <p>按低掌握度、未达标人数与错题积压综合排序。先看教学优先级，再进入全景关系。</p>
            </div>
            <span>当前需重点关注 {{ priorityKnowledgeNodes.length }} 项</span>
          </header>
          <ol class="knowledge-focus-list">
            <li v-for="(node, index) in priorityKnowledgeNodes" :key="node.id">
              <button type="button" @click="selectedKnowledgeNodeId = node.id">
                <span class="focus-rank">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="focus-copy">
                  <b>{{ node.name }}</b>
                  <small>{{ node.students_below_60 }} 人未达标 · {{ node.open_mistakes }} 道错题</small>
                </span>
                <span class="focus-mastery" :style="{ color: masteryColor(node.avg_mastery) }">
                  {{ node.avg_mastery == null ? '待采集' : `${Math.round(node.avg_mastery * 100)}%` }}
                </span>
                <span class="focus-track" aria-hidden="true">
                  <i :style="{ width: `${node.avg_mastery == null ? 0 : Math.round(node.avg_mastery * 100)}%`, background: masteryColor(node.avg_mastery) }" />
                </span>
              </button>
            </li>
          </ol>
        </section>

        <div class="knowledge-workspace">
          <div class="knowledge-canvas">
            <div class="knowledge-canvas-head">
              <div>
                <h3>课程知识网络</h3>
                <p>默认呈现 16 个高优先级节点。搜索或切换阶段后会展示匹配结果，全景模式可查看完整课程结构。</p>
              </div>
              <div class="knowledge-legend">
                <span><i class="strong" />掌握良好</span>
                <span><i class="watch" />需要关注</span>
                <span><i class="weak" />重点补强</span>
                <span><i class="unknown" />待采集</span>
              </div>
            </div>
            <div class="knowledge-toolrail" aria-label="知识图谱筛选与缩放工具">
              <label class="knowledge-search">
                <Search :size="17" aria-hidden="true" />
                <input v-model="knowledgeQuery" type="search" placeholder="搜索知识点、编号或课程说明" />
              </label>
              <label>
                <span>认知阶段</span>
                <select v-model="knowledgeStageFilter">
                  <option value="all">全部阶段</option>
                  <option v-for="(stage, index) in knowledgeStageNames" :key="stage" :value="String(index)">{{ stage }}</option>
                </select>
              </label>
              <label>
                <span>关系图层</span>
                <select v-model="knowledgeRelationFilter">
                  <option value="prerequisite">仅前置依赖</option>
                  <option value="all">全部关系</option>
                </select>
              </label>
              <div class="knowledge-view-switch" aria-label="图谱视图模式">
                <button type="button" :class="{ active: knowledgeViewMode === 'focus' }" @click="knowledgeViewMode = 'focus'">重点视图</button>
                <button type="button" :class="{ active: knowledgeViewMode === 'full' }" @click="knowledgeViewMode = 'full'">全景视图</button>
              </div>
              <div class="knowledge-zoom" aria-label="缩放图谱">
                <button type="button" aria-label="缩小图谱" :disabled="knowledgeZoom <= 0.75" @click="setKnowledgeZoom(knowledgeZoom - 0.1)"><ZoomOut :size="17" /></button>
                <output aria-live="polite">{{ Math.round(knowledgeZoom * 100) }}%</output>
                <button type="button" aria-label="放大图谱" :disabled="knowledgeZoom >= 1.6" @click="setKnowledgeZoom(knowledgeZoom + 0.1)"><ZoomIn :size="17" /></button>
              </div>
              <button type="button" class="knowledge-reset" @click="resetKnowledgeViewport">重置</button>
            </div>
            <div class="knowledge-canvas-status">
              <span>显示 {{ knowledgeGraphView.nodes.length }} / {{ knowledgeCoverage.total }} 个节点</span>
              <span>{{ knowledgeRelationFilter === 'prerequisite' ? '前置依赖层' : '全部关系层' }}</span>
              <span>可滚动浏览，点击节点查看右侧证据</span>
            </div>
            <div class="knowledge-svg-scroll">
              <div v-if="!knowledgeGraphView.nodes.length" class="knowledge-empty">
                <Search :size="22" />
                <b>没有匹配的知识点</b>
                <span>调整关键词或认知阶段后重试。</span>
                <button type="button" @click="resetKnowledgeViewport">恢复重点视图</button>
              </div>
              <svg
                v-else
                :viewBox="knowledgeGraphView.viewBox"
                :style="{ width: `${knowledgeGraphView.width * knowledgeZoom}px`, height: `${knowledgeGraphView.height * knowledgeZoom}px` }"
                role="img"
                aria-label="人工智能课程知识关系图"
              >
                <defs>
                  <marker id="knowledgeArrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                    <path d="M0,0 L8,4 L0,8 z" fill="#b9aa95" />
                  </marker>
                  <filter id="knowledgeNodeShadow" x="-20%" y="-30%" width="140%" height="170%">
                    <feDropShadow dx="0" dy="3" stdDeviation="3" flood-color="#654321" flood-opacity="0.10" />
                  </filter>
                </defs>
                <g class="knowledge-stage-labels">
                  <text v-for="stage in knowledgeGraphView.stageLabels" :key="stage.label" :x="stage.x" y="20" text-anchor="middle">{{ stage.label }}</text>
                </g>
                <path
                  v-for="edge in knowledgeGraphView.edges"
                  :key="edge.key"
                  :d="edge.path"
                  :class="['knowledge-edge', `relation-${edge.relation}`]"
                  :style="{ opacity: Math.max(0.25, Math.min(0.8, edge.weight)) }"
                  marker-end="url(#knowledgeArrow)"
                />
                <g
                  v-for="node in knowledgeGraphView.nodes"
                  :key="node.id"
                  :class="['knowledge-node', { selected: selectedKnowledgeNode?.id === node.id, unknown: node.avg_mastery == null }]"
                  role="button"
                  tabindex="0"
                  :aria-label="`${node.name}，${knowledgeNodeStatus(node)}`"
                  @click="selectedKnowledgeNodeId = node.id"
                  @keydown.enter="selectedKnowledgeNodeId = node.id"
                  @keydown.space.prevent="selectedKnowledgeNodeId = node.id"
                >
                  <rect :x="node.x" :y="node.y" :width="node.width" :height="node.height" rx="10" :style="{ '--node-color': node.color }" />
                  <circle :cx="node.x + 18" :cy="node.y + 22" r="5" :fill="node.color" />
                  <text :x="node.x + 32" :y="node.y + 26" class="node-title">{{ truncateKnowledgeName(node.name) }}</text>
                  <text :x="node.x + 18" :y="node.y + 51" class="node-metric">
                    {{ node.avg_mastery == null ? '待采集学习证据' : `掌握度 ${Math.round(node.avg_mastery * 100)}% · ${node.students_tracked} 人` }}
                  </text>
                </g>
              </svg>
            </div>
          </div>

          <aside class="knowledge-inspector">
            <template v-if="selectedKnowledgeNode">
              <span class="inspector-status" :style="{ color: masteryColor(selectedKnowledgeNode.avg_mastery) }">{{ knowledgeNodeStatus(selectedKnowledgeNode) }}</span>
              <h3>{{ selectedKnowledgeNode.name }}</h3>
              <p>{{ selectedKnowledgeNode.description || '该节点尚未补充课程说明，可在知识点数据中增加学习目标、先修条件与典型任务。' }}</p>
              <div class="inspector-mastery">
                <div class="mastery-dial large" :style="{ '--mastery': `${selectedKnowledgeNode.avg_mastery == null ? 0 : Math.round(selectedKnowledgeNode.avg_mastery * 100)}%`, '--dial-color': masteryColor(selectedKnowledgeNode.avg_mastery) }">
                  <b>{{ selectedKnowledgeNode.avg_mastery == null ? '—' : Math.round(selectedKnowledgeNode.avg_mastery * 100) }}</b><span>{{ selectedKnowledgeNode.avg_mastery == null ? '' : '%' }}</span>
                </div>
                <div><b>班级平均掌握度</b><span>基于 {{ selectedKnowledgeNode.students_tracked }} 名学生证据</span></div>
              </div>
              <dl>
                <div><dt>未达标学生</dt><dd>{{ selectedKnowledgeNode.students_below_60 }} 人</dd></div>
                <div><dt>未解决错题</dt><dd>{{ selectedKnowledgeNode.open_mistakes }} 道</dd></div>
                <div><dt>认知层级</dt><dd>{{ readableBloomLevel(selectedKnowledgeNode.bloom_level) }}</dd></div>
                <div><dt>学习难度</dt><dd>{{ readableDifficulty(selectedKnowledgeNode.difficulty) }}</dd></div>
              </dl>
            </template>
            <p v-else class="empty-line">选择一个知识点查看详细证据。</p>
          </aside>
        </div>

      </template>
    </section>

    <!-- ===================== Tab 学生对比 ===================== -->
    <section v-if="activeTab === 'compare'" class="tab-panel">
      <div class="toolbar">
        <p class="hint-line">选择 2-6 位学生进行横向对比：掌握度均值、全知识点掌握度向量、错题与活跃度。</p>
        <button type="button" class="ghost-btn" @click="loadStudents"><RefreshCcw :size="14" /> 刷新学生列表</button>
      </div>

      <div class="card">
        <h3>选择对比学生 <small>已选 {{ compareSelectedIds.length }}/6</small></h3>
        <div class="compare-picker">
          <label
            v-for="s in students"
            :key="s.user_id"
            :class="['compare-pick', { active: compareSelectedIds.includes(s.user_id) }]"
          >
            <input
              type="checkbox"
              :checked="compareSelectedIds.includes(s.user_id)"
              @change="toggleCompareStudent(s.user_id)"
            />
            <b>{{ s.display_name }}</b>
            <small>掌握度 {{ s.mastery_avg == null ? '—' : Math.round(s.mastery_avg * 100) + '%' }} · 错题 {{ s.mistakes_open }}</small>
          </label>
        </div>
      </div>

      <div v-if="compareLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 正在对比分析...</div>
      <template v-else-if="compareResult && compareResult.students.length >= 2">
        <div class="kpi-grid">
          <div v-for="s in compareResult.students" :key="s.user_id" class="kpi-card">
            <small>{{ s.user_id }}</small>
            <b>{{ s.mastery_avg != null ? Math.round(s.mastery_avg * 100) + '%' : '—' }}<em> 掌握度</em></b>
            <small>错题 {{ s.mistakes_open }} · 活跃 {{ s.last_active ? formatTime(s.last_active).slice(5, 16) : '—' }}</small>
          </div>
        </div>

        <div class="card">
          <h3>知识点掌握度对比 <small>每列一个学生，按 KP 名称对齐</small></h3>
          <div class="compare-table-wrap">
            <table class="data-table compare-table">
              <thead>
                <tr>
                  <th>知识点</th>
                  <th v-for="s in compareResult.students" :key="s.user_id">{{ s.user_id }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(kpId, ki) in compareResult.kp_ids" :key="kpId">
                  <td class="key-cell">{{ kpId }}</td>
                  <td v-for="s in compareResult.students" :key="s.user_id">
                    <span class="compare-cell" :style="{ background: masteryColor(s.mastery_vector[ki] ?? 0) }">
                      {{ Math.round((s.mastery_vector[ki] ?? 0) * 100) }}%
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="grid-two">
          <div class="card">
            <h3>最薄弱知识点对比</h3>
            <div v-for="s in compareResult.students" :key="s.user_id" class="compare-student-block">
              <b>{{ s.user_id }}</b>
              <div v-for="kp in s.weakest" :key="kp.kp_id" class="mastery-row">
                <span>{{ kp.kp_name }}</span>
                <div class="bar"><i class="low" :style="{ width: `${Math.round(kp.mastery * 100)}%` }" /></div>
                <em>{{ Math.round(kp.mastery * 100) }}%</em>
              </div>
            </div>
          </div>
          <div class="card">
            <h3>已掌握知识点对比</h3>
            <div v-for="s in compareResult.students" :key="s.user_id" class="compare-student-block">
              <b>{{ s.user_id }}</b>
              <div v-for="kp in s.strongest" :key="kp.kp_id" class="mastery-row">
                <span>{{ kp.kp_name }}</span>
                <div class="bar"><i :style="{ width: `${Math.round(kp.mastery * 100)}%` }" /></div>
                <em>{{ Math.round(kp.mastery * 100) }}%</em>
              </div>
            </div>
          </div>
        </div>
      </template>
      <p v-else-if="compareSelectedIds.length < 2" class="empty-line">请至少选择 2 位学生进行对比。</p>
    </section>

    <!-- ===================== Tab 干预日志 ===================== -->
    <section v-if="activeTab === 'interventions'" class="tab-panel">
      <div class="toolbar">
        <p class="hint-line">
          教师干预 Impact Loop：一键发起干预 · 追踪响应状态 · 支持批量目标。
          <template v-if="interventionLog">
            近 {{ interventionLog.days }} 天共 {{ interventionLog.total_interventions }} 次干预，学生已响应 {{ interventionLog.total_responded }} 次。
          </template>
        </p>
        <button type="button" class="ghost-btn" @click="loadInterventions"><RefreshCcw :size="14" /> 刷新日志</button>
      </div>

      <!-- ============ 一键干预面板 · 3 类真实 API ============ -->
      <div class="card quick-intervention-card">
        <div class="qi-head">
          <div>
            <h3><Sparkles :size="16" /> 一键干预面板</h3>
            <small>选择学生 → 选动作 → 一键触达。所有操作会计入干预日志并同步到师生群聊。</small>
          </div>
          <div class="qi-mode-switch" role="tablist" aria-label="干预类型">
            <button
              v-for="m in [
                { key: 'message', label: '发消息', icon: MessageSquare },
                { key: 'resource', label: '推资源', icon: BookOpen },
                { key: 'path', label: '推路径', icon: RouteIcon },
              ]"
              :key="m.key"
              type="button"
              role="tab"
              :aria-selected="quickMode === m.key"
              :class="['qi-mode-btn', { active: quickMode === m.key }]"
              @click="quickMode = m.key as InterventionMode"
            >
              <component :is="m.icon" :size="13" />
              {{ m.label }}
            </button>
          </div>
        </div>

        <!-- 目标学生选择 -->
        <div class="qi-target-row">
          <label class="qi-label">目标学生 <em>{{ quickTargets.length }} 名</em></label>
          <div class="qi-target-chips">
            <button
              v-for="s in students"
              :key="s.user_id"
              type="button"
              :class="['qi-target-chip', { active: quickTargets.includes(s.user_id) }]"
              @click="() => {
                const i = quickTargets.indexOf(s.user_id);
                if (i >= 0) quickTargets.splice(i, 1);
                else if (quickTargets.length < 20) quickTargets.push(s.user_id);
                else showNotice('单次最多 20 名学生');
              }"
            >
              {{ s.display_name }}
              <em v-if="s.mastery_avg != null" class="qi-target-meta">{{ Math.round(s.mastery_avg * 100) }}%</em>
            </button>
            <button
              v-if="students.length"
              type="button"
              class="qi-target-quick"
              @click="() => {
                if (!classData) return;
                const risks = classData.risk_students.map((r) => r.user_id);
                quickTargets = [...new Set([...quickTargets, ...risks])].slice(0, 20);
              }"
            >+ 全部高风险学生</button>
            <button
              v-if="quickTargets.length"
              type="button"
              class="qi-target-quick clear"
              @click="quickTargets = []"
            >清空</button>
          </div>
        </div>

        <!-- Mode: message -->
        <div v-if="quickMode === 'message'" class="qi-form">
          <label class="qi-label">消息内容</label>
          <textarea
            v-model="quickMessage"
            rows="3"
            placeholder="例：同学你好，最近看到你在多智能体系统上有明显进步…"
          ></textarea>
          <div class="qi-templates">
            <small class="qi-templates-label">话术模板：</small>
            <button
              v-for="t in MESSAGE_TEMPLATES"
              :key="t.key"
              type="button"
              class="qi-template-chip"
              @click="applyMessageTemplate(t)"
            >{{ t.label }}</button>
            <button type="button" class="qi-ai-btn" :disabled="quickSending" @click="draftMessageWithAI">
              <Sparkles :size="12" /> 让 Copilot 起草
            </button>
          </div>
        </div>

        <!-- Mode: resource -->
        <div v-if="quickMode === 'resource'" class="qi-form">
          <label class="qi-label">选择资源</label>
          <select v-model="quickResourceId">
            <option value="">— 从资源库选择 —</option>
            <option v-for="r in resources" :key="r.id" :value="r.id">
              {{ r.title }} ({{ r.type }})
            </option>
          </select>
          <p v-if="!resources.length" class="qi-empty-hint">资源列表为空，请先到「教学资源」页发布资源。</p>
          <label class="qi-label">附言（可选）</label>
          <textarea
            v-model="quickResourceNote"
            rows="2"
            placeholder="例：这份笔记是针对你上次错题的补强，建议今天完成"
          ></textarea>
        </div>

        <!-- Mode: path -->
        <div v-if="quickMode === 'path'" class="qi-form">
          <label class="qi-label">路径标题</label>
          <input v-model="quickPathTitle" placeholder="例：MAS 补强 3 步走" />
          <label class="qi-label">阶段（用逗号或换行分隔）</label>
          <textarea
            v-model="quickPathStages"
            rows="3"
            placeholder="第 1 步：概念回顾&#10;第 2 步：核心练习 5 题&#10;第 3 步：综合应用"
          ></textarea>
        </div>

        <!-- 提交行 -->
        <div class="qi-submit-row">
          <small v-if="quickTargets.length" class="qi-submit-hint">
            将向 <b>{{ quickTargets.length }}</b> 名学生同时发送
          </small>
          <small v-else class="qi-submit-hint muted">请先选择目标学生</small>
          <button
            type="button"
            class="primary-btn"
            :disabled="quickSending || !quickTargets.length"
            @click="runQuickIntervention"
          >
            <Loader2 v-if="quickSending" :size="14" class="spin" />
            <Send v-else :size="14" />
            {{ quickMode === 'message' ? '发送消息' : quickMode === 'resource' ? '推送资源' : '推送路径' }}
          </button>
        </div>
      </div>

      <div v-if="interventionLoading" class="panel-loading"><Loader2 :size="16" class="spin" /> 正在加载干预日志...</div>
      <template v-else-if="interventionLog && interventionLog.students.length">
        <div v-for="s in interventionLog.students" :key="s.user_id" class="card intervention-card">
          <div class="intervention-head">
            <div>
              <b>{{ s.user_id }}</b>
              <small>
                共 {{ s.total }} 次干预 · 资源 {{ s.resource_count }} · 路径 {{ s.path_count }} · 消息 {{ s.message_count }}
              </small>
            </div>
            <div class="intervention-response">
              <em :class="['resp-badge', s.responded > 0 ? 'good' : 'bad']">
                已响应 {{ s.responded }} / {{ s.total }}
              </em>
              <span v-if="s.not_responded" class="resp-rate">
                响应率 {{ Math.round((s.responded / s.total) * 100) }}%
              </span>
            </div>
          </div>
          <div class="intervention-timeline">
            <div v-for="entry in s.recent" :key="entry.id" :class="['timeline-item', { responded: entry.responded }]">
              <em class="chip">{{ interventionTypeLabel[entry.type] || entry.type }}</em>
              <span class="timeline-content">{{ entry.content }}</span>
              <small>{{ formatTime(entry.created_at) }}</small>
              <em :class="['resp-tag', entry.responded ? 'good' : 'bad']">
                {{ entry.responded ? '已响应' : '未响应' }}
              </em>
            </div>
          </div>
        </div>
      </template>
      <p v-else class="empty-line">近 30 天暂无教师干预记录。推荐资源、推送路径或发送消息后会自动记录。</p>
    </section>

    <transition name="notice-fade">
      <div v-if="notice" class="teacher-notice" role="status">{{ notice }}</div>
    </transition>
  </div>
</template>

<style scoped lang="scss">
/* ============================================================
 * 教师管理台 · TeacherView v2（2026-07-11）
 * 规范：Material Design 3 + ui-ux-pro-max 交付清单
 * 品牌：教师端采用更深 #d9480f（沉稳），与学生端 #ea5a1a 区分
 * ============================================================ */
.teacher-view {
  /* ---- Design Tokens（收敛到 4 灰阶 + 1 品牌色系） ---- */
  --tv-ink: #1a1d21;          /* on-surface，最强文本 */
  --tv-ink-2: #45505c;        /* on-surface-variant strong */
  --tv-muted: #6b7480;        /* on-surface-variant，对白底 5.5:1 */
  --tv-faint: #98a1ab;        /* 装饰性小注 */
  --tv-line: #e8e4dc;         /* outline-variant 轻线 */
  --tv-line-2: #d6d0c4;       /* outline 强线 */
  --tv-bg: #f7f5f0;           /* surface-container，略暖纸底 */
  --tv-panel: #ffffff;        /* surface */
  --tv-panel-2: #fbf9f4;      /* surface-dim 卡内子面 */

  --tv-brand: #F97316;        /* MD3 Primary（教学工作台品牌橙） */
  --tv-brand-hover: #EA580C;
  --tv-brand-ink: #C2410C;    /* on-primary-container，对 #FFF3E8 对比 5.5:1 */
  --tv-brand-soft: #FFF3E8;   /* MD3 Primary Container */
  --tv-brand-line: #FDBA74;   /* Primary Container border */

  /* MD3 AI Accent（辅助紫，用于 AI 洞察面 & Copilot） */
  --tv-ai: #7C5CFC;
  --tv-ai-hover: #6B4CE3;
  --tv-ai-ink: #5B3FE0;
  --tv-ai-soft: #F5F1FF;      /* AI Container */
  --tv-ai-line: #D8CCFB;

  --tv-ok: #16A34A;
  --tv-ok-soft: #ECFDF3;
  --tv-warn: #F59E0B;
  --tv-warn-soft: #FEF7E6;
  --tv-err: #DC2626;
  --tv-err-soft: #FEF2F2;
  --tv-info: #2563EB;
  --tv-info-soft: #EFF6FF;

  /* MD3 elevation 柔化 */
  --tv-elev-0: none;
  --tv-elev-1: 0 1px 2px rgba(20, 24, 28, 0.05), 0 8px 24px -20px rgba(20, 24, 28, 0.12);
  --tv-elev-2: 0 2px 4px rgba(20, 24, 28, 0.06), 0 20px 40px -22px rgba(20, 24, 28, 0.16);

  /* 动效 */
  --tv-ease: cubic-bezier(0.2, 0, 0, 1);
  --tv-dur: 220ms;

  /* Shape scale */
  --tv-r-lg: 20px;
  --tv-r-md: 16px;
  --tv-r-sm: 12px;
  --tv-r-xs: 8px;

  display: flex;
  flex-direction: column;
  gap: 24px;
  width: min(1480px, calc(100vw - 56px));
  max-width: 1480px;
  margin: 0 auto;
  padding: 12px 0 48px;
  color: var(--tv-ink);
}

/* ============================================================
 * MD3 App Bar：单一标题栏 · 面包屑徽章 + Headline + 主动作
 * ============================================================ */
.teacher-appbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px 24px 22px;
  border-radius: var(--tv-r-lg);
  border: 1px solid var(--tv-line);
  background:
    radial-gradient(600px 220px at 6% -30%, rgba(217, 72, 15, 0.06), transparent 65%),
    linear-gradient(180deg, #ffffff 0%, #fbf9f4 100%);
  box-shadow: var(--tv-elev-1);
}

.teacher-appbar-crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--tv-muted);
  letter-spacing: 0.02em;
}

.crumb-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  font-weight: 600;
  font-size: 11.5px;
}

.crumb-sep {
  color: var(--tv-faint);
}

.crumb-teacher {
  font-weight: 600;
  color: var(--tv-ink-2);
}

.teacher-appbar-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.teacher-appbar-title {
  min-width: 0;
  flex: 1;

  h1 {
    margin: 0;
    font-size: clamp(22px, 2vw, 26px);
    line-height: 1.2;
    font-weight: 750;
    letter-spacing: -0.02em;
    color: var(--tv-ink);
    text-wrap: balance;
  }

  p {
    margin: 6px 0 0;
    max-width: 72ch;
    font-size: 13.5px;
    line-height: 1.7;
    color: var(--tv-muted);
    text-wrap: pretty;
  }
}

.appbar-action {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  min-height: 44px;
  border-radius: 999px;
  border: 1px solid var(--tv-line-2);
  background: var(--tv-panel);
  color: var(--tv-ink-2);
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  transition: border-color var(--tv-dur) var(--tv-ease), color var(--tv-dur) var(--tv-ease), background var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease);
}

.appbar-action:hover {
  border-color: var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  transform: translateY(-1px);
  box-shadow: var(--tv-elev-1);
}

.appbar-action:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.28);
}

/* ============================================================
 * MD3 Primary Tab：底部 3px 品牌指示条 + hover state layer
 * ============================================================ */
.teacher-tabs {
  position: relative;
  display: flex;
  gap: 4px;
  padding: 0 4px;
  border-bottom: 1px solid var(--tv-line);
  overflow-x: auto;
  scrollbar-width: none;
}

.teacher-tabs::-webkit-scrollbar {
  display: none;
}

.tab-btn {
  position: relative;
  flex: none;
  padding: 0;
  min-height: 48px;             /* MD3 tab height */
  min-width: 90px;
  border: none;
  background: transparent;
  color: var(--tv-muted);
  font-size: 13.5px;
  font-weight: 550;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: color var(--tv-dur) var(--tv-ease);
}

.tab-btn .tab-inner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px 14px;
  border-radius: var(--tv-r-sm) var(--tv-r-sm) 0 0;
  transition: background var(--tv-dur) var(--tv-ease);
}

/* MD3 state layer on hover */
.tab-btn:hover:not(.active) {
  color: var(--tv-ink-2);
}

.tab-btn:hover:not(.active) .tab-inner {
  background: rgba(217, 72, 15, 0.06);
}

.tab-btn:focus-visible {
  outline: none;
}

.tab-btn:focus-visible .tab-inner {
  background: rgba(217, 72, 15, 0.1);
  box-shadow: inset 0 0 0 2px rgba(217, 72, 15, 0.35);
}

.tab-btn.active {
  color: var(--tv-brand);
  font-weight: 700;
}

.tab-btn.active .tab-inner {
  background: var(--tv-brand-soft);
}

/* 3px 底部 indicator：MD3 Primary Tab 关键特征 */
.tab-btn .tab-indicator {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: -1px;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: transparent;
  transition: background var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease);
  transform: scaleX(0.4);
}

.tab-btn.active .tab-indicator {
  background: var(--tv-brand);
  transform: scaleX(1);
}

/* ============================================================
 * 学生选择条：sticky 玻璃条 · 切 Tab 后仍带上下文
 * ============================================================ */
.student-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: var(--tv-r-md);
  border: 1px solid var(--tv-line);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px) saturate(1.3);
  -webkit-backdrop-filter: blur(14px) saturate(1.3);
  box-shadow: var(--tv-elev-1);
  font-size: 13px;
  color: var(--tv-ink-2);
}

.student-bar-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  border: 1px solid var(--tv-brand-line);
  flex-shrink: 0;
}

.student-bar-label {
  font-weight: 600;
  color: var(--tv-ink-2);
  flex-shrink: 0;
}

.student-bar-select {
  flex: 1;
  min-width: 280px;
  max-width: 520px;
  height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--tv-line-2);
  background: var(--tv-panel);
  color: var(--tv-ink);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease);
}

.student-bar-select:hover {
  border-color: var(--tv-brand-line);
}

.student-bar-select:focus-visible {
  outline: none;
  border-color: var(--tv-brand);
  box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.18);
}

.student-bar-loading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-style: normal;
  font-size: 12px;
  color: var(--tv-muted);
  flex-shrink: 0;
}

/* ============================================================
 * 无障碍：动效偏好
 * ============================================================ */
@media (prefers-reduced-motion: reduce) {
  .teacher-view *,
  .teacher-view *::before,
  .teacher-view *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

.tab-panel { display: flex; flex-direction: column; gap: 20px; }

// ---- 教学共创 ----
.copilot-panel { gap: 16px; }

.copilot-intro,
.copilot-form-head,
.copilot-result-head,
.copilot-submit-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.copilot-intro {
  h2 { margin: 0; color: #1f2937; font-size: 18px; }
  p { margin: 5px 0 0; color: #64748b; font-size: 12.5px; line-height: 1.65; max-width: 74ch; }
}

.copilot-actions {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.copilot-action {
  min-height: 96px;
  padding: 12px 14px;
  border: 1px solid #e7e0d4;
  border-radius: 10px;
  background: #fff;
  color: #475569;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, color 0.16s ease;

  b, span, em { display: block; }
  b { color: #1f2937; font-size: 13.5px; }
  span { margin-top: 5px; color: #64748b; font-size: 12px; line-height: 1.45; }
  em { margin-top: 7px; color: #9a5c16; font-size: 11px; font-style: normal; }

  &:hover { border-color: #e6ad7b; background: #fffaf5; }
  &.active { border-color: #e8590c; background: #fff7f0; }
  &.active b, &.active em { color: #c2410c; }
}

.copilot-workbench { display: flex; flex-direction: column; gap: 14px; }

.copilot-form-head {
  h3 { margin: 0; }
  p { margin: 5px 0 0; color: #64748b; font-size: 12px; }
}

.data-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  padding: 4px 8px;
  border-radius: 999px;
  background: #f3efe6;
  color: #6b7280;
  font-size: 11px;
}

.copilot-controls {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;

  label, .copilot-instruction {
    display: flex;
    flex-direction: column;
    gap: 5px;
    color: #475569;
    font-size: 12px;
    font-weight: 650;
  }

  select, textarea {
    width: 100%;
    box-sizing: border-box;
    border: 1px solid #ddd5c8;
    border-radius: 8px;
    background: #fff;
    color: #1f2937;
    font: inherit;
  }

  select { height: 34px; padding: 0 9px; }
}

.copilot-instruction {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: #475569;
  font-size: 12px;
  font-weight: 650;

  small { color: #8a94a3; font-size: 11px; font-weight: 400; }
  textarea {
    box-sizing: border-box;
    width: 100%;
    padding: 9px 10px;
    resize: vertical;
    border: 1px solid #ddd5c8;
    border-radius: 8px;
    background: #fff;
    color: #1f2937;
    font: inherit;
    font-size: 13px;
    line-height: 1.55;
  }
}

.copilot-submit-row {
  align-items: center;
  padding-top: 2px;
  border-top: 1px solid #f0e9dc;

  p { margin: 0; color: #8a94a3; font-size: 11.5px; line-height: 1.5; }
}

.copilot-result {
  display: flex;
  flex-direction: column;
  gap: 12px;

  h3 { margin-bottom: 4px; }
  p { margin: 0; color: #64748b; font-size: 12px; }
}

.agent-run-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 9px 10px;
  border-radius: 8px;
  background: #f8fafc;

  span {
    padding: 2px 7px;
    border-radius: 999px;
    background: #e9f7ef;
    color: #167344;
    font-size: 11px;
    &.failed { background: #fef2f2; color: #b91c1c; }
  }
}

.grid-two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

/* MD3 elevation-1 卡片：hover 升 elevation-2；子面 elevation-0 */
.card {
  padding: 24px;
  border-radius: var(--tv-r-md);
  border: 1px solid var(--tv-line);
  background: var(--tv-panel);
  box-shadow: var(--tv-elev-1);
  transition: box-shadow var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease);

  &:hover {
    box-shadow: var(--tv-elev-2);
    border-color: var(--tv-line-2);
  }

  h3 {
    margin: 0 0 18px;
    font-size: 16px;
    line-height: 1.4;
    font-weight: 650;
    letter-spacing: -0.01em;
    color: var(--tv-ink);
    display: flex;
    align-items: baseline;
    gap: 8px;
    small { color: var(--tv-muted); font-weight: 450; font-size: 12px; letter-spacing: 0; }
  }
}

.panel-loading {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #6b7280;
  font-size: 13px;
  padding: 18px;
}

.empty-line { color: #9ca3af; font-size: 12.5px; margin: 4px 0; }
.hint-line { color: #8a94a3; font-size: 12px; margin: 0; flex: 1; }

.risk-list {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 7px;

  li {
    display: flex; align-items: center; gap: 7px;
    font-size: 12.5px; padding: 8px 10px; border-radius: 8px;
    &.high { background: #fef2f2; color: #b91c1c; }
    &.medium { background: #fffbeb; color: #b45309; }
    &.low { background: #f0f9ff; color: #0369a1; }
  }
}

.mastery-cols {
  display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
  b { font-size: 12px; color: #6b7280; display: block; margin-bottom: 6px; }
}

.mastery-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 70px 36px;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  margin-bottom: 5px;

  span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar {
    height: 6px; background: #f1ede4; border-radius: 99px; overflow: hidden;
    i { display: block; height: 100%; background: #34a06b; border-radius: 99px; }
    i.low { background: #e8590c; }
  }
  em { font-style: normal; color: #6b7280; font-size: 11px; text-align: right; }
}

.insight-mastery-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.insight-mastery-list .mastery-row {
  grid-template-columns: minmax(0, 1.4fr) minmax(80px, 1fr) 90px;
}
.insight-forecast {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.8;
  color: #4b5563;
  white-space: pre-wrap;
}
.insight-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

// ---- 班级看板 KPI 条：Display 数字 + 品牌进度带 + 8pt 呼吸 ----
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  padding: 6px 0;
  border: 1px solid var(--tv-line);
  border-radius: var(--tv-r-md);
  background:
    linear-gradient(180deg, rgba(255, 246, 236, 0.55) 0%, rgba(255, 255, 255, 0.85) 100%),
    #fff;
  backdrop-filter: blur(14px) saturate(1.15);
  box-shadow: var(--tv-elev-1);
  overflow: hidden;
  position: relative;
}

/* 顶部 3px 品牌进度带 */
.kpi-grid::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--tv-brand), #f59e0b);
}

.kpi-card {
  position: relative;
  padding: 22px 26px 24px;
  border: 0;
  border-right: 1px solid var(--tv-line);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: background var(--tv-dur) var(--tv-ease);

  &:last-child { border-right: 0; }

  &:hover {
    background: rgba(255, 244, 232, 0.4);
  }

  small {
    color: var(--tv-muted);
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0.02em;
  }

  b {
    font-size: 32px;
    line-height: 1.05;
    font-weight: 750;
    letter-spacing: -0.03em;
    color: var(--tv-ink);
    font-variant-numeric: tabular-nums;

    em {
      font-style: normal;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0;
      color: var(--tv-muted);
      margin-left: 4px;
    }
  }
}

.profile-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 22px;
}

.profile-fact {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 14px;
  min-height: 58px;
  padding: 11px 0;
  border-bottom: 1px solid #eee7dc;

  &:nth-last-child(-n + 2) { border-bottom-color: transparent; }
  &.risk .profile-fact-label { color: #a84634; }
  &.ability .profile-fact-label { color: #2f7c55; }
  &.preference .profile-fact-label { color: #805a9e; }
  > div { min-width: 0; }
  b { display: block; color: #25313f; font-size: 12.5px; font-weight: 650; line-height: 1.55; }
}

.profile-fact-label {
  color: #7c5b3c;
  font-size: 11.5px;
  font-weight: 650;
}

.profile-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 7px;

  em {
    padding: 2px 7px;
    border-radius: 999px;
    background: #f4f1eb;
    color: #5d6672;
    font-size: 10.5px;
    font-style: normal;
  }
}

.path-compact-list,
.resource-usage-list {
  display: flex;
  flex-direction: column;
}

.path-compact-row,
.resource-usage-row {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 10px 0;
  border-bottom: 1px solid #eee7dc;

  &:last-child { border-bottom: 0; }
  > div:not(.path-progress) { flex: 1; min-width: 0; }
  b { display: block; color: #2c3745; font-size: 12.5px; line-height: 1.45; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  span, small { display: block; margin-top: 3px; color: #7d8795; font-size: 11px; }
}

.path-progress {
  --progress: 0%;
  flex: none;
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 50%;
  background: conic-gradient(#d86628 var(--progress), #eee8df 0);
  position: relative;

  &::after { content: ""; position: absolute; inset: 5px; border-radius: 50%; background: #fff; }
  b { position: relative; z-index: 1; color: #374151; font-size: 10px; }
}

.resource-type-mark {
  flex: none;
  display: grid !important;
  place-items: center;
  width: 66px;
  min-height: 28px;
  margin: 0 !important;
  border-radius: 7px;
  background: #f7eee5;
  color: #9a4c1f !important;
  font-size: 10.5px !important;
  font-weight: 650;
}

.weak-signal-list { display: flex; flex-direction: column; }

.weak-signal-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 52px auto;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #eee7dc;

  &:last-child { border-bottom: 0; }
  button {
    padding: 5px 9px;
    border: 1px solid #ddd3c5;
    border-radius: 7px;
    background: #fff;
    color: #5f6670;
    font-size: 11px;
    cursor: pointer;
    &:hover { border-color: #d86628; color: #bd4a16; background: #fffaf6; }
  }
}

.weak-rank { color: #a08d79; font: 650 11px/1 var(--mono); }
.weak-signal-main {
  min-width: 0;
  b { display: block; color: #26313e; font-size: 12.5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  span { display: block; margin-top: 4px; color: #7d8795; font-size: 10.5px; }
}

.mastery-dial {
  --mastery: 0%;
  --dial-color: #cbd5e1;
  position: relative;
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: conic-gradient(var(--dial-color) var(--mastery), #eee9e1 0);

  &::after { content: ""; position: absolute; inset: 5px; border-radius: 50%; background: #fff; }
  b, span { position: relative; z-index: 1; }
  b { color: #26313e; font-size: 12px; line-height: 1; }
  span { position: absolute; left: 30px; top: 22px; color: #8a94a3; font-size: 8px; }
  &.large { width: 72px; height: 72px; }
  &.large::after { inset: 7px; }
  &.large b { font-size: 17px; }
  &.large span { left: 46px; top: 34px; font-size: 9px; }
}

.error-composition {
  display: grid;
  grid-template-columns: 154px minmax(0, 1fr);
  align-items: center;
  gap: 24px;
  min-height: 210px;
}

.donut-chart {
  position: relative;
  width: 146px;
  height: 146px;
  border-radius: 50%;
  transform: rotate(-35deg);

  &::after { content: ""; position: absolute; inset: 20px; border-radius: 50%; background: #fff; }
  > div { position: absolute; inset: 20px; z-index: 1; display: grid; place-content: center; text-align: center; transform: rotate(35deg); }
  b { color: #202b37; font-size: 25px; line-height: 1; letter-spacing: -0.03em; }
  span { margin-top: 6px; color: #7d8795; font-size: 10px; }
}

.chart-legend-list {
  margin: 0;
  padding: 0;
  list-style: none;

  li { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto 38px; align-items: center; gap: 9px; padding: 7px 0; border-bottom: 1px solid #f0ebe3; }
  li:last-child { border-bottom: 0; }
  i { width: 7px; height: 7px; border-radius: 50%; }
  span { color: #4b5563; font-size: 11.5px; }
  b { color: #25313f; font-size: 11px; }
  em { color: #8a94a3; font-size: 10.5px; font-style: normal; text-align: right; }
}

.activity-stack,
.mastery-stack {
  display: flex;
  width: 100%;
  height: 12px;
  margin: 8px 0 20px;
  overflow: hidden;
  border-radius: 999px;
  background: #eee9e1;

  span { min-width: 0; }
}

.activity-state-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;

  details { padding: 12px; border-radius: 10px; background: #f8faf8; }
  details.warn { background: #fff9ef; }
  details.danger { background: #fff5f2; }
  summary { display: grid; grid-template-columns: 8px minmax(0, 1fr) auto; align-items: center; gap: 7px; cursor: pointer; list-style: none; }
  summary i { width: 7px; height: 7px; border-radius: 50%; }
  summary span { color: #25313f; font-size: 11px; }
  summary span b { font-size: 18px; line-height: 1; }
  summary em { color: #5f6874; font-size: 10.5px; font-style: normal; }
  summary small { grid-column: 2; color: #8a94a3; font-size: 10px; }
  p { margin: 9px 0 0; color: #667085; font-size: 10.5px; line-height: 1.6; word-break: break-all; }
}

.mastery-bucket-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;

  > div { display: grid; grid-template-columns: 7px 1fr; gap: 4px 7px; padding: 10px; border-radius: 9px; background: #faf9f7; }
  i { width: 7px; height: 7px; margin-top: 4px; border-radius: 50%; }
  span { color: #5e6874; font-size: 10.5px; }
  b { grid-column: 2; color: #26313e; font-size: 14px; }
  em { grid-column: 2; color: #8a94a3; font-size: 10px; font-style: normal; }
}

.trend-chart-wrap { position: relative; }
.chart-key { display: flex; justify-content: flex-end; gap: 16px; margin-bottom: 2px; }
.chart-key span { display: inline-flex; align-items: center; gap: 6px; color: #6b7280; font-size: 10.5px; }
.chart-key span::before { content: ""; width: 14px; height: 2px; border-radius: 99px; background: #2f8f5b; }
.chart-key .score-key::before { background: #d86628; }
.trend-chart-wrap svg { display: block; width: 100%; min-height: 210px; overflow: visible; }
.chart-grid-lines line { stroke: #ebe6de; stroke-width: 1; stroke-dasharray: 4 5; }
.activity-line, .score-line { fill: none; stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
.activity-line { stroke: #2f8f5b; }
.score-line { stroke: #d86628; }
.activity-dot { fill: #2f8f5b; stroke: #fff; stroke-width: 2; }
.score-dot { fill: #d86628; stroke: #fff; stroke-width: 2; }
.chart-x-labels text { fill: #89919b; font-size: 10px; }
.trend-latest { display: flex; gap: 20px; justify-content: flex-end; margin-top: -3px; color: #7d8795; font-size: 10.5px; }
.trend-latest b { color: #25313f; font-size: 12px; }

.priority-panel {
  padding: 15px 16px 16px;
  border: 1px solid #e7e0d4;
  border-radius: 12px;
  background: #fffdf9;
}

.priority-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;

  h2 { margin: 0; color: #1f2937; font-size: 15px; }
  p { margin: 4px 0 0; color: #64748b; font-size: 12px; line-height: 1.55; }
}

.priority-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.priority-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #ece5d9;
  border-radius: 9px;
  background: #fff;

  div { min-width: 0; }
  b { display: block; color: #334155; font-size: 12.5px; line-height: 1.4; }
  p { margin: 4px 0 0; color: #64748b; font-size: 11.5px; line-height: 1.45; }
  button {
    flex: none;
    padding: 5px 8px;
    border: 1px solid #ddd5c8;
    border-radius: 7px;
    background: #fff;
    color: #4b5563;
    font-size: 11.5px;
    cursor: pointer;
    white-space: nowrap;
    &:hover { border-color: #e8590c; color: #c2410c; }
  }
  &.danger { background: #fffafa; border-color: #f2d4d0; }
  &.warning { background: #fffdf7; border-color: #eadfc6; }
}

.weak-kp-list { display: flex; flex-direction: column; gap: 6px; }

.weak-kp-row {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(70px, 0.8fr) minmax(150px, auto) 58px;
  align-items: center;
  gap: 7px;
  font-size: 12px;

  span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar {
    height: 6px; background: #f1ede4; border-radius: 99px; overflow: hidden;
    i { display: block; height: 100%; background: #34a06b; border-radius: 99px; }
    i.low { background: #e8590c; }
  }
  em { font-style: normal; color: #6b7280; font-size: 11px; text-align: right; }
  button {
    padding: 3px 8px; border-radius: 6px; font-size: 11.5px;
    border: 1px solid #ddd5c8; background: #fff; color: #4b5563; cursor: pointer;
    white-space: nowrap;
    &:hover { border-color: #e8590c; color: #e8590c; }
  }
}

.activity-row {
  details { border-bottom: 1px dashed #eee6d8; padding: 4px 0; }
  details:last-child { border-bottom: none; }
  summary {
    display: grid;
    grid-template-columns: minmax(120px, 0.8fr) minmax(80px, 1fr) 50px;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    cursor: pointer;
    list-style: none;

    .bar {
      height: 6px; background: #f1ede4; border-radius: 99px; overflow: hidden;
      i { display: block; height: 100%; background: #34a06b; border-radius: 99px; }
      i.warn { background: #d9a406; }
      i.danger { background: #dc2626; }
    }
    em { font-style: normal; color: #6b7280; font-size: 11px; text-align: right; }
  }
  .act-names {
    margin: 6px 0 4px;
    font-size: 12px;
    color: #6b7280;
    line-height: 1.7;
    word-break: break-all;
  }
}

.risk-student-list { display: flex; flex-direction: column; gap: 8px; }

.risk-student-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #faf7f0;

  .risk-main {
    flex: 1; min-width: 0;
    display: flex; flex-direction: column; gap: 2px;
    b { font-size: 12.5px; }
    small { color: #8a94a3; font-size: 11.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  }
}

.risk-row-actions {
  display: flex;
  gap: 5px;
  flex: none;

  button {
    padding: 4px 9px; border-radius: 6px; font-size: 12px;
    border: 1px solid #ddd5c8; background: #fff; color: #4b5563; cursor: pointer;
    white-space: nowrap;
    &:hover { border-color: #e8590c; color: #e8590c; }
  }
}

.risk-badge {
  font-style: normal;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
  &.high { background: #fef2f2; color: #b91c1c; }
  &.medium { background: #fffbeb; color: #b45309; }
  &.low { background: #f0f9ff; color: #0369a1; }
}

.trend-list { max-height: 240px; overflow-y: auto; padding-right: 4px; }

.mini-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px;
  td { padding: 5px 8px; border-bottom: 1px dashed #eee6d8; }
  .key-cell { color: #8a5a2a; white-space: nowrap; width: 120px; }
}

.plain-list {
  margin: 0; padding: 0; list-style: none;
  display: flex; flex-direction: column; gap: 7px;
  font-size: 12.5px; color: #374151;
  b { font-weight: 700; }
}

.chip {
  display: inline-block;
  font-style: normal;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  background: #f3efe6;
  color: #6b7280;
  &.published { background: #e8f6ee; color: #157347; }
  &.draft { background: #fff4e0; color: #a16207; }
  &.archived { background: #f3f4f6; color: #6b7280; }
}
.teacher-chip { background: #fdeee2; color: #c2410c; }

.studio-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.9fr);
  gap: 24px;
  align-items: center;
  padding: 20px 22px;
  border: 1px solid #ead7c4;
  border-radius: 14px;
  background: linear-gradient(115deg, #fffaf5 0%, #fff 72%);
}

.studio-intro-copy {
  > span { color: #c2410c; font-size: 11px; font-weight: 750; letter-spacing: 0.08em; }
  h2 { margin: 6px 0 7px; color: #1f2937; font-size: 20px; line-height: 1.35; }
  p { margin: 0; max-width: 68ch; color: #64748b; font-size: 12.5px; line-height: 1.7; }
}

.studio-flow {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 10px;
    border: 1px solid #ead7c4;
    border-radius: 8px;
    background: #fff;
  }
  b { color: #c2410c; font-size: 11px; }
  span { color: #475569; font-size: 12px; }
}

.toolbar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
  input {
    height: 34px; padding: 0 12px; border-radius: 8px;
    border: 1px solid #ddd5c8; min-width: 220px; background: #fff;
  }
  select {
    height: 34px; padding: 0 8px; border-radius: 8px;
    border: 1px solid #ddd5c8; background: #fff;
  }
}

/* MD3 Buttons：Outlined + Filled，44px 触控高度（skill CRITICAL） */
.ghost-btn, .primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease), color var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease);
}

.ghost-btn {
  border: 1px solid var(--tv-line-2);
  background: var(--tv-panel);
  color: var(--tv-ink-2);
}
.ghost-btn:hover {
  border-color: var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}
.ghost-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.24);
}

.primary-btn {
  border: 0;
  background: var(--tv-brand);
  color: #fff;
  font-weight: 650;
  letter-spacing: 0.01em;

  &:hover:not(:disabled) {
    background: var(--tv-brand-hover);
    transform: translateY(-1px);
    box-shadow: 0 10px 20px -12px rgba(217, 72, 15, 0.5);
  }
  &:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.35);
  }
  &:active:not(:disabled) {
    transform: translateY(0);
    box-shadow: none;
  }
  &:disabled { opacity: 0.45; cursor: not-allowed; }
}

.data-table {
  width: 100%; border-collapse: collapse; font-size: 12.5px; background: #fff;
  border: 1px solid #e7e0d4; border-radius: 12px; overflow: hidden;

  th, td { padding: 9px 12px; border-bottom: 1px solid #f0e9dc; text-align: left; }
  th { background: #faf6ee; color: #6b7280; font-weight: 600; font-size: 12px; }
  .title-cell { max-width: 260px; }
  .title-cell > b { display: block; font-weight: 600; color: #334155; }
  .ops-col { width: 260px; }
}

.resource-file {
  display: block;
  margin-top: 3px;
  color: #8a94a3;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ops-cell {
  display: flex; gap: 6px; align-items: center;
  button {
    display: inline-flex; align-items: center; gap: 3px;
    padding: 4px 8px; border-radius: 6px; font-size: 12px;
    border: 1px solid #ddd5c8; background: #fff; color: #4b5563; cursor: pointer;
    &:hover { border-color: #e8590c; color: #e8590c; }
    &.danger:hover { border-color: #dc2626; color: #dc2626; }
  }
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.agent-card {
  min-height: 188px;
  padding: 18px;
  border-radius: 14px;
  border: 1px solid #e7e0d4;
  background: #fff;
  display: flex; flex-direction: column; gap: 12px;
  transition: border-color 0.18s ease, transform 0.18s cubic-bezier(0.16, 1, 0.3, 1);

  &:hover { transform: translateY(-1px); border-color: #d8c9b7; }
  &.disabled { opacity: 0.68; background: #faf9f7; }
  .agent-card-head { display: flex; align-items: center; gap: 13px; }
  p { margin: 0; color: #596473; font-size: 12px; line-height: 1.65; min-height: 40px; text-wrap: pretty; }
}

.agent-avatar-shell {
  --agent-accent: #6b7280;
  position: relative;
  flex: none;
  display: grid;
  place-items: center;
  width: 68px;
  height: 68px;
  overflow: visible;
  border-radius: 50%;
  background: color-mix(in srgb, var(--agent-accent) 10%, white);

  img { width: 86%; height: 86%; object-fit: contain; filter: drop-shadow(0 4px 5px rgba(58, 43, 29, 0.12)); }
  > b { font-size: 28px; }
  > i { position: absolute; right: 1px; bottom: 4px; width: 11px; height: 11px; border: 2px solid #fff; border-radius: 50%; background: #a1a1aa; }
  > i.online { background: #2f8f5b; }
}

.agent-identity {
  flex: 1;
  min-width: 0;

  > div { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; }
  b { color: #202b37; font-size: 17px; letter-spacing: -0.01em; }
  small { display: block; margin-top: 5px; color: #7d8795; font-size: 11.5px; }
}

.agent-caps { display: flex; flex-wrap: wrap; gap: 5px; min-height: 22px; }
.muted-chip { background: #f3f4f6 !important; color: #7d8795 !important; }

.agent-ops {
  display: flex; align-items: center; gap: 8px; margin-top: auto; padding-top: 10px; border-top: 1px solid #eee7dc;
  .switch { margin-right: auto; }
  button {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 9px; border-radius: 6px; font-size: 12px;
    border: 1px solid #ddd5c8; background: #fff; cursor: pointer; color: #4b5563;
    &:hover { border-color: #e8590c; color: #e8590c; }
    &.danger:hover { border-color: #dc2626; color: #dc2626; }
  }
}

.switch {
  display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #4b5563;
  cursor: pointer;
  input { accent-color: #e8590c; }
  &.inline { margin: 6px 0; }
}

.modal-mask {
  position: fixed; inset: 0; z-index: 300;
  background: rgba(30, 24, 16, 0.4);
  display: grid; place-items: center;
}

.modal {
  width: min(620px, 92vw);
  max-height: 86vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 14px;
  padding: 20px;
  display: flex; flex-direction: column; gap: 12px;

  header {
    display: flex; align-items: center; justify-content: space-between;
    b { font-size: 15.5px; }
    button { background: none; border: 0; cursor: pointer; color: #6b7280; }
  }

  label {
    display: flex; flex-direction: column; gap: 5px;
    font-size: 12.5px; color: #4b5563; font-weight: 600;
    input, textarea, select {
      font-weight: 400;
      padding: 8px 10px; border-radius: 8px;
      border: 1px solid #ddd5c8; background: #fff; font-size: 13px;
      font-family: inherit;
      &:disabled { background: #f7f4ee; color: #9ca3af; }
    }
  }

  footer { display: flex; justify-content: flex-end; gap: 10px; }
}

.prompt-guide {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding: 9px 10px;
  border-radius: 8px;
  background: #fff8f1;
  color: #7c4a1e;
  font-size: 11.5px;

  b { margin-right: 2px; color: #8a4b18; }
  span { padding: 2px 7px; border-radius: 99px; background: #fff; border: 1px solid #ead7c4; }
}

.video-review-modal {
  width: min(820px, 94vw);

  header > div { min-width: 0; }
  header small { display: block; margin-top: 4px; color: #8a94a3; font-size: 11px; }
  video { width: 100%; max-height: 58vh; border-radius: 10px; background: #111827; }
  footer { align-items: center; justify-content: space-between; color: #64748b; font-size: 11.5px; }
}

.upload-modal { width: min(660px, 92vw); }

.upload-picker {
  display: grid !important;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  gap: 8px !important;
  padding: 10px;
  border: 1px dashed #d2bda8;
  border-radius: 8px;
  background: #fffaf5;

  > span { color: #8a5a2a; font-size: 12px; }
  input { min-width: 0; font-size: 12px; }
  small { grid-column: 1 / -1; color: #6b7280; font-size: 11px; font-weight: 400; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}

.form-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
  &:has(> :nth-child(3)) { grid-template-columns: 1fr 1fr 1fr; }
}

.path-card {
  max-width: 760px;
  display: flex; flex-direction: column; gap: 12px;
  label {
    display: flex; flex-direction: column; gap: 5px;
    font-size: 12.5px; font-weight: 600; color: #4b5563;
    input, textarea {
      font-weight: 400; padding: 8px 10px; border-radius: 8px;
      border: 1px solid #ddd5c8; font-size: 13px; font-family: inherit;
    }
  }
}

.stage-list { display: flex; flex-direction: column; gap: 8px; }

.stage-row {
  display: grid;
  grid-template-columns: 26px 1fr 1fr 34px;
  gap: 8px; align-items: center;

  em {
    font-style: normal; display: grid; place-items: center;
    width: 24px; height: 24px; border-radius: 99px;
    background: #fdeee2; color: #c2410c; font-size: 12px; font-weight: 700;
  }
  input {
    padding: 7px 10px; border-radius: 8px; border: 1px solid #ddd5c8; font-size: 13px;
  }
  button {
    border: 1px solid #ddd5c8; background: #fff; border-radius: 6px;
    height: 30px; cursor: pointer; color: #6b7280;
    &:hover:not(:disabled) { border-color: #dc2626; color: #dc2626; }
    &:disabled { opacity: 0.4; cursor: not-allowed; }
  }
}

.chat-panel {
  display: flex; flex-direction: column; gap: 10px; min-height: 460px;
}

.chat-panel-head {
  display: flex; align-items: center; justify-content: space-between;
  b { font-size: 13.5px; }
}

.chat-scroll {
  flex: 1;
  max-height: 440px;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 10px;
  padding: 12px;
  background: #faf7f0;
  border-radius: 10px;
  border: 1px solid #efe8da;
}

.room-msg {
  max-width: 78%;
  padding: 9px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e8e1d3;
  align-self: flex-start;
  font-size: 13px;

  &.teacher { align-self: flex-end; background: #fdf1e7; border-color: #f3d9c3; }
  &.agent { background: #f0f7f3; border-color: #d8eadf; }

  .msg-meta {
    display: flex; align-items: center; gap: 7px; margin-bottom: 4px;
    b { font-size: 12px; }
    small { color: #9ca3af; font-size: 10.5px; }
  }
  .msg-body { color: #374151; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
}

.chat-compose {
  display: flex; gap: 10px; align-items: flex-end;
  textarea {
    flex: 1; padding: 9px 12px; border-radius: 10px;
    border: 1px solid #ddd5c8; font-size: 13px; resize: none; font-family: inherit;
  }
}

.teacher-notice {
  position: fixed;
  bottom: 26px; left: 50%; transform: translateX(-50%);
  z-index: 400;
  padding: 10px 18px; border-radius: 10px;
  background: rgba(25, 21, 17, 0.88); color: #fff; font-size: 13px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}

.notice-fade-enter-active, .notice-fade-leave-active { transition: opacity 0.2s ease; }
.notice-fade-enter-from, .notice-fade-leave-to { opacity: 0; }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

// ---- 班级知识网络 ----
.knowledge-coverage-strip {
  display: grid;
  grid-template-columns: 0.7fr 0.9fr 0.7fr 1.7fr;
  gap: 0;
  overflow: hidden;
  border: 1px solid #e3dacd;
  border-radius: 14px;
  background: #fff;

  > div { padding: 17px 20px; border-right: 1px solid #ece5db; }
  > div:last-child { border-right: 0; }
  span { display: block; color: #687382; font-size: 11px; }
  b { display: inline-block; margin-top: 7px; color: #202b37; font-size: 25px; line-height: 1; letter-spacing: -0.025em; }
  small { margin-left: 6px; color: #8a94a3; font-size: 10.5px; }
}

.coverage-meter {
  div { height: 7px; margin: 10px 0 8px; overflow: hidden; border-radius: 999px; background: #eee9e1; }
  div i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #d86628, #dba231 56%, #2f8f5b); }
  small { margin: 0; }
}

.knowledge-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  min-height: 560px;
  overflow: hidden;
  border: 1px solid #ded5c8;
  border-radius: 14px;
  background: #f7f8f9;
}

.knowledge-canvas { min-width: 0; background: #fbfcfd; }
.knowledge-canvas-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #e7e7e5;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);

  h3 { margin: 0; color: #202b37; font-size: 15px; }
  p { margin: 5px 0 0; color: #718096; font-size: 11px; line-height: 1.55; }
}

.knowledge-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px 12px;
  max-width: 330px;

  span { display: inline-flex; align-items: center; gap: 5px; color: #687382; font-size: 10px; }
  i { width: 7px; height: 7px; border-radius: 50%; background: #2f8f5b; }
  i.watch { background: #d9a614; }
  i.weak { background: #d85824; }
  i.unknown { background: #cbd5e1; }
}

.knowledge-svg-scroll {
  width: 100%;
  min-height: 500px;
  overflow: auto;
  background: radial-gradient(circle at 50% 45%, rgba(235, 239, 241, 0.6), transparent 64%);

  svg { display: block; width: max(100%, 940px); min-height: 500px; }
}

.knowledge-stage-labels text { fill: #8a94a3; font-size: 10px; font-weight: 650; }
.knowledge-edge { fill: none; stroke: #c8bbaa; stroke-width: 1.2; }
.knowledge-node { cursor: pointer; outline: none; }
.knowledge-node rect {
  --node-color: #cbd5e1;
  fill: #fff;
  stroke: color-mix(in srgb, var(--node-color) 72%, #d7dce2);
  stroke-width: 1.4;
  filter: url(#knowledgeNodeShadow);
  transition: fill 0.18s ease;
}
.knowledge-node:hover rect,
.knowledge-node:focus rect,
.knowledge-node.selected rect { fill: color-mix(in srgb, var(--node-color) 6%, white); stroke-width: 2.4; }
.knowledge-node.unknown rect { stroke-dasharray: 4 3; }
.node-title { fill: #283441; font-size: 10.5px; font-weight: 650; }
.node-metric { fill: #7d8795; font-size: 8.6px; }

.knowledge-inspector {
  padding: 23px 22px;
  border-left: 1px solid rgba(218, 207, 192, 0.9);
  background: rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(18px) saturate(1.05);

  h3 { margin: 8px 0 9px; color: #202b37; font-size: 19px; letter-spacing: -0.02em; }
  > p { margin: 0; color: #667085; font-size: 11.5px; line-height: 1.75; text-wrap: pretty; }
  dl { margin: 19px 0 0; }
  dl div { display: flex; justify-content: space-between; gap: 14px; padding: 10px 0; border-bottom: 1px solid #ece6de; }
  dt { color: #7d8795; font-size: 11px; }
  dd { margin: 0; color: #2c3745; font-size: 11.5px; font-weight: 650; text-align: right; }
}

.inspector-status { font-size: 11px; font-weight: 700; }
.inspector-mastery {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 22px 0 4px;
  padding: 14px;
  border-radius: 11px;
  background: #f7f5f1;

  > div:last-child { min-width: 0; }
  > div:last-child b { display: block; color: #2c3745; font-size: 11.5px; }
  > div:last-child span { display: block; margin-top: 5px; color: #7d8795; font-size: 10.5px; }
}

// ---- 学生对比 ----
.compare-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
}

.compare-pick {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #e7e0d4;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;

  input { accent-color: #e8590c; }
  b { font-size: 12.5px; color: #374151; }
  small { font-size: 11px; color: #9ca3af; }

  &.active {
    border-color: #e8590c;
    background: #fff7f0;
  }
}

.compare-table-wrap {
  overflow-x: auto;
}

.compare-table {
  th, td { white-space: nowrap; }
  .key-cell { color: #6b7280; font-size: 11.5px; }
}

.compare-cell {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  min-width: 36px;
  text-align: center;
}

.compare-student-block {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0e9dc;

  &:last-child { border-bottom: 0; margin-bottom: 0; }
  b { display: block; font-size: 12.5px; color: #374151; margin-bottom: 6px; }
}

// ---- 干预日志 ----
.intervention-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.intervention-head {
  display: flex;
  align-items: center;
  justify-content: space-between;

  b { font-size: 14px; color: #1f2937; }
  small { display: block; margin-top: 3px; color: #9ca3af; font-size: 11.5px; }
}

.intervention-response {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}

.resp-badge {
  font-style: normal;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 600;

  &.good { background: #e8f6ee; color: #157347; }
  &.bad { background: #fef2f2; color: #b91c1c; }
}

.resp-rate { font-size: 11px; color: #6b7280; }

.intervention-timeline {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.timeline-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 8px;
  border: 1px solid #f0e9dc;
  background: #fff;
  font-size: 12px;

  .timeline-content {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #4b5563;
  }
  small { color: #9ca3af; font-size: 11px; white-space: nowrap; }

  &.responded { background: #f8fdf9; border-color: #e0f0e6; }

  .resp-tag {
    font-style: normal;
    padding: 1px 7px;
    border-radius: 99px;
    font-size: 10.5px;

    &.good { background: #e8f6ee; color: #157347; }
    &.bad { background: #fef2f2; color: #b91c1c; }
  }
}

// ---- 错题批量处理 ----
.batch-ops {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0e9dc;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 12.5px;
  color: #374151;

  input { accent-color: #e8590c; }
}

.plain-list li.selected {
  background: #fff7f0;
  border-radius: 6px;
}

@media (max-width: 1180px) {
  .knowledge-workspace { grid-template-columns: 1fr; }
  .knowledge-inspector { border-top: 1px solid rgba(218, 207, 192, 0.9); border-left: 0; }
  .knowledge-coverage-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .knowledge-coverage-strip > div:nth-child(2) { border-right: 0; }
  .knowledge-coverage-strip > div:nth-child(-n + 2) { border-bottom: 1px solid #ece5db; }
}

@media (max-width: 980px) {
  .grid-two { grid-template-columns: 1fr; }
  .form-row { grid-template-columns: 1fr; }
  .copilot-actions { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .copilot-controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .studio-intro { grid-template-columns: 1fr; }
  .agent-grid { grid-template-columns: 1fr; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .kpi-card:nth-child(2) { border-right: 0; }
  .kpi-card:nth-child(-n + 2) { border-bottom: 1px solid #ebe3d8; }
  .activity-state-list { grid-template-columns: 1fr; }
  .mastery-bucket-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 620px) {
  .teacher-view { width: calc(100vw - 24px); gap: 16px; padding-top: 2px; }
  .teacher-head { align-items: flex-start; gap: 12px; }
  .teacher-head h1 { font-size: 22px; }
  .card { padding: 17px 16px; }
  .teacher-tabs { overflow-x: auto; }
  .copilot-actions, .copilot-controls { grid-template-columns: 1fr; }
  .copilot-intro, .copilot-form-head, .copilot-result-head, .copilot-submit-row { flex-direction: column; }
  .priority-panel-head { flex-direction: column; }
  .priority-panel-head > .ghost-btn { width: 100%; justify-content: center; }
  .priority-item { align-items: flex-start; flex-direction: column; }
  .priority-item button { width: 100%; }
  .copilot-intro > .ghost-btn, .copilot-result-head > .ghost-btn, .copilot-submit-row > .primary-btn { width: 100%; justify-content: center; }
  .risk-student-row { align-items: flex-start; flex-wrap: wrap; }
  .risk-row-actions { width: 100%; }
  .risk-row-actions button { flex: 1; }
  .studio-intro { padding: 16px; }
  .studio-flow { grid-template-columns: 1fr; }
  .studio-binary-result { align-items: stretch; flex-direction: column; }
  .studio-binary-result .ghost-btn { width: 100%; }
  .studio-actions { align-items: stretch; flex-direction: column; }
  .studio-actions .ghost-btn, .studio-actions .primary-btn { width: 100%; }
  .toolbar > input, .toolbar > select, .toolbar > button { width: 100%; min-width: 0; }
  .toolbar > button { justify-content: center; }
  .video-review-modal footer { align-items: stretch; flex-direction: column; }
  .kpi-grid { grid-template-columns: 1fr; }
  .kpi-card { border-right: 0; border-bottom: 1px solid #ebe3d8; }
  .kpi-card:last-child { border-bottom: 0; }
  .profile-facts { grid-template-columns: 1fr; }
  .profile-fact:nth-last-child(-n + 2) { border-bottom-color: #eee7dc; }
  .profile-fact:last-child { border-bottom-color: transparent; }
  .error-composition { grid-template-columns: 1fr; justify-items: center; }
  .chart-legend-list { width: 100%; }
  .mastery-bucket-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .weak-signal-row { grid-template-columns: 24px minmax(0, 1fr) 48px; }
  .weak-signal-row button { grid-column: 2 / -1; width: 100%; }
  .knowledge-coverage-strip { grid-template-columns: 1fr; }
  .knowledge-coverage-strip > div { border-right: 0; border-bottom: 1px solid #ece5db; }
  .knowledge-canvas-head { flex-direction: column; }
  .knowledge-legend { justify-content: flex-start; }
  .agent-card { padding: 15px; }
  .agent-avatar-shell { width: 58px; height: 58px; }
}

@media (prefers-reduced-motion: reduce) {
  .copilot-action, .spin, .agent-card, .activity-stack span, .mastery-stack span, .knowledge-node rect { transition-duration: 0.01ms; animation-duration: 0.01ms; }
}

.teacher-view .hint-line,
.teacher-view .empty-line { color: #667085; }
.teacher-view input::placeholder,
.teacher-view textarea::placeholder { color: #667085; opacity: 1; }

// ---- 教师端旗舰级视觉精修：统一节奏、字号、控件与数据密度 ----
.teacher-view {
  --teacher-surface: #ffffff;
  --teacher-surface-soft: #f7f8f8;
  --teacher-surface-tint: #fff8f2;
  --teacher-ink: #1f2933;
  --teacher-ink-soft: #445160;
  --teacher-muted: #687585;
  --teacher-line: #e5ddd2;
  --teacher-line-strong: #d8cabb;
  --teacher-accent: #d94f12;
  --teacher-accent-soft: #fff1e7;
  --teacher-focus: rgba(217, 79, 18, 0.22);
  gap: 28px;
  width: min(1540px, calc(100% - 48px));
  max-width: 1540px;
  padding: 18px 0 56px;
  color: var(--teacher-ink);
  font-size: 14px;
}

.teacher-head {
  min-height: 74px;
  gap: 28px;

  h1 { color: var(--teacher-ink); font-size: 32px; line-height: 1.18; font-weight: 780; letter-spacing: -0.025em; }
  p { margin-top: 10px; color: var(--teacher-muted); font-size: 14px; line-height: 1.7; }
}

.teacher-tabs {
  gap: 4px;
  min-height: 48px;
  border-color: var(--teacher-line);
}

.tab-btn {
  min-height: 47px;
  padding: 10px 18px;
  border-radius: 10px 10px 0 0;
  color: #5d6977;
  font-size: 14px;
  font-weight: 560;
  transition: color 180ms cubic-bezier(0.16, 1, 0.3, 1), background 180ms cubic-bezier(0.16, 1, 0.3, 1);

  &.active { color: #b93f0c; background: var(--teacher-accent-soft); border-color: var(--teacher-line); }
}

.tab-panel { gap: 26px; }

.toolbar,
.student-bar {
  min-height: 48px;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid rgba(216, 202, 187, 0.82);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(14px) saturate(1.05);
}

.toolbar {
  gap: 10px 12px;

  input, select {
    height: 42px;
    border-color: var(--teacher-line-strong);
    border-radius: 9px;
    color: var(--teacher-ink);
    font: 500 14px/1 var(--sans-cn);
  }
  input { min-width: 260px; }
}

.student-bar {
  gap: 10px;
  color: var(--teacher-ink-soft);
  font-size: 14px;

  select { min-width: 360px; height: 42px; border-color: var(--teacher-line-strong); color: var(--teacher-ink); font-size: 14px; }
}

.ghost-btn,
.primary-btn {
  min-height: 42px;
  height: auto;
  padding: 0 15px;
  border-radius: 9px;
  font-size: 13.5px;
  font-weight: 620;
  transition: color 170ms cubic-bezier(0.16, 1, 0.3, 1), border-color 170ms cubic-bezier(0.16, 1, 0.3, 1), background 170ms cubic-bezier(0.16, 1, 0.3, 1), transform 170ms cubic-bezier(0.16, 1, 0.3, 1);

  &:active:not(:disabled) { transform: translateY(1px); }
}

.ghost-btn { border-color: var(--teacher-line-strong); color: var(--teacher-ink-soft); }
.primary-btn { background: var(--teacher-accent); }

.teacher-view button:focus-visible,
.teacher-view input:focus-visible,
.teacher-view select:focus-visible,
.teacher-view textarea:focus-visible,
.knowledge-node:focus-visible rect {
  outline: 3px solid var(--teacher-focus);
  outline-offset: 2px;
}

.grid-two {
  gap: 24px;
  align-items: start;
}

.card {
  padding: 26px 28px;
  border-color: var(--teacher-line);
  border-radius: 14px;
  background: var(--teacher-surface);
  box-shadow: 0 2px 6px rgba(65, 49, 32, 0.045);

  h3 {
    margin-bottom: 20px;
    color: var(--teacher-ink);
    font-size: 18px;
    line-height: 1.35;
    letter-spacing: -0.015em;
    small { color: var(--teacher-muted); font-size: 13px; line-height: 1.5; }
  }
}

.hint-line,
.empty-line { color: var(--teacher-muted); font-size: 13.5px; line-height: 1.7; }
.panel-loading { min-height: 92px; justify-content: center; color: var(--teacher-muted); font-size: 14px; }

.kpi-grid {
  padding: 8px 0;
  border-color: var(--teacher-line);
  background: rgba(255, 255, 255, 0.84);
}

.kpi-card {
  padding: 21px 28px 22px;
  gap: 10px;

  small { color: var(--teacher-muted); font-size: 13px; }
  b { color: var(--teacher-ink); font-size: 32px; em { font-size: 13px; color: var(--teacher-muted); } }
}

.priority-panel { padding: 21px 24px 22px; border-color: var(--teacher-line); background: #fffdfa; }
.priority-panel-head { margin-bottom: 16px; h2 { font-size: 18px; } p { font-size: 13px; } }

.weak-signal-row {
  grid-template-columns: 32px minmax(0, 1fr) 58px auto;
  gap: 15px;
  min-height: 66px;
  padding: 13px 0;

  button { min-height: 36px; padding: 7px 12px; font-size: 12.5px; }
}
.weak-rank { font-size: 12px; }
.weak-signal-main {
  b { font-size: 14px; }
  span { margin-top: 6px; color: var(--teacher-muted); font-size: 12px; }
}
.mastery-dial { width: 54px; height: 54px; b { font-size: 13px; } span { left: 34px; top: 25px; font-size: 9px; } }

.error-composition { grid-template-columns: 182px minmax(0, 1fr); gap: 30px; min-height: 250px; }
.donut-chart {
  width: 172px;
  height: 172px;
  &::after { inset: 24px; }
  > div { inset: 24px; }
  b { font-size: 30px; }
  span { font-size: 12px; }
}
.chart-legend-list {
  li { grid-template-columns: 9px minmax(0, 1fr) auto 42px; gap: 11px; padding: 10px 0; }
  i { width: 8px; height: 8px; }
  span { font-size: 13px; }
  b { font-size: 12.5px; }
  em { font-size: 12px; }
}

.activity-stack,
.mastery-stack { height: 14px; margin: 10px 0 24px; }
.activity-state-list {
  gap: 12px;
  details { padding: 16px; }
  summary span { font-size: 13px; }
  summary span b { font-size: 22px; }
  summary em, summary small, p { font-size: 12px; }
}
.mastery-bucket-grid {
  gap: 10px;
  > div { padding: 14px; }
  span { font-size: 12px; }
  b { font-size: 17px; }
  em { font-size: 11.5px; }
}
.chart-key span,
.trend-latest { font-size: 12px; }
.trend-latest b { font-size: 13.5px; }
.chart-x-labels text { font-size: 11.5px; }
.trend-chart-wrap svg { min-height: 250px; }

.profile-facts { gap: 0 28px; }
.profile-fact { grid-template-columns: 100px minmax(0, 1fr); min-height: 66px; padding: 14px 0; }
.profile-fact-label { font-size: 12.5px; }
.profile-fact b { font-size: 14px; }
.profile-tags em { padding: 4px 9px; font-size: 12px; }

.mastery-row {
  grid-template-columns: minmax(0, 1fr) 92px 44px;
  gap: 10px;
  margin-bottom: 9px;
  font-size: 13.5px;
  .bar { height: 8px; }
  em { font-size: 12.5px; }
}
.insight-mastery-list { gap: 10px; }
.insight-forecast { font-size: 14px; line-height: 1.85; }

.path-compact-row,
.resource-usage-row {
  gap: 16px;
  min-height: 62px;
  padding: 13px 0;
  b { font-size: 14px; }
  span, small { font-size: 12px; }
}
.resource-type-mark { width: 76px; min-height: 34px; font-size: 12px !important; }

.plain-list { gap: 10px; color: var(--teacher-ink-soft); font-size: 14px; }
.plain-list li { padding: 8px 10px; }
.chip { padding: 3px 9px; font-size: 12px; }

.data-table { font-size: 14px; border-color: var(--teacher-line); }
.data-table th,
.data-table td { padding: 13px 15px; }
.data-table th { color: #566270; font-size: 12.5px; }
.resource-file { font-size: 12px; }
.ops-cell button,
.agent-ops button { min-height: 36px; padding: 6px 10px; font-size: 12.5px; }

.studio-intro {
  gap: 34px;
  padding: 28px 30px;
  border-color: var(--teacher-line);
  background: #fffaf6;
}
.studio-intro-copy {
  > span { font-size: 12px; letter-spacing: 0.04em; }
  h2 { margin: 9px 0; font-size: 24px; letter-spacing: -0.02em; }
  p { font-size: 14px; }
}
.studio-flow li { min-height: 44px; padding: 11px 13px; }
.studio-flow b { font-size: 12px; }
.studio-flow span { font-size: 13px; }

.agent-grid { gap: 20px; }
.agent-card { min-height: 218px; padding: 24px; gap: 16px; border-color: var(--teacher-line); }
.agent-card p { color: var(--teacher-ink-soft); font-size: 13.5px; }
.agent-avatar-shell { width: 76px; height: 76px; }
.agent-identity b { font-size: 19px; }
.agent-identity small { font-size: 12.5px; }
.agent-caps { gap: 7px; }
.switch { font-size: 13px; }

.modal { padding: 26px; gap: 16px; }
.modal header b { font-size: 18px; }
.modal label { gap: 7px; font-size: 13.5px; }
.modal label input,
.modal label textarea,
.modal label select,
.path-card label input,
.path-card label textarea { min-height: 42px; border-color: var(--teacher-line-strong); font-size: 14px; }
.prompt-guide { padding: 12px 14px; font-size: 13px; }

.path-card { max-width: 900px; gap: 18px; }
.path-card label { font-size: 13.5px; }
.stage-row { grid-template-columns: 30px 1fr 1fr 42px; gap: 12px; }
.stage-row input { min-height: 42px; font-size: 14px; }
.stage-row button { min-height: 40px; }

.chat-panel { min-height: 580px; gap: 16px; }
.chat-panel-head b { font-size: 15px; }
.chat-scroll { max-height: 560px; gap: 13px; padding: 18px; background: #f7f7f5; }
.room-msg { padding: 12px 15px; border-radius: 11px; font-size: 14px; }
.room-msg .msg-meta b { font-size: 13px; }
.room-msg .msg-meta small { font-size: 11.5px; }
.chat-compose textarea { min-height: 48px; padding: 12px 14px; font-size: 14px; }

// ---- 知识图谱：重点概览 → 筛选工具 → 可缩放全景 ----
.knowledge-coverage-strip {
  border-color: var(--teacher-line);
  background: var(--teacher-surface);

  > div { padding: 22px 24px; }
  span { color: var(--teacher-muted); font-size: 12.5px; }
  b { margin-top: 9px; color: var(--teacher-ink); font-size: 30px; }
  small { color: var(--teacher-muted); font-size: 12px; }
}
.coverage-meter div { height: 9px; margin: 13px 0 10px; }

.knowledge-focus-overview {
  overflow: hidden;
  border: 1px solid var(--teacher-line);
  border-radius: 14px;
  background: var(--teacher-surface);

  > header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    padding: 22px 24px 17px;
    border-bottom: 1px solid #eee8e0;
  }
  h2 { margin: 0; color: var(--teacher-ink); font-size: 19px; letter-spacing: -0.015em; }
  p { margin: 7px 0 0; max-width: 72ch; color: var(--teacher-muted); font-size: 13px; line-height: 1.65; }
  header > span { flex: none; color: #a33d11; font-size: 12.5px; font-weight: 700; }
}

.knowledge-focus-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 0;
  padding: 0 24px 8px;
  list-style: none;

  li:nth-child(odd) { padding-right: 22px; }
  li:nth-child(even) { padding-left: 22px; border-left: 1px solid #eee8e0; }
  button {
    display: grid;
    grid-template-columns: 32px minmax(0, 1fr) auto;
    align-items: center;
    gap: 5px 14px;
    width: 100%;
    min-height: 76px;
    padding: 14px 0;
    border: 0;
    border-bottom: 1px solid #eee8e0;
    background: transparent;
    text-align: left;
    cursor: pointer;
  }
  li:nth-last-child(-n + 2) button { border-bottom-color: transparent; }
  button:hover .focus-copy b { color: var(--teacher-accent); }
}

.focus-rank { color: #9a8875; font: 700 12px/1 var(--mono); }
.focus-copy {
  min-width: 0;
  b { display: block; overflow: hidden; color: var(--teacher-ink); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
  small { display: block; margin-top: 6px; color: var(--teacher-muted); font-size: 12px; }
}
.focus-mastery { font-size: 16px; font-weight: 760; }
.focus-track {
  grid-column: 2 / -1;
  display: block;
  height: 5px;
  overflow: hidden;
  border-radius: 99px;
  background: #eeeae4;
  i { display: block; height: 100%; border-radius: inherit; }
}

.knowledge-workspace {
  grid-template-columns: minmax(0, 1fr) 340px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  min-height: 680px;
  box-sizing: border-box;
  border-color: var(--teacher-line-strong);
  background: var(--teacher-surface-soft);
}
.knowledge-canvas { width: 100%; min-width: 0; max-width: 100%; overflow: hidden; }
.knowledge-canvas-head {
  padding: 24px 26px 19px;
  background: rgba(255, 255, 255, 0.86);

  h3 { color: var(--teacher-ink); font-size: 19px; }
  p { margin-top: 7px; max-width: 72ch; color: var(--teacher-muted); font-size: 13px; }
}
.knowledge-legend {
  gap: 10px 15px;
  span { color: var(--teacher-muted); font-size: 12px; }
  i { width: 8px; height: 8px; }
}

.knowledge-toolrail {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 10px;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e5e7;
  background: #f4f6f7;

  > * { min-width: 0; }

  > label:not(.knowledge-search) {
    display: flex;
    flex: 0 1 142px;
    flex-direction: column;
    gap: 5px;
    > span { color: #637080; font-size: 11.5px; font-weight: 650; }
  }
  select {
    max-width: 100%;
    height: 40px;
    padding: 0 30px 0 10px;
    border: 1px solid #cfd6dc;
    border-radius: 8px;
    background: #fff;
    color: #344050;
    font: 600 12.5px/1 var(--sans-cn);
  }
}

.knowledge-search {
  display: flex;
  flex: 1 1 280px;
  align-items: center;
  gap: 9px;
  height: 40px;
  box-sizing: border-box;
  padding: 0 12px;
  border: 1px solid #cfd6dc;
  border-radius: 8px;
  background: #fff;
  color: #74808d;

  input { width: 100%; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--teacher-ink); font-size: 13.5px; }
}

.knowledge-view-switch,
.knowledge-zoom {
  display: inline-flex;
  align-items: center;
  height: 40px;
  overflow: hidden;
  border: 1px solid #cfd6dc;
  border-radius: 8px;
  background: #fff;

  button { height: 100%; border: 0; background: transparent; color: #5e6a78; cursor: pointer; }
  button:hover:not(:disabled) { background: #f1f3f4; color: var(--teacher-ink); }
  button:disabled { cursor: not-allowed; opacity: 0.4; }
}
.knowledge-view-switch button { padding: 0 11px; font-size: 12.5px; }
.knowledge-view-switch button.active { background: #27323e; color: #fff; }
.knowledge-zoom {
  button { display: grid; place-items: center; width: 38px; }
  output { min-width: 48px; color: #465261; font-size: 12px; font-weight: 700; text-align: center; }
}
.knowledge-reset { height: 40px; padding: 0 12px; border: 1px solid #cfd6dc; border-radius: 8px; background: #fff; color: #5e6a78; font-size: 12.5px; cursor: pointer; }
.knowledge-reset:hover { color: var(--teacher-accent); border-color: #dea989; }

.knowledge-canvas-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  padding: 10px 20px;
  border-bottom: 1px solid #e5e8ea;
  background: #fbfcfc;
  color: #697684;
  font-size: 12px;

  span + span::before { content: "·"; margin-right: 18px; color: #a5afb8; }
}

.knowledge-svg-scroll {
  min-height: 540px;
  overscroll-behavior: contain;
  background: radial-gradient(circle at 50% 38%, rgba(229, 235, 238, 0.66), transparent 66%);

  svg { min-width: 915px; min-height: 500px; }
}
.knowledge-stage-labels text { fill: #667382; font-size: 12px; font-weight: 700; }
.knowledge-edge { stroke: #c7b7a4; stroke-width: 1.35; }
.knowledge-edge:not(.relation-prerequisite) { stroke: #8fa1ad; stroke-dasharray: 5 5; }
.node-title { fill: #26323f; font-size: 12.5px; font-weight: 700; }
.node-metric { fill: #687585; font-size: 10.8px; }
.knowledge-node rect { transition: fill 180ms cubic-bezier(0.16, 1, 0.3, 1); }

.knowledge-empty {
  display: grid;
  place-items: center;
  align-content: center;
  min-height: 520px;
  gap: 9px;
  color: #7a8794;

  b { color: #33404d; font-size: 16px; }
  span { font-size: 13px; }
  button { margin-top: 5px; min-height: 40px; padding: 0 14px; border: 1px solid #cfd6dc; border-radius: 8px; background: #fff; color: #4d5967; cursor: pointer; }
}

.knowledge-inspector {
  min-width: 0;
  box-sizing: border-box;
  padding: 30px 28px;
  background: rgba(255, 255, 255, 0.9);

  h3 { margin: 10px 0 12px; font-size: 22px; }
  > p { color: var(--teacher-muted); font-size: 13.5px; line-height: 1.8; }
  dl { margin-top: 24px; }
  dl div { padding: 13px 0; }
  dt { font-size: 12.5px; }
  dd { font-size: 13.5px; }
}
.inspector-status { font-size: 12.5px; }
.inspector-mastery {
  gap: 17px;
  margin-top: 26px;
  padding: 17px;
  > div:last-child b { font-size: 13.5px; }
  > div:last-child span { font-size: 12px; }
}

@media (max-width: 1700px) {
  .knowledge-workspace { grid-template-columns: minmax(0, 1fr); }
  .knowledge-inspector {
    border-top: 1px solid rgba(218, 207, 192, 0.9);
    border-left: 0;
  }
}

@media (max-width: 1240px) {
  .knowledge-search { flex-basis: 100%; }
  .knowledge-reset { min-width: 74px; }
}

@media (max-width: 760px) {
  .teacher-view { width: calc(100% - 28px); gap: 20px; padding-bottom: 36px; }
  .teacher-head { min-height: 0; }
  .teacher-head h1 { font-size: 26px; }
  .teacher-head p { font-size: 14px; }
  .toolbar, .student-bar { padding: 10px; }
  .card { padding: 21px 18px; }
  .card h3 { align-items: flex-start; flex-direction: column; gap: 4px; font-size: 17px; }
  .knowledge-focus-overview > header { flex-direction: column; padding: 19px 18px 15px; }
  .knowledge-focus-list { grid-template-columns: 1fr; padding: 0 18px 6px; }
  .knowledge-focus-list li { padding: 0 !important; border-left: 0 !important; }
  .knowledge-focus-list li:nth-last-child(2) button { border-bottom-color: #eee8e0; }
  .knowledge-toolrail { align-items: stretch; padding: 12px; }
  .knowledge-search { flex: 1 0 100%; }
  .knowledge-toolrail > label:not(.knowledge-search) { flex: 1 1 calc(50% - 5px); }
  .knowledge-view-switch { flex: 1 0 100%; }
  .knowledge-view-switch button { flex: 1; }
  .knowledge-zoom { justify-self: stretch; }
  .knowledge-zoom output { flex: 1; }
  .knowledge-reset { width: 100%; }
  .knowledge-canvas-status { flex-direction: column; gap: 5px; }
  .knowledge-canvas-status span + span::before { content: none; }
  .knowledge-inspector { padding: 24px 20px; }
  .knowledge-workspace { min-height: 0; }
  .student-bar { align-items: stretch; flex-direction: column; }
  .student-bar select { width: 100%; min-width: 0; }
  .data-table { min-width: 760px; }
  .error-composition { grid-template-columns: 1fr; }
  .profile-fact { grid-template-columns: 90px minmax(0, 1fr); }
  .room-msg { max-width: 90%; }
}

/* ============================================================
 * v2 收口层（2026-07-11）· 加载最后一位以覆盖旧 patch
 * 说明：前段 4728 起的 "旗舰级视觉精修" patch 使用 --teacher-*
 * token，与 v2 顶部 App Bar / Tabs / 学生条 目标一致但实现散乱。
 * 此段做两件事：
 *   1) 把 --teacher-* 变量映射到 v2 --tv-*，让业务组件仍能使用
 *   2) 用高特异性选择器把顶部 UI 强制走 v2 定义
 * 业务专属组件（.weak-signal-row/.donut-chart/.chart-legend-list/
 * .activity-stack/.mastery-bucket-grid 等）保留不动
 * ============================================================ */
.teacher-view {
  /* v2 → 老 patch 变量别名，兼容业务组件 */
  --teacher-surface: var(--tv-panel);
  --teacher-surface-soft: var(--tv-panel-2);
  --teacher-surface-tint: var(--tv-brand-soft);
  --teacher-ink: var(--tv-ink);
  --teacher-ink-soft: var(--tv-ink-2);
  --teacher-muted: var(--tv-muted);
  --teacher-line: var(--tv-line);
  --teacher-line-strong: var(--tv-line-2);
  --teacher-accent: var(--tv-brand);
  --teacher-accent-soft: var(--tv-brand-soft);
  --teacher-focus: rgba(217, 72, 15, 0.24);
}

/* 顶部结构强制走 v2（重定义前段 patch 的覆盖） */
.teacher-view .teacher-appbar {
  padding: 20px 24px 22px;
  gap: 10px;
  border-radius: var(--tv-r-lg);
  border: 1px solid var(--tv-line);
  background:
    radial-gradient(600px 220px at 6% -30%, rgba(217, 72, 15, 0.06), transparent 65%),
    linear-gradient(180deg, #ffffff 0%, #fbf9f4 100%);
  box-shadow: var(--tv-elev-1);
}

.teacher-view .teacher-appbar-title h1 {
  font-size: clamp(22px, 2vw, 26px);
  line-height: 1.2;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--tv-ink);
}

.teacher-view .teacher-appbar-title p {
  margin: 6px 0 0;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--tv-muted);
}

.teacher-view .teacher-tabs {
  gap: 4px;
  min-height: auto;
  padding: 0 4px;
  border-bottom: 1px solid var(--tv-line);
  overflow-x: auto;
  scrollbar-width: none;
}

.teacher-view .tab-btn {
  position: relative;
  min-height: 48px;
  min-width: 90px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--tv-muted);
  font-size: 13.5px;
  font-weight: 550;
  border-radius: 0;
  transition: color var(--tv-dur) var(--tv-ease);
}

.teacher-view .tab-btn:hover:not(.active) { color: var(--tv-ink-2); }
.teacher-view .tab-btn:hover:not(.active) .tab-inner { background: rgba(217, 72, 15, 0.06); }

.teacher-view .tab-btn.active {
  color: var(--tv-brand);
  font-weight: 700;
  background: transparent;
  border: none;
}

.teacher-view .tab-btn.active .tab-inner { background: var(--tv-brand-soft); }

.teacher-view .student-bar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 56px;
  padding: 10px 16px;
  border-radius: var(--tv-r-md);
  border: 1px solid var(--tv-line);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(14px) saturate(1.3);
  box-shadow: var(--tv-elev-1);
}

.teacher-view .student-bar-select {
  min-width: 280px;
  max-width: 520px;
  height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--tv-line-2);
  background: var(--tv-panel);
  color: var(--tv-ink);
  font-size: 13px;
  cursor: pointer;
}

/* KPI 条走 v2（数字放大 + 顶部品牌带） */
.teacher-view .kpi-grid {
  position: relative;
  padding: 6px 0;
  border: 1px solid var(--tv-line);
  border-radius: var(--tv-r-md);
  background:
    linear-gradient(180deg, rgba(255, 246, 236, 0.55) 0%, rgba(255, 255, 255, 0.85) 100%),
    #fff;
  box-shadow: var(--tv-elev-1);
  overflow: hidden;
}

.teacher-view .kpi-grid::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--tv-brand), #f59e0b);
}

.teacher-view .kpi-card {
  padding: 22px 26px 24px;
  border-right: 1px solid var(--tv-line);
  gap: 8px;
  transition: background var(--tv-dur) var(--tv-ease);
}

.teacher-view .kpi-card:hover { background: rgba(255, 244, 232, 0.4); }
.teacher-view .kpi-card small { color: var(--tv-muted); font-size: 12px; letter-spacing: 0.02em; }
.teacher-view .kpi-card b {
  font-size: 32px;
  line-height: 1.05;
  font-weight: 750;
  letter-spacing: -0.03em;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
}

/* 通用卡片走 v2 elevation-1 */
.teacher-view .card {
  padding: 24px;
  border-radius: var(--tv-r-md);
  border: 1px solid var(--tv-line);
  background: var(--tv-panel);
  box-shadow: var(--tv-elev-1);
  transition: box-shadow var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease);
}

.teacher-view .card:hover {
  box-shadow: var(--tv-elev-2);
  border-color: var(--tv-line-2);
}

.teacher-view .card h3 {
  margin: 0 0 18px;
  font-size: 16px;
  line-height: 1.4;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--tv-ink);
}

/* 按钮 44px 触控 + 品牌焦点环 */
.teacher-view .ghost-btn,
.teacher-view .primary-btn {
  min-height: 40px;
  padding: 0 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 550;
  transition: background var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease), color var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease);
}

.teacher-view .ghost-btn:hover {
  border-color: var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}

.teacher-view .ghost-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.24);
}

.teacher-view .primary-btn {
  background: var(--tv-brand);
  color: #fff;
  border: 0;
  font-weight: 650;
}

.teacher-view .primary-btn:hover:not(:disabled) {
  background: var(--tv-brand-hover);
  transform: translateY(-1px);
  box-shadow: 0 10px 20px -12px rgba(217, 72, 15, 0.5);
}

.teacher-view .primary-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(217, 72, 15, 0.35);
}

/* 响应式收口 */
@media (max-width: 768px) {
  .teacher-view {
    width: calc(100% - 28px);
    gap: 18px;
    padding-bottom: 36px;
  }
  .teacher-view .teacher-appbar { padding: 18px 16px 20px; }
  .teacher-view .teacher-appbar-main {
    flex-direction: column;
    align-items: stretch;
    gap: 14px;
  }
  .teacher-view .appbar-action { align-self: flex-start; }
  .teacher-view .student-bar {
    flex-wrap: wrap;
    gap: 8px 10px;
  }
  .teacher-view .student-bar-select {
    flex-basis: 100%;
    min-width: 0;
    max-width: none;
  }
  .teacher-view .kpi-grid { grid-template-columns: repeat(2, 1fr); }
  .teacher-view .kpi-card:nth-child(2n) { border-right: 0; }
  .teacher-view .kpi-card:nth-child(-n + 2) { border-bottom: 1px solid var(--tv-line); }
  .teacher-view .kpi-card b { font-size: 26px; }
  .teacher-view .card { padding: 18px; }
}

@media (max-width: 480px) {
  .teacher-view .kpi-grid { grid-template-columns: 1fr; }
  .teacher-view .kpi-card { border-right: 0; border-bottom: 1px solid var(--tv-line); }
  .teacher-view .kpi-card:last-child { border-bottom: 0; }
}

/* ============================================================
 * 班级态势 Board v2 深度重构（2026-07-11）
 * 目标：Bento 布局 + 卡片自适应等高铺满 + 内容饱满层
 * 规范：Material Design 3 + Claude 风格 hero 装饰
 * ============================================================ */

/* ---------- Claude 风格 board-hero：柔光晕 + 双列布局 ---------- */
.teacher-view .board-panel {
  gap: 28px;
}

.teacher-view .board-hero {
  position: relative;
  padding: 24px 28px;
  border-radius: var(--tv-r-lg);
  border: 1px solid var(--tv-line);
  background:
    linear-gradient(135deg, #ffffff 0%, #fef7ee 45%, #fff2e0 100%);
  box-shadow: var(--tv-elev-1);
  overflow: hidden;
  isolation: isolate;
}

.teacher-view .board-hero-art {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.teacher-view .board-hero-art .orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
}

.teacher-view .board-hero-art .orb-a {
  width: 340px;
  height: 340px;
  left: -80px;
  top: -180px;
  background: radial-gradient(circle, rgba(217, 72, 15, 0.35), transparent 70%);
}

.teacher-view .board-hero-art .orb-b {
  width: 260px;
  height: 260px;
  right: 8%;
  bottom: -160px;
  background: radial-gradient(circle, rgba(245, 158, 11, 0.28), transparent 70%);
}

.teacher-view .board-hero-art .orb-c {
  width: 180px;
  height: 180px;
  right: -60px;
  top: -60px;
  background: radial-gradient(circle, rgba(47, 143, 91, 0.20), transparent 70%);
}

.teacher-view .board-hero-body {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
}

.teacher-view .board-hero-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.teacher-view .board-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--tv-brand-line);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  color: var(--tv-brand-ink);
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.teacher-view .board-hero-copy h2 {
  margin: 0;
  font-size: clamp(20px, 2vw, 24px);
  line-height: 1.25;
  font-weight: 720;
  letter-spacing: -0.02em;
  color: var(--tv-ink);
  text-wrap: balance;
}

.teacher-view .board-hero-copy p {
  margin: 0;
  max-width: 74ch;
  font-size: 13px;
  line-height: 1.7;
  color: var(--tv-muted);
}

.teacher-view .board-hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

/* ---------- Section 章节头：橙色玻璃徽章 + Headline + 副标 ---------- */
.teacher-view .board-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.teacher-view .board-section-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 4px;
}

.teacher-view .board-section-chip {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid var(--tv-brand-line);
  background: linear-gradient(160deg, rgba(255, 244, 232, 0.9), rgba(255, 255, 255, 0.7));
  backdrop-filter: blur(8px);
  color: var(--tv-brand-ink);
  flex-shrink: 0;
}

.teacher-view .board-section-title {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-view .board-section-title b {
  font-size: 15.5px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--tv-ink);
}

.teacher-view .board-section-title small {
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--tv-muted);
}

/* 延伸细线：段落感 */
.teacher-view .board-section-head::after {
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--tv-line-2), transparent);
}

/* ---------- Bento 12 列布局：卡片 flex 铺满 ---------- */
.teacher-view .board-bento {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 16px;
  align-items: stretch;
}

.teacher-view .board-bento > .card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px 24px;
}

/* 卡内主体（h3 之后的直接子元素）拉伸铺满 */
.teacher-view .board-bento > .card > h3 {
  flex-shrink: 0;
  margin-bottom: 6px;
}

.teacher-view .board-bento > .card > :not(h3):last-child,
.teacher-view .board-bento > .card > .weak-signal-list,
.teacher-view .board-bento > .card > .risk-student-list,
.teacher-view .board-bento > .card > .error-composition,
.teacher-view .board-bento > .card > .trend-chart-wrap,
.teacher-view .board-bento > .card > .mastery-hero,
.teacher-view .board-bento > .card > .activity-state-list {
  flex: 1;
  min-height: 0;
}

.teacher-view .bento-span-4 { grid-column: span 4; }
.teacher-view .bento-span-5 { grid-column: span 5; }
.teacher-view .bento-span-7 { grid-column: span 7; }
.teacher-view .bento-span-8 { grid-column: span 8; }
.teacher-view .bento-span-12 { grid-column: span 12; }

/* ---------- 活跃度分布卡内容饱满层 ---------- */
.teacher-view .activity-highlight {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: var(--tv-r-sm);
  border: 1px solid var(--tv-line);
  background: linear-gradient(135deg, rgba(47, 143, 91, 0.08) 0%, rgba(255, 255, 255, 0.5) 100%);
}

.teacher-view .activity-highlight-num {
  display: flex;
  align-items: baseline;
  gap: 2px;
  flex-shrink: 0;
}

.teacher-view .activity-highlight-num .num-value {
  font-size: 40px;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1;
  color: #2f8f5b;
  font-variant-numeric: tabular-nums;
}

.teacher-view .activity-highlight-num .num-unit {
  font-size: 18px;
  font-weight: 600;
  color: #2f8f5b;
}

.teacher-view .activity-highlight-caption {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.teacher-view .activity-highlight-caption b {
  font-size: 13px;
  font-weight: 650;
  color: var(--tv-ink);
}

.teacher-view .activity-highlight-caption small {
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--tv-muted);
}

/* ---------- 掌握度分布 · 整行 hero + 5 桶柱状 + 分层徽章 ---------- */
.teacher-view .mastery-hero {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 28px;
  align-items: center;
  padding: 20px 4px;
}

.teacher-view .mastery-avg {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.teacher-view .mastery-avg-ring {
  position: relative;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: conic-gradient(var(--tv-brand) 0 var(--pct), var(--tv-line) var(--pct) 100%);
  padding: 12px;
}

.teacher-view .mastery-avg-ring::after {
  content: "";
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  background: #fff;
  box-shadow: inset 0 0 0 1px var(--tv-line);
}

.teacher-view .mastery-avg-inner {
  position: relative;
  z-index: 1;
  height: 100%;
  width: 100%;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #fff;
}

.teacher-view .mastery-avg-inner b {
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--tv-brand-ink);
  font-variant-numeric: tabular-nums;
}

.teacher-view .mastery-avg-inner span {
  font-size: 15px;
  color: var(--tv-brand-ink);
  font-weight: 650;
  margin-left: 2px;
}

.teacher-view .mastery-avg-caption {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-view .mastery-avg-caption b {
  font-size: 13.5px;
  font-weight: 650;
  color: var(--tv-ink);
}

.teacher-view .mastery-avg-caption small {
  font-size: 11.5px;
  color: var(--tv-muted);
}

.teacher-view .mastery-bars {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  align-items: end;
  height: 200px;
  padding: 0 4px;
}

.teacher-view .mastery-bar-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100%;
  min-width: 0;
}

.teacher-view .mastery-bar-track {
  position: relative;
  flex: 1;
  min-height: 60px;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.03));
  border-radius: 8px;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}

.teacher-view .mastery-bar-fill {
  width: 100%;
  min-height: 8px;
  border-radius: 6px 6px 0 0;
  position: relative;
  transition: height 400ms var(--tv-ease);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.teacher-view .mastery-bar-value {
  position: absolute;
  top: -22px;
  font-size: 15px;
  font-weight: 750;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

.teacher-view .mastery-bar-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.teacher-view .mastery-bar-meta b {
  font-size: 12px;
  font-weight: 600;
  color: var(--tv-ink-2);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.teacher-view .mastery-bar-meta em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--tv-muted);
}

/* 分层徽章：三层学生分类 */
.teacher-view .mastery-tiers {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding-top: 16px;
  border-top: 1px dashed var(--tv-line);
}

.teacher-view .mastery-tier {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--tv-r-sm);
  border: 1px solid var(--tv-line);
  background: var(--tv-panel-2);
}

.teacher-view .mastery-tier .tier-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  flex-shrink: 0;
}

.teacher-view .mastery-tier.tier-top {
  border-color: rgba(47, 143, 91, 0.3);
  background: linear-gradient(135deg, rgba(47, 143, 91, 0.06), transparent);
}
.teacher-view .mastery-tier.tier-top .tier-icon {
  background: rgba(47, 143, 91, 0.14);
  color: #1f6b47;
}

.teacher-view .mastery-tier.tier-mid {
  border-color: rgba(216, 146, 41, 0.28);
  background: linear-gradient(135deg, rgba(216, 146, 41, 0.06), transparent);
}
.teacher-view .mastery-tier.tier-mid .tier-icon {
  background: rgba(216, 146, 41, 0.14);
  color: #a06614;
}

.teacher-view .mastery-tier.tier-low {
  border-color: rgba(201, 58, 46, 0.28);
  background: linear-gradient(135deg, rgba(201, 58, 46, 0.06), transparent);
}
.teacher-view .mastery-tier.tier-low .tier-icon {
  background: rgba(201, 58, 46, 0.14);
  color: #9c2f24;
}

.teacher-view .mastery-tier > div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-view .mastery-tier b {
  font-size: 12.5px;
  font-weight: 650;
  color: var(--tv-ink);
}

.teacher-view .mastery-tier small {
  font-size: 11px;
  line-height: 1.5;
  color: var(--tv-muted);
}

/* ---------- 30 天趋势 · Delta 汇总条 ---------- */
.teacher-view .trend-delta-bar {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
  border-radius: var(--tv-r-sm);
  border: 1px solid var(--tv-line);
  background: linear-gradient(135deg, rgba(47, 143, 91, 0.05), rgba(217, 72, 15, 0.04));
  margin-bottom: 14px;
}

.teacher-view .trend-delta-tile {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(8px);
  border: 1px solid var(--tv-line);
}

.teacher-view .trend-delta-tile small {
  font-size: 11.5px;
  color: var(--tv-muted);
  font-weight: 500;
  letter-spacing: 0.02em;
}

.teacher-view .trend-delta-tile b {
  font-size: 24px;
  font-weight: 780;
  letter-spacing: -0.03em;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.teacher-view .trend-delta-tile em {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-style: normal;
  font-size: 11.5px;
  font-weight: 600;
}

.teacher-view .trend-delta-tile em.up { color: #1f8a5b; }
.teacher-view .trend-delta-tile em.down { color: #c93a2e; }
.teacher-view .trend-delta-tile em.muted { color: var(--tv-muted); font-weight: 500; }

/* ---------- 响应式：Bento 断点 ---------- */
@media (max-width: 1180px) {
  .teacher-view .board-bento {
    grid-template-columns: repeat(8, minmax(0, 1fr));
  }
  .teacher-view .bento-span-4 { grid-column: span 4; }
  .teacher-view .bento-span-5 { grid-column: span 8; }
  .teacher-view .bento-span-7 { grid-column: span 8; }
  .teacher-view .bento-span-8 { grid-column: span 8; }
  .teacher-view .bento-span-12 { grid-column: 1 / -1; }
  .teacher-view .mastery-hero { grid-template-columns: 200px 1fr; gap: 20px; }
  .teacher-view .mastery-tiers { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .teacher-view .board-panel { gap: 20px; }
  .teacher-view .board-hero { padding: 20px; }
  .teacher-view .board-hero-body { flex-direction: column; align-items: stretch; gap: 14px; }
  .teacher-view .board-hero-actions { flex-wrap: wrap; }
  .teacher-view .board-bento { grid-template-columns: 1fr; }
  .teacher-view .bento-span-4,
  .teacher-view .bento-span-5,
  .teacher-view .bento-span-7,
  .teacher-view .bento-span-8,
  .teacher-view .bento-span-12 { grid-column: 1 / -1; }
  .teacher-view .mastery-hero { grid-template-columns: 1fr; }
  .teacher-view .mastery-avg { flex-direction: row; justify-content: center; }
  .teacher-view .mastery-avg-caption { text-align: left; }
  .teacher-view .mastery-bars { height: 160px; gap: 8px; }
  .teacher-view .trend-delta-bar { grid-template-columns: 1fr; }
  .teacher-view .board-section-head::after { display: none; }
}

/* ================= v3 · 时间维度卡：ECharts 双轴组合图 + Metric 汇总条 ================= */
.teacher-view .trend-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.teacher-view .trend-metric {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: var(--tv-r-sm);
  border: 1px solid var(--tv-line);
  background: linear-gradient(180deg, #fff 0%, #fbf9f4 100%);
  overflow: hidden;
  transition: transform var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease);
}

.teacher-view .trend-metric::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--metric-accent, var(--tv-brand));
}

.teacher-view .trend-metric:hover {
  transform: translateY(-1px);
  box-shadow: var(--tv-elev-1);
}

.teacher-view .trend-metric-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 550;
  color: var(--tv-muted);
  letter-spacing: 0.02em;
}

.teacher-view .trend-metric-icon {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: var(--metric-soft, rgba(217, 72, 15, 0.1));
  color: var(--metric-accent, var(--tv-brand));
  flex-shrink: 0;
}

.teacher-view .trend-metric-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-size: 26px;
  font-weight: 780;
  line-height: 1.1;
  letter-spacing: -0.03em;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
}

.teacher-view .trend-metric-value .unit {
  font-size: 13px;
  font-weight: 550;
  color: var(--tv-muted);
  letter-spacing: 0;
}

.teacher-view .trend-metric-delta {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tv-muted);
}

.teacher-view .trend-metric-delta.up { color: #1f8a5b; }
.teacher-view .trend-metric-delta.down { color: #c93a2e; }

/* ECharts 容器 */
.teacher-view .trend-echarts-wrap {
  position: relative;
  min-height: 340px;
  padding: 8px 0 4px;
  border-radius: var(--tv-r-sm);
  background: linear-gradient(180deg, rgba(255, 244, 232, 0.35) 0%, rgba(255, 255, 255, 0) 55%);
}

.teacher-view .trend-echarts-el {
  width: 100%;
  height: 340px;
}

.teacher-view .trend-echarts-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
  padding: 0 4px;
  font-size: 11.5px;
  color: var(--tv-muted);
}

.teacher-view .trend-echarts-caption b {
  color: var(--tv-ink-2);
  font-weight: 650;
}

@media (max-width: 1180px) {
  .teacher-view .trend-metric-strip { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
  .teacher-view .trend-metric-strip { grid-template-columns: 1fr; }
  .teacher-view .trend-echarts-el { height: 280px; }
  .teacher-view .trend-echarts-wrap { min-height: 280px; }
}

/* ============================================================
 * v3 · MD3 AI 教学工作台（board tab · workbench-v3）
 * 规范：Material Design 3 · Primary #F97316 · AI Accent #7C5CFC
 * 布局：Insight Surface + KPI + 两栏（主 2fr + AI Copilot 1fr）
 * ============================================================ */
.teacher-view .workbench-v3 {
  --wb-ai: #7C5CFC;
  --wb-ai-ink: #5B3FE0;
  --wb-ai-soft: #F5F1FF;
  --wb-ai-line: #D8CCFB;
  gap: 20px;
  display: flex;
  flex-direction: column;
}

/* ---------- 1. AI 今日洞察 Insight Surface ---------- */
.teacher-view .insight-surface {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 32px;
  align-items: center;
  padding: 28px 32px;
  border-radius: 20px;
  border: 1px solid var(--wb-ai-line);
  background:
    radial-gradient(500px 220px at 100% 50%, rgba(124, 92, 252, 0.10), transparent 60%),
    linear-gradient(135deg, #ffffff 0%, var(--wb-ai-soft) 100%);
  overflow: hidden;
}

.teacher-view .insight-orb {
  position: relative;
  width: 168px;
  height: 168px;
  justify-self: end;
}

.teacher-view .insight-orb .orb-core {
  position: absolute;
  inset: 32px;
  border-radius: 50%;
  background: radial-gradient(circle at 32% 32%, #b9a2ff 0%, #7C5CFC 60%, #5B3FE0 100%);
  box-shadow: 0 20px 40px -18px rgba(124, 92, 252, 0.55), inset 0 -12px 24px rgba(0, 0, 0, 0.14);
  animation: orb-float 12s ease-in-out infinite;
}

.teacher-view .insight-orb .orb-halo {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(124, 92, 252, 0.25);
  animation: orb-pulse 8s ease-in-out infinite;
}

.teacher-view .insight-orb .halo-2 {
  inset: 12px;
  border-color: rgba(124, 92, 252, 0.35);
  animation-delay: -2s;
}

@keyframes orb-float {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  50% { transform: translate(-3px, -4px) rotate(6deg); }
}

@keyframes orb-pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.05); opacity: 0.8; }
}

.teacher-view .insight-copy {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.teacher-view .insight-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(6px);
  color: var(--wb-ai-ink);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.02em;
  width: fit-content;
  animation: chip-glow 5s ease-in-out infinite;
}

.teacher-view .insight-chip .chip-icon {
  animation: chip-spark 4s ease-in-out infinite;
}

@keyframes chip-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(124, 92, 252, 0); }
  50% { box-shadow: 0 0 0 6px rgba(124, 92, 252, 0.12); }
}

@keyframes chip-spark {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.15); opacity: 0.75; }
}

.teacher-view .insight-title {
  margin: 0;
  font-size: clamp(20px, 1.9vw, 24px);
  line-height: 1.5;
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--tv-ink);
  text-wrap: pretty;
}

.teacher-view .insight-title b {
  color: var(--wb-ai-ink);
  font-weight: 750;
}

.teacher-view .insight-meta {
  margin: 0;
  font-size: 12.5px;
  color: var(--tv-muted);
}

.teacher-view .insight-dot {
  margin: 0 6px;
  color: var(--tv-faint);
}

.teacher-view .insight-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* ---------- MD3 Buttons: Outlined / Filled / Tonal ---------- */
.teacher-view .btn-outlined,
.teacher-view .btn-filled,
.teacher-view .btn-tonal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 20px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 550;
  cursor: pointer;
  transition: background var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease), color var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease);
  font-family: inherit;
}

.teacher-view .btn-outlined {
  border: 1px solid var(--tv-line-2);
  background: transparent;
  color: var(--tv-ink-2);
}
.teacher-view .btn-outlined:hover {
  border-color: var(--wb-ai-line);
  background: rgba(124, 92, 252, 0.06);
  color: var(--wb-ai-ink);
}
.teacher-view .btn-outlined:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.24);
}

.teacher-view .btn-filled {
  border: none;
  background: var(--tv-brand);
  color: #fff;
  font-weight: 650;
}
.teacher-view .btn-filled:hover:not(:disabled) {
  background: var(--tv-brand-hover);
  transform: translateY(-1px);
  box-shadow: 0 10px 20px -12px rgba(249, 115, 22, 0.55);
}
.teacher-view .btn-filled:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.32);
}
.teacher-view .btn-filled:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.teacher-view .btn-tonal {
  border: 1px solid transparent;
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  font-weight: 600;
}
.teacher-view .btn-tonal:hover {
  background: #FFE4CC;
}

.teacher-view .btn-tonal-sm,
.teacher-view .btn-filled-sm {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  transition: all var(--tv-dur) var(--tv-ease);
}
.teacher-view .btn-tonal-sm {
  border: 1px solid var(--tv-line);
  background: var(--tv-panel-2);
  color: var(--tv-ink-2);
}
.teacher-view .btn-tonal-sm:hover {
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  border-color: var(--tv-brand-line);
}
.teacher-view .btn-filled-sm {
  border: none;
  background: var(--tv-brand);
  color: #fff;
}
.teacher-view .btn-filled-sm:hover {
  background: var(--tv-brand-hover);
}

/* ---------- Text link + Icon button + Chips ---------- */
.teacher-view .text-link {
  padding: 4px 10px;
  border: none;
  background: transparent;
  color: var(--tv-brand-ink);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 8px;
  transition: background var(--tv-dur) var(--tv-ease);
}
.teacher-view .text-link:hover {
  background: var(--tv-brand-soft);
}

.teacher-view .icon-btn {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: var(--tv-ink-2);
  cursor: pointer;
  transition: background var(--tv-dur) var(--tv-ease);
}
.teacher-view .icon-btn:hover {
  background: var(--tv-panel-2);
  color: var(--tv-brand-ink);
}

.teacher-view .trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
}
.teacher-view .trend-chip.up { background: var(--tv-ok-soft); color: var(--tv-ok); }
.teacher-view .trend-chip.down { background: var(--tv-err-soft); color: var(--tv-err); }

.teacher-view .mini-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* ---------- 2. Workbench 两栏布局 ---------- */
.teacher-view .workbench-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(340px, 1fr);
  gap: 20px;
  align-items: flex-start;
}

.teacher-view .workbench-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.teacher-view .workbench-main .row {
  display: grid;
  gap: 16px;
}

.teacher-view .workbench-main .action-row {
  grid-template-columns: 3fr 2fr;
  align-items: stretch;
}

.teacher-view .workbench-main .analytics-row {
  grid-template-columns: 1fr 1fr;
  align-items: stretch;
}

.teacher-view .workbench-main .secondary-row {
  grid-template-columns: 3fr 2fr;
  align-items: stretch;
}

.teacher-view .workbench-main .card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
  padding: 20px 22px;
}

.teacher-view .card-h3-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}

.teacher-view .card-h3-row h3 {
  margin: 0;
  font-size: 15.5px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--tv-ink);
}

.teacher-view .card-h3-row small {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  color: var(--tv-muted);
  font-weight: 400;
}

/* ---------- 3. 今日行动 ---------- */
.teacher-view .action-panel .action-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.teacher-view .action-item {
  position: relative;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--tv-panel);
  border: 1px solid var(--tv-line);
  transition: background var(--tv-dur) var(--tv-ease), border-color var(--tv-dur) var(--tv-ease), transform var(--tv-dur) var(--tv-ease);
  cursor: default;
}

.teacher-view .action-item:hover {
  background: var(--tv-panel-2);
  border-color: var(--tv-line-2);
}

.teacher-view .action-item.high {
  border-left: 3px solid var(--tv-brand);
}

.teacher-view .action-item.medium {
  border-left: 3px solid var(--tv-warn);
}

.teacher-view .action-item.low {
  border-left: 3px solid var(--tv-line-2);
}

.teacher-view .action-rank {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--tv-panel-2);
  color: var(--tv-muted);
  font-size: 14px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.teacher-view .action-item.high .action-rank {
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}

.teacher-view .action-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.teacher-view .action-body b {
  font-size: 14px;
  font-weight: 650;
  color: var(--tv-ink);
  line-height: 1.35;
}

.teacher-view .action-body small {
  font-size: 12px;
  line-height: 1.55;
  color: var(--tv-muted);
}

.teacher-view .action-badges {
  display: flex;
  gap: 6px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.teacher-view .action-cta {
  flex-shrink: 0;
}

/* ---------- 4. 掌握度分布 Donut ---------- */
.teacher-view .donut-panel {
  align-items: stretch;
}

.teacher-view .donut-canvas {
  width: 100%;
  height: 240px;
  min-height: 200px;
}

.teacher-view .donut-canvas.donut-mid {
  height: 200px;
}

.teacher-view .donut-legend {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.teacher-view .donut-legend.compact {
  gap: 4px;
}

.teacher-view .donut-legend li {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  padding: 6px 8px;
  border-radius: 8px;
  transition: background var(--tv-dur) var(--tv-ease);
}

.teacher-view .donut-legend li:hover {
  background: var(--tv-panel-2);
}

.teacher-view .donut-legend i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  display: block;
}

.teacher-view .donut-legend span {
  font-size: 12.5px;
  color: var(--tv-ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.teacher-view .donut-legend b {
  font-size: 12.5px;
  color: var(--tv-ink);
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.teacher-view .donut-legend em {
  font-style: normal;
  font-size: 11.5px;
  color: var(--tv-muted);
  min-width: 32px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* ---------- 5. 薄弱 KP TOP5 ---------- */
.teacher-view .weak-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.teacher-view .weak-row {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 88px;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border-radius: 10px;
  transition: background var(--tv-dur) var(--tv-ease);
}

.teacher-view .weak-row:hover {
  background: var(--tv-panel-2);
}

.teacher-view .weak-idx {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--tv-panel-2);
  color: var(--tv-brand-ink);
  font-size: 12px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.teacher-view .weak-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.teacher-view .weak-info b {
  font-size: 13px;
  font-weight: 600;
  color: var(--tv-ink);
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.teacher-view .weak-info small {
  font-size: 11px;
  color: var(--tv-muted);
}

.teacher-view .weak-progress-track {
  height: 4px;
  border-radius: 999px;
  background: var(--tv-line);
  overflow: hidden;
}

.teacher-view .weak-progress-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 500ms var(--tv-ease);
}

.teacher-view .weak-value {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}

.teacher-view .weak-value > b {
  font-size: 16px;
  font-weight: 750;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.teacher-view .weak-value > b span {
  font-size: 11px;
  font-weight: 500;
  color: var(--tv-muted);
  margin-left: 1px;
}

.teacher-view .weak-cta {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--tv-line);
  background: var(--tv-panel);
  color: var(--tv-brand-ink);
  cursor: pointer;
  transition: all var(--tv-dur) var(--tv-ease);
}

.teacher-view .weak-cta:hover {
  background: var(--tv-brand-soft);
  border-color: var(--tv-brand-line);
}

/* ---------- 6. 优先干预名单 v3 ---------- */
.teacher-view .risk-list-v3 {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.teacher-view .risk-row-v3 {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--tv-panel);
  border: 1px solid var(--tv-line);
  transition: all var(--tv-dur) var(--tv-ease);
}

.teacher-view .risk-row-v3:hover {
  border-color: var(--tv-line-2);
  background: var(--tv-panel-2);
}

.teacher-view .risk-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.teacher-view .risk-dot.high { background: var(--tv-err); box-shadow: 0 0 0 3px var(--tv-err-soft); }
.teacher-view .risk-dot.medium { background: var(--tv-warn); box-shadow: 0 0 0 3px var(--tv-warn-soft); }
.teacher-view .risk-dot.low { background: var(--tv-info); box-shadow: 0 0 0 3px var(--tv-info-soft); }

.teacher-view .risk-info {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.teacher-view .risk-info b {
  font-size: 13px;
  font-weight: 600;
  color: var(--tv-ink);
  font-family: var(--mono, inherit);
}

.teacher-view .risk-info small {
  font-size: 11.5px;
  color: var(--tv-muted);
  line-height: 1.45;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
}

.teacher-view .risk-badge-v3 {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.teacher-view .risk-badge-v3.high { background: var(--tv-err-soft); color: var(--tv-err); }
.teacher-view .risk-badge-v3.medium { background: var(--tv-warn-soft); color: var(--tv-warn); }
.teacher-view .risk-badge-v3.low { background: var(--tv-info-soft); color: var(--tv-info); }

.teacher-view .risk-actions-v3 {
  display: flex;
  gap: 6px;
}

/* ---------- 7. 活跃度分布 v3 ---------- */
.teacher-view .activity-card {
  gap: 16px;
}

.teacher-view .activity-hero-v3 {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.teacher-view .activity-big b {
  display: block;
  font-size: 38px;
  line-height: 1;
  font-weight: 800;
  color: #16A34A;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
}

.teacher-view .activity-big b span {
  font-size: 18px;
  font-weight: 650;
  color: #16A34A;
}

.teacher-view .activity-big small {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--tv-muted);
}

.teacher-view .activity-detail {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.teacher-view .activity-row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto auto;
  gap: 8px;
  align-items: center;
  font-size: 12px;
  color: var(--tv-ink-2);
}

.teacher-view .activity-row .dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.teacher-view .activity-row .label {
  color: var(--tv-muted);
}

.teacher-view .activity-row b {
  font-weight: 700;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
}

.teacher-view .activity-row em {
  font-style: normal;
  font-size: 10.5px;
  color: var(--tv-muted);
  min-width: 32px;
  text-align: right;
}

.teacher-view .activity-card .activity-stack {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--tv-line);
  margin-top: 6px;
}

.teacher-view .activity-card .activity-stack > span {
  display: block;
  height: 100%;
  transition: width 500ms var(--tv-ease);
}

/* ---------- 8. 30 天趋势 · 整卡 ---------- */
.teacher-view .trend-card-full {
  min-height: 380px;
}

.teacher-view .trend-latest-inline {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--tv-muted);
}

.teacher-view .trend-latest-inline b {
  font-size: 15px;
  font-weight: 750;
  color: var(--tv-ink);
  font-variant-numeric: tabular-nums;
}

/* ---------- 9. AI Copilot Panel · 右侧固定栏 ---------- */
.teacher-view .copilot-panel {
  position: sticky;
  top: 82px;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 100px);
  border-radius: 20px;
  border: 1px solid var(--wb-ai-line);
  background:
    linear-gradient(180deg, var(--wb-ai-soft) 0%, #fff 30%);
  overflow: hidden;
  box-shadow: 0 12px 32px -20px rgba(124, 92, 252, 0.35);
}

.teacher-view .copilot-panel.collapsed {
  max-height: 68px;
}

.teacher-view .copilot-panel.collapsed .copilot-fleet,
.teacher-view .copilot-panel.collapsed .copilot-messages,
.teacher-view .copilot-panel.collapsed .copilot-suggestions,
.teacher-view .copilot-panel.collapsed .copilot-input {
  display: none;
}

.teacher-view .copilot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
}

.teacher-view .copilot-header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.teacher-view .copilot-avatar {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(135deg, #b9a2ff, #7C5CFC);
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 12px -8px rgba(124, 92, 252, 0.55);
}

.teacher-view .copilot-header-title b {
  font-size: 14px;
  font-weight: 700;
  color: var(--tv-ink);
  display: block;
  line-height: 1.2;
}

.teacher-view .copilot-header-title small {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--tv-muted);
}

.teacher-view .beta-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--wb-ai);
  color: #fff;
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.06em;
  margin-right: 4px;
}

/* ---------- 10. Copilot Fleet Bar · 6 Agent ---------- */
.teacher-view .copilot-fleet {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 6px;
  padding: 14px 12px;
  border-bottom: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.5);
}

.teacher-view .fleet-agent {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 4px 2px;
  border-radius: 8px;
  transition: background var(--tv-dur) var(--tv-ease);
}

.teacher-view .fleet-agent:hover {
  background: rgba(124, 92, 252, 0.08);
}

.teacher-view .fleet-avatar {
  position: relative;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  overflow: visible;
  background: var(--tv-panel-2);
}

.teacher-view .fleet-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.teacher-view .fleet-fallback {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  border-radius: 50%;
  z-index: -1;
}

.teacher-view .fleet-online {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.05);
}

.teacher-view .fleet-agent small {
  font-size: 10.5px;
  color: var(--tv-ink-2);
  font-weight: 550;
  white-space: nowrap;
}

/* ---------- 11. Copilot Messages ---------- */
.teacher-view .copilot-messages {
  flex: 1;
  min-height: 200px;
  max-height: 420px;
  padding: 14px 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.teacher-view .copilot-messages::-webkit-scrollbar {
  width: 6px;
}
.teacher-view .copilot-messages::-webkit-scrollbar-thumb {
  background: var(--tv-line-2);
  border-radius: 3px;
}

.teacher-view .msg {
  animation: msg-in 320ms var(--tv-ease);
}

@keyframes msg-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.teacher-view .msg-ai .msg-content {
  padding: 12px 14px;
  border-radius: 4px 14px 14px 14px;
  background: #fff;
  border: 1px solid var(--wb-ai-line);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--tv-ink);
}

.teacher-view .msg-ai .msg-content :deep(p) {
  margin: 0 0 6px;
}

.teacher-view .msg-ai .msg-content :deep(ul),
.teacher-view .msg-ai .msg-content :deep(ol) {
  margin: 0 0 6px;
  padding-left: 18px;
}

.teacher-view .msg-agents {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed var(--tv-line);
  flex-wrap: wrap;
  font-size: 11px;
  color: var(--tv-muted);
}

.teacher-view .msg-agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--wb-ai-soft);
  color: var(--wb-ai-ink);
  font-size: 11px;
  font-weight: 650;
  border: 1px solid var(--wb-ai-line);
}

.teacher-view .msg-agent-chip img {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  object-fit: cover;
}

.teacher-view .msg-agent-chip.failed {
  background: var(--tv-err-soft);
  color: var(--tv-err);
  border-color: #fca5a5;
}

/* Loading state · MD3 Linear Progress */
.teacher-view .msg-loading {
  padding: 12px 14px;
  border-radius: 4px 14px 14px 14px;
  background: #fff;
  border: 1px solid var(--wb-ai-line);
}

.teacher-view .loading-agent {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.teacher-view .loading-agent-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}

.teacher-view .loading-agent-info {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.teacher-view .loading-agent-info b {
  font-size: 12.5px;
  font-weight: 700;
  color: var(--tv-ink);
}

.teacher-view .loading-agent-info small {
  font-size: 11px;
  color: var(--tv-muted);
}

.teacher-view .linear-progress {
  position: relative;
  width: 100%;
  height: 3px;
  background: var(--wb-ai-soft);
  border-radius: 3px;
  overflow: hidden;
}

.teacher-view .linear-progress span {
  position: absolute;
  height: 100%;
  width: 30%;
  border-radius: 3px;
  background: linear-gradient(90deg, transparent, var(--wb-ai), transparent);
  animation: linear-slide 1.4s ease-in-out infinite;
}

@keyframes linear-slide {
  0% { left: -30%; }
  100% { left: 100%; }
}

.teacher-view .msg-teacher {
  align-self: flex-end;
  max-width: 82%;
}

.teacher-view .msg-teacher p {
  margin: 0;
  padding: 10px 14px;
  border-radius: 14px 14px 4px 14px;
  background: var(--tv-brand);
  color: #fff;
  font-size: 12.5px;
  line-height: 1.55;
  box-shadow: 0 4px 10px -6px rgba(249, 115, 22, 0.35);
}

/* ---------- 12. Copilot Suggestions ---------- */
.teacher-view .copilot-suggestions {
  padding: 10px 14px 6px;
  border-top: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.5);
}

.teacher-view .section-note {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--tv-muted);
  font-weight: 550;
}

.teacher-view .chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.teacher-view .suggest-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.75);
  color: var(--wb-ai-ink);
  font-size: 11.5px;
  font-weight: 550;
  cursor: pointer;
  transition: all var(--tv-dur) var(--tv-ease);
  font-family: inherit;
}

.teacher-view .suggest-chip:hover:not(:disabled) {
  background: var(--wb-ai-soft);
  border-color: var(--wb-ai);
  transform: translateY(-1px);
}

.teacher-view .suggest-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---------- 13. Copilot Input ---------- */
.teacher-view .copilot-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 14px 14px;
  border-top: 1px solid var(--wb-ai-line);
  background: rgba(255, 255, 255, 0.75);
}

.teacher-view .copilot-input textarea {
  flex: 1;
  min-height: 46px;
  max-height: 120px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  font-size: 12.5px;
  line-height: 1.55;
  font-family: inherit;
  resize: none;
  color: var(--tv-ink);
  transition: border-color var(--tv-dur) var(--tv-ease), box-shadow var(--tv-dur) var(--tv-ease);
}

.teacher-view .copilot-input textarea:focus {
  outline: none;
  border-color: var(--wb-ai);
  box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.18);
}

.teacher-view .copilot-input textarea:disabled {
  background: var(--tv-panel-2);
  cursor: not-allowed;
}

.teacher-view .input-send {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border-radius: 12px;
  flex-shrink: 0;
}

/* ============================================================
 * 响应式：1180 / 768 / 480
 * ============================================================ */
@media (max-width: 1180px) {
  .teacher-view .workbench-grid {
    grid-template-columns: 1fr;
  }
  .teacher-view .copilot-panel {
    position: static;
    max-height: none;
  }
  .teacher-view .copilot-messages {
    max-height: 380px;
  }
  .teacher-view .insight-surface {
    grid-template-columns: 1fr;
    gap: 20px;
    padding: 24px;
  }
  .teacher-view .insight-orb {
    justify-self: start;
    width: 120px;
    height: 120px;
  }
  .teacher-view .insight-orb .orb-core {
    inset: 22px;
  }
}

@media (max-width: 768px) {
  .teacher-view .workbench-main .action-row,
  .teacher-view .workbench-main .analytics-row,
  .teacher-view .workbench-main .secondary-row {
    grid-template-columns: 1fr;
  }
  .teacher-view .insight-title {
    font-size: 18px;
  }
  .teacher-view .activity-hero-v3 {
    grid-template-columns: 1fr;
  }
  .teacher-view .risk-row-v3 {
    grid-template-columns: 10px minmax(0, 1fr);
    row-gap: 8px;
  }
  .teacher-view .risk-actions-v3,
  .teacher-view .risk-badge-v3 {
    grid-column: 2;
    justify-self: start;
  }
  .teacher-view .copilot-fleet {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* ============================================================
 * Studio · 教师提示词工作台
 * ============================================================ */
.teacher-view .studio-workspace {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: 20px;
  align-items: start;
}

.teacher-view .studio-editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 24px;
  min-height: 620px;
}

.teacher-view .studio-editor-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px dashed var(--tv-line);
}

.teacher-view .studio-editor-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--tv-brand-ink);
}

.teacher-view .studio-editor-head h3 svg {
  color: var(--tv-brand);
}

.teacher-view .studio-editor-head small {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--tv-muted);
}

.teacher-view .studio-agent-strip {
  display: flex;
  gap: -4px;
  flex-shrink: 0;
}

.teacher-view .studio-agent-avatar {
  position: relative;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--tv-panel-2);
  margin-left: -6px;
  border: 2px solid #fff;
  box-shadow: 0 1px 2px rgba(20, 24, 28, 0.08);
}

.teacher-view .studio-agent-avatar:first-child { margin-left: 0; }

.teacher-view .studio-agent-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.teacher-view .studio-agent-fallback {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  z-index: -1;
}

.teacher-view .studio-type-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.teacher-view .studio-type-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  color: var(--tv-ink-2);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 220ms cubic-bezier(0.2, 0, 0, 1);
}

.teacher-view .studio-type-chip:hover:not(.active) {
  border-color: var(--tv-brand-line);
  color: var(--tv-brand-ink);
  background: var(--tv-brand-soft);
}

.teacher-view .studio-type-chip.active {
  background: var(--tv-brand);
  color: #fff;
  border-color: var(--tv-brand);
}

.teacher-view .studio-type-hint {
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--tv-panel-2);
  border-left: 3px solid var(--tv-brand);
  font-size: 12px;
  color: var(--tv-ink-2);
  line-height: 1.55;
}

.teacher-view .studio-label {
  display: block;
  font-size: 11.5px;
  font-weight: 650;
  color: var(--tv-ink-2);
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

.teacher-view .studio-editor textarea {
  min-height: 140px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  font-size: 13.5px;
  line-height: 1.65;
  color: var(--tv-ink);
  font-family: inherit;
  resize: vertical;
  transition: border-color 220ms, box-shadow 220ms;
}

.teacher-view .studio-editor textarea:focus {
  outline: none;
  border-color: var(--tv-brand);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.18);
}

.teacher-view .studio-editor textarea:disabled {
  background: var(--tv-panel-2);
  cursor: not-allowed;
}

.teacher-view .studio-hint-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.teacher-view .studio-hint-row small {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tv-muted);
  margin-right: 4px;
}

.teacher-view .studio-hint-chip {
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px dashed var(--tv-line-2);
  background: transparent;
  color: var(--tv-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 220ms;
}

.teacher-view .studio-hint-chip:hover {
  border-color: var(--tv-brand-line);
  border-style: solid;
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}

.teacher-view .studio-scope-row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 16px;
  align-items: end;
  padding-top: 8px;
}

.teacher-view .studio-scope-row select {
  height: 40px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  font-size: 13px;
  color: var(--tv-ink);
}

.teacher-view .studio-submit-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px dashed var(--tv-line);
}

/* ---------- 右侧生成预览 ---------- */
.teacher-view .studio-preview {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 22px;
  min-height: 620px;
  max-height: calc(100vh - 200px);
  overflow: hidden;
  position: sticky;
  top: 82px;
}

.teacher-view .studio-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--tv-line);
}

.teacher-view .studio-preview-head h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--tv-ink);
}

.teacher-view .studio-preview-head small {
  display: block;
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--tv-muted);
}

.teacher-view .studio-agents-mini {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.teacher-view .studio-agent-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--tv-brand-soft);
  border: 1px solid var(--tv-brand-line);
  color: var(--tv-brand-ink);
  font-size: 10.5px;
  font-weight: 650;
}

.teacher-view .studio-agent-chip img {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  object-fit: cover;
}

.teacher-view .studio-agent-chip.failed {
  background: var(--tv-err-soft);
  color: var(--tv-err);
  border-color: #fca5a5;
}

.teacher-view .studio-loading {
  padding: 20px;
  border-radius: 12px;
  background: var(--tv-brand-soft);
  border: 1px solid var(--tv-brand-line);
}

.teacher-view .studio-result {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--tv-line);
  font-size: 13px;
  line-height: 1.7;
  color: var(--tv-ink);
}

.teacher-view .studio-result :deep(h1),
.teacher-view .studio-result :deep(h2),
.teacher-view .studio-result :deep(h3) {
  color: var(--tv-brand-ink);
  margin-top: 12px;
  margin-bottom: 6px;
}

.teacher-view .studio-result :deep(p) { margin: 0 0 8px; }
.teacher-view .studio-result :deep(ul),
.teacher-view .studio-result :deep(ol) { margin: 0 0 8px; padding-left: 20px; }

.teacher-view .studio-binary-result {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid #a7d8bd;
  border-radius: 10px;
  background: #f2fbf6;
  color: #17633a;
}

.teacher-view .studio-binary-result > div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.teacher-view .studio-binary-result small {
  overflow: hidden;
  color: var(--tv-ink-3);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.teacher-view .studio-binary-result .ghost-btn {
  flex: 0 0 auto;
  text-decoration: none;
}

.teacher-view .studio-binary-error {
  margin: 16px 0 0;
  padding: 12px 14px;
  border: 1px solid #efb1a4;
  border-radius: 10px;
  background: #fff5f2;
  color: #9d2f1d;
  line-height: 1.6;
}

.teacher-view .studio-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--tv-line);
}

.teacher-view .studio-empty {
  flex: 1;
  display: grid;
  place-content: center;
  text-align: center;
  color: var(--tv-muted);
  gap: 6px;
}

.teacher-view .studio-empty svg {
  color: var(--tv-brand-line);
  margin: 0 auto;
}

.teacher-view .studio-empty p {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.55;
}

.teacher-view .studio-empty p b {
  font-size: 14px;
  color: var(--tv-ink);
  font-weight: 700;
}

/* ---------- 直接上传行 ---------- */
.teacher-view .studio-upload-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px;
  border-radius: 14px;
  border: 1px dashed var(--tv-line-2);
  background: linear-gradient(180deg, var(--tv-panel-2) 0%, #fff 100%);
  flex-wrap: wrap;
}

.teacher-view .studio-upload-row > div:first-child b {
  display: block;
  font-size: 13.5px;
  font-weight: 700;
  color: var(--tv-ink);
  margin-bottom: 3px;
}

.teacher-view .studio-upload-row > div:first-child small {
  font-size: 11.5px;
  color: var(--tv-muted);
}

.teacher-view .studio-upload-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.teacher-view .studio-list-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0 -4px;
  font-size: 12px;
  font-weight: 650;
  color: var(--tv-muted);
  letter-spacing: 0.02em;
}

.teacher-view .studio-list-divider::before,
.teacher-view .studio-list-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--tv-line);
}

@media (max-width: 1180px) {
  .teacher-view .studio-workspace {
    grid-template-columns: 1fr;
  }
  .teacher-view .studio-preview {
    position: static;
    max-height: none;
  }
}

/* ============================================================
 * 教学干预 · 一键干预面板
 * ============================================================ */
.teacher-view .quick-intervention-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 16px;
  border: 1px solid var(--tv-brand-line);
  background: linear-gradient(180deg, var(--tv-brand-soft) 0%, #fff 40%);
  box-shadow: 0 1px 2px rgba(20, 24, 28, 0.04), 0 8px 24px -20px rgba(20, 24, 28, 0.12);
}

.teacher-view .qi-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.teacher-view .qi-head h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--tv-brand-ink);
}

.teacher-view .qi-head h3 svg {
  color: var(--tv-brand);
}

.teacher-view .qi-head small {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--tv-muted);
}

.teacher-view .qi-mode-switch {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid var(--tv-line);
}

.teacher-view .qi-mode-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: var(--tv-muted);
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 220ms cubic-bezier(0.2, 0, 0, 1);
}

.teacher-view .qi-mode-btn:hover:not(.active) {
  color: var(--tv-brand-ink);
  background: rgba(249, 115, 22, 0.08);
}

.teacher-view .qi-mode-btn.active {
  background: #fff;
  color: var(--tv-brand-ink);
  box-shadow: 0 1px 3px rgba(20, 24, 28, 0.1);
}

.teacher-view .qi-target-row {
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid var(--tv-line);
}

.teacher-view .qi-label {
  display: block;
  margin-bottom: 8px;
  font-size: 11.5px;
  font-weight: 650;
  color: var(--tv-ink-2);
  letter-spacing: 0.02em;
}

.teacher-view .qi-label em {
  font-style: normal;
  color: var(--tv-brand-ink);
  font-weight: 700;
  margin-left: 4px;
}

.teacher-view .qi-target-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.teacher-view .qi-target-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  color: var(--tv-ink-2);
  font-size: 12px;
  font-weight: 550;
  cursor: pointer;
  transition: all 220ms;
}

.teacher-view .qi-target-chip:hover {
  border-color: var(--tv-brand-line);
  color: var(--tv-brand-ink);
}

.teacher-view .qi-target-chip.active {
  background: var(--tv-brand);
  color: #fff;
  border-color: var(--tv-brand);
}

.teacher-view .qi-target-meta {
  font-style: normal;
  font-size: 10.5px;
  opacity: 0.75;
  font-variant-numeric: tabular-nums;
}

.teacher-view .qi-target-quick {
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px dashed var(--tv-brand-line);
  background: transparent;
  color: var(--tv-brand-ink);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 220ms;
}

.teacher-view .qi-target-quick:hover {
  background: var(--tv-brand-soft);
  border-style: solid;
}

.teacher-view .qi-target-quick.clear {
  border-color: var(--tv-line-2);
  color: var(--tv-muted);
}

.teacher-view .qi-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid var(--tv-line);
}

.teacher-view .qi-form textarea,
.teacher-view .qi-form input,
.teacher-view .qi-form select {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  font-size: 13px;
  line-height: 1.55;
  color: var(--tv-ink);
  font-family: inherit;
  transition: border-color 220ms, box-shadow 220ms;
  resize: vertical;
}

.teacher-view .qi-form textarea:focus,
.teacher-view .qi-form input:focus,
.teacher-view .qi-form select:focus {
  outline: none;
  border-color: var(--tv-brand);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.18);
}

.teacher-view .qi-empty-hint {
  margin: 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--tv-panel-2);
  color: var(--tv-muted);
  font-size: 12px;
}

.teacher-view .qi-templates {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--tv-line);
}

.teacher-view .qi-templates-label {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--tv-muted);
  margin-right: 4px;
}

.teacher-view .qi-template-chip {
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--tv-line-2);
  background: #fff;
  color: var(--tv-ink-2);
  font-size: 11.5px;
  font-weight: 550;
  cursor: pointer;
  transition: all 220ms;
}

.teacher-view .qi-template-chip:hover {
  border-color: var(--tv-brand-line);
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}

.teacher-view .qi-ai-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid #D8CCFB;
  background: #F5F1FF;
  color: #5B3FE0;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 220ms;
}

.teacher-view .qi-ai-btn:hover:not(:disabled) {
  background: #EAE0FF;
  transform: translateY(-1px);
}

.teacher-view .qi-ai-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.teacher-view .qi-submit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.teacher-view .qi-submit-hint {
  font-size: 12px;
  color: var(--tv-ink-2);
}

.teacher-view .qi-submit-hint.muted {
  color: var(--tv-muted);
}

.teacher-view .qi-submit-hint b {
  color: var(--tv-brand-ink);
  font-weight: 700;
}

/* ============================================================
 * 认知分析 · 遗忘曲线 ECharts 容器
 * ============================================================ */
.teacher-view .forecast-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.teacher-view .forecast-echarts {
  width: 100%;
  height: 260px;
  min-height: 220px;
  border-radius: var(--tv-r-sm);
  background: linear-gradient(180deg, rgba(255, 244, 232, 0.35) 0%, rgba(255, 255, 255, 0) 55%);
}

.teacher-view .forecast-card .insight-forecast {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--tv-r-sm);
  border: 1px solid var(--tv-line);
  background: var(--tv-panel-2);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--tv-ink-2);
}

/* ============================================================
 * 知识图谱 Tab · 底部节点被 border-radius 裁切修复
 * 原因：.knowledge-workspace 用了 overflow: hidden + border-radius: 14px，
 *      导致 SVG 底部圆角处内容被裁；min-height 也不足以容纳 4 行节点。
 * ============================================================ */
.teacher-view .knowledge-workspace {
  overflow: visible;
  min-height: 720px;
}
.teacher-view .knowledge-canvas {
  overflow: visible;
  border-radius: 14px 0 0 14px;
}
.teacher-view .knowledge-svg-scroll {
  min-height: 620px;
  padding-bottom: 28px;
  border-radius: 0 0 0 14px;
}

/* ============================================================
 * Stitch editorial convergence · 2026-07-11
 * Single source of visual truth for every teacher route.
 * ============================================================ */
.teacher-view {
  --tv-ink: #17202a;
  --tv-ink-2: #344255;
  --tv-muted: #617083;
  --tv-faint: #8a96a5;
  --tv-line: #eadbd3;
  --tv-line-2: #dfc6b8;
  --tv-bg: #fff7f1;
  --tv-panel: #fffefd;
  --tv-panel-2: #fffaf6;
  --tv-brand: #e95514;
  --tv-brand-hover: #cf430d;
  --tv-brand-ink: #a9340a;
  --tv-brand-soft: #fff1ea;
  --tv-brand-line: #f2b79d;
  --tv-ai: #2f6fed;
  --tv-ai-ink: #2458bd;
  --tv-ai-soft: #eef4ff;
  --tv-ai-line: #c9dafc;
  --tv-ok: #1f9d6a;
  --tv-ok-soft: #eaf8f2;
  --tv-warn: #d99100;
  --tv-warn-soft: #fff7e6;
  --tv-err: #d64545;
  --tv-err-soft: #fff0f0;
  --tv-info: #2f6fed;
  --tv-info-soft: #eef4ff;
  --tv-elev-1: 0 1px 2px rgba(23, 32, 42, 0.025);
  --tv-elev-2: 0 6px 18px rgba(23, 32, 42, 0.07);
  --tv-r-lg: 12px;
  --tv-r-md: 10px;
  --tv-r-sm: 8px;
  width: min(1520px, calc(100vw - 64px));
  max-width: 1520px;
  gap: 28px;
  padding: 24px 0 64px;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
}

.teacher-view::before {
  display: none;
}

/* Header is a command header, not another floating card. */
.teacher-view .teacher-appbar {
  gap: 12px;
  padding: 8px 4px 4px;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.teacher-view .teacher-appbar-title h1 {
  font-size: clamp(27px, 2.2vw, 32px);
  line-height: 1.22;
  font-weight: 760;
  letter-spacing: -0.035em;
}
.teacher-view .teacher-appbar-title p {
  max-width: 72ch;
  margin-top: 7px;
  color: var(--tv-muted);
  font-size: 14px;
  line-height: 1.65;
}
.teacher-view .crumb-chip {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--tv-brand-ink);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .04em;
}
.teacher-view .appbar-action {
  min-height: 44px;
  padding-inline: 16px;
  border-color: var(--tv-line-2);
  border-radius: 8px;
  background: var(--tv-panel);
  box-shadow: none;
}

/* Navigation and filters keep context while data scrolls. */
.teacher-view .teacher-tabs {
  position: sticky;
  top: 0;
  z-index: 28;
  min-height: 56px;
  padding: 4px 8px 0;
  border: 1px solid rgba(207, 215, 225, .82);
  border-radius: 10px;
  background: rgba(255, 255, 255, .86);
  box-shadow: 0 4px 16px rgba(23, 32, 42, .045);
  backdrop-filter: blur(16px) saturate(1.25);
}
.teacher-view .tab-btn { min-height: 48px; padding-inline: 6px; }
.teacher-view .tab-btn.active .tab-inner { background: #fff1ea; }
.teacher-view .tab-indicator { height: 2px; border-radius: 2px 2px 0 0; }
.teacher-view .student-bar {
  top: 64px;
  min-height: 58px;
  border-color: rgba(207, 215, 225, .82);
  border-radius: 10px;
  background: rgba(255, 255, 255, .88);
  box-shadow: 0 4px 16px rgba(23, 32, 42, .045);
}

/* One restrained surface language across all routes. */
.teacher-view .card,
.teacher-view .knowledge-focus-overview,
.teacher-view .knowledge-workspace,
.teacher-view .copilot-workbench,
.teacher-view .copilot-result {
  border-color: var(--tv-line);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--tv-elev-1);
}
.teacher-view .card { padding: 24px; }
.teacher-view .card:hover { border-color: var(--tv-line-2); box-shadow: 0 4px 8px rgba(126, 75, 47, .07); }
.teacher-view .card h3,
.teacher-view .card-h3-row h3 {
  color: var(--tv-ink);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -.015em;
}
.teacher-view .grid-two { gap: 20px; }
.teacher-view .tab-panel { gap: 24px; }

/* Stitch KPI rail: continuous data band with dividers, no decorative stripe. */
.teacher-view .kpi-grid {
  padding: 0;
  border-radius: 10px;
  background: var(--tv-panel);
  box-shadow: var(--tv-elev-1);
}
.teacher-view .kpi-grid::before { display: none; }
.teacher-view .kpi-card { min-height: 112px; padding: 24px 28px; }
.teacher-view .kpi-card:hover { background: #fff4ed; }
.teacher-view .kpi-card small { font-size: 12.5px; font-weight: 600; }
.teacher-view .kpi-card b { font-size: 30px; }

/* Board: convert the decorative AI hero into a compact decision brief. */
.teacher-view .board-panel { gap: 24px; }
.teacher-view .insight-surface {
  display: block;
  padding: 24px 28px;
  border: 1px solid #dbe3ec;
  border-left: 3px solid var(--tv-ai);
  border-radius: 10px;
  background: var(--tv-panel);
  overflow: visible;
}
.teacher-view .insight-orb { display: none; }
.teacher-view .insight-copy { gap: 10px; }
.teacher-view .insight-chip {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--tv-ai-ink);
  animation: none;
  backdrop-filter: none;
}
.teacher-view .insight-chip .chip-icon { animation: none; }
.teacher-view .insight-title { max-width: 1000px; font-size: clamp(18px, 1.6vw, 22px); line-height: 1.55; }
.teacher-view .insight-title b { color: var(--tv-ink); }
.teacher-view .workbench-grid { grid-template-columns: minmax(0, 1fr) 360px; gap: 24px; }
.teacher-view .workbench-main { gap: 24px; }
.teacher-view .workbench-main .row { gap: 20px; }
.teacher-view .workbench-main .action-row { grid-template-columns: minmax(0, 1.35fr) minmax(300px, .65fr); }
.teacher-view .workbench-main .analytics-row { grid-template-columns: minmax(0, 1.2fr) minmax(300px, .8fr); }
.teacher-view .copilot-panel { border-radius: 10px; box-shadow: var(--tv-elev-1); }
/* 教学共创的结果是页面正文，不是右侧固定 Copilot 栏；不能继承其视口高度与裁剪。 */
.teacher-view .tab-panel.copilot-panel {
  position: static;
  max-height: none;
  overflow: visible;
  isolation: auto;
}
.teacher-view .trend-echarts-wrap,
.teacher-view .forecast-echarts { background: var(--tv-panel); }

/* Knowledge graph: focus strip → glass controls → panoramic canvas. */
.teacher-view .knowledge-coverage-strip {
  overflow: hidden;
  border: 1px solid var(--tv-line);
  border-radius: 10px;
  background: var(--tv-panel);
}
.teacher-view .knowledge-coverage-strip > div { padding: 20px 24px; }
.teacher-view .knowledge-focus-overview > header { padding: 22px 24px 18px; border-bottom-color: var(--tv-line); }
.teacher-view .knowledge-focus-overview h2 { font-size: 19px; }
.teacher-view .knowledge-focus-list {
  grid-template-columns: repeat(auto-fit, minmax(205px, 1fr));
  padding: 0 16px 10px;
}
.teacher-view .knowledge-focus-list li { padding: 0 12px !important; border-left: 1px solid var(--tv-line); }
.teacher-view .knowledge-focus-list li:first-child { border-left: 0; }
.teacher-view .knowledge-focus-list button {
  grid-template-columns: 28px minmax(0, 1fr) auto;
  min-height: 90px;
  border-bottom: 0;
}
.teacher-view .knowledge-workspace {
  grid-template-columns: minmax(0, 1fr) 360px;
  min-height: 760px;
  overflow: hidden;
}
.teacher-view .knowledge-canvas { overflow: hidden; border-radius: 10px 0 0 10px; }
.teacher-view .knowledge-canvas-head { padding: 24px 26px 20px; border-bottom: 1px solid var(--tv-line); background: var(--tv-panel); }
.teacher-view .knowledge-toolrail {
  position: sticky;
  top: 0;
  z-index: 8;
  padding: 14px 18px;
  border-bottom-color: var(--tv-line);
  background: rgba(255, 250, 246, .92);
  backdrop-filter: blur(14px) saturate(1.2);
}
.teacher-view .knowledge-svg-scroll {
  min-height: 620px;
  overflow: auto;
  border-radius: 0;
  background-color: #fffaf6;
  background-image: radial-gradient(#eadbd3 1px, transparent 1px);
  background-size: 22px 22px;
}
.teacher-view .knowledge-edge { stroke: #9aa8b8; }
.teacher-view .knowledge-edge:not(.relation-prerequisite) { stroke: #7b91aa; }
.teacher-view .knowledge-inspector {
  padding: 28px 26px;
  border-left: 1px solid var(--tv-line);
  background: rgba(255,254,253,.95);
  backdrop-filter: blur(12px);
}

/* Student evidence uses readable narrative blocks instead of database-shaped rows. */
.teacher-view .profile-panel { padding: 26px; }
.teacher-view .profile-facts { gap: 0; border-top: 1px solid var(--tv-line); }
.teacher-view .profile-fact {
  grid-template-columns: 112px minmax(0, 1fr);
  gap: 18px;
  padding: 18px 0;
  border: 0;
  border-bottom: 1px solid var(--tv-line);
  border-radius: 0;
  background: transparent;
}
.teacher-view .profile-fact:last-child { border-bottom: 0; }
.teacher-view .profile-fact-label { color: var(--tv-muted); font-size: 12.5px; font-weight: 700; }
.teacher-view .profile-fact b { color: var(--tv-ink); font-size: 14.5px; line-height: 1.65; }
.teacher-view .profile-tags em { border-color: var(--tv-line); background: #f8fafc; color: var(--tv-ink-2); }
.teacher-view .resource-usage-row,
.teacher-view .path-compact-row { padding-block: 14px; border-bottom-color: var(--tv-line); }

/* Resources, studio, agents and intervention pages share the editorial workspace rhythm. */
.teacher-view .studio-workspace { gap: 24px; }
.teacher-view .studio-editor,
.teacher-view .studio-preview { min-height: 560px; }
.teacher-view .studio-agent-strip { padding: 10px 0; border-block: 1px solid var(--tv-line); }
.teacher-view .agent-grid { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
.teacher-view .agent-card {
  min-height: 240px;
  padding: 24px;
  border-color: var(--tv-line);
  border-radius: 10px;
  background: #fff;
  box-shadow: var(--tv-elev-1);
}
.teacher-view .agent-card:hover { transform: none; border-color: var(--tv-line-2); box-shadow: var(--tv-elev-2); }
.teacher-view .agent-avatar-shell { width: 54px; height: 54px; }
.teacher-view .quick-intervention-card { border-left: 3px solid var(--tv-brand); }
.teacher-view .intervention-card { border-left: 0; }

@media (max-width: 1280px) {
  .teacher-view { width: min(100% - 40px, 1400px); }
  .teacher-view .workbench-grid { grid-template-columns: minmax(0, 1fr); }
  .teacher-view .copilot-panel { position: static; }
  .teacher-view .knowledge-workspace { grid-template-columns: minmax(0, 1fr); }
  .teacher-view .knowledge-inspector { border-top: 1px solid var(--tv-line); border-left: 0; }
}

@media (max-width: 900px) {
  .teacher-view { width: calc(100% - 28px); padding-top: 14px; }
  .teacher-view .workbench-main .action-row,
  .teacher-view .workbench-main .analytics-row { grid-template-columns: 1fr; }
  .teacher-view .knowledge-focus-list { grid-template-columns: 1fr 1fr; }
  .teacher-view .knowledge-focus-list li:nth-child(odd) { border-left: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .teacher-view *, .teacher-view *::before, .teacher-view *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}

/* ============================================================
 * Stitch structure pass · visible command-centre hierarchy
 * ============================================================ */
.teacher-view .teacher-command-context {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 10px;
  border-block: 1px solid var(--tv-line);
}

.teacher-view .teacher-command-context > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  padding: 15px 20px 16px;
  border-left: 1px solid var(--tv-line);
}

.teacher-view .teacher-command-context > span:first-child { border-left: 0; padding-left: 0; }
.teacher-view .teacher-command-context small {
  color: var(--tv-muted);
  font-size: 11.5px;
  font-weight: 600;
}
.teacher-view .teacher-command-context b {
  overflow: hidden;
  color: var(--tv-ink);
  font-size: 13.5px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.teacher-view .insight-surface {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 292px;
  gap: 32px;
  align-items: stretch;
  padding: 30px 32px;
  border: 0;
  border-radius: 12px;
  background: #17202a;
  box-shadow: 0 8px 8px rgba(23, 32, 42, .08);
}

.teacher-view .insight-chip { color: #91b4ff; }
.teacher-view .insight-title,
.teacher-view .insight-title b { color: #fff; }
.teacher-view .insight-meta { color: #aeb9c6; }
.teacher-view .insight-dot { color: #718095; }
.teacher-view .insight-surface .btn-outlined {
  border-color: #48576a;
  color: #e9eef5;
}
.teacher-view .insight-surface .btn-outlined:hover {
  border-color: #8294aa;
  background: #243140;
  color: #fff;
}
.teacher-view .insight-surface .btn-filled {
  background: #e95514;
  color: #fff;
}

.teacher-view .insight-decision-rail {
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  padding-left: 28px;
  border-left: 1px solid #3b4859;
}
.teacher-view .insight-decision-rail > span {
  color: #91b4ff;
  font-size: 11.5px;
  font-weight: 700;
}
.teacher-view .insight-decision-rail > b {
  margin-top: 9px;
  color: #fff;
  font-size: 20px;
  line-height: 1.45;
  text-wrap: balance;
}
.teacher-view .insight-decision-rail dl {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 22px 0 0;
}
.teacher-view .insight-decision-rail dl div { min-width: 0; }
.teacher-view .insight-decision-rail dt {
  color: #92a0b1;
  font-size: 10.5px;
  line-height: 1.4;
}
.teacher-view .insight-decision-rail dd {
  margin: 5px 0 0;
  color: #fff;
  font-size: 14px;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}

/* Tables and management toolbars read as one professional workspace. */
.teacher-view.teacher-section-resources .toolbar,
.teacher-view.teacher-section-agents .toolbar,
.teacher-view.teacher-section-interventions .toolbar {
  padding: 12px;
  border-color: var(--tv-line);
  border-radius: 10px;
  background: var(--tv-panel);
}
.teacher-view .data-table-wrap {
  overflow: hidden;
  border: 1px solid var(--tv-line);
  border-radius: 10px;
  background: var(--tv-panel);
}
.teacher-view .data-table thead { background: #fff4ed; }
.teacher-view .data-table th {
  height: 48px;
  color: #526174;
  font-size: 12px;
  font-weight: 750;
}
.teacher-view .data-table td { height: 58px; border-bottom-color: var(--tv-line); }
.teacher-view .data-table tbody tr,
.teacher-view .data-table tbody td {
  transition: background-color 180ms ease-out, color 180ms ease-out;
}
.teacher-view .data-table tbody tr:hover td { background: #fff8f3; }
.teacher-view .data-table tbody tr:hover .title-cell b { color: var(--tv-brand-ink); }

.teacher-view .card {
  transition:
    transform 190ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 180ms ease-out,
    box-shadow 190ms ease-out;
}
.teacher-view .card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(126, 75, 47, .07);
}
.teacher-view .kpi-card b { transition: color 180ms ease-out, transform 190ms cubic-bezier(0.16, 1, 0.3, 1); }
.teacher-view .kpi-card:hover b { color: var(--tv-brand-ink); transform: translateY(-1px); }
.teacher-view .knowledge-focus-list button {
  transition: background-color 180ms ease-out, transform 190ms cubic-bezier(0.16, 1, 0.3, 1);
}
.teacher-view .knowledge-focus-list button:hover {
  background: #fff8f3;
  transform: translateY(-1px);
}

/* Agent cards become role dossiers instead of empty generic tiles. */
.teacher-view.teacher-section-agents .agent-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  border: 1px solid var(--tv-line);
  border-radius: 12px;
  background: var(--tv-line);
}
.teacher-view.teacher-section-agents .agent-card {
  min-height: 252px;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}
.teacher-view.teacher-section-agents .agent-card:hover {
  border: 0;
  background: #fff8f3;
  box-shadow: none;
}
.teacher-view .agent-avatar-shell,
.teacher-view .agent-identity b {
  transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1), color 180ms ease-out;
}
.teacher-view.teacher-section-agents .agent-card:hover .agent-avatar-shell { transform: scale(1.06); }
.teacher-view.teacher-section-agents .agent-card:hover .agent-identity b { color: var(--tv-brand-ink); }

/* Strong, state-driven interaction pass. */
.teacher-view .appbar-action,
.teacher-view .ghost-btn,
.teacher-view .primary-btn,
.teacher-view .btn-outlined,
.teacher-view .btn-filled,
.teacher-view .btn-tonal,
.teacher-view .btn-tonal-sm,
.teacher-view .btn-filled-sm,
.teacher-view .action-cta,
.teacher-view .ops-cell button {
  transform-origin: center;
  transition:
    transform 190ms cubic-bezier(0.16, 1, 0.3, 1),
    background-color 170ms ease-out,
    border-color 170ms ease-out,
    color 170ms ease-out,
    box-shadow 190ms ease-out;
}
.teacher-view .appbar-action:hover,
.teacher-view .ghost-btn:hover:not(:disabled),
.teacher-view .primary-btn:hover:not(:disabled),
.teacher-view .btn-outlined:hover:not(:disabled),
.teacher-view .btn-filled:hover:not(:disabled),
.teacher-view .btn-tonal:hover:not(:disabled),
.teacher-view .btn-tonal-sm:hover:not(:disabled),
.teacher-view .btn-filled-sm:hover:not(:disabled),
.teacher-view .action-cta:hover:not(:disabled),
.teacher-view .ops-cell button:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.015);
  box-shadow: 0 4px 8px rgba(126, 52, 17, .13);
}
.teacher-view .appbar-action:active,
.teacher-view .ghost-btn:active:not(:disabled),
.teacher-view .primary-btn:active:not(:disabled),
.teacher-view .btn-outlined:active:not(:disabled),
.teacher-view .btn-filled:active:not(:disabled),
.teacher-view .btn-tonal:active:not(:disabled),
.teacher-view .btn-tonal-sm:active:not(:disabled),
.teacher-view .btn-filled-sm:active:not(:disabled),
.teacher-view .action-cta:active:not(:disabled),
.teacher-view .ops-cell button:active:not(:disabled) {
  transform: translateY(0) scale(.955);
  box-shadow: none;
  transition-duration: 80ms;
}

.teacher-view .tab-inner,
.teacher-view .tab-btn svg {
  transition:
    transform 200ms cubic-bezier(0.16, 1, 0.3, 1),
    background-color 180ms ease-out,
    color 180ms ease-out;
}
.teacher-view .tab-btn:hover .tab-inner { transform: translateY(-1px); }
.teacher-view .tab-btn:hover svg { transform: scale(1.08); }
.teacher-view .tab-btn:active .tab-inner { transform: translateY(0) scale(.96); }

.teacher-view .card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(126, 75, 47, .08);
}
.teacher-view .kpi-card:hover b { transform: translateY(-1px) scale(1.025); }
.teacher-view .knowledge-focus-list button:hover { transform: translateY(-2px); }
.teacher-view.teacher-section-agents .agent-card:hover .agent-avatar-shell { transform: translateY(-2px) scale(1.08); }

@media (max-width: 1050px) {
  .teacher-view .teacher-command-context { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .teacher-view .teacher-command-context > span:nth-child(3) { border-left: 0; }
  .teacher-view .insight-surface { grid-template-columns: 1fr; }
  .teacher-view .insight-decision-rail { padding: 22px 0 0; border-top: 1px solid #3b4859; border-left: 0; }
  .teacher-view.teacher-section-agents .agent-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
  .teacher-view .teacher-command-context { grid-template-columns: 1fr; }
  .teacher-view .teacher-command-context > span { padding-inline: 0; border-top: 1px solid var(--tv-line); border-left: 0; }
  .teacher-view .teacher-command-context > span:first-child { border-top: 0; }
  .teacher-view .insight-surface { padding: 24px 20px; }
  .teacher-view .insight-decision-rail dl { grid-template-columns: 1fr; }
  .teacher-view.teacher-section-agents .agent-grid { grid-template-columns: 1fr; }
}

/* ============================================================
 * v4 全站视觉收敛（2026-07-12）· Design Source of Truth = 教学概览
 * 只覆盖视觉 tokens 与表现层，业务模板与图谱引擎零改动。
 * 基准规则：浅暖白 #FBFAF7 / 衬线页标题 / 细边框无阴影卡片 /
 *          KPI Strip / 浅橙洞察容器 / AI 低饱和紫 / 单一橙色主操作
 * ============================================================ */
.teacher-view {
  --tv-ink: #1f1d1a;
  --tv-ink-2: #393631;
  --tv-muted: #625f58;
  --tv-faint: #89857d;
  --tv-line: #e5e1d9;
  --tv-line-2: #dad6ce;
  --tv-bg: #fbfaf7;
  --tv-panel: #ffffff;
  --tv-panel-2: #f8f7f3;
  --tv-brand: #e85d16;
  --tv-brand-hover: #d75011;
  --tv-brand-ink: #b04510;
  --tv-brand-soft: #fff3ea;
  --tv-brand-line: #f1c9ae;
  --tv-ai: #6557d9;
  --tv-ai-hover: #5647c8;
  --tv-ai-ink: #5647c8;
  --tv-ai-soft: #faf9ff;
  --tv-ai-line: #e5e1f4;
  --tv-ok: #247553;
  --tv-ok-soft: #eef8f2;
  --tv-warn: #a46916;
  --tv-warn-soft: #fff6e4;
  --tv-err: #b5423a;
  --tv-err-soft: #fff1ee;
  --tv-info: #3e6d9c;
  --tv-info-soft: #eef4fa;
  --tv-elev-1: none;
  --tv-elev-2: 0 8px 24px rgba(35, 31, 25, 0.05);
  --tv-r-lg: 12px;
  --tv-r-md: 10px;
  --tv-r-sm: 8px;
  /* 宽度交给壳层 1540 网格；Section 节奏按规范收紧 */
  width: 100%;
  max-width: none;
  gap: 28px;
  padding: 0 0 48px;
  color: var(--tv-ink);
}

/* AI 工作台局部紫 tokens 同步到基准低饱和紫 */
.teacher-view .workbench-v3 {
  --wb-ai: #6557d9;
  --wb-ai-ink: #5647c8;
  --wb-ai-soft: #faf9ff;
  --wb-ai-line: #e5e1f4;
}

/* 页头：衬线编辑式标题（无 Eyebrow），与教学概览同构 */
.teacher-view .teacher-appbar { padding: 0; }
.teacher-view .teacher-appbar-title h1 {
  color: #171512;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: clamp(30px, 2.5vw, 38px);
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.teacher-view .teacher-appbar-title p {
  color: var(--tv-muted);
  font-size: 15px;
  line-height: 1.6;
}
.teacher-view .appbar-action {
  min-height: 42px;
  border: 1px solid var(--tv-line-2);
  border-radius: 9px;
  background: #fff;
  color: #393631;
  font-size: 13.5px;
  font-weight: 600;
}

/* Metadata Bar：与教学概览一致（50px · 13/13.5px） */
.teacher-view .teacher-command-context { margin-top: 24px; }
.teacher-view .teacher-command-context > span { padding: 14px 20px; }
.teacher-view .teacher-command-context small {
  color: var(--tv-muted);
  font-size: 13px;
  font-weight: 500;
}
.teacher-view .teacher-command-context b {
  color: var(--tv-ink);
  font-size: 13.5px;
  font-weight: 600;
}
.teacher-view .context-course-select {
  width: fit-content;
  padding: 2px 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--tv-ink);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: color 160ms ease-out;
}
.teacher-view .context-course-select:hover { color: var(--tv-brand); }
.teacher-view .context-course-select:focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
  outline-offset: 1px;
}

/* Tabs：去玻璃卡片，浅底线 + 橙色 2px Indicator；随内容滚动（不吸顶） */
.teacher-view .teacher-tabs {
  position: static;
  min-height: 48px;
  padding: 0;
  border: 0;
  border-bottom: 1px solid var(--tv-line);
  border-radius: 0;
  background: var(--tv-bg);
  box-shadow: none;
  backdrop-filter: none;
}
.teacher-view .tab-btn { min-height: 44px; }
.teacher-view .tab-btn.active .tab-inner { background: var(--tv-brand-soft); border-radius: 8px; }

/* 学生选择条：白色 Toolbar，无玻璃效果，随内容滚动（不吸顶） */
.teacher-view .student-bar {
  position: static;
  border: 1px solid var(--tv-line);
  border-radius: 10px;
  background: #fff;
  box-shadow: none;
  backdrop-filter: none;
}

/* KPI：卡片拼图 → 无背景 Strip（上下分割线） */
.teacher-view .kpi-grid {
  border: 0;
  border-block: 1px solid var(--tv-line);
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.teacher-view .kpi-card { min-height: 0; padding: 20px 26px; }
.teacher-view .kpi-card:hover { background: var(--tv-panel-2); }
.teacher-view .kpi-card small { color: var(--tv-faint); font-size: 12.5px; font-weight: 500; }
.teacher-view .kpi-card b { font-size: 32px; font-weight: 600; }

/* AI 今日洞察：深色 Hero → 教学概览同款浅橙洞察容器 */
.teacher-view .insight-surface {
  border: 1px solid var(--tv-brand-line);
  border-radius: 14px;
  background: var(--tv-brand-soft);
  box-shadow: none;
}
.teacher-view .insight-chip { color: var(--tv-brand-hover); font-size: 13px; }
.teacher-view .insight-title {
  color: #171512;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: clamp(21px, 1.8vw, 25px);
  font-weight: 600;
  line-height: 1.45;
}
.teacher-view .insight-title b { color: var(--tv-brand); font-weight: 650; }
.teacher-view .insight-meta { color: var(--tv-muted); font-size: 13px; }
.teacher-view .insight-dot { color: var(--tv-faint); }
.teacher-view .insight-surface .btn-outlined {
  border-color: #e7c9ad;
  background: rgba(255, 255, 255, 0.85);
  color: #393631;
}
.teacher-view .insight-surface .btn-outlined:hover {
  border-color: #d9b48f;
  background: #fff;
  color: #1f1d1a;
}
.teacher-view .insight-surface .btn-filled { background: var(--tv-brand); }
.teacher-view .insight-decision-rail { border-left: 1px solid #eed7c4; }
.teacher-view .insight-decision-rail > span { color: var(--tv-brand-hover); font-size: 12.5px; }
.teacher-view .insight-decision-rail > b { color: #171512; }
.teacher-view .insight-decision-rail dt { color: var(--tv-faint); font-size: 12px; }
.teacher-view .insight-decision-rail dd { color: var(--tv-ink); }

/* 按钮体系对齐基准：Outlined 中性、hover 位移 -1px、阴影统一 */
.teacher-view .btn-outlined,
.teacher-view .btn-filled,
.teacher-view .btn-tonal {
  min-height: 42px;
  border-radius: 9px;
  font-size: 13.5px;
  font-weight: 600;
}
.teacher-view .btn-outlined {
  border: 1px solid var(--tv-line-2);
  background: #fff;
  color: #393631;
}
.teacher-view .btn-outlined:hover {
  border-color: #c6c1b7;
  background: #fff;
  color: #1f1d1a;
}
.teacher-view .btn-outlined:focus-visible { box-shadow: 0 0 0 3px rgba(232, 93, 22, 0.24); }
.teacher-view .btn-filled:hover:not(:disabled) { box-shadow: 0 8px 24px rgba(35, 31, 25, 0.09); }
.teacher-view .btn-tonal:hover { background: #ffe9d8; }
.teacher-view .appbar-action:hover,
.teacher-view .ghost-btn:hover:not(:disabled),
.teacher-view .primary-btn:hover:not(:disabled),
.teacher-view .btn-outlined:hover:not(:disabled),
.teacher-view .btn-filled:hover:not(:disabled),
.teacher-view .btn-tonal:hover:not(:disabled),
.teacher-view .btn-tonal-sm:hover:not(:disabled),
.teacher-view .btn-filled-sm:hover:not(:disabled),
.teacher-view .action-cta:hover:not(:disabled),
.teacher-view .ops-cell button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.07);
}

/* 卡片：白底细边框 12px，默认无阴影，hover -1px + 轻阴影 */
.teacher-view .card {
  border-color: var(--tv-line);
  border-radius: 12px;
  background: #fff;
  box-shadow: none;
}
.teacher-view .card:hover {
  transform: translateY(-1px);
  border-color: #d7d1c7;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.teacher-view .kpi-card:hover b { color: var(--tv-brand-ink); }

/* 表格：中性表头 + 基准 hover 底色 */
.teacher-view .data-table thead { background: #f5f3ee; }
.teacher-view .data-table th { color: var(--tv-muted); }
.teacher-view .data-table tbody tr:hover td { background: #f8f6f2; }

/* 知识图谱画布：浅暖白点阵、中性连线（引擎不动，仅换肤） */
.teacher-view .knowledge-svg-scroll {
  background-color: #fcfbf8;
  background-image: radial-gradient(rgba(80, 75, 68, 0.08) 1px, transparent 1px);
}
.teacher-view .knowledge-edge { stroke: #d9d4cc; }
.teacher-view .knowledge-edge:not(.relation-prerequisite) { stroke: #c8c2b8; }
.teacher-view .knowledge-toolrail { background: rgba(251, 250, 247, 0.94); }
.teacher-view .knowledge-view-switch button.active {
  background: var(--tv-brand-soft);
  color: var(--tv-brand-ink);
}
.teacher-view .knowledge-focus-list button:hover { background: #f8f6f2; }

/* 资源/干预/Agent 工具条与列表 hover 统一 */
.teacher-view.teacher-section-agents .agent-card:hover { background: #f8f6f2; }
.teacher-view .data-table tbody tr:hover .title-cell b { color: var(--tv-brand-hover); }

@media (max-width: 1280px) {
  .teacher-view { width: 100%; }
}
@media (max-width: 1050px) {
  .teacher-view .insight-decision-rail { border-top: 1px solid #eed7c4; border-left: 0; }
}
@media (max-width: 900px) {
  .teacher-view { width: 100%; padding-top: 0; }
}
</style>
