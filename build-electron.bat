@echo off
chcp 65001 >nul
title 智学领航 · 桌面版构建

echo ================================================================
echo   智学领航 · A3 桌面版一键构建
echo ================================================================
echo.

REM ----- 配置 -----
set PYTHON_EXE=D:\Anaconda3\envs\dxtorch\python.exe
set PROJECT_ROOT=%~dp0
cd /d "%PROJECT_ROOT%"

REM ----- Step 1: 构建前端 (同源模式，API 走相对路径) -----
echo [1/4] 构建前端 (Vue 3 + Vite)...
cd frontend
set VITE_API_BASE_URL=
call npm run build
if %errorlevel% neq 0 (
    echo [ERROR] 前端构建失败
    pause
    exit /b 1
)
cd /d "%PROJECT_ROOT%"
echo       前端构建完成: frontend\dist\
echo.

REM ----- Step 2: PyInstaller 打包后端 -----
echo [2/4] 打包后端 (PyInstaller)...
"%PYTHON_EXE%" -m PyInstaller backend.spec --noconfirm
if %errorlevel% neq 0 (
    echo [ERROR] 后端打包失败
    pause
    exit /b 1
)
echo       后端打包完成: dist\a3-backend\
echo.

REM ----- Step 3: 编译 Electron TypeScript -----
echo [3/4] 编译 Electron 主进程...
cd electron
call npx tsc
if %errorlevel% neq 0 (
    echo [ERROR] Electron 编译失败
    pause
    exit /b 1
)
cd /d "%PROJECT_ROOT%"
echo       Electron 编译完成: dist-electron\
echo.

REM ----- Step 4: electron-builder 打包 -----
echo [4/4] 打包安装器 (electron-builder)...
call npx electron-builder --win
if %errorlevel% neq 0 (
    echo [ERROR] electron-builder 打包失败
    pause
    exit /b 1
)
echo.

echo ================================================================
echo   构建完成！
echo.
echo   安装包位置: dist_electron\智学领航-Setup-1.0.0.exe
echo.
echo   双击安装即可使用，无需 Python / Node.js 环境。
echo ================================================================
pause
