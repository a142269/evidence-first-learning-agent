<script setup lang="ts">
import AgentAvatar from "./AgentAvatar.vue";
import { AGENT_ROSTER } from "./agentTypes";
import type { AgentKind, AgentMood } from "./agentTypes";

withDefaults(
  defineProps<{
    active?: AgentKind;
    mood?: AgentMood;
    layout?: "horizontal" | "orbit";
    showLearner?: boolean;
  }>(),
  {
    active: undefined,
    mood: "idle",
    layout: "horizontal",
    showLearner: false,
  },
);
</script>

<template>
  <div class="agent-roster" :class="`agent-roster--${layout}`">
    <div v-if="showLearner" class="agent-roster__item agent-roster__item--learner">
      <AgentAvatar kind="learner" :mood="mood" :animated="active === 'learner'" />
      <span>学习者</span>
    </div>

    <div
      v-for="agent in AGENT_ROSTER"
      :key="agent.kind"
      class="agent-roster__item"
      :class="{ 'agent-roster__item--active': active === agent.kind }"
    >
      <AgentAvatar :kind="agent.kind" :mood="active === agent.kind ? mood : 'idle'" :animated="active === agent.kind" />
      <span>{{ agent.name }}</span>
    </div>
  </div>
</template>

<style scoped lang="scss">
.agent-roster {
  display: flex;
  gap: 14px;
}

.agent-roster--horizontal {
  flex-wrap: wrap;
  align-items: center;
}

.agent-roster--orbit {
  display: grid;
  grid-template-columns: repeat(3, minmax(92px, 1fr));
}

.agent-roster__item {
  display: grid;
  justify-items: center;
  gap: 8px;
  min-width: 84px;
  color: var(--ink);
  font-size: 12px;
  font-weight: 800;
  opacity: 0.72;
  transition: 0.18s ease;
}

.agent-roster__item--active,
.agent-roster__item:hover {
  opacity: 1;
}
</style>
