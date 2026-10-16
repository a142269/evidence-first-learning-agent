/**
 * spaced-repetition API · Plan D · 3.3
 *
 * 端点见 backend/app/api/v1/spaced_repetition.py
 */
import { getJson, postJson } from "@/api/http";

export interface SpacedItem {
  item_id: string;
  knowledge_point?: {
    id: string;
    name: string;
    description: string;
  };
  question?: {
    id: string;
    stem: string;
    options: string[];
    type: string;
    difficulty?: number;
    bloom?: string;
    kp_id?: string;
    kp_name?: string;
  } | null;
  easiness: number;
  interval_days: number;
  repetitions: number;
  next_review_at: number | null;
  last_review_at: number | null;
  retention_curve?: Record<string, number>;
  recommendation?: Record<string, any>;
  // Plan D · 3.3 — 复习优先级融合 SM2 + BKT
  priority_score?: number;
  priority_reason?: string;
}

export interface ReviewRecommendation {
  item_id: string;
  priority_score: number;
  reason: string;
  easiness: number;
  interval_days: number;
  repetitions: number;
  next_review_at: number | null;
}

export interface RecommendResponse {
  user_id: string;
  recommendations: ReviewRecommendation[];
  total_candidates: number;
  algorithm: "sm2" | "fsrs" | "hlr";
}

export interface SpacedStats {
  user_id: string;
  total_items: number;
  due_today: number;
  due_item_count: number;
  average_easiness: number;
  due_item_ids: string[];
}

export interface DailyResponse {
  user_id: string;
  total_due: number;
  stats: SpacedStats;
  items: SpacedItem[];
  algorithm: "sm2" | "fsrs" | "hlr";
}

export function fetchDailyReview(user_id: string, limit = 20) {
  return getJson<DailyResponse>(
    `/api/v1/spaced-repetition/daily/${encodeURIComponent(user_id)}`,
    { limit },
  );
}

export function fetchSpacedStats(user_id: string) {
  return getJson<SpacedStats>(
    `/api/v1/spaced-repetition/stats/${encodeURIComponent(user_id)}`,
  );
}

export function submitReview(payload: {
  user_id: string;
  item_id: string;
  algorithm?: "sm2" | "fsrs" | "hlr";
  quality: number;
  item_type?: string;
  duration_minutes?: number;
  before_mastery?: number;
  after_mastery?: number;
}) {
  // 后端 /review 返回 state 含 `interval`（天），不是 `interval_days`
  return postJson<{
    user_id: string;
    item_id: string;
    algorithm: string;
    quality: number;
    review_event_id: number;
    state: {
      easiness: number;
      interval: number;  // 与 SpacedItem.interval_days 对应
      repetitions: number;
      next_review_at: number | null;
      last_review_at: number | null;
    };
    retention_curve: Record<string, number>;
  }>("/api/v1/spaced-repetition/review", {
    algorithm: "sm2",
    ...payload,
  });
}

export interface ReviewHistoryItem {
  id: number;
  item_id: string;
  item_type: string;
  rating: number;
  before_mastery_pct: number;
  after_mastery_pct: number;
  duration_minutes: number;
  reviewed_at: number;
  display_date: string;
  metadata: Record<string, any>;
}

export function fetchReviewHistory(user_id: string, limit = 50) {
  return getJson<{ user_id: string; total: number; items: ReviewHistoryItem[] }>(
    `/api/v1/spaced-repetition/history/${encodeURIComponent(user_id)}`,
    { limit },
  );
}

export function enqueueReview(payload: { user_id: string; item_id: string }) {
  return postJson<{ status: string; user_id: string; item_id: string }>(
    "/api/v1/spaced-repetition/enqueue",
    payload,
  );
}

// Plan D · 3.3 — 复习推荐 Top-N（按 priority_score 排序）
export function fetchReviewRecommend(user_id: string, limit = 3) {
  return getJson<RecommendResponse>(
    `/api/v1/spaced-repetition/recommend/${encodeURIComponent(user_id)}`,
    { limit },
  );
}

/** 查看单个知识点的 SM-2 复习计划（下次复习时间、间隔、难度系数等） */
export interface SpacedSchedule {
  user_id: string;
  item_id: string;
  easiness: number;
  interval_days: number;
  repetitions: number;
  next_review_at: number | null;
  last_review_at: number | null;
  retention_curve?: Record<string, number>;
  algorithm?: string;
  [key: string]: unknown;
}

export function fetchSchedule(user_id: string, item_id: string) {
  return getJson<SpacedSchedule>(
    `/api/v1/spaced-repetition/schedule/${encodeURIComponent(user_id)}/${encodeURIComponent(item_id)}`,
  );
}
