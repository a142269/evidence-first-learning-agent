"""
DINA cognitive diagnosis model - Junker & Sijtsma 2001

EM algorithm estimates slip/guess/mastery. Exact E-step for K<=6,
Coordinative ascent mean-field VI for K>6.
"""
from __future__ import annotations
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class DINA:
    def __init__(self, slip_prior=0.1, guess_prior=0.2, mastery_prior=0.5,
                 max_iter=100, tolerance=1e-4, repository=None):
        self.slip_prior = slip_prior
        self.guess_prior = guess_prior
        self.mastery_prior = mastery_prior
        self.max_iter = max_iter
        self.tolerance = tolerance
        self.repository = repository
        # The same fitter is used with numeric legacy IDs and string IDs in
        # the research adapter; preserve the caller's item-key type.
        self.slip_: Dict[str | int, float] = {}
        self.guess_: Dict[str | int, float] = {}
        self.alpha_: Dict[int, Dict[str, float]] = {}
        self.converged_ = False
        self.iterations_ = 0

    def build_q_matrix(self, items: List[dict], all_kp_ids: List[str]) -> np.ndarray:
        kp_index = {kp: i for i, kp in enumerate(all_kp_ids)}
        Q = np.zeros((len(items), len(all_kp_ids)))
        for j, item in enumerate(items):
            for kp_id in item.get("kp_ids", []):
                if kp_id in kp_index:
                    Q[j, kp_index[kp_id]] = 1.0
        return Q

    @staticmethod
    def _ideal_response(alpha, q_row):
        if np.sum(q_row) == 0:
            return 1.0
        return float(np.prod(alpha ** q_row))

    def fit(self, responses, q_matrix, item_ids, kp_ids, student_ids=None):
        if student_ids is None:
            student_ids = list(responses.keys())
        J, K = len(item_ids), len(kp_ids)
        I = len(student_ids)
        if J == 0 or K == 0 or I == 0:
            return self._fallback_result(student_ids, kp_ids, item_ids)

        Q = np.asarray(q_matrix, dtype=float)
        if Q.shape != (J, K):
            raise ValueError(
                f"q_matrix shape must be {(J, K)}, got {Q.shape}"
            )

        R = np.zeros((I, J))
        for i, sid in enumerate(student_ids):
            for j, iid in enumerate(item_ids):
                R[i, j] = responses.get(sid, {}).get(iid, 0)

        slip = np.full(J, self.slip_prior)
        guess = np.full(J, self.guess_prior)
        alpha_prob = np.full((I, K), self.mastery_prior)

        prev_ll = -float("inf")
        for it in range(self.max_iter):
            if K <= 6:
                alpha_prob = self._e_step_exact(R, Q, slip, guess, K)
            else:
                alpha_prob = self._e_step_mean_field(R, Q, slip, guess, alpha_prob)

            slip, guess = self._m_step(R, Q, alpha_prob, slip, guess)

            ll = self._log_likelihood(R, Q, alpha_prob, slip, guess)
            if abs(ll - prev_ll) < self.tolerance:
                self.converged_ = True
                break
            prev_ll = ll

        self.iterations_ = it + 1
        self.slip_ = {iid: float(slip[j]) for j, iid in enumerate(item_ids)}
        self.guess_ = {iid: float(guess[j]) for j, iid in enumerate(item_ids)}
        self.alpha_ = {}
        for i, sid in enumerate(student_ids):
            self.alpha_[sid] = {kp_ids[k]: float(alpha_prob[i, k]) for k in range(K)}
        self._persist_results(student_ids, kp_ids)

        logger.info("[DINA] fit done: %d iters, converged=%s, mean_mastery=%.3f",
                     self.iterations_, self.converged_, float(np.mean(alpha_prob)))
        return {"slip": self.slip_, "guess": self.guess_, "alpha": self.alpha_,
                "converged": self.converged_, "iterations": self.iterations_}

    def _e_step_exact(self, R, Q, slip, guess, K):
        I, J = R.shape
        alpha_prob = np.zeros((I, K))
        combos = np.array([[int(b) for b in f"{x:0{K}b}"] for x in range(2**K)])
        for i in range(I):
            posteriors = np.zeros(2**K)
            for c, alpha in enumerate(combos):
                log_p = 0.0
                for j in range(J):
                    eta = self._ideal_response(alpha, Q[j])
                    p_correct = (1 - slip[j]) ** eta * guess[j] ** (1 - eta)
                    if R[i, j] == 1:
                        log_p += math.log(max(p_correct, 1e-12))
                    else:
                        log_p += math.log(max(1 - p_correct, 1e-12))
                posteriors[c] = log_p
            post_max = np.max(posteriors)
            probs = np.exp(posteriors - post_max)
            probs /= probs.sum()
            alpha_prob[i] = combos.T @ probs
        return alpha_prob

    def _e_step_mean_field(self, R, Q, slip, guess, alpha_prob):
        """Vectorized coordinate-ascent mean-field VI for K>6.

        For each student i and attribute k, compute Delta_ik =
        expected log-likelihood difference between alpha_k=1 and alpha_k=0,
        averaging over alpha_{-k} per mean-field. Then sigmoid-update.

        Vectorized over students (I) and items (J) using numpy.
        """
        I, J = R.shape
        K = alpha_prob.shape[1]
        new_prob = np.clip(alpha_prob.copy(), 0.01, 0.99)

        # Precompute per-item probabilities (J,)
        p_correct_mastered = np.clip(1.0 - slip, 1e-9, 1.0)   # P(R=1|mastered)
        p_correct_unmastered = np.clip(guess, 1e-9, 1.0)      # P(R=1|unmastered)
        p_wrong_mastered = np.clip(slip, 1e-9, 1.0)           # P(R=0|mastered)
        p_wrong_unmastered = np.clip(1.0 - guess, 1e-9, 1.0)  # P(R=0|unmastered)

        prior_logit = math.log(self.mastery_prior / (1.0 - self.mastery_prior))

        for _mf_iter in range(50):
            prev = new_prob.copy()
            for k in range(K):
                q_k = Q[:, k]  # (J,) which items require attribute k
                if not np.any(q_k > 0):
                    continue
                # Items that require attribute k
                req_items = np.where(q_k > 0)[0]

                # Expected eta excluding attribute k: product over other required attrs
                # eta_excl_k[i, j] = prod_{m != k, Q[j,m]>0} new_prob[i, m]
                Q_other = Q.copy()
                Q_other[:, k] = 0.0
                # log-space product to avoid underflow
                log_prob_safe = np.log(np.clip(new_prob, 1e-9, 1.0))  # (I, K)
                # For each item j, sum log-prob over required attrs (excluding k)
                # log_eta_excl = Q_other @ log_prob.T  -> shape (J, I)
                log_eta_excl = Q_other @ log_prob_safe.T  # (J, I)
                eta_excl_k = np.exp(log_eta_excl).T  # (I, J), clipped
                eta_excl_k = np.clip(eta_excl_k, 0.0, 1.0)

                # For required items only
                # lk1[i, j] = eta_excl * p(correct|mastered) + (1-eta_excl) * p(correct|unmastered)
                # Select p based on R[i, j]
                R_req = R[:, req_items]  # (I, n_req)
                eta_req = eta_excl_k[:, req_items]  # (I, n_req)

                # P(R | alpha_k=1): mixture
                p_obs_k1 = np.where(
                    R_req == 1,
                    eta_req * p_correct_mastered[req_items]
                    + (1 - eta_req) * p_correct_unmastered[req_items],
                    eta_req * p_wrong_mastered[req_items]
                    + (1 - eta_req) * p_wrong_unmastered[req_items],
                )
                # P(R | alpha_k=0): only unmastered path
                p_obs_k0 = np.where(
                    R_req == 1,
                    p_correct_unmastered[req_items],
                    p_wrong_unmastered[req_items],
                )

                # Delta_ik = sum_j log(p_obs_k1) - log(p_obs_k0)
                log_ratio = np.log(np.clip(p_obs_k1, 1e-12, None)) - \
                            np.log(np.clip(p_obs_k0, 1e-12, None))
                delta = log_ratio.sum(axis=1)  # (I,)

                # Sigmoid update (numerically stable)
                logit = prior_logit + delta
                logit = np.clip(logit, -30.0, 30.0)
                new_prob[:, k] = np.where(
                    logit >= 0,
                    1.0 / (1.0 + np.exp(-logit)),
                    np.exp(logit) / (1.0 + np.exp(logit)),
                )
                new_prob[:, k] = np.clip(new_prob[:, k], 0.01, 0.99)

            if np.max(np.abs(new_prob - prev)) < 1e-4:
                break
        return new_prob

    def _m_step(self, R, Q, alpha_prob, slip, guess):
        I, J = R.shape
        new_slip = np.copy(slip)
        new_guess = np.copy(guess)
        for j in range(J):
            q_j = Q[j]
            eta_exp = np.ones(I)
            for k, q_jk in enumerate(q_j):
                if q_jk > 0:
                    eta_exp *= alpha_prob[:, k]
            w_11 = np.sum(eta_exp * R[:, j])
            w_10 = np.sum(eta_exp * (1 - R[:, j]))
            w_01 = np.sum((1 - eta_exp) * R[:, j])
            w_00 = np.sum((1 - eta_exp) * (1 - R[:, j]))
            new_slip[j] = max(0.01, min(0.49, w_10 / max(w_11 + w_10, 1e-6)))
            new_guess[j] = max(0.01, min(0.49, w_01 / max(w_01 + w_00, 1e-6)))
        return new_slip, new_guess

    def _log_likelihood(self, R, Q, alpha_prob, slip, guess):
        I, J = R.shape
        ll = 0.0
        for i in range(I):
            for j in range(J):
                eta_exp = self._ideal_response(alpha_prob[i], Q[j])
                p_correct = eta_exp * (1 - slip[j]) + (1 - eta_exp) * guess[j]
                if R[i, j] == 1:
                    ll += math.log(max(p_correct, 1e-12))
                else:
                    ll += math.log(max(1 - p_correct, 1e-12))
        return ll

    def _fallback_result(self, student_ids, kp_ids, item_ids):
        self.slip_ = {iid: self.slip_prior for iid in item_ids}
        self.guess_ = {iid: self.guess_prior for iid in item_ids}
        self.alpha_ = {sid: {kp: self.mastery_prior for kp in kp_ids} for sid in student_ids}
        return {"slip": self.slip_, "guess": self.guess_, "alpha": self.alpha_,
                "converged": False, "iterations": 0, "fallback_reason": "insufficient_data"}

    def diagnose(self, student_id):
        return self.alpha_.get(student_id, {})

    def _persist_results(self, student_ids, kp_ids) -> None:
        if self.repository is None:
            return
        slip = float(np.mean(list(self.slip_.values()))) if self.slip_ else self.slip_prior
        guess = float(np.mean(list(self.guess_.values()))) if self.guess_ else self.guess_prior
        for student_id in student_ids:
            for kp_id in kp_ids:
                self.repository.save_dina_state(
                    str(student_id),
                    kp_id,
                    self.alpha_[student_id][kp_id],
                    slip,
                    guess,
                )

    def restore_user(self, user_id: str) -> dict[str, dict]:
        """Restore a learner mastery snapshot from persistent storage."""
        if self.repository is None:
            return {}
        snapshot = self.repository.load_dina_snapshot(str(user_id))
        if snapshot:
            self.alpha_[user_id] = {
                kp_id: state["mastery"] for kp_id, state in snapshot.items()
            }
        return snapshot


def diagnose_student(responses, items, kp_ids, student_ids=None):
    dina = DINA()
    q = dina.build_q_matrix(items, kp_ids)
    item_id_list = [item["item_id"] for item in items]
    return dina.fit(responses, q, item_id_list, kp_ids, student_ids)
