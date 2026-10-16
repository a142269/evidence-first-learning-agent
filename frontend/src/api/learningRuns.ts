import { getAuthToken } from "@/utils/auth";
import { ApiError, getApiBaseUrl, getJson, postJson } from "@/api/http";
import { consumeLearningStream, type LearningEvent } from "@/api/learningStream";

export interface LearningRun {
  run_id: string;
  status: string;
  request: { message: string; course_id: string; session_id: string; mode: string };
  result: Record<string, any>;
}

export function getLearningRun(id: string) {
  return getJson<LearningRun>(`/api/v2/learning-runs/${encodeURIComponent(id)}`);
}

export function reconcileLearningRun(id: string) {
  return postJson<LearningRun>(`/api/v2/learning-runs/${encodeURIComponent(id)}/reconcile`);
}

export function getLearningRunEvents(id: string, after = 0) {
  return getJson<{ run_id: string; events: Array<{ id: string; node: string; status: string; event_sequence: number; data: Record<string, any> }> }>(
    `/api/v2/learning-runs/${encodeURIComponent(id)}/events?after=${after}`,
  );
}

export async function continueLearningRun(id: string, onEvent: (event: LearningEvent) => void, signal: AbortSignal) {
  const response = await fetch(`${getApiBaseUrl()}/api/v2/learning-runs/${encodeURIComponent(id)}/continue`, {
    method: "POST", signal,
    headers: { Accept: "text/event-stream", Authorization: `Bearer ${getAuthToken()}` },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(response.status, String(payload.detail || "request_failed"));
  }
  if (!response.body) throw new Error("stream_unavailable");
  await consumeLearningStream(response.body, onEvent);
}

export async function streamLearningRun(
  body: Record<string, unknown>, onEvent: (event: LearningEvent) => void,
  signal: AbortSignal, resumeId?: string,
) {
  const path = resumeId ? `${encodeURIComponent(resumeId)}/resume` : "stream";
  const response = await fetch(`${getApiBaseUrl()}/api/v2/learning-runs/${path}`, {
    method: "POST", signal,
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", Authorization: `Bearer ${getAuthToken()}` },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new ApiError(response.status, String(payload.detail || "request_failed"));
  }
  if (!response.body) throw new Error("stream_unavailable");
  await consumeLearningStream(response.body, onEvent);
}
