import { createRouter, createWebHistory } from "vue-router";

import { getCurrentUser } from "@/api/auth";
import { clearAuthSession, isAuthenticated, isPreviewSession, isTeacherRole } from "@/utils/auth";
import IntegratedMapView from "@/views/IntegratedMapView.vue";
import LoginView from "@/views/LoginView.vue";
import LogoutView from "@/views/LogoutView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { title: "登录系统" },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/views/RegisterView.vue"),
      meta: { title: "构建初始学习画像" },
    },
    {
      path: "/logout",
      name: "logout",
      component: LogoutView,
      meta: { title: "退出登录" },
    },
    {
      path: "/",
      redirect: () => (isTeacherRole() ? { name: "teacher" } : { name: "home" }),
    },
    {
      path: "/home",
      name: "home",
      component: () => import("@/views/HomeView.vue"),
      meta: { title: "首页", shell: true },
    },
    {
      // 教师管理台：学情分析 / 课程资源 / Agent 管理 / 路径推荐 / 群聊消息
      path: "/teacher",
      name: "teacher",
      component: () => import("@/views/TeacherOverviewView.vue"),
      meta: { title: "教师管理台", shell: true, teacherOnly: true },
    },
    {
      // 知识库平台化（2026-07-16）：教师自主建课 + 上传文档 + 命中测试
      path: "/teacher/kb",
      name: "teacher-kb",
      component: () => import("@/views/TeacherKnowledgeBaseView.vue"),
      meta: { title: "课程知识库", shell: true, teacherOnly: true, teacherSection: "kb" },
    },
    {
      path: "/teacher/knowledge",
      name: "teacher-knowledge",
      component: () => import("@/views/TeacherView.vue"),
      meta: { title: "知识图谱", shell: true, teacherOnly: true, teacherSection: "overview", teacherTab: "knowledge-map" },
    },
    {
      path: "/teacher/students",
      name: "teacher-students",
      component: () => import("@/views/TeacherStudentsView.vue"),
      meta: { title: "学生分析", shell: true, teacherOnly: true, teacherSection: "students" },
    },
    {
      path: "/teacher/resources",
      name: "teacher-resources",
      component: () => import("@/views/TeacherView.vue"),
      meta: { title: "教学资源", shell: true, teacherOnly: true, teacherSection: "resources" },
    },
    {
      path: "/teacher/studio",
      name: "teacher-studio",
      component: () => import("@/views/TeacherView.vue"),
      meta: { title: "教学提示与视频", shell: true, teacherOnly: true, teacherSection: "studio" },
    },
    {
      path: "/teacher/interventions",
      name: "teacher-interventions",
      component: () => import("@/views/TeacherView.vue"),
      meta: { title: "教学干预", shell: true, teacherOnly: true, teacherSection: "interventions" },
    },
    {
      path: "/teacher/agents",
      name: "teacher-agents",
      component: () => import("@/views/TeacherView.vue"),
      meta: { title: "Agent 协作", shell: true, teacherOnly: true, teacherSection: "agents" },
    },
    {
      path: "/dashboard",
      name: "dashboard",
      component: () => import("@/views/DashboardView.vue"),
      meta: { title: "学习大屏", shell: false, studentOnly: true },
    },
    {
      path: "/path",
      name: "path",
      component: () => import("@/views/PathView.vue"),
      meta: { title: "学习路径", shell: true },
    },
    {
      path: "/resources",
      name: "resources",
      component: () => import("@/views/ResourcesView.vue"),
      meta: { title: "资源库", shell: true },
    },
    {
      path: "/workflow",
      name: "workflow",
      component: () => import("@/views/WorkflowView.vue"),
      meta: { title: "Agent 编排", shell: true },
    },
    {
      path: "/learning-package",
      name: "learning-package",
      component: () => import("@/views/LearningPackageView.vue"),
      meta: { title: "讲解与练习", shell: true },
    },
    {
      path: "/mistakes",
      name: "mistakes",
      component: () => import("@/views/MistakesView.vue"),
      meta: { title: "错题本", shell: true },
    },
    {
      path: "/graph",
      name: "graph",
      component: () => import("@/views/GraphView.vue"),
      meta: { title: "知识图谱", shell: true, studentOnly: true },
    },
    {
      path: "/profile",
      name: "profile",
      component: () => import("@/views/ProfileView.vue"),
      meta: { title: "学习画像", shell: true },
    },
    {
      // 安全中心属教学管理职责，已迁入教师端（学生角色访问会被守卫弹回）
      path: "/safety",
      name: "safety",
      component: () => import("@/views/SafetyView.vue"),
      meta: { title: "安全中心", shell: true, teacherOnly: true },
    },
    {
      path: "/evidence",
      name: "evidence",
      component: () => import("@/views/EvidenceView.vue"),
      meta: { title: "学习工具箱", shell: true },
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/views/SettingsView.vue"),
      meta: { title: "设置中心", shell: true },
    },
    {
      // Plan D · 3.2 — ChatBubble 组件演示页（Phase 2 正式挂到原生 chat）
      path: "/chat-bubble-demo",
      name: "chat-bubble-demo",
      component: () => import("@/views/ChatBubbleDemoView.vue"),
      meta: { title: "ChatBubble Demo", shell: true },
    },
    {
      // Plan D · 4.2 — Vue 原生 ChatView（Phase 2：替代 React iframe integrated-map）
      path: "/chat",
      name: "chat",
      component: () => import("@/views/ChatView.vue"),
      meta: { title: "群聊协作", shell: false },
    },
    {
      // Plan D · 4.2 — Vue 原生 ChatView demo（离线 mock，不需要后端）
      path: "/chat-demo",
      name: "chat-demo",
      component: () => import("@/views/ChatView.vue"),
      meta: { title: "Chat Demo (mock)", shell: false },
    },
    {
      // 实验场像素校园：全屏承载既有静态构建，游戏本体不做改动
      path: "/playground",
      name: "playground",
      component: () => import("@/views/PlaygroundView.vue"),
      meta: { title: "桃园学宫" },
    },
    {
      path: "/integrated-map",
      name: "integrated-map",
      component: IntegratedMapView,
      meta: { title: "AI Learning Companion (Legacy)" },
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: { name: "home" },
    },
  ],
});

let authVerified = false;
// 防止快速连续导航时多个 beforeEach 并发调用 getCurrentUser，
// 导致 authVerified 状态不一致（竞态条件 → 白屏）。
let authVerifyPromise: Promise<boolean> | null = null;

/** 登录后的默认首页：教师/管理员进管理台，学生进学生首页 */
function defaultHomeRoute() {
  return isTeacherRole() ? { name: "teacher" } : { name: "home" };
}

/** 单次并发安全地验证 token：多次导航只发一次请求 */
function verifyAuthOnce(): Promise<boolean> {
  if (authVerifyPromise) return authVerifyPromise;
  authVerifyPromise = getCurrentUser()
    .then(() => {
      authVerified = true;
      return true;
    })
    .catch(() => {
      authVerified = false;
      clearAuthSession();
      return false;
    })
    .finally(() => {
      authVerifyPromise = null;
    });
  return authVerifyPromise;
}

router.beforeEach(async (to) => {
  const loggedIn = isAuthenticated();
  const previewMode = isPreviewSession();

  if (to.name === "login" || to.name === "register") {
    if (!loggedIn) {
      return true;
    }
    if (previewMode) {
      authVerified = true;
      return defaultHomeRoute();
    }
    const ok = await verifyAuthOnce();
    return ok ? defaultHomeRoute() : true;
  }

  if (to.name === "logout") {
    return true;
  }

  if (!loggedIn) {
    authVerified = false;
    return { name: "login" };
  }

  // 教师专属页面：学生角色访问 /teacher 一律回学生首页
  if (to.meta.teacherOnly && !isTeacherRole()) {
    return { name: "home" };
  }

  // 教师端不复用个人学习大屏、个人知识图谱和个人认知分析。
  // 这些页面的 userId 语义是"当前学习者"，教师应进入班级态势与学生诊断。
  if (to.meta.studentOnly && isTeacherRole()) {
    return { name: "teacher" };
  }

  if (previewMode) {
    authVerified = true;
    return true;
  }

  if (authVerified) {
    return true;
  }

  const ok = await verifyAuthOnce();
  return ok ? true : { name: "login" };
});

router.afterEach((to) => {
  document.title = `${String(to.meta.title || "triple U")} | A3`;
});

export default router;
