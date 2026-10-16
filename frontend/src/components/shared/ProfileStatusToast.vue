<script setup lang="ts">
/**
 * ProfileStatusToast · Plan D · 2.3
 * 监听 SSE profile_status 事件并弹出 Toast
 *
 * Phase 2：当 Vue 原生 chat 接 SSE 时挂到 AppShell；当前对话在 React iframe，
 * 所以组件先建好不挂。
 */
import { ref } from "vue";
import { onBeforeUnmount, onMounted } from "vue";

import { streamChat } from "@/api/chat";

const message = ref<string>("");
const visible = ref(false);
let abortController: AbortController | null = null;

function showToast(text: string, ms = 3000) {
  message.value = text;
  visible.value = true;
  setTimeout(() => (visible.value = false), ms);
}

function start() {
  abortController = streamChat(
    {
      message: "我会一直在这里, 继续聊吧",
    },
    {
      onProfileStatus: (payload) => {
        const status = payload?.status;
        if (status === "success") {
          showToast(
            `已更新画像: ${
              payload.dimensions_count
                ? `${payload.dimensions_count} 个维度`
                : "你的学习风格"
            }`,
          );
        } else if (status === "json_parse_failed") {
          showToast("画像提取时格式不规范, 下轮对话会自动重试");
        }
      },
    },
  );
}

onMounted(() => {
  // 不主动 start — 等调用方挂载并触发
});

onBeforeUnmount(() => {
  abortController?.abort();
});
</script>

<template>
  <transition name="profile-toast">
    <div v-if="visible" class="profile-status-toast" role="status">
      <span class="emoji">📋</span>
      <span>{{ message }}</span>
    </div>
  </transition>
</template>

<style scoped lang="scss">
.profile-status-toast {
  position: fixed;
  top: 24px;
  right: 24px;
  background: rgba(254, 243, 199, 0.95);
  border: 1px solid rgba(217, 119, 6, 0.3);
  border-radius: 10px;
  padding: 10px 16px;
  font-size: 13px;
  color: #4b3414;
  z-index: 1000;
  box-shadow: 0 8px 22px rgba(78, 55, 34, 0.12);
}

.profile-toast-enter-active,
.profile-toast-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.profile-toast-enter-from,
.profile-toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
