"""RRF — Reciprocal Rank Fusion

公式: ``RRF_score(d) = Σ_i 1 / (k + rank_i(d))``

其中 ``k=60`` 为论文推荐常数 (Cormack, Clarke, Buettcher SIGIR 2009)。
适合融合多路异质召回：plain RAG / HyDE / KG 邻居 / BM25 等。

为什么用 RRF 而非加权求和:
    各路召回的相对 score 量纲不一致（cosine [0,1] vs BM25 [0,∞)），
    强行加权需要超参；rank-based 融合只看排名，无需归一，工程更稳。

设计:
    * 输入：``list[list[chunk_dict]]``，每个 sublist 是一路召回的有序结果
    * 输出：合并后按 RRF score 降序的 ``list[chunk_dict]``
    * 同一 chunk 在不同路里出现 → 累加各路的 1/(k+rank)
    * chunk 唯一性按 ``chunk_id``；若缺则按 ``source + content[:100]`` 兜底
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional

# 论文推荐 k=60，可调
DEFAULT_RRF_K = 60


def _chunk_uid(chunk: Dict[str, Any]) -> str:
    """生成 chunk 的唯一标识，用于跨路去重 + 累加 score。"""
    cid = chunk.get("chunk_id")
    if cid:
        return f"id:{cid}"
    source = chunk.get("source", "")
    content_head = (chunk.get("content", "") or "")[:100]
    sig = hashlib.sha1(f"{source}::{content_head}".encode("utf-8")).hexdigest()[:12]
    return f"sig:{sig}"


def reciprocal_rank_fusion(
    rank_lists: Iterable[List[Dict[str, Any]]],
    *,
    k: int = DEFAULT_RRF_K,
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """对多路召回做 RRF 融合。

    Args:
        rank_lists: 各路召回结果的迭代器；每路是按相关度降序的 chunk dict list。
        k: RRF 常数，默认 60（论文推荐）。
        top_n: 最终返回前 N 条；None 表示返回全部。

    Returns:
        融合后按 RRF score 降序的 chunk list，每个 chunk 含:
            * 原 chunk 字段（content / source / etc.）
            * ``rrf_score`` (float)
            * ``rrf_sources`` (list[str]) — 命中过哪些路（"hyde" / "plain" / "kg" 等）
            * ``rrf_ranks`` (dict[str, int]) — 各路对应 rank（1-based）
    """
    accumulated: Dict[str, Dict[str, Any]] = {}

    for rank_list in rank_lists:
        if not rank_list:
            continue
        for rank, chunk in enumerate(rank_list, start=1):
            if not isinstance(chunk, dict):
                continue
            uid = _chunk_uid(chunk)
            score_contrib = 1.0 / (k + rank)
            retriever_name = chunk.get("retriever", "unknown")

            if uid not in accumulated:
                # 第一次见到这个 chunk：复制 + 初始化 RRF 字段
                merged: Dict[str, Any] = dict(chunk)
                merged["rrf_score"] = score_contrib
                merged["rrf_sources"] = [retriever_name]
                merged["rrf_ranks"] = {retriever_name: rank}
                accumulated[uid] = merged
            else:
                # 已存在：累加 score + 记 source
                existing = accumulated[uid]
                existing["rrf_score"] += score_contrib
                if retriever_name not in existing["rrf_sources"]:
                    existing["rrf_sources"].append(retriever_name)
                # 同名 retriever 取最优 rank
                prev_rank = existing["rrf_ranks"].get(retriever_name)
                if prev_rank is None or rank < prev_rank:
                    existing["rrf_ranks"][retriever_name] = rank

    # 按 RRF score 降序排
    fused = sorted(
        accumulated.values(),
        key=lambda c: c["rrf_score"],
        reverse=True,
    )
    if top_n is not None:
        fused = fused[:top_n]
    return fused


def fuse_with_metadata(
    rank_lists: Dict[str, List[Dict[str, Any]]],
    *,
    k: int = DEFAULT_RRF_K,
    top_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """便利包装：传入 ``{retriever_name: chunks_list}`` dict。

    每个 chunk 自动打上 ``retriever`` 字段（如果还没有），方便后续 trace。
    """
    enriched: List[List[Dict[str, Any]]] = []
    for name, chunks in rank_lists.items():
        tagged = []
        for c in chunks:
            if not isinstance(c, dict):
                continue
            cc = dict(c)
            cc.setdefault("retriever", name)
            tagged.append(cc)
        enriched.append(tagged)
    return reciprocal_rank_fusion(enriched, k=k, top_n=top_n)
