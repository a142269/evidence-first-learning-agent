"""Shared validation and file handling for the human-eval CLI.

No command entry point lives here: the five modules next to this file parse
arguments, call these helpers and turn a ``PacketError`` code into exit 2.
Every artefact stays under ``output/`` and every write refuses to overwrite.
"""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.ablation_report import ARMS, RUBRICS
from backend.app.evaluation.human_agreement import (
    EVALUATOR_VERSION,
    canonical_digest,
    find_leaked_keys,
    score_completeness,
)

ROLES = ("a", "b")
DATASET_PATH = "evals/ablation_tasks_v1.jsonl"
PACKET_NAME = "human-eval-packet-{role}.json"
MANIFEST_NAME = "human-eval-manifest.json"
MAPPING_NAME = "human-eval-mapping.json"
ALIGNED_NAME = "human-eval-aligned-items.json"
ADJUDICATION_PACKET_NAME = "human-eval-adjudication-packet.json"
REVIEWED_NAME = "human-eval-reviewed-runs.jsonl"
ADJUDICATED_NAME = "human-eval-adjudicated-runs.jsonl"
REPORT_NAME = "human-eval-agreement-report.json"
SUMMARY_JSON_NAME = "human-eval-summary.json"
SUMMARY_MD_NAME = "human-eval-summary.md"
PRIVATE_ARTEFACTS = tuple(sorted({
    MANIFEST_NAME, MAPPING_NAME, ALIGNED_NAME, REPORT_NAME, REVIEWED_NAME, ADJUDICATED_NAME,
    ADJUDICATION_PACKET_NAME, SUMMARY_JSON_NAME, SUMMARY_MD_NAME,
    *[PACKET_NAME.format(role=role) for role in ROLES],
}))
ITEM_FIELDS = ("blind_id", "question", "evidence", "package", "scores", "notes")
MANIFEST_KEYS = ("generator_version", "split", "item_count", "dataset", "source_dataset_sha256", "runs_sha256",
                 "evidence_index_sha256", "permutation_sha256", "packet_sha256", "created_at")


class PacketError(Exception):
    """A validation failure named by the protocol error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def dataset_path() -> Path:
    return ROOT / DATASET_PATH


def private_dir(value: Path) -> Path:
    directory = Path(value).resolve()
    if not directory.is_relative_to((ROOT / "output").resolve()):
        raise PacketError("OUTPUT_OUTSIDE_PRIVATE_ROOT", "review materials must remain under output")
    if not directory.is_dir():
        raise PacketError("RUN_DIR_MISSING", "no such run directory")
    return directory


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PacketError("ARTEFACT_UNREADABLE", f"{path.name} is missing or not valid JSON") from None


def read_jsonl(path: Path) -> list:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise PacketError("ARTEFACT_UNREADABLE", f"{path.name} is missing") from None
    return [json.loads(line) for line in lines if line.strip()]


def write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        raise PacketError("ARTEFACT_EXISTS", f"{path.name} already exists; preserve existing work") from None


def write_text(path: Path, payload: str) -> None:
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        raise PacketError("ARTEFACT_EXISTS", f"{path.name} already exists; preserve existing work") from None


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError:
        raise PacketError("ARTEFACT_EXISTS", f"{path.name} already exists; preserve existing work") from None


def require_new_artefacts(directory: Path) -> None:
    existing = [name for name in PRIVATE_ARTEFACTS if (directory / name).exists()]
    if existing:
        raise PacketError("ARTEFACT_EXISTS", "already present: " + ", ".join(sorted(existing)))


def cases_by_split(split: str) -> list:
    rows = read_jsonl(dataset_path())
    selected = [row for row in rows if row.get("split") == split]
    if not selected:
        raise PacketError("DATASET_SPLIT_EMPTY", f"no {split} cases in {DATASET_PATH}")
    return selected


def input_state(directory: Path, split: str) -> tuple:
    """The exact inputs the manifest digests, so a later change is detectable."""
    cases = cases_by_split(split)
    known = {row["id"] for row in cases}
    runs = [row for row in read_jsonl(directory / "runs.jsonl") if row.get("case_id") in known]
    snapshots = read_jsonl(directory / "evidence.jsonl")
    return cases, runs, snapshots


def source_digests(cases: Sequence[Mapping[str, Any]], runs: Sequence[Mapping[str, Any]],
                   evidence: Sequence[Mapping[str, Any]]) -> dict:
    return {"source_dataset_sha256": canonical_digest(list(cases)),
            "runs_sha256": canonical_digest(list(runs)),
            "evidence_index_sha256": canonical_digest(list(evidence))}


def check_evidence_snapshots(runs: Sequence[Mapping[str, Any]],
                             snapshots: Sequence[Mapping[str, Any]]) -> dict:
    evidence = {row["case_id"]: row for row in snapshots}
    if len(evidence) != len(snapshots):
        raise PacketError("EVIDENCE_DUPLICATE", "duplicate evidence snapshots")
    for row in runs:
        if not row.get("completed"):
            continue
        snapshot = evidence.get(row.get("case_id"))
        if not snapshot or "evidence" not in snapshot:
            raise PacketError("EVIDENCE_MISSING", "completed run is missing its evidence snapshot")
        if canonical_digest(snapshot["evidence"]) != snapshot.get("sha256"):
            raise PacketError("EVIDENCE_TAMPERED", "evidence snapshot does not match its own digest")
        if canonical_digest(snapshot["evidence"]) != row.get("evidence_sha256"):
            raise PacketError("EVIDENCE_TAMPERED", "evidence snapshot does not match the run digest")
    return evidence


def shuffled(randomizer: random.SystemRandom, rows: Sequence[Any]) -> list:
    order = list(rows)
    randomizer.shuffle(order)
    return order


def distinct_permutations(randomizer: random.SystemRandom, rows: Sequence[Mapping[str, Any]]) -> tuple:
    """Two orders that do not coincide, so neither reviewer can anchor on item numbers."""
    keys = [(row["case_id"], row["arm"]) for row in rows]
    first = shuffled(randomizer, rows)
    second = shuffled(randomizer, rows)
    for _ in range(8):
        if [(row["case_id"], row["arm"]) for row in second] != keys:
            break
        second = shuffled(randomizer, rows)
    return first, second


def packet_item(role: str, index: int, question: str, evidence: Any, package: Any) -> dict:
    return {"blind_id": f"{role}-{index:03d}", "question": question, "evidence": evidence, "package": package,
            "scores": dict.fromkeys(RUBRICS), "notes": ""}


def mapping_row(role: str, item: Mapping[str, Any], case_id: str, arm: str, evidence_sha256: str) -> dict:
    return {"reviewer": role, "blind_id": item["blind_id"], "case_id": case_id, "arm": arm,
            "evidence_sha256": evidence_sha256, "package_sha256": canonical_digest(item["package"]),
            "question_sha256": canonical_digest(item["question"])}


def permutation_digest(blind_ids: Sequence[str]) -> str:
    return canonical_digest(list(blind_ids))


def frozen_packet(items: Sequence[Mapping[str, Any]]) -> list:
    """The part of a packet reviewers must not touch: ids, question, evidence, package.

    Scores and notes are filled in by the reviewers, so they are excluded from
    the manifest digest; everything else is covered by it.
    """
    return [{"blind_id": item["blind_id"], "question_sha256": canonical_digest(item["question"]),
             "evidence_sha256": canonical_digest(item["evidence"]),
             "package_sha256": canonical_digest(item["package"])} for item in items]


def check_packet_leaks(items: Sequence[Mapping[str, Any]]) -> None:
    for item in items:
        leaked = find_leaked_keys(item)
        if leaked:
            raise PacketError("ANSWER_LEAK", f"packet item {item.get('blind_id')} exposes "
                                             + ", ".join(leaked))


def score_state(scores: Any, blind_id: str) -> str:
    if not isinstance(scores, dict):
        raise PacketError("SCORE_TYPE", f"{blind_id} scores must be an object")
    if set(scores) != set(RUBRICS):
        raise PacketError("SCORE_TYPE", f"{blind_id} must carry exactly the rubric keys")
    try:
        return score_completeness(scores, RUBRICS)
    except ValueError as error:
        raise PacketError("SCORE_TYPE", f"{blind_id}: {error}") from None


def load_artefacts(directory: Path) -> tuple:
    manifest = read_json(directory / MANIFEST_NAME)
    mapping = read_json(directory / MAPPING_NAME)
    packets = {role: read_json(directory / PACKET_NAME.format(role=role)) for role in ROLES}
    if not isinstance(manifest, dict):
        raise PacketError("MANIFEST_INVALID", "manifest must be an object")
    for key in MANIFEST_KEYS:
        if key not in manifest:
            raise PacketError("MANIFEST_INVALID", f"manifest is missing {key}")
    if not isinstance(manifest["permutation_sha256"], dict) or not isinstance(manifest["packet_sha256"], dict):
        raise PacketError("MANIFEST_INVALID", "manifest digest blocks must be objects")
    if not isinstance(mapping, list) or not mapping:
        raise PacketError("MAPPING_INVALID", "mapping must be a non-empty list")
    if any(not isinstance(row, dict) or not isinstance(row.get("reviewer"), str)
           or not isinstance(row.get("blind_id"), str) for row in mapping):
        raise PacketError("MAPPING_INVALID", "mapping rows need a reviewer and a blind id")
    for role in ROLES:
        if not isinstance(packets[role], list) or not packets[role]:
            raise PacketError("PACKET_INVALID", f"packet {role} must be a non-empty list")
    return manifest, mapping, packets


def stale_inputs(directory: Path, manifest: Mapping[str, Any]) -> list:
    try:
        cases, runs, snapshots = input_state(directory, manifest["split"])
    except PacketError:
        return ["runs.jsonl or evidence.jsonl"]
    current = source_digests(cases, runs, snapshots)
    return [key for key, value in current.items() if manifest.get(key) != value]


def align_packets(directory: Path, manifest: Mapping[str, Any], mapping: Sequence[Mapping[str, Any]],
                  packets: Mapping[str, Sequence[Mapping[str, Any]]], *, require_reviewed: bool) -> list:
    """Run every runtime gate and return one aligned row per (case, arm) under review."""
    cases = {row["id"]: row for row in cases_by_split(manifest["split"])}
    _, runs, _ = input_state(directory, manifest["split"])
    runs_by_key = {}
    for row in runs:
        key = (row.get("case_id"), row.get("arm"))
        if key in runs_by_key:
            raise PacketError("RUNS_INVALID", "duplicate run for the same case and arm")
        runs_by_key[key] = row
    linked_by_key = {}
    for row in mapping:
        key = (row["reviewer"], row["blind_id"])
        if key in linked_by_key:
            raise PacketError("MAPPING_INVALID", "mapping rows must be unique per reviewer and blind id")
        linked_by_key[key] = row
    aligned = {}
    for role in ROLES:
        packet = packets[role]
        if any(not isinstance(item, dict) or set(item) != set(ITEM_FIELDS) for item in packet):
            raise PacketError("PACKET_INVALID", f"packet {role} items must carry exactly {list(ITEM_FIELDS)}")
        ids = [item["blind_id"] for item in packet]
        if not all(str(value).startswith(f"{role}-") for value in ids):
            raise PacketError("NAMESPACE_MISMATCH", f"packet {role} has ids outside the {role}- namespace")
        if any(item["blind_id"] != f"{role}-{position:03d}" for position, item in enumerate(packet, 1)):
            raise PacketError("NAMESPACE_MISMATCH", f"packet {role} blind ids must run {role}-001 upwards")
        if permutation_digest(ids) != manifest["permutation_sha256"].get(role):
            raise PacketError("PACKET_TAMPERED", f"packet {role} order no longer matches the manifest")
        if canonical_digest(frozen_packet(packet)) != manifest["packet_sha256"].get(role):
            raise PacketError("PACKET_TAMPERED", f"packet {role} content no longer matches the manifest")
        check_packet_leaks(packet)
        for item in packet:
            linked = linked_by_key.get((role, item["blind_id"]))
            if linked is None:
                raise PacketError("NAMESPACE_MISMATCH", f"{item['blind_id']} is not in the mapping")
            run = runs_by_key.get((linked["case_id"], linked["arm"]))
            if run is None:
                raise PacketError("RUNS_INVALID", "mapping points at a run that no longer exists")
            package = run.get("result", {}).get("package")
            if item["package"] != package or canonical_digest(package) != linked["package_sha256"]:
                raise PacketError("PACKET_TAMPERED", f"{item['blind_id']} package does not match the run")
            if run.get("evidence_sha256") != linked["evidence_sha256"] or \
                    canonical_digest(item["evidence"]) != run.get("evidence_sha256"):
                raise PacketError("PACKET_TAMPERED", f"{item['blind_id']} evidence does not match the run")
            question = cases.get(linked["case_id"], {}).get("question")
            if item["question"] != question or canonical_digest(question) != linked.get("question_sha256"):
                raise PacketError("PACKET_TAMPERED", f"{item['blind_id']} question does not match the dataset")
            score_state(item["scores"], item["blind_id"])
            row = aligned.setdefault((linked["case_id"], linked["arm"]),
                                     {"case_id": linked["case_id"], "arm": linked["arm"], "judgements": {},
                                      "blind_id_a": None, "blind_id_b": None})
            row[f"blind_id_{role}"] = item["blind_id"]
            row["judgements"][role] = dict(item["scores"])
    if len(aligned) != manifest["item_count"]:
        raise PacketError("PACKET_INVALID", "packet item count does not match the manifest")
    orders = {role: sorted((row[f"blind_id_{role}"], (row["case_id"], row["arm"])) for row in aligned.values())
              for role in ROLES}
    if [pair[1] for pair in orders["a"]] == [pair[1] for pair in orders["b"]]:
        raise PacketError("NAMESPACE_MISMATCH", "both reviewers were handed the same item order")
    rows = [aligned[key] for key in sorted(aligned)]
    if require_reviewed:
        for row in rows:
            first, second = row["judgements"]["a"], row["judgements"]["b"]
            if {metric for metric in RUBRICS if first.get(metric) is None} != \
                    {metric for metric in RUBRICS if second.get(metric) is None}:
                raise PacketError("COVERAGE_INCOMPLETE",
                                  f"{row['case_id']}/{row['arm']} was filled asymmetrically")
        if not any(value is not None for row in rows for role in ROLES
                   for value in row["judgements"][role].values()):
            raise PacketError("COVERAGE_INCOMPLETE", "neither packet carries any judgement yet")
    return rows


def disputed_metrics(item: Mapping[str, Any]) -> list:
    first, second = item["judgements"]["a"], item["judgements"]["b"]
    return [metric for metric in RUBRICS if first.get(metric) is not None and second.get(metric) is not None
            and first[metric] != second[metric]]


def item_payload(packets: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict:
    return {item["blind_id"]: item for role in ROLES for item in packets[role]}


def adjudication_packet(aligned: Sequence[Mapping[str, Any]], items: Mapping[str, Mapping[str, Any]]) -> list:
    """Disputed items for a third reviewer: no arm, no case id, no earlier judgement."""
    output = []
    for row in aligned:
        disputes = disputed_metrics(row)
        if not disputes:
            continue
        source = items[row["blind_id_a"]]
        output.append({"blind_id": row["blind_id_a"], "question": source["question"], "package": source["package"],
                       "evidence": source["evidence"], "disputed_metrics": disputes,
                       "scores": dict.fromkeys(RUBRICS), "notes": ""})
    return output


def validate_adjudication_scores(scores: Any, blind_id: str) -> dict:
    if not isinstance(scores, dict) or set(scores) != set(RUBRICS):
        raise PacketError("SCORE_TYPE", f"{blind_id} adjudication must carry exactly the rubric keys")
    if any(value is not None and type(value) is not bool for value in scores.values()):
        raise PacketError("SCORE_TYPE", f"{blind_id} adjudication values must be boolean or null")
    return dict(scores)


def load_adjudications(directory: Path, filename: str, aligned: Sequence[Mapping[str, Any]], adjudicator: str,
                       reviewers: Mapping[str, str]) -> dict:
    if Path(filename).name != filename:
        raise PacketError("ADJUDICATION_FILENAME", "adjudications must be a local filename")
    if not adjudicator.strip() or adjudicator.strip() in {name.strip() for name in reviewers.values()}:
        raise PacketError("REVIEWER_IDS_INVALID", "the adjudicator must be independent of both reviewers")
    disputes = {(row["case_id"], row["arm"]) for row in aligned if disputed_metrics(row)}
    entries = read_json(directory / filename)
    if not isinstance(entries, list):
        raise PacketError("ADJUDICATION_INVALID", "adjudications must be a list")
    by_blind_id = {row["blind_id_a"]: row for row in aligned}
    decisions = {}
    for entry in entries:
        row = by_blind_id.get(entry["blind_id"]) if isinstance(entry, dict) else None
        if row is None:
            raise PacketError("ADJUDICATION_INVALID", "unknown adjudication blind id")
        if row["blind_id_a"] in decisions:
            raise PacketError("ADJUDICATION_INVALID", "duplicate adjudication for the same item")
        if (row["case_id"], row["arm"]) not in disputes:
            raise PacketError("ADJUDICATION_REQUIRES_DISPUTE", f"{row['blind_id_a']} has no disagreement to settle")
        scores = validate_adjudication_scores(entry.get("scores"), row["blind_id_a"])
        decisions[row["blind_id_a"]] = {"reviewer": adjudicator.strip(), **scores}
    return decisions


def reviewer_names(reviewer_a: str, reviewer_b: str) -> Mapping[str, str]:
    if not reviewer_a.strip() or not reviewer_b.strip() or reviewer_a.strip() == reviewer_b.strip():
        raise PacketError("REVIEWER_IDS_INVALID", "two distinct reviewer names required")
    return {"a": reviewer_a.strip(), "b": reviewer_b.strip()}


def attach_reviews(runs: Sequence[Mapping[str, Any]], aligned: Sequence[Mapping[str, Any]],
                   reviewers: Mapping[str, str], decisions: Mapping[str, Mapping[str, Any]]) -> list:
    by_key = {(row["case_id"], row["arm"]): row for row in aligned}
    rows = []
    for run in runs:
        row = dict(run)
        linked = by_key.get((row.get("case_id"), row.get("arm")))
        if linked is None:
            raise PacketError("RUNS_INVALID", "a run has no aligned review item")
        if not row.get("completed"):
            raise PacketError("RUNS_INVALID", "only completed runs can carry reviews")
        row["reviews"] = [{"reviewer": reviewers[role], **linked["judgements"][role]} for role in ROLES]
        decision = decisions.get(linked["blind_id_a"])
        if decision is not None:
            row["adjudication"] = decision
        rows.append(row)
    return rows


def merge_aligned_with_adjudication(aligned: Sequence[Mapping[str, Any]],
                                    decisions: Mapping[str, Mapping[str, Any]]) -> list:
    rows = []
    for row in aligned:
        updated = dict(row)
        updated["adjudication"] = decisions.get(row["blind_id_a"])
        rows.append(updated)
    return rows


__all__ = ["ARMS", "ROLES", "RUBRICS", "EVALUATOR_VERSION", "PacketError", "dataset_path", "private_dir",
           "read_json", "read_jsonl", "write_json", "write_jsonl", "require_new_artefacts", "cases_by_split",
           "input_state", "source_digests", "check_evidence_snapshots", "shuffled", "distinct_permutations",
           "packet_item", "mapping_row", "permutation_digest", "frozen_packet", "check_packet_leaks", "score_state",
           "load_artefacts", "stale_inputs", "align_packets", "disputed_metrics", "adjudication_packet",
           "load_adjudications", "reviewer_names", "attach_reviews", "item_payload", "write_text",
           "merge_aligned_with_adjudication", "find_leaked_keys"]
