"""
POST /artifacts/generate/multi-stream — SSE 流式多资源生成

赛题需求：多模态资源生成的响应效率需满足实际学习场景需求，
如提供"生成进度追踪"或"流式呈现"机制，避免长时间白屏等待。

设计：
- 复用 multi.py 的 _gen_pptx / _gen_mermaid / _gen_code / _gen_tts / _gen_manim 等协程
- 用 asyncio.as_completed 逐个 yield SSE 事件，每完成一个资源就推送
- 前端通过 EventSource / fetch stream 实时更新节点状态（queue → running → done/failed）
- 最终推送一个 done 事件，携带完整聚合结果

SSE 事件协议：
  event: start     data: {types_requested, topic}
  event: progress  data: {type, status, detail, duration_ms, envelope?}
  event: done      data: {MultiResourceResponse JSON}

对比 /generate/multi（非流式）：
  - 非流式：所有资源并行跑，HTTP 响应等全部完成才返回（用户看到白屏）
  - 流式：每完成一个就推一条事件，前端实时更新进度条和节点状态
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.api.v1.artifacts.multi import (
    MultiResourceRequest,
    MultiResourceResponse,
    ResourceEnvelope,
    SUPPORTED_TYPES,
    _gen_pptx,
    _gen_mermaid,
    _gen_code,
    _gen_tts,
    _gen_manim,
    _gen_document,
    _gen_quiz,
    _build_downloads,
    _record_trace_for_multi,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/artifacts", tags=["artifacts"])


# ================================================================
# SSE 辅助
# ================================================================
def _sse_event(event: str, data: Any) -> str:
    """格式化一条 SSE 事件文本。"""
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


# ================================================================
# 资源生成器映射
# ================================================================
_GEN_MAP = {
    "pptx": _gen_pptx,
    "mermaid": _gen_mermaid,
    "code": _gen_code,
    "tts": _gen_tts,
    "manim": _gen_manim,
    "document": _gen_document,
    "quiz": _gen_quiz,
}


# ================================================================
# 主路由 — SSE 流式
# ================================================================
@router.post("/generate/multi-stream")
async def generate_multi_stream(req: MultiResourceRequest = Body(...)):
    """SSE 流式多资源生成 — 逐个推送完成事件，避免白屏等待。

    前端使用 fetch + ReadableStream 消费（EventSource 不支持 POST）。
    """
    start = time.perf_counter()
    if req.include_manim and "manim" not in req.types:
        req.types = list(req.types) + ["manim"]

    # P1-6 trace 记录
    await _record_trace_for_multi(req)

    requested = [t for t in req.types if t in SUPPORTED_TYPES] or ["mermaid"]

    async def event_generator():
        # 1. 推送 start 事件
        yield _sse_event("start", {
            "topic": req.topic,
            "types_requested": requested,
            "total": len(requested),
        })

        # 2. 构建并行任务
        tasks: Dict[str, asyncio.Task] = {}
        for t in requested:
            gen_fn = _GEN_MAP.get(t)
            if gen_fn:
                tasks[t] = asyncio.create_task(gen_fn(req))

        results: Dict[str, ResourceEnvelope] = {}
        succeeded: List[str] = []
        failed: List[str] = []
        all_artifact_ids: List[str] = []
        all_cov_scores: List[float] = []
        all_safety_risks: List[float] = []

        # 3. 用 as_completed 逐个推送完成事件
        pending = {task: rtype for rtype, task in tasks.items()}
        while pending:
            done, _ = await asyncio.wait(
                pending.keys(), return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                rtype = pending.pop(task)
                try:
                    envelope = await task
                    if isinstance(envelope, ResourceEnvelope):
                        results[rtype] = envelope
                        if envelope.success:
                            succeeded.append(rtype)
                            all_artifact_ids.extend(
                                [d["id"] for d in envelope.downloads]
                            )
                            if envelope.cov.get("checked"):
                                all_cov_scores.append(
                                    float(envelope.cov.get("score", 0.0))
                                )
                            if envelope.safety.get("checked"):
                                all_safety_risks.append(
                                    float(envelope.safety.get("overall_risk", 0.0))
                                )
                        else:
                            failed.append(rtype)
                        # 推送 progress 事件
                        yield _sse_event("progress", {
                            "type": rtype,
                            "status": "done" if envelope.success else "failed",
                            "detail": envelope.error or "",
                            "envelope": envelope.model_dump(),
                        })
                    else:
                        failed.append(rtype)
                        yield _sse_event("progress", {
                            "type": rtype,
                            "status": "failed",
                            "detail": "unexpected return type",
                        })
                except Exception as exc:
                    logger.warning(f"[multi-stream] {rtype} failed: {exc}")
                    failed.append(rtype)
                    results[rtype] = ResourceEnvelope(
                        success=False, type=rtype, error=str(exc),
                    )
                    yield _sse_event("progress", {
                        "type": rtype,
                        "status": "failed",
                        "detail": str(exc),
                    })

        # 4. 聚合分
        overall_quality = (
            round(sum(all_cov_scores) / max(1, len(all_cov_scores)), 3)
            if all_cov_scores else 0.0
        )
        overall_safety = (
            round(1.0 - sum(all_safety_risks) / max(1, len(all_safety_risks)), 3)
            if all_safety_risks else 1.0
        )

        profile = {
            "user_id": req.user_id,
            "kp_id": req.kp_id,
            "bloom_level": req.bloom_level,
            "learning_objective": req.learning_objective,
            "misconception": req.misconception,
        }

        resp = MultiResourceResponse(
            topic=req.topic,
            types_requested=requested,
            types_succeeded=succeeded,
            types_failed=failed,
            results=results,
            total_duration_ms=round((time.perf_counter() - start) * 1000, 2),
            success_count=len(succeeded),
            profile=profile,
            overall_quality=overall_quality,
            overall_safety=overall_safety,
        )

        # 5. 推送 done 事件
        yield _sse_event("done", resp.model_dump())

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
