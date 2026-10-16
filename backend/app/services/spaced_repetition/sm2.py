"""
SM-2 spaced repetition algorithm - Wozniak 1990

quality 0-5 updates easiness/interval/repetitions.
Persistence via state_repository (SQLite), falls back to in-memory.
"""
from __future__ import annotations
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SM2:
    def __init__(
        self,
        initial_easiness: float = 2.5,
        min_easiness: float = 1.3,
        repository=None,
    ):
        self.initial_easiness = initial_easiness
        self.min_easiness = min_easiness
        self.repository = repository
        self._schedules: Dict[tuple, dict] = {}
        self._restored_users: set[str] = set()

    def _ensure_user_loaded(self, user_id: str) -> None:
        """Hydrate one learner's schedules before serving in-memory reads."""
        normalized_user_id = str(user_id)
        if self.repository is None or normalized_user_id in self._restored_users:
            return
        self.restore_user(normalized_user_id)

    def _get_state(self, user_id: str, item_id: str) -> dict:
        self._ensure_user_loaded(user_id)
        key = (str(user_id), str(item_id))
        if key not in self._schedules:
            self._schedules[key] = {
                "easiness": self.initial_easiness, "interval": 1,
                "repetitions": 0, "next_review_at": time.time(),
                "last_review_at": 0, "history": [],
            }
        return self._schedules[key]

    def review(self, user_id: str, item_id: str, quality: int) -> Dict[str, Any]:
        quality = max(0, min(5, quality))
        state = self._get_state(user_id, item_id)
        now = time.time()
        state["last_review_at"] = now

        if quality < 3:
            state["repetitions"] = 0
            state["interval"] = 1
        else:
            ef = state["easiness"]
            ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            state["easiness"] = max(self.min_easiness, ef)
            reps = state["repetitions"] + 1
            state["repetitions"] = reps
            if reps == 1:
                state["interval"] = 1
            elif reps == 2:
                state["interval"] = 6
            else:
                state["interval"] = round(state["interval"] * state["easiness"])

        state["next_review_at"] = (
            now if quality < 3 else now + state["interval"] * 86400
        )
        state["history"].append({
            "quality": quality, "interval": state["interval"],
            "easiness": round(state["easiness"], 4), "timestamp": now,
        })
        if self.repository is not None:
            self.repository.save_sm2_state(user_id, item_id, state)
        return dict(state)

    def get_schedule(self, user_id: str, item_id: str) -> Optional[Dict]:
        self._ensure_user_loaded(user_id)
        key = (str(user_id), str(item_id))
        return dict(self._schedules[key]) if key in self._schedules else None

    def due_items(self, user_id: str) -> List[Dict]:
        self._ensure_user_loaded(user_id)
        now = time.time()
        prefix = str(user_id)
        due = []
        for (uid, iid), state in self._schedules.items():
            if uid == prefix and state["next_review_at"] <= now:
                due.append({"item_id": iid, **dict(state)})
        return sorted(due, key=lambda x: x["next_review_at"])

    def daily_review_list(self, user_id: str) -> List[str]:
        return [item["item_id"] for item in self.due_items(user_id)]

    def stats(self, user_id: str) -> Dict[str, Any]:
        self._ensure_user_loaded(user_id)
        prefix = str(user_id)
        items = [(iid, s) for (uid, iid), s in self._schedules.items() if uid == prefix]
        today = self.daily_review_list(user_id)
        return {
            "user_id": user_id, "total_items": len(items),
            "due_today": len(today),
            "average_easiness": round(
                sum(s["easiness"] for _, s in items) / max(len(items), 1), 2),
            "due_item_ids": today,
        }

    def add_to_review_queue(self, user_id: str, item_id: str) -> None:
        self.review(user_id, item_id, quality=0)

    def save_to_db(self, user_id: str, item_id: str) -> None:
        try:
            from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo
            state = self.get_schedule(user_id, item_id)
            if state:
                get_state_repo().save_sm2_state(user_id, item_id, state)
        except Exception:
            pass

    def load_from_db(self, user_id: str) -> int:
        return self.restore_user(user_id)

    def restore_user(self, user_id: str) -> int:
        """Restore every persisted schedule for a learner."""
        if self.repository is None:
            return 0
        normalized_user_id = str(user_id)
        try:
            schedules = self.repository.load_all_sm2(normalized_user_id)
            for item_id, state in schedules.items():
                self._schedules[(normalized_user_id, str(item_id))] = {
                    "easiness": state.get("easiness", self.initial_easiness),
                    "interval": state.get("interval", 1),
                    "repetitions": state.get("repetitions", 0),
                    "next_review_at": state.get("next_review_at", 0),
                    "last_review_at": 0,
                    "history": [],
                }
            # Keep empty users retryable so schedules seeded later in the same
            # process become visible without requiring another restart.
            if schedules:
                self._restored_users.add(normalized_user_id)
            return len(schedules)
        except Exception as exc:
            logger.warning("[SM2] state restore failed: %s", exc)
            return 0


_sm2: Optional[SM2] = None

def get_sm2() -> SM2:
    global _sm2
    if _sm2 is None:
        from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo

        _sm2 = SM2(repository=get_state_repo())
    return _sm2
