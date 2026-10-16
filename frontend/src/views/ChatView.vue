/**
 * ChatView · Plan D · 4.2 — Vue 原生对话主页面
 *
 * 界面风格：类似飞书/钉钉的全屏群聊界面
 *   左栏：群成员列表（6 个 AI 伙伴 + 学生）
 *   中栏：聊天消息 + 输入框
 *   右栏：群公告 / 群文件 / 群视频 / 群相册 / Agent 协作链路（标签页）
 *
 * 路由：/chat（生产）/chat-demo（带 mock，便于离线演示）
 */
<script setup lang="ts">
defineOptions({ name: 'ChatView' });
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  ArrowLeft,
  Bell,
  BellOff,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  Cpu,
  Download,
  ExternalLink,
  FileText,
  Hash,
  Library,
  ListChecks,
  Loader2,
  Megaphone,
  MessageSquare,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  RefreshCcw,
  Route as RouteIcon,
  Search,
  Sparkles,
  Star,
  Target,
  Trash2,
  User,
  UserRound,
  Users,
  X,
} from "lucide-vue-next";

import ChatMessageList from "@/components/chat/ChatMessageList.vue";
import ChatInput from "@/components/chat/ChatInput.vue";
import ChatAgentTrace from "@/components/chat/ChatAgentTrace.vue";
import MemberList from "@/components/chat/MemberList.vue";
import {
  normalizeAgentNames,
  getAvatar,
  getMentionedAgentKinds,
  guessAgentFromMessage,
  type AvatarKind,
} from "@/constants/agentAvatars";
import { getLearnerPartner, partners } from "@/constants/companion";

import { useSession } from "@/composables/useSession";
import {
  clearSession,
  getHistory,
  streamChat,
  type ResourceItem,
} from "@/api/chat";
import {
  buildRoomId,
  listGroupChatMessages,
  type GroupChatMessage,
} from "@/api/groupChat";
import { getAuthSession } from "@/utils/auth";
import { artifactDownloadUrl, listArtifacts, generateMultiStream, type ArtifactInfo } from "@/api/artifacts";
import { listKnowledgePoints, type KnowledgePoint } from "@/api/knowledgeGraph";
import { getProfile as getLearningProfile } from "@/api/profile";
import { getRealtimeState as fetchRealtimeState, type RealtimeState } from "@/api/realtime";

// ===== 类型 =====
/** 消息气泡里可直接预览的内联附件（与 ChatBubble.ChatAttachment 同构） */
interface ChatAttachment {
  kind: "code" | "quiz" | "mindmap" | "evaluation" | "media" | "resource";
  title?: string;
  content?: string;
  language?: string;
  stdout?: string;
  items?: Array<Record<string, any>>;
  dataUri?: string;
  branches?: string[];
  leaves?: Record<string, string[]>;
  overallScore?: number;
  dimensions?: Record<string, unknown>;
  evidenceStatus?: string;
  visualizations?: Array<{ title?: string; dataUri?: string; alt?: string; description?: string }>;
  mediaType?: "audio" | "video";
  src?: string;
  status?: string;
  description?: string;
  href?: string;
  downloadName?: string;
}

interface ChatSuggestedAction {
  id: string;
  label: string;
  description: string;
  prompt: string;
  icon?: "presentation" | "video" | "mindmap" | "quiz" | "learn";
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  agentKinds?: AvatarKind[];
  primaryKind?: AvatarKind;
  timestamp: number;
  isStreaming?: boolean;
  isThinking?: boolean;
  /** 群聊角色感知：教师消息 / 推荐卡片以教师身份渲染 */
  senderType?: "agent" | "teacher";
  senderName?: string;
  /** 气泡内联附件 —— 从新生成的 artifact.metadata 提取，直接在气泡里展开 */
  attachments?: ChatAttachment[];
  /** Agent 问候语后的任务导引卡片 */
  suggestedActions?: ChatSuggestedAction[];
}

interface Stage {
  stage: string;
  status: "running" | "done" | "pending";
}

interface GroupMember {
  key: string;
  name: string;
  title: string;
  role: string;
  avatar: string;
  state: string;
  isOnline: boolean;
  isStudent: boolean;
  isTeacher?: boolean;
}

type RightTab = "overview" | "tasks" | "files" | "knowledge" | "profile" | "trace" | "members" | "settings" | "realtime";

interface TabConfig {
  key: RightTab;
  label: string;
  icon: typeof Megaphone;
  count?: number;
}

interface GeneratedResource {
  id: string;
  resourceId?: string;
  title: string;
  type: string;
  format: string;
  author: string;
  authorKind: string;
  createdAt: number;
  meta?: string;
  summary?: string;
  /** 后端 artifact.metadata 原样透传，供 quiz/code 等类型做内联预览 */
  rawMetadata?: Record<string, any>;
}

/**
 * 2026-07-12：题目/代码/思维导图预览已下沉到消息气泡里（ChatBubble.attachments），
 * 右侧文件面板不再重复展开预览，只保留下载 / 跳转。
 */

interface QuickCommand {
  label: string;
  prompt: string;
  tab: RightTab;
  icon: typeof Sparkles;
}

type ResourceZoneKey = "all" | "ppt" | "word" | "pdf" | "other";

// ===== 路由 & 会话 =====
const route = useRoute();
const router = useRouter();
const { userId, course, chatSessionId: baseSessionId, resetChatSession } = useSession();

// 课程群聊房间：学生 / 教师 / Agent 共享，room_id = course:student_id
const groupRoomId = computed(() => buildRoomId(course.value, userId.value));
const studentDisplayName = computed(() => getAuthSession()?.displayName || userId.value);
const learnerPartner = computed(() => getLearnerPartner(userId.value, studentDisplayName.value));

// 从查询参数预填消息（从知识图谱/学习路径页跳转过来时）
const prefillText = computed(() => {
  // 教师发布的学习提示词：带入输入框后由学生确认、补充，再发给 Agent。
  const teacherPrompt = route.query.prompt;
  if (typeof teacherPrompt === "string" && teacherPrompt.trim()) {
    return teacherPrompt.trim().slice(0, 4000);
  }
  // 优先处理知识点跳转（kp_name / kp_id）
  const kpName = route.query.kp_name;
  const kpId = route.query.kp_id;
  if (typeof kpName === "string" && kpName.trim()) {
    return `请帮我讲解一下「${kpName.trim()}」这个知识点${kpId ? `（${kpId}）` : ""}，最好能结合例子说明，并梳理它的先修知识和后续延伸。`;
  }
  // 兼容旧的 topic 参数
  const t = route.query.topic;
  if (typeof t === "string" && t.trim()) {
    return `请帮我讲解一下「${t.trim()}」这个知识点，最好能结合例子说明。`;
  }
  return "";
});

// 标记是否需要自动发送（从知识图谱"让智灵讲解"跳转时 ask=1）
const shouldAutoAsk = computed(() => route.query.ask === "1");

// ===== 聊天状态 =====
const messages = ref<ChatMessage[]>([]);
const loadingHistory = ref(false);
const streaming = ref(false);
const error = ref("");

// ===== 引用回复状态 =====
const quotingMessage = ref<ChatMessage | null>(null);

function handleQuote(message: ChatMessage) {
  quotingMessage.value = message;
}

function cancelQuote() {
  quotingMessage.value = null;
}

// SSE 临时状态
const activeStages = ref<Stage[]>([]);
const activeAgentsInvoked = ref<string[]>([]);
const activePrimaryAgent = ref("");
const activeQuality = ref<any>(null);
const activeSafety = ref<any>(null);
const traceExpanded = ref(true);

// ===== 右栏学习工作台 =====
const rightPanelVisible = ref(true);
const activeTab = ref<RightTab>("tasks");

// ===== 顶栏状态 =====
const showSessionMenu = ref(false);
const showAgentSelector = ref(false);
const showNewMenu = ref(false);
const notificationEnabled = ref(true);

// 切换通知
function toggleNotification() {
  notificationEnabled.value = !notificationEnabled.value;
  // 保存到本地存储
  localStorage.setItem('a3_notification_enabled', String(notificationEnabled.value));
}

// 从本地存储读取通知设置
onMounted(() => {
  const saved = localStorage.getItem('a3_notification_enabled');
  if (saved !== null) {
    notificationEnabled.value = saved === 'true';
  }
});

// ===== 会话管理 =====
interface ChatSession {
  id: string;
  type: 'group' | 'private';
  name: string;
  isFavorite?: boolean;
  isPinned?: boolean;
  agentKey?: string;
  unreadCount?: number;
}

const sessions = ref<ChatSession[]>([
  { id: 'group', type: 'group', name: 'AI 学习助手群聊', isPinned: true },
]);
const currentSessionId = ref<string>('group');
const currentSession = computed(() => sessions.value.find(s => s.id === currentSessionId.value));
const isPrivateChat = computed(() => currentSession.value?.type === 'private');
const currentPrivateAgent = computed(() => {
  if (!isPrivateChat.value) return null;
  const agentKey = currentSession.value?.agentKey;
  return agentKey ? partners.find(p => p.key === agentKey) : null;
});

const groupGuidedActions: ChatSuggestedAction[] = [
  {
    id: "generate-ml-ppt",
    label: "生成「机器学习基础」PPT",
    description: "8 页课件，包含概念、流程、案例与总结",
    prompt: "@阿匠 请围绕「机器学习基础」生成一份 8 页教学 PPT，包含核心概念、完整流程、一个生活化案例、常见误区和最后一页知识总结。",
    icon: "presentation",
  },
  {
    id: "generate-bp-video",
    label: "生成「反向传播」视频",
    description: "用动画演示梯度如何逐层传递",
    prompt: "@阿匠 请围绕「反向传播」生成一个 3—5 分钟的动画讲解视频，用简单网络演示前向计算、损失函数、梯度回传和参数更新。",
    icon: "video",
  },
  {
    id: "generate-transformer-map",
    label: "梳理 Transformer 导图",
    description: "串联注意力、编码器与解码器",
    prompt: "@阿匠 请为「Transformer 架构」生成一份层次清晰的思维导图，覆盖 Self-Attention、Multi-Head、Encoder、Decoder、位置编码和训练流程。",
    icon: "mindmap",
  },
  {
    id: "generate-supervised-quiz",
    label: "生成「监督学习」练习",
    description: "由易到难，附答案与错因解析",
    prompt: "@小龙 请围绕「监督学习」生成 8 道由易到难的练习题，覆盖分类、回归、数据划分和模型评估，并附答案、解析与常见错因。",
    icon: "quiz",
  },
];

function guidedActionsForAgent(agentKey?: string): ChatSuggestedAction[] {
  if (!agentKey || agentKey === "content") {
    return groupGuidedActions.map((action) => ({
      ...action,
      prompt: agentKey === "content" ? action.prompt.replace(/^@(?:阿匠|小龙)\s*/, "") : action.prompt,
    }));
  }

  const actionsByAgent: Record<string, ChatSuggestedAction[]> = {
    planner: [
      { id: "plan-three-days", label: "制定 3 天攻克计划", description: "拆成每日目标、产物与检查点", prompt: "请帮我制定一个 3 天攻克 Transformer 的学习计划，拆成每日目标、时间安排、学习产物和检查点。", icon: "learn" },
      { id: "plan-knowledge-path", label: "规划知识进阶路径", description: "从先修知识排到实战项目", prompt: "请为我规划一条从机器学习基础到深度学习项目实战的进阶路径，并标注每阶段的验收标准。", icon: "mindmap" },
      { id: "plan-today", label: "拆解今天的学习任务", description: "按优先级生成可执行清单", prompt: "请结合我的学习画像，把今天的学习目标拆成 3—5 个可执行任务，并说明优先级和预计用时。", icon: "learn" },
    ],
    tutor: [
      { id: "explain-backprop", label: "一步步讲反向传播", description: "从链式法则到参数更新", prompt: "请用一个可手算的小例子，一步步讲清楚反向传播中的链式法则、梯度计算和参数更新。", icon: "learn" },
      { id: "explain-attention", label: "用图解讲注意力机制", description: "解释 Q、K、V 与权重计算", prompt: "请用图解式步骤和生活类比讲清楚 Self-Attention 中 Q、K、V 的作用与权重计算。", icon: "mindmap" },
      { id: "compare-concepts", label: "对比易混知识点", description: "整理差异、联系与易错点", prompt: "请对比监督学习、无监督学习和强化学习，整理它们的差异、联系、典型场景与易错点。", icon: "learn" },
    ],
    quiz: [
      { id: "quiz-baseline", label: "生成基础诊断题", description: "快速判断当前掌握程度", prompt: "请围绕机器学习基础生成 6 道诊断题，由易到难，并在最后给出答案与能力定位。", icon: "quiz" },
      { id: "quiz-debug", label: "来一组代码 Debug 题", description: "练习定位常见实现错误", prompt: "请生成 5 道 Python 机器学习代码 Debug 题，覆盖数据处理、训练循环和指标计算，并附修复说明。", icon: "quiz" },
      { id: "quiz-weakness", label: "针对薄弱点出题", description: "根据学习画像定制练习", prompt: "请根据我当前的学习画像和薄弱知识点，生成一组分层专项练习，并说明每题训练的能力。", icon: "quiz" },
    ],
    evaluation: [
      { id: "evaluate-mastery", label: "评估当前掌握度", description: "基于已有学习证据给结论", prompt: "请基于我已有的学习记录，评估机器学习基础的掌握度；证据不足的部分请明确标注。", icon: "learn" },
      { id: "evaluate-weakness", label: "分析最近的薄弱点", description: "定位问题并给出优先级", prompt: "请分析我最近的学习表现，找出最需要优先补强的 3 个薄弱点，并给出依据。", icon: "learn" },
      { id: "evaluate-next", label: "给出下一步改进建议", description: "形成可执行的调整方案", prompt: "请结合我的目标、进度和学习偏好，给出下一步可执行的学习调整建议。", icon: "learn" },
    ],
    safety: [
      { id: "check-answer", label: "核验一段知识回答", description: "检查事实、逻辑与误导风险", prompt: "请核验我接下来提供的知识回答，检查事实错误、逻辑跳步和可能误导学习者的表达。", icon: "learn" },
      { id: "check-sources", label: "检查结论是否有依据", description: "区分事实、推断与不确定项", prompt: "请帮我检查一段学习结论的证据是否充分，并区分已证实事实、合理推断和不确定内容。", icon: "learn" },
      { id: "check-plan", label: "审查学习计划风险", description: "识别过载、缺失与不可执行项", prompt: "请审查我的学习计划，找出时间过载、先修缺失和验收标准不清的问题。", icon: "learn" },
    ],
  };

  return actionsByAgent[agentKey] || groupGuidedActions;
}

function buildGroupWelcomeMessage(): ChatMessage {
  return {
    id: `welcome-group-${Date.now()}`,
    role: "assistant",
    content: "你好！我是你的 Agent 学习小队。需要我为你做什么吗？你可以直接描述任务，也可以从下面的示例开始。",
    timestamp: Date.now(),
    agentKinds: ["planner", "tutor", "content", "quiz"],
    primaryKind: "tutor",
    suggestedActions: guidedActionsForAgent(),
  };
}

function buildPrivateWelcomeMessage(partner: (typeof partners)[number]): ChatMessage {
  return {
    id: `welcome-${partner.key}-${Date.now()}`,
    role: "assistant",
    content: `你好！我是${partner.name}，${partner.title}。需要我为你做什么吗？可以从下面的任务开始，也可以直接告诉我你想学习的知识点。`,
    timestamp: Date.now(),
    agentKinds: [partner.key as AvatarKind],
    primaryKind: partner.key as AvatarKind,
    suggestedActions: guidedActionsForAgent(partner.key),
  };
}

function buildCurrentWelcomeMessage(): ChatMessage {
  return currentPrivateAgent.value
    ? buildPrivateWelcomeMessage(currentPrivateAgent.value)
    : buildGroupWelcomeMessage();
}

// 切换会话
function switchSession(session: ChatSession) {
  currentSessionId.value = session.id;
  realtimeState.value = null;
  void loadRealtimeState();
  // 清空消息并重新加载
  messages.value = [];
  if (session.type === 'private' && session.agentKey) {
    // 私聊会话，加载与该 Agent 的历史
    loadPrivateHistory(session.agentKey);
  } else {
    // 群聊会话
    loadHistory();
  }
}

// 创建私聊会话
async function createPrivateSession(agentKey: string) {
  // 检查是否已存在
  const existing = sessions.value.find(s => s.type === 'private' && s.agentKey === agentKey);
  if (existing) {
    switchSession(existing);
    return;
  }

  // 创建新会话
  const partner = partners.find(p => p.key === agentKey);
  if (!partner) return;

  const newSession: ChatSession = {
    id: `private-${agentKey}-${Date.now()}`,
    type: 'private',
    name: partner.name,
    agentKey: agentKey,
  };
  sessions.value.push(newSession);
  switchSession(newSession);
}

// 删除会话
function deleteSession(sessionId: string) {
  const idx = sessions.value.findIndex(s => s.id === sessionId);
  if (idx === -1) return;

  const session = sessions.value[idx];
  if (session.type !== 'private') return; // 只能删除私聊

  sessions.value.splice(idx, 1);

  // 如果删除的是当前会话，切换到群聊
  if (currentSessionId.value === sessionId) {
    const groupSession = sessions.value.find(s => s.type === 'group');
    if (groupSession) {
      switchSession(groupSession);
    }
  }
}

// 加载私聊历史
async function loadPrivateHistory(agentKey: string) {
  loadingHistory.value = true;
  try {
    const r = await getHistory(chatSessionId.value);
    const partner = partners.find(p => p.key === agentKey);
    const items: ChatMessage[] = (r.history ?? []).map((h, i) => {
      const role = (h.role === "user" ? "user" : "assistant") as "user" | "assistant";
      const agentKinds = h.agent_name
        ? normalizeAgentNames([h.agent_name])
        : partner
          ? [partner.key as AvatarKind]
          : [];
      const historyResources = role === "assistant" && Array.isArray(h.resources)
        ? h.resources as ResourceItem[]
        : [];
      return {
        id: `private-hist-${i}-${Date.now()}`,
        role,
        content: role === "assistant" && agentKinds[0] === "content" && historyResources.length
          ? resourceDeliveryExplanation(historyResources)
          : h.content || "",
        timestamp: Date.now() - (r.history.length - i) * 60_000,
        agentKinds: role === "assistant" ? agentKinds : undefined,
        primaryKind: role === "assistant" ? agentKinds[0] : undefined,
        attachments: historyResources.length
          ? resourcesToAttachments(
              historyResources,
              agentKinds[0] === "content" ? "download-only" : "inline",
            )
          : undefined,
      };
    });
    if (items.length) {
      messages.value = items;
    } else if (partner) {
      messages.value = [buildPrivateWelcomeMessage(partner)];
    } else {
      messages.value = [];
    }
  } catch (e: any) {
    error.value = e?.message || '加载历史失败';
  } finally {
    loadingHistory.value = false;
  }
}

// 当前会话 ID：群聊用 base，私聊用 session 特定的
const chatSessionId = computed(() => {
  if (isPrivateChat.value && currentSession.value) {
    return currentSession.value.id;
  }
  return baseSessionId.value;
});

const knowledgePoints = ref<KnowledgePoint[]>([]);
const knowledgeLoading = ref(false);
const knowledgeError = ref("");
const profileSnapshot = ref<Record<string, any>>({});
const profileCompleteness = ref(0);
const profileLoading = ref(false);
const profileError = ref("");
const resourcesLoading = ref(false);

// ===== 实时学情仪表盘 =====
const realtimeState = ref<RealtimeState | null>(null);
const realtimeLoading = ref(false);
let realtimeTimer: ReturnType<typeof setInterval> | null = null;

async function loadRealtimeState() {
  if (!currentSession.value || !chatSessionId.value) return;
  realtimeLoading.value = true;
  try {
    // 后端按真实 chat session_id 保存学情；UI 的 "group" 只是下拉项 ID。
    // 过去用 currentSession.id 查询，永远命中不到本轮对话数据。
    const r = await fetchRealtimeState(chatSessionId.value);
    realtimeState.value = r.state;
  } catch {
    realtimeState.value = null;
  }
  realtimeLoading.value = false;
}

function startRealtimePolling() {
  stopRealtimePolling();
  void loadRealtimeState();
  realtimeTimer = setInterval(() => void loadRealtimeState(), 5000);
}

function stopRealtimePolling() {
  if (realtimeTimer) {
    clearInterval(realtimeTimer);
    realtimeTimer = null;
  }
}

function realtimeLevelColor(level: number): string {
  if (level >= 0.7) return "#ef4444";
  if (level >= 0.4) return "#f59e0b";
  return "#10b981";
}

function realtimeLevelLabel(level: number): string {
  if (level >= 0.7) return "高";
  if (level >= 0.4) return "中";
  return "低";
}

const realtimeLearnerName = computed(() =>
  learnerPartner.value.name || studentDisplayName.value || "当前学习者",
);

const realtimeProfileBasis = computed(() => {
  const profile = profileSnapshot.value || {};
  const rows: Array<{ label: string; value: string }> = [];
  const knowledge = profileValueText(profile.knowledge_base);
  const style = [profileValueText(profile.cognitive_style), profileValueText(profile.learning_preference)]
    .filter((value, index, all) => value && all.indexOf(value) === index)
    .join("；");
  const weak = profileValueText(profile.weak_points || profile.error_pattern);
  if (knowledge) rows.push({ label: "知识基础", value: knowledge });
  if (style) rows.push({ label: "学习风格与偏好", value: style });
  if (weak) rows.push({ label: "当前补强", value: weak });
  return rows.slice(0, 3);
});

const realtimeEvidence = computed(() =>
  (realtimeState.value?.evidence || []).filter(Boolean).slice(0, 5),
);

// 标签配置：保留队友的群聊右栏壳，恢复旧驾驶舱的学习功能入口。
const rightTabs = computed<TabConfig[]>(() => [
  { key: "overview", label: "概览", icon: Megaphone },
  { key: "realtime", label: "学情", icon: Brain },
  { key: "tasks", label: "任务流", icon: ListChecks, count: activeTaskCount.value },
  { key: "files", label: "文件", icon: FileText, count: tabCounts.value.files },
  { key: "knowledge", label: "知识库", icon: Library, count: tabCounts.value.knowledge },
  { key: "profile", label: "画像", icon: UserRound, count: tabCounts.value.profile },
  { key: "trace", label: "链路", icon: Cpu },
]);

// ===== 左栏 =====
const memberSearch = ref("");

const groupAnnouncement =
  "欢迎使用 AI 学习助手群聊。你可以直接发学习任务，也可以使用下方快捷动作：资料生成、知识点梳理、路径规划会进入任务流，产物会同步到文件、知识库和学习画像面板。";

const quickCommands: QuickCommand[] = [
  {
    // 演示脚本：一次触发五位专业 Agent，各自交付高密度内容
    label: "🎬 演示：Transformer 深度攻坚",
    prompt:
      "我想在 3 天内系统攻克 Transformer 架构，请 @智狐 @智灵 @阿匠 @小龙 @团团 分工协作，并分别独立回答自己的任务：\n" +
      "1. @智狐 设计 3 天高强度学习路径。每天给出 2 个可验收目标、时间预算、先修依赖、动手产物和当日检查点，用表格呈现，并给出跟不上时的降级方案；\n" +
      "2. @智灵 深入讲清 Self-Attention：标注 Q/K/V 与每一步张量形状，推导缩放点积公式，给一个可手算的微型例子，解释 Mask、Multi-Head、残差连接与 LayerNorm，并列出至少 4 个常见误区；\n" +
      "3. @阿匠 围绕「Transformer 架构」生成一份高级思维导图（7-8 个一级分支、每支 3-5 个知识节点，覆盖 Encoder/Decoder、位置编码、注意力、FFN、训练与推理），再生成一段可直接运行的 PyTorch 多头自注意力代码，包含 shape 注释、padding mask、断言和运行输出；\n" +
      "4. @小龙 设计 12 道由易到难的分层练习，至少覆盖单选、多选、判断、填空、公式推导、代码阅读、代码 Debug 和综合设计 8 类题型；每题给难度、Bloom 层级、答案与详细解析；\n" +
      "5. @团团 只依据我已有的学习画像和本次目标评估计划可行性：给出证据、完成概率、3 个主要风险、短板优先级和可执行的调整建议；若画像数据不足，明确指出缺失证据，不要凭空假设。",
    tab: "tasks",
    icon: Sparkles,
  },
  {
    label: "生成资料",
    prompt: "@阿匠 请围绕机器学习基础生成课程讲义、PPT、分层练习、语音导学和短视频讲解，并整理一份可加入学习路径的资源清单。",
    tab: "files",
    icon: FileText,
  },
  {
    label: "梳理知识点",
    prompt: "@智灵 帮我梳理监督学习、无监督学习、模型评估之间的关系，并给出前置知识和易错点。",
    tab: "knowledge",
    icon: BookOpen,
  },
  {
    label: "规划路径",
    prompt: "@智狐 根据我当前进度安排今天的学习路径，拆成可执行任务并说明优先级。",
    tab: "tasks",
    icon: RouteIcon,
  },
  {
    label: "更新画像",
    prompt: "@团团 请结合这次学习任务更新我的学习画像，并指出下一步最该补强的能力。",
    tab: "profile",
    icon: Brain,
  },
];

// demo 模式
const isDemo = computed(() => route.path === "/chat-demo" || route.query.demo === "1");

// ===== 群成员 =====
// 房间里出现过的教师（从群聊消息动态提取，教师发过言就会出现在成员列表）
const teacherMembers = ref<Array<{ id: string; name: string }>>([]);

const groupMembers = computed<GroupMember[]>(() => {
  const members: GroupMember[] = partners.map((p) => ({
    key: p.key,
    name: p.name,
    title: p.title,
    role: p.role,
    avatar: p.avatar,
    state: p.state,
    isOnline: !p.state.includes("忙"),
    isStudent: false,
    isTeacher: false,
  }));
  // 教师成员：真实群聊房间成员（发消息/指派资源/推荐路径都会出现）
  const teachers = teacherMembers.value.length
    ? teacherMembers.value
    : [{ id: "teacher", name: "王老师" }];
  for (const t of teachers) {
    members.push({
      key: `teacher-${t.id}`,
      name: t.name,
      title: "教师",
      role: "答疑 · 指派资源 · 推荐路径",
      avatar: "/avatars/wang-teacher.svg",
      isTeacher: true,
      state: "异步在线",
      isOnline: true,
      isStudent: true, // 复用"真人成员"渲染：不显示私聊按钮
    });
  }
  members.push({
    key: "student",
    name: learnerPartner.value.name,
    title: "学习者",
    role: "提问 · 学习 · 反馈",
    avatar: learnerPartner.value.avatar,
    isTeacher: false,
    state: "在线",
    isOnline: true,
    isStudent: true,
  });
  return members;
});

const filteredMembers = computed(() => {
  const q = memberSearch.value.trim().toLowerCase();
  if (!q) return groupMembers.value;
  return groupMembers.value.filter(
    (m) =>
      m.name.toLowerCase().includes(q) ||
      m.title.toLowerCase().includes(q) ||
      m.role.toLowerCase().includes(q),
  );
});

const onlineCount = computed(() => groupMembers.value.filter((m) => m.isOnline).length);

// ===== Agent 生成的资源（群文件/资料库）=====
const generatedResources = ref<GeneratedResource[]>([]);

// demo 模式灌入样例资源
const demoResources: GeneratedResource[] = [
  { id: "r1", title: "机器学习基础_课程讲义", type: "doc", format: "Markdown", author: "阿匠", authorKind: "content", createdAt: Date.now() - 3600_000, meta: "32KB", summary: "系统介绍机器学习的基本概念、常见算法与学习路线。" },
  { id: "r2", title: "反向传播_全流程解析", type: "ppt", format: "PPTX", author: "智狐", authorKind: "planner", createdAt: Date.now() - 3000_000, meta: "18.6MB", summary: "从链式法则到梯度更新的阶段拆解。" },
  { id: "r3", title: "线性回归_动画讲解", type: "video", format: "MP4", author: "智灵", authorKind: "tutor", createdAt: Date.now() - 2400_000, meta: "24:35", summary: "用可视化方式理解损失函数与拟合过程。" },
  { id: "r4", title: "K-Means聚类_原理演示", type: "anim", format: "HTML", author: "智灵", authorKind: "tutor", createdAt: Date.now() - 1800_000, meta: "980KB", summary: "动态展示中心更新和样本归类过程。" },
  { id: "r5", title: "机器学习_知识图谱总览", type: "mind", format: "PNG", author: "团团", authorKind: "evaluation", createdAt: Date.now() - 1200_000, meta: "1.2MB", summary: "梳理机器学习核心概念之间的依赖关系。" },
  { id: "r6", title: "BP算法_梯度推导图解", type: "image", format: "PNG", author: "智灵", authorKind: "tutor", createdAt: Date.now() - 600_000, meta: "560KB", summary: "对反向传播关键公式做图解。" },
  { id: "r7", title: "K-Means算法_代码实现", type: "code", format: "Python", author: "阿匠", authorKind: "content", createdAt: Date.now() - 400_000, meta: "4.8KB", summary: "使用 Python 从零实现 K-Means 聚类。" },
  { id: "r8", title: "机器学习基础_练习题库", type: "quiz", format: "JSON", author: "小龙", authorKind: "quiz", createdAt: Date.now() - 200_000, meta: "10题 · 3难度", summary: "覆盖概念理解、公式推导和代码实践。" },
];

const demoKnowledgePoints: KnowledgePoint[] = [
  { kp_id: "ml_overview", name: "机器学习基础", description: "监督学习、无监督学习、模型训练与泛化评估的总览。", bloom_level: "理解" },
  { kp_id: "supervised_learning", name: "监督学习", description: "从带标签数据学习输入到输出的映射。", bloom_level: "应用" },
  { kp_id: "unsupervised_learning", name: "无监督学习", description: "在无标签数据中发现结构、聚类或降维表示。", bloom_level: "理解" },
  { kp_id: "model_evaluation", name: "模型评估", description: "用训练/验证/测试划分和指标判断模型效果。", bloom_level: "分析" },
  { kp_id: "backpropagation", name: "反向传播", description: "基于链式法则高效计算神经网络梯度。", bloom_level: "分析" },
];

const fallbackProfileRows = [
  { key: "knowledge_base", label: "知识基础", text: "机器学习基础掌握中，需继续巩固梯度推导。", evidence: "" },
  { key: "cognitive_style", label: "认知风格", text: "偏好图解、步骤化拆解和代码示例。", evidence: "" },
  { key: "error_pattern", label: "易错模式", text: "公式链路与概念边界容易混淆。", evidence: "" },
  { key: "learning_progress", label: "学习进度", text: "当前处于算法理解到实践应用过渡期。", evidence: "" },
];

const profileLabelMap: Record<string, string> = {
  academic_context: "学业背景",
  knowledge_base: "知识基础",
  cognitive_style: "认知风格",
  error_pattern: "易错模式",
  learning_habit: "学习习惯",
  learning_progress: "学习进度",
  interest_model: "兴趣模型",
  learning_goal: "学习目标",
  time_management: "时间安排",
  self_efficacy: "学习信心",
  learning_style: "学习风格",
  learning_preference: "学习偏好",
  resource_preference: "资源偏好",
  interaction_pattern: "互动方式",
  self_learning_ability: "自学能力",
  risk_analysis: "风险提醒",
  weak_points: "薄弱点",
};

const profileDimensionOrder = [
  "academic_context",
  "knowledge_base",
  "cognitive_style",
  "learning_preference",
  "weak_points",
  "learning_goal",
  "time_management",
  "self_efficacy",
  "learning_progress",
  "learning_habit",
  "resource_preference",
  "interaction_pattern",
  "self_learning_ability",
  "risk_analysis",
  "error_pattern",
  "interest_model",
  "learning_style",
];

const profileMetadataKeys = new Set([
  "user_id",
  "nickname",
  "display_name",
  "name",
  "tier",
  "_schema",
  "scores",
  "last_interaction_at",
  "recent_topics",
]);

const fileResources = computed(() => generatedResources.value);
const knowledgePointRows = computed(() =>
  (knowledgePoints.value.length ? knowledgePoints.value : isDemo.value ? demoKnowledgePoints : []).slice(0, 9),
);
const profileRows = computed(() => {
  const profile = profileSnapshot.value || {};
  const orderedKeys = [
    ...profileDimensionOrder,
    ...Object.keys(profile).filter((key) => !profileDimensionOrder.includes(key)),
  ];
  const rows = orderedKeys
    .filter((key, index, all) => all.indexOf(key) === index)
    .filter((key) => !profileMetadataKeys.has(key) && Boolean(profileLabelMap[key]))
    .map((key) => [key, profile[key]] as const)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 8)
    .map(([key, value]) => ({
      key,
      label: profileLabelMap[key],
      text: profileValueText(value),
      evidence: profileEvidenceText(value) || (value && typeof value === "object" && !Array.isArray(value) && "score" in value ? "待补充" : ""),
    }));
  return rows.length ? rows : isDemo.value ? fallbackProfileRows : [];
});

const activeTaskCount = computed(() =>
  taskRows.value.filter((task) => task.status === "进行中" || task.status === "已完成").length,
);
const taskRows = computed(() => {
  const started = activeAgentsInvoked.value.length > 0 || activeStages.value.length > 0;
  if (!started && !isDemo.value) return [];
  return partners.map((partner, index) => {
    const active = activeAgentsInvoked.value.includes(partner.key);
    const status = active
      ? streaming.value ? "进行中" : "已完成"
      : started ? "排队中" : index < 3 ? "待启动" : "排队中";
    return {
      key: partner.key,
      name: partner.name,
      role: partner.role.split(" · ")[0],
      title: partner.title,
      status,
      accent: partner.accent,
    };
  });
});
const taskProgress = computed(() => {
  if (streaming.value) return Math.max(35, Math.min(90, activeTaskCount.value * 16 + 28));
  return activeTaskCount.value ? 100 : 0;
});

const resourceIconMap: Record<string, string> = {
  doc: "DOC", ppt: "PPT", code: "CODE", quiz: "QUIZ",
  video: "VID", anim: "HTML",
  mind: "MAP", image: "IMG", audio: "AUD",
  word: "WORD", pdf: "PDF", other: "FILE",
};

function resourceSearchText(resource: GeneratedResource): string {
  return `${resource.type} ${resource.format} ${resource.title}`.toLowerCase();
}

function resourceZoneKey(resource: GeneratedResource): Exclude<ResourceZoneKey, "all"> {
  const text = resourceSearchText(resource);
  if (text.includes("ppt") || text.includes("slide") || text.includes("演示")) return "ppt";
  if (text.includes("doc") || text.includes("word") || text.includes("讲义") || text.includes("文档")) return "word";
  if (text.includes("pdf")) return "pdf";
  return "other";
}

const lastUserMessage = computed(() => {
  const latest = [...messages.value].reverse().find((message) => message.role === "user");
  return latest?.content?.trim() || "";
});

const currentTaskTitle = computed(() => {
  if (lastUserMessage.value) return lastUserMessage.value;
  return isPrivateChat.value ? currentSession.value?.name || "私聊任务" : currentSession.value?.name || "AI 学习助手群聊";
});

const currentTaskStatus = computed(() => {
  if (streaming.value) return "执行中";
  if (messages.value.some((message) => message.role === "user")) return "已同步";
  return "待开始";
});

const currentAgentLabel = computed(() => {
  const primaryKey = activePrimaryAgent.value || activeAgentsInvoked.value[0] || currentPrivateAgent.value?.key || "";
  const partner = partners.find((item) => item.key === primaryKey);
  if (partner) return `${partner.name} · ${partner.title}`;
  return isPrivateChat.value ? currentSession.value?.name || "当前 Agent" : "Agent 团队";
});

const tabCounts = computed(() => ({
  overview: 0,
  tasks: activeTaskCount.value,
  files: fileResources.value.length,
  knowledge: knowledgePointRows.value.length,
  profile: profileRows.value.length,
  trace: activeStages.value.length,
}));

// ===== SSE =====
let abortController: AbortController | null = null;

onMounted(async () => {
  if (isDemo.value) {
    generatedResources.value = [...demoResources];
    knowledgePoints.value = [...demoKnowledgePoints];
    profileSnapshot.value = {
      knowledge_base: { level: "中等", known_topics: ["Python基础", "监督学习", "模型评估"] },
      cognitive_style: "偏好图解和步骤化推导",
      error_pattern: "容易在梯度链式求导和模型评估指标之间混淆",
      learning_progress: "机器学习基础 45%，反向传播正在突破",
    };
    profileCompleteness.value = 68;
  }
  await Promise.all([loadHistory(), loadWorkspaceData()]);
  startRealtimePolling();

  // 从知识图谱"让智灵讲解"跳转时自动发送提问
  if (shouldAutoAsk.value && prefillText.value) {
    nextTick(() => {
      handleSend(prefillText.value);
      // 发送后清除 URL 查询参数，避免刷新重复发送
      router.replace({ path: route.path, query: {} });
    });
  }
});

async function loadWorkspaceData() {
  if (isDemo.value) return;
  await Promise.allSettled([loadArtifactsPanel(), loadKnowledgePanel(), loadProfilePanel()]);
}

async function loadArtifactsPanel() {
  resourcesLoading.value = true;
  try {
    const r = await listArtifacts({ session_id: chatSessionId.value, limit: 30 });
    const mapped = (r.artifacts ?? []).map(artifactToResource);
    if (mapped.length) mergeGeneratedResources(mapped);
  } catch {
    // 文件面板可降级为会话内实时资源，不阻塞聊天。
  } finally {
    resourcesLoading.value = false;
  }
}

async function loadKnowledgePanel() {
  knowledgeLoading.value = true;
  knowledgeError.value = "";
  try {
    const r = await listKnowledgePoints(course.value);
    knowledgePoints.value = r.kps ?? [];
  } catch (e: any) {
    knowledgeError.value = e?.message || "知识库暂不可用，已展示演示知识点";
  } finally {
    knowledgeLoading.value = false;
  }
}

async function loadProfilePanel() {
  profileLoading.value = true;
  profileError.value = "";
  try {
    const r = await getLearningProfile(userId.value);
    const profile = r.profile ?? {};
    profileSnapshot.value = profile;
    const rawCompleteness = Number(r.completeness ?? profile.completeness ?? 0);
    profileCompleteness.value = rawCompleteness > 1 ? Math.round(rawCompleteness) : Math.round(rawCompleteness * 100);
  } catch (e: any) {
    profileError.value = e?.message || "学习画像暂不可用，已展示演示摘要";
  } finally {
    profileLoading.value = false;
  }
}

function addGeneratedResource(r: {
  resourceId?: string;
  title: string;
  type: string;
  format: string;
  author: string;
  authorKind: string;
  meta?: string;
  summary?: string;
  rawMetadata?: Record<string, any>;
}) {
  mergeGeneratedResources([
    {
      id: r.resourceId || `res-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      ...r,
      type: normalizeResourceType(r.type),
      createdAt: Date.now(),
    },
  ]);
}

function mergeGeneratedResources(resources: GeneratedResource[]) {
  const seen = new Set<string>();
  generatedResources.value = [...resources, ...generatedResources.value].filter((item) => {
    const key = item.resourceId || item.id || item.title;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function normalizeResourceType(type: unknown, ...mediaHints: unknown[]): string {
  const raw = [type, ...mediaHints]
    .filter((value) => typeof value === "string" || typeof value === "number")
    .map((value) => String(value).toLowerCase())
    .join(" ") || "doc";
  const isManim = raw.includes("manim");
  const isVideoFile = [".mp4", ".webm", ".mov", ".m4v", "video/"]
    .some((marker) => raw.includes(marker));

  if (["ppt", "pptx", "slide"].some((k) => raw.includes(k))) return "ppt";
  if (["quiz", "exercise", "question"].some((k) => raw.includes(k))) return "quiz";
  // Manim 有两种返回：未渲染时返回动画脚本，渲染成功时返回 MP4。
  // 不再只依据 "manim" 标签把实际视频误归为 HTML 动画。
  if (
    ["video", "mp4", "webm", "mov", "m4v"].some((k) => raw.includes(k))
    || (isManim && (isVideoFile || raw.includes("rendered-manim")))
  ) return "video";
  if (["anim", "manim", "html"].some((k) => raw.includes(k))) return "anim";
  if (["mind", "mermaid", "map"].some((k) => raw.includes(k))) return "mind";
  if (["image", "png", "jpg", "jpeg"].some((k) => raw.includes(k))) return "image";
  if (["code", "python", "py"].some((k) => raw.includes(k))) return "code";
  if (["tts", "audio", "mp3"].some((k) => raw.includes(k))) return "audio";
  return "doc";
}

function artifactToResource(artifact: ArtifactInfo): GeneratedResource {
  const meta = artifact.metadata ?? {};
  const resourceId = String(artifact.resource_id || (artifact as any).id || meta.resource_id || meta.id || "");
  const type = normalizeResourceType(
    artifact.type || meta.type,
    artifact.filepath,
    meta.filepath,
    meta.format,
    meta.mime_type,
    meta.rendered ? "rendered-manim" : "",
  );
  const title = String(meta.title || meta.topic || meta.name || resourceId || "生成资源");
  return {
    id: resourceId || `artifact-${title}`,
    resourceId: resourceId || undefined,
    title,
    type,
    format: String(meta.format || artifact.type || type).toUpperCase(),
    author: String(meta.agent_name || meta.author || "AI伙伴"),
    authorKind: String(meta.agent_kind || "content"),
    createdAt: normalizeCreatedAt(artifact.created_at),
    meta: String(meta.size || meta.duration || meta.quiz_count || "").trim(),
    summary: String(meta.summary || meta.description || meta.content || "").slice(0, 120),
    rawMetadata: meta,
  };
}

function normalizeCreatedAt(value: unknown): number {
  if (typeof value === "number") return value > 10_000_000_000 ? value : value * 1000;
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return Date.now();
}

function profileEvidenceText(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";
  const obj = value as Record<string, any>;
  const evidence = Array.isArray(obj.evidence)
    ? obj.evidence.filter((item: unknown) => item !== null && item !== undefined && String(item).trim())
    : [];
  return evidence.slice(0, 2).map((item: unknown) => String(item)).join("；");
}

function profileValueText(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return `${Math.round(value * (value <= 1 ? 100 : 1))}%`;
  if (Array.isArray(value)) return value.slice(0, 5).map((v) => String(v)).join("、");
  if (value && typeof value === "object") {
    const obj = value as Record<string, any>;
    const parts: string[] = [];
    if (obj.major || obj.grade || obj.class_name) {
      if (obj.major) parts.push(`专业：${obj.major}`);
      if (obj.grade) parts.push(`年级：${obj.grade}`);
      if (obj.class_name) parts.push(`班级：${obj.class_name}`);
    }
    if (obj.level) parts.push(`水平：${obj.level}`);
    if (obj.primary || obj.secondary) parts.push(`偏好：${[obj.primary, obj.secondary].filter(Boolean).join(" · ")}`);
    if (obj.mode || obj.pace || obj.depth) parts.push(`方式：${[obj.mode, obj.pace, obj.depth].filter(Boolean).join(" · ")}`);
    if (obj.target || obj.timeline) parts.push(`目标：${[obj.target, obj.timeline].filter(Boolean).join(" · ")}`);
    if (Array.isArray(obj.known_topics) && obj.known_topics.length) parts.push(`已掌握：${obj.known_topics.slice(0, 4).join("、")}`);
    if (Array.isArray(obj.topics) && obj.topics.length) parts.push(`关注：${obj.topics.slice(0, 4).join("、")}`);
    if (Array.isArray(obj.patterns) && obj.patterns.length) parts.push(`模式：${obj.patterns.slice(0, 3).join("、")}`);
    if (obj.interests) parts.push(`兴趣：${Array.isArray(obj.interests) ? obj.interests.slice(0, 3).join("、") : obj.interests}`);
    if (obj.weekly_hours !== undefined || obj.best_time || obj.consistency) {
      parts.push(`安排：${[obj.weekly_hours !== undefined ? `每周${obj.weekly_hours}小时` : "", obj.best_time, obj.consistency].filter(Boolean).join(" · ")}`);
    }
    if (obj.confidence !== undefined || obj.persistence || obj.help_seeking) {
      parts.push(`状态：${[obj.confidence !== undefined ? `信心${profileValueText(obj.confidence)}` : "", obj.persistence, obj.help_seeking].filter(Boolean).join(" · ")}`);
    }
    if (obj.score !== undefined) parts.push(`评分：${profileValueText(obj.score)}`);
    const evidence = profileEvidenceText(value);
    if (evidence) parts.push(`证据：${evidence}`);
    if (obj.inferred && !evidence) parts.push(`推断：${String(obj.inferred).slice(0, 80)}`);
    if (obj.status && parts.length < 3) parts.push(`状态：${String(obj.status).slice(0, 80)}`);
    if (parts.length) return parts.join(" · ");
    const readablePairs = Object.entries(obj)
      .filter(([key, item]) => !["evidence", "score", "missing_evidence", "unknown_topics"].includes(key) && item !== null && item !== undefined && item !== "")
      .slice(0, 3)
      .map(([key, item]) => `${profileLabelMap[key] || key.replace(/_/g, " ")}：${Array.isArray(item) ? item.slice(0, 3).join("、") : String(item)}`);
    return readablePairs.join(" · ") || "待完善";
  }
  return "待完善";
}

function handleQuickCommand(command: QuickCommand) {
  if (streaming.value) return;
  rightPanelVisible.value = true;
  activeTab.value = command.tab;
  handleSend(command.prompt, { focusTab: command.tab });
}

function handleSuggestedAction(action: ChatSuggestedAction) {
  if (streaming.value) return;
  const focusTab: RightTab = action.icon === "quiz"
    ? "tasks"
    : ["presentation", "video", "mindmap"].includes(action.icon || "")
      ? "files"
      : "trace";
  rightPanelVisible.value = true;
  activeTab.value = focusTab;
  handleSend(action.prompt, { focusTab });
}

function openResource(resource: GeneratedResource) {
  if (resource.resourceId) {
    router.push({ path: "/resources", query: { id: resource.resourceId } });
    return;
  }
  router.push("/resources");
}

function downloadResource(resource: GeneratedResource) {
  if (!resource.resourceId) {
    console.warn("[downloadResource] resource has no resourceId, opening resource page instead", resource);
    openResource(resource);
    return;
  }
  // 统一走通用下载端点 /download/{rid}，后端从 registry filepath 直接返回文件
  const url = artifactDownloadUrl(resource.resourceId, "generic");
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = resource.title || "学习资源";
  anchor.rel = "noopener noreferrer";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

// ===== 一键生成资源（不离开聊天页面）=====
const quickGenTopic = ref("");
const quickGenRunning = ref(false);
const quickGenProgress = ref("");
const showQuickGen = ref(false);

function toggleQuickGen() {
  showQuickGen.value = !showQuickGen.value;
}

function profileSignal(...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = profileSnapshot.value?.[key];
    if (typeof value === "string" && value.trim()) return value.trim().slice(0, 240);
    if (Array.isArray(value)) {
      const text = value.filter(Boolean).map(String).join("；").trim();
      if (text) return text.slice(0, 240);
    }
    if (value && typeof value === "object") {
      const text = Object.values(value as Record<string, unknown>)
        .filter((item) => typeof item === "string" || typeof item === "number")
        .map(String)
        .join("；")
        .trim();
      if (text) return text.slice(0, 240);
    }
  }
  return undefined;
}

function quickGenerateContext(topic: string) {
  const routeKpId = typeof route.query.kp_id === "string" ? route.query.kp_id.trim() : "";
  const candidates = knowledgePoints.value.length
    ? knowledgePoints.value
    : (isDemo.value ? demoKnowledgePoints : []);
  const normalizedTopic = topic.toLowerCase();
  const matchedKp = candidates.find((kp) => String(kp.kp_id || kp.id || "") === routeKpId)
    ?? candidates.find((kp) => {
      const name = String(kp.name || kp.label || "").trim().toLowerCase();
      return Boolean(name && (normalizedTopic.includes(name) || name.includes(normalizedTopic)));
    });

  return {
    // 与学习画像、证据账本和教师端干预效果回流关联。
    user_id: userId.value,
    kp_id: String(matchedKp?.kp_id || matchedKp?.id || routeKpId || "") || undefined,
    bloom_level: String(matchedKp?.bloom_level || "") || undefined,
    learning_objective: profileSignal("learning_objective", "learning_goal", "goal", "current_goal")
      || `理解并能运用「${topic}」解决当前学习问题`,
    misconception: profileSignal("misconception", "error_pattern", "weak_points", "weaknesses"),
  };
}

async function runQuickGenerate() {
  const topicText = quickGenTopic.value.trim() || "机器学习基础";
  if (quickGenRunning.value) return;
  const personalization = quickGenerateContext(topicText);
  quickGenRunning.value = true;
  quickGenProgress.value = "正在启动多 Agent 并行生成…";
  activeTab.value = "files";
  rightPanelVisible.value = true;

  generateMultiStream(
    {
      topic: topicText,
      types: ["pptx", "mermaid", "code", "tts", "manim"],
      session_id: chatSessionId.value,
      ...personalization,
      // 优先请求可播放 MP4；服务不可用时后端仍会让其它资源正常降级完成。
      include_manim: true,
      manim_render: true,
      manim_template: "concept",
    },
    {
      onStart: (data) => {
        quickGenProgress.value = `已启动，共 ${data.total} 类资源待生成…`;
      },
      onProgress: (data) => {
        const labelMap: Record<string, string> = {
          pptx: "PPT", mermaid: "思维导图", code: "代码", tts: "音频", manim: "讲解视频",
        };
        const label = labelMap[data.type] ?? data.type;
        if (data.status === "done") {
          quickGenProgress.value = `✓ ${label} 生成成功`;
          // 将生成的资源归档到文件列表
          const envelope = data.envelope;
          const dlId = envelope?.downloads?.[0]?.id as string | undefined;
          const meta = envelope?.metadata ?? {};
          const downloadHints = (envelope?.downloads ?? []).flatMap((download) => [
            download?.type,
            download?.filename,
            download?.metadata?.format,
          ]);
          const resourceType = normalizeResourceType(
            data.type,
            envelope?.filepath,
            meta.filepath,
            meta.format,
            meta.mime_type,
            meta.rendered ? "rendered-manim" : "",
            ...downloadHints,
          );
          const formatHint = String(meta.format || "").trim().toLowerCase();
          addGeneratedResource({
            resourceId: dlId,
            title: meta.title || meta.topic || `${label} · ${topicText}`,
            type: resourceType,
            format: resourceType === "video" && (!formatHint || formatHint === "manim")
              ? "MP4"
              : String(meta.format || data.type).toUpperCase(),
            author: String(meta.agent_name || meta.author || "阿匠"),
            authorKind: "content",
            meta: meta.duration_ms ? `${(meta.duration_ms / 1000).toFixed(1)}s` : "",
            summary: String(meta.summary || meta.description || "").slice(0, 120),
          });
        } else {
          quickGenProgress.value = `✗ ${label} 生成失败：${data.detail}`;
        }
      },
      onDone: (result) => {
        quickGenProgress.value = `完成！成功 ${result.success_count}/${result.types_requested.length} 项，耗时 ${(result.total_duration_ms / 1000).toFixed(1)}s`;
        quickGenRunning.value = false;
        // 刷新 artifact 面板
        void loadArtifactsPanel();
      },
      onError: (err) => {
        quickGenProgress.value = `生成失败：${err}`;
        quickGenRunning.value = false;
      },
    },
  );
}

async function loadHistory() {
  if (isDemo.value) {
    messages.value = [
      buildGroupWelcomeMessage(),
      {
        id: "demo-1",
        role: "user",
        content: "反向传播算法到底是怎么算梯度的？我看了三遍还是没懂。",
        timestamp: Date.now() - 60_000,
      },
      {
        id: "demo-2",
        role: "assistant",
        content:
          "我们让 3 个 Agent 一起拆这个问题：智狐先拆 BP 的四步流水线；智灵接着用链式法则一步步推；球球最后做事实校验。\n\n先把 BP 看成一个流水线：前向 → 计算 loss → 反向求梯度 → 更新参数。每一步都是链式法则的局部应用。",
        agentKinds: ["planner", "tutor", "safety"],
        primaryKind: "tutor",
        timestamp: Date.now() - 55_000,
      },
    ];
    return;
  }

  loadingHistory.value = true;
  try {
    const r = await getHistory(chatSessionId.value);
    const items: ChatMessage[] = (r.history ?? []).map((h, i) => {
      const role = (h.role === "user" ? "user" : "assistant") as "user" | "assistant";
      // 从历史记录中的 agent_name 恢复头像，避免刷新后全部回退为智灵
      const agentKinds = h.agent_name ? normalizeAgentNames([h.agent_name]) : [];
      const attachmentMode = agentKinds[0] === "content" ? "download-only" : "inline";
      const historyResources = role === "assistant" && Array.isArray(h.resources)
        ? h.resources as ResourceItem[]
        : [];
      return {
        id: `hist-${i}-${Date.now()}`,
        role,
        content: role === "assistant" && agentKinds[0] === "content" && historyResources.length
          ? resourceDeliveryExplanation(historyResources)
          : h.content || "",
        timestamp: Date.now() - (r.history.length - i) * 60_000,
        agentKinds: role === "assistant" ? agentKinds : undefined,
        primaryKind: role === "assistant" ? agentKinds[0] : undefined,
        attachments: historyResources.length
          ? resourcesToAttachments(historyResources, attachmentMode)
          : undefined,
      };
    });
    // 合并群聊房间里的教师消息 / 资源推荐 / 路径推荐（学生自己的问答已在会话历史里）
    const teacherItems = await loadTeacherRoomMessages();
    const merged = [...items, ...teacherItems].sort((a, b) => a.timestamp - b.timestamp);
    messages.value = merged.length ? merged : [buildGroupWelcomeMessage()];
  } catch (e: any) {
    error.value = e?.message || "加载历史失败";
  } finally {
    loadingHistory.value = false;
  }
}

/** 群聊增量游标：已看到的最新消息 created_at（秒），轮询用 */
let lastRoomTs = 0;

function toTeacherBubble(m: GroupChatMessage): ChatMessage {
  return {
    id: `room-${m.id}`,
    role: "assistant" as const,
    content: formatTeacherMessage(m),
    timestamp: Math.round((m.created_at || 0) * 1000),
    senderType: "teacher" as const,
    senderName: m.sender_name || "教师",
  };
}

/** 拉取群聊房间中教师发出的消息并转成气泡（资源/路径卡片转成 Markdown 卡片文案） */
async function loadTeacherRoomMessages(): Promise<ChatMessage[]> {
  try {
    const r = await listGroupChatMessages(groupRoomId.value);
    const all = r.messages ?? [];
    lastRoomTs = all.reduce((acc, m) => Math.max(acc, m.created_at || 0), lastRoomTs);
    // 从消息里提取教师成员，让成员列表显示真实的老师
    const seen = new Map<string, string>();
    for (const m of all) {
      if (m.sender_role === "teacher") {
        seen.set(m.sender_id || "teacher", m.sender_name || "老师");
      }
    }
    if (seen.size) {
      teacherMembers.value = [...seen.entries()].map(([id, name]) => ({ id, name }));
    }
    return all
      .filter((m) => m.sender_role === "teacher" || m.message_type === "system_notice")
      .map(toTeacherBubble);
  } catch {
    // 群聊房间为空/后端未启动时静默跳过，不影响原有会话历史
    return [];
  }
}

/** 30s 增量轮询：学生停留页面期间，教师新发的消息/推荐卡片自动出现 */
let roomPollTimer: ReturnType<typeof setInterval> | null = null;

async function pollTeacherRoomMessages() {
  if (isDemo.value || isPrivateChat.value || streaming.value) return;
  try {
    const r = await listGroupChatMessages(groupRoomId.value, 100, lastRoomTs);
    const fresh = r.messages ?? [];
    if (!fresh.length) return;
    lastRoomTs = fresh.reduce((acc, m) => Math.max(acc, m.created_at || 0), lastRoomTs);
    const teacherBubbles = fresh
      .filter((m) => m.sender_role === "teacher" || m.message_type === "system_notice")
      .filter((m) => !messages.value.some((existing) => existing.id === `room-${m.id}`))
      .map(toTeacherBubble);
    if (teacherBubbles.length) {
      messages.value.push(...teacherBubbles);
    }
  } catch {
    // 轮询失败静默，下一轮再试
  }
}

onMounted(() => {
  roomPollTimer = setInterval(() => void pollTeacherRoomMessages(), 30_000);
});

onUnmounted(() => {
  if (roomPollTimer) clearInterval(roomPollTimer);
  roomPollTimer = null;
  stopRealtimePolling();
});

function formatTeacherMessage(m: GroupChatMessage): string {
  if (m.message_type === "resource_card") {
    const title = m.payload?.title || "学习资源";
    const type = m.payload?.type || "document";
    return `📚 **老师推荐了资源**《${title}》（${type}）\n\n${m.content}\n\n> 前往「资源库」即可查看该资源。`;
  }
  if (m.message_type === "path_card") {
    const title = m.payload?.title || "学习路径";
    const count = m.payload?.stages_count || 0;
    const preview = (m.payload?.stages_preview || []).join(" → ");
    return `🧭 **老师为你规划了学习路径**「${title}」（${count} 个阶段）${preview ? `\n\n${preview}` : ""}\n\n${m.content}\n\n> 已同步到「学习路径」页，进入即可开始。`;
  }
  return m.content;
}

function handleSend(message: string, options: { focusTab?: RightTab } = {}) {
  if (!message.trim()) return;

  const userMsg: ChatMessage = {
    id: `u-${Date.now()}`,
    role: "user",
    content: message,
    timestamp: Date.now(),
  };
  messages.value.push(userMsg);

    const assistantId = `a-${Date.now()}`;
  // 在 SSE meta 事件到来前，预推断 Agent 头像：
  // 1. 私聊时直接使用当前私聊的 Agent
  // 2. 群聊时根据 @ 提及 / 关键词猜测
  // 避免思考阶段错误显示智灵。猜不到时留 undefined，ChatBubble 会显示"思考中"占位。
  let guessedKind: AvatarKind | null = null;
  if (isPrivateChat.value && currentPrivateAgent.value) {
    // 私聊时直接使用当前 Agent 的 key
    guessedKind = currentPrivateAgent.value.key as AvatarKind;
  } else {
    // 多 @ 属于团队任务：先显示“团队思考中”，等 agent_start 后再拆成具名气泡。
    const mentioned = getMentionedAgentKinds(message);
    guessedKind = mentioned.length > 1 ? null : guessAgentFromMessage(message);
  }
  const assistantMsg: ChatMessage = {
    id: assistantId,
    role: "assistant",
    content: "",
    timestamp: Date.now(),
    isStreaming: true,
    agentKinds: guessedKind ? [guessedKind] : [],
    primaryKind: guessedKind ?? undefined,
  };
  messages.value.push(assistantMsg);

  activeStages.value = [];
  activeAgentsInvoked.value = [];
  activePrimaryAgent.value = "";
  activeQuality.value = null;
  activeSafety.value = null;
  traceExpanded.value = true;
  rightPanelVisible.value = true;
  activeTab.value = options.focusTab ?? "trace";
  streaming.value = true;
  error.value = "";

  if (isDemo.value) {
    simulateDemoStream(assistantId, message);
    return;
  }
  startRealStream(assistantId, message);
}
function simulateDemoStream(assistantId: string, message: string) {
  const mentioned = getMentionedAgentKinds(message);
  if (/transformer|self[- ]?attention/i.test(message) && mentioned.length > 1) {
    simulateTransformerTeamDemo(assistantId);
    return;
  }

  const fakeReply = `（Demo 模式）这是对「${message}」的模拟回复。\n\n真实环境下，A3 系统会让 6 个 Agent 协作回答：智狐规划、智灵讲解、球球校验、小龙出题、团团评估、阿匠生成多模态资源。\n\n打开 /chat（非 demo）即可接 SSE 流式真实后端。`;

  const stages = ["意图识别", "知识检索", "资源生成", "多 Agent 辩论", "安全校验", "反思", "画像更新"];
  let i = 0;
  activeStages.value = stages.map((s) => ({ stage: s, status: "pending" }));

  const tickStage = () => {
    if (i < stages.length) {
      activeStages.value = activeStages.value.map((s, idx) => ({
        ...s,
        status: idx < i + 1 ? "done" : idx === i ? "running" : "pending",
      }));
      i += 1;
      setTimeout(tickStage, 250);
    }
  };
  tickStage();

  let pos = 0;
  const chunkSize = 4;
  const interval = setInterval(() => {
    pos += chunkSize;
    const text = fakeReply.slice(0, pos);
    const msg = messages.value.find((m) => m.id === assistantId);
    if (msg) msg.content = text;
    if (pos >= fakeReply.length) {
      clearInterval(interval);
      const m = messages.value.find((m) => m.id === assistantId);
      if (m) {
        m.isStreaming = false;
        m.agentKinds = ["tutor", "content"];
        m.primaryKind = "tutor";
      }
      activeQuality.value = { overall_passed: true, overall_score: 0.85 };
      activeSafety.value = { overall_risk: 0.05, passed: true };
      streaming.value = false;
      // 模拟生成资源归档
      addGeneratedResource({
        title: `${message.slice(0, 12)}..._讲解笔记`,
        type: "doc",
        format: "Markdown",
        author: "智灵",
        authorKind: "tutor",
        meta: "12KB",
      });
    }
  }, 30);
}

/**
 * 离线演示的确定性剧本：真实 SSE 不可用时，仍完整展示“一个任务、五位 Agent、五份独立交付物”。
 * 内容与线上提示词的验收标准保持一致，避免演示页退化成单气泡占位文案。
 */
function demoDownload(text: string, mime: string, filename: string): ChatAttachment {
  return {
    kind: "resource",
    title: filename,
    href: `data:${mime};charset=utf-8,${encodeURIComponent(text)}`,
    downloadName: filename,
    description: "演示文件已准备好，点击下载链接获取完整内容。",
  };
}

function simulateTransformerTeamDemo(assistantId: string) {
  const code = [
    "import math",
    "import torch",
    "from torch import nn",
    "",
    "class MultiHeadSelfAttention(nn.Module):",
    "    def __init__(self, d_model: int = 32, heads: int = 4):",
    "        super().__init__()",
    "        assert d_model % heads == 0",
    "        self.heads, self.d_head = heads, d_model // heads",
    "        self.qkv = nn.Linear(d_model, 3 * d_model)",
    "        self.out = nn.Linear(d_model, d_model)",
    "",
    "    def forward(self, x, padding_mask=None):",
    "        # x: [batch, tokens, d_model]",
    "        b, n, d = x.shape",
    "        qkv = self.qkv(x).view(b, n, 3, self.heads, self.d_head)",
    "        q, k, v = qkv.unbind(dim=2)",
    "        q, k, v = [t.transpose(1, 2) for t in (q, k, v)]  # [B,H,N,Dh]",
    "        scores = q @ k.transpose(-2, -1) / math.sqrt(self.d_head)",
    "        if padding_mask is not None:",
    "            scores = scores.masked_fill(~padding_mask[:, None, None, :], -torch.inf)",
    "        attention = scores.softmax(dim=-1)",
    "        context = (attention @ v).transpose(1, 2).contiguous().view(b, n, d)",
    "        output = self.out(context)",
    "        assert output.shape == x.shape",
    "        return output, attention",
    "",
    "torch.manual_seed(7)",
    "x = torch.randn(2, 5, 32)",
    "mask = torch.tensor([[1, 1, 1, 1, 0], [1, 1, 1, 0, 0]], dtype=torch.bool)",
    "y, weights = MultiHeadSelfAttention()(x, mask)",
    "print('output:', tuple(y.shape))",
    "print('attention:', tuple(weights.shape))",
    "print('masked max:', weights[0, :, :, 4].max().item())",
  ].join("\n");

  const quizItems: Array<Record<string, any>> = [
    { type: "choice", difficulty: "easy", bloom: "记忆", question: "Self-Attention 中 Q、K、V 分别承担什么角色？", options: ["Q 发起查询，K 描述可匹配特征，V 携带被聚合内容", "三者完全相同", "Q 只用于输出", "V 只用于位置编码"], answer: "A", explanation: "相似度由 QKᵀ 决定，权重再作用到 V。" },
    { type: "multi_choice", difficulty: "easy", bloom: "理解", question: "哪些机制不会改变序列长度？", options: ["Self-Attention", "逐位置 FFN", "残差连接", "词嵌入查表"], answer: "A、B、C、D", explanation: "它们都保持 token 轴长度；仅表示维度或内容发生变化。" },
    { type: "judge", difficulty: "easy", bloom: "理解", question: "多头注意力只是把同一份注意力权重复制 h 次。", answer: "错误", explanation: "每个头拥有不同的投影子空间，能学习不同关系。" },
    { type: "fill", difficulty: "medium", bloom: "应用", question: "若 d_model=512、h=8，则每个头的 d_head=____，缩放因子为____。", answer: "64；1/√64=1/8", explanation: "d_head=d_model/h，缩放用于控制点积方差。" },
    { type: "short", difficulty: "medium", bloom: "分析", question: "推导 scaled dot-product attention，并解释不缩放会发生什么。", answer: "softmax(QKᵀ/√d_k)V；不缩放时点积方差随 d_k 增大，softmax 易饱和、梯度变小。", explanation: "假设各维独立且方差约为 1，点积方差约为 d_k。" },
    { type: "short", difficulty: "medium", bloom: "应用", question: "给出 B=2、N=5、d_model=32、h=4 时 QKᵀ 和注意力输出的形状。", answer: "QKᵀ=[2,4,5,5]；拼接后的输出=[2,5,32]。", explanation: "每头 d_head=8，token 两两计算相关性。" },
    { type: "code", difficulty: "medium", bloom: "分析", question: "阅读代码：为什么 transpose 后通常要调用 contiguous() 再 view？", signature: "x.transpose(1, 2).contiguous().view(B, N, D)", answer: "transpose 改变 stride，内存可能不连续；contiguous 生成连续布局，保证 view 合法且语义正确。", explanation: "也可用 reshape，由框架在必要时复制。" },
    { type: "debug", difficulty: "hard", bloom: "评价", question: "Debug：padding_mask 形状为 [B,N]，代码 scores.masked_fill(~mask, -inf) 为什么广播失败？", signature: "scores: [B,H,N,N]", answer: "应改为 ~mask[:, None, None, :]，让 mask 对齐 key 维。", explanation: "padding mask 屏蔽被关注的 key；causal mask 则通常是 [N,N]。" },
    { type: "debug", difficulty: "hard", bloom: "分析", question: "若某一行 scores 全部为 -inf，softmax 会产生什么问题？如何处理？", answer: "会得到 NaN；至少保留一个有效位置，或在全屏蔽行使用安全值并在 softmax 后清零。", explanation: "工程实现需覆盖全 padding 样本这一边界条件。" },
    { type: "short", difficulty: "hard", bloom: "分析", question: "比较 Pre-LN 与 Post-LN 的计算顺序及训练稳定性。", answer: "Pre-LN: x+F(LN(x))，深层网络梯度更稳定；Post-LN: LN(x+F(x))，原论文采用但深层训练更敏感。", explanation: "二者最终性能依任务与训练配置而异。" },
    { type: "case", difficulty: "hard", bloom: "创造", question: "为长文档摘要设计一种把 O(N²) 注意力成本降下来的方案。", answer: "可组合局部窗口+少量全局 token，或块稀疏/线性注意力；需说明跨块信息通路与复杂度。", explanation: "评价重点是信息可达性、复杂度和任务适配，而非只写模型名。" },
    { type: "case", difficulty: "hard", bloom: "创造", question: "设计最小实验，验证不同头是否学习了互补关系。", answer: "记录各头注意力图，计算头间相似度/熵；逐头消融并比较验证集指标，同时控制随机种子。", explanation: "可视化只能提供线索，消融实验更接近因果证据。" },
  ];

  const responses: Array<{ kind: AvatarKind; content: string; attachments?: ChatAttachment[] }> = [
    {
      kind: "planner",
      content: [
        "## 3 天 Transformer 冲刺路径",
        "",
        "| 天次 | 两个可验收目标 | 时间 | 动手产物 | 当日检查点 |",
        "|---|---|---:|---|---|",
        "| Day 1 · 机制 | ① 能从形状推导 Q/K/V 与缩放点积；② 手算 3-token 注意力 | 3.5h | 手算表 + NumPy 单头实现 | 不看资料写出公式并解释 √dₖ |",
        "| Day 2 · 架构 | ① 画出 Encoder/Decoder 数据流；② 说清 MHA、FFN、残差、LN、Mask | 4h | 架构图 + PyTorch MHA | 对每一层标注 [B,N,D] |",
        "| Day 3 · 工程 | ① 跑通最小 Transformer；② 定位 3 类 mask/shape bug | 4h | 可运行代码 + 12 题测评 | 正确率 ≥80%，能解释错误根因 |",
        "",
        "**先修依赖**：矩阵乘法、softmax、基础 PyTorch 张量操作。**降级方案**：若每天少于 2h，保留公式手算、架构复述和最小代码，暂缓训练技巧与长序列变体。",
      ].join("\n"),
    },
    {
      kind: "tutor",
      content: [
        "## Self-Attention：从张量到直觉",
        "",
        "输入 `X∈R^{B×N×D}`，线性投影得到 `Q=XW_Q`、`K=XW_K`、`V=XW_V`。Q 表示“我在找什么”，K 表示“我能被怎样匹配”，V 表示“匹配后取走什么信息”。",
        "",
        "**缩放点积**：`Attention(Q,K,V)=softmax(QKᵀ/√d_k)V`。若 Q/K 各维近似独立、方差为 1，点积方差随 `d_k` 增至 `d_k`；除以 `√d_k` 可避免 softmax 饱和。",
        "",
        "**微型例子**：令 `q=[1,0]`，`k₁=[1,0]`、`k₂=[0,1]`，则缩放 logits 为 `[1/√2,0]`，softmax≈`[0.67,0.33]`；输出是 `0.67v₁+0.33v₂`。",
        "",
        "**形状链**：`[B,N,D] → [B,H,N,D_h] → scores[B,H,N,N] → context[B,H,N,D_h] → [B,N,D]`。多头不是复制：每个头在不同投影子空间学习局部、句法、指代或位置关系；拼接后再投影融合。Padding mask 屏蔽补齐 token，causal mask 阻止看到未来。残差保留原信号，LayerNorm 稳定特征尺度。",
        "",
        "**4 个误区**：① Q/K/V 是三个固定语义向量；② 头越多一定越好；③ mask 在 softmax 后再乘就等价；④ 注意力图等同于因果解释。",
      ].join("\n"),
    },
    {
      kind: "content",
      content: "## 架构资产已生成\n\nTransformer 的思维导图、代码案例和课件说明已整理好，下面提供下载入口；聊天中不重复展开源码或 PPT 大纲。",
      attachments: [
        demoDownload(
          ["mindmap Transformer 架构", "  整体数据流", "  表示与位置", "  多头注意力", "  Encoder / Decoder", "  训练目标与推理优化", "  诊断与扩展"].join("\n"),
          "text/plain",
          "Transformer-架构思维导图.mmd",
        ),
        demoDownload(code, "text/x-python", "Transformer-多头自注意力.py"),
        demoDownload(
          "# Transformer 架构课件说明\n\n问题边界 → Self-Attention → Encoder/Decoder → Mask 与 LayerNorm → 工程实现 → 迁移练习",
          "text/markdown",
          "Transformer-架构课件说明.md",
        ),
      ],
    },
    {
      kind: "quiz",
      content: "## 12 题分层训练已就绪\n\n题型覆盖概念、形状、公式推导、代码阅读、代码 Debug 与系统设计；前 4 题建立基线，中间 4 题迁移到代码，最后 4 题检验分析与设计能力。展开每题可查看答案和解析。",
      attachments: [{ kind: "quiz", title: "Transformer · 8 类题型能力阶梯", items: quizItems }],
    },
    {
      kind: "evaluation",
      content: [
        "## 可行性评估（仅基于当前证据）",
        "",
        "**结论：有条件可行，当前估计完成概率 65%–75%。** 证据只有“目标明确为 3 天”和“能提出公式、代码、Debug 等具体交付要求”；目前缺少每日可用时长、线代/PyTorch 基线与历史正确率，因此不做能力臆测。",
        "",
        "| 优先级 | 主要风险 | 预警信号 | 调整动作 |",
        "|---|---|---|---|",
        "| P0 | 范围过宽 | Day 1 手算仍无法独立完成 | 冻结长序列/MoE，只保留核心架构 |",
        "| P1 | 会看不会写 | 代码离开示例就出现 shape/mask 错误 | 每天至少 45 分钟闭卷重写 |",
        "| P2 | 缺少反馈闭环 | 做题后只看答案、不归因 | 错题按概念/公式/工程三类复盘 |",
        "",
        "**建议先补证据**：用 20 分钟完成第 1、4、8 题作为基线；若正确率 <50%，Day 1 增加 1 小时矩阵与 softmax 复习；若 ≥80%，把时间转移到 Debug 和架构取舍。",
      ].join("\n"),
      attachments: [{
        kind: "evaluation",
        title: "3 天计划 · 可行性证据图",
        overallScore: 0.7,
        evidenceStatus: "insufficient",
        dimensions: {
          "目标清晰度": 0.9,
          "时间可验证性": 0.62,
          "先修证据": 0.35,
          "反馈闭环": 0.78,
        },
      }],
    },
  ];

  const stages = ["意图拆解", "角色路由", "并行生成", "资源组装", "质量校验"];
  activeStages.value = stages.map((stage, index) => ({ stage, status: index === 0 ? "running" : "pending" }));
  activeAgentsInvoked.value = [];

  responses.forEach((response, index) => {
    window.setTimeout(() => {
      activeAgentsInvoked.value = responses.slice(0, index + 1).map((item) => item.kind);
      activePrimaryAgent.value = response.kind;
      activeStages.value = stages.map((stage, stageIndex) => ({
        stage,
        status: stageIndex < Math.min(index + 1, stages.length) ? "done" : stageIndex === Math.min(index + 1, stages.length) ? "running" : "pending",
      }));

      const id = index === 0 ? assistantId : `demo-agent-${Date.now()}-${index}`;
      const existing = messages.value.find((item) => item.id === id);
      const payload: ChatMessage = {
        id,
        role: "assistant",
        content: response.content,
        timestamp: Date.now() + index,
        agentKinds: [response.kind],
        primaryKind: response.kind,
        isThinking: false,
        isStreaming: index < responses.length - 1,
        attachments: response.attachments,
      };
      if (existing) Object.assign(existing, payload);
      else messages.value.push(payload);

      if (index > 0) {
        const previousId = index === 1 ? assistantId : messages.value[messages.value.length - 2]?.id;
        const previous = messages.value.find((item) => item.id === previousId);
        if (previous) previous.isStreaming = false;
      }

      if (index === responses.length - 1) {
        payload.isStreaming = false;
        activeStages.value = stages.map((stage) => ({ stage, status: "done" }));
        activePrimaryAgent.value = "planner";
        activeQuality.value = { overall_passed: true, overall_score: 0.94 };
        activeSafety.value = { overall_risk: 0.02, passed: true };
        streaming.value = false;
        addGeneratedResource({ title: "Transformer 高级知识地图", type: "mindmap", format: "Mermaid", author: "阿匠", authorKind: "content", meta: "8 分支 · 30 节点" });
        addGeneratedResource({ title: "PyTorch 多头自注意力", type: "code", format: "Python", author: "阿匠", authorKind: "content", meta: "可运行 · 含 Mask" });
        addGeneratedResource({ title: "Transformer 12 题能力阶梯", type: "quiz", format: "交互题集", author: "小龙", authorKind: "quiz", meta: "8 类题型 · 含解析" });
      }
    }, 320 + index * 520);
  });
}

type ResourceAttachmentMode = "inline" | "download-only";

/**
 * Content Agent 只负责说明交付物，不在群聊气泡里重复展开文件正文。
 * 历史消息和旧版后端可能仍带有 PPT 大纲/代码正文，因此在渲染边界再次收口。
 */
function resourceDeliveryExplanation(resources: ResourceItem[]): string {
  const titles = resources
    .map((item) => String(item?.title || "").trim())
    .filter(Boolean)
    .slice(0, 3);
  const suffix = titles.length ? `（${titles.join("、")}）` : "";
  return `已生成${suffix}，请点击下方下载按钮获取完整文件。`;
}

function resourcesToAttachments(
  resources: ResourceItem[],
  mode: ResourceAttachmentMode = "inline",
): ChatAttachment[] {
  const attachments: ChatAttachment[] = [];
  for (const r of resources) {
    if (!r || typeof r !== "object") continue;
    const anyR = r as Record<string, any>;
    const meta = r.metadata && typeof r.metadata === "object" ? r.metadata : {};
    const pick = (key: string) => anyR[key] ?? meta[key];
    const typeStr = String(r.type || "").toLowerCase();
    const titleStr = String(r.title || meta.title || "学习资源");
    const downloads = Array.isArray(r.downloads)
      ? r.downloads
      : Array.isArray(meta.downloads) ? meta.downloads : [];
    const download = downloads.find((item) => item?.id && item?.exists !== false)
      || downloads.find((item) => item?.id);
    const href = download?.id ? artifactDownloadUrl(download.id, "generic") : "";
    const downloadAttachment: ChatAttachment | null = href
      ? {
          kind: "resource",
          title: titleStr,
          href,
          downloadName: download?.filename,
          description: `完整${String(r.format || r.type || "文件")}已生成，请点击下载后查看。`,
        }
      : null;

    // 阿匠只在聊天中交付解释和下载入口，不重复展开源码、导图节点或 PPT 大纲。
    if (mode === "download-only") {
      if (downloadAttachment) attachments.push(downloadAttachment);
      continue;
    }

    if (typeStr.includes("evaluation")) {
      const visualsRaw = pick("visualizations");
      const visualizations = Array.isArray(visualsRaw)
        ? visualsRaw.map((item: any) => ({
            title: String(item?.title || "评估图表"),
            dataUri: String(item?.data_uri || item?.dataUri || ""),
            alt: String(item?.alt || item?.title || "学习评估图表"),
            description: String(item?.description || ""),
          })).filter((item) => item.dataUri)
        : [];
      const overallRaw = pick("overall_score");
      const overallScore = overallRaw === undefined || overallRaw === null || overallRaw === ""
        ? undefined
        : Number(overallRaw);
      attachments.push({
        kind: "evaluation",
        title: titleStr || "学习评估可视化",
        overallScore: Number.isFinite(overallScore) ? overallScore : undefined,
        dimensions: (pick("dimensions") && typeof pick("dimensions") === "object")
          ? pick("dimensions") as Record<string, unknown>
          : {},
        evidenceStatus: String(pick("evidence_status") || "insufficient"),
        visualizations,
      });
      if (downloadAttachment) attachments.push(downloadAttachment);
      continue;
    }

    if (typeStr.includes("code")) {
      const codeText = String(pick("code") || pick("content") || "").trim();
      if (codeText) {
        attachments.push({
          kind: "code",
          title: titleStr || "可运行代码示例",
          content: codeText,
          language: String(pick("language") || "python"),
          stdout: String(pick("stdout") || "").trim() || undefined,
        });
      }
      if (downloadAttachment) attachments.push(downloadAttachment);
      continue;
    }

    if (typeStr.includes("quiz")) {
      const raw = pick("quiz_data") ?? pick("questions") ?? pick("items");
      const items = Array.isArray(raw) ? (raw as any[]) : [];
      if (items.length) attachments.push({ kind: "quiz", title: titleStr || "分层练习", items });
      if (downloadAttachment) attachments.push(downloadAttachment);
      continue;
    }

    if (
      typeStr.includes("mermaid") || typeStr.includes("mindmap") ||
      typeStr.includes("mind") || typeStr.includes("diagram")
    ) {
      const dataUri = String(pick("data_uri") || "");
      const code = String(pick("mermaid_code") || pick("content") || "");
      const branchesSrc = pick("branches");
      const leavesSrc = pick("leaves");
      const branches = Array.isArray(branchesSrc) ? (branchesSrc as string[]) : [];
      const leaves = (leavesSrc && typeof leavesSrc === "object")
        ? (leavesSrc as Record<string, string[]>)
        : {};
      if (dataUri || code || branches.length) {
        attachments.push({
          kind: "mindmap",
          title: titleStr || "知识结构思维导图",
          content: code,
          dataUri: dataUri || undefined,
          branches,
          leaves,
        });
      }
      if (downloadAttachment) attachments.push(downloadAttachment);
      continue;
    }

    const normalizedMedia = normalizeResourceType(
      r.type,
      r.format,
      r.filepath,
      download?.type,
      download?.filename,
      meta.rendered ? "rendered-manim" : "",
    );
    if ((normalizedMedia === "audio" || normalizedMedia === "video") && download?.id) {
      const playbackStatus = String(pick("playback_status") || "ready");
      if (playbackStatus !== "unavailable") {
        attachments.push({
          kind: "media",
          mediaType: normalizedMedia,
          title: titleStr || (normalizedMedia === "audio" ? "语音导学" : "视频讲解"),
          src: artifactDownloadUrl(download.id, "generic"),
          status: playbackStatus,
          description: normalizedMedia === "audio"
            ? "语音导学已生成，可直接播放。"
            : "视频讲解已生成，可直接播放。",
        });
      }
    } else if (downloadAttachment) {
      attachments.push(downloadAttachment);
    }
  }
  return attachments;
}

function attachAndArchiveResources(
  messageId: string,
  resources: ResourceItem[],
  ownerKind: AvatarKind,
) {
  const target = messages.value.find((x) => x.id === messageId);
  const attachmentMode: ResourceAttachmentMode = ownerKind === "content"
    ? "download-only"
    : "inline";
  const inline = resourcesToAttachments(resources, attachmentMode);
  if (target && inline.length) {
    target.attachments = [...(target.attachments || []), ...inline];
  }
  if (target && ownerKind === "content") {
    target.content = resourceDeliveryExplanation(resources);
  }

  const authorName = getAvatar(ownerKind).nick;
  for (const r of resources) {
    const rawMeta = r.metadata && typeof r.metadata === "object" ? r.metadata : {};
    const resourceDownloads = Array.isArray(r.downloads)
      ? r.downloads
      : Array.isArray(rawMeta.downloads) ? rawMeta.downloads : [];
    const downloadId = resourceDownloads[0]?.id;
    const resourceType = normalizeResourceType(
      r.type,
      r.format,
      r.filepath,
      resourceDownloads[0]?.type,
      resourceDownloads[0]?.filename,
      r.metadata?.rendered ? "rendered-manim" : "",
    );
    addGeneratedResource({
      resourceId: downloadId,
      title: r.title,
      type: resourceType,
      format: resourceType === "video" && String(r.format || "").toLowerCase() === "manim"
        ? "MP4"
        : r.format || "",
      author: authorName,
      authorKind: ownerKind,
      meta: r.quiz_count ? `${r.quiz_count}题` : r.stages_count ? `${r.stages_count}阶段` : "",
      rawMetadata: r.metadata,
    });
  }
}

function startRealStream(assistantId: string, message: string) {
  // 提取 target_agent：
  // 1. 私聊时直接使用当前私聊 Agent 的 key
  // 2. 群聊时从消息中解析 @ 提及
  let targetAgent: string | undefined;
  if (isPrivateChat.value && currentPrivateAgent.value) {
    targetAgent = currentPrivateAgent.value.key;
  } else {
    // 只有“明确 @ 一位伙伴”才进入单 Agent 模式。多 @ 或无 @ 都交给
    // orchestrator 做团队编排，避免第一位被识别的 Agent 吞掉整轮任务。
    const mentioned = getMentionedAgentKinds(message);
    if (mentioned.length === 1) targetAgent = mentioned[0];
  }

  const agentMessageIds = new Map<string, string>();
  let receivedAgentResponses = false;

  abortController = streamChat(
    {
      message,
      session_id: chatSessionId.value,
      course: course.value,
      user_id: userId.value,
      target_agent: targetAgent,
      // 群聊房间：问答双方消息同步写入 course:student_id 房间，教师端可见
      room_id: isPrivateChat.value ? undefined : groupRoomId.value,
      sender_role: "student",
      sender_name: studentDisplayName.value,
    },
    {
      onMeta: (meta) => {
        if (meta?.realtime_state && typeof meta.realtime_state === "object") {
          realtimeState.value = meta.realtime_state as RealtimeState;
        }
        // 后端 agent 字段形如 "tutor_agent"，需要归一化为 AvatarKind
        const rawPrimary = meta?.agent || meta?.primary_agent || "";
        // 后端 agents_invoked 是 [{name: "tutor_agent", success: true, ...}] 字典列表
        const rawInvoked = meta?.agents_invoked || [];
        const nameList: string[] = Array.isArray(rawInvoked)
          ? rawInvoked.map((a: any) =>
              typeof a === "string" ? a : a?.name || a?.agent || ""
            )
          : [];
        if (rawPrimary) nameList.unshift(rawPrimary);

        const kinds = normalizeAgentNames(nameList);
        if (kinds.length) {
          activeAgentsInvoked.value = kinds;
          const primaryKind = kinds[0];
          activePrimaryAgent.value = getAvatar(primaryKind).nick;
          const m = messages.value.find((x) => x.id === assistantId);
          if (m) {
            m.agentKinds = kinds;
            m.primaryKind = primaryKind;
          }
        }
      },
      onThinking: (text) => updateStagesFromThinking(text),
      onChunk: (text) => {
        const m = messages.value.find((x) => x.id === assistantId);
        if (m) m.content += text;
      },
      onAgentStart: (payload) => {
        const taskId = String(payload?.task_id || payload?.agent || `task-${Date.now()}`);
        const normalized = normalizeAgentNames([
          String(payload?.agent || ""),
          String(payload?.agent_key || ""),
        ]);
        const kind = normalized[0] || "tutor";
        const messageId = receivedAgentResponses
          ? `${assistantId}-${taskId}`
          : assistantId;

        if (!receivedAgentResponses) {
          const first = messages.value.find((x) => x.id === assistantId);
          if (first) {
            first.content = "";
            first.agentKinds = [kind];
            first.primaryKind = kind;
            first.isStreaming = true;
            first.attachments = [];
          }
        } else {
          messages.value.push({
            id: messageId,
            role: "assistant",
            content: "",
            timestamp: Date.now(),
            isStreaming: true,
            agentKinds: [kind],
            primaryKind: kind,
            attachments: [],
          });
        }
        receivedAgentResponses = true;
        agentMessageIds.set(taskId, messageId);
      },
      onAgentChunk: (payload) => {
        const messageId = agentMessageIds.get(String(payload?.task_id || ""));
        const target = messages.value.find((x) => x.id === messageId);
        if (target) target.content += String(payload?.text || "");
      },
      onAgentResources: (payload) => {
        const taskId = String(payload?.task_id || "");
        const messageId = agentMessageIds.get(taskId);
        if (!messageId) return;
        const kinds = normalizeAgentNames([
          String(payload?.agent || ""),
          String(payload?.agent_key || ""),
        ]);
        attachAndArchiveResources(
          messageId,
          Array.isArray(payload?.resources) ? payload.resources : [],
          kinds[0] || "content",
        );
      },
      onAgentDone: (payload) => {
        const messageId = agentMessageIds.get(String(payload?.task_id || ""));
        const target = messages.value.find((x) => x.id === messageId);
        if (!target) return;
        target.isStreaming = false;
        if (!target.content.trim()) {
          target.content = payload?.success === false
            ? `本轮子任务暂未完成：${payload?.error || "生成超时，请稍后重试"}`
            : "本轮子任务已完成，但没有返回可展示的正文。";
        }
      },
      onResources: (resources: ResourceItem[]) => {
        // 团队模式的资源已通过 agent_resources 归属到各自气泡；全局 resources
        // 仅用于兼容单 Agent/旧后端，避免附件和文件重复出现。
        if (receivedAgentResponses) return;
        const m = messages.value.find((x) => x.id === assistantId);
        if (m) (m as any).resources = resources;
        const primaryKind = activeAgentsInvoked.value[0] || "tutor";
        attachAndArchiveResources(assistantId, resources, primaryKind as AvatarKind);
      },
      onProfileUpdate: (profile) => {
        if (profile && typeof profile === "object") {
          profileSnapshot.value = { ...profileSnapshot.value, ...profile };
          const rawCompleteness = Number((profile as any).completeness ?? profileCompleteness.value);
          profileCompleteness.value = rawCompleteness > 1 ? Math.round(rawCompleteness) : Math.round(rawCompleteness * 100);
        }
        void loadProfilePanel();
      },
      onProfileStatus: (status) => {
        if (status?.dimensions_count !== undefined && profileCompleteness.value < 20) {
          profileCompleteness.value = Math.min(100, Math.max(10, status.dimensions_count * 12));
        }
      },
      onDone: (fullText) => {
        const m = messages.value.find((x) => x.id === assistantId);
        if (m) {
          m.isStreaming = false;
          // 兜底：如果流式结束但内容为空，显示提示
          if (!receivedAgentResponses && !m.content && !fullText) {
            m.content = "（Agent 未返回内容，可能后端 LLM 未配置或超时，请检查后端日志）";
            m.agentKinds = ["safety"];
            m.primaryKind = "safety";
          }
        }
        for (const messageId of agentMessageIds.values()) {
          const agentMessage = messages.value.find((x) => x.id === messageId);
          if (agentMessage) agentMessage.isStreaming = false;
        }
        // 确保所有阶段标记为完成
        activeStages.value = activeStages.value.map((s) => ({ ...s, status: "done" as const }));
        streaming.value = false;
        abortController = null;
        void loadRealtimeState();
        void Promise.allSettled([loadArtifactsPanel(), loadKnowledgePanel(), loadProfilePanel()]);
      },
      onError: (err) => {
        // err 可能是字符串或对象 {code, detail}
        const errStr = typeof err === "object"
          ? (err as any)?.detail || (err as any)?.message || JSON.stringify(err)
          : String(err);
        error.value = errStr;
        streaming.value = false;
        const m = messages.value.find((x) => x.id === assistantId);
        if (m) {
          m.isStreaming = false;
          if (!m.content) {
            m.content = `⚠ 后端响应失败：${errStr}`;
          } else {
            m.content += `\n\n[错误] ${errStr}`;
          }
          m.agentKinds = ["safety"];
          m.primaryKind = "safety";
        }
        for (const messageId of agentMessageIds.values()) {
          const agentMessage = messages.value.find((x) => x.id === messageId);
          if (agentMessage) agentMessage.isStreaming = false;
        }
        abortController = null;
      },
    },
  );
}

// 匹配后端 pipeline.py 中 _STAGE_PROMPTS 的中文 thinking 文本
const STAGE_KEYWORDS: Record<string, string[]> = {
  input_validation: ["会话", "准备会话", "会话就绪"],
  rag_retrieval: ["检索知识库", "知识检索", "知识库"],
  realtime_state: ["学习状态", "分析你的"],
  orchestration: ["Agent", "协作", "编排"],
  debate_reflection: ["辩论", "反思"],
  aggregation: ["安全审核", "安全", "审核"],
  persist: ["保存", "记录"],
};

// 后端 7 阶段中文标签（与 pipeline.py _STAGE_PROMPTS 对应）
const STAGE_LABELS: string[] = [
  "会话准备",
  "知识检索",
  "状态分析",
  "Agent 协作",
  "辩论反思",
  "安全审核",
  "记录保存",
];

function updateStagesFromThinking(text: string) {
  if (!text) return;
  // 初始化阶段列表
  if (!activeStages.value.length) {
    activeStages.value = STAGE_LABELS.map((s) => ({ stage: s, status: "pending" as const }));
  }

  const lower = text.toLowerCase();
  let runningIdx = -1;
  Object.entries(STAGE_KEYWORDS).forEach(([en, keywords], idx) => {
    for (const kw of keywords) {
      if (lower.includes(en) || text.includes(kw)) {
        runningIdx = idx;
        break;
      }
    }
  });

  if (runningIdx === -1) return;

  activeStages.value = activeStages.value.map((s, idx) => {
    if (idx < runningIdx) return { ...s, status: "done" };
    if (idx === runningIdx) return { ...s, status: "running" };
    return s;
  });
}

function handleStop() {
  if (abortController) {
    abortController.abort();
    abortController = null;
    streaming.value = false;
    const last = messages.value[messages.value.length - 1];
    if (last?.role === "assistant") last.isStreaming = false;
  }
}

async function handleClear() {
  if (!confirm("清空当前会话历史？此操作不可撤销。")) return;
  if (isDemo.value) {
    messages.value = [buildCurrentWelcomeMessage()];
    return;
  }
  try {
    await clearSession(chatSessionId.value);
    messages.value = [buildCurrentWelcomeMessage()];
    resetChatSession();
  } catch (e: any) {
    error.value = e?.message || "清空失败";
  }
}

function handleNewSession() {
  messages.value = [buildCurrentWelcomeMessage()];
  resetChatSession();
  router.replace({ path: route.path, query: { ...route.query, _t: Date.now() } });
}

function handleExit() {
  router.push("/home");
}

function toggleRightPanel() {
  rightPanelVisible.value = !rightPanelVisible.value;
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  }
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}
</script>

<template>
  <div class="chat-view">
    <!-- ===== 顶部栏 ===== -->
    <header class="chat-header">
      <div class="header-left">
        <button class="icon-btn" type="button" title="返回主界面" @click="handleExit">
          <ArrowLeft :size="20" />
        </button>
        <div class="room-info">
          <span class="room-icon">
            <User v-if="isPrivateChat" :size="18" />
            <Hash v-else :size="18" />
          </span>
          <div class="room-text">
            <h2>{{ isPrivateChat ? currentSession?.name : (isDemo ? "Chat Demo" : "AI 学习助手群聊") }}</h2>
            <p class="room-sub">
              <template v-if="isPrivateChat">
                <span class="private-indicator">私聊</span>
                {{ currentPrivateAgent?.title }} · {{ currentPrivateAgent?.role }}
              </template>
              <template v-else>
                <Users :size="11" /> {{ groupMembers.length }} 位成员 · {{ onlineCount }} 人在线
              </template>
              <!-- 个性化标识：让学生看到「Agent 回答基于我的画像」 -->
              <span
                v-if="profileCompleteness > 0"
                class="chat-personalized-pill"
                :title="`Agent 回答基于你的画像（完整度 ${profileCompleteness}%）个性化调整`"
              >✨ 已按画像个性化 · {{ profileCompleteness }}%</span>
            </p>
          </div>
        </div>
      </div>

      <div class="header-right">
        <!-- 会话切换下拉 -->
        <div class="session-dropdown">
          <button class="session-btn" @click="showSessionMenu = !showSessionMenu">
            <MessageSquare :size="16" />
            <span>{{ currentSession?.name || '选择会话' }}</span>
            <ChevronDown :size="14" />
          </button>
          <div v-if="showSessionMenu" class="session-menu">
            <div class="session-menu-header">
              <span>会话列表</span>
              <button class="new-chat-btn" @click="showAgentSelector = true; showSessionMenu = false">
                <Plus :size="14" /> 新建私聊
              </button>
            </div>
            <div class="session-menu-list">
              <div
                v-for="session in sessions"
                :key="session.id"
                class="session-menu-item"
                :class="{ active: session.id === currentSessionId, pinned: session.isPinned }"
                @click="switchSession(session); showSessionMenu = false"
              >
                <Hash v-if="session.type === 'group'" :size="14" />
                <User v-else :size="14" />
                <span class="session-name">{{ session.name }}</span>
                <span v-if="session.isFavorite" class="favorite-icon">★</span>
                <button
                  v-if="session.type === 'private'"
                  class="session-delete-btn"
                  @click.stop="deleteSession(session.id)"
                  title="删除会话"
                >
                  <X :size="12" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <button class="text-btn" type="button" @click="loadHistory">
          <RefreshCcw :size="15" />刷新
        </button>

        <!-- 新建按钮下拉 -->
        <div class="new-dropdown">
          <button class="text-btn" @click="showNewMenu = !showNewMenu">
            <Sparkles :size="15" />新建
          </button>
          <div v-if="showNewMenu" class="new-menu">
            <div class="new-menu-item" @click="handleNewSession(); showNewMenu = false">
              <MessageSquare :size="14" /> 新会话
            </div>
            <div class="new-menu-item" @click="showAgentSelector = true; showNewMenu = false">
              <User :size="14" /> 新建私聊
            </div>
            <div class="new-menu-divider"></div>
            <div class="new-menu-item" @click="activeTab = 'settings'; rightPanelVisible = true; showNewMenu = false">
              <PanelRightOpen :size="14" /> 设置
            </div>
          </div>
        </div>

        <!-- 通知按钮 -->
        <button
          class="icon-btn"
          :class="{ active: notificationEnabled }"
          :title="notificationEnabled ? '通知已开启' : '通知已关闭'"
          @click="toggleNotification"
        >
          <Bell v-if="notificationEnabled" :size="17" />
          <BellOff v-else :size="17" />
        </button>

        <button
          class="icon-btn"
          type="button"
          :class="{ active: rightPanelVisible }"
          title="群资料面板"
          @click="toggleRightPanel"
        >
          <PanelRightOpen v-if="!rightPanelVisible" :size="17" />
          <PanelRightClose v-else :size="17" />
        </button>

        <button class="text-btn danger" type="button" @click="handleClear">
          <Trash2 :size="15" />清空
        </button>

        <button class="exit-btn" type="button" @click="handleExit">
          <ArrowLeft :size="15" />返回主界面
        </button>
      </div>
    </header>

    <!-- ===== 主体三栏 ===== -->
    <div class="chat-body">
      <!-- ===== 左栏：群成员 ===== -->
      <aside class="member-sidebar">
        <div class="member-search-wrap">
          <Search :size="14" />
          <input
            v-model="memberSearch"
            class="member-search-input"
            placeholder="搜索群成员..."
          />
          <button v-if="memberSearch" class="clear-search" @click="memberSearch = ''">
            <X :size="13" />
          </button>
        </div>

        <div class="member-count-bar">
          <span>群成员</span>
          <em>{{ filteredMembers.length }} / {{ groupMembers.length }}</em>
        </div>

        <div class="member-list">
          <div
            v-for="m in filteredMembers"
            :key="m.key"
            class="member-item"
            :class="{ student: m.isStudent }"
            @click="!m.isStudent && createPrivateSession(m.key)"
            :style="!m.isStudent ? { cursor: 'pointer' } : {}"
          >
            <div class="member-avatar-wrap">
              <img v-if="m.avatar" :src="m.avatar" :alt="m.name" class="member-avatar-img" />
              <span
                v-else
                class="member-avatar-fallback"
                :class="{ teacher: m.isTeacher, learner: m.isStudent && !m.isTeacher }"
              >{{ m.isTeacher ? "师" : m.isStudent ? "我" : m.name.slice(0, 1) }}</span>
              <span class="member-status-dot" :class="m.isOnline ? 'online' : 'busy'" />
            </div>
            <div class="member-info">
              <div class="member-name-row">
                <b>{{ m.name }}</b>
                <span v-if="m.isStudent" class="member-tag">我</span>
                <span v-else class="chat-hint">点击对话</span>
              </div>
              <small>{{ m.title }}</small>
              <em class="member-state">{{ m.state }}</em>
            </div>
          </div>
        </div>
      </aside>

      <!-- ===== 中栏：聊天区 ===== -->
      <div class="chat-main">
        <p v-if="error" class="chat-error">⚠ {{ error }}</p>
        <section class="task-context-card" aria-label="当前任务上下文">
          <div class="task-context-icon">
            <Target :size="20" />
          </div>
          <div class="task-context-block task-context-main">
            <span>当前任务</span>
            <b>{{ currentTaskTitle }}</b>
          </div>
          <div class="task-context-block">
            <span>执行状态</span>
            <em :class="{ running: streaming }">{{ currentTaskStatus }}</em>
          </div>
          <div class="task-context-progress">
            <span>任务进度</span>
            <div class="task-context-bar">
              <i :style="{ transform: `scaleX(${taskProgress / 100})` }" />
            </div>
            <strong>{{ taskProgress }}%</strong>
          </div>
          <div class="task-context-block task-context-agent">
            <span>当前 Agent</span>
            <b>{{ currentAgentLabel }}</b>
          </div>
        </section>
        <ChatMessageList
          :messages="messages"
          :loading-history="loadingHistory"
          :suggestions-disabled="streaming"
          @avatar-click="createPrivateSession"
          @suggestion-click="handleSuggestedAction"
        />
        <div v-if="!isPrivateChat" class="quick-action-row" aria-label="学习快捷动作">
          <button
            v-for="command in quickCommands"
            :key="command.label"
            type="button"
            :disabled="streaming"
            :title="command.prompt"
            @click="handleQuickCommand(command)"
          >
            <component :is="command.icon" :size="14" />
            <span>{{ command.label }}</span>
          </button>
        </div>
        <ChatInput
          :disabled="streaming"
          :streaming="streaming"
          :prefill="prefillText"
          :placeholder="isPrivateChat
            ? `与 ${currentSession?.name} 私聊中，专注${currentPrivateAgent?.role?.split(' · ')[0] || '咨询'}...`
            : '在群聊中发送消息，6 个 Agent 会协作回答...'"
          @send="handleSend"
          @stop="handleStop"
        />
      </div>

      <!-- ===== 右栏：群资料面板（标签页） ===== -->
      <transition name="panel-slide">
        <aside v-if="rightPanelVisible" class="right-panel">
          <!-- 标签头 -->
          <div class="tab-bar">
            <button
              v-for="tab in rightTabs"
              :key="tab.key"
              type="button"
              class="tab-btn"
              :class="{ active: activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <component :is="tab.icon" :size="15" />
              <span>{{ tab.label }}</span>
              <em v-if="tab.count" class="tab-count">{{ tab.count }}</em>
            </button>
          </div>

          <!-- 标签内容 -->
          <div class="tab-content">
            <!-- 群概览 -->
            <div v-if="activeTab === 'overview'" class="tab-pane">
              <div class="pane-section-head">
                <Megaphone :size="16" />
                <span>群概览</span>
              </div>
              <div class="announcement-card">
                <p>{{ groupAnnouncement }}</p>
              </div>
              <div class="overview-grid">
                <div class="overview-card">
                  <b>{{ taskProgress }}%</b>
                  <small>任务进度</small>
                </div>
                <div class="overview-card">
                  <b>{{ generatedResources.length }}</b>
                  <small>生成资料</small>
                </div>
                <div class="overview-card">
                  <b>{{ knowledgePointRows.length }}</b>
                  <small>知识点</small>
                </div>
                <div class="overview-card">
                  <b>{{ profileCompleteness }}%</b>
                  <small>画像完整度</small>
                </div>
              </div>
              <div class="group-info-card">
                <div class="info-row"><span>群名称</span><b>AI 学习助手群聊</b></div>
                <div class="info-row"><span>成员数</span><b>{{ groupMembers.length }} 人</b></div>
                <div class="info-row"><span>在线数</span><b>{{ onlineCount }} 人</b></div>
                <div class="info-row"><span>课程</span><b>{{ course }}</b></div>
                <div class="info-row"><span>Session</span><code>{{ chatSessionId.slice(0, 16) }}...</code></div>
              </div>
            </div>

            <!-- 实时学情仪表盘 -->
            <div v-else-if="activeTab === 'realtime'" class="tab-pane">
              <div class="pane-section-head">
                <Brain :size="16" />
                <span>实时学情仪表盘</span>
                <button
                  type="button"
                  class="pane-refresh-btn"
                  @click="loadRealtimeState"
                  :disabled="realtimeLoading"
                >
                  <RefreshCcw :size="13" :class="{ spin: realtimeLoading }" />
                </button>
              </div>

              <div v-if="!realtimeState && !realtimeLoading" class="realtime-empty">
                <Brain :size="28" />
                <p>暂无实时学情数据</p>
                <small>开始对话后，团团会实时分析你的学习状态</small>
              </div>

              <div v-else-if="realtimeState" class="realtime-dashboard">
                <div class="realtime-identity-card">
                  <div class="realtime-identity-main">
                    <img
                      v-if="learnerPartner.avatar"
                      :src="learnerPartner.avatar"
                      :alt="realtimeLearnerName"
                      class="realtime-learner-avatar"
                    />
                    <div v-else class="realtime-learner-avatar-fallback">我</div>
                    <div>
                      <strong>{{ realtimeLearnerName }}的实时学情</strong>
                      <small>只分析当前会话，不会混入其他同学的数据</small>
                    </div>
                  </div>
                  <div class="realtime-session-badge">
                    <span>当前会话</span>
                    <code>{{ (realtimeState.session_id || chatSessionId).slice(0, 12) }}…</code>
                  </div>
                </div>

                <div class="realtime-profile-link-card">
                  <div class="realtime-card-title">
                    <UserRound :size="14" />
                    <span>这份学情如何关联你的画像</span>
                    <em>{{ profileCompleteness }}% 画像完整度</em>
                  </div>
                  <div v-if="realtimeProfileBasis.length" class="realtime-profile-basis">
                    <span v-for="item in realtimeProfileBasis" :key="item.label" class="realtime-profile-chip">
                      <b>{{ item.label }}</b>{{ item.value }}
                    </span>
                  </div>
                  <p v-else class="realtime-card-note">当前还没有足够的画像字段；继续对话后，系统会把目标、薄弱点和偏好写入这里。</p>
                  <div v-if="realtimeEvidence.length" class="realtime-evidence">
                    <span class="realtime-evidence-label">本轮对话识别到</span>
                    <ul>
                      <li v-for="item in realtimeEvidence" :key="item">{{ item }}</li>
                    </ul>
                  </div>
                  <div v-else class="realtime-evidence realtime-evidence-muted">
                    <span class="realtime-evidence-label">本轮对话证据</span>
                    <p>暂未返回可引用证据；上面的依据来自已保存画像，继续对话后会补充。</p>
                  </div>
                </div>

                <!-- 状态摘要 -->
                <div class="realtime-summary-card">
                  <div class="realtime-summary-head">
                    <span class="realtime-emotion-tag">{{ realtimeState.emotion || "—" }}</span>
                    <span class="realtime-engagement-tag">{{ realtimeState.engagement || "—" }}</span>
                  </div>
                  <p class="realtime-summary-text">{{ realtimeState.summary }}</p>
                </div>

                <!-- 3 维指标 -->
                <div class="realtime-metrics">
                  <div class="realtime-metric">
                    <div class="realtime-metric-head">
                      <small>困惑度</small>
                      <span :style="{ color: realtimeLevelColor(realtimeState.confusion) }">
                        {{ realtimeLevelLabel(realtimeState.confusion) }}
                      </span>
                    </div>
                    <div class="realtime-metric-bar">
                      <div
                        class="realtime-metric-fill"
                        :style="{
                          transform: `scaleX(${realtimeState.confusion})`,
                          background: realtimeLevelColor(realtimeState.confusion),
                        }"
                      ></div>
                    </div>
                  </div>

                  <div class="realtime-metric">
                    <div class="realtime-metric-head">
                      <small>疲劳度</small>
                      <span :style="{ color: realtimeLevelColor(realtimeState.fatigue) }">
                        {{ realtimeLevelLabel(realtimeState.fatigue) }}
                      </span>
                    </div>
                    <div class="realtime-metric-bar">
                      <div
                        class="realtime-metric-fill"
                        :style="{
                          transform: `scaleX(${realtimeState.fatigue})`,
                          background: realtimeLevelColor(realtimeState.fatigue),
                        }"
                      ></div>
                    </div>
                  </div>

                  <div class="realtime-metric">
                    <div class="realtime-metric-head">
                      <small>认知负荷</small>
                      <span :style="{ color: realtimeLevelColor(realtimeState.cognitive_load) }">
                        {{ realtimeLevelLabel(realtimeState.cognitive_load) }}
                      </span>
                    </div>
                    <div class="realtime-metric-bar">
                      <div
                        class="realtime-metric-fill"
                        :style="{
                          transform: `scaleX(${realtimeState.cognitive_load})`,
                          background: realtimeLevelColor(realtimeState.cognitive_load),
                        }"
                      ></div>
                    </div>
                  </div>

                  <div v-if="realtimeState.confidence !== undefined" class="realtime-metric">
                    <div class="realtime-metric-head">
                      <small>学习信心</small>
                      <span :style="{ color: realtimeLevelColor(realtimeState.confidence) }">
                        {{ realtimeLevelLabel(realtimeState.confidence) }}
                      </span>
                    </div>
                    <div class="realtime-metric-bar">
                      <div class="realtime-metric-fill" :style="{ transform: `scaleX(${realtimeState.confidence})`, background: realtimeLevelColor(realtimeState.confidence) }"></div>
                    </div>
                  </div>

                  <div v-if="realtimeState.curiosity !== undefined" class="realtime-metric">
                    <div class="realtime-metric-head">
                      <small>探索意愿</small>
                      <span :style="{ color: realtimeLevelColor(realtimeState.curiosity) }">
                        {{ realtimeLevelLabel(realtimeState.curiosity) }}
                      </span>
                    </div>
                    <div class="realtime-metric-bar">
                      <div class="realtime-metric-fill" :style="{ transform: `scaleX(${realtimeState.curiosity})`, background: realtimeLevelColor(realtimeState.curiosity) }"></div>
                    </div>
                  </div>
                </div>

                <!-- 卡住的知识点 -->
                <div v-if="realtimeState.stuck_topics?.length" class="realtime-topics-card">
                  <div class="realtime-topics-head">
                    <Target :size="14" />
                    <span>卡住的知识点</span>
                  </div>
                  <div class="realtime-topic-tags">
                    <span v-for="t in realtimeState.stuck_topics" :key="t" class="realtime-topic-tag stuck">{{ t }}</span>
                  </div>
                </div>

                <!-- 好奇的知识点 -->
                <div v-if="realtimeState.curiosity_topics?.length" class="realtime-topics-card">
                  <div class="realtime-topics-head">
                    <Sparkles :size="14" />
                    <span>感兴趣的知识点</span>
                  </div>
                  <div class="realtime-topic-tags">
                    <span v-for="t in realtimeState.curiosity_topics" :key="t" class="realtime-topic-tag curious">{{ t }}</span>
                  </div>
                </div>

                <!-- 下一步建议 -->
                <div v-if="realtimeState.next_best_action" class="realtime-action-card">
                  <div class="realtime-action-head">
                    <Sparkles :size="14" />
                    <span>AI 建议</span>
                  </div>
                  <p>{{ realtimeState.next_best_action }}</p>
                </div>
              </div>
            </div>

            <!-- 任务流 -->
            <div v-else-if="activeTab === 'tasks'" class="tab-pane">
              <div class="pane-section-head">
                <ListChecks :size="16" />
                <span>任务流</span>
                <em class="pane-count">{{ activeTaskCount }} / {{ taskRows.length }}</em>
              </div>
              <div class="task-progress-card">
                <div class="task-progress-head">
                  <b>{{ streaming ? "多 Agent 协作中" : activeTaskCount ? "任务已完成" : "等待学习任务" }}</b>
                  <small>{{ taskProgress }}%</small>
                </div>
                <div class="task-progress-bar"><span :style="{ transform: `scaleX(${taskProgress / 100})` }" /></div>
              </div>
              <div v-if="taskRows.length" class="task-flow-list">
                <div
                  v-for="task in taskRows"
                  :key="task.key"
                  class="task-flow-item"
                  :class="{
                    running: task.status === '进行中',
                    done: task.status === '已完成',
                    queue: task.status === '排队中',
                  }"
                  :style="{ '--task-accent': task.accent }"
                >
                  <span class="task-dot" />
                  <div>
                    <b>{{ task.role }}</b>
                    <small>{{ task.name }} · {{ task.title }}</small>
                  </div>
                  <em>{{ task.status }}</em>
                </div>
              </div>
              <div v-else class="empty-pane">
                <ListChecks :size="32" />
                <p>暂无执行中的任务流</p>
                <small>发送学习任务后，后端返回的 Agent 执行状态会在这里展示。</small>
              </div>
            </div>

            <!-- 文件 -->
            <div v-else-if="activeTab === 'files'" class="tab-pane">
              <div class="pane-section-head">
                <FileText :size="16" />
                <span>相关资源</span>
                <em class="pane-count">{{ fileResources.length }} 个</em>
                <button class="quick-gen-toggle" type="button" @click="toggleQuickGen">
                  <Sparkles :size="13" />
                  一键生成
                </button>
              </div>

              <!-- 一键生成面板 -->
              <div v-if="showQuickGen" class="quick-gen-panel">
                <div class="qg-input-row">
                  <input
                    v-model="quickGenTopic"
                    class="qg-input"
                    type="text"
                    placeholder="输入主题，如：反向传播、K-Means…"
                    :disabled="quickGenRunning"
                    @keyup.enter="runQuickGenerate"
                  />
                  <button
                    class="qg-btn"
                    type="button"
                    :disabled="quickGenRunning"
                    @click="runQuickGenerate"
                  >
                    <Loader2 v-if="quickGenRunning" :size="13" class="spin" />
                    <Sparkles v-else :size="13" />
                    {{ quickGenRunning ? '生成中' : '生成' }}
                  </button>
                </div>
                <p v-if="quickGenProgress" class="qg-progress" :class="{ done: !quickGenRunning }">
                  {{ quickGenProgress }}
                </p>
                <p v-else class="qg-hint">将并行生成 PPT、思维导图、代码、音频和讲解视频，生成后自动归档到上方文件列表。</p>
              </div>
              <p v-if="resourcesLoading" class="mini-loading"><Loader2 :size="13" class="spin" /> 正在同步资源...</p>

              <div class="related-resource-panel">
                <div class="related-resource-head">
                  <div>
                    <b>相关资源</b>
                    <small>后端返回的文件、PPT、Word、PDF 会在这里显示。</small>
                  </div>
                  <button type="button" @click="router.push('/resources')">全部 ›</button>
                </div>
                <div v-if="fileResources.length" class="related-resource-list">
                  <div
                    v-for="r in fileResources"
                    :key="r.id"
                    class="related-resource-item"
                    :class="resourceZoneKey(r)"
                  >
                    <span class="resource-file-badge">
                      {{ resourceIconMap[resourceZoneKey(r)] || resourceIconMap[r.type] || "FILE" }}
                    </span>
                    <div class="related-resource-body">
                      <b>{{ r.title }}</b>
                      <small>
                        {{ r.format || r.type }}{{ r.meta ? ` · ${r.meta}` : "" }} · {{ formatTime(r.createdAt) }}
                      </small>
                      <!-- 音频类型：内联播放器 -->
                      <audio
                        v-if="r.type === 'audio' && r.resourceId"
                        :src="artifactDownloadUrl(r.resourceId, 'generic')"
                        controls
                        preload="none"
                        class="resource-audio-player"
                      />
                      <!-- 视频类型：内联播放器 -->
                      <video
                        v-if="r.type === 'video' && r.resourceId"
                        :src="artifactDownloadUrl(r.resourceId, 'generic')"
                        controls
                        preload="metadata"
                        class="resource-video-player"
                      />
                    </div>
                    <div class="related-resource-actions">
                      <!-- 预览已下沉到消息气泡里；右侧只保留下载和跳转 -->
                      <button type="button" title="下载" @click="downloadResource(r)">
                        <Download :size="13" />
                      </button>
                      <button type="button" title="查看" @click="openResource(r)">
                        <ExternalLink :size="13" />
                      </button>
                    </div>
                  </div>
                </div>
                <div v-else class="related-resource-empty">
                  <FileText :size="30" />
                  <p>暂无相关资源</p>
                  <small>Agent 生成或后端同步文件后，会按真实返回内容显示在这里。</small>
                </div>
              </div>
            </div>

            <!-- 知识库 -->
            <div v-else-if="activeTab === 'knowledge'" class="tab-pane">
              <div class="pane-section-head">
                <Library :size="16" />
                <span>知识库 / 知识点</span>
                <em class="pane-count">{{ knowledgePointRows.length }} 个</em>
              </div>
              <p v-if="knowledgeLoading" class="mini-loading"><Loader2 :size="13" class="spin" /> 正在读取知识库...</p>
              <p v-else-if="knowledgeError" class="pane-hint">{{ knowledgeError }}</p>
              <div v-if="knowledgePointRows.length" class="knowledge-list">
                <button
                  v-for="kp in knowledgePointRows"
                  :key="String(kp.kp_id || kp.id || kp.name)"
                  type="button"
                  class="knowledge-card"
                  @click="router.push({ path: '/graph', query: { kp: String(kp.kp_id || kp.id || kp.name || '') } })"
                >
                  <BookOpen :size="17" />
                  <span>
                    <b>{{ kp.name || kp.label || kp.kp_id || kp.id }}</b>
                    <small>{{ kp.description || kp.bloom_level || kp.course || "知识点已接入课程图谱" }}</small>
                  </span>
                </button>
              </div>
              <div v-else class="empty-pane">
                <Library :size="32" />
                <p>暂无知识库数据</p>
                <small>知识点列表会在后端返回数据后自动展示。</small>
              </div>
            </div>

            <!-- 学习画像 -->
            <div v-else-if="activeTab === 'profile'" class="tab-pane">
              <div class="pane-section-head">
                <UserRound :size="16" />
                <span>学习画像</span>
                <em class="pane-count">{{ profileCompleteness }}%</em>
              </div>
              <p v-if="profileLoading" class="mini-loading"><Loader2 :size="13" class="spin" /> 正在同步画像...</p>
              <p v-else-if="profileError" class="pane-hint">{{ profileError }}</p>
              <div class="profile-meter-card">
                <div class="profile-ring" :style="{ '--value': `${profileCompleteness}%` }">
                  <strong>{{ profileCompleteness }}%</strong>
                </div>
                <div>
                  <b>对话式画像随学随新</b>
                  <small>群聊提到目标、薄弱点、偏好后会自动更新。</small>
                </div>
              </div>
              <div class="profile-dimension-list">
                <div v-for="row in profileRows" :key="row.key" class="profile-dimension-card">
                  <CheckCircle2 :size="15" />
                  <span>
                    <b>{{ row.label }}</b>
                    <small>{{ row.text }}</small>
                    <em v-if="row.evidence" :class="['profile-evidence', { pending: row.evidence === '待补充' }]">
                      证据：{{ row.evidence }}
                    </em>
                  </span>
                </div>
              </div>
              <div v-if="!profileRows.length" class="empty-pane">
                <UserRound :size="32" />
                <p>暂无画像维度</p>
                <small>学习画像会在后端返回数据后自动展示。</small>
              </div>
              <button type="button" class="wide-link-btn" @click="router.push('/profile')">
                <Target :size="14" /> 查看完整画像
              </button>
            </div>

            <!-- Agent 协作链路 -->
            <div v-else-if="activeTab === 'trace'" class="tab-pane">
              <ChatAgentTrace
                :stages="activeStages"
                :agents-invoked="activeAgentsInvoked"
                :primary-agent="activePrimaryAgent"
                :quality="activeQuality"
                :safety="activeSafety"
                :expanded="traceExpanded"
                @toggle="traceExpanded = !traceExpanded"
              />
              <div class="status-mini">
                <div class="status-row">
                  <span>消息数</span>
                  <b>{{ messages.length }}</b>
                </div>
                <div class="status-row">
                  <span>状态</span>
                  <b :class="streaming ? 'streaming' : 'idle'">
                    <Loader2 v-if="streaming" :size="11" class="spin" />
                    {{ streaming ? "生成中" : "空闲" }}
                  </b>
                </div>
                <div class="status-row">
                  <span>资源数</span>
                  <b>{{ generatedResources.length }}</b>
                </div>
              </div>
            </div>

            <!-- 成员列表 -->
            <div v-else-if="activeTab === 'members'" class="tab-pane">
              <div class="pane-section-head">
                <Users :size="16" />
                <span>群成员</span>
                <em class="pane-count">{{ groupMembers.length }}</em>
              </div>
              <MemberList :members="groupMembers" @private-chat="createPrivateSession" />
            </div>

            <!-- 设置 -->
            <div v-else-if="activeTab === 'settings'" class="tab-pane">
              <div class="pane-section-head">
                <PanelRightOpen :size="16" />
                <span>聊天设置</span>
              </div>
              <div class="settings-list">
                <div class="setting-item">
                  <span>消息通知</span>
                  <label class="toggle">
                    <input type="checkbox" checked />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="setting-item">
                  <span>声音提示</span>
                  <label class="toggle">
                    <input type="checkbox" />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="setting-item">
                  <span>显示成员列表</span>
                  <label class="toggle">
                    <input type="checkbox" checked />
                    <span class="toggle-slider"></span>
                  </label>
                </div>
                <div class="setting-divider"></div>
                <button class="setting-btn" @click="handleClear">
                  <Trash2 :size="14" /> 清空聊天记录
                </button>
                <button class="setting-btn" @click="handleNewSession">
                  <Sparkles :size="14" /> 新建会话
                </button>
              </div>
            </div>
          </div>
        </aside>
      </transition>
    </div>

    <!-- Agent选择器弹窗 -->
    <div v-if="showAgentSelector" class="agent-selector-modal" @click.self="showAgentSelector = false">
      <div class="agent-selector-content">
        <div class="selector-header">
          <h4>选择AI伙伴开始私聊</h4>
          <button class="close-btn" @click="showAgentSelector = false">
            <X :size="18" />
          </button>
        </div>
        <div class="agent-list">
          <div
            v-for="partner in partners"
            :key="partner.key"
            class="agent-item"
            @click="createPrivateSession(partner.key); showAgentSelector = false"
          >
            <img :src="partner.avatar" :alt="partner.name" class="agent-avatar" />
            <div class="agent-info">
              <span class="agent-name">{{ partner.name }}</span>
              <span class="agent-title">{{ partner.title }}</span>
              <span class="agent-role">{{ partner.role }}</span>
            </div>
            <div class="agent-status" :class="{ online: partner.state === '在线' }">
              {{ partner.state }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chat-view {
  width: 100vw;
  height: 100vh;
  min-height: 600px;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  color: #1f2937;
  overflow: hidden;
}

/* ===== 顶部栏 ===== */
.chat-header {
  flex: none;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  z-index: 20;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: auto;
}

.room-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.room-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  color: #6b7280;
  background: #f3f4f6;
  flex-shrink: 0;
}

.room-text h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.3;
}

.room-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: #9ca3af;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.chat-personalized-pill {
  padding: 1px 8px;
  border-radius: 999px;
  background: linear-gradient(90deg, #fff2e0, #ffe6d0);
  color: #b45309;
  border: 1px solid #fbd8b3;
  font-weight: 700;
  font-size: 10.5px;
  cursor: help;
}

/* 按钮 */
.icon-btn {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: #f3f4f6;
    border-color: #d1d5db;
  }

  &.active {
    background: #fef3e8;
    border-color: #ea5a1a;
    color: #ea5a1a;
  }
}

.text-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #374151;
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;

  &:hover { background: #f3f4f6; border-color: #d1d5db; }

  &.danger {
    color: #dc2626;
    border-color: rgba(220, 38, 38, 0.25);
    &:hover { background: #fef2f2; }
  }
}

/* ===== 顶栏会话下拉 ===== */
.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.session-dropdown {
  position: relative;
}

.session-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #1f2937;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #f9fafb;
    border-color: #d1d5db;
  }
}

.session-menu {
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  margin-top: 8px;
  width: 240px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  z-index: 100;
  overflow: hidden;
}

.session-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  border: none;
  background: #fff7ed;
  color: #ea580c;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #fed7aa;
  }
}

.session-menu-list {
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
}

.session-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 13px;
  color: #374151;

  &:hover {
    background: #f9fafb;
  }

  &.active {
    background: #fff7ed;
    color: #ea580c;
  }

  &.pinned {
    font-weight: 500;
  }
}

.session-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unread-dot {
  width: 8px;
  height: 8px;
  background: #ea580c;
  border-radius: 50%;
}

.exit-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: 0;
  background: linear-gradient(135deg, #ea5a1a, #d14710);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;

  &:hover {
    box-shadow: 0 4px 12px rgba(234, 90, 26, 0.3);
    transform: translateY(-1px);
  }
}

/* ===== 主体三栏 ===== */
.chat-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* ===== 左栏：群成员 ===== */
.member-sidebar {
  flex: none;
  width: 220px;
  background: #fff;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.member-search-wrap {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  color: #9ca3af;
}

.member-search-input {
  flex: 1;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  height: 32px;
  padding: 0 10px;
  font-size: 12.5px;
  color: #374151;
  background: #f9fafb;
  outline: none;

  &:focus {
    border-color: #ea5a1a;
    background: #fff;
    box-shadow: 0 0 0 3px rgba(234, 90, 26, 0.08);
  }
}

.clear-search {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 0;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  border-radius: 4px;

  &:hover { background: #f3f4f6; color: #6b7280; }
}

.member-count-bar {
  flex: none;
  display: flex;
  align-items: center;
  padding: 0 14px 8px;
  font-size: 11px;
  color: #9ca3af;
  border-bottom: 1px solid #f0f0f0;

  em {
    margin-left: auto;
    font-style: normal;
    font-weight: 500;
  }
}

.member-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 8px 16px;
}

.member-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.12s ease;

  &:hover { background: #f3f4f6; }

  &.student {
    background: #eff6ff;
    &:hover { background: #dbeafe; }
  }
}

.chat-hint {
  font-size: 10px;
  color: #ea580c;
  background: #fff7ed;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.2s;
}

.member-item:hover .chat-hint {
  opacity: 1;
}

.member-avatar-wrap {
  position: relative;
  flex-shrink: 0;
  width: 38px;
  height: 38px;
}

.member-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid #e5e7eb;
}

.member-avatar-fallback {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background: linear-gradient(135deg, #ea5a1a, #d14710);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.member-avatar-fallback.teacher {
  background: linear-gradient(135deg, #fff1df, #e8b878);
  color: #8a4b16;
  border: 1px solid #dba15e;
}

.member-avatar-fallback.learner {
  background: linear-gradient(135deg, #fff7ed, #fb923c);
  color: #fff;
}

.member-status-dot {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid #fff;

  &.online { background: #22c55e; }
  &.busy { background: #f59e0b; }
}

.member-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-name-row {
  display: flex;
  align-items: center;
  gap: 6px;

  b {
    font-size: 13px;
    color: #1f2937;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.member-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 500;
}

.member-info small {
  font-size: 11.5px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-state {
  font-size: 10.5px;
  font-style: normal;
  color: #22c55e;
}

/* ===== 中栏：聊天区 ===== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 16px 20px;
  gap: 12px;

  :deep(.chat-message-list) {
    flex: 1;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    background: #f5f6f8;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  }

  :deep(.chat-input-wrap) {
    border-color: #e5e7eb;
    border-radius: 12px;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  }
}

.chat-error {
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fef2f2;
  color: #991b1b;
  font-size: 12.5px;
  border: 1px solid #fecaca;
}

/* ===== 右栏：群资料面板 ===== */
.right-panel {
  flex: none;
  width: 340px;
  background: #fff;
  border-left: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 标签栏 */
.tab-bar {
  flex: none;
  display: flex;
  align-items: center;
  gap: 0;
  padding: 0 6px;
  height: 44px;
  border-bottom: 1px solid #f0f0f0;
  overflow-x: auto;
}

.tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 44px;
  padding: 0 10px;
  border: 0;
  background: transparent;
  color: #6b7280;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  transition: all 0.12s ease;

  &:hover {
    color: #374151;
    background: #f9fafb;
  }

  &.active {
    color: #ea5a1a;
    border-bottom-color: #ea5a1a;
    font-weight: 600;
  }
}

.tab-count {
  font-style: normal;
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 999px;
  background: #f3f4f6;
  color: #6b7280;
  margin-left: 2px;

  .tab-btn.active & {
    background: #fef3e8;
    color: #ea5a1a;
  }
}

/* 标签内容 */
.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
}

.tab-pane {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.pane-section-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;

  span { font-size: 13px; }
}

.pane-count {
  margin-left: auto;
  font-style: normal;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
}

/* 一键生成按钮 */
.quick-gen-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 10px;
  border-radius: 7px;
  border: 1px solid rgba(234, 90, 26, 0.25);
  background: rgba(234, 90, 26, 0.06);
  color: #c2410c;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}
.quick-gen-toggle:hover {
  background: rgba(234, 90, 26, 0.12);
  border-color: rgba(234, 90, 26, 0.4);
}

/* 一键生成面板 */
.quick-gen-panel {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px solid rgba(234, 90, 26, 0.15);
}
.qg-input-row {
  display: flex;
  gap: 8px;
}
.qg-input {
  flex: 1;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  font-size: 12.5px;
  outline: none;
  transition: border-color 0.15s;
}
.qg-input:focus {
  border-color: #ea5a1a;
}
.qg-input:disabled {
  background: #f5f5f4;
  color: #9ca3af;
}
.qg-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 14px;
  border-radius: 8px;
  border: none;
  background: linear-gradient(120deg, #ea5a1a, #f08441);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}
.qg-btn:hover:not(:disabled) {
  opacity: 0.9;
}
.qg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.qg-progress {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: #c2410c;
  font-weight: 500;
  font-family: ui-monospace, monospace;
}
.qg-progress.done {
  color: #16a34a;
}
.qg-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.5;
}

/* 群公告卡片 */
.announcement-card {
  padding: 14px;
  border-radius: 10px;
  background: #fef9f3;
  border: 1px solid rgba(234, 90, 26, 0.12);

  p {
    margin: 0;
    font-size: 12.5px;
    line-height: 1.7;
    color: #4b5563;
  }
}

/* 群信息卡片 */
.group-info-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
}

.info-row {
  display: flex;
  align-items: center;
  padding: 10px 14px;
  font-size: 12px;
  border-bottom: 1px solid #f5f5f5;

  &:last-child { border-bottom: 0; }

  span {
    color: #6b7280;
    flex-shrink: 0;
    width: 60px;
  }

  b {
    margin-left: auto;
    font-weight: 500;
    color: #1f2937;
  }

  code {
    margin-left: auto;
    font-family: ui-monospace, monospace;
    font-size: 11px;
    color: #9ca3af;
  }
}

/* 资源列表 */
.resource-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fafbfc;
  cursor: pointer;
  transition: all 0.12s ease;

  &:hover {
    border-color: #e5e7eb;
    background: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }
}

.res-icon {
  font-size: 22px;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #f0f0f0;
}

.res-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;

  b {
    font-size: 12.5px;
    color: #1f2937;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  small {
    font-size: 11px;
    color: #9ca3af;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.res-time {
  flex-shrink: 0;
  font-size: 10.5px;
  color: #d1d5db;
}

/* 群相册网格 */
.album-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.album-card {
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.12s ease;

  &:hover {
    border-color: #e5e7eb;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    transform: translateY(-2px);
  }
}

.album-thumb {
  height: 72px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #f9fafb, #f3f4f6);
  font-size: 28px;
}

.album-info {
  padding: 6px 8px;

  b {
    display: block;
    font-size: 11.5px;
    color: #1f2937;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  small {
    font-size: 10px;
    color: #9ca3af;
  }
}

/* 空状态 */
.empty-pane {
  margin: 40px 0;
  text-align: center;
  color: #d1d5db;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;

  p {
    margin: 4px 0 0;
    font-size: 13px;
    color: #9ca3af;
  }

  small {
    font-size: 11px;
    color: #d1d5db;
  }
}

/* 快捷动作 */
.quick-action-row {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding: 0 2px;
}

.quick-action-row button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 12px;
  font-family: inherit;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover:not(:disabled) {
    color: #ea5a1a;
    border-color: rgba(234, 90, 26, 0.28);
    background: #fff7ed;
  }

  &:disabled {
    opacity: 0.55;
    cursor: wait;
  }
}

/* 学习工作台 */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.overview-card,
.task-progress-card,
.profile-meter-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fafbfc;
  padding: 12px;
}

.overview-card b {
  display: block;
  color: #ea5a1a;
  font-size: 20px;
  line-height: 1.1;
}

.overview-card small {
  display: block;
  margin-top: 4px;
  color: #6b7280;
  font-size: 11px;
}

.task-progress-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;

  small {
    margin-left: auto;
    color: #ea5a1a;
    font-weight: 700;
  }
}

.task-progress-bar {
  height: 7px;
  border-radius: 999px;
  background: #f3f4f6;
  overflow: hidden;
  margin-top: 10px;

  span {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, #ea5a1a, #f59e0b);
    transform-origin: left center;
    transition: transform 0.22s ease;
  }
}

.task-flow-list,
.knowledge-list,
.profile-dimension-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-flow-item {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 10px 11px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fff;

  b,
  small {
    display: block;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  b { font-size: 12.5px; color: #1f2937; }
  small { margin-top: 2px; font-size: 10.5px; color: #9ca3af; }
  em { font-style: normal; font-size: 10.5px; color: #9ca3af; }

  &.running em { color: #ea5a1a; font-weight: 700; }
  &.done em { color: #16a34a; font-weight: 700; }
  &.queue em { color: #f59e0b; }
}

.task-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--task-accent, #d1d5db);
}

.resource-list.enhanced {
  gap: 8px;
}

.resource-item.enhanced {
  align-items: flex-start;

  .res-body p {
    margin: 4px 0 0;
    color: #6b7280;
    font-size: 11px;
    line-height: 1.45;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

.resource-actions {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex-shrink: 0;

  button {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    border: 1px solid #e5e7eb;
    background: #fff;
    color: #6b7280;
    cursor: pointer;

    &:hover {
      color: #ea5a1a;
      border-color: rgba(234, 90, 26, 0.25);
      background: #fff7ed;
    }
  }
}

.knowledge-card,
.profile-dimension-card {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 9px;
  align-items: flex-start;
  width: 100%;
  padding: 11px;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fff;
  color: inherit;
  text-align: left;
  font-family: inherit;
}

.knowledge-card {
  cursor: pointer;

  &:hover {
    border-color: rgba(234, 90, 26, 0.25);
    background: #fffaf5;
  }

  svg { color: #ea5a1a; }
}

.profile-dimension-card svg { color: #16a34a; margin-top: 1px; }

.knowledge-card b,
.profile-dimension-card b {
  display: block;
  font-size: 12.5px;
  color: #1f2937;
  white-space: normal;
}

.knowledge-card small,
.profile-dimension-card small {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: #6b7280;
  line-height: 1.45;
  white-space: normal;
  overflow-wrap: anywhere;
}

.profile-evidence {
  display: block;
  margin-top: 4px;
  color: #0f766e;
  font-size: 10px;
  font-style: normal;
  line-height: 1.4;
}

.profile-evidence.pending {
  color: #a1a1aa;
}

.profile-meter-card {
  display: grid;
  grid-template-columns: 62px minmax(0, 1fr);
  gap: 12px;
  align-items: center;

  b { display: block; font-size: 13px; color: #1f2937; }
  small { display: block; margin-top: 4px; font-size: 11px; color: #6b7280; line-height: 1.45; }
}

.profile-ring {
  width: 58px;
  height: 58px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: conic-gradient(#ea5a1a var(--value), #f3f4f6 0);
  position: relative;

  &::before {
    content: "";
    position: absolute;
    inset: 7px;
    border-radius: inherit;
    background: #fff;
  }

  strong {
    position: relative;
    font-size: 12px;
    color: #ea5a1a;
  }
}

.wide-link-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  height: 32px;
  border: 1px solid rgba(234, 90, 26, 0.22);
  border-radius: 8px;
  background: #fff7ed;
  color: #ea5a1a;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
}

.mini-loading,
.pane-hint {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f9fafb;
  color: #6b7280;
  font-size: 11.5px;
  line-height: 1.45;
}
/* Agent 链路状态卡 */
.status-mini {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  background: #f9fafb;
  margin-top: 8px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;

  span {
    color: #6b7280;
    flex-shrink: 0;
    width: 60px;
  }

  b {
    margin-left: auto;
    font-weight: 500;
    color: #1f2937;
    display: inline-flex;
    align-items: center;
    gap: 4px;

    &.streaming { color: #ea5a1a; }
    &.idle { color: #9ca3af; }
  }
}

/* ===== 动画 ===== */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 响应式 ===== */
@media (max-width: 1200px) {
  .right-panel {
    width: 310px;
  }
}

@media (max-width: 1000px) {
  .member-sidebar {
    width: 190px;
  }
}

@media (max-width: 860px) {
  .member-sidebar {
    display: none;
  }
}

@media (max-width: 720px) {
  .chat-header {
    height: auto;
    padding: 10px 12px;
    flex-wrap: wrap;
    gap: 8px;
  }

  .header-left {
    flex: 1;
    min-width: 0;
  }

  .header-right {
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .text-btn {
    padding: 0 8px;
    font-size: 11.5px;
  }

  .exit-btn {
    display: none;
  }

  .chat-main {
    padding: 10px;
  }

  .right-panel {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    max-width: 300px;
    z-index: 30;
  }
}

/* ===== 设置面板 ===== */
.settings-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #f0f0f0;
}

.setting-item span {
  font-size: 13px;
  color: #1f2937;
}

.toggle {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #e5e7eb;
  transition: 0.3s;
  border-radius: 24px;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: 0.3s;
  border-radius: 50%;
}

.toggle input:checked + .toggle-slider {
  background-color: #ea5a1a;
}

.toggle input:checked + .toggle-slider:before {
  transform: translateX(20px);
}

.setting-divider {
  height: 1px;
  background: #e2e8f0;
  margin: 8px 0;
}

.setting-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 10px;
  border: 1px solid #f0f0f0;
  background: #fff;
  color: #1f2937;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.setting-btn:hover {
  background: #f8fafc;
  border-color: #e2e8f0;
}

.setting-btn svg {
  color: #6b7280;
}

/* ===== 新建下拉菜单 ===== */
.new-dropdown {
  position: relative;
}

.new-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  width: 160px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  z-index: 100;
  overflow: hidden;
}

.new-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  font-size: 13px;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #f9fafb;
  }

  svg {
    color: #6b7280;
  }
}

.new-menu-divider {
  height: 1px;
  background: #e5e7eb;
  margin: 4px 0;
}

/* ===== 会话菜单增强 ===== */
.favorite-icon {
  color: #f59e0b;
  font-size: 12px;
  margin-left: 4px;
}

.session-delete-btn {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;

  &:hover {
    background: #fee2e2;
    color: #ef4444;
  }
}

.session-menu-item:hover .session-delete-btn {
  opacity: 1;
}

/* ===== Agent选择器弹窗 ===== */
.agent-selector-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.agent-selector-content {
  background: white;
  border-radius: 16px;
  width: 400px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.selector-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selector-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.agent-list {
  overflow-y: auto;
  padding: 8px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-item:hover {
  background: #f8fafc;
}

.agent-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  object-fit: cover;
}

.agent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.agent-title {
  font-size: 13px;
  color: #6b7280;
}

.agent-role {
  font-size: 11px;
  color: #9ca3af;
}

.agent-status {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  padding: 4px 8px;
  background: #f1f5f9;
  border-radius: 6px;
}

.agent-status.online {
  color: #16a34a;
  background: #dcfce7;
}

/* ===== Competition demo polish: AI SaaS workspace ===== */
.chat-view {
  background:
    radial-gradient(circle at 14% 0%, rgba(249, 115, 22, 0.09), transparent 28%),
    radial-gradient(circle at 84% 8%, rgba(37, 99, 235, 0.08), transparent 30%),
    #f6f8fb;
  color: #0f172a;
}

.chat-header {
  height: 64px;
  padding: 0 22px;
  border-bottom-color: #dbe4ef;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
  backdrop-filter: blur(16px);
}

.room-icon {
  border-radius: 12px;
  color: #f97316;
  background: linear-gradient(135deg, #fff7ed, #eff6ff);
  border: 1px solid #fed7aa;
}

.room-text h2 {
  font-size: 18px;
  color: #0f172a;
}

.room-sub {
  color: #64748b;
}

.icon-btn,
.text-btn,
.session-btn {
  border-color: #dbe4ef;
  border-radius: 11px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
}

.icon-btn:hover,
.text-btn:hover,
.session-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
  color: #ea580c;
}

.exit-btn {
  height: 36px;
  border-radius: 11px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  box-shadow: 0 10px 22px rgba(234, 88, 12, 0.22);
}

.chat-body {
  gap: 0;
  min-height: 0;
}

.member-sidebar {
  width: 270px;
  padding: 14px 12px 16px;
  border-right-color: #dbe4ef;
  background: rgba(255, 255, 255, 0.9);
}

.member-search-wrap {
  padding: 8px 2px 14px;
}

.member-search-input {
  height: 38px;
  border-radius: 12px;
  background: #fff;
  border-color: #dbe4ef;
}

.member-count-bar {
  padding: 0 2px 10px;
  color: #475569;
  border-bottom: 0;
  font-weight: 700;
}

.member-list {
  padding: 2px 0 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.member-item {
  position: relative;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.member-item:hover {
  background: #fff;
  border-color: rgba(249, 115, 22, 0.28);
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}

.member-item.student {
  background: linear-gradient(135deg, #eff6ff, #fff);
  border-color: #bfdbfe;
}

.member-avatar-wrap {
  width: 44px;
  height: 44px;
}

.member-avatar-img,
.member-avatar-fallback {
  border-radius: 14px;
}

.member-status-dot.online {
  background: #22c55e;
  box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.13);
}

.member-status-dot.busy {
  background: #f97316;
  animation: statusPulse 1.6s ease-in-out infinite;
}

.member-name-row b {
  font-size: 14px;
  color: #0f172a;
}

.member-info small {
  color: #475569;
}

.member-state {
  display: inline-flex;
  width: fit-content;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f0fdf4;
  color: #16a34a;
  font-weight: 700;
}

.chat-hint {
  color: #ea580c;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.chat-main {
  padding: 18px 18px 18px;
  gap: 12px;
}

.task-context-card {
  flex: none;
  display: grid;
  grid-template-columns: 44px minmax(180px, 1.4fr) minmax(110px, 0.5fr) minmax(170px, 0.7fr) minmax(150px, 0.7fr);
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.9)),
    #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
}

.task-context-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: #fff;
  background: linear-gradient(135deg, #8b5cf6, #2563eb);
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.22);
}

.task-context-block,
.task-context-progress {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.task-context-block span,
.task-context-progress span {
  font-size: 11px;
  color: #64748b;
}

.task-context-block b {
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.task-context-block em {
  width: fit-content;
  padding: 3px 9px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.task-context-block em.running {
  background: #fff7ed;
  color: #ea580c;
}

.task-context-bar {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.task-context-bar i {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #f97316, #fb923c);
  transform-origin: left center;
  transition: transform 0.22s ease;
}

.task-context-progress strong {
  font-size: 12px;
  color: #0f172a;
}

.right-panel {
  width: 360px;
  padding: 12px;
  border-left-color: #dbe4ef;
  background: rgba(255, 255, 255, 0.9);
}

.tab-bar {
  height: 44px;
  gap: 4px;
  padding: 2px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

.tab-btn {
  height: 38px;
  padding: 0 10px;
  border-radius: 11px;
  border-bottom: 0;
}

.tab-btn.active {
  color: #ea580c;
  border-bottom-color: transparent;
  background: #fff;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.07);
}

.tab-content {
  padding: 14px 2px 0;
}

.tab-pane {
  gap: 12px;
}

.pane-section-head {
  color: #0f172a;
}

.announcement-card,
.group-info-card,
.overview-card,
.task-progress-card,
.profile-meter-card,
.resource-item,
.knowledge-card,
.profile-dimension-card,
.status-mini {
  border-color: #e2e8f0;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045);
}

.announcement-card {
  background: linear-gradient(135deg, #fff7ed, #fff);
}

.overview-card b,
.task-progress-head small {
  color: #f97316;
}

.task-flow-item {
  position: relative;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  border-color: #e2e8f0;
  border-radius: 14px;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045);
}

.task-flow-item.running {
  border-color: rgba(249, 115, 22, 0.3);
  background: #fffaf5;
}

.task-flow-item.running .task-dot {
  animation: statusPulse 1.6s ease-in-out infinite;
}

.task-dot {
  width: 10px;
  height: 10px;
}

.res-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff, #fff7ed);
  color: #2563eb;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.resource-zone-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.resource-zone-card {
  min-height: 74px;
  padding: 11px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92)),
    #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.045);
}

.resource-zone-card.all {
  grid-column: span 2;
  background: linear-gradient(135deg, #fff7ed, #eff6ff);
}

.resource-zone-card strong {
  display: block;
  color: #0f172a;
  font-size: 20px;
  line-height: 1;
}

.resource-zone-card span {
  display: block;
  margin-top: 6px;
  color: #172033;
  font-size: 12px;
  font-weight: 800;
}

.resource-zone-card small {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 10.5px;
}

.resource-cabinet {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.resource-section {
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #f8fafc;
}

.resource-section-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.resource-section-head div {
  min-width: 0;
}

.resource-section-head b {
  display: block;
  color: #0f172a;
  font-size: 12.5px;
}

.resource-section-head small {
  display: block;
  margin-top: 2px;
  color: #64748b;
  font-size: 10.5px;
  line-height: 1.4;
}

.resource-section-head em {
  margin-left: auto;
  min-width: 24px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #fff;
  color: #ea580c;
  border: 1px solid #fed7aa;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.resource-list.compact {
  gap: 7px;
}

.resource-list.compact .resource-item {
  padding: 9px;
}

.resource-section-empty {
  padding: 12px;
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  background: #fff;
  color: #94a3b8;
  font-size: 11px;
  line-height: 1.5;
}

.related-resource-panel {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045);
}

.related-resource-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.related-resource-head div {
  min-width: 0;
}

.related-resource-head b {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.related-resource-head small {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 10.5px;
  line-height: 1.45;
}

.related-resource-head button {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.related-resource-head button:hover {
  color: #ea580c;
}

.related-resource-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-resource-item {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid #e5eaf1;
  border-radius: 12px;
  background: #fff;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.related-resource-item:hover {
  border-color: #cbd5e1;
  background: #fbfdff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.055);
}

.resource-file-badge {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 9px;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.related-resource-item.pdf .resource-file-badge {
  background: #fee2e2;
  color: #dc2626;
}

.related-resource-item.ppt .resource-file-badge {
  background: #ffedd5;
  color: #ea580c;
}

.related-resource-item.word .resource-file-badge {
  background: #dbeafe;
  color: #2563eb;
}

.related-resource-item.other .resource-file-badge {
  background: #dcfce7;
  color: #16a34a;
}

.related-resource-body {
  min-width: 0;
}

.related-resource-body b {
  display: block;
  overflow: hidden;
  color: #172033;
  font-size: 12px;
  font-weight: 750;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.related-resource-body small {
  display: block;
  margin-top: 3px;
  overflow: hidden;
  color: #94a3b8;
  font-size: 10.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.resource-audio-player {
  width: 100%;
  margin-top: 6px;
  height: 32px;
  border-radius: 6px;
}

.resource-video-player {
  width: 100%;
  margin-top: 8px;
  max-height: 240px;
  border-radius: 8px;
  background: #000;
  outline: none;
}

.related-resource-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.related-resource-actions button {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}

.related-resource-actions button:hover {
  background: #f1f5f9;
  color: #ea580c;
}

.related-resource-empty {
  padding: 24px 14px;
  border: 1px dashed #cbd5e1;
  border-radius: 13px;
  background: #f8fafc;
  text-align: center;
  color: #94a3b8;
}

.related-resource-empty p {
  margin: 8px 0 3px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.related-resource-empty small {
  color: #94a3b8;
  font-size: 10.5px;
  line-height: 1.5;
}

.resource-actions button,
.wide-link-btn {
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.resource-actions button:hover,
.wide-link-btn:hover {
  transform: translateY(-1px);
}

.empty-pane {
  margin: 18px 0;
  padding: 26px 18px;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: #f8fafc;
  color: #94a3b8;
}

@keyframes statusPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(249, 115, 22, 0.22);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(249, 115, 22, 0);
  }
}

@media (max-width: 1280px) {
  .task-context-card {
    grid-template-columns: 44px minmax(160px, 1fr) minmax(110px, 0.5fr) minmax(150px, 0.6fr);
  }

  .task-context-agent {
    display: none;
  }
}

@media (max-width: 1000px) {
  .member-sidebar {
    width: 230px;
  }

  .task-context-card {
    grid-template-columns: 44px minmax(0, 1fr) minmax(110px, auto);
  }

  .task-context-progress {
    display: none;
  }
}

@media (max-width: 720px) {
  .task-context-card {
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .task-context-icon {
    width: 36px;
    height: 36px;
  }

  .task-context-block:not(.task-context-main),
  .task-context-progress {
    display: none;
  }
}

/* ===== 实时学情仪表盘 ===== */
.pane-refresh-btn {
  margin-left: auto;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--neutral-500);
  padding: 2px;
  display: flex;
  align-items: center;
}
.pane-refresh-btn:hover { color: var(--orange-500); }
.pane-refresh-btn .spin { animation: spin 0.8s linear infinite; }

.realtime-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  color: var(--neutral-400);
  text-align: center;
}
.realtime-empty p { font-size: 14px; margin: 0; color: var(--neutral-600); }
.realtime-empty small { font-size: 12px; }

.realtime-dashboard {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.realtime-identity-card {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #fffaf3 0%, #fff 100%);
  border: 1px solid #f1dfc7;
  border-radius: 12px;
}
.realtime-identity-main { display: flex; align-items: center; gap: 10px; min-width: 0; }
.realtime-identity-main strong { display: block; color: #3a2a1d; font-size: 13px; }
.realtime-identity-main small { display: block; margin-top: 3px; color: #8b7e6e; font-size: 10px; }
.realtime-learner-avatar,
.realtime-learner-avatar-fallback { width: 34px; height: 34px; border-radius: 10px; object-fit: cover; flex: none; }
.realtime-learner-avatar-fallback { display: grid; place-items: center; background: linear-gradient(135deg, #fff7ed, #fb923c); color: #fff; font-weight: 800; }
.realtime-session-badge { flex: none; text-align: right; }
.realtime-session-badge span { display: block; color: #a08f7d; font-size: 10px; }
.realtime-session-badge code { color: #8a4b16; font-size: 10px; }
.realtime-profile-link-card {
  padding: 12px 14px;
  background: #f8fbff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
}
.realtime-card-title { display: flex; align-items: center; gap: 6px; color: #315b8a; font-size: 12px; font-weight: 700; }
.realtime-card-title em { margin-left: auto; color: #64748b; font-size: 10px; font-style: normal; font-weight: 500; }
.realtime-profile-basis { display: grid; gap: 6px; margin-top: 10px; }
.realtime-profile-chip { display: block; padding: 7px 8px; color: #46566b; background: #fff; border: 1px solid #e4edf8; border-radius: 8px; font-size: 11px; line-height: 1.4; }
.realtime-profile-chip b { display: inline-block; min-width: 54px; margin-right: 6px; color: #315b8a; }
.realtime-card-note { margin: 10px 0 0; color: #728197; font-size: 11px; line-height: 1.5; }
.realtime-evidence { margin-top: 10px; padding-top: 9px; border-top: 1px dashed #cbdcf0; }
.realtime-evidence-label { color: #315b8a; font-size: 10px; font-weight: 700; }
.realtime-evidence ul { margin: 5px 0 0; padding-left: 17px; color: #52657d; font-size: 11px; line-height: 1.5; }
.realtime-evidence-muted p { margin: 5px 0 0; color: #7c8da3; font-size: 11px; line-height: 1.5; }
.realtime-summary-card {
  padding: 12px 14px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border-radius: 8px;
  border: 1px solid #bae6fd;
}
.realtime-summary-head {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}
.realtime-emotion-tag,
.realtime-engagement-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}
.realtime-emotion-tag {
  background: #fef3c7;
  color: #92400e;
}
.realtime-engagement-tag {
  background: #d1fae5;
  color: #065f46;
}
.realtime-summary-text {
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.5;
  margin: 0;
}
.realtime-metrics {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.realtime-metric-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.realtime-metric-head small {
  font-size: 11px;
  color: var(--neutral-500);
}
.realtime-metric-head span {
  font-size: 12px;
  font-weight: 700;
}
.realtime-metric-bar {
  height: 6px;
  background: var(--neutral-100);
  border-radius: 3px;
  overflow: hidden;
}
.realtime-metric-fill {
  width: 100%;
  height: 100%;
  border-radius: 3px;
  transform-origin: left center;
  transition: transform .24s ease;
}
.realtime-topics-card {
  padding: 10px 12px;
  background: var(--neutral-50);
  border-radius: 8px;
}
.realtime-topics-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--neutral-600);
  margin-bottom: 8px;
}
.realtime-topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.realtime-topic-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.realtime-topic-tag.stuck {
  background: #fee2e2;
  color: #991b1b;
}
.realtime-topic-tag.curious {
  background: #ede9fe;
  color: #5b21b6;
}
.realtime-action-card {
  padding: 12px 14px;
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border-radius: 8px;
  border: 1px solid #fed7aa;
}
.realtime-action-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--orange-600);
  margin-bottom: 6px;
}
.realtime-action-card p {
  font-size: 12px;
  color: var(--neutral-700);
  line-height: 1.5;
  margin: 0;
}
</style>
