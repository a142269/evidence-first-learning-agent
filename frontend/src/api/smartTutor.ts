/**
 * 智能辅导引擎 API —— /api/v1/smart-tutor/*
 * 独立于群聊的多 Agent 辅导闭环，支持文本/语音/图片/代码输入
 */
import { getJson, postForm, postJson } from "@/api/http";

export interface SmartTutorResponse {
  question_id?: string;
  user_id: string;
  question: string;
  kp_id?: string;
  answer?: string;
  explanation?: string;
  examples?: string[];
  quiz?: Array<Record<string, any>>;
  multimodal?: Record<string, any>;
  profile_update?: Record<string, any>;
  agents_used?: string[];
  duration_ms?: number;
  [key: string]: unknown;
}

export interface SmartTutorRecord {
  question_id?: string;
  question: string;
  kp_id?: string;
  answer?: string;
  timestamp?: string;
  [key: string]: unknown;
}

export function askSmartTutor(params: {
  user_id: string;
  question: string;
  input_type?: "text" | "voice" | "image" | "code";
  session_id?: string;
  preferred_modes?: string[];
}) {
  return postJson<SmartTutorResponse>("/api/v1/smart-tutor/ask", params as Record<string, unknown>);
}

export function getSmartTutorRecords(userId: string, limit = 20) {
  return getJson<{ user_id: string; count: number; records: SmartTutorRecord[] }>(
    `/api/v1/smart-tutor/records/${encodeURIComponent(userId)}`,
    { limit },
  );
}

export interface ImageAnalysisResult {
  page_id: string;
  filename: string;
  title: string;
  summary: string;
  topics: string[];
  blocks: Array<{ id: string; type: string; content: string; bloom_level?: string; confidence?: number }>;
  bloom_distribution: Record<string, number>;
  formulas: string[];
  language: string;
  ocr_method: string;
  elapsed_ms: number;
  error: string;
  success: boolean;
}

export function analyzeLearningImage(file: File) {
  const body = new FormData();
  body.append("file", file);
  return postForm<ImageAnalysisResult>("/api/v1/smart-tutor/image-analyze", body);
}
