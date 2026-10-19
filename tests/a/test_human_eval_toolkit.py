import json

import pytest

from backend.app.evaluation.ablation_report import ARMS, RUBRICS
from backend.app.evaluation.human_agreement import canonical_digest
from scripts.human_eval import (
    agreement_report,
    common,
    export_summary,
    import_reviews,
    prepare_packets,
    validate_packets,
)

CASES = [
    {"id": "synth-1", "split": "holdout", "question": "synthetic question one", "course_id": "synthetic_course",
     "expected_sources": ["synthetic_course/chapters/one.md"]},
    {"id": "synth-2", "split": "holdout", "question": "synthetic question two", "course_id": "synthetic_course",
     "expected_sources": ["synthetic_course/chapters/two.md"]},
    {"id": "synth-3", "split": "dev", "question": "synthetic dev question", "course_id": "synthetic_course",
     "expected_sources": ["synthetic_course/chapters/three.md"]},
]
EVIDENCE = {"synth-1": [{"chunk_id": "k1", "source": "synthetic_course/chapters/one.md", "content": "fact one"}],
            "synth-2": [{"chunk_id": "k2", "source": "synthetic_course/chapters/two.md", "content": "fact two"}]}
CONFIG = {"model": "synthetic-model", "knowledge_snapshot": "synthetic-snapshot", "max_output_tokens": 512,
          "max_cost_cny": None}


def build_repo(tmp_path, *, leaking_package=False):
    (tmp_path / "evals").mkdir(parents=True, exist_ok=True)
    (tmp_path / "evals/ablation_tasks_v1.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in CASES), encoding="utf-8")
    directory = tmp_path / "output" / "synthetic-run"
    directory.mkdir(parents=True)
    digests = {case_id: canonical_digest(rows) for case_id, rows in EVIDENCE.items()}
    (directory / "evidence.jsonl").write_text("".join(
        json.dumps({"case_id": case_id, "sha256": digest, "evidence": EVIDENCE[case_id]}) + "\n"
        for case_id, digest in digests.items()), encoding="utf-8")
    package = {"lesson": "synthetic", "steps": [{"id": "s1"}]}
    if leaking_package:
        package["arm"] = "full"
    rows = [{"case_id": case["id"], "arm": arm, "completed": True, "config": CONFIG,
             "evidence_sha256": digests[case["id"]], "latency_ms": 100, "model_calls": 1,
             "result": {"package": json.loads(json.dumps(package)) | {"arm_value": arm}}, "reviews": []}
            for case in CASES if case["split"] == "holdout" for arm in ARMS]
    (directory / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return directory


def prepare(tmp_path, monkeypatch, directory):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    assert prepare_packets.main(["--run-dir", str(directory)]) == 0
    return directory


def read(directory, name):
    return json.loads((directory / name).read_text(encoding="utf-8"))


def fill(directory, role, judgements):
    mapping = read(directory, common.MAPPING_NAME)
    blind_to_key = {row["blind_id"]: (row["case_id"], row["arm"]) for row in mapping if row["reviewer"] == role}
    path = directory / common.PACKET_NAME.format(role=role)
    packet = read(directory, path.name)
    for item in packet:
        values = judgements[blind_to_key[item["blind_id"]]]
        item["scores"] = {metric: values.get(metric) for metric in RUBRICS}
    path.write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")


def agree(case_id, arm, overrides=None):
    values = dict.fromkeys(RUBRICS, True)
    values.update(overrides or {})
    return values


def test_packets_are_independently_ordered_and_never_prefilled(tmp_path, monkeypatch):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    packet_a = read(directory, common.PACKET_NAME.format(role="a"))
    packet_b = read(directory, common.PACKET_NAME.format(role="b"))
    assert len(packet_a) == len(packet_b) == 6
    assert all(value is None for item in packet_a + packet_b for value in item["scores"].values())
    assert all(set(item) == set(common.ITEM_FIELDS) for item in packet_a)
    assert not any(key in item for item in packet_a + packet_b for key in ("arm", "case_id", "expected_sources"))
    assert [item["blind_id"] for item in packet_a] == [f"a-{index:03d}" for index in range(1, 7)]
    mapping = read(directory, common.MAPPING_NAME)
    order = {role: [(row["case_id"], row["arm"]) for row in sorted(
        (entry for entry in mapping if entry["reviewer"] == role), key=lambda entry: entry["blind_id"])]
        for role in common.ROLES}
    assert order["a"] != order["b"], "both reviewers received the same item order"
    manifest = read(directory, common.MANIFEST_NAME)
    assert manifest["item_count"] == 6 and manifest["split"] == "holdout"
    assert set(manifest["permutation_sha256"]) == set(manifest["packet_sha256"]) == {"a", "b"}
    assert validate_packets.main(["--run-dir", str(directory)]) == 0


def test_generation_refuses_a_packet_that_would_expose_the_reference_arm(tmp_path, monkeypatch, capsys):
    directory = build_repo(tmp_path, leaking_package=True)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    with pytest.raises(SystemExit) as exit_info:
        prepare_packets.main(["--run-dir", str(directory)])
    assert exit_info.value.code == 2
    assert "ANSWER_LEAK" in capsys.readouterr().err
    assert not (directory / common.MANIFEST_NAME).exists()
    assert not (directory / common.PACKET_NAME.format(role="a")).exists()


def test_validate_is_read_only_and_names_the_broken_gate(tmp_path, monkeypatch, capsys):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    before = sorted(path.name for path in directory.iterdir())
    assert validate_packets.main(["--run-dir", str(directory)]) == 0
    assert sorted(path.name for path in directory.iterdir()) == before

    packet_path = directory / common.PACKET_NAME.format(role="a")
    packet = read(directory, packet_path.name)
    packet[0]["question"] = "rewritten question"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    with pytest.raises(SystemExit):
        validate_packets.main(["--run-dir", str(directory)])
    assert "PACKET_TAMPERED" in capsys.readouterr().err

    rows = [json.loads(line) for line in (directory / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    rows[0]["latency_ms"] = 999
    (directory / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(SystemExit):
        validate_packets.main(["--run-dir", str(directory)])
    assert "STALE_SOURCE" in capsys.readouterr().err


def test_swapping_the_two_namespaces_is_rejected(tmp_path, monkeypatch, capsys):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    path_a = directory / common.PACKET_NAME.format(role="a")
    path_b = directory / common.PACKET_NAME.format(role="b")
    path_b.write_text(path_a.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(SystemExit):
        validate_packets.main(["--run-dir", str(directory)])
    assert "NAMESPACE_MISMATCH" in capsys.readouterr().err


def test_review_round_trip_reports_kappa_and_keeps_disputes_open(tmp_path, monkeypatch, capsys):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    mapping = read(directory, common.MAPPING_NAME)
    keys = {(row["case_id"], row["arm"]) for row in mapping if row["reviewer"] == "a"}
    dispute_one = sorted(keys)[0]
    dispute_two = sorted(keys)[1]
    fill(directory, "a", {key: agree(*key) for key in keys})
    fill(directory, "b", {key: agree(*key, overrides={"facts_supported": False} if key == dispute_one
                                   else {"goal_covered": False} if key == dispute_two else {}) for key in keys})
    assert validate_packets.main(["--run-dir", str(directory), "--require-reviewed"]) == 0
    assert import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "two"]) == 0

    reviewed = [json.loads(line) for line in (directory / common.REVIEWED_NAME).read_text(encoding="utf-8").splitlines()]
    assert len(reviewed) == 6 and all(len(row["reviews"]) == 2 for row in reviewed)
    assert {row["reviews"][0]["reviewer"] for row in reviewed} == {"one"}
    disputes = read(directory, common.ADJUDICATION_PACKET_NAME)
    assert len(disputes) == 2 and all(item["scores"][metric] is None for item in disputes for metric in RUBRICS)
    assert not any(key in item for item in disputes for key in ("arm", "case_id", "reviews"))

    assert agreement_report.main(["--run-dir", str(directory), "--seed", "20261019", "--replicates", "50"]) == 0
    report = read(directory, common.REPORT_NAME)
    assert report["item_count"] == 6 and report["review_complete"] is False
    assert report["randomness"]["bootstrap_seed"] == 20261019
    assert report["per_metric"]["facts_supported"]["kappa"] == pytest.approx(0.0)
    assert report["per_metric"]["facts_supported"]["n"] == 6
    assert report["per_metric"]["difficulty_progression"]["kappa"] is None
    assert report["per_metric"]["difficulty_progression"]["reason"] == "degenerate_marginals"
    assert all(rate is None for rate in report["quality_pass_rate_by_arm"].values())
    assert len(report["disagreements"]) == 2
    assert any("profile_fit" in item for item in report["limitations"])

    assert export_summary.main(["--run-dir", str(directory)]) == 0
    summary_text = (directory / common.SUMMARY_JSON_NAME).read_text(encoding="utf-8")
    for forbidden in ("case_id", '"arm"', "notes", "synth-1", "one.md"):
        assert forbidden not in summary_text
    assert (directory / common.SUMMARY_MD_NAME).read_text(encoding="utf-8").startswith("# Human agreement summary")
    capsys.readouterr()


def test_adjudication_closes_the_review_without_rewriting_agreement(tmp_path, monkeypatch):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    mapping = read(directory, common.MAPPING_NAME)
    keys = {(row["case_id"], row["arm"]) for row in mapping if row["reviewer"] == "a"}
    first, second = sorted(keys)[:2]
    fill(directory, "a", {key: agree(*key) for key in keys})
    fill(directory, "b", {key: agree(*key, overrides={"facts_supported": False} if key == first else {})
                          for key in keys})
    assert import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "two"]) == 0
    aligned = read(directory, common.ALIGNED_NAME)["items"]
    disputed = next(row for row in aligned if row["judgements"]["a"]["facts_supported"]
                    != row["judgements"]["b"]["facts_supported"])
    decisions = [{"blind_id": disputed["blind_id_a"], "scores": dict.fromkeys(RUBRICS, True)}]
    (directory / "adjudications.json").write_text(json.dumps(decisions), encoding="utf-8")

    assert import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "two",
                                "--adjudications", "adjudications.json", "--adjudicator", "three"]) == 0
    adjudicated = [json.loads(line) for line in
                   (directory / common.ADJUDICATED_NAME).read_text(encoding="utf-8").splitlines()]
    assert sum("adjudication" in row for row in adjudicated) == 1

    assert agreement_report.main(["--run-dir", str(directory), "--seed", "7", "--replicates", "50",
                                  "--adjudications", "adjudications.json", "--adjudicator", "three",
                                  "--reviewer-a", "one", "--reviewer-b", "two"]) == 0
    report = read(directory, common.REPORT_NAME)
    assert report["review_complete"] is True
    assert report["adjudication"]["items_with_adjudication"] == 1
    assert report["quality_pass_rate_by_arm"]["full"] == 1.0


def test_asymmetric_coverage_and_non_boolean_scores_are_rejected(tmp_path, monkeypatch, capsys):
    directory = prepare(tmp_path, monkeypatch, build_repo(tmp_path))
    mapping = read(directory, common.MAPPING_NAME)
    keys = {(row["case_id"], row["arm"]) for row in mapping if row["reviewer"] == "a"}
    fill(directory, "a", {key: agree(*key) for key in keys})
    fill(directory, "b", {key: agree(*key, overrides={"profile_fit": None}) for key in keys})
    with pytest.raises(SystemExit) as exit_info:
        import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "two"])
    assert exit_info.value.code == 2
    assert "COVERAGE_INCOMPLETE" in capsys.readouterr().err
    assert not (directory / common.REVIEWED_NAME).exists()

    path_b = directory / common.PACKET_NAME.format(role="b")
    packet_b = read(directory, path_b.name)
    packet_b[0]["scores"]["profile_fit"] = "true"
    path_b.write_text(json.dumps(packet_b), encoding="utf-8")
    with pytest.raises(SystemExit):
        import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "two"])
    assert "SCORE_TYPE" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        import_reviews.main(["--run-dir", str(directory), "--reviewer-a", "one", "--reviewer-b", "one"])
    assert "REVIEWER_IDS_INVALID" in capsys.readouterr().err


def test_material_is_never_written_outside_the_private_root(tmp_path, monkeypatch, capsys):
    directory = build_repo(tmp_path)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    with pytest.raises(SystemExit):
        prepare_packets.main(["--run-dir", str(tmp_path / "elsewhere")])
    assert "OUTPUT_OUTSIDE_PRIVATE_ROOT" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        prepare_packets.main(["--run-dir", str(tmp_path / "output" / "missing")])
    assert "RUN_DIR_MISSING" in capsys.readouterr().err
    prepare_packets.main(["--run-dir", str(directory)])
    with pytest.raises(SystemExit):
        prepare_packets.main(["--run-dir", str(directory)])
    assert "ARTEFACT_EXISTS" in capsys.readouterr().err


def test_a_manifest_forged_over_leaking_content_still_fails_the_gate(tmp_path, monkeypatch, capsys):
    """The leak scan is not only a generation-time check: a crafted artefact set is caught too."""
    directory = build_repo(tmp_path)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    cases, runs, snapshots = common.input_state(directory, "holdout")
    by_id = {row["id"]: row for row in cases}
    evidence = common.check_evidence_snapshots(runs, snapshots)
    reviewable = [row for row in runs if row["completed"]]
    packets, mapping = {}, []
    for role, order in (("a", reviewable), ("b", reviewable[1:] + reviewable[:1])):
        items = []
        for index, run in enumerate(order, 1):
            package = dict(run["result"]["package"], expected_sources=["synthetic_course/chapters/one.md"])
            item = common.packet_item(role, index, by_id[run["case_id"]]["question"],
                                      evidence[run["case_id"]]["evidence"], package)
            items.append(item)
            mapping.append(common.mapping_row(role, item, run["case_id"], run["arm"], run["evidence_sha256"]))
        packets[role] = items
    manifest = {"generator_version": common.EVALUATOR_VERSION, "split": "holdout", "item_count": 6,
                "dataset": common.DATASET_PATH, **common.source_digests(cases, runs, snapshots),
                "permutation_sha256": {role: common.permutation_digest([item["blind_id"] for item in packets[role]])
                                       for role in common.ROLES},
                "packet_sha256": {role: canonical_digest(common.frozen_packet(packets[role]))
                                  for role in common.ROLES},
                "created_at": "2026-10-19T00:00:00+00:00"}
    for role in common.ROLES:
        common.write_json(directory / common.PACKET_NAME.format(role=role), packets[role])
    common.write_json(directory / common.MAPPING_NAME, mapping)
    common.write_json(directory / common.MANIFEST_NAME, manifest)
    with pytest.raises(SystemExit):
        validate_packets.main(["--run-dir", str(directory)])
    assert "ANSWER_LEAK" in capsys.readouterr().err
