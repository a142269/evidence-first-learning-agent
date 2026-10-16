<script setup lang="ts">
import { BookOpen, MessageCircle, NotebookTabs, UserRound } from "lucide-vue-next";

const tabs = [
  { to: "/messages", label: "消息", icon: MessageCircle },
  { to: "/mistakes", label: "错题", icon: NotebookTabs },
  { to: "/resources", label: "资源", icon: BookOpen },
  { to: "/me", label: "我的", icon: UserRound },
];
</script>

<template>
  <div class="mobile-shell">
    <main class="shell-content"><router-view /></main>
    <nav class="bottom-nav" aria-label="主要导航">
      <router-link v-for="tab in tabs" :key="tab.to" :to="tab.to" class="bottom-nav__item">
        <component :is="tab.icon" :size="22" :stroke-width="2" />
        <span>{{ tab.label }}</span>
      </router-link>
    </nav>
  </div>
</template>
