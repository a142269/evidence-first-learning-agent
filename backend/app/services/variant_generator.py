# ruff: noqa: RUF001
"""Mistake-to-variant remediation generator (A-owned).

This service turns one wrong answer into a visible learning loop:
mistake attribution -> Bloom-leveled variants -> mastery-aware recommendation.
It stays deterministic in offline demo mode and does not mutate the static
question bank.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import re
from typing import Any

from backend.app.services.mistake_review import classify_with_llm, generate_variants
from backend.app.services.question_bank import QuestionBank, get_question_bank
from backend.app.services.realdina_service import RealDINAService, get_realdina_service

_BLOOM_ORDER = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
_BLOOM_LABELS = {
    "remember": "记忆",
    "understand": "理解",
    "apply": "应用",
    "analyze": "分析",
    "evaluate": "评价",
    "create": "创造",
}
_ATTRIBUTION_CATEGORIES = [
    "concept_confusion",
    "careless",
    "ambiguous_question",
    "input_error",
    "boundary_unclear",
    "prerequisite_missing",
    "procedural_slip",
    "unknown",
]
_CATEGORY_LABELS = {
    "concept_confusion": "概念混淆",
    "careless": "粗心失误",
    "ambiguous_question": "题目歧义",
    "input_error": "输入错误",
    "boundary_unclear": "边界不清",
    "prerequisite_missing": "先修知识缺失",
    "procedural_slip": "程序性失误",
    "unknown": "未知",
}
_LEGACY_ERROR_TO_CATEGORY = {
    "知识缺漏": "prerequisite_missing",
    "计算失误": "procedural_slip",
    "概念混淆": "concept_confusion",
    "阅读理解": "ambiguous_question",
    "审题不清": "ambiguous_question",
    "方法选择错": "procedural_slip",
    "计算粗心": "careless",
    "概念边界混淆": "boundary_unclear",
}
_CATEGORY_DETAILS = {
    "concept_confusion": "学生答案混淆了相近概念，需要先做概念对比。",
    "careless": "学生答案接近正确结果，优先检查格式、符号或数值细节。",
    "ambiguous_question": "学生可能没有抓住题目条件或题干存在歧义。",
    "input_error": "学生答案为空或格式异常，先确认输入完整性。",
    "boundary_unclear": "学生没有把握定义边界或适用条件。",
    "prerequisite_missing": "学生可能缺少先修定义或基础概念。",
    "procedural_slip": "学生在多步解题流程中出现局部步骤错误。",
    "unknown": "暂未识别明确错因，建议先进行同知识点巩固。",
}


@dataclass(frozen=True)
class VariantGenerationRequest:
    user_id: str
    mistake_id: str
    question: str
    student_answer: str
    correct_answer: str
    kp_id: str = ""
    kp_name: str = ""
    count: int = 3


class VariantGenerator:
    """Generate and rank remediation variants for one mistake."""

    def __init__(
        self,
        question_bank: QuestionBank | None = None,
        realdina_service: RealDINAService | None = None,
        attribution_engine: Any | None = None,
    ) -> None:
        self.question_bank = question_bank or get_question_bank()
        self.realdina = realdina_service or get_realdina_service()
        self.attribution_engine = attribution_engine

    def generate(
        self,
        request: VariantGenerationRequest,
        llm_call: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Return a full remediation package for a single wrong answer."""
        count = max(1, min(5, request.count))
        kp_id = request.kp_id.strip()
        kp_name = request.kp_name.strip() or self._kp_name(kp_id)
        attribution = self._attribute(request, kp_id=kp_id, llm_call=llm_call)
        mastery = self._mastery(request.user_id, kp_id)
        target_bloom = self._target_bloom(
            mastery,
            attribution["error_type"],
            attribution.get("category", ""),
        )
        raw_variants = generate_variants(
            question=request.question,
            correct_answer=request.correct_answer,
            kp_id=kp_id,
            kp_name=kp_name,
            count=count + 2,
            llm_call=llm_call,
        )
        variants = self._normalize_variants(
            raw_variants=raw_variants,
            request=request,
            kp_name=kp_name,
            target_bloom=target_bloom,
            attribution=attribution,
            count=count,
        )
        recommended = self._recommend_variant(variants, target_bloom)
        return {
            "user_id": request.user_id,
            "mistake_id": request.mistake_id,
            "kp_id": kp_id,
            "kp_name": kp_name,
            "category": attribution["category"],
            "category_label": attribution["category_label"],
            "attribution": attribution,
            "mastery": {
                "current": round(mastery, 4),
                "band": self._mastery_band(mastery),
                "source": "RealDINAService",
            },
            "target_bloom": {
                "level": target_bloom,
                "label": _BLOOM_LABELS[target_bloom],
            },
            "variants": variants,
            "recommended_variant_id": recommended["variant_id"] if recommended else "",
            "recommendation_reason": self._recommendation_reason(
                mastery=mastery,
                target_bloom=target_bloom,
                attribution=attribution,
                recommended=recommended,
            ),
            "next_actions": self._next_actions(kp_name, mastery),
        }

    def _attribute(
        self,
        request: VariantGenerationRequest,
        kp_id: str,
        llm_call: Callable[..., Any] | None,
    ) -> dict[str, Any]:
        """Prefer B's AttributionEngine, falling back to legacy mistake_review."""
        try:
            engine = self.attribution_engine
            if engine is None:
                from backend.app.services.attribution_engine import get_attribution_engine

                engine = get_attribution_engine()
            result = engine.attribute(
                question=request.question,
                user_answer=request.student_answer,
                correct_answer=request.correct_answer,
                user_id=request.user_id,
                kp_ids=[kp_id] if kp_id else [],
            )
            category = _normalize_category(getattr(result, "category", "unknown"))
            confidence = float(getattr(result, "confidence", 0.0))
            source = str(getattr(result, "source", "rule") or "rule")
            evidence = getattr(result, "evidence", {}) or {}
            return {
                "error_type": _CATEGORY_LABELS[category],
                "detail": _CATEGORY_DETAILS[category],
                "source": source,
                "confidence": max(0.0, min(1.0, confidence)),
                "category": category,
                "category_label": _CATEGORY_LABELS[category],
                "evidence": evidence,
                "all_categories": list(_ATTRIBUTION_CATEGORIES),
            }
        except Exception as exc:
            return self._legacy_attribute(request, llm_call=llm_call, fallback_reason=str(exc))

    def _legacy_attribute(
        self,
        request: VariantGenerationRequest,
        llm_call: Callable[..., Any] | None,
        fallback_reason: str = "",
    ) -> dict[str, Any]:
        try:
            legacy = classify_with_llm(
                student_answer=request.student_answer,
                correct_answer=request.correct_answer,
                question=request.question,
                llm_call=llm_call,
            )
        except Exception as exc:
            legacy = {
                "error_type": "未知",
                "detail": f"归因引擎与旧分类器均不可用：{exc}",
                "source": "fallback",
                "confidence": 0.0,
            }
            fallback_reason = fallback_reason or str(exc)
        category = _legacy_category(str(legacy.get("error_type", "")))
        evidence: dict[str, Any] = {"fallback": "mistake_review"}
        if fallback_reason:
            evidence["reason"] = fallback_reason
        return {
            "error_type": str(legacy.get("error_type", _CATEGORY_LABELS[category])),
            "detail": str(legacy.get("detail", _CATEGORY_DETAILS[category])),
            "source": str(legacy.get("source", "rule")),
            "confidence": float(legacy.get("confidence", 0.0)),
            "category": category,
            "category_label": _CATEGORY_LABELS[category],
            "evidence": evidence,
            "all_categories": list(_ATTRIBUTION_CATEGORIES),
        }

    def _normalize_variants(
        self,
        raw_variants: list[dict[str, Any]],
        request: VariantGenerationRequest,
        kp_name: str,
        target_bloom: str,
        attribution: dict[str, Any],
        count: int,
    ) -> list[dict[str, Any]]:
        original_norm = _normalize_text(request.question)
        seen: set[str] = {original_norm}
        output: list[dict[str, Any]] = []
        for raw in raw_variants:
            stem = str(raw.get("question", "")).strip()
            norm = _normalize_text(stem)
            if not stem or norm in seen:
                continue
            seen.add(norm)
            bloom = _normalize_bloom(str(raw.get("bloom_level", raw.get("bloom", ""))))
            difficulty = int(raw.get("difficulty", _difficulty_for_bloom(bloom)))
            variant_id = self._variant_id(request.mistake_id, bloom, stem)
            output.append(
                {
                    "variant_id": variant_id,
                    "source": f"variant_of_{request.mistake_id}",
                    "source_mistake_id": request.mistake_id,
                    "kp_id": request.kp_id,
                    "kp_name": kp_name,
                    "bloom_level": bloom,
                    "bloom_label": _BLOOM_LABELS[bloom],
                    "difficulty": max(1, min(5, difficulty)),
                    "question": stem,
                    "answer": str(raw.get("answer", "")).strip(),
                    "explanation": str(raw.get("explanation", "")).strip(),
                    "error_type": attribution["error_type"],
                    "category": attribution["category"],
                    "category_label": attribution["category_label"],
                    "recommendation_score": self._score_variant(bloom, difficulty, target_bloom),
                }
            )
            if len(output) >= count:
                break

        while len(output) < count:
            fallback = self._fallback_variant(
                request,
                kp_name,
                target_bloom,
                attribution,
                len(output),
            )
            norm = _normalize_text(fallback["question"])
            if norm not in seen:
                seen.add(norm)
                fallback["recommendation_score"] = self._score_variant(
                    fallback["bloom_level"],
                    int(fallback["difficulty"]),
                    target_bloom,
                )
                output.append(fallback)
            else:
                break
        return sorted(output, key=lambda item: item["recommendation_score"])

    def _fallback_variant(
        self,
        request: VariantGenerationRequest,
        kp_name: str,
        target_bloom: str,
        attribution: dict[str, Any],
        index: int,
    ) -> dict[str, Any]:
        level = _BLOOM_ORDER[min(_BLOOM_ORDER.index(target_bloom) + index, len(_BLOOM_ORDER) - 1)]
        if level == "remember":
            question = f"请写出「{kp_name}」的核心定义，并列出 2 个关键词。"
        elif level == "understand":
            question = f"请用自己的话解释「{kp_name}」与原错题相关概念的区别。"
        elif level == "apply":
            question = f"换一个学习场景，说明如何应用「{kp_name}」解决同类问题。"
        else:
            question = "分析原错题中容易混淆的两个概念，并给出判断边界。"
        return {
            "variant_id": self._variant_id(request.mistake_id, level, question),
            "source": f"variant_of_{request.mistake_id}",
            "source_mistake_id": request.mistake_id,
            "kp_id": request.kp_id,
            "kp_name": kp_name,
            "bloom_level": level,
            "bloom_label": _BLOOM_LABELS[level],
            "difficulty": _difficulty_for_bloom(level),
            "question": question,
            "answer": f"参考原理：{request.correct_answer[:200]}",
            "explanation": "该题用于在相同知识点下进行低风险迁移练习。",
            "error_type": attribution["error_type"],
            "category": attribution["category"],
            "category_label": attribution["category_label"],
        }

    def _recommend_variant(
        self,
        variants: list[dict[str, Any]],
        target_bloom: str,
    ) -> dict[str, Any] | None:
        if not variants:
            return None
        return min(
            variants,
            key=lambda item: (
                item["recommendation_score"],
                abs(_BLOOM_ORDER.index(item["bloom_level"]) - _BLOOM_ORDER.index(target_bloom)),
                item["difficulty"],
            ),
        )

    def _score_variant(self, bloom: str, difficulty: int, target_bloom: str) -> float:
        bloom_gap = abs(_BLOOM_ORDER.index(bloom) - _BLOOM_ORDER.index(target_bloom))
        target_difficulty = _difficulty_for_bloom(target_bloom)
        difficulty_gap = abs(difficulty - target_difficulty)
        return round(bloom_gap * 1.5 + difficulty_gap * 0.6, 3)

    def _target_bloom(self, mastery: float, error_type: str, category: str = "") -> str:
        if (
            category in {"input_error", "prerequisite_missing", "ambiguous_question"}
            or error_type in {"知识缺漏", "阅读理解", "审题不清"}
            or mastery < 0.4
        ):
            return "remember"
        if (
            category in {"concept_confusion", "boundary_unclear"}
            or error_type in {"概念混淆", "概念边界混淆"}
            or mastery < 0.6
        ):
            return "understand"
        if (
            category in {"careless", "procedural_slip"}
            or error_type in {"计算失误", "计算粗心", "方法选择错"}
            or mastery < 0.78
        ):
            return "apply"
        return "analyze"

    def _mastery(self, user_id: str, kp_id: str) -> float:
        if not kp_id:
            snapshot = self.realdina.snapshot_for(user_id)
            return sum(snapshot.values()) / len(snapshot) if snapshot else 0.5
        return self.realdina.mastery(user_id, kp_id)

    def _mastery_band(self, mastery: float) -> str:
        if mastery < 0.4:
            return "薄弱"
        if mastery < 0.6:
            return "待巩固"
        if mastery < 0.8:
            return "基本掌握"
        return "优势"

    def _kp_name(self, kp_id: str) -> str:
        if not kp_id:
            return "当前知识点"
        questions = self.question_bank.by_kp(kp_id)
        if questions:
            return str(questions[0].get("kp_name", kp_id))
        return kp_id

    def _recommendation_reason(
        self,
        mastery: float,
        target_bloom: str,
        attribution: dict[str, Any],
        recommended: dict[str, Any] | None,
    ) -> str:
        if recommended is None:
            return "暂无可推荐变式题。"
        return (
            f"当前掌握度 {mastery:.0%}，错因为「{attribution['error_type']}」，"
            f"优先选择 {_BLOOM_LABELS[target_bloom]} 层级的 "
            f"`{recommended['variant_id']}` 进行同 KP 巩固。"
        )

    def _next_actions(self, kp_name: str, mastery: float) -> list[str]:
        if mastery < 0.5:
            return [
                f"先复习「{kp_name}」定义与核心例子。",
                "完成推荐变式题后再做 2 道同 KP 基础题。",
                "若再次答错，进入错题本 SM-2 复习队列。",
            ]
        return [
            "先完成推荐变式题验证迁移能力。",
            f"再尝试 1 道「{kp_name}」应用题。",
            "将新错因写回画像，更新下一轮学习路径。",
        ]

    @staticmethod
    def _variant_id(mistake_id: str, bloom: str, question: str) -> str:
        digest = hashlib.sha1(f"{mistake_id}:{bloom}:{question}".encode()).hexdigest()
        return f"variant_{mistake_id}_{bloom}_{digest[:8]}"


def request_from_record(record: dict[str, Any], count: int = 3) -> VariantGenerationRequest:
    """Build a generation request from a mistake API/DB record."""
    return VariantGenerationRequest(
        user_id=str(record.get("user_id", "")),
        mistake_id=str(record.get("id", record.get("mistake_id", ""))),
        question=str(record.get("question", "")),
        student_answer=str(record.get("student_answer", "")),
        correct_answer=str(record.get("correct_answer", "")),
        kp_id=str(record.get("kp_id", record.get("knowledge_point_id", "")) or ""),
        kp_name=str(record.get("kp_name", "") or ""),
        count=count,
    )


def _normalize_bloom(level: str) -> str:
    value = level.strip().lower()
    if value in _BLOOM_ORDER:
        return value
    aliases = {"记忆": "remember", "理解": "understand", "应用": "apply", "分析": "analyze"}
    return aliases.get(value, "understand")


def _difficulty_for_bloom(level: str) -> int:
    return {
        "remember": 1,
        "understand": 2,
        "apply": 3,
        "analyze": 4,
        "evaluate": 4,
        "create": 5,
    }[_normalize_bloom(level)]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _normalize_category(category: str) -> str:
    value = category.strip()
    if value in _ATTRIBUTION_CATEGORIES:
        return value
    return "unknown"


def _legacy_category(error_type: str) -> str:
    return _LEGACY_ERROR_TO_CATEGORY.get(error_type, "unknown")
