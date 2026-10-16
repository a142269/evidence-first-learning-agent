"""
Mistake Review Service — B owns

Unified mistake classification and variant generation.
Rule-based classifier (8 categories) with optional LLM enhancement.
Structured variant generation with answer/explanation/bloom_level.

Design:
  - classify_error() — pure rule engine, returns {error_type, detail, source}
  - classify_with_llm() — rule first, LLM override if available
  - generate_variants() — 3 Bloom-leveled variants with answer + explanation
  - build_heatmap_matrix() — cross-tabulation of KP × error_category
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ERROR_CATEGORIES = [
    "知识缺漏", "计算失误", "概念混淆", "阅读理解",
    "审题不清", "方法选择错", "计算粗心", "概念边界混淆",
]

BLOOM_VARIANT_TEMPLATES = {
    "remember": {
        "intro": "请回顾以下概念：",
        "answer_hint": "标准定义应包含核心术语和关键特征。",
    },
    "understand": {
        "intro": "请用自己的话解释以下概念，并举例说明：",
        "answer_hint": "好的解释应该能让他人理解，并包含一个具体例子。",
    },
    "apply": {
        "intro": "请运用以下知识解决这个新问题：",
        "answer_hint": "解法应展示知识迁移能力，参考答案给出完整步骤。",
    },
    "analyze": {
        "intro": "请对比以下两种解法，分析各自的优劣：",
        "answer_hint": "分析应从正确性、效率、可读性等维度展开。",
    },
}


def classify_error(
    student_answer: str,
    correct_answer: str,
) -> Dict[str, Any]:
    """Rule-based mistake classification into 8 categories.

    Args:
        student_answer: what the student wrote
        correct_answer: what is expected

    Returns:
        {"error_type": str, "detail": str, "source": "rule", "confidence": float}
    """
    s, c = str(student_answer).strip(), str(correct_answer).strip()

    # 1. Empty answer → knowledge gap
    if not s:
        return _result("知识缺漏", "未作答，可能完全不知道该知识点", confidence=0.95)

    # 2. Exact match but marked wrong → likely format issue (carelessness)
    if s == c:
        return _result("计算粗心", "答案与正确答案一致但被判错，可能为格式或单位问题", confidence=0.85)

    # 3. Numeric comparison
    try:
        sv = float(s.replace(",", "").replace(" ", ""))
        cv = float(c.replace(",", "").replace(" ", ""))
        rel_err = abs(sv - cv) / max(abs(cv), 1e-6)

        if rel_err < 0.05:
            return _result("计算粗心", f"数值极其接近（{s} vs {c}），误差仅 {rel_err:.1%}，可能为舍入误差", confidence=0.90)
        if rel_err < 0.30 and sv * cv > 0:
            return _result("计算失误", f"数值偏差 {rel_err:.0%}（{s} vs {c}），计算方法或中间步骤可能有误", confidence=0.70)
        if sv * cv < 0 and abs(sv) > 1e-6:
            return _result("概念混淆", f"符号相反（{s} vs {c}），可能混淆了正负方向", confidence=0.80)
        return _result("计算失误", f"数值差异显著（{s} vs {c}），偏离 {rel_err:.0%}", confidence=0.75)
    except (ValueError, TypeError):
        pass

    # 4. Text-based classification
    s_set = set(s)
    c_set = set(c)

    if not c_set:
        return _result("知识缺漏", "正确答案为空，可能是题目配置错误", confidence=0.50)

    overlap = len(s_set & c_set) / len(c_set)

    if overlap > 0.75:
        return _result("概念边界混淆", "核心概念大部分正确但表述不够精确", confidence=0.75)
    if overlap > 0.40:
        return _result("概念混淆", "部分概念正确但混淆了相关但不同的概念", confidence=0.65)

    # Short answer detection
    if len(s) < len(c) * 0.3 and len(s) < 30:
        return _result("阅读理解", "回答过于简短，可能未充分理解题意", confidence=0.60)

    # Question-in-answer detection
    if "?" in s or "？" in s:
        return _result("审题不清", "学生回答中包含反问，可能没有理解题目要求", confidence=0.70)

    # Default
    return _result("知识缺漏", "回答与正确答案差异较大，该知识点可能尚未掌握", confidence=0.55)


def classify_with_llm(
    student_answer: str,
    correct_answer: str,
    question: str = "",
    llm_call: Optional[Callable] = None,
) -> Dict[str, Any]:
    """Dual-channel classification: rule first, LLM override if available.

    If llm_call is provided, the LLM result overrides a low-confidence
    (< 0.7) rule result with source="llm".
    """
    rule_result = classify_error(student_answer, correct_answer)

    if llm_call is None or rule_result["confidence"] >= 0.80:
        return rule_result

    try:
        llm_result = llm_call(
            system=(
                "你是一位教学诊断专家。请分析学生的错误答案并给出错因分类。"
                f"可选分类：{', '.join(ERROR_CATEGORIES)}。"
                "输出 JSON: {\"error_type\": \"...\", \"detail\": \"...\"}"
            ),
            user=(
                f"题目：{question}\n"
                f"学生答案：{student_answer}\n"
                f"正确答案：{correct_answer}\n"
            ),
        )
        # Parse LLM JSON response (simplified)
        import json as _json
        if isinstance(llm_result, str):
            llm_result = _json.loads(llm_result)
        llm_type = llm_result.get("error_type", rule_result["error_type"])
        if llm_type not in ERROR_CATEGORIES:
            llm_type = rule_result["error_type"]
        return {
            "error_type": llm_type,
            "detail": llm_result.get("detail", rule_result["detail"]),
            "source": "llm",
            "confidence": 0.85,
        }
    except Exception:
        return rule_result


def generate_variants(
    question: str,
    correct_answer: str,
    kp_id: str = "",
    kp_name: str = "",
    count: int = 3,
    llm_call: Optional[Callable] = None,
) -> List[Dict[str, Any]]:
    """Generate Bloom-leveled variant questions with answers and explanations.

    Returns list of:
        {bloom_level, question, answer, explanation, difficulty}
    """
    bloom_levels = ["remember", "understand", "apply"]

    if llm_call:
        try:
            variants = _generate_variants_llm(
                question, correct_answer, kp_name, bloom_levels, llm_call
            )
            # Ensure we have at least `count` variants
            if len(variants) >= count:
                return variants[:count]
        except Exception as exc:
            logger.warning(f"[mistake_review] LLM variant generation failed: {exc}")

    # Rule-based fallback
    return _generate_variants_rule(question, correct_answer, kp_name, bloom_levels[:count])


def _generate_variants_rule(
    question: str,
    correct_answer: str,
    kp_name: str,
    bloom_levels: List[str],
) -> List[Dict[str, Any]]:
    """Template-based variant generation with structured answers."""
    variants = []
    topic = kp_name or question[:60]

    for level in bloom_levels:
        template = BLOOM_VARIANT_TEMPLATES.get(level, BLOOM_VARIANT_TEMPLATES["understand"])

        if level == "remember":
            variant_q = f"{template['intro']}\n\n{topic} 的核心定义是什么？请写出其关键概念。"
            variant_a = f"关于 {topic} 的标准定义是：{correct_answer[:200]}"
            variant_expl = template["answer_hint"]

        elif level == "understand":
            variant_q = f"{template['intro']}\n\n请用你自己的话解释「{topic}」的含义，并给出一个生活中的例子。"
            variant_a = f"核心解释：{correct_answer[:200]}。生活中的例子：可以从日常场景中类比..."
            variant_expl = template["answer_hint"]

        elif level == "apply":
            variant_q = f"{template['intro']}\n\n基于「{topic}」的知识，请解决以下场景问题：___（填入具体场景）___。"
            variant_a = f"解题步骤：1) 识别问题类型 → 2) 应用 {topic} 原理 → 3) 计算/推导 → 4) 验证结果。参考解法：{correct_answer[:200]}"
            variant_expl = template["answer_hint"]

        else:  # analyze
            variant_q = f"{template['intro']}\n\n在「{topic}」的相关场景中，方法A和方法B的优劣分别是什么？请从至少三个维度分析。"
            variant_a = f"分析框架：从正确性、效率、可维护性三个维度对比。正确解为：{correct_answer[:200]}"
            variant_expl = template["answer_hint"]

        variants.append({
            "bloom_level": level,
            "question": variant_q,
            "answer": variant_a,
            "explanation": variant_expl,
            "difficulty": {"remember": 1, "understand": 2, "apply": 3, "analyze": 4}.get(level, 2),
        })

    return variants


def _generate_variants_llm(
    question: str,
    correct_answer: str,
    kp_name: str,
    bloom_levels: List[str],
    llm_call: Callable,
) -> List[Dict[str, Any]]:
    """LLM-based variant generation."""
    import json as _json

    response = llm_call(
        system=(
            "你是一位出题专家。基于原题和正确答案，生成 Bloom 各层级的变式题。"
            f"层级：{', '.join(bloom_levels)}。每个变式题必须包含 question、answer、explanation 三字段。"
            "输出格式：JSON 数组 [{bloom_level, question, answer, explanation}]"
        ),
        user=(
            f"原题：{question}\n正确答案：{correct_answer}\n知识点：{kp_name}\n"
            f"请为以下 Bloom 层级各生成一道变式题：{', '.join(bloom_levels)}"
        ),
    )
    if isinstance(response, str):
        return _json.loads(response)
    return response


def build_heatmap_matrix(
    mistakes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build mistake heatmap: knowledge_point × error_category cross-tabulation."""
    kp_set = sorted(set(m.get("kp_id", "") for m in mistakes if m.get("kp_id")))
    cat_set = ERROR_CATEGORIES
    matrix = []

    for kp in kp_set:
        row_data: Dict[str, Any] = {"kp_id": kp}
        for cat in cat_set:
            row_data[cat] = sum(
                1 for m in mistakes
                if m.get("kp_id") == kp and m.get("error_type") == cat
            )
        row_data["total"] = sum(row_data.get(c, 0) for c in cat_set)
        matrix.append(row_data)

    return {
        "categories": cat_set,
        "kps": kp_set,
        "matrix": matrix,
        "total_mistakes": len(mistakes),
    }


def _result(error_type: str, detail: str, confidence: float = 0.70) -> Dict[str, Any]:
    return {
        "error_type": error_type,
        "detail": detail,
        "source": "rule",
        "confidence": confidence,
    }
