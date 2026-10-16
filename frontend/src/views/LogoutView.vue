<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import { logoutCurrentUser } from "@/api/auth";
import { clearAuthSession } from "@/utils/auth";

const router = useRouter();

onMounted(async () => {
  try {
    await logoutCurrentUser();
  } catch {
    // Ignore logout errors and clear local state anyway.
  } finally {
    clearAuthSession();
    router.replace("/login");
  }
});
</script>

<template>
  <div class="logout-screen">
    <div class="logout-card">
      <strong>正在退出登录</strong>
      <span>系统正在清理当前会话并返回登录页。</span>
    </div>
  </div>
</template>

<style scoped>
.logout-screen {
  display: flex;
  min-height: 100vh;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #f8fbff 0%, #eef5ff 100%);
}

.logout-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 28px 32px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(203, 213, 225, 0.8);
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.08);
  color: #0f172a;
}

.logout-card span {
  color: #64748b;
}
</style>
