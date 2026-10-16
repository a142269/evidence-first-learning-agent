/**
 * 系统指标 API —— /api/v1/metrics/*
 */
import { getJson } from "@/api/http";

export interface MetricsSummary {
  uptime_seconds: number;
  artifacts: {
    total: number;
    by_type: Record<string, number>;
    generated_total: number;
    persisted_total: number;
  };
  llm: {
    calls_total: number;
    live_calls_total: number;
    persisted_agent_calls_total: number;
  };
  agents: {
    failures_total: number;
    runs_total: number;
    successful_runs: number;
    success_rate_pct: number;
    tool_calls_total: number;
    average_duration_ms: number;
    runs_by_workflow: Record<string, number>;
  };
  pipeline: { stages_total: number; active_sessions: number };
}

export interface MetricsHealth {
  status?: string;
  checks?: Record<string, { ok: boolean; error?: string }>;
  [key: string]: unknown;
}

export function getMetricsSummary() {
  return getJson<MetricsSummary>("/api/v1/metrics/summary");
}

export function getMetricsHealth() {
  return getJson<MetricsHealth>("/api/v1/metrics/health");
}
