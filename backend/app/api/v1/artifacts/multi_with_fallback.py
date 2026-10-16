"""
Plan D · 2.4 — Manim 三级降级补强 (Mermaid + TTS 双轨兜底)

为什么单独文件
==============
- Plan D 设计原则："尽量不动已有代码"，已有 multi.py 的 _gen_manim 是稳定主线。
- 本模块作为 sibling，**不修改 multi.py**，而是新增端点
  POST /api/v1/artifacts/generate/multi-with-fallback，
  复用 multi.generate_multi() 的产物，再对 manim envelope 做兜底富化。
- 前端通过 include_manim=true + 调用 rich 端点即可激活，无需改 multi 协议。

降级链路
========
Level 1 (manim CLI)  → MP4 视频
Level 2 (Playwright) → PNG 静态截图
Level 3 (Placeholder SVG) → 概念卡片

兜底富化（当 Level 1 / Level 2 都失败时）：
  → 自动追加 Mermaid 概念图 + TTS 语音解说，让前端永远有
    「可视化 + 可听」的内容可展示。

与 Plan P1-5 / P1-6 完全兼容
=============================
- 调用 generate_multi() 拿到完整 envelope（evidence / cov / safety / downloads）
- 只在 manim 结果 metadata 字段追加 fallback_assets，不动其它字段
- 前端现有 /generate/multi 渲染逻辑完全不动
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

from backend.app.api.v1.artifacts.multi import (
    MultiResourceRequest,
    MultiResourceResponse,
    ResourceEnvelope,
    generate_multi,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


# ============================================================
# helpers
# ============================================================
def _detect_manim_needs_fallback(envelope: ResourceEnvelope) -> tuple[bool, str]:
    """检测 manim envelope 是否需要走兜底链。

    触发条件（任意一个满足即可）：
      1. envelope.success=False                       → manim_render_failed
      2. metadata.rendered=True 且 filepath 空         → manim_render_no_video
         (用户要 include_manim=true 但没拿到文件)
      3. metadata.rendered=True 且 filepath 后缀是 .svg → manim_fell_back_to_placeholder
         (用户要视频但只拿到占位 SVG)

    注：multi.py 的 _gen_manim 当前没透传 render_method，
    我们用 rendered + filepath 后缀两个信号做兜底判定。

    Returns:
        (needs_fallback, reason)
    """
    if not envelope.success:
        return True, "manim_render_failed"
    meta = envelope.metadata or {}
    rendered = bool(meta.get("rendered"))
    filepath = (envelope.filepath or "").lower()
    if rendered and not filepath:
        return True, "manim_render_no_video"
    if rendered and filepath.endswith(".svg"):
        return True, "manim_fell_back_to_placeholder"
    return False, ""


def _trim_envelope(env: ResourceEnvelope) -> Dict[str, Any]:
    """截取兜底 envelope 的关键字段，避免重复 evidence/cov。"""
    return {
        "type": env.type,
        "success": env.success,
        "filepath": env.filepath,
        "content_preview": (env.content or "")[:600],
        "metadata": dict(env.metadata or {}),
        "downloads": list(env.downloads or []),
    }


async def _build_manim_fallback(
    manim_envelope: ResourceEnvelope, req: MultiResourceRequest,
) -> Dict[str, Any]:
    """并发跑 Mermaid + TTS 富化，给 manim 兜底。

    Returns:
        永远返回 5 键 dict（used / reason / method / mermaid / tts）：
          - 不需要兜底：used=False，其余 None / ""
          - 需要兜底：used=True，reason 非空，mermaid/tts 各自可能为 None
    """
    fallback: Dict[str, Any] = {
        "used": False,
        "reason": "",
        "method": (manim_envelope.metadata or {}).get("render_method") or "code_only",
        "rendered": bool((manim_envelope.metadata or {}).get("rendered")),
        "mermaid": None,
        "tts": None,
    }
    needs, reason = _detect_manim_needs_fallback(manim_envelope)
    if not needs:
        return fallback

    fallback["used"] = True
    fallback["reason"] = reason
    logger.info(
        f"[multi-with-fallback] fallback triggered: reason={reason} "
        f"topic={req.topic!r}"
    )

    # 直接调用 multi._gen_mermaid / multi._gen_tts（同进程内复用）
    from backend.app.api.v1.artifacts.multi import _gen_mermaid, _gen_tts

    mer, ter = await asyncio.gather(
        _gen_mermaid(req), _gen_tts(req),
        return_exceptions=True,
    )
    if isinstance(mer, ResourceEnvelope):
        fallback["mermaid"] = _trim_envelope(mer)
    elif isinstance(mer, Exception):
        logger.warning(f"[multi-with-fallback] mermaid fallback failed: {mer}")
    if isinstance(ter, ResourceEnvelope):
        fallback["tts"] = _trim_envelope(ter)
    elif isinstance(ter, Exception):
        logger.warning(f"[multi-with-fallback] tts fallback failed: {ter}")
    return fallback


# ============================================================
# 主路由 — Plan D · 2.4 入口
# ============================================================
@router.post("/generate/multi-with-fallback", response_model=MultiResourceResponse)
async def generate_multi_with_fallback(
    req: MultiResourceRequest = Body(...),
) -> MultiResourceResponse:
    """Plan D · 2.4 — 一键多资源生成 + Manim 兜底富化

    等价于 :func:`backend.app.api.v1.artifacts.multi.generate_multi`，
    但额外在 manim envelope.metadata.fallback_assets 里塞入
    Mermaid + TTS 双轨兜底产物（仅在 manim 渲染失败时触发）。

    用法：
        curl -X POST http://127.0.0.1:8000/api/v1/artifacts/generate/multi-with-fallback \\
             -H "Content-Type: application/json" \\
             -d '{"topic":"Self-Attention","types":["manim","mermaid","tts"],
                  "include_manim":true,"kp_id":"self_attention"}'

    Returns:
        MultiResourceResponse，manim envelope.metadata.fallback_assets
        含 {used, reason, method, mermaid, tts} 五字段
    """
    try:
        # 复用 multi.py 的主流程
        base_resp: MultiResourceResponse = await generate_multi(req)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[multi-with-fallback] generate_multi failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # 只在请求含 manim 时做兜底
    if "manim" not in (req.types or []):
        return base_resp

    manim_env: Optional[ResourceEnvelope] = base_resp.results.get("manim")
    if manim_env is None:
        return base_resp

    # 跑兜底链 — 无论是否触发都返回 fallback_assets，
    # 让前端 envelope.metadata.fallback_assets 永远存在（前端写起来简单）
    fallback_assets = await _build_manim_fallback(manim_env, req)

    # 把 fallback 塞进 envelope.metadata.fallback_assets（不动 envelope 其它字段）
    existing_meta = dict(manim_env.metadata or {})
    existing_meta["fallback_assets"] = fallback_assets
    new_envelope = manim_env.model_copy(update={"metadata": existing_meta})
    new_results = dict(base_resp.results)
    new_results["manim"] = new_envelope
    return base_resp.model_copy(update={"results": new_results})


__all__ = ["router", "generate_multi_with_fallback"]