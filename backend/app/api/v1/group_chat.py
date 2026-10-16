"""课程群聊 API — 学生 / 教师 / AI Agent 共享的持久化异步群聊空间。

room_id = "{course}:{student_id}"，例如 "artificial_intelligence:demo-student-1"。
不做 WebSocket 实时推送；消息写入后，成员进入或刷新页面即可看到。
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from backend.app.repositories.group_chat_repo import (
    VALID_MESSAGE_TYPES,
    get_group_chat_repo,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/group-chat", tags=["group-chat"])

_VALID_ROLES = frozenset({"student", "teacher", "admin", "agent", "system"})


@router.get("/{room_id}/messages")
def list_messages(
    room_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    after: float = Query(default=0.0),
) -> Dict[str, Any]:
    """拉取房间消息（旧→新）；after 传上次最新消息的 created_at 可增量拉取。"""
    room_id = room_id.strip()
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id_required")
    messages = get_group_chat_repo().list_by_room(room_id, limit=limit, after=after)
    return {"room_id": room_id, "messages": messages, "total": len(messages)}


@router.post("/{room_id}/messages")
def post_message(room_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """向房间写入一条消息（学生普通消息 / 教师消息 / 系统通知等）。

    注意：本端点只写消息、不触发 LLM。学生发起 AI 问答仍走 /chat/stream
    （携带 room_id 后，问答双方消息会自动落到同一房间）。
    """
    room_id = room_id.strip()
    if not room_id:
        raise HTTPException(status_code=400, detail="room_id_required")

    content = str(payload.get("content", "")).strip()
    message_type = str(payload.get("message_type", "text")).strip() or "text"
    if not content and message_type == "text":
        raise HTTPException(status_code=400, detail="content_required")
    if message_type not in VALID_MESSAGE_TYPES:
        raise HTTPException(status_code=400, detail="invalid_message_type")

    sender_role = str(payload.get("sender_role", "student")).strip() or "student"
    if sender_role == "counselor":  # 旧角色兼容
        sender_role = "teacher"
    if sender_role not in _VALID_ROLES:
        raise HTTPException(status_code=400, detail="invalid_sender_role")

    message = get_group_chat_repo().append(
        room_id=room_id,
        sender_id=str(payload.get("sender_id", "")).strip(),
        sender_name=str(payload.get("sender_name", "")).strip(),
        sender_role=sender_role,
        content=content,
        message_type=message_type,
        payload=dict(payload.get("payload") or {}),
    )
    return {"status": "ok", "message": message}
