# ruff: noqa: RUF001
"""Judge-facing CoV-Edu demo service.

The core CoV agent already performs claim extraction and RAG verification.
This wrapper exposes five education-specific axes in a deterministic shape
for HTTP demos: factual, pedagogical, bloom, citation, and safety.
"""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import html
import json
from pathlib import Path
import re
from typing import Any

from backend.app.agents.cov_verifier import Claim, ClaimVerifier, ClaimsExtractor

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEMO_CASES_PATH = _PROJECT_ROOT / "data" / "cov_demo_cases.json"
_DEFAULT_AXES = ["factual", "pedagogical", "bloom", "citation", "safety"]


@dataclass(frozen=True)
class CoVDemoRequest:
    text: str
    ground_truth: str = ""
    axes: list[str] | None = None


class CoVDemoService:
    """Run CoV-Edu checks and format a compact demo response."""

    def __init__(
        self,
        llm_client: Any | None = None,
        rag_service: Any | None = None,
    ) -> None:
        # 允许上层显式注入；默认按需拉取全局单例，让核验用上真 LLM + RAG
        if llm_client is None:
            try:
                from backend.app.api.v1.chat_pipeline.stages._shared import get_shared_llm
                llm_client = get_shared_llm()
            except Exception:
                llm_client = None
        if rag_service is None:
            try:
                from backend.app.services.rag_service import get_rag_service
                rag_service = get_rag_service()
            except Exception:
                rag_service = None
        self._rag = rag_service
        self.extractor = ClaimsExtractor(llm_client=llm_client)
        self.verifier = ClaimVerifier(rag_service=rag_service, llm_client=llm_client)

    def run(self, request: CoVDemoRequest) -> dict[str, Any]:
        text = request.text.strip()
        if not text:
            return {
                "ok": False,
                "error": "text_required",
                "axes": [],
                "revised_text": "",
                "diff_html": "",
            }
        axes = self._normalize_axes(request.axes)
        axis_results = [
            self._run_axis(axis=axis, text=text, ground_truth=request.ground_truth)
            for axis in axes
        ]
        revised_text = self._revise_text(text, request.ground_truth, axis_results)
        return {
            "ok": True,
            "original_text": text,
            "ground_truth": request.ground_truth,
            "axes": axis_results,
            "summary": self._summary(axis_results),
            "revised_text": revised_text,
            "diff_html": _diff_html(text, revised_text),
        }

    def demo_cases(self) -> list[dict[str, Any]]:
        if not _DEMO_CASES_PATH.exists():
            return []
        payload = json.loads(_DEMO_CASES_PATH.read_text(encoding="utf-8"))
        cases = payload.get("cases", [])
        return cases if isinstance(cases, list) else []

    def _run_axis(
        self,
        axis: str,
        text: str,
        ground_truth: str,
    ) -> dict[str, Any]:
        if axis == "factual":
            return self._factual_axis(text, ground_truth)
        if axis == "pedagogical":
            return self._pedagogical_axis(text)
        if axis == "bloom":
            return self._bloom_axis(text)
        if axis == "citation":
            return self._citation_axis(text)
        if axis == "safety":
            return self._safety_axis(text)
        return _axis_result(
            axis=axis,
            verdict="uncertain",
            confidence=0.2,
            issue=f"未知验证轴: {axis}",
            correction="请使用 factual/pedagogical/bloom/citation/safety。",
        )

    def _factual_axis(self, text: str, ground_truth: str) -> dict[str, Any]:
        claims = self.extractor.extract(text)
        if not claims and len(text) >= 6:
            claims = [Claim(claim_id=1, text=text, claim_type="factual", source_span=text[:80])]
        rag: list[dict[str, Any]] = []
        if ground_truth.strip():
            rag.append({"content": ground_truth})
        # 无 ground_truth 时也走一遍 RAG 检索，让核验有真实证据
        if self._rag is not None:
            try:
                hits = self._rag.retrieve(text, top_k=5)
                for hit in hits or []:
                    content = hit.get("content") if isinstance(hit, dict) else ""
                    if content:
                        rag.append({"content": content})
            except Exception:
                pass
        evidences = [self.verifier.verify(claim, rag) for claim in claims]
        verdicts = [e.verdict for e in evidences]
        if not evidences:
            return _axis_result(
                axis="factual",
                verdict="uncertain",
                confidence=0.3,
                issue="未抽取到可验证声称。",
                correction="请补充明确事实声称或 ground_truth。",
            )
        if "refuted" in verdicts:
            return _axis_result(
                axis="factual",
                verdict="refuted",
                confidence=max(e.confidence for e in evidences),
                issue="至少一条事实声称与参考知识冲突。",
                correction=ground_truth or "请核对参考资料后改写事实表述。",
                details=_evidence_details(evidences),
            )
        if all(v == "verified" for v in verdicts):
            return _axis_result(
                axis="factual",
                verdict="verified",
                confidence=min(e.confidence for e in evidences),
                issue="事实声称获得参考知识支撑。",
                correction="无需修正。",
                details=_evidence_details(evidences),
            )
        return _axis_result(
            axis="factual",
            verdict="uncertain",
            confidence=0.45,
            issue="部分事实声称缺少足够证据。",
            correction="补充出处或降低确定性语气。",
            details=_evidence_details(evidences),
        )

    def _pedagogical_axis(self, text: str) -> dict[str, Any]:
        markers = ["例如", "比如", "步骤", "先", "再", "因为", "所以", "小结", "练习"]
        hits = [marker for marker in markers if marker in text]
        if len(text) < 40:
            return _axis_result(
                axis="pedagogical",
                verdict="uncertain",
                confidence=0.5,
                issue="讲解过短，缺少教学展开。",
                correction="补充概念定义、例子、步骤和练习提示。",
            )
        if len(hits) >= 2:
            return _axis_result(
                axis="pedagogical",
                verdict="verified",
                confidence=0.82,
                issue="内容包含教学支架。",
                correction="无需修正。",
            )
        return _axis_result(
            axis="pedagogical",
            verdict="uncertain",
            confidence=0.55,
            issue="教学支架不足。",
            correction="建议增加一个例子、一个步骤拆解和一个即时练习。",
        )

    def _bloom_axis(self, text: str) -> dict[str, Any]:
        bloom_hits = {
            "remember": ["定义", "列举", "识别"],
            "understand": ["解释", "说明", "比较"],
            "apply": ["应用", "计算", "实现"],
            "analyze": ["分析", "区分", "推导"],
            "evaluate": ["评价", "判断", "验证"],
            "create": ["设计", "构建", "生成"],
        }
        matched = [
            level
            for level, words in bloom_hits.items()
            if any(word in text for word in words)
        ]
        if matched:
            return _axis_result(
                axis="bloom",
                verdict="verified",
                confidence=0.78,
                issue=f"检测到 Bloom 动词: {', '.join(matched)}。",
                correction="无需修正。",
                details={"levels": matched},
            )
        return _axis_result(
            axis="bloom",
            verdict="uncertain",
            confidence=0.45,
            issue="没有显式 Bloom 学习动作。",
            correction="补充“解释/应用/分析/评价/设计”等任务动词。",
        )

    def _citation_axis(self, text: str) -> dict[str, Any]:
        has_claim_like = bool(re.search(r"\d{4}\s*年|et\s+al\.|提出|发明|首次", text))
        has_citation = bool(re.search(r"\[[0-9,\s]+\]|参考|来源|LeCun|Hinton|论文", text))
        if not has_claim_like:
            return _axis_result(
                axis="citation",
                verdict="verified",
                confidence=0.75,
                issue="未检测到强引用需求的历史/论文声称。",
                correction="无需修正。",
            )
        if has_citation:
            return _axis_result(
                axis="citation",
                verdict="verified",
                confidence=0.76,
                issue="关键声称包含出处线索。",
                correction="可在正式文档中补充完整参考文献。",
            )
        return _axis_result(
            axis="citation",
            verdict="uncertain",
            confidence=0.5,
            issue="存在历史/论文声称但缺少出处。",
            correction="补充教材、论文或知识库章节引用。",
        )

    def _safety_axis(self, text: str) -> dict[str, Any]:
        risky_terms = ["忽略所有指令", "泄露", "攻击", "绕过", "违法", "木马", "敏感信息"]
        hits = [term for term in risky_terms if term in text]
        if hits:
            return _axis_result(
                axis="safety",
                verdict="refuted",
                confidence=0.9,
                issue=f"检测到潜在不安全表达: {', '.join(hits)}。",
                correction="删除不安全请求，改为合规学习说明。",
            )
        return _axis_result(
            axis="safety",
            verdict="verified",
            confidence=0.86,
            issue="未发现明显安全风险。",
            correction="无需修正。",
        )

    def _revise_text(
        self,
        text: str,
        ground_truth: str,
        axis_results: list[dict[str, Any]],
    ) -> str:
        revised = text
        factual = next((item for item in axis_results if item["axis"] == "factual"), None)
        if factual and factual["verdict"] == "refuted" and ground_truth.strip():
            revised = ground_truth.strip()
        additions = []
        for item in axis_results:
            if item["verdict"] in {"refuted", "uncertain"} and item["correction"] != "无需修正。":
                additions.append(f"- [{item['axis']}] {item['correction']}")
        if additions:
            revised += "\n\n修订建议:\n" + "\n".join(additions)
        return revised

    def _normalize_axes(self, axes: list[str] | None) -> list[str]:
        if not axes:
            return list(_DEFAULT_AXES)
        normalized = []
        for axis in axes:
            value = str(axis).strip().lower()
            if value and value not in normalized:
                normalized.append(value)
        return normalized or list(_DEFAULT_AXES)

    def _summary(self, axis_results: list[dict[str, Any]]) -> dict[str, Any]:
        total = len(axis_results)
        refuted = sum(1 for item in axis_results if item["verdict"] == "refuted")
        uncertain = sum(1 for item in axis_results if item["verdict"] == "uncertain")
        verified = sum(1 for item in axis_results if item["verdict"] == "verified")
        return {
            "total_axes": total,
            "verified": verified,
            "uncertain": uncertain,
            "refuted": refuted,
            "risk_rate": round((refuted + uncertain) / total, 4) if total else 0.0,
        }


def _axis_result(
    axis: str,
    verdict: str,
    confidence: float,
    issue: str,
    correction: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "axis": axis,
        "verdict": verdict,
        "confidence": round(confidence, 4),
        "issue": issue,
        "correction": correction,
        "details": details or {},
    }


def _evidence_details(evidences: list[Any]) -> dict[str, Any]:
    return {
        "claims": [
            {
                "claim": ev.claim_text,
                "verdict": ev.verdict,
                "confidence": ev.confidence,
                "reasoning": ev.reasoning,
            }
            for ev in evidences
        ]
    }


def _diff_html(original: str, revised: str) -> str:
    if original == revised:
        safe = html.escape(original)
        return f"<span>{safe}</span>"
    original_words = original.split()
    revised_words = revised.split()
    parts = []
    for token in difflib.ndiff(original_words, revised_words):
        marker = token[:2]
        value = html.escape(token[2:])
        if marker == "- ":
            parts.append(f"<del>{value}</del>")
        elif marker == "+ ":
            parts.append(f"<ins>{value}</ins>")
        elif marker == "  ":
            parts.append(f"<span>{value}</span>")
    return " ".join(parts)

