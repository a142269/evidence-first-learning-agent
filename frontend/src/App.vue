<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import AppShell from "@/components/layout/AppShell.vue";
import ViewErrorBoundary from "@/components/layout/ViewErrorBoundary.vue";

const route = useRoute();
const useShell = computed(() => route.meta.shell === true);
</script>

<template>
  <AppShell v-if="useShell">
    <ViewErrorBoundary :key="route.fullPath" label="当前页面">
      <router-view />
    </ViewErrorBoundary>
  </AppShell>
  <ViewErrorBoundary v-else :key="route.fullPath" label="当前页面">
    <router-view v-slot="{ Component }">
      <transition name="route-fade" mode="out-in">
        <keep-alive :include="['ChatView']">
          <component :is="Component" />
        </keep-alive>
      </transition>
    </router-view>
  </ViewErrorBoundary>
</template>

<style>
.route-fade-enter-active,
.route-fade-leave-active {
  transition: opacity 0.15s ease;
}

.route-fade-enter-from,
.route-fade-leave-to {
  opacity: 0;
}

</style>
