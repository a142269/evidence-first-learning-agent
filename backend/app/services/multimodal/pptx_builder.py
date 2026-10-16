"""
PPTX Builder - 向后兼容 Facade (P1-3 重构版)

旧 71 行 spaghetti 一行式代码已替换为 backend/app/services/multimodal/pptx/ 包。
本文件保留旧 API 名 (`PPTXBuilder`, `PPTXOutline`, `SlideContent`, `get_pptx_builder`)
作为兼容层, 内部转发到新的 SlideDeckBuilder。

新代码请直接使用:
    from backend.app.services.multimodal.pptx import (
        SlideDeckBuilder, SlideDeckSpec, CoverSlide, ConceptSlide, ...,
    )
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from backend.app.services.multimodal.pptx import (
    AgendaSlide,
    CheckpointSlide,
    CodeSlide,
    ComparisonSlide,
    ConceptSlide,
    CoverSlide,
    DeckMeta,
    SlideDeckBuilder,
    SlideDeckSpec,
    WorkedExampleSlide,
    get_slide_deck_builder,
)


logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path("data/artifacts/pptx")


# ================================================================
# 旧 dataclass 兼容
# ================================================================
@dataclass
class SlideContent:
    """旧 SlideContent 兼容"""
    title: str
    bullets: List[str] = field(default_factory=list)
    code_block: str = ""
    notes: str = ""
    layout_hint: str = ""


@dataclass
class PPTXOutline:
    """旧 PPTXOutline 兼容"""
    title: str
    subtitle: str = ""
    author: str = "triple U"
    slides: List[SlideContent] = field(default_factory=list)
    summary_points: List[str] = field(default_factory=list)
    review_questions: List[str] = field(default_factory=list)
    theme_name: str = "academic"
    template_path: str = ""


# ================================================================
# 适配器: 把旧 PPTXOutline 转换为新 SlideDeckSpec
# ================================================================
def outline_to_deck_spec(
    outline: PPTXOutline, session_id: str = "",
) -> SlideDeckSpec:
    """旧 → 新转换

    根据内容语义映射为 Concept / Comparison / WorkedExample / Code，
    在首尾补上 CoverSlide / AgendaSlide / 总结类幻灯片。
    """
    slides: List[Any] = []
    slides.append(CoverSlide(
        title=outline.title,
        subtitle=outline.subtitle,
        author=outline.author,
    ))
    # 目录不能留空：旧实现虽然创建了 AgendaSlide，但 items=[]，导出的 PPT
    # 第二页只剩一个标题，看起来像“简单卡片”。从实际内容标题生成可读目录，
    # 同时保留 12 项上限以避免目录溢出。
    agenda_items = [
        s.title.strip() for s in outline.slides
        if getattr(s, "title", "") and s.title.strip()
    ][:12]
    slides.append(AgendaSlide(title="目录", items=agenda_items))

    for s in outline.slides:
        title = s.title.strip() or "核心知识点"
        bullets = [str(item).strip() for item in s.bullets if str(item).strip()]
        hint = s.layout_hint.strip().lower()
        title_lower = title.lower()
        # 从 notes 中提取 Kimi 生成的叙事任务和主视觉意图
        notes_text = s.notes or ""
        narrative_job = ""
        visual_intent = ""
        for line in notes_text.split("\n"):
            line = line.strip()
            if line.startswith("叙事任务："):
                narrative_job = line[len("叙事任务："):].strip()
            elif line.startswith("主视觉："):
                visual_intent = line[len("主视觉："):].strip()

        if s.code_block.strip() or hint == "code":
            code = s.code_block.strip() or "# 代码示例请结合讲义补充"
            code = "\n".join(code.splitlines()[:30])
            slides.append(CodeSlide(
                title=title,
                language="python",
                code=code,
                annotations=bullets[:3],
                notes=s.notes,
            ))
            continue

        comparison_tokens = ("对比", "区别", "比较", "vs", "误区", "优缺点")
        if hint == "comparison" or any(token in title_lower for token in comparison_tokens):
            # 尝试在 bullets 中找到自然分割点（含「而」「相反」「相比之下」等）
            # 不能用单字“而”作为切分标记，否则会在中文词语中间拆开内容；
            # 只有明确的对照连接词才允许把要点分到左右两栏。
            split_markers = ("相反", "相比之下", "不同于", "区别在于", "vs")
            split_at = -1
            for marker in split_markers:
                for i, b in enumerate(bullets):
                    if marker in b.lower():
                        split_at = i + 1
                        break
                if split_at > 0:
                    break
            if split_at <= 0:
                split_at = max(1, (len(bullets) + 1) // 2)
            left_points = bullets[:split_at] or ["概念与适用条件"]
            right_points = bullets[split_at:] or ["差异与选择依据"]
            left_title, right_title = "核心做法", "边界与取舍"
            if "误区" in title:
                left_title, right_title = "常见误区", "正确理解"
            else:
                match = re.search(r"(.+?)\s*(?:vs\.?|与|和)\s*(.+)", title, re.I)
                if match:
                    left_title, right_title = match.group(1).strip(), match.group(2).strip()
            # verdict 优先使用 LLM 生成的 visual_intent，不再写死通用结论
            verdict = visual_intent or "根据任务目标、数据条件与评价指标做选择。"
            slides.append(ComparisonSlide(
                title=title,
                left_title=left_title[:60], left_points=left_points[:6],
                right_title=right_title[:60], right_points=right_points[:6],
                verdict=verdict[:200],
                notes=s.notes,
            ))
            continue

        example_tokens = ("案例", "例题", "推导", "流程", "实践", "实战", "演算")
        if hint in {"worked_example", "example"} or any(token in title_lower for token in example_tokens):
            # 用标题作为问题，所有 bullets 作为解题步骤（不再把第一条当 problem）
            problem = title
            steps = list(bullets)
            if len(steps) < 2:
                steps = ["明确输入、目标与约束", "按步骤完成并检查结果"]
            while len(steps) < 2:
                steps.append("核对结果并总结可迁移的方法")
            # reflection 优先使用 LLM 生成的 narrative_job
            reflection = narrative_job or "回看每一步的依据，并检查常见边界条件。"
            slides.append(WorkedExampleSlide(
                title=title,
                problem=problem,
                solution_steps=steps[:6],
                reflection=reflection[:200],
                notes=s.notes,
            ))
            continue

        # ConceptSlide：第一条作为定义，其余作为要点；保留全部 bullets 内容
        definition = bullets[0] if bullets else "围绕本节目标建立核心概念框架。"
        remaining = bullets[1:7] if len(bullets) > 1 else []
        slides.append(ConceptSlide(
            title=title,
            definition=definition,
            bullets=remaining,
            notes=s.notes,
        ))

    if outline.summary_points:
        slides.append(ConceptSlide(
            title="课程总结",
            definition="本节关键要点回顾",
            bullets=outline.summary_points[:6],
        ))
    if outline.review_questions:
        slides.append(CheckpointSlide(
            title="学习自检",
            question=outline.review_questions[0],
            options=[
                "我能独立作答，并说明每一步依据",
                "我能给出结论，但推理依据还不完整",
                "我需要回看概念或案例后再作答",
            ],
            correct_index=0,
            hint="先口述推理，再核对公式、张量形状或代码输出。",
        ))
        if len(outline.review_questions) > 1:
            slides.append(ConceptSlide(
                title="迁移思考",
                definition="把本节方法迁移到新的任务场景。",
                bullets=outline.review_questions[1:6],
            ))

    return SlideDeckSpec(
        meta=DeckMeta(
            title=outline.title,
            subtitle=outline.subtitle,
            author=outline.author,
            session_id=session_id,
            theme_name=outline.theme_name,
        ),
        slides=slides,
    )


# ================================================================
# 旧 PPTXBuilder facade
# ================================================================
class PPTXBuilder:
    """旧 PPTXBuilder API 兼容

    内部转发到 SlideDeckBuilder, 但保持原签名 `build(outline, rid) -> dict`。
    """

    def __init__(self) -> None:
        self._inner: SlideDeckBuilder = get_slide_deck_builder()

    def build(self, outline: PPTXOutline, rid: str) -> Dict[str, Any]:
        """旧签名: 返回 {filepath, slides_count, json_fallback}"""
        try:
            deck = outline_to_deck_spec(outline)
            result = self._inner.build(
                deck, rid,
                template_path=outline.template_path or None,
            )
            return {
                "filepath": result.filepath,
                "slides_count": result.slides_count,
                "json_fallback": result.json_fallback,
                "lint_warnings": result.lint_warnings,
                "duration_ms": result.duration_ms,
            }
        except Exception as exc:
            logger.exception(f"[PPTXBuilder] facade build failed: {exc}")
            return {
                "filepath": "",
                "slides_count": 0,
                "json_fallback": json.dumps({
                    "title": outline.title, "error": str(exc),
                }),
            }


# ================================================================
# 单例兼容
# ================================================================
_builder: PPTXBuilder | None = None


def get_pptx_builder() -> PPTXBuilder:
    global _builder
    if _builder is None:
        _builder = PPTXBuilder()
    return _builder
