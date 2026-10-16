#!/usr/bin/env bash
# A3 智学领航 一键启动（Linux / macOS）
# 演示模式默认开启 (A3_OFFLINE_DEMO=1)，无 LLM API Key 也能跑

set -euo pipefail

# ----- 工具 -----
red()    { printf "\033[0;31m%s\033[0m\n" "$*"; }
green()  { printf "\033[0;32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[0;33m%s\033[0m\n" "$*"; }
cyan()   { printf "\033[0;36m%s\033[0m\n" "$*"; }

cyan "================================================================"
cyan "  智学领航 · A3 学习多智能体系统"
cyan "  第十五届中国软件杯 A3 赛题"
cyan "================================================================"
echo

# ----- 检查 Python -----
if ! command -v python3 >/dev/null 2>&1; then
  red "[ERROR] python3 未安装或不在 PATH 中"
  red "  请安装 Python 3.10+ (推荐 3.12)"
  exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[1/6] Python 版本: $PY_VERSION"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || {
  red "[ERROR] Python 版本过低，需要 3.10+ (推荐 3.12)"
  exit 1
}

# ----- 安装依赖 -----
echo "[2/6] 安装后端依赖..."
pip3 install -r requirements.txt --break-system-packages --quiet || \
  yellow "[WARN] pip 安装部分依赖失败，尝试继续..."

# ----- 检查 .env -----
if [[ ! -f .env ]]; then
  echo "[3/6] 复制 .env.example -> .env"
  cp .env.example .env
else
  echo "[3/6] .env 已存在"
fi

# ----- 初始化数据库 + 种子 -----
echo "[4/6] 初始化数据库和种子数据..."
python3 scripts/seed_demo.py || yellow "[WARN] seed_demo 失败，使用内存模式"

# ----- 健康检查 -----
echo "[5/6] 演示资产健康检查 (14/14 项)..."
if ! python3 -m scripts.verify_demo_assets; then
  red "[ERROR] 演示资产健康检查未通过"
  exit 1
fi

# ----- 启动 -----
echo "[6/6] 启动后端服务..."
echo
cyan "================================================================"
green "  启动完成！访问:"
echo
echo "  前端:    http://localhost:5173      (cd frontend && npm run dev)"
echo "  后端:    http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo "  Cockpit: http://localhost:8000/api/v1/cockpit/student/demo-student-1"
echo
echo "  默认账号: counselor / 123456     (辅导员)"
echo "           admin / 123456          (管理员)"
echo
echo "  离线模式: 已开启 A3_OFFLINE_DEMO=1"
echo
echo "  评委复现命令:"
echo "    python -m scripts.verify_demo_assets         (14/14)"
echo "    python -m scripts.docker_smoke               (Docker 部署后)"
echo "    python -m scripts.load_test                  (压测 p95)"
echo "    python -m scripts.prompt_cache_warmup        (演示日前预热)"
echo
echo "  Ctrl+C 停止服务"
cyan "================================================================"

A3_OFFLINE_DEMO=1 exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
