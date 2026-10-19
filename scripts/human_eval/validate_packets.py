"""Validate blind packets and their provenance; writes nothing, ever."""
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--require-reviewed", action="store_true",
                        help="also demand that both reviewers filled the same items")
    args = parser.parse_args(argv)
    try:
        directory = common.private_dir(args.run_dir)
        manifest, mapping, packets = common.load_artefacts(directory)
        changed = common.stale_inputs(directory, manifest)
        if changed:
            raise common.PacketError("STALE_SOURCE",
                                     "inputs changed after the packets were generated: " + ", ".join(changed))
        rows = common.align_packets(directory, manifest, mapping, packets,
                                    require_reviewed=args.require_reviewed)
    except common.PacketError as error:
        parser.exit(2, f"{error.code}: {error.message}\n")
    print(json.dumps({"status": "valid", "item_count": len(rows),
                      "reviewed": args.require_reviewed,
                      "split": manifest["split"],
                      "scored_items": sum(1 for row in rows
                                          if all(value is not None for value in row["judgements"]["a"].values()))},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
