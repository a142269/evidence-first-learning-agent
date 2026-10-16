"""
SlideDeckSpec - 声明式 Pydantic 幻灯片大纲 (P1-3)

设计原则:
- 每种 layout 是独立的 SlideSpec 子类 (discriminated union)
- LLM 输出 JSON → Pydantic 校验 → 任何不合规的 layout 在解析时即报错
- 替代原 PPTXOutline dataclass (允许任意 bullets 列表, 缺乏类型约束)

学术依据 (layout 选型):
- Mayer Multimedia Learning (2014) - Contiguity / Coherence / Signaling
- Sweller Cognitive Load Theory (1988) - Worked Example Effect
- Roediger & Karpicke (2006) - Testing Effect / Retrieval Practice
- Bloom Taxonomy (Anderson & Krathwohl 2001)
"""
from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ================================================================
# 通用类型
# ================================================================
class BloomLevel(str, Enum):
    """Anderson & Krathwohl (2001) 修订版 Bloom 六层认知"""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class Asset(BaseModel):
    """通用资源 — SVG / Mermaid / 图片"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["svg", "mermaid", "image"] = "image"
    source: str = Field(..., description="SVG 文本 / Mermaid 代码 / 图片路径")
    alt_text: str = Field("", description="无障碍替代文本")
    caption: str = Field("", description="图注")
    width_ratio: float = Field(1.0, ge=0.1, le=1.0)


class SlideBase(BaseModel):
    """所有幻灯片共享字段"""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=120)
    notes: str = Field("", description="讲者备注 (留空则自动生成)")
    bloom: BloomLevel = BloomLevel.UNDERSTAND
    knowledge_point: str = Field("", description="对应知识点 ID 或名称")
    auto_notes: bool = Field(True, description="若 notes 为空, 是否自动生成")


# ================================================================
# 7 种幻灯片 (discriminated union)
# ================================================================
class CoverSlide(SlideBase):
    """1. 封面 — 课程开篇

    设计要点:
    - 大标题 (Pt 44+)
    - 副标题说明范围
    - 讲者 / 章节 信息
    """
    layout: Literal["cover"] = "cover"
    subtitle: str = ""
    author: str = "triple U"
    chapter: str = ""


class AgendaSlide(SlideBase):
    """2. 目录 — 自动从其它幻灯片提取

    若 items 为空则由 Builder 自动填充。
    """
    layout: Literal["agenda"] = "agenda"
    items: List[str] = Field(default_factory=list)


class ConceptSlide(SlideBase):
    """3. 概念定义 — 标题 + 关键定义 + 配图

    Mayer Contiguity Principle: 解释文字与配图相邻摆放。
    """
    layout: Literal["concept"] = "concept"
    definition: str = Field(..., min_length=1, max_length=400)
    bullets: List[str] = Field(default_factory=list, max_length=6)
    asset: Optional[Asset] = None


class ComparisonSlide(SlideBase):
    """4. 对比 — 左右两栏

    Mayer Multimedia Principle: 同时展示两个对象便于差异识别。
    适用: SGD vs Adam / 监督 vs 无监督 / 编译型 vs 解释型 ...
    """
    layout: Literal["comparison"] = "comparison"
    left_title: str = Field(..., max_length=60)
    left_points: List[str] = Field(..., min_length=1, max_length=6)
    right_title: str = Field(..., max_length=60)
    right_points: List[str] = Field(..., min_length=1, max_length=6)
    verdict: str = Field("", description="对比结论 (可选)")


class WorkedExampleSlide(SlideBase):
    """5. 范例 — 问题 → 解 → 反思

    Sweller Worked Example Effect:
    完整展示求解过程, 降低新手认知负荷, 显著优于 problem-solving 法。
    """
    layout: Literal["worked_example"] = "worked_example"
    problem: str = Field(..., min_length=1)
    solution_steps: List[str] = Field(..., min_length=2, max_length=6)
    reflection: str = Field("", description="为什么这样做 + 常见错误")


class CodeSlide(SlideBase):
    """6. 代码 — 含行号 + 语言 + 关键解说

    实现注意: python-pptx 不原生支持语法高亮, 采用 monospace + 颜色注释模拟。
    """
    layout: Literal["code"] = "code"
    language: str = Field("python", description="编程语言")
    code: str = Field(..., min_length=1)
    annotations: List[str] = Field(
        default_factory=list,
        description="代码下方的关键解说点",
        max_length=5,
    )

    @field_validator("code")
    @classmethod
    def _code_length(cls, v: str) -> str:
        if len(v.splitlines()) > 30:
            msg = f"code too long ({len(v.splitlines())} lines, max 30)"
            raise ValueError(msg)
        return v


class CheckpointSlide(SlideBase):
    """7. 理解检查 — 嵌入选择题

    Roediger & Karpicke (2006) Testing Effect:
    主动检索比被动复习显著提升长期记忆保持率。
    """
    layout: Literal["checkpoint"] = "checkpoint"
    question: str = Field(..., min_length=1)
    options: List[str] = Field(..., min_length=2, max_length=5)
    correct_index: int = Field(..., ge=0)
    hint: str = Field("", description="提示 (可选)")

    @field_validator("correct_index")
    @classmethod
    def _correct_index_in_range(cls, v: int, info) -> int:
        opts = info.data.get("options") or []
        if opts and v >= len(opts):
            msg = f"correct_index {v} >= options length {len(opts)}"
            raise ValueError(msg)
        return v


# 后向兼容: SummaryReview slides 复用 AgendaSlide + ConceptSlide
SlideSpec = Union[
    CoverSlide,
    AgendaSlide,
    ConceptSlide,
    ComparisonSlide,
    WorkedExampleSlide,
    CodeSlide,
    CheckpointSlide,
]


# ================================================================
# 完整 Deck
# ================================================================
class DeckMeta(BaseModel):
    """整份幻灯片元数据"""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1)
    subtitle: str = ""
    author: str = "triple U"
    course: str = "artificial_intelligence"
    audience_level: BloomLevel = BloomLevel.UNDERSTAND
    theme_name: str = Field("academic", description="academic / modern / high_contrast")
    session_id: str = Field("", description="用于 QR 深链回到对话")


class SlideDeckSpec(BaseModel):
    """声明式幻灯片大纲"""
    model_config = ConfigDict(extra="forbid")

    meta: DeckMeta
    slides: List[SlideSpec] = Field(
        ..., min_length=1, max_length=60,
        description="discriminated union, 由 layout 字段决定具体类型",
    )

    @field_validator("slides")
    @classmethod
    def _validate_slides(cls, v: List[SlideSpec]) -> List[SlideSpec]:
        if not v:
            msg = "deck must contain at least one slide"
            raise ValueError(msg)
        return v

    def layout_counts(self) -> dict:
        """统计各 layout 数量 (供 lint 用)"""
        counts: dict = {}
        for s in self.slides:
            counts[s.layout] = counts.get(s.layout, 0) + 1
        return counts


# ================================================================
# 构建结果
# ================================================================
class SlideRenderResult(BaseModel):
    """单张幻灯片渲染结果"""
    model_config = ConfigDict(extra="allow")

    slide_index: int
    layout: str
    title: str
    rendered: bool
    warnings: List[str] = Field(default_factory=list)
    asset_method: str = Field("", description="svg/mermaid 实际渲染方式")


class DeckBuildResult(BaseModel):
    """完整 PPTX 构建结果"""
    model_config = ConfigDict(extra="allow")

    filepath: str = ""
    slides_count: int = 0
    theme_name: str = "academic"
    slide_results: List[SlideRenderResult] = Field(default_factory=list)
    lint_warnings: List[str] = Field(default_factory=list)
    lint_errors: List[str] = Field(default_factory=list)
    json_fallback: Optional[str] = None
    duration_ms: float = 0.0
