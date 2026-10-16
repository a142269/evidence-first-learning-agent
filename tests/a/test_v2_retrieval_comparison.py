import pytest

from backend.app.services.enterprise_retriever import diversify_candidates
from scripts.compare_v2_retrieval import compare


def _hit(chunk_id, source, content, score):
    return {"chunk_id": chunk_id, "source": source, "content": content, "score": score}


def test_diversity_downgrades_near_duplicate_from_same_document():
    hits = [_hit("a", "doc-a", "same content", .05),
            _hit("b", "doc-a", "same content", .049),
            _hit("c", "doc-b", "other topic", .04)]
    assert [item["chunk_id"] for item in diversify_candidates(hits, 2)] == ["a", "c"]


def test_comparison_requires_one_frozen_corpus_and_does_not_promote():
    row = {"case_id": "1", "corpus_sha256": "fixed", "expected_chunk_ids": ["b"],
           "dense": [_hit("a", "doc-a", "unrelated", .8), _hit("b", "doc-b", "relevant", .7)],
           "lexical": [_hit("b", "doc-b", "relevant", .9)]}
    report = compare([row], top_k=1)
    assert report["metrics"]["dense"]["recall_at_k"] == 0
    assert report["metrics"]["hybrid"]["recall_at_k"] == 1
    assert report["default_strategy"] == "hybrid"
    with pytest.raises(ValueError, match="one_frozen_corpus_required"):
        compare([{**row, "corpus_sha256": "other"}, row])
