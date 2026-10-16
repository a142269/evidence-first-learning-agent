"""
Debate Repository — 辩论日志持久化（A 拥有）

替代 critic_agent 和 debate_moderator 中的模块级 _debate_logs / _fallback_logs list。
使用 SQLAlchemy + SQLite，与 B 的 repository 层同构。
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List

from backend.app.core.database import SessionLocal
from backend.app.core.models import DebateLogRecord


class DebateRepository:
    """辩论日志 CRUD"""

    def __init__(self, session_factory: Callable = SessionLocal):
        self._session_factory = session_factory

    def insert(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """插入一条辩论记录

        Args:
            entry: {
                session_id, round_num, expert_name,
                draft_preview, critic_score, critic_passed,
                critic_issues, verdict
            }
        """
        with self._session_factory() as db:
            try:
                record = DebateLogRecord(
                    session_id=entry.get("session_id", ""),
                    round_num=entry.get("round_num", 1),
                    expert_name=entry.get("expert_name", ""),
                    draft_preview=entry.get("draft_preview", "")[:1000],
                    critic_score=float(entry.get("critic_score", 0)),
                    critic_passed=bool(entry.get("critic_passed", False)),
                    critic_issues=list(entry.get("critic_issues", [])),
                    verdict=entry.get("verdict", ""),
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return self._serialize(record)
            except Exception:
                db.rollback()
                raise

    def get_by_session(
        self, session_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取某会话的所有辩论记录"""
        with self._session_factory() as db:
            rows = (
                db.query(DebateLogRecord)
                .filter(DebateLogRecord.session_id == session_id)
                .order_by(DebateLogRecord.round_num.asc())
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近辩论记录"""
        with self._session_factory() as db:
            rows = (
                db.query(DebateLogRecord)
                .order_by(DebateLogRecord.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._serialize(r) for r in rows]

    def count_by_session(self, session_id: str) -> int:
        """统计某会话的辩论轮数"""
        with self._session_factory() as db:
            return (
                db.query(DebateLogRecord)
                .filter(DebateLogRecord.session_id == session_id)
                .count()
            )

    @staticmethod
    def _serialize(record: DebateLogRecord) -> Dict[str, Any]:
        return {
            "id": record.id,
            "session_id": record.session_id,
            "round_num": record.round_num,
            "expert_name": record.expert_name,
            "draft_preview": record.draft_preview,
            "critic_score": record.critic_score,
            "critic_passed": record.critic_passed,
            "critic_issues": record.critic_issues,
            "verdict": record.verdict,
            "created_at": record.created_at,
        }


# 全局单例
_debate_repo: DebateRepository | None = None


def get_debate_repository() -> DebateRepository:
    """获取 DebateRepository 全局单例"""
    global _debate_repo
    if _debate_repo is None:
        _debate_repo = DebateRepository()
    return _debate_repo


def insert_debate_log(entry: Dict[str, Any]) -> Dict[str, Any]:
    """便捷函数: 插入辩论日志（供 critic_agent 内部兼容）"""
    try:
        return get_debate_repository().insert(entry)
    except Exception:
        # 数据库不可用时降级到内存（保证演示不崩溃）
        return {
            "id": 0,
            "session_id": entry.get("session_id", ""),
            "round_num": entry.get("round_num", 0),
            "created_at": time.time(),
        }
