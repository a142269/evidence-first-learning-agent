"""
内容安全过滤 + 防幻觉机制
迁移自: 旧项目 configs/data/quality_rules.yaml + rules/intervention_rules.yaml
核心: 链式验证管道 —— 复用旧项目规则引擎的链式评估模式
"""
import re
import logging
from typing import List, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FilterLevel(Enum):
    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class FilterResult:
    """过滤结果 —— 类似旧项目 Rules 的评估结果"""
    level: FilterLevel
    reason: str = ""
    suggestions: List[str] = field(default_factory=list)
    flagged_content: List[str] = field(default_factory=list)


class ContentSafetyChecker:
    """
    内容安全 + 防幻觉检查器

    设计迁移:
    旧项目 quality_rules.yaml → 新项目 SAFETY_RULES
    旧项目 规则引擎链式评估 → 新项目 链式过滤器
    """

    # ---- 敏感词库（教育场景） ----
    SENSITIVE_PATTERNS = [
        r"作弊",
        r"代考",
        r"替考",
        r"代写",
        r"论文代写",
    ]

    # ---- 幻觉特征模式 ----
    # 借鉴旧项目异常检测的统计方法，迁移到文本层面
    HALLUCINATION_PATTERNS = [
        (r"根据.{0,20}研究表明.{0,50}但是(?!.*\d{4})", "缺乏具体引用"),
        (r"所有.{0,10}都", "过度绝对化表述"),
        (r"一定.{0,10}必然", "缺乏学术严谨性的表述"),
        (r"\d{4}年.{0,20}发现.{0,50}然而", "时间+事件可能为虚构"),
    ]

    def __init__(self):
        self.filters = [
            self._check_sensitive_content,
            self._check_hallucination,
            self._check_academic_integrity,
            self._check_source_citation,
        ]

    async def validate(
        self, content: str, knowledge_context: List[str] = None
    ) -> FilterResult:
        """
        链式验证 —— 直接复用旧项目规则引擎的链式评估模式

        旧项目模式:
        for rule in rules:
            if not rule.evaluate(data):
                return False

        新项目模式:
        for check in self.filters:
            result = check(content, knowledge_context)
            if result.level == FilterLevel.BLOCK:
                return result  # 快速失败
        """
        all_warnings = []
        all_flagged = []

        for check in self.filters:
            result = check(content, knowledge_context)
            if result.level == FilterLevel.BLOCK:
                logger.warning(f"内容被拦截: {result.reason}")
                return result
            all_warnings.append(result.reason)
            all_flagged.extend(result.flagged_content)

        if all_warnings:
            return FilterResult(
                level=FilterLevel.WARN,
                reason="; ".join([w for w in all_warnings if w]),
                flagged_content=all_flagged,
            )

        return FilterResult(level=FilterLevel.PASS)

    def _check_sensitive_content(
        self, content: str, context=None
    ) -> FilterResult:
        """敏感内容检查 —— 对应旧项目数据质量校验"""
        flagged = []
        for pattern in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, content)
            flagged.extend(matches)

        if flagged:
            return FilterResult(
                level=FilterLevel.BLOCK,
                reason=f"检测到敏感内容: {', '.join(flagged)}",
                flagged_content=flagged,
            )
        return FilterResult(level=FilterLevel.PASS)

    def _check_hallucination(
        self, content: str, context=None
    ) -> FilterResult:
        """
        幻觉检测 —— 借鉴旧项目异常检测思想

        旧项目: 消费金额 3-sigma 异常检测
        新项目: 文本中"过度绝对化"模式检测
        """
        warnings = []
        for pattern, description in self.HALLUCINATION_PATTERNS:
            if re.search(pattern, content):
                warnings.append(description)

        if warnings:
            return FilterResult(
                level=FilterLevel.WARN,
                reason=f"可疑表述: {', '.join(warnings)}",
                suggestions=["建议添加具体引用来源", "使用更严谨的学术表述"],
            )
        return FilterResult(level=FilterLevel.PASS)

    def _check_academic_integrity(
        self, content: str, context=None
    ) -> FilterResult:
        """学术诚信检查"""
        direct_answer_patterns = [
            r"答案是.{0,20}$",
            r"正确答案.{0,10}$",
        ]
        for pattern in direct_answer_patterns:
            if re.search(pattern, content) and len(content) < 100:
                return FilterResult(
                    level=FilterLevel.WARN,
                    reason="疑似直接给出答案，应引导解题思路",
                    suggestions=["请提供解题步骤和思路引导"],
                )
        return FilterResult(level=FilterLevel.PASS)

    def _check_source_citation(
        self, content: str, context=None
    ) -> FilterResult:
        """引用来源检查 —— 对应旧项目数据血缘追踪"""
        factual_indicators = [
            r"根据研究",
            r"数据显示",
            r"实验表明",
            r"据统计",
        ]
        has_factual_claim = any(
            re.search(p, content) for p in factual_indicators
        )
        has_citation = bool(re.search(r"\[\d+\]|\(\d{4}\)", content))

        if has_factual_claim and not has_citation:
            return FilterResult(
                level=FilterLevel.WARN,
                reason="事实性陈述缺少引用来源",
                suggestions=["请标注信息来源"],
            )
        return FilterResult(level=FilterLevel.PASS)
