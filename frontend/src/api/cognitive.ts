/**
 * 认知诊断 API —— /api/v1/cognitive/*
 * BKT 知识追踪 / Bloom 分类 / 掌握度预测（时光机）/ 反事实 / 主动学习推题 / 倒推计划
 */
import { getJson, postJson } from "@/api/http";

// ============================================================
// 掌握度预测（时光机）
// ============================================================
export interface ForecastPoint {
  day: number;
  p_learned?: number;
  mastery?: number;
  ci_low?: number;
  ci_high?: number;
  practice_count_expected?: number;
}

export interface Milestone {
  day: number;
  target?: number;
  label: string;
  p_at_day?: number;
  ci_at_day?: [number, number];
}

export interface ForecastResponse {
  user_id: string;
  kp_id: string;
  current_mastery: number;
  forecast: ForecastPoint[];
  milestones: Milestone[];
  svg?: string;
  ascii_chart?: string;
  summary_text: string;
  note?: string;
  error?: string;
}

export function getForecast(userId: string, kpId = "", horizonDays = 30) {
  return getJson<ForecastResponse>("/api/v1/cognitive/forecast", {
    user_id: userId,
    kp_id: kpId || undefined,
    horizon_days: horizonDays,
  });
}

// ============================================================
// 反事实分析（不同练习强度对比）
// ============================================================
export interface CounterfactualResponse {
  user_id: string;
  kp_id: string;
  scenarios?: Array<{
    daily_rate: number;
    curve: ForecastPoint[];
    final_mastery?: number;
    [key: string]: unknown;
  }>;
  baseline_curve?: ForecastPoint[];
  recommended_curve?: ForecastPoint[];
  expected_gain?: number;
  risk_warning?: string;
  [key: string]: unknown;
}

export function getCounterfactual(userId: string, kpId = "", horizonDays = 30) {
  return getJson<CounterfactualResponse>("/api/v1/cognitive/counterfactual", {
    user_id: userId,
    kp_id: kpId || undefined,
    horizon_days: horizonDays,
  });
}

// ============================================================
// BKT 知识追踪
// ============================================================
export interface BktStatus {
  user_id: string;
  masteries: Record<string, number>;
  trends?: Record<string, string>;
  note?: string;
}

export function getBktStatus(userId: string) {
  return getJson<BktStatus>(`/api/v1/cognitive/bkt/${encodeURIComponent(userId)}`);
}

export function updateBkt(userId: string, kpId: string, correct: boolean) {
  return postJson<{ user_id: string; kp_id: string; p_learned: number; trend: string }>(
    "/api/v1/cognitive/bkt/update",
    { user_id: userId, kp_id: kpId, correct },
  );
}

// ============================================================
// Bloom 认知层级
// ============================================================
export interface BloomLevel {
  key: string;
  label: string;
  index: number;
}

export function getBloomLevels() {
  return getJson<{ levels: BloomLevel[] }>("/api/v1/cognitive/bloom/levels");
}

export interface BloomDetail {
  text: string;
  level: string;
  level_label: string;
  sub_level: string;
  sub_level_label: string;
  definition: string;
  knowledge_dimension: string;
  knowledge_dim_label: string;
  keywords_matched: number;
  examples: string[];
  anti_examples: string[];
}

export function getBloomDetail(text: string) {
  return getJson<BloomDetail>("/api/v1/cognitive/bloom/detail", { text });
}

export function classifyBloom(text: string) {
  return postJson<Record<string, any>>("/api/v1/cognitive/bloom/classify", { text });
}

// ============================================================
// Active Learning 推题
// ============================================================
export interface NextBestQuestionResult {
  user_id?: string;
  strategy?: string;
  questions?: Array<Record<string, any>>;
  recommendations?: Array<Record<string, any>>;
  note?: string;
  error?: string;
  [key: string]: unknown;
}

export function nextBestQuestion(params: {
  user_id: string;
  kp_id?: string;
  bloom?: string;
  top_k?: number;
  strategy?: "entropy" | "margin" | "least_confident";
}) {
  const q = new URLSearchParams();
  q.set("user_id", params.user_id);
  if (params.kp_id) q.set("kp_id", params.kp_id);
  if (params.bloom) q.set("bloom", params.bloom);
  q.set("top_k", String(params.top_k ?? 5));
  q.set("strategy", params.strategy ?? "entropy");
  return postJson<NextBestQuestionResult>(`/api/v1/cognitive/next-best-question?${q.toString()}`);
}

// ============================================================
// 目标倒推计划
// ============================================================
export interface ReversePlanSchedulePoint {
  day: number;
  expected_mastery: number;
  cumulative_questions: number;
}

export interface ReversePlanMilestone {
  day: number;
  target: number;
  projected: number;
  label: string;
}

export interface ReversePlanResponse {
  status: string;
  current_mastery: number;
  target_mastery: number;
  horizon_days: number;
  daily_practice_rate?: number;
  daily_questions?: number;
  projected_mastery: number;
  schedule?: ReversePlanSchedulePoint[];
  milestones?: ReversePlanMilestone[];
  narrative?: string;
}

export function reversePlan(params: {
  current_mastery: number;
  target_mastery: number;
  horizon_days: number;
  questions_per_full_practice_day?: number;
}) {
  return postJson<ReversePlanResponse>("/api/v1/cognitive/reverse-plan", {
    questions_per_full_practice_day: 10,
    ...params,
  });
}

// ============================================================
// DINA 认知诊断模型
// ============================================================
export interface DinaResult {
  student_id?: string;
  alpha?: Record<string, number>;
  slip?: Record<string, number>;
  guess?: Record<string, number>;
  mastery_patterns?: Record<string, Record<string, boolean>>;
  attribute_mastery?: Record<string, number>;
  [key: string]: unknown;
}

export function diagnoseDina(params: {
  responses: Record<string, Record<string, number>>;
  items: Array<Record<string, any>>;
  kp_ids: string[];
}) {
  return postJson<DinaResult>("/api/v1/cognitive/diagnose", params as Record<string, unknown>);
}
