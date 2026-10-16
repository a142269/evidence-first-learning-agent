import { createRouter, createWebHistory } from "vue-router";

import { loadToken } from "@/api/client";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
    { path: "/", component: () => import("@/components/MobileShell.vue"), children: [
      { path: "", redirect: "/messages" },
      { path: "messages", name: "messages", component: () => import("@/views/RoomsView.vue") },
      { path: "mistakes", name: "mistakes", component: () => import("@/views/MistakesView.vue") },
      { path: "resources", name: "resources", component: () => import("@/views/ResourcesView.vue") },
      { path: "me", name: "me", component: () => import("@/views/ProfileView.vue") },
    ] },
    { path: "/chat/:roomId", name: "chat", component: () => import("@/views/ChatRoomView.vue") },
    { path: "/mistakes/:id", name: "mistake-detail", component: () => import("@/views/MistakeDetailView.vue") },
    { path: "/resources/:id", name: "resource-detail", component: () => import("@/views/ResourceDetailView.vue") },
    { path: "/:pathMatch(.*)*", redirect: "/messages" },
  ],
});

router.beforeEach(async (to) => {
  const token = await loadToken();
  if (!to.meta.public && !token) return { name: "login", query: { redirect: to.fullPath } };
  if (to.name === "login" && token) return { name: "messages" };
  return true;
});

window.addEventListener("mobile-auth-expired", () => router.replace({ name: "login" }));
export default router;
