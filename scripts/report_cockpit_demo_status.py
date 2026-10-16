#!/usr/bin/env python3
"""Export a 5-demo-user cockpit readiness matrix for role-B handoff."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_USERS = (
    "demo-student-1",
    "demo-student-2",
    "demo-student-3",
    "demo-student-4",
    "demo-student-5",
)


def _safe_len(value: object) -> int:
    return len(value) if isinstance(value, (list, dict, tuple, set)) else 0


def _has_valid_radar_labels(labels: object) -> bool:
    if not isinstance(labels, list) or len(labels) != 6:
        return False
    return all(isinstance(item, str) and "\\udc" not in repr(item) for item in labels)


def collect(users: tuple[str, ...]) -> dict:
    client = TestClient(app)
    rows = []
    summary = {
        "users": len(users),
        "profile_ready": 0,
        "forecast_ready": 0,
        "counterfactual_ready": 0,
        "kg_ready": 0,
        "attribution_ready": 0,
        "cov_ready": 0,
        "debate_ready": 0,
        "safety_ready": 0,
        "ledger_ready": 0,
    }

    for user_id in users:
        response = client.get(f"/api/v1/cockpit/student/{user_id}")
        response.raise_for_status()
        payload = response.json()

        profile = payload.get("profile", {})
        forecast = payload.get("forecast", {})
        kg = payload.get("kg", {})
        attribution = payload.get("attribution", {})
        cov = payload.get("cov", {})
        debate = payload.get("debate", {})
        safety = payload.get("safety", {})
        ledger = payload.get("ledger", {})

        row = {
            "user_id": user_id,
            "profile_ready": _safe_len(profile.get("radar_6d")) == 6 and _has_valid_radar_labels(profile.get("radar_labels")),
            "forecast_curve_points": _safe_len(forecast.get("curve")),
            "counterfactual_ready": bool(forecast.get("counterfactual")),
            "kg_nodes": _safe_len(kg.get("neighbors_2hop")),
            "kg_edges": _safe_len(kg.get("edges_2hop")),
            "attribution_categories": _safe_len(attribution.get("category_distribution")),
            "cov_verified_claims": sum(1 for claim in cov.get("recent_claims", []) if claim.get("verified")),
            "debate_rounds": _safe_len(debate.get("recent_traces")),
            "safety_fields": sum(
                1
                for key in (
                    "scaffolding_score",
                    "answer_leak_risk",
                    "misconception_reinforcement_risk",
                    "student_uptake_prompt",
                )
                if safety.get(key) not in (None, "")
            ),
            "ledger_sources_nonzero": sum(
                1 for value in ledger.get("source_distribution", {}).values() if value
            ),
            "ledger_conflict": any(claim.get("conflict_warning") for claim in ledger.get("claims", [])),
        }
        row["forecast_ready"] = row["forecast_curve_points"] >= 7
        row["kg_ready"] = row["kg_nodes"] >= 5 and row["kg_edges"] >= 4
        row["attribution_ready"] = row["attribution_categories"] >= 3
        row["cov_ready"] = row["cov_verified_claims"] >= 3
        row["debate_ready"] = row["debate_rounds"] >= 2
        row["safety_ready"] = row["safety_fields"] == 4
        row["ledger_ready"] = row["ledger_sources_nonzero"] >= 3

        summary["profile_ready"] += int(row["profile_ready"])
        summary["forecast_ready"] += int(row["forecast_ready"])
        summary["counterfactual_ready"] += int(row["counterfactual_ready"])
        summary["kg_ready"] += int(row["kg_ready"])
        summary["attribution_ready"] += int(row["attribution_ready"])
        summary["cov_ready"] += int(row["cov_ready"])
        summary["debate_ready"] += int(row["debate_ready"])
        summary["safety_ready"] += int(row["safety_ready"])
        summary["ledger_ready"] += int(row["ledger_ready"])
        rows.append(row)

    coverage = {
        key: round(value / len(users), 2)
        for key, value in summary.items()
        if key != "users"
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "users": list(users),
        "summary": summary,
        "coverage": coverage,
        "rows": rows,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Cockpit Demo Readiness",
        "",
        f"- generated_at: `{report['generated_at']}`",
        "",
        "## Coverage",
        "",
        "| Block | Ready Users | Coverage |",
        "|------|-------------|----------|",
    ]
    summary = report["summary"]
    coverage = report["coverage"]
    for key in (
        "profile_ready",
        "forecast_ready",
        "counterfactual_ready",
        "kg_ready",
        "attribution_ready",
        "cov_ready",
        "debate_ready",
        "safety_ready",
        "ledger_ready",
    ):
        lines.append(
            f"| {key} | {summary[key]}/{summary['users']} | {coverage[key] * 100:.0f}% |"
        )

    lines.extend(
        [
            "",
            "## Per User",
            "",
            "| User | Curve | CF | KG Nodes | Attr Cats | Verified Claims | Debate | Safety | Ledger Sources | Conflict |",
            "|------|------:|----|---------:|----------:|----------------:|-------:|-------:|---------------:|----------|",
        ]
    )
    for row in report["rows"]:
        lines.append(
            "| {user_id} | {forecast_curve_points} | {counterfactual_ready} | {kg_nodes} | "
            "{attribution_categories} | {cov_verified_claims} | {debate_rounds} | {safety_fields} | "
            "{ledger_sources_nonzero} | {ledger_conflict} |".format(**row)
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Report cockpit readiness for demo users")
    parser.add_argument("--json-out", required=True, help="Output JSON path")
    parser.add_argument("--md-out", required=True, help="Output Markdown path")
    parser.add_argument("--users", nargs="*", default=list(DEFAULT_USERS))
    args = parser.parse_args()

    report = collect(tuple(args.users))
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(render_markdown(report), encoding="utf-8")
    print(f"[cockpit-report] wrote {json_out}")
    print(f"[cockpit-report] wrote {md_out}")


if __name__ == "__main__":
    main()
