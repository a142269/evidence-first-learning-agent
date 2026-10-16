<script setup lang="ts">
import { Circle, Plus, Search } from "lucide-vue-next";
import { computed, onMounted, ref } from "vue";

import { listRooms } from "@/api";
import PageState from "@/components/PageState.vue";
import { agentAvatarFor } from "@/constants/agentAvatars";
import { useAuthStore } from "@/stores/auth";
import type { MobileRoom } from "@/types";
import { markdownToChatText } from "@/utils/chat";

const auth = useAuthStore();
const rooms = ref<MobileRoom[]>([]);
const loading = ref(true);
const error = ref("");
const search = ref("");
const searchInput = ref<HTMLInputElement | null>(null);
const visibleRooms = computed(() => {
  const needle = search.value.trim().toLowerCase();
  if (!needle) return rooms.value;
  return rooms.value.filter((room) => [room.name, room.description, room.peer?.display_name]
    .some((value) => String(value || "").toLowerCase().includes(needle)));
});
const profileInitial = computed(() => (auth.user?.display_name || "学").slice(0, 1));

function timeLabel(value?: number) {
  if (!value) return "";
  const date = new Date(value * 1000);
  const now = new Date();
  return date.toDateString() === now.toDateString()
    ? date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
    : date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function roomPreview(room: MobileRoom) {
  const message = room.last_message;
  if (!message) return room.description;
  const content = message.sender_role === "agent" ? markdownToChatText(message.content) : message.content;
  const sender = room.room_type === "group" && message.sender_name ? `${message.sender_name}：` : "";
  return `${sender}${content}`;
}

async function load() {
  loading.value = true; error.value = "";
  try { rooms.value = (await listRooms()).rooms; }
  catch { error.value = "无法获取会话，请检查后端连接。"; }
  finally { loading.value = false; }
}
onMounted(load);
</script>

<template>
  <div class="page page--rooms">
    <header class="rooms-profile-bar">
      <span class="rooms-profile-avatar">{{ profileInitial }}</span>
      <div class="rooms-profile-copy">
        <h1>{{ auth.user?.display_name || '同学' }}</h1>
        <p><Circle :size="8" fill="currentColor" /> 在线 · 学生端</p>
      </div>
      <button class="rooms-add-button" type="button" aria-label="查找课程群" @click="searchInput?.focus()">
        <Plus :size="28" />
      </button>
    </header>
    <label class="search-box rooms-search"><Search :size="20" /><input ref="searchInput" v-model="search" placeholder="搜索群聊或成员" /><span class="sr-only">搜索群聊或成员</span></label>
    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="load" />
    <PageState v-else-if="!visibleRooms.length" kind="empty" title="暂无会话" message="课程群、学习 Agent 和教师会话会显示在这里。" />
    <section v-else class="room-list" aria-label="会话列表">
      <router-link v-for="room in visibleRooms" :key="room.id" v-memo="[room.id, room.unread_count, room.last_message?.id]" class="room-row" :to="`/chat/${room.id}`">
        <span v-if="room.room_type === 'group'" class="room-avatar room-avatar--group" aria-hidden="true">
          <img src="/avatars/zhihu.png" alt=""><img src="/avatars/zhiling.png" alt="">
          <img src="/avatars/xiaolong.png" alt=""><img src="/avatars/ajiang.png" alt="">
          <i v-if="room.unread_count" class="room-avatar-badge">{{ room.unread_count > 99 ? '99+' : room.unread_count }}</i>
        </span>
        <span v-else-if="room.peer?.role === 'agent'" class="room-avatar room-avatar--direct" aria-hidden="true">
          <img :src="agentAvatarFor(room.peer.user_id, room.peer.display_name)" alt="">
          <i v-if="room.unread_count" class="room-avatar-badge">{{ room.unread_count > 99 ? '99+' : room.unread_count }}</i>
        </span>
        <span v-else class="room-avatar room-avatar--teacher" aria-hidden="true">
          {{ room.peer?.display_name.slice(0, 1) || '师' }}
          <i v-if="room.unread_count" class="room-avatar-badge">{{ room.unread_count > 99 ? '99+' : room.unread_count }}</i>
        </span>
        <span class="room-main">
          <span class="room-title"><strong>{{ room.name }}</strong><time>{{ timeLabel(room.last_message?.created_at) }}</time></span>
          <span class="room-preview">{{ roomPreview(room) }}</span>
        </span>
      </router-link>
    </section>
  </div>
</template>
