"""聊天历史持久化仓库 — 刷新不丢、跨会话可查。"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

from backend.app.core.database import SessionLocal
from backend.app.core.models import ChatHistoryRecord


class ChatHistoryRepository:
    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    def append(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        agent_name: str = "",
    ) -> Dict[str, Any]:
        """追加一条聊天记录到数据库。"""
        with self.session_factory() as db:
            row = ChatHistoryRecord(
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                agent_name=agent_name,
                created_at=time.time(),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return {
                "role": row.role,
                "content": row.content,
                "agent_name": row.agent_name,
            }

    def list_by_session(
        self, session_id: str, limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """按会话 ID 查询聊天历史（旧→新）。"""
        with self.session_factory() as db:
            rows = (
                db.query(ChatHistoryRecord)
                .filter(ChatHistoryRecord.session_id == session_id)
                .order_by(ChatHistoryRecord.created_at.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "agent_name": r.agent_name,
                }
                for r in rows
            ]

    def list_by_user(
        self, user_id: str, limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """按用户 ID 查询全部聊天历史（旧→新），用于聊天存档。"""
        with self.session_factory() as db:
            rows = (
                db.query(ChatHistoryRecord)
                .filter(ChatHistoryRecord.user_id == user_id)
                .order_by(ChatHistoryRecord.created_at.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "role": r.role,
                    "content": r.content,
                    "agent_name": r.agent_name,
                    "created_at": r.created_at,
                }
                for r in rows
            ]


_repo: ChatHistoryRepository | None = None


def get_chat_history_repo() -> ChatHistoryRepository:
    global _repo
    if _repo is None:
        _repo = ChatHistoryRepository()
    return _repo
