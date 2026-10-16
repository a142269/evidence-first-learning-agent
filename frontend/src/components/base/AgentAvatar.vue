<script setup lang="ts">
import { computed } from "vue";

import type { AgentKind, AgentMood } from "./agentTypes";

const props = withDefaults(
  defineProps<{
    kind: AgentKind;
    size?: number | string;
    mood?: AgentMood;
    animated?: boolean;
    alt?: string;
  }>(),
  {
    size: 72,
    mood: "idle",
    animated: false,
    alt: "",
  },
);

const avatarMap: Record<AgentKind, string> = {
  planner: "/integrated-map/avatars/zhihu.png",
  content: "/integrated-map/avatars/ajiang.png",
  tutor: "/integrated-map/avatars/zhiling.png",
  safety: "/integrated-map/avatars/qiuqiu.png",
  evaluation: "/integrated-map/avatars/tuantuan.png",
  quiz: "/integrated-map/avatars/xiaolong.png",
  learner: "/integrated-map/avatars/zhiling.png",
};

const avatarStyle = computed(() => {
  const size = typeof props.size === "number" ? `${props.size}px` : props.size;
  return {
    "--agent-avatar-size": size,
  };
});
</script>

<template>
  <span
    class="agent-avatar"
    :class="[`agent-avatar--${kind}`, `agent-avatar--${mood}`, { 'agent-avatar--animated': animated }]"
    :style="avatarStyle"
  >
    <img :src="avatarMap[kind]" :alt="alt" />
  </span>
</template>

<style scoped lang="scss">
.agent-avatar {
  display: inline-grid;
  place-items: center;
  width: var(--agent-avatar-size);
  height: var(--agent-avatar-size);
  border-radius: 999px;
  background:
    radial-gradient(circle at 50% 42%, rgba(255, 255, 255, 0.95), rgba(255, 249, 239, 0.74)),
    var(--agent-color, var(--orange-soft));
  box-shadow: 0 12px 24px rgba(99, 65, 34, 0.12);
}

.agent-avatar img {
  display: block;
  width: 86%;
  height: 86%;
  object-fit: contain;
  filter: drop-shadow(0 8px 12px rgba(99, 65, 34, 0.12));
}

.agent-avatar--planner {
  --agent-color: color-mix(in srgb, var(--agent-planner) 12%, white);
}

.agent-avatar--content {
  --agent-color: color-mix(in srgb, var(--agent-content) 14%, white);
}

.agent-avatar--tutor {
  --agent-color: color-mix(in srgb, var(--agent-tutor) 12%, white);
}

.agent-avatar--safety {
  --agent-color: color-mix(in srgb, var(--agent-safety) 13%, white);
}

.agent-avatar--evaluation {
  --agent-color: color-mix(in srgb, var(--agent-evaluation) 12%, white);
}

.agent-avatar--quiz {
  --agent-color: color-mix(in srgb, var(--agent-quiz) 12%, white);
}

.agent-avatar--animated {
  animation: agent-avatar-float 2.6s ease-in-out infinite;
}

.agent-avatar--thinking img {
  transform: rotate(-2deg);
}

.agent-avatar--talking img {
  animation: agent-avatar-talk 0.8s ease-in-out infinite;
}

.agent-avatar--celebrating img {
  transform: translateY(-2px) rotate(3deg);
}

@keyframes agent-avatar-float {
  50% {
    transform: translateY(-4px);
  }
}

@keyframes agent-avatar-talk {
  50% {
    transform: scale(1.04);
  }
}
</style>
