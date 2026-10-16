"""
Bloom Taxonomy 6-level classifier - Anderson & Krathwohl 2001

Keyword rules (primary) + LLM (optional). Now with 6x3 sub-levels + knowledge dimension.
"""
from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BLOOM_LEVELS = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
BLOOM_LABELS = {"remember": "记忆", "understand": "理解", "apply": "应用",
                "analyze": "分析", "evaluate": "评价", "create": "创造"}
BLOOM_COLORS = {"remember": "#94a3b8", "understand": "#60a5fa", "apply": "#34d399",
                "analyze": "#fbbf24", "evaluate": "#fb923c", "create": "#f87171"}

_BLOOM_KEYWORDS: Dict[str, List[str]] = {
    "remember": ["定义", "列举", "复述", "识别", "回忆", "描述", "什么是", "define", "list", "recall"],
    "understand": ["解释", "说明", "归纳", "概述", "比较", "区别", "举例", "explain", "summarize"],
    "apply": ["应用", "使用", "计算", "实现", "操作", "执行", "解决", "apply", "implement", "solve"],
    "analyze": ["分析", "分解", "比较", "对比", "检查", "归类", "区别", "analyze", "categorize"],
    "evaluate": ["评价", "评估", "判断", "论证", "批评", "推荐", "evaluate", "assess", "judge"],
    "create": ["设计", "构建", "开发", "创建", "规划", "生成", "创新", "design", "create", "develop"],
}

SUB_LEVELS = {
    "remember": ["recognizing", "recalling"],
    "understand": ["interpreting", "exemplifying", "classifying", "summarizing", "inferring", "comparing", "explaining"],
    "apply": ["executing", "implementing"],
    "analyze": ["differentiating", "organizing", "attributing"],
    "evaluate": ["checking", "critiquing"],
    "create": ["generating", "planning", "producing"],
}

KNOWLEDGE_DIMS = {"factual": "事实性", "conceptual": "概念性", "procedural": "程序性", "metacognitive": "元认知"}


class BloomTaxonomy:
    def __init__(self, use_llm: bool = False, llm_client=None):
        self.use_llm = use_llm
        self.llm = llm_client

    def classify(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        scores = {}
        for level in BLOOM_LEVELS:
            kws = _BLOOM_KEYWORDS[level]
            count = sum(1 for kw in kws if kw in text_lower)
            scores[level] = min(count / max(len(kws), 1), 1.0)
        best = max(scores, key=scores.get)
        return {"level": best, "label": BLOOM_LABELS[best],
                "scores": {lvl: round(s, 4) for lvl, s in scores.items()},
                "method": "keyword", "confidence": round(scores[best], 4)}

    def classify_detailed(self, text: str) -> Dict[str, Any]:
        result = self.classify(text)
        level = result["level"]
        sub = SUB_LEVELS[level][0]
        code_indicators = sum(1 for t in ["代码", "code", "实现", "算法"] if t in text.lower())
        concept_indicators = sum(1 for t in ["原理", "概念", "理论", "分类"] if t in text.lower())
        kd = "procedural" if code_indicators > concept_indicators else (
            "conceptual" if concept_indicators > 0 else "factual")
        return {**result, "sub_level": sub, "knowledge_dimension": kd,
                "knowledge_label": KNOWLEDGE_DIMS.get(kd, "")}

    def classify_question(self, question_text: str) -> str:
        return self.classify(question_text)["level"]

    @staticmethod
    def level_index(level: str) -> int:
        try:
            return BLOOM_LEVELS.index(level)
        except ValueError:
            return 1

    @staticmethod
    def level_difficulty_weight(level: str) -> float:
        return {"remember": 0.5, "understand": 0.6, "apply": 0.8,
                "analyze": 1.0, "evaluate": 1.2, "create": 1.5}.get(level, 0.8)

    def bloom_3d_grid_svg(self) -> str:
        import base64
        w, h = 700, 320
        cell_w, cell_h = 100, 40
        left, top = 120, 60
        knowledge = list(KNOWLEDGE_DIMS.keys())
        parts = []
        for ci, clevel in enumerate(BLOOM_LEVELS):
            for ki in range(len(knowledge)):
                x = left + ci * cell_w
                y = top + ki * cell_h
                parts.append(
                    f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h-4}" '
                    f'fill="{BLOOM_COLORS[clevel]}" fill-opacity="0.3" '
                    f'stroke="{BLOOM_COLORS[clevel]}" rx="4"/>')
                parts.append(
                    f'<text x="{x+(cell_w-4)/2:.1f}" y="{y+(cell_h-4)/2+5:.1f}" '
                    f'font-size="11" fill="#1e293b" text-anchor="middle">{BLOOM_LABELS[clevel]}</text>')
        for ki, klevel in enumerate(knowledge):
            parts.append(
                f'<text x="{left-8}" y="{top+ki*cell_h+cell_h/2+5:.1f}" '
                f'font-size="11" fill="#64748b" text-anchor="end">{klevel[:8]}</text>')
        parts.append(f'<text x="20" y="28" font-size="15" font-weight="600" fill="#111827">'
                     f'Bloom 6x4 Grid (Cognitive x Knowledge)</text>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
               f'viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#fff"/>'
               + "".join(parts) + "</svg>")
        raw = svg.encode("utf-8")
        return f"data:image/svg+xml;base64,{base64.b64encode(raw).decode('ascii')}"


_bloom: Optional[BloomTaxonomy] = None

def get_bloom() -> BloomTaxonomy:
    global _bloom
    if _bloom is None:
        _bloom = BloomTaxonomy()
    return _bloom
