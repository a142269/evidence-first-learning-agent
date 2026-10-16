<script setup lang="ts">
/**
 * AgentTracePanel · Plan 1.1 Agent 协作链路可视化
 *
 * 折叠面板：在对话气泡下方显示本次回答由哪些 Agent 协作完成
 * - primary_agent 主答气泡头像
 * - agents_invoked 所有参与者（hover 可见；点击展开看每个 Agent 的产出摘要）
 * - debate 辩论记录（多轮）
 * - reflection 反思评分
 *
 * 数据契约（后端）
 * ================
 * message.agent_trace?: {
 *   primary_agent: string,
 *   agents_invoked: string[],
 *   debate?: { rounds: [{ round: number, agents: string[], summary: string }] },
 *   reflection?: { score: number, hints: string[] },
 *   rag_hits?: [{ source: string, score: number }]
 * }
 */
import { computed, ref } from "vue";

import {
  AGENT_AVATARS,
  type AvatarKind,
  type AvatarEntry,
  getAvatar,
  normalizeAgentNames,
} from "@/constants/agentAvatars";

interface DebateRound {
  round: number;
  agents: string[];
  summary: string;
}

interface AgentTrace {
  primary_agent: string;
  agents_invoked: string[];
  debate?: { rounds: DebateRound[] };
  reflection?: { score: number; hints: string[] };
  rag_hits?: { source: string; score: number; course?: string }[];
}

const props = withDefaults(
  defineProps<{
    trace: AgentTrace | null | undefined;
    ragHits?: { source: string; score: number; course?: string }[];
  }>(),
  { trace: null, ragHits: () => [] },
);

const expanded = ref(false);

const primaryKind = computed<AvatarKind>(() => {
  if (!props.trace?.primary_agent) return "tutor";
  const arr = normalizeAgentNames([props.trace.primary_agent]);
  return arr[0] ?? "tutor";
});

const primary = computed<AvatarEntry>(() => getAvatar(primaryKind.value));

const allKinds = computed<AvatarKind[]>(() => {
  if (!props.trace) return [];
  return normalizeAgentNames(props.trace.agents_invoked || []);
});

const hasDebate = computed(
  () => !!props.trace?.debate?.rounds && (props.trace?.debate?.rounds?.length ?? 0) > 0,
);

const hasReflection = computed(
  () => !!props.trace?.reflection && typeof props.trace.reflection.score === "number",
);

const ragHitsList = computed(() => {
  const fromTrace = props.trace?.rag_hits ?? [];
  const fromProps = props.ragHits ?? [];
  return fromTrace.length ? fromTrace : fromProps;
});

function scoreClass(score: number): string {
  if (score >= 0.85) return "score--high";
  if (score >= 0.7) return "score--mid";
  return "score--low";
}
</script>

<template>
  <div
    v-if="trace && (allKinds.length || hasDebate || hasReflection || ragHitsList.length)"
    class="agent-trace-panel"
    :data-test="`agent-trace-${primaryKind}`"
  >
    <button
      class="agent-trace-toggle"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span class="agent-trace-toggle__pip" :style="{ background: primary.color }">
        <span class="emoji">{{ primary.emoji }}</span>
      </span>
      <span class="agent-trace-toggle__text">
        本次回答由 {{ allKinds.length || 1 }} 位伙伴协作完成
        <span class="agent-trace-toggle__names">
          <span
            v-for="kind in allKinds"
            :key="kind"
            class="agent-pill"
            :style="{ borderColor: AGENT_AVATARS[kind].color, color: AGENT_AVATARS[kind].color }"
          >
            {{ AGENT_AVATARS[kind].emoji }} {{ AGENT_AVATARS[kind].nick }}
          </span>
        </span>
      </span>
      <span class="agent-trace-toggle__caret">{{ expanded ? "▾" : "▸" }}</span>
    </button>

    <div v-show="expanded" class="agent-trace-body">
      <!-- 主答 + 协作者 timeline -->
      <ol class="agent-trace-list">
        <li
          v-for="(kind, idx) in allKinds"
          :key="kind"
          class="agent-trace-item"
          :style="{ '--accent': AGENT_AVATARS[kind].color }"
        >
          <span class="agent-trace-item__num">①{{ "②③④⑤⑥"[idx] || idx + 1 }}</span>
          <span class="agent-trace-item__avatar" :style="{ background: AGENT_AVATARS[kind].color }">
            <span class="emoji">{{ AGENT_AVATARS[kind].emoji }}</span>
          </span>
          <span class="agent-trace-item__body">
            <strong>{{ AGENT_AVATARS[kind].role }}</strong>
            <span class="agent-trace-item__desc">{{ AGENT_AVATARS[kind].responsibility }}</span>
          </span>
        </li>
      </ol>

      <!-- 辩论 -->
      <section v-if="hasDebate" class="agent-trace-section">
        <header>
          <span class="emoji">⚔️</span>
          <h4>辩论记录</h4>
        </header>
        <ul class="agent-trace-debate">
          <li v-for="round in trace.debate!.rounds" :key="round.round">
            <strong>Round {{ round.round }}</strong>
            <span class="agent-trace-debate__agents">
              <span
                v-for="a in round.agents"
                :key="a"
                class="agent-pill"
                :style="{ borderColor: AGENT_AVATARS[normalizeAgentNames([a])[0] ?? 'tutor'].color, color: AGENT_AVATARS[normalizeAgentNames([a])[0] ?? 'tutor'].color }"
              >
                {{ AGENT_AVATARS[normalizeAgentNames([a])[0] ?? 'tutor'].emoji }}
                {{ a }}
              </span>
            </span>
            <p>{{ round.summary }}</p>
          </li>
        </ul>
      </section>

      <!-- 反思 -->
      <section v-if="hasReflection" class="agent-trace-section">
        <header>
          <span class="emoji">🔍</span>
          <h4>质量反思</h4>
        </header>
        <div class="agent-trace-reflection">
          <div
            class="score-ring"
            :class="scoreClass(trace.reflection!.score)"
          >
            {{ Math.round((trace.reflection!.score ?? 0) * 100) }}
          </div>
          <ul v-if="trace.reflection!.hints?.length" class="agent-trace-hints">
            <li v-for="(h, i) in trace.reflection!.hints" :key="i">{{ h }}</li>
          </ul>
        </div>
      </section>

      <!-- RAG 引用 -->
      <section v-if="ragHitsList.length" class="agent-trace-section">
        <header>
          <span class="emoji">📚</span>
          <h4>参考来源（{{ ragHitsList.length }} 条命中）</h4>
        </header>
        <ul class="agent-trace-rag">
          <li
            v-for="(hit, idx) in ragHitsList"
            :key="idx"
            :class="scoreClass(hit.score)"
          >
            <span class="agent-trace-rag__idx">[{{ idx + 1 }}]</span>
            <span class="agent-trace-rag__source">{{ hit.source }}</span>
            <span v-if="hit.course" class="agent-trace-rag__course">· {{ hit.course }}</span>
            <span class="agent-trace-rag__score">(相关度 {{ hit.score.toFixed(2) }})</span>
          </li>
        </ul>
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
.agent-trace-panel {
  margin-top: 0.5rem;
  border-radius: 0.75rem;
  background: rgba(255, 248, 239, 0.7);
  border: 1px solid rgba(217, 119, 6, 0.18);
  font-size: 0.875rem;
  color: #4b3414;
}

.agent-trace-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.5rem 0.75rem;
  background: none;
  border: 0;
  cursor: pointer;
  text-align: left;

  &__pip {
    display: inline-grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    border-radius: 999px;
    color: #fff;
    font-size: 1rem;
  }

  &__text {
    flex: 1;
    line-height: 1.4;

    > .agent-trace-toggle__names {
      display: inline-flex;
      flex-wrap: wrap;
      gap: 0.25rem;
      margin-left: 0.25rem;
    }
  }

  &__caret {
    color: rgba(75, 52, 20, 0.5);
    font-size: 0.75rem;
  }
}

.agent-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
  padding: 0 0.5rem;
  font-size: 0.75rem;
  border-radius: 999px;
  border: 1px solid;
  background: rgba(255, 255, 255, 0.8);
}

.agent-trace-body {
  padding: 0.5rem 0.75rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  border-top: 1px dashed rgba(217, 119, 6, 0.2);
}

.agent-trace-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.agent-trace-item {
  display: grid;
  grid-template-columns: 1.2rem 1.8rem 1fr;
  gap: 0.5rem;
  align-items: center;
  padding: 0.3rem 0.4rem;
  border-left: 2px solid var(--accent, #d97706);
  background: rgba(255, 255, 255, 0.5);
  border-radius: 0.4rem;

  &__num {
    font-size: 0.7rem;
    color: rgba(75, 52, 20, 0.7);
    text-align: right;
  }

  &__avatar {
    display: inline-grid;
    place-items: center;
    width: 1.6rem;
    height: 1.6rem;
    border-radius: 999px;
    color: #fff;
    font-size: 1rem;
  }

  &__body {
    line-height: 1.3;
    > strong {
      display: block;
      font-size: 0.85rem;
    }
  }

  &__desc {
    font-size: 0.75rem;
    color: rgba(75, 52, 20, 0.7);
  }
}

.agent-trace-section {
  border-top: 1px dashed rgba(99, 65, 34, 0.18);
  padding-top: 0.5rem;

  > header {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin-bottom: 0.35rem;
    h4 {
      margin: 0;
      font-size: 0.85rem;
    }
  }
}

.agent-trace-debate {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.78rem;

  > li {
    background: rgba(255, 255, 255, 0.5);
    border-radius: 0.4rem;
    padding: 0.3rem 0.5rem;
    > strong {
      margin-right: 0.4rem;
    }
    > p {
      margin: 0.2rem 0 0;
      color: rgba(75, 52, 20, 0.85);
    }
  }

  &__agents {
    display: inline-flex;
    gap: 0.25rem;
  }
}

.agent-trace-reflection {
  display: flex;
  align-items: center;
  gap: 0.75rem;

  .score-ring {
    display: inline-grid;
    place-items: center;
    width: 3rem;
    height: 3rem;
    border-radius: 999px;
    color: #fff;
    font-weight: 700;
    font-size: 1rem;
    background: linear-gradient(135deg, #f59e0b, #d97706);

    &.score--high {
      background: linear-gradient(135deg, #34d399, #059669);
    }
    &.score--mid {
      background: linear-gradient(135deg, #fbbf24, #d97706);
    }
    &.score--low {
      background: linear-gradient(135deg, #f87171, #dc2626);
    }
  }
}

.agent-trace-hints {
  list-style: disc;
  padding-left: 1.2rem;
  margin: 0;
  font-size: 0.78rem;
  color: rgba(75, 52, 20, 0.85);
}

.agent-trace-rag {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.78rem;

  > li {
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
    background: rgba(255, 255, 255, 0.5);
    border-radius: 0.4rem;
    padding: 0.25rem 0.5rem;

    &.score--high {
      border-left: 3px solid #059669;
    }
    &.score--mid {
      border-left: 3px solid #d97706;
    }
    &.score--low {
      border-left: 3px solid #9ca3af;
    }
  }

  &__idx {
    color: rgba(75, 52, 20, 0.5);
    font-weight: 700;
    min-width: 2rem;
  }

  &__source {
    flex: 1;
  }

  &__course {
    color: rgba(75, 52, 20, 0.5);
  }

  &__score {
    color: rgba(75, 52, 20, 0.7);
    font-size: 0.7rem;
  }
}
</style>
