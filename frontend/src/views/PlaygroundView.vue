<script setup lang="ts">
const appUrl = "/integrated-map/index.html?page=lab&shell=0";
</script>

<template>
  <main class="playground-page">
    <header class="playground-toolbar">
      <RouterLink class="playground-exit" to="/home" aria-label="退出桃园学宫">
        <span>←</span>
        退出桃园学宫
      </RouterLink>
      <strong>桃园学宫</strong>
    </header>
    <iframe
      class="playground-frame"
      :src="appUrl"
      title="桃园学宫 · 像素校园"
      allow="fullscreen"
    />
  </main>
</template>

<style scoped>
.playground-page {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  background: linear-gradient(180deg, #fffaf3 0%, #fafaf9 100%);
}

.playground-toolbar {
  flex: 0 0 56px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 0 22px;
  border-bottom: 1px solid rgba(234, 90, 26, 0.14);
  background: rgba(255, 250, 243, 0.94);
  box-shadow: 0 8px 22px rgba(78, 55, 34, 0.06);
  backdrop-filter: blur(10px);
}

.playground-toolbar strong {
  color: #8f3f17;
  font-size: 14px;
  font-weight: 800;
}

.playground-exit {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid rgba(234, 90, 26, 0.26);
  border-radius: 999px;
  background: #fff;
  color: #c2410c;
  box-shadow: 0 8px 18px rgba(234, 90, 26, 0.1);
  font-size: 14px;
  font-weight: 800;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.playground-exit:hover {
  border-color: #ea5a1a;
  background: #fff7ed;
  color: #9a3412;
}

.playground-exit span {
  font-size: 18px;
  line-height: 1;
}

.playground-frame {
  display: block;
  width: 100%;
  flex: 1 1 auto;
  min-height: 0;
  border: 0;
  background: #fafaf9;
}
</style>
