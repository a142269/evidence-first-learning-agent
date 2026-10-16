"""
Attribution Engine — 错题归因 8 分类双通道（T1.2-B）

规则通道先行（基于文本/数值特征），低置信度时调 LLM 兜底。
8 分类（与 A 的 variant_generator 接口约定，英文原样返回）：
  concept_confusion / careless / ambiguous_question / input_error /
  boundary_unclear / prerequisite_missing / procedural_slip / unknown

References:
  - 规则通道：基于错题文本特征 + 数值比较的启发式分类
  - LLM 通道：低置信度时调用统一 LLMClient，约束输出为 8 分类之一
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 8 分类定义（英文，与 A 接口约定一致，勿改）──────────────
ATTRIBUTION_CATEGORIES: List[str] = [
    "concept_confusion",
    "careless",
    "ambiguous_question",
    "input_error",
    "boundary_unclear",
    "prerequisite_missing",
    "procedural_slip",
    "unknown",
]

CATEGORY_LABELS: Dict[str, str] = {
    "concept_confusion": "概念混淆",
    "careless": "粗心失误",
    "ambiguous_question": "题目歧义",
    "input_error": "输入错误",
    "boundary_unclear": "边界不清",
    "prerequisite_missing": "先修知识缺失",
    "procedural_slip": "程序性失误",
    "unknown": "未知",
}

# 规则置信度阈值：低于此值才调 LLM
_LLM_THRESHOLD = 0.60


@dataclass
class AttributionResult:
    """错题归因结果（A 的 variant_generator 直接消费此结构）。"""

    category: str
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    source: str = "rule"  # rule | llm

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category_label"] = CATEGORY_LABELS.get(self.category, "")
        return d


def _try_float(text: str) -> Optional[float]:
    """尝试解析数值（支持百分号、分数简易形式）。"""
    t = text.strip().replace("%", "").replace("，", ",").replace(" ", "")
    # 取第一个数值片段
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    try:
        val = float(m.group())
        if "%" in text:
            val /= 100.0
        return val
    except ValueError:
        return None


class AttributionEngine:
    """错题归因引擎：规则通道 + LLM 兜底双通道。"""

    # 模糊词（题目歧义信号）
    _AMBIGUOUS_HINTS = ("可能", "大约", "大概", "以下哪个可能", "最接近", "估算", "近似")
    # 边界词（边界不清信号）
    _BOUNDARY_HINTS = ("边界", "范围", "区间", "临界", "阈值", "极限", "是否包含")
    # 先修缺失信号：答案涉及更基础的概念
    _PREREQ_HINTS = ("定义", "是什么", "基本", "概念", "含义")

    def __init__(self, llm_client=None):
        self._llm = llm_client

    # ── 规则通道 ────────────────────────────────────────────
    def _rule_classify(
        self,
        question: str,
        user_answer: str,
        correct_answer: str,
        kp_ids: Optional[List[str]] = None,
    ) -> AttributionResult:
        s = str(user_answer).strip()
        c = str(correct_answer).strip()
        q = str(question).strip().lower()

        # 1. 输入错误：空答案 / 未作答
        if not s or s in ("", "未作答", "nan", "null", "None", "空"):
            return AttributionResult(
                category="input_error",
                confidence=0.92,
                evidence={"reason": "empty_or_invalid_answer", "user_answer": s},
                source="rule",
            )

        # 2. 粗心失误：数值接近（差值小），但排除多步骤答案
        s_num, c_num = _try_float(s), _try_float(c)
        has_steps = bool(re.search(r"步骤|step|;", s, re.IGNORECASE)) or s.count(",") >= 2
        if (s_num is not None and c_num is not None and c_num != 0
                and not has_steps):
            rel_diff = abs(s_num - c_num) / max(abs(c_num), 1e-9)
            if rel_diff < 0.15:

                return AttributionResult(
                    category="careless",
                    confidence=0.82,
                    evidence={
                        "reason": "numeric_close",
                        "user_value": s_num,
                        "correct_value": c_num,
                        "relative_diff": round(rel_diff, 4),
                    },
                    source="rule",
                )

        # 3. 题目歧义：题目含模糊词
        if any(h in question for h in self._AMBIGUOUS_HINTS):
            return AttributionResult(
                category="ambiguous_question",
                confidence=0.72,
                evidence={"reason": "ambiguous_wording", "hints_matched": [
                    h for h in self._AMBIGUOUS_HINTS if h in question
                ]},
                source="rule",
            )

        # 4. 边界不清：题目含边界词
        if any(h in question for h in self._BOUNDARY_HINTS):
            return AttributionResult(
                category="boundary_unclear",
                confidence=0.68,
                evidence={"reason": "boundary_wording", "hints_matched": [
                    h for h in self._BOUNDARY_HINTS if h in question
                ]},
                source="rule",
            )

        # 5. 程序性失误：多步骤答案部分正确（含分隔符，部分匹配）
        seps = r"[,，;；、/]|步骤|step"
        s_parts = [p.strip() for p in re.split(seps, s) if p.strip()]
        c_parts = [p.strip() for p in re.split(seps, c) if p.strip()]
        if len(s_parts) >= 2 and len(c_parts) >= 2:
            overlap = sum(1 for p in s_parts if p in c_parts)
            if 0 < overlap < len(c_parts):
                return AttributionResult(
                    category="procedural_slip",
                    confidence=0.66,
                    evidence={
                        "reason": "partial_steps_correct",
                        "correct_steps": overlap,
                        "total_steps": len(c_parts),
                    },
                    source="rule",
                )

        # 6. 先修知识缺失：题目问基础定义但答案完全偏离
        if any(h in question for h in self._PREREQ_HINTS) and s != c:
            return AttributionResult(
                category="prerequisite_missing",
                confidence=0.58,
                evidence={"reason": "basic_concept_question_wrong",
                          "hints_matched": [h for h in self._PREREQ_HINTS if h in question]},
                source="rule",
            )

        # 7. 概念混淆：非空、非数值、答案完全不同（需有实质长度）
        if s != c and s_num is None and c_num is None and len(s) >= 3 and len(c) >= 3:

            return AttributionResult(
                category="concept_confusion",
                confidence=0.70,
                evidence={"reason": "distinct_textual_answer",
                          "user_answer": s, "correct_answer": c},
                source="rule",
            )

        # 8. 兜底
        return AttributionResult(
            category="unknown",
            confidence=0.30,
            evidence={"reason": "no_rule_matched"},
            source="rule",
        )

    # ── LLM 通道 ────────────────────────────────────────────
    def _llm_classify(
        self,
        question: str,
        user_answer: str,
        correct_answer: str,
        kp_ids: Optional[List[str]] = None,
    ) -> AttributionResult:
        """调用 LLM 从 8 分类中选一个，失败时回退到规则结果。"""
        rule = self._rule_classify(question, user_answer, correct_answer, kp_ids)
        if self._llm is None:
            return rule
        try:
            prompt = (
                "你是错题归因专家。从以下 8 个分类中选最贴切的一个，返回 JSON：\n"
                f"分类：{', '.join(ATTRIBUTION_CATEGORIES)}\n"
                "输出格式：{\"category\": \"...\", \"evidence\": \"...\"}\n"
                f"题目：{question}\n学生答案：{user_answer}\n正确答案：{correct_answer}\n"
                f"知识点：{kp_ids or []}"
            )
            resp = self._llm.chat([
                {"role": "system", "content": "你是错题归因助手，只输出 JSON。"},
                {"role": "user", "content": prompt},
            ], temperature=0.2, max_tokens=200)
            data = json.loads(resp) if isinstance(resp, str) else resp
            cat = data.get("category", rule.category)
            if cat not in ATTRIBUTION_CATEGORIES:
                cat = rule.category
            return AttributionResult(
                category=cat,
                confidence=0.85,
                evidence={"llm_reason": data.get("evidence", ""), "rule_fallback": rule.category},
                source="llm",
            )
        except Exception as exc:
            if os.getenv("A3_OFFLINE_DEMO") == "1":
                logger.debug("[attribution] offline demo, LLM 通道跳过，走规则：%s", exc)
            else:
                logger.warning("[attribution] LLM 通道失败，回退规则：%s", exc)
            return rule

    # ── 主入口 ──────────────────────────────────────────────
    def attribute(
        self,
        question: str,
        user_answer: str,
        correct_answer: str,
        user_id: str = "",
        kp_ids: Optional[List[str]] = None,
    ) -> AttributionResult:
        """双通道归因：规则先行，置信度 < %.2f 时调 LLM。"""
        result = self._rule_classify(question, user_answer, correct_answer, kp_ids)
        if result.confidence < _LLM_THRESHOLD:
            result = self._llm_classify(question, user_answer, correct_answer, kp_ids)
        return result


# ── 模块单例 ───────────────────────────────────────────────
_engine: Optional[AttributionEngine] = None


def get_attribution_engine() -> AttributionEngine:
    global _engine
    if _engine is None:
        llm = None
        try:
            from backend.app.core.llm_client import LLMClient
            llm = LLMClient()
        except Exception as exc:
            logger.info("[attribution] LLM client unavailable, rule-only: %s", exc)
        _engine = AttributionEngine(llm_client=llm)
    return _engine
