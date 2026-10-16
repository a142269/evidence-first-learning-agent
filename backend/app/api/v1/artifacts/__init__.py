"""
Artifacts API 子包 - 5 类资源生成 + 下载 + 元数据

模块划分:
    registry.py            ArtifactRegistry (单例, in-memory)
    download.py            GET 类路由 (5 种文件下载 + data-uri + list/info)
    generate.py            POST /generate/* — 5 类资源生成
    multi.py               POST /generate/multi — 一键生成多类资源 (演示高光)
    multi_with_fallback.py POST /generate/multi-with-fallback — Manim 兜底富化 (Plan D 2.4)

向后兼容:
    router 直接 export 给 backend.app.api.router 使用。
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.artifacts.download import router as download_router
from backend.app.api.v1.artifacts.generate import router as generate_router
from backend.app.api.v1.artifacts.multi import router as multi_router
from backend.app.api.v1.artifacts.multi_with_fallback import (
    router as multi_fallback_router,
)
from backend.app.api.v1.artifacts.multi_stream import (
    router as multi_stream_router,
)
from backend.app.api.v1.artifacts.registry import (
    ArtifactRecord,
    ArtifactRegistry,
    get_artifact_registry,
    reset_artifact_registry,
)


# 聚合子 router 到一个对外暴露的 router
router = APIRouter()
router.include_router(download_router)
router.include_router(generate_router)
router.include_router(multi_router)
router.include_router(multi_fallback_router)
router.include_router(multi_stream_router)


__all__ = [
    "router",
    "ArtifactRecord",
    "ArtifactRegistry",
    "get_artifact_registry",
    "reset_artifact_registry",
]
