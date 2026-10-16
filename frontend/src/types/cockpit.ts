/**
 * Cockpit 聚合端点 TS 类型
 * 来源：docs/api/cockpit-endpoint.md §4
 * 冻结日期：2026-06-30（冻结前需 A+B 同意改动）
 *
 * 兜底约定：任一子块失败时整体仍 200，子块内附 `error` 字段（§5）。
 */

/* ============ 通用 ============ */

/** 任意子块都可能带 error 字段（永远 200 原则） */
export type WithError<T> = T & { error?: string };

/* ============ 4.1 profile ============ */

export interface ProfileDimensionLevel {
  level?: string;
  score?: number;
  primary?: string;
  mode?: string;
  topics?: string[];
  target?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface ProfileDimensions {
  knowledge_base?: ProfileDimensionLevel;
  cognitive_style?: ProfileDimensionLevel;
  learning_preference?: ProfileDimensionLevel;
  weak_points?: ProfileDimensionLevel;
  learning_goal?: ProfileDimensionLevel;
  learning_goals?: string[];
  self_efficacy?: ProfileDimensionLevel;
  [key: string]: unknown;
}

export interface CockpitProfile {
  dimensions: ProfileDimensions;
  /** 6 维雷达数值，长度恒为 6 */
  radar_6d: number[];
  /** 6 维雷达标签，长度恒为 6 */
  radar_labels: string[];
  /** 8 维画像填充率 0-100 */
  completeness: number;
}

/* ============ 4.2 kg ============ */

export interface KgNeighbor1Hop {
  kp_id: string;
  relation_type: string;
  weight: number;
}

export interface KgNeighbor2Hop {
  id: string;
  name: string;
  distance: number;
}

export interface KgEdge {
  source: string;
  target: string;
  type: string;
}

export interface KgNodeMeta {
  id: string;
  name: string;
  course?: string;
  [key: string]: unknown;
}

export interface CockpitKg {
  current_kp: string;
  current_kp_meta?: KgNodeMeta;
  neighbors_1hop: KgNeighbor1Hop[];
  neighbors_2hop: KgNeighbor2Hop[];
  edges_2hop: KgEdge[];
}

/* ============ 4.3 forecast ============ */

export interface ForecastPoint {
  day: number;
  mastery: number;
}

export interface ForecastCounterfactual {
  baseline_curve?: ForecastPoint[] | Record<string, number>;
  recommended_curve?: ForecastPoint[] | Record<string, number>;
  expected_gain?: number;
  risk_warning?: string;
}

export interface CockpitForecast {
  kp_id: string;
  horizon_days: number;
  current_mastery: number;
  curve: ForecastPoint[];
  milestones: Array<Record<string, unknown>>;
  counterfactual?: ForecastCounterfactual;
}

/* ============ 4.4 attribution ============ */

export interface MistakeRecord {
  id: string;
  question: string;
  category: string;
  confidence: number;
  resolved: boolean;
}

export interface CockpitAttribution {
  latest_mistakes: MistakeRecord[];
  category_distribution: Record<string, number>;
  total: number;
}

/* ============ 4.5 cov ============ */

export interface CovClaim {
  claim: string;
  verified: boolean;
  sources: string[];
}

export interface CockpitCov {
  recent_claims: CovClaim[];
  total_demo_cases: number;
}

/* ============ 4.6 debate ============ */

export interface DebateTrace {
  round: number;
  expert: string;
  critic: string;
  verdict: string;
}

export interface CockpitDebate {
  recent_traces: DebateTrace[];
  total: number;
}

/* ============ 4.7 safety ============ */

export interface CockpitSafety {
  scaffolding_score?: number;
  answer_leak_risk?: number;
  misconception_reinforcement_risk?: number;
  student_uptake_prompt?: string;
  [key: string]: unknown;
}

/* ============ 4.8 ledger ============ */

export type LedgerSourceType = "textbook" | "kg" | "rag_chunk" | "mistake" | "history" | string;

export interface LedgerClaim {
  claim?: string;
  text?: string;
  confidence?: number;
  best_confidence?: number;
  is_supported?: boolean;
  sources?: Array<{ type?: LedgerSourceType; source_type?: LedgerSourceType; ref: string; confidence?: number; excerpt?: string }> | string[];
  conflict_warning?: boolean | string;
  conflict_note?: string;
  [key: string]: unknown;
}

export interface CockpitLedger {
  claims: LedgerClaim[];
  total_claims?: number;
  supported_claims?: number;
  unsupported_claims?: number;
  conflicts?: number;
  support_rate?: number;
  source_distribution?: Record<LedgerSourceType, number>;
  [key: string]: unknown;
}

/* ============ 顶层 ============ */

export interface CockpitResponse {
  user_id: string;
  generated_at: string;
  profile: WithError<CockpitProfile>;
  kg: WithError<CockpitKg>;
  forecast: WithError<CockpitForecast>;
  attribution: WithError<CockpitAttribution>;
  cov: WithError<CockpitCov>;
  debate: WithError<CockpitDebate>;
  safety: WithError<CockpitSafety>;
  ledger: WithError<CockpitLedger>;
}

/* ============ 查询参数 ============ */

export interface CockpitQuery {
  horizon_days?: number;
  focus_kp?: string;
  sample_response?: string;
  sample_text?: string;
}

/* ============ P1.4 反事实独立端点 ============ */

export interface CounterfactualResponse {
  user_id: string;
  kp_id: string;
  horizon_days: number;
  baseline_curve: ForecastPoint[];
  recommended_curve: ForecastPoint[];
  expected_gain: number;
  risk_warning?: string;
}
