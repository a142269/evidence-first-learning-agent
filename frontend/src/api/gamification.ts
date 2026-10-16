/**
 * 游戏化激励 API —— /api/v1/gamification/*
 */
import { getJson, postJson } from "@/api/http";

export interface GamificationProfile {
  user_id: string;
  xp: number;
  level: number;
  xp_to_next_level: number;
  streak_days: number;
  achievements: string[];
  achievements_total: number;
  achievements_earned: number;
  achievement_codes?: string[];
  checked_in_today?: boolean;
}

export function getGamification(userId: string) {
  return getJson<GamificationProfile>(
    `/api/v1/gamification/${encodeURIComponent(userId)}`,
  );
}

export function addXp(userId: string, action: string, count = 1) {
  return postJson<{ user_id: string; xp_gained: number; total_xp: number; level: number }>(
    `/api/v1/gamification/${encodeURIComponent(userId)}/xp`,
    { action, count },
  );
}

export function unlockAchievement(userId: string, achievementKey: string) {
  return postJson<Record<string, any>>(
    `/api/v1/gamification/${encodeURIComponent(userId)}/achievement`,
    { achievement_key: achievementKey },
  );
}

export function dailyCheckin(userId: string) {
  return postJson<{
    status: "checked_in" | "already_checked_in";
    user_id: string;
    streak_days: number;
    bonus_xp: number;
    total_xp: number;
    level: number;
  }>(`/api/v1/gamification/${encodeURIComponent(userId)}/checkin`);
}
