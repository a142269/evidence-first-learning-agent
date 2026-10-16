"""
SessionStore - 替代原 chat.py 模块级 _sessions dict

设计:
- 单一职责: 仅管理 in-memory session lifecycle
- 内置过期清理 (访问时惰性 evict)
- 可注入到 Pipeline 便于测试 (避免全局状态污染)

未来扩展:
- 替换为 Redis 后端 (实现同接口)
- 加 Prometheus 指标
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple


MAX_HISTORY_TURNS_DEFAULT = 20
MAX_SESSION_AGE_DEFAULT = 7200  # seconds


class SessionStore:
    """In-memory session 存储

    数据结构:
        sessions[sid] = {
            "history": list[{role, content}],
            "profile": dict,
            "created_at": float,
            "user_id": str,
            "role_view": str,
        }
        realtime_states[sid] = RealtimeLearningState
    """

    def __init__(
        self,
        max_history_turns: int = MAX_HISTORY_TURNS_DEFAULT,
        max_session_age: float = MAX_SESSION_AGE_DEFAULT,
    ):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._realtime_states: Dict[str, Any] = {}
        self.max_history_turns = max_history_turns
        self.max_session_age = max_session_age

    # ----------------------------------------------------------------
    # Session lifecycle
    # ----------------------------------------------------------------
    def get_or_create(
        self, session_id: str = "",
    ) -> Tuple[str, Dict[str, Any]]:
        """获取或新建 session

        新会话创建时自动从数据库加载已有画像，保证跨会话画像延续。

        Returns:
            (sid, session_dict)
        """
        sid = session_id.strip() if session_id else self._new_id()
        self._evict_expired()

        if sid not in self._sessions:
            profile = self._load_profile_from_db(sid)
            self._sessions[sid] = {
                "history": [],
                "profile": profile,
                "created_at": time.time(),
                "user_id": sid,
                "session_id": sid,
                "role_view": "student",
            }
        return sid, self._sessions[sid]

    @staticmethod
    def _load_profile_from_db(user_id: str) -> Dict[str, Any]:
        """从数据库加载学生画像，失败时返回空 dict（安全降级）。

        这保证了「随学随新」的跨会话延续：
        - 上一次对话中抽取的画像已经持久化到 DB
        - 新会话创建时从 DB 加载，不会丢失历史画像
        - 前端 ProfileView 读 DB 和聊天 session 里的画像保持一致
        """
        try:
            from backend.app.repositories.profile_repo import ProfileRepository
            repo = ProfileRepository()
            return repo.get(user_id)
        except Exception:
            return {}

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def clear(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions.pop(session_id, None)
            self._realtime_states.pop(session_id, None)
            return True
        return False

    def _evict_expired(self) -> int:
        now = time.time()
        expired = [
            k for k, v in self._sessions.items()
            if now - v.get("created_at", 0) > self.max_session_age
        ]
        for k in expired:
            self._sessions.pop(k, None)
            self._realtime_states.pop(k, None)
        return len(expired)

    @staticmethod
    def _new_id() -> str:
        return f"sess_{uuid.uuid4().hex[:12]}"

    # ----------------------------------------------------------------
    # History
    # ----------------------------------------------------------------
    def append_history(
        self, session: Dict[str, Any], role: str, content: str,
        agent_name: str = "", resources: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """追加历史并裁剪到 max_history_turns

        Args:
            agent_name: 当 role="assistant" 时，记录主导 Agent 名称，
                        前端刷新后可据此恢复正确头像。

        同时写入数据库，保证刷新/重启后聊天记录不丢。
        """
        history = session.setdefault("history", [])
        entry: Dict[str, Any] = {"role": role, "content": content}
        if agent_name:
            entry["agent_name"] = agent_name
        if resources:
            entry["resources"] = list(resources)
        history.append(entry)
        cap = self.max_history_turns * 2
        if len(history) > cap:
            session["history"] = history[-cap:]
        # 持久化到数据库（安全降级）
        self._persist_history_to_db(session, role, content, agent_name)

    @staticmethod
    def _persist_history_to_db(
        session: Dict[str, Any], role: str, content: str, agent_name: str,
    ) -> None:
        """把聊天记录写入数据库，失败时安全降级。"""
        session_id = str(session.get("session_id", "") or session.get("user_id", "") or "")
        user_id = str(session.get("user_id", "") or "")
        if not session_id:
            return
        try:
            from backend.app.repositories.chat_history_repo import get_chat_history_repo
            get_chat_history_repo().append(
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                agent_name=agent_name,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "_persist_history_to_db failed: %s", e, exc_info=True,
            )

    # ----------------------------------------------------------------
    # Profile
    # ----------------------------------------------------------------
    def merge_profile(
        self, session: Dict[str, Any], updates: Dict[str, Any],
    ) -> None:
        """深度合并画像更新 (一级 dict 合并, 其余覆盖)

        同时同步到数据库，保证「随学随新」持久化：
        - 内存 session 更新 → 实时响应当前会话
        - DB upsert + 快照 → 跨会话延续 + 历史追溯
        """
        profile = session.setdefault("profile", {})
        for key, value in (updates or {}).items():
            if isinstance(value, dict) and isinstance(profile.get(key), dict):
                profile[key].update(value)
            else:
                profile[key] = value
        # 同步到数据库（source=chat 标记来源为对话式抽取）
        self._persist_profile_to_db(session)

    @staticmethod
    def _persist_profile_to_db(session: Dict[str, Any]) -> None:
        """把当前 session 画像写入数据库，失败时安全降级。"""
        user_id = session.get("user_id", "")
        profile = session.get("profile", {})
        if not user_id or not profile:
            return
        try:
            from backend.app.repositories.profile_repo import ProfileRepository
            repo = ProfileRepository()
            repo.upsert(user_id, profile, source="chat")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "_persist_profile_to_db failed: %s", e, exc_info=True,
            )
    # ----------------------------------------------------------------
    def set_realtime_state(self, sid: str, state: Any) -> None:
        self._realtime_states[sid] = state

    def get_realtime_state(self, sid: str) -> Optional[Any]:
        return self._realtime_states.get(sid)

    # ----------------------------------------------------------------
    # Inspection
    # ----------------------------------------------------------------
    def size(self) -> int:
        return len(self._sessions)


# ================================================================
# 全局单例 (向后兼容旧 chat.py 模块级状态)
# ================================================================
_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """获取全局 SessionStore 单例"""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store


def reset_session_store() -> None:
    """测试用: 重置全局单例"""
    global _store
    _store = None
