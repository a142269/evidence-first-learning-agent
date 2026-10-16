<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ForecastPoint } from "@/types/cockpit";

interface Milestone {
  day: number;
  label: string;
}

const props = withDefaults(
  defineProps<{
    baseline: ForecastPoint[];
    recommended?: ForecastPoint[];
    expectedGain?: number;
    milestones?: Milestone[];
    height?: number;
    /** 当 recommended 为空时显示的提示文案 */
    counterfactualHint?: string;
  }>(),
  {
    recommended: () => [],
    expectedGain: 0,
    milestones: () => [],
    height: 180,
    counterfactualHint: "暂无反事实推演",
  },
);

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function toPercent(value: number) {
  return value > 1 ? value : Math.round(value * 100);
}

const hasRecommended = computed(() => props.recommended.length > 0);
const gainPct = computed(() => Math.round((props.expectedGain ?? 0) * 100));

function renderChart() {
  if (!chartEl.value) {
    return;
  }
  if (!chart) {
    chart = echarts.init(chartEl.value);
  }

  const baseline = props.baseline.length
    ? props.baseline
    : [{ day: 0, mastery: 0 }];
  const recommended = props.recommended ?? [];
  const days = Array.from(
    new Set([...baseline, ...recommended].map((p) => p.day)),
  ).sort((a, b) => a - b);

  const baselineMap = new Map(baseline.map((p) => [p.day, toPercent(p.mastery)]));
  const recommendedMap = new Map(
    recommended.map((p) => [p.day, toPercent(p.mastery)]),
  );

  const baselineSeries = days.map((d) => baselineMap.get(d) ?? null);
  const recommendedSeries = days.map((d) => recommendedMap.get(d) ?? null);

  /** 终点处的 gain markArea — 在 x 轴最右侧画一条 baseline → recommended 的差额带 */
  const gainArea: echarts.MarkAreaComponentOption["data"] = [];
  if (hasRecommended.value && days.length > 0) {
    const lastDay = days[days.length - 1];
    const xLabel = `D${lastDay}`;
    const b = baselineMap.get(lastDay);
    const r = recommendedMap.get(lastDay);
    if (typeof b === "number" && typeof r === "number" && r > b) {
      gainArea.push([
        { xAxis: xLabel, yAxis: b, name: `+${gainPct.value}%` },
        { xAxis: xLabel, yAxis: r },
      ]);
    }
  }

  /** milestones markPoint */
  const milestonePoints = props.milestones
    .filter((m) => days.includes(m.day))
    .map((m) => ({
      name: m.label,
      coord: [`D${m.day}`, recommendedMap.get(m.day) ?? baselineMap.get(m.day) ?? 0],
      value: m.label,
      label: { fontSize: 10, color: "#0f172a" },
      itemStyle: { color: "#f59e0b", borderColor: "#ffffff", borderWidth: 2 },
      symbolSize: 12,
    }));

  const series: echarts.LineSeriesOption[] = [
    {
      name: "当前路径",
      type: "line",
      smooth: true,
      symbolSize: 5,
      connectNulls: true,
      data: baselineSeries,
      lineStyle: { color: "#64748b", width: 2, type: hasRecommended.value ? "dashed" : "solid" },
      areaStyle: hasRecommended.value
        ? { color: "rgba(100, 116, 139, 0.06)" }
        : { color: "rgba(37, 99, 235, 0.14)" },
      itemStyle: { color: "#64748b" },
    },
  ];

  if (hasRecommended.value) {
    series.push({
      name: `推荐路径 +${gainPct.value}%`,
      type: "line",
      smooth: true,
      symbolSize: 6,
      connectNulls: true,
      data: recommendedSeries,
      lineStyle: { color: "#2563eb", width: 3 },
      areaStyle: { color: "rgba(37, 99, 235, 0.16)" },
      itemStyle: { color: "#2563eb" },
      markArea: gainArea.length
        ? {
            silent: true,
            itemStyle: { color: "rgba(34, 197, 94, 0.18)" },
            label: {
              show: true,
              position: "insideRight",
              color: "#15803d",
              fontSize: 11,
              fontWeight: 800,
            },
            data: gainArea,
          }
        : undefined,
      markPoint: milestonePoints.length
        ? { symbol: "circle", data: milestonePoints }
        : undefined,
    });
  } else if (milestonePoints.length) {
    series[0].markPoint = { symbol: "circle", data: milestonePoints };
  }

  chart.setOption(
    {
      grid: { top: 26, right: 16, bottom: 26, left: 32 },
      tooltip: {
        trigger: "axis",
        valueFormatter: (v: number | string) =>
          typeof v === "number" ? `${v}%` : String(v ?? "—"),
      },
      legend: {
        top: 0,
        right: 0,
        itemWidth: 10,
        itemHeight: 6,
        textStyle: { fontSize: 11, color: "#475569" },
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: days.map((d) => `D${d}`),
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        axisLabel: { color: "#64748b", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLabel: { formatter: "{value}%", color: "#64748b", fontSize: 11 },
        splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.18)" } },
      },
      series,
    },
    { notMerge: true },
  );
}

function handleResize() {
  chart?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});

watch(
  () => [props.baseline, props.recommended, props.expectedGain, props.milestones],
  renderChart,
  { deep: true },
);
</script>

<template>
  <div class="forecast-wrap">
    <div ref="chartEl" class="forecast-curve" :style="{ height: `${height}px` }" />
    <p v-if="!hasRecommended && counterfactualHint" class="cf-hint">
      ⚠️ {{ counterfactualHint }}
    </p>
  </div>
</template>

<style scoped>
.forecast-wrap {
  display: grid;
  gap: 6px;
}

.forecast-curve {
  width: 100%;
  min-height: 140px;
}

.cf-hint {
  margin: 0;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fef3c7;
  color: #92400e;
  font-size: 11px;
  line-height: 1.4;
}
</style>
