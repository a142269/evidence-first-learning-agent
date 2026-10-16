@echo off
chcp 65001 >nul
title 智学领航 — A3 学习多智能体系统

echo ================================================================
echo   智学领航 · A3 学习多智能体系统
echo   第十五届中国软件杯 A3 赛题
echo ================================================================
echo.

REM ----- 检查 Python -----
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python 未安装或不在 PATH 中
    echo 请安装 Python 3.12+ 并添加到系统 PATH
    pause
    exit /b 1
)

echo [1/6] 检查 Python 环境...
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"
if %errorlevel% neq 0 (
    echo [ERROR] Python 版本过低, 需要 3.10+ (推荐 3.12)
    pause
    exit /b 1
)

REM ----- 安装依赖 -----
echo [2/6] 安装后端依赖...
pip install -r requirements.txt --break-system-packages --quiet
if %errorlevel% neq 0 (
    echo [WARN] pip 安装部分依赖失败，尝试继续...
)

REM ----- 检查 .env -----
if not exist ".env" (
    echo [3/6] 复制 .env.example -^> .env （演示模式可不填 LLM API Key）...
    copy .env.example .env >nul
) else (
    echo [3/6] .env 已存在
)

REM ----- 初始化数据库 + 种子数据 -----
echo [4/6] 初始化数据库和种子数据...
python scripts/seed_demo.py
if %errorlevel% neq 0 (
    echo [WARN] 数据库初始化失败，将使用内存模式
)

REM ----- 演示资产健康检查 -----
echo [5/6] 演示资产健康检查 (14/14 项)...
python -m scripts.verify_demo_assets
if %errorlevel% neq 0 (
    echo [ERROR] 演示资产健康检查未通过，请先修复
    pause
    exit /b 1
)

REM ----- 启动后端 -----
echo [6/6] 启动后端服务...
echo.
echo ================================================================
echo   启动完成！访问下面的地址:
echo.
echo   前端:    http://localhost:5173      (cd frontend ^&^& npm run dev)
echo   后端:    http://localhost:8000
echo   API 文档: http://localhost:8000/docs
echo   Cockpit: http://localhost:8000/api/v1/cockpit/student/demo-student-1
echo.
echo   默认账号: counselor / 123456     (辅导员)
echo            admin / 123456          (管理员)
echo            可在 .env 通过 AUTH_*_ACCOUNT/PASSWORD 覆盖
echo.
echo   离线模式: 已默认开启 (A3_OFFLINE_DEMO=1)
echo            无 LLM API Key 也能跑完整 demo
echo.
echo   评委复现命令:
echo     python -m scripts.verify_demo_assets         (14/14 健康检查)
echo     python -m scripts.docker_smoke               (Docker 部署后跑)
echo     python -m scripts.load_test                  (压测 p95)
echo     python -m scripts.prompt_cache_warmup        (演示日前预热)
echo.
echo   按 Ctrl+C 停止服务
echo ================================================================

REM 启动后端 (offline demo 模式)
cd /d "%~dp0"
set A3_OFFLINE_DEMO=1
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

pause
