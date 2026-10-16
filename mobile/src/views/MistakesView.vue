<script setup lang="ts">
import { BookCheck, NotebookTabs, Plus, Search, X } from "lucide-vue-next";
import { onMounted, ref, watch } from "vue";

import { createMistake, listMistakes } from "@/api";
import PageState from "@/components/PageState.vue";
import type { MobileMistake } from "@/types";

const items = ref<MobileMistake[]>([]); const loading = ref(true); const error = ref("");
const status = ref<"open" | "resolved">("open"); const search = ref(""); const showAdd = ref(false); const saving = ref(false);
const form = ref({ kp_id: "", question: "", student_answer: "", correct_answer: "", error_type: "unknown", course: "artificial_intelligence" });
let timer: number | undefined;
const labels: Record<string, string> = { concept: "概念理解", calculation: "计算错误", careless: "粗心失误", reading: "审题偏差", unknown: "待分析" };
async function load() {
  loading.value = true; error.value = "";
  try { items.value = (await listMistakes({ q: search.value, status: status.value, limit: 60 })).items; }
  catch { error.value = "错题本暂时无法访问。"; }
  finally { loading.value = false; }
}
async function save() {
  if (!form.value.question.trim()) return; saving.value = true;
  try { await createMistake(form.value); showAdd.value = false; form.value = { kp_id: "", question: "", student_answer: "", correct_answer: "", error_type: "unknown", course: "artificial_intelligence" }; await load(); }
  finally { saving.value = false; }
}
function dateLabel(value: number) { return new Date(value * 1000).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }); }
watch([search, status], () => { clearTimeout(timer); timer = window.setTimeout(load, 220); });
onMounted(load);
</script>

<template>
  <div class="page mistake-page">
    <header class="page-header hero-header"><div><p class="eyebrow">复习闭环</p><h1>错题本</h1><p>找到原因，再用一道变式真正掌握</p></div><button class="header-orb action" type="button" aria-label="录入错题" @click="showAdd = true"><Plus :size="24" /></button></header>
    <div class="segmented"><button type="button" :class="{ active: status === 'open' }" @click="status = 'open'"><NotebookTabs :size="17" />待复习</button><button type="button" :class="{ active: status === 'resolved' }" @click="status = 'resolved'"><BookCheck :size="17" />已掌握</button></div>
    <label class="search-box"><Search :size="18" /><input v-model="search" placeholder="搜索题目或知识点" /><span class="sr-only">搜索错题</span></label>
    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="load" />
    <PageState v-else-if="!items.length" kind="empty" :title="status === 'open' ? '没有待复习错题' : '还没有已掌握错题'" :message="status === 'open' ? '完成练习或手动录入一道错题。' : '完成复习后，错题会移动到这里。'" />
    <section v-else class="mistake-list">
      <router-link v-for="(item, index) in items" :key="item.id" class="mistake-card" :to="`/mistakes/${item.id}`">
        <span class="mistake-index">{{ String(index + 1).padStart(2, '0') }}</span><div><span class="mistake-meta"><i>{{ labels[item.error_type] || item.error_type }}</i><time>{{ dateLabel(item.created_at) }}</time></span><h2>{{ item.question || '题目内容待补充' }}</h2><p>{{ item.kp_id || '未标注知识点' }}</p></div>
      </router-link>
    </section>
    <div v-if="showAdd" class="modal-backdrop" @click.self="showAdd = false">
      <form class="bottom-sheet" @submit.prevent="save"><header><div><p class="eyebrow">手动录入</p><h2>添加错题</h2></div><button class="icon-button" type="button" aria-label="关闭" @click="showAdd = false"><X :size="21" /></button></header><label>题目<textarea v-model="form.question" rows="3" required placeholder="输入题目内容" /></label><label>知识点<input v-model="form.kp_id" placeholder="例如 ml_linear_regression" /></label><div class="two-fields"><label>我的答案<textarea v-model="form.student_answer" rows="2" /></label><label>正确答案<textarea v-model="form.correct_answer" rows="2" /></label></div><button class="primary-button" type="submit" :disabled="saving">{{ saving ? '正在保存' : '保存到错题本' }}</button></form>
    </div>
  </div>
</template>
