from __future__ import annotations

from backend.app.services.enterprise_retriever import (
    chinese_search_grams,
    confident_chinese_candidate,
    reciprocal_rank_fusion,
)


def test_reciprocal_rank_fusion_rewards_candidates_supported_by_two_retrievers():
    fused = reciprocal_rank_fusion(
        [
            [{"chunk_id": "dense-first"}, {"chunk_id": "shared"}],
            [{"chunk_id": "shared"}, {"chunk_id": "lexical-second"}],
        ]
    )

    assert [item["chunk_id"] for item in fused] == [
        "shared",
        "dense-first",
        "lexical-second",
    ]
    assert fused[0]["score"] > fused[1]["score"]


def test_rrf_is_invariant_to_raw_score_scale_and_does_not_mutate_input():
    rankings = [[{"chunk_id": "a", "score": 999999}, {"chunk_id": "b", "score": 0.9}],
                [{"chunk_id": "b", "score": -200}]]
    result = reciprocal_rank_fusion(rankings)
    assert result[0]["chunk_id"] == "b"
    assert abs(result[0]["score"] - (1 / 62 + 1 / 61)) < 1e-10
    assert rankings[0][0]["score"] == 999999
    assert result[0]["rank_contributions"][0]["raw_score"] == .9


def test_rrf_does_not_count_duplicates_within_one_ranking():
    result = reciprocal_rank_fusion([[{"source": "a"}, {"source": "a"}], [{"source": "b"}]], key_field="source")
    assert result[0]["score"] == result[1]["score"] == 1 / 61


def test_chinese_phrase_fallback_ignores_question_words_and_long_queries():
    grams = chinese_search_grams("图灵测试试图评估什么？")
    assert "图灵测试" in grams
    assert "什么" not in grams
    assert "探索与利" in chinese_search_grams("探索与利用的矛盾是什么？")
    assert chinese_search_grams("这是一个非常长的中文问题需要超过二十四个中文字符才能完成查询所以应该跳过该回退。") == []


def test_chinese_rescue_requires_a_clear_source_margin():
    assert confident_chinese_candidate([{"source": "exact", "score": 46},
                                        {"source": "generic", "score": 8}])["source"] == "exact"
    assert confident_chinese_candidate([{"source": "first", "score": 13},
                                        {"source": "second", "score": 13}]) is None
