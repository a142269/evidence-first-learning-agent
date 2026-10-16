/**
 * LearnerState API —— /api/v1/learner-state/*
 * 统一学习者状态聚合 + 事件流时间线 + 推荐解释
 */
import { getJson } from "@/api/http";

export interface LearnerStateProfile {
  profile: Record<string, any>;
  version: number;
  snapshot_count: number;
  snapshots: Array<{
    version: number;
    changed_keys: string[];
    source: string;
    profile: Record<string, any>;
    created_at: number;
  }>;
}

export interface LearnerStateMasteryItem {
  kp_id: string;
  bkt_p_learned: number | null;
  dina_mastery: number | null;
  average: number | null;
}

export interface LearnerStateMastery {
  items: LearnerStateMasteryItem[];
  total: number;
}

export interface LearnerStateMistakes {
  total: number;
  category_distribution: Record<string, number>;
  latest: Array<{
    id: string;
    kp_id: string;
    question: string;
    error_type: string;
    resolved: boolean;
  }>;
}

export interface LearnerStateRecommendation {
  focus_kps: Array<{ kp_id: string; average: number | null }>;
  overdue_reviews: number;
  primary_error_type: [string, number] | null;
  resource_count: number;
  why: string;
}

export interface LearnerStateSnapshot {
  user_id: string;
  version: number;
  generated_at: number;
  profile: LearnerStateProfile;
  mastery: LearnerStateMastery;
  mistakes: LearnerStateMistakes;
  review_schedule: { items: any[]; total: number };
  resources: { total_resources: number; type_distribution: Record<string, number>; recent: any[] };
  strategy: { paths: any[]; adjustments: any[] };
  assessment: { total: number; type_distribution: Record<string, number>; average_score: number | null; recent: any[] };
  recommendation: LearnerStateRecommendation;
}

export interface TimelineEvent {
  type: "profile_snapshot" | "path_adjustment" | "mistake_recorded" | "assessment" | "resource_generated";
  timestamp: number;
  description?: string;
  question?: string;
  student_answer?: string;
  correct_answer?: string;
  [key: string]: unknown;
}

export interface LearnerStateTimeline {
  user_id: string;
  events: TimelineEvent[];
  total: number;
  errors: string[];
}

export function getLearnerState(userId: string) {
  return getJson<LearnerStateSnapshot>(
    `/api/v1/learner-state/${encodeURIComponent(userId)}`,
  );
}

export function getLearnerStateTimeline(userId: string, limit = 50) {
  return getJson<LearnerStateTimeline>(
    `/api/v1/learner-state/${encodeURIComponent(userId)}/timeline`,
    { limit },
  );
}

export function getLearnerStateRecommendation(userId: string) {
  return getJson<{
    user_id: string;
    version: number;
    generated_at: number;
    recommendation: LearnerStateRecommendation;
  }>(`/api/v1/learner-state/${encodeURIComponent(userId)}/recommendation`);
}
