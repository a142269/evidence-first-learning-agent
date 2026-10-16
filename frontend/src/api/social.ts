/**
 * 学习社交推荐 API —— /api/v1/social/*
 */
import { getJson } from "@/api/http";

export interface SocialSuggestion {
  user_id?: string;
  peer_id?: string;
  score?: number;
  reason?: string;
  explanation?: string;
  display_name?: string;
  role?: string;
  [key: string]: unknown;
}

export interface SocialSuggestionsResponse {
  user_id: string;
  suggestions: SocialSuggestion[];
  total: number;
  privacy_note?: string;
  error?: string;
}

export function getPeerSuggestions(userId: string, limit = 5) {
  return getJson<SocialSuggestionsResponse>("/api/v1/social/peer-suggestions", {
    user_id: userId,
    limit,
  });
}

export function getTutorSuggestions(userId: string, limit = 3) {
  return getJson<SocialSuggestionsResponse>("/api/v1/social/tutor-suggestions", {
    user_id: userId,
    limit,
  });
}
