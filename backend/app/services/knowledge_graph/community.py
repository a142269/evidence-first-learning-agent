"""
GraphRAG Community Detector — Leiden algorithm + community-level LLM summary

Uses python-igraph for Leiden community detection (Traag 2019).
Falls back to NetworkX greedy_modularity_communities if igraph unavailable.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def detect_communities(
    nodes: List[str],
    edges: List[tuple],  # (src, tgt, weight)
    resolution: float = 1.0,
) -> Dict[str, Any]:
    """Leiden 社区检测（降级：NetworkX greedy）。

    Returns:
        {"communities": [{id, nodes, size}], "modularity": float,
         "algorithm": "leiden"|"greedy_modularity"}
    """
    # Try igraph Leiden first
    try:
        import igraph as ig

        g = ig.Graph(directed=False)
        node_idx = {n: i for i, n in enumerate(nodes)}
        for n in nodes:
            g.add_vertex(name=n)
        g.add_edges([(node_idx[s], node_idx[t]) for s, t, _ in edges])
        if edges and len(edges[0]) >= 3:
            g.es["weight"] = [w for _, _, w in edges]

        partition = g.community_leiden(
            objective_function="modularity",
            resolution_parameter=resolution,
            weights="weight" if g.es and "weight" in g.es.attributes() else None,
        )

        communities = []
        for i, members in enumerate(partition):
            communities.append({
                "id": f"community_{i}",
                "nodes": [g.vs[m]["name"] for m in members],
                "size": len(members),
            })

        return {
            "communities": communities,
            "modularity": round(g.modularity(partition, weights="weight" if "weight" in g.es.attributes() else None), 4),
            "algorithm": "leiden",
            "total_communities": len(communities),
        }
    except ImportError:
        logger.debug("[GraphRAG] igraph not available, using NetworkX greedy")

    # Fallback: NetworkX greedy modularity
    try:
        import networkx as nx

        G = nx.Graph()
        G.add_nodes_from(nodes)
        if edges and len(edges[0]) >= 3:
            G.add_weighted_edges_from([(s, t, w) for s, t, w in edges])
        else:
            G.add_edges_from([(s, t) for s, t, *_ in edges])

        raw_communities = list(nx.community.greedy_modularity_communities(G))
        communities = []
        for i, members in enumerate(raw_communities):
            communities.append({
                "id": f"community_{i}",
                "nodes": list(members),
                "size": len(members),
            })

        return {
            "communities": communities,
            "modularity": round(nx.community.modularity(G, raw_communities), 4),
            "algorithm": "greedy_modularity",
            "total_communities": len(communities),
        }
    except ImportError:
        # Last resort: single community
        return {
            "communities": [{"id": "community_0", "nodes": nodes, "size": len(nodes)}],
            "modularity": 0.0,
            "algorithm": "fallback_single",
            "total_communities": 1,
        }


def generate_community_summaries(
    communities: List[dict],
    kg_store=None,
    llm_client=None,
) -> List[dict]:
    """为每个社区生成摘要（提取 top-5 节点名 + 主要边标签）。

    不依赖 LLM，用规则生成确定性摘要。
    """
    summaries = []
    for comm in communities:
        node_names = comm.get("nodes", [])[:5]
        desc = (
            f"社区包含 {comm['size']} 个知识点，"
            f"核心概念：{'、'.join(node_names[:5])}"
        )
        summaries.append({
            "community_id": comm["id"],
            "summary": desc,
            "top_nodes": node_names,
            "node_count": comm["size"],
        })
    return summaries
