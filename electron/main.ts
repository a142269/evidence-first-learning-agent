/**
 * Electron 主进程入口
 *
 * 职责：
 *   1. 启动后端子进程（开发模式用 uvicorn，生产模式用打包的 a3-backend.exe）
 *   2. 轮询健康检查端点，等待后端就绪
 *   3. 创建 BrowserWindow 加载 http://127.0.0.1:8000
 *   4. 应用退出时优雅终止后端进程
 */
import { app, BrowserWindow, shell } from "electron";
import * as path from "path";
import * as fs from "fs";
import { spawn, ChildProcess } from "child_process";
import * as http from "http";

// ── 常量 ──────────────────────────────────────────────
const BACKEND_PORT = 18000;
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`;
const HEALTH_CHECK_INTERVAL = 500;  // ms
const HEALTH_CHECK_TIMEOUT = 30_000; // 最多等 30 秒

// ── 运行环境检测 ──────────────────────────────────────
const isDev = !app.isPackaged;

// ── 后端子进程 ────────────────────────────────────────
let backendProcess: ChildProcess | null = null;

/**
 * 获取用户数据目录（%APPDATA%/a3-learning）
 * 桌面版的数据库、向量库等可写数据存放在这里。
 */
function getUserDataDir(): string {
  return path.join(app.getPath("userData"), "data");
}

function logDesktop(message: string, error?: unknown) {
  try {
    const logDir = path.join(app.getPath("userData"), "logs");
    fs.mkdirSync(logDir, { recursive: true });
    const detail = error instanceof Error ? `${error.name}: ${error.message}\n${error.stack ?? ""}` : String(error ?? "");
    fs.appendFileSync(
      path.join(logDir, "desktop.log"),
      `[${new Date().toISOString()}] ${message}${detail ? ` ${detail}` : ""}\n`,
      "utf8",
    );
  } catch {
    // Logging must never block app startup.
  }
}

/**
 * 启动后端子进程
 */
function startBackend(): ChildProcess {
  const userDataDir = getUserDataDir();
  fs.mkdirSync(userDataDir, { recursive: true });

  // 环境变量：让后端把数据写到用户目录
  const env: Record<string, string> = {
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
    return spawn(pythonExe, [
      "-m", "uvicorn", "backend.app.main:app",
      "--host", "127.0.0.1", "--port", String(BACKEND_PORT),
    ], {
      cwd: app.getAppPath(),  // 项目根目录
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
  return spawn(backendExe, [
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
function waitForBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    const check = () => {
      const req = http.get(`${BACKEND_URL}/healthz`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
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
let mainWindow: BrowserWindow | null = null;

function createWindow() {
  const iconPath = path.join(app.getAppPath(), "electron", "assets", "icon.ico");

  mainWindow = new BrowserWindow({
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
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.webContents.on("did-finish-load", () => {
    logDesktop(`[renderer] did-finish-load ${mainWindow?.webContents.getURL() ?? ""}`);
  });
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    logDesktop(`[renderer] did-fail-load ${errorCode} ${errorDescription} ${validatedURL}`);
  });
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    logDesktop(`[renderer] render-process-gone ${details.reason} ${details.exitCode ?? ""}`);
  });
  mainWindow.webContents.on("console-message", (_event, level, message, line, sourceId) => {
    logDesktop(`[renderer:${level}] ${message} (${sourceId}:${line})`);
  });

  const currentWindow = mainWindow;
  void (async () => {
    try {
      await currentWindow.webContents.session.clearCache();
      logDesktop("[renderer] cleared session cache before load");
    } catch (err) {
      logDesktop("[renderer] failed to clear session cache", err);
    }

    try {
      await currentWindow.loadURL(BACKEND_URL);
    } catch (err) {
      logDesktop("[renderer] loadURL failed", err);
    }
  })();

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── 生命周期 ──────────────────────────────────────────
app.whenReady().then(async () => {
  console.log("[electron] 正在启动后端服务...");

  backendProcess = startBackend();

  // 转发后端 stdout/stderr 到控制台
  backendProcess.stdout?.on("data", (data: Buffer) => {
    const text = data.toString().trim();
    console.log(`[backend] ${text}`);
    logDesktop("[backend:stdout]", text);
  });
  backendProcess.stderr?.on("data", (data: Buffer) => {
    const text = data.toString().trim();
    console.error(`[backend] ${text}`);
    logDesktop("[backend:stderr]", text);
  });
  backendProcess.on("error", (err) => {
    console.error("[backend] 进程启动失败:", err);
    logDesktop("[backend] process start error", err);
  });
  backendProcess.on("exit", (code, signal) => {
    logDesktop(`[backend] process exit code=${code ?? ""} signal=${signal ?? ""}`);
  });

  try {
    console.log("[electron] 等待后端就绪...");
    await waitForBackend();
    console.log("[electron] 后端已就绪，创建窗口");
    createWindow();
  } catch (err) {
    console.error("[electron] 后端启动失败:", err);
    logDesktop("[electron] backend startup failed", err);
    // 仍然创建窗口，让用户看到错误信息
    createWindow();
  }
});

app.on("window-all-closed", () => {
  killBackend();
  app.quit();
});

app.on("before-quit", () => {
  killBackend();
});

/**
 * 优雅终止后端进程
 */
function killBackend() {
  if (!backendProcess) return;
  console.log("[electron] 正在停止后端服务...");

  // Windows 下 taskkill 整个进程树
  if (process.platform === "win32") {
    try {
      spawn("taskkill", ["/pid", String(backendProcess.pid), "/f", "/t"]);
    } catch {
      // 忽略
    }
  } else {
    backendProcess.kill("SIGTERM");
  }

  backendProcess = null;
}
