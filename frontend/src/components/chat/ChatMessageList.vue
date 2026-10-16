/**
 * ChatMessageList · Plan D · 4.2 — 对话消息列表
 *
 * 数据契约：
 *   messages: Array<{
 *     id: string;
 *     role: "user" | "assistant";
 *     content: string;
 *     agentKinds?: AvatarKind[];
 *     primaryKind?: AvatarKind;
 *     timestamp: number;
 *     isStreaming?: boolean;
 *     isThinking?: boolean;     // 显示"思考中"占位
 *   }>
 */
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Bot, Loader2 } from "lucide-vue-next";

import ChatBubble, {
  type ChatAttachment,
  type ChatSuggestedAction,
} from "@/components/shared/ChatBubble.vue";
import type { AvatarKind } from "@/constants/agentAvatars";

interface QuotedMessage {
  id: string;
  sender: string;
  senderAvatar?: string;
  content: string;
  timestamp: number;
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
  quotedMessage?: QuotedMessage;
  senderType?: "agent" | "teacher";
  senderName?: string;
  /** 消息气泡里的内联附件（code/quiz/mindmap） */
  attachments?: ChatAttachment[];
  /** Agent 问候语后的任务导引卡片 */
  suggestedActions?: ChatSuggestedAction[];
}

const props = withDefaults(
  defineProps<{
    messages: ChatMessage[];
    loadingHistory?: boolean;
    suggestionsDisabled?: boolean;
  }>(),
  {
    loadingHistory: false,
    suggestionsDisabled: false,
  },
);

const emit = defineEmits<{
  (e: 'avatar-click', agentKey: string): void;
  (e: 'suggestion-click', action: ChatSuggestedAction): void;
}>();

const scrollerRef = ref<HTMLDivElement | null>(null);

const hasContent = computed(() => props.messages.length > 0);

// 自动滚到底部
watch(
  () => props.messages.length,
  () => {
    void nextTick(() => {
      if (scrollerRef.value) {
        scrollerRef.value.scrollTop = scrollerRef.value.scrollHeight;
      }
    });
  },
  { flush: "post" },
);

// 流式更新也滚到底
watch(
  () =>
    props.messages
      .map((m) => (m.isStreaming ? m.content.length : 0))
      .reduce((a, b) => a + b, 0),
  () => {
    void nextTick(() => {
      if (scrollerRef.value) {
        scrollerRef.value.scrollTop = scrollerRef.value.scrollHeight;
      }
    });
  },
);
</script>

<template>
  <div ref="scrollerRef" class="chat-message-list">
    <div v-if="loadingHistory" class="loading">
      <Loader2 :size="16" class="spin" /> 加载历史消息...
    </div>
    <div v-else-if="!hasContent" class="empty">
      <Bot :size="32" />
      <p>开始一次新的对话，让 6 个 Agent 协作帮你解答。</p>
      <small>提示：回车发送，Shift+Enter 换行</small>
    </div>
    <template v-else>
      <ChatBubble
        v-for="m in messages"
        :key="m.id"
        :role="m.role"
        :content="m.content"
        :agent-kinds="m.agentKinds"
        :primary-kind="m.primaryKind"
        :timestamp="m.timestamp"
        :is-streaming="m.isStreaming"
        :quoted-message="m.quotedMessage"
        :sender-type="m.senderType"
        :sender-name="m.senderName"
        :attachments="m.attachments"
        :suggested-actions="m.suggestedActions"
        :suggestions-disabled="suggestionsDisabled"
        @avatar-click="(key: string) => emit('avatar-click', key)"
        @suggestion-click="(action: ChatSuggestedAction) => emit('suggestion-click', action)"
      />
    </template>
  </div>
</template>

<style scoped lang="scss">
.chat-message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background:
    radial-gradient(circle at 8% 0%, rgba(249, 115, 22, 0.08), transparent 26%),
    radial-gradient(circle at 88% 18%, rgba(37, 99, 235, 0.08), transparent 24%),
    #f8fafc;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
}

.empty {
  margin: auto;
  max-width: 360px;
  padding: 28px;
  text-align: center;
  color: #475569;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  border: 1px dashed #cbd5e1;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.78);

  p { margin: 4px 0 0; font-size: 13px; }
  small { font-size: 11.5px; color: #94a3b8; }
}

.loading {
  margin: auto;
  font-size: 12.5px;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
