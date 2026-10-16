<script setup lang="ts">
import { ArrowRight, BookOpenCheck, Eye, EyeOff, LockKeyhole, UserRound } from "lucide-vue-next";
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const account = ref("demo-student-1");
const password = ref("123456");
const showPassword = ref(false);
const loading = ref(false);
const error = ref("");
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function submit() {
  if (!account.value.trim() || !password.value) return;
  loading.value = true;
  error.value = "";
  try {
    await auth.signIn(account.value.trim(), password.value);
    await router.replace(typeof route.query.redirect === "string" ? route.query.redirect : "/messages");
  } catch (reason) {
    const detail = reason instanceof ApiError ? reason.detail : "network_error";
    error.value = detail === "password_invalid" ? "密码不正确" : detail === "account_not_found" ? "学生账号不存在" : "暂时无法登录，请检查网络";
  } finally { loading.value = false; }
}
</script>

<template>
  <main class="login-page">
    <section class="login-hero" aria-labelledby="login-title">
      <div class="brand-mark"><BookOpenCheck :size="28" /></div>
      <p class="eyebrow">TRIPLE-U STUDENT</p>
      <h1 id="login-title">把学习讨论，<br /><span>装进口袋里。</span></h1>
      <p class="login-copy">课程协作、错题复习和学习资源，在同一个学生空间里自然衔接。</p>
    </section>
    <form class="login-card" @submit.prevent="submit">
      <div class="field">
        <label for="account">学生账号</label>
        <div class="field-control"><UserRound :size="19" /><input id="account" v-model="account" autocomplete="username" /></div>
      </div>
      <div class="field">
        <label for="password">密码</label>
        <div class="field-control"><LockKeyhole :size="19" /><input id="password" v-model="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" /><button type="button" class="icon-button compact" aria-label="切换密码可见性" @click="showPassword = !showPassword"><EyeOff v-if="showPassword" :size="18" /><Eye v-else :size="18" /></button></div>
      </div>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
      <button class="primary-button login-submit" type="submit" :disabled="loading">
        <span>{{ loading ? "正在进入" : "进入学生端" }}</span><ArrowRight :size="19" />
      </button>
      <p class="demo-hint">演示账号已预填，可直接体验。</p>
    </form>
  </main>
</template>
