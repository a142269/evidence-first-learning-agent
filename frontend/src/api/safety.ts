/**
 * 安全红队 API —— /api/v1/safety/*
 * 答案泄露对抗测试（Adversarial Leakage Red-Teaming）
 */
import { postJson, getJson } from "@/api/http";

export interface AdversarialScenario {
  strategy: string;
  inducer: string;
  tutor_response?: string;
  scores?: Record<string, any>;
  revised_response?: string;
  issues?: string[];
  [key: string]: unknown;
}

export interface AdversarialLeakageResult {
  passed: boolean;
  leakage_score: number;
  scaffolding_score: number;
  misconception_risk: number;
  overall_risk: number;
  scenarios: AdversarialScenario[];
  recommendation: string;
  ind_count: number;
  [key: string]: unknown;
}

export function runAdversarialLeakage(params: {
  question: string;
  correct_answer: string;
  tutor_responses?: Record<string, string>;
  extra_inducers?: Array<{ strategy: string; inducer: string }>;
  kp_ids?: string[];
  bloom_level?: string;
}) {
  return postJson<AdversarialLeakageResult>(
    "/api/v1/safety/adversarial-leakage",
    params as Record<string, unknown>,
  );
}

export function listInducerStrategies() {
  return getJson<{
    strategies: Array<{ strategy: string; inducer: string }>;
  }>("/api/v1/safety/adversarial-leakage/strategies");
}
