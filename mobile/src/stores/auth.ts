import { defineStore } from "pinia";
import { ref } from "vue";

import * as api from "@/api";
import { clearToken, loadToken, saveToken } from "@/api/client";
import type { MobileUser } from "@/types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<MobileUser | null>(null);
  const ready = ref(false);

  async function restore() {
    const token = await loadToken();
    if (token) {
      try { user.value = await api.getMe(); } catch { await clearToken(); }
    }
    ready.value = true;
  }

  async function signIn(account: string, password: string) {
    const result = await api.login(account, password);
    await saveToken(result.access_token);
    user.value = result.user;
  }

  async function signOut() {
    try { await api.logout(); } catch { /* local logout remains authoritative */ }
    await clearToken();
    user.value = null;
  }

  return { user, ready, restore, signIn, signOut };
});
