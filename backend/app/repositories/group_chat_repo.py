"""课程群聊消息仓库 — 持久化异步群聊（写入后学生/教师刷新即可见）。

room_id 约定: "{course}:{student_id}"，例如 "artificial_intelligence:demo-student-1"。
同一房间成员：学生本人、教师、系统 Agent。
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.app.core.database import SessionLocal
from backend.app.core.models import GroupChatMessageRecord

VALID_MESSAGE_TYPES = frozenset({
    "text",             # 普通消息（学生/教师）
    "teacher_message",  # 教师普通消息
    "agent_reply",      # Agent 回复
    "resource_card",    # 资源推荐卡片
    "path_card",        # 路径推荐卡片
    "system_notice",    # 系统通知
})


def build_room_id(course: str, student_id: str) -> str:
    return f"{course.strip()}:{student_id.strip()}"


def _row_to_dict(row: GroupChatMessageRecord) -> Dict[str, Any]:
    return {
        "id": row.id,
        "room_id": row.room_id,
        "sender_id": row.sender_id,
        "sender_name": row.sender_name,
        "sender_role": row.sender_role,
        "content": row.content,
        "message_type": row.message_type,
        "payload": dict(row.payload or {}),
        "created_at": row.created_at,
    }


class GroupChatRepository:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    def append(
        self,
        room_id: str,
        sender_id: str,
        sender_name: str,
        sender_role: str,
        content: str,
        message_type: str = "text",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if message_type not in VALID_MESSAGE_TYPES:
            message_type = "text"
        with self.session_factory() as db:
            row = GroupChatMessageRecord(
                id=f"gcm_{uuid.uuid4().hex[:12]}",
                room_id=room_id,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_role=sender_role,
                content=content,
                message_type=message_type,
                payload=dict(payload or {}),
                created_at=time.time(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return _row_to_dict(row)

    def list_by_room(
        self,
        room_id: str,
        limit: int = 200,
        after: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """按房间查询消息（旧→新）；after 用于增量拉取。"""
        with self.session_factory() as db:
            query = (
                db.query(GroupChatMessageRecord)
                .filter(GroupChatMessageRecord.room_id == room_id)
            )
            if after > 0:
                query = query.filter(GroupChatMessageRecord.created_at > after)
            rows = (
                query.order_by(GroupChatMessageRecord.created_at.asc())
                .limit(limit)
                .all()
            )
            return [_row_to_dict(r) for r in rows]

    def list_rooms_by_student(self, student_id: str) -> List[str]:
        """列出某学生参与的全部房间（教师端选择入口用）。"""
        with self.session_factory() as db:
            rows = (
                db.query(GroupChatMessageRecord.room_id)
                .filter(GroupChatMessageRecord.room_id.like(f"%:{student_id}"))
                .distinct()
                .all()
            )
            return [r[0] for r in rows]


_repo: GroupChatRepository | None = None


def get_group_chat_repo() -> GroupChatRepository:
    global _repo
    if _repo is None:
        _repo = GroupChatRepository()
    return _repo
