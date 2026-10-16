<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/http";
import { loginByPassword } from "@/api/auth";
import { useSession } from "@/composables/useSession";
import OrbitDiagram from "@/components/base/OrbitDiagram.vue";
import RoleSelector from "@/components/base/RoleSelector.vue";
import type { RoleCard, RoleKind } from "@/components/base";
import { PREVIEW_ACCESS_TOKEN, setAuthSession } from "@/utils/auth";
import { Bell, HelpCircle, User } from "lucide-vue-next";

import plannerImg from "@/assets/login-avatars/planner.png";
import contentImg from "@/assets/login-avatars/content.png";
import tutorImg from "@/assets/login-avatars/tutor.png";
import quizImg from "@/assets/login-avatars/quiz.png";
import evaluationImg from "@/assets/login-avatars/evaluation.png";
import safetyImg from "@/assets/login-avatars/safety.png";

const router = useRouter();
const { refreshUser, resetChatSession } = useSession();



// 教师与管理员身份已合并（2026-07-16）：功能完全一致，统一走「教师」入口，
// admin 账号仍可在此登录，后端会话角色归一化为 teacher
const roles: RoleCard[] = [
  { kind: "student", index: "01", title: "学习者", subtitle: "LEARNER", account: "demo-student-1" },
  { kind: "teacher", index: "02", title: "教师 · 管理员", subtitle: "TEACHER / ADMIN", account: "teacher" },
];

const activeRole = ref<RoleKind>("student");

const form = reactive({
  account: roles[0].account,
  password: "123456",
  remember: true,
});

const loading = ref(false);
const errorMessage = ref("");

// 顶部导航：关于我们/消息中心/帮助弹窗 + 资源中心登录后跳转意图
const aboutVisible = ref(false);
const messagesVisible = ref(false);
const helpVisible = ref(false);
const notifyOpen = ref(false);
const userOpen = ref(false);
const noticesRead = ref(false);
const navHint = ref("");
const pendingRedirect = ref<string | null>(null);

const entryCardRef = ref<HTMLElement | null>(null);
const accountRef = ref<HTMLInputElement | null>(null);

function focusLogin() {
  entryCardRef.value?.scrollIntoView({ behavior: "smooth", block: "center" });
  accountRef.value?.focus();
}

function requestPageAfterLogin(path: string, label: string) {
  pendingRedirect.value = path;
  navHint.value = `「${label}」需登录后访问，登录成功将自动前往`;
  focusLogin();
}

function resetNavIntent() {
  pendingRedirect.value = null;
  navHint.value = "";
}

function closePopovers() {
  notifyOpen.value = false;
  userOpen.value = false;
}

function toggleNotify() {
  notifyOpen.value = !notifyOpen.value;
  userOpen.value = false;
  if (notifyOpen.value) noticesRead.value = true;
}

function toggleUser() {
  userOpen.value = !userOpen.value;
  notifyOpen.value = false;
}

function openMessages() {
  closePopovers();
  messagesVisible.value = true;
}

function loginForMessages() {
  messagesVisible.value = false;
  requestPageAfterLogin("/chat", "消息中心");
}

const currentRole = computed(() => roles.find((r) => r.kind === activeRole.value) ?? roles[0]);

function selectRole(kind: RoleKind) {
  activeRole.value = kind;
  const role = roles.find((r) => r.kind === kind);
  if (role) {
    form.account = role.account;
    form.password = "123456";
    errorMessage.value = "";
  }
}

function homeByRole(role: string): string {
  return role === "teacher" || role === "admin" ? "/teacher" : "/home";
}

function enterPreviewSession(account: string, displayName: string) {
  setAuthSession({
    accessToken: PREVIEW_ACCESS_TOKEN,
    tokenType: "bearer",
    expiresAt: new Date(Date.now() + 8 * 3600 * 1000).toISOString(),
    account,
    displayName,
    role: "student",
    loginAt: new Date().toISOString(),
    remember: form.remember,
  });
  refreshUser();
  resetChatSession();
  router.push(pendingRedirect.value ?? "/home");
}

async function handleEnter() {
  errorMessage.value = "";
  if (loading.value) return;

  if (!form.account || !form.password) {
    errorMessage.value = "请输入账号和访问密码";
    return;
  }

  loading.value = true;
  try {
    const payload = await loginByPassword({
      account: form.account.trim(),
      password: form.password,
      role: activeRole.value,
      remember: form.remember,
    });
    setAuthSession({
      accessToken: payload.access_token,
      tokenType: payload.token_type,
      expiresAt: payload.expires_at,
      account: payload.user.account,
      displayName: payload.user.display_name,
      role: payload.user.role,
      loginAt: new Date().toISOString(),
      remember: form.remember,
    });
    refreshUser();
    resetChatSession();
    router.push(pendingRedirect.value ?? homeByRole(payload.user.role));
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.detail === "account_not_found") errorMessage.value = "账号不存在";
      else if (error.detail === "password_invalid") errorMessage.value = "密码错误";
      else if (error.detail === "role_mismatch") errorMessage.value = "账号与所选身份不匹配";
      else errorMessage.value = error.detail || "登录失败，请稍后重试";
    } else {
      // 后端未启动时，学习者身份可退化为本地预览
      if (activeRole.value === "student") {
        enterPreviewSession(form.account || "demo-student-1", "杜同学");
        return;
      }
      errorMessage.value = "网络异常，请稍后重试";
    }
  } finally {
    loading.value = false;
  }
}

function previewDirectly() {
  enterPreviewSession("demo-student-1", "直接预览");
}

function openRegistration() {
  router.push("/register");
}

interface AgentNode {
  cls: string;
  img: string;
  name: string;
  english: string;
}

const agentNodes: AgentNode[] = [
  { cls: "agent-planner",    img: plannerImg,    name: "小狐规划", english: "Planner Agent" },
  { cls: "agent-content",    img: contentImg,    name: "河狸工匠", english: "Content Agent" },
  { cls: "agent-tutor",      img: tutorImg,      name: "猫头讲师", english: "Tutor Agent" },
  { cls: "agent-safety",     img: safetyImg,     name: "刺猬守护", english: "Safety Agent" },
  { cls: "agent-evaluation", img: evaluationImg, name: "熊猫评分", english: "Evaluation Agent" },
  { cls: "agent-quiz",       img: quizImg,       name: "小龙挑战", english: "Quiz Agent" },
];

// 消息中心演示数据：登录前展示 Agent 消息样例
interface MockMessage {
  avatar: string;
  from: string;
  text: string;
  time: string;
  unread?: boolean;
}

const mockMessages: MockMessage[] = [
  { avatar: tutorImg,      from: "猫头讲师", text: "你的「函数与极限」个性化讲解已生成，登录后可继续学习。", time: "今天 09:32", unread: true },
  { avatar: evaluationImg, from: "熊猫评分", text: "本周练习报告已出炉：正确率较上周提升 12%，继续保持！", time: "昨天 20:15", unread: true },
  { avatar: plannerImg,    from: "小狐规划", text: "学习路径已更新，建议优先完成「导数的应用」小节。", time: "昨天 18:02" },
  { avatar: quizImg,       from: "小龙挑战", text: "新的闯关练习「极限计算 · 第 3 关」已解锁，快来挑战。", time: "2 天前" },
  { avatar: safetyImg,     from: "刺猬守护", text: "系统公告：triple U 公网体验版已上线，欢迎反馈使用建议。", time: "3 天前" },
];

const mockNotices = [
  { title: "公网体验版上线", text: "triple U v0.1 已部署，功能持续更新中", time: "今天" },
  { title: "演示账号可用", text: "demo-student-1（密码 123456）可直接体验", time: "今天" },
  { title: "新功能开放", text: "群聊协作、资源中心与学习大屏已开放", time: "2 天前" },
];

const passwordRef = ref<HTMLInputElement | null>(null);

function onDocumentClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(".top-actions")) closePopovers();
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key !== "Escape") return;
  closePopovers();
  aboutVisible.value = false;
  messagesVisible.value = false;
  helpVisible.value = false;
}

onMounted(() => {
  if (activeRole.value !== "student") passwordRef.value?.focus();
  document.addEventListener("click", onDocumentClick);
  document.addEventListener("keydown", onDocumentKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("click", onDocumentClick);
  document.removeEventListener("keydown", onDocumentKeydown);
});
</script>

<template>
  <main class="page">
    <div class="paper-noise" aria-hidden="true"></div>

    <svg class="botany botany-left" viewBox="0 0 420 420" aria-hidden="true">
      <g fill="none" stroke="#cbbca7" stroke-width="2" opacity=".48">
        <path d="M52 365C110 276 105 188 68 91"/>
        <path d="M154 390C198 285 188 218 145 143"/>
        <path d="M282 400C255 300 283 214 348 128"/>
      </g>
      <g opacity=".58">
        <ellipse cx="65"  cy="286" rx="54" ry="15" fill="#b9baaa" transform="rotate(-34 65 286)"/>
        <ellipse cx="128" cy="237" rx="52" ry="14" fill="#d7c5aa" transform="rotate(26 128 237)"/>
        <ellipse cx="172" cy="312" rx="62" ry="17" fill="#a4aa9a" transform="rotate(-22 172 312)"/>
        <ellipse cx="246" cy="318" rx="55" ry="15" fill="#cec5b3" transform="rotate(31 246 318)"/>
      </g>
      <g opacity=".7">
        <circle cx="84"  cy="354" r="22" fill="#f1d8bd"/>
        <circle cx="110" cy="360" r="22" fill="#fff2df"/>
        <circle cx="96"  cy="336" r="22" fill="#fff8ed"/>
        <circle cx="98"  cy="357" r="10" fill="#d49a55"/>
        <circle cx="292" cy="360" r="18" fill="#f3dcc4"/>
        <circle cx="314" cy="365" r="18" fill="#fff5e9"/>
        <circle cx="302" cy="345" r="18" fill="#edceb0"/>
        <circle cx="303" cy="361" r="8"  fill="#ca8e4a"/>
      </g>
    </svg>

    <svg class="botany botany-right" viewBox="0 0 360 520" aria-hidden="true">
      <g fill="none" stroke="#d2c0aa" stroke-width="2" opacity=".42">
        <path d="M184 506C207 384 190 256 126 88"/>
        <path d="M188 410C246 332 288 264 308 162"/>
        <path d="M152 338C94 290 62 228 46 136"/>
      </g>
      <g opacity=".40">
        <ellipse cx="108" cy="140" rx="66" ry="18" fill="#c8c3b0" transform="rotate(51 108 140)"/>
        <ellipse cx="156" cy="220" rx="72" ry="20" fill="#abae9d" transform="rotate(-51 156 220)"/>
        <ellipse cx="206" cy="286" rx="74" ry="20" fill="#d5c5a9" transform="rotate(34 206 286)"/>
        <ellipse cx="272" cy="226" rx="60" ry="17" fill="#b0b29f" transform="rotate(-36 272 226)"/>
      </g>
    </svg>

    <div class="silk silk-a" aria-hidden="true"></div>
    <div class="silk silk-b" aria-hidden="true"></div>

    <header class="topbar">
      <a class="brand" href="#" aria-label="triple U">
        <img class="brand-icon" src="/logo.png" alt="triple U" />
        <span>triple U</span>
      </a>
      <nav class="main-nav">
        <a href="#" class="active" @click.prevent="resetNavIntent">首页</a>
        <a href="#" @click.prevent="openMessages">消息中心</a>
        <a href="#" @click.prevent="requestPageAfterLogin('/resources', '资源中心')">资源中心</a>
        <a href="#" @click.prevent="aboutVisible = true">关于我们</a>
      </nav>

      <div class="top-actions">
        <button aria-label="通知" :class="{ on: notifyOpen }" @click="toggleNotify">
          <Bell :size="18" stroke-width="2.5" />
          <i v-if="!noticesRead" class="badge-dot" aria-hidden="true"></i>
        </button>
        <button aria-label="帮助" @click="helpVisible = true"><HelpCircle :size="18" stroke-width="2.5" /></button>
        <button aria-label="用户" :class="{ on: userOpen }" @click="toggleUser"><User :size="18" stroke-width="2.5" /></button>

        <Transition name="pop">
          <div v-if="notifyOpen" class="popover" role="menu" aria-label="通知列表">
            <p class="pop-title">通知</p>
            <ul class="notice-list">
              <li v-for="notice in mockNotices" :key="notice.title">
                <b>{{ notice.title }}</b>
                <span>{{ notice.text }}</span>
                <time>{{ notice.time }}</time>
              </li>
            </ul>
          </div>
        </Transition>

        <Transition name="pop">
          <div v-if="userOpen" class="popover user-pop" role="menu" aria-label="用户菜单">
            <div class="user-head">
              <span class="user-avatar"><User :size="20" stroke-width="2" /></span>
              <div>
                <b>访客</b>
                <small>未登录 · 登录后可同步学习进度</small>
              </div>
            </div>
            <button class="pop-btn pop-btn-primary" @click="closePopovers(); focusLogin()">去登录</button>
            <button class="pop-btn" @click="closePopovers(); previewDirectly()">游客直接预览</button>
          </div>
        </Transition>
      </div>
    </header>

    <section class="layout">
      <div class="hero">
        <div class="copy">
          <h1>让每个学生<br/>拥有<span>适合自己</span>的学习路径</h1>
          <p>系统围绕学生的学习目标，协同完成路径规划、知识讲解、资源生成、练习反馈、<br/>学习评估与过程守护，形成可持续调整的个性化学习体验。</p>
        </div>

        <OrbitDiagram :nodes="agentNodes" />
      </div>

      <aside ref="entryCardRef" class="entry-card">
        
        <h2>开始本次体验</h2>
        <p class="entry-subtitle">选择身份登录，开启个性化学习之旅</p>

        <p v-if="navHint" class="nav-hint">{{ navHint }}</p>

        <RoleSelector :roles="roles" :active-role="activeRole" @select="selectRole" />

        <form class="login-form" @submit.prevent="handleEnter">
          <label>
            <span>账号</span>
            <div class="field">
              <input
                ref="accountRef"
                v-model="form.account"
                type="text"
                autocomplete="username"
                :placeholder="currentRole.account"
              />
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M20 21a8 8 0 0 0-16 0M12 13a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z"
                      fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
          </label>
          <label>
            <span>访问密码</span>
            <div class="field">
              <input
                ref="passwordRef"
                v-model="form.password"
                type="password"
                autocomplete="current-password"
                placeholder="••••••"
              />
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 3l18 18M10.6 10.6A2 2 0 0 0 13.4 13.4M9.9 4.2A9.7 9.7 0 0 1 12 4c6 0 9.5 6 9.5 6s-.8 1.4-2.3 2.8M6.2 6.2C3.8 7.7 2.5 10 2.5 10s3.5 6 9.5 6c1.3 0 2.5-.3 3.5-.7"
                      fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
          </label>
          <label class="remember">
            <input v-model="form.remember" type="checkbox" />
            <span>记住身份</span>
          </label>

          <p v-if="errorMessage" class="error-banner">⚠ {{ errorMessage }}</p>

          <button class="primary" type="submit" :disabled="loading">
            {{ loading ? "进入中…" : "进入系统" }} <span>→</span>
          </button>
          <button class="secondary" type="button" @click="openRegistration">
            注册
          </button>
        </form>

        <div class="form-footer">
          <a href="#" class="forgot-pwd">忘记密码？</a>
        </div>
      </aside>
    </section>

    <Transition name="fade">
      <div v-if="aboutVisible" class="about-mask" @click.self="aboutVisible = false">
        <div class="about-modal" role="dialog" aria-modal="true" aria-label="关于我们">
          <button class="about-close" aria-label="关闭" @click="aboutVisible = false">×</button>
          <h3>关于我们</h3>
          <p class="about-headline">第十五届中国软件杯大赛 —— A组赛题</p>
          <ul class="about-list">
            <li><span>赛题名称</span>基于大模型的个性化资源生成与学习多智能体系统开发</li>
            <li><span>组类</span>A组（本科、研究生、高职）</li>
            <li><span>出题企业</span>科大讯飞股份有限公司</li>
            <li><span>团队编号</span>44015640</li>
            <li><span>团队名</span>triple U</li>
          </ul>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div v-if="messagesVisible" class="about-mask" @click.self="messagesVisible = false">
        <div class="about-modal msg-modal" role="dialog" aria-modal="true" aria-label="消息中心">
          <button class="about-close" aria-label="关闭" @click="messagesVisible = false">×</button>
          <h3>消息中心</h3>
          <p class="about-headline">各位 Agent 伙伴给你留了新消息</p>
          <ul class="msg-list">
            <li v-for="msg in mockMessages" :key="msg.from + msg.time">
              <img :src="msg.avatar" :alt="msg.from" />
              <div class="msg-body">
                <div class="msg-head">
                  <b>{{ msg.from }}</b>
                  <time>{{ msg.time }}</time>
                </div>
                <p>{{ msg.text }}</p>
              </div>
              <i v-if="msg.unread" class="msg-unread" aria-label="未读"></i>
            </li>
          </ul>
          <button class="msg-login-btn" @click="loginForMessages">登录查看全部消息 →</button>
        </div>
      </div>
    </Transition>

    <Transition name="fade">
      <div v-if="helpVisible" class="about-mask" @click.self="helpVisible = false">
        <div class="about-modal" role="dialog" aria-modal="true" aria-label="帮助中心">
          <button class="about-close" aria-label="关闭" @click="helpVisible = false">×</button>
          <h3>帮助中心</h3>
          <p class="about-headline">快速上手指南</p>
          <ol class="help-steps">
            <li>在右侧登录卡片选择身份：<b>学习者</b> / <b>教师 · 管理员</b>（两者已合并，功能一致）。</li>
            <li>使用演示账号登录（访问密码均为 <code>123456</code>）。</li>
            <li>学习者可体验路径规划、AI 讲解、闯关练习、错题本与学习报告。</li>
            <li>教师进入管理台，可维护课程知识库、查看学情分析与 Agent 协作。</li>
          </ol>
          <div class="help-accounts">
            <div><span>学习者</span><code>demo-student-1</code></div>
            <div><span>教师</span><code>teacher</code></div>
            <div><span>管理员（同教师）</span><code>admin</code></div>
          </div>
          <p class="help-tip">想了解团队与赛题信息？点击顶部导航的「关于我们」。</p>
        </div>
      </div>
    </Transition>
  </main>
</template>

<style scoped lang="scss">
.page {
  --orange: #e95514;
  --orange-dark: #d9460b;
  --ink: #171d22;
  --serif-cn: "Songti SC", "SimSun", "STSong", "Noto Serif CJK SC", Georgia, serif;
  --sans-cn: "Inter", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;

  position: relative;
  min-height: 100vh;
  padding: 2vh 3.5vw 2vh;
  overflow-x: hidden;
  font-family: var(--sans-cn);
  color: var(--ink);
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at 62% 30%, rgba(255, 210, 141, .14), transparent 40%),
    radial-gradient(circle at 18% 88%, rgba(238, 203, 158, .15), transparent 34%),
    linear-gradient(118deg, #fffdf8 0%, #fdf5ec 55%, #f8edd9 100%);
}

* { box-sizing: border-box; }

.paper-noise {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: .22;
  background-image:
    radial-gradient(rgba(164, 125, 83, .15) .7px, transparent .7px),
    radial-gradient(rgba(255,255,255,.75) .8px, transparent .8px);
  background-position: 0 0, 12px 15px;
  background-size: 24px 24px;
}

.botany {
  position: absolute;
  pointer-events: none;
  z-index: 0;
}
.botany-left  { left: -8px; bottom: 0; width: 340px; }
.botany-right { right: 520px; top: 80px; width: 300px; opacity: .38; }

.silk {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(222, 170, 109, .10), transparent);
  transform: rotate(-22deg);
}
.silk-a { left: -60px; top: 330px; width: 880px; height: 100px; }
.silk-b { left: 500px; top: 440px; width: 720px; height: 120px; opacity: .5; }

.topbar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 14px;
  color: var(--ink);
  text-decoration: none;
  font-family: "Inter", "PingFang SC", "Microsoft YaHei", Arial, sans-serif;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -.02em;
}
.brand span {
  background: linear-gradient(135deg, #1a1a1a 0%, #555 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.brand-icon { width: 34px; height: 34px; flex: 0 0 auto; border-radius: 8px; object-fit: cover; }

.main-nav {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 48px;
}
.main-nav a {
  text-decoration: none;
  color: #1d2024;
  font-size: 15px;
  font-weight: 600;
  opacity: 0.85;
  transition: opacity 0.2s, color 0.2s;
  position: relative;
}
.main-nav a:hover, .main-nav a.active {
  opacity: 1;
  color: var(--orange);
}
.main-nav a.active::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: -8px;
  width: 16px;
  height: 2px;
  background: var(--orange);
  transform: translateX(-50%);
  border-radius: 2px;
}

.top-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 16px;
}
.top-actions button {
  position: relative;
  background: transparent;
  border: none;
  cursor: pointer;
  color: #1d2024;
  opacity: 0.7;
  padding: 4px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s, background 0.2s;
}
.top-actions button:hover,
.top-actions button.on {
  opacity: 1;
  background: rgba(0, 0, 0, 0.05);
}
.top-actions button:last-child {
  border: 1px solid rgba(0, 0, 0, 0.1);
  padding: 6px;
}

.layout {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) auto;
  gap: 1.2vw;
  align-items: center;
  padding-top: 1vh;
}

.hero {
  min-height: 0;
  overflow: visible;
}

.copy {
  margin-bottom: 2.5vh;
}

.copy h1 {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: clamp(26px, 3.2vw, 62px);
  line-height: 1.15;
  letter-spacing: -.04em;
  font-weight: 900;
}
.copy h1 span { color: var(--orange); padding: 0 8px; }
.copy p {
  margin: 1vh 0 0;
  color: #62666a;
  font-size: clamp(12px, 1vw, 15px);
  line-height: 1.7;
  font-weight: 500;
}

.entry-card {
  position: relative;
  width: clamp(370px, 28vw, 500px);
  padding: clamp(18px, 2.2vh, 34px) clamp(20px, 1.8vw, 32px) clamp(16px, 1.8vh, 28px);
  border: 1px solid rgba(171, 111, 65, .36);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(255,255,255,.96), rgba(255,251,245,.95)),
    rgba(255,255,255,.94);
  box-shadow: 0 30px 80px rgba(105, 70, 35, .13);
}

.entry-card h2 {
  margin: 0 0 2px;
  font-family: var(--serif-cn);
  font-size: clamp(20px, 1.6vw, 26px);
  font-weight: 900;
  text-align: center;
}

.entry-subtitle {
  text-align: center;
  color: #62666a;
  font-size: 13px;
  margin: 0 0 clamp(8px, 1.2vh, 18px);
}

.role-list { display: grid; gap: clamp(5px, 0.6vh, 10px); margin-bottom: clamp(8px, 1vh, 16px); }

.role {
  width: 100%;
  display: grid;
  grid-template-columns: 50px 1fr 24px;
  align-items: center;
  min-height: clamp(46px, 5.5vh, 66px);
  border: 1px solid rgba(29, 32, 36, .1);
  border-radius: 8px;
  background: rgba(255,255,255,.86);
  text-align: left;
  padding: 0 18px;
  cursor: pointer;
  transition: .2s ease;
  font-family: inherit;
  color: inherit;
}
.role.active {
  border-color: rgba(233, 85, 20, .72);
  background: linear-gradient(180deg, rgba(255,250,243,.98), rgba(255,247,236,.98));
  box-shadow: inset 0 0 0 1px rgba(233, 85, 20, .12);
}
.role strong { color: #1d2024; font-size: 16px; }
.role.active strong { color: var(--orange); }
.role b { display: block; font-size: 17px; line-height: 1.5; }
.role small { display: block; color: #6f7276; font-size: 13px; }
.role i {
  justify-self: end;
  width: 18px;
  height: 18px;
  border: 2px solid #c9c0b6;
  border-radius: 99px;
}
.role.active i {
  border: 2px solid var(--orange);
  box-shadow: inset 0 0 0 4px #fff;
  background: var(--orange);
}

.login-form label { display: block; margin-top: clamp(6px, 1vh, 14px); }
.login-form label > span {
  display: block;
  font-size: 14px;
  font-weight: 800;
  margin-bottom: clamp(3px, 0.5vh, 7px);
}

.field {
  display: flex;
  align-items: center;
  height: clamp(36px, 4vh, 44px);
  border: 1px solid rgba(37, 44, 48, .12);
  border-radius: 7px;
  background: rgba(255,255,255,.9);
  padding: 0 14px;
}
.field input {
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: #22272c;
  font-size: 14px;
  font-family: inherit;
}
.field svg { width: 20px; height: 20px; color: #22272c; }

.login-form em {
  display: block;
  margin: 9px 0 0 12px;
  color: #b2a99d;
  font-size: 12px;
  font-style: normal;
}

.remember {
  display: flex !important;
  align-items: center;
  gap: 8px;
  margin-top: clamp(4px, 0.7vh, 12px) !important;
  color: #686d70;
  font-size: 14px;
  cursor: pointer;
}
.remember input {
  appearance: none;
  width: 17px;
  height: 17px;
  border-radius: 3px;
  background: #ffffff;
  border: 1.5px solid rgba(233, 85, 20, .5);
  display: inline-grid;
  place-items: center;
  margin: 0;
  cursor: pointer;
}
.remember input:checked {
  background: var(--orange);
  border-color: var(--orange);
}
.remember input:checked::after {
  content: "✓";
  color: white;
  font-size: 13px;
  line-height: 1;
  font-weight: 900;
}

.nav-hint {
  margin: 0 0 clamp(8px, 1vh, 14px);
  padding: 8px 12px;
  border-radius: 7px;
  background: rgba(233, 85, 20, .07);
  border-left: 3px solid var(--orange);
  color: #9a4a1a;
  font-size: 12.5px;
  line-height: 1.5;
}

.about-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(23, 29, 34, .45);
  backdrop-filter: blur(3px);
}

.about-modal {
  position: relative;
  width: min(560px, 100%);
  padding: 30px 34px 28px;
  border: 1px solid rgba(171, 111, 65, .36);
  border-radius: 14px;
  background: linear-gradient(180deg, #fffdf8, #fdf4e8);
  box-shadow: 0 30px 80px rgba(60, 40, 20, .3);
}

.about-modal h3 {
  margin: 0 0 6px;
  font-family: var(--serif-cn);
  font-size: 24px;
  font-weight: 900;
}

.about-headline {
  margin: 0 0 16px;
  color: var(--orange);
  font-size: 15px;
  font-weight: 800;
}

.about-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}
.about-list li {
  display: flex;
  gap: 12px;
  align-items: baseline;
  font-size: 14px;
  line-height: 1.6;
  color: #2a2e32;
}
.about-list li span {
  flex: 0 0 68px;
  color: #8a7e72;
  font-size: 13px;
  font-weight: 700;
}

.about-close {
  position: absolute;
  top: 12px;
  right: 14px;
  border: 0;
  background: transparent;
  color: #8a7e72;
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
  padding: 4px;
  transition: color .2s;
}
.about-close:hover { color: var(--orange); }

.fade-enter-active, .fade-leave-active { transition: opacity .2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* —— 消息中心弹窗 —— */
.msg-modal { width: min(600px, 100%); }

.msg-list {
  margin: 0 0 18px;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
  max-height: min(46vh, 400px);
  overflow-y: auto;
}
.msg-list li {
  position: relative;
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: 10px;
  transition: background .15s;
}
.msg-list li:hover { background: rgba(233, 85, 20, .05); }
.msg-list img {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  object-fit: cover;
  border: 1px solid rgba(171, 111, 65, .25);
  flex: 0 0 auto;
}
.msg-body { min-width: 0; flex: 1; }
.msg-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}
.msg-head b { font-size: 14px; color: #1d2024; }
.msg-head time { font-size: 12px; color: #a89b8c; flex: 0 0 auto; }
.msg-body p {
  margin: 3px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: #55595e;
}
.msg-unread {
  position: absolute;
  left: 4px;
  top: 14px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--orange);
}
.msg-login-btn {
  width: 100%;
  height: 42px;
  border: 0;
  border-radius: 7px;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  font-family: inherit;
  cursor: pointer;
  background: linear-gradient(180deg, #ef681b, #e7500d);
  box-shadow: 0 10px 22px rgba(223, 78, 13, .2);
  transition: .18s ease;
}
.msg-login-btn:hover { transform: translateY(-1px); box-shadow: 0 14px 26px rgba(223, 78, 13, .25); }

/* —— 帮助中心弹窗 —— */
.help-steps {
  margin: 0 0 16px;
  padding-left: 20px;
  display: grid;
  gap: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #2a2e32;
}
.help-steps code,
.help-accounts code {
  padding: 1px 7px;
  border-radius: 5px;
  background: rgba(233, 85, 20, .08);
  color: #c14a10;
  font-size: 13px;
}
.help-accounts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}
.help-accounts div {
  padding: 10px 8px;
  border: 1px solid rgba(171, 111, 65, .22);
  border-radius: 9px;
  background: rgba(255, 255, 255, .7);
  text-align: center;
  display: grid;
  gap: 5px;
}
.help-accounts span { font-size: 12px; color: #8a7e72; font-weight: 700; }
.help-tip { margin: 0; font-size: 12.5px; color: #8a7e72; }

/* —— 右上角通知/用户下拉 —— */
.badge-dot {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--orange);
  border: 1.5px solid #fdf5ec;
}

.popover {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  z-index: 50;
  width: 300px;
  padding: 14px 16px;
  border: 1px solid rgba(171, 111, 65, .3);
  border-radius: 12px;
  background: linear-gradient(180deg, #fffdf8, #fdf4e8);
  box-shadow: 0 18px 48px rgba(60, 40, 20, .18);
  text-align: left;
}

.pop-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 900;
  color: #1d2024;
}

.notice-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 4px;
}
.notice-list li {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  transition: background .15s;
}
.notice-list li:hover { background: rgba(233, 85, 20, .05); }
.notice-list b { font-size: 13px; color: #1d2024; }
.notice-list span { font-size: 12.5px; line-height: 1.5; color: #55595e; }
.notice-list time { font-size: 11.5px; color: #a89b8c; }

.user-pop { width: 260px; }
.user-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: rgba(233, 85, 20, .1);
  color: var(--orange);
  flex: 0 0 auto;
}
.user-head b { display: block; font-size: 14px; color: #1d2024; }
.user-head small { display: block; font-size: 12px; color: #8a7e72; margin-top: 2px; }

.pop-btn {
  width: 100%;
  height: 36px;
  margin-top: 8px;
  border-radius: 7px;
  border: 1.5px solid rgba(45, 34, 24, .3);
  background: rgba(255, 255, 255, .74);
  color: #2a2e32;
  font-size: 13px;
  font-weight: 800;
  font-family: inherit;
  cursor: pointer;
  transition: .18s ease;
}
.pop-btn:hover { border-color: rgba(233, 85, 20, .6); color: var(--orange); }
.pop-btn-primary {
  border: 0;
  color: #fff;
  background: linear-gradient(180deg, #ef681b, #e7500d);
}
.pop-btn-primary:hover { color: #fff; filter: brightness(1.05); }

.pop-enter-active, .pop-leave-active { transition: opacity .18s ease, transform .18s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: translateY(-6px); }

.error-banner {
  margin: 16px 0 0;
  padding: 8px 12px;
  border-radius: 7px;
  background: rgba(217, 70, 11, .08);
  border-left: 3px solid var(--orange-dark);
  color: var(--orange-dark);
  font-size: 12px;
  line-height: 1.5;
}

.primary,
.secondary {
  width: 100%;
  height: clamp(38px, 4.2vh, 46px);
  border-radius: 7px;
  font-weight: 900;
  cursor: pointer;
  font-size: clamp(14px, 1vw, 16px);
  font-family: inherit;
  transition: .18s ease;
}

.primary {
  position: relative;
  margin-top: clamp(6px, 1vh, 14px);
  border: 0;
  color: #fff;
  background: linear-gradient(180deg, #ef681b, #e7500d);
  box-shadow: 0 14px 26px rgba(223, 78, 13, .23);
}
.primary span { position: absolute; right: 24px; }
.primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 18px 30px rgba(223, 78, 13, .26);
}
.primary:disabled {
  cursor: not-allowed;
  opacity: .7;
  filter: grayscale(.25);
}

.secondary {
  margin-top: clamp(5px, 0.6vh, 10px);
  border: 1.5px solid rgba(45, 34, 24, .45);
  background: rgba(255,255,255,.74);
  color: #2a2e32;
  display: flex;
  align-items: center;
  justify-content: center;
}
.secondary:hover { border-color: rgba(233, 85, 20, .6); color: var(--orange); }
.secondary svg { width: 20px; height: 20px; }

.form-footer {
  margin-top: clamp(8px, 1vh, 16px);
  text-align: center;
}
.forgot-pwd {
  color: #8a7e72;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  transition: color 0.2s;
}
.forgot-pwd:hover {
  color: var(--orange);
  text-decoration: underline;
}

@media (max-width: 1300px) {
  .page { padding: 2vh 2vw; }
  .layout {
    grid-template-columns: 1fr;
  }
  .entry-card { width: min(500px, 100%); margin: 0 auto; }
}

@media (max-width: 720px) {
  .page { padding: 1.5vh 4vw; }
  .brand { font-size: 22px; }
  .brand-icon { width: 28px; height: 28px; }
  .entry-card {
    padding: 20px 16px;
  }
}
</style>


