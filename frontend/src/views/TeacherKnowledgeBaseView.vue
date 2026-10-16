<script setup lang="ts">
/**
 * 课程知识库管理（知识库平台化改造 · 2026-07-16）
 *
 * 教师自助完成：新建课程 → 上传文档（KnowledgeGuard 审核）→ 增量索引
 * → 命中测试（对标 Dify 召回测试）→ 一键生成知识点图谱。
 * 全流程零代码变更，"换一门课即生成新页面"。
 */
import { computed, onMounted, ref } from "vue";
import {
  Archive,
  BadgeCheck,
  BookOpen,
  Database,
  FileText,
  Loader2,
  Network,
  Plus,
  RefreshCcw,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-vue-next";

import {
  archiveCourse,
  createCourse,
  deleteCoursePermanently,
  deleteCourseDocument,
  generateCourseMap,
  getIngestionTask,
  hitTest,
  listCourseDocuments,
  listCoursesAdmin,
  reindexCourse,
  restoreCourse,
  uploadCourseDocument,
  type CourseInfo,
  type HitTestChunk,
  type KnowledgeDocument,
} from "@/api/knowledge";
import { useTeacherCourse } from "@/composables/useTeacherCourse";

const { setCourse, loadCourseOptions } = useTeacherCourse();

const courses = ref<CourseInfo[]>([]);
const selectedSlug = ref("");
const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(true);
const docsLoading = ref(false);
const notice = ref("");
const noticeTone = ref<"ok" | "warn" | "error">("ok");

// 新建课程弹窗
const createVisible = ref(false);
const createForm = ref({ slug: "", display_name: "", description: "" });
const creating = ref(false);

// 课程生命周期：归档保留数据；永久删除仅针对已归档的自建课程。
const lifecycleLoading = ref(false);
const deleteCourseOpen = ref(false);
const deleteCourseConfirm = ref("");
const deletingCourse = ref(false);
const deleteCourseError = ref("");

// 上传
const uploading = ref(false);
const deepAudit = ref(false);
const dragActive = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

// 命中测试
const hitQuery = ref("");
const hitLoading = ref(false);
const hitChunks = ref<HitTestChunk[]>([]);
const hitTried = ref(false);

// 图谱生成 / 重建索引
const mapGenerating = ref(false);
const reindexing = ref(false);

// 审核报告展开
const expandedAudit = ref("");

const selectedCourse = computed(
  () => courses.value.find((c) => c.id === selectedSlug.value) || null,
);
const canManageSelectedCourse = computed(() => selectedCourse.value?.builtin !== true);
const selectedCourseArchived = computed(() => selectedCourse.value?.status === "archived");

const statusLabel: Record<string, string> = {
  indexed: "已索引",
  parsing: "解析中",
  uploaded: "已上传",
  failed: "失败",
  rejected: "审核拒绝",
};

function showNotice(message: string, tone: "ok" | "warn" | "error" = "ok") {
  notice.value = message;
  noticeTone.value = tone;
  window.setTimeout(() => {
    if (notice.value === message) notice.value = "";
  }, 5000);
}

const INGESTION_POLL_INTERVAL_MS = 1_000;
const INGESTION_TIMEOUT_MS = 120_000;

function pause(ms: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
}

async function waitForIngestionTask(taskId: string): Promise<KnowledgeDocument> {
  const deadline = Date.now() + INGESTION_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const task = await getIngestionTask(taskId);
    if (task.status === "success" && task.document) return task.document;
    if (["failure", "failed", "revoked"].includes(task.status)) {
      throw new Error(task.error || `异步入库任务失败（${task.status}）`);
    }
    await pause(INGESTION_POLL_INTERVAL_MS);
  }
  throw new Error("异步入库等待超时，请查看 Celery Worker 日志");
}

async function loadCourses(selectFirst = false) {
  loading.value = true;
  try {
    const result = await listCoursesAdmin();
    courses.value = result.courses || [];
    if ((selectFirst || !selectedSlug.value) && courses.value.length) {
      selectedSlug.value = courses.value[0].id;
    }
    if (selectedSlug.value) await loadDocuments();
  } catch (error) {
    showNotice(`课程清单加载失败：${String(error)}`, "error");
  } finally {
    loading.value = false;
  }
}

async function loadDocuments() {
  if (!selectedSlug.value) return;
  docsLoading.value = true;
  try {
    const result = await listCourseDocuments(selectedSlug.value);
    documents.value = result.documents || [];
  } catch (error) {
    showNotice(`文档列表加载失败：${String(error)}`, "error");
  } finally {
    docsLoading.value = false;
  }
}

async function selectCourseCard(slug: string) {
  selectedSlug.value = slug;
  hitChunks.value = [];
  hitTried.value = false;
  await loadDocuments();
}

async function submitCreate() {
  if (!createForm.value.slug.trim() || !createForm.value.display_name.trim()) {
    showNotice("课程标识与显示名必填", "warn");
    return;
  }
  creating.value = true;
  try {
    const result = await createCourse({
      slug: createForm.value.slug.trim(),
      display_name: createForm.value.display_name.trim(),
      description: createForm.value.description.trim(),
    });
    createVisible.value = false;
    createForm.value = { slug: "", display_name: "", description: "" };
    showNotice(`课程「${result.course.display_name}」创建成功，全端课程下拉即刻可见`);
    await loadCourses();
    await selectCourseCard(result.course.id);
    setCourse(result.course.id);
  } catch (error) {
    showNotice(`创建失败：${String(error)}`, "error");
  } finally {
    creating.value = false;
  }
}

async function archiveSelectedCourse() {
  if (!selectedCourse.value || lifecycleLoading.value) return;
  lifecycleLoading.value = true;
  try {
    const result = await archiveCourse(selectedCourse.value.id);
    showNotice(`课程「${result.course.display_name || result.course.id}」已归档，学生端不再展示；知识库与学习证据均已保留。`);
    await loadCourses();
    await loadCourseOptions(true);
  } catch (error) {
    showNotice(`归档失败：${String(error)}`, "error");
  } finally {
    lifecycleLoading.value = false;
  }
}

async function restoreSelectedCourse() {
  if (!selectedCourse.value || lifecycleLoading.value) return;
  lifecycleLoading.value = true;
  try {
    const result = await restoreCourse(selectedCourse.value.id);
    showNotice(`课程「${result.course.display_name || result.course.id}」已恢复发布，重新出现在课程选择器中。`);
    await loadCourses();
    await loadCourseOptions(true);
  } catch (error) {
    showNotice(`恢复失败：${String(error)}`, "error");
  } finally {
    lifecycleLoading.value = false;
  }
}

function openCourseDelete() {
  deleteCourseOpen.value = true;
  deleteCourseConfirm.value = "";
  deleteCourseError.value = "";
}

function closeCourseDelete() {
  if (deletingCourse.value) return;
  deleteCourseOpen.value = false;
  deleteCourseConfirm.value = "";
  deleteCourseError.value = "";
}

async function confirmCourseDelete() {
  if (!selectedCourse.value || deletingCourse.value) return;
  const slug = selectedCourse.value.id;
  if (deleteCourseConfirm.value.trim().toLowerCase() !== slug.toLowerCase()) {
    deleteCourseError.value = "课程标识不匹配，尚未删除。";
    return;
  }
  deletingCourse.value = true;
  deleteCourseError.value = "";
  try {
    const result = await deleteCoursePermanently(slug, deleteCourseConfirm.value.trim());
    const count = result.deleted.documents || 0;
    deleteCourseOpen.value = false;
    deleteCourseConfirm.value = "";
    documents.value = [];
    selectedSlug.value = "";
    setCourse("artificial_intelligence");
    showNotice(`课程「${slug}」已永久删除：清理 ${count} 份知识文档及关联索引；学生历史学习记录已保留。`);
    await loadCourses(true);
    await loadCourseOptions(true);
  } catch (error: any) {
    const detail = error?.detail || error?.message || String(error);
    deleteCourseError.value = detail === "archive_required_before_delete"
      ? "请先归档课程，再执行永久删除。"
      : `永久删除失败：${detail}`;
  } finally {
    deletingCourse.value = false;
  }
}

async function handleFiles(files: FileList | File[] | null) {
  if (!files || !files.length || !selectedSlug.value) return;
  uploading.value = true;
  for (const file of Array.from(files)) {
    try {
      const result = await uploadCourseDocument(selectedSlug.value, file, deepAudit.value);
      const doc = result.document
        ?? (result.task_id ? await waitForIngestionTask(result.task_id) : undefined);
      if (!doc) throw new Error("上传接口未返回文档或异步任务标识");
      if (doc.status === "indexed") {
        showNotice(`「${doc.filename}」已通过 KnowledgeGuard 审核并完成索引（${doc.chunk_count} 个知识块）`);
      } else if (doc.status === "rejected") {
        showNotice(`「${doc.filename}」被 KnowledgeGuard 拒绝入库：${doc.error_msg || "内容安全审核未通过"}`, "error");
      } else {
        showNotice(`「${doc.filename}」处理结果：${statusLabel[doc.status] || doc.status} ${doc.error_msg || ""}`, "warn");
      }
    } catch (error) {
      showNotice(`「${file.name}」上传失败：${String(error)}`, "error");
    }
  }
  uploading.value = false;
  if (fileInputRef.value) fileInputRef.value.value = "";
  await loadDocuments();
  await loadCourses();
}

function onDrop(event: DragEvent) {
  dragActive.value = false;
  handleFiles(event.dataTransfer?.files || null);
}

async function removeDocument(doc: KnowledgeDocument) {
  if (!window.confirm(`确认删除「${doc.filename}」？对应知识块将同步移出检索索引。`)) return;
  try {
    await deleteCourseDocument(doc.id);
    showNotice(`「${doc.filename}」已删除，索引已增量刷新`);
    await loadDocuments();
    await loadCourses();
  } catch (error) {
    showNotice(`删除失败：${String(error)}`, "error");
  }
}

async function runReindex(force: boolean) {
  if (!selectedSlug.value) return;
  reindexing.value = true;
  try {
    const result = await reindexCourse(selectedSlug.value, force);
    const total = (result.rag as any)?.total_chunks ?? "?";
    showNotice(`索引${force ? "全量重建" : "增量刷新"}完成，当前共 ${total} 个知识块`);
  } catch (error) {
    showNotice(`索引刷新失败：${String(error)}`, "error");
  } finally {
    reindexing.value = false;
  }
}

async function runHitTest() {
  if (!hitQuery.value.trim() || !selectedSlug.value) return;
  hitLoading.value = true;
  hitTried.value = true;
  try {
    const result = await hitTest({
      query: hitQuery.value.trim(),
      course: selectedSlug.value,
      top_k: 5,
    });
    hitChunks.value = result.chunks || [];
  } catch (error) {
    showNotice(`命中测试失败：${String(error)}`, "error");
  } finally {
    hitLoading.value = false;
  }
}

async function runGenerateMap() {
  if (!selectedSlug.value) return;
  mapGenerating.value = true;
  try {
    const result = await generateCourseMap(selectedSlug.value);
    showNotice(`知识点图谱已生成：${result.node_count} 个节点，已灌入图谱库（${result.kg_seeded} 个）`);
    await loadCourses();
  } catch (error) {
    showNotice(`图谱生成失败：${String(error)}`, "error");
  } finally {
    mapGenerating.value = false;
  }
}

function formatSize(bytes: number): string {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function auditIssues(doc: KnowledgeDocument) {
  return doc.audit?.issues || [];
}

onMounted(() => loadCourses(true));
</script>

<template>
  <div class="teacher-kb">
    <header class="page-heading">
      <div>
        <h1><Database :size="24" /> 课程知识库</h1>
        <p>新建课程、上传知识文档、审核入库、命中测试 —— 换一门课，无需改一行代码。</p>
      </div>
      <div>
        <button type="button" class="primary-button" @click="createVisible = true">
          <Plus :size="17" /> 新建课程
        </button>
      </div>
    </header>

    <Transition name="fade">
      <div v-if="notice" :class="['notice-bar', noticeTone]">{{ notice }}</div>
    </Transition>

    <!-- 防幻觉双 Agent 防线说明 -->
    <section class="guard-banner" aria-label="防幻觉机制">
      <ShieldCheck :size="20" />
      <div>
        <b>球球 · 刺猬守护 —— 防幻觉双重防线</b>
        <span>
          入库时由 <em>知识审核官 KnowledgeGuard</em> 执行内容安全扫描、注入检测与学术质量审查；
          生成时由 <em>验证链 CoV-Verifier</em> 将 AI 回答逐条对照本知识库核验。
          两个 Agent 同属「刺猬守护」安全体系，多智能体协同保障内容可信。
        </span>
      </div>
    </section>

    <div v-if="loading" class="loading-state"><Loader2 :size="26" class="spin" /><b>正在加载课程清单</b></div>

    <template v-else>
      <!-- 课程卡片 -->
      <section class="course-grid" aria-label="课程列表">
        <article
          v-for="course in courses"
          :key="course.id"
          :class="['course-card', course.id === selectedSlug ? 'active' : '']"
          @click="selectCourseCard(course.id)"
        >
          <header>
            <b>{{ course.display_name || course.id }}</b>
            <span :class="['status-pill', course.status === 'published' ? 'ok' : course.status === 'archived' ? 'archived' : 'draft']">
              {{ course.status === "published" ? "已发布" : course.status === "archived" ? "已归档" : "草稿" }}
            </span>
          </header>
          <p class="course-desc">{{ course.description || "暂无简介" }}</p>
          <footer>
            <span><FileText :size="14" /> {{ course.md_count ?? 0 }} 篇文档</span>
            <span><Upload :size="14" /> {{ course.documents?.total ?? 0 }} 次上传</span>
            <span v-if="course.has_knowledge_map" class="has-map"><Network :size="14" /> 已有图谱</span>
          </footer>
        </article>
      </section>

      <!-- 选中课程工作区 -->
      <section v-if="selectedCourse" class="workspace">
        <div class="workspace-main">
          <header class="workspace-head">
            <h2><BookOpen :size="19" /> {{ selectedCourse.display_name }} · 知识文档</h2>
            <div class="workspace-actions">
              <button type="button" class="secondary-button" :disabled="reindexing" @click="runReindex(false)">
                <Loader2 v-if="reindexing" :size="15" class="spin" /><RefreshCcw v-else :size="15" /> 增量刷新索引
              </button>
              <button type="button" class="secondary-button" :disabled="mapGenerating" @click="runGenerateMap">
                <Loader2 v-if="mapGenerating" :size="15" class="spin" /><Network v-else :size="15" /> 生成知识点图谱
              </button>
              <template v-if="canManageSelectedCourse">
                <button
                  v-if="!selectedCourseArchived"
                  type="button"
                  class="secondary-button"
                  :disabled="lifecycleLoading"
                  @click="archiveSelectedCourse"
                >
                  <Loader2 v-if="lifecycleLoading" :size="15" class="spin" /><Archive v-else :size="15" /> 归档课程
                </button>
                <button
                  v-else
                  type="button"
                  class="secondary-button"
                  :disabled="lifecycleLoading"
                  @click="restoreSelectedCourse"
                >
                  <Loader2 v-if="lifecycleLoading" :size="15" class="spin" /><RotateCcw v-else :size="15" /> 恢复课程
                </button>
                <button
                  type="button"
                  class="danger-button"
                  :disabled="!selectedCourseArchived"
                  :title="selectedCourseArchived ? '永久删除已归档课程' : '请先归档课程'"
                  @click="openCourseDelete"
                >
                  <Trash2 :size="15" /> 永久删除
                </button>
              </template>
            </div>
          </header>

          <section v-if="deleteCourseOpen" class="course-delete-confirmation" aria-labelledby="delete-course-title">
            <h3 id="delete-course-title">永久删除「{{ selectedCourse.display_name || selectedCourse.id }}」？</h3>
            <p>将删除课程目录、{{ selectedCourse.documents?.total ?? documents.length }} 份上传文档、检索索引和课程级知识图谱。学生的画像、学习路径、错题与个人资源将保留。</p>
            <label>
              <span>输入课程标识 <b>{{ selectedCourse.id }}</b> 确认</span>
              <input v-model="deleteCourseConfirm" :placeholder="selectedCourse.id" autocomplete="off" spellcheck="false" @keyup.enter="confirmCourseDelete" />
            </label>
            <p v-if="deleteCourseError" class="delete-course-error" role="alert">{{ deleteCourseError }}</p>
            <div class="delete-course-actions">
              <button type="button" :disabled="deletingCourse" @click="closeCourseDelete">取消</button>
              <button type="button" class="confirm-course-delete" :disabled="deletingCourse" @click="confirmCourseDelete">
                <Loader2 v-if="deletingCourse" :size="15" class="spin" /><Trash2 v-else :size="15" />
                {{ deletingCourse ? "正在删除" : "永久删除课程" }}
              </button>
            </div>
          </section>

          <!-- 上传区 -->
          <div
            :class="['upload-zone', dragActive ? 'drag' : '']"
            @dragover.prevent="dragActive = true"
            @dragleave="dragActive = false"
            @drop.prevent="onDrop"
            @click="fileInputRef?.click()"
          >
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept=".md,.txt,.pdf,.docx"
              hidden
              @change="handleFiles(($event.target as HTMLInputElement).files)"
            />
            <Loader2 v-if="uploading" :size="26" class="spin" />
            <Upload v-else :size="26" />
            <b>{{ uploading ? "上传处理中（解析 → 审核 → 索引）…" : "点击或拖拽上传知识文档" }}</b>
            <span>支持 Markdown / TXT / PDF / Word（≤20MB），上传后自动经 KnowledgeGuard 审核并入检索索引</span>
            <label class="deep-audit" @click.stop>
              <input v-model="deepAudit" type="checkbox" /> 启用大模型深度审查（更慢，逐条列出事实性疑点）
            </label>
          </div>

          <!-- 文档列表 -->
          <div v-if="docsLoading" class="loading-state small"><Loader2 :size="18" class="spin" /> 加载文档列表</div>
          <table v-else-if="documents.length" class="doc-table">
            <thead>
              <tr><th>文档</th><th>大小</th><th>状态</th><th>知识块</th><th>审核</th><th></th></tr>
            </thead>
            <tbody>
              <template v-for="doc in documents" :key="doc.id">
                <tr>
                  <td class="doc-name"><FileText :size="15" /> {{ doc.filename }}</td>
                  <td>{{ formatSize(doc.size_bytes) }}</td>
                  <td><span :class="['status-pill', doc.status]">{{ statusLabel[doc.status] || doc.status }}</span></td>
                  <td>{{ doc.chunk_count || "—" }}</td>
                  <td>
                    <button
                      v-if="auditIssues(doc).length"
                      type="button"
                      class="audit-toggle"
                      @click="expandedAudit = expandedAudit === doc.id ? '' : doc.id"
                    >
                      {{ auditIssues(doc).length }} 条意见
                    </button>
                    <span v-else class="audit-clean"><BadgeCheck :size="15" /> 通过</span>
                  </td>
                  <td>
                    <button type="button" class="icon-button danger" title="删除文档" @click="removeDocument(doc)">
                      <Trash2 :size="15" />
                    </button>
                  </td>
                </tr>
                <tr v-if="expandedAudit === doc.id" class="audit-row">
                  <td colspan="6">
                    <ul>
                      <li v-for="(issue, index) in auditIssues(doc)" :key="index" :class="issue.level">
                        <b>[{{ issue.category }}]</b> {{ issue.detail }}
                      </li>
                    </ul>
                    <p v-if="doc.error_msg" class="audit-error">{{ doc.error_msg }}</p>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
          <div v-else class="empty-state">
            该课程还没有教师上传的文档。内置章节（chapters/）已在检索索引中，可直接做命中测试。
          </div>
        </div>

        <!-- 命中测试面板 -->
        <aside class="hit-panel" aria-label="命中测试">
          <h3><Search :size="17" /> 命中测试</h3>
          <p>模拟学生提问，验证知识库召回质量（返回片段 + 相似度 + 来源，可作引用溯源）。</p>
          <div class="hit-input">
            <input
              v-model="hitQuery"
              placeholder="例如：什么是反向传播？"
              @keydown.enter="runHitTest"
            />
            <button type="button" :disabled="hitLoading || !hitQuery.trim()" @click="runHitTest">
              <Loader2 v-if="hitLoading" :size="15" class="spin" /><Search v-else :size="15" />
            </button>
          </div>
          <div v-if="hitChunks.length" class="hit-results">
            <article v-for="(chunk, index) in hitChunks" :key="index">
              <header>
                <span class="hit-score">{{ (chunk.score * 100).toFixed(1) }}%</span>
                <b>{{ chunk.title_hint || "未命名分块" }}</b>
              </header>
              <p>{{ chunk.content.slice(0, 180) }}{{ chunk.content.length > 180 ? "…" : "" }}</p>
              <footer>来源：{{ chunk.source }}</footer>
            </article>
          </div>
          <div v-else-if="hitTried && !hitLoading" class="empty-state small">
            未召回任何片段 —— 严格模式下该问题将回答「知识库未覆盖」而非编造内容。
          </div>
        </aside>
      </section>
    </template>

    <!-- 新建课程弹窗 -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
          <div class="modal-card" role="dialog" aria-label="新建课程">
            <button type="button" class="modal-close" aria-label="关闭" @click="createVisible = false"><X :size="18" /></button>
            <h3><Plus :size="18" /> 新建课程</h3>
            <label>
              <span>课程标识（英文小写+下划线，作为目录名）</span>
              <input v-model="createForm.slug" placeholder="computer_network" />
            </label>
            <label>
              <span>课程显示名</span>
              <input v-model="createForm.display_name" placeholder="计算机网络" />
            </label>
            <label>
              <span>课程简介（可选）</span>
              <textarea v-model="createForm.description" rows="3" placeholder="课程定位、覆盖章节等" />
            </label>
            <button type="button" class="primary-button wide" :disabled="creating" @click="submitCreate">
              <Loader2 v-if="creating" :size="16" class="spin" /> 创建课程
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped lang="scss">
.teacher-kb {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;

  h1 { display: flex; align-items: center; gap: 10px; font-size: 24px; margin: 0; }
  p { margin: 6px 0 0; color: var(--ink-500, #6b7280); font-size: 14px; }
}

.primary-button,
.secondary-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border-radius: 10px;
  padding: 9px 16px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: transform .15s ease, box-shadow .15s ease;
  &:hover { transform: translateY(-1px); }
  &:disabled { opacity: .6; cursor: not-allowed; transform: none; }
}
.primary-button { background: var(--orange-500, #e95514); color: #fff; }
.primary-button.wide { justify-content: center; width: 100%; margin-top: 8px; }
.secondary-button { background: #fff; border-color: var(--orange-200, #f8c9ae); color: var(--orange-600, #d9460b); }
.danger-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 1px solid #efb5b1;
  border-radius: 10px;
  padding: 9px 13px;
  background: #fff;
  color: #a12620;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background .15s ease, border-color .15s ease;
  &:hover:not(:disabled) { background: #fff4f3; border-color: #d77973; }
  &:disabled { cursor: not-allowed; opacity: .48; }
}

.notice-bar {
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 14px;
  &.ok { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
  &.warn { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
  &.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
}

.guard-banner {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  background: linear-gradient(120deg, #fff7f2, #fff);
  border: 1px solid var(--orange-200, #f8c9ae);
  border-radius: 12px;
  padding: 12px 16px;
  color: var(--ink-700, #374151);
  svg { color: var(--orange-500, #e95514); flex-shrink: 0; margin-top: 2px; }
  b { display: block; margin-bottom: 2px; }
  span { font-size: 13px; line-height: 1.6; }
  em { font-style: normal; font-weight: 700; color: var(--orange-600, #d9460b); }
}

.loading-state {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 48px 0;
  color: var(--ink-500, #6b7280);
  &.small { padding: 18px 0; font-size: 14px; }
}
.spin { animation: kb-spin 1s linear infinite; }
@keyframes kb-spin { to { transform: rotate(360deg); } }

.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 14px;
}

.course-card {
  background: #fff;
  border: 1.5px solid #eee5de;
  border-radius: 14px;
  padding: 14px 16px;
  cursor: pointer;
  transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease;
  &:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(233, 85, 20, .08); }
  &.active { border-color: var(--orange-500, #e95514); box-shadow: 0 0 0 3px rgba(233, 85, 20, .12); }

  header { display: flex; align-items: center; justify-content: space-between; gap: 8px; b { font-size: 16px; } }
  .course-desc {
    margin: 8px 0 10px;
    font-size: 13px;
    color: var(--ink-500, #6b7280);
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    min-height: 36px;
  }
  footer {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--ink-500, #6b7280);
    span { display: inline-flex; align-items: center; gap: 4px; }
    .has-map { color: #047857; }
  }
}

.status-pill {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 10px;
  white-space: nowrap;
  &.ok, &.indexed { background: #ecfdf5; color: #047857; }
  &.draft, &.uploaded, &.parsing { background: #fffbeb; color: #b45309; }
  &.archived { background: #f1f3f5; color: #59636f; }
  &.failed, &.rejected { background: #fef2f2; color: #b91c1c; }
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
  align-items: start;
  @media (max-width: 1024px) { grid-template-columns: 1fr; }
}

.workspace-main {
  background: #fff;
  border: 1px solid #eee5de;
  border-radius: 14px;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.workspace-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  h2 { display: flex; align-items: center; gap: 8px; font-size: 17px; margin: 0; }
  .workspace-actions { display: flex; gap: 8px; flex-wrap: wrap; }
}

.course-delete-confirmation {
  padding: 16px;
  border: 1px solid #e7bbb7;
  border-radius: 10px;
  background: #fff8f7;

  h3 { margin: 0; color: #772521; font-size: 14px; }
  > p { margin: 8px 0 0; color: #6f4a47; font-size: 12px; line-height: 1.65; }
  label { display: block; margin-top: 14px; }
  label span { display: block; margin-bottom: 7px; color: #5f403d; font-size: 11.5px; }
  label b { color: #852f2a; word-break: break-all; }
  input {
    width: 100%;
    box-sizing: border-box;
    height: 38px;
    padding: 0 10px;
    border: 1px solid #d8aaa6;
    border-radius: 7px;
    background: #fff;
    color: #31201f;
    font-size: 12px;
    &:focus { outline: none; border-color: #a83b35; box-shadow: 0 0 0 3px rgba(168, 59, 53, .14); }
  }
  .delete-course-error { color: #a12620; font-weight: 650; }
}

.delete-course-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 13px;
  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    min-height: 36px;
    padding: 0 12px;
    border: 1px solid #d6c6c4;
    border-radius: 7px;
    background: #fff;
    color: #4f3b39;
    font-size: 11.5px;
    font-weight: 650;
    &:disabled { cursor: not-allowed; opacity: .52; }
  }
  .confirm-course-delete { border-color: #a83b35; background: #a83b35; color: #fff; }
}

.upload-zone {
  border: 2px dashed var(--orange-200, #f8c9ae);
  border-radius: 12px;
  padding: 26px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
  cursor: pointer;
  color: var(--ink-600, #4b5563);
  transition: border-color .15s ease, background .15s ease;
  svg { color: var(--orange-500, #e95514); }
  b { font-size: 15px; }
  span { font-size: 12.5px; color: var(--ink-500, #6b7280); }
  &.drag, &:hover { border-color: var(--orange-500, #e95514); background: #fff9f5; }
  .deep-audit {
    margin-top: 8px;
    font-size: 12.5px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    input { accent-color: var(--orange-500, #e95514); }
  }
}

.doc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;

  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid #f3ece6; }
  th { color: var(--ink-500, #6b7280); font-weight: 600; font-size: 12.5px; }
  .doc-name { display: flex; align-items: center; gap: 7px; font-weight: 600; svg { color: var(--orange-500, #e95514); flex-shrink: 0; } }

  .audit-toggle {
    border: none; background: #fffbeb; color: #b45309;
    border-radius: 8px; padding: 3px 10px; font-size: 12px; cursor: pointer;
  }
  .audit-clean { display: inline-flex; align-items: center; gap: 4px; color: #047857; font-size: 12.5px; }

  .icon-button {
    border: none; background: transparent; cursor: pointer; padding: 6px; border-radius: 8px;
    &.danger { color: #b91c1c; &:hover { background: #fef2f2; } }
  }

  .audit-row td { background: #fffdf9; }
  .audit-row ul { margin: 4px 0; padding-left: 18px; li { margin: 3px 0; font-size: 12.5px; &.error { color: #b91c1c; } &.warning { color: #b45309; } } }
  .audit-error { color: #b91c1c; font-size: 12.5px; margin: 4px 0 0; }
}

.empty-state {
  padding: 22px;
  text-align: center;
  color: var(--ink-500, #6b7280);
  font-size: 13.5px;
  background: #faf7f4;
  border-radius: 10px;
  &.small { padding: 12px; font-size: 12.5px; }
}

.hit-panel {
  background: #fff;
  border: 1px solid #eee5de;
  border-radius: 14px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  position: sticky;
  top: 84px;

  h3 { display: flex; align-items: center; gap: 7px; margin: 0; font-size: 15.5px; }
  > p { margin: 0; font-size: 12.5px; color: var(--ink-500, #6b7280); line-height: 1.6; }
}

.hit-input {
  display: flex;
  gap: 8px;
  input {
    flex: 1;
    border: 1px solid #e5ddd6;
    border-radius: 10px;
    padding: 9px 12px;
    font-size: 13.5px;
    &:focus { outline: none; border-color: var(--orange-500, #e95514); }
  }
  button {
    border: none;
    background: var(--orange-500, #e95514);
    color: #fff;
    border-radius: 10px;
    width: 40px;
    display: grid;
    place-items: center;
    cursor: pointer;
    &:disabled { opacity: .55; cursor: not-allowed; }
  }
}

.hit-results {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow-y: auto;

  article {
    border: 1px solid #f0e8e1;
    border-radius: 10px;
    padding: 10px 12px;
    header { display: flex; align-items: center; gap: 8px; b { font-size: 13px; } }
    .hit-score {
      background: #ecfdf5; color: #047857; font-size: 11.5px; font-weight: 700;
      border-radius: 999px; padding: 1px 8px;
    }
    p { margin: 6px 0; font-size: 12.5px; color: var(--ink-600, #4b5563); line-height: 1.6; }
    footer { font-size: 11.5px; color: var(--ink-400, #9ca3af); word-break: break-all; }
  }
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(30, 20, 12, .45);
  display: grid;
  place-items: center;
  z-index: 200;
}

.modal-card {
  position: relative;
  background: #fff;
  border-radius: 16px;
  padding: 22px 24px;
  width: min(440px, calc(100vw - 40px));
  display: flex;
  flex-direction: column;
  gap: 12px;

  h3 { display: flex; align-items: center; gap: 8px; margin: 0 0 4px; }
  label {
    display: flex;
    flex-direction: column;
    gap: 5px;
    font-size: 13px;
    span { color: var(--ink-600, #4b5563); font-weight: 600; }
    input, textarea {
      border: 1px solid #e5ddd6;
      border-radius: 10px;
      padding: 9px 12px;
      font-size: 13.5px;
      font-family: inherit;
      resize: vertical;
      &:focus { outline: none; border-color: var(--orange-500, #e95514); }
    }
  }
}

.modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--ink-500, #6b7280);
  padding: 4px;
}

.fade-enter-active, .fade-leave-active { transition: opacity .18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
