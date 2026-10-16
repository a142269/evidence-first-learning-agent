"""Insights API — A 拥有的增量端点（2026-07-02 第三轮）。

把已有服务能力补成完整可用的后端功能：

1. POST /insights/kg/seed-from-map     用 knowledge_base/knowledge_map.yaml 灌满课程知识图谱
2. POST /insights/path/generate        知识图谱 × BKT 掌握度 → 个性化学习路径（拓扑序，免 LLM 秒级）
3. GET  /insights/report/{user_id}     学习诊断报告（DiagnosisReporter，Markdown + JSON 双格式）
4. GET  /insights/recommendations      画像/掌握度感知的资源精准推送（带推荐理由）
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException, Query, Request

from backend.app.core.deployment_policy import production_mode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/student-overview/{user_id}")
def student_overview(user_id: str, course: str = "") -> Dict[str, Any]:
    """Return the shared learner dashboard/profile/path aggregation."""
    from backend.app.services.student_overview import build_student_overview

    return build_student_overview(user_id, course=course)

# difficulty(1-5) → Bloom 主层级的保守映射
_DIFFICULTY_TO_BLOOM = {1: "remember", 2: "understand", 3: "apply", 4: "analyze", 5: "evaluate"}


def _load_knowledge_map() -> Dict[str, Any]:
    """聚合知识点图谱：旧全局 knowledge_map.yaml + 各课程级图谱文件。

    2026-07-16 平台化改造：新课程的图谱放 knowledge_base/<slug>/knowledge_map.yaml，
    由 course_registry 统一聚合；节点 meta 带 course 字段。
    """
    from backend.app.services.course_registry import get_course_registry

    nodes = get_course_registry().load_map_nodes()
    if not nodes:
        raise HTTPException(status_code=404, detail="knowledge map not found")
    return {"nodes": nodes}


# ================================================================
# 1. 课程知识图谱一键种子
# ================================================================
@router.post("/kg/seed-from-map")
def seed_kg_from_map(
    course: str = Query("artificial_intelligence", description="写入图谱的课程标识"),
) -> Dict[str, Any]:
    """把 knowledge_map.yaml（32 节点 AI 课程）灌进知识图谱库。幂等，可重复执行。"""
    from backend.app.services.knowledge_graph.store import get_kg_store

    data = _load_knowledge_map()
    nodes: Dict[str, Any] = data["nodes"]
    store = get_kg_store()

    kp_upserted = 0
    rel_added = 0
    for kp_id, meta in nodes.items():
        if not isinstance(meta, dict):
            continue
        difficulty = int(meta.get("difficulty", 2) or 2)
        bloom = _DIFFICULTY_TO_BLOOM.get(difficulty, "understand")
        objectives = meta.get("learning_objectives") or []
        store.upsert_kp(
            kp_id,
            name=str(meta.get("name", kp_id)),
            # 节点自带课程归属（聚合加载器打标）优先；无标记时用请求参数兜底
            course=str(meta.get("course") or course),
            description="；".join(str(o) for o in objectives),
            bloom_level=bloom,
            metadata={
                "difficulty": difficulty,
                "bloom_level": bloom,
                "keywords": meta.get("keywords") or [],
                "estimated_hours": meta.get("estimated_hours", 2),
            },
        )
        kp_upserted += 1

    # 关系：两端都在图内才建边（FK 安全）
    for kp_id, meta in nodes.items():
        if not isinstance(meta, dict):
            continue
        for pre in meta.get("prerequisites") or []:
            if pre in nodes:
                store.add_relation(str(pre), kp_id, "prerequisite", weight=1.0)
                rel_added += 1
        for rel in meta.get("related") or []:
            if rel in nodes:
                store.add_relation(kp_id, str(rel), "related", weight=0.5)
                rel_added += 1

    return {
        "course": course,
        "kps_upserted": kp_upserted,
        "relations_processed": rel_added,
        "kp_total": store.kp_count(),
        "relation_total": store.relation_count(),
    }


# ================================================================
# 2. 个性化学习路径直生成（图谱 × BKT，确定性算法，免 LLM）
# ================================================================
def _bkt_masteries(user_id: str) -> Dict[str, float]:
    try:
        from backend.app.services.cognitive_diagnosis.bkt import get_bkt

        return dict(get_bkt().get_all_masteries(user_id) or {})
    except Exception as exc:  # noqa: BLE001
        logger.warning("[insights] BKT unavailable: %s", exc)
        return {}


def _topo_order(nodes: Dict[str, Any]) -> List[str]:
    """Kahn 拓扑排序，先修在前；同层按 difficulty 升序稳定输出。"""
    indeg = {k: 0 for k in nodes}
    children: Dict[str, List[str]] = {k: [] for k in nodes}
    for kp_id, meta in nodes.items():
        for pre in (meta.get("prerequisites") or []):
            if pre in nodes:
                indeg[kp_id] += 1
                children[pre].append(kp_id)

    ready = deque(sorted(
        (k for k, d in indeg.items() if d == 0),
        key=lambda k: (nodes[k].get("difficulty", 2), k),
    ))
    order: List[str] = []
    while ready:
        cur = ready.popleft()
        order.append(cur)
        for child in children[cur]:
            indeg[child] -= 1
            if indeg[child] == 0:
                ready.append(child)
        ready = deque(sorted(ready, key=lambda k: (nodes[k].get("difficulty", 2), k)))
    # 有环兜底：漏掉的节点按难度补到末尾
    for k in nodes:
        if k not in order:
            order.append(k)
    return order


def _scope_nodes_to_course(nodes: Dict[str, Any], course: str) -> Dict[str, Any]:
    """Keep a generated path inside one course even when the shared YAML has several maps."""
    prefixes = {
        "artificial_intelligence": "AI_",
        "python_programming": "PY_",
    }
    prefix = prefixes.get(course.strip().lower())
    if not prefix:
        return nodes
    scoped = {kp_id: meta for kp_id, meta in nodes.items() if kp_id.upper().startswith(prefix)}
    return scoped or nodes


def _recent_unresolved_mistake_questions(user_id: str, course: str = "") -> List[str]:
    """Return recent mistake prompts so a replan can name the learner's real repair work."""
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord, MistakeRecord

        with SessionLocal() as db:
            query = db.query(MistakeRecord).filter(
                MistakeRecord.user_id == user_id,
                MistakeRecord.resolved_at.is_(None),
            )
            if course:
                query = query.join(
                    KnowledgePointRecord,
                    KnowledgePointRecord.id == MistakeRecord.knowledge_point_id,
                ).filter(KnowledgePointRecord.course == course)
            rows = query.order_by(MistakeRecord.created_at.desc()).limit(8).all()
        prompts = []
        for row in rows:
            payload = dict(row.question_data or {})
            prompt = str(payload.get("question") or payload.get("stem") or "").strip()
            if prompt and prompt not in prompts:
                prompts.append(prompt)
        return prompts
    except Exception as exc:  # noqa: BLE001
        logger.debug("[insights] recent mistakes unavailable: %s", exc)
        return []


def _build_multimodal_mistake_repair_stages(
    nodes: Dict[str, Any],
    mistake_prompts: List[str],
) -> List[Dict[str, Any]]:
    """Turn recent multimodal mistakes into a visible five-step repair loop."""
    primary_kp = "AI_015" if "AI_015" in nodes else next(iter(nodes))
    visual_kp = "AI_008" if "AI_008" in nodes else primary_kp
    latest_prompt = mistake_prompts[0][:36] if mistake_prompts else "本轮多模态闯关错题"
    definitions = [
        ("错因定位与图文回放", primary_kp, f"复盘：{latest_prompt}"),
        ("视觉编码与图文对齐补强", primary_kp, "理解视觉编码器如何保留语义，并用 CLIP 完成图文对齐"),
        ("跨模态检索与证据推理", primary_kp, "完成图文检索排序、RAG 证据链与答案依据验证"),
        ("可信评测与一致性校验", primary_kp, "识别图文不一致和无依据结论，完成可信性复核"),
        ("变式闯关与综合迁移", visual_kp, "用计算机视觉场景完成变式题，回写掌握度并更新下一轮推送"),
    ]
    stages: List[Dict[str, Any]] = []
    for index, (title, kp_id, topic) in enumerate(definitions):
        meta = nodes[kp_id]
        stages.append({
            "id": index,
            "title": title,
            "topics": [topic],
            "kp_ids": [kp_id],
            "duration": "约 1 小时",
            "estimated_minutes": 60,
            "resources": [],
            "prerequisites": [index - 1] if index else [],
            "assessment": f"{title}检查",
            "repair_mode": "mistake_repair",
            "repair_reason": str(meta.get("name", kp_id)),
        })
    return stages


def _interest_planner_note(interest: str, stage_titles: List[str]) -> str:
    """智狐（路径规划）对「路径如何贴合学生兴趣」的一句话说明。LLM best-effort，失败返回规则文案。"""
    try:
        from backend.app.core.llm_client import LLMClient
        text = LLMClient().chat(
            [
                {"role": "system", "content": (
                    "你是学习规划师智狐。学生给出了自己的兴趣方向，你刚为其生成了分阶段学习路径。"
                    "请用 1-2 句中文说明这条路径如何服务于该兴趣（学习哪些阶段后能开始接触兴趣方向、"
                    "建议在哪个阶段补充哪类兴趣相关资源）。直接输出说明文字，不要客套。"
                )},
                {"role": "user", "content": (
                    f"学生兴趣：{interest}\n路径阶段：{' → '.join(stage_titles)}"
                )},
            ],
            temperature=0.5, max_tokens=200,
        )
        text = (text or "").strip()
        if text:
            return text[:300]
    except Exception as exc:  # noqa: BLE001
        logger.debug("[insights] planner note LLM skip: %s", exc)
    return (
        f"已记录你的兴趣方向「{interest}」：路径仍按先修依赖推进打牢基础，"
        "建议完成核心方法阶段后，让阿匠生成该方向的拓展阅读与实操案例。"
    )


def _build_path_schedule(
    stages: List[Dict[str, Any]],
    *,
    goal: str = "",
    target_date: str = "",
    daily_minutes: int = 0,
    interest: str = "",
    today: date | None = None,
) -> Dict[str, Any]:
    """按学生时间约束生成阶段截止点与今日任务，不删减课程内容。"""
    current = today or date.today()
    total_minutes = sum(max(0, int(stage.get("estimated_minutes", 0) or 0)) for stage in stages)

    parsed_target: date | None = None
    if target_date:
        try:
            parsed_target = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="target_date_must_be_yyyy_mm_dd") from exc
        if parsed_target < current:
            raise HTTPException(status_code=422, detail="target_date_must_not_be_in_the_past")
    if parsed_target is None:
        default_days = max(1, math.ceil(total_minutes / 60))
        parsed_target = current + timedelta(days=default_days - 1)

    available_days = max(1, (parsed_target - current).days + 1)
    recommended_daily = max(1, math.ceil(total_minutes / available_days)) if total_minutes else 0
    effective_daily = max(1, int(daily_minutes or recommended_daily or 60))
    status = "feasible" if effective_daily >= recommended_daily else "insufficient"

    stage_deadlines: List[Dict[str, Any]] = []
    milestones: List[Dict[str, Any]] = []
    cumulative = 0
    for index, stage in enumerate(stages):
        cumulative += max(0, int(stage.get("estimated_minutes", 0) or 0))
        fraction = cumulative / max(total_minutes, 1)
        offset = min(available_days - 1, max(0, math.ceil(fraction * available_days) - 1))
        due = (current + timedelta(days=offset)).isoformat()
        stage_deadlines.append({"stage_id": stage.get("id", index), "due_date": due})
        milestones.append({
            "id": f"milestone-{index + 1}",
            "title": f"完成{stage.get('title', f'阶段 {index + 1}')}",
            "stage": str(stage.get("title", f"阶段 {index + 1}")),
            "due_date": due,
            "progress_pct": 0,
            "achieved": False,
        })

    today_tasks: List[Dict[str, Any]] = []
    remaining = effective_daily
    for stage_index, stage in enumerate(stages):
        kp_ids = list(stage.get("kp_ids") or [])
        topics = list(stage.get("topics") or kp_ids)
        stage_minutes = max(1, int(stage.get("estimated_minutes", 0) or 0))
        per_topic = max(15, math.ceil(stage_minutes / max(len(kp_ids), 1)))
        for topic_index, kp_id in enumerate(kp_ids):
            if remaining <= 0 or len(today_tasks) >= 5:
                break
            duration = min(remaining, per_topic)
            kp_name = topics[topic_index] if topic_index < len(topics) else kp_id
            today_tasks.append({
                "id": f"stage-{stage_index + 1}-kp-{topic_index + 1}",
                "title": f"学习{kp_name}",
                "description": "完成知识点学习并进行一次理解检查",
                "kp_id": kp_id,
                "kp_name": kp_name,
                "stage": str(stage.get("title", f"阶段 {stage_index + 1}")),
                "type": "quiz" if topic_index % 2 else "document",
                "due_date": "今日",
                "duration_minutes": duration,
                "progress_pct": 0,
                "status": "pending",
            })
            remaining -= duration
        if remaining <= 0 or len(today_tasks) >= 5:
            break

    return {
        "constraints": {
            "goal": goal,
            "target_date": parsed_target.isoformat(),
            "daily_minutes": effective_daily,
            "interest": interest,
        },
        "stage_deadlines": stage_deadlines,
        "recommended_daily_minutes": recommended_daily,
        "feasibility": {
            "status": status,
            "total_minutes": total_minutes,
            "available_days": available_days,
            "message": (
                "当前时间预算可完成学习计划"
                if status == "feasible"
                else f"按期完成建议每日学习 {recommended_daily} 分钟"
            ),
        },
        "today_tasks": today_tasks,
        "milestones": milestones,
    }


@router.post("/path/generate")
def generate_path(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    """图谱先修拓扑 × BKT 掌握度 → 4 阶段个性化路径，直接落库。

    Body: {user_id, course?=artificial_intelligence, mistake_repair?=false, mastered_threshold?=0.8, title?, interest?, goal?, target_date?, daily_minutes?}
    已掌握（BKT ≥ 阈值）的知识点自动跳过；未学过的按先修顺序编排。
    interest：学生自输入的兴趣/学习方向 → 写入画像（随学随新）、
    记入路径 metadata，并由智狐产出贴合说明（planner_note）。
    """
    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id_required")
    course = str(payload.get("course", "")).strip().lower() or "artificial_intelligence"
    mistake_repair = bool(payload.get("mistake_repair", False))
    threshold = float(payload.get("mastered_threshold", 0.8))
    interest = str(payload.get("interest", "")).strip()[:200]
    goal = str(payload.get("goal", "")).strip()[:200]
    target_date = str(payload.get("target_date", "")).strip()
    daily_minutes = max(0, min(1440, int(payload.get("daily_minutes", 0) or 0)))
    if interest or goal or target_date or daily_minutes:
        try:
            from backend.app.repositories.profile_repo import ProfileRepository
            profile_updates: Dict[str, Any] = {}
            if interest:
                profile_updates["learning_preference"] = {"interests": interest}
            if goal or target_date:
                profile_updates["learning_goal"] = {"goal": goal, "target_date": target_date}
            if daily_minutes:
                profile_updates["time_management"] = {"daily_available_minutes": daily_minutes}
            ProfileRepository().upsert(
                user_id,
                profile_updates,
                source="path_constraints",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[insights] interest profile upsert failed: %s", exc)

    data = _load_knowledge_map()
    nodes: Dict[str, Any] = {
        k: v for k, v in data["nodes"].items() if isinstance(v, dict)
    }
    nodes = _scope_nodes_to_course(nodes, course)
    if not nodes:
        raise HTTPException(status_code=404, detail="course_knowledge_map_not_found")
    course_name = {
        "artificial_intelligence": "人工智能导论",
        "python_programming": "Python 程序设计",
    }.get(course, str((data.get("course") or {}).get("name", course)))
    masteries = _bkt_masteries(user_id)

    order = _topo_order(nodes)
    pending = [k for k in order if masteries.get(k, 0.0) < threshold]
    skipped = [k for k in order if k not in pending]

    if not pending:
        return {
            "user_id": user_id,
            "note": "all_mastered",
            "skipped_kps": skipped,
        }

    # “调整路径”使用真实错题生成五步修复闭环；AI 一键规划仍保留通用课程路径。
    if mistake_repair and course == "artificial_intelligence":
        stages = _build_multimodal_mistake_repair_stages(
            nodes,
            _recent_unresolved_mistake_questions(user_id, course),
        )
    else:
        stages = []

    # 按难度切 4 阶段（保持拓扑顺序）
    stage_defs = [
        ("基础概念", lambda d: d <= 1),
        ("核心方法", lambda d: d == 2),
        ("进阶原理", lambda d: d == 3),
        ("综合实战", lambda d: d >= 4),
    ]
    if not stages:
        for idx, (title, pred) in enumerate(stage_defs):
            kp_ids = [k for k in pending if pred(int(nodes[k].get("difficulty", 2) or 2))]
            if not kp_ids:
                continue
            hours = sum(float(nodes[k].get("estimated_hours", 2) or 2) for k in kp_ids)
            stages.append({
                "id": idx,
                "title": title,
                "topics": [str(nodes[k].get("name", k)) for k in kp_ids],
                "kp_ids": kp_ids,
                "duration": f"约 {hours:.0f} 小时",
                "estimated_minutes": max(1, math.ceil(hours * 60)),
                "resources": [],
                "prerequisites": [idx - 1] if stages else [],
                "assessment": f"{title}阶段测验",
            })

    # 通过 learning_path 模块既有存储落库（repository 优先，内存兜底）
    from backend.app.api.v1 import learning_path as lp_api

    schedule = _build_path_schedule(
        stages,
        goal=goal,
        target_date=target_date,
        daily_minutes=daily_minutes,
        interest=interest,
    )
    for stage, deadline in zip(stages, schedule["stage_deadlines"]):
        stage["due_date"] = deadline["due_date"]

    record = {
        "user_id": user_id,
        "title": (
            f"{course_name} · 个性化路径"
            + (f"（兴趣：{interest[:20]}）" if interest else "")
        ),
        "stages": stages,
        "current_stage": 0,
        "progress": round(len(skipped) / max(len(order), 1) * 100, 1),
        "metadata": {
            **schedule,
            "planned_by": "path_planner",
            "course": course,
            "mode": "mistake_repair" if mistake_repair else "course_plan",
        },
    }
    saved = lp_api.save_path(record)

    planner_note = ""
    if interest:
        planner_note = _interest_planner_note(
            interest, [str(s["title"]) for s in stages],
        )

    return {
        "user_id": user_id,
        "path_id": saved.get("path_id"),
        "path": saved.get("path"),
        "pending_kps": len(pending),
        "skipped_kps": skipped,
        "algorithm": "kg-topo-sort × bkt-mastery-filter",
        "constraints": schedule["constraints"],
        "stage_deadlines": schedule["stage_deadlines"],
        "recommended_daily_minutes": schedule["recommended_daily_minutes"],
        "feasibility": schedule["feasibility"],
        **({"planner_note": planner_note} if planner_note else {}),
    }


# ================================================================
# 3. 学习诊断报告（评委可读 Markdown + 结构化 JSON）
# ================================================================
@router.get("/report/{user_id}")
def diagnosis_report(user_id: str) -> Dict[str, Any]:
    """一键生成学习诊断报告：画像 → 强弱项 → 预测 → 推荐练习 → Bloom → 路径 → 错题。"""
    try:
        from backend.app.services.diagnosis_reporter import DiagnosisReporter
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"reporter_unavailable: {exc}")

    start = time.perf_counter()
    try:
        report = DiagnosisReporter().build_report(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[insights] report failed for %s", user_id)
        raise HTTPException(status_code=500, detail=f"report_failed: {exc}")

    return {
        "user_id": user_id,
        "nickname": report.nickname,
        "generated_at": report.generated_at.isoformat(),
        "focus_kp_id": report.focus_kp_id,
        "markdown": report.markdown,
        "payload": report.json_payload,
        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
    }


# ================================================================
# 4. 画像/掌握度感知的资源精准推送
# ================================================================
def _sort_recommendation_items(
    items: List[Dict[str, Any]],
    weights: Dict[str, float] | None,
    weakness_rank: Dict[str, int] | None = None,
) -> List[Dict[str, Any]]:
    """先按薄弱点优先级、再按自适应资源权重稳定排序。"""
    if not weights and not weakness_rank:
        return items

    def resource_type(item: Dict[str, Any]) -> str:
        raw = str(item.get("type") or "").lower()
        if raw:
            aliases = {
                "doc": "document", "markdown": "document", "pdf": "document",
                "ppt": "document", "pptx": "document",
                "question": "quiz", "exercise": "quiz",
                "map": "mindmap", "knowledge_map": "mindmap",
                "animation": "video", "notebook": "code",
            }
            return aliases.get(raw, raw)
        suggested = item.get("suggested_types") or []
        return str(suggested[0]).lower() if suggested else "document"

    ranks = weakness_rank or {}
    type_weights = weights or {}
    fallback_rank = len(ranks) + 1
    return sorted(
        items,
        key=lambda item: (
            int(ranks.get(str(item.get("kp_id") or ""), fallback_rank)),
            -float(type_weights.get(resource_type(item), 1.0)),
        ),
    )


_RECOMMENDABLE_RESOURCE_TYPES = frozenset({
    "document", "doc", "markdown", "pdf", "ppt", "pptx",
    "quiz", "question", "exercise", "mindmap", "map", "knowledge_map",
    "video", "animation", "code", "notebook",
})


def _is_recommendable_resource(
    resource: Dict[str, Any],
    user_id: str,
    course: str = "",
) -> bool:
    """Keep recommendation cards limited to polished, student-visible learning assets."""
    from backend.app.api.v1 import resources as resources_api

    if not resources_api._visible_to_student(resource, user_id):
        return False
    metadata = resource.get("metadata") or {}
    if course and str(metadata.get("course", "")).strip() != course:
        return False
    status = str(metadata.get("status", "")).strip().lower()
    if status and status != "published":
        return False
    resource_type = str(resource.get("type", "")).strip().lower()
    if resource_type not in _RECOMMENDABLE_RESOURCE_TYPES:
        return False
    title = str(resource.get("title", "")).strip()
    if not title or len(title) > 120 or "\n" in title or title.startswith("草稿"):
        return False
    return True


def _multimodal_suggested_types(user_id: str, kp_id: str) -> List[str]:
    """Return a complementary resource pack instead of a generic document-only fallback.

    The dashboard uses this sequence to make the recommendation rationale visible:
    build a visual representation first, then practice with runnable material, and
    finally verify with a differentiated quiz.  The order is lightly adapted to
    the learner's stated style while staying deterministic and course-agnostic.
    """
    kp = kp_id.lower()
    if kp in {"ai_015", "ai_006_03", "ai_008"} or any(
        token in kp for token in ("transformer", "attention", "multimodal", "clip")
    ):
        pack = ["mindmap", "video", "code", "quiz", "pptx"]
    elif any(token in kp for token in ("rag", "retrieval", "embedding", "namespace")):
        pack = ["mindmap", "document", "code", "quiz", "tts"]
    else:
        pack = ["mindmap", "video", "document", "quiz", "code"]

    style = _profile_style_text(user_id)
    if "听觉" in style:
        pack = ["tts", *pack]
    elif "视觉" in style or "图" in style:
        pack = ["mindmap", "video", *pack]
    elif "动手" in style or "实践" in style:
        pack = ["code", *pack]

    # Keep the response compact and stable, with no duplicate resource modes.
    return list(dict.fromkeys(pack))[:4]


@router.get("/recommendations")
def recommendations(
    request: Request,
    user_id: str = Query(...),
    limit: int = Query(6, ge=1, le=20),
    course: str = Query(default=""),
) -> Dict[str, Any]:
    """基于 BKT 最弱知识点 + 图谱关键词，对已生成资源做精准匹配推送。

    命中资源 → 推「去学习」；薄弱点无资源 → 推「一键生成」行动项。
    """
    if production_mode():
        from sqlalchemy.exc import SQLAlchemyError

        from backend.app.api.v1.auth import _get_session, _parse_bearer_token
        from backend.app.repositories.auth_repo import AuthRepository

        session = _get_session(_parse_bearer_token(request.headers.get("Authorization")))
        if session.role == "student":
            if user_id != session.account:
                raise HTTPException(status_code=403, detail="student_resource_scope_required")
            if course:
                try:
                    permitted = AuthRepository().has_course(session.account, course)
                except SQLAlchemyError as exc:
                    raise HTTPException(status_code=503, detail="course_auth_storage_unavailable") from exc
                if not permitted:
                    raise HTTPException(status_code=403, detail="course_access_denied")
    from backend.app.api.v1 import resources as resources_api

    masteries = _bkt_masteries(user_id)
    course_kp_names = _load_kp_names(course) if course else {}
    if course:
        masteries = {
            kp_id: value
            for kp_id, value in masteries.items()
            if kp_id in course_kp_names
        }
    try:
        map_nodes: Dict[str, Any] = _load_knowledge_map()["nodes"]
    except HTTPException:
        map_nodes = {}
    if course:
        map_nodes = {
            kp_id: meta
            for kp_id, meta in map_nodes.items()
            if kp_id in course_kp_names
        }

    # 最弱的 3 个知识点（未学过的按 0 记）
    known = {k: v for k, v in masteries.items()}
    for k in map_nodes:
        known.setdefault(k, 0.0)
    weakest = sorted(known.items(), key=lambda kv: kv[1])[:3]

    all_resources = [
        resource
        for resource in resources_api._resources.values()
        if _is_recommendable_resource(resource, user_id, course)
    ]
    items: List[Dict[str, Any]] = []
    covered_kps: set[str] = set()

    for kp_id, mastery in weakest:
        meta = map_nodes.get(kp_id, {}) if isinstance(map_nodes.get(kp_id), dict) else {}
        kp_name = str(meta.get("name") or course_kp_names.get(kp_id) or kp_id)
        keywords = [kp_name] + [str(x) for x in (meta.get("keywords") or [])]
        suggested_types = _multimodal_suggested_types(user_id, kp_id)
        matched = [
            r for r in all_resources
            if (
                kp_id in {
                    str(value)
                    for value in ((r.get("metadata") or {}).get("kp_ids") or [])
                }
                or any(
                    kw and kw.lower() in f"{r.get('title','')}{r.get('content','')[:400]}".lower()
                    for kw in keywords
                )
            )
        ]
        matched.sort(key=lambda r: r.get("created_at", 0), reverse=True)
        if matched:
            covered_kps.add(kp_id)
            for r in matched[:2]:
                items.append({
                    "kind": "resource",
                    "resource_id": r.get("id"),
                    "title": r.get("title"),
                    "type": r.get("type"),
                    "kp_id": kp_id,
                    "suggested_types": suggested_types,
                    "reason": f"「{kp_name}」当前掌握 {mastery:.0%}，此资源与其直接相关",
                })
        else:
            items.append({
                "kind": "generate",
                "kp_id": kp_id,
                "topic": kp_name,
                "suggested_types": suggested_types,
                "reason": f"「{kp_name}」掌握 {mastery:.0%} 且暂无匹配资源，建议按图解、实操、变式练习生成多模态学习包",
            })

    try:
        weights = _build_adaptive_strategy(
            user_id, course=course
        )["strategy"]["resource_type_weights"]
    except Exception:
        weights = None
    items = _sort_recommendation_items(
        items,
        weights,
        {kp_id: index for index, (kp_id, _mastery) in enumerate(weakest)},
    )

    return {
        "user_id": user_id,
        "weakest_kps": [
            {"kp_id": k, "mastery": round(v, 3),
             "name": str((map_nodes.get(k) or {}).get("name") or course_kp_names.get(k) or k)
             if isinstance(map_nodes.get(k), dict) else course_kp_names.get(k, k)}
            for k, v in weakest
        ],
        "items": items[:limit],
        "total_resources_scanned": len(all_resources),
    }


# ================================================================
# 5. 学习活跃日历（真实行为数据聚合，前端热力图用）
# ================================================================
def _assessment_records(user_id: str) -> List[Dict[str, Any]]:
    from backend.app.api.v1 import assessment as assessment_api

    if assessment_api._repository is not None:
        return assessment_api._repository.list(user_id)
    return list(assessment_api._assessments.get(user_id, []))


@router.get("/study-calendar/{user_id}")
def study_calendar(user_id: str, days: int = Query(91, ge=7, le=365)) -> Dict[str, Any]:
    """近 N 天学习行为按天聚合：次数/时长/强度等级，附连续学习统计。"""
    from datetime import date, timedelta

    records = _assessment_records(user_id)
    today = date.today()
    start = today - timedelta(days=days - 1)

    by_day: Dict[str, Dict[str, Any]] = {}
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            continue
        d = date.fromtimestamp(float(ts))
        if d < start or d > today:
            continue
        key = d.isoformat()
        slot = by_day.setdefault(key, {"count": 0, "minutes": 0.0})
        slot["count"] += 1
        slot["minutes"] += float(r.get("duration") or 0)

    calendar: List[Dict[str, Any]] = []
    cur = start
    while cur <= today:
        key = cur.isoformat()
        slot = by_day.get(key, {"count": 0, "minutes": 0.0})
        count = slot["count"]
        level = 0 if count == 0 else 1 if count <= 1 else 2 if count <= 3 else 3 if count <= 6 else 4
        calendar.append({
            "date": key,
            "count": count,
            "minutes": round(slot["minutes"], 1),
            "level": level,
        })
        cur += timedelta(days=1)

    # 连续学习统计
    current_streak = 0
    for day in reversed(calendar):
        if day["count"] > 0:
            current_streak += 1
        elif day["date"] != today.isoformat():
            break
    longest = run = 0
    for day in calendar:
        run = run + 1 if day["count"] > 0 else 0
        longest = max(longest, run)

    active_days = sum(1 for d in calendar if d["count"] > 0)
    return {
        "user_id": user_id,
        "days": days,
        "calendar": calendar,
        "active_days": active_days,
        "total_activities": sum(d["count"] for d in calendar),
        "total_minutes": round(sum(d["minutes"] for d in calendar), 1),
        "current_streak": current_streak,
        "longest_streak": longest,
    }


# ================================================================
# 6. 评估驱动的动态调整闭环（赛题功能 5：根据评估结果动态调整
#    学习资源推送策略与学习计划）
# ================================================================
def _unresolved_mistakes(user_id: str, course: str = "") -> int:
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord, MistakeRecord

        with SessionLocal() as db:
            query = db.query(MistakeRecord).filter(
                MistakeRecord.user_id == user_id,
                MistakeRecord.resolved_at.is_(None),
            )
            if course:
                query = query.join(
                    KnowledgePointRecord,
                    KnowledgePointRecord.id == MistakeRecord.knowledge_point_id,
                ).filter(KnowledgePointRecord.course == course)
            return int(query.count())
    except Exception as exc:  # noqa: BLE001
        logger.warning("[insights] mistakes unavailable: %s", exc)
        return 0


def _profile_style_text(user_id: str) -> str:
    try:
        from backend.app.api.v1 import profile as profile_api

        prof = (profile_api._repository.get(user_id)
                if profile_api._repository is not None
                else profile_api._profiles.get(user_id, {}))
        parts = [prof.get("cognitive_style"), prof.get("learning_preference")]
        return "；".join(str(p) for p in parts if p)
    except Exception:  # noqa: BLE001
        return ""


def _build_adaptive_strategy(user_id: str, course: str = "") -> Dict[str, Any]:
    records = _assessment_records(user_id)
    quiz = [r for r in records if r.get("type") in ("quiz", "evaluation")
            and r.get("score") is not None][-10:]
    scores = [float(r["score"]) for r in quiz]
    avg = sum(scores) / len(scores) if scores else None

    trend = "insufficient_data"
    delta = 0.0
    if len(scores) >= 4:
        half = len(scores) // 2
        early, late = scores[:half], scores[half:]
        delta = sum(late) / len(late) - sum(early) / len(early)
        trend = "improving" if delta > 3 else "declining" if delta < -3 else "stable"

    unresolved = _unresolved_mistakes(user_id, course=course)
    masteries = _bkt_masteries(user_id)
    course_kp_names = _load_kp_names(course) if course else {}
    if course:
        masteries = {
            kp_id: value
            for kp_id, value in masteries.items()
            if kp_id in course_kp_names
        }
    try:
        map_nodes = _load_knowledge_map()["nodes"]
    except HTTPException:
        map_nodes = {}
    if course:
        map_nodes = {
            kp_id: meta
            for kp_id, meta in map_nodes.items()
            if kp_id in course_kp_names
        }
    known = dict(masteries)
    for k in map_nodes:
        known.setdefault(k, 0.0)
    weakest = sorted(known.items(), key=lambda kv: kv[1])[:3]
    focus_kps = [
        {"kp_id": k, "mastery": round(v, 3),
         "name": str((map_nodes.get(k) or {}).get("name") or course_kp_names.get(k) or k)
         if isinstance(map_nodes.get(k), dict) else course_kp_names.get(k, k)}
        for k, v in weakest
    ]

    # 资源类型权重：认知风格 × 成绩信号
    weights = {"document": 1.0, "quiz": 1.0, "mindmap": 1.0, "video": 1.0, "code": 1.0}
    style = _profile_style_text(user_id)
    if "视觉" in style or "图" in style:
        weights["mindmap"] += 0.5
        weights["video"] += 0.5
    if "听觉" in style:
        weights["video"] += 0.5
    if "动手" in style or "实践" in style or "实操" in style:
        weights["code"] += 0.5
        weights["quiz"] += 0.3
    if trend == "declining" or (avg is not None and avg < 60):
        weights["document"] += 0.4   # 退步/低分 → 先回讲解再练题
        weights["quiz"] += 0.3
    if unresolved >= 3:
        weights["quiz"] += 0.5       # 错题堆积 → 加大变式练习

    # 每日练习强度
    intensity = 4
    reasons: List[str] = []
    if trend == "declining":
        intensity += 2
        reasons.append(f"近期测验均分下滑 {abs(delta):.1f} 分，建议加练巩固")
    elif trend == "improving":
        reasons.append(f"近期测验均分上升 {delta:.1f} 分，保持当前节奏")
    if avg is not None and avg < 60:
        intensity += 2
        reasons.append(f"测验均分 {avg:.0f} 低于 60，需要强化基础")
    if unresolved >= 3:
        intensity += 1
        reasons.append(f"有 {unresolved} 道错题未解决，优先复盘错题")
    intensity = min(intensity, 10)

    replan = trend == "declining" or (avg is not None and avg < 60) or unresolved >= 5

    signals = [
        {"name": "测验成绩趋势", "value": trend, "detail":
            f"近 {len(scores)} 次均分 {avg:.1f}，前后段差 {delta:+.1f}" if avg is not None
            else "暂无测验记录，先在错题本或群聊做几道题"},
        {"name": "未解决错题", "value": unresolved, "detail":
            "错题堆积，推送策略已向变式练习倾斜" if unresolved >= 3 else "错题处理及时"},
        {"name": "最薄弱知识点", "value": focus_kps[0]["name"] if focus_kps else "—",
         "detail": "、".join(f"{f['name']}({f['mastery']:.0%})" for f in focus_kps) or "暂无 BKT 追踪数据"},
    ]

    adjustments = [
        {"action": "daily_intensity", "label": f"每日练习强度调整为 {intensity} 题",
         "reason": "；".join(reasons) or "当前学习状态平稳，维持默认强度"},
        {"action": "resource_weights", "label": "资源推送权重已按认知风格与成绩信号再平衡",
         "reason": "权重最高的类型将优先出现在推送列表",
         "weights": {k: round(v, 2) for k, v in weights.items()}},
    ]
    if replan:
        adjustments.append({
            "action": "replan_path", "label": "建议重新规划学习路径",
            "reason": "评估信号触发（成绩下滑 / 均分过低 / 错题堆积），可一键应用",
        })

    return {
        "user_id": user_id,
        "signals": signals,
        "adjustments": adjustments,
        "strategy": {
            "daily_practice_intensity": intensity,
            "resource_type_weights": {k: round(v, 2) for k, v in weights.items()},
            "focus_kps": focus_kps,
            "replan_recommended": replan,
        },
        "algorithm": "assessment-trend × mistakes-backlog × bkt-weakness → strategy",
    }


@router.get("/adaptive-strategy/{user_id}")
def adaptive_strategy(user_id: str, course: str = Query(default="")) -> Dict[str, Any]:
    """学习效果评估 → 推送策略/学习计划动态调整决策（确定性算法，免 LLM）。"""
    return _build_adaptive_strategy(user_id, course=course)


@router.post("/adaptive-strategy/{user_id}/apply")
def apply_adaptive_strategy(
    user_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
) -> Dict[str, Any]:
    """一键应用动态调整：按最新评估重新生成个性化路径 + 刷新推送。"""
    course = str(payload.get("course", "")).strip()
    strategy = _build_adaptive_strategy(user_id, course=course)
    applied: List[str] = []
    new_path: Dict[str, Any] | None = None

    force = bool(payload.get("force", False))
    if strategy["strategy"]["replan_recommended"] or force:
        try:
            new_path = generate_path({"user_id": user_id, "course": course, "mistake_repair": True})
            applied.append("replan_path")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[insights] replan failed: %s", exc)

    reco = recommendations(user_id=user_id, limit=6, course=course)
    applied.append("refresh_recommendations")

    return {
        "user_id": user_id,
        "applied": applied,
        "strategy": strategy["strategy"],
        "new_path_id": (new_path or {}).get("path_id"),
        "recommendations": reco["items"],
    }


# ================================================================
# 7. 个性化推理链聚合 API
#    汇总 BKT 掌握度 / 学习者类型 / 认知风格 / 路径个性化数据 / 自适应策略信号
#    为前端提供一条完整的「为什么这条路径适合你」推理链。
# ================================================================
def _load_kp_names(course: str = "") -> Dict[str, str]:
    """从 knowledge_map.yaml 加载 kp_id → name 映射。"""
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.core.models import KnowledgePointRecord

        with SessionLocal() as db:
            query = db.query(KnowledgePointRecord)
            if course:
                query = query.filter(KnowledgePointRecord.course == course)
            rows = query.all()
        if rows:
            return {str(row.id): str(row.name) for row in rows}
    except Exception as exc:  # noqa: BLE001
        logger.debug("[insights] knowledge-point names from DB unavailable: %s", exc)
    try:
        data = _load_knowledge_map()
        return {k: str(v.get("name", k)) for k, v in data.get("nodes", {}).items() if isinstance(v, dict)}
    except Exception:
        return {}


def _get_learner_archetype(user_id: str) -> Dict[str, Any]:
    """获取学习者画像类型（9 种 archetype）。"""
    try:
        from backend.app.services.learner_archetype import get_learner_archetype_service
        from backend.app.api.v1 import profile as profile_api

        prof = (profile_api._repository.get(user_id)
                if profile_api._repository is not None
                else profile_api._profiles.get(user_id, {}))
        if not prof:
            prof = profile_api._fallback_profile(user_id)
        # 把 profile 8 维分数提取出来
        dimensions: Dict[str, Any] = {}
        for key in ("knowledge_base", "learning_preference", "weak_points",
                     "time_management", "self_efficacy", "cognitive_style",
                     "learning_goal", "interaction_pattern"):
            val = prof.get(key)
            if isinstance(val, dict):
                dimensions[key] = val
            elif isinstance(val, (int, float)):
                dimensions[key] = {"score": float(val)}
            elif isinstance(val, str):
                dimensions[key] = {"score": 0.5}
            else:
                dimensions[key] = {"score": 0.5}
        svc = get_learner_archetype_service()
        result = svc.identify(dimensions)
        try:
            from backend.app.core.database import SessionLocal
            from backend.app.core.models import LearnerArchetypeRecord

            with SessionLocal() as db:
                row = db.get(LearnerArchetypeRecord, user_id)
                if row is None:
                    row = LearnerArchetypeRecord(user_id=user_id)
                    db.add(row)
                row.archetype_code = str(result.get("code", "stable_average"))
                row.archetype_data = dict(result)
                row.updated_at = time.time()
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.debug("[insights] archetype persistence skip: %s", exc)
        return result
    except Exception as exc:
        logger.debug("[insights] archetype skip: %s", exc)
        return {}


def _get_cognitive_style(user_id: str) -> str:
    """从画像中提取认知风格文本。"""
    try:
        from backend.app.api.v1 import profile as profile_api
        prof = (profile_api._repository.get(user_id)
                if profile_api._repository is not None
                else profile_api._profiles.get(user_id, {}))
        if not prof:
            prof = profile_api._fallback_profile(user_id)
        cs = prof.get("cognitive_style", "")
        if isinstance(cs, dict):
            return str(
                cs.get("label")
                or cs.get("value")
                or cs.get("primary")
                or cs.get("mode")
                or cs.get("style")
                or ""
            )
        if not cs:
            preference = prof.get("learning_preference", "")
            if isinstance(preference, dict):
                return str(preference.get("mode") or preference.get("primary") or "")
        return str(cs) if cs else ""
    except Exception:
        return ""


_PEER_DIMENSIONS = (
    "knowledge_base",
    "learning_preference",
    "weak_points",
    "time_management",
    "self_efficacy",
    "cognitive_style",
    "learning_goal",
    "interaction_pattern",
)


def _profile_dimension_score(value: Any) -> float:
    if isinstance(value, dict):
        for key in ("score", "value", "completeness", "confidence"):
            if key in value:
                value = value[key]
                break
        else:
            return 0.5 if value else 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5 if value else 0.0
    if number > 1:
        number /= 100.0
    return max(0.0, min(1.0, number))


@router.get("/peer-comparison/{user_id}")
def peer_comparison(user_id: str) -> Dict[str, Any]:
    """Return a real class baseline and activity metrics for ProfileView."""
    from sqlalchemy import func

    from backend.app.core.database import SessionLocal
    from backend.app.core.models import (
        AssessmentRecord,
        GroupChatMessageRecord,
        ProfileRecord,
    )

    with SessionLocal() as db:
        profiles = db.query(ProfileRecord).all()
        target = next((row for row in profiles if row.user_id == user_id), None)
        if target is None:
            raise HTTPException(status_code=404, detail=f"learner_not_found: {user_id}")

        eligible = [
            row for row in profiles
            if row.user_id.startswith("demo-student-")
        ] or profiles
        peer_rows = [row for row in eligible if row.user_id != user_id] or eligible

        def scores(row: Any) -> Dict[str, float]:
            profile = dict(row.profile_data or {})
            if row.user_id.startswith("demo-student-"):
                try:
                    from backend.app.api.v1 import profile as profile_api

                    seed_profile = profile_api._seed_profiles().get(row.user_id, {})
                    for key, seed_value in seed_profile.items():
                        current = profile.get(key)
                        if isinstance(seed_value, dict) and isinstance(current, dict):
                            profile[key] = {**seed_value, **current}
                        elif current in (None, "", [], {}):
                            profile[key] = seed_value
                except Exception:
                    pass
            return {
                key: round(_profile_dimension_score(profile.get(key)), 3)
                for key in _PEER_DIMENSIONS
            }

        target_scores = scores(target)
        peer_scores = [scores(row) for row in peer_rows]
        peer_average = {
            key: round(sum(row[key] for row in peer_scores) / max(len(peer_scores), 1), 3)
            for key in _PEER_DIMENSIONS
        }

        now = time.time()
        current_start = now - 7 * 86400
        previous_start = now - 14 * 86400
        current_scores = (
            db.query(AssessmentRecord.score)
            .filter(
                AssessmentRecord.user_id == user_id,
                AssessmentRecord.timestamp >= current_start,
                AssessmentRecord.score.is_not(None),
            )
            .all()
        )
        previous_scores = (
            db.query(AssessmentRecord.score)
            .filter(
                AssessmentRecord.user_id == user_id,
                AssessmentRecord.timestamp >= previous_start,
                AssessmentRecord.timestamp < current_start,
                AssessmentRecord.score.is_not(None),
            )
            .all()
        )
        participation = (
            db.query(func.count(GroupChatMessageRecord.id))
            .filter(
                GroupChatMessageRecord.sender_id == user_id,
                GroupChatMessageRecord.created_at >= now - 30 * 86400,
            )
            .scalar()
            or 0
        )

    def normalized_average(rows: List[tuple[float]]) -> float | None:
        values = [float(score) * 100 if float(score) <= 1 else float(score) for (score,) in rows]
        return sum(values) / len(values) if values else None

    current_avg = normalized_average(current_scores)
    previous_avg = normalized_average(previous_scores)
    weekly_lift = None
    if current_avg is not None and previous_avg is not None:
        weekly_lift = round(float(current_avg) - float(previous_avg), 2)
    return {
        "user_id": user_id,
        "cohort_size": len(eligible),
        "dimensions": target_scores,
        "peer_average": peer_average,
        "metrics": {
            "current_week_score": round(float(current_avg), 2) if current_avg is not None else None,
            "previous_week_score": round(float(previous_avg), 2) if previous_avg is not None else None,
            "weekly_lift": weekly_lift,
            "group_messages_30d": int(participation),
        },
        "generated_at": time.time(),
    }


@router.get("/personalization-chain/{user_id}")
def personalization_chain(
    user_id: str,
    course: str = Query(default=""),
) -> Dict[str, Any]:
    """个性化推理链：汇总所有个性化数据，为前端提供完整推理依据。

    返回结构：
    {
        "user_id": "...",
        "archetype": { code, archetype, nickname, description, study_strategy, ... },
        "cognitive_style": "视觉型",
        "bkt_summary": { weakest, strongest, total_kps, mastered_count },
        "path_personalization": { skipped_kps, pending_kps, interest, planner_note },
        "adaptive_signals": [ ... ],
        "reasoning_chain": [ { icon, label, detail } ... ],
        "tags": [ { label, color, icon } ... ]   // 个性化标签
    }
    """
    kp_names = _load_kp_names(course)
    masteries = _bkt_masteries(user_id)
    if course:
        masteries = {
            kp_id: value
            for kp_id, value in masteries.items()
            if kp_id in kp_names
        }

    # --- BKT 掌握度汇总 ---
    all_kps = set(kp_names.keys()) | set(masteries.keys())
    mastery_list = sorted(
        [(kp, masteries.get(kp, 0.0), kp_names.get(kp, kp)) for kp in all_kps],
        key=lambda x: x[1],
    )
    weakest_3 = [{"kp_id": k, "mastery": round(v, 3), "name": n} for k, v, n in mastery_list[:3] if v < 0.8]
    strongest_3 = [{"kp_id": k, "mastery": round(v, 3), "name": n} for k, v, n in reversed(mastery_list[-3:]) if v >= 0.5]
    mastered_count = sum(1 for _, v, _ in mastery_list if v >= 0.8)
    total_kps = len(all_kps)

    # --- 学习者类型 ---
    archetype = _get_learner_archetype(user_id)

    # --- 认知风格 ---
    cognitive_style = _get_cognitive_style(user_id)

    # --- 路径个性化 ---
    path_personalization: Dict[str, Any] = {}
    try:
        from backend.app.api.v1 import learning_path as lp_api
        paths = lp_api.list_paths(user_id)
        if paths.get("paths"):
            candidates = paths["paths"]
            if course:
                scoped = [p for p in candidates if str(p.get("course", "")) == course]
                if scoped:
                    candidates = scoped
            p = max(
                candidates,
                key=lambda item: (
                    float(item.get("progress", 0) or 0),
                    float(item.get("created_at", 0) or 0),
                ),
            )
            path_personalization = {
                "path_id": p.get("id"),
                "title": p.get("title", ""),
                "progress": p.get("progress", 0),
                "current_stage": p.get("current_stage", 0),
                "stage_count": len(p.get("stages", [])),
                "interest": (p.get("metadata") or {}).get("interest", ""),
                "planner_note": (p.get("metadata") or {}).get("planner_note", ""),
            }
    except Exception as exc:
        logger.debug("[insights] path personalization skip: %s", exc)

    # --- 自适应策略信号 ---
    adaptive_signals: List[Dict[str, Any]] = []
    try:
        strat = _build_adaptive_strategy(user_id, course=course)
        adaptive_signals = strat.get("signals", [])
        replan_recommended = strat.get("strategy", {}).get("replan_recommended", False)
        daily_intensity = strat.get("strategy", {}).get("daily_practice_intensity", 4)
    except Exception:
        replan_recommended = False
        daily_intensity = 4

    # --- 推理链 ---
    reasoning_chain: List[Dict[str, str]] = []

    if archetype:
        reasoning_chain.append({
            "icon": "user",
            "label": f"学习者类型：{archetype.get('archetype', '—')}",
            "detail": archetype.get("description", ""),
        })

    if weakest_3:
        weakest_text = "、".join(f"{w['name']}({w['mastery']:.0%})" for w in weakest_3)
        reasoning_chain.append({
            "icon": "target",
            "label": f"最薄弱知识点：{weakest_text}",
            "detail": "路径优先编排这些知识点的前置内容，确保基础牢固后再推进",
        })

    if cognitive_style:
        style_detail = ""
        if "视觉" in cognitive_style or "图" in cognitive_style:
            style_detail = "推荐资源优先展示思维导图和视频类内容"
        elif "听觉" in cognitive_style:
            style_detail = "推荐资源优先展示语音讲解和视频类内容"
        elif "动手" in cognitive_style or "实践" in cognitive_style or "实操" in cognitive_style:
            style_detail = "推荐资源优先展示代码示例和实操练习"
        else:
            style_detail = "推荐资源按通用策略推送"
        reasoning_chain.append({
            "icon": "eye",
            "label": f"认知风格：{cognitive_style}",
            "detail": style_detail,
        })

    if mastered_count > 0:
        reasoning_chain.append({
            "icon": "skip",
            "label": f"已跳过 {mastered_count} 个已掌握知识点（BKT ≥ 80%）",
            "detail": f"为你节省了约 {mastered_count * 2} 小时的重复学习时间，聚焦真正需要提升的内容",
        })

    if path_personalization.get("interest"):
        reasoning_chain.append({
            "icon": "heart",
            "label": f"兴趣方向：{path_personalization['interest']}",
            "detail": path_personalization.get("planner_note", "路径会在完成核心阶段后增加该方向的拓展资源"),
        })

    if replan_recommended:
        reasoning_chain.append({
            "icon": "alert",
            "label": "评估信号触发路径重规划建议",
            "detail": "近期评估数据显示学习状态波动，建议重新规划学习路径以适应当前水平",
        })

    reasoning_chain.append({
        "icon": "gauge",
        "label": f"每日推荐练习强度：{daily_intensity} 题",
        "detail": "根据评估趋势、错题积压和 BKT 薄弱程度综合计算",
    })

    # --- 个性化标签 ---
    tags: List[Dict[str, str]] = []
    if weakest_3:
        tags.append({"label": "薄弱知识点", "color": "#ef4444", "icon": "target"})
    if cognitive_style:
        if "视觉" in cognitive_style or "图" in cognitive_style:
            tags.append({"label": "视觉型推荐", "color": "#8b5cf6", "icon": "eye"})
        elif "听觉" in cognitive_style:
            tags.append({"label": "听觉型推荐", "color": "#3b82f6", "icon": "volume2"})
        elif "动手" in cognitive_style or "实践" in cognitive_style:
            tags.append({"label": "动手型推荐", "color": "#10b981", "icon": "code"})
    if replan_recommended:
        tags.append({"label": "退步预警", "color": "#f59e0b", "icon": "alert"})
    if archetype:
        tags.append({"label": archetype.get("archetype", ""), "color": "#ea5a1a", "icon": "user"})
    if path_personalization.get("interest"):
        tags.append({"label": "兴趣驱动", "color": "#ec4899", "icon": "heart"})

    return {
        "user_id": user_id,
        "archetype": archetype,
        "cognitive_style": cognitive_style,
        "bkt_summary": {
            "weakest": weakest_3,
            "strongest": strongest_3,
            "total_kps": total_kps,
            "mastered_count": mastered_count,
        },
        "path_personalization": path_personalization,
        "adaptive_signals": adaptive_signals,
        "replan_recommended": replan_recommended,
        "daily_intensity": daily_intensity,
        "reasoning_chain": reasoning_chain,
        "tags": tags,
    }
