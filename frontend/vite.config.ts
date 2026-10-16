import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        // echarts（~1MB）只被知识图谱/预测曲线等图表页使用，独立分包按需加载
        manualChunks: {
          echarts: ["echarts"],
          vendor: ["vue", "vue-router"],
          markdown: ["marked"],
        },
      },
    },
    // echarts 单包体积由 manualChunks 明确隔离，放宽默认 500KB 告警阈值
    chunkSizeWarningLimit: 1200,
  },
});
