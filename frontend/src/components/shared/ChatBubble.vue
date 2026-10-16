<script setup lang="ts">
/**
 * ChatBubble · 群聊气泡组件
 *
 * - assistant: 头像 + 名字在左侧，气泡左对齐
 * - user: 头像 + 名字在右侧，气泡右对齐
 * - 多 Agent 协作时显示主导 Agent 头像 + 协作数量
 */
import { computed, ref } from "vue";
import { markedWithMath } from "@/utils/markedWithMath";

import {
  AGENT_AVATARS,
  getAvatar,
  type AvatarKind,
} from "@/constants/agentAvatars";
import { getLearnerPartner } from "@/constants/companion";
import { useSession } from "@/composables/useSession";
import { getAuthSession } from "@/utils/auth";
import {
  ArrowUpRight,
  BarChart3,
  BookOpenCheck,
  Check,
  Copy,
  Headphones,
  ListChecks,
  Loader2,
  Network,
  Presentation,
  Sparkles,
  Video,
} from "lucide-vue-next";

interface QuotedMessage {
  id: string;
  sender: string;
  senderAvatar?: string;
  content: string;
  timestamp: number;
}

/** 气泡内联附件：让 code/quiz/mindmap 直接在消息里预览，不必去右侧文件面板 */
export interface ChatAttachment {
  /** code | quiz | mindmap | evaluation | media | resource */
  kind: "code" | "quiz" | "mindmap" | "evaluation" | "media" | "resource";
  title?: string;
  /** code: 源码字符串；mindmap: mermaid_code */
  content?: string;
  /** code: 语言标记 */
  language?: string;
  /** code: 运行输出（stdout） */
  stdout?: string;
  /** quiz: 题目列表 */
  items?: Array<Record<string, any>>;
  /** mindmap: 渲染好的 data:image/png */
  dataUri?: string;
  /** mindmap: 大纲结构（当 mermaid_code 渲染失败时兜底显示） */
  branches?: string[];
  leaves?: Record<string, string[]>;
  /** evaluation: 可读维度条 + SVG 图表 */
  overallScore?: number;
  dimensions?: Record<string, unknown>;
  evidenceStatus?: "sufficient" | "insufficient" | string;
  visualizations?: Array<{
    title?: string;
    dataUri?: string;
    alt?: string;
    description?: string;
  }>;
  /** media: 阿匠生成的可播放语音/视频 */
  mediaType?: "audio" | "video";
  src?: string;
  status?: string;
  description?: string;
  /** 兜底资源卡：结构化预览不可用时仍提供真实文件入口 */
  href?: string;
  downloadName?: string;
}

export type ChatSuggestedActionIcon = "presentation" | "video" | "mindmap" | "quiz" | "learn";

/** Agent 问候气泡中的任务导引卡片。点击后由页面沿用正常消息发送链路。 */
export interface ChatSuggestedAction {
  id: string;
  label: string;
  description: string;
  prompt: string;
  icon?: ChatSuggestedActionIcon;
}

interface Props {
  role: "user" | "assistant";
  content: string;
  agentKinds?: AvatarKind[];
  primaryKind?: AvatarKind;
  timestamp?: number;
  isStreaming?: boolean;
  quotedMessage?: QuotedMessage;
  /** 群聊角色感知：teacher 时以教师身份渲染（头像/名称/标签） */
  senderType?: "agent" | "teacher";
  senderName?: string;
  attachments?: ChatAttachment[];
  suggestedActions?: ChatSuggestedAction[];
  suggestionsDisabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  agentKinds: () => [],
  primaryKind: undefined,
  timestamp: 0,
  isStreaming: false,
  quotedMessage: undefined,
  senderType: "agent",
  senderName: "",
  attachments: () => [],
  suggestedActions: () => [],
  suggestionsDisabled: false,
});

const { userId } = useSession();
const learnerPartner = computed(() => getLearnerPartner(
  userId.value,
  getAuthSession()?.displayName || "",
));
// 教师头像加载失败时回退到"师"字圆徽，不留空白头像。
const teacherAvatarFailed = ref(false);

/** 轻量 Python/JS 语法着色：单次扫描原始字符，绝不二次处理生成的 HTML。 */
const CODE_KEYWORDS = new Set([
  "def", "class", "if", "elif", "else", "for", "while", "return", "import",
  "from", "as", "in", "not", "and", "or", "True", "False", "None", "lambda",
  "try", "except", "finally", "with", "pass", "break", "continue", "yield",
  "raise", "self", "async", "await", "global", "nonlocal", "assert", "del",
  "is", "print", "len", "range", "int", "str", "float", "list", "dict", "tuple",
  "set", "bool", "const", "let", "var", "function", "new", "this", "throw",
  "switch", "case", "default", "typeof", "instanceof", "interface", "type",
  "extends", "implements", "public", "private", "protected", "static", "void",
  "undefined", "null", "true", "false", "export",
]);
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
function highlightCodeLine(line: string, language?: string): string {
  const lang = String(language || "python").toLowerCase();
  if (!["python", "py", "javascript", "js", "ts", "typescript"].includes(lang)) {
    return escapeHtml(line);
  }

  const isJs = ["javascript", "js", "ts", "typescript"].includes(lang);
  let html = "";
  let index = 0;
  while (index < line.length) {
    const char = line[index];
    const next = line[index + 1] || "";

    if ((!isJs && char === "#") || (isJs && char === "/" && next === "/")) {
      html += `<span class="c-comment">${escapeHtml(line.slice(index))}</span>`;
      break;
    }

    if (char === '"' || char === "'" || (isJs && char === "`")) {
      const quote = char;
      let end = index + 1;
      while (end < line.length) {
        if (line[end] === quote && line[end - 1] !== "\\") {
          end += 1;
          break;
        }
        end += 1;
      }
      html += `<span class="c-str">${escapeHtml(line.slice(index, end))}</span>`;
      index = end;
      continue;
    }

    if (!isJs && char === "@") {
      const match = line.slice(index).match(/^@[A-Za-z_][A-Za-z0-9_.]*/);
      if (match) {
        html += `<span class="c-dec">${escapeHtml(match[0])}</span>`;
        index += match[0].length;
        continue;
      }
    }

    if (/\d/.test(char)) {
      const match = line.slice(index).match(/^\d+(?:\.\d+)?(?:e[+-]?\d+)?/i);
      if (match) {
        html += `<span class="c-num">${match[0]}</span>`;
        index += match[0].length;
        continue;
      }
    }

    if (/[A-Za-z_]/.test(char)) {
      const match = line.slice(index).match(/^[A-Za-z_][A-Za-z0-9_]*/);
      if (match) {
        const word = match[0];
        html += CODE_KEYWORDS.has(word)
          ? `<span class="c-kw">${word}</span>`
          : escapeHtml(word);
        index += word.length;
        continue;
      }
    }

    html += escapeHtml(char);
    index += 1;
  }
  return html;
}

function codeLines(code: string): string[] {
  return String(code || "").replace(/\r\n/g, "\n").split("\n");
}

function scorePercent(value: unknown): number {
  const raw = typeof value === "object" && value !== null
    ? Number((value as Record<string, unknown>).score ?? 0)
    : Number(value ?? 0);
  if (!Number.isFinite(raw)) return 0;
  return Math.max(0, Math.min(100, Math.round(raw <= 1 ? raw * 100 : raw)));
}

function evaluationRows(dimensions?: Record<string, unknown>) {
  return Object.entries(dimensions || {}).map(([label, value]) => ({
    label,
    value: scorePercent(value),
  }));
}

const copiedAttachment = ref(-1);
async function copyCode(code: string, index: number) {
  try {
    await navigator.clipboard.writeText(code);
    copiedAttachment.value = index;
    window.setTimeout(() => {
      if (copiedAttachment.value === index) copiedAttachment.value = -1;
    }, 1600);
  } catch {
    copiedAttachment.value = -1;
  }
}

const isTeacherMessage = computed(
  () => props.role === "assistant" && props.senderType === "teacher",
);

const emit = defineEmits<{
  (e: 'avatar-click', agentKey: string): void;
  (e: 'suggestion-click', action: ChatSuggestedAction): void;
}>();

const suggestedActionIcons = {
  presentation: Presentation,
  video: Video,
  mindmap: Network,
  quiz: ListChecks,
  learn: BookOpenCheck,
} as const;

/**
 * 清洗 Agent 输出中的结构化 JSON / 代码块，
 * 避免聊天界面显示原始 JSON 或 evaluation_result 代码块。
 */
function sanitizeContent(text: string): string {
  if (!text) return "";
  let cleaned = text;
  // 1. 移除 ```evaluation_result ... ``` 包裹块
  cleaned = cleaned.replace(/```evaluation_result\s*\n[\s\S]*?\n```/g, "");
  cleaned = cleaned.replace(/```(?:quiz_json|profile_update|learning_path)\s*\n[\s\S]*?\n```/g, "");
  // 结构块删除后同步移除孤立标题，兼容已经写入历史的旧消息。
  cleaned = cleaned.replace(
    /^\s{0,3}(?:#{1,6}\s*)?(?:\*\*)?(?:结构化数据(?:\s*[（(]?JSON[）)]?)?|路径\s*JSON|JSON\s*数据)(?:\*\*)?\s*[:：]?\s*$/gim,
    "",
  );
  // 防御旧缓存/旧模型回显的内部命题协议，不让系统提示混入用户正文。
  cleaned = cleaned
    .split("\n")
    .filter((line) => !/人类可读的完整题目|练习题：设计\s*\d+\s*道|请根据以下要求出题/.test(line))
    .join("\n");
  // 2. 移除 ```json ... ``` 包裹的纯 JSON（仅当包含结构化标记字段时）
  cleaned = cleaned.replace(/```(?:json|JSON)?\s*\n(\{[\s\S]*?\})\s*\n```/g, (_m, json) => {
    if (/"overall_score"|"dimensions"|"strengths"|"weaknesses"|"path_adjustments"|"profile_updates"/.test(json)) {
      return "";
    }
    return _m;
  });
  // 3. 兜底：移除裸 JSON 对象（以 { 开头且包含结构化标记字段）
  const lines = cleaned.split("\n");
  const result: string[] = [];
  let inJson = false;
  let braceDepth = 0;
  for (const line of lines) {
    const stripped = line.trim();
    if (!inJson && stripped.startsWith("{") && /"overall_score"|"dimensions"|"strengths"|"path_adjustments"/.test(stripped)) {
      inJson = true;
      braceDepth = (stripped.match(/{/g) || []).length - (stripped.match(/}/g) || []).length;
      if (braceDepth <= 0) inJson = false;
      continue;
    }
    if (inJson) {
      braceDepth += (stripped.match(/{/g) || []).length - (stripped.match(/}/g) || []).length;
      if (braceDepth <= 0) inJson = false;
      continue;
    }
    result.push(line);
  }
  cleaned = result.join("\n");
  // 清理多余空行
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n").trim();
  return cleaned;
}

const normalizedKinds = computed<AvatarKind[]>(() => {
  if (props.agentKinds.length) return props.agentKinds;
  return [];
});

// 思考中状态：流式输出且尚未收到 meta 事件（无 primaryKind、无 agentKinds）
// 但如果 agentKinds 有值，说明已经知道是哪个 Agent 在回答
const isThinking = computed(
  () => props.isStreaming && !props.primaryKind && normalizedKinds.value.length === 0,
);

// 思考中的 Agent 名称
const thinkingName = computed(() => {
  // 如果已经有明确的 Agent，显示该 Agent 名称
  if (props.primaryKind) {
    return getAvatar(props.primaryKind).nick + ' 思考中...';
  }
  // 如果有 agentKinds，显示第一个
  if (normalizedKinds.value.length > 0) {
    return getAvatar(normalizedKinds.value[0]).nick + ' 思考中...';
  }
  // 默认显示团队
  return 'Agent 团队思考中';
});

const primary = computed(() => {
  if (props.primaryKind) return getAvatar(props.primaryKind);
  const first = normalizedKinds.value[0];
  return first ? getAvatar(first) : AGENT_AVATARS.tutor;
});

const collabCount = computed(() =>
  normalizedKinds.value.length > 1 ? normalizedKinds.value.length - 1 : 0,
);

const timeStr = computed(() => {
  if (!props.timestamp) return "";
  try {
    const d = new Date(props.timestamp);
    return d.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
});
</script>

<template>
  <div :class="['chat-bubble-wrap', `is-${role}`]">
    <!-- ===== Agent / 教师 消息（左侧） ===== -->
    <template v-if="role === 'assistant'">
      <!-- 头像 -->
      <div class="avatar-col">
        <div v-if="isTeacherMessage" class="avatar-circle avatar-teacher" title="教师">
          <img
            v-if="!teacherAvatarFailed"
            src="/avatars/wang-teacher.svg"
            alt="教师"
            @error="teacherAvatarFailed = true"
          />
          <span v-else class="avatar-teacher-text">师</span>
        </div>
        <div v-else-if="isThinking" class="avatar-circle avatar-thinking">
          <Loader2 :size="18" class="spin" />
        </div>
        <div
          v-else
          class="avatar-circle clickable"
          :style="{ borderColor: primary.color }"
          @click="$emit('avatar-click', primary.kind)"
          title="点击开始私聊"
        >
          <img
            v-if="primary.png"
            :src="primary.png!"
            :alt="primary.nick"
            @error="($event.target as HTMLImageElement).style.display = 'none'"
          />
          <span v-else class="avatar-emoji">{{ primary.emoji }}</span>
        </div>
      </div>

      <!-- 消息体 -->
      <div
        class="body-col agent-card"
        :style="{ '--agent-color': isTeacherMessage ? '#b45309' : primary.color }"
      >
        <div class="meta-row">
          <template v-if="isTeacherMessage">
            <strong style="color: #b45309">{{ senderName || "教师" }}</strong>
            <span class="role-tag teacher-tag">教师</span>
          </template>
          <template v-else-if="isThinking">
            <strong class="thinking-name">{{ thinkingName }}</strong>
          </template>
          <template v-else>
            <strong :style="{ color: primary.color }">{{ primary.nick }}</strong>
            <span class="role-tag">{{ primary.role }}</span>
            <span v-if="collabCount" class="collab-tag">+{{ collabCount }} 协作</span>
          </template>
          <span v-if="timeStr" class="time-text">{{ timeStr }}</span>
        </div>
        <!-- 引用消息 -->
        <div v-if="quotedMessage" class="quoted-message">
          <div class="quoted-sender">{{ quotedMessage.sender }}</div>
          <div class="quoted-content">{{ quotedMessage.content }}</div>
        </div>
        <div
          :class="['bubble-content', 'markdown-body', isStreaming ? 'streaming' : '']"
        >
          <div v-html="markedWithMath.parse(sanitizeContent(content))"></div>
          <span v-if="isStreaming" class="cursor-blink">▍</span>
        </div>

        <section
          v-if="suggestedActions.length"
          class="guided-actions"
          aria-label="推荐学习任务"
        >
          <div class="guided-actions-head">
            <span><Sparkles :size="15" /> 你可以试试</span>
            <small>点击卡片即可发起任务</small>
          </div>
          <div class="guided-action-grid">
            <button
              v-for="action in suggestedActions"
              :key="action.id"
              type="button"
              class="guided-action-card"
              :disabled="suggestionsDisabled"
              :aria-label="`${action.label}：${action.description}`"
              @click="emit('suggestion-click', action)"
            >
              <span class="guided-action-icon" aria-hidden="true">
                <component :is="suggestedActionIcons[action.icon || 'learn']" :size="18" />
              </span>
              <span class="guided-action-copy">
                <b>{{ action.label }}</b>
                <small>{{ action.description }}</small>
              </span>
              <ArrowUpRight :size="15" class="guided-action-arrow" aria-hidden="true" />
            </button>
          </div>
          <p class="guided-actions-foot">也可以在输入框中换成你正在学习的知识点。</p>
        </section>

        <!-- 内联附件：思维导图 / 代码 / 题目直接在气泡里展开 -->
        <div v-if="attachments && attachments.length" class="bubble-attachments">
          <template v-for="(att, idx) in attachments" :key="idx">
            <!-- 思维导图 -->
            <div v-if="att.kind === 'mindmap'" class="att-card att-mindmap">
              <div class="att-head"><b>{{ att.title || '思维导图' }}</b><small>Mindmap</small></div>
              <img v-if="att.dataUri" :src="att.dataUri" :alt="att.title || 'mindmap'" class="mm-img" />
              <div v-else-if="att.branches && att.branches.length" class="mm-outline">
                <div v-for="(br, bi) in att.branches" :key="bi" class="mm-branch">
                  <b>{{ br }}</b>
                  <ul v-if="att.leaves && att.leaves[br] && att.leaves[br].length">
                    <li v-for="(leaf, li) in att.leaves[br]" :key="li">{{ leaf }}</li>
                  </ul>
                </div>
              </div>
              <details v-if="att.content" class="mm-code">
                <summary>查看 Mermaid 源码</summary>
                <pre><code>{{ att.content }}</code></pre>
              </details>
            </div>

            <!-- 评估可视化：结构化维度条 + 有图像描述的 SVG -->
            <div v-else-if="att.kind === 'evaluation'" class="att-card att-evaluation">
              <div class="att-head">
                <span class="eval-head-title"><BarChart3 :size="15" /><b>{{ att.title || '学习评估可视化' }}</b></span>
                <small>{{ att.evidenceStatus === 'insufficient' ? '证据待补充' : '基于学习证据' }}</small>
              </div>
              <div class="eval-body">
                <div v-if="att.overallScore !== undefined" class="eval-overall">
                  <span>综合参考值</span>
                  <strong>{{ scorePercent(att.overallScore) }}%</strong>
                  <div class="eval-track" aria-hidden="true"><i :style="{ width: `${scorePercent(att.overallScore)}%` }" /></div>
                </div>
                <div v-if="evaluationRows(att.dimensions).length" class="eval-dimensions" aria-label="评估维度">
                  <div v-for="row in evaluationRows(att.dimensions)" :key="row.label" class="eval-dimension-row">
                    <span>{{ row.label }}</span>
                    <div class="eval-track"><i :style="{ width: `${row.value}%` }" /></div>
                    <b>{{ row.value }}%</b>
                  </div>
                </div>
                <div v-if="att.visualizations && att.visualizations.length" class="eval-figures">
                  <figure v-for="(visual, vi) in att.visualizations" :key="vi">
                    <img v-if="visual.dataUri" :src="visual.dataUri" :alt="visual.alt || visual.title || '学习评估图表'" />
                    <figcaption>
                      <b>{{ visual.title || '评估图表' }}</b>
                      <span v-if="visual.description">{{ visual.description }}</span>
                    </figcaption>
                  </figure>
                </div>
                <p v-if="att.evidenceStatus === 'insufficient'" class="eval-evidence-note">
                  当前证据不足，图中不对缺失维度做能力推断；建议先完成基线测验后再比较。
                </p>
              </div>
            </div>

            <div v-else-if="att.kind === 'resource'" class="att-card att-resource">
              <div class="att-head">
                <b>{{ att.title || '学习资源' }}</b>
                <small>READY</small>
              </div>
              <p>{{ att.description || '文件已经生成，可直接下载完整内容。' }}</p>
              <a v-if="att.href" :href="att.href" :download="att.downloadName || ''" rel="noopener noreferrer">
                下载文件
              </a>
            </div>

            <!-- 阿匠生成的音频 / 视频，可直接在所属 Agent 气泡中播放 -->
            <div v-else-if="att.kind === 'media'" class="att-card att-media">
              <div class="att-head">
                <span class="media-head-title">
                  <Headphones v-if="att.mediaType === 'audio'" :size="15" />
                  <Video v-else :size="15" />
                  <b>{{ att.title || (att.mediaType === 'audio' ? '语音导学' : '视频讲解') }}</b>
                </span>
                <small>{{ att.mediaType === 'audio' ? 'AUDIO' : 'VIDEO' }}</small>
              </div>
              <div class="media-body">
                <audio v-if="att.mediaType === 'audio' && att.src" :src="att.src" controls preload="none" />
                <video v-else-if="att.src" :src="att.src" controls preload="metadata" playsinline />
                <p v-if="att.description">{{ att.description }}</p>
              </div>
            </div>

            <!-- 代码：VS Code Dark 风格 + 语法着色 -->
            <div v-else-if="att.kind === 'code'" class="att-card att-code">
              <div class="att-head att-head-code">
                <div class="code-title">
                  <span class="win-btn red" />
                  <span class="win-btn yellow" />
                  <span class="win-btn green" />
                  <b>{{ att.title || '代码示例' }}</b>
                </div>
                <div class="code-head-actions">
                  <small>{{ (att.language || 'python').toUpperCase() }}</small>
                  <button type="button" class="copy-code" @click="copyCode(att.content || '', idx)">
                    <Check v-if="copiedAttachment === idx" :size="13" />
                    <Copy v-else :size="13" />
                    {{ copiedAttachment === idx ? '已复制' : '复制' }}
                  </button>
                </div>
              </div>
              <div class="code-block" role="region" :aria-label="att.title || '代码示例'">
                <div
                  v-for="(line, lineIndex) in codeLines(att.content || '')"
                  :key="lineIndex"
                  class="code-line"
                >
                  <span class="line-number" aria-hidden="true">{{ lineIndex + 1 }}</span>
                  <code v-html="highlightCodeLine(line, att.language)"></code>
                </div>
              </div>
              <details v-if="att.stdout" class="code-stdout">
                <summary>运行输出</summary>
                <pre><code>{{ att.stdout }}</code></pre>
              </details>
            </div>

            <!-- 题目 -->
            <div v-else-if="att.kind === 'quiz'" class="att-card att-quiz">
              <div class="att-head"><b>{{ att.title || '练习题' }}</b><small>{{ (att.items || []).length }} 道</small></div>
              <div class="quiz-list">
                <details
                  v-for="(q, qi) in (att.items || [])"
                  :key="qi"
                  class="quiz-question"
                  :open="qi < 3"
                >
                  <summary>
                    <span class="q-index">{{ String(qi + 1).padStart(2, '0') }}</span>
                    <span class="q-summary-main">
                      <span class="q-badges">
                        <em class="q-type">{{ q.type === 'choice' ? '单选' : q.type === 'multi_choice' ? '多选' : q.type === 'judge' ? '判断' : q.type === 'fill' ? '填空' : q.type === 'code' ? '编程' : q.type === 'debug' ? 'Debug' : q.type === 'case' ? '综合' : q.type === 'short' ? '简答' : '练习' }}</em>
                        <em v-if="q.difficulty" class="q-difficulty" :class="`is-${q.difficulty}`">{{ q.difficulty }}</em>
                        <em v-if="q.bloom" class="q-bloom">{{ q.bloom }}</em>
                      </span>
                      <span class="q-stem">{{ q.question || q.stem || '' }}</span>
                    </span>
                  </summary>
                  <div class="q-detail">
                    <ul v-if="Array.isArray(q.options) && q.options.length" class="q-options">
                      <li v-for="(opt, oi) in q.options" :key="oi">{{ opt }}</li>
                    </ul>
                    <div v-if="q.signature || q.example || q.complexity" class="q-code-brief">
                      <code v-if="q.signature">{{ q.signature }}</code>
                      <span v-if="q.example">示例：{{ q.example }}</span>
                      <span v-if="q.complexity">复杂度：{{ q.complexity }}</span>
                    </div>
                    <div v-if="q.answer !== undefined || q.explanation" class="q-answer">
                      <p v-if="q.answer !== undefined"><b>参考答案</b>{{ q.answer }}</p>
                      <p v-if="q.explanation"><b>解析</b>{{ q.explanation }}</p>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </template>
        </div>
      </div>
    </template>

    <!-- ===== 用户消息（右侧） ===== -->
    <template v-else>
      <div class="body-col body-col-user">
        <div v-if="timeStr" class="meta-row meta-row-user">
          <span class="time-text">{{ timeStr }}</span>
        </div>
        <!-- 引用消息 -->
        <div v-if="quotedMessage" class="quoted-message quoted-message-user">
          <div class="quoted-sender">{{ quotedMessage.sender }}</div>
          <div class="quoted-content">{{ quotedMessage.content }}</div>
        </div>
        <div class="bubble-content bubble-user">
          <slot>{{ content }}</slot>
        </div>
      </div>
      <div class="avatar-col avatar-col-user">
        <div class="avatar-circle avatar-student" :style="{ background: learnerPartner.accent }">
          <img
            v-if="learnerPartner.avatar"
            :src="learnerPartner.avatar"
            :alt="learnerPartner.name"
          />
          <span v-else>{{ learnerPartner.name.slice(0, 1) }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.chat-bubble-wrap {
  display: flex;
  gap: 10px;
  margin: 10px 0;
  font-size: 13px;
  align-items: flex-start;

  &.is-user {
    justify-content: flex-end;
  }
}

/* ===== 头像列 ===== */
.avatar-col {
  flex-shrink: 0;
  width: 40px;
}

.avatar-circle {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border: 2px solid #fff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
  background: #f3f4f6;
  transition: all 0.2s;

  &.clickable {
    cursor: pointer;

    &:hover {
      box-shadow: 0 0 0 3px rgba(234, 88, 12, 0.2);
      transform: scale(1.05);
    }
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.avatar-emoji {
  font-size: 20px;
  line-height: 1;
}

.avatar-thinking {
  background: #f3f0ec;
  border-color: #d4c9b8;
  color: #a59786;
}

.thinking-name {
  color: #a59786;
  font-weight: 500;
  font-size: 12.5px;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.avatar-student {
  background: linear-gradient(135deg, #ea5a1a, #d14710);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  border: 2px solid #fff;
}

.avatar-teacher {
  background: linear-gradient(135deg, #b45309, #92400e);
  border-color: #f6e0c8;
}

.avatar-teacher-text {
  color: #fff;
  font-size: 16px;
  font-weight: 800;
}

.teacher-tag {
  background: #fdf1e0 !important;
  color: #b45309 !important;
}

/* ===== 消息体列 ===== */
.body-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: calc(100% - 52px);
}

.body-col-user {
  align-items: flex-end;
  max-width: 70%;
}

/* ===== 元信息行 ===== */
.meta-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  flex-wrap: wrap;

  strong {
    font-weight: 600;
    font-size: 12.5px;
  }
}

.meta-row-user {
  flex-direction: row-reverse;
}

.role-tag {
  padding: 1px 6px;
  border-radius: 999px;
  background: rgba(234, 90, 26, 0.1);
  color: #ea5a1a;
  font-size: 10.5px;
  font-weight: 500;
}

.collab-tag {
  font-size: 10.5px;
  color: #8b7e6e;
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 999px;
}

.time-text {
  font-size: 10.5px;
  color: #b0b0b0;
}

/* ===== 引用消息 ===== */
.quoted-message {
  background: #f8fafc;
  border-left: 3px solid #ea580c;
  padding: 8px 12px;
  border-radius: 0 8px 8px 0;
  margin-bottom: 6px;
  max-width: 100%;
}

.quoted-message-user {
  background: rgba(255, 255, 255, 0.15);
  border-left-color: rgba(255, 255, 255, 0.5);
}

.quoted-sender {
  font-size: 11px;
  font-weight: 600;
  color: #6b7280;
  margin-bottom: 2px;
}

.quoted-message-user .quoted-sender {
  color: rgba(255, 255, 255, 0.8);
}

.quoted-content {
  font-size: 12px;
  color: #4b5563;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quoted-message-user .quoted-content {
  color: rgba(255, 255, 255, 0.9);
}

/* ===== 气泡 ===== */
.bubble-content {
  display: inline-block;
  background: #fff;
  padding: 10px 14px;
  border-radius: 4px 14px 14px 14px;
  border: 1px solid #e5e7eb;
  color: #1f2937;
  line-height: 1.65;
  word-break: break-word;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  max-width: 100%;
}

.bubble-user {
  background: linear-gradient(135deg, #ea5a1a, #d14710);
  color: #fff;
  border: none;
  border-radius: 14px 4px 14px 14px;
  white-space: pre-wrap;
}

/* ===== Agent 问候语后的任务导引 ===== */
.guided-actions {
  display: grid;
  gap: 10px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--agent-color, #f97316) 16%, #e2e8f0);
  border-radius: 12px;
  background: color-mix(in srgb, var(--agent-color, #f97316) 4%, #fff);
}

.guided-actions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.guided-actions-head > span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 12.5px;
  font-weight: 750;
}

.guided-actions-head > span svg {
  color: var(--agent-color, #f97316);
}

.guided-actions-head > small,
.guided-actions-foot {
  color: #64748b;
  font-size: 11px;
}

.guided-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.guided-action-card {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 16px;
  align-items: center;
  gap: 9px;
  min-height: 70px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.92);
  color: #172033;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 180ms ease, background-color 180ms ease, box-shadow 180ms ease;
}

.guided-action-card:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--agent-color, #f97316) 38%, #cbd5e1);
  background: #fff;
  box-shadow: 0 7px 18px rgba(15, 23, 42, 0.08);
}

.guided-action-card:focus-visible {
  outline: 3px solid color-mix(in srgb, var(--agent-color, #f97316) 28%, transparent);
  outline-offset: 2px;
}

.guided-action-card:disabled {
  opacity: 0.52;
  cursor: wait;
}

.guided-action-icon {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: color-mix(in srgb, var(--agent-color, #f97316) 11%, #fff);
  color: var(--agent-color, #f97316);
}

.guided-action-copy {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.guided-action-copy b {
  overflow: hidden;
  color: #0f172a;
  font-size: 12.5px;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.guided-action-copy small {
  display: -webkit-box;
  overflow: hidden;
  color: #64748b;
  font-size: 11px;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.guided-action-arrow {
  color: #94a3b8;
  transition: color 180ms ease;
}

.guided-action-card:hover:not(:disabled) .guided-action-arrow {
  color: var(--agent-color, #f97316);
}

.guided-actions-foot {
  margin: 0;
  line-height: 1.5;
}

.bubble-content.streaming {
  position: relative;
}

.cursor-blink {
  display: inline-block;
  margin-left: 2px;
  animation: blink 1s steps(2) infinite;
  color: #ea5a1a;
  font-weight: 600;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* ===== Markdown 样式 ===== */
.markdown-body {
  :deep(p) {
    margin: 0 0 8px;
    &:last-child { margin-bottom: 0; }
  }

  :deep(h1),
  :deep(h2),
  :deep(h3) {
    margin: 12px 0 6px;
    font-weight: 600;
    line-height: 1.4;
  }

  :deep(h1) { font-size: 16px; }
  :deep(h2) { font-size: 15px; }
  :deep(h3) { font-size: 14px; }

  :deep(ul),
  :deep(ol) {
    margin: 4px 0 8px;
    padding-left: 20px;
  }

  :deep(li) {
    margin: 2px 0;
  }

  :deep(code) {
    background: #f3f4f6;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, monospace;
    font-size: 12px;
    color: #d6336c;
  }

  :deep(pre) {
    background: #1e293b;
    color: #e2e8f0;
    padding: 10px 12px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 8px 0;
    font-size: 12px;
    line-height: 1.5;

    code {
      background: none;
      color: inherit;
      padding: 0;
    }
  }

  :deep(blockquote) {
    border-left: 3px solid #ea5a1a;
    margin: 8px 0;
    padding: 4px 12px;
    background: #fff7f0;
    color: #6b4f2f;
    border-radius: 0 6px 6px 0;
  }

  :deep(table) {
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 12px;

    th,
    td {
      border: 1px solid #e5e7eb;
      padding: 6px 10px;
    }

    th {
      background: #f9fafb;
      font-weight: 600;
    }
  }

  :deep(a) {
    color: #ea5a1a;
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }

  /* ===== KaTeX 数学公式 ===== */
  :deep(.katex) {
    font-size: 1.05em;
  }

  :deep(.katex-display) {
    margin: 8px 0;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 2px 0;
  }

  :deep(.katex-display > .katex) {
    font-size: 1.15em;
  }

  :deep(.katex-block) {
    margin: 10px 0;
    text-align: center;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 4px 0;
  }
}

/* ===== AI 工作卡片视觉升级 ===== */
.chat-bubble-wrap {
  gap: 12px;
  margin: 14px 0;
}

.avatar-col {
  width: 44px;
}

.avatar-circle {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  border-color: #fff;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.09);
}

.avatar-circle.clickable:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.13), 0 0 0 3px rgba(249, 115, 22, 0.14);
}

.body-col.agent-card {
  gap: 8px;
  max-width: min(820px, calc(100% - 56px));
  padding: 13px 14px 14px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid var(--agent-color, #f97316);
  border-radius: 14px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.92)),
    #fff;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.06);
}

.meta-row {
  align-items: center;
  gap: 8px;
}

.meta-row strong {
  color: #0f172a !important;
  font-size: 13px;
}

.role-tag {
  background: color-mix(in srgb, var(--agent-color, #f97316) 12%, white);
  color: var(--agent-color, #f97316);
  border: 1px solid color-mix(in srgb, var(--agent-color, #f97316) 18%, white);
  font-weight: 700;
}

.collab-tag {
  background: #eef6ff;
  color: #2563eb;
  border: 1px solid #dbeafe;
}

.time-text {
  margin-left: auto;
  color: #94a3b8;
}

.bubble-content {
  display: block;
  width: 100%;
  padding: 12px 14px;
  border-radius: 12px;
  border-color: #dbe4ef;
  background: #fff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
  color: #172033;
  line-height: 1.72;
}

.bubble-user {
  width: auto;
  max-width: 620px;
  padding: 11px 14px;
  border-radius: 14px 6px 14px 14px;
  background: linear-gradient(135deg, #f97316, #ea580c);
  box-shadow: 0 10px 24px rgba(234, 88, 12, 0.2);
}

.body-col-user {
  max-width: min(680px, 72%);
}

.quoted-message {
  border-left-color: var(--agent-color, #f97316);
  background: #f8fafc;
}

.markdown-body :deep(pre) {
  border: 1px solid #1e293b;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.14);
}

.markdown-body :deep(table) {
  width: 100%;
}

@media (max-width: 720px) {
  .body-col.agent-card,
  .body-col-user {
    max-width: calc(100% - 52px);
  }

  .guided-action-grid {
    grid-template-columns: 1fr;
  }

  .guided-actions-head {
    align-items: flex-start;
    flex-direction: column;
    gap: 3px;
  }
}

/* ============================================================
 * 气泡内联附件 —— 让 code/quiz/mindmap 直接在消息里预览
 * ============================================================ */
.bubble-attachments {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.att-card {
  border: 1px solid #e7e2da;
  border-radius: 10px;
  background: #fbfaf7;
  overflow: hidden;
}
.att-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #ece8e1;
  background: #f6f4ef;
}
.att-head b { font-size: 13.5px; color: #24211d; }
.att-head small { color: #918b82; font-size: 11.5px; letter-spacing: .05em; }

.att-code { border: 1px solid #24273a; background: #1e1e2e; overflow: hidden; }
.att-code .att-head-code {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #2a2b3c;
  background: #24273a;
}
.att-code .code-title { display: inline-flex; align-items: center; gap: 8px; }
.att-code .code-title b { color: #e9eef7; font-size: 13.5px; font-weight: 600; letter-spacing: 0.01em; }
.att-code .code-title .win-btn {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}
.att-code .code-title .win-btn.red { background: #ff5f56; box-shadow: inset 0 0 0 1px rgba(0,0,0,.1); }
.att-code .code-title .win-btn.yellow { background: #ffbd2e; box-shadow: inset 0 0 0 1px rgba(0,0,0,.1); }
.att-code .code-title .win-btn.green { background: #27c93f; box-shadow: inset 0 0 0 1px rgba(0,0,0,.1); }
.att-code .att-head-code small { color: #8b8fa8; font-size: 11px; font-weight: 600; letter-spacing: 0.12em; font-family: "SF Mono", Consolas, monospace; }
.att-code .code-head-actions { display: inline-flex; align-items: center; gap: 10px; }
.att-code .copy-code {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  padding: 4px 8px;
  border: 1px solid #45485e;
  border-radius: 6px;
  background: #2d3044;
  color: #d8dced;
  font-size: 11px;
  cursor: pointer;
  transition: background-color 160ms ease-out, border-color 160ms ease-out;
}
.att-code .copy-code:hover { background: #383c54; border-color: #5c617d; }
.att-code .copy-code:focus-visible { outline: 2px solid #89b4fa; outline-offset: 2px; }
.att-code .code-block {
  margin: 0;
  padding: 14px 0;
  background: #1e1e2e;
  color: #cdd6f4;
  font-family: "JetBrains Mono", "Fira Code", "SF Mono", Consolas, "Cascadia Code", "PingFang SC", monospace;
  font-size: 12.5px;
  line-height: 1.72;
  overflow-x: auto;
  white-space: pre;
  tab-size: 4;
  border-radius: 0;
}
.att-code .code-line {
  display: grid;
  grid-template-columns: 48px minmax(max-content, 1fr);
  min-height: 22px;
  padding-right: 18px;
}
.att-code .code-line:hover { background: #252638; }
.att-code .line-number {
  padding-right: 14px;
  color: #585b70;
  text-align: right;
  user-select: none;
}
.att-code .code-block code {
  display: block;
  min-width: max-content;
  background: transparent;
  color: inherit;
  font-family: inherit;
}
/* Catppuccin Mocha 灵感的浅色高亮方案 */
.att-code :deep(.c-kw)      { color: #cba6f7; font-weight: 500; }  /* keywords: purple */
.att-code :deep(.c-str)     { color: #a6e3a1; }                    /* string: green */
.att-code :deep(.c-num)     { color: #fab387; }                    /* number: peach */
.att-code :deep(.c-comment) { color: #6c7086; font-style: italic; } /* comment: overlay */
.att-code :deep(.c-dec)     { color: #f9e2af; }                    /* decorator: yellow */
.att-code .code-stdout {
  padding: 8px 14px;
  border-top: 1px solid #313246;
  background: #202131;
  font-size: 12px;
}
.att-code .code-stdout summary { color: #b4b9d2; cursor: pointer; }
.att-code .code-stdout pre {
  margin: 6px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: #181927;
  color: #a6e3a1;
  font-family: "SF Mono", Consolas, monospace;
  font-size: 11.5px;
  white-space: pre-wrap;
}

.att-mindmap .mm-img { display: block; width: 100%; height: auto; padding: 12px 14px; background: #fff; }
.att-mindmap .mm-outline {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  padding: 12px 14px;
  background: #fff;
}
.att-mindmap .mm-branch { padding: 10px 12px; border: 1px solid #e7e2da; border-radius: 8px; background: #fbfaf7; }
.att-mindmap .mm-branch b { display: inline-block; padding: 3px 9px; border-radius: 999px; background: #fff1e8; color: #b53f0a; font-size: 12.5px; font-weight: 700; }
.att-mindmap .mm-branch ul { margin: 7px 0 0 18px; padding: 0; color: #514c45; font-size: 12.5px; line-height: 1.7; }
.att-mindmap .mm-code {
  padding: 8px 14px;
  border-top: 1px solid #ece8e1;
  font-size: 12px;
}
.att-mindmap .mm-code summary { color: #68635b; cursor: pointer; }
.att-mindmap .mm-code pre { margin: 6px 0 0; padding: 8px 10px; border-radius: 6px; background: #f6f4ef; color: #24211d; font-size: 11.5px; white-space: pre-wrap; }

.eval-head-title,
.media-head-title { display: inline-flex; align-items: center; gap: 7px; color: #24211d; }
.att-evaluation { background: #fff; }
.att-evaluation .eval-body { display: grid; gap: 14px; padding: 14px; }
.eval-overall { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 7px 12px; }
.eval-overall span { color: #514c45; font-size: 12.5px; font-weight: 600; }
.eval-overall strong { color: #0f766e; font-size: 18px; font-variant-numeric: tabular-nums; }
.eval-overall .eval-track { grid-column: 1 / -1; }
.eval-track { height: 7px; overflow: hidden; border-radius: 999px; background: #e7eceb; }
.eval-track i { display: block; height: 100%; border-radius: inherit; background: #0f8a7d; }
.eval-dimensions { display: grid; gap: 9px; padding-top: 12px; border-top: 1px solid #ece8e1; }
.eval-dimension-row { display: grid; grid-template-columns: minmax(90px, 150px) minmax(100px, 1fr) 40px; align-items: center; gap: 10px; }
.eval-dimension-row span { color: #514c45; font-size: 12px; }
.eval-dimension-row b { color: #24211d; font-size: 11.5px; text-align: right; font-variant-numeric: tabular-nums; }
.eval-figures { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.eval-figures figure { margin: 0; overflow: hidden; border: 1px solid #e7e2da; border-radius: 8px; background: #fff; }
.eval-figures img { display: block; width: 100%; height: auto; background: #fff; }
.eval-figures figcaption { display: grid; gap: 4px; padding: 10px 12px; border-top: 1px solid #ece8e1; }
.eval-figures figcaption b { color: #24211d; font-size: 12.5px; }
.eval-figures figcaption span { color: #625c54; font-size: 11.5px; line-height: 1.6; }
.eval-evidence-note { margin: 0; padding: 9px 10px; border-radius: 6px; background: #fff7e8; color: #7a4b08; font-size: 12px; line-height: 1.6; }

.att-media { background: #fff; }
.att-media .media-body { display: grid; gap: 9px; padding: 12px 14px; }
.att-media audio,
.att-media video { display: block; width: 100%; }
.att-media video { max-height: 420px; background: #111827; }
.att-media .media-body p { margin: 0; color: #625c54; font-size: 12px; line-height: 1.6; }

.att-resource {
  padding-bottom: 12px;
  background: #fff;
}
.att-resource p {
  margin: 12px 14px 10px;
  color: #514c45;
  font-size: 12.5px;
  line-height: 1.6;
}
.att-resource a {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  margin-inline: 14px;
  padding-inline: 14px;
  border-radius: 8px;
  background: #ea5a1a;
  color: #fff;
  font-size: 12.5px;
  font-weight: 700;
  text-decoration: none;
}
.att-resource a:hover { background: #c8480f; }
.att-resource a:focus-visible { outline: 3px solid rgba(234, 90, 26, .28); outline-offset: 2px; }

.att-quiz .quiz-list { display: flex; flex-direction: column; gap: 8px; padding: 12px 14px; background: #fff; }
.att-quiz .quiz-question { border: 1px solid #e7e2da; border-radius: 8px; background: #fbfaf7; overflow: hidden; }
.att-quiz .quiz-question[open] { background: #fff; border-color: #d6cec2; }
.att-quiz .quiz-question > summary {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  color: #24211d;
  cursor: pointer;
  list-style: none;
}
.att-quiz .quiz-question > summary::-webkit-details-marker { display: none; }
.att-quiz .q-index { flex: 0 0 auto; color: #9a8f82; font-family: "SF Mono", Consolas, monospace; font-size: 11px; font-weight: 700; line-height: 22px; }
.att-quiz .q-summary-main { min-width: 0; display: flex; flex-direction: column; gap: 4px; }
.att-quiz .q-badges { display: flex; flex-wrap: wrap; gap: 5px; }
.att-quiz .q-stem { font-size: 13px; font-weight: 600; line-height: 1.6; }
.att-quiz .q-type,
.att-quiz .q-difficulty,
.att-quiz .q-bloom { display: inline-flex; padding: 1px 7px; border-radius: 999px; font-size: 10.5px; font-style: normal; font-weight: 700; }
.att-quiz .q-type { background: #f1efff; color: #5f4fc7; }
.att-quiz .q-difficulty { background: #eef2f7; color: #566174; }
.att-quiz .q-difficulty.is-hard { background: #fff0ed; color: #b83c25; }
.att-quiz .q-difficulty.is-easy { background: #eaf8ef; color: #287548; }
.att-quiz .q-bloom { background: #eef6ff; color: #2867a8; }
.att-quiz .q-detail { padding: 0 12px 12px 48px; }
.att-quiz .q-options { margin: 2px 0 8px; padding-left: 18px; color: #514c45; font-size: 12.5px; line-height: 1.75; }
.att-quiz .q-code-brief { display: flex; flex-direction: column; gap: 5px; margin: 8px 0; padding: 9px 10px; border-radius: 6px; background: #f3f4f6; color: #44403c; font-size: 12px; }
.att-quiz .q-answer { display: grid; gap: 6px; margin-top: 8px; padding-top: 9px; border-top: 1px solid #ece8e1; }
.att-quiz .q-answer p { margin: 0; color: #24211d; font-size: 12.5px; line-height: 1.65; }
.att-quiz .q-answer b { display: block; margin-bottom: 2px; color: #b53f0a; font-size: 11px; }

@media (max-width: 640px) {
  .att-code .att-head-code { align-items: flex-start; gap: 8px; }
  .att-code .code-title b { max-width: 22ch; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .att-quiz .q-detail { padding-left: 12px; }
  .eval-dimension-row { grid-template-columns: minmax(80px, 120px) minmax(80px, 1fr) 36px; gap: 7px; }
  .eval-figures { grid-template-columns: 1fr; }
}
</style>
