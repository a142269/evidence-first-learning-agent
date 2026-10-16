<script setup lang="ts">
const appUrl = "/integrated-map/index.html";
</script>

<template>
  <main class="integrated-map-page">
    <iframe
      class="integrated-map-frame"
      :src="appUrl"
      title="AI Learning Companion"
      allow="fullscreen"
    />
  </main>
</template>

<style scoped>
.integrated-map-page {
  width: 100vw;
  height: 100vh;
  margin: 0;
  overflow: hidden;
  background: #fafaf9;
}

.integrated-map-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: #fafaf9;
}
</style>
