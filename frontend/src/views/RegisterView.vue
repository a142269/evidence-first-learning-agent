<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-vue-next";

import { registerAccount } from "@/api/auth";
import { ApiError } from "@/api/http";
import plannerImg from "@/assets/login-avatars/planner.png";
import { useSession } from "@/composables/useSession";
import { setAuthSession } from "@/utils/auth";

const router = useRouter();
const { refreshUser, resetChatSession } = useSession();

const step = ref(0);
const loading = ref(false);
const completed = ref(false);
const errorMessage = ref("");
const profileCompleteness = ref(0);

const account = reactive({
  displayName: "",
  account: "",
  password: "",
  confirmPassword: "",
});

const answers = reactive({
  academic: { major: "", grade: "", current_course: "" },
  goal: {
    target: "",
    interests: [] as string[],
    timeline: "",
    motivation: "",
    success_evidence: "",
  },
  foundation: {
    level: "",
    known_topics_text: "",
    applied_experience: "",
  },
  errors: {
    difficulty_stages: [] as string[],
    error_patterns: [] as string[],
    stuck_response: "",
  },
  cognition: {
    styles: [] as string[],
    explanation_depth: "",
    information_density: "",
  },
  resources: {
    formats: [] as string[],
    practice_mode: "",
    pace: "",
    challenge_level: "",
  },
  habits: {
    weekly_hours: 6,
    session_length: "",
    best_time: "",
    schedule: "",
    interruption_risks: [] as string[],
  },
  autonomy: {
    confidence: "",
    help_style: "",
    reflection_habit: "",
    collaboration: "",
  },
});

const totalSteps = 10;
const progress = computed(() => Math.round(((step.value + 1) / totalSteps) * 100));

const stepMeta = [
  { short: "账号", title: "先认识一下你", eyebrow: "创建学习身份" },
  { short: "背景", title: "你目前在学什么？", eyebrow: "第 1 轮 · 学业背景" },
  { short: "目标", title: "这段学习想带你去哪里？", eyebrow: "第 2 轮 · 目标与动机" },
  { short: "基础", title: "你觉得自己的起点在哪里？", eyebrow: "第 3 轮 · 基础与经历" },
  { short: "难点", title: "学习最容易在哪一步卡住？", eyebrow: "第 4 轮 · 易错与应对" },
  { short: "理解", title: "怎样讲解最容易让你“懂了”？", eyebrow: "第 5 轮 · 认知风格" },
  { short: "资源", title: "你更愿意用什么材料学习？", eyebrow: "第 6 轮 · 资源与反馈" },
  { short: "节奏", title: "怎样安排才真正做得到？", eyebrow: "第 7 轮 · 时间与习惯" },
  { short: "自主", title: "偏航时，你希望怎样回到正轨？", eyebrow: "第 8 轮 · 自主与协作" },
  { short: "完成", title: "你的初始学习画像已准备好", eyebrow: "画像预览" },
];

const currentMeta = computed(() => stepMeta[step.value]);
const learningSubject = computed(() =>
  answers.academic.current_course
  || answers.goal.interests[0]
  || answers.academic.major
  || "当前学习主题"
);
const goalTarget = computed(() => answers.goal.target || "你想达成的目标");
const difficultyFocus = computed(() =>
  answers.errors.difficulty_stages[0] || "遇到难点"
);
const preferredStyle = computed(() =>
  answers.cognition.styles.join("和") || "适合你的理解方式"
);
const timelineContext = computed(() => answers.goal.timeline || "你期望的周期");

const currentTitle = computed(() => {
  if (step.value === 2) return `学好「${learningSubject.value}」后，你想做到什么？`;
  if (step.value === 3) return `为了「${goalTarget.value}」，你的起点在哪里？`;
  if (step.value === 4) return `学习「${learningSubject.value}」时，哪一步最容易卡住？`;
  if (step.value === 5) return `当「${difficultyFocus.value}」发生时，怎样讲你更容易懂？`;
  if (step.value === 6) return `配合「${preferredStyle.value}」，什么资源最顺手？`;
  if (step.value === 7) return `为了在「${timelineContext.value}」见到成果，怎样安排更现实？`;
  if (step.value === 8) return `如果「${goalTarget.value}」的计划偏航，你通常怎么调整？`;
  return currentMeta.value.title;
});

const currentPrompt = computed(() => {
  const prompts = [
    "先创建你的学习身份。接下来我会沿着同一条线索，用 8 个简短问题逐步了解你。",
    "专业、阶段和当前课程是画像的上下文，只用于匹配案例与先修内容，不需要填写学校等敏感信息。",
    `你刚刚提到「${learningSubject.value}」。接下来把目标、学习动力和“怎样算学成”说清楚，路径才不会只停留在泛泛推荐。`,
    `目标是「${goalTarget.value}」。我会结合你的已有知识和实践经历，从合适的难度开始，而不是默认所有人都从零起步。`,
    `知道起点后，还要找到真正影响进步的环节。这里记录的是自述线索，后续会由练习错因和行为证据校准。`,
    `你提到容易在「${difficultyFocus.value}」卡住。现在选择更适合你的理解入口和信息密度，我会据此调整讲解方式。`,
    `理解方式确定后，再选择资源、反馈和挑战强度，让首批推荐真正服务于「${goalTarget.value}」。`,
    `你希望在「${timelineContext.value}」看到成果。请按真实可用时间和常见干扰来安排，现实的小计划比理想的大计划更有效。`,
    "最后补充遇到困难时的求助、复盘与协作方式。这能帮助系统决定何时提示、何时追问、何时让你独立探索。",
    "下面是根据前面回答形成的初步理解。确认后，系统会保存为第 1 版画像，并在学习中持续更新。",
  ];
  return prompts[step.value];
});

function toggle(list: string[], value: string, max = 99) {
  const index = list.indexOf(value);
  if (index >= 0) list.splice(index, 1);
  else if (list.length < max) list.push(value);
}

function validateAccount(): boolean {
  if (!account.displayName.trim() || !account.account.trim() || !account.password) {
    errorMessage.value = "请先填写称呼、账号和密码";
    return false;
  }
  if (account.account.trim().length < 3 || account.account.trim().length > 32) {
    errorMessage.value = "账号长度需要在 3–32 个字符之间";
    return false;
  }
  if (account.password.length < 6) {
    errorMessage.value = "密码至少需要 6 位";
    return false;
  }
  if (account.password !== account.confirmPassword) {
    errorMessage.value = "两次输入的密码不一致";
    return false;
  }
  return true;
}

function next() {
  errorMessage.value = "";
  if (step.value === 0 && !validateAccount()) return;
  if (step.value < 9) step.value += 1;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function previous() {
  errorMessage.value = "";
  if (step.value > 0) step.value -= 1;
}

function splitTopics(value: string): string[] {
  return value
    .split(/[，,、；;\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 12);
}

const profileAnswers = computed(() => ({
  academic: { ...answers.academic },
  goal: { ...answers.goal },
  foundation: {
    level: answers.foundation.level,
    known_topics: splitTopics(answers.foundation.known_topics_text),
    applied_experience: answers.foundation.applied_experience,
  },
  errors: {
    difficulty_stages: [...answers.errors.difficulty_stages],
    error_patterns: [...answers.errors.error_patterns],
    stuck_response: answers.errors.stuck_response,
  },
  cognition: { ...answers.cognition, styles: [...answers.cognition.styles] },
  resources: { ...answers.resources, formats: [...answers.resources.formats] },
  habits: { ...answers.habits, interruption_risks: [...answers.habits.interruption_risks] },
  autonomy: { ...answers.autonomy },
}));

const portraitHighlights = computed(() => [
  {
    label: "当前起点",
    value: answers.foundation.level || "等待后续诊断",
    detail: answers.academic.current_course || answers.academic.major || "尚未填写课程",
  },
  {
    label: "学习目标",
    value: answers.goal.target || "探索适合自己的方向",
    detail: answers.goal.timeline ? `期望周期：${answers.goal.timeline}` : "将随学习过程持续明确",
  },
  {
    label: "学习动力",
    value: answers.goal.motivation || "在学习中继续发现",
    detail: answers.goal.success_evidence || "通过阶段成果持续确认目标",
  },
  {
    label: "理解方式",
    value: answers.cognition.styles.join(" + ") || "多种方式综合尝试",
    detail: answers.cognition.explanation_depth || "根据反馈动态调整讲解深度",
  },
  {
    label: "资源组合",
    value: answers.resources.formats.join(" + ") || "图文、练习与实践混合",
    detail: answers.resources.pace || "自适应节奏",
  },
  {
    label: "学习节奏",
    value: `每周约 ${answers.habits.weekly_hours || 0} 小时`,
    detail: [answers.habits.best_time, answers.habits.session_length].filter(Boolean).join(" · ") || "待学习行为校准",
  },
  {
    label: "优先关注",
    value: answers.errors.difficulty_stages.join("、") || "通过首轮练习发现薄弱点",
    detail: answers.errors.error_patterns.join("、") || "这是自述型线索，不会被当作永久结论",
  },
  {
    label: "自主与协作",
    value: answers.autonomy.confidence || "在实践中继续观察",
    detail: [answers.autonomy.help_style, answers.autonomy.collaboration].filter(Boolean).join(" · ") || "按需要提供提示与协作",
  },
]);

async function submitRegistration() {
  errorMessage.value = "";
  if (loading.value || !validateAccount()) return;
  loading.value = true;
  try {
    const payload = await registerAccount({
      account: account.account.trim(),
      password: account.password,
      display_name: account.displayName.trim(),
      role: "student",
      profile_answers: profileAnswers.value,
    });
    setAuthSession({
      accessToken: payload.access_token,
      tokenType: payload.token_type,
      expiresAt: payload.expires_at,
      account: payload.user.account,
      displayName: payload.user.display_name,
      role: payload.user.role,
      loginAt: new Date().toISOString(),
      remember: true,
    });
    refreshUser();
    resetChatSession();
    profileCompleteness.value = payload.profile_completeness || 0;
    completed.value = true;
  } catch (error) {
    if (error instanceof ApiError) {
      const messages: Record<string, string> = {
        account_exists: "这个账号已经存在，请换一个试试",
        account_length_invalid: "账号长度需要在 3–32 个字符之间",
        password_too_short: "密码至少需要 6 位",
        profile_initialization_failed: "账号暂未创建成功，画像保存遇到问题，请稍后重试",
      };
      errorMessage.value = messages[error.detail] || error.detail || "注册失败，请稍后重试";
    } else {
      errorMessage.value = "暂时无法连接服务，请确认后端已启动";
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <main class="onboarding-page">
    <div class="paper-noise" aria-hidden="true"></div>
    <div class="glow glow-a" aria-hidden="true"></div>
    <div class="glow glow-b" aria-hidden="true"></div>

    <header class="topbar">
      <button class="back-login" type="button" @click="router.push('/login')">
        <ArrowLeft :size="18" aria-hidden="true" /> 返回登录
      </button>
      <a class="brand" href="/login" aria-label="triple U 登录页">
        <img src="/logo.png" alt="" />
        <span>triple U</span>
      </a>
      <span class="privacy-note"><ShieldCheck :size="17" /> 仅用于个性化学习</span>
    </header>

    <section v-if="!completed" class="onboarding-shell">
      <aside class="journey-card" aria-label="注册画像进度">
        <div class="journey-heading">
          <span class="mini-label">INITIAL PORTRAIT</span>
          <h1>认识你，<br />从一次轻松对话开始</h1>
          <p>大约 4 分钟。每一轮都会承接前面的回答，画像也会在今后的学习中持续更新。</p>
        </div>

        <div
          class="progress-track"
          role="progressbar"
          aria-label="画像构建进度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="progress"
        >
          <span :style="{ width: `${progress}%` }"></span>
        </div>
        <div class="progress-caption"><b>{{ progress }}%</b><span>已完成</span></div>

        <ol class="step-list">
          <li
            v-for="(item, index) in stepMeta.slice(0, 9)"
            :key="item.short"
            :class="{ active: index === step, done: index < step }"
          >
            <span class="step-dot"><Check v-if="index < step" :size="13" /><template v-else>{{ index + 1 }}</template></span>
            <span>{{ item.short }}</span>
          </li>
        </ol>

        <div class="trust-card">
          <LockKeyhole :size="18" aria-hidden="true" />
          <p><b>你始终拥有控制权</b><span>可跳过问题，也可在画像页修改或重置。</span></p>
        </div>
      </aside>

      <section class="conversation-card" aria-live="polite">
        <div class="conversation-head">
          <div class="agent-avatar"><img :src="plannerImg" alt="小狐规划画像助手" /></div>
          <div><b>小狐规划</b><span>初始画像助手 · 在线</span></div>
          <Sparkles class="spark-icon" :size="22" aria-hidden="true" />
        </div>

        <div class="conversation-body">
          <div class="agent-message">
            <p class="eyebrow">{{ currentMeta.eyebrow }}</p>
            <h2>{{ currentTitle }}</h2>
            <p>{{ currentPrompt }}</p>
          </div>

          <div class="answer-card">
            <form v-if="step === 0" class="account-grid" @submit.prevent="next">
              <label class="field-label full">
                <span>希望我们怎么称呼你？</span>
                <div class="text-field"><UserRound :size="18" /><input v-model="account.displayName" autocomplete="name" placeholder="例如：小林" /></div>
              </label>
              <label class="field-label full">
                <span>登录账号</span>
                <div class="text-field"><UserRound :size="18" /><input v-model="account.account" autocomplete="username" placeholder="3–32 个字符" /></div>
              </label>
              <label class="field-label">
                <span>设置密码</span>
                <div class="text-field"><LockKeyhole :size="18" /><input v-model="account.password" type="password" autocomplete="new-password" placeholder="至少 6 位" /></div>
              </label>
              <label class="field-label">
                <span>确认密码</span>
                <div class="text-field"><LockKeyhole :size="18" /><input v-model="account.confirmPassword" type="password" autocomplete="new-password" placeholder="再次输入" /></div>
              </label>
            </form>

            <div v-else-if="step === 1" class="question-stack">
              <fieldset><legend>你的专业或方向</legend><div class="choice-grid compact">
                <button v-for="item in ['计算机科学与技术','人工智能','软件工程','电子信息','数学与统计','其他方向']" :key="item" type="button" :class="['choice', { selected: answers.academic.major === item }]" :aria-pressed="answers.academic.major === item" @click="answers.academic.major = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>目前所处阶段</legend><div class="choice-grid compact">
                <button v-for="item in ['大一','大二','大三','大四','研究生','其他']" :key="item" type="button" :class="['choice', { selected: answers.academic.grade === item }]" :aria-pressed="answers.academic.grade === item" @click="answers.academic.grade = item">{{ item }}</button>
              </div></fieldset>
              <label class="field-label"><span>正在学习的课程或主题（选填）</span><div class="text-field"><input v-model="answers.academic.current_course" placeholder="例如：机器学习、Python 程序设计" /></div></label>
            </div>

            <div v-else-if="step === 2" class="question-stack">
              <fieldset><legend>你当前最主要的学习目标</legend><div class="choice-grid">
                <button v-for="item in ['学好当前课程','考研或考试','参加学科竞赛','开展科研','求职与就业','完成实践项目']" :key="item" type="button" :class="['choice', { selected: answers.goal.target === item }]" :aria-pressed="answers.goal.target === item" @click="answers.goal.target = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>感兴趣的方向（可多选）</legend><div class="choice-grid compact">
                <button v-for="item in ['Python','机器学习','深度学习','自然语言处理','计算机视觉','智能硬件']" :key="item" type="button" :class="['choice', { selected: answers.goal.interests.includes(item) }]" :aria-pressed="answers.goal.interests.includes(item)" @click="toggle(answers.goal.interests, item, 4)">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>希望多久看到阶段性成果</legend><div class="choice-row">
                <button v-for="item in ['2 周','1 个月','3 个月','一学期','长期积累']" :key="item" type="button" :class="['choice', { selected: answers.goal.timeline === item }]" :aria-pressed="answers.goal.timeline === item" @click="answers.goal.timeline = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>现在投入学习，最主要的动力是什么？</legend><div class="choice-grid compact">
                <button v-for="item in ['真心感兴趣','课程或成绩要求','升学与考试','职业发展','完成作品','解决实际问题']" :key="item" type="button" :class="['choice', { selected: answers.goal.motivation === item }]" :aria-pressed="answers.goal.motivation === item" @click="answers.goal.motivation = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>出现什么结果，你会认为这一阶段“学成了”？</legend><div class="choice-grid">
                <button v-for="item in ['能独立讲清楚','考试或测验达标','能独立完成题目','做出可展示项目','能解决真实问题','形成作品或证书']" :key="item" type="button" :class="['choice', { selected: answers.goal.success_evidence === item }]" :aria-pressed="answers.goal.success_evidence === item" @click="answers.goal.success_evidence = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 3" class="question-stack">
              <fieldset><legend>对当前主题的熟悉程度</legend><div class="choice-grid">
                <button v-for="item in ['零基础','刚入门','有一些基础','能够独立应用','有项目经验']" :key="item" type="button" :class="['choice', { selected: answers.foundation.level === item }]" :aria-pressed="answers.foundation.level === item" @click="answers.foundation.level = item">{{ item }}</button>
              </div></fieldset>
              <label class="field-label"><span>已经接触过的知识点（选填，用逗号分隔）</span><div class="text-field"><input v-model="answers.foundation.known_topics_text" placeholder="例如：Python 基础、线性代数" /></div></label>
              <fieldset><legend>你对这些知识有过怎样的实际使用？</legend><div class="choice-grid">
                <button v-for="item in ['只听过或看过','跟着教程做过','独立完成过练习','在课程作业中用过','做过小型项目','能向别人讲解']" :key="item" type="button" :class="['choice', { selected: answers.foundation.applied_experience === item }]" :aria-pressed="answers.foundation.applied_experience === item" @click="answers.foundation.applied_experience = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 4" class="question-stack roomy">
              <fieldset><legend>最容易影响进度的环节（最多选 3 项）</legend><div class="choice-grid compact">
                <button v-for="item in ['听懂但不会做','概念容易混淆','数学或公式推导','题意转化困难','代码实现卡住','调试与排错','复习后又遗忘','暂时不清楚']" :key="item" type="button" :class="['choice', { selected: answers.errors.difficulty_stages.includes(item) }]" :aria-pressed="answers.errors.difficulty_stages.includes(item)" @click="toggle(answers.errors.difficulty_stages, item, 3)">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>回想过去，哪些情况会反复出现？（可多选）</legend><div class="choice-grid compact">
                <button v-for="item in ['忽略条件或边界','相近概念混淆','会套模板但不理解','缺少检查与验证','做题速度偏慢','遇难题容易拖延','复习没有形成体系','暂未发现规律']" :key="item" type="button" :class="['choice', { selected: answers.errors.error_patterns.includes(item) }]" :aria-pressed="answers.errors.error_patterns.includes(item)" @click="toggle(answers.errors.error_patterns, item, 3)">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>卡住超过 10 分钟时，你通常会……</legend><div class="choice-grid">
                <button v-for="item in ['自己搜索资料','换一种方法反复尝试','向老师或 AI 求助','和同学讨论','先跳过稍后再来','容易停下来不再继续']" :key="item" type="button" :class="['choice', { selected: answers.errors.stuck_response === item }]" :aria-pressed="answers.errors.stuck_response === item" @click="answers.errors.stuck_response = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 5" class="question-stack roomy">
              <fieldset><legend>哪些方式最能帮助你理解？（最多选 2 项）</legend><div class="choice-grid visual-choices">
                <button v-for="item in ['图示与知识脉络','一步一步推导','生活案例与类比','边做边学的实践']" :key="item" type="button" :class="['choice', { selected: answers.cognition.styles.includes(item) }]" :aria-pressed="answers.cognition.styles.includes(item)" @click="toggle(answers.cognition.styles, item, 2)"><CheckCircle2 :size="19" />{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>遇到新概念时，你希望先……</legend><div class="choice-grid">
                <button v-for="item in ['先看全局，再拆细节','先从例子入手','先理解原理与公式','先完成一个可运行结果']" :key="item" type="button" :class="['choice', { selected: answers.cognition.explanation_depth === item }]" :aria-pressed="answers.cognition.explanation_depth === item" @click="answers.cognition.explanation_depth = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>一段讲解的信息量，你更喜欢……</legend><div class="choice-row">
                <button v-for="item in ['先给结论，尽量简洁','重点清楚，适量细节','完整展开，解释来龙去脉']" :key="item" type="button" :class="['choice', { selected: answers.cognition.information_density === item }]" :aria-pressed="answers.cognition.information_density === item" @click="answers.cognition.information_density = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 6" class="question-stack">
              <fieldset><legend>偏好的学习资源（最多选 3 项）</legend><div class="choice-grid compact">
                <button v-for="item in ['短视频讲解','图文讲义','PPT 导图','题目练习','代码案例','完整项目']" :key="item" type="button" :class="['choice', { selected: answers.resources.formats.includes(item) }]" :aria-pressed="answers.resources.formats.includes(item)" @click="toggle(answers.resources.formats, item, 3)">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>练习反馈方式</legend><div class="choice-grid">
                <button v-for="item in ['立即告诉我答案','先给提示让我再试','展示相似例题','解释错因并安排复习']" :key="item" type="button" :class="['choice', { selected: answers.resources.practice_mode === item }]" :aria-pressed="answers.resources.practice_mode === item" @click="answers.resources.practice_mode = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>内容节奏</legend><div class="choice-row">
                <button v-for="item in ['慢一些，基础扎实','适中，讲练结合','快一些，多给挑战']" :key="item" type="button" :class="['choice', { selected: answers.resources.pace === item }]" :aria-pressed="answers.resources.pace === item" @click="answers.resources.pace = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>初始挑战强度</legend><div class="choice-row">
                <button v-for="item in ['从能完成的任务建立信心','保持一点难度，边学边试','直接给有挑战性的任务']" :key="item" type="button" :class="['choice', { selected: answers.resources.challenge_level === item }]" :aria-pressed="answers.resources.challenge_level === item" @click="answers.resources.challenge_level = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 7" class="question-stack">
              <label class="hours-control"><span><b>每周可投入时间</b><strong>{{ answers.habits.weekly_hours }} 小时</strong></span><input v-model.number="answers.habits.weekly_hours" type="range" min="1" max="30" step="1" aria-label="每周可投入学习小时数" /></label>
              <fieldset><legend>通常哪段时间状态更好？</legend><div class="choice-row">
                <button v-for="item in ['清晨','上午','下午','晚上','不固定']" :key="item" type="button" :class="['choice', { selected: answers.habits.best_time === item }]" :aria-pressed="answers.habits.best_time === item" @click="answers.habits.best_time = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>一次学习多久比较舒服？</legend><div class="choice-row">
                <button v-for="item in ['15–25 分钟','30–45 分钟','约 1 小时','1 小时以上']" :key="item" type="button" :class="['choice', { selected: answers.habits.session_length === item }]" :aria-pressed="answers.habits.session_length === item" @click="answers.habits.session_length = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>更可能坚持下来的安排方式</legend><div class="choice-grid">
                <button v-for="item in ['固定每天同一时间','每天灵活安排一小段','集中在周末学习','按课程任务推进','有截止日期才集中投入','目前还没有规律']" :key="item" type="button" :class="['choice', { selected: answers.habits.schedule === item }]" :aria-pressed="answers.habits.schedule === item" @click="answers.habits.schedule = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>最可能打断计划的因素（最多选 2 项）</legend><div class="choice-grid compact">
                <button v-for="item in ['其他课程或工作','手机与社交媒体','时间过于碎片化','难度高后动力下降','不知道下一步做什么','临时事务较多']" :key="item" type="button" :class="['choice', { selected: answers.habits.interruption_risks.includes(item) }]" :aria-pressed="answers.habits.interruption_risks.includes(item)" @click="toggle(answers.habits.interruption_risks, item, 2)">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else-if="step === 8" class="question-stack">
              <fieldset><legend>遇到难题时，更像现在的你的是……</legend><div class="choice-grid">
                <button v-for="item in ['经常需要帮助','有提示就能继续','通常能独立解决','喜欢主动探索']" :key="item" type="button" :class="['choice', { selected: answers.autonomy.confidence === item }]" :aria-pressed="answers.autonomy.confidence === item" @click="answers.autonomy.confidence = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>你希望系统怎样介入？</legend><div class="choice-grid">
                <button v-for="item in ['卡住时主动提醒我','等我提问再帮助','先用问题引导我思考','直接给关键提示','提供完整讲解后让我练习','只在偏离计划时提醒']" :key="item" type="button" :class="['choice', { selected: answers.autonomy.help_style === item }]" :aria-pressed="answers.autonomy.help_style === item" @click="answers.autonomy.help_style = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>完成一段学习后，你通常会……</legend><div class="choice-row">
                <button v-for="item in ['整理笔记或导图','回顾错题和原因','做小测检验掌握','直接进入下一内容','很少复盘']" :key="item" type="button" :class="['choice', { selected: answers.autonomy.reflection_habit === item }]" :aria-pressed="answers.autonomy.reflection_habit === item" @click="answers.autonomy.reflection_habit = item">{{ item }}</button>
              </div></fieldset>
              <fieldset><legend>更舒服的学习关系</legend><div class="choice-row">
                <button v-for="item in ['更喜欢独立学习','需要时找同伴讨论','喜欢结伴互相督促','愿意分享并讲给别人']" :key="item" type="button" :class="['choice', { selected: answers.autonomy.collaboration === item }]" :aria-pressed="answers.autonomy.collaboration === item" @click="answers.autonomy.collaboration = item">{{ item }}</button>
              </div></fieldset>
            </div>

            <div v-else class="portrait-preview">
              <div v-for="item in portraitHighlights" :key="item.label" class="portrait-item">
                <span>{{ item.label }}</span><b>{{ item.value }}</b><small>{{ item.detail }}</small>
              </div>
              <p class="calibration-note"><Sparkles :size="18" />这是一份自述型初始画像。系统会结合对话、练习正确率、错因与资源使用行为持续校准。</p>
            </div>

            <p v-if="errorMessage" class="error-banner" role="alert">{{ errorMessage }}</p>
          </div>
        </div>

        <footer class="conversation-footer">
          <button v-if="step > 0" class="text-button" type="button" @click="previous"><ArrowLeft :size="17" /> 上一步</button>
          <span v-else></span>
          <div class="footer-actions">
            <button v-if="step > 0 && step < 9" class="skip-button" type="button" @click="next">暂时跳过</button>
            <button v-if="step < 9" class="primary-button" type="button" @click="next">继续 <ArrowRight :size="18" /></button>
            <button v-else class="primary-button submit-button" type="button" :disabled="loading" @click="submitRegistration">
              <Sparkles :size="18" /> {{ loading ? "正在生成画像…" : "确认并创建画像" }}
            </button>
          </div>
        </footer>
      </section>
    </section>

    <section v-else class="success-card">
      <div class="success-mark"><Check :size="34" stroke-width="3" /></div>
      <p class="eyebrow">PORTRAIT READY</p>
      <h1>{{ account.displayName }}，你的第 1 版学习画像已建立</h1>
      <p>已覆盖 {{ Math.round(profileCompleteness / 12.5) }} / 8 个核心维度。小狐规划会据此调整首批学习路径与资源，后续画像将随学习证据持续更新。</p>
      <div class="success-highlights">
        <div v-for="item in portraitHighlights.slice(0, 3)" :key="item.label"><span>{{ item.label }}</span><b>{{ item.value }}</b></div>
      </div>
      <div class="success-actions">
        <button class="primary-button" type="button" @click="router.push('/profile')">查看完整画像 <ArrowRight :size="18" /></button>
        <button class="skip-button" type="button" @click="router.push('/home')">进入学习首页</button>
      </div>
    </section>
  </main>
</template>

<style scoped lang="scss">
.onboarding-page {
  --orange: #e95514;
  --orange-dark: #cc3f08;
  --ink: #182026;
  --muted: #647078;
  --line: rgba(96, 75, 54, 0.16);
  min-height: 100vh;
  position: relative;
  overflow-x: hidden;
  color: var(--ink);
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: linear-gradient(120deg, #fffdf8 0%, #fbf4e9 58%, #f4e6d2 100%);
}

* { box-sizing: border-box; }
button, input { font: inherit; }
button { cursor: pointer; }
.paper-noise { position: fixed; inset: 0; opacity: .2; pointer-events: none; background-image: radial-gradient(rgba(126, 92, 54, .18) .7px, transparent .7px); background-size: 21px 21px; }
.glow { position: fixed; border-radius: 50%; filter: blur(2px); pointer-events: none; }
.glow-a { width: 380px; height: 380px; left: -180px; top: 30%; background: rgba(234, 169, 97, .16); }
.glow-b { width: 440px; height: 440px; right: -220px; bottom: -140px; background: rgba(214, 177, 116, .2); }

.topbar { height: 76px; max-width: 1440px; margin: 0 auto; padding: 0 42px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; position: relative; z-index: 2; }
.brand { display: inline-flex; align-items: center; gap: 10px; color: var(--ink); text-decoration: none; font-size: 21px; font-weight: 800; letter-spacing: -.03em; }
.brand img { width: 30px; height: 30px; object-fit: contain; }
.back-login, .privacy-note { justify-self: start; display: inline-flex; align-items: center; gap: 8px; color: #4c565b; }
.back-login { border: 0; background: transparent; padding: 9px 0; font-weight: 650; }
.back-login:hover { color: var(--orange); }
.privacy-note { justify-self: end; font-size: 13px; }

.onboarding-shell { width: min(1320px, calc(100% - 48px)); min-height: calc(100vh - 108px); margin: 10px auto 22px; display: grid; grid-template-columns: 330px minmax(0, 1fr); border: 1px solid rgba(108, 85, 60, .14); border-radius: 28px; overflow: hidden; position: relative; z-index: 1; background: rgba(255,255,255,.68); box-shadow: 0 28px 80px rgba(103, 73, 40, .12); backdrop-filter: blur(18px); }
.journey-card { padding: 44px 36px 34px; background: linear-gradient(155deg, rgba(40,49,51,.98), rgba(28,35,37,.98)); color: white; display: flex; flex-direction: column; }
.mini-label, .eyebrow { color: #e99359; font-size: 11px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
.journey-heading h1 { margin: 14px 0 16px; font-family: "Songti SC", SimSun, serif; font-size: 30px; line-height: 1.28; letter-spacing: -.04em; }
.journey-heading p { margin: 0; color: rgba(255,255,255,.65); font-size: 13px; line-height: 1.8; }
.progress-track { height: 6px; margin-top: 36px; border-radius: 999px; overflow: hidden; background: rgba(255,255,255,.12); }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #e95514, #f6b56e); transition: width .3s ease; }
.progress-caption { display: flex; justify-content: space-between; align-items: baseline; margin-top: 10px; font-size: 12px; color: rgba(255,255,255,.52); }
.progress-caption b { color: white; font-size: 14px; }
.step-list { list-style: none; padding: 0; margin: 30px 0; display: grid; gap: 17px; }
.step-list li { display: flex; align-items: center; gap: 13px; color: rgba(255,255,255,.45); font-size: 13px; transition: color .2s ease; }
.step-list li.active { color: white; font-weight: 700; }
.step-list li.done { color: rgba(255,255,255,.7); }
.step-dot { width: 25px; height: 25px; flex: 0 0 auto; display: grid; place-items: center; border: 1px solid rgba(255,255,255,.22); border-radius: 50%; font-size: 11px; }
.active .step-dot { background: var(--orange); border-color: var(--orange); box-shadow: 0 0 0 5px rgba(233,85,20,.16); }
.done .step-dot { color: #263032; background: #efaa73; border-color: #efaa73; }
.trust-card { margin-top: auto; display: flex; align-items: flex-start; gap: 11px; padding: 15px; border: 1px solid rgba(255,255,255,.1); border-radius: 14px; background: rgba(255,255,255,.045); }
.trust-card svg { color: #efaa73; flex: 0 0 auto; }
.trust-card p { margin: 0; display: grid; gap: 4px; }
.trust-card b { font-size: 12px; }
.trust-card span { color: rgba(255,255,255,.54); font-size: 11px; line-height: 1.55; }

.conversation-card { display: grid; grid-template-rows: auto 1fr auto; min-height: 700px; }
.conversation-head { min-height: 83px; padding: 15px 34px; display: flex; align-items: center; gap: 12px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.58); }
.agent-avatar { width: 48px; height: 48px; border-radius: 15px; overflow: hidden; background: #f7d4b3; box-shadow: inset 0 0 0 1px rgba(133,86,45,.1); }
.agent-avatar img { width: 100%; height: 100%; object-fit: cover; }
.conversation-head > div:nth-child(2) { display: grid; gap: 3px; }
.conversation-head b { font-size: 14px; }
.conversation-head span { color: #758087; font-size: 11px; }
.spark-icon { margin-left: auto; color: var(--orange); }
.conversation-body { padding: clamp(26px, 4vw, 50px) clamp(24px, 6vw, 72px) 30px; overflow-y: auto; }
.agent-message { max-width: 760px; margin-bottom: 24px; }
.agent-message h2 { margin: 8px 0 10px; font-family: "Songti SC", SimSun, serif; font-size: clamp(25px, 3vw, 36px); line-height: 1.25; letter-spacing: -.035em; }
.agent-message > p:last-child { margin: 0; max-width: 680px; color: var(--muted); font-size: 14px; line-height: 1.75; }
.answer-card { max-width: 860px; padding: 26px; border: 1px solid rgba(123,91,55,.14); border-radius: 20px; background: rgba(255,255,255,.82); box-shadow: 0 14px 36px rgba(96,67,35,.08); }
.account-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.full { grid-column: 1 / -1; }
.field-label { display: grid; gap: 8px; color: #444f54; font-size: 12px; font-weight: 700; }
.text-field { min-height: 46px; padding: 0 14px; display: flex; align-items: center; gap: 10px; border: 1px solid #dcd6ce; border-radius: 11px; background: #fff; color: #889096; transition: border-color .2s ease, box-shadow .2s ease; }
.text-field:focus-within { border-color: var(--orange); box-shadow: 0 0 0 3px rgba(233,85,20,.1); }
.text-field input { width: 100%; border: 0; outline: 0; color: var(--ink); background: transparent; font-size: 14px; }
.text-field input::placeholder { color: #a7adb0; }
.question-stack { display: grid; gap: 23px; }
.question-stack.roomy { gap: 32px; }
fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }
legend { margin-bottom: 11px; color: #414b50; font-size: 13px; font-weight: 750; }
.choice-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.choice-grid.compact { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.choice-row { display: flex; flex-wrap: wrap; gap: 9px; }
.choice { min-height: 42px; padding: 10px 14px; display: inline-flex; align-items: center; justify-content: center; gap: 8px; text-align: center; color: #4f5a60; border: 1px solid #ded9d2; border-radius: 11px; background: #fffdfb; font-size: 13px; font-weight: 600; transition: color .2s ease, border-color .2s ease, background .2s ease, box-shadow .2s ease; }
.choice:hover { border-color: #e79a6c; color: #a94116; }
.choice:focus-visible, .primary-button:focus-visible, .skip-button:focus-visible, .text-button:focus-visible { outline: 3px solid rgba(233,85,20,.25); outline-offset: 2px; }
.choice.selected { color: #a63b11; border-color: #ed8c5d; background: #fff2e9; box-shadow: inset 0 0 0 1px rgba(233,85,20,.12); }
.visual-choices .choice { min-height: 64px; justify-content: flex-start; padding-left: 19px; }
.hours-control { display: grid; gap: 12px; padding: 17px; border-radius: 13px; background: #fbf6ef; }
.hours-control span { display: flex; justify-content: space-between; font-size: 13px; }
.hours-control strong { color: var(--orange-dark); }
.hours-control input { width: 100%; accent-color: var(--orange); cursor: pointer; }
.portrait-preview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.portrait-item { min-height: 112px; padding: 16px; display: grid; align-content: start; gap: 6px; border: 1px solid #e7dfd6; border-radius: 13px; background: #fffdf9; }
.portrait-item span { color: #8a6b55; font-size: 11px; font-weight: 750; }
.portrait-item b { font-size: 14px; line-height: 1.45; }
.portrait-item small { color: #7b858a; font-size: 11px; line-height: 1.5; }
.calibration-note { grid-column: 1 / -1; margin: 4px 0 0; padding: 13px 15px; display: flex; align-items: flex-start; gap: 9px; color: #735744; border-radius: 11px; background: #fff2df; font-size: 12px; line-height: 1.6; }
.calibration-note svg { flex: 0 0 auto; color: var(--orange); }
.error-banner { margin: 16px 0 0; padding: 11px 13px; color: #9e2d18; border: 1px solid #f2c1b5; border-radius: 10px; background: #fff3ef; font-size: 12px; }

.conversation-footer { min-height: 82px; padding: 16px 34px; display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--line); background: rgba(255,255,255,.62); }
.footer-actions, .success-actions { display: flex; align-items: center; gap: 10px; }
.text-button, .skip-button { min-height: 42px; padding: 0 14px; display: inline-flex; align-items: center; gap: 7px; color: #667278; border: 0; border-radius: 10px; background: transparent; font-weight: 650; font-size: 13px; }
.text-button:hover, .skip-button:hover { color: var(--orange-dark); background: rgba(233,85,20,.06); }
.primary-button { min-height: 45px; padding: 0 20px; display: inline-flex; align-items: center; justify-content: center; gap: 9px; color: white; border: 0; border-radius: 11px; background: linear-gradient(135deg, var(--orange), #cf410a); box-shadow: 0 8px 20px rgba(207,65,10,.2); font-weight: 750; font-size: 13px; transition: background .2s ease, box-shadow .2s ease; }
.primary-button:hover { background: linear-gradient(135deg, #f06122, #c73a05); box-shadow: 0 10px 24px rgba(207,65,10,.28); }
.primary-button:disabled { cursor: wait; opacity: .65; }
.submit-button { min-width: 190px; }

.success-card { width: min(760px, calc(100% - 36px)); margin: clamp(30px, 8vh, 90px) auto; padding: clamp(34px, 6vw, 66px); position: relative; z-index: 2; text-align: center; border: 1px solid rgba(118,87,54,.15); border-radius: 28px; background: rgba(255,255,255,.84); box-shadow: 0 28px 80px rgba(92,62,31,.14); backdrop-filter: blur(18px); }
.success-mark { width: 72px; height: 72px; margin: 0 auto 20px; display: grid; place-items: center; color: white; border-radius: 50%; background: linear-gradient(145deg, #e95514, #efa46e); box-shadow: 0 12px 32px rgba(233,85,20,.25); }
.success-card h1 { margin: 10px 0 14px; font-family: "Songti SC", SimSun, serif; font-size: clamp(28px, 4vw, 42px); line-height: 1.3; }
.success-card > p:not(.eyebrow) { max-width: 600px; margin: 0 auto; color: var(--muted); line-height: 1.8; font-size: 14px; }
.success-highlights { margin: 28px 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.success-highlights div { padding: 16px 10px; display: grid; gap: 7px; border-radius: 13px; background: #faf5ed; }
.success-highlights span { color: #8a6b55; font-size: 11px; }
.success-highlights b { font-size: 13px; }
.success-actions { justify-content: center; }

@media (max-width: 900px) {
  .topbar { padding: 0 20px; }
  .privacy-note { display: none; }
  .onboarding-shell { width: min(720px, calc(100% - 28px)); grid-template-columns: 1fr; }
  .journey-card { padding: 24px; }
  .journey-heading h1 { font-size: 24px; }
  .journey-heading p, .step-list, .trust-card { display: none; }
  .progress-track { margin-top: 20px; }
  .conversation-card { min-height: 680px; }
  .conversation-body { padding: 30px 24px; }
}

@media (max-width: 600px) {
  .topbar { height: 64px; grid-template-columns: 1fr auto; }
  .brand { grid-column: 2; font-size: 0; }
  .brand img { width: 27px; height: 27px; }
  .onboarding-shell { width: calc(100% - 16px); margin-top: 4px; border-radius: 20px; }
  .journey-card { padding: 20px; }
  .conversation-head { padding: 13px 18px; }
  .conversation-body { padding: 24px 15px; }
  .answer-card { padding: 18px 14px; }
  .account-grid, .choice-grid, .choice-grid.compact, .portrait-preview { grid-template-columns: 1fr; }
  .calibration-note { grid-column: auto; }
  .choice { min-height: 45px; }
  .conversation-footer { padding: 13px 15px; }
  .footer-actions { gap: 5px; }
  .skip-button { padding: 0 9px; }
  .primary-button { padding: 0 15px; }
  .submit-button { min-width: 0; }
  .success-highlights { grid-template-columns: 1fr; }
  .success-actions { flex-direction: column; }
  .success-actions button { width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; }
}
</style>
