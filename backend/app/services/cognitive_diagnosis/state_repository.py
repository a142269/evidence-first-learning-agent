"""
B 模块状态持久化 Repository — SM-2 / BKT / DINA 落库

将当前内存 dict 中的 SM-2 schedules / BKT states / DINA results
持久化到 SQLite 表，重启不丢数据。容错设计：表不存在时降级为内存模式。
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from backend.app.core.database import SessionLocal
from backend.app.core.models import Sm2ScheduleRecord, BktStateRecord, DinaStateRecord

logger = logging.getLogger(__name__)

_db_available = True


class StateRepository:
    """统一持久化：SM-2 / BKT / DINA"""

    def __init__(self, session_factory: Callable = SessionLocal):
        self.session_factory = session_factory

    # ── SM-2 ────────────────────────────────────────────
    def save_sm2_state(self, user_id: str, item_id: str, state: dict) -> None:
        try:
            with self.session_factory() as db:
                row = (
                    db.query(Sm2ScheduleRecord)
                    .filter(Sm2ScheduleRecord.user_id == user_id)
                    .filter(Sm2ScheduleRecord.item_id == item_id)
                    .one_or_none()
                )
                if row is None:
                    row = Sm2ScheduleRecord(user_id=user_id, item_id=item_id)
                    db.add(row)
                row.repetitions = state.get("repetitions", 0)
                row.interval_days = state.get("interval", 1)
                row.easiness = state.get("easiness", 2.5)
                row.due_at = state.get("next_review_at", 0)
                db.commit()
        except Exception as exc:
            logger.warning(f"[StateRepo] SM-2 落库失败: {exc}")

    def load_sm2_state(self, user_id: str, item_id: str) -> dict | None:
        try:
            with self.session_factory() as db:
                row = (
                    db.query(Sm2ScheduleRecord)
                    .filter(Sm2ScheduleRecord.user_id == user_id)
                    .filter(Sm2ScheduleRecord.item_id == item_id)
                    .one_or_none()
                )
                if row:
                    return {
                        "repetitions": row.repetitions,
                        "interval": row.interval_days,
                        "easiness": row.easiness,
                        "next_review_at": row.due_at,
                    }
        except Exception as exc:
            logger.warning(f"[StateRepo] SM-2 读失败: {exc}")
        return None

    def load_all_sm2(self, user_id: str) -> dict[str, dict]:
        """Load every SM-2 schedule owned by a learner."""
        result: dict[str, dict] = {}
        try:
            with self.session_factory() as db:
                rows = (
                    db.query(Sm2ScheduleRecord)
                    .filter(Sm2ScheduleRecord.user_id == user_id)
                    .all()
                )
                for row in rows:
                    result[row.item_id] = {
                        "repetitions": row.repetitions,
                        "interval": row.interval_days,
                        "easiness": row.easiness,
                        "next_review_at": row.due_at,
                    }
        except Exception as exc:
            logger.warning("[StateRepo] SM-2 batch load failed: %s", exc)
        return result

    # ── BKT ─────────────────────────────────────────────
    def save_bkt_state(self, user_id: str, kp_id: str, state: dict) -> None:
        try:
            with self.session_factory() as db:
                row = (
                    db.query(BktStateRecord)
                    .filter(BktStateRecord.user_id == user_id)
                    .filter(BktStateRecord.knowledge_point_id == kp_id)
                    .one_or_none()
                )
                if row is None:
                    row = BktStateRecord(user_id=user_id, knowledge_point_id=kp_id)
                    db.add(row)
                row.p_learned = state.get("p_learned", 0.2)
                row.p_transit = state.get("p_transit", 0.1)
                row.p_slip = state.get("p_slip", 0.1)
                row.p_guess = state.get("p_guess", 0.2)
                row.history = state.get("history", [])
                db.commit()
        except Exception as exc:
            logger.warning(f"[StateRepo] BKT 落库失败: {exc}")

    def load_bkt_state(self, user_id: str, kp_id: str) -> dict | None:
        try:
            with self.session_factory() as db:
                row = (
                    db.query(BktStateRecord)
                    .filter(BktStateRecord.user_id == user_id)
                    .filter(BktStateRecord.knowledge_point_id == kp_id)
                    .one_or_none()
                )
                if row:
                    return {
                        "p_learned": row.p_learned,
                        "p_transit": row.p_transit,
                        "p_slip": row.p_slip,
                        "p_guess": row.p_guess,
                        "history": row.history or [],
                    }
        except Exception as exc:
            logger.warning(f"[StateRepo] BKT 读失败: {exc}")
        return None

    def load_all_bkt(self, user_id: str) -> dict[str, dict]:
        """加载某用户的所有 BKT 状态（供重启恢复）"""
        result = {}
        try:
            with self.session_factory() as db:
                rows = (
                    db.query(BktStateRecord)
                    .filter(BktStateRecord.user_id == user_id)
                    .all()
                )
                for row in rows:
                    result[row.knowledge_point_id] = {
                        "p_learned": row.p_learned,
                        "p_transit": row.p_transit,
                        "p_slip": row.p_slip,
                        "p_guess": row.p_guess,
                        "history": row.history or [],
                    }
        except Exception as exc:
            logger.warning(f"[StateRepo] BKT 批量加载失败: {exc}")
        return result

    # ── DINA ────────────────────────────────────────────
    def save_dina_state(self, user_id: str, kp_id: str,
                        mastery: float, slip: float, guess: float) -> None:
        try:
            with self.session_factory() as db:
                row = (
                    db.query(DinaStateRecord)
                    .filter(DinaStateRecord.user_id == user_id)
                    .filter(DinaStateRecord.knowledge_point_id == kp_id)
                    .one_or_none()
                )
                if row is None:
                    row = DinaStateRecord(user_id=user_id, knowledge_point_id=kp_id)
                    db.add(row)
                row.mastery = mastery
                row.slip = slip
                row.guess = guess
                row.evidence = {"last_updated": __import__("time").time()}
                db.commit()
        except Exception as exc:
            logger.warning(f"[StateRepo] DINA 落库失败: {exc}")

    def load_dina_snapshot(self, user_id: str) -> dict[str, dict]:
        """加载某用户的所有 DINA 诊断结果"""
        result = {}
        try:
            with self.session_factory() as db:
                rows = (
                    db.query(DinaStateRecord)
                    .filter(DinaStateRecord.user_id == user_id)
                    .all()
                )
                for row in rows:
                    result[row.knowledge_point_id] = {
                        "mastery": row.mastery,
                        "slip": row.slip,
                        "guess": row.guess,
                    }
        except Exception as exc:
            logger.warning(f"[StateRepo] DINA 加载失败: {exc}")
        return result


# 模块单例
_state_repo: StateRepository | None = None


def get_state_repo() -> StateRepository:
    global _state_repo
    if _state_repo is None:
        _state_repo = StateRepository()
    return _state_repo
