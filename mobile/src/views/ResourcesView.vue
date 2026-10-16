<script setup lang="ts">
import { BookOpen, Code2, FileText, PlayCircle, Search, Sparkles } from "lucide-vue-next";
import { computed, onMounted, ref, watch } from "vue";

import { listResources } from "@/api";
import PageState from "@/components/PageState.vue";
import type { MobileResource } from "@/types";

const items = ref<MobileResource[]>([]);
const loading = ref(true);
const error = ref("");
const search = ref("");
const type = ref("");
let timer: number | undefined;
const types = [
  { key: "", label: "全部" }, { key: "document", label: "讲义" },
  { key: "video", label: "视频" }, { key: "code", label: "代码" }, { key: "quiz", label: "练习" },
];
function iconFor(value: string) { return value === "video" ? PlayCircle : value === "code" ? Code2 : value === "quiz" ? Sparkles : FileText; }
function dateLabel(value: number) { return new Date(value * 1000).toLocaleDateString("zh-CN", { month: "long", day: "numeric" }); }
async function load() {
  loading.value = true; error.value = "";
  try { items.value = (await listResources({ q: search.value, resource_type: type.value, limit: 50 })).items; }
  catch { error.value = "资源库暂时无法访问。"; }
  finally { loading.value = false; }
}
watch([search, type], () => { clearTimeout(timer); timer = window.setTimeout(load, 250); });
onMounted(load);
</script>

<template>
  <div class="page resource-page">
    <header class="page-header hero-header"><div><p class="eyebrow">学习资料</p><h1>资源库</h1><p>课程讲义、视频与练习集中整理</p></div><span class="header-orb"><BookOpen :size="24" /></span></header>
    <label class="search-box"><Search :size="18" /><input v-model="search" placeholder="搜索标题、内容或标签" /><span class="sr-only">搜索资源</span></label>
    <div class="chip-scroller" role="tablist" aria-label="资源类型">
      <button v-for="option in types" :key="option.key" type="button" :class="{ active: type === option.key }" @click="type = option.key">{{ option.label }}</button>
    </div>
    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="load" />
    <PageState v-else-if="!items.length" kind="empty" title="没有匹配的资源" message="试试其他关键词或分类。" />
    <section v-else class="resource-list">
      <router-link v-for="item in items" :key="item.id" class="resource-card" :to="`/resources/${item.id}`">
        <span class="resource-icon"><component :is="iconFor(item.type)" :size="22" /></span>
        <div><span class="resource-card__meta">{{ item.type.toUpperCase() }} · {{ dateLabel(item.created_at) }}</span><h2>{{ item.title }}</h2><p>{{ item.content?.slice(0, 70) || '点击查看资源详情' }}</p><span class="tag-row"><i v-for="tag in item.tags?.slice(0, 3)" :key="tag">{{ tag }}</i></span></div>
      </router-link>
    </section>
  </div>
</template>
