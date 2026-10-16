/**
 * 教师管理端 API — 学情分析 / 课程资源 / Agent 管理 / 路径推荐 / 群聊消息。
 * 需要 teacher / admin 角色的登录 token（http.ts 自动携带）。
 */
import { deleteJson, getBlob, getJson, patchJson, postForm, postJson } from "@/api/http";
import type { GroupChatMessage } from "@/api/groupChat";

// ============ 学生与学情 ============
export interface TeacherStudentBrief {
  user_id: string;
  display_name: string;
  course: string;
  mastery_avg: number | null;
  mistakes_open: number;
  last_active: number;
  profile_completeness_pct?: number;
  deletable?: boolean;
}

export interface MasteryItem {
  kp_id: string;
  kp_name: string;
  mastery: number;
}

export interface StudentSummary {
  user_id: string;
  course: string;
  profile: Record<string, any>;
  mastery: { average: number | null; weakest: MasteryItem[]; strongest: MasteryItem[] };
  mistakes: {
    open_count: number;
    recent: Array<{ id: string; kp_id: string | null; error_type: string; question: string; created_at: number }>;
  };
  paths: Array<{ id: string; title: string; progress: number; stages_count: number; created_at: number; recommended_by: string }>;
  resources: { total: number; recent: Array<{ id: string; title: string; type: string; created_at: number }> };
  risks: Array<{ level: "high" | "medium" | "low"; message: string }>;
}

export function listStudents() {
  return getJson<{ students: TeacherStudentBrief[]; total: number }>("/api/v1/teacher/students");
}

export function getStudentSummary(userId: string, course = "artificial_intelligence") {
  return getJson<StudentSummary>(
    `/api/v1/teacher/students/${encodeURIComponent(userId)}/summary`,
    { course },
  );
}

export interface DeleteStudentResult {
  status: "deleted";
  user_id: string;
  account_removed: boolean;
  deleted_total: number;
  deleted_counts: Record<string, number>;
}

export function deleteStudentData(userId: string) {
  return deleteJson<DeleteStudentResult>(
    `/api/v1/teacher/students/${encodeURIComponent(userId)}`,
  );
}

export interface RestoreStudentAccountResult {
  status: "restored";
  user_id: string;
  display_name: string;
}

/** 教师为已有学习数据的学生恢复或重置登录密码。 */
export function restoreStudentAccount(userId: string, newPassword: string) {
  return postJson<RestoreStudentAccountResult>(
    `/api/v1/teacher/students/${encodeURIComponent(userId)}/restore-account`,
    { new_password: newPassword },
  );
}

// ============ 班级学情看板 ============
export interface ClassWeakKp {
  kp_id: string;
  kp_name: string;
  avg_mastery: number;
  students_tracked: number;
  students_below_60: number;
  mistake_count: number;
}

export interface ClassRiskStudent {
  user_id: string;
  display_name: string;
  level: "high" | "medium" | "low";
  risk_score_pct: number;
  activity_level: "active" | "dormant" | "inactive";
  mastery_avg: number | null;
  mistakes_open: number;
  last_active: number;
  reasons: string[];
}

export interface ClassTrendPoint {
  date: string;
  activity_count: number;
  avg_score: number | null;
}

export interface ClassAnalytics {
  course: string;
  generated_at: number;
  student_count: number;
  students: Array<{
    user_id: string;
    display_name: string;
    activity_level: "active" | "dormant" | "inactive";
    mastery_pct: number;
    mistakes_open: number;
    last_active: number;
    profile_completeness_pct: number;
  }>;
  active_7d: number;
  active_30d: number;
  mistakes_open_total: number;
  mastery: {
    overall_avg: number | null;
    no_data_count: number;
    distribution: Array<{ bucket: string; count: number }>;
    trend: ClassTrendPoint[];
  };
  weak_kps: ClassWeakKp[];
  error_distribution: Array<{
    code: string;
    label: string;
    category: string;
    count: number;
    ratio: number;
    ratio_pct: number;
  }>;
  activity: {
    active_7d: string[];
    dormant_7_30: string[];
    inactive_30p: string[];
  };
  risk_students: ClassRiskStudent[];
}

export function getClassAnalytics(params: {
  course?: string;
  days?: number;
  weak_top?: number;
  risk_top?: number;
} = {}) {
  return getJson<ClassAnalytics>("/api/v1/teacher/analytics/class", params as Record<string, any>);
}

// ============ 教学共创（教师数据 → 既有多 Agent 编排） ============
export type TeachingCopilotAction =
  | "class_diagnosis"
  | "learning_path"
  | "student_intervention";

export interface TeachingCopilotResult {
  action: TeachingCopilotAction;
  action_label: string;
  scope: "class" | "student";
  student_id: string;
  snapshot: Record<string, any>;
  session_id: string;
  content: string;
  content_type: string;
  primary_agent: string;
  agents_invoked: Array<{ name: string; success: boolean; content_type: string }>;
  quality?: Record<string, any>;
  safety?: { level: string; reason: string };
  success: boolean;
  error?: string;
}

export function consultTeachingCopilot(payload: {
  action: TeachingCopilotAction;
  scope: "class" | "student";
  user_id?: string;
  course?: string;
  instruction?: string;
  /** 留空时由系统按任务调度多个内置 Agent；填写则定向调用已启用 Agent。 */
  agent_name?: string;
}) {
  return postJson<TeachingCopilotResult>("/api/v1/teacher/copilot/consult", payload);
}

// ============ 课程资源 ============
export interface TeacherResource {
  id: string;
  user_id: string;
  type: string;
  title: string;
  content: string;
  content_type: string;
  agent_name: string;
  metadata: {
    course?: string;
    scope?: "course" | "student";
    status?: "draft" | "published" | "archived";
    created_by?: string;
    target_user_ids?: string[];
    kp_ids?: string[];
    attachment?: {
      filename: string;
      storage_key: string;
      size_bytes: number;
      media_type: string;
    };
    [key: string]: any;
  };
  tags: string[];
  created_at: number;
}

export function listTeacherResources(params: { course?: string; status?: string; q?: string } = {}) {
  return getJson<{ resources: TeacherResource[]; total: number }>("/api/v1/teacher/resources", params);
}

export function createTeacherResource(payload: {
  title: string;
  type?: string;
  content?: string;
  course?: string;
  scope?: "course" | "student";
  status?: "draft" | "published" | "archived";
  tags?: string[];
  kp_ids?: string[];
  target_user_ids?: string[];
  created_by?: string;
}) {
  return postJson<{ resource_id: string; resource: TeacherResource }>("/api/v1/teacher/resources", payload);
}

export function createTeacherResourceFromArtifact(payload: {
  artifact_id: string;
  title: string;
  type: "ppt" | "video";
  content?: string;
  course?: string;
  scope?: "course" | "student";
  status?: "draft" | "published" | "archived";
  tags?: string[];
  kp_ids?: string[];
  target_user_ids?: string[];
  created_by?: string;
}) {
  return postJson<{ resource_id: string; resource: TeacherResource }>(
    "/api/v1/teacher/resources/from-artifact",
    payload,
  );
}

export function uploadTeacherResource(payload: {
  file: File;
  title?: string;
  resourceType?: string;
  course?: string;
  scope?: "course" | "student";
  status?: "draft" | "published" | "archived";
  tags?: string;
  kpIds?: string;
  targetUserIds?: string;
  createdBy?: string;
}) {
  const form = new FormData();
  form.set("file", payload.file);
  form.set("title", payload.title || "");
  form.set("resource_type", payload.resourceType || "document");
  form.set("course", payload.course || "artificial_intelligence");
  form.set("scope", payload.scope || "course");
  form.set("status", payload.status || "draft");
  form.set("tags", payload.tags || "");
  form.set("kp_ids", payload.kpIds || "");
  form.set("target_user_ids", payload.targetUserIds || "");
  form.set("created_by", payload.createdBy || "teacher");
  return postForm<{ resource_id: string; resource: TeacherResource }>(
    "/api/v1/teacher/resources/upload",
    form,
  );
}

export function updateTeacherResource(resourceId: string, payload: Record<string, unknown>) {
  return patchJson<{ resource: TeacherResource }>(
    `/api/v1/teacher/resources/${encodeURIComponent(resourceId)}`,
    payload,
  );
}

export function deleteTeacherResource(resourceId: string) {
  return deleteJson<{ status: string }>(`/api/v1/teacher/resources/${encodeURIComponent(resourceId)}`);
}

export function downloadTeacherResource(resourceId: string) {
  return getBlob(`/api/v1/teacher/resources/${encodeURIComponent(resourceId)}/download`);
}

export function assignResourceToStudent(payload: {
  resource_id: string;
  user_id: string;
  course?: string;
  note?: string;
  sender_id?: string;
  sender_name?: string;
}) {
  return postJson<{ status: string; resource: TeacherResource; message: GroupChatMessage; room_id: string }>(
    "/api/v1/teacher/assignments/resource",
    payload,
  );
}

// ============ 路径推荐 ============
export function assignPathToStudent(payload: {
  user_id: string;
  title: string;
  stages: Array<string | { name: string; desc?: string }>;
  course?: string;
  note?: string;
  sender_id?: string;
  sender_name?: string;
}) {
  return postJson<{ status: string; path: Record<string, any>; message: GroupChatMessage; room_id: string }>(
    "/api/v1/teacher/assignments/path",
    payload,
  );
}

// ============ Agent 配置 ============
export interface AgentConfig {
  key: string;
  name: string;
  title: string;
  avatar: string;
  role_desc: string;
  system_prompt: string;
  capabilities: string[];
  allowed_tools: string[];
  enabled: boolean;
  builtin: boolean;
  created_by: string;
  created_at: number;
  updated_at: number;
}

export function listAgentConfigs() {
  return getJson<{ agents: AgentConfig[]; total: number }>("/api/v1/teacher/agents");
}

export function createAgentConfig(payload: Partial<AgentConfig>) {
  return postJson<{ status: string; agent: AgentConfig }>("/api/v1/teacher/agents", payload as any);
}

export function updateAgentConfig(agentKey: string, payload: Partial<AgentConfig>) {
  return patchJson<{ status: string; agent: AgentConfig }>(
    `/api/v1/teacher/agents/${encodeURIComponent(agentKey)}`,
    payload as any,
  );
}

export function deleteAgentConfig(agentKey: string) {
  return deleteJson<{ status: string }>(`/api/v1/teacher/agents/${encodeURIComponent(agentKey)}`);
}

// ============ 教师发消息 ============
export function sendTeacherMessage(payload: {
  user_id: string;
  content: string;
  course?: string;
  sender_id?: string;
  sender_name?: string;
}) {
  return postJson<{ status: string; message: GroupChatMessage; room_id: string }>(
    "/api/v1/teacher/messages",
    payload,
  );
}

// ============ 增强 1：教师干预日志 ============
export interface InterventionEntry {
  id: string;
  type: string;
  content: string;
  created_at: number;
  responded: boolean;
  payload: Record<string, any>;
}

export interface InterventionStudent {
  user_id: string;
  total: number;
  resource_count: number;
  path_count: number;
  message_count: number;
  responded: number;
  not_responded: number;
  recent: InterventionEntry[];
}

export interface InterventionLog {
  generated_at: number;
  days: number;
  students: InterventionStudent[];
  total_interventions: number;
  total_responded: number;
}

export function listInterventions(params: { user_id?: string; days?: number } = {}) {
  return getJson<InterventionLog>("/api/v1/teacher/interventions", params);
}

// ============ 增强 2：班级知识图谱热力图 ============
export interface KnowledgeMapNode {
  id: string;
  name: string;
  description: string;
  avg_mastery: number | null;
  students_tracked: number;
  students_below_60: number;
  open_mistakes: number;
  bloom_level: string;
  difficulty: string;
}

export interface KnowledgeMapEdge {
  source: string;
  target: string;
  relation_type: string;
  weight: number;
}

export interface KnowledgeMap {
  course: string;
  nodes: KnowledgeMapNode[];
  edges: KnowledgeMapEdge[];
  generated_at: number;
}

export function getKnowledgeMap(course = "artificial_intelligence") {
  return getJson<KnowledgeMap>("/api/v1/teacher/analytics/knowledge-map", { course });
}

// ============ 增强 3：学生对比分析 ============
export interface CompareStudent {
  user_id: string;
  mastery_avg: number | null;
  mastery_vector: number[];
  mistakes_open: number;
  last_active: number;
  weakest: Array<{ kp_id: string; kp_name: string; mastery: number }>;
  strongest: Array<{ kp_id: string; kp_name: string; mastery: number }>;
}

export interface CompareResult {
  course: string;
  generated_at: number;
  students: CompareStudent[];
  kp_ids: string[];
}

export function compareStudents(userIds: string[], course = "artificial_intelligence") {
  return getJson<CompareResult>("/api/v1/teacher/analytics/compare", {
    user_ids: userIds.join(","),
    course,
  });
}

// ============ 增强 4：班级学情报告导出 ============
export function exportClassReport(params: { course?: string; days?: number } = {}) {
  return getBlob("/api/v1/teacher/analytics/class/export", params);
}

// ============ 增强 5：错题批量处理 ============
export function batchResolveMistakes(payload: {
  mistake_ids: string[];
  action: "resolve" | "unresolve";
}) {
  return postJson<{
    status: string;
    action: string;
    action_label: string;
    requested: number;
    changed: number;
    skipped: number;
  }>("/api/v1/teacher/mistakes/batch-resolve", payload as any);
}
