<script setup lang="ts">
import { ChevronLeft, Download, LoaderCircle, MessageCircle, Share2 } from "lucide-vue-next";
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { downloadResource, getResource, listRooms, sendMessage } from "@/api";
import { createClientMessageId } from "@/api/client";
import PageState from "@/components/PageState.vue";
import type { MobileResource, MobileRoom } from "@/types";

const route = useRoute(); const router = useRouter();
const item = ref<MobileResource | null>(null);
const rooms = ref<MobileRoom[]>([]);
const loading = ref(true); const error = ref(""); const downloading = ref(false);
const sharing = ref(false); const shareRoom = ref(""); const shareDone = ref(false);
async function load() {
  loading.value = true;
  try { item.value = (await getResource(String(route.params.id))).resource; rooms.value = (await listRooms()).rooms.filter((room) => room.room_type === "group"); shareRoom.value = rooms.value[0]?.id || ""; }
  catch { error.value = "无法读取这份资源，可能已下架。"; }
  finally { loading.value = false; }
}
async function downloadFile() {
  if (!item.value) return; downloading.value = true;
  try { const blob = await downloadResource(item.value.id); const url = URL.createObjectURL(blob); const anchor = document.createElement("a"); anchor.href = url; anchor.download = String(item.value.metadata?.attachment?.filename || item.value.title); anchor.click(); URL.revokeObjectURL(url); }
  catch { window.alert("该资源没有可下载附件"); }
  finally { downloading.value = false; }
}
async function share() {
  if (!item.value || !shareRoom.value) return; sharing.value = true;
  try { await sendMessage(shareRoom.value, { content: "", message_type: "resource_card", client_message_id: createClientMessageId(), payload: { resource_id: item.value.id } }); shareDone.value = true; }
  finally { sharing.value = false; }
}
onMounted(load);
</script>

<template>
  <div class="detail-page">
    <header class="detail-header"><button class="icon-button" type="button" aria-label="返回" @click="router.back()"><ChevronLeft :size="23" /></button><h1>资源详情</h1><span /></header>
    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="load" />
    <main v-else-if="item" class="detail-content resource-detail">
      <p class="eyebrow">{{ item.type.toUpperCase() }} · {{ item.agent_name || '课程资源' }}</p><h2>{{ item.title }}</h2>
      <div class="tag-row"><i v-for="tag in item.tags" :key="tag">{{ tag }}</i></div>
      <article class="reading-surface">{{ item.content || '资源正文请通过附件查看。' }}</article>
      <section class="share-panel"><span class="share-panel__icon"><Share2 :size="21" /></span><div><strong>分享到课程群</strong><p>让同学和老师一起查看这份资料</p></div><select v-model="shareRoom" aria-label="选择课程群"><option v-for="room in rooms" :key="room.id" :value="room.id">{{ room.name }}</option></select><button class="secondary-button" type="button" :disabled="sharing || !shareRoom" @click="share"><LoaderCircle v-if="sharing" class="spin" :size="17" /><MessageCircle v-else :size="17" />{{ shareDone ? '已分享' : '分享' }}</button></section>
    </main>
    <footer v-if="item" class="detail-actions"><button class="primary-button" type="button" :disabled="downloading" @click="downloadFile"><LoaderCircle v-if="downloading" class="spin" :size="18" /><Download v-else :size="18" />下载附件</button></footer>
  </div>
</template>
