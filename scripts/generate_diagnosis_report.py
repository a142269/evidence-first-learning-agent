"""CLI for generating a judge-facing learning diagnosis report.

Examples
--------
Generate both Markdown and JSON in the default `reports/diagnosis/` dir::

    python -m scripts.generate_diagnosis_report --user demo-student-1 --format both

Override the output dir and request only JSON::

    python -m scripts.generate_diagnosis_report \\
        --user demo-student-2 --format json --out-dir reports/diagnosis-prod
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.diagnosis_reporter import DiagnosisReporter  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an A3 learning diagnosis report")
    parser.add_argument("--user", required=True, help="Student user_id, e.g. demo-student-1")
    parser.add_argument(
        "--out-dir",
        default=str(PROJECT_ROOT / "reports" / "diagnosis"),
        help="Output directory for generated report files",
    )
    parser.add_argument(
        "--focus-kp",
        default=None,
        help="Optional KP id used for the 30-day forecast section",
    )
    parser.add_argument(
        "--format",
        default="both",
        choices=["md", "json", "both"],
        help="Output format(s); 'both' writes Markdown and JSON",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Also export PDF if markdown-pdf is installed (requires --format md or both)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reporter = DiagnosisReporter()
    formats = DiagnosisReporter.parse_format_arg(args.format)
    if args.pdf and "md" not in formats:
        print("--pdf requires Markdown output; ignoring PDF export.")
        export_pdf = False
    else:
        export_pdf = args.pdf
    result = reporter.write_report(
        user_id=args.user,
        output_dir=Path(args.out_dir),
        generated_at=datetime.now(timezone.utc),
        focus_kp_id=args.focus_kp,
        formats=formats,
        export_pdf=export_pdf,
    )
    if result.markdown_path is not None:
        print(f"Markdown report: {result.markdown_path}")
    if result.json_path is not None:
        print(f"JSON report    : {result.json_path}")
    if export_pdf:
        if result.pdf_path is None:
            print("PDF report     : skipped (markdown-pdf not available or export failed)")
        else:
            print(f"PDF report     : {result.pdf_path}")
    print(
        "Summary: "
        f"{result.report.nickname} ({result.report.archetype}), "
        f"focus={result.report.focus_kp_id}, "
        f"questions={len(result.report.recommendations.questions)}, "
        f"forecast_available={result.report.forecast.status.available}, "
        f"bloom_source={result.report.bloom.status.source}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
