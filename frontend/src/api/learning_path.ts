/**
 * 学习路径 API
 */
import { getJson, postJson } from "@/api/http";

export interface LearningStage {
  id: number | string;
  title: string;
  topics: string[];
  kp_ids?: string[];
  duration: string;
  resources: string[];
  prerequisites: number[];
  assessment: string;
}

export interface StageLearningItem {
  kp_id: string;
  name: string;
  description: string;
  bloom_level: string;
  difficulty: number;
  estimated_minutes: number;
  mastery_pct: number;
}

export interface StageContentResponse {
  path_id: string;
  stage: { id: string | number; title: string };
  items: StageLearningItem[];
  total: number;
  source: string;
}

export interface LearningPath {
  id: string;
  user_id: string;
  title: string;
  stages: LearningStage[];
  current_stage: number;
  progress: number;
  created_at: number;
  course?: string;
  recommended_by?: string;
  recommended_role?: string;
  metadata?: Record<string, unknown>;
}

export function listPaths(userId?: string) {
  return getJson<{ paths: LearningPath[]; total: number }>(
    "/api/v1/learning-path/list",
    userId ? { user_id: userId } : undefined
  );
}

export function getPath(pathId: string) {
  return getJson<{ path: LearningPath }>(`/api/v1/learning-path/${pathId}`);
}

export function getStageContent(pathId: string, stageId: string, userId: string) {
  return getJson<StageContentResponse>(
    `/api/v1/learning-path/${encodeURIComponent(pathId)}/stages/${encodeURIComponent(stageId)}/content`,
    { user_id: userId },
  );
}

export function savePath(data: Partial<LearningPath>) {
  return postJson<{ path_id: string; path: LearningPath }>(
    "/api/v1/learning-path/save",
    data as Record<string, unknown>
  );
}

export function updateProgress(pathId: string, stageIndex: number, completed: boolean) {
  return postJson<{ path: LearningPath }>(
    `/api/v1/learning-path/${pathId}/progress`,
    { stage_index: stageIndex, completed }
  );
}
