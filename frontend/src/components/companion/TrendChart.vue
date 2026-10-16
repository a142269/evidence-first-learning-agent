<script setup lang="ts">
import { computed } from "vue";

interface Props {
  large?: boolean;
}

const props = withDefaults(defineProps<Props>(), { large: false });

const width = computed(() => (props.large ? 560 : 340));
const height = computed(() => (props.large ? 210 : 170));

const pointsList = computed<string[]>(() =>
  props.large
    ? [
        "40,68 136,60 232,48 328,42 424,39 530,34",
        "40,150 136,130 232,110 328,96 424,85 530,72",
        "40,128 136,112 232,99 328,90 424,82 530,68",
      ]
    : ["28,122 84,110 142,105 202,76 270,55 316,36"],
);

const colors = computed<string[]>(() =>
  props.large ? ["#ea5a1a", "#f1a63a", "#9a642d"] : ["url(#lineWarm)"],
);

const gridYs = computed(() => [height.value - 36, height.value - 78, height.value - 120]);

const viewBox = computed(() => `0 0 ${width.value} ${height.value}`);

function dotPoints(p: string): Array<[string, string]> {
  return p.split(" ").map((pt) => pt.split(",") as [string, string]);
}

function dotColor(i: number): string {
  return props.large ? colors.value[i] : "#ea5a1a";
}
</script>

<template>
  <svg class="trend-svg" :viewBox="viewBox" role="img" aria-label="学习趋势图">
    <defs>
      <linearGradient id="lineWarm" x1="0" x2="1">
        <stop offset="0%" stop-color="#f3b347" />
        <stop offset="100%" stop-color="#ea5a1a" />
      </linearGradient>
    </defs>
    <line v-for="y in gridYs" :key="y" :x1="24" :y1="y" :x2="width - 24" :y2="y" class="chart-grid" />
    <g v-for="(p, i) in pointsList" :key="p">
      <polyline
        :points="p"
        fill="none"
        :stroke="colors[i]"
        stroke-width="3.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle
        v-for="[x, y] in dotPoints(p)"
        :key="`${p}-${x}-${y}`"
        :cx="x"
        :cy="y"
        r="4"
        :fill="dotColor(i)"
      />
    </g>
    <g class="chart-labels">
      <text :x="24" :y="height - 12">05-03</text>
      <text :x="width * 0.25" :y="height - 12">05-10</text>
      <text :x="width * 0.47" :y="height - 12">05-17</text>
      <text :x="width * 0.69" :y="height - 12">05-24</text>
      <text :x="width - 58" :y="height - 12">今天</text>
    </g>
  </svg>
</template>
