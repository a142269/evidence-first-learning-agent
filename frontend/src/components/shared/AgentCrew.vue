<script setup lang="ts">
/**
 * AgentCrew · 本页智能体分工条
 *
 * 让 6 个智能体贯穿所有功能页：每个页面顶部声明「这页背后是哪些 Agent 在工作、各负责什么」。
 * 用法：<AgentCrew :crew="[{ key: 'planner', note: '路径规划' }, ...]" />
 */
import { computed } from "vue";
import { partners } from "@/constants/companion";

interface CrewItem {
  key: string;   // partner.key: planner/tutor/content/quiz/evaluation/safety
  note: string;  // 本页职责
}

const props = defineProps<{
  crew: CrewItem[];
  label?: string;
}>();

const resolved = computed(() =>
  props.crew
    .map((c) => {
      const p = partners.find((x) => x.key === c.key);
      return p ? { ...c, name: p.name, title: p.title, avatar: p.avatar, accent: p.accent } : null;
    })
    .filter((x): x is NonNullable<typeof x> => x !== null),
);
</script>

<template>
  <div class="agent-crew" role="note">
    <b class="crew-label">{{ label || "本页智能体分工" }}</b>
    <span v-for="a in resolved" :key="a.key" class="crew-chip" :style="{ '--accent': a.accent }" :title="`${a.name}（${a.title}）：${a.note}`">
      <img v-if="a.avatar" :src="a.avatar" :alt="a.name" @error="($event.target as HTMLImageElement).style.display = 'none'" />
      <em>{{ a.name }}</em>
      <small>{{ a.note }}</small>
    </span>
  </div>
</template>

<style scoped>
.agent-crew {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fffaf4;
  border: 1px dashed #ecd9c2;
}

.crew-label {
  font-size: 11.5px;
  color: #a07948;
  font-weight: 700;
  letter-spacing: 0.5px;
  flex: none;
}

.crew-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px 3px 4px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #eee1cf;
  font-size: 11.5px;
  cursor: default;
}

.crew-chip img {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
}

.crew-chip em {
  font-style: normal;
  font-weight: 700;
  color: var(--accent, #ea5a1a);
}

.crew-chip small {
  color: #8a7a64;
  font-size: 10.5px;
}
</style>
