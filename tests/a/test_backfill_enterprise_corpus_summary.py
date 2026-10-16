from __future__ import annotations

import json
import sys
from types import SimpleNamespace

from scripts import backfill_enterprise_corpus


def test_backfill_reports_failed_embeddings_instead_of_only_indexed(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("V2_EVAL_BUDGET_CNY", "100")
    monkeypatch.setenv("V2_EVAL_BUDGET_ID", "test-backfill")
    course = tmp_path / "artificial_intelligence"
    course.mkdir()
    (course / "first.md").write_text("# First", encoding="utf-8")
    (course / "second.md").write_text("# Second", encoding="utf-8")
    (course / "third.md").write_text("# Third", encoding="utf-8")
    monkeypatch.setattr(backfill_enterprise_corpus, "get_config", lambda: SimpleNamespace(
        rag=SimpleNamespace(knowledge_base_path=str(tmp_path))))
    monkeypatch.setattr(backfill_enterprise_corpus, "backfill_curated_markdown",
                        lambda **kwargs: {"status": "indexed", "embedding": {
                            "status": "embedded" if kwargs["storage_key"].endswith("first.md") else "failed"}})
    monkeypatch.setattr(sys, "argv", ["backfill_enterprise_corpus.py", "--summary-only"])
    assert backfill_enterprise_corpus.main() == 1
    summary = json.loads(capsys.readouterr().out)["summary"]
    assert summary["indexed"] == 2
    assert summary["embedded"] == 1
    assert summary["embedding_failed"] == 1
    assert summary["stopped_early"] is True
    assert summary["documents"] == 2
    assert summary["planned_documents"] == 3


def test_paid_backfill_requires_shared_budget(monkeypatch, tmp_path):
    import pytest

    monkeypatch.delenv("V2_EVAL_BUDGET_CNY", raising=False)
    monkeypatch.delenv("V2_EVAL_BUDGET_ID", raising=False)
    monkeypatch.setattr(backfill_enterprise_corpus, "get_config", lambda: SimpleNamespace(
        rag=SimpleNamespace(knowledge_base_path=str(tmp_path))))
    monkeypatch.setattr(sys, "argv", ["backfill_enterprise_corpus.py"])
    with pytest.raises(SystemExit, match="shared_eval_budget_required"):
        backfill_enterprise_corpus.main()
