<script setup lang="ts">
/**
 * TodayReview · Plan D · 3.3 — 今日复习模块
 *
 * 数据契约:
 * GET /api/v1/spaced-repetition/daily/{user_id} → { items, stats }
 *
 * 视觉:
 * - 顶部统计 (due today / total / avg easiness)
 * - 每条知识点卡片: 难易度进度 + 间隔 + retention curve
 * - 提交答案按钮（质量 0-5）
 */
import { computed, onMounted, ref } from "vue";

import { BookOpenCheck, Check, ChevronRight, ChevronUp, Flame, Minus, RefreshCw } from "lucide-vue-next";

import {
  fetchDailyReview,
  submitReview,
  fetchSchedule,
  type DailyResponse,
  type SpacedItem,
  type SpacedSchedule,
} from "@/api/spacedRepetition";

const props = defineProps<{
  userId: string;
}>();

const loading = ref(false);
const error = ref<string>("");
const data = ref<DailyResponse | null>(null);
const lastSubmitted = ref<string | null>(null);

async function refresh() {
  if (!props.userId) return;
  loading.value = true;
  error.value = "";
  try {
    data.value = await fetchDailyReview(props.userId);
  } catch (e: any) {
    if (e?.message === "Failed to fetch") {
      error.value = "加载失败：无法连接到复习服务，请检查网络或后端服务状态";
    } else {
      error.value = e?.detail || e?.message || "今日复习加载失败";
    }
  } finally {
    loading.value = false;
  }
}

async function review(item: SpacedItem, quality: number) {
  if (!props.userId) return;
  try {
    const res = await submitReview({
      user_id: props.userId,
      item_id: item.item_id,
      quality,
    });
    lastSubmitted.value = item.item_id;
    // 乐观更新：把 easiness/interval 立即反映到本地
    if (data.value) {
      data.value.items = data.value.items.map((it) =>
        it.item_id === item.item_id
          ? {
              ...it,
              easiness: res.state.easiness ?? it.easiness,
              interval_days: (res.state as any).interval ?? it.interval_days,
              repetitions: res.state.repetitions ?? it.repetitions,
              next_review_at: res.state.next_review_at ?? it.next_review_at,
            }
          : it,
      );
      data.value.total_due = Math.max(0, data.value.total_due - 1);
    }
  } catch (e: any) {
    error.value = `提交失败: ${e?.detail || e?.message}`;
  }
}

onMounted(refresh);

// ---- 单知识点复习计划查询 ----
const scheduleItemId = ref("");
const scheduleLoading = ref(false);
const scheduleResult = ref<SpacedSchedule | null>(null);
const scheduleError = ref("");

async function lookupSchedule() {
  const id = scheduleItemId.value.trim();
  if (!id || scheduleLoading.value) return;
  scheduleLoading.value = true;
  scheduleResult.value = null;
  scheduleError.value = "";
  try {
    scheduleResult.value = await fetchSchedule(props.userId, id);
  } catch (e: any) {
    scheduleError.value = `查询失败：${e?.detail ?? e?.message ?? e}`;
  }
  scheduleLoading.value = false;
}

function fmtDate(ts: number | null): string {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// 可视化难易度（SM2: 1.3 ~ 2.5+，归一化到 0~100%）
function easinessPct(ef: number): number {
  // 1.3 -> 0%, 3.0 -> 100%
  const v = ((ef - 1.3) / (3.0 - 1.3)) * 100;
  return Math.max(0, Math.min(100, Math.round(v)));
}

const retentionPoints = computed(() => {
  if (!data.value?.items?.length) return [];
  const first = data.value.items[0];
  if (!first?.retention_curve) return [];
  return Object.entries(first.retention_curve)
    .map(([k, v]) => ({ day: k, rate: Number(v) }))
    .slice(0, 6);
});

// Plan D · 3.3 — 复习优先级映射
function priorityLabel(score: number): string {
  if (score >= 0.7) return "优先";
  if (score >= 0.4) return "次优";
  return "一般";
}
function priorityStyle(score: number): Record<string, string> {
  if (score >= 0.7) return { background: "rgba(220, 38, 38, 0.92)", color: "#fff" };
  if (score >= 0.4) return { background: "rgba(217, 119, 6, 0.92)", color: "#fff" };
  return { background: "rgba(107, 114, 128, 0.92)", color: "#fff" };
}
</script>

<template>
  <section class="today-review" :data-loading="loading">
    <header>
      <div class="tr-head-left">
        <BookOpenCheck :size="16" />
        <strong>今日复习任务</strong>
      </div>
      <button class="tr-refresh" type="button" :disabled="loading" @click="refresh">
        <RefreshCw :size="13" :class="{ spin: loading }" />
        刷新
      </button>
    </header>

    <div v-if="data" class="tr-summary">
      <div class="tr-stat">
        <span class="tr-stat-label">今日到期</span>
        <strong class="tr-stat-value">{{ data.total_due }}</strong>
      </div>
      <div class="tr-stat">
        <span class="tr-stat-label">总复习项</span>
        <strong class="tr-stat-value">{{ data.stats.total_items }}</strong>
      </div>
      <div class="tr-stat">
        <span class="tr-stat-label">平均难易度</span>
        <strong class="tr-stat-value">{{ data.stats.average_easiness?.toFixed(2) || "—" }}</strong>
      </div>
      <div class="tr-stat">
        <span class="tr-stat-label">主力算法</span>
        <strong class="tr-stat-value">{{ data.algorithm }}</strong>
      </div>
    </div>

    <p v-if="error" class="tr-error">{{ error }}</p>

    <div v-if="!loading && data && !data.items.length" class="tr-empty">
      <Check :size="22" style="color: var(--status-done)" />
      <p>今日暂无复习任务，继续探索新知识吧！</p>
    </div>

    <ol v-if="data?.items?.length" class="tr-list">
      <li v-for="it in data.items" :key="it.item_id" :class="{ just: lastSubmitted === it.item_id }">
        <header class="tr-row-head">
          <strong class="tr-item-id">{{ it.item_id }}</strong>
          <span class="tr-pill">reps {{ it.repetitions }}</span>
          <!-- Plan D · 3.3 — 优先级标签 -->
          <span
            v-if="it.priority_score != null"
            class="tr-priority"
            :style="priorityStyle(it.priority_score)"
            :title="it.priority_reason || ''"
          >
            <Flame v-if="it.priority_score >= 0.6" :size="11" />
            <ChevronUp v-else-if="it.priority_score >= 0.4" :size="11" />
            <Minus v-else :size="11" />
            {{ priorityLabel(it.priority_score) }}
          </span>
        </header>
        <!-- Plan D · 3.3 — 优先级原因 -->
        <div v-if="it.priority_reason" class="tr-priority-reason">
          {{ it.priority_reason }}
        </div>
        <div class="tr-row-body">
          <div class="tr-easiness">
            <label>难易度</label>
            <div class="bar">
              <i :style="{ width: `${easinessPct(it.easiness)}%` }" />
            </div>
            <em>{{ it.easiness?.toFixed(2) }}</em>
          </div>
          <div class="tr-interval">
            间隔 {{ it.interval_days }} 天 / 已复习 {{ it.repetitions }} 次
          </div>
          <div v-if="it.recommendation" class="tr-rec">
            <ChevronRight :size="11" />
            <span>建议：{{ it.recommendation.action || "—" }}</span>
          </div>
        </div>
        <div class="tr-actions">
          <button type="button" class="q-err" :disabled="lastSubmitted === it.item_id" @click="review(it, 0)">
            完全不会 (0)
          </button>
          <button type="button" class="q-ok2" :disabled="lastSubmitted === it.item_id" @click="review(it, 3)">
            勉强 (3)
          </button>
          <button type="button" class="q-ok4" :disabled="lastSubmitted === it.item_id" @click="review(it, 4)">
            还好 (4)
          </button>
          <button type="button" class="q-ok5" :disabled="lastSubmitted === it.item_id" @click="review(it, 5)">
            完全正确 (5)
          </button>
        </div>
        <div v-if="retentionPoints.length && it === data.items[0]" class="tr-curve">
          <small>留存曲线（前 6 个检查点）:</small>
          <ol>
            <li v-for="pt in retentionPoints" :key="pt.day">
              <span class="tr-curve-day">+{{ pt.day }}d</span>
              <div class="bar"><i :style="{ width: `${Math.round(pt.rate * 100)}%` }" /></div>
              <em>{{ Math.round(pt.rate * 100) }}%</em>
            </li>
          </ol>
        </div>
      </li>
    </ol>

    <!-- 单知识点复习计划查询 -->
    <div class="tr-schedule-lookup">
      <header>
        <small>按知识点 ID 查看复习计划</small>
      </header>
      <div class="tr-schedule-input">
        <input
          v-model="scheduleItemId"
          placeholder="输入知识点 ID，如：kp_backprop"
          @keydown.enter="lookupSchedule"
        />
        <button type="button" :disabled="scheduleLoading" @click="lookupSchedule">
          <Loader2 v-if="scheduleLoading" :size="12" class="spin" />
          查询
        </button>
      </div>
      <p v-if="scheduleError" class="tr-schedule-err">{{ scheduleError }}</p>
      <div v-if="scheduleResult" class="tr-schedule-card">
        <div class="tr-schedule-row">
          <span>难度系数</span>
          <b>{{ scheduleResult.easiness?.toFixed(2) ?? "—" }}</b>
        </div>
        <div class="tr-schedule-row">
          <span>当前间隔</span>
          <b>{{ scheduleResult.interval_days }} 天</b>
        </div>
        <div class="tr-schedule-row">
          <span>已复习次数</span>
          <b>{{ scheduleResult.repetitions }}</b>
        </div>
        <div class="tr-schedule-row">
          <span>上次复习</span>
          <b>{{ fmtDate(scheduleResult.last_review_at) }}</b>
        </div>
        <div class="tr-schedule-row">
          <span>下次复习</span>
          <b>{{ fmtDate(scheduleResult.next_review_at) }}</b>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.today-review {
  border: 1px solid var(--border-soft, #e5d4be);
  border-radius: 12px;
  background: var(--paper, #fdf6e3);
  padding: 0.7rem 0.9rem;
  font-size: 13px;
  color: #4b3414;
}

.tr-head-left {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  > strong { font-weight: 600; }
}

header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.tr-refresh {
  background: var(--paper-2);
  border: 1px solid var(--border-soft);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  &:disabled { opacity: 0.5; }
}

.tr-summary {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.tr-stat {
  flex: 1;
  background: var(--paper-2);
  border-radius: 8px;
  padding: 0.3rem 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tr-stat-label {
  font-size: 11px;
  color: var(--muted, #6b4f2f);
}

.tr-stat-value {
  font-size: 16px;
  font-weight: 600;
}

.tr-list {
  list-style: none;
  padding: 0;
  margin: 0.4rem 0 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tr-list li {
  background: var(--paper-2);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  &.just {
    border-color: #16a34a;
    box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.15) inset;
  }
}

.tr-row-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.tr-item-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
  font-size: 12.5px;
}

.tr-pill {
  font-size: 10.5px;
  padding: 1px 6px;
  background: rgba(217, 119, 6, 0.18);
  border-radius: 999px;
  color: #b45309;
}

/* Plan D · 3.3 — 复习优先级标签 */
.tr-priority {
  margin-left: auto;
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-weight: 600;
}

.tr-priority-reason {
  font-size: 11px;
  color: var(--muted, #6b4f2f);
  background: rgba(255, 248, 239, 0.6);
  border-radius: 4px;
  padding: 3px 6px;
  margin-bottom: 4px;
}

.tr-row-body {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 0.6rem;
  align-items: center;
}

.tr-easiness {
  display: grid;
  grid-template-columns: 4rem 1fr 2.5rem;
  gap: 0.4rem;
  align-items: center;
  > label { font-size: 11px; color: var(--muted); }
  > .bar {
    height: 6px;
    background: rgba(217, 119, 6, 0.15);
    border-radius: 4px;
    overflow: hidden;
    > i {
      display: block; height: 100%;
      background: linear-gradient(90deg, #f59e0b, #d97706);
    }
  }
  > em { font-size: 11px; text-align: right; }
}

.tr-interval {
  font-size: 12px;
  color: var(--muted);
}

.tr-rec {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 11.5px;
  color: var(--muted);
}

.tr-actions {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.4rem;
  > button {
    flex: 1;
    padding: 4px 8px;
    border: 0;
    border-radius: 6px;
    font-size: 12px;
    color: #fff;
    cursor: pointer;
    &:disabled { opacity: 0.4; cursor: not-allowed; }
  }
  .q-err { background: #dc2626; }
  .q-ok2 { background: #d97706; }
  .q-ok4 { background: #65a30d; }
  .q-ok5 { background: #16a34a; }
}

.tr-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  color: var(--muted);
  text-align: center;
}

.tr-error {
  background: rgba(254, 226, 226, 0.7);
  color: #991b1b;
  border-radius: 6px;
  padding: 0.4rem 0.6rem;
  font-size: 12px;
  margin: 0.4rem 0;
}

.tr-curve {
  margin-top: 0.5rem;
  background: rgba(255, 248, 239, 0.7);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;

  > small { font-size: 11px; color: var(--muted); }
  > ol {
    list-style: none;
    margin: 0.3rem 0 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 0.4rem;
    > li {
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 2px;
    }
  }
}
.tr-curve-day {
  font-size: 10.5px;
  color: var(--muted);
}
.bar {
  height: 6px;
  background: rgba(217, 119, 6, 0.15);
  border-radius: 4px;
  overflow: hidden;
  > i {
    display: block; height: 100%;
    background: linear-gradient(90deg, #f59e0b, #d97706);
  }
}

.tr-schedule-lookup {
  margin-top: 0.6rem;
  padding-top: 0.5rem;
  border-top: 1px dashed var(--border-soft, #e5d4be);

  header small {
    font-size: 11.5px;
    color: var(--muted, #6b4f2f);
    font-weight: 600;
  }
}

.tr-schedule-input {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.35rem;

  input {
    flex: 1;
    height: 28px;
    padding: 0 8px;
    border-radius: 6px;
    border: 1px solid var(--border-soft, #e5d4be);
    background: var(--paper, #fdf6e3);
    font-size: 12px;
  }

  button {
    padding: 4px 12px;
    border: 0;
    border-radius: 6px;
    background: var(--orange-500, #ea5a1a);
    color: #fff;
    font-size: 12px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 4px;

    &:disabled { opacity: 0.5; cursor: not-allowed; }
  }
}

.tr-schedule-err {
  margin: 0.3rem 0 0;
  font-size: 11.5px;
  color: #dc2626;
}

.tr-schedule-card {
  margin-top: 0.4rem;
  padding: 0.5rem 0.6rem;
  border-radius: 8px;
  background: var(--paper-2, #f5ead0);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.tr-schedule-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;

  span { color: var(--muted, #6b4f2f); }
  b { color: var(--ink, #4b3414); font-weight: 600; }
}
</style>
