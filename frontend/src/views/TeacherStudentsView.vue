<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Copy,
  GitCompare,
  KeyRound,
  Loader2,
  MessageSquare,
  RefreshCcw,
  Search,
  Send,
  Sparkles,
  Target,
  Trash2,
  UserRound,
} from "lucide-vue-next";

import {
  consultTeachingCopilot,
  deleteStudentData,
  getStudentSummary,
  listStudents,
  restoreStudentAccount,
  type StudentSummary,
  type TeacherStudentBrief,
} from "@/api/teacher";
import MarkdownBlock from "@/components/shared/MarkdownBlock.vue";
import { AGENT_AVATARS } from "@/constants/agentAvatars";
import { useTeacherCourse } from "@/composables/useTeacherCourse";

const { course, courseOptions, loadCourseOptions, setCourse, courseLabelOf } = useTeacherCourse();
const route = useRoute();
const router = useRouter();
const students = ref<TeacherStudentBrief[]>([]);
const selectedId = ref("");
const summary = ref<StudentSummary | null>(null);
const loading = ref(true);
const search = ref("");
const riskFilter = ref("all");
const adviceLoading = ref(false);
const advice = ref("");
const deleteOpen = ref(false);
const deleteConfirmText = ref("");
const deleteLoading = ref(false);
const deleteError = ref("");
const operationNotice = ref("");
const copiedAccount = ref("");
const restoreOpen = ref(false);
const restorePassword = ref("");
const restoreLoading = ref(false);
const restoreError = ref("");

const agents = [
  AGENT_AVATARS.planner,
  AGENT_AVATARS.tutor,
  AGENT_AVATARS.evaluation,
  AGENT_AVATARS.safety,
  AGENT_AVATARS.content,
  AGENT_AVATARS.quiz,
];

const selectedBrief = computed(() => students.value.find((item) => item.user_id === selectedId.value));
const canDeleteSelected = computed(() => selectedBrief.value?.deletable === true);
const canRecoverSelected = computed(() => selectedBrief.value?.deletable === true);
const deleteConfirmed = computed(
  () => deleteConfirmText.value.trim() === selectedId.value && canDeleteSelected.value,
);

function humanStudentName(value: string) {
  const match = String(value || "").match(/^demo-student-(\d+)$/i);
  return match ? `学生 ${match[1]}` : value;
}
const filteredStudents = computed(() => students.value.filter((item) => {
  const keyword = search.value.trim().toLowerCase();
  const matchesSearch = !keyword || item.display_name.toLowerCase().includes(keyword) || item.user_id.toLowerCase().includes(keyword);
  const mastery = item.mastery_avg == null ? null : item.mastery_avg * 100;
  const matchesRisk = riskFilter.value === "all"
    || (riskFilter.value === "high" && (mastery == null || mastery < 45 || item.mistakes_open >= 25))
    || (riskFilter.value === "watch" && mastery != null && mastery >= 45 && mastery < 65)
    || (riskFilter.value === "stable" && mastery != null && mastery >= 65);
  return matchesSearch && matchesRisk;
}));

const profile = computed(() => summary.value?.profile || {});
const displayName = computed(() => String(profile.value.nickname || selectedBrief.value?.display_name || "当前学生"));
const mastery = computed(() => Math.round((summary.value?.mastery.average || selectedBrief.value?.mastery_avg || 0) * 100));
const riskLevel = computed(() => {
  if ((summary.value?.risks || []).some((item) => item.level === "high")) return { label: "需要优先关注", tone: "high" };
  if ((summary.value?.risks || []).some((item) => item.level === "medium")) return { label: "建议持续观察", tone: "medium" };
  return { label: "学习状态稳定", tone: "stable" };
});

const learningNarrative = computed(() => {
  const base = typeof profile.value.knowledge_base === "object" ? profile.value.knowledge_base : {};
  const preference = typeof profile.value.learning_preference === "object" ? profile.value.learning_preference : {};
  const levelMap: Record<string, string> = { high: "较扎实", excellent: "扎实", intermediate: "处于发展阶段", low: "需要补强" };
  const level = levelMap[String(base.level || profile.value.tier || "").toLowerCase()] || "正在持续形成";
  const style = String(profile.value.learning_style || "").includes("视觉") ? "偏好图解" : "偏好结构化讲解";
  const mode = String(preference.mode || "").includes("项目") ? "与项目实践" : "与即时练习";
  return `知识基础${level}，${style}${mode}；近期应优先巩固薄弱知识点，并观察错题是否持续回落。`;
});

const profileFacts = computed(() => [
  { label: "学习方式", value: String(profile.value.learning_style || "视觉与结构化学习").replace(/[-_]/g, " · ") },
  { label: "知识基础", value: mastery.value >= 75 ? "整体较扎实" : mastery.value >= 55 ? "基础正在形成" : "需要系统补强" },
  { label: "当前节奏", value: (selectedBrief.value?.last_active || 0) > 0 ? "近期保持学习" : "近期活跃证据不足" },
]);

const evidenceRows = computed(() => {
  const weak = summary.value?.mastery.weakest || [];
  const strong = summary.value?.mastery.strongest || [];
  return [
    ...strong.slice(0, 3).map((item) => ({ ...item, group: "优势" })),
    ...weak.slice(0, 5).map((item) => ({ ...item, group: "需巩固" })),
  ].sort((a, b) => b.mastery - a.mastery);
});

const mistakeType: Record<string, string> = {
  misconception: "概念混淆",
  knowledge_gap: "知识缺漏",
  concept_boundary: "概念边界",
  careless: "审题疏漏",
  calculation: "计算失误",
  reading: "阅读理解",
  unknown: "待教师归因",
};

const resourceType: Record<string, string> = {
  quiz: "练习",
  document: "讲义",
  ppt: "课件",
  pptx: "课件",
  tutoring: "即时答疑",
  evaluation_report: "学习评估",
  video: "课程视频",
  mindmap: "思维导图",
};

async function loadStudentsData() {
  loading.value = true;
  try {
    const response = await listStudents();
    students.value = response.students;
    const requested = typeof route.query.student === "string" ? route.query.student : "";
    selectedId.value = requested && response.students.some((item) => item.user_id === requested)
      ? requested
      : response.students[0]?.user_id || "";
  } finally {
    loading.value = false;
  }
}

async function loadSummary() {
  if (!selectedId.value) return;
  loading.value = true;
  advice.value = "";
  try {
    summary.value = await getStudentSummary(selectedId.value, course.value);
  } finally {
    loading.value = false;
  }
}

async function generateAdvice() {
  if (!selectedId.value || adviceLoading.value) return;
  adviceLoading.value = true;
  try {
    const result = await consultTeachingCopilot({
      action: "student_intervention",
      scope: "student",
      user_id: selectedId.value,
      course: course.value,
      instruction: "基于该学生的掌握证据、错题模式和资源行为，生成一份教师可审核的三步干预建议。",
    });
    advice.value = result.content || result.error || "本次没有生成可审核建议。";
  } catch (reason: any) {
    advice.value = `建议生成失败：${reason?.detail || reason?.message || reason}`;
  } finally {
    adviceLoading.value = false;
  }
}

function openDeletePanel() {
  deleteOpen.value = true;
  deleteConfirmText.value = "";
  deleteError.value = "";
}

function closeDeletePanel() {
  if (deleteLoading.value) return;
  deleteOpen.value = false;
  deleteConfirmText.value = "";
  deleteError.value = "";
}

function openRestorePanel() {
  restoreOpen.value = true;
  restorePassword.value = "";
  restoreError.value = "";
}

function closeRestorePanel() {
  if (restoreLoading.value) return;
  restoreOpen.value = false;
  restorePassword.value = "";
  restoreError.value = "";
}

async function confirmRestoreAccount() {
  if (!canRecoverSelected.value || restoreLoading.value) return;
  if (restorePassword.value.trim().length < 6) {
    restoreError.value = "新密码至少需要 6 位。";
    return;
  }
  restoreLoading.value = true;
  restoreError.value = "";
  try {
    await restoreStudentAccount(selectedId.value, restorePassword.value);
    operationNotice.value = `已恢复 ${displayName.value} 的登录账号；学生可使用账号 ${selectedId.value} 和新密码登录。`;
    restoreOpen.value = false;
    restorePassword.value = "";
  } catch (reason: any) {
    const detail = reason?.detail || reason?.message || String(reason);
    restoreError.value = detail === "student_data_not_found"
      ? "未找到该学生的已有学习数据，不能恢复账号。"
      : `恢复失败：${detail}`;
  } finally {
    restoreLoading.value = false;
  }
}

async function copyStudentAccount() {
  if (!selectedId.value) return;
  try {
    await navigator.clipboard.writeText(selectedId.value);
    copiedAccount.value = selectedId.value;
    operationNotice.value = `已复制学生账号：${selectedId.value}`;
    window.setTimeout(() => {
      if (copiedAccount.value === selectedId.value) copiedAccount.value = "";
    }, 2000);
  } catch {
    operationNotice.value = `无法自动复制，请手动记录学生账号：${selectedId.value}`;
  }
}

async function confirmDeleteStudent() {
  if (!deleteConfirmed.value || deleteLoading.value) return;
  const userId = selectedId.value;
  const studentName = displayName.value;
  deleteLoading.value = true;
  deleteError.value = "";
  try {
    const result = await deleteStudentData(userId);
    deleteOpen.value = false;
    deleteConfirmText.value = "";
    summary.value = null;
    selectedId.value = "";
    operationNotice.value = `已删除 ${studentName} 的测试账号与 ${result.deleted_total} 条关联学习记录。`;
    await loadStudentsData();
  } catch (reason: any) {
    const detail = reason?.detail || reason?.message || String(reason);
    deleteError.value = detail === "protected_demo_account"
      ? "杜同学、林同学等内置演示账号受保护，不能删除。"
      : `删除失败：${detail}`;
  } finally {
    deleteLoading.value = false;
  }
}

function onCourseChange(event: Event) {
  setCourse((event.target as HTMLSelectElement).value);
}

watch(selectedId, () => {
  copiedAccount.value = "";
  closeDeletePanel();
  closeRestorePanel();
  loadSummary();
});
// 课程切换（来自共享课程选择器）后重新按新课程加载学生证据
watch(course, loadSummary);
onMounted(() => {
  loadCourseOptions();
  loadStudentsData();
});
</script>

<template>
  <div class="teacher-students-v4">
    <header class="page-heading">
      <div><h1>从学习状态，下钻到可执行的个体干预</h1><span>把画像、掌握、错题和资源行为整理成教师可读的学习叙事。</span></div>
      <div><button type="button" class="secondary-button" @click="router.push('/teacher/students?compare=1')"><GitCompare :size="17" />对比学生</button><button type="button" class="primary-button" @click="generateAdvice"><Sparkles :size="17" />生成干预建议</button></div>
    </header>

    <section class="context-bar" aria-label="当前教学工作上下文">
      <div>
        <small>课程</small>
        <select class="course-select" :value="course" aria-label="切换教学课程" @change="onCourseChange">
          <option v-for="c in courseOptions" :key="c" :value="c">{{ courseLabelOf(c) }}</option>
        </select>
      </div>
      <div><small>工作模式</small><b>教师决策端</b></div>
      <div><small>Agent 协作</small><b>{{ agents.length }} 个角色已接入</b></div>
      <div><small>数据范围</small><b>{{ students.length ? `${students.length} 名学生` : "当前课程" }}</b></div>
    </section>

    <section class="filter-bar" aria-label="学生筛选">
      <label class="search-field"><Search :size="17" /><input v-model="search" placeholder="搜索学生" /></label>
      <select v-model="riskFilter"><option value="all">全部状态</option><option value="high">优先关注</option><option value="watch">持续观察</option><option value="stable">状态稳定</option></select>
      <select v-model="selectedId" aria-label="选择学生账号"><option v-for="student in filteredStudents" :key="student.user_id" :value="student.user_id">{{ humanStudentName(student.display_name || student.user_id) }} · 账号 {{ student.user_id }} · 掌握度 {{ student.mastery_avg == null ? '待采集' : Math.round(student.mastery_avg * 100) + '%' }}</option></select>
      <button type="button" title="刷新学生数据" @click="loadStudentsData"><RefreshCcw :size="17" /></button>
      <span>共 {{ filteredStudents.length }} 名学生</span>
    </section>
    <p v-if="operationNotice" class="operation-notice" role="status">
      <CheckCircle2 :size="16" />{{ operationNotice }}
    </p>

    <div v-if="loading" class="loading-state"><Loader2 :size="28" class="spin" /><b>正在整理学生学习证据</b></div>

    <template v-else-if="summary">
      <section class="student-story-grid">
        <aside class="student-identity">
          <div class="student-avatar"><UserRound :size="30" /></div>
          <span :class="['risk-pill', riskLevel.tone]">{{ riskLevel.label }}</span>
          <h2>{{ displayName }}</h2>
          <p>{{ learningNarrative }}</p>
          <div class="mastery-number"><b>{{ mastery }}%</b><span>综合掌握度</span></div>
          <dl><div v-for="fact in profileFacts" :key="fact.label"><dt>{{ fact.label }}</dt><dd>{{ fact.value }}</dd></div></dl>
          <div class="student-account">
            <span>学生账号</span>
            <code>{{ selectedId }}</code>
            <button type="button" :title="`复制账号 ${selectedId}`" @click="copyStudentAccount">
              <CheckCircle2 v-if="copiedAccount === selectedId" :size="14" />
              <Copy v-else :size="14" />
              {{ copiedAccount === selectedId ? "已复制" : "复制" }}
            </button>
          </div>
          <div class="identity-actions"><button type="button" @click="router.push({ path: '/teacher/interventions', query: { tab: 'chat', student: selectedId } })"><MessageSquare :size="16" />联系学生</button><button type="button" @click="router.push({ path: '/teacher/resources', query: { student: selectedId } })"><BookOpen :size="16" />指派资源</button></div>
          <button v-if="canRecoverSelected" type="button" class="restore-account-trigger" @click="openRestorePanel">
            <KeyRound :size="15" />恢复 / 重置学生登录密码
          </button>
          <section v-if="restoreOpen" class="restore-account-panel" aria-labelledby="restore-account-title">
            <h3 id="restore-account-title">恢复 {{ displayName }} 的登录账号</h3>
            <p>系统将为账号 <b>{{ selectedId }}</b> 保存新密码。已有画像、学习路径、错题和资源不会被修改；该学生的旧登录会话将失效。</p>
            <label>
              <span>设置新密码（至少 6 位）</span>
              <input v-model="restorePassword" type="password" autocomplete="new-password" @keyup.enter="confirmRestoreAccount" />
            </label>
            <p v-if="restoreError" class="restore-error" role="alert">{{ restoreError }}</p>
            <div class="restore-actions">
              <button type="button" :disabled="restoreLoading" @click="closeRestorePanel">取消</button>
              <button type="button" class="confirm-restore" :disabled="restoreLoading" @click="confirmRestoreAccount">
                <Loader2 v-if="restoreLoading" :size="15" class="spin" />
                <KeyRound v-else :size="15" />
                {{ restoreLoading ? "正在保存" : "恢复登录" }}
              </button>
            </div>
          </section>
          <button
            type="button"
            class="delete-student-trigger"
            :disabled="!canDeleteSelected"
            :title="canDeleteSelected ? '删除该测试学生及其学习数据' : '内置演示账号受保护'"
            @click="openDeletePanel"
          >
            <Trash2 :size="15" />
            {{ canDeleteSelected ? "删除测试学生数据" : "内置演示账号已保护" }}
          </button>
          <section v-if="deleteOpen" class="delete-confirmation" aria-labelledby="delete-student-title">
            <h3 id="delete-student-title">永久删除 {{ displayName }}？</h3>
            <p>将同时删除账号、画像、学习路径、掌握度、测评、错题、个人资源和对话记录。公共课程与其他学生数据不会受影响。</p>
            <dl>
              <div><dt>学习路径</dt><dd>{{ summary.paths.length }} 条</dd></div>
              <div><dt>未解决错题</dt><dd>{{ summary.mistakes.open_count }} 条</dd></div>
              <div><dt>个人资源</dt><dd>{{ summary.resources.total }} 项</dd></div>
            </dl>
            <label>
              <span>输入账号 <b>{{ selectedId }}</b> 确认</span>
              <input
                v-model="deleteConfirmText"
                :placeholder="selectedId"
                autocomplete="off"
                spellcheck="false"
                @keyup.enter="confirmDeleteStudent"
              />
            </label>
            <p v-if="deleteError" class="delete-error" role="alert">{{ deleteError }}</p>
            <div class="delete-actions">
              <button type="button" :disabled="deleteLoading" @click="closeDeletePanel">取消</button>
              <button
                type="button"
                class="confirm-delete"
                :disabled="!deleteConfirmed || deleteLoading"
                @click="confirmDeleteStudent"
              >
                <Loader2 v-if="deleteLoading" :size="15" class="spin" />
                <Trash2 v-else :size="15" />
                {{ deleteLoading ? "正在删除" : "永久删除" }}
              </button>
            </div>
          </section>
        </aside>

        <article class="evidence-panel">
          <header><div><h2>掌握证据</h2><p>优势与薄弱知识点放在同一尺度中比较</p></div><span>共 {{ evidenceRows.length }} 项证据</span></header>
          <div class="evidence-list">
            <div v-for="item in evidenceRows" :key="`${item.group}-${item.kp_id}`">
              <span :class="item.group === '优势' ? 'strong' : 'weak'">{{ item.group }}</span>
              <div><b>{{ item.kp_name }}</b><i><em :class="item.group === '优势' ? 'strong' : 'weak'" :style="{ width: `${Math.round(item.mastery * 100)}%` }"></em></i></div>
              <strong>{{ Math.round(item.mastery * 100) }}%</strong>
            </div>
          </div>
          <section class="change-note"><span><Target :size="17" /></span><div><b>近期教学判断</b><p>{{ mastery >= 70 ? '整体表现稳定，但仍需防止薄弱知识点形成持续性错误。' : '基础掌握出现波动，建议降低单次任务负荷并增加即时反馈。' }}</p></div></section>
          <section class="risk-evidence"><h3>风险证据</h3><p v-if="!summary.risks.length"><CheckCircle2 :size="16" />当前没有高优先级风险。</p><p v-for="(risk, index) in summary.risks" :key="index"><AlertTriangle :size="16" />{{ risk.message }}</p></section>
        </article>

        <aside class="advice-panel">
          <header><span><Sparkles :size="18" /></span><div><h2>AI 教学建议</h2><p>教师审核后执行</p></div><i>在线</i></header>
          <div class="agent-stack"><img v-for="agent in agents" :key="agent.kind" :src="agent.png || ''" :alt="agent.nick" :title="`${agent.nick} · ${agent.role}`" /></div>
          <div v-if="advice" class="advice-content"><MarkdownBlock :content="advice" /></div>
          <div v-else class="advice-default"><b>建议采用三步干预</b><ol><li>先用 8 分钟辨析薄弱概念</li><li>完成 3 道即时反馈练习</li><li>48 小时后复测并对比变化</li></ol></div>
          <button type="button" class="advice-button" :disabled="adviceLoading" @click="generateAdvice"><Loader2 v-if="adviceLoading" :size="16" class="spin" /><Sparkles v-else :size="16" />{{ adviceLoading ? '多 Agent 协作中' : '基于最新证据重新生成' }}</button>
          <div class="quick-actions"><small>执行建议</small><button type="button" @click="router.push({ path: '/teacher/interventions', query: { tab: 'paths', student: selectedId } })">创建补强路径<ChevronRight :size="14" /></button><button type="button" @click="router.push({ path: '/teacher/interventions', query: { tab: 'chat', student: selectedId } })">发送教师提醒<ChevronRight :size="14" /></button></div>
        </aside>
      </section>

      <section class="detail-sections">
        <article class="mistake-section">
          <header><div><h2>错题模式</h2><p>{{ summary.mistakes.open_count }} 道未解决错题，优先阅读重复出现的错误</p></div><button type="button" @click="router.push({ path: '/teacher/interventions', query: { student: selectedId } })">发起干预<ArrowRight :size="15" /></button></header>
          <div v-if="!summary.mistakes.recent.length" class="empty-line">暂无未解决错题</div>
          <div v-else class="mistake-list"><div v-for="mistake in summary.mistakes.recent.slice(0, 7)" :key="mistake.id"><span>{{ mistakeType[mistake.error_type] || '待教师归因' }}</span><p>{{ mistake.question || '题目内容暂未记录' }}</p><button type="button" aria-label="查看错题"><ChevronRight :size="16" /></button></div></div>
        </article>

        <article class="path-section">
          <header><h2>学习路径</h2><span>{{ summary.paths.length }} 条</span></header>
          <div v-if="!summary.paths.length" class="empty-line">还没有教师推荐的学习路径</div>
          <div v-else class="path-list"><div v-for="path in summary.paths.slice(0, 6)" :key="path.id"><i :style="{ '--progress': `${Math.round(path.progress)}%` }"><b>{{ Math.round(path.progress) }}%</b></i><span><b>{{ path.title }}</b><small>{{ path.stages_count }} 个阶段 · {{ path.recommended_by ? '教师或 Agent 推荐' : '学生自主创建' }}</small></span></div></div>
        </article>

        <article class="resource-section">
          <header><h2>资源使用</h2><span>{{ summary.resources.total }} 项</span></header>
          <div v-if="!summary.resources.recent.length" class="empty-line">暂无资源使用记录</div>
          <div v-else class="resource-list"><div v-for="resource in summary.resources.recent.slice(0, 7)" :key="resource.id"><span>{{ resourceType[String(resource.type).toLowerCase()] || '学习资源' }}</span><div><b>{{ resource.title.replace(/^生成的\s*/i, '').replace(/\s*资源$/i, '') || '学习记录' }}</b><small>{{ resource.created_at ? new Date(resource.created_at * 1000).toLocaleDateString('zh-CN') : '时间未记录' }}</small></div></div></div>
        </article>
      </section>
    </template>
  </div>
</template>

<style scoped lang="scss">
.teacher-students-v4 { --ink:#121b2b; --muted:#647187; --line:#eadbd3; --soft:#fff4ed; --orange:#e95514; --orange-dark:#b63a0c; --indigo:#665df5; width:min(1450px,calc(100% - 32px)); margin:0 auto; padding:24px 28px 72px; border:0; border-radius:18px; background:transparent; box-shadow:none; color:var(--ink); font-family:Inter,"PingFang SC","Microsoft YaHei",system-ui,sans-serif; }
button,input,select{font:inherit} button{cursor:pointer}.page-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;padding:18px 4px 26px}.page-heading>div:first-child p{margin:0 0 8px;color:var(--orange-dark);font-size:13px;font-weight:750}.page-heading h1{max-width:780px;margin:0;font-size:34px;line-height:1.2;letter-spacing:-.035em}.page-heading>div:first-child span{display:block;margin-top:10px;color:var(--muted);font-size:14px}.page-heading>div:last-child{display:flex;gap:10px}.primary-button,.secondary-button{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 17px;border-radius:9px;font-size:13px;font-weight:700;transition:transform 180ms cubic-bezier(.16,1,.3,1),box-shadow 180ms}.primary-button{border:1px solid var(--orange);background:var(--orange);color:#fff}.secondary-button{border:1px solid #d3dae4;background:#fff;color:#344155}.primary-button:hover,.secondary-button:hover{transform:translateY(-2px);box-shadow:0 4px 8px rgba(18,27,43,.12)}
.filter-bar{position:sticky;top:0;z-index:20;display:grid;grid-template-columns:minmax(210px,.8fr) 160px minmax(330px,1.4fr) 44px auto;align-items:center;gap:10px;padding:11px;border:1px solid rgba(211,219,228,.9);border-radius:11px;background:rgba(255,255,255,.91);box-shadow:0 4px 8px rgba(18,27,43,.05);backdrop-filter:blur(14px)}.search-field{display:flex;align-items:center;gap:8px;height:44px;padding:0 12px;border:1px solid #d7dee7;border-radius:8px;color:#78859a}.search-field input{width:100%;border:0;outline:0}.filter-bar select{height:44px;padding:0 12px;border:1px solid #d7dee7;border-radius:8px;background:#fff;color:#344155}.filter-bar>button{display:grid;place-items:center;width:44px;height:44px;border:1px solid #d7dee7;border-radius:8px;background:#fff;color:#506078}.filter-bar>span{justify-self:end;padding-right:8px;color:var(--muted);font-size:12px}
.student-story-grid{display:grid;grid-template-columns:minmax(280px,4fr) minmax(420px,5fr) minmax(280px,3fr);gap:22px;margin-top:24px}.student-identity,.evidence-panel,.advice-panel{min-width:0;border:1px solid var(--line);border-radius:11px;background:#fff}.student-identity{padding:28px}.student-avatar{display:grid;place-items:center;width:58px;height:58px;border-radius:16px;background:#fff0e8;color:var(--orange-dark)}.risk-pill{display:inline-block;margin-top:20px;padding:5px 9px;border-radius:999px;font-size:11px;font-weight:750}.risk-pill.high{background:#fff0f0;color:#b52f2f}.risk-pill.medium{background:#fff6e5;color:#976000}.risk-pill.stable{background:#eaf8f1;color:#13724c}.student-identity h2{margin:14px 0 0;font-size:26px;letter-spacing:-.03em}.student-identity>p{margin:11px 0 0;color:var(--muted);font-size:13px;line-height:1.75}.mastery-number{display:flex;align-items:baseline;gap:10px;margin:25px 0;padding:20px 0;border-block:1px solid var(--line)}.mastery-number b{font-size:40px;letter-spacing:-.04em}.mastery-number span{color:var(--muted);font-size:12px}.student-identity dl{margin:0}.student-identity dl div{display:grid;grid-template-columns:82px 1fr;gap:12px;padding:11px 0;border-top:1px solid var(--line)}.student-identity dl div:first-child{border-top:0}.student-identity dt{color:var(--muted);font-size:11.5px}.student-identity dd{margin:0;font-size:12.5px;font-weight:650}.identity-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:22px}.identity-actions button{display:flex;align-items:center;justify-content:center;gap:6px;min-height:42px;border:1px solid #d7dee7;border-radius:8px;background:#fff;color:#39475b;font-size:12px;font-weight:700;transition:background 180ms,transform 180ms}.identity-actions button:hover{background:#fff4ed;transform:translateY(-2px)}
.evidence-panel{padding:27px}.evidence-panel>header{display:flex;justify-content:space-between;gap:18px}.evidence-panel h2,.advice-panel h2{margin:0;font-size:18px}.evidence-panel header p{margin:6px 0 0;color:var(--muted);font-size:12px}.evidence-panel header>span{color:var(--muted);font-size:11.5px}.evidence-list{margin-top:22px}.evidence-list>div{display:grid;grid-template-columns:48px minmax(0,1fr) 42px;align-items:center;gap:12px;min-height:55px;border-top:1px solid var(--line)}.evidence-list>div:first-child{border-top:0}.evidence-list>div>span{font-size:10.5px;font-weight:750}.evidence-list>div>span.strong{color:#16734f}.evidence-list>div>span.weak{color:#b84a16}.evidence-list>div div b{display:block;overflow:hidden;font-size:12.5px;text-overflow:ellipsis;white-space:nowrap}.evidence-list i{display:block;height:5px;margin-top:8px;overflow:hidden;border-radius:99px;background:#edf0f4}.evidence-list i em{display:block;height:100%;border-radius:inherit}.evidence-list i em.strong{background:#28a36f}.evidence-list i em.weak{background:#ed6a24}.evidence-list strong{font-size:12px;text-align:right}.change-note{display:flex;gap:12px;margin-top:23px;padding:16px;border-radius:9px;background:#f2f5ff}.change-note>span{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:#fff;color:#5149d7}.change-note b{font-size:12.5px}.change-note p{margin:5px 0 0;color:#55637a;font-size:11.5px;line-height:1.65}.risk-evidence{margin-top:22px}.risk-evidence h3{margin:0 0 10px;font-size:13px}.risk-evidence p{display:flex;align-items:flex-start;gap:7px;margin:7px 0;color:#5a687c;font-size:11.5px;line-height:1.55}
.advice-panel{overflow:hidden;border-color:#d9d7ff}.advice-panel>header{display:flex;align-items:center;gap:10px;padding:20px;border-bottom:1px solid #deddfa;background:#f7f7ff}.advice-panel header>span{display:grid;place-items:center;width:38px;height:38px;border-radius:10px;background:var(--indigo);color:#fff}.advice-panel header p{margin:4px 0 0;color:var(--muted);font-size:10.5px}.advice-panel header i{margin-left:auto;color:#19835a;font-size:10.5px;font-style:normal;font-weight:750}.agent-stack{display:flex;padding:18px 20px 6px}.agent-stack img{width:38px;height:38px;margin-left:-7px;border:3px solid #fff;border-radius:50%;object-fit:cover;transition:transform 180ms}.agent-stack img:first-child{margin-left:0}.agent-stack img:hover{z-index:2;transform:translateY(-4px) scale(1.1)}.advice-default,.advice-content{margin:15px 20px;padding:17px;border:1px solid #deddfa;border-radius:9px;background:#fff}.advice-default b{font-size:13px}.advice-default ol{margin:12px 0 0;padding-left:20px;color:#536078;font-size:11.5px;line-height:1.9}.advice-content{max-height:260px;overflow:auto;font-size:12px;line-height:1.65}.advice-button{display:flex;align-items:center;justify-content:center;gap:7px;width:calc(100% - 40px);min-height:43px;margin:0 20px;border:0;border-radius:9px;background:var(--indigo);color:#fff;font-size:12px;font-weight:750}.quick-actions{display:grid;gap:7px;margin-top:17px;padding:16px 20px 20px;border-top:1px solid #deddfa;background:#f7f7ff}.quick-actions small{color:var(--muted);font-size:10.5px}.quick-actions button{display:flex;align-items:center;justify-content:space-between;min-height:37px;padding:0 10px;border:1px solid #d8d5ff;border-radius:8px;background:#fff;color:#4c46b5;font-size:11.5px;text-align:left}
.detail-sections{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(260px,.75fr) minmax(280px,.9fr);gap:34px;margin-top:48px;padding-top:34px;border-top:1px solid var(--line)}.detail-sections article{min-width:0}.detail-sections article>header{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:16px}.detail-sections h2{margin:0;font-size:19px;letter-spacing:-.02em}.detail-sections header p{margin:6px 0 0;color:var(--muted);font-size:11.5px}.detail-sections header>span{color:var(--muted);font-size:11.5px}.detail-sections header button{display:flex;align-items:center;gap:5px;border:0;background:transparent;color:var(--orange-dark);font-size:11.5px;font-weight:750}.mistake-list>div{display:grid;grid-template-columns:80px minmax(0,1fr) 28px;align-items:center;gap:11px;min-height:58px;border-top:1px solid var(--line)}.mistake-list>div>span{width:max-content;padding:4px 7px;border-radius:6px;background:#f4f1ec;color:#6b6258;font-size:10.5px}.mistake-list p{overflow:hidden;margin:0;color:#334057;font-size:11.5px;text-overflow:ellipsis;white-space:nowrap}.mistake-list button{display:grid;place-items:center;width:28px;height:28px;border:0;border-radius:7px;background:transparent;color:#778398}.mistake-list>div:hover{background:#fafbfc}.path-list,.resource-list{border-top:1px solid var(--line)}.path-list>div{display:grid;grid-template-columns:48px 1fr;gap:12px;align-items:center;min-height:66px;border-bottom:1px solid var(--line)}.path-list i{display:grid;place-items:center;width:42px;height:42px;border-radius:50%;background:conic-gradient(var(--orange) var(--progress),#edf0f4 0);font-style:normal}.path-list i::before{content:"";grid-area:1/1;width:32px;height:32px;border-radius:50%;background:#fff}.path-list i b{z-index:1;grid-area:1/1;font-size:9px}.path-list span b,.path-list span small,.resource-list div div b,.resource-list div div small{display:block}.path-list span b,.resource-list div div b{font-size:11.5px}.path-list span small,.resource-list div div small{margin-top:4px;color:var(--muted);font-size:10px}.resource-list>div{display:grid;grid-template-columns:70px 1fr;gap:10px;align-items:center;min-height:58px;border-bottom:1px solid var(--line)}.resource-list>div>span{width:max-content;padding:4px 7px;border-radius:6px;background:#fff1e8;color:var(--orange-dark);font-size:10px}.empty-line{padding:30px 0;color:var(--muted);font-size:12px}.loading-state{display:grid;place-items:center;align-content:center;gap:12px;min-height:480px;color:var(--muted)}.loading-state b{font-size:14px}.spin{animation:spin .8s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}
@media(max-width:1180px){.student-story-grid{grid-template-columns:minmax(280px,.85fr) minmax(430px,1.15fr)}.advice-panel{grid-column:1/-1}.detail-sections{grid-template-columns:1fr 1fr}.mistake-section{grid-column:1/-1}.filter-bar{grid-template-columns:1fr 150px minmax(280px,1fr) 44px}.filter-bar>span{display:none}}@media(max-width:760px){.teacher-students-v4{width:calc(100% - 24px)}.page-heading{align-items:flex-start;flex-direction:column}.page-heading h1{font-size:28px}.filter-bar{position:static;grid-template-columns:1fr 1fr}.search-field,.filter-bar select:nth-of-type(2){grid-column:1/-1}.student-story-grid,.detail-sections{grid-template-columns:1fr}.mistake-section{grid-column:auto}.identity-actions{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}}
.filter-bar{border-radius:14px;box-shadow:0 8px 22px rgba(18,27,43,.07)}
.student-identity,.evidence-panel,.advice-panel{border-radius:16px;background:#fffefd}
@media(max-width:760px){.teacher-students-v4{padding:18px 16px 48px;border-radius:14px}}

/* ============================================================
 * v4 全站视觉收敛（2026-07-12）· 基准 = 教学概览
 * 浅暖白 tokens / 衬线页标题 / 中性边框 / AI 低饱和紫 / 统一宽度
 * ============================================================ */
.teacher-students-v4 {
  --ink: #1f1d1a;
  --muted: #625f58;
  --line: #e5e1d9;
  --soft: #f8f7f3;
  --orange: #e85d16;
  --orange-dark: #d75011;
  --indigo: #6757d9;
  width: 100%;
  padding: 0 0 48px;
}
.teacher-students-v4 .page-heading { padding: 0 0 24px; }
.teacher-students-v4 .page-heading > div:first-child p {
  color: #89857d;
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.teacher-students-v4 .page-heading h1 {
  color: #171512;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 38px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.01em;
}
.teacher-students-v4 .page-heading > div:first-child span { font-size: 15px; line-height: 1.6; }
.teacher-students-v4 .primary-button,
.teacher-students-v4 .secondary-button {
  min-height: 42px;
  border-radius: 9px;
  font-size: 13.5px;
  font-weight: 600;
}
.teacher-students-v4 .secondary-button { border-color: #dad6ce; color: #393631; }
.teacher-students-v4 .primary-button:hover {
  background: var(--orange-dark);
  border-color: var(--orange-dark);
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.09);
}
.teacher-students-v4 .secondary-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 24px rgba(35, 31, 25, 0.05);
}
.teacher-students-v4 .filter-bar {
  position: static;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  box-shadow: none;
  backdrop-filter: none;
}
.teacher-students-v4 .search-field,
.teacher-students-v4 .filter-bar select,
.teacher-students-v4 .filter-bar > button { border-color: #dad6ce; color: #393631; }
.teacher-students-v4 .student-identity,
.teacher-students-v4 .evidence-panel,
.teacher-students-v4 .advice-panel { border-radius: 12px; background: #fff; }
.teacher-students-v4 .identity-actions button { border-color: #dad6ce; color: #393631; }
.teacher-students-v4 .identity-actions button:hover { background: #f8f6f2; transform: translateY(-1px); }
.teacher-students-v4 .change-note { background: #faf9ff; }
.teacher-students-v4 .change-note > span { color: var(--indigo); }
.teacher-students-v4 .advice-panel { border-color: #e5e1f4; }
.teacher-students-v4 .advice-panel > header { border-bottom-color: #e5e1f4; background: #faf9ff; }
.teacher-students-v4 .advice-panel header > span { background: #efecfb; color: var(--indigo); }
.teacher-students-v4 .advice-default,
.teacher-students-v4 .advice-content { border-color: #e5e1f4; }
.teacher-students-v4 .advice-button { background: var(--indigo); }
.teacher-students-v4 .quick-actions { border-top-color: #e5e1f4; background: #faf9ff; }
.teacher-students-v4 .quick-actions button { border-color: #e5e1f4; color: #5647c8; }
.teacher-students-v4 .mistake-list > div:hover { background: #f8f6f2; }
.teacher-students-v4 .context-bar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 24px;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.teacher-students-v4 .context-bar > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  padding: 14px 20px;
  border-left: 1px solid var(--line);
}
.teacher-students-v4 .context-bar > div:first-child { border-left: 0; padding-left: 0; }
.teacher-students-v4 .context-bar small { color: #625f58; font-size: 13px; }
.teacher-students-v4 .context-bar b {
  overflow: hidden;
  color: #1f1d1a;
  font-size: 13.5px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.teacher-students-v4 .course-select {
  width: fit-content;
  padding: 2px 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #1f1d1a;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition: color 160ms ease-out;
}
.teacher-students-v4 .course-select:hover { color: var(--orange); }
.teacher-students-v4 .course-select:focus-visible {
  outline: 3px solid rgba(232, 93, 22, 0.28);
  outline-offset: 1px;
}
@media (max-width: 1050px) {
  .teacher-students-v4 .context-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .teacher-students-v4 .context-bar > div:nth-child(3) { border-left: 0; padding-left: 0; }
  .teacher-students-v4 .context-bar > div:nth-child(n + 3) { border-top: 1px solid var(--line); }
}
.teacher-students-v4 .resource-list > div > span { background: #fff3ea; color: #b04510; }
.teacher-students-v4 .detail-sections header button { color: var(--muted); }
.teacher-students-v4 .detail-sections header button:hover { color: var(--orange); }
.operation-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 0;
  color: #146c4b;
  font-size: 13px;
  font-weight: 600;
}
.student-account {
  display: grid;
  grid-template-columns: 66px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 10px 0;
  border-block: 1px solid var(--line);
}
.student-account > span {
  color: var(--muted);
  font-size: 11.5px;
}
.student-account code {
  overflow: hidden;
  color: #393631;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 11.5px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.student-account button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 30px;
  padding: 0 8px;
  border: 1px solid #dad6ce;
  border-radius: 6px;
  background: #fff;
  color: #514d47;
  font-size: 11px;
  font-weight: 650;
}
.student-account button:hover { background: #f8f6f2; }
.restore-account-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  min-height: 39px;
  margin-top: 10px;
  border: 1px solid #dad6ce;
  border-radius: 8px;
  background: #fff;
  color: #514d47;
  font-size: 12px;
  font-weight: 650;
}
.restore-account-trigger:hover { background: #f8f6f2; }
.restore-account-panel {
  margin-top: 10px;
  padding: 16px;
  border: 1px solid #d9d0f3;
  border-radius: 10px;
  background: #fbfaff;
}
.restore-account-panel h3 {
  margin: 0;
  color: #3f3578;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
}
.restore-account-panel > p {
  margin: 8px 0 0;
  color: #5c5575;
  font-size: 11.5px;
  line-height: 1.65;
}
.restore-account-panel label,
.restore-account-panel label span { display: block; }
.restore-account-panel label { margin-top: 14px; }
.restore-account-panel label span { margin-bottom: 7px; color: #514a6b; font-size: 11px; }
.restore-account-panel input {
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border: 1px solid #c9c1e6;
  border-radius: 7px;
  background: #fff;
  color: #312d41;
  font-size: 12px;
  outline: 0;
}
.restore-account-panel input:focus { border-color: #6757d9; box-shadow: 0 0 0 3px rgba(103, 87, 217, 0.14); }
.restore-account-panel .restore-error { color: #a12620; font-weight: 650; }
.restore-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 13px; }
.restore-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid #d6cfe9;
  border-radius: 7px;
  background: #fff;
  color: #4f4867;
  font-size: 11.5px;
  font-weight: 650;
}
.restore-actions .confirm-restore { border-color: #6757d9; background: #6757d9; color: #fff; }
.restore-actions button:disabled { cursor: not-allowed; opacity: 0.52; }
.delete-student-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  min-height: 39px;
  margin-top: 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #a83b35;
  font-size: 12px;
  font-weight: 650;
  transition: background 180ms ease-out, color 180ms ease-out;
}
.delete-student-trigger:hover:not(:disabled) {
  background: #fff1ef;
  color: #8d2924;
}
.delete-student-trigger:disabled {
  cursor: not-allowed;
  color: #8a8781;
}
.delete-confirmation {
  margin-top: 10px;
  padding: 16px;
  border: 1px solid #e7bbb7;
  border-radius: 10px;
  background: #fff8f7;
}
.delete-confirmation h3 {
  margin: 0;
  color: #772521;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0;
}
.delete-confirmation > p {
  margin: 8px 0 0;
  color: #6f4a47;
  font-size: 11.5px;
  line-height: 1.65;
}
.delete-confirmation dl {
  display: flex;
  gap: 16px;
  margin: 14px 0;
  padding: 10px 0;
  border-block: 1px solid #efd4d1;
}
.delete-confirmation dl div {
  display: block;
  padding: 0;
  border: 0;
}
.delete-confirmation dt {
  color: #80615e;
  font-size: 10.5px;
}
.delete-confirmation dd {
  margin: 3px 0 0;
  color: #512c29;
  font-size: 12px;
  font-weight: 700;
}
.delete-confirmation label,
.delete-confirmation label span {
  display: block;
}
.delete-confirmation label span {
  margin-bottom: 7px;
  color: #5f403d;
  font-size: 11px;
}
.delete-confirmation label b {
  color: #852f2a;
  word-break: break-all;
}
.delete-confirmation input {
  width: 100%;
  height: 38px;
  padding: 0 10px;
  border: 1px solid #d8aaa6;
  border-radius: 7px;
  background: #fff;
  color: #31201f;
  font-size: 12px;
  outline: 0;
}
.delete-confirmation input:focus {
  border-color: #a83b35;
  box-shadow: 0 0 0 3px rgba(168, 59, 53, 0.14);
}
.delete-confirmation .delete-error {
  color: #a12620;
  font-weight: 650;
}
.delete-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 13px;
}
.delete-actions button {
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
}
.delete-actions .confirm-delete {
  border-color: #a83b35;
  background: #a83b35;
  color: #fff;
}
.delete-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.52;
}
</style>
