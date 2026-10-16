<script setup lang="ts">
import { computed } from "vue";

interface Point {
  label: string;
  value: number;
}

interface Props {
  /** 数据点（label 用于 x 轴, value 用于 y 轴 0-100） */
  points: Point[];
  /** 是否高亮末端 */
  highlightEnd?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  highlightEnd: true,
});

const W = 520;
const H = 200;
const PAD_L = 32;
const PAD_R = 14;
const PAD_T = 18;
const PAD_B = 28;

const innerW = W - PAD_L - PAD_R;
const innerH = H - PAD_T - PAD_B;

const data = computed(() =>
  props.points.length >= 2 ? props.points : [
    { label: "05/02", value: 62 },
    { label: "05/03", value: 64 },
    { label: "05/04", value: 66 },
    { label: "05/05", value: 67 },
    { label: "05/06", value: 70 },
    { label: "05/07", value: 72 },
    { label: "05/08", value: 74 },
  ],
);

const yTicks = [0, 25, 50, 75, 100];

const coords = computed(() => {
  const n = data.value.length;
  return data.value.map((p, i) => {
    const x = PAD_L + (n === 1 ? innerW / 2 : (innerW * i) / (n - 1));
    const y = PAD_T + innerH - (Math.max(0, Math.min(100, p.value)) / 100) * innerH;
    return { x, y, ...p };
  });
});

const linePath = computed(() => {
  const pts = coords.value;
  if (!pts.length) return "";
  return pts
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
});

const areaPath = computed(() => {
  const pts = coords.value;
  if (!pts.length) return "";
  const start = `M ${pts[0].x.toFixed(1)} ${(PAD_T + innerH).toFixed(1)}`;
  const up = pts
    .map((p) => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");
  const end = `L ${pts[pts.length - 1].x.toFixed(1)} ${(PAD_T + innerH).toFixed(1)} Z`;
  return `${start} ${up} ${end}`;
});

const lastPoint = computed(() => coords.value[coords.value.length - 1]);
const lastValue = computed(() => lastPoint.value?.value ?? 0);
</script>

<template>
  <div class="trend-chart">
    <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" role="img" aria-label="近7日趋势">
      <defs>
        <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--orange-500)" stop-opacity=".28" />
          <stop offset="100%" stop-color="var(--orange-500)" stop-opacity="0" />
        </linearGradient>
      </defs>

      <!-- y 轴网格线 + 刻度 -->
      <g class="trend-grid">
        <line
          v-for="t in yTicks"
          :key="t"
          :x1="PAD_L"
          :x2="W - PAD_R"
          :y1="PAD_T + innerH - (t / 100) * innerH"
          :y2="PAD_T + innerH - (t / 100) * innerH"
        />
        <text
          v-for="t in yTicks"
          :key="`yt-${t}`"
          :x="PAD_L - 6"
          :y="PAD_T + innerH - (t / 100) * innerH + 3"
          text-anchor="end"
        >{{ t }}%</text>
      </g>

      <!-- 区域填充 -->
      <path :d="areaPath" fill="url(#trendFill)" />

      <!-- 折线 -->
      <path :d="linePath" class="trend-line" />

      <!-- 数据点 -->
      <g>
        <circle
          v-for="(p, i) in coords"
          :key="`pt-${i}`"
          :cx="p.x"
          :cy="p.y"
          r="3"
          class="trend-dot"
        />
      </g>

      <!-- 末端高亮徽标 -->
      <g v-if="highlightEnd && lastPoint">
        <rect
          :x="lastPoint.x - 22"
          :y="lastPoint.y - 26"
          width="44"
          height="20"
          rx="10"
          class="trend-badge"
        />
        <text
          :x="lastPoint.x"
          :y="lastPoint.y - 12"
          text-anchor="middle"
          class="trend-badge-text"
        >{{ lastValue }}%</text>
      </g>

      <!-- x 轴标签 -->
      <g class="trend-x">
        <text
          v-for="(p, i) in coords"
          :key="`xt-${i}`"
          :x="p.x"
          :y="H - 8"
          text-anchor="middle"
        >{{ p.label }}</text>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.trend-chart {
  width: 100%;
  height: 220px;
}

.trend-chart svg {
  width: 100%;
  height: 100%;
  display: block;
}

.trend-grid line {
  stroke: var(--neutral-200);
  stroke-width: 1;
  stroke-dasharray: 3 3;
}

.trend-grid text {
  font-size: 10px;
  fill: var(--muted);
}

.trend-line {
  fill: none;
  stroke: var(--orange-500);
  stroke-width: 2.4;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.trend-dot {
  fill: #fff;
  stroke: var(--orange-500);
  stroke-width: 2;
}

.trend-badge {
  fill: var(--orange-500);
}

.trend-badge-text {
  font-size: 11px;
  font-weight: 600;
  fill: #fff;
  font-family: var(--serif);
}

.trend-x text {
  font-size: 10.5px;
  fill: var(--muted);
}
</style>