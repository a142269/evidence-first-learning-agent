<script setup lang="ts">
import { computed } from "vue";

interface Props {
  /** 维度标签（3-6 个），缺省用默认画像维度 */
  labels?: string[];
  /** 维度取值 0-100，缺省用演示数据 */
  values?: number[];
}

const props = defineProps<Props>();

const DEFAULT_LABELS = ["知识基础", "学习能力", "逻辑思维", "实践能力", "学习兴趣", "薄弱点"];
const DEFAULT_VALUES = [70, 85, 75, 60, 90, 40];

const labels = computed(() => {
  const list = props.labels && props.labels.length >= 3 ? props.labels : DEFAULT_LABELS;
  return list.slice(0, 6);
});
const values = computed(() => {
  const list = props.values && props.values.length >= 3 ? props.values : DEFAULT_VALUES;
  return list.slice(0, labels.value.length).map((v) => Math.max(0, Math.min(100, v)));
});

const N = computed(() => labels.value.length);
const R_MAX = 86;

function polar(idx: number, radius: number): [number, number] {
  const angle = -Math.PI / 2 + (2 * Math.PI * idx) / N.value;
  return [Math.cos(angle) * radius, Math.sin(angle) * radius];
}

function ringPoints(r: number): string {
  return Array.from({ length: N.value }, (_, i) => polar(i, r).map((v) => v.toFixed(1)).join(",")).join(" ");
}

const rings = computed(() => [78, 54, 30].map(ringPoints));
const axes = computed(() => Array.from({ length: N.value }, (_, i) => polar(i, R_MAX)));

const shapePoints = computed(() =>
  values.value
    .map((v, i) => polar(i, (v / 100) * R_MAX).map((n) => n.toFixed(1)).join(","))
    .join(" "),
);
const basePoints = computed(() =>
  values.value
    .map((v, i) => polar(i, (v / 100) * R_MAX * 0.72).map((n) => n.toFixed(1)).join(","))
    .join(" "),
);
const dots = computed(() => values.value.map((v, i) => polar(i, (v / 100) * R_MAX)));

interface AxisLabel {
  x: number;
  y: number;
  anchor: "start" | "middle" | "end";
  text: string;
}

const axisLabels = computed<AxisLabel[]>(() =>
  labels.value.map((label, i) => {
    const [x, y] = polar(i, R_MAX + 14);
    const anchor: AxisLabel["anchor"] = Math.abs(x) < 12 ? "middle" : x > 0 ? "start" : "end";
    return {
      x: Math.round(x),
      y: Math.round(y + (Math.abs(x) < 12 ? (y < 0 ? -2 : 12) : 4)),
      anchor,
      text: `${label} ${values.value[i]}`,
    };
  }),
);
</script>

<template>
  <svg class="radar-svg" viewBox="0 0 280 230" role="img" aria-label="学习画像雷达图">
    <defs>
      <radialGradient id="radarAura" cx="50%" cy="45%" r="70%">
        <stop offset="0%" stop-color="#ffe4b8" stop-opacity=".78" />
        <stop offset="100%" stop-color="#ffe4b8" stop-opacity="0" />
      </radialGradient>
    </defs>
    <circle cx="140" cy="112" r="92" fill="url(#radarAura)" />
    <g transform="translate(140 112)">
      <polygon v-for="(r, i) in rings" :key="i" class="radar-axis" :points="r" />
      <line
        v-for="([x, y], i) in axes"
        :key="`axis-${i}`"
        class="radar-axis"
        x1="0"
        y1="0"
        :x2="x.toFixed(1)"
        :y2="y.toFixed(1)"
      />
      <polygon class="radar-base" :points="basePoints" />
      <polygon class="radar-shape" :points="shapePoints" />
      <circle
        v-for="([x, y], i) in dots"
        :key="`dot-${i}`"
        class="radar-dot"
        :cx="x.toFixed(1)"
        :cy="y.toFixed(1)"
        r="4"
      />
      <text
        v-for="(l, i) in axisLabels"
        :key="`label-${i}`"
        :x="l.x"
        :y="l.y"
        :text-anchor="l.anchor"
      >
        {{ l.text }}
      </text>
    </g>
  </svg>
</template>
