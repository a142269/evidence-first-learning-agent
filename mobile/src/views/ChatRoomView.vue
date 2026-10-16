<script setup lang="ts">
import {
  ArrowDown,
  AtSign,
  ChevronLeft,
  CircleAlert,
  CornerUpLeft,
  FileUp,
  LoaderCircle,
  MoreHorizontal,
  RotateCcw,
  UsersRound,
  WifiOff,
  X,
} from "lucide-vue-next";
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { listMembers, listMessages, listRooms, markRead, sendMessage } from "@/api";
import { ApiError, createClientMessageId, loadToken, websocketUrl } from "@/api/client";
import PageState from "@/components/PageState.vue";
import { agentAvatarFor } from "@/constants/agentAvatars";
import { useAuthStore } from "@/stores/auth";
import type { MobileMember, MobileMessage, MobileRoom } from "@/types";
import { buildAgentMentions, markdownToChatText, shortMemberName } from "@/utils/chat";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const roomId = String(route.params.roomId);
const room = ref<MobileRoom | null>(null);
const members = ref<MobileMember[]>([]);
const messages = ref<MobileMessage[]>([]);
const loading = ref(true);
const loadingOlder = ref(false);
const error = ref("");
const hasMore = ref(false);
const cursor = ref("");
const draft = ref("");
const sending = ref(false);
const sendError = ref("");
const replyTo = ref<MobileMessage | null>(null);
const listElement = ref<HTMLElement | null>(null);
const composerElement = ref<HTMLTextAreaElement | null>(null);
const memberPanelOpen = ref(false);
const mentionPanelOpen = ref(false);
const typingAgent = ref<{ id: string; name: string } | null>(null);
const expandedMessageIds = ref(new Set<string>());
const connection = ref<"connecting" | "online" | "offline">("connecting");
let socket: WebSocket | null = null;
let reconnectTimer: number | null = null;
let reconnectAttempt = 0;
let disposed = false;

const agentMembers = computed(() => members.value.filter((member) => member.role === "agent"));
const humanMembers = computed(() => members.value.filter((member) => member.role !== "agent"));
const isDirect = computed(() => room.value?.room_type === "direct");
const directPeer = computed(() => room.value?.peer ?? null);
const directAgent = computed(() => directPeer.value?.role === "agent" ? directPeer.value : null);
const connectionLabel = computed(() => ({
  online: "消息已同步",
  connecting: "正在连接",
  offline: "网络断开，正在重连",
}[connection.value]));

function own(message: MobileMessage) { return message.sender_id === auth.user?.account; }
function replyPreview(id: string | null) { return messages.value.find((item) => item.id === id); }
function replyText(id: string | null) {
  const message = replyPreview(id);
  return message ? `${message.sender_name}：${messageText(message)}` : "原消息";
}
function messageText(message: MobileMessage) {
  return message.sender_role === "agent" || message.message_type === "system_notice"
    ? markdownToChatText(message.content)
    : message.content;
}
function messageAuthor(message: MobileMessage) {
  return own(message) ? "我" : message.sender_name.split(" · ")[0];
}
function displayedMessageText(message: MobileMessage) {
  const content = messageText(message);
  return content.length > 700 && !expandedMessageIds.value.has(message.id)
    ? `${content.slice(0, 700).trimEnd()}…`
    : content;
}
function toggleMessage(messageId: string) {
  const next = new Set(expandedMessageIds.value);
  if (next.has(messageId)) next.delete(messageId); else next.add(messageId);
  expandedMessageIds.value = next;
}
function memberName(member: MobileMember) { return shortMemberName(member); }
function memberRole(member: MobileMember) {
  if (member.display_name.includes(" · ")) return member.display_name.split(" · ")[1];
  if (member.role === "teacher") return "课程教师";
  if (member.role === "student") return "课程成员";
  return "群成员";
}
function timelineLabel(value: number) {
  const date = new Date(value * 1000);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const time = date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  return sameDay ? time : `${date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })} ${time}`;
}
function showTimeline(index: number) {
  if (index === 0) return true;
  return messages.value[index].created_at - messages.value[index - 1].created_at > 300;
}

async function scrollBottom(behavior: ScrollBehavior = "auto") {
  await nextTick();
  listElement.value?.scrollTo({ top: listElement.value.scrollHeight, behavior });
}

async function loadInitial() {
  loading.value = true;
  error.value = "";
  try {
    const [roomResult, memberResult, messageResult] = await Promise.all([
      listRooms(), listMembers(roomId), listMessages(roomId),
    ]);
    room.value = roomResult.rooms.find((item) => item.id === roomId) ?? null;
    members.value = memberResult.members;
    messages.value = messageResult.items;
    hasMore.value = messageResult.has_more;
    cursor.value = messageResult.next_cursor ?? "";
    const last = messages.value.at(-1);
    if (last) await markRead(roomId, last.id);
  } catch {
    error.value = "暂时无法进入会话，请稍后重试。";
  } finally {
    loading.value = false;
    if (!error.value) await scrollBottom();
  }
}

async function loadOlder() {
  if (!hasMore.value || loadingOlder.value) return;
  loadingOlder.value = true;
  try {
    const oldHeight = listElement.value?.scrollHeight ?? 0;
    const result = await listMessages(roomId, cursor.value);
    messages.value = [...result.items, ...messages.value];
    hasMore.value = result.has_more;
    cursor.value = result.next_cursor ?? "";
    await nextTick();
    if (listElement.value) listElement.value.scrollTop = listElement.value.scrollHeight - oldHeight;
  } finally {
    loadingOlder.value = false;
  }
}

function addMessage(message: MobileMessage) {
  if (message.room_id !== roomId || messages.value.some((item) => item.id === message.id)) return;
  if (message.sender_role === "agent" || message.message_type === "system_notice") {
    typingAgent.value = null;
  }
  messages.value.push(message);
  void markRead(roomId, message.id);
  void scrollBottom("smooth");
}

async function catchUpMessages() {
  try {
    const result = await listMessages(roomId);
    result.items.forEach(addMessage);
  } catch {
    // The next reconnect attempt will retry without interrupting the composer.
  }
}

async function connectSocket() {
  if (disposed) return;
  connection.value = "connecting";
  const token = await loadToken();
  socket = new WebSocket(websocketUrl());
  socket.onopen = () => socket?.send(JSON.stringify({ type: "auth", token }));
  socket.onmessage = (event) => {
    try {
      const frame = JSON.parse(event.data);
      if (frame.type === "auth.ok") {
        connection.value = "online";
        reconnectAttempt = 0;
        void catchUpMessages();
      }
      if (frame.type === "agent.typing" && frame.room_id === roomId) {
        typingAgent.value = { id: String(frame.agent_id), name: String(frame.agent_name) };
        void scrollBottom("smooth");
      }
      if (frame.type === "message.created") addMessage(frame.message as MobileMessage);
    } catch {
      connection.value = "offline";
    }
  };
  socket.onclose = () => {
    connection.value = "offline";
    if (disposed) return;
    const delay = Math.min(30000, 1000 * 2 ** reconnectAttempt++);
    reconnectTimer = window.setTimeout(() => void connectSocket(), delay);
  };
  socket.onerror = () => socket?.close();
}

async function send() {
  const content = draft.value.trim();
  if (!content || sending.value) return;
  sending.value = true;
  sendError.value = "";
  const mentions = isDirect.value
    ? (directAgent.value ? [directAgent.value.user_id] : [])
    : buildAgentMentions(content, agentMembers.value);
  const requestedAgent = directAgent.value
    ?? agentMembers.value.find((member) => member.user_id === mentions[0]);
  typingAgent.value = requestedAgent
    ? { id: requestedAgent.user_id, name: requestedAgent.display_name }
    : null;
  try {
    const result = await sendMessage(roomId, {
      content,
      message_type: "text",
      client_message_id: createClientMessageId(),
      reply_to_id: replyTo.value?.id ?? null,
      mentions,
      payload: {},
    });
    addMessage(result.message);
    draft.value = "";
    replyTo.value = null;
    if (composerElement.value) composerElement.value.style.height = "44px";
  } catch (cause) {
    typingAgent.value = null;
    sendError.value = cause instanceof ApiError && cause.status === 403
      ? "你已不在这个会话中，消息未发送。"
      : "消息发送失败，内容已保留。请检查网络后重试。";
  } finally {
    sending.value = false;
  }
}

async function insertMention(member: MobileMember) {
  const mention = `@${memberName(member)}`;
  if (!draft.value.includes(mention)) draft.value = `${draft.value.trimEnd()}${draft.value ? " " : ""}${mention} `;
  mentionPanelOpen.value = false;
  memberPanelOpen.value = false;
  await nextTick();
  composerElement.value?.focus();
}

function resizeComposer(event: Event) {
  const target = event.target as HTMLTextAreaElement;
  target.style.height = "44px";
  target.style.height = `${Math.min(target.scrollHeight, 116)}px`;
}

onMounted(async () => {
  if (!auth.ready) await auth.restore();
  await loadInitial();
  await connectSocket();
});
onBeforeUnmount(() => {
  disposed = true;
  if (reconnectTimer) clearTimeout(reconnectTimer);
  socket?.close();
});
</script>

<template>
  <div class="chat-page">
    <header class="chat-header">
      <span class="chat-back-wrap">
        <button class="icon-button" type="button" aria-label="返回消息列表" @click="router.back()"><ChevronLeft :size="27" /></button>
        <i v-if="room?.unread_count" class="chat-unread-count">{{ room.unread_count > 99 ? '99+' : room.unread_count }}</i>
      </span>
      <button class="chat-title-button" type="button" @click="memberPanelOpen = true">
        <strong>{{ room?.name || '会话' }} <span v-if="!isDirect">({{ members.length }})</span></strong>
      </button>
      <button
        class="icon-button"
        type="button"
        aria-label="查看会话信息"
        :aria-expanded="memberPanelOpen"
        @click="memberPanelOpen = true"
      >
        <MoreHorizontal :size="23" />
      </button>
    </header>

    <PageState v-if="loading" kind="loading" />
    <PageState v-else-if="error" kind="error" :message="error" @retry="loadInitial" />
    <div v-else ref="listElement" class="message-list" aria-live="polite">
      <div v-if="connection !== 'online'" class="connection-banner" :class="connection">
        <WifiOff v-if="connection === 'offline'" :size="14" />
        <LoaderCircle v-else class="spin" :size="14" />
        {{ connectionLabel }}
      </div>

      <button v-if="hasMore" class="older-button" type="button" :disabled="loadingOlder" @click="loadOlder">
        <LoaderCircle v-if="loadingOlder" class="spin" :size="15" />
        <ArrowDown v-else :size="15" />
        查看更早消息
      </button>

      <template v-for="(message, index) in messages" :key="message.id">
        <time v-if="showTimeline(index)" class="timeline-label">{{ timelineLabel(message.created_at) }}</time>
        <article
          v-memo="[message.id, replyTo?.id, expandedMessageIds.has(message.id)]"
          class="message"
          :class="{ own: own(message), system: message.message_type === 'system_notice' }"
        >
          <template v-if="message.message_type === 'system_notice'">
            <p class="system-notice">{{ messageText(message) }}</p>
          </template>
          <template v-else>
            <span class="message-avatar" :class="message.sender_role">
              <img
                v-if="message.sender_role === 'agent'"
                :src="agentAvatarFor(message.sender_id, message.sender_name)"
                :alt="`${message.sender_name}头像`"
              >
              <span v-else>{{ message.sender_name.slice(0, 1) }}</span>
            </span>
            <div class="message-stack">
              <span class="message-author">{{ messageAuthor(message) }}</span>
              <div class="message-bubble">
                <button v-if="message.reply_to_id" class="reply-reference" type="button">
                  {{ replyText(message.reply_to_id) }}
                </button>
                <router-link
                  v-if="message.message_type === 'resource_card'"
                  class="resource-message"
                  :to="`/resources/${message.payload.resource_id}`"
                >
                  <strong>{{ message.payload.title }}</strong>
                  <span>学习资源 · 点击查看</span>
                </router-link>
                <p v-else>{{ displayedMessageText(message) }}</p>
                <button v-if="messageText(message).length > 700" class="message-expand" type="button" :aria-expanded="expandedMessageIds.has(message.id)" @click="toggleMessage(message.id)">
                  {{ expandedMessageIds.has(message.id) ? '收起' : '展开全文' }}
                </button>
              </div>
              <button class="message-reply" type="button" @click="replyTo = message">
                <CornerUpLeft :size="14" />回复
              </button>
            </div>
          </template>
        </article>
      </template>

      <article v-if="typingAgent" class="message agent-typing" aria-live="polite">
        <span class="message-avatar agent">
          <img :src="agentAvatarFor(typingAgent.id, typingAgent.name)" :alt="`${typingAgent.name}头像`">
        </span>
        <div class="message-stack">
          <span class="message-author">{{ typingAgent.name }}</span>
          <div class="message-bubble typing-bubble">
            <span class="typing-dots" aria-hidden="true"><i /><i /><i /></span>
            <span>正在思考</span>
          </div>
        </div>
      </article>
    </div>

    <footer class="composer-wrap">
      <div v-if="replyTo" class="reply-bar">
        <span><b>回复 {{ replyTo.sender_name }}</b>{{ messageText(replyTo) }}</span>
        <button type="button" aria-label="取消回复" @click="replyTo = null"><X :size="17" /></button>
      </div>
      <div v-if="sendError" class="send-error" role="alert">
        <CircleAlert :size="15" />
        <span>{{ sendError }}</span>
        <button type="button" :disabled="sending" @click="send"><RotateCcw :size="14" />重试</button>
      </div>
      <div v-if="mentionPanelOpen && !isDirect" class="agent-mention-panel">
        <button
          v-for="agent in agentMembers"
          :key="agent.user_id"
          type="button"
          :aria-label="`提及 ${memberName(agent)}`"
          @click="insertMention(agent)"
        >
          <span><img :src="agentAvatarFor(agent.user_id, agent.display_name)" :alt="`${memberName(agent)}头像`"></span>{{ memberName(agent) }}
        </button>
      </div>
      <div class="composer-main">
        <textarea
          ref="composerElement"
          v-model="draft"
          rows="1"
          maxlength="4000"
          aria-label="聊天消息"
          placeholder="发送消息"
          @input="resizeComposer"
          @keydown.enter.exact.prevent="send"
        />
        <button class="send-button" type="button" :disabled="!draft.trim() || sending" @click="send">
          <LoaderCircle v-if="sending" class="spin" :size="19" />
          <template v-else>发送</template>
        </button>
      </div>
      <div class="composer-actions" aria-label="消息工具">
        <button class="composer-tool" type="button" aria-label="分享学习资源" @click="router.push('/resources')"><FileUp :size="24" /></button>
        <button v-if="!isDirect" class="composer-tool" type="button" aria-label="提及群内 Agent" :aria-expanded="mentionPanelOpen" @click="mentionPanelOpen = !mentionPanelOpen"><AtSign :size="25" /></button>
        <button class="composer-tool" type="button" aria-label="查看会话信息" :aria-expanded="memberPanelOpen" @click="memberPanelOpen = true"><UsersRound :size="24" /></button>
      </div>
    </footer>

    <div v-if="memberPanelOpen" class="member-panel-backdrop" @click.self="memberPanelOpen = false">
      <section class="member-panel" role="dialog" aria-modal="true" aria-labelledby="member-panel-title">
        <header>
          <div>
            <p>{{ isDirect ? '私聊信息' : '课程群信息' }}</p>
            <h2 id="member-panel-title">{{ isDirect ? room?.name : '群成员' }}</h2>
          </div>
          <button class="icon-button compact" type="button" aria-label="关闭会话信息" @click="memberPanelOpen = false"><X :size="20" /></button>
        </header>
        <div class="member-summary">
          <span><UsersRound :size="18" /></span>
          <p v-if="isDirect"><strong>与 {{ directPeer?.display_name || room?.name }} 私聊</strong><small>只有会话双方可以查看消息</small></p>
          <p v-else><strong>{{ members.length }} 位成员</strong><small>{{ agentMembers.length }} 个 Agent 正在协作</small></p>
        </div>
        <template v-if="isDirect">
          <h3>私聊成员</h3>
          <ul class="human-member-list direct-member-list">
            <li v-for="member in members" :key="member.user_id">
              <span class="member-avatar" :class="member.role">
                <img v-if="member.role === 'agent'" :src="agentAvatarFor(member.user_id, member.display_name)" :alt="`${memberName(member)}头像`">
                <template v-else>{{ member.display_name.slice(0, 1) }}</template>
              </span>
              <p><strong>{{ member.user_id === auth.user?.account ? `${member.display_name}（我）` : memberName(member) }}</strong><small>{{ memberRole(member) }}</small></p>
            </li>
          </ul>
        </template>
        <template v-else>
          <h3>学习 Agent</h3>
          <div class="agent-member-grid">
            <button v-for="agent in agentMembers" :key="agent.user_id" type="button" @click="insertMention(agent)">
              <span class="member-avatar agent"><img :src="agentAvatarFor(agent.user_id, agent.display_name)" :alt="`${memberName(agent)}头像`"></span>
              <strong>{{ memberName(agent) }}</strong><small>{{ memberRole(agent) }}</small>
              <i><AtSign :size="12" />提问</i>
            </button>
          </div>
          <h3>教师与同学</h3>
          <ul class="human-member-list">
            <li v-for="member in humanMembers" :key="member.user_id">
              <span class="member-avatar" :class="member.role">{{ member.display_name.slice(0, 1) }}</span>
              <p><strong>{{ member.display_name }}</strong><small>{{ memberRole(member) }}</small></p>
            </li>
          </ul>
        </template>
      </section>
    </div>
  </div>
</template>
