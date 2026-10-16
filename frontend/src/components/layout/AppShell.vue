<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Wrench,
  BarChart3,
  Bell,
  BookOpen,
  BookX,
  Database,
  Gamepad2,
  LayoutDashboard,
  HelpCircle,
  Home,
  Library,
  LogOut,
  MessageSquare,
  Network,
  Plus,
  Route as RouteIcon,
  Search,
  Settings,
  SlidersHorizontal,
  ShieldCheck,
  Users,
  Workflow,
} from "lucide-vue-next";

import { getLearnerPartner, partners, teacherPartner } from "@/constants/companion";
import Avatar from "@/components/companion/Avatar.vue";
import PlannerPixelPet from "@/components/companion/PlannerPixelPet.vue";
import HelpCenter from "@/components/shared/HelpCenter.vue";
import { getAuthSession, isTeacherRole } from "@/utils/auth";
import { useSession } from "@/composables/useSession";
import { getGamification, type GamificationProfile } from "@/api/gamification";
import { listCourses } from "@/api/knowledge";

const route = useRoute();
const router = useRouter();
const { userId, course, setCourse } = useSession();
// 课程显示名由后端 course.yaml 清单下发（2026-07-16 平台化改造，去除前端写死映射）
const fallbackCourses = [{ value: "artificial_intelligence", label: "人工智能导论" }];
const courseOptions = ref([...fallbackCourses]);

const legacyDemoNames = new Set(["演示学习者", "张三", "小明"]);
const displayName = computed(() => {
  const name = getAuthSession()?.displayName || "杜同学";
  return legacyDemoNames.has(name) ? "杜同学" : name;
});
const teacherView = computed(() => isTeacherRole());
// 顶栏用户形象：教师账号用独立的教师头像，学生账号按学号取学习者头像。
// 过去教师也走 getLearnerPartner，导致王老师顶着杜同学的照片头像。
const learnerPartner = computed(() =>
  teacherView.value
    ? { ...teacherPartner, name: displayName.value }
    : getLearnerPartner(userId.value, displayName.value),
);
// 学生端采用教师式工作台壳层的页面：首页 + 学习路径/资源库/Agent协作/错题本/学习工具箱
const STUDENT_WORKBENCH_PATHS = ["/home", "/path", "/resources", "/workflow", "/mistakes", "/evidence"];
const studentWorkbenchView = computed(
  () => !teacherView.value && STUDENT_WORKBENCH_PATHS.some((path) => route.path.startsWith(path)),
);
const roleLabel = computed(() => {
  const role = getAuthSession()?.role || "student";
  if (role === "teacher") return "教师";
  if (role === "admin") return "管理员";
  return "学习者";
});

interface ShellNavItem {
  label: string;
  to: string;
  name: string;
  icon: typeof Home;
}

const studentNavItems: ShellNavItem[] = [
  { label: "首页", to: "/home", name: "home", icon: Home },
  { label: "学习大屏", to: "/dashboard", name: "dashboard", icon: LayoutDashboard },
  { label: "群聊协作", to: "/chat", name: "chat", icon: MessageSquare },
  { label: "学习路径", to: "/path", name: "path", icon: RouteIcon },
  { label: "资源库", to: "/resources", name: "resources", icon: Library },
  { label: "Agent 协作", to: "/workflow", name: "workflow", icon: Workflow },
  { label: "错题本", to: "/mistakes", name: "mistakes", icon: BookX },
  { label: "知识图谱", to: "/graph", name: "graph", icon: Network },
  { label: "学习画像", to: "/profile", name: "profile", icon: BarChart3 },
  // 安全中心已迁入教师端（内容审核属教学管理职责，学生端不再展示）
  { label: "学习工具箱", to: "/evidence", name: "evidence", icon: Wrench },
  { label: "桃园学宫", to: "/playground", name: "playground", icon: Gamepad2 },
];

const teacherNavItems: ShellNavItem[] = [
  { label: "教师管理台", to: "/teacher", name: "teacher", icon: LayoutDashboard },
  { label: "安全中心", to: "/safety", name: "safety", icon: ShieldCheck },
  { label: "设置中心", to: "/settings", name: "settings", icon: Settings },
];

const teacherTaskNavItems: ShellNavItem[] = [
  { label: "教学概览", to: "/teacher", name: "teacher", icon: LayoutDashboard },
  { label: "课程知识库", to: "/teacher/kb", name: "teacher-kb", icon: Database },
  { label: "知识图谱", to: "/teacher/knowledge", name: "teacher-knowledge", icon: Network },
  { label: "学生分析", to: "/teacher/students", name: "teacher-students", icon: Users },
  { label: "教学提示与视频", to: "/teacher/studio", name: "teacher-studio", icon: BookOpen },
  { label: "教学资源", to: "/teacher/resources", name: "teacher-resources", icon: Library },
  { label: "教学干预", to: "/teacher/interventions", name: "teacher-interventions", icon: MessageSquare },
  { label: "Agent 协作", to: "/teacher/agents", name: "teacher-agents", icon: Workflow },
  { label: "安全中心", to: "/safety", name: "safety", icon: ShieldCheck },
  { label: "设置中心", to: "/settings", name: "settings", icon: Settings },
];

const navItems = computed<ShellNavItem[]>(() =>
  teacherView.value ? teacherTaskNavItems : studentNavItems,
);
const searchQuery = ref("");
const gamify = ref<GamificationProfile | null>(null);

const spaceProgress = computed(() => {
  if (!gamify.value) return 45;
  const level = gamify.value.level;
  const need = Math.max(level * 100, 1);
  return Math.min(99, Math.round(((gamify.value.xp % need) / need) * 100));
});

async function refreshGamify() {
  try {
    gamify.value = await getGamification(userId.value);
  } catch {
    gamify.value = null;
  }
}

function handleGamifyRefresh() {
  refreshGamify();
}

onMounted(async () => {
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
  await refreshGamify();
  window.addEventListener("gamify:refresh", handleGamifyRefresh);
});

onUnmounted(() => {
  window.removeEventListener("gamify:refresh", handleGamifyRefresh);
});

function handleNewTask() {
  router.push({ path: "/chat", query: { compose: "1" } });
}

function handleCourseChange(event: Event) {
  setCourse((event.target as HTMLSelectElement).value);
}

function handleSearch() {
  const q = searchQuery.value.trim();
  if (!q) return;
  if (teacherView.value) {
    router.push({ path: "/teacher/resources", query: { q } });
    searchQuery.value = "";
    return;
  }
  router.push({ path: "/resources", query: { q } });
  searchQuery.value = "";
}

const notice = ref("");
let noticeTimer: ReturnType<typeof setTimeout> | null = null;
function showNotice(msg: string) {
  notice.value = msg;
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => (notice.value = ""), 2600);
}

function handleBell() {
  showNotice("暂无新消息 · 群聊中 @智灵 即可发起对话");
}
// 2026-07-17：「?」= 完整帮助中心（平台介绍/逐页功能手册/Agent 说明/FAQ），
// 任何页面直接打开；分步引导作为帮助中心里的一个入口。
const helpCenterOpen = ref(false);

function handleHelp() {
  helpCenterOpen.value = true;
}

/** 帮助中心里点「播放分步引导」：引导组件挂在两端首页，跨页时打标记跳转 */
function handleReplayTour() {
  helpCenterOpen.value = false;
  const target = teacherView.value ? "/teacher" : "/home";
  if (route.path === target) {
    window.dispatchEvent(new CustomEvent("tripleu:open-tour"));
    return;
  }
  try {
    sessionStorage.setItem("tripleu.tour.request", "1");
  } catch {
    /* 隐私模式忽略 */
  }
  void router.push(target);
}
function handleInvite() {
  showNotice("自定义 Agent 由教师在管理台「Agent 管理」配置，群聊中 @名称 即可调用");
}

function navIsActive(item: ShellNavItem) {
  return item.to === "/teacher" ? route.path === "/teacher" : route.path.startsWith(item.to);
}

function updateNavPointer(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  target.style.setProperty("--nav-x", `${event.clientX - rect.left}px`);
  target.style.setProperty("--nav-y", `${event.clientY - rect.top}px`);
}

</script>

<template>
  <div
    class="companion-scope app-shell"
    :class="{
      'teacher-shell': teacherView,
      'student-workbench-shell': studentWorkbenchView,
      'profile-shell': !teacherView && route.path.startsWith('/profile'),
    }"
  >
    <header class="shell-header">
      <div class="shell-topbar">
        <div class="brand">
          <span class="brand-logo"><img src="/logo.png" alt="triple U" /></span>
          <strong>triple U</strong>
          <em class="brand-badge">多Agent协作系统</em>
        </div>

        <form class="topbar-search" @submit.prevent="handleSearch">
          <Search :size="15" />
          <input v-model="searchQuery" placeholder="搜索课程、资源与知识" aria-label="全局搜索" />
        </form>

        <div class="topbar-actions">
          <label v-if="!teacherView" class="topbar-course-picker">
            <BookOpen :size="15" />
            <select :value="course" aria-label="切换当前课程" @change="handleCourseChange">
              <option v-for="item in courseOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <button v-if="!teacherView" type="button" class="new-task-btn" @click="handleNewTask">
            <Plus :size="16" :stroke-width="2.5" /><span>新建任务</span>
          </button>
          <button type="button" class="topbar-icon-btn" title="消息" aria-label="消息" @click="handleBell"><Bell :size="17" /><i class="dot" /></button>
          <button type="button" class="topbar-icon-btn" title="帮助" aria-label="帮助" @click="handleHelp"><HelpCircle :size="17" /></button>
          <div class="topbar-user">
            <Avatar :partner="learnerPartner" size="md" />
            <div class="user-copy">
              <b>{{ displayName }}</b>
              <small>{{ roleLabel }}{{ !teacherView && gamify ? ` · Lv.${gamify.level}` : "" }}</small>
            </div>
            <button type="button" class="topbar-icon-btn logout-btn" title="退出登录" aria-label="退出登录" @click="router.push('/logout')">
              <LogOut :size="15" />
            </button>
          </div>
        </div>
      </div>

      <div class="shell-navigation">
        <nav class="shell-nav" aria-label="主导航">
          <div class="shell-nav-scroll">
            <router-link
              v-for="item in navItems"
              :key="item.name"
              :to="item.to"
              :class="['shell-nav-item', navIsActive(item) ? 'active' : '']"
              @pointermove="updateNavPointer"
            >
              <component :is="item.icon" :size="17" :stroke-width="1.9" />
              <span>{{ item.label }}</span>
            </router-link>
          </div>
        </nav>
        <div v-if="!teacherView" class="nav-tools" aria-label="界面工具">
          <button type="button" title="设置中心" aria-label="设置中心" @click="router.push('/settings')"><Settings :size="17" /></button>
          <button type="button" title="界面偏好" aria-label="界面偏好" @click="showNotice('界面偏好可在设置中心调整')"><SlidersHorizontal :size="16" /></button>
        </div>
        <div v-if="!teacherView" class="nav-context" aria-label="学习状态">
          <div class="progress-chip" title="机器学习基础课程进度">
            <BookOpen :size="15" />
            <span>学习进度</span>
            <b>{{ spaceProgress }}%</b>
            <i><span :style="{ transform: `scaleX(${spaceProgress / 100})` }" /></i>
          </div>
          <button type="button" class="agent-chip" title="查看 Agent 协作说明" @click="handleInvite">
            <Users :size="15" />Agent 群 <b>{{ partners.length + 1 }}</b>
          </button>
        </div>
      </div>
    </header>

    <div class="shell-body">
      <main class="shell-main">
        <div
          :class="[
            'shell-content',
            teacherView || studentWorkbenchView ? 'teacher-content-canvas' : '',
          ]"
        >
          <slot />
        </div>
      </main>
    </div>

    <transition name="notice-fade">
      <div v-if="notice" class="shell-notice" role="status">{{ notice }}</div>
    </transition>
    <PlannerPixelPet v-if="!teacherView && !route.path.startsWith('/graph')" />
    <HelpCenter
      v-if="helpCenterOpen"
      :role="teacherView ? 'teacher' : 'student'"
      @close="helpCenterOpen = false"
      @replay-tour="handleReplayTour"
    />
  </div>
</template>

<style scoped>
.shell-notice {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 200;
  padding: 10px 18px;
  border-radius: 10px;
  background: rgba(25, 21, 17, 0.86);
  color: #fff;
  font-size: 13px;
  letter-spacing: 0.2px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
}

.notice-fade-enter-active,
.notice-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.notice-fade-enter-from,
.notice-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, 6px);
}

.app-shell {
  height: 100vh;
  min-width: 0;
  max-width: 100vw;
  width: 100%;
  overflow: hidden;
  background: #f7f8fa;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: auto minmax(0, 1fr);
}

/* ---------- 顶部应用导航 ---------- */
.shell-header {
  z-index: 60;
  min-width: 0;
  padding: 14px 24px 0;
  background: var(--neutral-50);
}

.shell-topbar {
  display: flex;
  align-items: center;
  gap: 24px;
  min-width: 0;
  min-height: 68px;
  padding: 10px 14px 10px 18px;
  background: var(--neutral-0);
  border: var(--border-soft);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: max-content;
  white-space: nowrap;
}

.brand-logo {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  overflow: hidden;
  position: relative;
  flex: none;
}

.brand-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

.brand:hover .brand-logo img { transform: scale(1.08) rotate(-2deg); }

.brand strong {
  font-size: 18px;
  color: var(--neutral-800);
  font-weight: 800;
  letter-spacing: 0;
}

.brand-badge {
  font-style: normal;
  font-size: var(--fs-tiny);
  padding: 3px 8px;
  border-radius: 999px;
  background: var(--orange-50);
  border: 1px solid var(--orange-100);
  color: var(--orange-700);
  font-weight: 700;
}

.topbar-search {
  flex: 1;
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 14px;
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  border: var(--border-soft);
  color: var(--neutral-400);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.topbar-search:focus-within {
  border-color: var(--orange-500);
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.12);
}

.topbar-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--neutral-700);
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.topbar-course-picker {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 40px;
  min-width: 146px;
  padding: 0 10px;
  border: var(--border-soft);
  border-radius: var(--radius-md);
  background: var(--neutral-0);
  color: var(--orange-700);
  transition: border-color 160ms ease-out, box-shadow 160ms ease-out, transform 180ms cubic-bezier(.16,1,.3,1);
}

.topbar-course-picker:hover { border-color: var(--orange-200); transform: translateY(-1px); }
.topbar-course-picker:focus-within { border-color: var(--orange-500); box-shadow: 0 0 0 3px rgba(234,90,26,.1); }
.topbar-course-picker select {
  min-width: 0;
  max-width: 156px;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--neutral-700);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.shell-navigation {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  min-height: 58px;
  padding: 8px 12px 9px;
  background: var(--neutral-0);
  border: var(--border-soft);
  border-top: 0;
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
  box-shadow: 0 8px 0 rgba(49, 42, 35, 0.08);
}

.topbar-icon-btn {
  position: relative;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  border: var(--border-soft);
  background: var(--neutral-0);
  color: var(--neutral-600);
  transition:
    background 180ms ease-out,
    border-color 180ms ease-out,
    color 180ms ease-out,
    transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.topbar-icon-btn:hover {
  background: var(--orange-50);
  border-color: var(--orange-200);
  color: var(--orange-700);
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 8px rgba(126, 52, 17, .12);
}

.topbar-icon-btn:active { transform: translateY(0) scale(.96); }
.topbar-icon-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px rgba(234, 90, 26, .16);
}

.topbar-icon-btn .dot {
  position: absolute;
  top: 6px;
  right: 7px;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--orange-500);
}

.topbar-user {
  display: flex;
  align-items: center;
  gap: 9px;
  height: 40px;
  padding: 0 8px 0 5px;
  border-radius: 999px;
  border: var(--border-soft);
  background: var(--neutral-0);
  transition:
    border-color 180ms ease-out,
    background 180ms ease-out,
    transform 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.topbar-user:hover {
  border-color: var(--orange-200);
  background: var(--orange-50);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(23, 32, 42, .08);
}

.logout-btn {
  width: 30px;
  height: 30px;
  border: 0;
  background: transparent;
}

.user-avatar {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--orange-500);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}

.user-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.user-copy b {
  font-size: var(--fs-body);
  color: var(--neutral-800);
}

.user-copy small {
  font-size: 10.5px;
  color: var(--muted);
}

.shell-body {
  grid-row: 2;
  min-width: 0;
  width: 100%;
  min-height: 0;
}

.new-task-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 40px;
  padding: 0 16px;
  border-radius: var(--radius-md);
  background: var(--orange-500);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  white-space: nowrap;
  box-shadow: var(--shadow-1);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}

.new-task-btn:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-3);
}

.shell-nav {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.shell-nav-scroll {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.shell-nav-scroll::-webkit-scrollbar {
  display: none;
}

@media (max-width: 1760px) {
  .student-workbench-shell .shell-navigation { gap: 8px; }
  .student-workbench-shell .shell-nav-scroll { gap: 1px; }
  .student-workbench-shell .shell-nav-item { gap: 7px; padding-inline: 8px; font-size: 12.5px; }
  .student-workbench-shell .nav-tools { padding-left: 5px; }
  .student-workbench-shell .nav-tools button { width: 31px; }
  .student-workbench-shell .nav-context { gap: 5px; padding-left: 8px; }
  .student-workbench-shell .progress-chip,
  .student-workbench-shell .agent-chip { gap: 5px; padding-inline: 8px; }
  .student-workbench-shell .progress-chip > i { width: 34px; }
}

@media (max-width: 1439px) {
  .student-workbench-shell .shell-nav-scroll {
    padding-right: 10px;
    mask-image: linear-gradient(90deg, #000 0, #000 calc(100% - 18px), transparent);
  }
  .student-workbench-shell .nav-context { display: none; }
}

.shell-nav-item {
  --nav-x: 50%;
  --nav-y: 50%;
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
  height: 38px;
  padding: 0 11px;
  border-radius: var(--radius-md);
  font-size: var(--fs-body);
  color: var(--neutral-600);
  text-decoration: none;
  transition:
    color 180ms cubic-bezier(0.16, 1, 0.3, 1),
    transform 180ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 180ms cubic-bezier(0.16, 1, 0.3, 1);
}

.shell-nav-item::before {
  content: "";
  position: absolute;
  inset: 3px;
  z-index: -1;
  border-radius: calc(var(--radius-md) - 2px);
  background:
    radial-gradient(circle 62px at var(--nav-x) var(--nav-y), rgba(234, 90, 26, .22), transparent 72%),
    var(--orange-50);
  transform: scale(.82);
  opacity: 0;
  transition:
    transform 200ms cubic-bezier(0.16, 1, 0.3, 1),
    opacity 160ms ease-out;
}

.shell-nav-item::after {
  content: "";
  position: absolute;
  right: 12px;
  bottom: 1px;
  left: 12px;
  height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--orange-500);
  transform: scaleX(0);
  transform-origin: center;
  transition: transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}

.shell-nav-item svg {
  transition:
    transform 200ms cubic-bezier(0.16, 1, 0.3, 1),
    color 160ms ease-out;
}

.shell-nav-item:hover {
  color: var(--orange-700);
  transform: translateY(-3px);
  box-shadow: 0 5px 8px rgba(126, 52, 17, .13);
}

.shell-nav-item:hover::before {
  opacity: 1;
  transform: scale(1);
}

.shell-nav-item:hover::after { transform: scaleX(.7); }

.shell-nav-item:hover svg {
  color: var(--orange-600);
  transform: translateY(-1px) scale(1.14) rotate(-4deg);
}

.shell-nav-item:active {
  transform: translateY(0) scale(.96);
  box-shadow: none;
  transition-duration: 80ms;
}

.shell-nav-item.active {
  color: var(--orange-700);
  font-weight: 700;
}

.shell-nav-item.active::before {
  opacity: 1;
  transform: scale(1);
}

.shell-nav-item.active::after { transform: scaleX(1); }

.shell-nav-item:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 2px rgba(234, 90, 26, .42);
}

.nav-context {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 14px;
  border-left: var(--border-soft);
}

.nav-tools {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
  padding-left: 8px;
  border-left: 1px solid #ece8e1;
}

.nav-tools button {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--neutral-500);
  cursor: pointer;
  transition: transform 170ms cubic-bezier(.16,1,.3,1), background-color 160ms ease-out, color 160ms ease-out;
}

.nav-tools button:hover {
  background: var(--orange-50);
  color: var(--orange-700);
  transform: translateY(-1px);
}

.progress-chip,
.agent-chip {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 11px;
  border-radius: var(--radius-md);
  background: var(--paper-2);
  border: var(--border-soft);
  color: var(--neutral-500);
  font-size: 12px;
  white-space: nowrap;
}

.progress-chip b,
.agent-chip b {
  color: var(--orange-700);
}

.progress-chip > i {
  display: block;
  width: 44px;
  height: 5px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--neutral-200);
}

.progress-chip > i span {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--orange-400), var(--orange-500));
  transform-origin: left center;
  transition: transform 0.32s ease;
}

.agent-chip {
  cursor: pointer;
  transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.agent-chip:hover {
  background: var(--orange-50);
  color: var(--orange-600);
  border-color: var(--orange-300);
}

/* ---------- 主区 ---------- */
.shell-main {
  height: 100%;
  min-width: 0;
  overflow: auto;
  padding: 28px 24px 24px;
  background: #f7f8fa;
}

/* 教师端与学习画像使用各自的工作台底色，避免共用壳层互相串色。 */
/* 教师端：浅暖白纸面背景，页面连续无卡片画布（Editorial Minimalism）。 */
.app-shell.teacher-shell,
.app-shell.student-workbench-shell,
.teacher-shell .shell-main,
.student-workbench-shell .shell-main {
  background: #fbfaf7;
}

/* 教师端首屏垂直节奏 Tokens：每段间距只允许一个来源，禁止多层叠加 */
.app-shell.teacher-shell,
.app-shell.student-workbench-shell {
  --header-top-height: 64px;
  --header-nav-height: 50px;
  /* 页头已去掉 Eyebrow，标题相应上移，避免导航下方过于空旷 */
  --header-content-gap: 28px;
  --content-max-width: 1540px;
  --content-padding-x: 24px;
}

/* Header：全宽白底两层 + 底部 1px 分割线，去掉悬浮圆角卡片外壳 */
.teacher-shell .shell-header,
.student-workbench-shell .shell-header {
  padding: 0;
  background: #fff;
  border-bottom: 1px solid #e8e4dd;
}

/* 品牌栏与二级导航使用与主内容一致的水平网格 */
.teacher-shell .shell-topbar,
.teacher-shell .shell-navigation,
.student-workbench-shell .shell-topbar,
.student-workbench-shell .shell-navigation {
  width: min(calc(100% - var(--content-padding-x) * 2), var(--content-max-width));
  margin-inline: auto;
  padding: 0;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

.teacher-shell .shell-topbar,
.student-workbench-shell .shell-topbar {
  min-height: var(--header-top-height);
}

.teacher-shell .shell-navigation,
.student-workbench-shell .shell-navigation {
  min-height: var(--header-nav-height);
  border-top: 1px solid #f1eee9;
}

/* Header 到内容的唯一间距来源（页面容器自身 padding-top 为 0） */
.teacher-shell .shell-main,
.student-workbench-shell .shell-main {
  padding: var(--header-content-gap) var(--content-padding-x) 24px;
}

@media (max-width: 1439px) {
  .app-shell.teacher-shell,
  .app-shell.student-workbench-shell {
    --header-top-height: 60px;
    --header-nav-height: 48px;
    --header-content-gap: 26px;
  }
}

@media (max-width: 1023px) {
  .app-shell.teacher-shell,
  .app-shell.student-workbench-shell {
    --header-content-gap: 24px;
  }
}

@media (max-width: 700px) {
  .app-shell.teacher-shell,
  .app-shell.student-workbench-shell {
    --header-content-gap: 20px;
    --content-padding-x: 12px;
  }
}

.shell-content {
  width: min(100%, 1540px);
  min-width: 0;
  min-height: 100%;
  margin-inline: auto;
}

/* 普通壳层页面统一使用首页的内容宽度；全屏路由不会经过 AppShell。 */
.shell-content > :deep(*) {
  width: 100% !important;
  max-width: 100% !important;
  margin-inline: 0 !important;
}

.teacher-content-canvas {
  --teacher-canvas: #fbfaf7;
  --teacher-canvas-soft: #f8f7f3;
  --teacher-surface: #ffffff;
  --teacher-line: #e5e1d9;
  --teacher-accent: #e85d16;
  min-height: 100%;
  overflow: clip;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.teacher-content-canvas :deep(:is(h1, h2, h3)) {
  text-wrap: balance;
}

.teacher-content-canvas :deep(:is(button, a, [role="button"], input, select, textarea):focus-visible) {
  outline: 3px solid rgba(233, 85, 20, .28);
  outline-offset: 2px;
}

.teacher-content-canvas :deep(:is(button, a, [role="button"]) svg) {
  transition: transform 190ms cubic-bezier(.16, 1, .3, 1), color 170ms ease-out;
}

.teacher-content-canvas :deep(:is(button, a, [role="button"]):hover svg) {
  transform: translateY(-1px) scale(1.08);
}

.teacher-content-canvas :deep(:is(button, a, [role="button"]):active svg) {
  transform: scale(.94);
}

.teacher-content-canvas :deep(:is(.secondary-button, .dark-button, .appbar-action, .ghost-btn, .btn-outlined, .btn-tonal, .btn-tonal-sm, .identity-actions button, .quick-actions button)) {
  background-image: linear-gradient(90deg, rgba(233, 85, 20, .09) 0 50%, transparent 50% 100%);
  background-position: 100% 0;
  background-size: 205% 100%;
  transition: background-position 220ms cubic-bezier(.16, 1, .3, 1), transform 190ms cubic-bezier(.16, 1, .3, 1), border-color 170ms ease-out, color 170ms ease-out, box-shadow 190ms ease-out;
}

.teacher-content-canvas :deep(:is(.secondary-button, .dark-button, .appbar-action, .ghost-btn, .btn-outlined, .btn-tonal, .btn-tonal-sm, .identity-actions button, .quick-actions button):hover) {
  background-position: 0 0;
}

.teacher-content-canvas :deep(:is(.surface, .student-identity, .evidence-panel, .advice-panel, .safety-block, .settings-card, .side-card)) {
  transition: transform 200ms cubic-bezier(.16, 1, .3, 1), border-color 180ms ease-out, background-color 180ms ease-out, box-shadow 200ms ease-out;
}

.teacher-content-canvas :deep(:is(.surface, .student-identity, .evidence-panel, .advice-panel, .safety-block, .settings-card, .side-card):hover) {
  transform: translateY(-1px);
  border-color: #c9c4ba;
}

.app-shell.profile-shell,
.profile-shell .shell-main {
  background: #fff;
}

@media (max-width: 1180px) {
  .shell-topbar {
    flex-wrap: wrap;
    gap: 12px;
  }

  .topbar-search {
    order: 3;
    flex-basis: 100%;
    max-width: none;
    margin: 0;
  }

  .topbar-actions {
    margin-left: auto;
  }

  .nav-context {
    display: none;
  }
}

@media (max-width: 700px) {
  .shell-header {
    padding: 8px 8px 0;
  }

  .shell-topbar {
    padding: 9px 10px;
  }

  .brand-badge,
  .user-copy {
    display: none;
  }

  .topbar-actions { gap: 4px; }
  .topbar-course-picker { min-width: 92px; width: 92px; padding-inline: 7px; }
  .topbar-course-picker > svg { display: none; }
  .topbar-course-picker select { max-width: 76px; font-size: 11px; }

  .topbar-user {
    padding-right: 4px;
  }

  .new-task-btn {
    width: 40px;
    padding: 0;
  }

  .new-task-btn span {
    display: none;
  }

  .shell-navigation {
    padding-inline: 8px;
  }

  .shell-nav-item {
    height: 36px;
  }

  .shell-main {
    padding: 20px 12px 16px;
  }

  .teacher-content-canvas {
    border-radius: 14px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .notice-fade-enter-active,
  .notice-fade-leave-active,
  .new-task-btn,
  .brand-logo img,
  .topbar-icon-btn,
  .topbar-user,
  .shell-nav-item,
  .shell-nav-item::before,
  .shell-nav-item::after,
  .shell-nav-item svg,
  .agent-chip,
  .progress-chip > i span {
    transition-duration: 0.01ms;
  }

  .teacher-content-canvas,
  .teacher-content-canvas :deep(*) {
    scroll-behavior: auto !important;
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
</style>
