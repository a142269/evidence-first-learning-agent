<script setup lang="ts">
import { BrainCircuit, CheckCircle2, ChevronLeft, LoaderCircle, RefreshCw, Sparkles } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { getMistake, mistakeAction } from "@/api";
import PageState from "@/components/PageState.vue";
import type { MobileMistake } from "@/types";

const route = useRoute(); const router = useRouter(); const item = ref<MobileMistake | null>(null);
const loading = ref(true); const error = ref(""); const activeAction = ref(""); const result = ref<any>(null);
async function load() { loading.value = true; try { item.value = (await getMistake(String(route.params.id))).mistake; } catch { error.value = "无法读取这道错题。"; } finally { loading.value = false; } }
async function run(action: "analyze" | "remediation" | "variants" | "resolve") {
  if (!item.value) return; activeAction.value = action;
  try { result.value = await mistakeAction(item.value.id, action); if (action === "resolve") { item.value.resolved = true; window.setTimeout(() => router.replace("/mistakes"), 700); } }
  finally { activeAction.value = ""; }
}
function asText(value: unknown) { return typeof value === "string" ? value : JSON.stringify(value, null, 2); }
onMounted(load);
</script>

<template>
  <div class="detail-page mistake-detail-page">
    <header class="detail-header"><button class="icon-button" type="button" aria-label="返回" @click="router.back()"><ChevronLeft :size="23" /></button><h1>错题复习</h1><span /></header>
    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="load" />
    <main v-else-if="item" class="detail-content">
      <section class="question-card"><span class="question-label">题目</span><h2>{{ item.question }}</h2><dl><div><dt>我的答案</dt><dd>{{ item.student_answer || '未填写' }}</dd></div><div><dt>正确答案</dt><dd>{{ item.correct_answer || '待补充' }}</dd></div></dl></section>
      <section v-if="item.analysis" class="analysis-card"><span><BrainCircuit :size="20" />已有分析</span><p>{{ item.analysis }}</p></section>
      <section class="action-grid"><button type="button" @click="run('analyze')"><BrainCircuit :size="21" /><strong>AI 归因</strong><small>识别错误根源</small></button><button type="button" @click="run('remediation')"><Sparkles :size="21" /><strong>补救建议</strong><small>生成复习方案</small></button><button type="button" @click="run('variants')"><RefreshCw :size="21" /><strong>变式练习</strong><small>检验真正掌握</small></button></section>
      <section v-if="activeAction" class="result-card loading-result"><LoaderCircle class="spin" :size="22" />学习助理正在处理...</section>
      <section v-else-if="result && !result.status" class="result-card"><h3>学习助理建议</h3><pre>{{ asText(result.analysis || result.attribution || result.variants || result) }}</pre></section>
      <button class="master-button" type="button" :disabled="item.resolved || !!activeAction" @click="run('resolve')"><CheckCircle2 :size="20" />{{ item.resolved ? '已标记掌握' : '我已掌握这道题' }}</button>
    </main>
  </div>
</template>
