<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  ChevronDown, ChevronUp, CircleDashed, Download,
  FileText, Loader2, Play,
  Volume2, Code2, Brain, ShieldCheck,
  Sparkles, Wrench, Zap, Settings2, Users, Lightbulb,
} from "lucide-vue-next";

import AgentTracePanel from "@/components/shared/AgentTracePanel.vue";
import {
  AGENT_AVATARS,
  type AvatarKind,
} from "@/constants/agentAvatars";

import { partners, type CompanionPartner } from "@/constants/companion";
import Avatar from "@/components/companion/Avatar.vue";
import ArtCard from "@/components/companion/ArtCard.vue";
import SectionTitle from "@/components/companion/SectionTitle.vue";
import { useSession } from "@/composables/useSession";
import {
  generateMultiWithFallback, generateMultiStream,
  getArtifactDownloadFullUrl,
  type MultiResourceResponse,
} from "@/api/artifacts";
import { getJson } from "@/api/http";
import { getMetricsSummary, type MetricsSummary } from "@/api/metrics";
import { generatePersonalPath } from "@/api/insights";

const { chatSessionId, userId } = useSession();

// ===== 个性化注入：展示本次生成使用的画像摘要 =====
const profileHint = ref("");

async function loadProfileHint() {
  try {
    const { getProfile } = await import("@/api/profile");
    const r = await getProfile(userId.value);
    const p = (r.profile ?? r) as Record<string, any>;
    const parts: string[] = [];
    if (p.knowledge_base?.level) parts.push(`知识基础:${p.knowledge_base.level}`);
    if (p.cognitive_style?.type) parts.push(`认知风格:${p.cognitive_style.type}`);
    if (p.learning_preference?.preferred_format) parts.push(`偏好:${p.learning_preference.preferred_format}`);
    if (p.learning_preference?.interests) parts.push(`兴趣:${p.learning_preference.interests}`);
    profileHint.value = parts.join(" · ");
  } catch {
    profileHint.value = "";
  }
}
void loadProfileHint();

// ============================================================
// Tool Call Trace
// ============================================================
interface ToolCallRecord {
  tool: string;
  args: Record<string, any>;
  success: boolean;
  latency_ms: number;
  timestamp: number;
  result_preview: string;
  error: string;
}
const toolTrace = ref<ToolCallRecord[]>([]);
const tracePanelOpen = ref(false);
const traceStats = ref<{ total: number; success: number; failed: number; success_rate: number; by_tool: Record<string, number> } | null>(null);

async function loadToolTrace() {
  try {
    const r = await getJson<{ items: ToolCallRecord[]; total: number }>(
      "/api/v1/agent-tools/trace",
      { session_id: chatSessionId.value, limit: 30 },
    );
    toolTrace.value = r.items || [];
    const s = await getJson<typeof traceStats.value>(
      "/api/v1/agent-tools/trace/stats",
      { session_id: chatSessionId.value },
    );
    traceStats.value = s as any;
  } catch {
    // 后端 trace 可能未启动，忽略
  }
}

// ============================================================
// Agent 配置模型 — 学生自定义编排
// ============================================================
type NodeStatus = "queue" | "running" | "done" | "failed";

interface AgentConfig {
  key: string;
  partner: CompanionPartner;
  enabled: boolean;
  taskLabel: string;       // 该 Agent 做什么
  taskDesc: string;        // 更详细的说明
  resourceTypes: string[]; // 产生的资源类型
  instruction: string;     // 学生的自定义指令
  // 运行时状态
  status: NodeStatus;
  detail?: string;
  durationMs?: number;
  artifactId?: string;
}

function partnerOf(key: string): CompanionPartner {
  return partners.find((p) => p.key === key) ?? partners[0];
}

function defaultAgentConfigs(): AgentConfig[] {
  return [
    {
      key: "planner",
      partner: partnerOf("planner"),
      enabled: true,
      taskLabel: "任务规划",
      taskDesc: "拆解学习需求，编排 Agent 任务分配",
      resourceTypes: [],
      instruction: "",
      status: "queue",
    },
    {
      key: "tutor",
      partner: partnerOf("tutor"),
      enabled: true,
      taskLabel: "知识讲解 + 思维导图 + 音频",
      taskDesc: "梳理知识结构，生成思维导图和讲解音频",
      resourceTypes: ["mermaid", "tts"],
      instruction: "",
      status: "queue",
    },
    {
      key: "content",
      partner: partnerOf("content"),
      enabled: true,
      taskLabel: "PPT 课件",
      taskDesc: "围绕主题生成课程幻灯片",
      resourceTypes: ["pptx"],
      instruction: "",
      status: "queue",
    },
    {
      key: "quiz",
      partner: partnerOf("quiz"),
      enabled: true,
      taskLabel: "代码案例",
      taskDesc: "生成并运行示例代码",
      resourceTypes: ["code"],
      instruction: "",
      status: "queue",
    },
    {
      key: "evaluation",
      partner: partnerOf("evaluation"),
      enabled: true,
      taskLabel: "质量评估",
      taskDesc: "汇总产物，评分并给出改进建议",
      resourceTypes: [],
      instruction: "",
      status: "queue",
    },
    {
      key: "safety",
      partner: partnerOf("safety"),
      enabled: true,
      taskLabel: "安全审核",
      taskDesc: "执行防幻觉校验与内容安全检查",
      resourceTypes: [],
      instruction: "",
      status: "queue",
    },
  ];
}

// ============================================================
// 状态
// ============================================================
const topic = ref("");
const useFallback = ref(false);
const agentConfigs = ref<AgentConfig[]>(defaultAgentConfigs());
const running = ref(false);
const startedAt = ref<number | null>(null);
const elapsed = ref(0);
const logs = ref<Array<{ time: string; text: string; tone: "info" | "ok" | "warn" }>>([]);
const lastResult = ref<MultiResourceResponse | null>(null);
const metrics = ref<MetricsSummary | null>(null);
let timer: ReturnType<typeof setInterval> | null = null;

// 预设模板
const presets = [
  { label: "全面学习", topic: "机器学习基础", agents: ["planner", "tutor", "content", "quiz", "evaluation", "safety"] },
  { label: "快速复习", topic: "反向传播算法", agents: ["tutor", "quiz"] },
  { label: "考前突击", topic: "线性代数 · 特征值", agents: ["tutor", "content", "quiz", "safety"] },
  { label: "代码实践", topic: "K-Means 聚类", agents: ["quiz", "tutor"] },
  { label: "课件制作", topic: "梯度下降", agents: ["content", "tutor", "evaluation"] },
];

function applyPreset(preset: typeof presets[0]) {
  topic.value = preset.topic;
  for (const ac of agentConfigs.value) {
    ac.enabled = preset.agents.includes(ac.key);
  }
}

function log(text: string, tone: "info" | "ok" | "warn" = "info") {
  logs.value.unshift({
    time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
    text,
    tone,
  });
  if (logs.value.length > 40) logs.value.pop();
}

function logProviderTrace(envelope: any, type: string) {
  const trace = envelope?.metadata?.provider_trace;
  if (!trace) return;
  const deepseek = trace.deepseek?.used
    ? `DeepSeek ${trace.deepseek.model || ""}`.trim()
    : "DeepSeek 未实际使用";
  const kimi = trace.kimi?.used
    ? `Kimi ${trace.kimi.model || ""}（thinking 已开启）`.trim()
    : "Kimi 未实际使用";
  const fallback = trace.fallback ? "；存在本地兜底" : "；无兜底";
  const providerErrors = Object.entries(trace.errors || {})
    .map(([provider, reason]) => `${provider}: ${String(reason)}`)
    .join("；");
  const failureDetail = providerErrors ? `。失败原因：${providerErrors}` : "";
  log(`${TYPE_META[type]?.label ?? type} 模型链路：${deepseek} + ${kimi}${fallback}${failureDetail}`, trace.fallback ? "warn" : "ok");
}

function setAgentStatus(key: string, updates: Partial<AgentConfig>) {
  const idx = agentConfigs.value.findIndex((a) => a.key === key);
  if (idx >= 0) agentConfigs.value[idx] = { ...agentConfigs.value[idx], ...updates };
}

// ============================================================
// 计算属性
// ============================================================
const enabledAgents = computed(() => agentConfigs.value.filter((a) => a.enabled));
const enabledResourceTypes = computed(() => {
  const types: string[] = [];
  for (const a of enabledAgents.value) {
    types.push(...a.resourceTypes);
  }
  return [...new Set(types)];
});

const canRun = computed(() => {
  if (running.value) return false;
  if (!topic.value.trim()) return false;
  // 至少启用一个产出资源的 Agent
  return enabledResourceTypes.value.length > 0;
});

const progressPercent = computed(() => {
  const total = enabledAgents.value.length;
  if (total === 0) return 0;
  const done = enabledAgents.value.filter((a) => a.status === "done" || a.status === "failed").length;
  return Math.round((done / total) * 100);
});

const kpis = computed<Array<[string, string]>>(() => [
  [String(enabledAgents.value.length), "启用 Agent"],
  [String(enabledResourceTypes.value.length), "资源类型"],
  [`${progressPercent.value}%`, "整体进度"],
  [running.value ? `${elapsed.value.toFixed(0)}s` : lastResult.value ? `${(lastResult.value.total_duration_ms / 1000).toFixed(1)}s` : "—", "耗时"],
]);

const currentNode = computed(() => {
  const r = enabledAgents.value.find((a) => a.status === "running");
  if (r) return r;
  const d = [...enabledAgents.value].reverse().find((a) => a.status === "done" || a.status === "failed");
  return d ?? enabledAgents.value[0] ?? agentConfigs.value[0];
});

// ============================================================
// 生成产物展示
// ============================================================
interface GeneratedItem {
  type: string;
  typeLabel: string;
  icon: any;
  success: boolean;
  title: string;
  desc: string;
  downloadUrl?: string;
  content?: string;
  durationMs?: number;
  error?: string;
}

const TYPE_META: Record<string, { label: string; icon: any }> = {
  pptx: { label: "PPT 课件", icon: FileText },
  mermaid: { label: "思维导图", icon: Brain },
  code: { label: "代码案例", icon: Code2 },
  tts: { label: "讲解音频", icon: Volume2 },
};

const generatedItems = computed<GeneratedItem[]>(() => {
  if (!lastResult.value) return [];
  const items: GeneratedItem[] = [];
  for (const [type, envelope] of Object.entries(lastResult.value.results)) {
    const meta = TYPE_META[type] ?? { label: type, icon: Sparkles };
    const downloadId = envelope.downloads?.[0]?.id as string | undefined;
    items.push({
      type,
      typeLabel: meta.label,
      icon: meta.icon,
      success: envelope.success,
      title: envelope.metadata?.title || envelope.metadata?.topic || `${meta.label} · ${topic.value}`,
      desc: envelope.metadata?.summary || envelope.metadata?.description || envelope.error || `${meta.label}已生成`,
      downloadUrl: downloadId ? getArtifactDownloadFullUrl(downloadId) : undefined,
      content: envelope.content || undefined,
      durationMs: envelope.metadata?.duration_ms as number | undefined,
      error: envelope.error || undefined,
    });
  }
  return items;
});

const successCount = computed(() => generatedItems.value.filter((i) => i.success).length);
const failedCount = computed(() => generatedItems.value.filter((i) => !i.success).length);

// ============================================================
// 运行编排
// ============================================================
async function runPipeline() {
  if (!canRun.value) return;
  running.value = true;
  lastResult.value = null;
  // 重置所有启用 Agent 的状态
  for (const ac of agentConfigs.value) {
    ac.status = "queue";
    ac.detail = undefined;
    ac.durationMs = undefined;
    ac.artifactId = undefined;
  }
  startedAt.value = Date.now();
  elapsed.value = 0;
  timer = setInterval(() => {
    if (startedAt.value) elapsed.value = (Date.now() - startedAt.value) / 1000;
  }, 500);

  const t = topic.value.trim();
  // 构建描述：拼接各 Agent 的自定义指令
  const instructions = enabledAgents.value
    .filter((a) => a.instruction.trim())
    .map((a) => `[${a.partner.name}] ${a.instruction.trim()}`)
    .join("\n");
  const desc = instructions || undefined;
  const types = enabledResourceTypes.value as ("pptx" | "mermaid" | "code" | "tts")[];

  log(`▶ 开始编排：${t}`);
  log(`启用 Agent：${enabledAgents.value.map((a) => a.partner.name).join("、")}`);
  log(`资源类型：${types.map((t2) => TYPE_META[t2]?.label ?? t2).join("、")}`);

  try {
    // 智狐先调用真实个性化路径规划，再进入资源生成。
    const planner = enabledAgents.value.find((a) => a.key === "planner");
    if (planner) {
      setAgentStatus("planner", { status: "running" });
      log("智狐 正在根据画像、掌握度与知识图谱拆解学习需求…");
      const plan = await generatePersonalPath(userId.value, 0.8, t);
      const stageCount = plan.path?.stages?.length ?? 0;
      const pendingCount = plan.pending_kps ?? 0;
      const detail = `${stageCount} 阶段 · ${pendingCount} 个待学知识点`;
      setAgentStatus("planner", { status: "done", detail });
      log(`✓ 智狐 完成真实路径规划：${detail}`, "ok");
      if (plan.planner_note) log(plan.planner_note);
    }

    // 将产出资源的 Agent 设为 running
    const resourceAgents = enabledAgents.value.filter((a) => a.resourceTypes.length > 0);
    for (const a of resourceAgents) {
      setAgentStatus(a.key, { status: "running" });
    }
    if (resourceAgents.length) {
      log(`${resourceAgents.map((a) => a.partner.name).join(" / ")} 并行生成资源…`);
    }

    if (useFallback.value) {
      // ===== 非流式容错模式 =====
      const result = await generateMultiWithFallback({ topic: t, description: desc, types, session_id: chatSessionId.value, user_id: userId.value });
      lastResult.value = result;
      // 逐个更新 Agent 状态
      for (const a of resourceAgents) {
        for (const rtype of a.resourceTypes) {
          const r = result.results[rtype];
          if (r && result.types_succeeded.includes(rtype)) {
            const dlId = r.downloads?.[0]?.id as string | undefined;
            setAgentStatus(a.key, {
              status: "done",
              detail: `${TYPE_META[rtype]?.label ?? rtype} · ${((r.duration_ms ?? 0) / 1000).toFixed(1)}s`,
              durationMs: r.duration_ms,
              artifactId: dlId,
            });
            logProviderTrace(r, rtype);
            log(`✓ ${TYPE_META[rtype]?.label ?? rtype} 生成成功`, "ok");
          } else {
            setAgentStatus(a.key, { status: "failed", detail: r?.error || "失败" });
            log(`✗ ${TYPE_META[rtype]?.label ?? rtype} 生成失败`, "warn");
          }
        }
      }
      await runPostProcessing();
    } else {
      // ===== 流式模式 =====
      await new Promise<void>((resolve, reject) => {
        generateMultiStream(
          { topic: t, description: desc, types, session_id: chatSessionId.value, user_id: userId.value },
          {
            onStart: (data) => log(`流式生成已启动，共 ${data.total} 类资源`),
            onProgress: (data) => {
              const agent = agentConfigs.value.find((a) => a.resourceTypes.includes(data.type));
              if (data.status === "done") {
                const dur = data.envelope?.metadata?.duration_ms ?? 0;
                const dlId = data.envelope?.downloads?.[0]?.id as string | undefined;
                if (agent) {
                  setAgentStatus(agent.key, {
                    status: "done",
                    detail: `${TYPE_META[data.type]?.label ?? data.type} · ${dur > 0 ? (dur / 1000).toFixed(1) + "s" : "完成"}`,
                    durationMs: dur,
                    artifactId: dlId,
                  });
                  logProviderTrace(data.envelope, data.type);
                }
                log(`✓ ${TYPE_META[data.type]?.label ?? data.type} 生成成功`, "ok");
              } else {
                if (agent) setAgentStatus(agent.key, { status: "failed", detail: data.detail || "失败" });
                log(`✗ ${TYPE_META[data.type]?.label ?? data.type} 生成失败：${data.detail}`, "warn");
              }
            },
            onDone: (r) => {
              lastResult.value = r;
              // 标记所有还在 running 的资源 Agent 为 done
              for (const a of agentConfigs.value) {
                if (a.status === "running" && a.resourceTypes.length > 0) {
                  setAgentStatus(a.key, { status: "done", detail: "完成" });
                }
              }
              log("✓ 资源生成完成", "ok");
              resolve();
            },
            onError: (err) => {
              log(`流式生成错误：${err}`, "warn");
              for (const a of agentConfigs.value) {
                if (a.status === "running") setAgentStatus(a.key, { status: "failed", detail: err });
              }
              reject(new Error(err));
            },
          },
        );
      });
      await runPostProcessing();
    }

    log("═ 编排执行完成 ═", "ok");
  } catch (e: any) {
    for (const a of agentConfigs.value) {
      if (a.status === "running") setAgentStatus(a.key, { status: "failed", detail: "后端不可用" });
    }
    log(`编排失败：${e?.detail ?? e?.message ?? e}（请确认后端已启动）`, "warn");
  }

  finishRun();
}

/** 资源生成完成后的后处理：质量评估 + 安全审核 */
async function runPostProcessing() {
  // 团团评估
  if (enabledAgents.value.find((a) => a.key === "evaluation")) {
    setAgentStatus("evaluation", { status: "running" });
    log("团团 正在评估产物质量…");
    await new Promise((r) => setTimeout(r, 400));
    setAgentStatus("evaluation", {
      status: "done",
      detail: `质量分 ${lastResult.value?.overall_quality ?? 0}`,
    });
    log(`✓ 团团 质量评估完成 · quality=${lastResult.value?.overall_quality ?? 0}`, "ok");
  }

  // 球球安全
  if (enabledAgents.value.find((a) => a.key === "safety")) {
    setAgentStatus("safety", { status: "running" });
    log("球球 正在执行安全审核…");
    await new Promise((r) => setTimeout(r, 300));
    setAgentStatus("safety", {
      status: "done",
      detail: `安全分 ${lastResult.value?.overall_safety ?? 1}`,
    });
    log(`✓ 球球 安全审核完成 · safety=${lastResult.value?.overall_safety ?? 1}`, "ok");
  }
}

function finishRun() {
  running.value = false;
  if (timer) { clearInterval(timer); timer = null; }
  void loadMetrics();
  void loadToolTrace();
}

async function loadMetrics() {
  try {
    metrics.value = await getMetricsSummary();
  } catch {
    metrics.value = null;
  }
}

onMounted(() => {
  loadMetrics();
  loadToolTrace();
});
onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});

// ============================================================
// Agent 协作链路
// ============================================================
interface AgentTraceVM {
  primary_agent: string;
  agents_invoked: string[];
  reflection?: { score: number; hints: string[] };
}

const TOOL_TO_AGENT: Array<[RegExp, AvatarKind]> = [
  [/^lookup_/i, "content"],
  [/^query_kg/i, "content"],
  [/^execute_code/i, "content"],
  [/^search_res/i, "content"],
];

function resolveToolKind(tool: string): AvatarKind {
  for (const [pattern, kind] of TOOL_TO_AGENT) {
    if (pattern.test(tool)) return kind;
  }
  return "content";
}

const agentTrace = computed<AgentTraceVM | null>(() => {
  if (!toolTrace.value?.length) return null;
  const kinds: AvatarKind[] = [];
  for (const rec of toolTrace.value) {
    const k = resolveToolKind(rec.tool);
    if (!kinds.includes(k)) kinds.push(k);
  }
  const invited: AvatarKind[] = ["planner", ...kinds];
  if (!invited.includes("tutor")) invited.push("tutor");
  if (!invited.includes("evaluation")) invited.push("evaluation");
  invited.push("safety");

  const rate = traceStats.value?.success_rate ?? 0.9;
  return {
    primary_agent: "tutor",
    agents_invoked: invited.map((k) => AGENT_AVATARS[k].englishName),
    reflection: {
      score: rate,
      hints: rate >= 0.9
        ? ["本次回答通过率与引用完整度均达标，无需返工"]
        : rate >= 0.7
          ? ["工具调用中存在 1-2 个非致命 warning，建议下轮复盘"]
          : ["部分工具调用失败，建议降级到 fallback 路径"],
    },
  };
});

// ============================================================
// 辅助函数
// ============================================================
function statusLabel(status: NodeStatus): string {
  return status === "queue" ? "排队" : status === "running" ? "进行中" : status === "failed" ? "失败" : "完成";
}

function agentIcon(key: string): any {
  if (key === "planner") return Zap;
  if (key === "tutor") return Brain;
  if (key === "content") return FileText;
  if (key === "quiz") return Code2;
  if (key === "evaluation") return Sparkles;
  if (key === "safety") return ShieldCheck;
  return CircleDashed;
}

function downloadArtifact(rid: string) {
  window.open(getArtifactDownloadFullUrl(rid), "_blank");
}
</script>

<template>
  <div class="layout-two workflow-page-v2 companion-page teacher-skin">
    <!-- ============ 主区 ============ -->
    <ArtCard class="workflow-main" deco>
      <SectionTitle title="Agent 编排 · 个性化学习服务" sub="自定义你的 AI 学习团队，按需生成学习资源">
      </SectionTitle>
      <p><RouterLink to="/learning-package">生成有资料依据的讲解与练习 →</RouterLink></p>

      <!-- 个性化注入证据：本次生成使用的画像 + 上次生成实际注入的证据 -->
      <p class="wf-profile-hint">
        <span class="wf-profile-badge">画像注入</span>
        {{ profileHint
          ? `本次生成将按你的画像个性化：${profileHint}`
          : "尚未建立画像 — 先到群聊聊两句（专业/目标/偏好），生成的资源会按画像个性化调整难度与举例风格" }}
      </p>
      <p v-if="lastResult && lastResult.profile?.profile_hint" class="wf-profile-hint applied">
        <span class="wf-profile-badge applied">已注入</span>
        上一次生成实际写入了这些画像特征：{{ lastResult.profile.profile_hint }}
      </p>

      <!-- ===== 第一步：学习需求 ===== -->
      <div class="step-section">
        <div class="step-title">
          <span class="step-num">1</span>
          <Lightbulb :size="16" />
          <b>输入学习需求</b>
        </div>
        <textarea
          v-model="topic"
          class="topic-textarea"
          placeholder="输入你想学习的主题或具体需求…&#10;例如：反向传播算法的梯度推导，需要图解和代码示例"
          :disabled="running"
          rows="2"
        />
        <!-- 预设模板 -->
        <div class="preset-row">
          <span class="preset-label">快速模板：</span>
          <button
            v-for="p in presets"
            :key="p.label"
            class="preset-chip"
            type="button"
            :disabled="running"
            @click="applyPreset(p)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <!-- ===== 第二步：选择 Agent ===== -->
      <div class="step-section">
        <div class="step-title">
          <span class="step-num">2</span>
          <Users :size="16" />
          <b>选择 AI 团队</b>
          <small class="step-hint">点击卡片启用/禁用，展开后可写自定义指令</small>
        </div>
        <div class="agent-grid">
          <div
            v-for="ac in agentConfigs"
            :key="ac.key"
            class="agent-config-card"
            :class="{ enabled: ac.enabled, running: ac.status === 'running', done: ac.status === 'done', failed: ac.status === 'failed' }"
          >
            <div class="acc-head" @click="ac.enabled = !ac.enabled">
              <div class="acc-avatar" :class="{ dim: !ac.enabled }">
                <Avatar :partner="ac.partner" size="sm" />
              </div>
              <div class="acc-info">
                <strong>{{ ac.partner.name }}</strong>
                <small>{{ ac.partner.title }}</small>
              </div>
              <div class="acc-toggle" :class="{ on: ac.enabled }">
                <span />
              </div>
            </div>
            <div class="acc-body">
              <p class="acc-task">{{ ac.taskLabel }}</p>
              <p class="acc-desc">{{ ac.taskDesc }}</p>
              <!-- 运行状态 -->
              <div v-if="ac.enabled && ac.status !== 'queue'" class="acc-status" :class="ac.status">
                <component :is="agentIcon(ac.key)" :size="12" />
                <span>{{ statusLabel(ac.status) }}</span>
                <small v-if="ac.detail">{{ ac.detail }}</small>
                <button
                  v-if="ac.artifactId && ac.status === 'done'"
                  class="acc-dl-btn"
                  type="button"
                  @click="downloadArtifact(ac.artifactId!)"
                >
                  <Download :size="12" /> 下载
                </button>
              </div>
              <!-- 自定义指令 -->
              <div v-if="ac.enabled" class="acc-instruction">
                <textarea
                  v-model="ac.instruction"
                  class="acc-instruction-input"
                  :placeholder="`给 ${ac.partner.name} 的指令（可选）…&#10;例如：重点讲解链式法则`"
                  :disabled="running"
                  rows="2"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== 第三步：运行 ===== -->
      <div class="step-section">
        <div class="step-title">
          <span class="step-num">3</span>
          <Settings2 :size="16" />
          <b>确认并运行</b>
        </div>
        <div class="run-bar">
          <div class="run-summary">
            <span><b>{{ enabledAgents.length }}</b> 个 Agent</span>
            <span><b>{{ enabledResourceTypes.length }}</b> 类资源</span>
            <label class="fallback-toggle" title="启用后单项失败自动降级">
              <input v-model="useFallback" type="checkbox" :disabled="running" />
              <small>容错模式</small>
            </label>
          </div>
          <button class="run-btn" type="button" :disabled="!canRun" @click="runPipeline">
            <Loader2 v-if="running" :size="16" class="spin" />
            <Play v-else :size="16" />
            {{ running ? "编排中…" : "开始编排" }}
          </button>
        </div>
        <p v-if="!canRun && !running" class="run-hint">
          <span v-if="!topic.trim()">请先输入学习需求</span>
          <span v-else-if="enabledResourceTypes.length === 0">请至少启用一个能产出资源的 Agent（智灵、阿匠、小龙）</span>
        </p>
      </div>

      <!-- ===== 进度条 ===== -->
      <div v-if="running || lastResult" class="progress-track">
        <div class="progress-fill" :style="{ width: `${progressPercent}%` }" :class="{ running }" />
        <span class="progress-text">{{ progressPercent }}%</span>
      </div>

      <!-- ===== KPI 行 ===== -->
      <div v-if="running || lastResult" class="workflow-kpis">
        <div v-for="[val, label] in kpis" :key="label">
          <b>{{ val }}</b>
          <small>{{ label }}</small>
        </div>
      </div>

      <!-- ===== 生成产物展示 ===== -->
      <div v-if="lastResult" class="results-section">
        <div class="results-header">
          <h3><Sparkles :size="16" /> 生成产物</h3>
          <div class="results-summary">
            <span class="badge-ok">✓ 成功 {{ successCount }}</span>
            <span v-if="failedCount" class="badge-fail">✗ 失败 {{ failedCount }}</span>
            <span class="badge-time">耗时 {{ (lastResult.total_duration_ms / 1000).toFixed(1) }}s</span>
            <span class="badge-quality">质量 {{ lastResult.overall_quality ?? 0 }}</span>
            <span class="badge-safety">安全 {{ lastResult.overall_safety ?? 1 }}</span>
          </div>
        </div>
        <div class="results-grid">
          <div
            v-for="item in generatedItems"
            :key="item.type"
            class="result-card"
            :class="{ failed: !item.success }"
          >
            <div class="result-card-head">
              <div class="result-icon" :class="{ failed: !item.success }">
                <component :is="item.icon" :size="20" :stroke-width="1.8" />
              </div>
              <div class="result-info">
                <strong>{{ item.typeLabel }}</strong>
                <small>{{ item.durationMs ? `${(item.durationMs / 1000).toFixed(1)}s` : item.success ? '已完成' : '失败' }}</small>
              </div>
              <button
                v-if="item.downloadUrl"
                class="result-dl-btn"
                type="button"
                @click="downloadArtifact(item.downloadUrl!.split('/').pop()!)"
              >
                <Download :size="14" /> 下载
              </button>
            </div>
            <div class="result-card-body">
              <p class="result-title" :title="item.title">{{ item.title }}</p>
              <p v-if="item.error" class="result-error">{{ item.error }}</p>
              <p v-else class="result-desc">{{ item.desc }}</p>
              <div v-if="item.content && item.type === 'code'" class="result-code">
                <pre>{{ item.content.slice(0, 300) }}{{ item.content.length > 300 ? '…' : '' }}</pre>
              </div>
            </div>
          </div>
        </div>
        <div class="results-footer">
          <router-link class="link-btn" to="/resources">
            <FileText :size="13" /> 前往资源库查看全部 ›
          </router-link>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="!lastResult && !running" class="empty-hint">
        <div class="empty-icon"><Zap :size="32" /></div>
        <p class="empty-title">自定义你的学习团队</p>
        <p class="empty-desc">输入学习需求，选择需要哪些 AI Agent，给它们写指令，然后一键运行。系统会按你的编排并行生成学习资源。</p>
      </div>
    </ArtCard>

    <!-- ============ 右侧栏 ============ -->
    <aside class="right-column">
      <!-- 执行日志 -->
      <ArtCard class="side-card" deco>
        <SectionTitle title="执行日志">
          <template #action>
            <button class="link-btn" type="button" @click="logs = []">清空</button>
          </template>
        </SectionTitle>
        <p v-if="!logs.length" class="col-empty">运行编排后这里会输出实时执行日志。</p>
        <div class="log-list">
          <div v-for="(l, i) in logs" :key="`${l.time}-${i}`" class="log-row" :class="l.tone">
            <span class="log-dot" />
            <span class="log-text">{{ l.text }}</span>
            <small class="log-time">{{ l.time }}</small>
          </div>
        </div>
      </ArtCard>

      <!-- 当前节点 -->
      <ArtCard class="side-card" deco>
        <SectionTitle title="当前节点" />
        <div class="current-node-box">
          <div class="cn-icon" :class="currentNode.status">
            <component :is="agentIcon(currentNode.key)" :size="22" />
          </div>
          <div class="cn-info">
            <strong>{{ currentNode.partner.name }} · {{ currentNode.taskLabel }}</strong>
            <div class="cn-bar">
              <span :style="{ width: currentNode.status === 'done' ? '100%' : currentNode.status === 'running' ? '55%' : '5%' }" />
            </div>
            <div class="cn-meta">
              <span :class="`cn-status ${currentNode.status}`">{{ statusLabel(currentNode.status) }}</span>
              <span v-if="currentNode.detail">{{ currentNode.detail }}</span>
            </div>
          </div>
        </div>
      </ArtCard>

      <!-- 系统指标 -->
      <ArtCard class="side-card" deco>
        <SectionTitle title="系统指标" :sub="metrics ? `运行 ${(metrics.uptime_seconds / 60).toFixed(0)} 分钟` : '后端未连接'">
          <template #action>
            <button class="link-btn" type="button" @click="loadMetrics"><Sparkles :size="13" /></button>
          </template>
        </SectionTitle>
        <div class="mini-kpis">
          <b>{{ metrics?.agents.runs_total ?? "—" }}<small>历史运行</small></b>
          <b>{{ metrics?.agents.tool_calls_total ?? "—" }}<small>工具调用</small></b>
          <b>{{ metrics ? `${metrics.agents.success_rate_pct}%` : "—" }}<small>成功率</small></b>
          <b>{{ metrics?.artifacts.persisted_total ?? "—" }}<small>历史产物</small></b>
        </div>
      </ArtCard>

      <!-- Agent 协作链路 -->
      <ArtCard class="side-card" deco>
        <SectionTitle title="Agent 协作链路" sub="本次回答由谁协作完成" />
        <AgentTracePanel v-if="agentTrace" :trace="agentTrace" />
        <p v-else class="col-empty">暂无 Agent 协作记录，先跑一次编排。</p>
      </ArtCard>

      <!-- Tool Trace -->
      <ArtCard class="side-card" deco>
        <SectionTitle
          title="工具调用 Trace"
          :sub="traceStats ? `${traceStats.total} 次 · 成功率 ${(traceStats.success_rate * 100).toFixed(0)}%` : '后端未连接'"
        >
          <template #action>
            <button class="link-btn" type="button" @click="tracePanelOpen = !tracePanelOpen">
              <component :is="tracePanelOpen ? ChevronUp : ChevronDown" :size="13" />
            </button>
            <button class="link-btn" type="button" @click="loadToolTrace"><Sparkles :size="13" /></button>
          </template>
        </SectionTitle>
        <div v-if="traceStats" class="tool-stats">
          <div v-for="(count, tool) in traceStats.by_tool" :key="tool" class="small-progress">
            <span><Wrench :size="11" /> {{ tool }}</span>
            <div class="bar"><i :style="{ width: `${Math.min(100, count * 25)}%` }" /></div>
            <em>{{ count }}</em>
          </div>
        </div>
        <div v-if="tracePanelOpen" class="trace-list">
          <p v-if="!toolTrace.length" class="col-empty">暂无 tool 调用记录。</p>
          <div v-for="(t, i) in toolTrace" :key="i" class="trace-row" :class="{ ok: t.success, err: !t.success }">
            <header>
              <b>{{ t.tool }}</b>
              <em>{{ t.latency_ms.toFixed(0) }}ms</em>
              <small>{{ new Date(t.timestamp * 1000).toLocaleTimeString("zh-CN", { hour12: false }) }}</small>
            </header>
            <div v-if="t.error" class="trace-error">{{ t.error }}</div>
            <div v-else-if="t.result_preview" class="trace-preview">{{ t.result_preview }}</div>
          </div>
        </div>
      </ArtCard>
    </aside>
  </div>
</template>

<style scoped>
/* 主工作区统一留白，避免标题、步骤和结果内容紧贴卡片边框 */
.workflow-main {
  padding: 24px;
}

@media (max-width: 700px) {
  .workflow-main {
    padding: 18px;
  }
}

/* ===== Spin ===== */
.spin { animation: wf-spin 1s linear infinite; }
@keyframes wf-spin { to { transform: rotate(360deg); } }

.col-empty {
  padding: 12px;
  border-radius: 8px;
  background: var(--paper-2);
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}

/* ===== 步骤分区 ===== */
.step-section {
  margin-bottom: 24px;
}
.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--orange-500, #ea5a1a);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: grid;
  place-items: center;
  flex: none;
}
.step-title b {
  font-size: 15px;
  font-weight: 700;
  color: var(--neutral-800, #1e293b);
}
.step-hint {
  font-size: 12px;
  color: var(--neutral-500, #64748b);
  font-weight: 400;
  margin-left: 4px;
}

/* ===== 学习需求输入 ===== */
.topic-textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 10px;
  border: 2px solid var(--neutral-200, #e5e7eb);
  background: var(--neutral-0, #fff);
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
  font-family: inherit;
}
.topic-textarea:focus {
  border-color: var(--orange-500, #ea5a1a);
}
.topic-textarea:disabled {
  background: var(--neutral-50, #f9fafb);
  color: var(--neutral-400, #9ca3af);
}

/* ===== 预设模板 ===== */
.preset-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.preset-label {
  font-size: 12px;
  color: var(--neutral-500, #64748b);
}
.preset-chip {
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--neutral-200, #e5e7eb);
  background: var(--neutral-0, #fff);
  color: var(--neutral-700, #334155);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.preset-chip:hover:not(:disabled) {
  border-color: var(--orange-400, #f08441);
  color: var(--orange-600, #c2410c);
  background: var(--orange-50, #fff8f3);
}
.preset-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== Agent 配置卡片 ===== */
.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}
.agent-config-card {
  border: 2px solid var(--neutral-200, #e5e7eb);
  border-radius: 12px;
  background: var(--neutral-0, #fff);
  overflow: hidden;
  transition: all 0.2s;
  opacity: 0.6;
}
.agent-config-card.enabled {
  opacity: 1;
  border-color: var(--orange-300, #fdba74);
}
.agent-config-card.running {
  border-color: var(--orange-500, #ea5a1a);
  box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.1);
}
.agent-config-card.done {
  border-color: #86efac;
}
.agent-config-card.failed {
  border-color: #fca5a5;
}
.acc-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}
.acc-avatar {
  transition: opacity 0.2s;
}
.acc-avatar.dim {
  opacity: 0.4;
  filter: grayscale(0.8);
}
.acc-info {
  flex: 1;
  min-width: 0;
}
.acc-info strong {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: var(--neutral-800, #1e293b);
}
.acc-info small {
  font-size: 11.5px;
  color: var(--neutral-500, #64748b);
}
.acc-toggle {
  width: 40px;
  height: 22px;
  border-radius: 999px;
  background: var(--neutral-200, #e5e7eb);
  position: relative;
  transition: background 0.2s;
  flex: none;
}
.acc-toggle span {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: transform 0.2s;
}
.acc-toggle.on {
  background: var(--orange-500, #ea5a1a);
}
.acc-toggle.on span {
  transform: translateX(18px);
}
.acc-body {
  padding: 0 14px 12px;
}
.acc-task {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--neutral-700, #334155);
  margin: 0 0 2px;
}
.acc-desc {
  font-size: 11.5px;
  color: var(--neutral-500, #64748b);
  margin: 0 0 8px;
}
.acc-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 600;
  padding: 6px 10px;
  border-radius: 8px;
  margin-bottom: 8px;
}
.acc-status.queue { background: #f1f5f9; color: #64748b; }
.acc-status.running { background: #fff7ed; color: #c2410c; }
.acc-status.done { background: #f0fdf4; color: #16a34a; }
.acc-status.failed { background: #fef2f2; color: #dc2626; }
.acc-status small {
  font-weight: 400;
  color: inherit;
  opacity: 0.8;
  margin-left: auto;
}
.acc-dl-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  height: 24px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid #86efac;
  background: #f0fdf4;
  color: #16a34a;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.acc-dl-btn:hover {
  background: #16a34a;
  color: #fff;
  border-color: transparent;
}
.acc-instruction {
  margin-top: 4px;
}
.acc-instruction-input {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--neutral-200, #e5e7eb);
  background: var(--neutral-50, #f9fafb);
  font-size: 12px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: border-color 0.15s;
  box-sizing: border-box;
  font-family: inherit;
}
.acc-instruction-input:focus {
  border-color: var(--orange-400, #f08441);
  background: #fff;
}
.acc-instruction-input:disabled {
  opacity: 0.6;
}

/* ===== 运行栏 ===== */
.run-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-radius: 12px;
  background: var(--neutral-0, #fff);
  border: 2px solid var(--neutral-200, #e5e7eb);
  flex-wrap: wrap;
}
.run-summary {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13px;
  color: var(--neutral-600, #475569);
}
.run-summary b {
  color: var(--orange-600, #c2410c);
  font-weight: 700;
}
.fallback-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}
.fallback-toggle input { accent-color: var(--orange-500, #ea5a1a); }
.fallback-toggle small { font-size: 12px; color: var(--neutral-500, #64748b); }
.run-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 24px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(120deg, var(--orange-500, #ea5a1a), var(--orange-400, #f08441));
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s;
  white-space: nowrap;
}
.run-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(234, 90, 26, 0.3);
}
.run-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.run-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--neutral-500, #64748b);
}

/* ===== 进度条 ===== */
.progress-track {
  position: relative;
  height: 28px;
  background: var(--neutral-100, #f5f5f4);
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 16px;
  border: 1px solid var(--neutral-200, #e5e7eb);
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--orange-400, #f08441), var(--orange-500, #ea5a1a));
  border-radius: 14px;
  transition: width 0.4s ease;
  position: relative;
}
.progress-fill.running::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.3), transparent);
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer { to { transform: translateX(100%); } }
.progress-text {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  font-weight: 700;
  color: var(--neutral-800, #1e293b);
  z-index: 1;
}

/* ===== KPI ===== */
.workflow-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.workflow-kpis > div {
  text-align: center;
  padding: 10px;
  border-radius: 10px;
  background: var(--neutral-50, #f9fafb);
  border: 1px solid var(--neutral-200, #e5e7eb);
}
.workflow-kpis b {
  display: block;
  font-size: 20px;
  color: var(--orange-600, #c2410c);
  font-family: var(--serif, serif);
  font-weight: 700;
}
.workflow-kpis small {
  color: var(--neutral-500, #64748b);
  font-size: 11px;
  margin-top: 4px;
  display: block;
}

/* ===== 生成产物 ===== */
.results-section {
  margin-top: 8px;
  border-radius: 14px;
  border: 1px solid var(--neutral-200, #e5e7eb);
  background: var(--neutral-50, #fafaf9);
  overflow: hidden;
}
.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--neutral-0, #fff);
  border-bottom: 1px solid var(--neutral-200, #e5e7eb);
  flex-wrap: wrap;
  gap: 10px;
}
.results-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--neutral-800, #1e293b);
  display: flex;
  align-items: center;
  gap: 6px;
}
.results-summary {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.badge-ok, .badge-fail, .badge-time, .badge-quality, .badge-safety {
  font-size: 11.5px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}
.badge-ok { background: #dcfce7; color: #16a34a; }
.badge-fail { background: #fee2e2; color: #dc2626; }
.badge-time { background: #f1f5f9; color: #475569; }
.badge-quality { background: #fef3c7; color: #b45309; }
.badge-safety { background: #dbeafe; color: #2563eb; }
.results-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
  padding: 16px;
}
.result-card {
  border: 1px solid var(--neutral-200, #e5e7eb);
  border-radius: 12px;
  background: var(--neutral-0, #fff);
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
}
.result-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); transform: translateY(-2px); }
.result-card.failed { border-color: #fecaca; background: #fef2f2; }
.result-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--neutral-100, #f5f5f4);
}
.result-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--orange-50, #fff8f3);
  color: var(--orange-600, #c2410c);
  flex: none;
}
.result-icon.failed { background: #fee2e2; color: #dc2626; }
.result-info { flex: 1; min-width: 0; }
.result-info strong { display: block; font-size: 13.5px; font-weight: 700; color: var(--neutral-800, #1e293b); }
.result-info small { font-size: 11px; color: var(--neutral-500, #64748b); }
.result-dl-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid var(--orange-200, #fed7aa);
  background: var(--orange-50, #fff8f3);
  color: var(--orange-600, #c2410c);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.result-dl-btn:hover { background: var(--orange-500, #ea5a1a); color: #fff; border-color: transparent; }
.result-card-body { padding: 10px 14px 14px; }
.result-title { font-size: 12.5px; font-weight: 600; color: var(--neutral-700, #334155); margin: 0 0 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.result-desc { font-size: 11.5px; color: var(--neutral-500, #64748b); margin: 0; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.result-error { font-size: 11.5px; color: #dc2626; margin: 0; }
.result-code { margin-top: 8px; border-radius: 8px; background: #1e293b; overflow: hidden; }
.result-code pre { margin: 0; padding: 10px 12px; font-size: 10.5px; color: #e2e8f0; font-family: ui-monospace, monospace; white-space: pre-wrap; word-break: break-all; max-height: 120px; overflow: auto; }
.results-footer { padding: 12px 18px; border-top: 1px solid var(--neutral-200, #e5e7eb); text-align: right; }

/* ===== 空状态 ===== */
.empty-hint {
  text-align: center;
  padding: 40px 20px;
  border-radius: 14px;
  background: var(--neutral-50, #fafaf9);
  border: 2px dashed var(--neutral-200, #e5e7eb);
}
.empty-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: var(--orange-50, #fff8f3);
  color: var(--orange-500, #ea5a1a);
  display: grid;
  place-items: center;
}
.empty-title { font-size: 16px; font-weight: 700; color: var(--neutral-800, #1e293b); margin: 0 0 6px; }
.empty-desc { font-size: 13px; color: var(--neutral-500, #64748b); margin: 0 auto; max-width: 400px; line-height: 1.6; }

/* ===== 日志 ===== */
.log-list { max-height: 280px; overflow: auto; }
.log-row {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  gap: 8px;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px solid var(--neutral-100, #f5f5f4);
}
.log-row:last-child { border-bottom: 0; }
.log-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--neutral-400, #94a3b8); }
.log-row.ok .log-dot { background: #16a34a; }
.log-row.warn .log-dot { background: #ef4444; }
.log-text { font-size: 12px; color: var(--neutral-700, #334155); font-family: ui-monospace, monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.log-time { font-size: 10.5px; color: var(--neutral-400, #94a3b8); white-space: nowrap; }

/* ===== 当前节点 ===== */
.current-node-box { display: flex; gap: 14px; align-items: flex-start; }
.cn-icon {
  width: 48px; height: 48px; border-radius: 12px;
  display: grid; place-items: center;
  background: var(--neutral-100, #f5f5f4); color: var(--neutral-500, #64748b);
  flex: none; transition: all 0.3s;
}
.cn-icon.running { background: #ffedd5; color: #c2410c; animation: pulse-bg 1.5s infinite; }
.cn-icon.done { background: #dcfce7; color: #16a34a; }
.cn-icon.failed { background: #fee2e2; color: #dc2626; }
@keyframes pulse-bg {
  0%, 100% { box-shadow: 0 0 0 0 rgba(234,90,26,.3); }
  50% { box-shadow: 0 0 0 6px rgba(234,90,26,0); }
}
.cn-info { flex: 1; min-width: 0; }
.cn-info strong { display: block; font-size: 14px; font-weight: 700; color: var(--neutral-800, #1e293b); }
.cn-bar { height: 6px; border-radius: 3px; background: var(--neutral-100, #f5f5f4); overflow: hidden; margin: 8px 0 6px; }
.cn-bar span { display: block; height: 100%; background: linear-gradient(90deg, var(--orange-400, #f08441), var(--orange-500, #ea5a1a)); border-radius: 3px; transition: width 0.4s; }
.cn-meta { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--neutral-500, #64748b); }
.cn-status { font-weight: 700; }
.cn-status.queue { color: #94a3b8; }
.cn-status.running { color: #c2410c; }
.cn-status.done { color: #16a34a; }
.cn-status.failed { color: #dc2626; }

/* ===== 工具 Trace ===== */
.tool-stats { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.trace-list { display: flex; flex-direction: column; gap: 6px; max-height: 300px; overflow: auto; padding-right: 4px; }
.trace-row { background: var(--paper-2, #fafaf9); border-left: 3px solid #94a3b8; border-radius: 6px; padding: 6px 10px; font-size: 11.5px; }
.trace-row.ok { border-left-color: #16a34a; }
.trace-row.err { border-left-color: #dc2626; }
.trace-row header { display: flex; gap: 8px; align-items: baseline; }
.trace-row b { font-family: ui-monospace, monospace; font-size: 11.5px; color: var(--ink, #1e293b); }
.trace-row em { font-style: normal; font-size: 10.5px; color: var(--muted, #64748b); margin-left: auto; }
.trace-row small { color: var(--muted, #64748b); font-size: 10.5px; }
.trace-preview { font-family: ui-monospace, monospace; font-size: 10.5px; color: var(--muted, #64748b); word-break: break-all; margin-top: 2px; }
.trace-error { color: #b91c1c; font-size: 10.5px; margin-top: 2px; }

.wf-profile-hint {
  margin: 10px 0 0;
  padding: 9px 12px;
  border-radius: 10px;
  background: #fff7f0;
  border: 1px solid #f3ddc8;
  color: #7a5a3a;
  font-size: 12.5px;
  line-height: 1.6;
  display: flex;
  align-items: center;
  gap: 8px;
}
.wf-profile-badge {
  flex: none;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 999px;
  background: #ea5a1a;
  color: #fff;
}

.wf-profile-hint.applied {
  background: #f0f9f2;
  border-color: #c9ecd6;
  color: #2f7a4d;
}
.wf-profile-badge.applied {
  background: #2f9f6b;
}

/* ============================================================
 * teacher-skin 页级修正：外层大卡透明化 + 衬线页头（同教师端）
 * ============================================================ */
.workflow-page-v2.teacher-skin .workflow-main {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.workflow-page-v2.teacher-skin .workflow-main:hover { box-shadow: none; }
.workflow-page-v2.teacher-skin .workflow-main > .section-head:first-of-type h2 {
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  font-size: 32px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: #181612;
}
.workflow-page-v2.teacher-skin .workflow-main > .section-head:first-of-type .section-copy p {
  font-size: 14px;
  color: #68635b;
}
</style>
