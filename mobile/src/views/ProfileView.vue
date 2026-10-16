<script setup lang="ts">
import { BookOpen, ChevronRight, LogOut, MessageCircle, Settings2, Trash2, UserRound } from "lucide-vue-next";
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const appVersion = import.meta.env.VITE_APP_VERSION || "0.1.0";
onMounted(() => { if (!auth.ready) void auth.restore(); });
async function signOut() { await auth.signOut(); await router.replace("/login"); }
async function clearCache() {
  const keys = Object.keys(localStorage).filter((key) => key.startsWith("triple_u_mobile_cache"));
  keys.forEach((key) => localStorage.removeItem(key));
  window.alert("本地缓存已清理");
}
</script>

<template>
  <div class="page profile-page">
    <header class="page-header"><p class="eyebrow">个人空间</p><h1>我的</h1></header>
    <section class="profile-card">
      <span class="profile-avatar"><UserRound :size="34" /></span>
      <div><strong>{{ auth.user?.display_name || '学生' }}</strong><p>{{ auth.user?.account || '正在读取账号' }}</p><span class="role-chip">学生账号</span></div>
    </section>
    <section class="quick-grid">
      <router-link to="/messages"><MessageCircle :size="21" /><span>课程群</span></router-link>
      <router-link to="/mistakes"><BookOpen :size="21" /><span>错题复习</span></router-link>
    </section>
    <section class="settings-list">
      <button type="button" @click="clearCache"><span class="settings-icon"><Trash2 :size="19" /></span><span><strong>清理缓存</strong><small>清除本机临时数据</small></span><ChevronRight :size="18" /></button>
      <div class="settings-row"><span class="settings-icon"><Settings2 :size="19" /></span><span><strong>当前版本</strong><small>H5 · Capacitor Ready</small></span><b>{{ appVersion }}</b></div>
    </section>
    <button class="logout-button" type="button" @click="signOut"><LogOut :size="19" />退出登录</button>
  </div>
</template>
