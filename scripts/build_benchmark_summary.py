#!/usr/bin/env python3
"""Assemble role-B benchmark summary artifacts from verified source reports."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs" / "benchmarks"

DEFAULT_SAKT = REPORTS_DIR / "benchmark_20260623_201019.json"
DEFAULT_DKT = REPORTS_DIR / "benchmark_20260623_201927.json"
DEFAULT_DINA = REPORTS_DIR / "dina_real_20260622_153141.json"
DEFAULT_SPACED = REPORTS_DIR / "spaced_repetition_benchmark_20260624_104358.json"
DEFAULT_BLOOM = DOCS_DIR / "bloom_relabel_audit.md"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_bloom_metrics(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    exact = re.search(r"完全匹配[^\n|]*\|\s*(\d+)/(\d+)\s*=\s*\*\*(\d+(?:\.\d+)?)%", text)
    near = re.search(r"±1 层级内匹配[^\n|]*\|\s*(\d+)/(\d+)\s*=\s*\*\*(\d+(?:\.\d+)?)%", text)
    human = re.search(r"\*\*人工准确率\*\*:\s*(\d+(?:\.\d+)?)%", text)
    if not (exact and near and human):
        raise ValueError(f"Unable to extract Bloom metrics from {path}")
    return {
        "exact_match": {
            "matched": int(exact.group(1)),
            "total": int(exact.group(2)),
            "rate": float(exact.group(3)),
        },
        "within_one_level": {
            "matched": int(near.group(1)),
            "total": int(near.group(2)),
            "rate": float(near.group(3)),
        },
        "human_spot_check": {
            "matched": 16,
            "total": 20,
            "rate": float(human.group(1)),
        },
    }


def build_summary(
    *,
    label: str,
    sakt_path: Path,
    dkt_path: Path,
    dina_path: Path,
    spaced_path: Path,
    bloom_path: Path,
) -> dict:
    sakt = _load_json(sakt_path)
    dkt = _load_json(dkt_path)
    dina = _load_json(dina_path)
    spaced = _load_json(spaced_path)
    bloom = _extract_bloom_metrics(bloom_path)

    return {
        "label": label,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": {
            "sakt": str(sakt_path.relative_to(PROJECT_ROOT)),
            "dkt": str(dkt_path.relative_to(PROJECT_ROOT)),
            "real_dina": str(dina_path.relative_to(PROJECT_ROOT)),
            "spaced_repetition": str(spaced_path.relative_to(PROJECT_ROOT)),
            "bloom_audit": str(bloom_path.relative_to(PROJECT_ROOT)),
        },
        "knowledge_tracing": {
            "dataset": sakt["dataset"]["name"],
            "sakt": {
                "auc": round(sakt["results"]["sakt"]["mean_metrics"]["auc"], 4),
                "accuracy": round(sakt["results"]["sakt"]["mean_metrics"]["accuracy"], 4),
                "rmse": round(sakt["results"]["sakt"]["mean_metrics"]["rmse"], 4),
                "folds": sakt["results"]["sakt"]["n_folds"],
            },
            "dkt": {
                "auc": round(dkt["results"]["dkt"]["mean_metrics"]["auc"], 4),
                "accuracy": round(dkt["results"]["dkt"]["mean_metrics"]["accuracy"], 4),
                "rmse": round(dkt["results"]["dkt"]["mean_metrics"]["rmse"], 4),
                "folds": dkt["results"]["dkt"]["n_folds"],
            },
        },
        "cognitive_diagnosis": {
            "dataset": "ASSISTments-2009 (multi-skill remap)",
            "real_dina": {
                "auc": round(dina["models"]["dina_a"]["mean_auc"], 4),
                "accuracy": round(dina["models"]["dina_a"]["mean_accuracy"], 4),
                "rmse": round(dina["models"]["dina_a"]["mean_rmse"], 4),
                "folds": dina["data"]["n_folds"],
                "q_matrix_mean_skills": round(dina["data"]["mean_q_per_item"], 4),
                "multi_skill_ratio": round(dina["data"]["pct_multi_skill_items"], 4),
            },
        },
        "bloom_audit": bloom,
        "spaced_repetition": {
            "dataset": spaced["dataset"],
            "n_students_sampled": spaced["n_students_sampled"],
            "n_review_sequences": spaced["n_review_sequences"],
            "sm2_proxy_mae": spaced["sm2"]["actual_gap_proxy_mae"],
            "fsrs_proxy_mae": spaced["fsrs"]["actual_gap_proxy_mae"],
            "sm2_forgetting_rate": spaced["sm2"]["simulated_forgetting_rate"],
            "fsrs_forgetting_rate": spaced["fsrs"]["simulated_forgetting_rate"],
            "hlr_avg_predicted_recall": spaced["hlr"]["avg_predicted_recall"],
            "limitation_note": spaced["data_limitation_note"],
        },
        "ppt_highlights": {
            "headline_metrics": [
                "SAKT AUC 0.8381",
                "RealDINA AUC 0.8024",
                "Bloom audit 90.5% within +/-1 level",
            ],
            "honesty_note": (
                "ASSISTments-2009 lacks day-level revisit timestamps, so spaced repetition "
                "results remain proxy-MAE / calibration metrics rather than true day-level MAE."
            ),
        },
    }


def render_markdown(summary: dict) -> str:
    kt = summary["knowledge_tracing"]
    cd = summary["cognitive_diagnosis"]["real_dina"]
    bloom = summary["bloom_audit"]
    sr = summary["spaced_repetition"]
    source_lines = "\n".join(
        f"- `{name}`: `{path}`" for name, path in summary["sources"].items()
    )
    return f"""# Benchmark Summary · {summary['label']}

- generated_at: `{summary['generated_at']}`

## Sources

{source_lines}

## Headline Metrics

| Area | Metric | Value |
|------|--------|-------|
| Knowledge Tracing | SAKT mean AUC | **{kt['sakt']['auc']:.4f}** |
| Knowledge Tracing | DKT mean AUC | **{kt['dkt']['auc']:.4f}** |
| Cognitive Diagnosis | RealDINA mean AUC | **{cd['auc']:.4f}** |
| Bloom Audit | Exact match | **{bloom['exact_match']['rate']:.1f}%** |
| Bloom Audit | Within +/-1 level | **{bloom['within_one_level']['rate']:.1f}%** |
| Bloom Audit | Human spot-check | **{bloom['human_spot_check']['rate']:.1f}%** |
| Spaced Repetition | SM-2 proxy MAE | **{sr['sm2_proxy_mae']:.4f}** |
| Spaced Repetition | FSRS proxy MAE | **{sr['fsrs_proxy_mae']:.4f}** |
| Spaced Repetition | HLR avg predicted recall | **{sr['hlr_avg_predicted_recall']:.4f}** |

## Notes

- PPT-recommended trio: `SAKT 0.8381` / `RealDINA 0.8024` / `Bloom 90.5%`.
- Spaced repetition remains honesty-scoped: proxy MAE + calibration only, not true day-level MAE.
- RealDINA report is the multi-skill problem-granularity run used for competition-facing evidence.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build benchmark summary artifacts")
    parser.add_argument("--label", default="W3-preflight", help="Summary label")
    parser.add_argument("--json-out", required=True, help="Output JSON path")
    parser.add_argument("--md-out", required=True, help="Output Markdown path")
    parser.add_argument("--sakt", default=str(DEFAULT_SAKT))
    parser.add_argument("--dkt", default=str(DEFAULT_DKT))
    parser.add_argument("--dina", default=str(DEFAULT_DINA))
    parser.add_argument("--spaced", default=str(DEFAULT_SPACED))
    parser.add_argument("--bloom", default=str(DEFAULT_BLOOM))
    args = parser.parse_args()

    summary = build_summary(
        label=args.label,
        sakt_path=Path(args.sakt),
        dkt_path=Path(args.dkt),
        dina_path=Path(args.dina),
        spaced_path=Path(args.spaced),
        bloom_path=Path(args.bloom),
    )

    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(render_markdown(summary), encoding="utf-8")

    print(f"[benchmark-summary] wrote {json_out}")
    print(f"[benchmark-summary] wrote {md_out}")


if __name__ == "__main__":
    main()
