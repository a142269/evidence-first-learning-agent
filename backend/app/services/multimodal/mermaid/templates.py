"""
5 种 diagram → Mermaid 代码生成器

每种 spec 一个独立 builder, 严格按 Mermaid 8+ 语法规范生成。

参考:
- Mermaid.js 官方语法 (v10+)
- mindmap 在 v9.2 才稳定支持
"""
from __future__ import annotations

import re
from typing import Any, List

from backend.app.services.multimodal.mermaid.spec import (
    ClassDiagramSpec,
    ClassEntity,
    ClassMember,
    ClassRelation,
    DiagramSpec,
    FlowEdge,
    FlowNode,
    FlowchartSpec,
    GraphEdge,
    GraphNode,
    GraphSpec,
    MindmapNode,
    MindmapSpec,
    SequenceSpec,
)


# ================================================================
# 文本清洗 — Mermaid 不接受某些特殊字符
# ================================================================
_LABEL_FORBIDDEN = re.compile(r'[`"\\\n\r]')
_MINDMAP_TRANSLATION = str.maketrans({
    "(": "（", ")": "）", "[": "【", "]": "】",
    "{": "〔", "}": "〕", "<": "〈", ">": "〉",
    ":": "：", ";": "；", "#": "＃", "&": "＆",
})


def _safe_label(text: str, max_len: int = 60) -> str:
    """转义 Mermaid 标签 — 移除非法字符 + 限长"""
    cleaned = _LABEL_FORBIDDEN.sub(" ", text or "")
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len - 1] + "…"
    return cleaned


def _safe_mindmap_label(text: str, max_len: int = 60) -> str:
    """Mindmap 的裸文本节点不能携带 Mermaid 形状/样式控制字符。"""
    cleaned = _safe_label(text, max_len=max_len).translate(_MINDMAP_TRANSLATION)
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned)
    cleaned = cleaned.replace(":::", "：").strip()
    return cleaned or "未命名节点"


# ================================================================
# 1. Mindmap
# ================================================================
def _mindmap_node_to_lines(
    node: MindmapNode, depth: int, *, is_root: bool = False,
) -> List[str]:
    indent = "  " * depth
    label = _safe_mindmap_label(node.text)
    if node.icon:
        label = f"{node.icon} {label}"

    if is_root:
        line = f"{indent}root(({label}))"
    else:
        line = f"{indent}{label}"

    out = [line]
    for child in node.children[:12]:
        out.extend(_mindmap_node_to_lines(child, depth + 1))
    return out


def build_mindmap(spec: MindmapSpec) -> str:
    """构造 Mermaid mindmap 代码

    输出格式:
        mindmap
          root((中心主题))
            子节点1
              叶子A
            子节点2
    """
    lines = ["mindmap"]
    lines.extend(_mindmap_node_to_lines(spec.root, depth=1, is_root=True))
    return "\n".join(lines)


# ================================================================
# 2. Flowchart
# ================================================================
_SHAPE_TEMPLATES = {
    "rect":    "{id}[{label}]",
    "round":   "{id}({label})",
    "diamond": "{id}{{{label}}}",
    "circle":  "{id}(({label}))",
    "stadium": "{id}([{label}])",
}


def _flow_node_decl(node: FlowNode) -> str:
    tpl = _SHAPE_TEMPLATES.get(node.shape, _SHAPE_TEMPLATES["rect"])
    return tpl.format(id=node.id, label=_safe_label(node.label))


def _flow_edge_decl(edge: FlowEdge) -> str:
    if edge.style == "dashed":
        arrow = "-..->"
    elif edge.style == "thick":
        arrow = "==>"
    else:
        arrow = "-->"

    if edge.label:
        return f"{edge.source} {arrow}|{_safe_label(edge.label, 30)}| {edge.target}"
    return f"{edge.source} {arrow} {edge.target}"


def build_flowchart(spec: FlowchartSpec) -> str:
    """构造 Mermaid flowchart 代码"""
    lines = [f"flowchart {spec.direction}"]
    if spec.title:
        lines.append(f"  %% {_safe_label(spec.title)}")
    for n in spec.nodes:
        lines.append(f"  {_flow_node_decl(n)}")
    for e in spec.edges:
        lines.append(f"  {_flow_edge_decl(e)}")
    return "\n".join(lines)


# ================================================================
# 3. Sequence
# ================================================================
_SEQ_ARROW = {
    "sync":  "->>",
    "async": "->>",
    "reply": "-->>",
}


def build_sequence(spec: SequenceSpec) -> str:
    """构造 Mermaid sequenceDiagram 代码"""
    lines = ["sequenceDiagram"]
    if spec.title:
        lines.append(f"  %% {_safe_label(spec.title)}")
    for actor in spec.actors:
        lines.append(f"  participant {_safe_label(actor, 30)}")
    for msg in spec.messages:
        arrow = _SEQ_ARROW.get(msg.arrow, "->>")
        lines.append(
            f"  {_safe_label(msg.sender, 30)} {arrow} "
            f"{_safe_label(msg.receiver, 30)}: {_safe_label(msg.text)}"
        )
    return "\n".join(lines)


# ================================================================
# 4. Class Diagram
# ================================================================
_VIS_PREFIX = {"public": "+", "private": "-", "protected": "#"}


def _class_member_line(m: ClassMember) -> str:
    prefix = _VIS_PREFIX.get(m.visibility, "+")
    if m.kind == "method":
        return f"{prefix}{m.name}() {m.type_hint}".strip()
    return f"{prefix}{m.name} {m.type_hint}".strip()


def _class_decl(c: ClassEntity) -> List[str]:
    lines = [f"  class {c.name} {{"]
    for m in c.members[:15]:
        lines.append(f"    {_class_member_line(m)}")
    lines.append("  }")
    return lines


_REL_ARROW = {
    "inherit":     "<|--",
    "implement":   "<|..",
    "composition": "*--",
    "aggregation": "o--",
    "association": "--",
}


def _class_relation_line(r: ClassRelation) -> str:
    arrow = _REL_ARROW.get(r.relation, "--")
    label = f" : {_safe_label(r.label, 30)}" if r.label else ""
    return f"  {r.source} {arrow} {r.target}{label}"


def build_class_diagram(spec: ClassDiagramSpec) -> str:
    """构造 Mermaid classDiagram 代码"""
    lines = ["classDiagram"]
    if spec.title:
        lines.append(f"  %% {_safe_label(spec.title)}")
    for c in spec.classes:
        lines.extend(_class_decl(c))
    for r in spec.relations:
        lines.append(_class_relation_line(r))
    return "\n".join(lines)


# ================================================================
# 5. Graph (知识图谱)
# ================================================================
def build_graph(spec: GraphSpec) -> str:
    """构造 Mermaid graph (知识图谱风格)

    用 flowchart LR 实现, 节点按 group 着色。
    """
    lines = ["flowchart LR"]
    if spec.title:
        lines.append(f"  %% {_safe_label(spec.title)}")
    # 节点声明
    for n in spec.nodes:
        lines.append(
            f"  {n.id}([{_safe_label(n.label)}])"
        )
    # 边
    arrow = "-->" if spec.directed else "---"
    for e in spec.edges:
        if e.label:
            lines.append(
                f"  {e.source} {arrow}|{_safe_label(e.label, 30)}| "
                f"{e.target}"
            )
        else:
            lines.append(f"  {e.source} {arrow} {e.target}")
    # 按 group 着色 (用 Mermaid classDef)
    groups = {n.group for n in spec.nodes if n.group}
    palette = [
        "#1E40AF", "#0EA5E9", "#DC2626", "#16A34A",
        "#9333EA", "#F59E0B", "#EC4899",
    ]
    for i, g in enumerate(sorted(groups)):
        color = palette[i % len(palette)]
        lines.append(
            f"  classDef g{i} fill:{color},color:#fff,stroke:#0f172a"
        )
        ids = [n.id for n in spec.nodes if n.group == g]
        if ids:
            lines.append(f"  class {','.join(ids)} g{i}")
    return "\n".join(lines)


# ================================================================
# 统一 dispatcher
# ================================================================
def build_mermaid_code(spec: DiagramSpec) -> str:
    if isinstance(spec, MindmapSpec):
        return build_mindmap(spec)
    if isinstance(spec, FlowchartSpec):
        return build_flowchart(spec)
    if isinstance(spec, SequenceSpec):
        return build_sequence(spec)
    if isinstance(spec, ClassDiagramSpec):
        return build_class_diagram(spec)
    if isinstance(spec, GraphSpec):
        return build_graph(spec)
    msg = f"unsupported spec kind: {type(spec).__name__}"
    raise ValueError(msg)
