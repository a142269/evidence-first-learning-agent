# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置 — A3 学习后端

用法:
  pyinstaller backend.spec --noconfirm

输出:
  dist/a3-backend/a3-backend.exe   (onedir 模式，启动快)

注意:
  - onedir 模式比 onefile 启动快 3-5 秒
  - jieba 词典和 sklearn 模型通过 --collect-data 自动包含
  - knowledge_base/ 和种子数据手动打包
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── 隐式导入（PyInstaller 无法自动检测的动态导入）──────────
hiddenimports = []
hiddenimports += collect_submodules("jieba")
hiddenimports += collect_submodules("aiohttp")
hiddenimports += collect_submodules("edge_tts")
hiddenimports += collect_submodules("imageio_ffmpeg")
hiddenimports += [
    "sklearn.cluster",
    "sklearn.feature_extraction",
    "sklearn.feature_extraction.text",
    "sklearn.impute",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
    "sklearn.mixture",
    "sklearn.preprocessing",
    "scipy.optimize",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "sse_starlette",
    "sse_starlette.sse",
    "PIL._tkinter_finder",
]

# ── 数据文件（jieba 词典、sklearn 模型等）────────────────
datas = []
datas += collect_data_files("jieba")
datas += collect_data_files("sklearn")
datas += collect_data_files("certifi")
datas += collect_data_files("imageio_ffmpeg")

# ── 项目数据文件 ────────────────────────────────────────
# 知识库（只读资源）
datas += [
    ("knowledge_base", "knowledge_base"),
    ("configs", "configs"),
]

# 种子数据（首次启动初始化用）
seed_files = [
    "data/seed.json",
    "data/seed_extended.json",
    "data/seed_mistakes.json",
    "data/question_bank.json",
    "data/quiz_bank.json",
    "data/question_bank_analytics_0708.json",
    "data/question_bank_extra_0703.json",
    "data/question_bank_extra_0704.json",
    "data/question_bank_fill.json",
    "data/question_bank_programming.json",
    "data/question_bank_programming_extra_0704.json",
    "data/learning_path_examples.json",
    "data/simulated_learning_data.json",
    "data/variant_demo_samples.json",
    "data/cov_demo_cases.json",
    "data/class_comparison_data.json",
]
for f in seed_files:
    if os.path.exists(f):
        datas.append((f, "data"))

# 演示用 artifacts（mp3/pptx/mermaid 等）
artifact_dirs = ["data/artifacts/mp3", "data/artifacts/pptx", "data/artifacts/mermaid_png"]
for d in artifact_dirs:
    if os.path.exists(d):
        datas.append((d, d))

# code_examples 目录
if os.path.exists("data/code_examples"):
    datas.append(("data/code_examples", "data/code_examples"))

# Vue 桌面端静态资源。build-electron.bat 会先生成 frontend/dist。
if os.path.exists("frontend/dist/index.html"):
    datas.append(("frontend/dist", "frontend/dist"))

# ── 排除的模块（减小体积）────────────────────────────────
excludes = [
    "pytest",
    "pytest_asyncio",
    "pytest_cov",
    "pytest_benchmark",
    "mypy",
    "ruff",
    "pre_commit",
    "matplotlib",
    "torch",
    "torchvision",
    "torchaudio",
    "functorch",
    "backend.app.research.models.dkt",
    "backend.app.research.models.sakt",
    "IPython",
    "notebook",
    "jupyter",
    "jupyterlab",
    "playwright",
    "cairosvg",
]

# ── Analysis ───────────────────────────────────────────
a = Analysis(
    ["backend/desktop_entry.py"],
    pathex=[os.getcwd()],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)

# ── PYZ ────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="a3-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # 保留控制台窗口，方便查看后端日志
    icon="electron/assets/icon.ico" if os.path.exists("electron/assets/icon.ico") else None,
)

# ── COLLECT (onedir) ───────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="a3-backend",
)
