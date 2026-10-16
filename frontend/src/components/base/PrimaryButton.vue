<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    loading?: boolean;
    disabled?: boolean;
    block?: boolean;
  }>(),
  {
    type: "button",
    loading: false,
    disabled: false,
    block: false,
  },
);
</script>

<template>
  <button class="primary-button" :class="{ 'primary-button--block': block }" :type="type" :disabled="disabled || loading">
    <span v-if="loading" class="primary-button__spinner" aria-hidden="true"></span>
    <slot name="icon" />
    <span class="primary-button__label"><slot /></span>
  </button>
</template>

<style scoped lang="scss">
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 42px;
  gap: 10px;
  padding: 0 18px;
  border: 0;
  border-radius: var(--radius-sm);
  color: #fff;
  background: linear-gradient(180deg, #ef681b, #e7500d);
  box-shadow: var(--shadow-btn);
  cursor: pointer;
  font-weight: 900;
  transition: 0.18s ease;
}

.primary-button--block {
  width: 100%;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 18px 30px rgba(223, 78, 13, 0.26);
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
  filter: grayscale(0.25);
}

.primary-button__spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.48);
  border-top-color: #fff;
  border-radius: 999px;
  animation: primary-button-spin 0.8s linear infinite;
}

@keyframes primary-button-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
