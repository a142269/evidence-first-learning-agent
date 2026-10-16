/**
 * 多智能体对话 API —— SSE 流式 + REST
 * 迁移自旧项目 qa.ts 的 SSE 流式架构
 */
import { getJson, postJson, getApiBaseUrl } from "@/api/http";
import { getAuthToken } from "@/utils/auth";

// ============================================================
// 类型定义
// ============================================================
export interface ChatResponse {
  session_id: string;
  /** FIX-09（2026-07-17）：后端实际返回 primary_agent；agent 仅为旧字段兼容 */
  primary_agent: string;
  agent?: string;
  content: string;
  content_type: string;
  resources: ResourceItem[];
  profile: Record<string, any>;
  success: boolean;
  error: string;
  agent_messages?: AgentMessageItem[];
  // 后端实际返回但此前类型缺失的字段（FIX-09）
  saved_resources?: Array<Record<string, any>>;
  profile_meta?: Record<string, any>;
  realtime_state?: Record<string, any>;
  rag_hits?: Array<Record<string, any>>;
  agents_invoked?: string[];
  quality?: Record<string, any>;
  safety?: Record<string, any>;
  debate?: Record<string, any>;
  reflection?: Record<string, any>;
  telemetry?: Record<string, any>;
}

export interface AgentMessageItem {
  task_id: string;
  agent: string;
  agent_key: string;
  display_name: string;
  role: string;
  content?: string;
  content_type?: string;
  resources?: ResourceItem[];
  success?: boolean;
  error?: string;
}

export interface ResourceDownload {
  id: string;
  type: string;
  url: string;
  filename?: string;
  exists?: boolean;
  metadata?: Record<string, any>;
}

export interface ResourceItem {
  id?: string;
  type: string;
  title: string;
  content?: string;
  format?: string;
  filepath?: string;
  downloads?: ResourceDownload[];
  quiz_count?: number;
  stages_count?: number;
  metadata?: Record<string, any>;
}

export interface StreamEvent {
  type:
    | "meta"
    | "thinking"
    | "chunk"
    | "agent_start"
    | "agent_chunk"
    | "agent_resources"
    | "agent_done"
    | "resources"
    | "profile_update"
    | "profile_status"
    | "done"
    | "error";
  payload?: any;
}

// ============================================================
// REST 接口
// ============================================================
export function sendMessage(params: {
  message: string;
  session_id?: string;
  course?: string;
  user_id?: string;
}) {
  return postJson<ChatResponse>("/api/v1/chat/send", params);
}

export function getProfile(sessionId: string) {
  return getJson<{ profile: Record<string, any> }>(`/api/v1/chat/profile/${sessionId}`);
}

export function getHistory(sessionId: string) {
return getJson<{ history: Array<{ role: string; content: string; agent_name?: string; resources?: ResourceItem[] }> }>(
`/api/v1/chat/history/${sessionId}`
);
}

export function clearSession(sessionId: string) {
  return postJson<{ status: string }>("/api/v1/chat/clear", {
    session_id: sessionId,
  });
}

// ============================================================
// 聊天存档 — 跨会话全部聊天记录，供资源库「聊天存档」tab 使用
// ============================================================
export interface ChatArchiveRecord {
  id?: number;
  session_id: string;
  role: string;       // user / assistant
  content: string;
  agent_name?: string;
  created_at?: number;
}

export function getChatArchive(userId: string, limit = 100) {
  return getJson<{ records: ChatArchiveRecord[]; total: number }>(
    `/api/v1/chat/archive/${encodeURIComponent(userId)}`,
    { limit },
  );
}

// ============================================================
// CoV-Edu 防幻觉核验
// ============================================================
export interface CovAxisResult {
  axis?: string;
  label?: string;
  passed?: boolean;
  score?: number;
  detail?: string;
  [key: string]: unknown;
}

export interface CovResult {
  text?: string;
  overall_passed?: boolean;
  overall_score?: number;
  axes?: CovAxisResult[];
  results?: CovAxisResult[];
  verified_claims?: Array<Record<string, any>>;
  summary?: string;
  [key: string]: unknown;
}

/** 五轴教育幻觉核验（事实性/答案泄漏/误概念/引用/难度适配） */
export function chatWithCov(text: string, groundTruth = "") {
  return postJson<CovResult>("/api/v1/chat/with-cov", {
    text,
    ground_truth: groundTruth,
  });
}

export function getCovDemoCases() {
  return getJson<{ cases: Array<Record<string, any>>; total: number }>(
    "/api/v1/chat/cov-demo-cases",
  );
}

// ============================================================
// SSE 流式接口 —— 直接迁移自旧项目 qa.ts 的 queryQAStream
// ============================================================
export function streamChat(
  params: {
    message: string;
    session_id?: string;
    course?: string;
    user_id?: string;
    /** 前端 partner.key (planner/tutor/content/quiz/evaluation/safety)，
     * 指定后后端走单 Agent 模式，只让该 Agent 回复 */
    target_agent?: string;
    /** 课程群聊房间 ID（course:student_id）。携带后学生提问与 Agent 回复
     * 会同步写入群聊房间，教师端可见 */
    room_id?: string;
    sender_role?: string;
    sender_name?: string;
  },
  callbacks: {
    onMeta?: (meta: any) => void;
    onThinking?: (text: string) => void;
    onChunk?: (text: string) => void;
    /** 团队模式：每位 Agent 使用独立 task_id 流式输出到自己的气泡 */
    onAgentStart?: (agent: AgentMessageItem) => void;
    onAgentChunk?: (payload: { task_id: string; agent?: string; text: string }) => void;
    onAgentResources?: (payload: {
      task_id: string;
      agent?: string;
      agent_key?: string;
      resources: ResourceItem[];
    }) => void;
    onAgentDone?: (payload: {
      task_id: string;
      agent?: string;
      success?: boolean;
      error?: string;
    }) => void;
    onResources?: (resources: ResourceItem[]) => void;
    onProfileUpdate?: (profile: Record<string, any>) => void;
    onDone?: (fullText: string, contentType: string) => void;
    onError?: (error: string) => void;
    // Plan D · 2.3 — 画像提取状态事件（用于前端 Toast）
    onProfileStatus?: (status: {
      status: string;
      dimensions_count?: number;
    }) => void;
  }
): AbortController {
  const controller = new AbortController();
  const apiBase = getApiBaseUrl();
  const url = `${apiBase}/api/v1/chat/stream`;

  fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
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
      let fullText = "";
      let buffer = "";
      let contentType = "markdown";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event: StreamEvent = JSON.parse(line.slice(6));
              switch (event.type) {
                case "meta":
                  callbacks.onMeta?.(event.payload);
                  break;
                case "thinking":
                  callbacks.onThinking?.(event.payload);
                  break;
                case "chunk":
                  fullText += event.payload;
                  callbacks.onChunk?.(event.payload);
                  break;
                case "agent_start":
                  callbacks.onAgentStart?.(event.payload);
                  break;
                case "agent_chunk":
                  callbacks.onAgentChunk?.(event.payload);
                  break;
                case "agent_resources":
                  callbacks.onAgentResources?.(event.payload);
                  break;
                case "agent_done":
                  callbacks.onAgentDone?.(event.payload);
                  break;
                case "resources":
                  callbacks.onResources?.(event.payload);
                  break;
                case "profile_update":
                  callbacks.onProfileUpdate?.(event.payload);
                  break;
                // Plan D · 2.3 — 画像提取状态（前端 Toast）
                case "profile_status":
                  callbacks.onProfileStatus?.(event.payload);
                  break;
                case "done":
                  contentType = event.payload?.content_type || "markdown";
                  callbacks.onDone?.(fullText, contentType);
                  break;
                case "error":
                  callbacks.onError?.(event.payload);
                  break;
              }
            } catch {
              // Skip malformed lines
            }
          }
        }
      }
      // If we got text but no 'done' event
      if (fullText && !buffer.includes('"done"')) {
        callbacks.onDone?.(fullText, contentType);
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError?.(err.message || "Network error");
      }
    });

  return controller;
}

/** Generate a unique session ID */
export function generateSessionId(): string {
  return "sess_" + Math.random().toString(36).slice(2, 14);
}
