<script setup lang="ts">
import { computed } from "vue";

import type { CalendarDay } from "@/api/insights";

interface Props {
  days: CalendarDay[];
}

const props = defineProps<Props>();

// 按周分列（GitHub 风格）：每列 7 天，周一为首行
const weeks = computed<Array<Array<CalendarDay | null>>>(() => {
  if (!props.days.length) return [];
  const first = new Date(`${props.days[0].date}T00:00:00`);
  // getDay(): 周日=0 → 转为周一=0 的偏移
  const offset = (first.getDay() + 6) % 7;
  const cells: Array<CalendarDay | null> = [
    ...Array.from({ length: offset }, () => null),
    ...props.days,
  ];
  const cols: Array<Array<CalendarDay | null>> = [];
  for (let i = 0; i < cells.length; i += 7) {
    cols.push(cells.slice(i, i + 7));
  }
  const last = cols[cols.length - 1];
  if (last) while (last.length < 7) last.push(null);
  return cols;
});

const monthLabels = computed<Array<{ index: number; label: string }>>(() => {
  const labels: Array<{ index: number; label: string }> = [];
  let prev = "";
  weeks.value.forEach((week, i) => {
    const day = week.find((d) => d != null);
    if (!day) return;
    const month = day.date.slice(5, 7);
    if (month !== prev) {
      labels.push({ index: i, label: `${Number(month)}月` });
      prev = month;
    }
  });
  return labels;
});

function tooltip(day: CalendarDay): string {
  const base = `${day.date} · ${day.count} 次学习`;
  return day.minutes > 0 ? `${base} · ${day.minutes} 分钟` : base;
}
</script>

<template>
  <div class="study-calendar">
    <div class="cal-months">
      <span
        v-for="m in monthLabels"
        :key="m.index"
        :style="{ gridColumnStart: m.index + 1 }"
      >{{ m.label }}</span>
    </div>
    <div class="cal-grid" role="img" aria-label="学习活跃热力日历">
      <div v-for="(week, wi) in weeks" :key="wi" class="cal-week">
        <span
          v-for="(day, di) in week"
          :key="di"
          :class="['cal-cell', day ? `lv-${day.level}` : 'empty']"
          :title="day ? tooltip(day) : undefined"
        />
      </div>
    </div>
    <div class="cal-legend">
      <small>少</small>
      <span v-for="lv in [0, 1, 2, 3, 4]" :key="lv" :class="['cal-cell', `lv-${lv}`]" />
      <small>多</small>
    </div>
  </div>
</template>

<style scoped>
.study-calendar {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cal-months {
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: 15px;
  gap: 3px;
  font-size: 10px;
  color: var(--muted);
  height: 14px;
}

.cal-grid {
  display: flex;
  gap: 3px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.cal-week {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.cal-cell {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  background: var(--paper-2, #f3ede4);
  flex-shrink: 0;
}

.cal-cell.empty {
  background: transparent;
}

.cal-cell.lv-1 {
  background: #fbd9b8;
}

.cal-cell.lv-2 {
  background: #f5ab6b;
}

.cal-cell.lv-3 {
  background: #ea7a33;
}

.cal-cell.lv-4 {
  background: #c9531a;
}

.cal-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
}

.cal-legend small {
  font-size: 10px;
  color: var(--muted);
}
</style>
