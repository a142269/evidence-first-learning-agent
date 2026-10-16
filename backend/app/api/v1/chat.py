"""
Chat API - 多智能体对话 (P1-1 Pipeline 重构版)

设计:
- 将原 213 行 spaghetti 一行式代码拆分为 7 阶段流水线
- 业务逻辑全部下沉到 chat_pipeline/ 包
- 本文件只保留 FastAPI 路由 + 请求/响应模型 + SSE 编排

7 阶段:
    1. InputValidationStage    - 输入校验 + 会话准备
    2. RAGRetrievalStage       - 知识库检索
    3. RealtimeStateStage      - 实时学情分析
    4. OrchestrationStage      - 多智能体编排
    5. DebateReflectionStage   - 辩论 + 反思
    6. AggregationStage        - 聚合 + 安全 + 质量
    7. PersistStage            - 持久化 + 历史

SSE 升级:
- 事件含 id, 支持 Last-Event-ID 头实现断线重连
- 心跳保持长连接

迁移自原 chat.py - 保留所有路由 + 响应字段, 向后兼容。
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import APIRouter, Body, Header, HTTPException
from fastapi.responses import StreamingResponse

from backend.app.api.v1.chat_pipeline import (
    PipelineContext,
    build_default_pipeline,
    get_or_create_buffer,
    get_session_store,
    parse_last_event_id,
    sse_format,
    sse_heartbeat,
)
from backend.app.api.v1.chat_pipeline.events import clear_buffer
from backend.app.agents.orchestrator import VALID_AGENT_KEYS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# 对外展示的五位学习伙伴。内部 Agent 类名/路由别名在这里统一收口，
# SSE 和群聊持久化都使用同一套身份，不再把所有结果记到 primary Agent 名下。
_PUBLIC_AGENT_INFO: Dict[str, Dict[str, Any]] = {
    "path_planner": {"key": "planner", "name": "智狐", "role": "学习规划师", "order": 0},
    "path_planner_agent": {"key": "planner", "name": "智狐", "role": "学习规划师", "order": 0},
    "tutor": {"key": "tutor", "name": "智灵", "role": "知识讲师", "order": 1},
    "tutor_agent": {"key": "tutor", "name": "智灵", "role": "知识讲师", "order": 1},
    "doc_gen": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "resource_generator": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "resource_generator_agent": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "mindmap": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "reading": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "video": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "audio": {"key": "content", "name": "阿匠", "role": "内容工匠", "order": 2},
    "exercise": {"key": "quiz", "name": "小龙", "role": "闯关教练", "order": 3},
    "quiz_generator": {"key": "quiz", "name": "小龙", "role": "闯关教练", "order": 3},
    "evaluator": {"key": "evaluation", "name": "团团", "role": "学习评估师", "order": 4},
    "evaluator_agent": {"key": "evaluation", "name": "团团", "role": "学习评估师", "order": 4},
    "safe_decline": {"key": "safety", "name": "球球", "role": "安全守护员", "order": 5},
}


def _clean_public_content(text: str) -> str:
    """移除只供程序解析的结构化代码块，保留人类可读正文。"""
    cleaned = text or ""
    cleaned = re.sub(
        r"```(?:quiz_json|evaluation_result|profile_update|learning_path)\s*\n[\s\S]*?\n```",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?im)^\s{0,3}(?:#{1,6}\s*)?(?:\*\*)?"
        r"(?:结构化数据(?:\s*[（(]?JSON[）)]?)?|路径\s*JSON|JSON\s*数据)"
        r"(?:\*\*)?\s*[:：]?\s*$",
        "",
        cleaned,
    )
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _serialize_agent_messages(ctx: PipelineContext) -> list[Dict[str, Any]]:
    """把编排结果转换成前端可逐条展示的具名 Agent 消息。"""
    rows: list[Dict[str, Any]] = []
    for task_id, resp in (ctx.agent_results or {}).items():
        info = _PUBLIC_AGENT_INFO.get(str(getattr(resp, "agent_name", "")))
        if not info:
            continue
        content = _clean_public_content(str(getattr(resp, "content", "") or ""))
        success = bool(getattr(resp, "success", False))
        if not content and not success:
            detail = str(getattr(resp, "error", "") or "生成超时，请稍后重试").strip()
            content = f"本轮子任务暂未完成：{detail}"
        rows.append({
            "task_id": str(task_id),
            "agent": str(getattr(resp, "agent_name", "")),
            "agent_key": info["key"],
            "display_name": info["name"],
            "role": info["role"],
            "content": content,
            "content_type": str(getattr(resp, "content_type", "markdown") or "markdown"),
            "resources": list(getattr(resp, "resources", None) or []),
            "success": success,
            "error": str(getattr(resp, "error", "") or ""),
            "order": int(info["order"]),
        })

    # 默认按演示脚本的叙事顺序呈现；如果输入明确 @ 了角色，则 @ 出现位置优先。
    request = ctx.user_input or ""
    rows.sort(key=lambda row: (
        request.find(f"@{row['display_name']}")
        if request.find(f"@{row['display_name']}") >= 0
        else 10_000 + row["order"],
        row["order"],
    ))
    for row in rows:
        row.pop("order", None)
    return rows


# ================================================================
# Pipeline 单例
# ================================================================
_pipeline = None


def _get_pipeline():
    """获取全局 Pipeline 单例 (懒加载, 避免启动时全副作用)"""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_default_pipeline()
    return _pipeline


# ================================================================
# 核心处理函数 - 复用于 send / stream
# ================================================================
async def _process_turn(
    sid: str,
    session: Dict[str, Any],
    message: str,
    course: str,
    sse_buffer: Optional[Any] = None,
    target_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """处理 7 阶段流水线并返回标准响应 dict"""
    store = get_session_store()
    services: Dict[str, Any] = {"session_store": store}
    # Plan D · 2.1 — 把 SSE buffer 透传给 Pipeline，让 stage thinking 事件
    # 流到同一个 EventBuffer，前端 stream 接口能 replay_after 拉到。
    if sse_buffer is not None:
        services["sse_buffer"] = sse_buffer
    ctx = PipelineContext(
        session_id=sid,
        session=session,
        user_input=message,
        course=course,
        role_view=session.get("role_view", "student"),
        services=services,
        target_agent=target_agent if target_agent in VALID_AGENT_KEYS else None,
    )
    ctx.telemetry.session_id = sid

    pipeline = _get_pipeline()
    await pipeline.execute(ctx)

    if ctx.abort_reason:
        raise HTTPException(status_code=400, detail=ctx.abort_reason)

    primary = ctx.primary_response
    # Plan D · 2.3 — 从 ProfileAgent 收集画像状态元数据，让上游 SSE 推 profile_status 事件
    profile_meta: dict[str, Any] = {}
    for resp in (ctx.agent_results or {}).values():
        md = getattr(resp, "metadata", None) if resp else None
        if isinstance(md, dict) and "profile_extract_status" in md:
            profile_meta = {
                "status": md.get("profile_extract_status"),
                "dimensions_count": md.get("profile_dimensions_count", 0),
            }
            break

    content = ctx.aggregated_text or ""
    primary_agent = primary.agent_name if primary else "tutor_agent"
    content_type = (primary.content_type if primary else "text") or "text"
    success = primary.success if primary else False
    error = primary.error if primary else "no_primary"
    if not content.strip():
        content, error = _empty_response_fallback(ctx)
        content_type = "markdown"
        success = False
        ctx.aggregated_text = content

    agent_messages = _serialize_agent_messages(ctx)

    return {
        "session_id": sid,
        "primary_agent": primary_agent,
        "content": content,
        "content_type": content_type,
        "resources": (
            (primary.resources or []) if primary else []
        ) + ctx.other_resources,
        "saved_resources": ctx.saved_resources,
        "profile": session.get("profile", {}),
        # Plan D · 2.3 — 画像提取 meta 透传
        "profile_meta": profile_meta,
        "realtime_state": _serialize_state(ctx.realtime_state),
        "rag_hits": [
            {
                "source": r.get("source"),
                "course": r.get("course"),
                "score": r.get("score"),
            }
            for r in ctx.rag_results
        ],
        "agents_invoked": [
            {
                "name": r.agent_name,
                "success": r.success,
                "content_type": r.content_type,
            }
            for r in ctx.agent_results.values()
            if r.agent_name in _PUBLIC_AGENT_INFO
        ],
        # 五位伙伴各自的可展示正文与资源。REST 保持 aggregated content 兼容，
        # SSE 在 team mode 下则逐条发送这些消息。
        "agent_messages": agent_messages,
        "quality": ctx.quality,
        "safety": {"level": ctx.safety_flag, "reason": ctx.safety_reason},
        "debate": _sanitize_debate(ctx.debate_log),
        "reflection": ctx.reflection_log,
        "success": success,
        "error": error,
        "telemetry": ctx.telemetry.summary(),
    }


def _empty_response_fallback(ctx: PipelineContext) -> tuple[str, str]:
    """Return a readable fallback when the pipeline produced no text."""
    fatal_stage = next(
        (m for m in ctx.telemetry.stage_metrics if getattr(m, "fatal", False)),
        None,
    )
    stage_name = getattr(fatal_stage, "name", "") if fatal_stage else ""
    stage_error = getattr(fatal_stage, "error", "") if fatal_stage else ""

    if stage_name == "orchestration":
        reason = (
            "多 Agent 编排超过配置时间仍未完成"
            if "timeout" in stage_error.lower()
            else "多 Agent 编排阶段失败"
        )
        return (
            f"本次请求没有生成完整结果：{reason}。\n\n"
            "系统已经收到请求，但为了避免展示不可靠的空答案，先返回这条诊断信息。"
            "你可以继续这样处理：\n\n"
            "- 将大任务拆成单步：先生成课程资料，再生成 PPT、练习题或学习路径。\n"
            "- 直接发送一个更具体的目标，例如“先生成机器学习基础讲义”。\n"
            "- 如果连续出现，请检查后端 LLM 配置、模型响应时间或 API 限流。\n\n"
            f"原始错误：{stage_error or 'orchestration_failed'}",
            stage_error or "orchestration_failed",
        )

    if stage_name:
        return (
            f"本次请求在「{stage_name}」阶段未生成有效正文。\n\n"
            "请稍后重试，或把任务拆成更具体的单步请求。\n\n"
            f"原始错误：{stage_error or 'empty_response'}",
            stage_error or "empty_response",
        )

    return (
        "本次请求已收到，但后端没有生成有效正文。"
        "请稍后重试，或把任务拆成更具体的单步请求。",
        "empty_response",
    )


def _sanitize_debate(
    debate_log: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """从 debate_log 中剔除不可 JSON 序列化的字段 (AgentResponse 对象)"""
    if not debate_log:
        return None
    return {
        k: v for k, v in debate_log.items()
        if k not in ("final_response",)
    }


def _serialize_state(state: Any) -> Dict[str, Any]:
    if state is None:
        return {}
    return {
        "summary": state.summary(),
        "confusion": state.confusion_level,
        "engagement": state.engagement,
        "emotion": state.emotion,
        "fatigue": state.fatigue_level,
        "cognitive_load": state.cognitive_load_level,
        "confidence": state.confidence_level,
        "curiosity": state.curiosity_level,
        "preferred_reply_style": state.preferred_reply_style,
        "evidence": list(state.evidence or []),
        "next_best_action": state.next_best_action,
    }


# ================================================================
# 路由: POST /chat/send
# ================================================================
@router.post("/send")
async def chat_send(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """同步多智能体对话端点"""
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message_required")

    session_id = str(payload.get("session_id", "")).strip()
    # 单 Agent 模式: dm_session_id 优先作为会话 ID
    dm_session_id = str(payload.get("dm_session_id", "")).strip()
    if dm_session_id:
        session_id = dm_session_id
    target_agent = str(payload.get("target_agent", "")).strip() or None
    course = (
        str(payload.get("course", "artificial_intelligence")).strip()
        or "artificial_intelligence"
    )

    store = get_session_store()
    sid, session = store.get_or_create(session_id)
    _bind_session_user(session, payload)
    result = await _process_turn(sid, session, message, course, target_agent=target_agent)
    _persist_group_chat_turn(payload, message, result)
    return result


def _bind_session_user(session: Dict[str, Any], payload: Dict[str, Any]) -> None:
    """把前端传来的学生 ID 绑定到会话，使画像/资源/评估记录归属真实学生而非会话 ID。"""
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return

    previous_user_id = str(session.get("user_id", "")).strip()
    session["user_id"] = user_id

    # 聊天 session_id 与学生 user_id 是两套标识。过去这里只保存 user_id，
    # 却没有把该学生的持久化画像装入会话，导致 Agent 仍拿空画像工作；切换
    # 演示账号时还可能沿用上一名学生的画像。这里以持久化画像为基线，同一
    # 学生保留本轮会话新增字段，换学生时则完整替换，避免数据串号。
    try:
        from backend.app.api.v1.profile import get_profile

        persisted = dict(get_profile(user_id).get("profile") or {})
        current = dict(session.get("profile") or {}) if previous_user_id == user_id else {}
        merged = dict(persisted)
        for key, value in current.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            elif value not in (None, "", [], {}):
                merged[key] = value
        session["profile"] = merged
        session["profile_user_id"] = user_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("[chat] failed to hydrate profile for %s: %s", user_id, exc)


def _persist_group_chat_turn(
    payload: Dict[str, Any], message: str, result: Dict[str, Any],
) -> None:
    """群聊房间落库：携带 room_id 的对话，把学生提问 + Agent 回复写进
    course:student_id 房间，教师端进入同一房间即可看到完整上下文。
    Best-effort，失败不影响主流程。
    """
    room_id = str(payload.get("room_id", "")).strip()
    if not room_id:
        return
    try:
        from backend.app.repositories.group_chat_repo import get_group_chat_repo

        repo = get_group_chat_repo()
        sender_role = str(payload.get("sender_role", "student")).strip() or "student"
        if sender_role == "counselor":
            sender_role = "teacher"
        sender_id = str(payload.get("user_id", "")).strip()
        sender_name = str(payload.get("sender_name", "")).strip() or sender_id or "学习者"
        repo.append(
            room_id=room_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            content=message,
            message_type="text",
        )
        agent_messages = result.get("agent_messages") or []
        if len(agent_messages) > 1:
            for item in agent_messages:
                content = str(item.get("content", "")).strip()
                if not content:
                    continue
                repo.append(
                    room_id=room_id,
                    sender_id=str(item.get("agent_key") or item.get("agent") or "agent"),
                    sender_name=str(item.get("display_name") or item.get("agent") or "Agent"),
                    sender_role="agent",
                    content=content,
                    message_type="agent_reply",
                    payload={
                        "agent": item.get("agent"),
                        "agent_key": item.get("agent_key"),
                        "role": item.get("role"),
                    },
                )
        else:
            content = str(result.get("content", "")).strip()
            if content:
                item = agent_messages[0] if agent_messages else {}
                repo.append(
                    room_id=room_id,
                    sender_id=str(item.get("agent_key") or result.get("primary_agent", "agent")),
                    sender_name=str(item.get("display_name") or result.get("primary_agent", "agent")),
                    sender_role="agent",
                    content=content,
                    message_type="agent_reply",
                    payload={"agents_invoked": result.get("agents_invoked", [])},
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[chat] group chat persist skipped: %s", exc)


# ================================================================
# 路由: POST /chat/stream  (SSE 流式 + Last-Event-ID 重连)
# ================================================================
@router.post("/stream")
async def chat_stream(
    payload: Dict[str, Any] = Body(...),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
):
    """SSE 流式对话端点

    断线重连:
    - 客户端重连时携带 Last-Event-ID 头
    - 服务端从 EventBuffer 重放之后的事件
    - 若缓冲区已淘汰, 重放全部 (客户端自行去重)
    """
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message_required")

    session_id = str(payload.get("session_id", "")).strip()
    # 单 Agent 模式: dm_session_id 优先作为会话 ID
    dm_session_id = str(payload.get("dm_session_id", "")).strip()
    if dm_session_id:
        session_id = dm_session_id
    target_agent = str(payload.get("target_agent", "")).strip() or None
    course = (
        str(payload.get("course", "artificial_intelligence")).strip()
        or "artificial_intelligence"
    )

    store = get_session_store()
    sid, session = store.get_or_create(session_id)
    _bind_session_user(session, payload)
    resume_after_id = parse_last_event_id(last_event_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        buffer = get_or_create_buffer(sid)

        # ---- 断线重连: 重放之前事件 ----
        if resume_after_id > 0:
            replayed = buffer.replay_after(resume_after_id)
            for evt in replayed:
                yield evt.to_sse_lines()
            if replayed:
                logger.info(
                    f"[chat/stream] resume sid={sid} from id={resume_after_id} "
                    f"replayed={len(replayed)}"
                )

        # ---- 新一轮事件 ----
        evt = buffer.publish("meta", {
            "session_id": sid, "profile": session.get("profile", {}),
        })
        yield evt.to_sse_lines()

        # Plan D · 2.1 — 移除写死的两条 thinking 占位
        # Pipeline.execute 内部会以 emit_thinking() 主动推送 7 阶段状态，
        # 通过 sse_buffer 透传给 _process_turn，前端能逐阶段看到进度。
        await asyncio.sleep(0.02)
        yield sse_heartbeat()

        try:
            turn_task = asyncio.create_task(
                _process_turn(sid, session, message, course, sse_buffer=buffer,
                              target_agent=target_agent),
            )
            last_yielded_id = buffer.latest_id
            
            while not turn_task.done():
                new_events = buffer.replay_after(last_yielded_id)
                for evt in new_events:
                    yield evt.to_sse_lines()
                    last_yielded_id = evt.event_id
                await asyncio.sleep(0.1)
                
            # Yield any remaining events
            for evt in buffer.replay_after(last_yielded_id):
                yield evt.to_sse_lines()
                last_yielded_id = evt.event_id
                
            result = turn_task.result()
            _persist_group_chat_turn(payload, message, result)
        except HTTPException as exc:
            evt = buffer.publish("error", {
                "code": exc.status_code, "detail": exc.detail,
            })
            yield evt.to_sse_lines()
            return
        except Exception as exc:
            logger.exception(f"[chat/stream] failed: {exc}")
            evt = buffer.publish("error", str(exc))
            yield evt.to_sse_lines()
            return

        # ---- 结果事件流 ----
        public_messages = result.get("agent_messages") or []
        stream_primary = (
            public_messages[0].get("agent")
            if len(public_messages) > 1
            else result["primary_agent"]
        )
        evt = buffer.publish("meta", {
            "session_id": sid,
            "agent": stream_primary,
            "profile": result["profile"],
            "agents_invoked": result["agents_invoked"],
            "rag_hits": result["rag_hits"],
            "realtime_state": result["realtime_state"],
        })
        yield evt.to_sse_lines()

        agent_messages = result.get("agent_messages") or []
        team_mode = len(agent_messages) > 1
        if team_mode:
            # 每个 Agent 独立开启、流式输出、附加自己的资源并结束。
            # 前端据 task_id 创建五个气泡，身份和内容不会再归到 primary Agent。
            for item in agent_messages:
                task_id = str(item.get("task_id") or item.get("agent") or "agent")
                start_payload = {
                    key: item.get(key)
                    for key in (
                        "task_id", "agent", "agent_key", "display_name",
                        "role", "content_type", "success", "error",
                    )
                }
                evt = buffer.publish("agent_start", start_payload)
                yield evt.to_sse_lines()

                agent_text = str(item.get("content", ""))
                chunk_size = 16
                for i in range(0, len(agent_text), chunk_size):
                    evt = buffer.publish("agent_chunk", {
                        "task_id": task_id,
                        "agent": item.get("agent"),
                        "text": agent_text[i:i + chunk_size],
                    })
                    yield evt.to_sse_lines()
                    await asyncio.sleep(0.008)

                resources = item.get("resources") or []
                if resources:
                    evt = buffer.publish("agent_resources", {
                        "task_id": task_id,
                        "agent": item.get("agent"),
                        "agent_key": item.get("agent_key"),
                        "resources": resources,
                    })
                    yield evt.to_sse_lines()

                evt = buffer.publish("agent_done", {
                    "task_id": task_id,
                    "agent": item.get("agent"),
                    "success": item.get("success", True),
                    "error": item.get("error", ""),
                })
                yield evt.to_sse_lines()
        else:
            full_text = result["content"]
            chunk_size = 8
            for i in range(0, len(full_text), chunk_size):
                evt = buffer.publish("chunk", full_text[i:i + chunk_size])
                yield evt.to_sse_lines()
                await asyncio.sleep(0.015)

        for event_type, key in [
            ("resources", "resources"),
            ("saved_resources", "saved_resources"),
            ("profile_update", "profile"),
            ("quality", "quality"),
            ("safety", "safety"),
            ("debate", "debate"),
            ("reflection", "reflection"),
            ("telemetry", "telemetry"),
        ]:
            value = result.get(key)
            if value:
                evt = buffer.publish(event_type, value)
                yield evt.to_sse_lines()

        # Plan D · 2.3 — 画像提取状态独立事件，让前端弹 Toast
        try:
            profile_meta = result.get("profile_meta") or {}
            if profile_meta:
                evt = buffer.publish("profile_status", profile_meta)
                yield evt.to_sse_lines()
        except Exception as exc:
            logger.debug(f"[chat/stream] profile_status skip: {exc}")

        evt = buffer.publish("done", {
            "content_type": result["content_type"],
            "multi_agent": team_mode,
            "agent_count": len(agent_messages),
        })
        yield evt.to_sse_lines()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ================================================================
# 路由: GET /chat/profile/{session_id}
# ================================================================
@router.get("/profile/{session_id}")
def get_profile(session_id: str) -> Dict[str, Any]:
    session = get_session_store().get(session_id)
    return {"profile": (session or {}).get("profile", {})}


@router.get("/history/{session_id}")
def get_history(session_id: str) -> Dict[str, Any]:
    session = get_session_store().get(session_id)
    if session:
        return {
            "history": _recover_history_resources(
                session.get("history", []), session_id,
            ),
        }
    # 内存中找不到（刷新/重启后），从数据库加载
    try:
        from backend.app.repositories.chat_history_repo import get_chat_history_repo
        history = get_chat_history_repo().list_by_session(session_id, limit=50)
        return {"history": _recover_history_resources(history, session_id)}
    except Exception:
        return {"history": []}


def _recover_history_resources(
    history: list[Dict[str, Any]], session_id: str,
) -> list[Dict[str, Any]]:
    """为旧聊天恢复资源附件，解决刷新后只剩“已生成”文字的问题。"""
    rows = [dict(item) for item in (history or [])]
    if not rows or any(item.get("resources") for item in rows):
        return rows

    try:
        import base64
        from pathlib import Path

        from backend.app.api.v1.artifacts.registry import get_artifact_registry

        records = get_artifact_registry().list(session_id=session_id, limit=200)
        resources: list[Dict[str, Any]] = []
        for record in records:
            metadata = dict(record.metadata or {})
            path = Path(record.filepath) if record.filepath else None
            record_type = str(record.type or "")
            if path and path.exists() and "code" in record_type:
                try:
                    metadata.setdefault("code", path.read_text(encoding="utf-8")[:120_000])
                    metadata.setdefault("language", "python")
                except (OSError, UnicodeError):
                    pass
            if path and path.exists() and (
                "mermaid" in record_type or record_type in {"png", "mindmap"}
            ):
                try:
                    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                    metadata.setdefault("data_uri", f"data:image/png;base64,{encoded}")
                except OSError:
                    pass
            resources.append({
                "id": record.id,
                "type": record.type,
                "title": str(metadata.get("title") or (path.name if path else record.id)),
                "filepath": record.filepath,
                "metadata": metadata,
                "downloads": [{
                    "id": record.id,
                    "type": record.type,
                    "url": f"/api/v1/artifacts/download/{record.id}",
                    "filename": path.name if path else record.id,
                    "exists": bool(path and path.exists()),
                }],
            })

        if not resources:
            return rows
        target = next((
            item for item in reversed(rows)
            if item.get("role") == "assistant"
            and str(item.get("agent_name") or "") in {
                "doc_gen", "resource_generator", "resource_generator_agent",
                "mindmap", "reading", "video", "audio",
            }
        ), None)
        if target is None:
            target = next((item for item in reversed(rows) if item.get("role") == "assistant"), None)
        if target is not None:
            target["resources"] = resources
    except Exception as exc:  # noqa: BLE001
        logger.warning("[chat] failed to recover history resources: %s", exc)
    return rows


@router.get("/realtime/{session_id}")
def get_realtime(session_id: str) -> Dict[str, Any]:
    store = get_session_store()
    session = store.get(session_id) or {}
    state = store.get_realtime_state(session_id)
    if not state:
        try:
            from backend.app.core.database import SessionLocal
            from backend.app.core.models import RealtimeStateRecord

            with SessionLocal() as db:
                row = db.get(RealtimeStateRecord, session_id)
                payload = dict(row.state_data or {}) if row else None
                if payload is not None:
                    payload["session_id"] = session_id
                    payload["user_id"] = str(session.get("user_id") or "")
                return {"state": payload}
        except Exception as exc:  # noqa: BLE001
            logger.warning("[chat] realtime DB fallback failed: %s", exc)
            return {"state": None}
    payload = _serialize_state(state)
    payload["session_id"] = session_id
    payload["user_id"] = str(session.get("user_id") or "")
    return {"state": payload}


@router.post("/clear")
def clear_session(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    session_id = str(payload.get("session_id", "")).strip()
    store = get_session_store()
    if store.clear(session_id):
        clear_buffer(session_id)
        return {"status": "cleared", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@router.get("/archive/{user_id}")
def get_chat_archive(user_id: str, limit: int = 100) -> Dict[str, Any]:
    """获取用户的聊天存档（跨会话全部记录），用于资源库「聊天存档」tab。"""
    try:
        from backend.app.repositories.chat_history_repo import get_chat_history_repo
        records = get_chat_history_repo().list_by_user(user_id, limit=limit)
        return {"records": records, "total": len(records)}
    except Exception:
        return {"records": [], "total": 0}


@router.post("/with-cov")
def chat_with_cov(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """CoV-Edu demo endpoint: five-axis hallucination and safety check."""
    from backend.app.services.cov_demo_service import CoVDemoRequest, CoVDemoService

    text = str(payload.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text_required")
    axes_raw = payload.get("axes")
    axes = [str(axis) for axis in axes_raw] if isinstance(axes_raw, list) else None
    request = CoVDemoRequest(
        text=text,
        ground_truth=str(payload.get("ground_truth", "")),
        axes=axes,
    )
    return CoVDemoService().run(request)


@router.get("/cov-demo-cases")
def cov_demo_cases() -> Dict[str, Any]:
    """Built-in CoV-Edu demo cases, one for each education-specific axis."""
    from backend.app.services.cov_demo_service import CoVDemoService

    cases = CoVDemoService().demo_cases()
    return {"cases": cases, "total": len(cases)}
