/**
 * ChatInput · Plan D · 4.2 — 对话输入框组件
 *
 * 数据契约：纯受控组件，emit("send", message) 由父组件接 SSE 流
 *
 * 群聊工具栏：@ 提及 / 图片 / 文件 / 表情 / 代码块
 */
<script setup lang="ts">
import { ref, watch } from "vue";
import {
  AtSign,
  Code2,
  FileText,
  Image,
  Paperclip,
  Send,
  Smile,
  Square,
  X,
} from "lucide-vue-next";

const props = withDefaults(
  defineProps<{
    placeholder?: string;
    disabled?: boolean;
    streaming?: boolean;
    prefill?: string;
  }>(),
  {
    placeholder: "输入消息，回车发送（Shift+Enter 换行）",
    disabled: false,
    streaming: false,
    prefill: "",
  },
);

const emit = defineEmits<{
  (e: "send", message: string): void;
  (e: "stop"): void;
}>();

const text = ref("");

// 预填文本（从外部传入时自动填充输入框）
watch(
  () => props.prefill,
  (v) => {
    if (v && !text.value) {
      text.value = v;
    }
  },
  { immediate: true },
);

// 工具栏状态
const showEmojiPicker = ref(false);
const attachments = ref<{ name: string; type: string }[]>([]);

// 表情列表
const emojis = [
  "😀", "😄", "😁", "😊", "😍", "🤔", "😴", "😭",
  "👍", "👎", "👏", "🙌", "💪", "🎉", "🔥", "✨",
  "📚", "✏️", "💡", "🎯", "🧠", "💻", "📝", "🔍",
];

// @ 提及列表
const mentionList = [
  { key: "planner", name: "智狐", title: "规划伙伴" },
  { key: "tutor", name: "智灵", title: "讲解伙伴" },
  { key: "content", name: "阿匠", title: "资源伙伴" },
  { key: "quiz", name: "小龙", title: "练习伙伴" },
  { key: "evaluation", name: "团团", title: "评估伙伴" },
  { key: "safety", name: "球球", title: "守护伙伴" },
  { key: "all", name: "全体成员", title: "通知所有人" },
];
const showMentionList = ref(false);

// 当流式完成 → 自动清空输入
watch(
  () => props.streaming,
  (s) => {
    if (!s) text.value = "";
  },
);

function handleSend() {
  const msg = text.value.trim();
  if (!msg || props.disabled) return;
  emit("send", msg);
}

function handleKeydown(ev: KeyboardEvent) {
  // @ 触发提及列表
  if (ev.key === "@" || (ev.key === "2" && ev.shiftKey)) {
    showMentionList.value = true;
  }
  if (ev.key === "Escape") {
    showMentionList.value = false;
    showEmojiPicker.value = false;
  }
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    handleSend();
  }
}

function handleStop() {
  emit("stop");
}

// @ 提及
function toggleMention() {
  showMentionList.value = !showMentionList.value;
  if (showMentionList.value) {
    text.value += text.value.endsWith(" ") || text.value === "" ? "@" : " @";
  }
}

function insertMention(m: { key: string; name: string }) {
  // 移除末尾的 @
  text.value = text.value.replace(/@\s*$/, "");
  text.value += `@${m.name} `;
  showMentionList.value = false;
}

// 表情
function toggleEmoji() {
  showEmojiPicker.value = !showEmojiPicker.value;
  showMentionList.value = false;
}

function insertEmoji(emoji: string) {
  text.value += emoji;
  showEmojiPicker.value = false;
}

// 文件 / 图片（模拟）
function handleFileSelect(e: Event, type: "file" | "image") {
  const input = e.target as HTMLInputElement;
  if (!input.files?.length) return;
  const file = input.files[0];
  attachments.value.push({
    name: file.name,
    type: type === "image" ? "image" : "file",
  });
  // 重置 input，允许重复选择同一文件
  input.value = "";
}

function removeAttachment(idx: number) {
  attachments.value.splice(idx, 1);
}

// 代码块
function insertCodeBlock() {
  text.value += "\n```\n\n```\n";
}
</script>

<template>
  <div class="chat-input-wrap" :class="{ disabled }">
    <!-- 附件预览 -->
    <div v-if="attachments.length" class="attachment-list">
      <div
        v-for="(att, idx) in attachments"
        :key="idx"
        class="attachment-chip"
      >
        <component :is="att.type === 'image' ? Image : FileText" :size="13" />
        <span>{{ att.name }}</span>
        <button type="button" class="att-remove" @click="removeAttachment(idx)">
          <X :size="12" />
        </button>
      </div>
    </div>

    <!-- @ 提及浮层 -->
    <transition name="pop">
      <div v-if="showMentionList" class="mention-popup">
        <div class="popup-head">选择要 @ 的成员</div>
        <div class="mention-list">
          <button
            v-for="m in mentionList"
            :key="m.key"
            type="button"
            class="mention-item"
            @click="insertMention(m)"
          >
            <span class="mention-at">@</span>
            <b>{{ m.name }}</b>
            <small>{{ m.title }}</small>
          </button>
        </div>
      </div>
    </transition>

    <!-- 表情面板 -->
    <transition name="pop">
      <div v-if="showEmojiPicker" class="emoji-popup">
        <div class="popup-head">表情</div>
        <div class="emoji-grid">
          <button
            v-for="emoji in emojis"
            :key="emoji"
            type="button"
            class="emoji-item"
            @click="insertEmoji(emoji)"
          >
            {{ emoji }}
          </button>
        </div>
      </div>
    </transition>

    <!-- 工具栏 -->
    <div class="chat-toolbar">
      <button type="button" class="tool-btn" title="@ 提及" @click="toggleMention">
        <AtSign :size="17" />
      </button>
      <label class="tool-btn" title="发送图片">
        <Image :size="17" />
        <input
          type="file"
          accept="image/*"
          hidden
          :disabled="disabled"
          @change="(e) => handleFileSelect(e, 'image')"
        />
      </label>
      <label class="tool-btn" title="发送文件">
        <Paperclip :size="17" />
        <input
          type="file"
          hidden
          :disabled="disabled"
          @change="(e) => handleFileSelect(e, 'file')"
        />
      </label>
      <button type="button" class="tool-btn" title="代码块" @click="insertCodeBlock">
        <Code2 :size="17" />
      </button>
      <button type="button" class="tool-btn" title="表情" @click="toggleEmoji">
        <Smile :size="17" />
      </button>
    </div>

    <!-- 输入区 -->
    <textarea
      v-model="text"
      class="chat-input"
      :placeholder="placeholder"
      :disabled="disabled"
      rows="2"
      @keydown="handleKeydown"
    />

    <!-- 底部操作栏 -->
    <div class="chat-input-actions">
      <span v-if="streaming" class="streaming-tag">流式中...</span>
      <button
        v-if="streaming"
        type="button"
        class="ghost-btn stop-btn"
        @click="handleStop"
      >
        <Square :size="13" />停止
      </button>
      <button
        v-else
        type="button"
        class="primary-btn send-btn"
        :disabled="disabled || !text.trim()"
        @click="handleSend"
      >
        <Send :size="14" />发送
      </button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chat-input-wrap {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid #dbe4ef;
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.94)),
    #fff;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
  position: relative;
}

/* ===== 工具栏 ===== */
.chat-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eef2f7;
}

.tool-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover {
    background: #fff7ed;
    border-color: rgba(249, 115, 22, 0.22);
    color: #ea580c;
  }

  &:active {
    transform: scale(0.92);
  }

  /* label 包裹 file input 时 */
  input[type="file"] {
    display: none;
  }
}

/* ===== 附件预览 ===== */
.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 6px;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px 4px 10px;
  border-radius: 8px;
  background: #f0f7ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;

  span {
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.att-remove {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 0;
  border-radius: 4px;
  background: rgba(29, 78, 216, 0.1);
  color: #1d4ed8;
  cursor: pointer;

  &:hover {
    background: rgba(29, 78, 216, 0.2);
  }
}

/* ===== 弹出层通用 ===== */
.popup-head {
  font-size: 11.5px;
  color: #9ca3af;
  padding: 8px 12px 6px;
  border-bottom: 1px solid #f3f4f6;
}

/* ===== @ 提及 ===== */
.mention-popup {
  position: absolute;
  bottom: 100%;
  left: 12px;
  margin-bottom: 4px;
  width: 240px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.1);
  z-index: 50;
  overflow: hidden;
}

.mention-list {
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  text-align: left;
  transition: background 0.1s ease;

  &:hover {
    background: #f3f4f6;
  }

  .mention-at {
    color: #ea5a1a;
    font-weight: 700;
    font-size: 14px;
  }

  b {
    font-size: 13px;
    color: #1f2937;
    font-weight: 600;
  }

  small {
    font-size: 11px;
    color: #9ca3af;
    margin-left: auto;
  }
}

/* ===== 表情 ===== */
.emoji-popup {
  position: absolute;
  bottom: 100%;
  left: 12px;
  margin-bottom: 4px;
  width: 280px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.1);
  z-index: 50;
  overflow: hidden;
}

.emoji-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: 6px;
}

.emoji-item {
  display: grid;
  place-items: center;
  width: 100%;
  aspect-ratio: 1;
  border: 0;
  border-radius: 6px;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  transition: background 0.1s ease;

  &:hover {
    background: #f3f4f6;
    transform: scale(1.15);
  }
}

/* ===== 输入区 ===== */
.chat-input {
  border: 0;
  outline: 0;
  resize: none;
  background: transparent;
  min-height: 44px;
  font-size: 14px;
  color: #172033;
  line-height: 1.58;
  font-family: inherit;

  &:disabled {
    color: #9ca3af;
    cursor: not-allowed;
  }
}

/* ===== 底部操作 ===== */
.chat-input-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
  min-height: 34px;
}

.streaming-tag {
  font-size: 11px;
  color: #ea5a1a;
  font-weight: 500;
  margin-right: auto;
  animation: streaming-pulse 1.4s ease-in-out infinite;
}

@keyframes streaming-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

.primary-btn.send-btn,
.ghost-btn.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 10px;
  padding: 0 16px;
  height: 34px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.primary-btn.send-btn {
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
  box-shadow: 0 10px 20px rgba(234, 88, 12, 0.22);

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.ghost-btn.stop-btn {
  background: #fff;
  border: 1px solid #fecaca;
  color: #dc2626;
}

/* ===== 弹出动画 ===== */
.pop-enter-active,
.pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
