"""Claim Ledger / Evidence Trail (P1.2)

给 LLM 输出的每个事实性 claim 自动附上**证据链**：来源类型 / 来源定位 /
置信度 / 跨源冲突警告。让评委可以直接看到「这句话来自《教材第 3 章》/ 知识图谱节点 X /
学生历史错题 Y」，不是空话。

与 CoV (Chain-of-Verification) 的关系:
    * CoV    = 输出后验证：抽 claim → 反问 → 不一致回写
    * Ledger = 输出时打证据：每个 claim 输出时就附来源
    * 两者互补：CoV 防幻觉，Ledger 给可解释性

5 种 source type:
    1. "textbook"    教材章节（knowledge_base/*.md）
    2. "kg"          知识图谱节点 / 边
    3. "rag_chunk"   RAG 召回的 chunk
    4. "mistake"     学生历史错题记录
    5. "history"     学生学习历史（KT 状态 / 完成路径）

设计取舍:
    * 纯启发式 claim 抽取（按句号 / 分号切句 + 长度过滤），无 LLM 依赖
    * 证据匹配通过子串包含 + 关键词重叠（Jaccard），不调向量
    * 冲突检测：同 claim 在多 source 拿到差距 ≥ 0.4 的 confidence → 标记
    * 与 ARES 评估方向一致：context_relevance / answer_faithfulness / answer_relevance
    * 与 B 的 KT / attribution 解耦：source 是可选 list，缺哪种就跳过哪种
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


# ================================================================
# Source type 枚举（字符串便于 JSON 序列化）
# ================================================================
SOURCE_TYPES = ("textbook", "kg", "rag_chunk", "mistake", "history")


# ================================================================
# 数据模型
# ================================================================
@dataclass
class EvidenceSource:
    """单条证据来源。"""
    source_type: str           # "textbook" / "kg" / "rag_chunk" / "mistake" / "history"
    ref: str                   # 具体定位字符串（章节名 / KG 节点 id / chunk_id / mistake_id 等）
    confidence: float          # 0-1 该 claim 被此 source 支持的置信度
    excerpt: str = ""          # 来源里命中的原文片段（≤120 字）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "ref": self.ref,
            "confidence": round(self.confidence, 3),
            "excerpt": self.excerpt[:120],
        }


@dataclass
class Claim:
    """一条事实性陈述 + 证据链。"""
    text: str
    sources: List[EvidenceSource] = field(default_factory=list)
    conflict_warning: bool = False
    conflict_note: str = ""

    @property
    def best_confidence(self) -> float:
        return max((s.confidence for s in self.sources), default=0.0)

    @property
    def is_supported(self) -> bool:
        return self.best_confidence >= 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "sources": [s.to_dict() for s in self.sources],
            "best_confidence": round(self.best_confidence, 3),
            "is_supported": self.is_supported,
            "conflict_warning": self.conflict_warning,
            "conflict_note": self.conflict_note,
        }


@dataclass
class ClaimLedgerResult:
    """完整 ledger：所有 claim + 总体支持率。"""
    claims: List[Claim] = field(default_factory=list)
    total_claims: int = 0
    supported_claims: int = 0  # best_confidence >= 0.5 的条数
    unsupported_claims: int = 0
    conflicts: int = 0
    source_distribution: Dict[str, int] = field(default_factory=dict)

    @property
    def support_rate(self) -> float:
        if self.total_claims == 0:
            return 0.0
        return self.supported_claims / self.total_claims

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claims": [c.to_dict() for c in self.claims],
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "conflicts": self.conflicts,
            "support_rate": round(self.support_rate, 3),
            "source_distribution": self.source_distribution,
        }


@dataclass
class EvidencePool:
    """5 种 source 的原料池，全部 optional。

    每个 source 是 ``list[dict]``，dict 字段约定：
        * 必含 ``ref``（来源定位）+ ``content``（原文）
        * 可选 ``title`` / ``chunk_id`` / ``score`` 等
    """
    textbook: List[Dict[str, Any]] = field(default_factory=list)
    kg: List[Dict[str, Any]] = field(default_factory=list)
    rag_chunk: List[Dict[str, Any]] = field(default_factory=list)
    mistake: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def all_sources(self) -> Iterable[tuple[str, List[Dict[str, Any]]]]:
        """yield (source_type, list[source_dict])。"""
        yield "textbook", self.textbook
        yield "kg", self.kg
        yield "rag_chunk", self.rag_chunk
        yield "mistake", self.mistake
        yield "history", self.history


# ================================================================
# Claim 抽取 + 匹配
# ================================================================
class ClaimLedger:
    """证据链建模主入口。

    用法::

        ledger = ClaimLedger()
        pool = EvidencePool(
            rag_chunk=[
                {"ref": "ai/04_cnn.md#L23", "content": "CNN 通过卷积核共享权重..."},
            ],
            kg=[
                {"ref": "kp:cnn", "content": "CNN 是处理图像的核心架构"},
            ],
        )
        result = ledger.build("CNN 通过卷积核共享权重，因此参数量比全连接少。", pool=pool)
        for c in result.claims:
            print(c.to_dict())
    """

    # claim 切分：句号 / 问号 / 感叹号 / 分号 / 换行
    _CLAIM_SPLIT = re.compile(r"[。！？；\.;\n]+")
    _MIN_CLAIM_LEN = 6   # < 6 字符的片段视为接续词，不算 claim
    _MAX_CLAIMS = 50     # 一次最多抽 50 条，防 DoS

    # 抽 keyword：中文 2-4 字词 + 英文/数字 token
    _ZH_WORD = re.compile(r"[一-鿿]{2,4}")
    _EN_TOKEN = re.compile(r"[A-Za-z0-9_\-]{2,}")

    def build(
        self,
        text: str,
        pool: Optional[EvidencePool] = None,
    ) -> ClaimLedgerResult:
        """对 text 抽 claim 并匹配 pool 中的证据。"""
        pool = pool or EvidencePool()
        claims_raw = self._extract_claims(text)

        claims: List[Claim] = []
        source_dist: Dict[str, int] = {st: 0 for st in SOURCE_TYPES}

        for raw in claims_raw:
            sources = self._match_evidence(raw, pool)
            conflict, note = self._detect_conflict(sources)
            claim = Claim(
                text=raw,
                sources=sources,
                conflict_warning=conflict,
                conflict_note=note,
            )
            claims.append(claim)
            for s in sources:
                source_dist[s.source_type] = source_dist.get(s.source_type, 0) + 1

        supported = sum(1 for c in claims if c.is_supported)
        result = ClaimLedgerResult(
            claims=claims,
            total_claims=len(claims),
            supported_claims=supported,
            unsupported_claims=len(claims) - supported,
            conflicts=sum(1 for c in claims if c.conflict_warning),
            source_distribution=source_dist,
        )
        return result

    # ── claim 抽取 ─────────────────────────────────────────
    def _extract_claims(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []
        parts = [p.strip() for p in self._CLAIM_SPLIT.split(text)]
        claims = [p for p in parts if len(p) >= self._MIN_CLAIM_LEN]
        return claims[: self._MAX_CLAIMS]

    # ── keyword 重叠（Jaccard） ────────────────────────────
    def _tokenize(self, text: str) -> Set[str]:
        text = (text or "").lower()
        tokens: Set[str] = set()
        tokens.update(m.group() for m in self._ZH_WORD.finditer(text))
        tokens.update(m.group() for m in self._EN_TOKEN.finditer(text))
        return tokens

    def _jaccard(self, a: Set[str], b: Set[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    # ── 证据匹配 ───────────────────────────────────────────
    def _match_evidence(
        self, claim_text: str, pool: EvidencePool
    ) -> List[EvidenceSource]:
        """对每个 source 算 (substring | jaccard) 得分，取 ≥ 0.3 的入选。"""
        claim_tokens = self._tokenize(claim_text)
        claim_norm = claim_text.lower()
        matched: List[EvidenceSource] = []

        for source_type, source_list in pool.all_sources():
            for src in source_list:
                content = str(src.get("content", "") or "")
                if not content:
                    continue
                ref = str(src.get("ref", "") or "unknown")

                # 1. 子串包含 → 高置信度
                content_lower = content.lower()
                if claim_norm and claim_norm in content_lower:
                    matched.append(
                        EvidenceSource(
                            source_type=source_type,
                            ref=ref,
                            confidence=0.95,
                            excerpt=self._head(content),
                        )
                    )
                    continue

                # 2. keyword 重叠（Jaccard）
                src_tokens = self._tokenize(content)
                jacc = self._jaccard(claim_tokens, src_tokens)
                if jacc >= 0.3:
                    matched.append(
                        EvidenceSource(
                            source_type=source_type,
                            ref=ref,
                            confidence=min(0.9, 0.3 + jacc),  # 0.6 ~ 0.9
                            excerpt=self._head(content),
                        )
                    )

        # 按 confidence 降序、source_type 优先级（textbook > kg > rag > mistake > history）
        priority = {st: i for i, st in enumerate(SOURCE_TYPES)}
        matched.sort(key=lambda s: (-s.confidence, priority.get(s.source_type, 99)))
        return matched

    # ── 冲突检测 ───────────────────────────────────────────
    @staticmethod
    def _detect_conflict(sources: List[EvidenceSource]) -> tuple[bool, str]:
        """如同 claim 的 source 置信度差距 ≥ 0.4 → 标 conflict。"""
        if len(sources) < 2:
            return False, ""
        best = max(s.confidence for s in sources)
        worst = min(s.confidence for s in sources)
        if best - worst >= 0.4:
            return (
                True,
                f"证据强弱差距大: best={best:.2f} ({sources[0].source_type}) "
                f"vs worst={worst:.2f}",
            )
        return False, ""

    @staticmethod
    def _head(text: str, max_len: int = 120) -> str:
        text = (text or "").strip()
        return text[:max_len] + ("…" if len(text) > max_len else "")


# ================================================================
# 全局单例
# ================================================================
_ledger: Optional[ClaimLedger] = None


def get_claim_ledger() -> ClaimLedger:
    global _ledger
    if _ledger is None:
        _ledger = ClaimLedger()
    return _ledger
