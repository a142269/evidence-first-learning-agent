/**
 * 学习画像 API
 */
import { getJson, postJson } from "@/api/http";

export interface ProfileDimension {
  label: string;
  icon: string;
  description: string;
}

export interface ProfileData {
  user_id: string;
  profile: Record<string, any>;
  completeness: number;
  filled_dimensions: number;
  total_dimensions: number;
}

export function getProfileDimensions() {
  return getJson<{ dimensions: Record<string, ProfileDimension> }>(
    "/api/v1/profile/dimensions"
  );
}

export function getProfile(userId: string) {
  return getJson<ProfileData>(`/api/v1/profile/${userId}`);
}

export function updateProfile(userId: string, updates: Record<string, any>) {
  return postJson<ProfileData>(`/api/v1/profile/${userId}/update`, { updates });
}

export function resetProfile(userId: string) {
  return postJson<{ status: string }>(`/api/v1/profile/${userId}/reset`);
}

export interface ProfileSnapshot {
  version: number;
  changed_keys: string[];
  changed_labels: string[];
  source: string;
  profile: Record<string, any>;
  created_at: number;
}

export function getProfileHistory(userId: string, limit = 10) {
  return getJson<{ user_id: string; count: number; snapshots: ProfileSnapshot[] }>(
    `/api/v1/profile/${userId}/history`,
    { limit },
  );
}
