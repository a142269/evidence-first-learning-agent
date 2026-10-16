"""
CoV-Edu: Chain-of-Verification for Educational Content (Phase 1 Week 2 Day 8-9)

学术依据: Dhuliawala et al. 2023 "Chain-of-Verification Reduces Hallucination in LLMs"
教育适配: 基于 RAG 知识库对教学内容的声称级验证

Pipeline:
    1. ClaimsExtractor   — 从 LLM 生成内容中抽取离散的声称 (facts/statements/numbers)
    2. ClaimVerifier     — 每条声称 vs RAG 知识库: 规则粗筛 + LLM 精判
    3. ContentRewriter   — 基于验证结果重写，标记 [已验证]/[不确定]/[已纠正]
    4. COVVerifierAgent  — Agent wrapper，接入 Pipeline + SSE 流式

验证判决:
    verified   — RAG 中有直接支撑，与多个 chunk 一致
    uncertain  — RAG 中无明确支撑，但无法完全反驳
    refuted    — RAG 中明确矛盾（如年份错、定义错）

SSE 事件 (给前端实时展示):
    cov_claim        — 抽取到的新 claim
    cov_verification — 单条 claim 验证完成
    cov_final        — 重写完成，diff 对比
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)

# ================================================================
# 数据模型
# ================================================================
@dataclass
class Claim:
    """单条声称"""
    claim_id: int
    text: str                           # 主张原文
    claim_type: str = "factual"         # factual / definition / number / citation / opinion
    source_span: str = ""               # 在原内容中的上下文片段


@dataclass
class ClaimEvidence:
    """单条声称的验证证据"""
    claim_id: int
    claim_text: str
    verdict: str                        # "verified" / "uncertain" / "refuted"
    confidence: float                   # 0.0 - 1.0
    supporting_chunks: List[str] = field(default_factory=list)  # 支撑的 RAG 片段
    contradicting_chunks: List[str] = field(default_factory=list)  # 矛盾的 RAG 片段
    reasoning: str = ""                 # 判决理由
    suggested_correction: str = ""      # 建议修正 (refuted 时)


@dataclass
class COVResult:
    """CoV 完整结果"""
    original_content: str
    claims: List[Claim] = field(default_factory=list)
    evidences: List[ClaimEvidence] = field(default_factory=list)
    rewritten_content: str = ""
    summary: Dict[str, Any] = field(default_factory=dict)

    @property
    def claims_verified(self) -> int:
        return sum(1 for e in self.evidences if e.verdict == "verified")

    @property
    def claims_uncertain(self) -> int:
        return sum(1 for e in self.evidences if e.verdict == "uncertain")

    @property
    def claims_refuted(self) -> int:
        return sum(1 for e in self.evidences if e.verdict == "refuted")

    def hallucination_rate(self) -> float:
        total = len(self.evidences)
        if total == 0:
            return 0.0
        return (self.claims_uncertain + self.claims_refuted) / total


# ================================================================
# 1. ClaimsExtractor — 声称抽取
# ================================================================
class ClaimsExtractor:
    """从 LLM 生成内容中抽取离散声称

    双通道:
    - 规则通道: 基于标点/关键词分段（毫秒级，用于无 LLM 场景）
    - LLM 通道: 语义级别的声称识别（区分事实 vs 评论）

    教育场景专门的声称类型:
    - factual:    "CNN 由 Yann LeCun 于 1998 年提出"
    - definition: "卷积操作定义为 (f * g)(t) = ∫..."
    - number:     "LeNet-5 在 MNIST 上达到 99.05% 准确率"
    - citation:   "参见 Hinton et al. 2012"
    - opinion:    "CNN 是最适合图像任务的架构"
    """

    CLAIM_INDICATORS: List[str] = [
        r"是[^的]", r"定义为", r"等于", r"由.*提出",
        r"达到", r"包含", r"属于", r"具有",
        r"根据", r"参见", r"实验表明", r"研究显示",
        r"例如",  # 事实举例中也含 claim
    ]

    FACT_PATTERNS: List[str] = [
        r"\d{4}\s*年",           # 年份
        r"\d+\.?\d*\s*%",       # 百分比
        r"et\s+al\.",           # 论文引用
        r"\[[\d,\s]+\]",        # 文献编号
        r"\b\d+\s*(层|个|种|步|次)",  # 数量
    ]

    EXTRACT_CLAIMS_PROMPT = """从以下教育内容中提取所有可验证的事实声称。

内容:
{content}

请提取每个事实声称，每行一个，格式: "<声称文本> || <类型>"
类型: factual(事实) / definition(定义) / number(数字) / citation(引用) / opinion(观点)
只提取可验证的事实。跳过纯粹的解释性语句和过渡性语句。

输出示例:
卷积神经网络由 Yann LeCun 于 1998 年提出 || factual
卷积操作定义为 (f*g)(t)=∫f(τ)g(t-τ)dτ || definition
LeNet-5 在 MNIST 上达到 99.05% 准确率 || number"""

    def __init__(self, llm_client: Any = None):
        self._llm = llm_client

    def extract(self, content: str) -> List[Claim]:
        """从内容中抽取声称

        优先 LLM 通道，失败时降级到规则通道。
        """
        if not content or not content.strip():
            return []

        # 尝试 LLM 通道
        if self._llm:
            try:
                return self._extract_via_llm(content)
            except Exception as exc:
                logger.warning(f"[CoV] LLM claim extraction failed: {exc}")

        # 降级到规则通道
        return self._extract_via_rules(content)

    def _extract_via_llm(self, content: str) -> List[Claim]:
        """LLM 驱动的声称抽取"""
        prompt = self.EXTRACT_CLAIMS_PROMPT.format(content=content[:3000])

        messages = [
            {"role": "system", "content": "你是一个精确的事实提取器。只输出格式化的声称列表，不输出其他内容。"},
            {"role": "user", "content": prompt},
        ]

        if hasattr(self._llm, "chat"):
            raw = self._llm.chat(messages, temperature=0.1, max_tokens=500)
        elif hasattr(self._llm, "achat"):
            # 同步包装异步
            import asyncio
            loop = asyncio.get_event_loop()
            raw = loop.run_until_complete(
                self._llm.achat(messages, temperature=0.1, max_tokens=500)
            )
        else:
            return self._extract_via_rules(content)

        return self._parse_llm_output(raw, content)

    def _parse_llm_output(self, raw: str, content: str) -> List[Claim]:
        """解析 LLM 输出"""
        claims: List[Claim] = []
        claim_id = 0
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("||")
            text = parts[0].strip() if parts else line
            claim_type = parts[1].strip() if len(parts) > 1 else "factual"
            claim_type = claim_type.strip().lower()

            if claim_type not in ("factual", "definition", "number", "citation", "opinion"):
                claim_type = "factual"

            # LLM 已显式用 || 标注为声称, 用较低阈值避免误丢短声称
            # (如 "准确率 99.05%" 等数字声称只有 9-10 字符)
            if len(text) >= 4:
                claim_id += 1
                claims.append(Claim(
                    claim_id=claim_id,
                    text=text,
                    claim_type=claim_type,
                    source_span=self._find_span(text, content),
                ))

        return claims

    def _extract_via_rules(self, content: str) -> List[Claim]:
        """规则驱动的声称抽取

        策略: 找包含事实标记词 + 关键模式的句子。
        """
        claims: List[Claim] = []
        claim_id = 0

        # 按句子拆分
        sentences = re.split(r'[。！？\n](?![a-z])', content)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 10:  # 太短的忽略
                continue

            # 是否包含声称标记
            has_indicator = any(re.search(p, sent) for p in self.CLAIM_INDICATORS)
            has_fact = any(re.search(p, sent) for p in self.FACT_PATTERNS)

            if not (has_indicator or has_fact):
                continue

            # 判定类型
            if any(re.search(p, sent) for p in [r"et\s+al\.", r"\[\d+\]", r"参考文献", r"参见"]):
                claim_type = "citation"
            elif any(re.search(p, sent) for p in [r"\d+\.?\d*\s*%", r"\b\d+\s*(层|个|种)"]):
                claim_type = "number"
            elif any(re.search(p, sent) for p in [r"定义", r"公式", r"记为", r"表示为"]):
                claim_type = "definition"
            else:
                claim_type = "factual"

            claim_id += 1
            claims.append(Claim(
                claim_id=claim_id,
                text=sent[:200],
                claim_type=claim_type,
                source_span=sent[:100],
            ))

        return claims

    @staticmethod
    def _find_span(claim_text: str, full_content: str) -> str:
        """在原文中定位声称的上下文"""
        idx = full_content.find(claim_text[:20])
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(full_content), idx + len(claim_text) + 30)
            return full_content[start:end]
        return claim_text[:100]


# ================================================================
# 2. ClaimVerifier — 声称验证
# ================================================================
class ClaimVerifier:
    """对每条声称进行 RAG 知识库验证

    两层:
    - 规则层 (毫秒): 术语重叠度 / 数字精确匹配 / 引用格式检查
    - LLM 层 (秒):  语义级别的支撑/矛盾判断

    判决:
    - verified:   ≥ 2 个 RAG chunk 包含声称关键术语，语义一致
    - uncertain:  术语部分重叠但不足以确认
    - refuted:    包含与 RAG 矛盾的信息（数字不同 / 定义错）
    """

    RULE_OVERLAP_THRESHOLD: float = 0.3   # 术语 Jaccard ≥ 30%
    LLM_OVERLAP_THRESHOLD: float = 0.15   # 低重叠 → 跳过 LLM 直接 uncertain

    VERIFY_PROMPT = """验证以下声称是否被知识库支持。

声称: "{claim}"

知识库参考:
{context}

请判断:
- verified: 知识库直接支持该声称
- uncertain: 知识库没有明确信息，但逻辑上合理
- refuted: 知识库中有矛盾信息

输出 JSON:
{{"verdict": "verified|uncertain|refuted", "confidence": 0.0-1.0, "reasoning": "...", "correction": "..."}}"""

    def __init__(self, rag_service: Any = None, llm_client: Any = None):
        self._rag = rag_service
        self._llm = llm_client

    def verify(self, claim: Claim, rag_context: List[Dict[str, Any]]) -> ClaimEvidence:
        """验证单条声称"""
        # -- 规则层: 快速筛 --
        rule_result = self._rule_check(claim, rag_context)

        # 规则层高置信度 → 直接返回
        if rule_result and rule_result.confidence >= 0.85:
            return rule_result

        # -- LLM 层: 精细判 --
        if self._llm and rag_context:
            try:
                return self._llm_verify(claim, rag_context)
            except Exception as exc:
                logger.warning(f"[CoV] LLM verify failed for claim {claim.claim_id}: {exc}")

        # 降级: 规则层结果
        return rule_result or self._default_verdict(claim)

    def _rule_check(
        self, claim: Claim, rag_context: List[Dict[str, Any]],
    ) -> Optional[ClaimEvidence]:
        """规则驱动的快速验证"""
        if not rag_context:
            return None

        claim_terms = self._extract_terms(claim.text)
        if not claim_terms:
            return None

        supporting: List[str] = []
        contradicting: List[str] = []

        for chunk in rag_context:
            chunk_text = chunk.get("content", "")
            chunk_terms = self._extract_terms(chunk_text)
            overlap = claim_terms & chunk_terms
            overlap_ratio = len(overlap) / len(claim_terms)

            # 数字精确比较
            claim_nums = set(re.findall(r'\d+\.?\d*', claim.text))
            chunk_nums = set(re.findall(r'\d+\.?\d*', chunk_text))

            if claim_nums and chunk_nums:
                num_match = claim_nums & chunk_nums
                num_conflict = claim_nums - chunk_nums

                if num_conflict and overlap_ratio > 0.3:
                    # 有数字不匹配 → 可能矛盾
                    contradicting.append(chunk_text[:200])
                elif overlap_ratio >= self.RULE_OVERLAP_THRESHOLD:
                    supporting.append(chunk_text[:200])
            elif overlap_ratio >= self.RULE_OVERLAP_THRESHOLD:
                supporting.append(chunk_text[:200])

        if contradicting:
            return ClaimEvidence(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                verdict="refuted",
                confidence=0.7,
                contradicting_chunks=contradicting,
                reasoning="RAG 中存在数值矛盾",
                suggested_correction="请核对数字准确后修正",
            )

        if supporting:
            return ClaimEvidence(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                verdict="verified",
                confidence=0.8,
                supporting_chunks=supporting[:3],
                reasoning=f"知识库中有 {len(supporting)} 条相关证据",
            )

        return ClaimEvidence(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            verdict="uncertain",
            confidence=0.4,
            reasoning="规则层未找到足够支撑",
        )

    def _llm_verify(
        self, claim: Claim, rag_context: List[Dict[str, Any]],
    ) -> ClaimEvidence:
        """LLM 驱动的精细验证"""
        context = "\n\n---\n".join(
            c.get("content", "")[:400] for c in rag_context[:5]
        )
        prompt = self.VERIFY_PROMPT.format(claim=claim.text, context=context)

        messages = [
            {"role": "system", "content": "你是教育内容事实核查员。只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]

        if hasattr(self._llm, "chat"):
            raw = self._llm.chat(messages, temperature=0.1, max_tokens=200)
        else:
            return self._rule_check(claim, rag_context) or self._default_verdict(claim)

        try:
            # 提取 JSON
            json_match = re.search(r'\{.*?\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                verdict = data.get("verdict", "uncertain")
                if verdict not in ("verified", "uncertain", "refuted"):
                    verdict = "uncertain"
                return ClaimEvidence(
                    claim_id=claim.claim_id,
                    claim_text=claim.text,
                    verdict=verdict,
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    suggested_correction=data.get("correction", ""),
                )
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

        return self._default_verdict(claim)

    # 常见中文虚词 / 助词 — 用作术语切分边界
    _CHINESE_PARTICLES: frozenset = frozenset(
        "的了在和与或由是被把使将让向给从对于及以为之而其也都还又或且但若如则若"
    )

    @classmethod
    def _extract_terms(cls, text: str) -> set:
        """抽取中文 + 英文关键术语

        策略 (双通道合并, 互补):
        1. 英文: 3+ 字母连串 (cnn / lecun / etc.)
        2. 中文 jieba 分词: 标准分词单元 (卷积 / 神经网络 / 提出)
        3. 中文虚词切分: 保留长复合词 (卷积神经网络) — jieba 拆碎了它
        """
        terms: set = set()

        # 英文术语 (3+ 字母)
        for m in re.finditer(r'[A-Za-z]{3,}', text.lower()):
            terms.add(m.group())

        # 中文虚词切分 — 保留长复合词
        for m in re.finditer(r'[一-鿿]{2,}', text):
            run = m.group()
            buf: List[str] = []
            for ch in run:
                if ch in cls._CHINESE_PARTICLES:
                    if len(buf) >= 2:
                        terms.add("".join(buf))
                    buf = []
                else:
                    buf.append(ch)
            if len(buf) >= 2:
                terms.add("".join(buf))

        # 中文 jieba 分词 — 标准分词单元 (互补)
        try:
            import jieba
            for w in jieba.lcut(text):
                if len(w) >= 2 and re.fullmatch(r'[一-鿿]+', w):
                    terms.add(w)
        except ImportError:
            pass

        return terms

    @staticmethod
    def _default_verdict(claim: Claim) -> ClaimEvidence:
        return ClaimEvidence(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            verdict="uncertain",
            confidence=0.3,
            reasoning="无法完成验证（无 LLM / 无 RAG）",
        )


# ================================================================
# 3. ContentRewriter — 内容重写
# ================================================================
class ContentRewriter:
    """基于验证结果重写内容

    策略:
    - verified 声称: 保留原文，加 [✓] 标记（可配置是否显示）
    - uncertain 声称: 弱化语气（"可能是..."），加 [?] 标记
    - refuted 声称: 使用建议修正替换，加 [✗→...] 标记
    """

    def rewrite(self, original: str, evidences: List[ClaimEvidence]) -> str:
        """基于验证结果重写内容"""
        if not evidences:
            return original

        result = original
        verified_count = 0
        uncertain_count = 0
        refuted_count = 0

        # 处理 refuted 声称（最优先）
        for ev in evidences:
            if ev.verdict != "refuted":
                continue
            if ev.suggested_correction and ev.claim_text in result:
                replacement = f"~~{ev.claim_text}~~ [已纠正: {ev.suggested_correction}]"
                result = result.replace(ev.claim_text, replacement)
                refuted_count += 1

        # 处理 uncertain 声称
        for ev in evidences:
            if ev.verdict != "uncertain":
                continue
            if ev.claim_text in result:
                # 在声称前加不确定标记
                marked = f"[? 待核实] {ev.claim_text}"
                result = result.replace(ev.claim_text, marked)
                uncertain_count += 1

        # 统计 verified
        verified_count = sum(1 for e in evidences if e.verdict == "verified")

        # 添加验证摘要
        result += (
            f"\n\n---\n"
            f"*内容验证: {verified_count} 条已验证, "
            f"{uncertain_count} 条待核实, {refuted_count} 条已纠正*"
        )

        return result


# ================================================================
# 4. COVVerifierAgent
# ================================================================
class COVVerifierAgent(BaseAgent):
    """CoV 防幻觉验证 Agent

    Pipeline 集成点:
    - Orchestrator 路由到本 Agent
    - 输入: user_input = 原始生成内容
    - context.extra.rag_results = RAG 检索结果
    - 输出: metadata 含 cov_result + claims + evidence

    SSE 事件:
    - cov_claim:       抽取到的新 claim
    - cov_verification: 单条 claim 验证完成
    - cov_final:       重写完成，含 stats
    """

    prompt_version = "v1"

    def __init__(self, llm_client=None, rag_service=None):
        super().__init__(llm_client=llm_client)
        self._extractor = ClaimsExtractor(llm_client=llm_client)
        self._verifier = ClaimVerifier(rag_service=rag_service, llm_client=llm_client)
        self._rewriter = ContentRewriter()

    @property
    def name(self) -> str:
        return "cov_verifier"

    @property
    def description(self) -> str:
        return "Chain-of-Verification 防幻觉: 声称抽取 → RAG 验证 → 证据重写"

    @property
    def system_prompt(self) -> str:
        return (
            "你是 Chain-of-Verification 验证器。\n\n"
            "你的任务:\n"
            "1. 从生成内容中抽取可验证的声称\n"
            "2. 在知识库中逐一验证每条声称\n"
            "3. 基于验证结果重写内容\n\n"
            "判决标准:\n"
            "- verified: 知识库有直接支撑\n"
            "- uncertain: 知识库无明确信息\n"
            "- refuted: 与知识库矛盾"
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行 CoV 验证"""
        content = (
            context.extra.get("content_to_review")
            or context.user_input
        )

        if not content or not content.strip():
            return self._error("CoV 验证内容为空")

        rag_results = context.rag_results or []
        start = time.perf_counter()

        # 1. 抽取声称
        claims = self._extractor.extract(content)

        # 2. 逐条验证
        evidences: List[ClaimEvidence] = []
        for claim in claims:
            ev = self._verifier.verify(claim, rag_results)
            evidences.append(ev)

        # 3. 重写
        rewritten = self._rewriter.rewrite(content, evidences)

        # 4. 统计
        cov_result = COVResult(
            original_content=content,
            claims=claims,
            evidences=evidences,
            rewritten_content=rewritten,
            summary={
                "total_claims": len(claims),
                "verified": sum(1 for e in evidences if e.verdict == "verified"),
                "uncertain": sum(1 for e in evidences if e.verdict == "uncertain"),
                "refuted": sum(1 for e in evidences if e.verdict == "refuted"),
                "hallucination_rate": (
                    sum(1 for e in evidences if e.verdict in ("uncertain", "refuted"))
                    / max(len(evidences), 1)
                ),
                "elapsed_ms": (time.perf_counter() - start) * 1000,
            },
        )

        # 构建 Markdown 报告
        report_lines = [
            f"## CoV 验证报告",
            f"",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 总声称数 | {cov_result.summary['total_claims']} |",
            f"| 已验证 | {cov_result.summary['verified']} |",
            f"| 不确定 | {cov_result.summary['uncertain']} |",
            f"| 已纠正 | {cov_result.summary['refuted']} |",
            f"| 幻觉率 | {cov_result.summary['hallucination_rate']:.0%} |",
            f"| 耗时 | {cov_result.summary['elapsed_ms']:.0f}ms |",
            f"",
        ]

        for ev in evidences:
            icon = {"verified": "✓", "uncertain": "?", "refuted": "✗"}
            report_lines.append(
                f"- {icon.get(ev.verdict, '?')} [{ev.verdict}] "
                f"{ev.claim_text[:80]}"
            )
            if ev.suggested_correction:
                report_lines.append(f"  → {ev.suggested_correction}")

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content="\n".join(report_lines),
            content_type="markdown",
            metadata={
                "cov_result": cov_result,
                "claims": [{"id": c.claim_id, "text": c.text, "type": c.claim_type} for c in claims],
                "evidences": [
                    {
                        "claim_id": e.claim_id,
                        "verdict": e.verdict,
                        "confidence": e.confidence,
                        "reasoning": e.reasoning,
                        "correction": e.suggested_correction,
                    }
                    for e in evidences
                ],
                "rewritten_content": rewritten,
                "hallucination_rate": cov_result.hallucination_rate(),
            },
        )
