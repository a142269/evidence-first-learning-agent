<script setup lang="ts">
import { computed } from "vue";
import { markedWithMath } from "@/utils/markedWithMath";

const props = defineProps<{
  content: string;
}>();

function sanitize(html: string) {
  return html
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, "")
    .replace(/\son\w+="[^"]*"/gi, "")
    .replace(/\son\w+='[^']*'/gi, "");
}

const html = computed(() => sanitize(markedWithMath.parse(props.content || "")));
</script>

<template>
  <div class="markdown-block" v-html="html" />
</template>

<style scoped>
.markdown-block {
  color: #334155;
  font-size: 13px;
  line-height: 1.72;
}

.markdown-block :deep(p) {
  margin: 0 0 8px;
}

.markdown-block :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-block :deep(ul),
.markdown-block :deep(ol) {
  margin: 8px 0;
  padding-left: 18px;
}

.markdown-block :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: #eef2ff;
  color: #1d4ed8;
  font-size: 12px;
}

.markdown-block :deep(pre) {
  overflow: auto;
  padding: 10px;
  border-radius: 6px;
  background: #0f172a;
  color: #e2e8f0;
}

.markdown-block :deep(.katex) {
  font-size: 1.05em;
}

.markdown-block :deep(.katex-display) {
  margin: 8px 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 2px 0;
}

.markdown-block :deep(.katex-block) {
  margin: 10px 0;
  text-align: center;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 4px 0;
}
</style>
