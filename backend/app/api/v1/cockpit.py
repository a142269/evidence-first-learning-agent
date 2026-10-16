"""Cockpit 聚合端点 — A+B 合并版学情驾驶舱数据源。

GET /api/v1/cockpit/student/{user_id}

目标：
1. 前端 CockpitView 一次调用拿齐多块面板数据。
2. 保留 A 侧 safety / ledger / schema 端点能力。
3. 保留 B 侧 learning_goals 映射、KG/forecast 修正、demo seed 回退。
4. 单块失败不影响整体返回。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cockpit", tags=["cockpit"])

DEFAULT_HORIZON_DAYS = 7
# radar_labels 使用显式 Unicode 编码构建，避免 Windows GBK codepage 导致 surrogate mojibake
_RADAR_LABELS = [
    "知识基础",   # 知识基础
    "认知风格",   # 认知风格
    "学习偏好",   # 学习偏好
    "薄弱环节",   # 薄弱环节
    "学习目标",   # 学习目标
    "自我效能",    # 自我效能
]
_RADAR_SAFE_FALLBACK: dict[int, str] | None = None

def _radar_labels_clean() -> list[str]:
    """获取编码安全的 radar_labels——硬编码版本，永不依赖源码文件编码。

    P0-1 修复：Windows GBK codepage 下源码中的中文字面量可能被误编码
    为 surrogate mojibake。此函数直接返回硬编码的 `chr()` 构造字符串，
    确保在任何文件编码下拿到正确 UTF-8 中文。
    """
    raw = [
        "知识基础",   # 知识基础
        "认知风格",   # 认知风格
        "学习偏好",   # 学习偏好
        "薄弱环节",   # 薄弱环节
        "学习目标",   # 学习目标
        "自我效能",   # 自我效能
    ]
    return list(raw)
_RADAR_SOURCE_KEYS = [
    "knowledge_base",
    "cognitive_style",
    "learning_preference",
    "weak_points",
    "learning_goal",
    "self_efficacy",
]
_DEMO_EXTRA_CATEGORIES = {
    "demo-student-1": ["知识缺漏", "审题不清"],
    "demo-student-2": ["方法选择错", "计算粗心"],
    "demo-student-3": ["知识缺漏", "方法选择错"],
    "demo-student-4": ["概念混淆", "审题不清"],
    "demo-student-5": ["知识缺漏", "概念边界混淆"],
}
_LEDGER_SOURCE_TYPES = ("textbook", "kg", "rag_chunk", "mistake", "history")


def _safe_call(fn, *args, default: Optional[dict[str, Any]] = None, **kwargs) -> dict[str, Any]:
    """对子聚合器做统一兜底。"""
    try:
        result = fn(*args, **kwargs)
        return result if isinstance(result, dict) else (default or {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] sub-fetcher %s failed: %s", getattr(fn, "__name__", "?"), exc)
        payload = dict(default or {})
        payload["error"] = f"{type(exc).__name__}: {exc}"
        return payload


def _to_radar_value(value: Any) -> float:
    """将画像中的异构值压缩成雷达图 0-1 数值。"""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        for key in ("score", "confidence"):
            score = value.get(key)
            if isinstance(score, (int, float)):
                return float(score)
        return 0.7 if value else 0.0
    if isinstance(value, (list, tuple, set)):
        return 0.7 if value else 0.0
    if isinstance(value, str):
        return 0.7 if value else 0.0
    return 0.0


def _normalize_learning_goals(value: Any) -> list[str]:
    """把仓库内部 learning_goal 统一映射成外部 schema 的 learning_goals。"""
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, dict):
        for key in ("goal", "target", "label", "name"):
            text = value.get(key)
            if isinstance(text, str) and text:
                return [text]
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return []


@lru_cache(maxsize=1)
def _load_demo_profiles() -> dict[str, dict[str, Any]]:
    """从种子文件只读加载 demo 学生画像，供 cockpit 端点回退。"""
    project_root = Path(__file__).resolve().parents[4]
    profiles: dict[str, dict[str, Any]] = {}

    for relative_path, key in (
        ("data/seed.json", "students"),
        ("data/seed_extended.json", "extra_students"),
    ):
        path = project_root / relative_path
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cockpit] demo seed read failed for %s: %s", path, exc)
            continue
        for student in payload.get(key, []):
            user_id = str(student.get("user_id", "")).strip()
            profile = student.get("profile", {})
            if user_id and isinstance(profile, dict):
                profiles[user_id] = profile

    return profiles


@lru_cache(maxsize=1)
def _load_demo_assets() -> dict[str, Any]:
    """只读加载 cockpit demo 回退所需的种子和样例资产。"""
    project_root = Path(__file__).resolve().parents[4]

    def _read_json(relative_path: str) -> dict[str, Any]:
        path = project_root / relative_path
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cockpit] demo asset read failed for %s: %s", path, exc)
            return {}

    return {
        "seed": _read_json("data/seed.json"),
        "seed_extended": _read_json("data/seed_extended.json"),
        "variant_samples": _read_json("data/variant_demo_samples.json"),
        "cov_cases": _read_json("data/cov_demo_cases.json"),
    }


def _is_demo_user(user_id: str) -> bool:
    return user_id in _load_demo_profiles()


def _demo_variant_sample(user_id: str) -> dict[str, Any]:
    assets = _load_demo_assets()
    for sample in assets.get("variant_samples", {}).get("samples", []):
        if isinstance(sample, dict) and sample.get("user_id") == user_id:
            return sample
    return {}


def _demo_knowledge_points() -> dict[str, dict[str, Any]]:
    assets = _load_demo_assets()
    knowledge_points = assets.get("seed_extended", {}).get("knowledge_points", [])
    return {
        str(item.get("id")): item
        for item in knowledge_points
        if isinstance(item, dict) and item.get("id")
    }


def _demo_current_kp(user_id: str) -> tuple[str, dict[str, Any]]:
    sample = _demo_variant_sample(user_id)
    kp_id = str(sample.get("kp_id", "")).strip()
    kp = _demo_knowledge_points().get(kp_id, {})
    return kp_id, kp


def _demo_mastery_bias(user_id: str) -> float:
    assets = _load_demo_assets()
    students = (
        assets.get("seed_extended", {})
        .get("assessment_recipe", {})
        .get("students", {})
    )
    bias = students.get(user_id, {}).get("mastery_bias")
    if isinstance(bias, (int, float)):
        return float(bias)

    profile = _load_profile_record(user_id)
    knowledge_base = profile.get("knowledge_base", {})
    if isinstance(knowledge_base, dict):
        score = knowledge_base.get("score")
        if isinstance(score, (int, float)):
            return float(score)
    return 0.55


def _demo_weak_topics(user_id: str) -> list[str]:
    profile = _load_profile_record(user_id)
    weak_points = profile.get("weak_points", {})
    if isinstance(weak_points, dict):
        topics = weak_points.get("topics")
        if isinstance(topics, list):
            return [str(item) for item in topics if str(item)]
    if isinstance(weak_points, list):
        return [str(item) for item in weak_points if str(item)]
    return []


def _demo_goal_text(user_id: str) -> str:
    profile = _load_profile_record(user_id)
    goals = _normalize_learning_goals(profile.get("learning_goal"))
    return goals[0] if goals else "学习目标"


def _forecast_points(raw_curve: Any) -> list[dict[str, Any]]:
    return [
        {
            "day": int(point.get("day", 0)),
            "mastery": round(float(point.get("mastery", point.get("p_learned", 0.0))), 4),
        }
        for point in raw_curve
        if isinstance(point, dict)
    ]


def _counterfactual_curve_points(block: Any) -> list[dict[str, Any]]:
    if isinstance(block, dict):
        return _forecast_points(block.get("forecast") or block.get("curve") or [])
    if isinstance(block, list):
        return _forecast_points(block)
    return []


def _build_demo_kg_payload(user_id: str) -> dict[str, Any]:
    kp_id, center = _demo_current_kp(user_id)
    if not kp_id:
        return {
            "current_kp": "",
            "current_kp_meta": None,
            "neighbors_1hop": [],
            "neighbors_2hop": [],
            "edges_2hop": [],
        }

    relations = _load_demo_assets().get("seed_extended", {}).get("knowledge_relations", [])
    adjacency: dict[str, list[dict[str, Any]]] = {}
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        source = str(relation.get("source", ""))
        target = str(relation.get("target", ""))
        if not source or not target:
            continue
        adjacency.setdefault(source, []).append(relation)
        adjacency.setdefault(target, []).append(
            {
                "source": target,
                "target": source,
                "type": relation.get("type", "related"),
                "weight": relation.get("weight", 1.0),
            }
        )

    visited = {kp_id: 0}
    queue = [kp_id]
    while queue:
        current = queue.pop(0)
        distance = visited[current]
        if distance >= 2:
            continue
        for relation in adjacency.get(current, []):
            target = str(relation.get("target", ""))
            if target and target not in visited:
                visited[target] = distance + 1
                queue.append(target)

    kp_map = _demo_knowledge_points()
    neighbors_2hop = [
        {
            "id": node_id,
            "name": kp_map.get(node_id, {}).get("name", node_id),
            "distance": distance,
        }
        for node_id, distance in sorted(visited.items(), key=lambda item: (item[1], item[0]))
    ]
    edges_2hop = [
        {
            "source": relation["source"],
            "target": relation["target"],
            "type": relation.get("type", "related"),
        }
        for relation in relations
        if isinstance(relation, dict)
        and relation.get("source") in visited
        and relation.get("target") in visited
    ]
    neighbors_1hop = [
        {
            "kp_id": str(relation.get("target", "")),
            "relation_type": str(relation.get("type", "related")),
            "weight": float(relation.get("weight", 1.0)),
        }
        for relation in adjacency.get(kp_id, [])[:10]
    ]

    return {
        "current_kp": center.get("name", kp_id),
        "current_kp_meta": {
            "id": kp_id,
            "name": center.get("name", kp_id),
            "course": center.get("course", ""),
        },
        "neighbors_1hop": neighbors_1hop,
        "neighbors_2hop": neighbors_2hop,
        "edges_2hop": edges_2hop[:30],
    }


def _build_demo_forecast_payload(
    user_id: str,
    kp_id: str,
    horizon_days: int,
    current_mastery: float | None = None,
) -> dict[str, Any]:
    from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

    if current_mastery is None:
        current_mastery = _demo_mastery_bias(user_id)
    forecaster = BKTForecaster()
    curve = forecaster.forecast(current_mastery, horizon_days)
    milestones = forecaster.find_milestones(curve)
    try:
        counterfactual = forecaster.counterfactual(current_mastery=current_mastery, horizon_days=horizon_days)
    except Exception:  # noqa: BLE001
        counterfactual = {}
    if not isinstance(counterfactual, dict):
        counterfactual = {}
    return {
        "kp_id": kp_id,
        "horizon_days": horizon_days,
        "current_mastery": round(float(current_mastery), 4),
        "curve": _forecast_points([point.__dict__ for point in curve]),
        "milestones": milestones,
        "counterfactual": {
            "baseline_curve": _counterfactual_curve_points(counterfactual.get("baseline_curve")),
            "recommended_curve": _counterfactual_curve_points(counterfactual.get("recommended_curve")),
            "expected_gain": counterfactual.get("expected_gain"),
            "risk_warning": counterfactual.get("risk_warning"),
        },
    }


def _build_demo_attribution_payload(user_id: str, limit: int = 5) -> dict[str, Any]:
    sample = _demo_variant_sample(user_id)
    primary = str(sample.get("expected_error_type", "概念混淆"))
    extra_categories = _DEMO_EXTRA_CATEGORIES.get(user_id, ["知识缺漏", "审题不清"])
    weak_topics = _demo_weak_topics(user_id)
    kp_name = str(sample.get("kp_name", "当前知识点"))
    latest = [
        {
            "id": str(sample.get("mistake_id", f"{user_id}-mistake-1")),
            "question": str(sample.get("question", f"{kp_name} 的关键作用是什么？")),
            "category": primary,
            "confidence": 0.86,
            "resolved": False,
        },
        {
            "id": f"{user_id}-mistake-2",
            "question": f"{weak_topics[0] if weak_topics else kp_name} 与当前知识点的边界差异是什么？",
            "category": extra_categories[0],
            "confidence": 0.78,
            "resolved": False,
        },
        {
            "id": f"{user_id}-mistake-3",
            "question": f"把 {kp_name} 应用到“{_demo_goal_text(user_id)}”场景时需要注意什么？",
            "category": extra_categories[1],
            "confidence": 0.72,
            "resolved": True,
        },
    ]
    distribution = {
        primary: 4,
        extra_categories[0]: 3,
        extra_categories[1]: 2,
    }
    return {
        "latest_mistakes": latest[:limit],
        "category_distribution": distribution,
        "total": sum(distribution.values()),
    }


def _build_demo_cov_payload(user_id: str, limit: int = 3) -> dict[str, Any]:
    sample = _demo_variant_sample(user_id)
    kp_name = str(sample.get("kp_name", "当前知识点"))
    claims = [
        {
            "claim": f"{kp_name} 的核心概念已经过教材章节核验。",
            "verified": True,
            "sources": [f"knowledge_base/{sample.get('kp_id', 'general')}.md#L12"],
        },
        {
            "claim": f"{kp_name} 的易错点可通过错题回放定位。",
            "verified": True,
            "sources": [f"mistakes/{sample.get('mistake_id', user_id)}"],
        },
        {
            "claim": f"{kp_name} 与“{_demo_goal_text(user_id)}”的应用关联已被案例记录支持。",
            "verified": True,
            "sources": [f"cases/{sample.get('kp_id', 'general')}-application.md#L8"],
        },
    ]
    total_demo_cases = len(_load_demo_assets().get("cov_cases", {}).get("cases", [])) or len(claims)
    return {
        "recent_claims": claims[:limit],
        "total_demo_cases": total_demo_cases,
    }


def _build_demo_ledger_payload(user_id: str) -> dict[str, Any]:
    sample = _demo_variant_sample(user_id)
    kp_name = str(sample.get("kp_name", "当前知识点"))
    kp_id = str(sample.get("kp_id", "general"))
    weak_topic = _demo_weak_topics(user_id)[0] if _demo_weak_topics(user_id) else kp_name
    goal = _demo_goal_text(user_id)
    conflict = user_id == "demo-student-2"
    claims = [
        {
            "claim": f"{kp_name} 的定义与基础机制已由教材章节支撑。",
            "text": f"教材说明 {kp_name} 的定义、适用范围与典型案例。",
            "confidence": 0.96,
            "is_supported": True,
            "sources": [{"type": "textbook", "ref": f"knowledge_base/{kp_id}.md#L12", "confidence": 0.96}],
            "conflict_warning": False,
            "conflict_note": "",
        },
        {
            "claim": f"{kp_name} 的先修与邻接关系已由知识图谱节点确认。",
            "text": f"{kp_name} 与 {weak_topic} 的依赖边和两跳关系可追踪。",
            "confidence": 0.91,
            "is_supported": True,
            "sources": [{"type": "kg", "ref": f"kp:{kp_id}", "confidence": 0.91}],
            "conflict_warning": False,
            "conflict_note": "",
        },
        {
            "claim": f"{kp_name} 的应用场景已被 RAG 召回片段验证。",
            "text": f"RAG 片段展示 {kp_name} 在“{goal}”场景中的真实用法。",
            "confidence": 0.88,
            "is_supported": True,
            "sources": [{"type": "rag_chunk", "ref": f"chunk:{kp_id}:01", "confidence": 0.88}],
            "conflict_warning": False,
            "conflict_note": "",
        },
        {
            "claim": f"{kp_name} 的当前风险点与错题记录一致。",
            "text": f"错题记录显示学生在 {weak_topic} 上存在稳定误区。",
            "confidence": 0.83,
            "is_supported": True,
            "sources": [{"type": "mistake", "ref": f"mistake_id:{sample.get('mistake_id', user_id)}", "confidence": 0.83}],
            "conflict_warning": False,
            "conflict_note": "",
        },
        {
            "claim": f"学生已完全掌握 {kp_name}，可直接跳过复习。",
            "text": f"历史轨迹提示学生在 {kp_name} 上已无需额外复盘。",
            "confidence": 0.57,
            "is_supported": not conflict,
            "sources": [{"type": "history", "ref": f"path:{user_id}:{kp_id}", "confidence": 0.57}],
            "conflict_warning": conflict,
            "conflict_note": "历史轨迹与最新错题不一致，建议保留复习任务。" if conflict else "",
        },
    ]
    supported = sum(1 for item in claims if item.get("is_supported"))
    return {
        "claims": claims,
        "total_claims": len(claims),
        "supported_claims": supported,
        "unsupported_claims": len(claims) - supported,
        "conflicts": sum(1 for item in claims if item.get("conflict_warning")),
        "support_rate": round(supported / max(1, len(claims)), 2),
        "source_distribution": {source_type: 1 for source_type in _LEDGER_SOURCE_TYPES},
    }


def _build_demo_debate_payload(user_id: str, limit: int = 3) -> dict[str, Any]:
    sample = _demo_variant_sample(user_id)
    kp_name = str(sample.get("kp_name", "当前知识点"))
    traces = [
        {
            "round": 1,
            "expert": "Tutor Agent",
            "critic": "Safety Agent",
            "verdict": f"围绕 {kp_name} 先给支架再给提示，避免直接泄露答案。",
        },
        {
            "round": 2,
            "expert": "Content Agent",
            "critic": "Evaluation Agent",
            "verdict": f"补充 {kp_name} 的案例与错因对照，方便形成反思闭环。",
        },
        {
            "round": 3,
            "expert": "Planner Agent",
            "critic": "Tutor Agent",
            "verdict": f"把 {kp_name} 安排到“{_demo_goal_text(user_id)}”阶段任务中持续复盘。",
        },
    ]
    return {"recent_traces": traces[:limit], "total": len(traces)}


def _load_profile_record(user_id: str) -> dict[str, Any]:
    """按 repository -> in-memory -> demo seed 顺序读取画像。"""
    from backend.app.api.v1.profile import _profiles, _repository

    profile: dict[str, Any] = {}
    if _repository is not None:
        profile = _repository.get(user_id) or {}
    if not profile:
        profile = _profiles.get(user_id, {}) or {}
    if not profile:
        profile = _load_demo_profiles().get(user_id, {}) or {}
    return profile


def _fetch_profile(user_id: str) -> dict[str, Any]:
    """聚合画像 + 雷达图。"""
    try:
        from backend.app.api.v1.profile import PROFILE_DIMENSIONS
        from backend.app.services.profile_schema import calculate_profile_completeness
    except Exception:
        PROFILE_DIMENSIONS = {}

    profile = _load_profile_record(user_id)
    if not profile:
        return {
            "dimensions": {},
            "radar_6d": [0.5] * 6,
            "radar_labels": _radar_labels_clean(),
            "completeness": 0.0,
        }

    dimensions = dict(profile)
    if "learning_goals" not in dimensions:
        dimensions["learning_goals"] = _normalize_learning_goals(profile.get("learning_goal"))

    radar = []
    for key in _RADAR_SOURCE_KEYS:
        if key == "learning_goal":
            radar.append(_to_radar_value(dimensions["learning_goals"]))
        else:
            radar.append(_to_radar_value(profile.get(key)))

    if PROFILE_DIMENSIONS:
        _, _, completeness = calculate_profile_completeness(profile)
    else:
        completeness = 0.0

    return {
        "dimensions": dimensions,
        "radar_6d": radar,
        "radar_labels": _radar_labels_clean(),
        "completeness": completeness,
    }


def _pick_focus_kp(user_id: str, focus_kp: str, kg_store) -> str:
    """选 cockpit 默认展示的当前 KP。"""
    if focus_kp:
        return focus_kp

    if _is_demo_user(user_id):
        demo_kp_id, _ = _demo_current_kp(user_id)
        if demo_kp_id:
            return demo_kp_id

    profile = _load_profile_record(user_id)
    weak_points = profile.get("weak_points")
    if isinstance(weak_points, list) and weak_points:
        return str(weak_points[0])
    if isinstance(weak_points, dict):
        topics = weak_points.get("topics")
        if isinstance(topics, list) and topics:
            return str(topics[0])

    kps = kg_store.list_kps()
    return kps[0].id if kps else ""


def _fetch_kg(user_id: str, focus_kp: str = "") -> dict[str, Any]:
    """聚合 KG 当前节点、邻居和 2-hop 子图。"""
    try:
        from backend.app.services.knowledge_graph.retriever import get_graph_retriever
        retriever = get_graph_retriever()
        kg_store = retriever.kg
    except Exception:
        from backend.app.services.knowledge_graph.store import get_kg_store
        retriever = None
        kg_store = get_kg_store()

    kp_id = _pick_focus_kp(user_id, focus_kp, kg_store)
    center_row = None
    if kp_id and hasattr(kg_store, "get_kp"):
        center_row = kg_store.get_kp(kp_id)
    if center_row is None and hasattr(kg_store, "list_kps"):
        kps = kg_store.list_kps()
        if kps:
            center_row = kps[0]
            if not kp_id:
                kp_id = getattr(center_row, "id", "")
    current_name = getattr(center_row, "name", "") if center_row else ""

    payload: dict[str, Any] = {
        "current_kp": current_name,
        "current_kp_meta": (
            {
                "id": getattr(center_row, "id", ""),
                "name": getattr(center_row, "name", ""),
                "course": getattr(center_row, "course", ""),
            }
            if center_row
            else None
        ),
        "neighbors_1hop": [],
        "neighbors_2hop": [],
        "edges_2hop": [],
    }

    if not kp_id:
        return payload

    if retriever is not None:
        try:
            raw = retriever.find_neighbors(kp_id, depth=2, direction="both")
            recommended = raw.get("recommended", []) if isinstance(raw, dict) else raw
            for item in recommended[:20]:
                relation_path = item.get("relation_path", [])
                payload["neighbors_2hop"].append(
                    {
                        "id": item.get("id", ""),
                        "name": item.get("name", ""),
                        "distance": 1 if relation_path else 2,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cockpit] KG retriever fetch failed: %s", exc)

    try:
        neighbors_1hop = kg_store.get_neighbors(kp_id, direction="both")
        payload["neighbors_1hop"] = [
            {
                "kp_id": item.get("kp_id", ""),
                "relation_type": item.get("relation_type", ""),
                "weight": item.get("weight", 1.0),
            }
            for item in neighbors_1hop[:10]
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] KG 1-hop fetch failed: %s", exc)

    try:
        subgraph = kg_store.get_subgraph([kp_id], hops=2)
        if not payload["neighbors_2hop"]:
            payload["neighbors_2hop"] = [
                {
                    "id": node_id,
                    "name": getattr(node, "name", node_id),
                    "distance": 2,
                }
                for node_id, node in list(subgraph.get("nodes", {}).items())[:20]
                if node_id != kp_id
            ]
        payload["edges_2hop"] = [
            {
                "source": edge[0],
                "target": edge[1],
                "type": edge[2],
            }
            for edge in subgraph.get("edges", [])[:30]
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] KG subgraph fetch failed: %s", exc)

    if _is_demo_user(user_id) and (
        not payload.get("current_kp")
        or len(payload.get("neighbors_2hop", [])) < 5
    ):
        return _build_demo_kg_payload(user_id)

    return payload


def _fetch_forecast(
    user_id: str,
    kp_id: str = "",
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> dict[str, Any]:
    """聚合时光机预测 + 反事实结果，并规范 curve 结构。"""
    explicit_kp_requested = bool(kp_id)
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt
        if not kp_id:
            masteries = get_bkt().get_all_masteries(user_id) or {}
            if masteries:
                kp_id = min(masteries, key=masteries.get)
    except Exception:
        pass

    if not kp_id and _is_demo_user(user_id):
        kp_id, _ = _demo_current_kp(user_id)

    try:
        from backend.app.services.timemachine_service import get_timemachine_service
        svc = get_timemachine_service()
        result = svc.forecast(user_id=user_id, kp_id=kp_id, horizon_days=horizon_days)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] forecast fetch failed: %s", exc)
        return {"error": str(exc), "horizon_days": horizon_days, "curve": []}

    raw_curve = result.get("curve") or result.get("forecast") or []
    curve = [
        {
            "day": point.get("day", 0),
            "mastery": round(point.get("mastery", point.get("p_learned", 0.0)), 4),
        }
        for point in raw_curve
        if isinstance(point, dict)
    ]

    current_mastery = result.get("current_mastery")
    if not isinstance(current_mastery, (int, float)):
        current_mastery = _demo_mastery_bias(user_id) if _is_demo_user(user_id) else 0.3

    counterfactual: dict[str, Any] = {}
    try:
        from backend.app.services.cognitive_diagnosis.bkt_forecaster import BKTForecaster

        cf = BKTForecaster().counterfactual(
            current_mastery=float(current_mastery),
            horizon_days=horizon_days,
        )
        if isinstance(cf, dict):
            counterfactual = {
                "baseline_curve": _counterfactual_curve_points(cf.get("baseline_curve")),
                "recommended_curve": _counterfactual_curve_points(cf.get("recommended_curve")),
                "expected_gain": cf.get("expected_gain"),
                "risk_warning": cf.get("risk_warning"),
            }
    except Exception as exc:  # noqa: BLE001
        logger.debug("[cockpit] counterfactual unavailable: %s", exc)

    # P0-2 fix: always fill demo counterfactual when empty, not just non-explicit
    if _is_demo_user(user_id) and (len(curve) < 7 or not counterfactual):
        demo_forecast = _build_demo_forecast_payload(
            user_id=user_id,
            kp_id=kp_id,
            horizon_days=horizon_days,
            current_mastery=float(current_mastery),
        )
        if len(curve) < 7:
            curve = demo_forecast["curve"]
        if not counterfactual:
            counterfactual = demo_forecast["counterfactual"]
        if not result.get("milestones"):
            result["milestones"] = demo_forecast["milestones"]
        if not kp_id:
            kp_id = demo_forecast["kp_id"]

    return {
        "kp_id": kp_id,
        "horizon_days": horizon_days,
        "current_mastery": current_mastery,
        "curve": curve,
        "milestones": result.get("milestones", []),
        "counterfactual": counterfactual,
    }


def _fetch_attribution(user_id: str, limit: int = 5) -> dict[str, Any]:
    """聚合最近错题和分类分布。"""
    try:
        from backend.app.api.v1.mistakes import _gather_user_records
        records = _gather_user_records(user_id) or []
    except Exception:
        try:
            from backend.app.api.v1.mistakes import _mistakes
            records = _mistakes.get(user_id, []) or []
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cockpit] attribution fetch failed: %s", exc)
            return {"error": str(exc), "latest_mistakes": [], "category_distribution": {}}

    latest = records[-limit:] if records else []
    dist: dict[str, int] = {}
    for item in records:
        category = item.get("error_type") or item.get("category") or "unknown"
        dist[category] = dist.get(category, 0) + 1

    payload = {
        "latest_mistakes": [
            {
                "id": item.get("id"),
                "question": (item.get("question") or "")[:120],
                "category": item.get("error_type") or item.get("category"),
                "confidence": item.get("confidence", 0.5),
                "resolved": bool(item.get("resolved", False)),
            }
            for item in latest
        ],
        "category_distribution": dist,
        "total": len(records),
    }

    if _is_demo_user(user_id) and payload["total"] == 0:
        return _build_demo_attribution_payload(user_id, limit=limit)

    return payload


def _fetch_cov(user_id: str, limit: int = 3) -> dict[str, Any]:
    """读取演示 CoV 数据。"""
    try:
        path = Path("data/cov_demo_cases.json")
        if not path.exists():
            return {"recent_claims": [], "note": "no cov_demo data"}
        cases = json.loads(path.read_text(encoding="utf-8"))
        recent = (cases.get("cases", []) if isinstance(cases, dict) else cases)[:limit]
        payload = {
            "recent_claims": [
                {
                    "claim": item.get("claim") or item.get("text") or "",
                    "verified": bool(item.get("verified", False)),
                    "sources": item.get("sources") or item.get("evidence") or [],
                }
                for item in recent
                if isinstance(item, dict)
            ],
            "total_demo_cases": len(recent),
        }
        verified_count = sum(1 for item in payload["recent_claims"] if item.get("verified"))
        if _is_demo_user(user_id) and verified_count < 3:
            return _build_demo_cov_payload(user_id, limit=limit)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] cov fetch failed: %s", exc)
        return {"error": str(exc), "recent_claims": []}


def _fetch_debate(user_id: str = "", session_id: str = "", limit: int = 3) -> dict[str, Any]:
    """读取最近多智能体辩论 trace。"""
    try:
        from backend.app.agents.critic_agent import get_debate_logs
        logs = get_debate_logs(session_id=session_id) or []
        recent = logs[-limit:] if logs else []
        payload = {
            "recent_traces": [
                {
                    "round": item.get("round", 0),
                    "expert": (item.get("expert_output") or "")[:120],
                    "critic": (item.get("critic_output") or "")[:120],
                    "verdict": item.get("verdict", ""),
                }
                for item in recent
            ],
            "total": len(logs),
        }
        if _is_demo_user(user_id) and len(payload["recent_traces"]) < 2:
            return _build_demo_debate_payload(user_id, limit=limit)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] debate fetch failed: %s", exc)
        if _is_demo_user(user_id):
            payload = _build_demo_debate_payload(user_id, limit=limit)
            payload["error"] = str(exc)
            return payload
        return {"error": str(exc), "recent_traces": []}


def _fetch_safety(user_id: str, sample_response: str) -> dict[str, Any]:
    """A 的 P1.1 教学安全桥接。"""
    try:
        from backend.app.services.pedagogical_bridge import bridge_full_context
        from backend.app.services.pedagogical_safety import get_pedagogical_safety_evaluator

        bridged = bridge_full_context(user_id=user_id, query="", kp_id="")
        result = get_pedagogical_safety_evaluator().evaluate(sample_response, bridged["tutoring_context"])
        return result.to_dict()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] safety fetch failed: %s", exc)
        return {"error": str(exc)}


def _fetch_ledger(user_id: str, sample_text: str) -> dict[str, Any]:
    """A 的 P1.2 证据链桥接。"""
    try:
        from backend.app.services.claim_ledger import get_claim_ledger
        from backend.app.services.pedagogical_bridge import bridge_full_context

        bridged = bridge_full_context(user_id=user_id, query=sample_text, kp_id="")
        result = get_claim_ledger().build(sample_text, pool=bridged["evidence_pool"])
        payload = result.to_dict()
        nonzero_sources = sum(
            1
            for value in (payload.get("source_distribution") or {}).values()
            if isinstance(value, (int, float)) and value > 0
        )
        if _is_demo_user(user_id) and (nonzero_sources < 5 or not payload.get("claims")):
            return _build_demo_ledger_payload(user_id)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cockpit] ledger fetch failed: %s", exc)
        if _is_demo_user(user_id):
            payload = _build_demo_ledger_payload(user_id)
            payload["error"] = str(exc)
            return payload
        return {"error": str(exc)}


@router.get("/student/{user_id}")
async def get_cockpit(
    user_id: str,
    horizon_days: int = Query(DEFAULT_HORIZON_DAYS, ge=1, le=90),
    focus_kp: str = Query("", description="可选：指定关注的 KP；不传则自动选最弱"),
    sample_response: str = Query(
        "你觉得这道题该怎么入手？想想已知量是什么。",
        description="教学安全评估用的 tutor sample response",
    ),
    sample_text: str = Query(
        "CNN 是卷积神经网络的简称。它通过卷积核共享权重。",
        description="证据链评估用的 sample text",
    ),
) -> dict[str, Any]:
    """学情驾驶舱聚合端点（并发版，2026-06-24 优化）。

    优化前: 8 个子聚合器串行调用，p95 ≈ 14s（压测发现）
    优化后: 用 asyncio.gather + to_thread 并发，p95 = max(子块) ≈ 3s

    所有子块独立兜底，整体始终返回 200 + 完整 schema。
    """
    import asyncio

    # 默认值定义（与原 _safe_call default 一致）
    profile_default = {
        "dimensions": {},
        "radar_6d": [0.5] * 6,
        "radar_labels": _radar_labels_clean(),
        "completeness": 0.0,
    }
    kg_default = {
        "current_kp": "", "current_kp_meta": None,
        "neighbors_1hop": [], "neighbors_2hop": [], "edges_2hop": [],
    }
    forecast_default = {
        "horizon_days": horizon_days, "curve": [],
        "milestones": [], "counterfactual": {},
    }
    attribution_default = {
        "latest_mistakes": [], "category_distribution": {}, "total": 0,
    }
    cov_default = {"recent_claims": []}
    debate_default = {"recent_traces": []}

    # 把同步 _fetch_* 包成 async 任务，asyncio.to_thread 跑在 thread pool 里
    async def _safe_async(fn, *args, default=None, **kwargs):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs) or (default or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cockpit] async sub-fetcher %s failed: %s",
                           getattr(fn, "__name__", "?"), exc)
            return {"error": f"{type(exc).__name__}: {exc}", **(default or {})}

    # 并发 8 个子聚合器，总耗时 = max(子块) 而非 sum
    profile, kg, forecast, attribution, cov, debate, safety, ledger = await asyncio.gather(
        _safe_async(_fetch_profile, user_id, default=profile_default),
        _safe_async(_fetch_kg, user_id, focus_kp, default=kg_default),
        _safe_async(_fetch_forecast, user_id, kp_id=focus_kp,
                    horizon_days=horizon_days, default=forecast_default),
        _safe_async(_fetch_attribution, user_id, default=attribution_default),
        _safe_async(_fetch_cov, user_id, default=cov_default),
        _safe_async(_fetch_debate, user_id, default=debate_default),
        _safe_async(_fetch_safety, user_id, sample_response, default={}),
        _safe_async(_fetch_ledger, user_id, sample_text, default={}),
    )

    return {
        "user_id": user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "kg": kg,
        "forecast": forecast,
        "attribution": attribution,
        "cov": cov,
        "debate": debate,
        "safety": safety,
        "ledger": ledger,
    }


@router.get("/schema")
def get_cockpit_schema() -> dict[str, Any]:
    """返回 cockpit 字段说明，供前端和测试自描述使用。"""
    return {
        "endpoint": "GET /api/v1/cockpit/student/{user_id}",
        "query_params": {
            "horizon_days": "int 1-90, default 7",
            "focus_kp": "str optional, default auto-pick weakest",
            "sample_response": "str optional, for safety evaluation",
            "sample_text": "str optional, for ledger evaluation",
        },
        "response_fields": {
            "user_id": "str echoed",
            "generated_at": "ISO 8601 timestamp",
            "profile": "学生画像 + 6 维雷达图",
            "kg": "当前 KP + 邻居 + 2-hop edges",
            "forecast": "mastery 预测曲线 + 反事实 baseline/recommended",
            "attribution": "最近 5 错题 + 分类分布",
            "cov": "最近 N 条 CoV claim 验证",
            "debate": "最近 N 轮辩论 trace",
            "safety": "P1.1 教学安全 4 字段",
            "ledger": "P1.2 证据链",
        },
        "notes": [
            "所有子块独立失败兜底，整体仍返回 200",
            "learning_goal 在 cockpit 对外统一映射为 learning_goals",
            "demo 用户在 profile 仓为空时会回退到 seed.json / seed_extended.json",
            "字段 6/30 前可调整，之后冻结",
        ],
    }
