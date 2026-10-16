/**
 * 课程群聊 API — 学生 / 教师 / AI Agent 共享的持久化异步群聊。
 * room_id = "{course}:{student_id}"，消息写入后刷新即可见（不做 WebSocket）。
 */
import { getJson, postJson } from "@/api/http";

export type GroupChatSenderRole = "student" | "teacher" | "admin" | "agent" | "system";

export type GroupChatMessageType =
  | "text"
  | "teacher_message"
  | "agent_reply"
  | "resource_card"
  | "path_card"
  | "system_notice";

export interface GroupChatMessage {
  id: string;
  room_id: string;
  sender_id: string;
  sender_name: string;
  sender_role: GroupChatSenderRole;
  content: string;
  message_type: GroupChatMessageType;
  payload: Record<string, any>;
  created_at: number;
}

export function buildRoomId(course: string, studentId: string): string {
  return `${course}:${studentId}`;
}

export function listGroupChatMessages(roomId: string, limit = 200, after = 0) {
  return getJson<{ room_id: string; messages: GroupChatMessage[]; total: number }>(
    `/api/v1/group-chat/${encodeURIComponent(roomId)}/messages`,
    { limit, after: after || undefined },
  );
}

export function postGroupChatMessage(
  roomId: string,
  params: {
    sender_id: string;
    sender_name: string;
    sender_role: GroupChatSenderRole;
    content: string;
    message_type?: GroupChatMessageType;
    payload?: Record<string, any>;
  },
) {
  return postJson<{ status: string; message: GroupChatMessage }>(
    `/api/v1/group-chat/${encodeURIComponent(roomId)}/messages`,
    params,
  );
}
