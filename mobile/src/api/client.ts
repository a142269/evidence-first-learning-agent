import { Preferences } from "@capacitor/preferences";

const TOKEN_KEY = "triple_u_mobile_token";
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
let tokenCache = "";

export function createClientMessageId(
  cryptoApi: { randomUUID?: () => string } | undefined = globalThis.crypto,
) {
  if (typeof cryptoApi?.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }
  const time = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 12);
  return `mobile-${time}-${random}`;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

export async function loadToken() {
  if (!tokenCache) tokenCache = (await Preferences.get({ key: TOKEN_KEY })).value ?? "";
  return tokenCache;
}

export async function saveToken(token: string) {
  tokenCache = token;
  await Preferences.set({ key: TOKEN_KEY, value: token });
}

export async function clearToken() {
  tokenCache = "";
  await Preferences.remove({ key: TOKEN_KEY });
}

async function parseError(response: Response) {
  try {
    const data = await response.json();
    return String(data.detail || response.statusText || "request_failed");
  } catch {
    return response.statusText || "request_failed";
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  query?: Record<string, string | number | undefined>,
): Promise<T> {
  const token = await loadToken();
  const url = new URL(`${API_BASE}${path}`);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  });
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const error = new ApiError(response.status, await parseError(response));
    if (response.status === 401) {
      await clearToken();
      window.dispatchEvent(new CustomEvent("mobile-auth-expired"));
    }
    throw error;
  }
  return response.json() as Promise<T>;
}

export async function download(path: string) {
  const token = await loadToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new ApiError(response.status, await parseError(response));
  return response.blob();
}

export function websocketUrl() {
  const url = new URL(`${API_BASE}/api/v1/mobile/ws`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
