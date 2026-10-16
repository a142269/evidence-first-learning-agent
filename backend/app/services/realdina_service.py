"""Real-time DINA mastery snapshot service (A-owned).

Wires Day 7's `RealDINAAdapter` (AUC 0.8024 on ASSISTments-2009) into the
chat pipeline so that downstream agents can read a per-(user, KP)
mastery vector without invoking the full EM at every turn.

Two delivery modes:

1. **Precomputed snapshots** — `data/realdina_snapshots.json` (built by
   `scripts/precompute_realdina_snapshots.py`). For the 5 demo students
   this is the fast path; the chat agent just looks up by user_id.
2. **Live online update** — for users not in the precomputed set, the
   service maintains an in-memory per-user alpha vector and updates it
   with each observed response using the same Bayesian-style step as
   `RealDINAAdapter.predict_proba`. Mastery starts at the global prior
   derived from the demo students.

The service is *read-mostly*; writes happen on `record_response()`.
There is no DB persistence yet — Day 9 will sync to `dina_states` table
via `state_repository`.
"""
from __future__ import annotations

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


_DEFAULT_SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "realdina_snapshots.json"
)
_DEFAULT_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "seed_extended.json"
)

_MIN_MASTERY = 0.05
_MAX_MASTERY = 0.95
_PRIOR_MASTERY = 0.5
_DEFAULT_BAYES_STEP = 0.4


class RealDINAService:
    """Cached per-user DINA mastery snapshots + online update path."""

    def __init__(
        self,
        snapshot_path: Optional[Path] = None,
        seed_path: Optional[Path] = None,
        bayes_step: float = _DEFAULT_BAYES_STEP,
    ) -> None:
        self.snapshot_path = snapshot_path or _DEFAULT_SNAPSHOT_PATH
        self.seed_path = seed_path or _DEFAULT_SEED_PATH
        self.bayes_step = bayes_step

        # user_id -> {kp_id: mastery}; populated at load time.
        self._snapshots: dict[str, dict[str, float]] = {}
        # All kp_ids that appear in any snapshot — used as the global prior set.
        self._kp_universe: list[str] = []
        # Meta info (fit hash, version) carried over from precompute step.
        self._meta: dict[str, Any] = {}
        # Online state for unseen users.
        self._online: dict[str, dict[str, float]] = {}
        self._lock = threading.Lock()

        self._load()

    # ------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------
    def _load(self) -> None:
        if self.snapshot_path.exists():
            try:
                payload = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
                self._snapshots = {
                    str(uid): {str(kp): float(v) for kp, v in (mast or {}).items()}
                    for uid, mast in payload.get("snapshots", {}).items()
                }
                self._meta = payload.get("_meta", {})
                self._kp_universe = sorted(
                    {kp for mast in self._snapshots.values() for kp in mast}
                )
                logger.info(
                    "[RealDINAService] loaded %d snapshots covering %d KPs from %s",
                    len(self._snapshots),
                    len(self._kp_universe),
                    self.snapshot_path,
                )
                return
            except (json.JSONDecodeError, OSError, ValueError) as exc:
                logger.warning(
                    "[RealDINAService] failed to load %s (%s), falling back to seed",
                    self.snapshot_path, exc,
                )

        # Fallback: synthesize snapshots from seed_extended.json mastery bias.
        # This keeps demos functional without running the offline precompute
        # script; numbers are approximate but plausible for the 5 demo students.
        self._snapshots = self._synthesize_from_seed()
        self._kp_universe = sorted(
            {kp for mast in self._snapshots.values() for kp in mast}
        )
        self._meta = {"source": "seed_synthesis", "version": "fallback-v1"}
        logger.info(
            "[RealDINAService] synthesized %d snapshots from %s",
            len(self._snapshots), self.seed_path,
        )

    def _synthesize_from_seed(self) -> dict[str, dict[str, float]]:
        if not self.seed_path.exists():
            return {}
        try:
            data = json.loads(self.seed_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("[RealDINAService] cannot read seed: %s", exc)
            return {}

        kp_difficulty = {
            str(kp["id"]): int(kp.get("difficulty", 2))
            for kp in data.get("knowledge_points", [])
        }
        recipe = data.get("assessment_recipe", {}).get("students", {})

        snapshots: dict[str, dict[str, float]] = {}
        for user_id, cfg in recipe.items():
            bias = float(cfg.get("mastery_bias", 0.5))
            mast: dict[str, float] = {}
            for kp_id, diff in kp_difficulty.items():
                mastery = bias - 0.05 * (diff - 1) + 0.02 * (hash(kp_id + user_id) % 3 - 1)
                mast[kp_id] = max(_MIN_MASTERY, min(_MAX_MASTERY, round(mastery, 3)))
            snapshots[user_id] = mast
        return snapshots

    # ------------------------------------------------------------
    # Read interface
    # ------------------------------------------------------------
    @property
    def known_users(self) -> list[str]:
        return sorted(self._snapshots.keys())

    @property
    def kp_universe(self) -> list[str]:
        return list(self._kp_universe)

    @property
    def meta(self) -> dict[str, Any]:
        return dict(self._meta)

    def snapshot_for(self, user_id: str) -> dict[str, float]:
        """Return {kp_id: mastery} for a known user, or merge precomputed + online for new users."""
        uid = str(user_id)
        with self._lock:
            base = dict(self._snapshots.get(uid, {}))
            online = self._online.get(uid, {})
            # Online updates override the precomputed snapshot for the same KP.
            base.update(online)
        return base

    def mastery(self, user_id: str, kp_id: str) -> float:
        """Single-KP lookup with prior fallback."""
        snap = self.snapshot_for(user_id)
        if kp_id in snap:
            return float(snap[kp_id])
        return _PRIOR_MASTERY

    def top_strengths(self, user_id: str, k: int = 3) -> list[tuple[str, float]]:
        """Top-k KPs ranked by mastery for the user."""
        snap = self.snapshot_for(user_id)
        if not snap:
            return []
        return sorted(snap.items(), key=lambda x: -x[1])[:k]

    def top_weaknesses(self, user_id: str, k: int = 3) -> list[tuple[str, float]]:
        """Bottom-k KPs by mastery — useful for "recommend next practice"."""
        snap = self.snapshot_for(user_id)
        if not snap:
            return []
        return sorted(snap.items(), key=lambda x: x[1])[:k]

    # ------------------------------------------------------------
    # Write interface (online update for unseen users)
    # ------------------------------------------------------------
    def record_response(
        self,
        user_id: str,
        kp_ids: list[str],
        correct: bool,
    ) -> dict[str, float]:
        """Update the running alpha estimate after observing a response.

        Mirrors the online step in `RealDINAAdapter.predict_proba`: pull each
        tapped skill toward the observed correctness by `bayes_step`. Returns
        the user's updated snapshot.
        """
        if not kp_ids:
            return self.snapshot_for(user_id)
        uid = str(user_id)
        target = float(int(correct))
        with self._lock:
            current = dict(self._snapshots.get(uid, {}))
            online = self._online.setdefault(uid, {})
            for kp in kp_ids:
                kp_str = str(kp)
                prior = online.get(kp_str, current.get(kp_str, _PRIOR_MASTERY))
                updated = (1.0 - self.bayes_step) * prior + self.bayes_step * target
                online[kp_str] = max(_MIN_MASTERY, min(_MAX_MASTERY, updated))
            merged = dict(current)
            merged.update(online)
        return merged


# ============================================================
# Singleton
# ============================================================
@lru_cache(maxsize=1)
def get_realdina_service() -> RealDINAService:
    return RealDINAService()


def reset_realdina_service() -> None:
    """Testing hook: clear the lru cache."""
    get_realdina_service.cache_clear()
