﻿import { getAuthToken } from "@/utils/auth";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL;
const SAME_ORIGIN = RAW_API_BASE === "" || (RAW_API_BASE === undefined && import.meta.env.PROD);
const API_BASE_URL = SAME_ORIGIN
  ? ""
  : (RAW_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

type QueryValue = string | number | boolean | undefined;

function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (SAME_ORIGIN) {
    const search = new URLSearchParams();
    if (query) {
      Object.entries(query).forEach(([key, value]) => {
        if (value === undefined || value === "") return;
        search.set(key, String(value));
      });
    }
    const qs = search.toString();
    return qs ? `${normalizedPath}?${qs}` : normalizedPath;
  }

  const url = new URL(`${API_BASE_URL}${normalizedPath}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value === undefined || value === "") return;
      url.searchParams.set(key, String(value));
    });
  }
  return url.toString();
}

async function readError(response: Response) {
  let detail = response.statusText || "request_failed";
  try {
    const payload = (await response.json()) as { detail?: string };
    if (payload?.detail) detail = payload.detail;
  } catch {
    // Keep the HTTP status text when the backend returns non-JSON errors.
  }
  return detail;
}

export async function getJson<T>(
  path: string,
  query?: Record<string, QueryValue>,
): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path, query), {
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return (await response.json()) as T;
}

export async function postJson<T>(
  path: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body ?? {}),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return (await response.json()) as T;
}

/** 发送 multipart/form-data；浏览器会自动补齐 boundary，勿手工设置 Content-Type。 */
export async function postForm<T>(path: string, body: FormData): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body,
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return (await response.json()) as T;
}

export async function getBlob(
  path: string,
  query?: Record<string, QueryValue>,
): Promise<Blob> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path, query), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return response.blob();
}

export async function patchJson<T>(
  path: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path), {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body ?? {}),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return (await response.json()) as T;
}

export async function deleteJson<T>(
  path: string,
  body?: Record<string, unknown>,
): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(buildUrl(path), {
    method: "DELETE",
    headers: {
      Accept: "application/json",
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }

  return (await response.json()) as T;
}

export function getApiBaseUrl() {
  return API_BASE_URL;
}
