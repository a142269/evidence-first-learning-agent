"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
/**
 * Electron 主进程入口
 *
 * 职责：
 *   1. 启动后端子进程（开发模式用 uvicorn，生产模式用打包的 a3-backend.exe）
 *   2. 轮询健康检查端点，等待后端就绪
 *   3. 创建 BrowserWindow 加载 http://127.0.0.1:8000
 *   4. 应用退出时优雅终止后端进程
 */
const electron_1 = require("electron");
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const child_process_1 = require("child_process");
const http = __importStar(require("http"));
// ── 常量 ──────────────────────────────────────────────
const BACKEND_PORT = 18000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const HEALTH_CHECK_INTERVAL = 500; // ms
const HEALTH_CHECK_TIMEOUT = 30_000; // 最多等 30 秒
// ── 运行环境检测 ──────────────────────────────────────
const isDev = !electron_1.app.isPackaged;
// ── 后端子进程 ────────────────────────────────────────
let backendProcess = null;
/**
 * 获取用户数据目录（%APPDATA%/a3-learning）
 * 桌面版的数据库、向量库等可写数据存放在这里。
 */
function getUserDataDir() {
    return path.join(electron_1.app.getPath("userData"), "data");
}
function logDesktop(message, error) {
    try {
        const logDir = path.join(electron_1.app.getPath("userData"), "logs");
        fs.mkdirSync(logDir, { recursive: true });
        const detail = error instanceof Error ? `${error.name}: ${error.message}\n${error.stack ?? ""}` : String(error ?? "");
        fs.appendFileSync(path.join(logDir, "desktop.log"), `[${new Date().toISOString()}] ${message}${detail ? ` ${detail}` : ""}\n`, "utf8");
    }
    catch {
        // Logging must never block app startup.
    }
}
/**
 * 启动后端子进程
 */
function startBackend() {
    const userDataDir = getUserDataDir();
    fs.mkdirSync(userDataDir, { recursive: true });
    // 环境变量：让后端把数据写到用户目录
    const env = {
        ...process.env,
        DATABASE_URL: `sqlite:///${path.join(userDataDir, "a3_learning.db").replace(/\\/g, "/")}`,
        VECTOR_DB_PATH: path.join(userDataDir, "vector_store"),
        A3_DATA_DIR: userDataDir,
        A3_OFFLINE_DEMO: "1",
        PORT: String(BACKEND_PORT),
    };
    if (isDev) {
        // 开发模式：直接用 Python 启动 uvicorn
        const preferredPython = "D:\\Anaconda3\\envs\\dxtorch\\python.exe";
        const pythonExe = process.env.A3_PYTHON_EXE || (fs.existsSync(preferredPython) ? preferredPython : "python");
        console.log(`[dev] 启动后端: ${pythonExe} -m uvicorn backend.app.main:app --port ${BACKEND_PORT}`);
        return (0, child_process_1.spawn)(pythonExe, [
            "-m", "uvicorn", "backend.app.main:app",
            "--host", "127.0.0.1", "--port", String(BACKEND_PORT),
        ], {
            cwd: electron_1.app.getAppPath(), // 项目根目录
            env,
            shell: false,
        });
    }
    // 生产模式：启动 PyInstaller 打包的 a3-backend.exe
    const backendExe = path.join(process.resourcesPath, "a3-backend", "a3-backend.exe");
    if (!fs.existsSync(backendExe)) {
        throw new Error(`Backend executable not found: ${backendExe}`);
    }
    console.log(`[prod] 启动后端: ${backendExe}`);
    logDesktop(`[prod] starting backend: ${backendExe}`);
    return (0, child_process_1.spawn)(backendExe, [
        "--host", "127.0.0.1", "--port", String(BACKEND_PORT),
    ], {
        cwd: path.dirname(backendExe),
        env,
        shell: false,
    });
}
/**
 * 轮询健康检查端点
 */
function waitForBackend() {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        const check = () => {
            const req = http.get(`${BACKEND_URL}/healthz`, (res) => {
                if (res.statusCode === 200) {
                    resolve();
                }
                else {
                    retry();
                }
                res.resume(); // 释放内存
            });
            req.on("error", () => retry());
            req.setTimeout(2000, () => {
                req.destroy();
                retry();
            });
        };
        const retry = () => {
            if (Date.now() - startTime > HEALTH_CHECK_TIMEOUT) {
                reject(new Error("后端启动超时（30 秒）"));
                return;
            }
            setTimeout(check, HEALTH_CHECK_INTERVAL);
        };
        check();
    });
}
// ── 窗口管理 ──────────────────────────────────────────
let mainWindow = null;
function createWindow() {
    const iconPath = path.join(electron_1.app.getAppPath(), "electron", "assets", "icon.ico");
    mainWindow = new electron_1.BrowserWindow({
        width: 1280,
        height: 800,
        minWidth: 960,
        minHeight: 640,
        title: "智学领航 · A3 学习多智能体系统",
        icon: iconPath,
        webPreferences: {
            preload: path.join(__dirname, "preload.js"),
            contextIsolation: true,
            nodeIntegration: false,
        },
    });
    // 外部链接用系统浏览器打开
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith("http")) {
            electron_1.shell.openExternal(url);
            return { action: "deny" };
        }
        return { action: "allow" };
    });
    mainWindow.loadURL(BACKEND_URL);
    if (isDev) {
        mainWindow.webContents.openDevTools({ mode: "detach" });
    }
    mainWindow.on("closed", () => {
        mainWindow = null;
    });
}
// ── 生命周期 ──────────────────────────────────────────
electron_1.app.whenReady().then(async () => {
    console.log("[electron] 正在启动后端服务...");
    backendProcess = startBackend();
    // 转发后端 stdout/stderr 到控制台
    backendProcess.stdout?.on("data", (data) => {
        console.log(`[backend] ${data.toString().trim()}`);
    });
    backendProcess.stderr?.on("data", (data) => {
        console.error(`[backend] ${data.toString().trim()}`);
    });
    backendProcess.on("error", (err) => {
        console.error("[backend] 进程启动失败:", err);
        logDesktop("[backend] process start error", err);
    });
    try {
        console.log("[electron] 等待后端就绪...");
        await waitForBackend();
        console.log("[electron] 后端已就绪，创建窗口");
        createWindow();
    }
    catch (err) {
        console.error("[electron] 后端启动失败:", err);
        logDesktop("[electron] backend startup failed", err);
        // 仍然创建窗口，让用户看到错误信息
        createWindow();
    }
});
electron_1.app.on("window-all-closed", () => {
    killBackend();
    electron_1.app.quit();
});
electron_1.app.on("before-quit", () => {
    killBackend();
});
/**
 * 优雅终止后端进程
 */
function killBackend() {
    if (!backendProcess)
        return;
    console.log("[electron] 正在停止后端服务...");
    // Windows 下 taskkill 整个进程树
    if (process.platform === "win32") {
        try {
            (0, child_process_1.spawn)("taskkill", ["/pid", String(backendProcess.pid), "/f", "/t"]);
        }
        catch {
            // 忽略
        }
    }
    else {
        backendProcess.kill("SIGTERM");
    }
    backendProcess = null;
}
