<script setup lang="ts">
import { computed } from "vue";
import type { CompanionPartner } from "@/constants/companion";
import Avatar from "./Avatar.vue";

interface Props {
  partners: CompanionPartner[];
  limit?: number;
}

const props = withDefaults(defineProps<Props>(), { limit: 6 });
const visible = computed(() => props.partners.slice(0, props.limit));
</script>

<template>
  <div class="avatar-stack" aria-label="协作学习伙伴">
    <Avatar v-for="p in visible" :key="p.key" :partner="p" size="sm" />
  </div>
</template>
