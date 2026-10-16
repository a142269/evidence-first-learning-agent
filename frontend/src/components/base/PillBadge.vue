<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "orange" | "ink" | "success" | "warning";
  }>(),
  {
    tone: "orange",
  },
);
</script>

<template>
  <span class="pill-badge" :class="`pill-badge--${tone}`">
    <slot name="icon" />
    <slot />
  </span>
</template>

<style scoped lang="scss">
.pill-badge {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  gap: 8px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
}

.pill-badge--orange {
  border: 1px solid rgba(230, 91, 20, 0.28);
  color: var(--orange);
  background: #fffaf4;
}

.pill-badge--ink {
  border: 1px solid rgba(23, 29, 34, 0.14);
  color: var(--ink);
  background: rgba(255, 255, 255, 0.72);
}

.pill-badge--success {
  border: 1px solid rgba(47, 143, 91, 0.24);
  color: var(--success);
  background: rgba(47, 143, 91, 0.08);
}

.pill-badge--warning {
  border: 1px solid rgba(196, 122, 24, 0.24);
  color: var(--warning);
  background: rgba(196, 122, 24, 0.09);
}
</style>
