﻿import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./styles/tokens.scss";
import "./styles/global.scss";
import "./styles/paper.scss";
import "./styles/typography.scss";
import "./styles/companion-design.css";
import "katex/dist/katex.min.css";

const app = createApp(App);

// 全局错误处理器：防止组件渲染异常导致整个应用白屏
// 快速切换路由时，如果某个异步组件加载或 setup 抛错，
// Vue 3 默认行为是卸载整棵组件树 → 白屏。
// 这里捕获后仅打印日志，保持已有 DOM 不被销毁。
app.config.errorHandler = (err, _instance, info) => {
  // eslint-disable-next-line no-console
  console.error("[Vue Error]", info, err);
};

// 捕获未处理的 Promise rejection（如快速点击导致的网络请求竞态）
window.addEventListener("unhandledrejection", (event) => {
  // 快速导航时可能产生竞态 rejection，阻止它冒泡到控制台红屏
  // eslint-disable-next-line no-console
  console.warn("[Unhandled Rejection]", event.reason);
  event.preventDefault();
});

app.use(router).mount("#app");
