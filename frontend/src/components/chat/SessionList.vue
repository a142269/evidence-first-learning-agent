<script setup lang="ts">
import { computed, ref } from "vue";
import {
  Plus,
  MessageSquare,
  User,
  Hash,
  Pin,
  MoreHorizontal,
  Star,
  CheckSquare,
  FileText,
  X,
} from "lucide-vue-next";
import { partners } from "@/constants/companion";

export interface ChatSession {
  id: string;
  type: "group" | "private";
  name: string;
  avatar?: string;
  description?: string;
  lastMessage: string;
  lastTime: number;
  unreadCount: number;
  isPinned: boolean;
  agentKey?: string;
  agentName?: string;
  agentAvatar?: string;
  memberCount?: number;
  onlineCount?: number;
}

const props = defineProps<{
  sessions: ChatSession[];
  currentSessionId: string;
}>();

const emit = defineEmits<{
  (e: "select", session: ChatSession): void;
  (e: "createPrivate", agentKey: string): void;
  (e: "pin", sessionId: string, pinned: boolean): void;
  (e: "delete", sessionId: string): void;
}>();

const showNewChatMenu = ref(false);
const showAgentSelector = ref(false);

// 排序：置顶的在前，然后按时间倒序
const sortedSessions = computed(() => {
  if (!props.sessions || !Array.isArray(props.sessions)) return [];
  return [...props.sessions].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return b.lastTime - a.lastTime;
  });
});

const pinnedSessions = computed(() => sortedSessions.value.filter((s) => s.isPinned));
const unpinnedSessions = computed(() => sortedSessions.value.filter((s) => !s.isPinned));

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) {
    return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } else if (days === 1) {
    return "昨天";
  } else if (days < 7) {
    return ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][d.getDay()];
  } else {
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

function handleCreatePrivateChat(agentKey: string) {
  showAgentSelector.value = false;
  emit("createPrivate", agentKey);
}

function handleSessionClick(session: ChatSession) {
  emit("select", session);
}

function handlePinClick(e: Event, session: ChatSession) {
  e.stopPropagation();
  emit("pin", session.id, !session.isPinned);
}

function handleDeleteClick(e: Event, session: ChatSession) {
  e.stopPropagation();
  if (session.type === "group") return; // 群聊不能删除
  if (confirm(`确定删除与 ${session.name} 的会话吗？`)) {
    emit("delete", session.id);
  }
}
</script>

<template>
  <div class="session-list">
    <!-- 头部 -->
    <div class="session-header">
      <h3>会话列表</h3>
      <div class="header-actions">
        <button
          class="icon-btn"
          title="新建会话"
          @click="showAgentSelector = true"
        >
          <Plus :size="18" />
        </button>
      </div>
    </div>

    <!-- 快捷入口 -->
    <div class="quick-access">
      <div class="quick-item">
        <Star :size="16" />
        <span>收藏消息</span>
      </div>
      <div class="quick-item">
        <CheckSquare :size="16" />
        <span>待办事项</span>
      </div>
      <div class="quick-item">
        <FileText :size="16" />
        <span>最近文件</span>
      </div>
    </div>

    <!-- 会话列表 -->
    <div class="sessions-container">
      <!-- 置顶会话 -->
      <div v-if="pinnedSessions.length > 0" class="session-group">
        <div class="group-label">
          <Pin :size="12" />
          <span>置顶</span>
        </div>
        <div
          v-for="session in pinnedSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="handleSessionClick(session)"
        >
          <div class="session-avatar">
            <img
              v-if="session.avatar || session.agentAvatar"
              :src="session.avatar || session.agentAvatar"
              :alt="session.name"
            />
            <div v-else class="avatar-placeholder">
              <Hash v-if="session.type === 'group'" :size="16" />
              <User v-else :size="16" />
            </div>
            <div v-if="session.type === 'private'" class="online-indicator"></div>
          </div>
          <div class="session-info">
            <div class="session-name-row">
              <span class="session-name">{{ session.name }}</span>
              <span class="session-time">{{ formatTime(session.lastTime) }}</span>
            </div>
            <div class="session-preview">
              <span class="preview-text">{{ truncate(session.lastMessage, 20) }}</span>
              <span v-if="session.unreadCount > 0" class="unread-badge">
                {{ session.unreadCount > 99 ? "99+" : session.unreadCount }}
              </span>
            </div>
          </div>
          <div class="session-actions">
            <button
              class="action-btn"
              :class="{ pinned: session.isPinned }"
              @click="(e) => handlePinClick(e, session)"
            >
              <Pin :size="14" />
            </button>
            <button
              v-if="session.type === 'private'"
              class="action-btn"
              @click="(e) => handleDeleteClick(e, session)"
            >
              <X :size="14" />
            </button>
          </div>
        </div>
      </div>

      <!-- 普通会话 -->
      <div class="session-group">
        <div class="group-label">
          <MessageSquare :size="12" />
          <span>所有会话</span>
        </div>
        <div
          v-for="session in unpinnedSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === currentSessionId }"
          @click="handleSessionClick(session)"
        >
          <div class="session-avatar">
            <img
              v-if="session.avatar || session.agentAvatar"
              :src="session.avatar || session.agentAvatar"
              :alt="session.name"
            />
            <div v-else class="avatar-placeholder">
              <Hash v-if="session.type === 'group'" :size="16" />
              <User v-else :size="16" />
            </div>
            <div v-if="session.type === 'private'" class="online-indicator"></div>
          </div>
          <div class="session-info">
            <div class="session-name-row">
              <span class="session-name">{{ session.name }}</span>
              <span class="session-time">{{ formatTime(session.lastTime) }}</span>
            </div>
            <div class="session-preview">
              <span class="preview-text">{{ truncate(session.lastMessage, 20) }}</span>
              <span v-if="session.unreadCount > 0" class="unread-badge">
                {{ session.unreadCount > 99 ? "99+" : session.unreadCount }}
              </span>
            </div>
          </div>
          <div class="session-actions">
            <button
              class="action-btn"
              :class="{ pinned: session.isPinned }"
              @click="(e) => handlePinClick(e, session)"
            >
              <Pin :size="14" />
            </button>
            <button
              v-if="session.type === 'private'"
              class="action-btn"
              @click="(e) => handleDeleteClick(e, session)"
            >
              <X :size="14" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建私聊选择器 -->
    <div v-if="showAgentSelector" class="agent-selector-modal" @click.self="showAgentSelector = false">
      <div class="agent-selector-content">
        <div class="selector-header">
          <h4>选择AI伙伴开始私聊</h4>
          <button class="close-btn" @click="showAgentSelector = false">
            <X :size="18" />
          </button>
        </div>
        <div class="agent-list">
          <div
            v-for="partner in partners"
            :key="partner.key"
            class="agent-item"
            @click="handleCreatePrivateChat(partner.key)"
          >
            <img :src="partner.avatar" :alt="partner.name" class="agent-avatar" />
            <div class="agent-info">
              <span class="agent-name">{{ partner.name }}</span>
              <span class="agent-title">{{ partner.title }}</span>
              <span class="agent-role">{{ partner.role }}</span>
            </div>
            <div class="agent-status" :class="{ online: partner.state === '在线' }">
              {{ partner.state }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-list {
  width: 260px;
  height: 100%;
  background: #f8fafc;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.session-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e2e8f0;
}

.session-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.icon-btn:hover {
  background: #e2e8f0;
  color: #1f2937;
}

/* 快捷入口 */
.quick-access {
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-bottom: 1px solid #e2e8f0;
}

.quick-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: #4b5563;
  font-size: 13px;
  transition: all 0.2s;
}

.quick-item:hover {
  background: #e2e8f0;
  color: #1f2937;
}

.quick-item svg {
  color: #6b7280;
}

/* 会话列表 */
.sessions-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.session-group {
  margin-bottom: 8px;
}

.group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.session-item:hover {
  background: #f1f5f9;
}

.session-item.active {
  background: #fff7ed;
  border-left: 3px solid #ea580c;
}

.session-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.session-avatar img {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  object-fit: cover;
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  border-radius: 10px;
  background: #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
}

.online-indicator {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 10px;
  height: 10px;
  background: #22c55e;
  border: 2px solid #f8fafc;
  border-radius: 50%;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.session-name {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-time {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
}

.session-preview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.preview-text {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.unread-badge {
  background: #ea580c;
  color: white;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 10px;
  flex-shrink: 0;
}

.session-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.action-btn {
  width: 24px;
  height: 24px;
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

.action-btn.pinned {
  color: #ea580c;
}

/* Agent选择器弹窗 */
.agent-selector-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.agent-selector-content {
  background: white;
  border-radius: 16px;
  width: 400px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
}

.selector-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selector-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #f1f5f9;
  color: #1f2937;
}

.agent-list {
  overflow-y: auto;
  padding: 8px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.agent-item:hover {
  background: #f8fafc;
}

.agent-avatar {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  object-fit: cover;
}

.agent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
}

.agent-title {
  font-size: 13px;
  color: #6b7280;
}

.agent-role {
  font-size: 11px;
  color: #9ca3af;
}

.agent-status {
  font-size: 11px;
  font-weight: 500;
  color: #9ca3af;
  padding: 4px 8px;
  background: #f1f5f9;
  border-radius: 6px;
}

.agent-status.online {
  color: #16a34a;
  background: #dcfce7;
}
</style>
