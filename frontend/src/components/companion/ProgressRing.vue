<script setup lang="ts">
import { computed } from "vue";

interface Props {
  value?: number;
  label?: string;
  size?: "sm" | "md";
}

const props = withDefaults(defineProps<Props>(), {
  value: 75,
  size: "md",
});

const ringStyle = computed(() => ({ "--value": `${props.value}%` }));
const displayLabel = computed(() => props.label ?? `${props.value}%`);
</script>

<template>
  <div :class="['progress-ring', `progress-ring-${size}`]" :style="ringStyle">
    <strong>{{ displayLabel }}</strong>
  </div>
</template>
