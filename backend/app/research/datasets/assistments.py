"""
ASSISTments 2009-2010 Skill Builder Dataset Loader

Downloads (with caching), parses, and prepares data for cognitive diagnosis benchmark.
Data source: USTC mirror of official ASSISTments 2009 skill builder corrected.

Key fields used:
    - user_id: student identifier
    - skill_id / skill_name: knowledge component
    - correct: binary correctness (0/1)
    - order_id: temporal ordering

Output format:
    - responses: dict[str(user_id), dict[str(item_id), int(0/1)]]
    - q_matrix: numpy.ndarray shape (n_items, n_skills)
    - sequences: list[list[dict]] — per-student ordered interaction sequences (for DKT)
    - item_skill_map: dict[str(item_id), str(skill_id)]

References:
    - Feng et al. (2009) "Addressing the Assessment Challenge with an
      Online System that Tutors as it Assesses"
    - Piech et al. (2015) "Deep Knowledge Tracing"
"""
from __future__ import annotations

import logging
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Constants
_DOWNLOAD_URL = (
    "http://base.ustc.edu.cn/data/ASSISTment/2009_skill_builder_data_corrected.zip"
)
_FILE_NAME = "skill_builder_data_corrected.csv"

# Default cache directory: data/benchmarks/ relative to project root
_DEFAULT_CACHE_DIR = os.path.join("data", "benchmarks")


def _cache_dir(override: Optional[str] = None) -> Path:
    """Resolve cache directory for benchmark datasets."""
    if override:
        return Path(override)
    # Walk up from this file to find project root (has pyproject.toml)
    here = Path(__file__).resolve().parent
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent / _DEFAULT_CACHE_DIR
    return here.parent.parent.parent / _DEFAULT_CACHE_DIR


def download_assistments(cache_dir: Optional[str] = None) -> Path:
    """Download ASSISTments 2009 skill builder dataset if not cached.

    Args:
        cache_dir: Override cache directory. Defaults to data/benchmarks/.

    Returns:
        Path to the extracted CSV file.

    Raises:
        RuntimeError: If download fails after retry.
    """
    cache = _cache_dir(cache_dir)
    csv_path = cache / _FILE_NAME
    zip_path = cache / "assist2009.zip"

    # Already cached
    if csv_path.exists() and csv_path.stat().st_size > 1_000_000:
        logger.info("[ASSISTments] Using cached: %s (%d bytes)",
                    csv_path, csv_path.stat().st_size)
        return csv_path

    cache.mkdir(parents=True, exist_ok=True)

    import requests
    logger.info("[ASSISTments] Downloading from %s ...", _DOWNLOAD_URL)
    resp = requests.get(_DOWNLOAD_URL, timeout=180, stream=True)
    resp.raise_for_status()

    with open(zip_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)

    logger.info("[ASSISTments] Saved zip (%d bytes), extracting...", zip_path.stat().st_size)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(cache)

    if not csv_path.exists():
        raise RuntimeError(
            f"Expected {_FILE_NAME} after extraction, but not found in {cache}"
        )
    logger.info("[ASSISTments] Extracted: %s (%d bytes)",
                csv_path, csv_path.stat().st_size)
    return csv_path


def load_raw(csv_path: Optional[str] = None, cache_dir: Optional[str] = None) -> pd.DataFrame:
    """Load raw ASSISTments CSV into a DataFrame.

    Filters out rows with NaN skill_id (they can't be mapped to Q-matrix).

    Args:
        csv_path: Path to CSV. If None, auto-downloads.
        cache_dir: Override cache directory for auto-download.

    Returns:
        DataFrame with columns: user_id, skill_id, skill_name, correct, order_id, item_id.
    """
    if csv_path is None:
        csv_path = str(download_assistments(cache_dir))

    df = pd.read_csv(csv_path, encoding="latin-1")

    # Drop rows without skill mapping
    before = len(df)
    df = df.dropna(subset=["skill_id"]).copy()
    df["skill_id"] = df["skill_id"].astype(int).astype(str)
    df["user_id"] = df["user_id"].astype(str)
    after = len(df)
    logger.info("[ASSISTments] Loaded %d rows (dropped %d with NaN skill_id)",
                after, before - after)

    return df[["user_id", "skill_id", "skill_name", "correct", "order_id", "problem_id"]]


def prepare_benchmark_data(
    csv_path: Optional[str] = None,
    cache_dir: Optional[str] = None,
    min_interactions: int = 5,
    min_skill_freq: int = 50,
    item_granularity: str = "skill",
    min_item_freq: int = 0,
) -> Dict[str, Any]:
    """Prepare ASSISTments data in all formats needed by benchmark models.

    Applies standard preprocessing filters used in Piech et al. (2015):
    - Remove students with fewer than min_interactions
    - Remove skills with fewer than min_skill_freq occurrences

    Args:
        csv_path: Path to CSV. If None, auto-downloads.
        cache_dir: Override cache directory for auto-download.
        min_interactions: Minimum interactions per student to keep.
        min_skill_freq: Minimum skill frequency to keep.
        item_granularity: "skill" (default, 论文标准 KT 设置) — each skill is
            one item, Q-matrix is identity. "problem" — each problem is one
            item (multi-attribute Q-matrix, suitable for DINA which needs
            items spanning multiple skills).
        min_item_freq: Minimum item frequency to keep (only used when
            item_granularity="problem"). Set >0 to filter rare problems and
            control item count for DINA tractability.

    Returns:
        dict with keys:
            - "n_students": int
            - "n_skills": int
            - "n_items": int
            - "n_interactions": int
            - "responses": dict[str(student_id), dict[str(item_id), int(0/1)]]
            - "q_matrix": np.ndarray (n_items, n_skills)
            - "item_ids": list[str]
            - "skill_ids": list[str]
            - "student_ids": list[str]
            - "sequences": list[list[dict]] — per-student ordered interactions
            - "skill_names": dict[str(skill_id), str]
    """
    df = load_raw(csv_path, cache_dir)

    # Create item_id based on granularity.
    # "skill" (论文标准 KT): each skill is one item → Q-matrix is identity.
    # "problem": each problem is one item → multi-attribute Q-matrix where a
    #   problem practiced under multiple skills requires multiple attributes.
    if item_granularity == "skill":
        df["item_id"] = df["skill_id"]
    else:
        df["item_id"] = "p_" + df["problem_id"].astype(str)

    # Filter students
    student_counts = df["user_id"].value_counts()
    valid_students = set(student_counts[student_counts >= min_interactions].index)
    df = df[df["user_id"].isin(valid_students)]

    # Filter skills
    skill_counts = df["skill_id"].value_counts()
    valid_skills = set(skill_counts[skill_counts >= min_skill_freq].index)
    df = df[df["skill_id"].isin(valid_skills)]

    # Filter items by frequency (problem granularity only)
    if min_item_freq > 0:
        item_counts = df["item_id"].value_counts()
        valid_items = set(item_counts[item_counts >= min_item_freq].index)
        df = df[df["item_id"].isin(valid_items)]
        # Re-filter students who now have too few interactions
        student_counts2 = df["user_id"].value_counts()
        valid_students = set(student_counts2[student_counts2 >= min_interactions].index)
        df = df[df["user_id"].isin(valid_students)]

    # Build skill mapping (re-derive from filtered df to avoid stale skills)
    skill_ids = sorted(df["skill_id"].unique())
    skill_index = {s: i for i, s in enumerate(skill_ids)}
    skill_names = {}
    for sid in skill_ids:
        names = df[df["skill_id"] == sid]["skill_name"].dropna()
        skill_names[sid] = names.iloc[0] if len(names) > 0 else sid

    # Build item mapping
    item_ids = sorted(df["item_id"].unique())
    item_index = {item: j for j, item in enumerate(item_ids)}

    # Build Q-matrix (item x skill).
    # NOTE: the previous implementation used df.drop_duplicates("item_id")
    # which only kept the FIRST (item, skill) row per problem_id. ASSISTments-2009
    # has ~17% multi-skill problems (max 4 skills/problem) so collapsing to
    # one skill leaks 17% of the multi-skill signal. We now collect every
    # distinct (item, skill) pair the dataframe carries.
    q_matrix = np.zeros((len(item_ids), len(skill_ids)), dtype=float)
    item_skill_pairs = df[["item_id", "skill_id"]].drop_duplicates()
    for item_id, skill_id in zip(item_skill_pairs["item_id"].values, item_skill_pairs["skill_id"].values):
        if item_id in item_index and skill_id in skill_index:
            q_matrix[item_index[item_id], skill_index[skill_id]] = 1.0

    # Build responses dict: student → {item: correct} — vectorized via set_index
    df_sorted = df.sort_values(["user_id", "order_id"])
    responses: Dict[str, Dict[str, int]] = {}
    for uid, group in df_sorted.groupby("user_id", sort=False):
        responses[uid] = dict(zip(group["item_id"].values, group["correct"].values))

    # Build sequences for DKT — vectorized per group
    sequences = _build_sequences_fast(df_sorted, skill_index, len(skill_ids))

    student_ids = sorted(responses.keys())

    result = {
        "n_students": len(student_ids),
        "n_skills": len(skill_ids),
        "n_items": len(item_ids),
        "n_interactions": len(df),
        "responses": responses,
        "q_matrix": q_matrix,
        "item_ids": item_ids,
        "skill_ids": skill_ids,
        "student_ids": student_ids,
        "sequences": sequences,
        "skill_names": skill_names,
    }

    logger.info(
        "[ASSISTments] Prepared: %d students, %d skills, %d items, %d interactions",
        result["n_students"], result["n_skills"],
        result["n_items"], result["n_interactions"],
    )
    return result


def _build_sequences_fast(
    df: pd.DataFrame,
    skill_index: Dict[str, int],
    n_skills: int,
) -> List[List[Dict[str, Any]]]:
    """Build per-student time-ordered interaction sequences for DKT.

    Vectorized per-group: uses numpy advanced indexing within each group
    to build one-hot skill vectors without per-row np.zeros().
    df must already be sorted by (user_id, order_id).
    """
    sequences: List[List[Dict[str, Any]]] = []
    for uid, group in df.groupby("user_id", sort=False):
        n = len(group)
        skill_vals = group["skill_id"].values
        correct_vals = group["correct"].values
        item_vals = group["item_id"].values

        # Map skill IDs to indices
        skill_indices = np.array(
            [skill_index.get(str(s), -1) for s in skill_vals], dtype=int,
        )
        valid = skill_indices >= 0

        # Build one-hot matrix (n, n_skills)
        onehots = np.zeros((n, n_skills), dtype=float)
        rows = np.arange(n)
        onehots[rows[valid], skill_indices[valid]] = 1.0

        seq = [
            {
                "skill_onehot": onehots[t],
                "correct": int(correct_vals[t]),
                "item_id": item_vals[t],
                "skill_idx": int(skill_indices[t]) if skill_indices[t] >= 0 else -1,
            }
            for t in range(n)
        ]
        sequences.append(seq)
    return sequences
