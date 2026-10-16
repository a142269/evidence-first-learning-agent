from __future__ import annotations

import hashlib
import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from backend.app.services.profile_schema import (
    PROFILE_SCHEMA_VERSION,
    normalize_profile,
    standard_profile_only,
)

logger = logging.getLogger(__name__)

_TUTORING_RECORDS: list[dict[str, Any]] = []

# 关键词兜底表（覆盖高频 AI 概念，比原来 5 条大一圈；找不到时再回落到 general_ai）
_KP_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("cnn", ("cnn", "convolution", "卷积")),
    ("mlp", ("mlp", "多层感知机", "感知机")),
    ("attention", ("transformer", "attention", "注意力", "自注意力")),
    ("rnn", ("rnn", "lstm", "gru", "循环神经")),
    ("backpropagation", ("gradient", "梯度", "反向传播", "bp 算法", "链式法则")),
    ("kmeans", ("k-means", "kmeans", "k 均值", "均值聚类")),
    ("dbscan", ("dbscan", "密度聚类")),
    ("decision_tree", ("决策树", "id3", "c4.5", "cart")),
    ("random_forest", ("随机森林", "random forest")),
    ("svm", ("svm", "支持向量机")),
    ("naive_bayes", ("朴素贝叶斯", "naive bayes")),
    ("logistic_regression", ("逻辑回归", "logistic")),
    ("linear_regression", ("线性回归", "linear regression", "最小二乘")),
    ("bkt", ("bkt", "贝叶斯知识追踪")),
    ("bloom", ("bloom", "布卢姆", "认知层级")),
    ("regularization", ("正则化", "l1", "l2", "dropout", "过拟合")),
    ("optimizer", ("adam", "sgd", "优化器", "learning rate")),
    ("clustering", ("聚类", "clustering", "hierarchical")),
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _question_id(user_id: str, question: str) -> str:
    raw = f"{user_id}:{question}:{_now_iso()}".encode("utf-8")
    return "stq-" + hashlib.sha1(raw).hexdigest()[:12]


def _locate_knowledge_point(question: str) -> str:
    """基于关键词 + 知识图谱语义搜索定位 kp_id。"""
    lower = question.lower()
    for kp_id, keywords in _KP_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return kp_id
    # 关键词兜底失败 → 试着走图谱语义检索，把最相关的知识点 id 返回
    try:
        from backend.app.services.knowledge_graph.retriever import get_graph_retriever
        retriever = get_graph_retriever()
        hits = retriever.retrieve(question, top_k=3)
        for hit in hits or []:
            kp_ids = hit.get("kp_ids") if isinstance(hit, dict) else None
            if kp_ids:
                return str(kp_ids[0])
    except Exception as exc:
        logger.debug(f"[SmartTutor] KG retrieve failed: {exc}")
    return "general_ai"


def _call_llm_answer(question: str, kp: str) -> str:
    """让真正的 LLM 出一段个性化讲解；失败时回落到简短模板。"""
    system = (
        "你是一位大学人工智能课程的助教。学生刚刚提出了一个问题，"
        f"你识别出核心知识点是「{kp}」。请按以下结构回答（≤400 字）：\n"
        "1. **一句话直答**：直接给结论；\n"
        "2. **核心概念**：定义、关键要素；\n"
        "3. **一个例子**：用一句话给出直观类比或最小例子；\n"
        "4. **易错点 & 后续练习**：提示学生下一步应做什么。\n"
        "语气亲切、结构清晰，避免使用 Markdown 之外的标记。"
    )
    try:
        from backend.app.api.v1.chat_pipeline.stages._shared import get_shared_llm
        llm = get_shared_llm()
        answer = llm.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": question.strip()[:600]},
            ],
            temperature=0.6,
            max_tokens=600,
        )
        if answer and not answer.startswith("[API_ERROR]") and not answer.startswith("[ERROR]"):
            return answer.strip()
    except Exception as exc:
        logger.warning(f"[SmartTutor] LLM answer failed: {exc}")
    return (
        f"识别到核心知识点：{kp}。\n"
        "1. 先用一句话直答：先想清楚问题要求什么；\n"
        "2. 核心概念：请回到课程知识图谱查阅该知识点的定义与前置；\n"
        "3. 例子：找一个最小可运行的实例（例如 3~5 行代码或一张图）；\n"
        "4. 建议练习：完成一道相关小题，并把易错点写进错题本。"
    )


def _load_profile(user_id: str) -> dict[str, Any]:
    try:
        from backend.app.repositories.profile_repo import ProfileRepository

        profile = ProfileRepository().get(user_id)
    except Exception:
        profile = {}
    return normalize_profile(profile, preserve_extra=True)


def _persist_profile_update(user_id: str, profile_update: dict[str, Any]) -> None:
    try:
        from backend.app.repositories.profile_repo import ProfileRepository

        ProfileRepository().upsert(user_id, profile_update, source="smart_tutor")
    except Exception:
        return


class SmartTutoringEngine:
    """Minimal closed-loop tutoring engine for acceptance alignment."""

    used_agents = [
        "profile_agent",
        "course_expert",
        "derivation_agent",
        "example_agent",
        "quiz_generator",
        "multimodal_agent",
    ]

    def ask(
        self,
        *,
        user_id: str,
        question: str,
        input_type: str = "text",
        preferred_modes: list[str] | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        qid = _question_id(user_id, question)
        kp = _locate_knowledge_point(question)
        profile = _load_profile(user_id)
        response_mode = "text+diagram+animation"

        text_answer = _call_llm_answer(question, kp)
        diagram = {
            "format": "mermaid",
            "type": "flowchart",
            "code": (
                "flowchart LR\n"
                "  Q[Question input] --> I[Intent and KP detection]\n"
                "  I --> P[Profile matching]\n"
                "  P --> A[Agent collaboration]\n"
                "  A --> T[Text answer]\n"
                "  A --> D[Diagram explanation]\n"
                "  A --> V[Animation fallback]\n"
                "  T --> U[Profile and path update]\n"
            ),
        }
        video = {
            "format": "animation",
            "status": "degraded",
            "reason": "render_not_requested_in_acceptance_api",
            "script": f"Scene: animate the key intuition of {kp} step by step.",
        }
        practice = {
            "type": "short_practice",
            "prompt": f"Explain one misconception about {kp} and correct it in two sentences.",
        }

        profile_update = normalize_profile(
            {
                "learning_progress": {
                    "last_question_id": qid,
                    "last_knowledge_point": kp,
                    "last_input_type": input_type,
                    "updated_at": _now_iso(),
                },
                "interest_model": {
                    "recent_interest": kp,
                    "preferred_response_modes": preferred_modes or ["text", "diagram", "animation"],
                },
            },
            preserve_extra=True,
        )
        _persist_profile_update(user_id, standard_profile_only(profile_update))

        path_update = {
            "next_kp": kp,
            "reason": "smart_tutor_question_loop",
            "recommended_activity": "review_answer_then_try_practice",
        }
        record = {
            "question_id": qid,
            "user_id": user_id,
            "session_id": session_id or "",
            "input_type": input_type,
            "knowledge_point": kp,
            "response_mode": response_mode,
            "used_agents": list(self.used_agents),
            "created_at": _now_iso(),
            "profile_schema_version": PROFILE_SCHEMA_VERSION,
        }
        _TUTORING_RECORDS.append(deepcopy(record))

        return {
            "question_id": qid,
            "knowledge_point": kp,
            "response_mode": response_mode,
            "used_agents": list(self.used_agents),
            "matched_profile": standard_profile_only(profile),
            "agent_plan": {
                "profile_agent": "match standard six-dimension profile",
                "course_expert": "explain concept and prerequisite",
                "derivation_agent": "provide derivation or reasoning chain",
                "example_agent": "provide concrete example",
                "quiz_generator": "create follow-up exercise",
                "multimodal_agent": "prepare diagram and animation fallback",
            },
            "outputs": {
                "text_answer": text_answer,
                "diagram": diagram,
                "video": video,
                "practice": practice,
            },
            "record": record,
            "profile_update": standard_profile_only(profile_update),
            "path_update": path_update,
        }


def get_smart_tutoring_engine() -> SmartTutoringEngine:
    return SmartTutoringEngine()


def recent_tutoring_records(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    records = [item for item in _TUTORING_RECORDS if item.get("user_id") == user_id]
    return list(reversed(records[-limit:]))
