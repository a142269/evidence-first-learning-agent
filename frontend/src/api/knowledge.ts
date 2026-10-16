/**
 * 知识库管理 API —— /api/v1/knowledge/*
 */
import { deleteJson, getJson, postForm, postJson } from "@/api/http";

export interface KnowledgeStatus {
  status?: string;
  indexed?: boolean;
  chunks?: number;
  courses?: string[];
  [key: string]: unknown;
}

export function getKnowledgeStatus() {
  return getJson<KnowledgeStatus>("/api/v1/knowledge/status");
}

export function indexCourse(courseName: string) {
  return postJson<Record<string, any>>(
    `/api/v1/knowledge/index/${encodeURIComponent(courseName)}`,
  );
}

export interface CourseInfo {
  id: string;
  name?: string;
  display_name?: string;
  description?: string;
  status?: string;
  builtin?: boolean;
  md_count?: number;
  file_count?: number;
  has_knowledge_map?: boolean;
  documents?: { total: number; indexed: number; rejected: number; failed: number };
  [key: string]: unknown;
}

export function listCourses() {
  return getJson<{ courses: Array<string | CourseInfo> }>(
    "/api/v1/knowledge/courses",
  );
}

// ================================================================
// 知识库平台化（2026-07-16）：教师端管理 API — /api/v1/teacher/knowledge/*
// ================================================================
export interface KnowledgeDocument {
  id: string;
  course: string;
  filename: string;
  file_type: string;
  size_bytes: number;
  status: "uploaded" | "parsing" | "indexed" | "failed" | "rejected";
  chunk_count: number;
  audit?: {
    verdict?: string;
    issues?: Array<{ level: string; category: string; detail: string }>;
    [key: string]: unknown;
  };
  error_msg?: string;
  uploaded_by?: string;
  created_at?: number;
}

export interface IngestionTask {
  task_id: string;
  /** Celery reports lower-case task states, e.g. pending / started / success. */
  status: string;
  document?: KnowledgeDocument;
  error?: string;
}

export interface UploadCourseDocumentResponse {
  status: string;
  document?: KnowledgeDocument;
  task_id?: string;
  filename?: string;
  next?: string;
}

export interface HitTestChunk {
  content: string;
  source: string;
  course: string;
  score: number;
  title_hint: string;
}

export function listCoursesAdmin() {
  return getJson<{ courses: CourseInfo[]; total: number }>(
    "/api/v1/teacher/knowledge/courses",
  );
}

export function createCourse(payload: {
  slug: string;
  display_name: string;
  description?: string;
  status?: string;
}) {
  return postJson<{ status: string; course: CourseInfo }>(
    "/api/v1/teacher/knowledge/courses",
    payload,
  );
}

export function archiveCourse(slug: string) {
  return postJson<{ status: string; course: CourseInfo }>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/archive`,
  );
}

export function restoreCourse(slug: string) {
  return postJson<{ status: string; course: CourseInfo }>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/restore`,
  );
}

export interface DeleteCourseResult {
  status: "deleted";
  course: string;
  deleted: Record<string, number>;
  student_records_preserved: boolean;
}

export function deleteCoursePermanently(slug: string, confirmSlug: string) {
  return deleteJson<DeleteCourseResult>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}`,
    { confirm_slug: confirmSlug },
  );
}

export function listCourseDocuments(slug: string) {
  return getJson<{ course: string; documents: KnowledgeDocument[]; allowed_suffixes: string[] }>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/documents`,
  );
}

export function uploadCourseDocument(slug: string, file: File, deepAudit = false) {
  const form = new FormData();
  form.append("file", file);
  return postForm<UploadCourseDocumentResponse>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/documents?deep_audit=${deepAudit}`,
    form,
  );
}

export function getIngestionTask(taskId: string) {
  return getJson<IngestionTask>(
    `/api/v1/teacher/knowledge/ingestion-tasks/${encodeURIComponent(taskId)}`,
  );
}

export function deleteCourseDocument(docId: string) {
  return deleteJson<{ status: string }>(
    `/api/v1/teacher/knowledge/documents/${encodeURIComponent(docId)}`,
  );
}

export function reindexCourse(slug: string, force = false) {
  return postJson<{ status: string; rag: Record<string, unknown> }>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/reindex?force=${force}`,
  );
}

export function hitTest(payload: { query: string; course?: string; top_k?: number }) {
  return postJson<{ query: string; total: number; chunks: HitTestChunk[] }>(
    "/api/v1/teacher/knowledge/hit-test",
    payload,
  );
}

export function generateCourseMap(slug: string) {
  return postJson<{ status: string; node_count: number; kg_seeded: number }>(
    `/api/v1/teacher/knowledge/courses/${encodeURIComponent(slug)}/generate-map`,
  );
}
