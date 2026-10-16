<script setup lang="ts">
interface Props {
  deco?: boolean;
}
withDefaults(defineProps<Props>(), { deco: false });
</script>

<template>
  <section :class="['art-card', deco ? 'art-card-deco' : '']">
    <slot />
  </section>
</template>
