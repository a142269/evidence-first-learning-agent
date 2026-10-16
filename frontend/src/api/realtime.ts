/**
 * 实时学情 API — B owned
 * Chat session 的 6 维实时学情状态
 */
import { getJson } from "@/api/http";

export interface RealtimeState {
  session_id?: string;
  user_id?: string;
  summary: string;
  emotion: string;
  engagement: string;
  confusion: number;
  fatigue: number;
  cognitive_load: number;
  confidence?: number;
  curiosity?: number;
  preferred_reply_style?: string;
  evidence?: string[];
  stuck_topics: string[];
  curiosity_topics: string[];
  next_best_action: string;
}

export function getRealtimeState(sessionId: string) {
  return getJson<{ state: RealtimeState | null }>(`/api/v1/chat/realtime/${sessionId}`);
}
