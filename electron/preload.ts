/**
 * Electron 预加载脚本
 *
 * 在渲染进程（前端 Vue）中安全地暴露桌面 API，
 * 通过 contextBridge 隔离，不影响网页端的正常运行。
 */
import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("desktopAPI", {
  /** 当前是否运行在桌面版中 */
  isDesktop: true,

  /** 应用版本号 */
  version: process.env.npm_package_version || "1.0.0",
});
