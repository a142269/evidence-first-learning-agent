export type AuthRole = "student" | "teacher" | "admin";

export interface MobileUser {
  account: string;
  display_name: string;
  role: AuthRole;
}

export interface MobileMember {
  user_id: string;
  display_name: string;
  role: "student" | "teacher" | "agent" | "system";
  joined_at: number;
}

export interface MobileMessage {
  id: string;
  room_id: string;
  sender_id: string;
  sender_name: string;
  sender_role: MobileMember["role"];
  content: string;
  message_type: "text" | "resource_card" | "agent_reply" | "system_notice";
  client_message_id: string;
  reply_to_id: string | null;
  mentions: string[];
  payload: Record<string, unknown>;
  created_at: number;
}

export interface MobileRoom {
  id: string;
  course: string;
  name: string;
  description: string;
  avatar_key: string;
  room_type: "group" | "direct";
  peer: MobileMember | null;
  member_count: number;
  unread_count: number;
  last_message: MobileMessage | null;
  created_at: number;
}

export interface MobileResource {
  id: string;
  user_id: string;
  type: string;
  title: string;
  content: string;
  content_type: string;
  agent_name: string;
  metadata: Record<string, any>;
  tags: string[];
  created_at: number;
}

export interface MobileMistake {
  id: string;
  user_id: string;
  kp_id: string;
  question: string;
  student_answer: string;
  correct_answer: string;
  error_type: string;
  analysis: string;
  created_at: number;
  resolved: boolean;
  course?: string;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
  total?: number;
}
