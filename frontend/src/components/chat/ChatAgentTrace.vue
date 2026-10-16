/**
 * ChatAgentTrace · Plan D · 4.2 — 7 阶段 Agent 协作链路折叠面板
 *
 * 数据契约：
 *   stages: Array<{ stage: string; status: "running" | "done" | "pending" }>
 *   agentsInvoked: string[] (后端 agents_invoked，归一化到 AvatarKind[])
 *   primaryAgent: string (主导 Agent)
 *   quality: { overall_passed?: boolean; overall_score?: number } | null
 *   safety: { overall_risk?: number; passed?: boolean } | null
 *
 * 默认 7 阶段（与 backend/services/agent_orchestrator 一致）：
 *   1. 意图识别 (intent)
 *   2. 知识检索 (kg_lookup)
 *   3. 资源生成 (resource_gen)
 *   4. 多 Agent 辩论 (debate)
 *   5. 安全校验 (safety)
 *   6. 反思 (reflection)
 *   7. 画像更新 (profile_update)
 */
<script setup lang="ts">
import { computed } from "vue";
import { ChevronDown, ChevronRight, Cpu, ShieldCheck, Sparkles } from "lucide-vue-next";

import { AGENT_AVATARS, normalizeAgentNames, type AvatarKind } from "@/constants/agentAvatars";

interface Stage {
  stage: string;
  status: "running" | "done" | "pending";
}

interface Quality {
  overall_passed?: boolean;
  overall_score?: number;
}

interface Safety {
  overall_risk?: number;
  passed?: boolean;
}

const props = withDefaults(
  defineProps<{
    stages?: Stage[];
    agentsInvoked?: string[];
    primaryAgent?: string;
    quality?: Quality | null;
    safety?: Safety | null;
    expanded?: boolean;
  }>(),
  {
    stages: () => [],
    agentsInvoked: () => [],
    primaryAgent: "",
    quality: null,
    safety: null,
    expanded: false,
  },
);

const emit = defineEmits<{
  (e: "toggle"): void;
}>();

const normalizedKinds = computed<AvatarKind[]>(() => {
  if (!props.agentsInvoked?.length) return [];
  return normalizeAgentNames(props.agentsInvoked);
});

const hasContent = computed(
  () => (props.stages?.length ?? 0) > 0 || normalizedKinds.value.length > 0,
);

const completedCount = computed(
  () => props.stages?.filter((s) => s.status === "done").length ?? 0,
);

const totalCount = computed(() => props.stages?.length ?? 0);

function stageColor(status: string): string {
  if (status === "done") return "#16a34a";
  if (status === "running") return "#ea5a1a";
  return "#cbd5e1";
}
</script>

<template>
  <div v-if="hasContent" class="chat-agent-trace">
    <button class="trace-head" type="button" @click="emit('toggle')">
      <component :is="expanded ? ChevronDown : ChevronRight" :size="14" />
      <Cpu :size="14" />
      <span class="trace-title">Agent 协作链路</span>
      <span class="trace-progress">
        {{ completedCount }} / {{ totalCount }} 阶段
      </span>
      <span
        v-if="quality"
        class="trace-badge"
        :class="quality.overall_passed ? 'good' : 'bad'"
      >
        <Sparkles :size="11" />
        CoV {{ (quality.overall_score ?? 0).toFixed(2) }}
      </span>
      <span
        v-if="safety"
        class="trace-badge"
        :class="safety.passed ? 'good' : 'bad'"
      >
        <ShieldCheck :size="11" />
        安全 {{ ((safety.overall_risk ?? 0) * 100).toFixed(0) }}%
      </span>
    </button>

    <div v-if="expanded" class="trace-body">
      <!-- Agent 头像栈 -->
      <div v-if="normalizedKinds.length" class="agents-row">
        <span class="row-label">协作 Agent：</span>
        <span
          v-for="kind in normalizedKinds.slice(0, 6)"
          :key="kind"
          class="agent-pill"
          :style="{ borderColor: AGENT_AVATARS[kind]?.color ?? '#cbd5e1' }"
          :title="AGENT_AVATARS[kind]?.nick"
        >
          <img
            v-if="AGENT_AVATARS[kind]?.png"
            :src="AGENT_AVATARS[kind]!.png!"
            :alt="AGENT_AVATARS[kind]?.nick"
            @error="($event.target as HTMLImageElement).style.display = 'none'"
          />
          <span v-else>{{ AGENT_AVATARS[kind]?.emoji }}</span>
          <span class="agent-nick">{{ AGENT_AVATARS[kind]?.nick }}</span>
        </span>
      </div>

      <!-- 7 阶段 -->
      <ol v-if="stages?.length" class="stages-list">
        <li
          v-for="(s, i) in stages"
          :key="`${s.stage}-${i}`"
          :class="['stage-row', s.status]"
        >
          <span class="stage-dot" :style="{ background: stageColor(s.status) }" />
          <span class="stage-name">{{ s.stage }}</span>
          <span class="stage-status">
            {{ s.status === "done" ? "完成" : s.status === "running" ? "运行中" : "待执行" }}
          </span>
        </li>
      </ol>

      <p v-if="primaryAgent" class="primary-agent">
        主导 Agent：<b>{{ primaryAgent }}</b>
      </p>
    </div>
  </div>
</template>

<style scoped lang="scss">
.chat-agent-trace {
  border: 1px solid var(--border-soft, #e5d4be);
  border-radius: 10px;
  background: var(--paper, #fdf6e3);
  overflow: hidden;
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 12.5px;
  color: var(--ink, #3d3830);
  font-family: inherit;
}

.trace-title {
  font-weight: 600;
}

.trace-progress {
  font-size: 11px;
  color: var(--muted, #6b4f2f);
  background: var(--paper-2, #fdf0e8);
  padding: 2px 8px;
  border-radius: 999px;
}

.trace-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 999px;
  margin-left: auto;

  &.good {
    background: rgba(22, 163, 74, 0.12);
    color: #15803d;
  }
  &.bad {
    background: rgba(220, 38, 38, 0.12);
    color: #b91c1c;
  }
}

.trace-body {
  border-top: 1px dashed var(--border-soft, #e5d4be);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 12px;
  background: var(--paper-2, #fdf0e8);
}

.agents-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.row-label {
  font-size: 11.5px;
  color: var(--muted, #6b4f2f);
}

.agent-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px 2px 2px;
  border-radius: 999px;
  border: 1.5px solid #fff;
  background: var(--paper, #fdf6e3);
  box-shadow: 0 0 0 1px var(--border-soft, #e5d4be);
  font-size: 11px;

  img {
    width: 16px;
    height: 16px;
    border-radius: 999px;
    object-fit: cover;
  }
  span:first-of-type {
    font-size: 12px;
  }
}

.agent-nick {
  font-weight: 500;
  color: var(--ink, #3d3830);
}

.stages-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stage-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 6px;
  background: var(--paper, #fdf6e3);

  &.running {
    background: rgba(234, 90, 26, 0.06);
  }

  &.pending {
    opacity: 0.55;
  }
}

.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.stage-name {
  flex: 1;
  color: var(--ink, #3d3830);
}

.stage-status {
  font-size: 10.5px;
  color: var(--muted, #6b4f2f);
}

.primary-agent {
  margin: 0;
  font-size: 11.5px;
  color: var(--muted, #6b4f2f);
  padding-top: 6px;
  border-top: 1px dashed var(--border-soft, #e5d4be);

  b {
    color: var(--orange-700, #c2410c);
  }
}
</style>