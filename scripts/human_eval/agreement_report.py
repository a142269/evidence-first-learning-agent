"""Compute per-rubric agreement statistics from validated blind packets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.evaluation.ablation_report import ARMS, RUBRICS
from backend.app.evaluation.human_agreement import BOOTSTRAP_REPLICATES, build_agreement_report
from scripts.human_eval import common


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int, help="bootstrap seed, recorded in the report")
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--adjudications", help="JSON filename inside the run directory")
    parser.add_argument("--adjudicator", help="independent adjudicator identifier")
    parser.add_argument("--reviewer-a", help="only used to prove the adjudicator is independent")
    parser.add_argument("--reviewer-b", help="only used to prove the adjudicator is independent")
    args = parser.parse_args(argv)
    if args.replicates < 2:
        parser.error("replicates must be at least 2")
    if bool(args.adjudications) != bool(args.adjudicator):
        parser.error("adjudications and adjudicator go together")
    if args.adjudications and not (args.reviewer_a and args.reviewer_b):
        parser.error("both reviewer names are required to check adjudicator independence")
    try:
        directory = common.private_dir(args.run_dir)
        manifest, mapping, packets = common.load_artefacts(directory)
        changed = common.stale_inputs(directory, manifest)
        if changed:
            raise common.PacketError("STALE_SOURCE",
                                     "inputs changed after the packets were generated: " + ", ".join(changed))
        rows = common.align_packets(directory, manifest, mapping, packets, require_reviewed=True)
        stored = common.read_json(directory / common.ALIGNED_NAME)
        if stored.get("items") != rows:
            raise common.PacketError("PACKET_TAMPERED", "aligned review items no longer match the packets")
        decisions = {}
        if args.adjudications:
            reviewers = common.reviewer_names(args.reviewer_a, args.reviewer_b)
            decisions = common.load_adjudications(directory, args.adjudications, rows, args.adjudicator, reviewers)
        rows = common.merge_aligned_with_adjudication(rows, decisions)
        report = build_agreement_report(rows, RUBRICS, ARMS, seed=args.seed,
                                        inputs={key: manifest[key] for key in
                                                ("source_dataset_sha256", "runs_sha256", "evidence_index_sha256",
                                                 "permutation_sha256", "packet_sha256", "split", "dataset",
                                                 "created_at")},
                                        replicates=args.replicates)
        common.write_json(directory / common.REPORT_NAME, report)
    except common.PacketError as error:
        parser.exit(2, f"{error.code}: {error.message}\n")
    print(json.dumps({"kappa": {metric: report["per_metric"][metric]["kappa"] for metric in RUBRICS},
                      "review_complete": report["review_complete"],
                      "disagreements": len(report["disagreements"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
