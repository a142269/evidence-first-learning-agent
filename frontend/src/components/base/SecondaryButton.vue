<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
    block?: boolean;
  }>(),
  {
    type: "button",
    disabled: false,
    block: false,
  },
);
</script>

<template>
  <button class="secondary-button" :class="{ 'secondary-button--block': block }" :type="type" :disabled="disabled">
    <slot name="icon" />
    <span class="secondary-button__label"><slot /></span>
  </button>
</template>

<style scoped lang="scss">
.secondary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  gap: 10px;
  padding: 0 18px;
  border: 1px solid rgba(45, 34, 24, 0.32);
  border-radius: var(--radius-sm);
  color: var(--ink);
  background: rgba(255, 255, 255, 0.74);
  cursor: pointer;
  font-weight: 900;
  transition: 0.18s ease;
}

.secondary-button--block {
  width: 100%;
}

.secondary-button:hover:not(:disabled) {
  border-color: rgba(233, 85, 20, 0.55);
  background: rgba(255, 250, 243, 0.92);
}

.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}
</style>
