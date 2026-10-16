<script setup lang="ts">
/**
 * SourceCitations · Plan D · 1.3 — RAG 引用溯源展示
 *
 * 后端在 meta / SSE 中已经返回 rag_hits（如 1.1 AgentTracePanel 也消费它）；
 * 此组件提供独立复用入口（ResourcesView、Cockpit 抽屉、错题本都能挂）。
 *
 * 数据契约：
 * [
 *   { source: "chapters/05_transformer.md", course?: "AI-101", score: 0.87 }
 * ]
 */
import { computed, ref } from "vue";

import {
  BookText,
  ChevronDown,
  ChevronUp,
} from "lucide-vue-next";

interface RagHit {
  source: string;
  course?: string;
  score: number;
}

const props = withDefaults(
  defineProps<{
    hits: RagHit[];
    /** 默认折叠状态 */
    collapsed?: boolean;
    /** 阈值：高相关显示绿色描边 */
    high_threshold?: number;
    mid_threshold?: number;
  }>(),
  { collapsed: false, high_threshold: 0.85, mid_threshold: 0.7 },
);

const expanded = ref(!props.collapsed);

const sortedHits = computed(() =>
  [...props.hits].sort((a, b) => b.score - a.score),
);

function bucket(score: number): "high" | "mid" | "low" {
  if (score >= props.high_threshold) return "high";
  if (score >= props.mid_threshold) return "mid";
  return "low";
}

function fname(src: string): string {
  // 取 source 最后一段作为标题
  const parts = src.split(/[\\/]/);
  return parts[parts.length - 1] || src;
}
</script>

<template>
  <section v-if="hits.length" class="source-citations" :data-collapsed="!expanded">
    <header @click="expanded = !expanded">
      <BookText :size="14" />
      <strong>参考来源（{{ hits.length }} 条命中）</strong>
      <em class="dot" />
      <component :is="expanded ? ChevronUp : ChevronDown" :size="13" />
    </header>

    <ol v-if="expanded" class="source-list">
      <li
        v-for="(hit, i) in sortedHits"
        :key="i"
        :class="bucket(hit.score)"
      >
        <span class="src-idx">[{{ i + 1 }}]</span>
        <span class="src-name" :title="hit.source">
          {{ fname(hit.source) }}
        </span>
        <span v-if="hit.course && hit.course !== fname(hit.course)" class="src-course">
          · {{ hit.course }}
        </span>
        <span class="src-score">{{ hit.score.toFixed(2) }}</span>
      </li>
    </ol>
  </section>
</template>

<style scoped lang="scss">
.source-citations {
  border: 1px dashed rgba(217, 119, 6, 0.25);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
  background: rgba(255, 248, 239, 0.65);
  font-size: 12.5px;
  margin-top: 0.5rem;

  > header {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    cursor: pointer;
    user-select: none;
    > strong { font-weight: 600; }
    > em.dot {
      margin-left: auto;
      width: 6px; height: 6px;
      border-radius: 999px;
      background: linear-gradient(120deg, #f97316, #db2777);
    }
  }
}

.source-list {
  list-style: none;
  padding: 0;
  margin: 0.4rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.source-list li {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  background: rgba(255, 255, 255, 0.6);
  padding: 2px 6px;
  border-radius: 4px;
  border-left: 2px solid #9ca3af;
  &.high { border-left-color: #16a34a; }
  &.mid  { border-left-color: #f59e0b; }
}

.src-idx {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: rgba(75, 52, 20, 0.6);
  min-width: 1.6rem;
}

.src-name {
  flex: 1;
  word-break: break-all;
  font-weight: 500;
}

.src-course {
  font-size: 11px;
  color: rgba(75, 52, 20, 0.6);
}

.src-score {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: rgba(75, 52, 20, 0.8);
}
</style>
