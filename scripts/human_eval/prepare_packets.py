"""Create two independently ordered blind-review packets for two human reviewers."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import random
from pathlib import Path
import sys
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.ablation_report import ARMS, summarize_ablation
from backend.app.evaluation.human_agreement import canonical_digest
from scripts.human_eval import common


def build_payloads(cases: Sequence[dict], runs: Sequence[dict], evidence: dict) -> tuple:
    by_id = {row["id"]: row for row in cases}
    reviewable = [row for row in runs if row.get("completed")]
    randomizer = random.SystemRandom()
    orders = dict(zip(common.ROLES, common.distinct_permutations(randomizer, reviewable)))
    packets = {}
    mapping = []
    for role in common.ROLES:
        items = []
        for index, run in enumerate(orders[role], 1):
            item = common.packet_item(role, index, by_id[run["case_id"]]["question"],
                                      evidence[run["case_id"]]["evidence"], run["result"]["package"])
            items.append(item)
            mapping.append(common.mapping_row(role, item, run["case_id"], run["arm"], run["evidence_sha256"]))
        common.check_packet_leaks(items)
        packets[role] = items
    manifest = {
        "generator_version": common.EVALUATOR_VERSION,
        "split": cases[0]["split"],
        "item_count": len(packets["a"]),
        "dataset": common.DATASET_PATH,
        "permutation_sha256": {role: common.permutation_digest([item["blind_id"] for item in packets[role]])
                               for role in common.ROLES},
        "packet_sha256": {role: canonical_digest(common.frozen_packet(packets[role])) for role in common.ROLES},
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return packets, mapping, manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--split", choices=("dev", "holdout"), default="holdout")
    args = parser.parse_args(argv)
    try:
        directory = common.private_dir(args.run_dir)
        common.require_new_artefacts(directory)
        cases = common.cases_by_split(args.split)
        _, runs, snapshots = common.input_state(directory, args.split)
        report = summarize_ablation(cases, runs)
        if any(report["arms"][arm]["run_count"] != len(cases) for arm in ARMS):
            raise common.PacketError("RUNS_INCOMPLETE", "all runs of the split must finish before blinding")
        evidence = common.check_evidence_snapshots(runs, snapshots)
        packets, mapping, manifest = build_payloads(cases, runs, evidence)
        manifest.update(common.source_digests(cases, runs, snapshots))
        for role in common.ROLES:
            blinded = [(row["case_id"], row["arm"]) for row in mapping if row["reviewer"] == role]
            if len(set(blinded)) != len(blinded):
                raise common.PacketError("RUNS_INVALID", f"packet {role} blinds a case and arm pair twice")
        distinct = {(row["case_id"], row["arm"]) for row in mapping}
        if len(mapping) != 2 * len(runs) or distinct != {(run["case_id"], run["arm"]) for run in runs}:
            raise common.PacketError("RUNS_INVALID", "blinded items must cover every run of the split exactly twice")
        for role in common.ROLES:
            common.write_json(directory / common.PACKET_NAME.format(role=role), packets[role])
        common.write_json(directory / common.MAPPING_NAME, mapping)
        common.write_json(directory / common.MANIFEST_NAME, manifest)
    except common.PacketError as error:
        parser.exit(2, f"{error.code}: {error.message}\n")
    print(json.dumps({"item_count": manifest["item_count"], "reviewers_required": 2,
                      "run_dir": directory.name}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
