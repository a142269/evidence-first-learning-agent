/**
 * 会话级共享状态：当前学生 ID / 聊天 session / 课程。
 * 轻量 module-scope 单例，不引入 pinia。
 */
import { ref } from "vue";

import { getAuthSession } from "@/utils/auth";
import { generateSessionId } from "@/api/chat";

const CHAT_SESSION_KEY = "a3_chat_session_id";
const COURSE_STORAGE_KEY = "a3_current_course";
const DEFAULT_COURSE = "artificial_intelligence";

/** 后端画像/认知/错题等端点使用的学生 ID（demo 种子学生兜底） */
const userId = ref(resolveUserId());
const course = ref(loadCourse());
const chatSessionId = ref(loadChatSessionId(userId.value));

function resolveUserId(): string {
  const session = getAuthSession();
  const account = String(session?.account || "").trim();
  const displayName = String(session?.displayName || "").trim();
  // 演示身份发生冲突时，优先采用用户此刻登录后看见的姓名。旧版本曾留下
  // account=林同学、displayName=杜同学的混合缓存，若先信 account 就会继续串号。
  if (displayName === "杜同学") return "demo-student-1";
  if (displayName === "林同学") return "demo-student-21";
  if (account === "demo-student-1" || account === "demo-student-21") return account;
  return account || "demo-student-1";
}

function chatSessionStorageKey(forUserId: string): string {
  return `${CHAT_SESSION_KEY}:${forUserId || "anonymous"}`;
}

function loadChatSessionId(forUserId: string): string {
  if (typeof window === "undefined") return generateSessionId();
  const storageKey = chatSessionStorageKey(forUserId);
  const cached = window.localStorage.getItem(storageKey);
  if (cached) return cached;
  // 只为默认杜同学迁移旧版全局会话；林同学必须使用独立会话，避免共享
  // 历史、画像和资源附件。
  if (forUserId === "demo-student-1") {
    const legacy = window.localStorage.getItem(CHAT_SESSION_KEY);
    if (legacy) {
      window.localStorage.setItem(storageKey, legacy);
      return legacy;
    }
  }
  const fresh = generateSessionId();
  window.localStorage.setItem(storageKey, fresh);
  return fresh;
}

function loadCourse(): string {
  if (typeof window === "undefined") return DEFAULT_COURSE;
  return window.localStorage.getItem(COURSE_STORAGE_KEY)?.trim() || DEFAULT_COURSE;
}

function syncAuthUser() {
  const nextUserId = resolveUserId();
  if (nextUserId !== userId.value) {
    userId.value = nextUserId;
    chatSessionId.value = loadChatSessionId(nextUserId);
  }
}

if (typeof window !== "undefined") {
  // setAuthSession 在同一标签页不会触发原生 storage 事件，使用自定义事件
  // 让登录/退出后所有页面立即切换到正确的学生画像和会话。
  window.addEventListener("a3-auth-changed", syncAuthUser);
}

export function useSession() {
  function resetChatSession() {
    const fresh = generateSessionId();
    chatSessionId.value = fresh;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(chatSessionStorageKey(userId.value), fresh);
    }
    return fresh;
  }

  function refreshUser() {
    syncAuthUser();
  }

  function setCourse(nextCourse: string) {
    const normalized = nextCourse.trim() || DEFAULT_COURSE;
    course.value = normalized;
    if (typeof window !== "undefined") {
      window.localStorage.setItem(COURSE_STORAGE_KEY, normalized);
    }
  }

  return { userId, course, chatSessionId, resetChatSession, refreshUser, setCourse };
}
