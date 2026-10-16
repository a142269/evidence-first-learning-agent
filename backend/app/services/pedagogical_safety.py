"""Pedagogical Safety / Scaffolding Guard (P1.1)

把通用"内容安全"升级为"教学安全"。SafeTutors / Scaffolding 研究指出，AI tutor
的危险不只是 prompt injection / 黄色内容，更核心的教学风险包括：

    1. 直接泄题（answer_leak）—— 学生只 copy 不思考
    2. 分层失败（scaffolding_failure）—— 一次性吐答案而非引导
    3. 误概念强化（misconception_reinforcement）—— echo 学生错误推理
    4. uptake 缺失（uptake_missing）—— 没有把球抛回学生

本模块给出 4 字段评估，纯规则（无 LLM），10ms 内可返回，可被以下模块按需接入：
    * agents/critic_agent.py PedagogyDimension 作为补充信号
    * agents/cov_verifier.py 在 ContentRewriter 前调用
    * services/mistake_review / variant_generator 输出过滤层

设计取舍:
    * 规则化 = 可解释、可测试、不依赖 LLM 配额
    * 4 个 0-1 标量 + 1 段 uptake 文本，便于前端 Cockpit 直接渲染
    * 与 B 的 attribution / KT 解耦：B 提供的"错因 / 当前 Bloom 层级"可作为 hint
      传进来精化判断；不传也能跑（用 mock context 兜底）
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ================================================================
# 数据模型
# ================================================================
@dataclass
class TutoringContext:
    """教学上下文（B 可提供更精细字段，全 optional）"""
    student_question: str = ""
    student_answer: Optional[str] = None         # 学生的（可能错的）答案
    correct_answer: Optional[str] = None         # 真正的正确答案
    bloom_level: Optional[str] = None            # B 的 KT/Bloom 层级标注（remember/understand/...）
    attribution_category: Optional[str] = None   # B 的 8 分类归因（公式/概念/计算/...）
    kp_ids: List[str] = field(default_factory=list)


@dataclass
class PedagogicalSafetyResult:
    """4 字段教学安全评估，全部 JSON 可序列化"""
    scaffolding_score: float                  # 0.0(无引导，直接吐答案) ~ 1.0(完整分层引导)
    answer_leak_risk: float                   # 0.0(完全不泄题) ~ 1.0(整道题答案逐字给出)
    misconception_reinforcement_risk: float   # 0.0(明确纠错) ~ 1.0(echo 学生错答不纠正)
    student_uptake_prompt: str                # 引导学生下一步思考的问题
    overall_risk: float                       # max(answer_leak, misconception) - scaffolding/2
    evidence: List[str]                       # 触发各项分数的关键证据（debug 用）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scaffolding_score": round(self.scaffolding_score, 3),
            "answer_leak_risk": round(self.answer_leak_risk, 3),
            "misconception_reinforcement_risk": round(self.misconception_reinforcement_risk, 3),
            "student_uptake_prompt": self.student_uptake_prompt,
            "overall_risk": round(self.overall_risk, 3),
            "evidence": self.evidence,
        }


# ================================================================
# 模式 / 关键词字典
# ================================================================
# 引导性话术（提高 scaffolding_score）
_SCAFFOLD_PATTERNS = [
    r"你(觉得|认为|是否|能否|可以)",
    r"想想?\s*[一二三四五六七]?",
    r"考虑一下",
    r"我们?\s*(一起|先)",
    r"试着",
    r"分(几|两|三)步",
    r"第(一|二|三|1|2|3)步",
    r"提示[:：]",
    r"先\s*\S+\s*再",
    r"为什么",
]

# 直接答案标志（提高 answer_leak_risk）
_LEAK_PATTERNS = [
    r"答案(是|为|应该是)",
    r"正确答案",
    r"标准答案",
    r"最终(结果|答案)",
    r"^(解|答)[:：]",
    r"^=\s*",  # 单独 "= 数字" 行
    r"完整代码[:：]",
    r"完整解答",
    r"直接给(出|你)",
]

# 误概念强化（含学生错答 echo 或盲目肯定）
_MISCONCEPTION_ECHO_PATTERNS = [
    r"你说得?对",
    r"没错[，,]",
    r"完全(正确|对)",
    r"是的[，,]",
    r"赞同你",
]

# Uptake 模板池（按 Bloom 层级选择）
_UPTAKE_TEMPLATES = {
    "remember": [
        "你能复述一下刚才提到的关键概念吗？",
        "在这个定义里，有哪些词是你以前没见过的？",
    ],
    "understand": [
        "用你自己的话解释一下这个原理，可以吗？",
        "这个概念和你之前学的什么内容最像？",
    ],
    "apply": [
        "如果把题目里的数字换成 X，结果会怎么变？",
        "试着画一个最简单的例子来验证刚才的方法。",
    ],
    "analyze": [
        "这个问题如果换一种条件，哪一步最容易出错？",
        "可以把这道题拆成几个子问题吗？",
    ],
    "evaluate": [
        "如果让你点评这种解法，你觉得它的优缺点是什么？",
        "有没有别的解法可能更高效？为什么？",
    ],
    "create": [
        "你能设计一个类似但更难一点的题目吗？",
        "如果让你写一个真实场景的例子来用这个方法，你会怎么写？",
    ],
    "default": [
        "你能用一句话总结刚才学到的东西吗？",
        "下一步你打算怎么验证自己的理解？",
    ],
}


# ================================================================
# 评估器
# ================================================================
class PedagogicalSafetyEvaluator:
    """4 字段教学安全规则评估器。

    用法::

        ev = PedagogicalSafetyEvaluator()
        ctx = TutoringContext(
            student_question="2x+3=7 求 x",
            student_answer="x=4",
            correct_answer="x=2",
            bloom_level="apply",
        )
        result = ev.evaluate(tutor_response="正确答案是 x=2，过程: 2x=4, x=2", context=ctx)
        # result.answer_leak_risk → ~0.85（含"正确答案" + 直接给数值）
    """

    def evaluate(
        self,
        tutor_response: str,
        context: Optional[TutoringContext] = None,
    ) -> PedagogicalSafetyResult:
        ctx = context or TutoringContext()
        response = (tutor_response or "").strip()

        evidence: List[str] = []
        scaffold = self._score_scaffolding(response, evidence)
        leak = self._score_answer_leak(response, ctx, evidence)
        misc = self._score_misconception(response, ctx, evidence)
        uptake = self._build_uptake_prompt(response, ctx)

        # 综合风险：取两个 risk 的 max，再用 scaffolding/2 抵消（最低 0）
        overall = max(0.0, max(leak, misc) - scaffold / 2)

        return PedagogicalSafetyResult(
            scaffolding_score=scaffold,
            answer_leak_risk=leak,
            misconception_reinforcement_risk=misc,
            student_uptake_prompt=uptake,
            overall_risk=overall,
            evidence=evidence,
        )

    # ── 子评分 ─────────────────────────────────────────────
    def _score_scaffolding(self, response: str, evidence: List[str]) -> float:
        """命中越多引导性话术 → 分越高，上限 1.0。"""
        if not response:
            return 0.0
        hits = 0
        for pat in _SCAFFOLD_PATTERNS:
            if re.search(pat, response):
                hits += 1
                if len(evidence) < 10:
                    evidence.append(f"scaffold:{pat}")
        # 命中 ≥ 3 即接近满分
        return min(1.0, hits / 3.0)

    def _score_answer_leak(
        self, response: str, ctx: TutoringContext, evidence: List[str]
    ) -> float:
        """直接答案标志命中 + correct_answer 整体出现 → 风险加权。"""
        if not response:
            return 0.0
        risk = 0.0
        for pat in _LEAK_PATTERNS:
            if re.search(pat, response):
                risk += 0.25
                if len(evidence) < 10:
                    evidence.append(f"leak:{pat}")

        # 如果有 correct_answer 且整段出现在 response 里 → 强信号
        if ctx.correct_answer:
            normalized = self._normalize(ctx.correct_answer)
            if normalized and self._normalize(response).find(normalized) >= 0:
                risk += 0.5
                evidence.append("leak:full_correct_answer_inline")

        return min(1.0, risk)

    def _score_misconception(
        self, response: str, ctx: TutoringContext, evidence: List[str]
    ) -> float:
        """echo 学生错答 + 盲目肯定话术 → 风险加权。"""
        if not response:
            return 0.0
        risk = 0.0

        # 盲目肯定话术
        affirmation_hit = False
        for pat in _MISCONCEPTION_ECHO_PATTERNS:
            if re.search(pat, response):
                affirmation_hit = True
                if len(evidence) < 10:
                    evidence.append(f"misc_affirm:{pat}")
                break

        # echo 学生错答
        echoed_wrong = False
        if ctx.student_answer and ctx.correct_answer:
            wrong = self._normalize(ctx.student_answer)
            correct = self._normalize(ctx.correct_answer)
            resp_n = self._normalize(response)
            if wrong and wrong != correct and len(wrong) >= 1 and resp_n.find(wrong) >= 0:
                echoed_wrong = True
                evidence.append("misc:wrong_answer_echoed")
                # 同时缺乏纠错信号 → 加重
                if not re.search(r"(不对|错|更正|纠正|应该是|实际上|其实)", response):
                    risk += 0.6
                    evidence.append("misc:no_correction_signal")
                else:
                    risk += 0.2

        if affirmation_hit and echoed_wrong:
            risk += 0.3  # 既肯定又 echo 错答 → 双重风险

        return min(1.0, risk)

    def _build_uptake_prompt(
        self, response: str, ctx: TutoringContext
    ) -> str:
        """按 Bloom 层级选模板；已含问号 → 直接复用响应里的问句。"""
        # 如果响应里已经有问句，复用第一个
        if response and "？" in response:
            first_q = response.split("？")[0].split("\n")[-1].strip() + "？"
            if 6 <= len(first_q) <= 80:
                return first_q

        bloom = (ctx.bloom_level or "default").lower()
        pool = _UPTAKE_TEMPLATES.get(bloom, _UPTAKE_TEMPLATES["default"])
        # 用 question hash 做稳定选择（同 question 同 prompt，便于测试）
        idx = (hash(ctx.student_question or "x") % len(pool) + len(pool)) % len(pool)
        return pool[idx]

    @staticmethod
    def _normalize(text: str) -> str:
        """归一化：去空白 / 标点 / 大小写。"""
        if not text:
            return ""
        return re.sub(r"[\s\.,;:!?，。；：！？\(\)（）]+", "", text).lower()


# ================================================================
# CriticDimension 适配（可选接入 critic_agent 维度链）
# ================================================================
def make_critic_dimension() -> Any:
    """工厂：返回一个可插入 ``CriticAgent(dimensions=[...])`` 的维度对象。

    懒导入避免循环依赖，调用方按需:
        from backend.app.services.pedagogical_safety import make_critic_dimension
        from backend.app.agents.critic_agent import CriticAgent

        agent = CriticAgent(dimensions=[..., make_critic_dimension()])
    """
    from backend.app.agents.critic_agent import (
        CriticDimension,
        CriticIssue,
        CriticVerdict,
    )

    evaluator = get_pedagogical_safety_evaluator()

    class PedagogicalSafetyDimension(CriticDimension):
        """把 PedagogicalSafetyEvaluator 包装为 critic 维度。"""

        @property
        def name(self) -> str:
            return "pedagogical_safety"

        def evaluate(self, content: str, context: Dict[str, Any]) -> "CriticVerdict":
            ctx = TutoringContext(
                student_question=context.get("student_question", ""),
                student_answer=context.get("student_answer"),
                correct_answer=context.get("correct_answer"),
                bloom_level=context.get("bloom_level"),
                attribution_category=context.get("attribution_category"),
                kp_ids=context.get("kp_ids", []),
            )
            r = evaluator.evaluate(content, ctx)

            issues: List[Any] = []
            if r.answer_leak_risk >= 0.5:
                issues.append(
                    CriticIssue(
                        severity="major",
                        description=f"answer_leak_risk={r.answer_leak_risk:.2f} 偏高，疑似直接泄题",
                        suggestion="把'答案是 X'改成'你觉得这一步应该……'",
                    )
                )
            if r.misconception_reinforcement_risk >= 0.5:
                issues.append(
                    CriticIssue(
                        severity="major",
                        description=(
                            f"misconception_risk={r.misconception_reinforcement_risk:.2f} 偏高，"
                            "可能 echo 了学生错答而未纠正"
                        ),
                        suggestion="添加明确的纠错信号：'实际上' / '正确的做法是'",
                    )
                )
            if r.scaffolding_score < 0.3:
                issues.append(
                    CriticIssue(
                        severity="minor",
                        description=f"scaffolding_score={r.scaffolding_score:.2f} 偏低，缺乏引导话术",
                        suggestion="加入'你觉得' / '想想' / '第一步' 等引导提示",
                    )
                )

            # score 设计：1 - overall_risk
            score = round(max(0.0, 1.0 - r.overall_risk), 2)
            return CriticVerdict(
                dimension=self.name,
                passed=score >= self.pass_threshold,
                score=score,
                issues=issues,
                suggestions=[r.student_uptake_prompt] if r.student_uptake_prompt else [],
                evidence=r.to_dict(),
            )

    return PedagogicalSafetyDimension()


# ================================================================
# 全局单例
# ================================================================
_evaluator: Optional[PedagogicalSafetyEvaluator] = None


def get_pedagogical_safety_evaluator() -> PedagogicalSafetyEvaluator:
    global _evaluator
    if _evaluator is None:
        _evaluator = PedagogicalSafetyEvaluator()
    return _evaluator
