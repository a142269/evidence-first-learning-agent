const AUTH_STORAGE_KEY = "student_behavior_auth";
export const PREVIEW_ACCESS_TOKEN = "a3-local-preview-token";

export type AuthRole = "student" | "teacher" | "admin";

export interface AuthSession {
  accessToken: string;
  tokenType: "bearer";
  expiresAt: string;
  account: string;
  displayName: string;
  role: AuthRole;
  loginAt: string;
  remember: boolean;
}

/** 旧会话里可能存着 counselor，统一映射为 teacher */
function normalizeRole(role: string | undefined): AuthRole {
  if (role === "counselor") return "teacher";
  if (role === "teacher" || role === "admin") return role;
  return "student";
}

export function getAuthSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const session = JSON.parse(raw) as AuthSession;
    session.role = normalizeRole(session.role as string);
    return session;
  } catch {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function isAuthenticated(): boolean {
  const session = getAuthSession();
  if (!session) {
    return false;
  }

  return Boolean(session.accessToken);
}

export function getAuthToken(): string {
  return getAuthSession()?.accessToken || "";
}

export function getAuthRole(): AuthRole {
  return getAuthSession()?.role || "student";
}

export function isTeacherRole(): boolean {
  const role = getAuthRole();
  return role === "teacher" || role === "admin";
}

export function isPreviewSession(): boolean {
  return getAuthToken() === PREVIEW_ACCESS_TOKEN;
}

export function setAuthSession(session: AuthSession) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event("a3-auth-changed"));
}

export function clearAuthSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  window.dispatchEvent(new Event("a3-auth-changed"));
}
