<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { CompanionPartner } from "@/constants/companion";

interface Props {
  partner?: Partial<CompanionPartner>;
  size?: "xs" | "sm" | "md" | "lg";
  pulse?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  size: "md",
  pulse: false,
});

const accentVar = computed(() => ({ "--avatar-accent": props.partner?.accent ?? "#ea5a1a" }));
const fallback = computed(() => props.partner?.name?.slice(0, 1) ?? "张");
const imageFailed = ref(false);

watch(() => props.partner?.avatar, () => {
  imageFailed.value = false;
});
</script>

<template>
  <span
    :class="['avatar', `avatar-${size}`, pulse ? 'avatar-pulse' : '']"
    :style="accentVar"
    :title="partner?.name"
  >
    <img
      v-if="partner?.avatar && !imageFailed"
      :src="partner.avatar"
      :alt="partner.name"
      @error="imageFailed = true"
    />
    <span v-else>{{ fallback }}</span>
  </span>
</template>
