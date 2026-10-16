<script setup lang="ts">
/**
 * QuizCard · Plan D · 1.2 — 交互式答题卡片
 *
 * 和 ResourceCard.quiz 分支区别：
 * - 用户先作答（点 radio）
 * - 提交后显示对/错 + 反馈
 * - 不主动露出答案
 *
 * 数据契约：
 * {
 *   stem: string,
 *   options: [{ key, text }],
 *   answer: "A",
 *   explanation?: string,
 *   expected_keywords?: string[],
 * }
 */
import { computed, ref } from "vue";

import {
  CheckCircle2,
  CircleHelp,
  RotateCcw,
  XCircle,
} from "lucide-vue-next";

interface QuizOption { key: string; text: string }
const props = withDefaults(
  defineProps<{
    stem: string;
    options?: QuizOption[];
    /** 正确选项 key (A/B/C/D) */
    answer?: string;
    explanation?: string;
    expected_keywords?: string[];
    /** 是否允许重答 */
    retryable?: boolean;
  }>(),
  { retryable: true, options: () => [] },
);

const emit = defineEmits<{
  (e: "answered", payload: { correct: boolean; chosen: string }): void;
}>();

const chosen = ref<string>("");
const submitted = ref(false);

const isCorrect = computed(() => chosen.value === props.answer);

function submit() {
  if (!chosen.value) return;
  submitted.value = true;
  emit("answered", { correct: isCorrect.value, chosen: chosen.value });
}

function reset() {
  chosen.value = "";
  submitted.value = false;
}

// 把 {key, text} 或 string[] 都规范成 [{key, text}]
const normalizedOptions = computed<QuizOption[]>(() => {
  return props.options.map((o, i) =>
    typeof o === "string"
      ? { key: String.fromCharCode(65 + i), text: o }
      : o,
  );
});
</script>

<template>
  <article class="quiz-card" :class="{ submitted, correct: submitted && isCorrect, wrong: submitted && !isCorrect }">
    <header class="qc-head">
      <span class="qc-stem-tag">
        <CircleHelp :size="14" /> 答题
      </span>
    </header>
    <p class="qc-stem">{{ stem }}</p>

    <ol class="qc-options">
      <li
        v-for="opt in normalizedOptions"
        :key="opt.key"
      >
        <label :class="{
          active: chosen === opt.key && !submitted,
          right: submitted && opt.key === answer,
          wrong: submitted && opt.key === chosen && opt.key !== answer,
        }">
          <input
            type="radio"
            :name="stem"
            :value="opt.key"
            v-model="chosen"
            :disabled="submitted"
          />
          <strong>{{ opt.key }}.</strong>
          <span>{{ opt.text }}</span>
        </label>
      </li>
    </ol>

    <div v-if="submitted" class="qc-feedback" :class="isCorrect ? 'ok' : 'err'">
      <strong v-if="isCorrect">
        <CheckCircle2 :size="14" /> 答对了
      </strong>
      <strong v-else>
        <XCircle :size="14" /> 答错了，正确答案是 {{ answer }}
      </strong>
      <p v-if="explanation" class="qc-explanation">{{ explanation }}</p>
      <div v-if="expected_keywords?.length && !isCorrect" class="qc-keywords">
        <span>关键词:</span>
        <span v-for="k in expected_keywords" :key="k" class="kw">{{ k }}</span>
      </div>
    </div>

    <div class="qc-actions">
      <button v-if="!submitted" class="qc-submit" :disabled="!chosen" type="button" @click="submit">
        提交
      </button>
      <button v-else-if="retryable" class="qc-retry" type="button" @click="reset">
        <RotateCcw :size="12" /> 再答一次
      </button>
    </div>
  </article>
</template>

<style scoped lang="scss">
.quiz-card {
  border: 1px solid #e5d4be;
  border-radius: 12px;
  background: var(--paper, #fdf6e3);
  padding: 0.7rem 0.9rem;
  font-size: 13px;
  color: #4b3414;

  &.correct { border-left: 4px solid #16a34a; }
  &.wrong   { border-left: 4px solid #dc2626; }
}

.qc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.qc-stem-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
  border-radius: 999px;
}

.qc-stem {
  font-weight: 600;
  margin: 0.4rem 0 0.5rem;
  line-height: 1.4;
}

.qc-options {
  list-style: none;
  padding: 0;
  margin: 0 0 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  > li > label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.6rem;
    background: var(--paper-2, #fff8e8);
    border: 1px solid transparent;
    border-radius: 8px;
    cursor: pointer;
    > input { accent-color: #d97706; }
    &.active { border-color: #d97706; background: rgba(254, 243, 199, 0.7); }
    &.right  { border-color: #16a34a; background: rgba(220, 252, 231, 0.7); }
    &.wrong  { border-color: #dc2626; background: rgba(254, 226, 226, 0.7); }
  }
}

.qc-feedback {
  margin-top: 0.4rem;
  padding: 0.5rem;
  border-radius: 6px;
  &.ok  { background: rgba(220, 252, 231, 0.7); color: #166534; }
  &.err { background: rgba(254, 226, 226, 0.7); color: #991b1b; }
  > p { margin: 0.25rem 0 0; font-size: 12.5px; }
}

.qc-keywords {
  margin-top: 0.4rem;
  display: flex;
  gap: 0.25rem;
  align-items: center;
  flex-wrap: wrap;
  font-size: 11.5px;
  color: #991b1b;
  .kw {
    background: rgba(245, 158, 11, 0.2);
    padding: 1px 6px;
    border-radius: 999px;
  }
}

.qc-actions {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.5rem;
}

.qc-submit {
  background: #d97706;
  color: #fff;
  border: 0;
  border-radius: 6px;
  padding: 4px 14px;
  font-size: 12px;
  cursor: pointer;
  &:disabled { opacity: 0.4; cursor: not-allowed; }
}

.qc-retry {
  background: var(--paper-2);
  color: var(--ink, #4b3414);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
}
</style>
