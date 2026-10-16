import { download, request } from "@/api/client";
import type {
  CursorPage, MobileMember, MobileMessage, MobileMistake, MobileResource, MobileRoom, MobileUser,
} from "@/types";

export function login(account: string, password: string) {
  return request<{ access_token: string; user: MobileUser; expires_at: string }>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify({ account, password, role: "student", remember: true }) },
  );
}
export const getMe = () => request<MobileUser>("/api/v1/auth/me");
export const logout = () => request<{ status: string }>("/api/v1/auth/logout", { method: "POST", body: "{}" });
export const listRooms = () => request<{ rooms: MobileRoom[] }>("/api/v1/mobile/rooms");
export const listMembers = (roomId: string) => request<{ members: MobileMember[] }>(`/api/v1/mobile/rooms/${roomId}/members`);
export const listMessages = (roomId: string, cursor = "") => request<CursorPage<MobileMessage>>(
  `/api/v1/mobile/rooms/${roomId}/messages`, {}, { cursor, limit: 40 },
);
export const sendMessage = (roomId: string, body: Record<string, unknown>) => request<{ message: MobileMessage }>(
  `/api/v1/mobile/rooms/${roomId}/messages`, { method: "POST", body: JSON.stringify(body) },
);
export const markRead = (roomId: string, messageId: string) => request(
  `/api/v1/mobile/rooms/${roomId}/read`, { method: "POST", body: JSON.stringify({ last_message_id: messageId }) },
);
export const listResources = (query: Record<string, string | number | undefined>) => request<CursorPage<MobileResource>>(
  "/api/v1/mobile/resources", {}, query,
);
export const getResource = (id: string) => request<{ resource: MobileResource }>(`/api/v1/mobile/resources/${id}`);
export const downloadResource = (id: string) => download(`/api/v1/mobile/resources/${id}/download`);
export const listMistakes = (query: Record<string, string | number | undefined>) => request<CursorPage<MobileMistake>>(
  "/api/v1/mobile/mistakes", {}, query,
);
export const createMistake = (body: Record<string, unknown>) => request<{ mistake_id: string }>(
  "/api/v1/mobile/mistakes", { method: "POST", body: JSON.stringify(body) },
);
export const getMistake = (id: string) => request<{ mistake: MobileMistake }>(`/api/v1/mobile/mistakes/${id}`);
export const mistakeAction = (id: string, action: "analyze" | "remediation" | "variants" | "resolve") => request<any>(
  `/api/v1/mobile/mistakes/${id}/${action}`, { method: "POST", body: "{}" },
);
