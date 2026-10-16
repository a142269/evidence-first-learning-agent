"""Authenticated APIs for the isolated student mobile client."""
from __future__ import annotations

import asyncio
from collections import defaultdict
import contextlib
import logging
import re
from typing import Any, Literal
import uuid

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field

from backend.app.api.v1.auth import _get_session, _parse_bearer_token
from backend.app.repositories.mobile_chat_repo import (
    MOBILE_AGENT_MEMBERS,
    VALID_MOBILE_MESSAGE_TYPES,
    get_mobile_chat_repo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mobile", tags=["mobile"])

_AGENT_MENTION_TOKENS = {
    "agent-planner": ("@智狐", "@规划伙伴"),
    "agent-content": ("@阿匠", "@资源伙伴"),
    "ai-assistant": ("@ai", "@智灵", "@讲解伙伴"),
    "agent-quiz": ("@小龙", "@练习伙伴"),
    "agent-evaluation": ("@团团", "@评估伙伴"),
    "agent-safety": ("@球球", "@守护伙伴"),
}
_AGENT_DISPLAY_NAMES = {
    user_id: display_name for user_id, display_name, _role in MOBILE_AGENT_MEMBERS
}
_AGENT_PIPELINE_TARGETS = {
    "agent-planner": "planner",
    "agent-content": "content",
    "ai-assistant": "tutor",
    "agent-quiz": "quiz",
    "agent-evaluation": "evaluation",
    "agent-safety": "safety",
}
_AGENT_CAPABILITIES = {
    "agent-planner": "梳理学习目标和下一步安排",
    "agent-content": "查找、整理和制作学习资料",
    "ai-assistant": "讲解知识点和解答课程问题",
    "agent-quiz": "出题、练习和巩固知识",
    "agent-evaluation": "分析作答并给出改进建议",
    "agent-safety": "检查学习内容并提供安全提醒",
}
_MOBILE_REPLY_LIMIT = 2000


def _requested_agent(content: str, mentions: list[str]) -> tuple[str, str] | None:
    mention_ids = {str(value).lower() for value in mentions}
    lowered = content.lower()
    if "ai" in mention_ids:
        return "ai-assistant", _AGENT_DISPLAY_NAMES["ai-assistant"]
    for user_id, tokens in _AGENT_MENTION_TOKENS.items():
        if user_id.lower() in mention_ids or any(token.lower() in lowered for token in tokens):
            return user_id, _AGENT_DISPLAY_NAMES[user_id]
    return None


def _requested_agent_for_room(
    room: dict[str, Any], content: str, mentions: list[str],
) -> tuple[str, str] | None:
    """Server-side DM routing prevents clients from choosing another Agent."""
    if room.get("room_type") == "direct":
        peer = room.get("peer") or {}
        if peer.get("role") == "agent" and peer.get("user_id") in _AGENT_DISPLAY_NAMES:
            peer_id = str(peer["user_id"])
            return peer_id, _AGENT_DISPLAY_NAMES[peer_id]
        return None
    return _requested_agent(content, mentions)


def _student_question(content: str) -> str:
    """Remove routing mentions before the current message reaches an Agent."""
    result = content
    for tokens in _AGENT_MENTION_TOKENS.values():
        for token in tokens:
            result = re.sub(re.escape(token), "", result, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", result).strip(" ，,。.!！?？:：")


def _is_short_greeting(content: str) -> bool:
    normalized = re.sub(r"[\s，,。.!！?？~～]+", "", content).lower()
    return normalized in {
        "你好", "您好", "你们好", "大家好", "嗨", "哈喽", "在吗",
        "hi", "hello", "hey",
    }


def _greeting_reply(agent_id: str, agent_name: str) -> str:
    nickname = agent_name.split(" · ", maxsplit=1)[0]
    capability = _AGENT_CAPABILITIES.get(agent_id, "解决学习问题")
    return f"你好！我是{nickname}，可以帮你{capability}。你现在想解决什么问题？"


def _plain_chat_text(raw: str) -> str:
    """Turn pipeline Markdown/HTML into safe, readable plain chat text."""
    text = str(raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"```[^\n]*\n?", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)

    lines: list[str] = []
    for line in text.split("\n"):
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)
        line = re.sub(r"^\s*>+\s?", "", line)
        if re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*", line):
            continue
        if line.count("|") >= 2:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            line = " · ".join(cell for cell in cells if cell)
        line = re.sub(r"^\s*[-+*]\s+", "• ", line)
        lines.append(line.rstrip())

    text = "\n".join(lines)
    text = re.sub(r"(\*\*|__)(.*?)\1", r"\2", text, flags=re.DOTALL)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > _MOBILE_REPLY_LIMIT:
        text = text[:_MOBILE_REPLY_LIMIT].rstrip() + "…"
    return text


def _mobile_agent_prompt(question: str) -> str:
    return (
        "请只回答学生下面这条当前消息，不要延伸成与问题无关的完整方案。"
        "使用自然、简洁的中文聊天纯文本，优先直接回答，通常不超过300字；"
        "不要使用Markdown标题、表格、粗体标记或代码围栏。\n"
        f"学生当前消息：{question}"
    )


def _session(authorization: str | None):
    return _get_session(_parse_bearer_token(authorization))


def _http_session(authorization: str | None = Header(default=None)):
    return _session(authorization)


def _membership_or_403(room_id: str, user_id: str):
    try:
        return get_mobile_chat_repo().require_member(room_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


class MobileMessageCreate(BaseModel):
    content: str = Field(default="", max_length=4000)
    message_type: Literal["text", "resource_card"] = "text"
    client_message_id: str = Field(min_length=1, max_length=128)
    reply_to_id: str | None = None
    mentions: list[str] = Field(default_factory=list, max_length=50)
    payload: dict[str, Any] = Field(default_factory=dict)


class MobileReadCreate(BaseModel):
    last_message_id: str = Field(min_length=1, max_length=64)


class MobileMistakeCreate(BaseModel):
    kp_id: str = ""
    question: str = Field(min_length=1, max_length=8000)
    student_answer: str = Field(default="", max_length=8000)
    correct_answer: str = Field(default="", max_length=8000)
    error_type: str = "unknown"
    course: str = ""


class _SocketHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if sockets is not None:
                sockets.discard(websocket)
                if not sockets:
                    self._connections.pop(user_id, None)

    async def room_event(self, room_id: str, event: dict[str, Any]) -> None:
        targets = get_mobile_chat_repo().member_ids(room_id)
        async with self._lock:
            sockets = [ws for uid in targets for ws in self._connections.get(uid, set())]
        stale: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(event)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    for user_sockets in self._connections.values():
                        user_sockets.discard(websocket)


_socket_hub = _SocketHub()
_background_tasks: set[asyncio.Task] = set()


def _start_background(coro) -> None:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _run_ai_reply(
    room_id: str,
    course: str,
    user_id: str,
    content: str,
    agent_id: str,
    agent_name: str,
) -> None:
    """Reuse the existing pipeline without writing into legacy web chat rooms."""
    repo = get_mobile_chat_repo()
    try:
        question = _student_question(content) or content.strip()
        if _is_short_greeting(question):
            reply = _greeting_reply(agent_id, agent_name)
        else:
            from backend.app.api.v1.chat import _bind_session_user, _process_turn
            from backend.app.api.v1.chat_pipeline import get_session_store

            # Each mobile question gets a fresh pipeline session. This keeps another
            # student's or an earlier room turn from steering the current answer.
            session_key = f"mobile:{room_id}:{user_id}:{uuid.uuid4().hex}"
            sid, chat_session = get_session_store().get_or_create(session_key)
            _bind_session_user(chat_session, {"user_id": user_id})
            result = await _process_turn(
                sid,
                chat_session,
                _mobile_agent_prompt(question),
                course,
                target_agent=_AGENT_PIPELINE_TARGETS.get(agent_id),
            )
            reply = _plain_chat_text(str(result.get("content") or ""))
        if not reply:
            error = "empty_ai_reply"
            raise RuntimeError(error)
        message = repo.append_message(
            room_id=room_id,
            sender_id=agent_id,
            sender_name=agent_name,
            sender_role="agent",
            content=reply,
            message_type="agent_reply",
            client_message_id=f"ai-{uuid.uuid4().hex}",
            mentions=[user_id],
            payload={"source": "existing_chat_pipeline"},
        )
    except Exception as exc:
        logger.exception("[mobile] AI group reply failed: %s", exc)
        message = repo.append_message(
            room_id=room_id,
            sender_id="system",
            sender_name="系统通知",
            sender_role="system",
            content="学习助理暂时没有完成回答，请稍后重新 @AI。",
            message_type="system_notice",
            client_message_id=f"ai-error-{uuid.uuid4().hex}",
            mentions=[user_id],
            payload={"retryable": True},
        )
    await _socket_hub.room_event(room_id, {"type": "message.created", "message": message})


@router.get("/rooms")
def list_mobile_rooms(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    session = _http_session(authorization)
    repo = get_mobile_chat_repo()
    repo.ensure_defaults()
    if session.role == "student":
        repo.ensure_student_direct_rooms(session.account, session.display_name)
    return {"rooms": repo.list_rooms(session.account)}


@router.get("/rooms/{room_id}/members")
def list_mobile_members(
    room_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    try:
        members = get_mobile_chat_repo().list_members(room_id, session.account)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"room_id": room_id, "members": members, "total": len(members)}


@router.get("/rooms/{room_id}/messages")
def list_mobile_messages(
    room_id: str,
    cursor: str = Query(default=""),
    limit: int = Query(default=30, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    try:
        page = get_mobile_chat_repo().list_messages(
            room_id, session.account, cursor=cursor, limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"room_id": room_id, **page}


@router.post("/rooms/{room_id}/messages")
async def create_mobile_message(
    room_id: str,
    payload: MobileMessageCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    repo = get_mobile_chat_repo()
    _membership_or_403(room_id, session.account)
    try:
        room = repo.room_context(room_id, session.account)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    content = payload.content.strip()
    if payload.message_type == "text" and not content:
        raise HTTPException(status_code=400, detail="message_content_required")
    if payload.message_type not in VALID_MOBILE_MESSAGE_TYPES:
        raise HTTPException(status_code=400, detail="mobile_message_type_invalid")

    card_payload = dict(payload.payload)
    if payload.message_type == "resource_card":
        resource_id = str(card_payload.get("resource_id") or "").strip()
        from backend.app.api.v1.resources import _visible_to_student, get_resource_dict

        resource = get_resource_dict(resource_id)
        if resource is None or not _visible_to_student(resource, session.account):
            raise HTTPException(status_code=404, detail="resource_not_available")
        card_payload = {
            "resource_id": resource_id,
            "title": resource.get("title", "学习资源"),
            "resource_type": resource.get("type", "document"),
        }
        content = content or f"分享资源：{card_payload['title']}"

    try:
        message = repo.append_message(
            room_id=room_id,
            sender_id=session.account,
            sender_name=session.display_name,
            sender_role=session.role,
            content=content,
            message_type=payload.message_type,
            client_message_id=payload.client_message_id,
            reply_to_id=payload.reply_to_id,
            mentions=[str(value) for value in payload.mentions],
            payload=card_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await _socket_hub.room_event(room_id, {"type": "message.created", "message": message})
    requested_agent = _requested_agent_for_room(room, content, payload.mentions)
    if requested_agent:
        await _socket_hub.room_event(
            room_id,
            {
                "type": "agent.typing",
                "room_id": room_id,
                "agent_id": requested_agent[0],
                "agent_name": requested_agent[1],
            },
        )
        _start_background(
            _run_ai_reply(
                room_id,
                str(room.get("course") or "artificial_intelligence"),
                session.account,
                content,
                requested_agent[0],
                requested_agent[1],
            )
        )
    return {"status": "ok", "message": message}


@router.post("/rooms/{room_id}/read")
async def mark_mobile_room_read(
    room_id: str,
    payload: MobileReadCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    try:
        result = get_mobile_chat_repo().mark_read(
            room_id, session.account, payload.last_message_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _socket_hub.room_event(
        room_id,
        {"type": "room.read", "room_id": room_id, "user_id": session.account, **result},
    )
    return {"status": "ok", **result}


@router.websocket("/ws")
async def mobile_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    user_id = ""
    try:
        auth_frame = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        if auth_frame.get("type") != "auth":
            await websocket.close(code=4401, reason="auth_frame_required")
            return
        session = _get_session(str(auth_frame.get("token") or ""))
        user_id = session.account
        await _socket_hub.connect(user_id, websocket)
        await websocket.send_json({"type": "auth.ok", "user": {
            "account": session.account,
            "display_name": session.display_name,
            "role": session.role,
        }})
        while True:
            frame = await websocket.receive_json()
            if frame.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    except Exception as exc:
        logger.info("[mobile/ws] connection closed: %s", exc)
        with contextlib.suppress(Exception):
            await websocket.close(code=4401, reason="authentication_failed")
    finally:
        if user_id:
            await _socket_hub.disconnect(user_id, websocket)


def _visible_mobile_resources(user_id: str) -> list[dict[str, Any]]:
    from backend.app.api.v1.resources import _resources, _visible_to_student

    return [record for record in _resources.values() if _visible_to_student(record, user_id)]


@router.get("/resources")
def list_mobile_resources(
    q: str = Query(default=""),
    course: str = Query(default=""),
    resource_type: str = Query(default=""),
    cursor: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    items = _visible_mobile_resources(session.account)
    if course:
        items = [
            item
            for item in items
            if str((item.get("metadata") or {}).get("course") or "") == course
        ]
    if resource_type:
        items = [item for item in items if item.get("type") == resource_type]
    if q.strip():
        needle = q.strip().lower()
        items = [item for item in items if needle in " ".join([
            str(item.get("title") or ""), str(item.get("content") or ""),
            " ".join(str(tag) for tag in item.get("tags") or []),
        ]).lower()]
    items.sort(key=lambda item: (item.get("created_at", 0), item.get("id", "")), reverse=True)
    start = 0
    if cursor:
        indices = [index for index, item in enumerate(items) if item.get("id") == cursor]
        if not indices:
            raise HTTPException(status_code=400, detail="invalid_resource_cursor")
        start = indices[0] + 1
    page = items[start:start + limit]
    has_more = start + limit < len(items)
    return {
        "items": page,
        "next_cursor": page[-1]["id"] if has_more and page else None,
        "has_more": has_more,
        "total": len(items),
    }


@router.get("/resources/{resource_id}")
def get_mobile_resource(
    resource_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    from backend.app.api.v1.resources import _visible_to_student, get_resource_dict

    resource = get_resource_dict(resource_id)
    if resource is None or not _visible_to_student(resource, session.account):
        raise HTTPException(status_code=404, detail="resource_not_available")
    return {"resource": resource}


@router.get("/resources/{resource_id}/download")
def download_mobile_resource(
    resource_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
):
    session = _http_session(authorization)
    from backend.app.api.v1.resources import (
        _visible_to_student,
        download_course_resource,
        get_resource_dict,
    )

    resource = get_resource_dict(resource_id)
    if resource is None or not _visible_to_student(resource, session.account):
        raise HTTPException(status_code=404, detail="resource_not_available")
    return download_course_resource(resource_id, request, user_id=session.account)


def _owned_mistake(mistake_id: str, user_id: str) -> dict[str, Any]:
    from backend.app.api.v1.mistakes import _find_mistake

    record = _find_mistake(mistake_id)
    if record is None or record.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="mistake_not_found")
    return record


@router.get("/mistakes")
def list_mobile_mistakes(
    q: str = Query(default=""),
    course: str = Query(default=""),
    status: Literal["", "open", "resolved"] = Query(default=""),
    category: str = Query(default=""),
    cursor: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    from backend.app.api.v1.mistakes import _filter_records_by_course, _gather_user_records

    items = _filter_records_by_course(_gather_user_records(session.account), course)
    if category:
        items = [item for item in items if item.get("error_type") == category]
    if status == "open":
        items = [item for item in items if not item.get("resolved")]
    elif status == "resolved":
        items = [item for item in items if item.get("resolved")]
    if q.strip():
        needle = q.strip().lower()
        items = [item for item in items if needle in " ".join([
            str(item.get("question") or ""), str(item.get("kp_id") or ""),
            str(item.get("analysis") or ""),
        ]).lower()]
    start = 0
    if cursor:
        indices = [index for index, item in enumerate(items) if item.get("id") == cursor]
        if not indices:
            raise HTTPException(status_code=400, detail="invalid_mistake_cursor")
        start = indices[0] + 1
    page = items[start:start + limit]
    has_more = start + limit < len(items)
    return {
        "items": page,
        "next_cursor": page[-1]["id"] if has_more and page else None,
        "has_more": has_more,
        "total": len(items),
    }


@router.post("/mistakes")
def create_mobile_mistake(
    payload: MobileMistakeCreate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    from backend.app.api.v1.mistakes import record_mistake

    return record_mistake({**payload.model_dump(), "user_id": session.account})


@router.get("/mistakes/{mistake_id}")
def get_mobile_mistake(
    mistake_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    return {"mistake": _owned_mistake(mistake_id, session.account)}


@router.post("/mistakes/{mistake_id}/analyze")
def analyze_mobile_mistake(
    mistake_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    _owned_mistake(mistake_id, session.account)
    from backend.app.api.v1.mistakes import analyze_mistake
    return analyze_mistake(mistake_id)


@router.post("/mistakes/{mistake_id}/remediation")
def remediate_mobile_mistake(
    mistake_id: str,
    count: int = Query(default=3, ge=1, le=5),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    _owned_mistake(mistake_id, session.account)
    from backend.app.api.v1.mistakes import remediate_mistake
    return remediate_mistake(mistake_id, count=count)


@router.post("/mistakes/{mistake_id}/variants")
def variants_mobile_mistake(
    mistake_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    _owned_mistake(mistake_id, session.account)
    from backend.app.api.v1.mistakes import make_variants
    return make_variants(mistake_id)


@router.post("/mistakes/{mistake_id}/resolve")
def resolve_mobile_mistake(
    mistake_id: str, authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    session = _http_session(authorization)
    _owned_mistake(mistake_id, session.account)
    from backend.app.api.v1.mistakes import resolve_mistake
    return resolve_mistake(mistake_id)
