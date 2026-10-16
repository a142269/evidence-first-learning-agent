import { getJson, postJson } from "@/api/http";

export type AuthRolePayload = "student" | "teacher" | "admin";

export interface AuthUserPayload {
  account: string;
  display_name: string;
  role: AuthRolePayload;
}

export interface LoginResponsePayload {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUserPayload;
  profile_initialized: boolean;
  profile_completeness: number;
}

export interface LoginRequestPayload {
  account: string;
  password: string;
  role: AuthRolePayload;
  remember: boolean;
}

export function loginByPassword(payload: LoginRequestPayload) {
  return postJson<LoginResponsePayload>("/api/v1/auth/login", payload as any);
}

export interface RegisterRequestPayload {
  account: string;
  password: string;
  display_name?: string;
  role: "student" | "teacher";
  profile_answers?: Record<string, unknown>;
}

/** 注册新账号（注册成功即返回登录态） */
export function registerAccount(payload: RegisterRequestPayload) {
  return postJson<LoginResponsePayload>("/api/v1/auth/register", payload as any);
}

export function getCurrentUser() {
  return getJson<AuthUserPayload>("/api/v1/auth/me");
}

export function logoutCurrentUser() {
  return postJson<{ status: string; account: string }>("/api/v1/auth/logout");
}
