"""Pedagogical Safety / Scaffolding Guard 测试 (P1.1)

覆盖 4 字段评估的边界条件:
    A. scaffolding_score：高引导 / 无引导 / 部分引导
    B. answer_leak_risk：直接答案 / 含 correct_answer 整体 / 完全规避
    C. misconception_reinforcement：echo 错答 / 盲目肯定 / 明确纠错
    D. student_uptake_prompt：按 Bloom 层级 / 响应已含问句复用 / fallback
    E. overall_risk 综合计算
    F. 空输入 / None ctx 兜底
"""
from __future__ import annotations

import pytest

from backend.app.services.pedagogical_safety import (
    PedagogicalSafetyEvaluator,
    PedagogicalSafetyResult,
    TutoringContext,
    get_pedagogical_safety_evaluator,
)


@pytest.fixture
def ev() -> PedagogicalSafetyEvaluator:
    return PedagogicalSafetyEvaluator()


# ================================================================
# A. scaffolding_score
# ================================================================
class TestScaffolding:
    def test_strong_scaffolding_high_score(self, ev: PedagogicalSafetyEvaluator) -> None:
        text = (
            "我们一起想想，第一步你觉得应该先做什么？\n"
            "想想题目里给了哪些已知量？\n"
            "试着把它们写下来，再考虑怎么列方程。"
        )
        r = ev.evaluate(text)
        assert r.scaffolding_score >= 0.8, r.evidence

    def test_no_scaffolding_zero_score(self, ev: PedagogicalSafetyEvaluator) -> None:
        text = "x = 2"
        r = ev.evaluate(text)
        assert r.scaffolding_score == 0.0

    def test_partial_scaffolding(self, ev: PedagogicalSafetyEvaluator) -> None:
        text = "你觉得这个方程怎么解？"
        r = ev.evaluate(text)
        assert 0 < r.scaffolding_score < 0.8


# ================================================================
# B. answer_leak_risk
# ================================================================
class TestAnswerLeak:
    def test_direct_answer_phrase_high_risk(self, ev: PedagogicalSafetyEvaluator) -> None:
        text = "正确答案是 x=2"
        r = ev.evaluate(text)
        assert r.answer_leak_risk >= 0.25

    def test_full_correct_answer_inline_strong_signal(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(
            student_question="2x+3=7 求 x",
            correct_answer="x=2",
        )
        text = "解：2x=4，所以 x=2"
        r = ev.evaluate(text, ctx)
        # 应包含 "full_correct_answer_inline" 证据
        assert any("full_correct_answer_inline" in e for e in r.evidence)
        assert r.answer_leak_risk >= 0.5

    def test_pure_guidance_no_leak(self, ev: PedagogicalSafetyEvaluator) -> None:
        ctx = TutoringContext(correct_answer="x=2")
        text = "你能先把已知量列出来吗？想想看哪些是变量。"
        r = ev.evaluate(text, ctx)
        assert r.answer_leak_risk == 0.0


# ================================================================
# C. misconception_reinforcement
# ================================================================
class TestMisconception:
    def test_blind_affirmation_with_wrong_echo(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(
            student_answer="x=4",
            correct_answer="x=2",
        )
        text = "你说得对，x=4。我们继续下一题。"
        r = ev.evaluate(text, ctx)
        # 既肯定 ("你说得对") 又 echo 学生错答 ("x=4") 且无纠错
        assert r.misconception_reinforcement_risk >= 0.6

    def test_wrong_echo_with_correction_lower_risk(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(
            student_answer="x=4",
            correct_answer="x=2",
        )
        text = "你的答案 x=4 不对，应该再检查计算步骤——实际上 2x=4 推出 x=2"
        r = ev.evaluate(text, ctx)
        # echo 了错答但有"不对/应该是/实际上"纠错信号 → 风险低很多
        assert r.misconception_reinforcement_risk < 0.5

    def test_no_echo_no_risk(self, ev: PedagogicalSafetyEvaluator) -> None:
        ctx = TutoringContext(
            student_answer="x=4",
            correct_answer="x=2",
        )
        text = "我们一起再算一遍，看看是哪一步出了问题。"
        r = ev.evaluate(text, ctx)
        assert r.misconception_reinforcement_risk == 0.0


# ================================================================
# D. uptake_prompt
# ================================================================
class TestUptakePrompt:
    def test_apply_level_template(self, ev: PedagogicalSafetyEvaluator) -> None:
        ctx = TutoringContext(
            student_question="2x+3=7 求 x",
            bloom_level="apply",
        )
        r = ev.evaluate("解：x=2", ctx)
        # apply 模板池里两条都含 "X" 或 "例子"
        assert "X" in r.student_uptake_prompt or "例子" in r.student_uptake_prompt

    def test_response_with_question_mark_is_reused(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        text = "你能解释一下这个公式的意义吗？再回答我。"
        r = ev.evaluate(text)
        assert "你能解释一下这个公式的意义吗？" == r.student_uptake_prompt

    def test_unknown_bloom_falls_back_to_default(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(bloom_level="some_unknown_level")
        r = ev.evaluate("OK", ctx)
        # default 模板池里两条都含 "总结" 或 "验证"
        assert "总结" in r.student_uptake_prompt or "验证" in r.student_uptake_prompt

    def test_uptake_stable_per_question(self, ev: PedagogicalSafetyEvaluator) -> None:
        """同一 question 多次 evaluate 应得到相同 uptake_prompt（hash 稳定）。"""
        ctx = TutoringContext(student_question="测试题", bloom_level="apply")
        r1 = ev.evaluate("x", ctx)
        r2 = ev.evaluate("x", ctx)
        assert r1.student_uptake_prompt == r2.student_uptake_prompt


# ================================================================
# E. overall_risk
# ================================================================
class TestOverallRisk:
    def test_high_leak_low_scaffold_high_overall(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(correct_answer="x=2")
        r = ev.evaluate("正确答案是 x=2，直接给你", ctx)
        assert r.overall_risk >= 0.5

    def test_strong_scaffold_offsets_some_leak(
        self, ev: PedagogicalSafetyEvaluator
    ) -> None:
        ctx = TutoringContext(correct_answer="x=2")
        leaky_text = "正确答案是 x=2"
        leaky = ev.evaluate(leaky_text, ctx)

        scaffolded_text = (
            "正确答案是 x=2。但我希望你想想，第一步为什么要这么做？"
            "我们一起再考虑一下，试着画出过程。第二步呢？"
        )
        scaffolded = ev.evaluate(scaffolded_text, ctx)
        # scaffolding 提高时 overall_risk 应下降
        assert scaffolded.overall_risk < leaky.overall_risk

    def test_safe_text_zero_overall(self, ev: PedagogicalSafetyEvaluator) -> None:
        r = ev.evaluate("你觉得这个题应该怎么入手？试着写第一步。")
        assert r.overall_risk == 0.0


# ================================================================
# F. 边界
# ================================================================
class TestEdgeCases:
    def test_empty_response(self, ev: PedagogicalSafetyEvaluator) -> None:
        r = ev.evaluate("")
        assert r.scaffolding_score == 0.0
        assert r.answer_leak_risk == 0.0
        assert r.misconception_reinforcement_risk == 0.0
        assert r.overall_risk == 0.0
        assert r.student_uptake_prompt  # uptake 总有兜底文本

    def test_none_context_works(self, ev: PedagogicalSafetyEvaluator) -> None:
        r = ev.evaluate("正确答案是 x=2", context=None)
        assert isinstance(r, PedagogicalSafetyResult)

    def test_to_dict_serializable(self, ev: PedagogicalSafetyEvaluator) -> None:
        import json
        r = ev.evaluate("hello")
        d = r.to_dict()
        # 必须可被 json.dumps 序列化（前端 / API 直传）
        json.dumps(d, ensure_ascii=False)
        assert set(d.keys()) == {
            "scaffolding_score",
            "answer_leak_risk",
            "misconception_reinforcement_risk",
            "student_uptake_prompt",
            "overall_risk",
            "evidence",
        }


# ================================================================
# G. 全局单例
# ================================================================
def test_singleton_returns_same_instance() -> None:
    a = get_pedagogical_safety_evaluator()
    b = get_pedagogical_safety_evaluator()
    assert a is b


# ================================================================
# H. CriticDimension 适配（可选接入 critic_agent 维度链）
# ================================================================
class TestCriticDimensionAdapter:
    def test_make_critic_dimension_returns_compatible_dimension(self) -> None:
        from backend.app.agents.critic_agent import CriticDimension, CriticVerdict
        from backend.app.services.pedagogical_safety import make_critic_dimension

        dim = make_critic_dimension()
        assert isinstance(dim, CriticDimension)
        assert dim.name == "pedagogical_safety"

        verdict = dim.evaluate(
            "你觉得这道题怎么入手？想想第一步。",
            context={"bloom_level": "apply"},
        )
        assert isinstance(verdict, CriticVerdict)
        assert verdict.dimension == "pedagogical_safety"
        assert 0.0 <= verdict.score <= 1.0

    def test_critic_dimension_flags_leak(self) -> None:
        from backend.app.services.pedagogical_safety import make_critic_dimension

        dim = make_critic_dimension()
        verdict = dim.evaluate(
            "正确答案是 x=2，过程: 2x=4, x=2",
            context={"correct_answer": "x=2"},
        )
        # 应至少有一个 major issue
        assert any(i.severity == "major" for i in verdict.issues)
        assert verdict.passed is False

    def test_critic_dimension_safe_text_passes(self) -> None:
        from backend.app.services.pedagogical_safety import make_critic_dimension

        dim = make_critic_dimension()
        verdict = dim.evaluate(
            "你觉得第一步应该怎么做？试着想想题目里给了哪些已知量。",
            context={"bloom_level": "apply"},
        )
        assert verdict.passed is True
        assert verdict.score >= 0.6

    def test_critic_dimension_can_be_plugged_into_agent(self) -> None:
        """CriticAgent 接受自定义 dimensions list 时不应崩，验证可插拔。"""
        from backend.app.agents.critic_agent import CriticAgent
        from backend.app.services.pedagogical_safety import make_critic_dimension

        agent = CriticAgent(dimensions=[make_critic_dimension()])
        # 单维度 list 也应该能正常初始化
        assert agent.name == "critic"
