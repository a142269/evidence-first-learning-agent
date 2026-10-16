/**
 * 多模态资源生成 API —— /api/v1/artifacts/*
 * 覆盖 PPT / 思维导图(Mermaid) / 代码沙箱 / TTS 音频 / Manim 视频 / 一键多资源
 */
import { getJson, postJson, getApiBaseUrl } from "@/api/http";
import { getAuthToken } from "@/utils/auth";

// ============================================================
// 通用响应
// ============================================================
export interface ResourceResult {
  resource_id: string;
  type: string;
  filepath: string;
  data_uri: string;
  method: string;
  metadata: Record<string, any>;
  duration_ms: number;
  error: string;
  success: boolean;
}

export interface ArtifactInfo {
  id?: string;
  resource_id?: string;
  type: string;
  filepath?: string;
  metadata?: Record<string, any>;
  session_id?: string;
  created_at?: number;
  [key: string]: unknown;
}

// ============================================================
// 生成端点
// ============================================================
export function generatePptx(params: {
  title: string;
  subtitle?: string;
  slides?: Array<{ title: string; bullets?: string[] }>;
  summary?: string[];
  review?: string[];
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/pptx", params);
}

export function generateMindmap(params: {
  title: string;
  branches: string[];
  leaves?: Record<string, string[]>;
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/mermaid", params);
}

export function generateMermaidCode(params: {
  code: string;
  kind?: "mindmap" | "flowchart" | "sequence" | "class" | "graph";
  name_hint?: string;
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/mermaid-code", params);
}

export function executeCode(params: {
  code: string;
  language?: string;
  timeout?: number;
  with_review?: boolean;
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/code", params);
}

export function generateTts(params: {
  text: string;
  voice?: string;
  speed?: number;
  volume?: number;
  pitch?: number;
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/tts", params);
}

export function listTtsVoices() {
  return getJson<{ voices: Array<Record<string, any>> }>("/api/v1/artifacts/tts/voices");
}

export function generateManim(params: {
  topic: string;
  template?: "concept" | "comparison" | "timeline" | "code";
  persona?: string;
  render?: boolean;
  session_id?: string;
}) {
  return postJson<ResourceResult>("/api/v1/artifacts/generate/manim", params);
}

// ============================================================
// 一键多模态套餐
// ============================================================
export type MultiResourceType = "pptx" | "mermaid" | "code" | "tts" | "manim";

export interface ResourceEnvelope {
  success: boolean;
  type: string;
  error?: string | null;
  content?: string | null;
  filepath?: string | null;
  evidence?: Array<Record<string, any>>;
  cov?: Record<string, any>;
  safety?: Record<string, any>;
  downloads?: Array<Record<string, any>>;
  metadata?: Record<string, any>;
  [key: string]: any;
}

export interface MultiResourceProfile {
  user_id?: string;
  kp_id?: string | null;
  bloom_level?: string | null;
  learning_objective?: string | null;
  misconception?: string | null;
  /** 后端 _profile_hint_str() 输出：本次生成注入的画像摘要（空=未建画像） */
  profile_hint?: string;
  [key: string]: any;
}

export interface MultiResourceResponse {
  topic: string;
  types_requested: string[];
  types_succeeded: string[];
  types_failed: string[];
  results: Record<string, ResourceEnvelope>;
  total_duration_ms: number;
  success_count: number;
  profile: MultiResourceProfile;
  overall_quality: number;
  overall_safety: number;
}

export function generateMulti(params: {
  topic: string;
  description?: string;
  types?: MultiResourceType[];
  session_id?: string;
  pptx_bullets?: string[];
  mermaid_branches?: string[];
  code_snippet?: string;
  tts_text?: string;
  manim_template?: string;
  manim_render?: boolean;
  kp_id?: string;
  bloom_level?: string;
  learning_objective?: string;
  misconception?: string;
  include_manim?: boolean;
  user_id?: string;
}) {
  return postJson<MultiResourceResponse>("/api/v1/artifacts/generate/multi", params);
}

/** 降级容错版多资源生成：单项失败自动降级，不影响其他资源 */
export function generateMultiWithFallback(params: {
  topic: string;
  description?: string;
  types?: MultiResourceType[];
  session_id?: string;
  user_id?: string;
}) {
  return postJson<MultiResourceResponse>(
    "/api/v1/artifacts/generate/multi-with-fallback",
    params as Record<string, unknown>,
  );
}

// ============================================================
// SSE 流式多资源生成 — 逐个推送完成事件，避免白屏等待
// ============================================================
export interface MultiStreamCallbacks {
  onStart?: (data: { topic: string; types_requested: string[]; total: number }) => void;
  onProgress?: (data: {
    type: string;
    status: "done" | "failed";
    detail: string;
    envelope?: ResourceEnvelope;
  }) => void;
  onDone?: (result: MultiResourceResponse) => void;
  onError?: (error: string) => void;
}

/**
 * SSE 流式多资源生成。
 *
 * 前端用 fetch + ReadableStream 消费（EventSource 不支持 POST）。
 * 每完成一个资源就触发 onProgress，最终触发 onDone 携带完整聚合结果。
 */
export function generateMultiStream(
  params: {
    topic: string;
    description?: string;
    types?: MultiResourceType[];
    session_id?: string;
    kp_id?: string;
    bloom_level?: string;
    learning_objective?: string;
    misconception?: string;
    include_manim?: boolean;
    manim_template?: "concept" | "comparison" | "timeline" | "code";
    manim_render?: boolean;
    user_id?: string;
  },
  callbacks: MultiStreamCallbacks,
): AbortController {
  const controller = new AbortController();
  const apiBase = getApiBaseUrl();
  const url = `${apiBase}/api/v1/artifacts/generate/multi-stream`;
  const token = getAuthToken();

  fetch(url, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(params),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        callbacks.onError?.(`HTTP ${response.status}`);
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError?.("Stream not supported");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const evtText of events) {
          const eventLine = evtText.match(/^event: (.+)$/m);
          const dataLine = evtText.match(/^data: (.+)$/m);
          if (!eventLine || !dataLine) continue;

          const eventType = eventLine[1].trim();
          let payload: any;
          try {
            payload = JSON.parse(dataLine[1]);
          } catch {
            continue;
          }

          switch (eventType) {
            case "start":
              callbacks.onStart?.(payload);
              break;
            case "progress":
              callbacks.onProgress?.(payload);
              break;
            case "done":
              callbacks.onDone?.(payload as MultiResourceResponse);
              break;
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err.message || "Network error");
      }
    });

  return controller;
}

// ============================================================
// 产物列表 / 下载
// ============================================================
export function listArtifacts(params?: { type?: string; session_id?: string; limit?: number }) {
  return getJson<{ artifacts: ArtifactInfo[]; total: number }>(
    "/api/v1/artifacts/list",
    params as Record<string, string | number>,
  );
}

export function getArtifactInfo(rid: string) {
  return getJson<ArtifactInfo>(`/api/v1/artifacts/info/${encodeURIComponent(rid)}`);
}

/** 拼下载直链（浏览器直接 open / <a download>）。
 *  kind: pptx/mp3/png/mermaid/manim 走类型特定端点；
 *  kind: "generic" 走通用端点 /download/{rid}，从 registry filepath 直接返回文件。
 */
export function artifactDownloadUrl(
  rid: string,
  kind: "pptx" | "mp3" | "png" | "mermaid" | "manim" | "generic",
) {
  if (kind === "generic") {
    return `${getApiBaseUrl()}/api/v1/artifacts/download/${encodeURIComponent(rid)}`;
  }
  return `${getApiBaseUrl()}/api/v1/artifacts/${encodeURIComponent(rid)}/${kind}`;
}

/** 拼通用下载完整 URL（含 host），用于 <a :href> 直接下载 */
export function getArtifactDownloadFullUrl(rid: string) {
  return `${getApiBaseUrl()}/api/v1/artifacts/download/${encodeURIComponent(rid)}`;
}

export function artifactDataUriUrl(rid: string) {
  return `${getApiBaseUrl()}/api/v1/artifacts/${encodeURIComponent(rid)}/data-uri`;
}
