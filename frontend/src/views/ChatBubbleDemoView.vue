<script setup lang="ts">
/**
 * ChatBubble Demo · Plan D · 3.2
 *
 * 一个最小可运行的演示页，用于验证 ChatBubble 组件 + AGENT_AVATARS 映射。
 * Phase 2 当 Vue 原生 chat 视图接入时，把 <ChatBubble /> 直接复用即可。
 */
import { ref } from "vue";
import { Send, Trash2 } from "lucide-vue-next";

import ChatBubble from "@/components/shared/ChatBubble.vue";
import type { AvatarKind } from "@/constants/agentAvatars";

interface DemoMessage {
  role: "user" | "assistant";
  content: string;
  agentKinds?: AvatarKind[];
  primaryKind?: AvatarKind;
  timestamp: number;
  isStreaming?: boolean;
}

const now = Date.now();
const messages = ref<DemoMessage[]>([
  {
    role: "user",
    content: "反向传播算法到底是怎么算梯度的？我看了三遍还是没懂。",
    timestamp: now - 60_000,
  },
  {
    role: "assistant",
    content:
      "我们让 3 个 Agent 一起拆这个问题：智狐先拆 BP 的四步流水线；智灵接着用链式法则一步步推；球球最后做事实校验。",
    agentKinds: ["planner", "tutor", "safety"],
    primaryKind: "tutor",
    timestamp: now - 55_000,
  },
  {
    role: "assistant",
    content:
      "先把 BP 看成一个流水线：前向 → 计算 loss → 反向求梯度 → 更新参数。每一步都是链式法则的局部应用。",
    agentKinds: ["tutor"],
    primaryKind: "tutor",
    timestamp: now - 50_000,
  },
  {
    role: "user",
    content: "那「链式法则」具体怎么写？",
    timestamp: now - 40_000,
  },
  {
    role: "assistant",
    content:
      "先记住一句话：复合函数的导数是各层导数的乘积。所以 BP 就是把这个乘积按层拆开，从最后一层往前推。每层的梯度只依赖 (1) 该层输入、(2) 该层参数、(3) 后面传回来的梯度。",
    agentKinds: ["tutor", "content"],
    primaryKind: "content",
    timestamp: now - 30_000,
    isStreaming: true,
  },
]);

const inputText = ref("");

function send() {
  const text = inputText.value.trim();
  if (!text) return;
  messages.value.push({
    role: "user",
    content: text,
    timestamp: Date.now(),
  });
  inputText.value = "";
  // 模拟 assistant 回复
  setTimeout(() => {
    messages.value.push({
      role: "assistant",
      content: "这是模拟回复 — 真实环境下会接 SSE 流。",
      agentKinds: ["tutor"],
      primaryKind: "tutor",
      timestamp: Date.now(),
    });
  }, 600);
}

function clear() {
  messages.value = [];
}
</script>

<template>
  <div class="chat-bubble-demo">
    <header class="demo-head">
      <h2>ChatBubble 演示 · Plan D · 3.2</h2>
      <p class="demo-sub">
        6 个 Agent 头像映射（AGENT_AVATARS）+ 多 Agent 协作头像栈 + 流式光标。
        Phase 2 当 Vue 原生 chat 接 SSE 时，直接复用 ChatBubble 即可。
      </p>
      <button type="button" class="ghost-btn" @click="clear">
        <Trash2 :size="13" />清空
      </button>
    </header>

    <div class="demo-stage">
      <ChatBubble
        v-for="(m, i) in messages"
        :key="i"
        :role="m.role"
        :content="m.content"
        :agent-kinds="m.agentKinds"
        :primary-kind="m.primaryKind"
        :timestamp="m.timestamp"
        :is-streaming="m.isStreaming"
      />
      <p v-if="!messages.length" class="empty-hint">
        还没有消息，下方输入框写一句试试。
      </p>
    </div>

    <footer class="demo-input">
      <input
        v-model="inputText"
        placeholder="输入学生问题，回车模拟发送"
        @keydown.enter="send"
      />
      <button type="button" class="primary-btn" :disabled="!inputText.trim()" @click="send">
        <Send :size="14" />发送
      </button>
    </footer>
  </div>
</template>

<style scoped lang="scss">
.chat-bubble-demo {
  max-width: 720px;
  margin: 24px auto;
  padding: 16px;
  background: var(--paper, #fdf6e3);
  border: 1px solid var(--border-soft, #e5d4be);
  border-radius: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.demo-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-bottom: 1px dashed var(--border-soft, #e5d4be);
  padding-bottom: 8px;

  h2 {
    margin: 0;
    font-size: 18px;
    color: var(--ink, #3d3830);
  }
  .demo-sub {
    margin: 0;
    font-size: 12.5px;
    color: var(--muted, #6b4f2f);
    line-height: 1.6;
  }
}

.demo-stage {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 240px;
}

.demo-input {
  display: flex;
  gap: 8px;
  border-top: 1px dashed var(--border-soft, #e5d4be);
  padding-top: 10px;

  input {
    flex: 1;
    height: 36px;
    padding: 0 12px;
    border-radius: 10px;
    border: 1px solid var(--border-soft, #e5d4be);
    background: #fff;
    font-size: 13px;
  }
}

.empty-hint {
  padding: 20px;
  text-align: center;
  color: var(--muted, #6b4f2f);
  font-size: 13px;
}

.ghost-btn {
  align-self: flex-end;
  background: transparent;
  border: 1px solid var(--border-soft, #e5d4be);
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #ea5a1a;
  color: #fff;
  border: 0;
  border-radius: 10px;
  padding: 0 14px;
  height: 36px;
  font-size: 13px;
  cursor: pointer;

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
</style>