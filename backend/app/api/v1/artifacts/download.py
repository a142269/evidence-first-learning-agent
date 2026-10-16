"""
Artifacts 下载端点 - GET 类路由

支持的资源类型 ↔ 路径映射:
    pptx        → data/artifacts/pptx/{rid}.pptx
    mp3         → data/artifacts/mp3/{rid}.mp3
    png         → data/artifacts/png/{rid}.png
    mermaid     → data/artifacts/mermaid_png/{rid}.png
    manim       → data/artifacts/manim/{rid}.mp4
    qr          → data/artifacts/qr/{rid}.png

每个端点:
- 文件不存在返回 404
- 文件存在用 FileResponse 流式下载, 带正确 media_type
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.app.api.v1.artifacts.registry import get_artifact_registry


router = APIRouter(prefix="/artifacts", tags=["artifacts"])


ARTIFACTS_ROOT = Path("data/artifacts")


# ================================================================
# 类型 ↔ 路径映射
# ================================================================
TYPE_TO_SUBDIR_AND_EXT = {
    "pptx":         ("pptx", "pptx"),
    "mp3":          ("mp3", "mp3"),
    "png":          ("png", "png"),
    "mermaid":      ("mermaid_png", "png"),
    "mermaid_png":  ("mermaid_png", "png"),
    "manim":        ("manim", "mp4"),
    "manim_video":  ("manim", "mp4"),
    "qr":           ("qr", "png"),
    "svg":          ("svg", "svg"),
}

MEDIA_TYPES = {
    "pptx": (
        "application/vnd.openxmlformats-officedocument."
        "presentationml.presentation"
    ),
    "mp3":  "audio/mpeg",
    "wav":  "audio/wav",
    "png":  "image/png",
    "mp4":  "video/mp4",
    "svg":  "image/svg+xml",
    "md":   "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
    "txt":  "text/plain; charset=utf-8",
    "py":   "text/x-python; charset=utf-8",
    "mmd":  "text/plain; charset=utf-8",
}


def _resolve(rid: str, kind: str) -> Path:
    """根据 kind 和 rid 算出文件路径"""
    subdir, ext = TYPE_TO_SUBDIR_AND_EXT.get(kind, (kind, kind))
    return ARTIFACTS_ROOT / subdir / f"{rid}.{ext}"


def _media_type(kind: str) -> str:
    ext = TYPE_TO_SUBDIR_AND_EXT.get(kind, (kind, kind))[1]
    return MEDIA_TYPES.get(ext, "application/octet-stream")


# ================================================================
# 通用下载端点 — 从 registry 查 filepath 直接返回文件
# ================================================================
_EXT_TO_MEDIA = {
    ".pptx": MEDIA_TYPES["pptx"],
    ".mp3":  MEDIA_TYPES["mp3"],
    ".wav":  MEDIA_TYPES["wav"],
    ".png":  MEDIA_TYPES["png"],
    ".mp4":  MEDIA_TYPES["mp4"],
    ".svg":  MEDIA_TYPES["svg"],
    ".md":   MEDIA_TYPES["md"],
    ".json": MEDIA_TYPES["json"],
    ".txt":  MEDIA_TYPES["txt"],
    ".py":   MEDIA_TYPES["py"],
    ".mmd":  MEDIA_TYPES["mmd"],
}


@router.get("/download/{rid}")
def download_generic(rid: str):
    """通用下载端点 —— 根据 artifact registry 中的 filepath 直接返回文件。

    解决问题：
    - multi.py 的 _gen_document / _gen_quiz 把文件写到 tempfile，
      不在 data/artifacts/{subdir}/ 下，类型特定的端点找不到。
    - _build_downloads 生成的 URL 就是 /api/v1/artifacts/download/{rid}，
      此端点正是对应的 handler。
    """
    rec = get_artifact_registry().get(rid)
    if rec is None:
        raise HTTPException(404, f"artifact {rid} not registered")

    filepath = rec.filepath or ""
    path = Path(filepath) if filepath else None
    try:
        download_ready = bool(path and path.is_file() and path.stat().st_size > 0)
    except OSError:
        download_ready = False
    if not download_ready:
        raise HTTPException(404, f"file not found for artifact {rid}")

    ext = path.suffix.lower()
    media_type = _EXT_TO_MEDIA.get(ext, "application/octet-stream")
    filename = path.name

    return FileResponse(
        str(path),
        media_type=media_type,
        filename=filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


# ================================================================
# 类型特定下载端点
# ================================================================
@router.get("/{rid}/pptx")
def download_pptx(rid: str) -> FileResponse:
    p = _resolve(rid, "pptx")
    if not p.exists():
        raise HTTPException(404, "PPTX not found")
    return FileResponse(str(p), media_type=_media_type("pptx"))


@router.get("/{rid}/mp3")
def download_mp3(rid: str) -> FileResponse:
    p = _resolve(rid, "mp3")
    if not p.exists():
        raise HTTPException(404, "MP3 not found")
    return FileResponse(str(p), media_type=_media_type("mp3"))


@router.get("/{rid}/png")
def download_png(rid: str) -> FileResponse:
    p = _resolve(rid, "png")
    if not p.exists():
        raise HTTPException(404, "PNG not found")
    return FileResponse(str(p), media_type=_media_type("png"))


@router.get("/{rid}/mermaid")
def download_mermaid(rid: str) -> FileResponse:
    p = _resolve(rid, "mermaid")
    if not p.exists():
        raise HTTPException(404, "Mermaid PNG not found")
    return FileResponse(str(p), media_type=_media_type("mermaid"))


@router.get("/{rid}/manim")
def download_manim_video(rid: str) -> FileResponse:
    p = _resolve(rid, "manim")
    if not p.exists():
        raise HTTPException(404, "Manim video not found")
    return FileResponse(str(p), media_type=_media_type("manim"))


@router.get("/{rid}/data-uri")
def get_data_uri(rid: str, kind: str = Query("png")) -> Dict[str, Any]:
    """返回 base64 data URI - 供前端 <img> 直接渲染"""
    record = get_artifact_registry().get(rid)
    p = Path(record.filepath) if record and record.filepath else _resolve(rid, kind)
    if not p.exists():
        raise HTTPException(404, f"{kind} not found")
    with open(p, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    media = _EXT_TO_MEDIA.get(p.suffix.lower(), _media_type(kind))
    return {"data_uri": f"data:{media};base64,{data}", "kind": kind}


# ================================================================
# 列表
# ================================================================
@router.get("/list")
def list_artifacts(
    artifact_type: str = Query(default=""),
    session_id: str = Query(default=""),
    limit: int = Query(default=100, ge=1, le=500),
) -> Dict[str, Any]:
    """列出已注册的 artifacts (按 type / session_id 过滤)"""
    items = get_artifact_registry().list(
        artifact_type=artifact_type,
        session_id=session_id,
        limit=limit,
    )
    return {
        "artifacts": [r.to_dict() for r in items],
        "total": len(items),
    }


@router.get("/info/{rid}")
def get_info(rid: str) -> Dict[str, Any]:
    """获取单个 artifact 元数据 (不下载文件)"""
    rec = get_artifact_registry().get(rid)
    if not rec:
        raise HTTPException(404, f"artifact {rid} not registered")
    return rec.to_dict()
