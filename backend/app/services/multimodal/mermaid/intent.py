"""
DiagramIntent - 从自然语言推断目标 diagram 类型

赛题场景: 用户说"给我画一个 CNN 的思维导图" / "梯度下降的流程" / "MVC 类关系"
→ 自动选 mindmap / flowchart / class

降级: 兜底用 mindmap (最通用)
"""
from __future__ import annotations

from typing import Dict, List, Tuple


# ================================================================
# 关键词词典 — 中文 + 英文混合, 覆盖学生常用表达
# ================================================================
_INTENT_KEYWORDS: Dict[str, List[str]] = {
    "mindmap": [
        "思维导图", "脑图", "知识地图", "概念图", "mindmap",
        "mind map", "概览", "结构图",
    ],
    "flowchart": [
        "流程", "流程图", "算法图", "步骤", "决策树", "决策图",
        "flowchart", "flow", "pipeline", "工作流",
    ],
    "sequence": [
        "时序图", "交互图", "时序", "调用链", "通信",
        "sequence", "时间线",
    ],
    "class": [
        "类图", "类关系", "继承", "面向对象", "uml",
        "class diagram", "class relation",
    ],
    "graph": [
        "知识图谱", "实体关系", "网络", "图结构", "拓扑",
        "graph", "knowledge graph", "kg",
    ],
}


def detect_intent(text: str) -> str:
    """识别用户想要的 diagram 类型

    Returns:
        kind ∈ {"mindmap", "flowchart", "sequence", "class", "graph"}
        兜底: "mindmap" (赛题最常见)
    """
    if not text:
        return "mindmap"
    s = text.lower()
    # 命中越具体的越优先 (按词条数倒序遍历)
    matches: List[Tuple[str, int]] = []
    for kind, keywords in _INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw.lower() in s)
        if hits > 0:
            matches.append((kind, hits))
    if not matches:
        return "mindmap"
    matches.sort(key=lambda x: (-x[1], len(x[0])))
    return matches[0][0]


def list_supported_kinds() -> List[str]:
    return list(_INTENT_KEYWORDS.keys())
