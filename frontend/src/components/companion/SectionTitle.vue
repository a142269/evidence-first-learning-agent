<script setup lang="ts">
interface Props {
  title: string;
  sub?: string;
}
defineProps<Props>();
</script>

<template>
  <div class="section-head">
    <div class="section-copy">
      <div class="section-title-row">
        <span v-if="$slots.icon" class="section-title-icon">
          <slot name="icon" />
        </span>
        <h2>{{ title }}</h2>
      </div>
      <p v-if="sub">{{ sub }}</p>
    </div>
    <div v-if="$slots.action" class="section-action">
      <slot name="action" />
    </div>
  </div>
</template>

<style scoped>
.section-title-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.section-title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
