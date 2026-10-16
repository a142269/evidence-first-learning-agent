/**
 * 学习效果评估 API
 */
import { getJson, postJson } from "@/api/http";

export interface AssessmentRecord {
  external_id?: string;
  type: string;
  score?: number;
  topic?: string;
  duration?: number;
  timestamp: number;
  metadata?: Record<string, any>;
}

export interface AssessmentSummary {
  user_id: string;
  total_sessions: number;
  quiz_avg_score: number;
  resources_used: number;
  questions_asked: number;
  completed_task_ids?: string[];
  recent_records: AssessmentRecord[];
}

export function getAssessment(userId: string) {
  return getJson<AssessmentSummary>(`/api/v1/assessment/${userId}`);
}

export function addAssessmentRecord(userId: string, record: Partial<AssessmentRecord>) {
  return postJson<{ status: string; record: AssessmentRecord }>(
    `/api/v1/assessment/${userId}/record`,
    record as Record<string, unknown>,
  );
}
