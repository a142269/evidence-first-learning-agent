/**
 * Insights API —— /api/v1/insights/*
 * 图谱种子 / 个性化路径直生成 / 学习诊断报告 / 画像感知资源推送
 */
import { getJson, postJson } from "@/api/http";
import type { LearningPath } from "@/api/learning_path";

export function seedKnowledgeGraph(course = "artificial_intelligence") {
  return postJson<{
    course: string;
    kps_upserted: number;
    relations_processed: number;
    kp_total: number;
    relation_total: number;
  }>(`/api/v1/insights/kg/seed-from-map?course=${encodeURIComponent(course)}`);
}

export interface PathGenerationConstraints {
  goal?: string;
  target_date?: string;
  daily_minutes?: number;
  interest?: string;
}

type PathGenerationRequest = PathGenerationConstraints & {
  course?: string;
  mistake_repair?: boolean;
};

export interface PathFeasibility {
  status: "feasible" | "insufficient";
  total_minutes: number;
  available_days: number;
  message: string;
}

export function generatePersonalPath(
  userId: string,
  masteredThreshold = 0.8,
  constraintsOrInterest: PathGenerationRequest | string = {},
) {
  const constraints = typeof constraintsOrInterest === "string"
    ? { interest: constraintsOrInterest }
    : constraintsOrInterest;
  return postJson<{
    user_id: string;
    path_id?: string;
    path?: LearningPath;
    pending_kps?: number;
    skipped_kps?: string[];
    note?: string;
    algorithm?: string;
    constraints?: PathGenerationConstraints;
    stage_deadlines?: Array<{ stage_id: string | number; due_date: string }>;
    recommended_daily_minutes?: number;
    feasibility?: PathFeasibility;
    /** 学生输入兴趣时，智狐（路径规划）对路径如何贴合兴趣的说明 */
    planner_note?: string;
  }>("/api/v1/insights/path/generate", {
    user_id: userId,
    mastered_threshold: masteredThreshold,
    ...constraints,
  });
}

export interface PeerComparisonResponse {
  user_id: string;
  cohort_size: number;
  dimensions: Record<string, number>;
  peer_average: Record<string, number>;
  metrics: {
    current_week_score: number | null;
    previous_week_score: number | null;
    weekly_lift: number | null;
    group_messages_30d: number;
  };
  generated_at: number;
}

export function getPeerComparison(userId: string) {
  return getJson<PeerComparisonResponse>(
    `/api/v1/insights/peer-comparison/${encodeURIComponent(userId)}`,
  );
}

export interface StudentOverviewKnowledgePoint {
  kp_id: string;
  kp_name: string;
  mastery_pct: number;
  updated_at: number;
  updated_date: string;
}

export interface StudentOverviewAssessment {
  external_id: string;
  record_type: string;
  topic: string;
  score_pct: number;
  duration_minutes: number;
  normalized_from_legacy: boolean;
  timestamp: number;
  display_date: string;
}

export interface StudentOverviewResponse {
  user_id: string;
  generated_at: number;
  generated_date: string;
  summary: {
    average_mastery_pct: number;
    mastered_knowledge_points: number;
    mistake_count: number;
    unresolved_mistake_count: number;
    streak_days: number;
    profile_completeness_pct: number;
  };
  activity: {
    total_minutes: number;
    this_week_minutes: number;
    last_week_minutes: number;
    week_over_week_pct: number;
    active_days_30d: number;
    hour_distribution: Array<{ hour: number; minutes: number }>;
    weekday_distribution: Array<{ weekday: number; minutes: number }>;
    calendar: Array<{ date: string; minutes: number }>;
    normalized_from_legacy_count: number;
  };
  assessment: {
    total: number;
    average_score_pct: number;
    this_week_average_score_pct: number;
    week_score_change_pct: number;
    recent: StudentOverviewAssessment[];
  };
  profile: {
    display_name: string;
    registered_at: number | null;
    registered_date: string;
    snapshot_count: number;
    dimensions: Record<string, Record<string, any>>;
    strengths: StudentOverviewKnowledgePoint[];
    risks: StudentOverviewKnowledgePoint[];
    mastery_trend: Array<{ timestamp: number; display_date: string; mastery_pct: number }>;
    knowledge_points: StudentOverviewKnowledgePoint[];
  };
  path: {
    id: string;
    title: string;
    current_stage: number;
    progress_pct: number;
    stages: Array<Record<string, any>>;
    stage_mastery: Array<{ stage_id: string; title: string; mastery_pct: number }>;
    milestones: Array<Record<string, any>>;
    today_tasks: Array<Record<string, any>>;
    updated_at: number | null;
    updated_date: string;
  };
  collaboration: {
    message_count: number;
    question_count: number;
    similar_stage_peer_count: number;
  };
  review: {
    due_today: number;
    completed_7d: number;
    completion_rate_pct: number;
    recent: Array<Record<string, any>>;
  };
  mistake_types: Array<{ code: string; label: string; count: number }>;
}

export function getStudentOverview(userId: string, course = "") {
  return getJson<StudentOverviewResponse>(
    `/api/v1/insights/student-overview/${encodeURIComponent(userId)}`,
    course ? { course } : undefined,
  );
}

export interface DiagnosisReportResponse {
  user_id: string;
  nickname: string;
  generated_at: string;
  focus_kp_id: string;
  markdown: string;
  payload: Record<string, any>;
  duration_ms: number;
}

export function getDiagnosisReport(userId: string) {
  return getJson<DiagnosisReportResponse>(
    `/api/v1/insights/report/${encodeURIComponent(userId)}`,
  );
}

export interface RecommendationItem {
  kind: "resource" | "generate";
  resource_id?: string;
  title?: string;
  type?: string;
  kp_id: string;
  topic?: string;
  suggested_types?: string[];
  reason: string;
}

export interface RecommendationsResponse {
  user_id: string;
  weakest_kps: Array<{ kp_id: string; mastery: number; name: string }>;
  items: RecommendationItem[];
  total_resources_scanned: number;
}

export function getRecommendations(userId: string, limit = 6, course = "") {
  return getJson<RecommendationsResponse>("/api/v1/insights/recommendations", {
    user_id: userId,
    limit,
    course,
  });
}

// ---------- 学习活跃日历（真实行为数据聚合） ----------
export interface CalendarDay {
  date: string;
  count: number;
  minutes: number;
  level: 0 | 1 | 2 | 3 | 4;
}

export interface StudyCalendarResponse {
  user_id: string;
  days: number;
  calendar: CalendarDay[];
  active_days: number;
  total_activities: number;
  total_minutes: number;
  current_streak: number;
  longest_streak: number;
}

export function getStudyCalendar(userId: string, days = 91) {
  return getJson<StudyCalendarResponse>(
    `/api/v1/insights/study-calendar/${encodeURIComponent(userId)}`,
    { days },
  );
}

// ---------- 评估驱动的动态调整闭环 ----------
export interface StrategySignal {
  name: string;
  value: string | number;
  detail: string;
}

export interface StrategyAdjustment {
  action: string;
  label: string;
  reason: string;
  weights?: Record<string, number>;
}

export interface AdaptiveStrategyResponse {
  user_id: string;
  signals: StrategySignal[];
  adjustments: StrategyAdjustment[];
  strategy: {
    daily_practice_intensity: number;
    resource_type_weights: Record<string, number>;
    focus_kps: Array<{ kp_id: string; mastery: number; name: string }>;
    replan_recommended: boolean;
  };
  algorithm: string;
}

export function getAdaptiveStrategy(userId: string, course = "artificial_intelligence") {
  return getJson<AdaptiveStrategyResponse>(
    `/api/v1/insights/adaptive-strategy/${encodeURIComponent(userId)}`,
    course ? { course } : undefined,
  );
}

export function applyAdaptiveStrategy(
  userId: string,
  force = false,
  course = "artificial_intelligence",
) {
  return postJson<{
    user_id: string;
    applied: string[];
    strategy: AdaptiveStrategyResponse["strategy"];
    new_path_id?: string;
    recommendations: RecommendationItem[];
  }>(`/api/v1/insights/adaptive-strategy/${encodeURIComponent(userId)}/apply`, {
    force,
    course,
  });
}

// ---------- 个性化推理链 ----------
export interface ReasoningChainItem {
  icon: string;
  label: string;
  detail: string;
}

export interface PersonalizationTag {
  label: string;
  color: string;
  icon: string;
}

export interface PersonalizationChainResponse {
  user_id: string;
  archetype: Record<string, any>;
  cognitive_style: string;
  bkt_summary: {
    weakest: Array<{ kp_id: string; mastery: number; name: string }>;
    strongest: Array<{ kp_id: string; mastery: number; name: string }>;
    total_kps: number;
    mastered_count: number;
  };
  path_personalization: Record<string, any>;
  adaptive_signals: StrategySignal[];
  replan_recommended: boolean;
  daily_intensity: number;
  reasoning_chain: ReasoningChainItem[];
  tags: PersonalizationTag[];
}

export function getPersonalizationChain(userId: string, course = "artificial_intelligence") {
  return getJson<PersonalizationChainResponse>(
    `/api/v1/insights/personalization-chain/${encodeURIComponent(userId)}`,
    course ? { course } : undefined,
  );
}
