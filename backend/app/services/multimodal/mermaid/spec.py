"""
MermaidSpec - 5 种图的声明式 Pydantic 模型

设计目标:
- LLM 输出结构化 JSON, 我们生成 Mermaid 代码 (避免 LLM 直接生成坏语法)
- 5 种 spec 覆盖赛题要求的所有图类:
    1. MindmapSpec       思维导图 (赛题"知识点思维导图")
    2. FlowchartSpec     流程图  (赛题"算法流程")
    3. SequenceSpec      时序图  (赛题"系统交互")
    4. ClassDiagramSpec  类图    (面向对象课程)
    5. GraphSpec         知识图谱 (GraphRAG 可视化)
"""
from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ================================================================
# 共享类型
# ================================================================
class DiagramTheme(BaseModel):
    """Mermaid 主题配置 (复用 pptx Theme 体系)"""
    model_config = ConfigDict(extra="forbid")

    name: str = Field("academic", description="academic / modern / high_contrast")
    primary: str = Field("#1E40AF")
    secondary: str = Field("#0EA5E9")
    accent: str = Field("#DC2626")
    text: str = Field("#0F172A")
    bg: str = Field("#FFFFFF")


# ================================================================
# 1. Mindmap (赛题必备 - 思维导图)
# ================================================================
class MindmapNode(BaseModel):
    """思维导图节点 (递归结构)"""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=80)
    children: List["MindmapNode"] = Field(default_factory=list)
    icon: str = Field("", description="可选 emoji, e.g. 🎯")

    @field_validator("children")
    @classmethod
    def _max_depth_children(cls, v: list) -> list:
        if len(v) > 12:
            msg = f"too many children ({len(v)} > 12)"
            raise ValueError(msg)
        return v


MindmapNode.model_rebuild()


class MindmapSpec(BaseModel):
    """思维导图 — 中心主题 + 多层分支"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["mindmap"] = "mindmap"
    root: MindmapNode
    theme: DiagramTheme = Field(default_factory=DiagramTheme)


# ================================================================
# 2. Flowchart (算法/流程)
# ================================================================
class FlowNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    label: str = Field(..., min_length=1, max_length=80)
    shape: Literal[
        "rect", "round", "diamond", "circle", "stadium",
    ] = "rect"


class FlowEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str = Field("", description="边标签 (可选)")
    style: Literal["solid", "dashed", "thick"] = "solid"


class FlowchartSpec(BaseModel):
    """流程图 / 算法图"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["flowchart"] = "flowchart"
    direction: Literal["TD", "LR", "BT", "RL"] = "TD"
    nodes: List[FlowNode] = Field(..., min_length=1, max_length=40)
    edges: List[FlowEdge] = Field(default_factory=list, max_length=80)
    title: str = ""
    theme: DiagramTheme = Field(default_factory=DiagramTheme)

    @field_validator("edges")
    @classmethod
    def _edges_refer_to_nodes(cls, v: list, info) -> list:
        nodes = info.data.get("nodes") or []
        node_ids = {n.id for n in nodes}
        for e in v:
            if e.source not in node_ids or e.target not in node_ids:
                msg = (
                    f"edge {e.source}→{e.target} references unknown node"
                )
                raise ValueError(msg)
        return v


# ================================================================
# 3. Sequence (系统交互)
# ================================================================
class SequenceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender: str
    receiver: str
    text: str = Field(..., max_length=100)
    arrow: Literal["sync", "async", "reply"] = "sync"


class SequenceSpec(BaseModel):
    """时序图 — 多 actor 交互"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["sequence"] = "sequence"
    actors: List[str] = Field(..., min_length=2, max_length=8)
    messages: List[SequenceMessage] = Field(..., min_length=1, max_length=30)
    title: str = ""
    theme: DiagramTheme = Field(default_factory=DiagramTheme)


# ================================================================
# 4. Class Diagram (面向对象课程)
# ================================================================
class ClassMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type_hint: str = ""
    kind: Literal["attribute", "method"] = "attribute"
    visibility: Literal["public", "private", "protected"] = "public"


class ClassEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., pattern=r"^[A-Z][A-Za-z0-9_]*$")
    members: List[ClassMember] = Field(default_factory=list, max_length=15)


class ClassRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    relation: Literal[
        "inherit", "implement", "composition", "aggregation", "association",
    ] = "association"
    label: str = ""


class ClassDiagramSpec(BaseModel):
    """类图 — 面向对象关系"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["class"] = "class"
    classes: List[ClassEntity] = Field(..., min_length=1, max_length=20)
    relations: List[ClassRelation] = Field(default_factory=list, max_length=40)
    title: str = ""
    theme: DiagramTheme = Field(default_factory=DiagramTheme)


# ================================================================
# 5. Graph (知识图谱 - GraphRAG 可视化)
# ================================================================
class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str = Field(..., max_length=60)
    weight: float = Field(1.0, ge=0.0)
    group: str = Field("", description="社区/类别 id")


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    target: str
    label: str = ""
    weight: float = Field(1.0, ge=0.0)


class GraphSpec(BaseModel):
    """无向/有向图 — 知识图谱可视化"""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["graph"] = "graph"
    directed: bool = False
    nodes: List[GraphNode] = Field(..., min_length=1, max_length=50)
    edges: List[GraphEdge] = Field(default_factory=list, max_length=120)
    title: str = ""
    theme: DiagramTheme = Field(default_factory=DiagramTheme)


# ================================================================
# Union 类型
# ================================================================
DiagramSpec = Union[
    MindmapSpec,
    FlowchartSpec,
    SequenceSpec,
    ClassDiagramSpec,
    GraphSpec,
]


# ================================================================
# 渲染结果
# ================================================================
class MermaidResult(BaseModel):
    """统一渲染输出"""
    model_config = ConfigDict(extra="allow")

    kind: str
    mermaid_code: str
    png_path: Optional[str] = None
    data_uri: Optional[str] = None
    method: str = "placeholder"
    width_px: int = 0
    height_px: int = 0
    validation_passed: bool = True
    warnings: List[str] = Field(default_factory=list)
    error: str = ""
    duration_ms: float = 0.0
