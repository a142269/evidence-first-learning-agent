"""
Manim Scene DSL — 教学动画领域专用语言 (Phase 3 Innovation 2)

核心设计:
    LLM 输出 JSON DSL (安全) → DSLCompiler 生成 Manim Python (受控) → Manim 渲染视频

安全保证:
    1. LLM 只输出结构化 JSON，不写 Python 代码 — 杜绝代码注入
    2. DSLCompiler 只生成白名单内的 Manim API 调用 — 杜绝任意代码执行
    3. ManimSafetyValidator AST 终检 — 最后防线

DSL 设计参考:
    - Manim Community Edition 场景结构 (Scene → Mobject → Animation)
    - Adobe After Effects 图层模型 (layer-based composition)

学术依据:
    - 3Blue1Brown 数学动画教学法
    - Cognitive Theory of Multimedia Learning (Mayer 2005)
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationInfo, field_validator


# ================================================================
# DSL 枚举
# ================================================================
class ElementType(str, Enum):
    """可渲染元素类型"""
    TEXT = "text"
    FORMULA = "formula"       # LaTeX
    CODE = "code"
    SHAPE = "shape"           # rect/circle/arrow
    AXES = "axes"             # 坐标轴
    GRAPH = "graph"           # 函数图
    IMAGE = "image"
    BULLET_LIST = "bullet_list"


class AnimationType(str, Enum):
    """动画类型"""
    WRITE = "write"           # 逐字写出
    FADE_IN = "fade_in"       # 淡入
    FADE_OUT = "fade_out"     # 淡出
    TRANSFORM = "transform"   # 变形
    MOVE_TO = "move_to"       # 移动到
    SCALE = "scale"           # 放缩
    ROTATE = "rotate"         # 旋转
    HIGHLIGHT = "highlight"   # 高亮
    CREATE = "create"         # 创建图形
    INDICATE = "indicate"     # 指示（箭头指向）


class Position(str, Enum):
    """元素位置"""
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    UP = "up"
    DOWN = "down"


class Color(str, Enum):
    """预定义颜色 (Manim 兼容)"""
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    RED = "#FC6255"
    ORANGE = "#FF8C00"
    YELLOW = "#FFD700"
    GREEN = "#83C167"
    BLUE = "#58C4DD"
    PURPLE = "#9B59B6"
    PINK = "#E91E63"
    TEAL = "#00BCD4"
    GRAY = "#888888"
    LIGHT_GRAY = "#CCCCCC"
    DARK_BLUE = "#1A237E"
    GOLD = "#FFC107"


# ================================================================
# DSL 元素模型
# ================================================================
class AnimationStep(BaseModel):
    """单步动画指令"""
    type: AnimationType
    target_id: str = ""                # 目标元素 ID，空=全部
    duration: float = 1.0              # 持续时间 (秒)
    delay: float = 0.0                 # 延迟 (秒)
    params: Dict[str, Any] = Field(default_factory=dict)  # 额外参数

    @field_validator("duration")
    @classmethod
    def duration_range(cls, v: float) -> float:
        if v < 0.1 or v > 10.0:
            raise ValueError(f"duration must be 0.1-10.0, got {v}")
        return v


class ElementStyle(BaseModel):
    """元素样式"""
    color: str = "#FFFFFF"             # 文字/填充颜色
    background_color: str = ""         # 背景色
    font_size: int = 36
    font_family: str = "sans-serif"
    stroke_width: float = 1.0
    fill_opacity: float = 1.0
    stroke_color: str = ""


class SceneElement(BaseModel):
    """场景中的一个可渲染元素"""
    id: str                            # 唯一标识 (如 "title", "equation_1")
    type: ElementType
    content: str = ""                  # 文本/公式/代码内容
    position: Position = Position.CENTER
    style: ElementStyle = Field(default_factory=ElementStyle)
    width: float = 6.0                 # 相对宽度
    height: float = 1.0                # 相对高度
    shift_x: float = 0.0               # X 偏移
    shift_y: float = 0.0               # Y 偏移
    layer: int = 0                     # 图层顺序 (0=最底层)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def content_not_empty_for_text_types(
        cls, v: str, info: ValidationInfo,
    ) -> str:
        t = info.data.get("type")
        if t in (ElementType.TEXT, ElementType.FORMULA, ElementType.CODE):
            if not v or not v.strip():
                raise ValueError(f"content required for {t} element")
        return v


class Scene(BaseModel):
    """一个动画场景 (对应一个 Manim Scene)"""
    scene_id: str
    title: str = ""
    elements: List[SceneElement] = Field(default_factory=list, max_length=20)
    animations: List[AnimationStep] = Field(default_factory=list, max_length=30)
    duration_seconds: float = 5.0
    background_color: str = "#1A1A2E"  # 深色背景 (适合教学)
    camera_frame_width: float = 14.0
    camera_frame_height: float = 8.0


# ================================================================
# DSL 顶层模型
# ================================================================
class ManimDSLSpec(BaseModel):
    """完整的 Manim 教学动画规格

    这是 LLM 输出的唯一格式。LLM 不写 Python，只填此结构。
    """
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    topic: str = Field(..., min_length=1, max_length=100)
    concept_tags: List[str] = Field(default_factory=list, max_length=8)

    # 视觉效果
    color_scheme: str = "dark"         # "dark" / "light" / "colorful"
    animation_speed: float = 1.0       # 全局速度因子 (0.5-2.0)

    # 场景序列
    scenes: List[Scene] = Field(..., min_length=1, max_length=10)

    @field_validator("animation_speed")
    @classmethod
    def speed_range(cls, v: float) -> float:
        if v < 0.3 or v > 3.0:
            raise ValueError(f"animation_speed must be 0.3-3.0, got {v}")
        return v

    def total_duration(self) -> float:
        return sum(s.duration_seconds for s in self.scenes)

    def element_count(self) -> int:
        return sum(len(s.elements) for s in self.scenes)

    def animation_count(self) -> int:
        return sum(len(s.animations) for s in self.scenes)
