"""Plan D · 启动前端 + 后端 dev server（Python subprocess 强 detached）

之前的版本在 detached flags 上少 CREATE_BREAKAWAY_FROM_JOB，子进程被
PowerShell session kill 一起带走。本版本强制独离。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"F:\比赛\中软杯\A3")
FRONTEND = ROOT / "frontend"
LOG_DIR = ROOT / "data" / ".tmp" / "dev_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
PY = r"E:\Anaconda\python.exe"

# Windows flags — 关键: 用 CREATE_BREAKAWAY_FROM_JOB 让子进程脱离 PowerShell job
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _start(cmd: list[str], cwd: Path, name: str, env_overrides: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    # 去掉 JAVA / Path 中可能在子进程里干扰的项
    env.pop("PYTHONIOENCODING", None)
    env["PYTHONUTF8"] = "1"

    logfile = LOG_DIR / f"{name}.log"
    fout = open(logfile, "ab", buffering=0)
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=fout,
        stderr=subprocess.STDOUT,
        creationflags=flags,
        close_fds=True,
    )


def start_servers() -> tuple[subprocess.Popen | None, subprocess.Popen | None]:
    backend_p = None
    frontend_p = None

    # 后端
    if port_open(8000):
        print("[backend] 8000 already in use")
    else:
        backend_p = _start(
            [PY, "-m", "uvicorn", "backend.app.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
            name="backend",
            env_overrides={"A3_OFFLINE_DEMO": "1"},
        )
        print(f"[backend] started pid={backend_p.pid}")

    # 前端
    if port_open(5173):
        print("[frontend] 5173 already in use")
    else:
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_p = _start(
            [npm, "run", "dev"],
            cwd=FRONTEND,
            name="frontend",
        )
        print(f"[frontend] started pid={frontend_p.pid}")

    return backend_p, frontend_p


def stop_servers() -> int:
    try:
        import psutil
    except ImportError:
        print("[stop] psutil not installed; skipping clean stop")
        return 0
    killed = 0
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cl = proc.info.get("cmdline") or []
            cmd_str = " ".join(cl)
            if not cmd_str:
                continue
            if any(s in cmd_str for s in (
                "uvicorn backend.app.main",
                "vite",
                "npm run dev",
                "node_modules/.bin/vite",
                "node_modules\\.bin\\vite",
            )):
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    print(f"[stop] killed={killed}")
    return killed


def status() -> None:
    print(f"backend  http://127.0.0.1:8000  ->  {'open' if port_open(8000) else 'down'}")
    print(f"frontend http://127.0.0.1:5173  ->  {'open' if port_open(5173) else 'down'}")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "start"

    if action == "start":
        b, f = start_servers()
        print("等待 10s 让服务起来...")
        time.sleep(10)
        status()
        if f and f.poll() is not None:
            print(f"[warn] frontend 进程已退出, rc={f.returncode}")
            log = LOG_DIR / "frontend.log"
            if log.exists():
                tail = log.read_text(encoding="utf-8", errors="ignore")[-1500:]
                print("---- frontend.log tail ----")
                print(tail)
    elif action == "stop":
        stop_servers()
    elif action == "status":
        status()
    else:
        print(__doc__)
