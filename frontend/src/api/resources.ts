/**
 * 资源管理 API
 */
import { deleteJson, getBlob, getJson, postJson } from "@/api/http";

export interface Resource {
  id: string;
  user_id: string;
  type: string;
  title: string;
  content: string;
  content_type: string;
  agent_name: string;
  metadata: Record<string, any>;
  created_at: number;
  tags: string[];
}

export interface ResourceType {
  key: string;
  label: string;
  icon: string;
  agent: string;
}

export function listResources(params?: {
  user_id?: string;
  resource_type?: string;
  course?: string;
  limit?: number;
}) {
  return getJson<{ resources: Resource[]; total: number }>(
    "/api/v1/resources/list",
    params as Record<string, string | number>
  );
}

export function getResource(resourceId: string) {
  return getJson<{ resource: Resource }>(`/api/v1/resources/${resourceId}`);
}

export function downloadResourceAttachment(resourceId: string, userId?: string) {
  const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
  return getBlob(`/api/v1/resources/${encodeURIComponent(resourceId)}/download${query}`);
}

export function saveResource(data: Partial<Resource>) {
  return postJson<{ resource_id: string; resource: Resource }>(
    "/api/v1/resources/save",
    data as Record<string, unknown>
  );
}

export function deleteResource(resourceId: string) {
  return deleteJson<{ status: string }>(
    `/api/v1/resources/${encodeURIComponent(resourceId)}`,
  );
}

export function getResourceTypes() {
  return getJson<{ types: ResourceType[] }>("/api/v1/resources/types");
}
