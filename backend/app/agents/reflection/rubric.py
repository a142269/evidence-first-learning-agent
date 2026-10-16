"""
ReflectionRubric - 多维度评分量表 + Bloom-aware 失败模式

设计:
- 5 维评分: factual / pedagogy / bloom_match / engagement / structure
- 每维独立的规则引擎 + 阈值 (低耦合 LLM, 毫秒级)
- Bloom-aware: 不同 Bloom 层级有不同的失败模式诊断

学术贡献 (创新点):
传统 Reflexion (Shinn 2023) 是通用 verbal 反馈; 我们的 Bloom-aware Rubric
按学习目标层级针对性诊断, 这是 A3 项目的原创设计, 可投 AIED workshop。
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from backend.app.agents.reflection.trace import (
    ReflectionScore,
    WeaknessItem,
)


# ================================================================
# Bloom-aware 失败模式 — 按层级定义"应警告什么"
# ================================================================
BLOOM_FAILURE_MODES: Dict[str, List[Tuple[str, str]]] = {
    # (检查描述, 提示)
    "remember": [
        ("事实陈述应明确无误", "补充准确定义并标注来源"),
        ("术语应规范使用", "避免使用未定义的非标准词"),
    ],
    "understand": [
        ("应有例子说明", "添加至少 1-2 个具体实例"),
        ("应有类比帮助理解", "用日常生活类比降低门槛"),
    ],
    "apply": [
        ("应有可执行步骤", "把抽象描述拆为可复现的步骤"),
        ("应包含代码或操作示例", "提供可直接运行/上手的范例"),
    ],
    "analyze": [
        ("应展现对比/拆解", "列出至少 2 个对照对象"),
        ("应说明结构性关系", "明确部分 - 整体 / 因 - 果 关系"),
    ],
    "evaluate": [
        ("应陈述判断标准", "明确权衡的维度"),
        ("应包含利弊讨论", "列优势 + 局限"),
    ],
    "create": [
        ("应体现新颖整合", "避免只是概念罗列"),
        ("应给出可创新的开放问题", "引导学生提出自己的方案"),
    ],
}


# ================================================================
# 评分量表
# ================================================================
class ReflectionRubric:
    """多维度评分 + Bloom-aware 失败模式诊断

    用法:
        rubric = ReflectionRubric()
        score, weaknesses = rubric.evaluate(content, bloom="apply", rag_results=...)
    """

    # ---- 各维度阈值 ----
    MIN_LENGTH = 80
    MIN_UNIQUE_WORDS = 8
    PASS_OVERALL = 0.7

    # 关键词库 (复用 critic_agent BloomDimension 的设计)
    BLOOM_KEYWORDS: Dict[str, List[str]] = {
        "remember":   ["定义", "列出", "描述", "是什么", "define"],
        "understand": ["解释", "总结", "为什么", "理解为", "explain"],
        "apply":      ["使用", "实现", "应用", "代码", "练习", "apply"],
        "analyze":    ["分析", "比较", "对比", "区别", "analyze"],
        "evaluate":   ["评估", "判断", "优缺点", "evaluate"],
        "create":     ["设计", "构建", "创新", "综合", "create"],
    }

    PEDAGOGY_PATTERNS: Dict[str, List[str]] = {
        "examples": ["例如", "比如", "举个例子", "example", "实例"],
        "analogy":  ["就像", "好比", "类比", "类似", "可以理解为"],
        "steps":    ["首先", "然后", "接着", "最后", "第一步", "step"],
        "practice": ["练习", "巩固", "回顾", "习题", "动手"],
    }

    BLOOM_ORDER = [
        "remember", "understand", "apply",
        "analyze", "evaluate", "create",
    ]

    def evaluate(
        self,
        content: str,
        bloom: str = "understand",
        rag_results: list = None,
    ) -> Tuple[ReflectionScore, List[WeaknessItem]]:
        """计算 5 维评分 + 弱点诊断"""
        score = ReflectionScore()
        weaknesses: List[WeaknessItem] = []

        if not content or not content.strip():
            return score, [WeaknessItem(
                "structure", "blocker", "内容为空",
                suggestion="请生成实质性内容",
            )]

        # ---- structure ----
        score.structure = self._score_structure(content, weaknesses)
        # ---- factual (RAG 重叠度) ----
        score.factual = self._score_factual(content, rag_results or [], weaknesses)
        # ---- pedagogy ----
        score.pedagogy = self._score_pedagogy(content, weaknesses)
        # ---- bloom_match ----
        score.bloom_match = self._score_bloom(
            content, bloom, weaknesses,
        )
        # ---- engagement ----
        score.engagement = self._score_engagement(content, weaknesses)

        # 加权综合
        score.overall = (
            0.30 * score.factual
            + 0.25 * score.pedagogy
            + 0.20 * score.bloom_match
            + 0.15 * score.structure
            + 0.10 * score.engagement
        )
        return score, weaknesses

    # ----------------------------------------------------------------
    # 5 个维度
    # ----------------------------------------------------------------
    def _score_structure(
        self, content: str, weaknesses: List[WeaknessItem],
    ) -> float:
        s = content.strip()
        meaningful = re.sub(r'[\s`#*\-\[\]()>]+', '', s)
        score = 1.0
        if len(meaningful) < self.MIN_LENGTH:
            score -= 0.4
            weaknesses.append(WeaknessItem(
                "structure", "major",
                f"有效内容过短({len(meaningful)}字符)",
                suggestion="补充实质性段落",
            ))
        if not re.search(r'^#{1,6}\s', s, re.MULTILINE):
            score -= 0.15
            weaknesses.append(WeaknessItem(
                "structure", "minor",
                "缺少标题层级",
                suggestion="使用 # / ## / ### 划分章节",
            ))
        if not re.search(r'\n\n', s):
            score -= 0.1
        return max(0.0, score)

    def _score_factual(
        self, content: str, rag_results: list,
        weaknesses: List[WeaknessItem],
    ) -> float:
        if not rag_results:
            return 0.8  # 无 RAG 不扣分, 但不给满分
        # 抽取术语并计算 Jaccard 重叠
        terms = set(
            t.lower() for t in
            re.findall(r'[一-鿿]{2,}|[A-Za-z]{3,}', content)
        )
        rag_terms = set()
        for r in rag_results:
            rc = r.get("content", "")
            rag_terms.update(
                t.lower() for t in
                re.findall(r'[一-鿿]{2,}|[A-Za-z]{3,}', rc)
            )
        if not terms or not rag_terms:
            return 0.6
        overlap_ratio = len(terms & rag_terms) / len(terms)
        if overlap_ratio < 0.15:
            weaknesses.append(WeaknessItem(
                "factual", "major",
                f"与知识库重叠度仅 {overlap_ratio:.0%}",
                suggestion="参考 RAG 检索结果, 校对关键事实",
            ))
            return 0.4
        return min(1.0, 0.5 + overlap_ratio)

    def _score_pedagogy(
        self, content: str, weaknesses: List[WeaknessItem],
    ) -> float:
        score = 1.0
        hits = {}
        for k, patterns in self.PEDAGOGY_PATTERNS.items():
            hits[k] = any(p in content for p in patterns)

        if not hits["examples"]:
            score -= 0.25
            weaknesses.append(WeaknessItem(
                "pedagogy", "major", "缺少具体例子",
                suggestion="每个核心概念后加 1-2 个生活化或技术化实例",
            ))
        if not hits["analogy"]:
            score -= 0.15
        if not hits["steps"]:
            score -= 0.10
        if not hits["practice"]:
            score -= 0.10
        return max(0.0, score)

    def _score_bloom(
        self, content: str, target: str,
        weaknesses: List[WeaknessItem],
    ) -> float:
        if target not in self.BLOOM_ORDER:
            target = "understand"
        target_idx = self.BLOOM_ORDER.index(target)

        # 检测最高命中层级
        detected_idx = 0
        for i in range(len(self.BLOOM_ORDER) - 1, -1, -1):
            level = self.BLOOM_ORDER[i]
            if any(kw in content for kw in self.BLOOM_KEYWORDS[level]):
                detected_idx = i
                break

        # Bloom-aware 弱点检查
        for desc, suggestion in BLOOM_FAILURE_MODES.get(target, []):
            covered = self._covered_by_keyword(content, target, desc)
            if not covered:
                weaknesses.append(WeaknessItem(
                    "bloom", "minor",
                    f"[{target}] {desc} — 未在内容中明确体现",
                    suggestion=suggestion,
                ))

        if detected_idx < target_idx:
            return 0.3 + 0.1 * detected_idx
        return 1.0 if detected_idx == target_idx else 0.9

    def _covered_by_keyword(
        self, content: str, bloom: str, hint: str,
    ) -> bool:
        # 粗启发: 只要命中该 bloom 层级的关键词就视为覆盖
        return any(
            kw in content for kw in self.BLOOM_KEYWORDS.get(bloom, [])
        )

    def _score_engagement(
        self, content: str, weaknesses: List[WeaknessItem],
    ) -> float:
        score = 0.6
        if re.search(r"[?？]", content):
            score += 0.15
        if re.search(r"你|学习者|同学", content):
            score += 0.1
        if re.search(r"[😀-🙏✅⚠️❓🎯💡]", content):
            score += 0.1
        if re.search(r"想象|思考|尝试", content):
            score += 0.05
        return min(1.0, score)
