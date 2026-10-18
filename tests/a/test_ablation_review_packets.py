import hashlib
import json
import sys

import pytest

from scripts import merge_ablation_reviews, prepare_ablation_adjudication, prepare_ablation_review
from backend.app.evaluation.ablation_report import RUBRICS


def test_blinded_packets_round_trip(tmp_path, monkeypatch):
    output = tmp_path / "output" / "run"
    output.mkdir(parents=True)
    evaluation = tmp_path / "evals"
    evaluation.mkdir()
    case = {"id": "a", "split": "holdout", "question": "question"}
    (evaluation / "ablation_tasks_v1.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")
    evidence = [{"chunk_id": "c", "source": "s", "content": "evidence"}]
    digest = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (output / "evidence.jsonl").write_text(json.dumps({"case_id": "a", "sha256": digest, "evidence": evidence}) + "\n", encoding="utf-8")
    config = {"model": "m", "knowledge_snapshot": "snapshot", "max_output_tokens": 8192, "max_cost_cny": None}
    rows = [{"case_id": "a", "arm": arm, "completed": True, "config": config,
             "evidence_sha256": digest, "result": {"package": {"lesson": arm}}, "reviews": []}
            for arm in ("single", "without_reviewer", "full")]
    (output / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(prepare_ablation_review, "ROOT", tmp_path)
    monkeypatch.setattr(merge_ablation_reviews, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare", "--run-dir", str(output)])
    prepare_ablation_review.main()
    for name in ("reviewer-a.json", "reviewer-b.json"):
        path = output / name
        packet = json.loads(path.read_text(encoding="utf-8"))
        for item in packet:
            item["scores"] = {key: (None if key == "profile_fit" else True) for key in RUBRICS}
            assert "arm" not in item
        path.write_text(json.dumps(packet), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["merge", "--run-dir", str(output), "--reviewer-a", "one", "--reviewer-b", "two"])
    rows[0]["evidence_sha256"] = "altered"
    (output / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises(SystemExit):
        merge_ablation_reviews.main()
    assert not (output / "reviewed-runs.jsonl").exists()
    rows[0]["evidence_sha256"] = digest
    (output / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    merge_ablation_reviews.main()
    merged = [json.loads(line) for line in (output / "reviewed-runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(len(row["reviews"]) == 2 and row["reviews"][0]["profile_fit"] is None for row in merged)

    packet_b_path = output / "reviewer-b.json"
    packet_b = json.loads(packet_b_path.read_text(encoding="utf-8"))
    packet_b[0]["scores"]["facts_supported"] = False
    packet_b_path.write_text(json.dumps(packet_b), encoding="utf-8")
    monkeypatch.setattr(prepare_ablation_adjudication, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare", "--run-dir", str(output)])
    prepare_ablation_adjudication.main()
    packet = json.loads((output / "adjudication-packet.json").read_text(encoding="utf-8"))
    assert len(packet) == 1 and packet[0]["disputed_metrics"] == ["facts_supported"]
    assert all(value is None for value in packet[0]["scores"].values())
    assert "reviews" not in packet[0] and "arm" not in packet[0]
    decisions = [{"blind_id": packet_b[0]["blind_id"],
                  "scores": {key: (None if key == "profile_fit" else True) for key in RUBRICS}}]
    (output / "adjudications.json").write_text(json.dumps(decisions), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["merge", "--run-dir", str(output), "--reviewer-a", "one", "--reviewer-b", "two",
                                     "--adjudications", "adjudications.json", "--adjudicator", "three"])
    merge_ablation_reviews.main()
    adjudicated = [json.loads(line) for line in (output / "adjudicated-runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum("adjudication" in row for row in adjudicated) == 1
    assert next(row["adjudication"]["reviewer"] for row in adjudicated if "adjudication" in row) == "three"
    assert (output / "reviewed-runs.jsonl").exists()


def test_blinding_rejects_modified_evidence_before_creating_packets(tmp_path, monkeypatch):
    output = tmp_path / "output" / "run"
    output.mkdir(parents=True)
    evaluation = tmp_path / "evals"
    evaluation.mkdir()
    (evaluation / "ablation_tasks_v1.jsonl").write_text(
        json.dumps({"id": "a", "split": "holdout", "question": "question"}) + "\n", encoding="utf-8")
    evidence = [{"chunk_id": "c", "source": "s", "content": "original"}]
    digest = hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    evidence[0]["content"] = "modified"
    (output / "evidence.jsonl").write_text(json.dumps({"case_id": "a", "sha256": digest, "evidence": evidence}) + "\n", encoding="utf-8")
    config = {"model": "m", "knowledge_snapshot": "snapshot", "max_output_tokens": 8192, "max_cost_cny": None}
    rows = [{"case_id": "a", "arm": arm, "completed": True, "config": config,
             "evidence_sha256": digest, "result": {"package": {}}, "reviews": []}
            for arm in ("single", "without_reviewer", "full")]
    (output / "runs.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(prepare_ablation_review, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["prepare", "--run-dir", str(output)])
    with pytest.raises(SystemExit):
        prepare_ablation_review.main()
    assert not (output / "reviewer-a.json").exists()
