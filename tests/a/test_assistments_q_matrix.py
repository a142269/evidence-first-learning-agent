"""Lock the multi-skill Q-matrix fix in `backend/app/research/datasets/assistments.py`.

The original implementation called `df.drop_duplicates("item_id")` which
silently kept the first (item, skill) row per problem_id, collapsing 17%
of ASSISTments-2009's multi-skill problems into single-skill entries.
That destroyed the very signal DINA was designed to exploit and led to
AUC stuck at 0.69 on problem granularity.

After the fix (Day 7) the Q-matrix retains every distinct (item, skill)
pair the dataframe carries. This regression test asserts the fix is still
in place by constructing a tiny synthetic dataset where the multi-skill
structure is known ahead of time, monkeypatching `pd.read_csv` so we do
not depend on the 60MB cached download.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


_FAKE_ROWS = [
    # (user_id, problem_id, skill_id, skill_name, correct, order_id)
    # skill_id must be int-castable since load_raw casts via int(...).
    # u1 / u2: problem 1 taps two skills (1, 2); problem 2 taps skill 3
    ("u1", "p1", 1, "Algebra", 1, 1),
    ("u1", "p1", 2, "Bases",   1, 2),
    ("u1", "p2", 3, "Counts",  0, 3),
    ("u2", "p1", 1, "Algebra", 0, 4),
    ("u2", "p1", 2, "Bases",   0, 5),
    ("u2", "p2", 3, "Counts",  1, 6),
    ("u3", "p1", 1, "Algebra", 1, 7),
    ("u3", "p1", 2, "Bases",   0, 8),
    ("u3", "p2", 3, "Counts",  1, 9),
    ("u4", "p3", 1, "Algebra", 0, 10),
    ("u4", "p3", 1, "Algebra", 1, 11),  # repeat
    ("u4", "p3", 2, "Bases",   1, 12),  # tap second skill
    ("u4", "p2", 3, "Counts",  1, 13),
    ("u5", "p3", 1, "Algebra", 1, 14),
    ("u5", "p3", 2, "Bases",   1, 15),
    ("u5", "p2", 3, "Counts",  0, 16),
]


def _make_fake_csv(monkeypatch, tmp_path):
    """Patch pandas.read_csv inside the assistments module so prepare_benchmark_data
    consumes our hand-crafted rows instead of the real 60MB file."""
    df = pd.DataFrame(
        _FAKE_ROWS,
        columns=["user_id", "problem_id", "skill_id", "skill_name", "correct", "order_id"],
    )
    df["original_correct"] = df["correct"]  # column the loader expects

    def fake_read_csv(*args, **kwargs):
        return df.copy()

    from backend.app.research.datasets import assistments as mod
    monkeypatch.setattr(mod.pd, "read_csv", fake_read_csv)


def test_q_matrix_retains_all_skill_pairs_at_problem_granularity(monkeypatch, tmp_path):
    """The fixed loader must emit Q[problem, skill] = 1 for every distinct pair."""
    _make_fake_csv(monkeypatch, tmp_path)
    from backend.app.research.datasets.assistments import prepare_benchmark_data

    data = prepare_benchmark_data(
        csv_path=str(tmp_path / "fake.csv"),
        min_interactions=1,
        min_skill_freq=1,
        item_granularity="problem",
        min_item_freq=1,
    )

    # We expect items p_p1, p_p2, p_p3, all carrying skill_id mappings
    item_ids = data["item_ids"]
    skill_ids = data["skill_ids"]
    q = data["q_matrix"]

    # p1 should tap two skills (a, b); the OLD buggy code would only mark one
    p1_idx = item_ids.index("p_p1")
    skill_a_idx = skill_ids.index("1")
    skill_b_idx = skill_ids.index("2")
    assert q[p1_idx, skill_a_idx] == 1.0
    assert q[p1_idx, skill_b_idx] == 1.0
    # And p1's count of marked skills is exactly 2
    assert int(q[p1_idx].sum()) == 2

    # p3 should also tap two skills (a, b)
    p3_idx = item_ids.index("p_p3")
    assert int(q[p3_idx].sum()) == 2

    # p2 stays single-skill
    p2_idx = item_ids.index("p_p2")
    assert int(q[p2_idx].sum()) == 1


def test_mean_q_per_item_exceeds_one_when_multi_skill_present(monkeypatch, tmp_path):
    """Sanity check we'd have caught the bug: mean q-per-item must be > 1.0."""
    _make_fake_csv(monkeypatch, tmp_path)
    from backend.app.research.datasets.assistments import prepare_benchmark_data

    data = prepare_benchmark_data(
        csv_path=str(tmp_path / "fake.csv"),
        min_interactions=1,
        min_skill_freq=1,
        item_granularity="problem",
        min_item_freq=1,
    )
    q = data["q_matrix"]
    mean_q = float(q.sum(axis=1).mean())
    assert mean_q > 1.0, (
        f"expected mean q-per-item > 1 with multi-skill items, got {mean_q:.3f} "
        "(the drop_duplicates bug would yield exactly 1.0)"
    )


def test_skill_granularity_q_matrix_stays_identity(monkeypatch, tmp_path):
    """At skill granularity the Q-matrix must remain the (n x n) identity."""
    _make_fake_csv(monkeypatch, tmp_path)
    from backend.app.research.datasets.assistments import prepare_benchmark_data

    data = prepare_benchmark_data(
        csv_path=str(tmp_path / "fake.csv"),
        min_interactions=1,
        min_skill_freq=1,
        item_granularity="skill",
    )
    q = data["q_matrix"]
    n = data["n_skills"]
    assert q.shape == (n, n)
    np.testing.assert_array_equal(q, np.eye(n))
