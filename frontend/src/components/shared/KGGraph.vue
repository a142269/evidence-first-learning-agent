<script setup lang="ts">
import * as echarts from "echarts";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { KgEdge, KgNeighbor2Hop } from "@/types/cockpit";

const props = withDefaults(
  defineProps<{
    nodes: KgNeighbor2Hop[];
    edges: KgEdge[];
    height?: number;
    /** 中心节点 id（高亮显示）。不填则按 distance===0 自动判定 */
    centerId?: string;
  }>(),
  {
    height: 220,
    centerId: "",
  },
);

const chartEl = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const hasNodes = computed(() => props.nodes.length > 0);

const palette = {
  center: "#2563eb",
  hop1: "#38bdf8",
  hop2: "#94a3b8",
};

function colorOf(node: KgNeighbor2Hop) {
  if (props.centerId && node.id === props.centerId) return palette.center;
  if (node.distance === 0) return palette.center;
  if (node.distance === 1) return palette.hop1;
  return palette.hop2;
}

function symbolOf(node: KgNeighbor2Hop) {
  if (props.centerId && node.id === props.centerId) return 52;
  if (node.distance === 0) return 48;
  if (node.distance === 1) return 36;
  return 28;
}

function renderChart() {
  if (!chartEl.value || !hasNodes.value) return;
  if (!chart) chart = echarts.init(chartEl.value);

  chart.setOption(
    {
      tooltip: {
        formatter: (params: { dataType?: string; data?: { name?: string; value?: number } }) => {
          if (params.dataType === "node" && params.data) {
            const hop = params.data.value === 0 ? "中心" : `${params.data.value} 跳`;
            return `<strong>${params.data.name ?? ""}</strong><br/>距离：${hop}`;
          }
          return "";
        },
      },
      legend: {
        bottom: 0,
        itemWidth: 8,
        itemHeight: 8,
        textStyle: { fontSize: 10, color: "#475569" },
        data: ["中心节点", "1 跳邻居", "2 跳邻居"],
      },
      series: [
        {
          type: "graph",
          layout: "force",
          roam: false,
          top: 8,
          bottom: 24,
          left: 8,
          right: 8,
          force: { repulsion: 130, edgeLength: 70 },
          label: { show: true, color: "#0f172a", fontSize: 11, fontWeight: 600 },
          edgeSymbol: ["none", "arrow"],
          edgeSymbolSize: 6,
          categories: [
            { name: "中心节点", itemStyle: { color: palette.center } },
            { name: "1 跳邻居", itemStyle: { color: palette.hop1 } },
            { name: "2 跳邻居", itemStyle: { color: palette.hop2 } },
          ],
          data: props.nodes.map((node) => ({
            id: node.id,
            name: node.name,
            value: node.distance,
            symbolSize: symbolOf(node),
            category: node.distance === 0 ? 0 : node.distance === 1 ? 1 : 2,
            itemStyle: { color: colorOf(node) },
          })),
          links: props.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            label: { show: false, formatter: edge.type, fontSize: 9 },
            lineStyle: { color: "rgba(37, 99, 235, 0.32)", width: 1.4 },
          })),
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
  () => [props.nodes, props.edges, props.centerId],
  () => {
    if (hasNodes.value) {
      renderChart();
    } else if (chart) {
      chart.clear();
    }
  },
  { deep: true },
);
</script>

<template>
  <div ref="chartEl" class="kg-graph" :style="{ height: `${height}px` }" />
</template>

<style scoped>
.kg-graph {
  width: 100%;
  min-height: 160px;
}
</style>
