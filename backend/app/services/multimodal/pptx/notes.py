"""
Speaker Notes 自动生成器

每张幻灯片自动生成 3 段讲者备注:
    🎯 学习目标 — 基于 Bloom 层级 + 标题
    💬 讲解要点 — 基于 layout 类型给出讲解骨架
    ❓ 引导问题 — 设计互动提问帮助学生主动思考

学术依据:
- Roediger Retrieval Practice — 引导问题促进检索练习
- Vygotsky ZPD (1978) — 引导问题应在最近发展区
"""
from __future__ import annotations

from typing import Any

from backend.app.services.multimodal.pptx.spec import (
    BloomLevel,
    CheckpointSlide,
    CodeSlide,
    ComparisonSlide,
    ConceptSlide,
    CoverSlide,
    SlideSpec,
    WorkedExampleSlide,
)


# ================================================================
# Bloom → 学习目标动词
# ================================================================
BLOOM_VERBS = {
    BloomLevel.REMEMBER:   ["回忆", "识别", "列出"],
    BloomLevel.UNDERSTAND: ["解释", "总结", "推断"],
    BloomLevel.APPLY:      ["应用", "实现", "练习"],
    BloomLevel.ANALYZE:    ["分析", "比较", "辨别"],
    BloomLevel.EVALUATE:   ["评估", "权衡", "判断"],
    BloomLevel.CREATE:     ["设计", "构建", "创新"],
}


def _bloom_verb(level: BloomLevel) -> str:
    verbs = BLOOM_VERBS.get(level, ["理解"])
    return verbs[0]


# ================================================================
# Speaker Notes 主入口
# ================================================================
def generate_notes(slide: SlideSpec) -> str:
    """为一张幻灯片自动生成 3 段讲者备注"""
    if slide.notes and slide.notes.strip():
        return slide.notes

    if not slide.auto_notes:
        return ""

    objective = _objective(slide)
    points = _talking_points(slide)
    questions = _guiding_questions(slide)

    parts: list = []
    if objective:
        parts.append(f"🎯 学习目标\n{objective}")
    if points:
        parts.append(f"💬 讲解要点\n{points}")
    if questions:
        parts.append(f"❓ 引导问题\n{questions}")
    return "\n\n".join(parts)


# ================================================================
# 1. 学习目标
# ================================================================
def _objective(slide: SlideSpec) -> str:
    verb = _bloom_verb(slide.bloom)
    return f"学习者将能{verb}「{slide.title}」的核心内容。"


# ================================================================
# 2. 讲解要点 — 按 layout 类型给出讲解骨架
# ================================================================
def _talking_points(slide: SlideSpec) -> str:
    if isinstance(slide, CoverSlide):
        return (
            f"- 开场: 介绍课程「{slide.title}」\n"
            f"- 副标题强调本节关注 {slide.subtitle or '核心知识'}\n"
            f"- 营造学习动机, 提示与之前/之后内容的连接"
        )
    if isinstance(slide, ConceptSlide):
        body = f"- 关键定义: {slide.definition[:80]}"
        if slide.bullets:
            body += "\n- 要点逐条解释, 每点配一例"
        if slide.asset:
            body += "\n- 配图引导: 让学生先观察 5 秒再讲解"
        return body
    if isinstance(slide, ComparisonSlide):
        return (
            f"- 左侧重点: {slide.left_title}\n"
            f"- 右侧对照: {slide.right_title}\n"
            "- 引导学生指出至少 2 个差异 + 1 个共同点\n"
            + (f"- 给出对比结论: {slide.verdict}" if slide.verdict else "")
        )
    if isinstance(slide, WorkedExampleSlide):
        return (
            f"- 复述问题: {slide.problem[:60]}\n"
            "- 逐步推演: 强调每步为什么这样做\n"
            "- 反思: 常见错误 + 替代方案"
        )
    if isinstance(slide, CodeSlide):
        body = f"- 逐行讲解 {slide.language} 代码"
        if slide.annotations:
            body += "\n- 重点标注的关键行: " + "; ".join(
                slide.annotations[:3]
            )
        body += "\n- 提示学生在本地复现"
        return body
    if isinstance(slide, CheckpointSlide):
        return (
            f"- 给学生 30 秒独立思考: {slide.question[:60]}\n"
            "- 现场举手投票\n"
            f"- 公布正确选项 #{slide.correct_index + 1}, 解析其它选项错点"
        )
    return f"- 围绕「{slide.title}」展开核心内容讲解"


# ================================================================
# 3. 引导问题 (Socratic + ZPD)
# ================================================================
def _guiding_questions(slide: SlideSpec) -> str:
    if isinstance(slide, ConceptSlide):
        return (
            f"- 用你自己的话定义「{slide.title}」?\n"
            f"- 这个概念在哪些真实场景中出现?"
        )
    if isinstance(slide, ComparisonSlide):
        return (
            f"- 什么情境下选择 {slide.left_title}, 什么情境下选 "
            f"{slide.right_title}?"
        )
    if isinstance(slide, WorkedExampleSlide):
        return (
            "- 如果改变问题某个条件, 解法第几步会受影响?\n"
            "- 你能找出至少一个替代解吗?"
        )
    if isinstance(slide, CodeSlide):
        return (
            f"- 如果修改第一行的 {slide.language} 关键字, 程序会怎样?\n"
            "- 这段代码的时间复杂度是多少?"
        )
    if isinstance(slide, CheckpointSlide):
        return (
            "- 选错的同学先别看正确答案, 想一想错在哪一步?\n"
            "- 该题对应的现实场景例子?"
        )
    return f"- 关于「{slide.title}」, 你最想追问的一个问题是什么?"


# ================================================================
# 兼容旧 API
# ================================================================
def generate_notes_for_dict(slide_dict: Any) -> str:
    """供未走 Pydantic 的旧调用方使用"""
    title = (slide_dict.get("title", "") if hasattr(slide_dict, "get") else "")
    if not title:
        return ""
    return f"🎯 学习目标\n学习者将能理解「{title}」。"
