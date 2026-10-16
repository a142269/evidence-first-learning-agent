<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowRight,
  BookX,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  PlayCircle,
  Route as RouteIcon,
  Sparkles,
  TrendingUp,
} from "lucide-vue-next";

import OnboardingTour, { type TourStep } from "@/components/shared/OnboardingTour.vue";
import { STUDENT_VALUE_PROPS } from "@/constants/platformGuide";
import { getStudentOverview, getRecommendations, type StudentOverviewResponse, type RecommendationsResponse } from "@/api/insights";
import { getLearnerStateTimeline, type TimelineEvent } from "@/api/learner_state";
import { getGamification, type GamificationProfile } from "@/api/gamification";
import { listCourses } from "@/api/knowledge";
import { useSession } from "@/composables/useSession";
import { getAuthSession } from "@/utils/auth";
import plannerImg from "@/assets/login-avatars/planner.png";
import contentImg from "@/assets/login-avatars/content.png";
import tutorImg from "@/assets/login-avatars/tutor.png";
import quizImg from "@/assets/login-avatars/quiz.png";
import evaluationImg from "@/assets/login-avatars/evaluation.png";
import safetyImg from "@/assets/login-avatars/safety.png";

interface TodayTask {
  index: string;
  kind: string;
  title: string;
  detail: string;
  minutes: number;
  action: string;
  to: string;
  urgent?: boolean;
}

const router = useRouter();
const { userId, course, setCourse } = useSession();
const overview = ref<StudentOverviewResponse | null>(null);
const recommendations = ref<RecommendationsResponse | null>(null);
const timeline = ref<TimelineEvent[]>([]);
const gamification = ref<GamificationProfile | null>(null);
const loading = ref(true);
const notice = ref("");
let noticeTimer: ReturnType<typeof setTimeout> | null = null;

const legacyDemoNames = new Set(["演示学习者", "张三", "小明"]);
const displayName = computed(() => {
  const name = getAuthSession()?.displayName || "杜同学";
  return legacyDemoNames.has(name) ? "杜同学" : name;
});
// 课程显示名由后端 course.yaml 清单下发（2026-07-16 平台化改造，去除前端写死映射）
const fallbackCourses = [{ value: "artificial_intelligence", label: "人工智能导论" }];
const courseOptions = ref([...fallbackCourses]);
const currentCourseLabel = computed(() =>
  courseOptions.value.find((item) => item.value === course.value)?.label
    || course.value.replace(/_/g, " "),
);
const summary = computed(() => overview.value?.summary);
const path = computed(() => overview.value?.path);
const hasLearningPath = computed(() => Boolean(
  path.value?.id || path.value?.stages?.length,
));
const hasLearningHistory = computed(() => Boolean(
  hasLearningPath.value
  || (summary.value?.mastered_knowledge_points ?? 0) > 0
  || (overview.value?.assessment.total ?? 0) > 0
  || (overview.value?.activity.total_minutes ?? 0) > 0,
));
const isNewLearner = computed(() => !hasLearningHistory.value);
const riskPoints = computed(() => {
  const risks = overview.value?.profile.risks || [];
  return risks.slice(0, 3);
});

const focusName = computed(() => {
  if (!hasLearningPath.value) return "创建你的第一条学习路径";
  const task = path.value?.today_tasks?.[0] as Record<string, any> | undefined;
  const raw = String(task?.kp_name || task?.title || task?.name || riskPoints.value[0]?.kp_name || "课程知识点").trim();
  return raw
    .replace(/^(学习|复习|练习|巩固|继续学习)\s*[「《]?/, "")
    .replace(/[」》]$/, "")
    || "课程知识点";
});
const mastery = computed(() => Math.round(summary.value?.average_mastery_pct ?? 0));
const progress = computed(() => Math.round(path.value?.progress_pct ?? 0));
const stage = computed(() => Number(path.value?.current_stage ?? 0));
const completedKps = computed(() => summary.value?.mastered_knowledge_points ?? 0);
const totalKps = computed(() => overview.value?.profile.knowledge_points.length ?? 0);
const streakDays = computed(() => summary.value?.streak_days ?? gamification.value?.streak_days ?? 0);
const weekMinutes = computed(() => overview.value?.activity.this_week_minutes ?? 0);
const unresolvedMistakes = computed(() => summary.value?.unresolved_mistake_count ?? 0);
const weeklyCompleted = computed(() => overview.value?.review.completed_7d ?? 0);
const masteryChange = computed(() => Math.max(overview.value?.assessment.week_score_change_pct ?? 0, 0));
const activeLearningCount = computed(() => hasLearningPath.value
  ? (path.value?.today_tasks ?? []).filter((task: Record<string, any>) => task.status !== "completed").length
  : 0);
const lastLearningText = computed(() =>
  overview.value?.assessment.recent?.[0]?.display_date
  || path.value?.updated_date
  || "尚未开始",
);

const onboardingTasks: TodayTask[] = [
  { index: "01", kind: "开始规划", title: "生成专属学习路径", detail: "结合注册问卷中的目标、基础与学习偏好规划路线", minutes: 3, action: "去规划", to: "/path", urgent: true },
  { index: "02", kind: "校准起点", title: "完成首次知识诊断", detail: "用少量问题确认真实起点，不会预设你已经掌握知识点", minutes: 8, action: "开始诊断", to: "/chat?agent=quiz" },
  { index: "03", kind: "认识讲师", title: "告诉猫头讲师你想先学什么", detail: "你的对话将用于持续校准画像和后续推荐", minutes: 4, action: "开始对话", to: "/chat?agent=tutor" },
];

const todayTasks = computed<TodayTask[]>(() => {
  const source = path.value?.today_tasks || [];
  if (!source.length) return onboardingTasks;
  const mapped = source.slice(0, 3).map((raw, index) => {
    const item = raw as Record<string, any>;
    const type = String(item.type || item.kind || "学习任务");
    return {
      index: String(index + 1).padStart(2, "0"),
      kind: index === 0 ? "优先学习" : type,
      title: String(item.title || item.name || item.kp_name || `学习任务 ${index + 1}`),
      detail: String(item.description || item.reason || item.detail || "已根据学习路径自动排序"),
      minutes: Number(item.estimated_minutes || item.minutes || 10),
      action: index === 0 ? "继续任务" : "开始学习",
      to: String(item.route || item.to || "/path"),
      urgent: index === 0,
    };
  });
  return mapped;
});

const suggestedTopic = computed(() =>
  recommendations.value?.weakest_kps?.[0]?.name
  || riskPoints.value[0]?.kp_name
  || "首次知识诊断",
);
const suggestionReason = computed(() => {
  if (isNewLearner.value) {
    return "注册问卷只用于建立初始偏好和目标，不会被当作学习完成记录。先生成路径并完成一次诊断后，这里才会出现基于真实行为的建议。";
  }
  return recommendations.value?.items?.[0]?.reason
    || `你在「${suggestedTopic.value}」上的掌握仍不稳定，建议先完成短讲解，再用基础练习及时验证。`;
});
const suggestionTitle = computed(() => isNewLearner.value
  ? "先确定学习起点，再生成个性化建议"
  : `先巩固「${suggestedTopic.value}」，再进入下一阶段`,
);

const recentFeedback = computed(() => {
  if (!timeline.value.length) return [];
  return timeline.value.slice(0, 3).map((event) => ({
    time: formatEventTime(event.timestamp),
    title: eventTitle(event),
    result: String(event.description || event.question || "学习状态已同步到你的个人画像"),
    tone: event.type === "assessment" ? "success" : event.type === "mistake_recorded" ? "warning" : "info",
  }));
});

const agents = computed(() => {
  if (isNewLearner.value) {
    return [
      { img: plannerImg, name: "小狐规划", work: "等待你生成第一条学习路径", state: "idle", label: "待开始" },
      { img: tutorImg, name: "猫头讲师", work: "等待你的第一次学习对话", state: "idle", label: "待开始" },
      { img: quizImg, name: "小龙挑战", work: "首次诊断后再生成分层练习", state: "idle", label: "待开始" },
      { img: evaluationImg, name: "熊猫评分", work: "暂无真实学习结果可评估", state: "idle", label: "待采集" },
      { img: contentImg, name: "河狸工匠", work: "路径确定后再生成个性化资源", state: "idle", label: "待开始" },
      { img: safetyImg, name: "刺猬守护", work: "注册信息与学习数据保持分离", state: "safe", label: "已就绪" },
    ];
  }
  return [
    { img: plannerImg, name: "小狐规划", work: `已更新 ${todayTasks.value.length} 项今日学习任务`, state: "done", label: "已完成" },
    { img: tutorImg, name: "猫头讲师", work: `准备了「${suggestedTopic.value}」概念讲解`, state: "working", label: "进行中" },
    { img: quizImg, name: "小龙挑战", work: "正在准备分层练习题", state: "working", label: "进行中" },
    { img: evaluationImg, name: "熊猫评分", work: `发现 ${unresolvedMistakes.value} 道需要复习的错题`, state: unresolvedMistakes.value ? "attention" : "done", label: unresolvedMistakes.value ? "需关注" : "已完成" },
    { img: contentImg, name: "河狸工匠", work: "正在整理相关学习资源", state: "done", label: "已完成" },
    { img: safetyImg, name: "刺猬守护", work: "学习环境与内容检查正常", state: "safe", label: "已就绪" },
  ];
});

// ============================================================
// 首页叙事优化 v2（2026-07-17）：「学 → 练 → 复盘」宣传 + 功能聚合大卡片
// 调研对标：学习通"任务优先"信息层级、知到"课前-课中-课后"阶段组织、
// Coursera 首页"一个主任务 + 场景化分组"。每张卡 = 阶段叙事 + 实时学情
// 数据 + 该场景全部功能入口 + 主 CTA，新用户一张卡即可理解一个场景。
// ============================================================
const journeyCards = computed(() => [
  {
    key: "learn",
    step: "01",
    icon: PlayCircle,
    stage: "学",
    title: "跟着今日计划学",
    promo: isNewLearner.value
      ? "注册问卷已形成初始画像；先生成路径并完成首次诊断，Agent 才会开始按真实学习证据调整顺序。"
      : `6 个 Agent 按你的画像排好了顺序，今天从「${focusName.value}」开始，不用自己纠结学什么。`,
    stats: [
      { label: "今日任务", value: `${todayTasks.value.length} 个` },
      { label: "预计", value: `${todayTasks.value.reduce((sum, item) => sum + item.minutes, 0)} 分钟` },
    ],
    links: [
      { label: "学习路径", hint: "阶段目标与顺序", to: "/path" },
      { label: "资源库", hint: "讲义/视频/代码", to: "/resources" },
      { label: "AI 讲解", hint: "听猫头讲师讲概念", to: "/chat?agent=tutor" },
    ],
    cta: "继续学习",
    to: "/path",
  },
  {
    key: "practice",
    step: "02",
    icon: BookX,
    stage: "练",
    title: "练习 + 错题闭环",
    promo: "小龙挑战按掌握度出分层练习；做错的题自动进错题本并生成变式题，直到真正掌握。",
    stats: [
      { label: "待复习错题", value: `${unresolvedMistakes.value} 道` },
      { label: "薄弱知识点", value: `${riskPoints.value.length} 个` },
    ],
    links: [
      { label: "闯关练习", hint: "分层题目即时反馈", to: "/chat?agent=quiz" },
      { label: "错题本", hint: "变式练习消灭错题", to: "/mistakes" },
      { label: "知识图谱", hint: "定位薄弱知识点", to: "/graph" },
    ],
    cta: "去练习",
    to: "/mistakes",
  },
  {
    key: "review",
    step: "03",
    icon: TrendingUp,
    stage: "复盘",
    title: "看懂自己的成长",
    promo: "掌握度、学习报告和画像随学随新，熊猫评分会告诉你下一步该补什么。",
    stats: [
      { label: "当前掌握度", value: `${mastery.value}%` },
      { label: "本周变化", value: `+${masteryChange.value}%` },
    ],
    links: [
      { label: "学习画像", hint: "6 维动态画像", to: "/profile" },
      { label: "学习大屏", hint: "全景数据可视化", to: "/dashboard" },
      { label: "群聊协作", hint: "和 Agent 小队复盘", to: "/chat" },
    ],
    cta: "看学习报告",
    to: "/profile",
  },
]);

// 首访新手引导（v2：每步带功能清单，讲清"有什么、在哪里、怎么用"）
const tourSteps: TourStep[] = [
  {
    badge: "👋",
    nav: "认识 triple U",
    image: plannerImg,
    title: "欢迎来到 triple U",
    desc: "这是你的个性化学习工作台。6 个 Agent 会根据你的画像和进度，每天替你决定「学什么、怎么学、学得如何」，你只需要沿着「学 → 练 → 复盘」一条动线走。",
    points: [
      { label: "智狐规划", text: "每天为你排好学习计划和路径" },
      { label: "猫头讲师", text: "用你能听懂的方式讲解概念" },
      { label: "小龙挑战", text: "按你的掌握度出分层练习题" },
      { label: "刺猬守护", text: "审核内容安全，防止 AI 幻觉" },
    ],
  },
  {
    badge: "①",
    nav: "学：今日计划",
    image: tutorImg,
    title: "学：每天从「今日学习计划」开始",
    desc: "首页中部的任务列表就是今天要做的全部事情，已按优先级排好。不知道学什么的时候，回到首页点第一条任务就对了。",
    points: [
      { label: "今日学习计划", text: "首页中部 · 点任务右侧按钮直接开始" },
      { label: "继续学习", text: "首页橙色大按钮 · 从上次断点继续" },
      { label: "学习路径", text: "顶部导航 · 查看完整阶段目标和顺序" },
      { label: "资源库", text: "顶部导航 · 讲义 / 视频 / 代码案例" },
    ],
  },
  {
    badge: "②",
    nav: "练：错题闭环",
    image: quizImg,
    title: "练：练习和错题自动闭环",
    desc: "做题不用自己找：小龙挑战按掌握度出题；做错的题自动进错题本并生成变式题，「需要复习」卡片还会按遗忘风险提醒你巩固。",
    points: [
      { label: "闯关练习", text: "群聊协作里 @小龙，或首页「开始练习」" },
      { label: "错题本", text: "顶部导航 · 错题自动收集 + 变式练习" },
      { label: "知识图谱", text: "顶部导航 · 红色节点 = 薄弱点，点击直达复习" },
      { label: "需要复习", text: "首页下方卡片 · 按遗忘风险排序" },
    ],
  },
  {
    badge: "③",
    nav: "复盘与求助",
    image: evaluationImg,
    title: "复盘 + 随时求助小狐狸",
    desc: "学习画像和报告随学随新，告诉你下一步补什么。迷路了就点右下角的桌宠小狐，或点顶栏「?」重看本引导——它的「指引」页会讲解每一页是干什么的、怎么用。",
    points: [
      { label: "学习画像", text: "顶部导航 · 6 维画像与学习报告" },
      { label: "学习大屏", text: "顶部导航 · 全景数据可视化" },
      { label: "桌宠小狐 · 指引", text: "右下角 · 每一页的玩法讲解 + 带路" },
      { label: "群聊协作", text: "顶部导航 · @任意 Agent 布置任务" },
    ],
    cta: "开始今日学习",
  },
];

function finishTour() {
  document.getElementById("today-plan")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** 随时重看新手引导（与顶栏「?」按钮同一机制） */
function reopenTour() {
  window.dispatchEvent(new CustomEvent("tripleu:open-tour"));
}

function formatEventTime(timestamp: number) {
  if (!timestamp) return "最近";
  const date = new Date(timestamp * (timestamp < 10_000_000_000 ? 1000 : 1));
  const today = new Date();
  const prefix = date.toDateString() === today.toDateString() ? "今天" : `${date.getMonth() + 1}月${date.getDate()}日`;
  return `${prefix} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function eventTitle(event: TimelineEvent) {
  const labels: Record<TimelineEvent["type"], string> = {
    profile_snapshot: "学习画像已更新",
    path_adjustment: "小狐规划调整了学习路径",
    mistake_recorded: "新增一条错题诊断",
    assessment: "熊猫评分完成了一次学习评估",
    resource_generated: "河狸工匠生成了新学习资源",
  };
  return labels[event.type] || "学习状态已更新";
}

function showNotice(message: string) {
  notice.value = message;
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (notice.value = ""), 2400);
}

function go(to: string) {
  void router.push(to);
}

async function loadHome() {
  loading.value = true;
  const [overviewResult, recommendationResult, timelineResult, gamificationResult] = await Promise.allSettled([
    getStudentOverview(userId.value, course.value),
    getRecommendations(userId.value, 4, course.value),
    getLearnerStateTimeline(userId.value, 8),
    getGamification(userId.value),
  ]);
  if (overviewResult.status === "fulfilled") overview.value = overviewResult.value;
  if (recommendationResult.status === "fulfilled") recommendations.value = recommendationResult.value;
  if (timelineResult.status === "fulfilled") timeline.value = timelineResult.value.events;
  if (gamificationResult.status === "fulfilled") gamification.value = gamificationResult.value;
  loading.value = false;
}

async function loadCourseOptions() {
  try {
    const response = await listCourses();
    const options = response.courses
      .map((item) => {
        if (typeof item === "string") {
          return { value: item, label: item.replace(/_/g, " ") };
        }
        const value = String(item.id || item.name || "");
        return {
          value,
          label: String(item.display_name || "") || value.replace(/_/g, " "),
        };
      })
      .filter((item) => Boolean(item.value));
    if (options.length) {
      courseOptions.value = options;
    }
  } catch {
    courseOptions.value = [...fallbackCourses];
  }
  if (!courseOptions.value.some((item) => item.value === course.value)) {
    setCourse(courseOptions.value[0]?.value || "artificial_intelligence");
  }
}

watch(course, () => void loadHome());
onMounted(async () => {
  await loadCourseOptions();
  await loadHome();
});
</script>

<template>
  <div class="student-home" :class="{ loading }">
    <header class="page-header">
      <div>
        <div class="course-eyebrow">课程 · 我的学习工作台</div>
        <h1 v-if="isNewLearner">{{ displayName }}，欢迎开始「{{ currentCourseLabel }}」的第一次学习</h1>
        <h1 v-else>{{ displayName }}，今天沿着「{{ currentCourseLabel }}」学习路径继续推进「{{ focusName }}」</h1>
        <p v-if="isNewLearner">注册问卷已经形成初始画像，但学习路径、掌握度和已完成知识点都从 0 开始。</p>
        <p v-else>根据你的学习进度、掌握状态和近期表现，6 个 Agent 已为你整理好今天的学习计划。</p>
      </div>
      <nav aria-label="页面操作">
        <button type="button" @click="go('/path')"><RouteIcon :size="16" />查看学习路径</button>
        <button type="button" @click="go('/profile')"><FileText :size="16" />查看学习报告</button>
      </nav>
    </header>

    <section class="metadata-bar" aria-label="学习概览">
      <div><span>当前课程</span><strong>{{ currentCourseLabel }}</strong></div>
      <div><span>学习路径</span><strong>{{ hasLearningPath ? `第 ${stage + 1} 阶段` : "待生成" }}</strong></div>
      <div><span>已完成知识点</span><strong>{{ totalKps ? `${completedKps} / ${totalKps}` : `${completedKps} 个` }}</strong></div>
      <div><span>连续学习</span><strong>{{ streakDays }} 天</strong></div>
      <div><span>最近学习</span><strong>{{ lastLearningText }}</strong></div>
    </section>

    <!-- 学习动线大卡片（2026-07-17 叙事优化 v2）：宣传 + 实时学情 + 功能聚合 -->
    <section class="journey-map" aria-label="学习动线与功能地图">
      <header class="journey-head">
        <div>
          <span class="journey-eyebrow">平台概览 · 学习动线</span>
          <h2>每天三步，学完就有反馈</h2>
          <p>全部功能围绕这条动线组织——先跟计划学，再练习闭环，最后看懂成长。点击卡片内任意入口直达。</p>
        </div>
        <button type="button" class="journey-replay" @click="reopenTour">重看新手引导</button>
      </header>
      <!-- 平台价值主张：一眼看懂 triple U 是什么（宣传 + 解释） -->
      <div class="journey-props" aria-label="平台核心能力">
        <article v-for="prop in STUDENT_VALUE_PROPS" :key="prop.label">
          <b>{{ prop.label }}</b>
          <span>{{ prop.text }}</span>
        </article>
      </div>
      <div class="journey-cards">
        <template v-for="(card, index) in journeyCards" :key="card.key">
          <article :class="{ active: index === 0 }">
            <span class="jc-watermark" aria-hidden="true">{{ card.step }}</span>
            <div class="jc-top">
              <span class="jc-icon"><component :is="card.icon" :size="19" /></span>
              <span class="jc-stage">第{{ ['一','二','三'][index] }}步 · {{ card.stage }}</span>
            </div>
            <h3>{{ card.title }}</h3>
            <p class="jc-promo">{{ card.promo }}</p>
            <div class="jc-stats">
              <div v-for="stat in card.stats" :key="stat.label">
                <b>{{ stat.value }}</b><small>{{ stat.label }}</small>
              </div>
            </div>
            <div class="jc-links">
              <button v-for="link in card.links" :key="link.to" type="button" @click="go(link.to)">
                <span class="jc-link-label">{{ link.label }}</span>
                <span class="jc-link-hint">{{ link.hint }}</span>
                <ChevronRight :size="13" />
              </button>
            </div>
            <button type="button" class="jc-cta" @click="go(card.to)">{{ card.cta }}<ArrowRight :size="15" /></button>
          </article>
          <span v-if="index < journeyCards.length - 1" class="journey-connector" aria-hidden="true"><ChevronRight :size="16" /></span>
        </template>
      </div>
    </section>

    <section class="focus-panel" aria-labelledby="focus-title">
      <div class="focus-copy">
        <span><PlayCircle :size="16" />{{ isNewLearner ? "开始第一次学习" : "继续学习" }}</span>
        <h2 id="focus-title">{{ focusName }}</h2>
        <p v-if="isNewLearner">当前没有学习路径，也没有已完成知识点。问卷中的“有基础”只作为自述，不会自动算作掌握。</p>
        <p v-else>学习路径已完成 {{ progress }}%，上次学习进度和相关反馈已经同步。</p>
        <p>{{ isNewLearner ? "建议依次完成" : "今天建议完成" }} {{ todayTasks.length }} 个任务，预计需要 {{ todayTasks.reduce((sum, item) => sum + item.minutes, 0) }} 分钟。</p>
        <div class="focus-actions">
          <button type="button" class="primary" @click="go('/path')">{{ isNewLearner ? "生成学习路径" : "继续学习" }}<ArrowRight :size="17" /></button>
          <button type="button" @click="go('/path')">查看学习路径</button>
        </div>
      </div>
      <dl class="focus-kpis">
        <div><dt>当前掌握度</dt><dd>{{ mastery }}<small>%</small></dd></div>
        <div><dt>今日任务</dt><dd>0<small>/ {{ todayTasks.length }}</small></dd></div>
        <div><dt>预计时长</dt><dd>{{ todayTasks.reduce((sum, item) => sum + item.minutes, 0) }}<small>分钟</small></dd></div>
      </dl>
    </section>

    <section id="today-plan" class="content-section today-plan" aria-labelledby="today-title">
      <header class="section-heading">
        <div><h2 id="today-title">{{ isNewLearner ? "从这里开始" : "今天的学习计划" }}</h2><p>{{ isNewLearner ? "先建立路径和学习证据，再开始个性化排序。" : "根据你的掌握状态和学习路径自动排序。" }}</p></div>
        <span><Clock3 :size="15" />预计 {{ todayTasks.reduce((sum, item) => sum + item.minutes, 0) }} 分钟</span>
      </header>
      <div class="task-list">
        <article v-for="task in todayTasks" :key="task.index" :class="{ urgent: task.urgent }">
          <span class="task-index">{{ task.index }}</span>
          <span class="task-kind">{{ task.kind }}</span>
          <div><h3>{{ task.title }}</h3><p>{{ task.detail }}</p></div>
          <span class="task-time">{{ task.minutes }} 分钟</span>
          <button type="button" @click="go(task.to)">{{ task.action }}<ChevronRight :size="15" /></button>
        </article>
      </div>
    </section>

    <section class="ai-panel" aria-labelledby="ai-title">
      <div class="ai-icon"><Sparkles :size="21" /></div>
      <div class="ai-copy">
        <span>AI 学习建议</span>
        <h2 id="ai-title">{{ suggestionTitle }}</h2>
        <p>{{ suggestionReason }}</p>
        <div><button type="button" @click="go('/chat?agent=tutor')">查看讲解</button><button type="button" @click="go('/chat?agent=quiz')">开始练习</button></div>
        <small>建议来源：熊猫评分 + 猫头讲师 + 小狐规划</small>
      </div>
    </section>

    <section class="content-section progress-section" aria-labelledby="progress-title">
      <header class="section-heading"><div><h2 id="progress-title">我的学习进度</h2><p>从学习路径与本周行为中汇总。</p></div><button type="button" @click="go('/profile')">查看完整画像<ArrowRight :size="14" /></button></header>
      <div class="progress-layout">
        <div class="path-progress">
          <span>学习路径进度</span>
          <strong>{{ progress }}%</strong>
          <div><i :style="{ transform: `scaleX(${progress / 100})` }" /></div>
          <p>{{ hasLearningPath ? `当前位于第 ${stage + 1} 阶段 · 已完成 ${completedKps} 个知识点` : "尚未生成学习路径 · 已完成 0 个知识点" }}</p>
        </div>
        <dl class="kpi-strip">
          <div><dt>正在学习</dt><dd>{{ activeLearningCount }}</dd></div>
          <div><dt>待学习</dt><dd>{{ Math.max(totalKps - completedKps - activeLearningCount, 0) }}</dd></div>
          <div><dt>本周完成任务</dt><dd>{{ weeklyCompleted }}<small>/ 10</small></dd></div>
          <div><dt>本周学习时长</dt><dd>{{ weekMinutes }}<small>分钟</small></dd></div>
          <div><dt>掌握度变化</dt><dd :class="{ positive: masteryChange > 0 }">{{ masteryChange > 0 ? "+" : "" }}{{ masteryChange }}<small>%</small></dd></div>
        </dl>
      </div>
    </section>

    <div class="two-column-sections">
      <section class="content-section review-section" aria-labelledby="review-title">
        <header class="section-heading"><div><h2 id="review-title">需要复习</h2><p>根据错题、掌握度和遗忘风险排序。</p></div><button type="button" @click="go('/mistakes')">查看错题本</button></header>
        <div class="review-list">
          <article v-for="(point, index) in riskPoints" :key="point.kp_id">
            <div><strong>{{ point.kp_name }}</strong><span>{{ index === 0 ? '建议今天复习' : index === 1 ? '建议 2 天内复习' : '建议本周复习' }}</span></div>
            <div class="mastery"><span>掌握度 {{ Math.round(point.mastery_pct) }}%</span><i><em :style="{ transform: `scaleX(${point.mastery_pct / 100})` }" /></i></div>
            <span>{{ Math.max(unresolvedMistakes - index, 1) }} 道错题</span>
            <button type="button" @click="go(`/graph?kp=${encodeURIComponent(point.kp_id)}`)">复习<ChevronRight :size="14" /></button>
          </article>
          <div v-if="!riskPoints.length" class="home-empty-state">
            <BookX :size="22" />
            <strong>暂无需要复习的知识点</strong>
            <p>完成首次诊断或练习后，真实薄弱点和复习安排会显示在这里。</p>
          </div>
        </div>
      </section>

      <section class="content-section feedback-section" aria-labelledby="feedback-title">
        <header class="section-heading"><div><h2 id="feedback-title">最近反馈</h2><p>学习结果与 Agent 调整记录。</p></div></header>
        <div class="timeline-list">
          <article v-for="item in recentFeedback" :key="`${item.time}-${item.title}`">
            <span :class="item.tone"><CheckCircle2 v-if="item.tone === 'success'" :size="15" /><TrendingUp v-else :size="15" /></span>
            <div><time>{{ item.time }}</time><strong>{{ item.title }}</strong><p>{{ item.result }}</p></div>
          </article>
          <div v-if="!recentFeedback.length" class="home-empty-state">
            <TrendingUp :size="22" />
            <strong>暂无学习反馈</strong>
            <p>这里不会放演示数据；你的第一次对话、练习或路径调整会形成真实记录。</p>
          </div>
        </div>
      </section>
    </div>

    <section class="content-section agent-section" aria-labelledby="agents-title">
      <header class="section-heading"><div><h2 id="agents-title">你的学习小队正在工作</h2><p>只展示 Agent 当前任务和完成状态。</p></div><button type="button" @click="go('/workflow')">查看协作详情</button></header>
      <div class="agent-status-list">
        <article v-for="agent in agents" :key="agent.name">
          <img :src="agent.img" :alt="agent.name" />
          <div><strong>{{ agent.name }}</strong><p>{{ agent.work }}</p></div>
          <span :class="agent.state">{{ agent.label }}</span>
        </article>
      </div>
    </section>

    <transition name="notice"><div v-if="notice" class="home-notice" role="status">{{ notice }}</div></transition>

    <OnboardingTour
      :storage-key="`tripleu.tour.student.v1::${userId || 'guest'}`"
      heading="三步开始今天的学习"
      :steps="tourSteps"
      @finish="finishTour"
    />
  </div>
</template>

<style scoped>
.student-home {
  --background: #fbfaf7;
  --surface: #fff;
  --surface-hover: #f8f6f2;
  --text: #1f1d1a;
  --heading: #171512;
  --secondary: #625f58;
  --tertiary: #89857d;
  --border: #e5e1d9;
  --divider: #e9e5de;
  --primary: #e85d16;
  --primary-hover: #d75011;
  --primary-soft: #fff3ea;
  --primary-border: #f1c9ae;
  width: min(100%, 1280px);
  margin: 0 auto;
  padding: 4px 0 56px;
  color: var(--text);
  font-family: Inter, "PingFang SC", "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
  animation: page-enter 260ms ease-out both;
}
@keyframes page-enter { from { opacity: 0; transform: translateY(6px); } }
button { font: inherit; }
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 36px; }
.page-header > div { max-width: 820px; }
.page-header span { color: var(--primary); font-size: 12px; font-weight: 700; letter-spacing: .03em; }
.course-eyebrow { display: block; color: var(--primary); font-size: 12px; font-weight: 750; }
.page-header h1 { margin: 10px 0 8px; color: var(--heading); font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif; font-size: clamp(34px, 3vw, 40px); font-weight: 560; line-height: 1.2; letter-spacing: -.02em; }
.page-header p { margin: 0; color: var(--secondary); font-size: 15px; line-height: 1.65; }
.page-header nav { display: flex; gap: 8px; padding-bottom: 3px; }
.page-header nav button, .section-heading > button { display: inline-flex; align-items: center; gap: 7px; min-height: 40px; padding: 0 12px; border: 1px solid var(--border); border-radius: 8px; background: #fff; color: var(--secondary); font-size: 12px; font-weight: 650; cursor: pointer; transition: transform 180ms cubic-bezier(.16,1,.3,1), border-color 170ms ease-out, background-position 200ms ease-out, color 170ms ease-out; background-image: linear-gradient(90deg, var(--primary-soft) 0 50%, #fff 50% 100%); background-size: 205% 100%; background-position: 100% 0; }
.page-header nav button:hover, .section-heading > button:hover { border-color: var(--primary-border); background-position: 0 0; color: var(--primary-hover); transform: translateY(-1px); }
.metadata-bar { display: grid; grid-template-columns: repeat(5, auto); justify-content: start; gap: 0; min-height: 52px; margin-top: 22px; border-top: 1px solid var(--divider); border-bottom: 1px solid var(--divider); }
.metadata-bar div { display: flex; align-items: center; gap: 9px; padding: 0 26px; border-left: 1px solid var(--divider); }
.metadata-bar div:first-child { padding-left: 0; border-left: 0; }
.metadata-bar span { color: var(--tertiary); font-size: 12px; }
.metadata-bar strong { color: var(--text); font-size: 13px; font-weight: 650; font-variant-numeric: tabular-nums; }
.focus-panel { display: grid; grid-template-columns: minmax(0,1fr) 320px; gap: 34px; margin-top: 34px; padding: 31px 38px; border: 1px solid var(--primary-border); border-radius: 14px; background: var(--primary-soft); }
.focus-copy > span { display: inline-flex; align-items: center; gap: 7px; color: var(--primary); font-size: 12px; font-weight: 750; }
.focus-copy h2 { margin: 12px 0 10px; color: var(--heading); font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif; font-size: 27px; font-weight: 600; }
.focus-copy p { margin: 3px 0; color: var(--secondary); font-size: 14px; line-height: 1.65; }
.focus-actions { display: flex; gap: 9px; margin-top: 20px; }
.focus-actions button { display: inline-flex; align-items: center; justify-content: center; gap: 7px; min-height: 42px; padding: 0 16px; border: 1px solid var(--primary-border); border-radius: 8px; background: transparent; color: var(--secondary); font-size: 13px; font-weight: 700; cursor: pointer; }
.focus-actions .primary { border-color: var(--primary); background: var(--primary); color: #fff; }
.focus-actions button:hover { transform: translateY(-1px); }
.focus-actions .primary:hover { background: var(--primary-hover); }
.focus-kpis { display: grid; grid-template-columns: 1fr; margin: 0; padding-left: 32px; border-left: 1px solid #efd9c9; }
.focus-kpis div { display: flex; align-items: baseline; justify-content: space-between; padding: 7px 0; }
.focus-kpis dt { color: var(--tertiary); font-size: 12px; }
.focus-kpis dd { margin: 0; color: var(--heading); font-size: 30px; font-weight: 750; font-variant-numeric: tabular-nums; }
.focus-kpis small { margin-left: 4px; color: var(--secondary); font-size: 11px; font-weight: 500; }
.content-section, .ai-panel { margin-top: 44px; }
.section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 15px; }
.section-heading h2 { margin: 0; color: var(--heading); font-size: 19px; font-weight: 700; }
.section-heading p { margin: 5px 0 0; color: var(--tertiary); font-size: 12px; line-height: 1.55; }
.section-heading > span { display: inline-flex; align-items: center; gap: 6px; color: var(--tertiary); font-size: 12px; }
.section-heading > button { min-height: 34px; background: transparent; border-color: transparent; }
.task-list { border-top: 1px solid var(--divider); }
.task-list article { display: grid; grid-template-columns: 44px 78px minmax(0,1fr) 76px 110px; align-items: center; gap: 14px; min-height: 79px; padding: 0 12px; border-bottom: 1px solid var(--divider); transition: background-color 170ms ease-out, transform 180ms cubic-bezier(.16,1,.3,1); }
.task-list article:hover { background: var(--surface-hover); transform: translateX(2px); }
.task-list article.urgent { background: linear-gradient(90deg, rgba(255,246,228,.72), transparent 48%); }
.task-index { color: #b8b2a8; font-size: 13px; font-weight: 750; }
.task-kind { width: max-content; padding: 4px 7px; border-radius: 5px; background: #f2efe9; color: var(--secondary); font-size: 11px; font-weight: 650; }
.urgent .task-kind { background: #fff0d3; color: #a46916; }
.task-list h3 { margin: 0; color: var(--text); font-size: 15px; }
.task-list p { margin: 4px 0 0; color: var(--tertiary); font-size: 12px; }
.task-time { color: var(--tertiary); font-size: 12px; }
.task-list article > button { display: inline-flex; align-items: center; justify-content: center; gap: 3px; min-height: 36px; padding: 0 9px; border: 1px solid var(--border); border-radius: 7px; background: #fff; color: var(--secondary); font-size: 12px; font-weight: 650; cursor: pointer; }
.task-list article > button:hover { border-color: var(--primary-border); color: var(--primary-hover); }
.ai-panel { display: grid; grid-template-columns: 48px minmax(0,1fr); gap: 16px; padding: 24px 28px; border: 1px solid #e5e1f4; border-radius: 12px; background: #faf9ff; }
.ai-icon { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 10px; background: #eeebff; color: #6557d9; }
.ai-copy > span { color: #6557d9; font-size: 12px; font-weight: 750; }
.ai-copy h2 { margin: 7px 0 6px; color: var(--heading); font-size: 18px; }
.ai-copy p { max-width: 850px; margin: 0; color: var(--secondary); font-size: 13px; line-height: 1.7; }
.ai-copy > div { display: flex; gap: 7px; margin-top: 14px; }
.ai-copy button { min-height: 35px; padding: 0 11px; border: 1px solid #d9d3f1; border-radius: 7px; background: #fff; color: #6557d9; font-size: 12px; font-weight: 650; cursor: pointer; }
.ai-copy button:hover { background: #eeebff; transform: translateY(-1px); }
.ai-copy small { display: block; margin-top: 12px; color: var(--tertiary); font-size: 11px; }
.progress-layout { display: grid; grid-template-columns: 350px minmax(0,1fr); min-height: 132px; border-top: 1px solid var(--divider); border-bottom: 1px solid var(--divider); }
.path-progress { padding: 20px 28px 18px 0; }
.path-progress > span { color: var(--tertiary); font-size: 12px; }
.path-progress > strong { display: block; margin-top: 4px; color: var(--heading); font-size: 34px; font-variant-numeric: tabular-nums; }
.path-progress > div { height: 7px; margin: 10px 0; overflow: hidden; border-radius: 999px; background: #eeeae3; }
.path-progress i { display: block; width: 100%; height: 100%; border-radius: inherit; background: #e88d4f; transform-origin: left; transition: transform 460ms cubic-bezier(.16,1,.3,1); }
.path-progress p { margin: 0; color: var(--tertiary); font-size: 11px; }
.kpi-strip { display: grid; grid-template-columns: repeat(5,1fr); margin: 0; border-left: 1px solid var(--divider); }
.kpi-strip div { display: flex; flex-direction: column; justify-content: center; padding: 16px 18px; border-left: 1px solid var(--divider); }
.kpi-strip div:first-child { border-left: 0; }
.kpi-strip dt { color: var(--tertiary); font-size: 11px; }
.kpi-strip dd { margin: 8px 0 0; color: var(--heading); font-size: 27px; font-weight: 720; font-variant-numeric: tabular-nums; }
.kpi-strip small { margin-left: 3px; color: var(--tertiary); font-size: 10px; font-weight: 500; }
.kpi-strip .positive { color: #247553; }
.two-column-sections { display: grid; grid-template-columns: minmax(0,1.08fr) minmax(0,.92fr); gap: 46px; }
.review-list, .timeline-list { border-top: 1px solid var(--divider); }
.review-list article { display: grid; grid-template-columns: minmax(160px,1fr) 150px 72px 55px; align-items: center; gap: 14px; min-height: 70px; padding: 0 8px; border-bottom: 1px solid var(--divider); }
.review-list article:hover { background: var(--surface-hover); }
.review-list article > div:first-child { display: flex; flex-direction: column; gap: 4px; }
.review-list strong { font-size: 13px; }
.review-list article > div:first-child span, .review-list article > span { color: var(--tertiary); font-size: 10.5px; }
.mastery { display: flex; flex-direction: column; gap: 6px; }
.mastery > span { color: var(--secondary); font-size: 11px; }
.mastery > i { display: block; height: 5px; overflow: hidden; border-radius: 999px; background: #eeeae3; }
.mastery em { display: block; width: 100%; height: 100%; border-radius: inherit; background: #c98680; transform-origin: left; }
.review-list button { display: inline-flex; align-items: center; border: 0; background: transparent; color: var(--primary-hover); font-size: 11px; cursor: pointer; }
.timeline-list article { position: relative; display: grid; grid-template-columns: 30px minmax(0,1fr); gap: 9px; min-height: 70px; padding: 12px 6px; border-bottom: 1px solid var(--divider); }
.timeline-list article > span { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: #eef4fa; color: #3e6d9c; }
.timeline-list article > span.success { background: #eef8f2; color: #247553; }
.timeline-list article > span.warning { background: #fff6e4; color: #a46916; }
.timeline-list div { display: flex; flex-direction: column; gap: 3px; }
.timeline-list time { color: var(--tertiary); font-size: 10px; }
.timeline-list strong { font-size: 12.5px; }
.timeline-list p { margin: 0; color: var(--tertiary); font-size: 11px; }
.home-empty-state {
  display: grid;
  justify-items: start;
  gap: 6px;
  min-height: 154px;
  padding: 28px 10px;
  color: var(--tertiary);
}
.home-empty-state strong { color: var(--secondary); font-size: 13px; }
.home-empty-state p { max-width: 46ch; margin: 0; font-size: 11.5px; line-height: 1.7; }
.agent-status-list { display: grid; grid-template-columns: repeat(3,1fr); overflow: hidden; border: 1px solid var(--border); border-radius: 12px; background: #fff; }
.agent-status-list article { display: grid; grid-template-columns: 40px minmax(0,1fr) auto; align-items: center; gap: 10px; min-height: 72px; padding: 10px 14px; border-left: 1px solid var(--divider); border-top: 1px solid var(--divider); }
.agent-status-list article:nth-child(-n+3) { border-top: 0; }
.agent-status-list article:nth-child(3n+1) { border-left: 0; }
.agent-status-list img { width: 38px; height: 38px; border-radius: 50%; object-fit: cover; }
.agent-status-list div { min-width: 0; }
.agent-status-list strong { font-size: 12px; }
.agent-status-list p { overflow: hidden; margin: 4px 0 0; color: var(--tertiary); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.agent-status-list article > span { padding: 3px 6px; border-radius: 999px; background: #eef8f2; color: #247553; font-size: 9px; }
.agent-status-list span.working { background: #faf9ff; color: #6557d9; }
.agent-status-list span.attention { background: #fff6e4; color: #a46916; }
.agent-status-list span.idle { background: #f2f0ec; color: #777168; }
/* ============ 学习动线大卡片 v2（2026-07-17 叙事优化）============
   每张卡三层信息：阶段叙事（宣传语）→ 实时学情数据 → 功能入口聚合 + 主 CTA */
.journey-map { display: flex; flex-direction: column; gap: 16px; }
.journey-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px; }
.journey-eyebrow { display: inline-block; margin-bottom: 8px; padding: 4px 12px; border-radius: 999px; background: var(--primary-soft); color: var(--primary); font-size: 12px; font-weight: 800; letter-spacing: .05em; }
.journey-head h2 { margin: 0; color: var(--heading); font-size: 23px; letter-spacing: -.01em; }
.journey-head p { margin: 7px 0 0; color: var(--secondary); font-size: 13.5px; }
.journey-replay { flex-shrink: 0; padding: 9px 16px; border: 1px solid var(--border); border-radius: 11px; background: #fff; color: var(--secondary); font-size: 13px; font-weight: 600; cursor: pointer; transition: border-color 160ms ease-out, color 160ms ease-out; }
.journey-replay:hover { border-color: var(--primary); color: var(--primary); }

/* 平台价值主张行：宣传 + 解释「这是什么平台」 */
.journey-props { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; }
.journey-props > article { display: flex; flex-direction: column; gap: 4px; padding: 12px 15px; border: 1px solid var(--border); border-radius: 12px; background: linear-gradient(155deg, #fffaf6, #fff); }
.journey-props b { color: var(--primary); font-size: 13.5px; }
.journey-props span { color: var(--secondary); font-size: 12px; line-height: 1.6; }
@media (max-width: 1100px) { .journey-props { grid-template-columns: repeat(2,1fr); } }
@media (max-width: 760px) { .journey-props { grid-template-columns: 1fr; } }

.journey-cards { display: grid; grid-template-columns: 1fr 22px 1fr 22px 1fr; align-items: stretch; gap: 0; }
.journey-connector { display: grid; place-items: center; color: #d8d1c5; }

.journey-cards > article { position: relative; display: flex; flex-direction: column; gap: 9px; overflow: hidden; padding: 18px 18px 16px; border: 1.5px solid var(--border); border-radius: 15px; background: #fff; transition: transform 200ms cubic-bezier(.16,1,.3,1), border-color 180ms ease-out, box-shadow 200ms ease-out; }
.journey-cards > article:hover { transform: translateY(-3px); border-color: #dcd5ca; box-shadow: 0 14px 34px rgba(35,31,25,.08); }
.journey-cards > article.active { border-color: var(--primary); background: linear-gradient(155deg, #fff6ef 0%, #fff 46%); box-shadow: 0 10px 30px rgba(233,85,20,.09); }

.jc-watermark { position: absolute; top: -14px; right: 6px; color: rgba(35,31,25,.05); font-size: 78px; font-weight: 800; letter-spacing: -.04em; pointer-events: none; }
.journey-cards > article.active .jc-watermark { color: rgba(233,85,20,.08); }

.jc-top { display: flex; align-items: center; gap: 10px; }
.jc-icon { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 13px; background: var(--primary-soft); color: var(--primary); }
.jc-stage { color: var(--primary); font-size: 12.5px; font-weight: 800; letter-spacing: .06em; }
.journey-cards h3 { margin: 0; color: var(--heading); font-size: 19px; }
.jc-promo { margin: 0; color: var(--secondary); font-size: 13px; line-height: 1.7; min-height: 44px; }

.jc-stats { display: flex; gap: 10px; }
.jc-stats > div { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 10px 13px; border-radius: 11px; background: var(--surface-hover); }
.jc-stats b { color: var(--heading); font-size: 17px; }
.jc-stats small { color: var(--tertiary); font-size: 11.5px; }
.journey-cards > article.active .jc-stats > div { background: #fff0e5; }
.journey-cards > article.active .jc-stats b { color: var(--primary); }

.jc-links { display: flex; flex-direction: column; gap: 5px; }
.jc-links button { display: grid; grid-template-columns: auto minmax(0,1fr) 15px; align-items: center; gap: 10px; padding: 9px 11px; border: 1px solid transparent; border-radius: 10px; background: transparent; text-align: left; cursor: pointer; transition: background-color 150ms ease-out, border-color 150ms ease-out, transform 150ms ease-out; }
.jc-links button:hover { background: var(--primary-soft); border-color: #f4d8c4; transform: translateX(2px); }
.jc-link-label { color: var(--text); font-size: 14px; font-weight: 700; white-space: nowrap; }
.jc-link-hint { overflow: hidden; color: var(--tertiary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.jc-links button:hover .jc-link-label { color: var(--primary); }
.jc-links button > svg { color: #c9c2b6; }

.jc-cta { display: inline-flex; align-items: center; justify-content: center; gap: 8px; margin-top: auto; padding: 12px 16px; border: 1px solid var(--border); border-radius: 12px; background: #fff; color: var(--text); font-size: 14.5px; font-weight: 700; cursor: pointer; transition: transform 160ms ease-out, box-shadow 160ms ease-out, background-color 160ms ease-out, color 160ms ease-out, border-color 160ms ease-out; }
.jc-cta:hover { transform: translateY(-1px); border-color: var(--primary); color: var(--primary); }
.journey-cards > article.active .jc-cta { border-color: transparent; background: var(--primary); color: #fff; box-shadow: 0 6px 18px rgba(233,85,20,.28); }
.journey-cards > article.active .jc-cta:hover { transform: translateY(-1px); box-shadow: 0 9px 22px rgba(233,85,20,.34); }
.home-notice { position: fixed; bottom: 24px; left: 50%; z-index: 180; padding: 9px 15px; border-radius: 8px; background: #1f1d1a; color: #fff; font-size: 12px; transform: translateX(-50%); }
:is(button,a):focus-visible { outline: 3px solid rgba(232,93,22,.24); outline-offset: 2px; }
@media (max-width: 1100px) {
  .page-header { align-items: flex-start; flex-direction: column; gap: 18px; }
  .metadata-bar { grid-template-columns: repeat(3,1fr); }
  .metadata-bar div { min-height: 45px; padding: 0 14px; }
  .focus-panel { grid-template-columns: 1fr 260px; }
  .progress-layout, .two-column-sections { grid-template-columns: 1fr; }
  .path-progress { padding-right: 0; }
  .kpi-strip { border-top: 1px solid var(--divider); border-left: 0; }
  .agent-status-list { grid-template-columns: repeat(2,1fr); }
  .journey-cards { grid-template-columns: 1fr; gap: 12px; }
  .journey-connector { display: none; }
  .jc-promo { min-height: 0; }
  .agent-status-list article:nth-child(3) { border-top: 1px solid var(--divider); }
  .agent-status-list article:nth-child(3n+1) { border-left: 1px solid var(--divider); }
  .agent-status-list article:nth-child(2n+1) { border-left: 0; }
}
@media (max-width: 760px) {
  .student-home { padding-bottom: 40px; }
  .page-header h1 { font-size: 30px; }
  .page-header nav { flex-wrap: wrap; }
  .metadata-bar { grid-template-columns: 1fr 1fr; }
  .metadata-bar div { align-items: flex-start; flex-direction: column; justify-content: center; gap: 2px; border-bottom: 1px solid var(--divider); }
  .focus-panel { grid-template-columns: 1fr; padding: 24px 20px; }
  .focus-kpis { grid-template-columns: repeat(3,1fr); padding: 15px 0 0; border-top: 1px solid #efd9c9; border-left: 0; }
  .focus-kpis div { align-items: flex-start; flex-direction: column; }
  .focus-kpis dd { font-size: 24px; }
  .task-list article { grid-template-columns: 34px minmax(0,1fr) auto; gap: 9px; padding: 12px 4px; }
  .task-kind { grid-column: 2; grid-row: 1; }
  .task-list article > div { grid-column: 2 / -1; }
  .task-time { grid-column: 2; }
  .task-list article > button { grid-column: 3; grid-row: 3; }
  .ai-panel { grid-template-columns: 1fr; padding: 20px; }
  .kpi-strip { grid-template-columns: repeat(2,1fr); }
  .kpi-strip div { border-top: 1px solid var(--divider); }
  .review-list article { grid-template-columns: minmax(0,1fr) auto; padding: 10px 6px; }
  .mastery { grid-column: 1; }
  .review-list article > span { grid-column: 1; }
  .review-list button { grid-column: 2; grid-row: 1 / 4; }
  .agent-status-list { grid-template-columns: 1fr; }
  .journey-head { flex-direction: column; align-items: flex-start; }
  .agent-status-list article { border-left: 0 !important; border-top: 1px solid var(--divider) !important; }
  .agent-status-list article:first-child { border-top: 0 !important; }
}
@media (prefers-reduced-motion: reduce) {
  .student-home, .student-home *, .student-home *::before, .student-home *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; scroll-behavior: auto !important; }
}
</style>
