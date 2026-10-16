<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{
    distribution: Record<string, number>;
    height?: number;
  }>(),
  {
    height: 180,
  },
);

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const palette = ["#2563eb", "#0ea5e9", "#14b8a6", "#f97316", "#ef4444", "#a855f7"];

/** 中文友好的错题分类标签（B 的 category 字符串映射） */
const categoryLabels: Record<string, string> = {
  concept_confusion: "概念混淆",
  reasoning_gap: "推理断层",
  transfer_error: "迁移失败",
  careless: "粗心错误",
  calculation_error: "计算错误",
  edge_case_oversight: "边界遗漏",
};

const entries = computed(() =>
  Object.entries(props.distribution)
    .filter(([, v]) => typeof v === "number" && v > 0)
    .sort((a, b) => b[1] - a[1]),
);

const total = computed(() => entries.value.reduce((acc, [, v]) => acc + v, 0));

const hasData = computed(() => entries.value.length > 0);

function labelOf(key: string) {
  return categoryLabels[key] ?? key;
}

function renderChart() {
  if (!chartEl.value || !hasData.value) return;
  if (!chart) chart = echarts.init(chartEl.value);

  const data = entries.value.map(([name, value], i) => ({
    name: labelOf(name),
    value,
    itemStyle: { color: palette[i % palette.length] },
  }));

  chart.setOption(
    {
      tooltip: {
        formatter: (p: { name?: string; value?: number; percent?: number }) =>
          `<strong>${p.name ?? ""}</strong><br/>错题 ${p.value ?? 0} 道（${p.percent ?? 0}%）`,
      },
      series: [
        {
          type: "treemap",
          roam: false,
          breadcrumb: { show: false },
          nodeClick: false,
          label: {
            color: "#ffffff",
            fontSize: 12,
            fontWeight: 700,
            formatter: (params: { name: string; value: number }) =>
              `${params.name}\n${params.value}`,
          },
          upperLabel: { show: false },
          itemStyle: {
            borderColor: "#ffffff",
            borderWidth: 2,
            gapWidth: 2,
          },
          data,
        },
      ],
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
  () => props.distribution,
  () => {
    if (hasData.value) renderChart();
    else if (chart) chart.clear();
  },
  { deep: true },
);

defineExpose({ total, entries, hasData, labelOf });
</script>

<template>
  <div
    ref="chartEl"
    class="attribution-heatmap"
    :style="{ height: `${height}px` }"
  />
</template>

<style scoped>
.attribution-heatmap {
  width: 100%;
  min-height: 140px;
}
</style>
