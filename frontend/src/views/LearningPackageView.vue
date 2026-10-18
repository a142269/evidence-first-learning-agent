<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { continueLearningRun, getLearningRun, getLearningRunEvents, reconcileLearningRun, streamLearningRun } from "@/api/learningRuns";
import type { LearningEvent } from "@/api/learningStream";
import { useSession } from "@/composables/useSession";
import { isTeacherRole } from "@/utils/auth";

const { course, chatSessionId, resetChatSession } = useSession();
const message = ref("请解释 RAG 的检索、生成与引用，并给我三道由浅入深的练习。");
const mode = ref("learning_package");
const requireApproval = ref(false);
const busy = ref(false);
const error = ref("");
const status = ref("idle");
const runId = ref("");
const lookupId = ref("");
const result = ref<Record<string, any>>({});
const trace = ref<string[]>([]);
const reviewEdit = ref("");
const toolProgress = ref<string[]>([]);
let controller: AbortController | undefined;
const teacher = computed(() => isTeacherRole());
const courseName = computed(() => course.value === "artificial_intelligence" ? "人工智能导论" : course.value);
const labels: Record<string, string> = {
  guard: "检查请求", planner: "规划学习步骤", decide: "判断是否补充资料", tool: "查询课程资料",
  tutor: "生成讲解", practice: "生成练习", review: "检查学习内容", compose: "整理学习包",
  retrieve: "检索课程资料", generate: "生成回答", verify: "整理引用", rejected: "审核未通过", safe_decline: "请求未执行",
};
const states: Record<string, string> = {
  idle: "准备开始", running: "正在生成", awaiting_approval: "等待教师审核", reviewing: "正在审核",
  completed: "已完成", partially_completed: "部分完成（仅交付已审核内容）", rejected: "未通过",
  failed: "执行失败", disconnected: "连接已断开", interrupted: "执行已中断",
};
const errors: Record<string, string> = {
  authorization_required: "请先使用真实账号登录。", invalid_token: "登录已失效，请重新登录。",
  session_not_found: "登录已失效，请重新登录。", session_expired: "登录已过期，请重新登录。",
  auth_storage_unavailable: "登录服务暂不可用，请稍后重试。",
  course_auth_storage_unavailable: "暂时无法核验课程权限，请稍后重试。",
  course_auth_configuration_invalid: "课程权限服务配置有误，请联系管理员。",
  course_access_denied: "当前账号未获授权访问这门课程。", run_access_denied: "你没有权限查看该任务。",
  run_not_found: "没有找到这个任务，请检查任务编号。",
  run_not_awaiting_approval: "任务已被处理，请重新查看最新结果。",
  durable_review_unavailable: "审核恢复服务尚未就绪，请联系管理员。",
  learning_package_unavailable: "学习包运行组件尚未安装。",
  learning_package_no_evidence: "课程资料不足，请补充章节名称或上传相关资料。",
  learning_package_repeated_search: "重复检索仍未找到资料，请补充具体问题。",
  learning_package_invalid_output: "模型返回的内容格式不符合要求，本次未交付学习包。",
  learning_package_invalid_citation: "模型引用了无法核对的来源，本次未交付学习包。",
  learning_package_tool_denied: "模型提出了不支持的操作，本次执行已停止。",
  learning_package_quality_failed: "内容返工后仍未通过检查，请缩小学习范围后重试。",
  learning_package_budget_exceeded: "本次任务已达到执行预算，请缩小学习范围。",
  run_timeout: "任务超时，请缩小学习范围后重试。",
  run_persistence_unavailable: "任务存储暂不可用，请稍后再试。",
  stream_incomplete: "连接提前结束，请用任务编号查询已保存的结果。",
  execution_lease_lost: "本次执行已失去运行权限，请查询任务状态，由教师检查已保存的结果。",
  execution_lease_expired: "执行进程已中断，教师可检查并恢复已保存的结果。",
  run_not_reconcilable: "任务仍在执行或已处理，请先查询最新状态。",
  checkpoint_not_settled: "没有可直接恢复的完整结果，请重新发起学习任务。",
  checkpoint_identity_mismatch: "保存的结果与本次执行不匹配，请联系管理员核查。",
  checkpoint_unavailable: "暂时无法读取保存的结果，请稍后重试。",
  run_state_changed: "任务状态已改变，请重新查询。",
  legacy_run_restart_required: "这是旧版本任务，请重新发起学习任务。",
  run_not_continuable: "当前任务没有可继续的中断节点。",
  checkpoint_not_unfinished: "没有可继续的未完成节点。",
  checkpoint_requires_review: "此任务需要教师审核，请使用审核操作。",
  login_rate_limited: "登录尝试过于频繁，请稍后重试。",
};

const costLabel = computed(() => {
  const budget = result.value.budget;
  if (!budget) return "用量尚无记录";
  const cost = budget.cost;
  if (cost?.status === "actual") return `实际模型用量：${budget.actual_input_tokens || 0} 输入 / ${budget.actual_output_tokens || 0} 输出 token；按配置单价估算 ¥${cost.amount_cny}`;
  if (cost?.status === "estimated") return `模型费用估算 ¥${cost.amount_cny}`;
  return `模型费用未知；已记录 ${budget.actual_input_tokens || 0} 输入 / ${budget.actual_output_tokens || 0} 输出 token，${budget.usage_unknown_calls || 0} 次调用未返回用量`;
});

// Server-provided delivery metadata only; withheld item text is never rendered.
function deliveredPartsLabel(partial: Record<string, any> | undefined): string {
  if (!partial) return "已审核内容";
  if (partial.withheld_exercise_numbers?.length) {
    return `讲解与其余练习（原第 ${partial.withheld_exercise_numbers.join("、")} 题未交付）`;
  }
  if ((partial.withheld_parts || []).includes("practice")) return "仅讲解（练习未交付）";
  if ((partial.withheld_parts || []).length) return "仅讲解（部分内容未交付）";
  return "已审核内容";
}

function handleEvent(event: LearningEvent) {
  if (event.name === "run.started") {
    runId.value = event.data.run_id;
    lookupId.value = runId.value;
  } else if (event.name === "node.started") {
    trace.value.push(labels[event.data.node] || "执行学习任务");
  } else if (event.name === "retrieval.completed") {
    trace.value.push(`找到 ${event.data.evidence_count} 条资料依据`);
  } else if (event.name === "tool.completed") {
    toolProgress.value.push(`${event.data.tool}：${event.data.status}（${event.data.result_count ?? 0} 项）`);
  } else if (event.name === "review.required") {
    status.value = "awaiting_approval";
  } else if (event.name === "run.completed") {
    result.value = event.data;
    status.value = event.data.status;
  } else if (event.name === "run.failed") {
    status.value = "failed";
    error.value = errors[event.data.error] || "执行失败，请检查服务配置后重试。";
  }
}

async function execute(approved?: boolean) {
  if (busy.value) return;
  const resumeId = approved === undefined ? undefined : runId.value;
  controller = new AbortController();
  busy.value = true;
  error.value = "";
  result.value = {};
  trace.value = [];
  toolProgress.value = [];
  status.value = "running";
  if (!resumeId) { runId.value = ""; lookupId.value = ""; reviewEdit.value = ""; }
  try {
    await streamLearningRun(approved === undefined ? {
      message: message.value.trim(), course_id: course.value, session_id: chatSessionId.value,
      mode: mode.value, require_approval: requireApproval.value,
    } : { approved, edited_answer: approved ? reviewEdit.value.trim() : "" }, handleEvent, controller.signal, resumeId);
  } catch (exc) {
    const code = exc instanceof Error ? exc.message : "request_failed";
    status.value = "disconnected";
    error.value = controller.signal.aborted
      ? "已停止本次请求。如已取得任务编号，可查询服务器保存的状态。"
      : errors[code] || "连接失败，请查看任务状态或检查服务配置。";
  } finally { controller = undefined; busy.value = false; }
}

async function refresh() {
  if (!lookupId.value.trim() || busy.value) return;
  busy.value = true;
  error.value = "";
  result.value = {};
  reviewEdit.value = "";
  try {
    const record = await getLearningRun(lookupId.value.trim());
    runId.value = record.run_id;
    status.value = record.status;
    result.value = record.result;
    const history = await getLearningRunEvents(record.run_id).catch(() => null);
    if (history) {
      trace.value = history.events.filter(item => item.status === "node.completed")
        .map(item => labels[item.node] || item.node);
      toolProgress.value = history.events.filter(item => item.status === "tool.completed")
        .map(item => `${item.data.tool}：${item.data.status}（${item.data.result_count ?? 0} 项）`);
    }
    if (record.status === "failed") error.value = errors[record.result.error] || "该任务执行失败。";
  } catch (exc) {
    error.value = errors[exc instanceof Error ? exc.message : ""] || "无法读取任务，请检查编号与登录状态。";
  } finally { busy.value = false; }
}

async function continueRun() {
  if (!runId.value || busy.value) return;
  controller = new AbortController();
  busy.value = true;
  error.value = "";
  status.value = "running";
  try {
    await continueLearningRun(runId.value, handleEvent, controller.signal);
  } catch (exc) {
    const code = exc instanceof Error ? exc.message : "request_failed";
    status.value = "disconnected";
    error.value = errors[code] || "续跑失败，请查询任务状态。";
  } finally { controller = undefined; busy.value = false; }
}

async function repairRun() {
  if (!runId.value || busy.value || !teacher.value) return;
  busy.value = true;
  error.value = "";
  reviewEdit.value = "";
  try {
    const record = await reconcileLearningRun(runId.value);
    status.value = record.status;
    result.value = record.result;
    trace.value.push("已读取并恢复保存的任务结果");
  } catch (exc) {
    error.value = errors[exc instanceof Error ? exc.message : ""] || "恢复失败，请重新查询任务状态。";
  } finally { busy.value = false; }
}

function newSession() {
  reviewEdit.value = "";
  resetChatSession(); result.value = {}; trace.value = []; toolProgress.value = []; runId.value = ""; lookupId.value = "";
  status.value = "idle"; error.value = "";
}
onBeforeUnmount(() => controller?.abort());
</script>

<template>
  <div class="learning-package">
    <header>
      <RouterLink to="/workflow">← 返回 Agent 编排</RouterLink>
      <h1>讲解与练习</h1>
      <p>围绕你的学习目标，规划讲解、查找依据、生成练习并检查内容。继续提问会参考本会话最近三次已完成的回答。</p>
    </header>
    <div class="package-grid">
      <section class="panel">
        <h2>这次想学什么？</h2>
        <form @submit.prevent="execute()">
          <label for="learning-goal">学习目标</label>
          <textarea id="learning-goal" v-model="message" :disabled="busy" maxlength="8000" rows="5" required />
          <div class="form-row">
            <label for="learning-mode">交付内容</label>
            <select id="learning-mode" v-model="mode" :disabled="busy">
              <option value="learning_package">讲解 + 三道练习</option>
              <option value="answer">课程问答</option>
            </select>
          </div>
          <p class="muted">当前课程：{{ courseName }}</p>
          <label class="check"><input v-model="requireApproval" type="checkbox" :disabled="busy" />交付前请教师审核</label>
          <div class="actions">
            <button type="submit" :disabled="busy || !message.trim()">{{ busy ? '处理中…' : '开始学习' }}</button>
            <button type="button" class="secondary" :disabled="busy" @click="newSession">开启新会话</button>
            <button v-if="busy && controller" type="button" class="secondary" @click="controller?.abort()">停止本次生成</button>
          </div>
        </form>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </section>
      <section class="panel progress" aria-live="polite">
        <h2>{{ states[status] || status }}</h2>
        <p v-if="!trace.length" class="muted">{{ status === 'idle' ? '开始后，这里会显示实际执行进度。' : busy ? '正在等待服务返回执行进度…' : status === 'disconnected' ? '可通过任务编号查询保存的状态。' : '已读取任务状态，可查看下方保存的内容。' }}</p>
        <ol><li v-for="(item, index) in trace" :key="index">{{ item }}</li></ol>
        <div v-if="toolProgress.length"><h3>只读工具进度</h3><ol><li v-for="(item, index) in toolProgress" :key="index">{{ item }}</li></ol></div>
        <p v-if="result.budget" class="muted">{{ costLabel }}</p>
        <p v-if="status === 'awaiting_approval'">内容已保存，教师审核通过后才会向学习者交付。</p>
        <p v-if="runId" class="run-id">任务编号：{{ runId }}</p>
        <button v-if="teacher && runId && ['failed', 'interrupted', 'running', 'reviewing'].includes(status)" class="secondary" :disabled="busy" @click="repairRun">检查并恢复已保存结果</button>
        <button v-if="runId && ['failed', 'interrupted'].includes(status)" class="secondary" :disabled="busy" @click="continueRun">从中断节点继续</button>
        <label for="run-lookup">查询已保存的任务</label>
        <div class="actions"><input id="run-lookup" v-model="lookupId" placeholder="粘贴任务编号" :disabled="busy" /><button class="secondary" :disabled="busy || !lookupId.trim()" @click="refresh">查看</button></div>
      </section>
    </div>
    <section v-if="result.approval && teacher" class="panel">
      <h2>教师审核</h2>
      <p v-if="result.approval.message">学习目标：{{ result.approval.message }}</p>
      <p v-if="result.approval.partial_completion" class="partial" role="status">
        本次仅对可交付部分发起审核：{{ deliveredPartsLabel(result.approval.partial_completion) }}。审核通过不代表未交付内容已经验证。
      </p>
      <pre>{{ result.approval.draft_answer }}</pre>
      <ul><li v-for="citation in result.approval.citations" :key="citation.chunk_id">{{ citation.source }}（{{ citation.chunk_id }}）</li></ul>
      <label for="review-edit">替换答案（可选）</label>
      <textarea id="review-edit" v-model="reviewEdit" :disabled="busy || status !== 'awaiting_approval'" maxlength="12000" rows="4" placeholder="留空则交付原学习包；填写后将用此文本替换，原题目卡片和引用不再沿用。" />
      <div class="actions"><button :disabled="busy || status !== 'awaiting_approval'" @click="execute(true)">{{ reviewEdit.trim() ? '替换并交付' : '通过并交付' }}</button><button class="secondary" :disabled="busy || status !== 'awaiting_approval'" @click="execute(false)">不予通过</button></div>
    </section>
    <section v-if="result.answer" class="panel result">
      <h2>{{ ['completed', 'partially_completed'].includes(status) ? '学习内容' : '处理结果' }}</h2>
      <p v-if="result.partial_completion" class="partial" role="status">
        本次为部分交付：{{ deliveredPartsLabel(result.partial_completion) }}。未交付内容未通过内容检查，不会因为部分交付而被视为已验证。
      </p>
      <p v-if="result.memory_run_ids?.length" class="muted">已参考本会话 {{ result.memory_run_ids.length }} 次历史回答。</p>
      <template v-if="result.learning_package">
        <h3>学习安排</h3>
        <ol><li v-for="step in result.learning_package.plan.steps" :key="step.id">{{ step.goal }}</li></ol>
        <h3>讲解</h3><pre>{{ result.learning_package.lesson.explanation }}</pre>
        <div class="citations"><p>讲解依据</p><ul><li v-for="citation in result.learning_package.lesson.citations" :key="citation.chunk_id">{{ citation.source }}（{{ citation.chunk_id }}）</li></ul></div>
        <article v-for="(exercise, index) in result.learning_package.exercises" :key="index">
          <h3>练习 {{ Number(index) + 1 }}</h3><p>{{ exercise.question }}</p>
          <details><summary>查看答案与解析</summary><p>{{ exercise.answer }}</p><p>{{ exercise.explanation }}</p></details>
          <div class="citations"><p>本题依据</p><ul><li v-for="citation in exercise.citations" :key="citation.chunk_id">{{ citation.source }}（{{ citation.chunk_id }}）</li></ul></div>
        </article>
        <h3>实际使用的资料来源</h3><ul><li v-for="citation in result.citations" :key="citation.chunk_id">{{ citation.source }}（{{ citation.chunk_id }}）</li></ul>
      </template>
      <pre v-else>{{ result.answer }}</pre>
    </section>
  </div>
</template>

<style scoped>
.learning-package { max-width: 1160px; margin: 0 auto; padding: 28px; color: #243343; }
header { max-width: 780px; margin-bottom: 24px; } header p { line-height: 1.8; color: #5c6b76; }
h1 { font-size: 30px; margin: 16px 0 8px; } h2 { font-size: 20px; margin: 0 0 18px; } h3 { font-size: 17px; }
.package-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; }
.panel { background: #fff; border: 1px solid #dce4e6; border-radius: 16px; padding: 24px; margin-bottom: 20px; }
label { display: block; margin: 12px 0 8px; } textarea, input:not([type=checkbox]), select { box-sizing: border-box; border: 1px solid #aab8bf; border-radius: 8px; padding: 10px; font: inherit; min-width: 0; }
textarea { width: 100%; resize: vertical; line-height: 1.6; } .form-row { display: flex; align-items: center; gap: 16px; }
.check { display: flex; align-items: center; gap: 8px; } .actions { display: flex; gap: 12px; margin-top: 18px; flex-wrap: wrap; }
.actions input { flex: 1; } button { border: 1px solid #246a60; border-radius: 8px; padding: 10px 18px; color: white; background: #246a60; font: inherit; cursor: pointer; }
button.secondary { background: #fff; color: #246a60; } button:disabled { opacity: .5; cursor: not-allowed; }
.muted, .run-id { color: #63737e; font-size: 13px; } .run-id { overflow-wrap: anywhere; }
.citations { color: #52656d; font-size: 13px; overflow-wrap: anywhere; } .citations p { margin-bottom: 4px; }
.error { color: #a63030; line-height: 1.6; } li { margin: 8px 0; line-height: 1.6; }
.partial { background: #fff8e6; border: 1px solid #e6c56a; border-radius: 8px; padding: 10px 12px; color: #7a5a12; line-height: 1.7; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; line-height: 1.8; } article { padding: 12px 0; border-bottom: 1px solid #e4eaed; }
summary { cursor: pointer; color: #246a60; } p { line-height: 1.7; }
:is(button, a, input, select, textarea, summary):focus-visible { outline: 3px solid #69a5da; outline-offset: 3px; }
@media (max-width: 760px) { .learning-package { padding: 16px; } .package-grid { grid-template-columns: 1fr; } .panel { padding: 18px; } }
</style>
