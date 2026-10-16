<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  BrainCircuit,
  ChevronRight,
  Database,
  MessageSquare,
  Network,
  RefreshCcw,
  Send,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-vue-next";

import OnboardingTour, { type TourStep } from "@/components/shared/OnboardingTour.vue";
import { TEACHER_VALUE_PROPS } from "@/constants/platformGuide";
import { getAuthSession } from "@/utils/auth";

// 引导去重 key 按账号隔离（2026-07-17 修复）：注册的新账号必须能看到引导
const teacherAccount = getAuthSession()?.account || "guest";

import {
  consultTeachingCopilot,
  getClassAnalytics,
  type ClassAnalytics,
} from "@/api/teacher";
import MarkdownBlock from "@/components/shared/MarkdownBlock.vue";
import { AGENT_AVATARS } from "@/constants/agentAvatars";
import { useTeacherCourse } from "@/composables/useTeacherCourse";

const router = useRouter();
const { course, courseOptions, loadCourseOptions, setCourse, courseLabelOf } = useTeacherCourse();
const data = ref<ClassAnalytics | null>(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref("");
const copilotInput = ref("");
const copilotLoading = ref(false);
const copilotResult = ref("");
const assistantEl = ref<HTMLElement | null>(null);
const chartDays = ref(30);
const hoverIdx = ref<number | null>(null);

const reduceMotion =
  typeof window !== "undefined" &&
  !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

const agents = [
  AGENT_AVATARS.planner,
  AGENT_AVATARS.tutor,
  AGENT_AVATARS.content,
  AGENT_AVATARS.quiz,
  AGENT_AVATARS.evaluation,
  AGENT_AVATARS.safety,
];

// ============================================================
// 首页叙事优化 v2（2026-07-17）：教学工作流大卡片（备课 → 观察 → 干预 → 协作）
// 每张卡 = 场景叙事 + 实时班级数据 + 该场景全部入口 + 主 CTA，
// 突出「课程知识库」自助建课能力（0716 平台化改造）
// ============================================================
const workflowCards = computed(() => [
  {
    key: "prepare",
    step: "01",
    icon: Database,
    stage: "备课",
    title: "课程知识库",
    promo: "自助新建课程、上传讲义资料，刺猬守护审核入库后学生端即刻可学——换一门课零代码。",
    stat: { value: `${courseOptions.value.length} 门`, label: "课程在库" },
    links: [
      { label: "课程知识库", hint: "建课 / 上传 / 命中测试", to: "/teacher/kb" },
      { label: "教学资源", hint: "指派讲义与课件", to: "/teacher/resources" },
      { label: "知识图谱", hint: "课程知识结构", to: "/teacher/knowledge" },
    ],
    cta: "维护知识库",
    to: "/teacher/kb",
  },
  {
    key: "observe",
    step: "02",
    icon: Users,
    stage: "观察",
    title: "学情诊断",
    promo: "掌握度、活跃度与风险名单全部来自真实学习数据，用证据定位该教什么、先帮谁。",
    stat: { value: `${data.value?.student_count ?? 0} 人`, label: `班级学生 · ${counters.risk} 人需关注` },
    links: [
      { label: "学生分析", hint: "个体诊断与对比", to: "/teacher/students" },
      { label: "知识薄弱点", hint: "班级掌握度地图", to: "/teacher/knowledge" },
    ],
    cta: "查看学情",
    to: "/teacher/students",
  },
  {
    key: "act",
    step: "03",
    icon: MessageSquare,
    stage: "干预",
    title: "精准干预",
    promo: "指派资源、推荐学习路径、发送消息，全部直达学生课程群聊，学生刷新即见。",
    stat: { value: `${counters.mistakes} 道`, label: "待处理错题" },
    links: [
      { label: "教学干预", hint: "干预记录与执行", to: "/teacher/interventions" },
      { label: "教学提示与视频", hint: "讲评素材制作", to: "/teacher/studio" },
    ],
    cta: "执行干预",
    to: "/teacher/interventions",
  },
  {
    key: "collab",
    step: "04",
    icon: Sparkles,
    stage: "协作",
    title: "Agent 协作组",
    promo: "6 个 Agent 分工协作，可配置提示词与能力；刺猬守护把关内容安全与防幻觉。",
    stat: { value: "6 个", label: "Agent 在线" },
    links: [
      { label: "Agent 协作", hint: "配置与启停", to: "/teacher/agents" },
      { label: "安全中心", hint: "内容安全与审计", to: "/safety" },
    ],
    cta: "管理 Agent",
    to: "/teacher/agents",
  },
]);

// 首访新手引导（教师端，v2：每步带功能清单）
const teacherTourSteps: TourStep[] = [
  {
    badge: "👋",
    nav: "认识管理台",
    image: AGENT_AVATARS.planner.png || "",
    title: "欢迎使用教师管理台",
    desc: "管理台遵循「备课 → 观察 → 干预 → 协作」的教学工作流：每次进来先看本周核心教学洞察，系统已用真实学习数据替你完成了归因，你只需要决策和执行。",
    points: [
      { label: "本周核心洞察", text: "首页顶部 · 一句话告诉你先补什么" },
      { label: "班级关键指标", text: "掌握度 / 活跃 / 风险 / 错题实时更新" },
      { label: "今日三件事", text: "按风险和教学收益排好的待办" },
      { label: "教师 = 管理员", text: "两种身份已合并，一个入口全部搞定" },
    ],
  },
  {
    badge: "①",
    nav: "备课：知识库",
    image: AGENT_AVATARS.safety.png || "",
    title: "备课：课程知识库自助建课",
    desc: "在「课程知识库」里新建课程、拖拽上传讲义（支持 Markdown/PDF/Word），刺猬守护自动审核入库，学生端即刻可学——换一门课不需要找开发改代码。",
    points: [
      { label: "新建课程", text: "课程知识库页 · 右上角橙色按钮" },
      { label: "上传文档", text: "拖拽即传 · 自动安全审核 + 索引" },
      { label: "命中测试", text: "右侧面板 · 模拟学生提问验证召回" },
      { label: "生成知识图谱", text: "一键从文档标题生成课程图谱" },
    ],
  },
  {
    badge: "②",
    nav: "观察与干预",
    image: AGENT_AVATARS.evaluation.png || "",
    title: "观察 → 干预，一条动线",
    desc: "从学情分析定位薄弱学生和知识点，再用指派资源、推荐路径或群聊消息完成干预——所有动作直达学生的课程群聊，学生刷新即见。随时点顶栏「?」可重看本引导。",
    points: [
      { label: "学生分析", text: "左侧导航 · 个体诊断 + 学生对比" },
      { label: "指派资源", text: "学生详情页 · 一键推送到群聊" },
      { label: "教学干预", text: "左侧导航 · 干预记录与执行追踪" },
      { label: "Agent 协作", text: "左侧导航 · 配置 6 个 Agent 的分工" },
    ],
    cta: "开始使用管理台",
  },
];

/** 随时重看新手引导（与顶栏「?」按钮同一机制） */
function reopenTour() {
  window.dispatchEvent(new CustomEvent("tripleu:open-tour"));
}

const mastery = computed(() => Math.round((data.value?.mastery.overall_avg || 0) * 100));
const focusKp = computed(() => data.value?.weak_kps[0]);
const activeRate = computed(() => {
  const total = data.value?.student_count || 0;
  return total ? Math.round(((data.value?.active_7d || 0) / total) * 100) : 0;
});

// KPI 数字 Count Up（真实数据加载后触发，400ms）
const counters = reactive({ mastery: 0, active: 0, risk: 0, mistakes: 0 });
function countTo(key: keyof typeof counters, to: number) {
  if (reduceMotion) {
    counters[key] = to;
    return;
  }
  const from = counters[key];
  const start = performance.now();
  const duration = 400;
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    counters[key] = Math.round(from + (to - from) * eased);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function startCounters() {
  countTo("mastery", mastery.value);
  countTo("active", data.value?.active_7d || 0);
  countTo("risk", data.value?.risk_students.length || 0);
  countTo("mistakes", data.value?.mistakes_open_total || 0);
}

/* ---------- KPI：数字 + 由真实数据推导的结论 ---------- */
const weakLayerCount = computed(() => {
  const dist = data.value?.mastery.distribution || [];
  return dist.slice(0, 2).reduce((sum, item) => sum + item.count, 0);
});
const masteryKpi = computed(() => {
  const m = mastery.value;
  if (m >= 70) return { cls: "good", text: `健康水平 · ${weakLayerCount.value} 人待提升` };
  if (m >= 50) return { cls: "warn", text: `中等水平 · ${weakLayerCount.value} 人处于待提升及以下` };
  return { cls: "bad", text: `低于达标线 · ${weakLayerCount.value} 人待提升` };
});
const activeKpi = computed(() => {
  const total = data.value?.student_count || 0;
  const active = data.value?.active_7d || 0;
  if (total && active >= total) return { cls: "good", text: "全员保持学习" };
  const idle = total - active;
  return {
    cls: total && active / total >= 0.6 ? "good" : "warn",
    text: `${idle} 人超过 7 天未学习`,
  };
});
const riskKpi = computed(() => {
  const list = data.value?.risk_students || [];
  if (!list.length) return { cls: "good", text: "暂无高风险学生" };
  const high = list.filter((s) => s.level === "high").length;
  return high
    ? { cls: "bad", text: `其中 ${high} 人为高风险` }
    : { cls: "warn", text: "以中低风险为主" };
});
const mistakesKpi = computed(() => {
  const top = data.value?.error_distribution?.[0];
  const label = top?.label || top?.code;
  return {
    cls: "plain",
    text: top && label ? `最多来自「${label}」` : "可形成课堂讲评素材",
  };
});

function humanStudentName(value: string) {
  const match = String(value || "").match(/^demo-student-(\d+)$/i);
  return match ? `学生 ${match[1]}` : value;
}

const distribution = computed(() => {
  const labels: Record<string, string> = {
    "0-20%": "薄弱",
    "20-40%": "待提升",
    "40-60%": "发展中",
    "60-80%": "良好",
    "80-100%": "优秀",
  };
  // 低饱和状态色：风险 → 健康
  const colors = ["#be5a50", "#d88c45", "#d0a84a", "#6e9565", "#327a55"];
  const total = Math.max(1, data.value?.student_count || 0);
  return (data.value?.mastery.distribution || []).map((item, index) => ({
    ...item,
    label: labels[item.bucket] || item.bucket,
    percent: Math.round((item.count / total) * 100),
    color: colors[index] || "#89857d",
  }));
});

/* ---------- 近 N 天趋势：双折线 + 数据点 + Tooltip（全部真实数据） ---------- */
const CHART_W = 720;
const CHART_H = 240;
const CHART_TOP = 16;
const CHART_BOTTOM = 30;

const trendChart = computed(() => {
  const rows = data.value?.mastery.trend || [];
  if (!rows.length) return null;
  const usable = CHART_H - CHART_TOP - CHART_BOTTOM;
  const xs = rows.map((_, i) =>
    rows.length === 1 ? CHART_W / 2 : (i / (rows.length - 1)) * CHART_W,
  );
  const actMax = Math.max(1, ...rows.map((row) => row.activity_count || 0));
  const scoreY: Array<number | null> = rows.map((row) =>
    row.avg_score == null ? null : CHART_TOP + (1 - Math.min(100, row.avg_score) / 100) * usable,
  );
  const actY = rows.map(
    (row) => CHART_TOP + (1 - (row.activity_count || 0) / actMax) * usable,
  );
  const scoreLine = rows
    .map((_, i) => (scoreY[i] == null ? "" : `${xs[i].toFixed(1)},${scoreY[i]!.toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  const actLine = rows.map((_, i) => `${xs[i].toFixed(1)},${actY[i].toFixed(1)}`).join(" ");
  let lastScoreIdx = -1;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (scoreY[i] != null) {
      lastScoreIdx = i;
      break;
    }
  }
  const gridYs = [0, 0.5, 1].map((f) => CHART_TOP + f * usable);
  return {
    rows,
    xs,
    scoreY,
    actY,
    scoreLine,
    actLine,
    lastScoreIdx,
    actMax,
    gridYs,
    firstDate: rows[0].date,
    lastDate: rows[rows.length - 1].date,
  };
});

const hoverPoint = computed(() => {
  const chart = trendChart.value;
  if (!chart || hoverIdx.value == null || !chart.rows[hoverIdx.value]) return null;
  const i = hoverIdx.value;
  return {
    row: chart.rows[i],
    x: chart.xs[i],
    leftPct: Math.min(90, Math.max(10, (chart.xs[i] / CHART_W) * 100)),
    scoreY: chart.scoreY[i],
    actY: chart.actY[i],
  };
});

function onChartMove(event: MouseEvent) {
  const chart = trendChart.value;
  if (!chart) return;
  const rect = (event.currentTarget as SVGSVGElement).getBoundingClientRect();
  const ratio = (event.clientX - rect.left) / Math.max(1, rect.width);
  hoverIdx.value = Math.min(
    chart.rows.length - 1,
    Math.max(0, Math.round(ratio * (chart.rows.length - 1))),
  );
}
function onChartLeave() {
  hoverIdx.value = null;
}

/* 教师观察：由真实趋势数据计算近 7 天 vs 前 7 天的变化 */
const trendInsight = computed(() => {
  const rows = data.value?.mastery.trend || [];
  if (rows.length < 14) {
    return {
      title: "持续观察",
      lead: "趋势数据积累中，完成更多课堂练习后将给出对比结论。",
      detail: "建议优先围绕薄弱知识点组织短时练习，为趋势对比建立基线。",
    };
  }
  const last7 = rows.slice(-7);
  const prev7 = rows.slice(-14, -7);
  const sumAct = (list: typeof rows) => list.reduce((s, r) => s + (r.activity_count || 0), 0);
  const avgScore = (list: typeof rows) => {
    const valid = list.filter((r) => r.avg_score != null);
    if (!valid.length) return null;
    return valid.reduce((s, r) => s + (r.avg_score || 0), 0) / valid.length;
  };
  const actNow = sumAct(last7);
  const actPrev = sumAct(prev7);
  const actDelta = actPrev ? Math.round(((actNow - actPrev) / actPrev) * 100) : null;
  const scoreNow = avgScore(last7);
  const scorePrev = avgScore(prev7);
  const scoreDelta =
    scoreNow != null && scorePrev != null ? Math.round(scoreNow - scorePrev) : null;

  const parts: string[] = [];
  if (actDelta != null) {
    parts.push(`近 7 天学习活跃度${actDelta >= 0 ? "上升" : "下降"} ${Math.abs(actDelta)}%`);
  }
  if (scoreDelta != null) {
    parts.push(`日均得分${scoreDelta >= 0 ? "提升" : "下降"} ${Math.abs(scoreDelta)} 分`);
  }
  const lead = parts.length ? `${parts.join("，")}。` : "近两周数据不足以形成对比。";

  let detail = "建议持续追踪活跃与得分变化，及时安排课堂干预。";
  if (actDelta != null && scoreDelta != null) {
    if (actDelta < 0 && scoreDelta >= 0)
      detail = "参与人数减少，但当前活跃学生的学习质量有所提高，优先召回沉默学生。";
    else if (actDelta >= 0 && scoreDelta >= 0)
      detail = "参与与质量同步向好，可趁势推进分层练习任务。";
    else if (actDelta < 0 && scoreDelta < 0)
      detail = "参与与质量同步回落，建议尽快安排课堂干预并召回学生。";
    else detail = "活跃提升但得分下降，注意练习难度与讲解节奏的匹配。";
  }
  const needAttention = (actDelta ?? 0) < 0 || (scoreDelta ?? 0) < 0;
  return { title: needAttention ? "需要关注" : "趋势稳定", lead, detail };
});

function setChartDays(days: number) {
  if (chartDays.value === days || loading.value || refreshing.value) return;
  chartDays.value = days;
  load();
}

/* ---------- 今日行动：优先级 / 耗时 / 操作，全部来自真实数据 ---------- */
const actions = computed(() => {
  if (!data.value) return [];
  const risk = data.value.risk_students[0];
  const weak = data.value.weak_kps[0];
  return [
    {
      kind: "risk",
      tag: "高优先级",
      title: risk
        ? `跟进${humanStudentName(risk.display_name || risk.user_id)}`
        : "班级风险处于可控范围",
      detail: risk
        ? `掌握度 ${Math.round((risk.mastery_avg || 0) * 100)}%，${risk.mistakes_open} 道错题尚未解决`
        : "继续观察本周活跃度与知识掌握变化",
      minutes: 8,
      action: "查看学生",
      run: () => router.push({ path: "/teacher/students", query: { student: risk?.user_id || "" } }),
    },
    {
      kind: "focus",
      tag: "知识补强",
      title: weak ? `围绕「${weak.kp_name}」准备补强` : "等待更多知识点证据",
      detail: weak
        ? `${weak.students_below_60} 人未达标，${weak.mistake_count} 道题重复出错`
        : "完成课堂练习后将生成教学重点",
      minutes: 18,
      action: "查看图谱",
      run: () => router.push("/teacher/knowledge"),
    },
    {
      kind: "plan",
      tag: "待确认",
      title: "审核本周分层教学任务",
      detail: "由多个 Agent 协同生成，等待教师确认",
      minutes: 5,
      action: "进入计划",
      run: () => router.push({ path: "/teacher/interventions", query: { tab: "copilot" } }),
    },
  ];
});

function masteryTone(percent: number) {
  if (percent < 50) return "#be5a50";
  if (percent < 65) return "#d88c45";
  return "#327a55";
}

/* ---------- AI 助理快捷模板（含真实数据） ---------- */
const quickPrompts = computed(() => [
  `为${focusKp.value?.kp_name || "薄弱知识点"}生成 18 分钟分层练习`,
  `为 ${data.value?.risk_students.length || 0} 名重点学生制定干预计划`,
  "生成本周课堂教学方案",
]);

async function load() {
  if (data.value) refreshing.value = true;
  else loading.value = true;
  error.value = "";
  try {
    data.value = await getClassAnalytics({
      course: course.value,
      days: chartDays.value,
      weak_top: 6,
      risk_top: 6,
    });
    startCounters();
  } catch (reason: any) {
    error.value = reason?.detail || reason?.message || "班级数据加载失败";
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
}

async function askCopilot(prompt?: string) {
  const instruction = (prompt || copilotInput.value).trim();
  if (!instruction || copilotLoading.value) return;
  copilotInput.value = instruction;
  copilotLoading.value = true;
  copilotResult.value = "";
  try {
    const result = await consultTeachingCopilot({
      action: "class_diagnosis",
      scope: "class",
      course: course.value,
      instruction,
    });
    copilotResult.value = result.content || result.error || "本次没有生成可审核建议。";
  } catch (reason: any) {
    copilotResult.value = `生成失败：${reason?.detail || reason?.message || reason}`;
  } finally {
    copilotLoading.value = false;
  }
}

function draftFromHero() {
  askCopilot(`围绕${focusKp.value?.kp_name || "本周课程"}制定一份18分钟课堂补强方案`);
  assistantEl.value?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
}

function formatUpdate(value = 0) {
  if (!value) return "刚刚同步";
  return new Date(value * 1000).toLocaleString("zh-CN", { hour12: false });
}

function onCourseChange(event: Event) {
  setCourse((event.target as HTMLSelectElement).value);
}

// 切换课程后按新课程重新拉取真实班级数据
watch(course, () => {
  copilotResult.value = "";
  load();
});

onMounted(() => {
  loadCourseOptions();
  load();
});
</script>

<template>
  <div class="teacher-overview-v6">
    <!-- 页面标题区：不使用卡片，无 Eyebrow -->
    <header class="page-heading">
      <div class="heading-copy">
        <h1>把班级证据，转化为本周教学行动</h1>
        <p class="lede">优先看、再分析、后执行，所有 Agent 建议均基于可核验的学习数据。</p>
      </div>
      <div class="heading-actions">
        <button class="btn-outlined" type="button" @click="router.push('/teacher/knowledge')">
          <Network :size="16" />班级图谱
        </button>
        <button
          class="btn-text"
          type="button"
          :disabled="loading || refreshing"
          @click="load"
        >
          <RefreshCcw :size="15" :class="{ spin: loading || refreshing }" />同步数据
        </button>
        <button
          class="btn-outlined"
          type="button"
          @click="router.push({ path: '/teacher/interventions', query: { tab: 'copilot' } })"
        >
          <Sparkles :size="16" />转化教学计划
        </button>
      </div>
    </header>

    <!-- Metadata Bar：上下 1px 浅分割线 · 含课程切换 -->
    <div v-if="data" class="meta-bar" aria-label="当前课程上下文">
      <div>
        <small>课程</small>
        <select
          class="course-select"
          :value="course"
          aria-label="切换教学课程"
          @change="onCourseChange"
        >
          <option v-for="id in courseOptions" :key="id" :value="id">{{ courseLabelOf(id) }}</option>
        </select>
      </div>
      <div><small>学生范围</small><b>{{ data.student_count }} 人</b></div>
      <div><small>学习证据</small><b>{{ data.student_count - data.mastery.no_data_count }} 人已采集</b></div>
      <div><small>最近同步</small><b>{{ formatUpdate(data.generated_at) }}</b></div>
    </div>

    <div v-if="loading" class="loading-state">
      <span></span>
      <b>正在整理班级教学证据</b>
      <p>同步知识追踪、错题归因与资源行为…</p>
    </div>
    <div v-else-if="error" class="error-state">
      <b>暂时无法读取班级数据</b>
      <p>{{ error }}</p>
      <button class="btn-filled" type="button" @click="load">重新加载</button>
    </div>

    <template v-else-if="data">
      <!-- 本周核心教学洞察：页面唯一的 Filled Primary 所在地 -->
      <section class="insight-hero" aria-label="本周核心教学洞察">
        <div class="hero-copy">
          <span class="hero-label"><BrainCircuit :size="15" />本周核心教学洞察</span>
          <h2>
            班级掌握度 {{ mastery }}%，本周优先补强<em>「{{ focusKp?.kp_name || "基础知识" }}」</em>
          </h2>
          <p>
            {{ focusKp
              ? `${focusKp.students_below_60} 名学生尚未达标，已识别 ${focusKp.mistake_count} 道典型错题。`
              : "当前证据不足，建议先完成一次基础练习。" }}
            建议安排 18 分钟完成概念辨析和分层练习。
          </p>
          <div class="hero-actions">
            <button class="btn-filled" type="button" @click="draftFromHero">
              让 Agent 创建方案<ArrowRight :size="15" />
            </button>
            <button class="btn-text" type="button" @click="router.push('/teacher/knowledge')">查看分析依据</button>
          </div>
        </div>
        <aside class="hero-stats">
          <div><small>未达标</small><b>{{ focusKp?.students_below_60 || 0 }}<i>人</i></b></div>
          <div><small>典型错题</small><b>{{ focusKp?.mistake_count || 0 }}<i>道</i></b></div>
          <div><small>建议投入</small><b>18<i>分钟</i></b></div>
        </aside>
      </section>

      <!-- KPI Strip：数字 + 明确结论 -->
      <section class="kpi-strip" aria-label="班级关键指标">
        <div>
          <small>班级掌握度</small>
          <b>{{ counters.mastery }}<i>%</i></b>
          <span :class="masteryKpi.cls"><TrendingUp :size="13" />{{ masteryKpi.text }}</span>
        </div>
        <div>
          <small>7 日活跃</small>
          <b>{{ counters.active }}<i>/{{ data.student_count }}</i></b>
          <span :class="activeKpi.cls">{{ activeKpi.text }}</span>
        </div>
        <div>
          <small>优先关注</small>
          <b>{{ counters.risk }}<i>人</i></b>
          <span :class="riskKpi.cls">{{ riskKpi.text }}</span>
        </div>
        <div>
          <small>待处理错题</small>
          <b>{{ counters.mistakes }}</b>
          <span :class="mistakesKpi.cls">{{ mistakesKpi.text }}</span>
        </div>
      </section>

      <!-- 教学工作流大卡片（2026-07-17 叙事优化 v2）：备课 → 观察 → 干预 → 协作 -->
      <section class="workflow-strip" aria-label="教学工作流">
        <header class="wf-head">
          <div>
            <span class="wf-eyebrow">平台概览 · 教学工作流</span>
            <h2>备课 → 观察 → 干预 → 协作</h2>
            <p>全部功能按这条动线组织，每张卡片聚合了对应场景的入口，点击直达。</p>
          </div>
          <button type="button" class="wf-replay" @click="reopenTour">重看新手引导</button>
        </header>
        <!-- 平台价值主张：一眼看懂管理台能做什么（宣传 + 解释） -->
        <div class="wf-props" aria-label="管理台核心能力">
          <article v-for="prop in TEACHER_VALUE_PROPS" :key="prop.label">
            <b>{{ prop.label }}</b>
            <span>{{ prop.text }}</span>
          </article>
        </div>
        <div class="wf-cards">
          <article v-for="(card, index) in workflowCards" :key="card.key" :class="{ active: index === 0 }">
            <span class="wf-watermark" aria-hidden="true">{{ card.step }}</span>
            <div class="wf-top">
              <span class="wf-icon"><component :is="card.icon" :size="18" /></span>
              <span class="wf-stage">{{ card.stage }}</span>
            </div>
            <h3>{{ card.title }}</h3>
            <p class="wf-promo">{{ card.promo }}</p>
            <div class="wf-stat"><b>{{ card.stat.value }}</b><small>{{ card.stat.label }}</small></div>
            <div class="wf-links">
              <button v-for="link in card.links" :key="link.to" type="button" @click="router.push(link.to)">
                <span class="wf-link-label">{{ link.label }}</span>
                <span class="wf-link-hint">{{ link.hint }}</span>
                <ChevronRight :size="12" />
              </button>
            </div>
            <button type="button" class="wf-cta" @click="router.push(card.to)">{{ card.cta }}<ArrowRight :size="14" /></button>
          </article>
        </div>
      </section>

      <!-- 今天优先做三件事：任务列表 -->
      <section class="section">
        <header class="section-head">
          <div>
            <h2>今天优先做三件事</h2>
            <p>根据风险、影响范围和教学收益排序。</p>
          </div>
          <button class="btn-text" type="button" @click="router.push('/teacher/interventions')">查看全部</button>
        </header>
        <div class="task-list">
          <div
            v-for="(item, index) in actions"
            :key="item.title"
            :class="['task-item', item.kind]"
            role="button"
            tabindex="0"
            @click="item.run"
            @keydown.enter="item.run"
          >
            <span class="task-no">{{ String(index + 1).padStart(2, "0") }}</span>
            <i :class="['task-tag', item.kind]">{{ item.tag }}</i>
            <div class="task-copy">
              <b>{{ item.title }}</b>
              <small>{{ item.detail }}</small>
            </div>
            <span class="task-eta">预计 {{ item.minutes }} 分钟</span>
            <button class="btn-outlined btn-sm" type="button" @click.stop="item.run">
              {{ item.action }}<ChevronRight :size="14" />
            </button>
          </div>
        </div>
      </section>

      <!-- 班级学习结构：保留大型分析卡片 -->
      <section class="section">
        <header class="section-head">
          <div>
            <h2>班级学习结构</h2>
            <p>BKT 知识追踪的五层掌握分布。</p>
          </div>
          <span class="pill-positive">7 日活跃率 {{ activeRate }}%</span>
        </header>
        <div class="structure-card">
          <div class="structure-summary">
            <b>{{ mastery }}<i>%</i></b>
            <span>班级平均掌握度</span>
            <div class="stacked-bar" role="img" aria-label="班级掌握度五层分布">
              <i
                v-for="seg in distribution"
                :key="seg.bucket"
                :style="{ width: `${Math.max(seg.percent, seg.count ? 2 : 0)}%`, background: seg.color }"
                :title="`${seg.label} ${seg.count} 人`"
              />
            </div>
            <p class="structure-conclusion">
              {{ weakLayerCount }} 名学生处于待提升及薄弱层，是本周补强的重点对象。
            </p>
          </div>
          <ul class="structure-list">
            <li v-for="item in distribution" :key="item.bucket">
              <i :style="{ background: item.color }" />
              <span>{{ item.label }}</span>
              <small>{{ item.bucket }}</small>
              <b>{{ item.count }} 人</b>
              <em>{{ item.percent }}%</em>
            </li>
          </ul>
        </div>
      </section>

      <!-- 薄弱知识点与错误原因：前移到趋势与 AI 之前 -->
      <section class="section evidence-section">
        <div class="evidence-col">
          <header>
            <h2>薄弱知识点</h2>
            <button class="btn-text" type="button" @click="router.push('/teacher/knowledge')">进入知识图谱</button>
          </header>
          <ol>
            <li
              v-for="kp in data.weak_kps.slice(0, 5)"
              :key="kp.kp_id"
              role="button"
              tabindex="0"
              @click="router.push('/teacher/knowledge')"
              @keydown.enter="router.push('/teacher/knowledge')"
            >
              <div class="ev-copy">
                <b>{{ kp.kp_name }}</b>
                <small>{{ kp.students_below_60 }} 人未达标 · {{ kp.mistake_count }} 道错题</small>
              </div>
              <div class="ev-meter">
                <i
                  :style="{
                    width: `${Math.round(kp.avg_mastery * 100)}%`,
                    background: masteryTone(Math.round(kp.avg_mastery * 100)),
                  }"
                />
              </div>
              <span>{{ Math.round(kp.avg_mastery * 100) }}%</span>
              <ChevronRight class="ev-go" :size="15" />
            </li>
          </ol>
        </div>
        <div class="evidence-col">
          <header>
            <h2>错误原因</h2>
            <button class="btn-text" type="button" @click="router.push('/teacher/students')">查看学生证据</button>
          </header>
          <ol>
            <li
              v-for="item in data.error_distribution.slice(0, 5)"
              :key="item.code"
              role="button"
              tabindex="0"
              @click="router.push('/teacher/students')"
              @keydown.enter="router.push('/teacher/students')"
            >
              <div class="ev-copy">
                <b>{{ item.label || item.code || "待教师归因" }}</b>
                <small>{{ item.count }} 道待处理</small>
              </div>
              <div class="ev-meter"><i :style="{ width: `${item.ratio_pct}%` }" /></div>
              <span>{{ item.ratio_pct }}%</span>
              <ChevronRight class="ev-go" :size="15" />
            </li>
          </ol>
        </div>
      </section>

      <!-- 近 N 天学习趋势：范围切换 + 双轴 + 数据点 + Tooltip -->
      <section class="section">
        <header class="section-head">
          <div>
            <h2>近 {{ chartDays }} 天学习趋势</h2>
            <p>学习活跃度、日均得分与教学干预变化。</p>
          </div>
          <div class="trend-controls">
            <div class="range-switch" role="tablist" aria-label="趋势时间范围">
              <button
                v-for="d in [7, 30, 90]"
                :key="d"
                type="button"
                role="tab"
                :aria-selected="chartDays === d"
                :class="{ active: chartDays === d }"
                @click="setChartDays(d)"
              >{{ d }} 天</button>
            </div>
            <div class="trend-legend">
              <span class="lg-score">日均得分（左轴）</span>
              <span class="lg-act">活动次数（右轴）</span>
            </div>
          </div>
        </header>
        <div class="trend-layout">
          <figure v-if="trendChart" class="trend-chart" :class="{ dim: refreshing }">
            <svg
              viewBox="0 0 720 240"
              role="img"
              aria-label="学习活跃度与日均得分趋势"
              @mousemove="onChartMove"
              @mouseleave="onChartLeave"
            >
              <line
                v-for="y in trendChart.gridYs"
                :key="y"
                class="grid"
                x1="0"
                :y1="y"
                x2="720"
                :y2="y"
              />
              <!-- 左轴（得分）与右轴（活动）标签 -->
              <text class="axis" x="0" :y="trendChart.gridYs[0] - 5">100 分</text>
              <text class="axis" x="0" :y="trendChart.gridYs[1] - 5">50 分</text>
              <text class="axis" x="0" :y="trendChart.gridYs[2] - 5">0</text>
              <text class="axis right" x="720" :y="trendChart.gridYs[0] - 5">{{ trendChart.actMax }} 次</text>
              <text class="axis right" x="720" :y="trendChart.gridYs[1] - 5">{{ Math.round(trendChart.actMax / 2) }} 次</text>
              <line
                v-if="hoverPoint"
                class="hover-guide"
                :x1="hoverPoint.x"
                :y1="trendChart.gridYs[0] - 8"
                :x2="hoverPoint.x"
                :y2="trendChart.gridYs[2]"
              />
              <polyline v-if="trendChart.actLine" class="line-activity" :points="trendChart.actLine" />
              <polyline v-if="trendChart.scoreLine" class="line-score" :points="trendChart.scoreLine" />
              <template v-if="trendChart.rows.length <= 45">
                <circle
                  v-for="(y, i) in trendChart.actY"
                  :key="`a${i}`"
                  class="pt-act"
                  :cx="trendChart.xs[i]"
                  :cy="y"
                  r="2"
                />
                <template v-for="(y, i) in trendChart.scoreY" :key="`s${i}`">
                  <circle v-if="y != null" class="pt-score" :cx="trendChart.xs[i]" :cy="y" r="2" />
                </template>
              </template>
              <circle
                v-if="trendChart.lastScoreIdx >= 0"
                class="pt-last"
                :cx="trendChart.xs[trendChart.lastScoreIdx]"
                :cy="trendChart.scoreY[trendChart.lastScoreIdx] ?? 0"
                r="3.5"
              />
              <g v-if="hoverPoint">
                <circle v-if="hoverPoint.scoreY != null" class="pt-hover score" :cx="hoverPoint.x" :cy="hoverPoint.scoreY" r="3.5" />
                <circle class="pt-hover act" :cx="hoverPoint.x" :cy="hoverPoint.actY" r="3.5" />
              </g>
            </svg>
            <div v-if="hoverPoint" class="trend-tooltip" :style="{ left: `${hoverPoint.leftPct}%` }">
              <b>{{ hoverPoint.row.date }}</b>
              <span><i class="tt-act" />学习活跃度 {{ hoverPoint.row.activity_count }} 次</span>
              <span v-if="hoverPoint.row.avg_score != null"><i class="tt-score" />日均得分 {{ Math.round(hoverPoint.row.avg_score) }} 分</span>
              <span v-else class="tt-none">当日无得分记录</span>
            </div>
            <figcaption>
              <span>{{ trendChart.firstDate }}</span>
              <span>{{ trendChart.lastDate }}</span>
            </figcaption>
          </figure>
          <div v-else class="trend-empty">本周期暂无趋势数据，完成一次课堂练习后开始记录。</div>
          <div class="trend-note">
            <small>{{ trendInsight.title }}</small>
            <b>{{ trendInsight.lead }}</b>
            <p>{{ trendInsight.detail }}</p>
          </div>
        </div>
      </section>

      <!-- AI 教学助理：低调浅紫，融入页面 -->
      <section ref="assistantEl" class="section">
        <div class="assistant-shell">
          <div class="assistant-main">
            <header>
              <span class="assistant-mark"><Sparkles :size="18" /></span>
              <div>
                <h2>AI 教学助理</h2>
                <p>基于当前班级证据，与 6 个 Agent 协同生成教学方案。</p>
              </div>
              <i>在线</i>
            </header>
            <div v-if="copilotResult" class="assistant-answer"><MarkdownBlock :content="copilotResult" /></div>
            <div v-else class="assistant-empty">
              <b>你希望如何推进本周教学？</b>
              <p>描述教学目标，多个 Agent 将协同完成分析、内容生成和教学任务设计。</p>
              <div class="assistant-templates">
                <button
                  v-for="tpl in quickPrompts"
                  :key="tpl"
                  type="button"
                  @click="askCopilot(tpl)"
                >{{ tpl }}</button>
              </div>
            </div>
            <form @submit.prevent="askCopilot()">
              <input v-model="copilotInput" placeholder="例如：为多智能体系统设计 18 分钟分层练习" />
              <button type="submit" :disabled="copilotLoading">
                <Send :size="16" /><span>{{ copilotLoading ? "协作中" : "发送" }}</span>
              </button>
            </form>
          </div>
          <aside class="assistant-team">
            <h3>6 Agent 协作组</h3>
            <div class="agent-list">
              <div v-for="agent in agents" :key="agent.kind">
                <img :src="agent.png || ''" :alt="agent.nick" />
                <span><b>{{ agent.nick }}</b><small>{{ agent.role }}</small></span>
                <i></i>
              </div>
            </div>
          </aside>
        </div>
      </section>
    </template>

    <OnboardingTour
      :storage-key="`tripleu.tour.teacher.v1::${teacherAccount}`"
      heading="教师管理台 · 快速上手"
      :steps="teacherTourSteps"
    />
  </div>
</template>

<style scoped lang="scss">
/* ============ Design Tokens（教师端提示词 2 · 更浅暖白 + 编辑式排版） ============ */
.teacher-overview-v6 {
  --bg: #fbfaf7;
  --bg-subtle: #f8f7f3;
  --surface: #ffffff;
  --surface-muted: #f5f3ee;
  --heading: #181612;
  --ink: #24211d;
  --ink-2: #68635b;
  --ink-3: #918b82;
  --line: #e7e2da;
  --line-btn: #e7e2da;
  --brand: #e85d16;
  --brand-hover: #d75011;
  --brand-container: #fff1e8;
  --brand-container-border: #f3c5a8;
  --ai: #6757d9;
  --ai-container: #f7f5ff;
  --ai-border: #e4dff8;
  --good: #23966a;
  --warn: #a86d19;
  --bad: #b84940;
  --plain: #68635b;
  --serif: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  /* 垂直节奏 Tokens：与壳层 --header-content-gap 配套，间距不叠加 */
  --page-heading-gap: 10px;
  --heading-metadata-gap: 20px;
  --metadata-insight-gap: 24px;
  /* 规范：普通 Section 24–32px，主要业务 32–40px —— 紧凑但不拥挤 */
  --section-gap: 32px;
  /* 宽度交给壳层 1540 网格统一限制 */
  width: 100%;
  margin: 0 auto;
  /* 顶部间距由壳层 shell-main 统一提供，此处不再叠加 padding-top */
  padding: 0 0 64px;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.7;
}
button,
input {
  font: inherit;
}
button {
  cursor: pointer;
}

/* 页面加载：淡入 + translateY(6px→0)，240ms，Section stagger 50ms */
@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.teacher-overview-v6 > * {
  animation: rise 240ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
.teacher-overview-v6 > :nth-child(2) { animation-delay: 50ms; }
.teacher-overview-v6 > :nth-child(3) { animation-delay: 100ms; }
.teacher-overview-v6 > :nth-child(4) { animation-delay: 150ms; }
.teacher-overview-v6 > :nth-child(5) { animation-delay: 200ms; }
.teacher-overview-v6 > :nth-child(6) { animation-delay: 250ms; }
.teacher-overview-v6 > :nth-child(7) { animation-delay: 300ms; }
.teacher-overview-v6 > :nth-child(8) { animation-delay: 350ms; }
.teacher-overview-v6 > :nth-child(9) { animation-delay: 400ms; }

/* ============ 按钮体系：首屏唯一 Filled Primary 在核心洞察 ============ */
.btn-filled,
.btn-outlined {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 18px;
  border-radius: 9px;
  font-size: 14px;
  font-weight: 600;
  transition:
    background 170ms ease-out,
    border-color 170ms ease-out,
    color 170ms ease-out,
    transform 170ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 170ms ease-out;
}
.btn-filled {
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
}
.btn-filled:hover {
  background: var(--brand-hover);
  border-color: var(--brand-hover);
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.09);
}
.btn-outlined {
  border: 1px solid var(--line-btn);
  background: var(--surface);
  color: #393631;
}
.btn-outlined:hover {
  border-color: #c6c1b7;
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.btn-filled:active,
.btn-outlined:active {
  transform: translateY(0) scale(0.98);
}
.btn-filled:disabled,
.btn-outlined:disabled,
.btn-text:disabled {
  opacity: 0.55;
  cursor: default;
  transform: none;
  box-shadow: none;
}
.btn-sm {
  min-height: 34px;
  padding: 0 13px;
  border-radius: 8px;
  font-size: 13px;
  gap: 4px;
}
.btn-text {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ink-2);
  font-size: 13.5px;
  font-weight: 600;
  transition: color 160ms ease-out, background 160ms ease-out;
}
.btn-text:hover {
  color: var(--brand);
  background: var(--bg-subtle);
}

/* ============ 页面标题区：Grid 对齐，操作按钮随基线，不用独立 margin 下沉 ============ */
.page-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  column-gap: 32px;
  row-gap: var(--page-heading-gap);
  align-items: end;
  padding-bottom: var(--heading-metadata-gap);
}
.page-heading h1 {
  max-width: 720px;
  margin: 0;
  color: var(--heading);
  font-family: var(--serif);
  font-size: 38px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
  text-wrap: balance;
}
.lede {
  max-width: 60ch;
  margin: 8px 0 0;
  color: var(--ink-2);
  font-size: 15px;
  line-height: 1.6;
}
.heading-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  align-self: end;
  margin-bottom: 4px;
}

/* ============ Metadata Bar：50px 高，紧跟标题区 ============ */
.meta-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 32px;
  min-height: 50px;
  padding: 4px 2px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.meta-bar > div {
  display: flex;
  align-items: baseline;
  gap: 9px;
}
.meta-bar small {
  color: var(--ink-3);
  font-size: 13px;
}
.meta-bar b {
  font-size: 13.5px;
  font-weight: 600;
}
.course-select {
  padding: 4px 2px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--ink);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background 160ms ease-out, color 160ms ease-out;
}
.course-select:hover {
  background: var(--surface-muted);
  color: var(--brand);
}
.course-select:focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
  outline-offset: 1px;
}

/* ============ 本周核心教学洞察 ============ */
.insight-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 290px;
  gap: 36px;
  margin-top: var(--metadata-insight-gap);
  padding: 32px 40px;
  border: 1px solid var(--brand-container-border);
  border-radius: 14px;
  background: var(--brand-container);
}
.hero-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--brand-hover);
  font-size: 13px;
  font-weight: 700;
}
.hero-copy h2 {
  max-width: 30ch;
  margin: 12px 0 12px;
  color: var(--heading);
  font-family: var(--serif);
  font-size: 26px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: -0.01em;
}
.hero-copy h2 em {
  color: var(--brand);
  font-style: normal;
}
.hero-copy p {
  max-width: 64ch;
  margin: 0 0 22px;
  color: var(--ink-2);
  font-size: 14.5px;
  line-height: 1.7;
}
.hero-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
}
.hero-stats {
  display: grid;
  align-content: center;
  gap: 18px;
  padding-left: 34px;
  border-left: 1px solid #eed7c4;
}
.hero-stats small {
  display: block;
  color: var(--ink-3);
  font-size: 12.5px;
}
.hero-stats b {
  display: block;
  margin-top: 5px;
  font-size: 27px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.hero-stats b i {
  margin-left: 5px;
  color: var(--ink-2);
  font-size: 13.5px;
  font-style: normal;
  font-weight: 500;
}

/* ============ KPI Strip：数字 + 结论 ============ */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: var(--section-gap);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.kpi-strip > div {
  padding: 20px 26px;
  border-left: 1px solid var(--line);
  transition: background 170ms ease-out;
}
.kpi-strip > div:first-child {
  border-left: 0;
  padding-left: 2px;
}
.kpi-strip > div:hover {
  background: var(--bg-subtle);
}
.kpi-strip small {
  display: block;
  color: var(--ink-3);
  font-size: 12.5px;
}
.kpi-strip b {
  display: block;
  margin: 9px 0 7px;
  font-size: 32px;
  font-weight: 600;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.kpi-strip b i {
  margin-left: 4px;
  color: var(--ink-3);
  font-size: 14px;
  font-style: normal;
  font-weight: 500;
}
.kpi-strip span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--plain);
  font-size: 13px;
}
.kpi-strip span.good { color: var(--good); }
.kpi-strip span.warn { color: var(--warn); }
.kpi-strip span.bad { color: var(--bad); }
.kpi-strip span.plain { color: var(--plain); }

/* ============ 教学工作流大卡片 v2（2026-07-17 叙事优化） ============
   每张卡三层信息：场景叙事（宣传语）→ 实时班级数据 → 入口聚合 + 主 CTA */
.workflow-strip { margin-top: var(--section-gap); }

.wf-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;

  h2 { margin: 0; color: var(--heading); font-size: 22px; letter-spacing: -0.01em; }
  p { margin: 7px 0 0; color: var(--ink-2); font-size: 13.5px; }
}
.wf-eyebrow {
  display: inline-block;
  margin-bottom: 8px;
  padding: 4px 12px;
  border-radius: 999px;
  background: #fff2ea;
  color: #d9460b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
}
.wf-replay {
  flex-shrink: 0;
  padding: 9px 16px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #fff;
  color: var(--ink-2);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 160ms ease-out, color 160ms ease-out;
  &:hover { border-color: #e95514; color: #d9460b; }
}

/* 平台价值主张行：宣传 + 解释「管理台能做什么」 */
.wf-props {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;

  > article {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 15px;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: linear-gradient(155deg, #fffaf6, #fff);
  }
  b { color: #d9460b; font-size: 13.5px; }
  span { color: var(--ink-2); font-size: 12px; line-height: 1.6; }
}
@media (max-width: 1100px) { .wf-props { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .wf-props { grid-template-columns: 1fr; } }

.wf-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;

  > article {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow: hidden;
    padding: 17px 16px 14px;
    background: var(--surface);
    border: 1.5px solid var(--line);
    border-radius: 15px;
    transition: transform 200ms cubic-bezier(0.16, 1, 0.3, 1), border-color 180ms ease-out, box-shadow 200ms ease-out;

    &:hover {
      transform: translateY(-3px);
      border-color: #ddd5c9;
      box-shadow: 0 14px 32px rgba(32, 27, 20, 0.08);
    }
    &.active {
      border-color: #e95514;
      background: linear-gradient(155deg, #fff6ef 0%, #fff 46%);
      box-shadow: 0 10px 28px rgba(233, 85, 20, 0.09);
    }
  }

  .wf-watermark {
    position: absolute;
    top: -12px;
    right: 6px;
    color: rgba(32, 27, 20, 0.05);
    font-size: 68px;
    font-weight: 800;
    letter-spacing: -0.04em;
    pointer-events: none;
  }
  > article.active .wf-watermark { color: rgba(233, 85, 20, 0.08); }

  .wf-top { display: flex; align-items: center; gap: 9px; }
  .wf-icon {
    display: grid;
    place-items: center;
    width: 42px;
    height: 42px;
    border-radius: 12px;
    background: #fff2ea;
    color: #d9460b;
  }
  .wf-stage { color: #d9460b; font-size: 12px; font-weight: 800; letter-spacing: 0.06em; }
  h3 { margin: 0; color: var(--heading); font-size: 17.5px; }

  .wf-promo {
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    margin: 0;
    color: var(--ink-2);
    font-size: 12.5px;
    line-height: 1.7;
    min-height: 60px;
  }

  .wf-stat {
    display: flex;
    align-items: baseline;
    gap: 8px;
    padding: 9px 13px;
    border-radius: 11px;
    background: var(--surface-muted);
    b { color: var(--heading); font-size: 17px; }
    small { color: var(--ink-3); font-size: 11.5px; }
  }
  > article.active .wf-stat { background: #fff0e5; b { color: #d9460b; } }

  .wf-links { display: flex; flex-direction: column; gap: 4px; }
  .wf-links button {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 14px;
    align-items: center;
    gap: 9px;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 10px;
    background: transparent;
    text-align: left;
    cursor: pointer;
    transition: background-color 150ms ease-out, border-color 150ms ease-out, transform 150ms ease-out;

    &:hover { background: #fff2ea; border-color: #f4d8c4; transform: translateX(2px); .wf-link-label { color: #d9460b; } }
  }
  .wf-link-label { color: var(--ink); font-size: 13.5px; font-weight: 700; white-space: nowrap; }
  .wf-link-hint { overflow: hidden; color: var(--ink-3); font-size: 11.5px; text-overflow: ellipsis; white-space: nowrap; }
  .wf-links svg { color: #cdc6ba; }

  .wf-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    margin-top: auto;
    padding: 11px 14px;
    border: 1px solid var(--line);
    border-radius: 11px;
    background: #fff;
    color: var(--ink);
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: transform 160ms ease-out, border-color 160ms ease-out, color 160ms ease-out, box-shadow 160ms ease-out;
    &:hover { transform: translateY(-1px); border-color: #e95514; color: #d9460b; }
  }
  > article.active .wf-cta {
    border-color: transparent;
    background: #e95514;
    color: #fff;
    box-shadow: 0 6px 16px rgba(233, 85, 20, 0.28);
  }
}

@media (max-width: 1100px) {
  .wf-cards { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 700px) {
  .wf-cards { grid-template-columns: 1fr; }
  .wf-cards .wf-promo { min-height: 0; }
}

/* ============ Section 节奏：模块间统一 --section-gap，标题与内容 16px ============ */
.section {
  margin-top: var(--section-gap);
}
.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}
.section-head h2 {
  margin: 0;
  color: var(--heading);
  font-size: 19px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.section-head p {
  margin: 6px 0 0;
  color: var(--ink-2);
  font-size: 13.5px;
}
.pill-positive {
  padding: 5px 11px;
  border-radius: 999px;
  background: #e9f2ec;
  color: var(--good);
  font-size: 12.5px;
  font-weight: 600;
}

/* ============ 今天优先做三件事：任务列表 ============ */
.task-list {
  display: grid;
  gap: 8px;
}
.task-item {
  display: grid;
  grid-template-columns: 30px auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  min-height: 72px;
  padding: 10px 16px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  cursor: pointer;
  transition:
    transform 170ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 170ms ease-out,
    background 170ms ease-out,
    box-shadow 170ms ease-out;
}
.task-item.risk {
  background: #fff8f6;
}
.task-item:hover {
  transform: translateY(-1px);
  border-color: #d7d1c7;
  background: var(--bg-subtle);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.task-item:focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
  outline-offset: 2px;
}
.task-no {
  color: var(--ink-3);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.task-tag {
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
  font-weight: 600;
  white-space: nowrap;
}
.task-tag.risk {
  background: #f9ebe8;
  color: var(--bad);
}
.task-tag.focus {
  background: #f4ede2;
  color: var(--warn);
}
.task-tag.plan {
  background: var(--surface-muted);
  color: var(--plain);
}
.task-copy b {
  display: block;
  font-size: 15px;
  font-weight: 600;
}
.task-copy small {
  display: block;
  margin-top: 4px;
  color: var(--ink-2);
  font-size: 13px;
}
.task-eta {
  color: var(--ink-3);
  font-size: 12.5px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* ============ 班级学习结构 ============ */
.structure-card {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 40px;
  padding: 26px 30px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  transition: border-color 180ms ease-out, box-shadow 180ms ease-out, transform 180ms ease-out;
}
.structure-card:hover {
  border-color: #d7d1c7;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
  transform: translateY(-1px);
}
.structure-summary b {
  font-size: 46px;
  font-weight: 600;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}
.structure-summary b i {
  color: var(--ink-3);
  font-size: 20px;
  font-style: normal;
  font-weight: 500;
}
.structure-summary > span {
  display: block;
  margin-top: 2px;
  color: var(--ink-2);
  font-size: 13.5px;
}
.stacked-bar {
  display: flex;
  height: 14px;
  margin-top: 20px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-muted);
}
.stacked-bar i {
  height: 100%;
  transition: width 250ms ease-out;
}
.stacked-bar i + i {
  border-left: 2px solid #fff;
}
.structure-conclusion {
  margin: 12px 0 0;
  color: var(--ink-2);
  font-size: 13.5px;
  line-height: 1.6;
}
.structure-list {
  margin: 0;
  padding: 0;
  list-style: none;
  align-self: center;
}
.structure-list li {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto 54px 46px;
  align-items: center;
  gap: 12px;
  min-height: 40px;
  border-top: 1px solid var(--line);
  font-size: 13.5px;
  transition: background 160ms ease-out;
}
.structure-list li:first-child {
  border-top: 0;
}
.structure-list li:hover {
  background: var(--bg-subtle);
}
.structure-list i {
  width: 9px;
  height: 9px;
  border-radius: 3px;
}
.structure-list small {
  color: var(--ink-3);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.structure-list b {
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.structure-list em {
  color: var(--ink-3);
  font-style: normal;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* ============ 薄弱知识点与错误原因 ============ */
.evidence-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 40px;
}
.evidence-col header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.evidence-col h2 {
  margin: 0;
  color: var(--heading);
  font-size: 19px;
  font-weight: 600;
}
.evidence-col ol {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.evidence-col li {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 110px 46px 16px;
  align-items: center;
  gap: 14px;
  min-height: 56px;
  padding: 0 8px;
  border-top: 1px solid var(--line);
  cursor: pointer;
  transition: background 160ms ease-out;
}
.evidence-col li:hover {
  background: var(--bg-subtle);
}
.evidence-col li:focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
  outline-offset: -2px;
}
.ev-copy b,
.ev-copy small {
  display: block;
}
.ev-copy b {
  font-size: 14px;
  font-weight: 600;
}
.ev-copy small {
  margin-top: 3px;
  color: var(--ink-3);
  font-size: 12.5px;
}
.ev-meter {
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-muted);
}
.ev-meter i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--ink-3);
  transition: width 250ms ease-out;
}
.evidence-col li > span {
  font-size: 14.5px;
  font-weight: 600;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.ev-go {
  color: var(--ink-3);
  opacity: 0;
  transform: translateX(-3px);
  transition: opacity 160ms ease-out, transform 160ms ease-out, color 160ms ease-out;
}
.evidence-col li:hover .ev-go {
  opacity: 1;
  transform: translateX(0);
  color: var(--brand);
}

/* ============ 趋势：范围切换 + 双轴 + Tooltip ============ */
.trend-controls {
  display: flex;
  align-items: center;
  gap: 18px;
}
.range-switch {
  display: inline-flex;
  padding: 3px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
}
.range-switch button {
  min-height: 30px;
  padding: 0 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink-2);
  font-size: 12.5px;
  font-weight: 600;
  transition: background 160ms ease-out, color 160ms ease-out;
}
.range-switch button:hover {
  color: var(--heading);
}
.range-switch button.active {
  background: var(--surface-muted);
  color: var(--heading);
}
.trend-legend {
  display: flex;
  gap: 16px;
  font-size: 12.5px;
  color: var(--ink-2);
}
.trend-legend span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.trend-legend span::before {
  content: "";
  width: 16px;
  height: 3px;
  border-radius: 2px;
}
.lg-score::before {
  background: #e8601b;
}
.lg-act::before {
  background: #6f9b78;
}
.trend-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 272px;
  gap: 30px;
  align-items: center;
}
.trend-chart {
  position: relative;
  margin: 0;
  padding: 18px 20px 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  transition: opacity 200ms ease-out;
}
.trend-chart.dim {
  opacity: 0.55;
}
.trend-chart svg {
  width: 100%;
  height: 244px;
  overflow: visible;
}
.trend-chart .grid {
  stroke: #ece9e3;
  stroke-width: 1;
}
.trend-chart .axis {
  fill: var(--ink-3);
  font-size: 12px;
}
.trend-chart .axis.right {
  text-anchor: end;
}
.hover-guide {
  stroke: #d7d1c7;
  stroke-width: 1;
  stroke-dasharray: 3 3;
}
.line-score {
  fill: none;
  stroke: #e8601b;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.line-activity {
  fill: none;
  stroke: #6f9b78;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.pt-score {
  fill: #e8601b;
}
.pt-act {
  fill: #6f9b78;
}
.pt-last {
  fill: #e8601b;
  stroke: #fff;
  stroke-width: 2;
}
.pt-hover {
  stroke: #fff;
  stroke-width: 2;
}
.pt-hover.score {
  fill: #e8601b;
}
.pt-hover.act {
  fill: #6f9b78;
}
.trend-tooltip {
  position: absolute;
  top: 10px;
  transform: translateX(-50%);
  display: grid;
  gap: 3px;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.08);
  pointer-events: none;
  white-space: nowrap;
  z-index: 5;
}
.trend-tooltip b {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.trend-tooltip span {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--ink-2);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.trend-tooltip i {
  width: 8px;
  height: 8px;
  border-radius: 3px;
}
.tt-score {
  background: #e8601b;
}
.tt-act {
  background: #6f9b78;
}
.tt-none {
  color: var(--ink-3);
}
.trend-chart figcaption {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  color: var(--ink-3);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.trend-empty {
  display: grid;
  place-items: center;
  min-height: 200px;
  border: 1px dashed var(--line);
  border-radius: 12px;
  color: var(--ink-3);
  font-size: 13.5px;
}
.trend-note {
  padding-left: 26px;
  border-left: 1px solid var(--line);
}
.trend-note small {
  color: var(--brand-hover);
  font-size: 12.5px;
  font-weight: 700;
}
.trend-note b {
  display: block;
  margin-top: 9px;
  font-size: 15.5px;
  font-weight: 600;
  line-height: 1.55;
}
.trend-note p {
  margin: 9px 0 0;
  color: var(--ink-2);
  font-size: 13.5px;
  line-height: 1.7;
}

/* ============ AI 教学助理：融入页面的浅紫 ============ */
.assistant-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 272px;
  overflow: hidden;
  border: 1px solid var(--ai-border);
  border-radius: 14px;
  background: var(--ai-container);
}
.assistant-main {
  min-height: 340px;
  padding: 24px 28px;
}
.assistant-main header {
  display: flex;
  align-items: center;
  gap: 13px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--ai-border);
}
.assistant-mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 11px;
  background: #efecfb;
  color: var(--ai);
}
.assistant-main header h2 {
  margin: 0;
  color: var(--heading);
  font-size: 17px;
  font-weight: 600;
}
.assistant-main header p {
  margin: 4px 0 0;
  color: var(--ink-2);
  font-size: 13px;
}
.assistant-main header i {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  color: var(--good);
  font-size: 12.5px;
  font-style: normal;
  font-weight: 600;
}
.assistant-main header i::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--good);
}
.assistant-empty {
  display: grid;
  justify-items: center;
  align-content: center;
  min-height: 190px;
  padding: 18px 0;
  text-align: center;
}
.assistant-empty b {
  font-size: 17px;
  font-weight: 600;
}
.assistant-empty p {
  max-width: 46ch;
  margin: 8px 0 0;
  color: var(--ink-2);
  font-size: 14px;
  line-height: 1.7;
}
.assistant-templates {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
}
.assistant-templates button {
  min-height: 34px;
  padding: 0 13px;
  border: 1px solid var(--ai-border);
  border-radius: 999px;
  background: #fff;
  color: #4f43ad;
  font-size: 13px;
  font-weight: 550;
  transition: border-color 160ms ease-out, background 160ms ease-out, transform 160ms ease-out;
}
.assistant-templates button:hover {
  border-color: var(--ai);
  background: #f3f1fd;
  transform: translateY(-1px);
}
.assistant-answer {
  max-height: 280px;
  overflow: auto;
  padding: 16px 4px;
  color: #33312c;
  font-size: 14px;
  line-height: 1.7;
}
.assistant-main form {
  display: flex;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--ai-border);
}
.assistant-main input {
  flex: 1;
  min-width: 0;
  height: 46px;
  padding: 0 16px;
  border: 1px solid var(--line);
  border-radius: 10px;
  outline: 0;
  background: #fff;
  color: var(--ink);
  font-size: 14px;
  transition: border-color 160ms ease-out, box-shadow 160ms ease-out;
}
.assistant-main input::placeholder {
  color: var(--ink-3);
}
.assistant-main input:focus {
  border-color: var(--ai);
  box-shadow: 0 0 0 3px rgba(101, 87, 217, 0.12);
}
.assistant-main form button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 92px;
  border: 0;
  border-radius: 10px;
  background: var(--ai);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  transition: background 160ms ease-out, transform 160ms ease-out;
}
.assistant-main form button:hover {
  background: #5647c8;
  transform: translateY(-1px);
}
.assistant-main form button:disabled {
  opacity: 0.6;
  transform: none;
}
.assistant-team {
  padding: 24px 22px;
  border-left: 1px solid var(--ai-border);
  background: #f6f5fc;
}
.assistant-team h3 {
  margin: 0 0 14px;
  color: var(--heading);
  font-size: 14.5px;
  font-weight: 600;
}
.agent-list {
  display: grid;
  gap: 4px;
}
.agent-list > div {
  display: grid;
  grid-template-columns: 32px 1fr 8px;
  align-items: center;
  gap: 11px;
  padding: 6px 9px;
  border-radius: 9px;
  transition: background 160ms ease-out;
}
.agent-list > div:hover {
  background: #fff;
}
.agent-list img {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}
.agent-list span b,
.agent-list span small {
  display: block;
}
.agent-list span b {
  font-size: 13px;
  font-weight: 600;
}
.agent-list span small {
  margin-top: 1px;
  color: var(--ink-3);
  font-size: 12px;
}
.agent-list i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--good);
}

/* ============ 加载与错误 ============ */
.loading-state,
.error-state {
  display: grid;
  place-items: center;
  align-content: center;
  min-height: 360px;
  text-align: center;
}
.loading-state span {
  width: 32px;
  height: 32px;
  border: 3px solid var(--line);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-state b,
.error-state b {
  margin-top: 16px;
  font-size: 16px;
}
.loading-state p,
.error-state p {
  margin: 8px 0 16px;
  color: var(--ink-2);
  font-size: 14px;
}
.spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* ============ 响应式 ============ */
@media (max-width: 1439px) {
  .page-heading h1 {
    font-size: 34px;
  }
}
@media (max-width: 1100px) {
  .teacher-overview-v6 {
    --section-gap: 28px;
    padding: 0 0 56px;
  }
  .page-heading {
    grid-template-columns: 1fr;
    align-items: start;
  }
  .heading-actions {
    justify-self: start;
    margin-bottom: 0;
  }
  .insight-hero,
  .trend-layout,
  .assistant-shell {
    grid-template-columns: 1fr;
  }
  .hero-stats {
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    padding: 20px 0 0;
    border-top: 1px solid #eed7c4;
    border-left: 0;
  }
  .structure-card {
    grid-template-columns: 1fr;
    gap: 22px;
  }
  .trend-note {
    padding: 20px 0 0;
    border-top: 1px solid var(--line);
    border-left: 0;
  }
  .assistant-team {
    border-top: 1px solid var(--ai-border);
    border-left: 0;
  }
  .evidence-section {
    grid-template-columns: 1fr;
    gap: 40px;
  }
  .trend-controls {
    flex-wrap: wrap;
    gap: 10px;
  }
}
@media (max-width: 720px) {
  .teacher-overview-v6 {
    --section-gap: 24px;
    --metadata-insight-gap: 20px;
    padding: 0 0 48px;
  }
  .page-heading h1 {
    font-size: 30px;
  }
  .insight-hero {
    padding: 24px 20px;
  }
  .hero-stats {
    grid-template-columns: 1fr 1fr;
  }
  .kpi-strip {
    grid-template-columns: repeat(2, 1fr);
  }
  .kpi-strip > div {
    padding: 16px 16px;
  }
  .kpi-strip > div:nth-child(odd) {
    border-left: 0;
    padding-left: 2px;
  }
  .kpi-strip > div:nth-child(n + 3) {
    border-top: 1px solid var(--line);
  }
  .structure-card {
    padding: 20px 16px;
  }
  .task-item {
    grid-template-columns: 30px auto minmax(0, 1fr);
    row-gap: 8px;
  }
  .task-eta,
  .task-item .btn-sm {
    grid-column: 3;
    justify-self: start;
  }
  .evidence-col li {
    grid-template-columns: minmax(0, 1fr) 70px 42px;
    gap: 10px;
  }
  .ev-go {
    display: none;
  }
}
@media (prefers-reduced-motion: reduce) {
  .teacher-overview-v6 > *,
  .teacher-overview-v6 *,
  .teacher-overview-v6 *::before,
  .teacher-overview-v6 *::after {
    animation-duration: 0.01ms !important;
    animation-delay: 0ms !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
