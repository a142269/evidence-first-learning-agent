<script setup lang="ts">
import { computed, ref } from "vue";
import { Search, User, MessageCircle, MoreHorizontal, X } from "lucide-vue-next";
import { partners } from "@/constants/companion";

export interface GroupMember {
  key: string;
  name: string;
  title: string;
  role: string;
  avatar: string;
  state: string;
  isOnline: boolean;
  isStudent: boolean;
  isTeacher?: boolean;
}

const props = defineProps<{
  members: GroupMember[];
}>();

const emit = defineEmits<{
  (e: "privateChat", agentKey: string): void;
}>();

const searchQuery = ref("");
const showMenuFor = ref<string | null>(null);

const filteredMembers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return props.members;
  return props.members.filter(
    (m) =>
      m.name.toLowerCase().includes(q) ||
      m.title.toLowerCase().includes(q) ||
      m.role.toLowerCase().includes(q)
  );
});

const onlineMembers = computed(() => filteredMembers.value.filter((m) => m.isOnline));
const offlineMembers = computed(() => filteredMembers.value.filter((m) => !m.isOnline));

function handlePrivateChat(member: GroupMember) {
  if (member.isStudent) return;
  emit("privateChat", member.key);
  showMenuFor.value = null;
}

function showMenu(memberKey: string) {
  showMenuFor.value = showMenuFor.value === memberKey ? null : memberKey;
}
</script>

<template>
  <div class="member-list-panel">
    <!-- 搜索 -->
    <div class="member-search">
      <Search :size="14" class="search-icon" />
      <input
        v-model="searchQuery"
        type="text"
        placeholder="搜索成员..."
        class="search-input"
      />
      <button v-if="searchQuery" class="clear-btn" @click="searchQuery = ''">
        <X :size="14" />
      </button>
    </div>

    <!-- 在线成员 -->
    <div class="member-section">
      <div class="section-header">
        <span class="section-title">在线</span>
        <span class="section-count">{{ onlineMembers.length }}</span>
      </div>
      <div class="member-items">
        <div
          v-for="member in onlineMembers"
          :key="member.key"
          class="member-item"
          :class="{ student: member.isStudent }"
        >
          <div class="member-avatar">
            <img v-if="member.avatar" :src="member.avatar" :alt="member.name" />
            <div v-else class="avatar-fallback" :class="{ teacher: member.isTeacher, learner: member.isStudent && !member.isTeacher }">
              <span v-if="member.isTeacher" class="avatar-fallback-glyph">师</span>
              <User v-if="!member.isTeacher" :size="16" />
            </div>
            <div class="status-dot online"></div>
          </div>
          <div class="member-info">
            <div class="member-name-row">
              <span class="name">{{ member.name }}</span>
              <span v-if="member.isStudent" :class="['tag', member.key.startsWith('teacher') ? 'teacher' : '']">
                {{ member.key.startsWith("teacher") ? "师" : "我" }}
              </span>
            </div>
            <span class="title">{{ member.title }}</span>
            <span class="role">{{ member.role }}</span>
          </div>
          <div class="member-actions">
            <button
              v-if="!member.isStudent"
              class="action-btn"
              title="私聊"
              @click="handlePrivateChat(member)"
            >
              <MessageCircle :size="14" />
            </button>
            <button class="action-btn" @click="showMenu(member.key)">
              <MoreHorizontal :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 离线/忙碌成员 -->
    <div v-if="offlineMembers.length > 0" class="member-section">
      <div class="section-header">
        <span class="section-title">离线/忙碌</span>
        <span class="section-count">{{ offlineMembers.length }}</span>
      </div>
      <div class="member-items">
        <div
          v-for="member in offlineMembers"
          :key="member.key"
          class="member-item offline"
        >
          <div class="member-avatar">
            <img v-if="member.avatar" :src="member.avatar" :alt="member.name" />
            <div v-else class="avatar-fallback" :class="{ teacher: member.isTeacher, learner: member.isStudent && !member.isTeacher }">
              <span v-if="member.isTeacher" class="avatar-fallback-glyph">师</span>
              <User v-if="!member.isTeacher" :size="16" />
            </div>
            <div class="status-dot busy"></div>
          </div>
          <div class="member-info">
            <div class="member-name-row">
              <span class="name">{{ member.name }}</span>
            </div>
            <span class="title">{{ member.title }}</span>
            <span class="role">{{ member.role }}</span>
          </div>
          <div class="member-actions">
            <button
              class="action-btn"
              title="私聊"
              @click="handlePrivateChat(member)"
            >
              <MessageCircle :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.member-list-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.member-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e2e8f0;
  position: relative;
}

.search-icon {
  color: #9ca3af;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: #1f2937;
  outline: none;
}

.search-input::placeholder {
  color: #9ca3af;
}

.clear-btn {
  width: 20px;
  height: 20px;
  border-radius: 4px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.clear-btn:hover {
  background: #f1f5f9;
  color: #1f2937;
}

.member-section {
  flex: 1;
  overflow-y: auto;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px 8px;
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-count {
  color: #9ca3af;
  font-size: 11px;
}

.member-items {
  padding: 0 8px;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.member-item:hover {
  background: #f8fafc;
}

.member-item.student {
  background: #fff7ed;
}

.member-item.offline {
  opacity: 0.7;
}

.member-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.member-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  object-fit: cover;
}

.avatar-fallback {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.avatar-fallback.teacher {
  background: linear-gradient(135deg, #fff1df, #f3c58f);
  color: #8a4b16;
  border: 1px solid #e8b878;
  font-weight: 800;
}

.avatar-fallback.learner {
  background: linear-gradient(135deg, #fff7ed, #fed7aa);
  color: #c2410c;
}

.avatar-fallback-glyph {
  font-size: 16px;
  line-height: 1;
}

.status-dot {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid white;
}

.status-dot.online {
  background: #22c55e;
}

.status-dot.busy {
  background: #f59e0b;
}

.member-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.name {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
}

.tag {
  font-size: 10px;
  font-weight: 600;
  color: #ea580c;
  background: #fff7ed;
  padding: 2px 6px;
  border-radius: 4px;
}

.tag.teacher {
  color: #92400e;
  background: #fdf1e0;
}

.title {
  font-size: 12px;
  color: #6b7280;
}

.role {
  font-size: 11px;
  color: #9ca3af;
}

.member-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.member-item:hover .member-actions {
  opacity: 1;
}

.action-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #e2e8f0;
  color: #1f2937;
}
</style>
