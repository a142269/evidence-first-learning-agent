/**
 * 知识图谱 API —— /api/v1/knowledge-graph/*
 */
import { getJson, postJson } from "@/api/http";

export interface KnowledgePoint {
  id?: string;
  kp_id?: string;
  name?: string;
  label?: string;
  course?: string;
  description?: string;
  bloom_level?: string;
  [key: string]: unknown;
}

export function listKnowledgePoints(course = "") {
  return getJson<{ kps: KnowledgePoint[]; total?: number }>(
    "/api/v1/knowledge-graph/kps",
    course ? { course } : undefined,
  );
}

export function getKnowledgePoint(kpId: string) {
  return getJson<Record<string, any>>(
    `/api/v1/knowledge-graph/kps/${encodeURIComponent(kpId)}`,
  );
}

export function searchKnowledgeGraph(q: string, topK = 5) {
  return getJson<{ query: string; results: Array<Record<string, any>>; total: number }>(
    "/api/v1/knowledge-graph/search",
    { q, top_k: topK },
  );
}

export function getGraphStats() {
  return getJson<{ kp_count?: number; relation_count?: number; [key: string]: unknown }>(
    "/api/v1/knowledge-graph/stats",
  );
}

// ============================================================
// 3D 力导向图数据（含 BKT 掌握度着色）
// ============================================================
export interface Graph3dNode {
  id: string;
  name: string;
  mastery: number;
  bloom_level: string;
  bloom_color: string;
  size_hint: number;
  course: string;
  // Plan D · 3.4 — BKT mastery hover 用
  bkt_trend?: "improving" | "declining" | "stable" | "insufficient_data";
  bkt_attempts?: number;
}

export interface Graph3dEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface Graph3dResponse {
  nodes: Graph3dNode[];
  edges: Graph3dEdge[];
  stats: {
    total_kps?: number;
    mastered_kps?: number;
    in_progress_kps?: number;
    untouched_kps?: number;
  };
  note?: string;
}

export function getGraph3d(userId: string, course = "artificial_intelligence", maxNodes = 80) {
  return getJson<Graph3dResponse>("/api/v1/knowledge-graph/3d", {
    user_id: userId,
    course,
    max_nodes: maxNodes,
  });
}

export function getNeighbors(kp: string, depth = 2, direction: "prereq" | "postreq" | "both" = "both") {
  return getJson<Record<string, any>>("/api/v1/knowledge-graph/neighbors", {
    kp,
    depth,
    direction,
  });
}

/** 按 kp_id 精确查找知识点（不等同于语义搜索，用于已知 ID 的快速定位） */
export function lookupKnowledgePoint(kpId: string) {
  return getJson<Record<string, any>>("/api/v1/knowledge-graph/lookup", {
    kp_id: kpId,
  });
}

// 获取学习路径
export function getLearningPath(userId: string, course = "artificial_intelligence") {
  return getJson<{
    path: Array<{ kp_id: string; name: string; order: number }>;
    current_index: number;
  }>("/api/v1/learner/learning_path", {
    user_id: userId,
    course,
  });
}

// 获取知识点掌握度历史趋势
export function getMasteryHistory(
  userId: string,
  kpId: string,
  days = 30,
) {
  return getJson<{
    history: Array<{
      date: string;
      mastery: number;
      attempts: number;
      correct: number;
    }>;
    kp_name: string;
  }>("/api/v1/learner/mastery_history", {
    user_id: userId,
    kp_id: kpId,
    days,
  });
}

// ============================================================
// 双图路径规划（先修图 + 语义相似图）
// ============================================================
export function planDualGraph(userId: string, focusKp: string) {
  return postJson<{
    focus_kp: string;
    focus_kp_name: string;
    main_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string; stage_index: number }>;
    detour_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string; stage_index: number }>;
    remediation_path: Array<{ kp_id: string; title: string; source: string; reason: string; mastery: number | null; bloom: string; stage_index: number }>;
    explanations: Array<{ kind: string; note: string; weakness_handling: string }>;
    stats: { kp_count: number; edge_count: number; similar_count: number; weak_kp_count: number };
  }>("/api/v1/learning-path/dual-graph", {
    user_id: userId,
    focus_kp: focusKp,
    mastery_threshold: 0.6,
    max_steps: 8,
  });
}

// ============================================================
// 掌握度时光机预测（BKT + Kalman 平滑）
// ============================================================
export function getMasteryForecast(userId: string, kpId: string, horizonDays = 30) {
  return getJson<{
    user_id: string;
    kp_id: string;
    current_mastery: number;
    forecast: Array<{ day: number; p_learned: number; ci_low: number; ci_high: number }>;
    milestones: Array<{ day: number; target: number; label: string; p_at_day: number; ci_at_day: number }>;
    summary_text: string;
    ascii_chart: string;
    svg: string;
  }>("/api/v1/cognitive/forecast", {
    user_id: userId,
    kp_id: kpId,
    horizon_days: horizonDays,
    use_kalman: true,
  });
}
