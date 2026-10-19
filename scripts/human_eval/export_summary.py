"""Export the publishable, anonymised agreement summary from an agreement report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.human_eval import common

PRIVATE_KEYS = ("case_id", "arm", "notes", "notes_a", "notes_b", "adjudicator", "disputed_metrics")


def redact(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: ("anonymous" if key == "reviewer" else redact(nested))
                for key, nested in value.items() if key not in PRIVATE_KEYS}
    if isinstance(value, (list, tuple)):
        return [redact(nested) for nested in value]
    return value


def show(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, (list, tuple)):
        return f"{value[0]:.4f} to {value[1]:.4f}"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def markdown(summary: Mapping[str, Any]) -> str:
    lines = [f"# Human agreement summary ({summary['evaluator_version']})", "",
             f"- evaluation mode: `{summary['evaluation_mode']}`",
             f"- review items: {summary['item_count']}; review_complete: {show(summary['review_complete'])}",
             f"- bootstrap: seed {summary['randomness']['bootstrap_seed']}, "
             f"{summary['randomness']['bootstrap_replicates']} replicates, percentile 2.5/97.5", "",
             "| rubric | paired n | kappa | kappa 95% CI | po | po 95% CI | prevalence | bias | status | reason |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for metric, block in summary["per_metric"].items():
        lines.append("| " + " | ".join([metric, show(block["n"]), show(block["kappa"]), show(block["kappa_ci_95"]),
                                        show(block["po"]), show(block["po_ci_95"]), show(block["prevalence"]),
                                        show(block["bias"]), block["status"], show(block["reason"])]) + " |")
    lines += ["", "## Disagreements by rubric", ""]
    counts: dict[str, int] = {}
    for entry in summary["disagreements"]:
        counts[entry["metric"]] = counts.get(entry["metric"], 0) + 1
    lines += [f"- {metric}: {counts.get(metric, 0)}" for metric in summary["per_metric"]]
    lines += ["", "## Quality pass rate by arm", "",
              "*null means the review is not complete, not that the arm failed.*"]
    lines += [f"- {arm}: {show(rate)}" for arm, rate in summary["quality_pass_rate_by_arm"].items()]
    lines += ["", "## Limitations", ""]
    lines += [f"- {item}" for item in summary["limitations"]]
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        directory = common.private_dir(args.run_dir)
        report = common.read_json(directory / common.REPORT_NAME)
        if report.get("evaluation_mode") != "human_agreement_offline":
            raise common.PacketError("REPORT_INVALID", "agreement report is missing its evaluation mode")
        summary = redact(report)
        summary["reviewer_ids"] = ["anonymous", "anonymous"]
        common.write_json(directory / common.SUMMARY_JSON_NAME, summary)
        common.write_text(directory / common.SUMMARY_MD_NAME, markdown(summary))
    except common.PacketError as error:
        parser.exit(2, f"{error.code}: {error.message}\n")
    print(json.dumps({"metrics": len(summary["per_metric"]), "disagreements": len(summary["disagreements"]),
                      "artefacts": [common.SUMMARY_JSON_NAME, common.SUMMARY_MD_NAME]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
