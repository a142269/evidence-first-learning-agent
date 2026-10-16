<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    padding?: "lg" | "md";
    muted?: boolean;
  }>(),
  {
    padding: "lg",
    muted: false,
  },
);
</script>

<template>
  <section class="paper-card" :class="[`paper-card--${padding}`, { 'paper-card--muted': muted }]">
    <header v-if="title || $slots.header" class="paper-card__header">
      <slot name="header">
        <h2>{{ title }}</h2>
      </slot>
    </header>
    <slot />
  </section>
</template>

<style scoped lang="scss">
.paper-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 251, 245, 0.95)),
    rgba(255, 255, 255, 0.94);
  box-shadow: var(--shadow-card);
}

.paper-card--lg {
  padding: 30px;
}

.paper-card--md {
  padding: 22px;
}

.paper-card--muted {
  background:
    linear-gradient(180deg, rgba(255, 250, 243, 0.92), rgba(250, 240, 224, 0.9)),
    rgba(255, 255, 255, 0.78);
  box-shadow: 0 18px 46px rgba(105, 70, 35, 0.09);
}

.paper-card__header {
  margin-bottom: 18px;
}

.paper-card__header h2 {
  margin: 0;
  font-family: var(--serif-cn);
  font-size: 24px;
  font-weight: 900;
  line-height: 1.2;
}
</style>
