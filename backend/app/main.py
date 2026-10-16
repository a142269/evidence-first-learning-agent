from __future__ import annotations
import asyncio

import logging
import mimetypes
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.auth import _get_session, _parse_bearer_token
from backend.app.api.router import api_router
from backend.app.api.v2.router import api_v2_router
from backend.app.core.deployment_policy import production_mode, validate_deployment
from backend.app.core.v1_production_access import v1_route_allowed


LOGGER = logging.getLogger(__name__)

_PUBLIC_AUTH_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
}


app = FastAPI(
    title="A3 个性化学习智能体系统 API",
    version="1.0.0",
    description="基于大模型的个性化资源生成与学习多智能体系统",
)


@app.middleware("http")
async def _require_auth_for_api(request, call_next):
    path = request.url.path

    if production_mode() and path.startswith("/api/v1/"):
        # Public login/registration still have an exact method/path check. The
        # authenticated legacy surface is checked again after session lookup.
        if path in _PUBLIC_AUTH_PATHS:
            if not v1_route_allowed(request.method, path, None):
                return JSONResponse(status_code=403, content={"detail": "v1_route_unavailable_in_production"})
            return await call_next(request)

    if path.startswith("/api/v1") and path not in _PUBLIC_AUTH_PATHS:
        # 公开接口列表（无需认证即可访问）
        _PUBLIC_PREFIXES = (
            "/api/v1/chat/",
            "/api/v1/profile/",
            "/api/v1/resources/",
            "/api/v1/learning-path/",
            "/api/v1/assessment/",
            "/api/v1/knowledge/",
            "/api/v1/mistakes/",
            "/api/v1/cognitive/",
            "/api/v1/knowledge-graph/",
            "/api/v1/gamification/",
            "/api/v1/social/",
            "/api/v1/system/",
            "/api/v1/cockpit/",
            "/api/v1/safety/",
            "/api/v1/learner-state/",
            "/api/v1/agent-tools/",
            "/api/v1/smart-tutor/",
            "/api/v1/spaced-repetition/",  # Plan D · 3.3
            "/api/v1/insights/",
            "/api/v1/artifacts/",
            "/api/v1/metrics/",
            "/api/v1/group-chat/",  # 课程群聊（学生端刷新拉取，与 chat 同级公开）
            "/api/v1/learner/",  # learner 视角查询（GraphView 路径叠加/掌握度趋势）
        )
        if not production_mode() and any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
            return await call_next(request)

        try:
            token = _parse_bearer_token(request.headers.get("Authorization"))
            session = await asyncio.to_thread(_get_session, token)
        except Exception as exc:
            detail = getattr(exc, "detail", "authorization_required")
            status_code = getattr(exc, "status_code", 401)
            return JSONResponse(status_code=status_code, content={"detail": detail})

        if production_mode() and not v1_route_allowed(request.method, path, session.role):
            return JSONResponse(status_code=403, content={"detail": "v1_route_unavailable_in_production"})

        # 教师管理端仅 teacher / admin 可用（学生 token 拒绝）
        if path.startswith("/api/v1/teacher/") and session.role not in ("teacher", "admin"):
            return JSONResponse(status_code=403, content={"detail": "teacher_role_required"})

    return await call_next(request)


_extra_cors_origins = [
    value.strip()
    for value in os.getenv("A3_CORS_ORIGINS", "").split(",")
    if value.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_cors_origins if production_mode() else [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        # 桌面版：后端同时服务前端，同源访问
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:18000",
        "http://127.0.0.1:18000",
        # Electron file:// 协议
        "null",
        "capacitor://localhost",
        "http://localhost",
        *_extra_cors_origins,
    ],
    allow_origin_regex=None if production_mode() else r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+):(517\d|8000|18000)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
app.include_router(api_v2_router)


def _ensure_course_resources() -> dict[str, int]:
    """Backfill both course resource packs and refresh the API memory cache."""
    from backend.app.api.v1 import resources as resources_api
    from backend.app.core.seed_db import seed_py_teacher_resources, seed_teacher_resources

    inserted = {
        "artificial_intelligence": seed_teacher_resources(),
        "python_programming": seed_py_teacher_resources(),
    }
    resources_api._load_from_db()
    return inserted


@app.on_event("startup")
async def _warmup() -> None:
    """初始化数据库并预热知识库索引，避免首次请求长延迟。"""
    from backend.app.agent_runtime.checkpointing import initialize_checkpointer
    from backend.app.core.database import init_db
    from backend.app.core.observability import configure_observability

    validate_deployment()
    configure_observability()
    init_db()
    await initialize_checkpointer()
    # Retire only expired V2 leases; never auto-replay models or tools at startup.
    from backend.app.agent_runtime.run_leases import expire_batch
    try:
        await asyncio.to_thread(expire_batch)
    except Exception as exc:
        LOGGER.warning("Run lease sweep unavailable (%s)", type(exc).__name__)
    try:
        from backend.app.services.rag_service import get_rag_service
        rag = get_rag_service()
        stats = rag.stats()
        LOGGER.info(f"[startup] RAG 已就绪: {stats}")
    except Exception as exc:
        LOGGER.warning(f"[startup] RAG 预热失败（不影响运行）: {exc}")

    # 空库时自动导入种子数据（幂等，已有数据则跳过）
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord
        with SessionLocal() as db:
            if db.query(KnowledgePointRecord).count() == 0:
                LOGGER.info("[startup] 检测到空数据库，开始导入种子数据…")
                from backend.app.core.seed_db import seed_all
                seed_all(verbose=True)
                LOGGER.info("[startup] 种子数据导入完成")
    except Exception as exc:
        LOGGER.warning(f"[startup] 种子数据导入失败（不影响运行）: {exc}")

    # 扫描并注册现有资源文件
    try:
        inserted = _ensure_course_resources()
        LOGGER.info("[startup] course resources ready: %s", inserted)
    except Exception as exc:
        LOGGER.warning("[startup] course resource backfill failed: %s", exc)

    try:
        _scan_and_register_existing_artifacts()
    except Exception as exc:
        LOGGER.warning(f"[startup] 资源扫描失败（不影响运行）: {exc}")

@app.on_event("shutdown")
async def _shutdown_agent_runtime() -> None:
    from backend.app.agent_runtime.checkpointing import shutdown_checkpointer

    await shutdown_checkpointer()


LEGACY_ARTIFACT_COURSE = "artificial_intelligence"


def _scan_and_register_existing_artifacts():
    """扫描 data/artifacts 目录并注册现有资源"""
    from backend.app.api.v1.artifacts.registry import get_artifact_registry
    import hashlib
    import json

    registry = get_artifact_registry()
    base_path = Path(__file__).parent.parent.parent / "data"
    artifact_dir = base_path / "artifacts"

    count = 0

    def register_file(
        file_path: Path,
        artifact_type: str,
        prefix: str,
        metadata: dict,
    ) -> bool:
        """仅登记尚未持久化的文件，并使用跨进程稳定的恢复 ID。"""
        absolute = file_path.resolve()
        if registry.find_by_filepath(str(absolute)):
            return False
        digest = hashlib.sha1(str(absolute).encode("utf-8")).hexdigest()[:10]
        registry.register(
            resource_id=f"{prefix}_{file_path.stem}_{digest}",
            artifact_type=artifact_type,
            filepath=str(absolute),
            metadata={**metadata, "recovered": True},
            session_id="system_scan",
            persist=False,
        )
        return True

    # 1. 扫描 MP3
    mp3_dir = artifact_dir / "mp3"
    if mp3_dir.exists():
        for f in mp3_dir.glob("*.mp3"):
            if f.name.startswith('_') or f.name.startswith('test_'):
                continue
            count += int(register_file(
                f, "mp3", "mp3",
                {"title": f"语音导学: {f.stem}", "duration": "5-8分钟", "course": LEGACY_ARTIFACT_COURSE},
            ))

    # 2. 扫描 PPT
    pptx_dir = artifact_dir / "pptx"
    if pptx_dir.exists():
        for f in pptx_dir.glob("*.pptx"):
            if f.name.startswith('_') or f.name.startswith('bad'):
                continue
            count += int(register_file(
                f, "pptx", "pptx",
                {"title": f"课件: {f.stem}", "slides": "10-20页", "course": LEGACY_ARTIFACT_COURSE},
            ))

    # 3. 扫描 Mermaid 图片
    mermaid_dir = artifact_dir / "mermaid_png"
    if mermaid_dir.exists():
        for f in mermaid_dir.glob("*.png"):
            count += int(register_file(
                f, "mermaid_png", "mermaid",
                {"title": f"思维导图: {f.stem}", "type": "知识图谱", "course": LEGACY_ARTIFACT_COURSE},
            ))

    # 4. 扫描已生成讲解视频。启动恢复时使用 system_scan 会话，保证文件仍可
    # 在资源中心查看；当前会话中新生成的视频仍由生成接口写入真实 session_id。
    video_dir = artifact_dir / "video"
    if video_dir.exists():
        for f in video_dir.glob("*.mp4"):
            if f.name.startswith(("_", "test_", "diagnostic_")):
                continue
            count += int(register_file(
                f, "video", "video",
                {"title": f"视频讲解: {f.stem}", "format": "mp4", "course": LEGACY_ARTIFACT_COURSE},
            ))

    # 5. 扫描代码示例
    code_sources = [artifact_dir / "code", base_path / "code_examples"]
    for code_dir in code_sources:
        if not code_dir.exists():
            continue
        for pattern in ("*.py", "*.txt", "*.ipynb"):
            for f in code_dir.glob(pattern):
                if f.name.startswith(("_", "test_")):
                    continue
                kind = "Jupyter Notebook" if f.suffix == ".ipynb" else "可运行代码示例"
                count += int(register_file(
                    f, "code_result", "code",
                    {"title": f"代码示例: {f.stem}", "type": kind, "course": LEGACY_ARTIFACT_COURSE},
                ))

    # 6. 扫描题库
    quiz_files = [
        (base_path / "question_bank.json", "主题库"),
        (base_path / "quiz_bank.json", "测验题库"),
        (base_path / "question_bank_analytics_0708.json", "分析题库"),
    ]
    for qf, desc in quiz_files:
        if qf.exists():
            try:
                with open(qf, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    qcount = len(data) if isinstance(data, list) else len(data.get('questions', []))
                count += int(register_file(
                    qf, "quiz_bank", "quiz",
                    {"title": f"{desc} ({qcount}题)", "question_count": qcount, "course": LEGACY_ARTIFACT_COURSE},
                ))
            except Exception:
                pass

    if count > 0:
        registry.flush()
        LOGGER.info(f"[startup] 已扫描并注册 {count} 个现有资源")
    pruned = registry.prune_missing()
    if pruned > 0:
        LOGGER.info(f"[startup] 已清理 {pruned} 个失效资源索引")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "app": "A3 Learning Agent System"}


@app.get("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint — pure Python, zero dependencies."""
    from fastapi.responses import PlainTextResponse
    from backend.app.core.telemetry import get_telemetry
    return PlainTextResponse(
        content=get_telemetry().export_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@app.get("/metrics/llm-cost")
def llm_cost() -> dict:
    """LLM 调用成本统计 —— 给答辩演示 / 成本监控 dashboard 用。

    聚合 telemetry 中的 llm_calls_total / llm_tokens_total / llm_cost_yuan，
    按 provider 拆分，输出调用次数 / token 用量 / 估算成本（元）。

    成本估算（参考 2026 讯飞星火 v3.5 定价，单位：元/千 token）:
      - spark: input 0.018, output 0.018
      - openai_compatible: input 0.022, output 0.022
      - mock: 0
    """
    from backend.app.core.telemetry import get_telemetry

    reg = get_telemetry()
    # 定价表（元/千 token，可按 provider 扩展）
    PRICING = {
        "spark": {"input": 0.018, "output": 0.018},
        "openai_compatible": {"input": 0.022, "output": 0.022},
        "mock": {"input": 0.0, "output": 0.0},
    }

    # 从 counter 提取按 provider 聚合的调用数
    calls_counter = reg.counter("llm_calls_total")
    tokens_counter = reg.counter("llm_tokens_total")
    cost_gauge = reg.gauge("llm_cost_yuan")

    # counter 内部 _values: {((provider, p_val), (status, s_val)): count}
    by_provider: dict[str, dict] = {}
    for key, count in calls_counter._values.items():
        labels = dict(key)
        provider = labels.get("provider", "unknown")
        status = labels.get("status", "unknown")
        entry = by_provider.setdefault(provider, {
            "provider": provider, "calls": 0.0, "success": 0.0, "failed": 0.0,
            "tokens_input": 0.0, "tokens_output": 0.0, "cost_yuan": 0.0,
        })
        entry["calls"] += count
        if status == "success":
            entry["success"] += count
        else:
            entry["failed"] += count

    # token 聚合
    for key, tokens in tokens_counter._values.items():
        labels = dict(key)
        provider = labels.get("provider", "unknown")
        tok_type = labels.get("type", "input")
        entry = by_provider.setdefault(provider, {
            "provider": provider, "calls": 0.0, "success": 0.0, "failed": 0.0,
            "tokens_input": 0.0, "tokens_output": 0.0, "cost_yuan": 0.0,
        })
        if tok_type == "output":
            entry["tokens_output"] += tokens
        else:
            entry["tokens_input"] += tokens

    # 成本估算
    total_cost = 0.0
    for provider, entry in by_provider.items():
        rate = PRICING.get(provider, PRICING["mock"])
        cost = (entry["tokens_input"] / 1000.0 * rate["input"]
                + entry["tokens_output"] / 1000.0 * rate["output"])
        entry["cost_yuan"] = round(cost, 4)
        total_cost += cost

    # 同步到 gauge（便于 /metrics 也能查）
    cost_gauge.set(round(total_cost, 4))

    return {
        "total_calls": sum(e["calls"] for e in by_provider.values()),
        "total_tokens_input": sum(e["tokens_input"] for e in by_provider.values()),
        "total_tokens_output": sum(e["tokens_output"] for e in by_provider.values()),
        "total_cost_yuan": round(total_cost, 4),
        "by_provider": list(by_provider.values()),
        "pricing_reference": PRICING,
        "note": "成本为基于公开定价的估算值，实际以服务商账单为准。",
    }


@app.get("/api/v1/system/status")
def system_status() -> dict:
    """系统总体状态 —— 给前端首页/答辩演示用"""
    from backend.app.services.rag_service import get_rag_service
    from backend.app.core.config import get_config

    cfg = get_config()
    rag_stats = get_rag_service().stats()
    return {
        "app": "A3 Learning Agent System",
        "llm_provider": cfg.llm.provider,
        "profile_dimensions": cfg.profile_dimensions,
        "rag": rag_stats,
        "agents": [
            "profile_agent", "course_expert", "quiz_generator", "path_planner",
            "multimodal_agent", "tutor_agent", "evaluator_agent", "reviewer",
        ],
    }


# ============================================================
# 桌面版 / 生产环境：挂载前端静态文件
# ============================================================
# 当 frontend/dist 存在时，FastAPI 同时服务 API 和前端 SPA，
# Electron 只需加载 http://127.0.0.1:18000 即可，无需 CORS。
# 开发模式下（无 dist 目录）不影响现有的前后端分离开发流程。

def _find_frontend_dist() -> Path | None:
    """按优先级查找前端构建产物目录。"""
    pyinstaller_root = getattr(sys, "_MEIPASS", None)
    candidates = [
        Path(os.environ["A3_FRONTEND_DIST"]) if os.environ.get("A3_FRONTEND_DIST") else None,
        Path(pyinstaller_root) / "frontend" / "dist" if pyinstaller_root else None,
        Path(sys.executable).resolve().parent / "frontend" / "dist",
        Path(__file__).resolve().parents[2] / "frontend" / "dist",   # 项目根/frontend/dist
        Path(__file__).resolve().parents[1] / "frontend" / "dist",   # PyInstaller onedir
        Path.cwd() / "frontend" / "dist",                              # CWD 兜底
    ]
    for p in candidates:
        if p is None:
            continue
        if (p / "index.html").exists():
            return p
    return None


_FRONTEND_DIST = _find_frontend_dist()

if _FRONTEND_DIST:
    from fastapi.responses import FileResponse

    mimetypes.add_type("text/javascript", ".js")
    mimetypes.add_type("text/css", ".css")

    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend-assets")

    LOGGER.info(f"[desktop] 前端静态文件已挂载: {_FRONTEND_DIST}")

    @app.get("/{full_path:path}")
    async def _spa_fallback(full_path: str):
        """Vue Router 历史模式 fallback：所有未命中路径返回 index.html"""
        # 不拦截 API 和已挂载的静态资源
        if full_path.startswith(("api/", "healthz", "metrics", "assets/")):
            return JSONResponse(status_code=404, content={"detail": "not found"})
        # 如果请求的是 dist 中的真实文件（如 integrated-map/index.html），直接返回
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        # SPA fallback：返回 index.html 让 Vue Router 处理
        index_file = _FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(status_code=404, content={"detail": "frontend not built"})
