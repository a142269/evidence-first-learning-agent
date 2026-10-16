/**
 * 错题本闭环 API —— /api/v1/mistakes/* + /api/v1/system/variant/*
 * 记录 → 归因（8 分类）→ Bloom 变式 → 补救方案 → 解决
 */
import { getJson, postJson } from "@/api/http";

export interface MistakeItem {
  id: string;
  user_id: string;
  kp_id: string;
  question: string;
  student_answer: string;
  correct_answer: string;
  error_type: string;
  analysis: string;
  created_at: number;
  resolved: boolean;
  course?: string;
}

export interface HeatmapRow {
  kp_id: string;
  total: number;
  [errorType: string]: number | string;
}

export interface HeatmapResponse {
  user_id: string;
  kps: string[];
  categories: string[];
  matrix: HeatmapRow[];
  total_mistakes: number;
}

export function getMistakeCategories() {
  return getJson<{ categories: string[] }>("/api/v1/mistakes/categories");
}

export function getMistakesHeatmap(userId: string, course = "") {
  return getJson<HeatmapResponse>("/api/v1/mistakes/heatmap", {
    user_id: userId,
    course: course || undefined,
  });
}

export function listMistakes(userId: string, category = "", limit = 50, course = "") {
  return getJson<{ mistakes: MistakeItem[]; total: number }>(
    `/api/v1/mistakes/${encodeURIComponent(userId)}`,
    { category: category || undefined, limit, course: course || undefined },
  );
}

export function recordMistake(payload: {
  user_id: string;
  kp_id?: string;
  question: string;
  student_answer: string;
  correct_answer: string;
  error_type?: string;
  course?: string;
}) {
  return postJson<{ mistake_id: string; status: string; in_review_queue: boolean }>(
    "/api/v1/mistakes/record",
    payload,
  );
}

export interface MistakeAnalysis {
  error_type: string;
  detail: string;
  confidence?: number;
  [key: string]: unknown;
}

export function analyzeMistake(mistakeId: string) {
  return postJson<{ mistake_id: string; analysis: MistakeAnalysis }>(
    `/api/v1/mistakes/${encodeURIComponent(mistakeId)}/analyze`,
  );
}

export interface VariantQuestion {
  question?: string;
  answer?: string;
  explanation?: string;
  bloom_level?: string;
  bloom?: string;
  difficulty?: string;
  [key: string]: unknown;
}

export function makeVariants(mistakeId: string) {
  return postJson<{ mistake_id: string; variants: VariantQuestion[] | Record<string, any> }>(
    `/api/v1/mistakes/${encodeURIComponent(mistakeId)}/variants`,
  );
}

export interface RemediationPackage {
  attribution: { error_type: string; detail: string; [key: string]: unknown };
  variants?: VariantQuestion[] | Record<string, any>;
  remediation_path?: unknown;
  [key: string]: unknown;
}

export function getRemediation(mistakeId: string, count = 3) {
  return postJson<RemediationPackage>(
    `/api/v1/mistakes/${encodeURIComponent(mistakeId)}/remediation?count=${count}`,
  );
}

export function resolveMistake(mistakeId: string) {
  return postJson<{ mistake_id: string; status: string }>(
    `/api/v1/mistakes/${encodeURIComponent(mistakeId)}/resolve`,
  );
}

export function getAttribution(mistakeId: string) {
  return getJson<Record<string, any>>(
    `/api/v1/mistakes/${encodeURIComponent(mistakeId)}/attribution`,
  );
}

/** 演示用样例错题（system 路由，A 的变式演示） */
export function getVariantDemoSamples() {
  return getJson<{ samples: Array<Record<string, any>>; total: number }>(
    "/api/v1/system/variant/demo-samples",
  );
}

/** 批量导入错题种子数据（30 道，覆盖 8 大错因） */
export function seedMistakes(userId: string) {
  return postJson<{ user_id: string; imported: number; skipped: number; total_after: number }>(
    `/api/v1/mistakes/seed?user_id=${encodeURIComponent(userId)}`,
    {},
  );
}

// ── 错题智能分析（LLM 驱动） ──────────────────────────────

export interface MistakeWeakPoint {
  kp_id: string;
  reason: string;
  error_count: number;
}

export interface SimilarQuestion {
  question: string;
  answer: string;
  explanation: string;
  bloom_level?: string;
  source_kp?: string;
}

export interface LearningMaterial {
  title: string;
  type: string;
  url: string;
  reason: string;
}

export interface MistakeEvaluation {
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

export interface MistakeInsights {
  summary: string;
  weak_points: MistakeWeakPoint[];
  error_pattern: string;
  recommendations: {
    similar_questions: SimilarQuestion[];
    learning_materials: LearningMaterial[];
  };
  evaluation: MistakeEvaluation;
  source: "llm" | "rule";
  generated_at: number;
  user_id?: string;
  total_mistakes?: number;
}

/** 获取错题智能分析（LLM 总结 + 推荐 + 评估） */
export function getMistakeInsights(userId: string, course = "") {
  return getJson<MistakeInsights>(
    `/api/v1/mistakes/insights/${encodeURIComponent(userId)}`,
    { course: course || undefined },
  );
}

/** A 的独立 Bloom 分层变式生成端点（POST /system/variant/{mistake_id}）
 *  可直接传入完整错题信息生成变式，不需要先存到错题库 */
export function generateVariantSystem(
  mistakeId: string,
  payload: {
    user_id?: string;
    kp_id?: string;
    kp_name?: string;
    question: string;
    student_answer?: string;
    correct_answer: string;
    count?: number;
  },
  count = 3,
) {
  const q = new URLSearchParams();
  q.set("count", String(payload.count ?? count));
  return postJson<{ variants: VariantQuestion[]; source_endpoint: string }>(
    `/api/v1/system/variant/${encodeURIComponent(mistakeId)}?${q.toString()}`,
    payload as Record<string, unknown>,
  );
}
