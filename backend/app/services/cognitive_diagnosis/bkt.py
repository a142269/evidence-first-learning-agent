"""
BKT 贝叶斯知识追踪 —— 答辩创新点 #3

实现 Corbett & Anderson (1995) 的 4 参数 BKT 模型。
每次做题后增量更新 P(L)：学生掌握该知识点的概率。

4 个参数：
  - P(L0): 初始掌握概率（学生未学习时就已掌握的概率）
  - P(T):  学习转移概率（从未掌握到掌握的概率）
  - P(S):  失误概率 slip（掌握但答错）
  - P(G):  猜测概率 guess（未掌握但答对）

增量更新（每次答题后）：
  - 答对：P(L|correct) = P(L)*(1-P(S)) / [P(L)*(1-P(S)) + (1-P(L))*P(G)]
  - 答错：P(L|wrong)   = P(L)*P(S) / [P(L)*P(S) + (1-P(L))*(1-P(G))]
  - 然后加学习转移：P(L') = P(L|obs) + (1 - P(L|obs)) * P(T)
"""
from __future__ import annotations

import logging
import hashlib
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BKT:
    """4 参数 BKT 模型 (Corbett & Anderson, 1995)

    每个 (student_id, kp_id) 维护一个 BKT 状态。
    """

    def __init__(
        self,
        p_initial: float = 0.2,    # P(L0)
        p_transit: float = 0.1,    # P(T)
        p_slip: float = 0.1,       # P(S)
        p_guess: float = 0.2,      # P(G)
        repository=None,
    ):
        self.p_initial = p_initial
        self.p_transit = p_transit
        self.p_slip = p_slip
        self.p_guess = p_guess
        self.repository = repository

        # 内部状态：{(student_id, kp_id): dict}
        self._states: Dict[tuple, dict] = {}

    def _get_state(self, student_id: str, kp_id: str) -> dict:
        key = (str(student_id), str(kp_id))
        if key not in self._states:
            self._states[key] = {
                "p_learned": self.p_initial,
                "history": [],
            }
        return self._states[key]

    def update(self, student_id: str, kp_id: str, correct: bool) -> float:
        """一次答题后增量更新 P(L)。

        Args:
            student_id: 学生 ID
            kp_id: 知识点 ID
            correct: 是否答对

        Returns:
            更新后的 P(L)
        """
        state = self._get_state(student_id, kp_id)
        P_L = state["p_learned"]

        if correct:
            p_correct_given_learned = 1.0 - self.p_slip
            p_correct = P_L * p_correct_given_learned + (1.0 - P_L) * self.p_guess
            if p_correct > 0:
                P_L_given_obs = P_L * p_correct_given_learned / p_correct
            else:
                P_L_given_obs = P_L
        else:
            p_wrong_given_learned = self.p_slip
            p_wrong = P_L * p_wrong_given_learned + (1.0 - P_L) * (1.0 - self.p_guess)
            if p_wrong > 0:
                P_L_given_obs = P_L * p_wrong_given_learned / p_wrong
            else:
                P_L_given_obs = P_L

        # BKT+ 个性化转移率：根据历史表现微调 P(T)
        p_transit = self._personalized_transit(student_id, kp_id)

        P_L_new = P_L_given_obs + (1.0 - P_L_given_obs) * p_transit
        P_L_new = max(0.01, min(0.99, P_L_new))

        state["p_learned"] = P_L_new
        state["history"].append({
            "correct": correct,
            "p_before": P_L,
            "p_after": P_L_new,
            "ts": time.time(),  # /learner/mastery_history 按日聚合用
        })

        # 异步持久化
        self._maybe_persist(student_id, kp_id, state)

        return P_L_new

    def _personalized_transit(self, student_id: str, kp_id: str) -> float:
        """BKT+ 个性化转移率：根据该学生该知识点的历史表现微调 P(T)。

        答对率高 → P(T) 略高（学生容易学）；答错率高 → P(T) 略低。
        """
        state = self._get_state(student_id, kp_id)
        history = state.get("history", [])
        if len(history) < 3:
            return self.p_transit
        recent = history[-5:]
        correct_rate = sum(1 for h in recent if h.get("correct")) / len(recent)
        # 调整范围：p_transit × [0.7, 1.3]
        return self.p_transit * (0.7 + 0.6 * correct_rate)

    def get_transit_rate(self, student_id: str, kp_id: str) -> float:
        """获取某学生某知识点的个性化 P(T)"""
        return self._personalized_transit(student_id, kp_id)

    def _maybe_persist(self, student_id: str, kp_id: str, state: dict) -> None:
        """每 5 次更新持久化一次（减少 DB 写入）"""
        if self.repository is None:
            return
        history_len = len(state.get("history", []))
        if history_len % 5 == 0:
            try:
                self.repository.save_bkt_state(student_id, kp_id, {
                    "p_learned": state["p_learned"],
                    "p_transit": self._personalized_transit(student_id, kp_id),
                    "p_slip": self.p_slip,
                    "p_guess": self.p_guess,
                    "history": state.get("history", []),
                })
            except Exception as exc:
                logger.warning("[BKT] state persistence failed: %s", exc)

    def load_all_from_db(self, user_id: str) -> int:
        """从 SQLite 恢复该用户的所有 BKT 状态。返回恢复条数。"""
        return self.restore_user(user_id)

    def restore_user(self, user_id: str) -> int:
        """Restore all persisted BKT states for one learner."""
        if self.repository is None:
            return 0
        try:
            all_states = self.repository.load_all_bkt(user_id)
            for kp_id, db_state in all_states.items():
                key = (str(user_id), str(kp_id))
                self._states[key] = {
                    "p_learned": db_state.get("p_learned", self.p_initial),
                    "history": db_state.get("history", []),
                }
            return len(all_states)
        except Exception as exc:
            logger.warning("[BKT] state restore failed: %s", exc)
            return 0

    def get_mastery(self, student_id: str, kp_id: str) -> float:
        """获取当前 P(L)"""
        return self._get_state(student_id, kp_id)["p_learned"]

    def get_all_masteries(self, student_id: str) -> Dict[str, float]:
        """获取某学生所有知识点的 P(L)"""
        prefix = str(student_id)
        return {
            kp_id: state["p_learned"]
            for (sid, kp_id), state in self._states.items()
            if sid == prefix
        }

    def get_history(self, student_id: str, kp_id: str) -> List[dict]:
        """获取某学生的答题历史"""
        return self._get_state(student_id, kp_id)["history"]

    def trend(self, student_id: str, kp_id: str) -> str:
        """判断掌握趋势：improving / declining / stable"""
        history = self.get_history(student_id, kp_id)
        if len(history) < 2:
            return "stable"
        recent = history[-5:]
        start = recent[0]["p_before"]
        end = recent[-1]["p_after"]
        if end > start + 0.05:
            return "improving"
        if end < start - 0.05:
            return "declining"
        return "stable"

    def reset(self, student_id: str, kp_id: str = "") -> None:
        """重置状态"""
        if kp_id:
            self._states.pop((str(student_id), str(kp_id)), None)
        else:
            prefix = str(student_id)
            keys = [k for k in self._states if k[0] == prefix]
            for k in keys:
                self._states.pop(k, None)


# 模块级单例（供 Agent 调用）
_bkt_instance: Optional[BKT] = None
_bkt_seeded = False


def _demo_mastery_value(base_score: float, offset: float, user_id: str, kp_id: str) -> float:
    """生成稳定的小幅离散值，让演示数据自然但不随刷新跳动。"""
    digest = hashlib.sha256(f"{user_id}:{kp_id}".encode("utf-8")).digest()
    unit = int.from_bytes(digest[:2], "big") / 65535
    jitter = (unit - 0.5) * 0.07
    return round(max(0.1, min(0.95, base_score + offset + jitter)), 4)


def get_bkt() -> BKT:
    global _bkt_instance, _bkt_seeded
    if _bkt_instance is None:
        try:
            from backend.app.services.cognitive_diagnosis.state_repository import get_state_repo

            _bkt_instance = BKT(repository=get_state_repo())
        except Exception:  # pragma: no cover - database-less fallback
            _bkt_instance = BKT()
    if not _bkt_seeded:
        _seed_demo_bkt(_bkt_instance)
        _bkt_seeded = True
    return _bkt_instance


def _seed_demo_bkt(bkt: BKT) -> None:
    """为 demo 学生注入基于 seed.json 画像的 BKT 初始掌握度，
    避免演示时所有知识点都显示 20%。"""
    import json
    from pathlib import Path

    data_dir = Path(__file__).resolve().parents[4] / "data"
    students: list[dict] = []
    seen_user_ids: set[str] = set()
    for filename, key in (
        ("seed.json", "students"),
        ("seed_extended.json", "extra_students"),
    ):
        try:
            seed = json.loads((data_dir / filename).read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[BKT] demo seed unavailable (%s): %s", filename, exc)
            continue
        for student in seed.get(key, []):
            user_id = str(student.get("user_id", ""))
            if not user_id or user_id in seen_user_ids:
                continue
            seen_user_ids.add(user_id)
            students.append(student)

    # 知识点 ID → 默认掌握度偏移（基础+进阶分层）
    kp_difficulty = {
        "AI_001": 0.0, "AI_002": -0.05, "AI_003": 0.05, "AI_004": -0.1,
        "AI_005": -0.15, "AI_005_01": -0.1, "AI_005_02": -0.2, "AI_005_03": -0.25,
        "AI_006": -0.1, "AI_006_01": -0.15, "AI_006_02": -0.2, "AI_006_03": -0.25,
        "AI_007": -0.05, "AI_008": -0.1, "AI_009": -0.15, "AI_010": -0.2,
        "MATH_001": 0.0, "MATH_002": -0.1, "MATH_003": -0.15,
        "CODE_001": 0.0, "CODE_002": -0.1,
    }

    demo_user_ids: list[str] = []
    for student in students:
        user_id = str(student.get("user_id", ""))
        if not user_id.startswith("demo-student-"):
            continue
        demo_user_ids.append(user_id)
        profile = student.get("profile", {})
        kb = profile.get("knowledge_base", {})
        base_score = kb.get("score", 0.5) if isinstance(kb, dict) else 0.5

        for kp_id, offset in kp_difficulty.items():
            p = _demo_mastery_value(base_score, offset, user_id, kp_id)
            bkt._states[(user_id, kp_id)] = {
                "p_learned": round(p, 4),
                "history": [],
            }

    restored = 0
    if bkt.repository is not None:
        for user_id in demo_user_ids:
            restored += bkt.restore_user(user_id)

    logger.info(
        "[BKT] seeded %d demo student baselines from primary and extended seeds "
        "and restored %d persisted states",
        len(demo_user_ids),
        restored,
    )
