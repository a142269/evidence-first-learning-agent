<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    state: "healthy" | "degraded" | "empty";
    label?: string;
  }>(),
  {
    label: undefined,
  },
);

const labels = {
  healthy: "正常",
  degraded: "降级",
  empty: "暂无",
};
</script>

<template>
  <span class="status-chip" :class="`status-chip--${props.state}`">
    <i aria-hidden="true"></i>
    {{ props.label ?? labels[props.state] }}
  </span>
</template>

<style scoped lang="scss">
.status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  gap: 7px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.status-chip i {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
}

.status-chip--healthy {
  color: var(--success);
  background: rgba(47, 143, 91, 0.1);
}

.status-chip--degraded {
  color: var(--warning);
  background: rgba(196, 122, 24, 0.1);
}

.status-chip--empty {
  color: var(--gray-500);
  background: rgba(113, 113, 122, 0.1);
}
</style>

