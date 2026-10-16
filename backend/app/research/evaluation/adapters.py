"""
Model Adapters — unified fit/predict_proba interface for benchmark CV loop.

Four models: DINA / BKT / DKT / Naive, all follow next-step KT protocol.
Uses precomputed skill_idx (O(1) lookup) — no O(K) skill scan per entry.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _split_data_by_students(data, train_students, test_students):
    train_resp = {s: data["responses"][s] for s in train_students if s in data["responses"]}
    test_resp = {s: data["responses"][s] for s in test_students if s in data["responses"]}
    train_seqs = [data["sequences"][i] for i, sid in enumerate(data["student_ids"])
                  if str(sid) in set(str(s) for s in train_students)]
    test_seqs = [data["sequences"][i] for i, sid in enumerate(data["student_ids"])
                 if str(sid) in set(str(s) for s in test_students)]
    return train_resp, test_resp, train_seqs, test_seqs


def _skill_lookup(entry, skill_ids, n_skills):
    """O(1) skill lookup using precomputed skill_idx field."""
    idx = entry.get("skill_idx", -1)
    if idx < 0 or idx >= n_skills:
        return None
    return skill_ids[idx]


# ═══════════════════════════════════════════════════════
# DINA Adapter
# ═══════════════════════════════════════════════════════

class DINAAdapter:
    def __init__(self, max_iter=100, tolerance=1e-4, n_super=12):
        self.max_iter = max_iter
        self.tolerance = tolerance
        self.n_super = n_super
        self._dina = None
        self._q_matrix = None
        self._item_ids = None
        self._skill_ids = None
        self._skill_to_super: Optional[Dict[str, int]] = None
        # super-attribute 级别 slip/guess（从 DINA fit 结果继承）
        self._super_slip: Dict[int, float] = {}
        self._super_guess: Dict[int, float] = {}
        self._super_p_initial: Dict[int, float] = {}
        self._super_p_transit: Dict[int, float] = {}
        # skill 级别独立 slip/guess（per-skill 估计，更精准）
        self._skill_slip: Dict[str, float] = {}
        self._skill_guess: Dict[str, float] = {}
        self._skill_p_initial: Dict[str, float] = {}
        self._train_time: float = 0.0

    @property
    def name(self) -> str:
        return "DINA"

    def fit(self, data, train_students):
        """两阶段拟合：① super-attribute DINA 获取全局先验 ② per-skill EM 精细化 slip/guess。"""
        from backend.app.services.cognitive_diagnosis.dina import DINA

        self._q_matrix = data["q_matrix"]
        self._item_ids = data["item_ids"]
        self._skill_ids = data["skill_ids"]
        n_skills = len(data["skill_ids"])
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))

        start = time.perf_counter()

        # ── 阶段 1：super-attribute DINA 拿全局先验（快速，仅用于正则）──
        self._skill_to_super = self._cluster_skills(data)
        super_ids = [f"super_{i}" for i in range(self.n_super)]
        super_item_ids = [f"sitem_{i}" for i in range(self.n_super)]
        super_q = np.eye(self.n_super)

        train_resp_super: Dict[str, Dict[str, int]] = {}
        for uid in train_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            super_corrects: Dict[int, list] = {i: [] for i in range(self.n_super)}
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid is None:
                    continue
                super_idx = self._skill_to_super.get(sid, 0)
                super_corrects[super_idx].append(int(entry["correct"]))
            train_resp_super[uid_str] = {
                siid: (1 if sum(v) * 2 >= len(v) else 0)
                for i, siid in enumerate(super_item_ids)
                if (v := super_corrects.get(i))
            }

        # super-attribute DINA 用少迭代拿先验（主力于 per-skill EM）
        self._dina = DINA(max_iter=20, tolerance=self.tolerance)
        train_ids_str = [str(s) for s in train_students]
        try:
            self._dina.fit(train_resp_super, super_q, super_item_ids, super_ids, train_ids_str)
            for i, siid in enumerate(super_item_ids):
                self._super_slip[i] = max(0.01, min(0.4, float(self._dina.slip_.get(siid, 0.2))))
                self._super_guess[i] = max(0.05, min(0.4, float(self._dina.guess_.get(siid, 0.2))))
                alphas = [float(self._dina.alpha_.get(uid, {}).get(siid, 0.3)) for uid in train_ids_str]
                self._super_p_initial[i] = max(0.05, min(0.5, sum(alphas) / max(1, len(alphas))))
                self._super_p_transit[i] = 0.1
        except Exception as e:
            logger.warning("[DINA] super-attribute fit failed, using defaults: %s", e)
            for i in range(self.n_super):
                self._super_slip[i] = 0.2
                self._super_guess[i] = 0.25
                self._super_p_initial[i] = 0.3
                self._super_p_transit[i] = 0.1

        # ── 阶段 2：per-skill EM 精细化（主力，5 轮迭代）──
        self._estimate_per_skill_params(data, train_students, seq_by_student)

        self._train_time = time.perf_counter() - start
        logger.info(
            "[DINA] fit: %d students, %d super + per-skill EM, %.2fs",
            len(train_students), self.n_super, self._train_time,
        )

    def _cluster_skills(self, data):
        """按频率排序后 round-robin 分配到 super-attribute。"""
        skill_to_super: Dict[str, int] = {}
        n = len(data["skill_ids"])
        if n <= self.n_super:
            for i, sid in enumerate(data["skill_ids"]):
                skill_to_super[sid] = i % self.n_super
            return skill_to_super
        skill_freq = {sid: 0 for sid in data["skill_ids"]}
        n_skills = n
        for seq in data["sequences"]:
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid:
                    skill_freq[sid] += 1
        sorted_skills = sorted(data["skill_ids"], key=lambda s: -skill_freq.get(s, 0))
        for i, sid in enumerate(sorted_skills):
            skill_to_super[sid] = i % self.n_super
        return skill_to_super

    def _estimate_per_skill_params(self, data, train_students, seq_by_student):
        """Per-skill slip/guess 矩估计 + EM 迭代精化 + super 先验正则。

        用 3 轮 EM 迭代：
        - E-step：用当前 slip/guess 算每步的 mastered 后验
        - M-step：用后验权重重新估 slip/guess
        - 样本不足时向 super 先验收缩
        """
        n_skills = len(data["skill_ids"])
        # 每个技能收集作答序列（按学生）
        skill_sequences: Dict[str, list] = {sid: [] for sid in data["skill_ids"]}
        for uid in train_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid is None:
                    continue
                skill_sequences[sid].append(int(entry["correct"]))

        for sid in data["skill_ids"]:
            responses = skill_sequences.get(sid, [])
            super_idx = self._skill_to_super.get(sid, 0)
            super_slip = self._super_slip.get(super_idx, 0.2)
            super_guess = self._super_guess.get(super_idx, 0.2)
            super_init = self._super_p_initial.get(super_idx, 0.3)

            if len(responses) < 20:
                self._skill_slip[sid] = super_slip
                self._skill_guess[sid] = super_guess
                self._skill_p_initial[sid] = super_init
                continue

            # 初始化：用首次作答正确率估 p_initial，整体正确率估 guess
            p_init = max(0.05, min(0.5, super_init))
            slip = super_slip
            guess = super_guess

            # 5 轮 EM 迭代
            for _em_iter in range(5):
                # E-step：逐题算 mastered 后验
                eta = p_init
                mastered_weights = []  # (eta, correct) pairs
                for c in responses:
                    mastered_weights.append((eta, c))
                    # 贝叶斯更新
                    if c:
                        p_obs_l = 1 - slip
                        p_obs_nl = guess
                    else:
                        p_obs_l = slip
                        p_obs_nl = 1 - guess
                    denom = p_obs_l * eta + p_obs_nl * (1 - eta)
                    if denom > 1e-9:
                        eta = p_obs_l * eta / denom
                    eta = min(0.99, eta + (1 - eta) * 0.1)  # transit

                # M-step：用后验权重估 slip/guess
                # slip = sum(eta_i * (1-c_i)) / sum(eta_i)  掌握但答错的比例
                # guess = sum((1-eta_i) * c_i) / sum(1-eta_i)  未掌握但答对的比例
                sum_eta = sum(e for e, _ in mastered_weights)
                sum_not_eta = sum(1 - e for e, _ in mastered_weights)
                if sum_eta > 1e-6:
                    new_slip = sum(e * (1 - c) for e, c in mastered_weights) / sum_eta
                else:
                    new_slip = slip
                if sum_not_eta > 1e-6:
                    new_guess = sum((1 - e) * c for e, c in mastered_weights) / sum_not_eta
                else:
                    new_guess = guess
                # 平滑（避免极端值）
                slip = 0.5 * slip + 0.5 * new_slip
                guess = 0.5 * guess + 0.5 * new_guess

            # p_initial 用首次作答估
            first_corrects = responses[:50]  # 取前 50 个首次作答
            if first_corrects:
                p_init = max(0.05, min(0.5, sum(first_corrects) / len(first_corrects)))

            # 贝叶斯收缩
            n_obs = len(responses)
            shrink = n_obs / (n_obs + 50.0)
            slip = shrink * slip + (1 - shrink) * super_slip
            guess = shrink * guess + (1 - shrink) * super_guess
            p_init = shrink * p_init + (1 - shrink) * super_init

            self._skill_slip[sid] = max(0.01, min(0.35, slip))
            self._skill_guess[sid] = max(0.05, min(0.4, guess))
            self._skill_p_initial[sid] = max(0.05, min(0.5, p_init))

    def predict_proba(self, data, test_students):
        """Per-skill DINA 预测：P(correct) = (1-slip)·η + guess·(1-η)。

        η 是该 skill 的掌握后验，用贝叶斯更新维护。
        slip/guess 用 per-skill 精细化参数。
        """
        probs: List[float] = []
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        n_skills = len(data["skill_ids"])
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            skill_mastery: Dict[str, float] = {}
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid is None:
                    probs.append(0.5)
                    continue
                # 取 per-skill 参数
                if sid not in skill_mastery:
                    skill_mastery[sid] = self._skill_p_initial.get(sid, 0.3)
                eta = max(0.01, min(0.99, skill_mastery[sid]))
                slip = self._skill_slip.get(sid, 0.2)
                guess = self._skill_guess.get(sid, 0.2)
                # DINA 作答概率
                p_correct = (1 - slip) * eta + guess * (1 - eta)
                probs.append(float(max(0.01, min(0.99, p_correct))))
                # 贝叶斯更新 eta
                correct = int(entry["correct"])
                if correct:
                    p_obs_eta1 = 1 - slip
                    p_obs_eta0 = guess
                else:
                    p_obs_eta1 = slip
                    p_obs_eta0 = 1 - guess
                denom = p_obs_eta1 * eta + p_obs_eta0 * (1 - eta)
                if denom > 1e-9:
                    eta_post = p_obs_eta1 * eta / denom
                else:
                    eta_post = eta
                # 转移概率（学习进步）
                super_idx = self._skill_to_super.get(sid, 0)
                p_transit = self._super_p_transit.get(super_idx, 0.1)
                eta_new = eta_post + (1 - eta_post) * p_transit
                skill_mastery[sid] = max(0.01, min(0.99, eta_new))
        return probs

    def get_train_time(self):
        return self._train_time


# ═══════════════════════════════════════════════════════
# BKT Adapter
# ═══════════════════════════════════════════════════════

class BKTAdapter:
    def __init__(self):
        self._skill_params: Dict[str, Dict[str, float]] = {}
        self._train_time: float = 0.0

    @property
    def name(self) -> str:
        return "BKT"

    def fit(self, data, train_students):
        start = time.perf_counter()
        n_skills = len(data["skill_ids"])
        skill_stats = {sid: {"first_correct": [], "prev_cur_pairs": [], "all_correct": []}
                       for sid in data["skill_ids"]}
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))

        for uid in train_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            skill_mastery: Dict[str, float] = {}
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid is None:
                    continue
                correct = bool(entry["correct"])
                stats = skill_stats[sid]
                if sid not in skill_mastery:
                    stats["first_correct"].append(1 if correct else 0)
                    skill_mastery[sid] = 0.5
                else:
                    stats["prev_cur_pairs"].append((skill_mastery[sid], 1 if correct else 0))
                stats["all_correct"].append(1 if correct else 0)
                if correct:
                    skill_mastery[sid] = min(0.95, skill_mastery[sid] + 0.15)
                else:
                    skill_mastery[sid] = max(0.05, skill_mastery[sid] - 0.15)

        for sid in data["skill_ids"]:
            stats = skill_stats[sid]
            first = stats["first_correct"]
            pairs = stats["prev_cur_pairs"]
            l0 = sum(first) / len(first) if first else 0.5
            low_trans = [c for (pm, c) in pairs if pm < 0.5]
            t = sum(low_trans) / len(low_trans) if low_trans else 0.1
            high = [c for (pm, c) in pairs if pm >= 0.5]
            slip = 1 - (sum(high) / len(high)) if high else 0.1
            self._skill_params[sid] = {
                "L0": max(0.05, min(0.5, l0)),
                "T": max(0.05, min(0.5, t)),
                "S": max(0.01, min(0.3, slip)),
                "G": max(0.05, min(0.4, max(0.05, t))),
            }
        self._train_time = time.perf_counter() - start
        logger.info("[BKT] fit: %d students, %d skills, %.2fs",
                    len(train_students), len(self._skill_params), self._train_time)

    def predict_proba(self, data, test_students):
        probs: List[float] = []
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        n_skills = len(data["skill_ids"])
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            skill_mastery: Dict[str, float] = {}
            for entry in seq:
                sid = _skill_lookup(entry, data["skill_ids"], n_skills)
                if sid is None:
                    probs.append(0.5)
                    continue
                params = self._skill_params.get(sid, {"L0": 0.3, "T": 0.1, "S": 0.1, "G": 0.2})
                if sid not in skill_mastery:
                    skill_mastery[sid] = params["L0"]
                mastered = skill_mastery[sid]
                s, g = params["S"], params["G"]
                probs.append(mastered * (1 - s) + (1 - mastered) * g)
                correct = bool(entry["correct"])
                if correct:
                    p_obs_l, p_obs_nl = 1 - s, g
                else:
                    p_obs_l, p_obs_nl = s, 1 - g
                p_l = max(mastered * p_obs_l + (1 - mastered) * p_obs_nl, 1e-9)
                new_m = mastered * p_obs_l / p_l
                new_m = new_m + (1 - new_m) * params["T"]
                skill_mastery[sid] = min(0.99, max(0.01, float(new_m)))
        return probs

    def get_train_time(self):
        return self._train_time


# ═══════════════════════════════════════════════════════
# DKT Adapter
# ═══════════════════════════════════════════════════════

class DKTAdapter:
    def __init__(self, hidden_dim=64, n_layers=1, max_epochs=30, batch_size=32):
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self._trainer: Any = None
        self._train_time: float = 0.0

    @property
    def name(self) -> str:
        return "DKT"

    def fit(self, data, train_students):
        from backend.app.research.models.dkt import DKTTrainer
        train_seqs = []
        for i, sid in enumerate(data["student_ids"]):
            if str(sid) in set(str(s) for s in train_students):
                train_seqs.append(data["sequences"][i])
        self._trainer = DKTTrainer(
            n_skills=len(data["skill_ids"]), hidden_dim=self.hidden_dim,
            n_layers=self.n_layers, max_epochs=self.max_epochs, batch_size=self.batch_size,
        )
        start = time.perf_counter()
        self._trainer.train_model(train_seqs)
        self._train_time = time.perf_counter() - start
        logger.info("[DKT] fit: %d students, %.2fs", len(train_students), self._train_time)

    def predict_proba(self, data, test_students):
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        test_seqs = []
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            test_seqs.append(seq if seq else [])
        all_preds = self._trainer.predict(test_seqs)
        probs: List[float] = []
        for student_idx in range(len(test_students)):
            preds = all_preds[student_idx] if student_idx < len(all_preds) else []
            probs.extend(preds)
        return probs

    def get_train_time(self):
        return self._train_time


# ═══════════════════════════════════════════════════════
# Naive Baseline Adapter
# ═══════════════════════════════════════════════════════

class NaiveModelAdapter:
    def __init__(self):
        self._model = None
        self._train_time: float = 0.0

    @property
    def name(self) -> str:
        return "Naive"

    def fit(self, data, train_students):
        from backend.app.research.models.naive_baseline import NaiveBaseline
        self._model = NaiveBaseline()
        start = time.perf_counter()
        self._model.fit(
            train_students=train_students, train_responses=data["responses"],
            train_item_ids=data["item_ids"], train_skill_ids=data["skill_ids"],
            train_q_matrix=data["q_matrix"],
        )
        self._train_time = time.perf_counter() - start
        logger.info("[Naive] fit: %d students, %.2fs", len(train_students), self._train_time)

    def predict_proba(self, data, test_students):
        probs: List[float] = []
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            if not seq:
                continue
            step_items = [entry["item_id"] for entry in seq]
            pred = self._model.predict_proba([uid], step_items)
            probs.extend(pred)
        return probs

    def get_train_time(self):
        return self._train_time


# ═══════════════════════════════════════════════════════
# SAKT Adapter (Self-Attentive Knowledge Tracing)
# ═══════════════════════════════════════════════════════

class SAKTAdapter:
    def __init__(self, embed_dim=64, num_heads=4, num_layers=1, max_epochs=30, batch_size=32):
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self._trainer: Any = None
        self._train_time: float = 0.0

    @property
    def name(self) -> str:
        return "SAKT"

    def fit(self, data, train_students):
        from backend.app.research.models.sakt import SAKTTrainer
        train_seqs = []
        for i, sid in enumerate(data["student_ids"]):
            if str(sid) in set(str(s) for s in train_students):
                train_seqs.append(data["sequences"][i])
        self._trainer = SAKTTrainer(
            n_skills=len(data["skill_ids"]),
            embed_dim=self.embed_dim,
            num_heads=self.num_heads,
            num_layers=self.num_layers,
            max_epochs=self.max_epochs,
            batch_size=self.batch_size,
        )
        start = time.perf_counter()
        self._trainer.train_model(train_seqs)
        self._train_time = time.perf_counter() - start
        logger.info("[SAKT] fit: %d students, %.2fs", len(train_students), self._train_time)

    def predict_proba(self, data, test_students):
        seq_by_student = dict(zip(data["student_ids"], data["sequences"]))
        test_seqs = []
        for uid in test_students:
            uid_str = str(uid)
            seq = seq_by_student.get(uid_str) or seq_by_student.get(uid)
            test_seqs.append(seq if seq else [])
        all_preds = self._trainer.predict(test_seqs)
        probs: List[float] = []
        for student_idx in range(len(test_students)):
            preds = all_preds[student_idx] if student_idx < len(all_preds) else []
            probs.extend(preds)
        return probs

    def get_train_time(self):
        return self._train_time
