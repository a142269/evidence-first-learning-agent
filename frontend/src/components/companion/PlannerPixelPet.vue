<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { BellOff, BookOpen, ChevronRight, Compass, GripHorizontal, HelpCircle, Loader2, Map, MessageCircle, Minimize2, RotateCcw, Send, Sparkles, X } from "lucide-vue-next";

import plannerSprite from "@/assets/companion/planner-pixel-sprite.png";
import { sendMessage } from "@/api/chat";
import { getRecommendations, getStudentOverview, type RecommendationsResponse, type StudentOverviewResponse } from "@/api/insights";
import { useSession } from "@/composables/useSession";
import { STUDENT_PAGE_GUIDES, type PageGuide } from "@/constants/platformGuide";

type PetAction = "idle" | "blink" | "wave" | "think" | "point" | "celebrate" | "sleep";

const route = useRoute();
const router = useRouter();
const { userId, course, chatSessionId } = useSession();
type PetTab = "nav" | "chat" | "todo" | "recommend" | "guide";
const open = ref(false);
const activeTab = ref<PetTab>("todo");
const collapsed = ref(false);
const muted = ref(false);
const frame = ref(0);
const currentAction = ref<PetAction>("idle");
const bubbleVisible = ref(true);
const petEl = ref<HTMLElement | null>(null);
const position = reactive({ x: 0, y: 0 });
const overview = ref<StudentOverviewResponse | null>(null);
const recommendations = ref<RecommendationsResponse | null>(null);
const petDataLoading = ref(false);
const chatLoading = ref(false);
const chatInput = ref("");
const chatMessages = ref<Array<{ role: "student" | "fox"; content: string }>>([
  { role: "fox", content: "杜同学，我在这里。可以问知识问题，也可以和我聊聊今天的学习状态。" },
]);
const dragging = ref(false);
let moved = false;
let startX = 0;
let startY = 0;
let originX = 0;
let originY = 0;
let idleTimer: ReturnType<typeof setInterval> | null = null;
let actionTimer: ReturnType<typeof setTimeout> | null = null;
let bubbleTimer: ReturnType<typeof setTimeout> | null = null;

const frameByAction: Record<PetAction, number> = {
  idle: 0,
  blink: 2,
  wave: 3,
  think: 4,
  point: 5,
  celebrate: 6,
  sleep: 7,
};

const statusMessage = computed(() => {
  if (route.path.startsWith("/path")) return "我正在帮你核对学习路径。";
  if (route.path.startsWith("/mistakes")) return "先处理最影响掌握度的错题吧。";
  if (route.path.startsWith("/graph")) return "点击聚类，可以更清楚地看知识结构。";
  if (route.path.startsWith("/resources")) return "需要的话，我可以按任务整理资源。";
  if (route.path.startsWith("/chat")) return "在群聊里 @智狐，我会重新安排计划。";
  return "今天的学习顺序已经整理好了。";
});

const spriteStyle = computed(() => {
  const col = frame.value % 4;
  const row = Math.floor(frame.value / 4);
  return {
    backgroundImage: `url(${plannerSprite})`,
    backgroundPosition: `${col * 33.3333}% ${row * 100}%`,
  };
});

const petStyle = computed(() => ({ left: `${position.x}px`, top: `${position.y}px` }));
const petTasks = computed<Array<Record<string, any>>>(() => {
  const source = overview.value?.path.today_tasks || [];
  if (source.length) return source.slice(0, 4) as Array<Record<string, any>>;
  if (course.value === "python_programming") {
    return [
      { id: "python-review", title: "复习函数与参数", description: "巩固易错调用方式", estimated_minutes: 8, route: "/mistakes" },
      { id: "python-path", title: "完成装饰器学习节点", description: "沿当前路径继续学习", estimated_minutes: 12, route: "/path" },
      { id: "python-practice", title: "完成分层练习", description: "让练习 Agent 即时反馈", estimated_minutes: 8, route: "/chat?agent=quiz" },
    ];
  }
  return [
    { id: "ai-review", title: "复习 Agent 角色分工", description: "处理近期易错知识点", estimated_minutes: 8, route: "/mistakes" },
    { id: "ai-path", title: "学习任务分解机制", description: "沿当前路径继续学习", estimated_minutes: 12, route: "/path" },
    { id: "ai-practice", title: "完成协作协议练习", description: "让练习 Agent 即时反馈", estimated_minutes: 8, route: "/chat?agent=quiz" },
  ];
});
const petRecommendations = computed(() => (recommendations.value?.items || []).slice(0, 3));
const quickNav = [
  { label: "首页", to: "/home" },
  { label: "学习路径", to: "/path" },
  { label: "知识图谱", to: "/graph" },
  { label: "错题本", to: "/mistakes" },
  { label: "资源库", to: "/resources" },
  { label: "学习工具箱", to: "/evidence" },
];

// ============================================================
// 功能指引（2026-07-17）：点击桌宠即可查每个功能"干什么用 + 在哪里"，
// 并可一键带路——回应"交互引导缺失"的评审意见
// ============================================================
interface GuideItem {
  label: string;
  desc: string;
  where: string;
  to: string;
}
const featureGuide: Array<{ group: string; items: GuideItem[] }> = [
  {
    group: "学 · 每天从这里开始",
    items: [
      { label: "首页", desc: "查看今日学习计划、掌握度和 Agent 工作状态，每天的起点", where: "顶部导航 · 首页", to: "/home" },
      { label: "学习路径", desc: "6 个 Agent 按你的画像规划的阶段目标和知识点顺序，沿着走就行", where: "顶部导航 · 学习路径", to: "/path" },
      { label: "资源库", desc: "本课程的讲义、视频、PPT、代码案例，支持收藏和检索", where: "顶部导航 · 资源库", to: "/resources" },
      { label: "AI 讲解", desc: "让猫头讲师用你能听懂的方式讲概念，支持追问", where: "群聊协作 @智灵，或首页「AI 学习建议」", to: "/chat?agent=tutor" },
    ],
  },
  {
    group: "练 · 练习与错题闭环",
    items: [
      { label: "闯关练习", desc: "小龙挑战按你的掌握度出分层题，做完即时反馈", where: "群聊协作 @小龙", to: "/chat?agent=quiz" },
      { label: "错题本", desc: "做错的题自动进来，还会生成变式题帮你真正掌握", where: "顶部导航 · 错题本", to: "/mistakes" },
      { label: "知识图谱", desc: "3D 课程知识地图，红色节点就是你的薄弱点，点击可直达复习", where: "顶部导航 · 知识图谱", to: "/graph" },
    ],
  },
  {
    group: "看 · 复盘自己的成长",
    items: [
      { label: "学习画像", desc: "6 维动态画像和学习报告，随学随新，告诉你下一步补什么", where: "顶部导航 · 学习画像", to: "/profile" },
      { label: "学习大屏", desc: "全景数据可视化，适合阶段性复盘和展示", where: "顶部导航 · 学习大屏", to: "/dashboard" },
      { label: "学习工具箱", desc: "证据链、间隔复习等进阶学习工具", where: "顶部导航 · 学习工具箱", to: "/evidence" },
    ],
  },
  {
    group: "协作 · 和 Agent 小队一起",
    items: [
      { label: "群聊协作", desc: "在群里 @任意 Agent 布置任务：出题、讲解、画图、做视频", where: "顶部导航 · 群聊协作", to: "/chat" },
      { label: "Agent 编排", desc: "查看 6 个 Agent 如何分工协作完成你的请求", where: "顶部导航 · Agent 协作", to: "/workflow" },
      { label: "桃园学宫", desc: "像素校园小游戏，学累了来放松一下", where: "顶部导航 · 桃园学宫", to: "/playground" },
    ],
  },
];

/** 重看首页新手引导：跳回首页并唤起引导（跨页用 sessionStorage 标记） */
function replayOnboarding() {
  if (route.path.startsWith("/home")) {
    window.dispatchEvent(new CustomEvent("tripleu:open-tour"));
    open.value = false;
    return;
  }
  try {
    sessionStorage.setItem("tripleu.tour.request", "1");
  } catch {
    /* 隐私模式忽略 */
  }
  void router.push("/home");
}

// ============================================================
// 逐页讲解（2026-07-17 v2）：数据源统一在 constants/platformGuide.ts，
// 与顶栏「?」帮助中心共用同一份"平台说明书"，避免两处内容漂移。
// ============================================================
const _FALLBACK_GUIDE: PageGuide = {
  prefix: "",
  name: "当前页面",
  where: "",
  purpose: "这里是 triple U 的功能页面。不确定怎么用时，可以看下面的整体脉络，点顶栏「?」打开完整帮助中心，或在群聊里直接问我。",
  howto: ["从下面的「整体脉络」选择你要去的功能"],
  next: { label: "首页", to: "/home", reason: "回到学习工作台，从今日计划开始" },
};

const currentPageGuide = computed<PageGuide>(() => {
  const matched = STUDENT_PAGE_GUIDES.find((guide) => route.path.startsWith(guide.prefix));
  return matched ?? _FALLBACK_GUIDE;
});

function clampPosition() {
  const width = petEl.value?.offsetWidth || 132;
  const height = petEl.value?.offsetHeight || 150;
  position.x = Math.max(8, Math.min(window.innerWidth - width - 8, position.x));
  position.y = Math.max(76, Math.min(window.innerHeight - height - 8, position.y));
}

function trigger(action: PetAction, duration = 1000) {
  if (actionTimer) clearTimeout(actionTimer);
  currentAction.value = action;
  frame.value = frameByAction[action];
  if (action !== "idle") {
    actionTimer = setTimeout(() => {
      currentAction.value = "idle";
      frame.value = frameByAction.idle;
    }, duration);
  }
}

function revealBubble() {
  bubbleVisible.value = true;
  if (bubbleTimer) clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(() => (bubbleVisible.value = false), 5200);
}

function togglePanel() {
  open.value = !open.value;
  if (open.value) void loadPetData();
  trigger(open.value ? "wave" : "idle", 1100);
  revealBubble();
}

async function loadPetData() {
  if (petDataLoading.value) return;
  petDataLoading.value = true;
  const [overviewResult, recommendationResult] = await Promise.allSettled([
    getStudentOverview(userId.value, course.value),
    getRecommendations(userId.value, 4, course.value),
  ]);
  if (overviewResult.status === "fulfilled") overview.value = overviewResult.value;
  if (recommendationResult.status === "fulfilled") recommendations.value = recommendationResult.value;
  petDataLoading.value = false;
  if (open.value && (overviewResult.status === "fulfilled" || recommendationResult.status === "fulfilled")) {
    trigger("celebrate", 760);
  }
}

function selectTab(tab: PetTab) {
  activeTab.value = tab;
  trigger(tab === "chat" ? "wave" : tab === "recommend" ? "think" : "point", 850);
  if (tab === "todo" || tab === "recommend") void loadPetData();
}

async function askFox(text?: string) {
  const question = (text ?? chatInput.value).trim();
  if (!question || chatLoading.value) return;
  chatMessages.value.push({ role: "student", content: question });
  chatInput.value = "";
  chatLoading.value = true;
  trigger("think", 1500);
  try {
    const response = await sendMessage({
      message: `@智狐 ${question}`,
      session_id: chatSessionId.value,
      course: course.value,
      user_id: userId.value,
    });
    chatMessages.value.push({
      role: "fox",
      content: response.content || response.error || "我已经记录了，我们换一种方式继续。",
    });
    trigger("celebrate", 900);
  } catch (error: any) {
    chatMessages.value.push({ role: "fox", content: `暂时没有连接到学习小队：${error?.detail ?? error?.message ?? "请稍后再试"}` });
  }
  chatLoading.value = false;
}

function askAboutRecommendation(title: string, reason: string) {
  activeTab.value = "chat";
  void askFox(`请解释为什么推荐我学习「${title}」。推荐依据是：${reason}`);
}

function navigateQuickly(to: string) {
  open.value = false;
  trigger("point", 720);
  void router.push(to);
}

function openTask(task: Record<string, any>) {
  trigger("celebrate", 900);
  const target = String(task.route || task.to || "").trim();
  if (target) {
    navigateQuickly(target);
    return;
  }
  const title = String(task.title || task.name || "今日学习任务");
  activeTab.value = "chat";
  void askFox(`请带我开始今天的任务「${title}」，先说明目标，再给我第一步。`);
}

function startDrag(event: PointerEvent) {
  if (event.button !== 0) return;
  dragging.value = true;
  moved = false;
  startX = event.clientX;
  startY = event.clientY;
  originX = position.x;
  originY = position.y;
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
}

function moveDrag(event: PointerEvent) {
  if (!dragging.value) return;
  const dx = event.clientX - startX;
  const dy = event.clientY - startY;
  if (Math.abs(dx) + Math.abs(dy) > 5) moved = true;
  position.x = originX + dx;
  position.y = originY + dy;
  clampPosition();
}

function endDrag() {
  if (!dragging.value) return;
  dragging.value = false;
  if (!moved) togglePanel();
  localStorage.setItem("tripleu.planner-pet-position", JSON.stringify(position));
}

function minimizePet() {
  collapsed.value = true;
  open.value = false;
  localStorage.setItem("tripleu.planner-pet-collapsed", "1");
}

function restorePet() {
  collapsed.value = false;
  localStorage.removeItem("tripleu.planner-pet-collapsed");
  trigger("wave", 1000);
}

watch(() => route.path, () => {
  open.value = false;
  trigger("point", 720);
  revealBubble();
});
watch(course, () => {
  overview.value = null;
  recommendations.value = null;
  if (open.value) void loadPetData();
});

onMounted(async () => {
  await nextTick();
  const saved = localStorage.getItem("tripleu.planner-pet-position");
  if (saved) {
    try {
      const parsed = JSON.parse(saved) as { x: number; y: number };
      position.x = parsed.x;
      position.y = parsed.y;
    } catch {
      position.x = window.innerWidth - 156;
      position.y = window.innerHeight - 176;
    }
  } else {
    position.x = window.innerWidth - 156;
    position.y = window.innerHeight - 176;
  }
  collapsed.value = localStorage.getItem("tripleu.planner-pet-collapsed") === "1";
  clampPosition();
  window.addEventListener("resize", clampPosition);
  idleTimer = setInterval(() => {
    if (dragging.value || open.value) return;
    const roll = Math.random();
    const action: PetAction = roll < .45 ? "blink" : roll < .62 ? "wave" : roll < .76 ? "think" : roll < .9 ? "point" : "sleep";
    const duration = action === "sleep" ? 1800 : action === "blink" ? 520 : 980;
    trigger(action, duration);
  }, 3200);
  revealBubble();
  void loadPetData();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", clampPosition);
  if (idleTimer) clearInterval(idleTimer);
  if (actionTimer) clearTimeout(actionTimer);
  if (bubbleTimer) clearTimeout(bubbleTimer);
});
</script>

<template>
  <button v-if="collapsed" type="button" class="pet-restore" aria-label="唤回小狐规划" title="唤回小狐规划" @click="restorePet">🦊</button>
  <div v-else ref="petEl" class="planner-pet" :class="[{ dragging, open }, `pet-action-${currentAction}`]" :style="petStyle">
    <transition name="pet-pop">
      <section v-if="open" class="pet-panel" aria-label="小狐规划快捷功能">
        <header>
          <div><span>Planner Agent</span><strong>小狐规划</strong></div>
          <button type="button" aria-label="关闭小狐规划菜单" @click="open = false"><X :size="15" /></button>
        </header>
        <nav class="pet-tabs" aria-label="小狐规划功能">
          <button type="button" :class="{ active: activeTab === 'guide' }" @click="selectTab('guide')"><HelpCircle :size="14" />指引</button>
          <button type="button" :class="{ active: activeTab === 'nav' }" @click="selectTab('nav')"><Compass :size="14" />导航</button>
          <button type="button" :class="{ active: activeTab === 'chat' }" @click="selectTab('chat')"><MessageCircle :size="14" />问答</button>
          <button type="button" :class="{ active: activeTab === 'todo' }" @click="selectTab('todo')"><Map :size="14" />待办</button>
          <button type="button" :class="{ active: activeTab === 'recommend' }" @click="selectTab('recommend')"><Sparkles :size="14" />推荐</button>
        </nav>

        <div class="pet-workspace">
          <section v-if="activeTab === 'guide'" class="pet-guide">
            <!-- 本页讲解：按当前路由自动匹配 -->
            <div class="pet-page-guide">
              <span class="pet-page-tag">本页讲解</span>
              <h3>{{ currentPageGuide.name }}</h3>
              <p class="pet-page-purpose">{{ currentPageGuide.purpose }}</p>
              <ol class="pet-page-howto">
                <li v-for="(step, index) in currentPageGuide.howto" :key="index">{{ step }}</li>
              </ol>
              <button type="button" class="pet-page-next" @click="navigateQuickly(currentPageGuide.next.to)">
                <span><b>下一步去「{{ currentPageGuide.next.label }}」</b><small>{{ currentPageGuide.next.reason }}</small></span>
                <ChevronRight :size="14" />
              </button>
            </div>

            <p class="pet-summary">整体脉络 · 每个功能是干什么的、在哪里，点一下我就带你过去。</p>
            <div v-for="section in featureGuide" :key="section.group" class="pet-guide-group">
              <h4>{{ section.group }}</h4>
              <button v-for="item in section.items" :key="item.to" type="button" @click="navigateQuickly(item.to)">
                <span class="pet-guide-main">
                  <b>{{ item.label }}</b>
                  <small>{{ item.desc }}</small>
                  <em><Compass :size="10" />{{ item.where }}</em>
                </span>
                <span class="pet-guide-go">带我去<ChevronRight :size="12" /></span>
              </button>
            </div>
            <button type="button" class="pet-guide-replay" @click="replayOnboarding">
              <RotateCcw :size="13" />重看首页新手引导
            </button>
          </section>

          <section v-else-if="activeTab === 'nav'" class="pet-nav-grid">
            <button v-for="item in quickNav" :key="item.to" type="button" @click="navigateQuickly(item.to)">
              <span>{{ item.label }}</span><ChevronRight :size="13" />
            </button>
          </section>

          <section v-else-if="activeTab === 'chat'" class="pet-chat">
            <div class="pet-chat-log" aria-live="polite">
              <p v-for="(message, index) in chatMessages.slice(-6)" :key="index" :class="message.role">{{ message.content }}</p>
              <p v-if="chatLoading" class="fox thinking"><Loader2 :size="13" class="pet-spin" />小狐正在和学习小队一起分析…</p>
            </div>
            <div class="pet-chat-prompts">
              <button type="button" @click="askFox('帮我解释今天最难的知识点')">解释难点</button>
              <button type="button" @click="askFox('我今天有点学不动，陪我聊聊并调整计划')">陪我聊聊</button>
            </div>
            <form @submit.prevent="askFox()">
              <input v-model="chatInput" aria-label="向小狐提问" placeholder="问知识问题，或聊聊学习状态…" />
              <button type="submit" :disabled="chatLoading || !chatInput.trim()" aria-label="发送"><Send :size="15" /></button>
            </form>
          </section>

          <section v-else-if="activeTab === 'todo'" class="pet-list-panel">
            <p class="pet-summary">{{ overview?.path.title || statusMessage }}</p>
            <div v-if="petDataLoading" class="pet-inline-loading"><Loader2 :size="14" class="pet-spin" />正在整理今日待办</div>
            <button v-for="(task, index) in petTasks" v-else :key="String(task.id || index)" type="button" @click="openTask(task)">
              <em>{{ String(index + 1).padStart(2, '0') }}</em>
              <span><b>{{ task.title || task.name }}</b><small>{{ task.description || task.type }} · {{ task.estimated_minutes || 10 }} 分钟</small></span>
              <ChevronRight :size="13" />
            </button>
            <p v-if="!petDataLoading && !petTasks.length" class="pet-empty">今天没有生成待办，可以在问答中让小狐规划。</p>
          </section>

          <section v-else class="pet-list-panel recommendation-panel">
            <p class="pet-summary">根据当前课程、薄弱点和近期表现生成。</p>
            <div v-if="petDataLoading" class="pet-inline-loading"><Loader2 :size="14" class="pet-spin" />正在生成推荐</div>
            <button
              v-for="(item, index) in petRecommendations"
              v-else
              :key="String(item.resource_id || item.kp_id || index)"
              type="button"
              @click="askAboutRecommendation(String(item.title || item.topic || item.kp_id), item.reason)"
            >
              <BookOpen :size="15" />
              <span><b>{{ item.title || item.topic || item.kp_id }}</b><small>{{ item.reason }}</small></span>
              <MessageCircle :size="13" />
            </button>
            <p v-if="!petDataLoading && !petRecommendations.length" class="pet-empty">完成一次学习或练习后，我会给出更准确的推荐。</p>
          </section>
        </div>
        <footer>
          <button type="button" :class="{ active: muted }" @click="muted = !muted"><BellOff :size="14" />{{ muted ? '已静音' : '静音提醒' }}</button>
          <button type="button" @click="minimizePet"><Minimize2 :size="14" />暂时收起</button>
        </footer>
      </section>
    </transition>

    <transition name="pet-bubble">
      <button v-if="bubbleVisible && !open" type="button" class="pet-message" @click="togglePanel">{{ statusMessage }}</button>
    </transition>

    <button
      type="button"
      class="pet-sprite-button"
      :aria-expanded="open"
      aria-label="打开小狐规划"
      title="点击打开 · 拖动可移动"
      @pointerdown="startDrag"
      @pointermove="moveDrag"
      @pointerup="endDrag"
      @pointercancel="endDrag"
      @mouseenter="!dragging && !open && trigger('wave', 760)"
      @dblclick.stop="trigger('celebrate', 1100)"
    >
      <span class="pet-grip"><GripHorizontal :size="13" /></span>
      <span class="pet-sprite" :style="spriteStyle" />
      <i class="pet-status" />
    </button>
  </div>
</template>

<style scoped>
.planner-pet { position: fixed; z-index: 145; width: 132px; height: 150px; user-select: none; touch-action: none; }
.planner-pet.dragging { cursor: grabbing; }
.pet-sprite-button { position: absolute; right: 0; bottom: 0; width: 124px; height: 142px; padding: 0; border: 0; background: transparent; cursor: grab; filter: drop-shadow(0 8px 10px rgba(75, 43, 20, .16)); transition: transform 180ms cubic-bezier(.16,1,.3,1), filter 180ms ease-out; }
.pet-sprite-button:hover { transform: translateY(-3px); filter: drop-shadow(0 11px 13px rgba(75, 43, 20, .2)); }
.pet-sprite-button:active { cursor: grabbing; transform: translateY(0) scale(.98); }
.pet-sprite-button:focus-visible { outline: 3px solid rgba(232,93,22,.3); outline-offset: 3px; border-radius: 16px; }
.planner-pet.pet-action-idle:not(.open):not(.dragging) .pet-sprite-button { animation: pet-breathe 2.6s steps(2, end) infinite; }
.planner-pet.pet-action-blink .pet-sprite-button { animation: pet-nod 520ms steps(2, end); }
.planner-pet.pet-action-wave .pet-sprite-button { animation: pet-wave 760ms steps(3, end); }
.planner-pet.pet-action-think .pet-sprite-button { animation: pet-think 980ms steps(3, end); }
.planner-pet.pet-action-point .pet-sprite-button { animation: pet-point 820ms steps(2, end); }
.planner-pet.pet-action-celebrate .pet-sprite-button { animation: pet-celebrate 820ms steps(4, end); }
.planner-pet.pet-action-sleep .pet-sprite-button { animation: pet-sleep 1.8s steps(3, end); filter: drop-shadow(0 6px 8px rgba(75,43,20,.12)) saturate(.82); }
.pet-sprite { position: absolute; inset: 8px 0 0; display: block; background-repeat: no-repeat; background-size: 400% 200%; image-rendering: pixelated; }
.pet-grip { position: absolute; top: 0; left: 50%; z-index: 2; display: grid; place-items: center; width: 28px; height: 17px; border: 1px solid #e5e1d9; border-radius: 999px; background: rgba(255,255,255,.88); color: #89857d; opacity: 0; transform: translateX(-50%); transition: opacity 150ms ease-out; }
.pet-sprite-button:hover .pet-grip { opacity: 1; }
.pet-status { position: absolute; right: 10px; bottom: 10px; z-index: 3; width: 10px; height: 10px; border: 2px solid #fff; border-radius: 50%; background: #247553; box-shadow: 0 0 0 2px rgba(36,117,83,.14); }
.pet-message { position: absolute; right: 110px; bottom: 88px; width: max-content; max-width: 224px; padding: 9px 12px; border: 1px solid #e5e1d9; border-radius: 10px 10px 2px 10px; background: rgba(255,255,255,.96); color: #625f58; font-size: 12px; line-height: 1.45; text-align: left; box-shadow: 0 8px 24px rgba(35,31,25,.06); cursor: pointer; }
.pet-panel { position: absolute; right: 116px; bottom: 24px; width: 348px; overflow: hidden; border: 1px solid #e5e1d9; border-radius: 13px; background: #fff; box-shadow: 0 12px 32px rgba(35,31,25,.12); }
.pet-panel header { display: flex; align-items: center; justify-content: space-between; padding: 14px 14px 11px; border-bottom: 1px solid #ece8e1; background: #fffaf5; }
.pet-panel header div { display: flex; flex-direction: column; gap: 2px; }
.pet-panel header span { color: #a46916; font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
.pet-panel header strong { color: #171512; font-size: 15px; }
.pet-panel header button { display: grid; place-items: center; width: 30px; height: 30px; padding: 0; border: 1px solid #e5e1d9; border-radius: 7px; background: #fff; color: #625f58; cursor: pointer; }
.pet-tabs { display: grid; grid-template-columns: repeat(5, 1fr); padding: 5px; border-bottom: 1px solid #ece8e1; background: #fbfaf7; }
.pet-tabs button { display: inline-flex; align-items: center; justify-content: center; gap: 4px; min-height: 34px; padding: 0 4px; border: 0; border-radius: 6px; background: transparent; color: #89857d; font-size: 10px; cursor: pointer; }
.pet-tabs button:hover, .pet-tabs button.active { background: #fff3ea; color: #d75011; }
.pet-workspace { min-height: 220px; max-height: 410px; overflow-y: auto; }
.pet-nav-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; padding: 12px; }
.pet-nav-grid button { display: flex; align-items: center; justify-content: space-between; min-height: 42px; padding: 0 10px; border: 1px solid #e5e1d9; border-radius: 8px; background: #fff; color: #625f58; font-size: 11px; cursor: pointer; }
.pet-nav-grid button:hover { border-color: #f1c9ae; background: #fff3ea; color: #d75011; transform: translateY(-1px); }
.pet-summary { margin: 0; padding: 11px 12px 8px; color: #89857d; font-size: 10.5px; line-height: 1.5; }
/* 功能指引（2026-07-17）：干什么 + 在哪里 + 带我去 */
.pet-guide { padding: 0 8px 10px; }
/* 本页讲解：目的 + 怎么用步骤 + 下一步建议（增强页面间脉络连贯性） */
.pet-page-guide { margin: 9px 4px 4px; padding: 11px 12px; border: 1.5px solid #f4d8c4; border-radius: 11px; background: linear-gradient(155deg, #fff6ef, #fff); }
.pet-page-tag { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #e85d16; color: #fff; font-size: 8.5px; font-weight: 800; letter-spacing: .05em; }
.pet-page-guide h3 { margin: 7px 0 4px; color: #171512; font-size: 13px; }
.pet-page-purpose { margin: 0 0 6px; color: #625f58; font-size: 10.5px; line-height: 1.6; }
.pet-page-howto { margin: 0; padding-left: 16px; display: flex; flex-direction: column; gap: 3px; }
.pet-page-howto li { color: #6b675f; font-size: 10px; line-height: 1.55; }
.pet-page-next { display: grid; grid-template-columns: minmax(0,1fr) 14px; align-items: center; gap: 6px; width: 100%; margin-top: 9px; padding: 8px 10px; border: 1px solid #f1c9ae; border-radius: 9px; background: #fff; text-align: left; cursor: pointer; transition: border-color 150ms ease-out, transform 150ms ease-out; }
.pet-page-next:hover { border-color: #e85d16; transform: translateX(2px); }
.pet-page-next b { display: block; color: #d75011; font-size: 10.5px; }
.pet-page-next small { display: block; margin-top: 1px; color: #89857d; font-size: 9px; line-height: 1.4; }
.pet-page-next svg { color: #d75011; }
.pet-guide-group h4 { margin: 8px 4px 3px; color: #a46916; font-size: 10px; font-weight: 800; letter-spacing: .04em; }
.pet-guide-group > button { display: grid; grid-template-columns: minmax(0,1fr) auto; align-items: center; gap: 8px; width: 100%; padding: 7px 8px; border: 0; border-radius: 9px; background: transparent; text-align: left; cursor: pointer; transition: background-color 150ms ease-out, transform 150ms ease-out; }
.pet-guide-group > button:hover { background: #fff3ea; transform: translateX(2px); }
.pet-guide-main { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.pet-guide-main b { color: #1f1d1a; font-size: 11.5px; }
.pet-guide-main small { display: -webkit-box; overflow: hidden; color: #89857d; font-size: 9.5px; line-height: 1.45; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.pet-guide-main em { display: inline-flex; align-items: center; gap: 3px; margin-top: 1px; color: #b08946; font-size: 9px; font-style: normal; font-weight: 700; }
.pet-guide-go { display: inline-flex; align-items: center; gap: 2px; color: #d75011; font-size: 9.5px; font-weight: 700; white-space: nowrap; opacity: 0; transition: opacity 150ms ease-out; }
.pet-guide-group > button:hover .pet-guide-go { opacity: 1; }
.pet-guide-replay { display: flex; align-items: center; justify-content: center; gap: 5px; width: 100%; margin-top: 9px; padding: 8px; border: 1px dashed #e5d5c5; border-radius: 9px; background: #fffaf5; color: #a46916; font-size: 10.5px; font-weight: 700; cursor: pointer; transition: border-color 150ms ease-out, color 150ms ease-out; }
.pet-guide-replay:hover { border-color: #d75011; color: #d75011; }
.pet-list-panel { padding: 0 7px 9px; }
.pet-list-panel > button { display: grid; grid-template-columns: 24px minmax(0,1fr) 14px; align-items: center; gap: 7px; width: 100%; min-height: 54px; padding: 6px 7px; border: 0; border-radius: 8px; background: transparent; color: #625f58; text-align: left; cursor: pointer; }
.pet-list-panel > button:hover { background: #fff3ea; color: #d75011; transform: translateX(2px); }
.pet-list-panel > button em { color: #b4aea4; font-size: 10px; font-style: normal; font-weight: 700; }
.pet-list-panel > button > span { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.pet-list-panel b { overflow: hidden; color: #1f1d1a; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.pet-list-panel small { display: -webkit-box; overflow: hidden; color: #89857d; font-size: 9.5px; line-height: 1.35; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.recommendation-panel > button { grid-template-columns: 20px minmax(0,1fr) 14px; }
.recommendation-panel > button > svg:first-child { color: #6557d9; }
.pet-inline-loading, .pet-empty { display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 110px; margin: 0; padding: 14px; color: #89857d; font-size: 10.5px; text-align: center; }
.pet-chat { display: flex; min-height: 252px; flex-direction: column; padding: 9px; }
.pet-chat-log { display: flex; min-height: 142px; max-height: 230px; overflow-y: auto; flex-direction: column; gap: 6px; padding: 3px; }
.pet-chat-log p { width: fit-content; max-width: 88%; margin: 0; padding: 7px 9px; border-radius: 9px; font-size: 10.5px; line-height: 1.5; white-space: pre-wrap; }
.pet-chat-log p.fox { align-self: flex-start; border: 1px solid #ece8e1; border-radius: 3px 9px 9px 9px; background: #fbfaf7; color: #625f58; }
.pet-chat-log p.student { align-self: flex-end; border-radius: 9px 3px 9px 9px; background: #fff3ea; color: #7b3d19; }
.pet-chat-log p.thinking { display: inline-flex; align-items: center; gap: 5px; color: #6557d9; }
.pet-chat-prompts { display: flex; gap: 5px; padding: 7px 2px 5px; }
.pet-chat-prompts button { min-height: 26px; padding: 0 8px; border: 1px solid #e5e1f4; border-radius: 999px; background: #faf9ff; color: #6557d9; font-size: 9.5px; cursor: pointer; }
.pet-chat form { display: grid; grid-template-columns: minmax(0,1fr) 34px; gap: 5px; margin-top: auto; padding-top: 5px; border-top: 1px solid #ece8e1; }
.pet-chat input { min-width: 0; height: 36px; padding: 0 9px; border: 1px solid #e5e1d9; border-radius: 8px; outline: 0; color: #1f1d1a; font-size: 10.5px; }
.pet-chat input:focus { border-color: #e85d16; box-shadow: 0 0 0 3px rgba(232,93,22,.09); }
.pet-chat form button { display: grid; place-items: center; width: 34px; height: 36px; padding: 0; border: 0; border-radius: 8px; background: #e85d16; color: #fff; cursor: pointer; }
.pet-chat form button:disabled { opacity: .45; cursor: default; }
.pet-spin { animation: pet-spin 900ms linear infinite; }
@keyframes pet-spin { to { transform: rotate(360deg); } }
@keyframes pet-breathe { 50% { transform: translateY(-2px); } }
@keyframes pet-nod { 45% { transform: translateY(2px) rotate(-1deg); } }
@keyframes pet-wave { 30% { transform: translateY(-4px) rotate(-2deg); } 70% { transform: translateY(-2px) rotate(2deg); } }
@keyframes pet-think { 35%, 75% { transform: translateX(-2px); } 55% { transform: translateX(2px) translateY(-1px); } }
@keyframes pet-point { 45% { transform: translateX(-4px) translateY(-2px); } }
@keyframes pet-celebrate { 25%, 75% { transform: translateY(-8px) rotate(-2deg); } 50% { transform: translateY(0) rotate(2deg); } }
@keyframes pet-sleep { 50% { transform: translateY(3px) scale(.99); } }
.pet-actions { display: grid; gap: 3px; padding: 0 7px 8px; }
.pet-actions > button { display: grid; grid-template-columns: 20px minmax(0,1fr) 14px; align-items: center; gap: 8px; min-height: 50px; padding: 6px 8px; border: 0; border-radius: 8px; background: transparent; color: #625f58; text-align: left; cursor: pointer; transition: background-color 160ms ease-out, transform 160ms ease-out; }
.pet-actions > button:hover { background: #fff3ea; color: #d75011; transform: translateX(2px); }
.pet-actions span { display: flex; min-width: 0; flex-direction: column; gap: 2px; }
.pet-actions b { color: #1f1d1a; font-size: 12px; }
.pet-actions small { overflow: hidden; color: #89857d; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.pet-panel footer { display: flex; justify-content: space-between; padding: 8px 10px; border-top: 1px solid #ece8e1; background: #fbfaf7; }
.pet-panel footer button { display: inline-flex; align-items: center; gap: 5px; min-height: 30px; padding: 0 6px; border: 0; background: transparent; color: #89857d; font-size: 10px; cursor: pointer; }
.pet-panel footer button:hover, .pet-panel footer button.active { color: #d75011; }
.pet-restore { position: fixed; right: 10px; bottom: 82px; z-index: 145; display: grid; place-items: center; width: 40px; height: 44px; padding: 0; border: 1px solid #f1c9ae; border-radius: 10px 0 0 10px; background: #fff3ea; font-size: 22px; box-shadow: 0 8px 24px rgba(35,31,25,.07); cursor: pointer; }
.pet-pop-enter-active, .pet-pop-leave-active, .pet-bubble-enter-active, .pet-bubble-leave-active { transition: opacity 180ms ease-out, transform 200ms cubic-bezier(.16,1,.3,1); }
.pet-pop-enter-from, .pet-pop-leave-to { opacity: 0; transform: translate(8px, 5px) scale(.96); }
.pet-bubble-enter-from, .pet-bubble-leave-to { opacity: 0; transform: translateX(6px); }
@media (max-width: 700px) {
  .planner-pet { width: 96px; height: 112px; }
  .pet-sprite-button { width: 94px; height: 108px; }
  .pet-panel { position: fixed; right: 8px; bottom: 116px; width: min(348px, calc(100vw - 16px)); }
  .pet-message { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .pet-sprite-button, .pet-panel, .pet-message, .pet-actions > button { animation: none !important; transition-duration: .01ms !important; }
}
</style>
