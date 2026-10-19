"""Merge two validated blind packets into reviewed run records plus aligned review items."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.human_eval import common


def write_or_confirm(path: Path, value: object) -> None:
    """Keep already-produced material: identical content passes, a difference fails."""
    if path.exists():
        if read_back(path) != value:
            raise common.PacketError("PACKET_TAMPERED", f"{path.name} differs from the existing artefact")
        return
    common.write_json(path, value)


def read_back(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--reviewer-a", required=True)
    parser.add_argument("--reviewer-b", required=True)
    parser.add_argument("--adjudications", help="JSON filename inside the run directory")
    parser.add_argument("--adjudicator", help="independent adjudicator identifier")
    args = parser.parse_args(argv)
    try:
        if bool(args.adjudications) != bool(args.adjudicator):
            raise common.PacketError("ADJUDICATION_FILENAME", "adjudications and adjudicator go together")
        directory = common.private_dir(args.run_dir)
        reviewers = common.reviewer_names(args.reviewer_a, args.reviewer_b)
        manifest, mapping, packets = common.load_artefacts(directory)
        changed = common.stale_inputs(directory, manifest)
        if changed:
            raise common.PacketError("STALE_SOURCE",
                                     "inputs changed after the packets were generated: " + ", ".join(changed))
        rows = common.align_packets(directory, manifest, mapping, packets, require_reviewed=True)
        decisions = {}
        if args.adjudications:
            decisions = common.load_adjudications(directory, args.adjudications, rows, args.adjudicator, reviewers)
        _, runs, _ = common.input_state(directory, manifest["split"])
        reviewed = common.attach_reviews(runs, rows, reviewers, decisions)
        disputes = common.adjudication_packet(rows, common.item_payload(packets))
        write_or_confirm(directory / common.ADJUDICATION_PACKET_NAME, disputes)
        write_or_confirm(directory / common.ALIGNED_NAME,
                         {"generator_version": common.EVALUATOR_VERSION, "split": manifest["split"], "items": rows})
        common.write_jsonl(directory / (common.ADJUDICATED_NAME if decisions else common.REVIEWED_NAME), reviewed)
    except common.PacketError as error:
        parser.exit(2, f"{error.code}: {error.message}\n")
    print(json.dumps({"reviewed_runs": len(reviewed), "aligned_items": len(rows), "disputed_items": len(disputes),
                      "adjudicated": bool(decisions)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
