"""
ReflectionTrace - 反思全过程的可追踪记录

设计目标:
- 每轮反思的完整决策过程留痕 — 可在 UI 展开"Agent 内心戏"
- 替代纯文本日志, 让评分 + reasoning 都结构化
- 为未来的 prompt engineering A/B 实验提供数据基础

学术参考:
- Shinn et al. (2023) Reflexion: Language Agents with Verbal Reinforcement Learning
- Madaan et al. (2023) Self-Refine: Iterative Refinement with Self-Feedback
- Asai et al. (2023) Self-RAG: Learning to Retrieve, Generate, and Critique
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReflectionVerdict(str, Enum):
    """反思结论 — 决定下一步动作"""
    PASS = "pass"             # 内容已足够好, 无需重写
    NEEDS_REVISION = "revise"  # 需要修订, 已给出 improved_draft
    NEEDS_REGEN = "regen"      # 严重问题, 应整体重新生成


@dataclass
class WeaknessItem:
    """单条弱点诊断"""
    dimension: str            # factual / pedagogy / bloom / engagement / structure
    severity: str             # blocker / major / minor
    description: str
    location: str = ""        # 段落 / 句子定位
    suggestion: str = ""


@dataclass
class ReflectionScore:
    """反思评分明细

    总分 0.0-1.0; 各维度独立打分。Bloom-aware 反思会额外标注 bloom_match。
    """
    overall: float = 0.0
    factual: float = 0.0
    pedagogy: float = 0.0
    bloom_match: float = 0.0
    engagement: float = 0.0
    structure: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "overall": round(self.overall, 3),
            "factual": round(self.factual, 3),
            "pedagogy": round(self.pedagogy, 3),
            "bloom_match": round(self.bloom_match, 3),
            "engagement": round(self.engagement, 3),
            "structure": round(self.structure, 3),
        }


@dataclass
class ReflectionStep:
    """一轮反思的完整记录 (evaluate → reflect → revise → verify)"""
    step_index: int
    timestamp: float = field(default_factory=time.time)

    # 评估
    pre_score: ReflectionScore = field(default_factory=ReflectionScore)
    weaknesses: List[WeaknessItem] = field(default_factory=list)

    # 反思 (verbal reasoning)
    reasoning: str = ""

    # 修订
    revised_content: str = ""
    revision_diff_summary: str = ""

    # 验证
    post_score: ReflectionScore = field(default_factory=ReflectionScore)
    improved: bool = False

    duration_ms: float = 0.0


@dataclass
class ReflectionTrace:
    """完整反思轨迹 — 一次 reflect() 调用产生一条 Trace

    支持多轮反思 (Self-Refine 多步), 每轮一个 ReflectionStep。
    """
    agent_name: str
    strategy: str = "self_refine"
    prompt_version: str = ""

    original_content: str = ""
    final_content: str = ""

    verdict: ReflectionVerdict = ReflectionVerdict.PASS
    steps: List[ReflectionStep] = field(default_factory=list)

    started_at: float = field(default_factory=time.time)
    total_ms: float = 0.0
    bloom_target: str = ""

    def add_step(self, step: ReflectionStep) -> None:
        self.steps.append(step)
        self.total_ms += step.duration_ms

    def best_score(self) -> float:
        if not self.steps:
            return 0.0
        return max(
            (s.post_score.overall for s in self.steps),
            default=0.0,
        )

    def needs_rewrite(self) -> bool:
        return self.verdict != ReflectionVerdict.PASS

    def to_dict(self) -> Dict[str, Any]:
        """序列化供 chat_pipeline / SSE 下发"""
        return {
            "agent_name": self.agent_name,
            "strategy": self.strategy,
            "prompt_version": self.prompt_version,
            "verdict": self.verdict.value,
            "needs_rewrite": self.needs_rewrite(),
            "improved_draft": self.final_content,
            "rounds": len(self.steps),
            "best_score": round(self.best_score(), 3),
            "total_ms": round(self.total_ms, 2),
            "bloom_target": self.bloom_target,
            "issues": [
                {
                    "dimension": w.dimension,
                    "severity": w.severity,
                    "description": w.description,
                    "suggestion": w.suggestion,
                }
                for step in self.steps for w in step.weaknesses
            ],
            "reasoning_chain": [
                {
                    "step": s.step_index,
                    "reasoning": s.reasoning,
                    "pre_score": s.pre_score.overall,
                    "post_score": s.post_score.overall,
                    "improved": s.improved,
                }
                for s in self.steps
            ],
        }
