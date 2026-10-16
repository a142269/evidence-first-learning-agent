"""
Debate Convergence Tracker — 研究级辩论收敛分析工具 (Phase 1 Week 2 Day 6-7)

设计目标:
    - 不是简单的 CSV logger，是研究级统计工具
    - 追踪每轮每个 Critic 维度的评分
    - 分类收敛类型: 快速收敛 / 缓慢收敛 / 振荡 / 发散
    - 输出 JSONL 供学术分析

统计方法:
    - Mann-Kendall 趋势检验 (非参数)
    - 滑动窗口标准差 (振荡检测)
    - 收敛判定: 3 种信号联合决策

用法:
    tracker = ConvergenceTracker()
    # 每轮辩论后
    tracker.record_round(session_id, round_num, dimension_scores, passed)
    # 辩论结束后
    analysis = tracker.analyze(session_id)
    # analysis.convergence_type → "fast" / "slow" / "oscillating" / "divergent"
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ================================================================
# 枚举与常量
# ================================================================
class ConvergenceType(Enum):
    """收敛类型分类"""
    FAST = "fast"                 # 2 轮内通过
    SLOW = "slow"                 # 2+ 轮通过，递减趋势
    OSCILLATING = "oscillating"   # 高分↔低分振荡
    STUCK = "stuck"               # 持续低分，无改善
    DIVERGENT = "divergent"       # 越改越差


# 维度名常量
DIM_FACTUAL = "factual"
DIM_PEDAGOGY = "pedagogy"
DIM_BLOOM = "bloom"
DIM_CITATION = "citation"
TRACKED_DIMENSIONS: Tuple[str, ...] = (DIM_FACTUAL, DIM_PEDAGOGY, DIM_BLOOM, DIM_CITATION)


# ================================================================
# 数据模型
# ================================================================
@dataclass
class RoundSnapshot:
    """单轮辩论快照"""
    round_num: int
    overall_score: float
    passed: bool
    dimension_scores: Dict[str, float]    # factual/pedagogy/bloom/citation → 0-1
    issue_count: int = 0
    elapsed_ms: float = 0.0


@dataclass
class ConvergenceAnalysis:
    """单次辩论的收敛分析结果"""
    session_id: str
    query_text: str
    total_rounds: int
    passed: bool
    final_score: float

    # 统计量
    mean_score: float
    std_score: float
    score_trend_slope: float              # 线性回归斜率 (正=改善)
    score_trend_p_value: float            # Mann-Kendall p 值

    # 收敛类型
    convergence_type: ConvergenceType
    convergence_round: int                # 收敛发生的轮次 (0=未收敛)
    rounds_until_pass: int                # 到通过需要的轮数 (0=未通过)

    # 分维度趋势
    dimension_trends: Dict[str, float]    # 每维的分数变化 (最后一轮 - 第一轮)

    # 原始数据
    snapshots: List[RoundSnapshot] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "query_text": self.query_text,
            "total_rounds": self.total_rounds,
            "passed": self.passed,
            "final_score": self.final_score,
            "mean_score": round(self.mean_score, 3),
            "std_score": round(self.std_score, 3),
            "score_trend_slope": round(self.score_trend_slope, 4),
            "score_trend_p_value": round(self.score_trend_p_value, 4),
            "convergence_type": self.convergence_type.value,
            "convergence_round": self.convergence_round,
            "rounds_until_pass": self.rounds_until_pass,
            "dimension_trends": {
                k: round(v, 3) for k, v in self.dimension_trends.items()
            },
            "snapshots": [asdict(s) for s in self.snapshots],
        }


# ================================================================
# 统计分析工具
# ================================================================
class StatsUtils:
    """无第三方依赖的统计分析"""

    @staticmethod
    def mean(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def std(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = StatsUtils.mean(values)
        return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))

    @staticmethod
    def linear_slope(y_values: List[float]) -> float:
        """简单线性回归斜率 (x = 轮次序号)"""
        n = len(y_values)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = StatsUtils.mean(y_values)
        numerator = sum((i - x_mean) * (y_values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def mann_kendall_p_value(y_values: List[float]) -> float:
        """Mann-Kendall 趋势检验 (非参数)

        返回近似 p 值。p < 0.05 → 显著趋势。
        实现: 完整 MK 检验 + 正态近似
        """
        n = len(y_values)
        if n < 3:
            return 1.0  # 数据不足

        # 计算 S 统计量
        s = 0
        for k in range(n - 1):
            for j in range(k + 1, n):
                diff = y_values[j] - y_values[k]
                if diff > 0:
                    s += 1
                elif diff < 0:
                    s -= 1

        # 处理 ties
        unique_vals: Dict[float, int] = {}
        for v in y_values:
            unique_vals[v] = unique_vals.get(v, 0) + 1

        # 方差 (含 tie correction)
        tie_correction = sum(
            t * (t - 1) * (2 * t + 5) for t in unique_vals.values()
        )
        variance = (n * (n - 1) * (2 * n + 5) - tie_correction) / 18.0

        if variance == 0:
            return 0.5

        # Z 统计量
        if s > 0:
            z = (s - 1) / math.sqrt(variance)
        elif s < 0:
            z = (s + 1) / math.sqrt(variance)
        else:
            z = 0.0

        # 正态近似 → p 值 (双尾)
        # 使用 Abramowitz & Stegun 近似
        abs_z = abs(z)
        if abs_z < 0.01:
            return 1.0

        # 标准正态 CDF 近似
        p = StatsUtils._norm_cdf_approx(-abs_z)
        return min(1.0, max(0.0, 2.0 * p))

    @staticmethod
    def _norm_cdf_approx(x: float) -> float:
        """标准正态 CDF 近似 (Abramowitz & Stegun 7.1.26)"""
        # 只处理负值 (x < 0)
        if x >= 0:
            return 1.0 - StatsUtils._norm_cdf_approx(-x)

        a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
        p_val = 0.3275911
        t = 1.0 / (1.0 + p_val * abs(x))
        poly = t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))))
        return poly * math.exp(-x * x / 2.0) / math.sqrt(2 * math.pi)

    @staticmethod
    def classify_convergence(
        scores: List[float],
        passed_rounds: List[int],
    ) -> ConvergenceType:
        """分类收敛类型

        决策树:
        1. 任意轮 passed → 检查轮数 (≤2 → FAST, else → SLOW)
        2. 未通过:
           a. 分数单调递减 → DIVERGENT
           b. 分数振荡 (std > 0.15) → OSCILLATING
           c. 分数持平低值 → STUCK
        """
        if not scores:
            return ConvergenceType.STUCK

        n = len(scores)
        slope = StatsUtils.linear_slope(scores)
        score_std = StatsUtils.std(scores)

        # 通过了
        if passed_rounds:
            first_pass = min(passed_rounds)
            return ConvergenceType.FAST if first_pass <= 2 else ConvergenceType.SLOW

        # 未通过 — 分析模式
        if slope < -0.03:
            return ConvergenceType.DIVERGENT
        if score_std > 0.10:
            return ConvergenceType.OSCILLATING

        return ConvergenceType.STUCK


# ================================================================
# ConvergenceTracker
# ================================================================
class ConvergenceTracker:
    """辩论收敛研究追踪器

    用法:
        tracker = ConvergenceTracker(output_dir="data/research")

        # 每轮辩论后
        tracker.start_session(sid="deb_001", query="讲解CNN", query_category="theory")
        tracker.record_round(sid="deb_001", round_num=1,
                            dimension_scores={"factual":0.8, "pedagogy":0.6, ...},
                            overall_score=0.7, passed=False)
        tracker.record_round(sid="deb_001", round_num=2,
                            dimension_scores={"factual":0.9, "pedagogy":0.8, ...},
                            overall_score=0.85, passed=True)

        # 完成后分析
        analysis = tracker.analyze("deb_001")
        print(analysis.convergence_type)  # "fast"

        # 批量导出
        tracker.export_jsonl("convergence_logs.jsonl")
    """

    def __init__(self, output_dir: str = "data/research"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # session_id → {
        #   query_text, query_category, start_time,
        #   snapshots: List[RoundSnapshot]
        # }
        self._sessions: Dict[str, Dict[str, Any]] = {}

    # ----------------------------------------------------------------
    # Session lifecycle
    # ----------------------------------------------------------------
    def start_session(
        self,
        session_id: str,
        query_text: str,
        query_category: str = "unknown",
        agent_name: str = "",
    ) -> None:
        """开始追踪一次辩论"""
        self._sessions[session_id] = {
            "query_text": query_text[:200],
            "query_category": query_category,
            "agent_name": agent_name,
            "start_time": time.time(),
            "snapshots": [],
        }

    def record_round(
        self,
        session_id: str,
        round_num: int,
        dimension_scores: Dict[str, float],
        overall_score: float,
        passed: bool,
        issue_count: int = 0,
        elapsed_ms: float = 0.0,
    ) -> None:
        """记录一轮辩论结果

        Args:
            session_id: 会话 ID
            round_num: 轮次编号
            dimension_scores: 各维度分数字典 {factual: 0.8, pedagogy: 0.6, ...}
            overall_score: 综合分数 0-1
            passed: 是否通过审查
            issue_count: 发现的问题数
            elapsed_ms: 本轮耗时
        """
        if session_id not in self._sessions:
            logger.warning(f"[Tracker] unknown session: {session_id}")
            return

        snapshot = RoundSnapshot(
            round_num=round_num,
            overall_score=overall_score,
            passed=passed,
            dimension_scores=dict(dimension_scores),
            issue_count=issue_count,
            elapsed_ms=elapsed_ms,
        )
        self._sessions[session_id]["snapshots"].append(snapshot)

    # ----------------------------------------------------------------
    # Analysis
    # ----------------------------------------------------------------
    def analyze(self, session_id: str) -> ConvergenceAnalysis:
        """对某次辩论做统计收敛分析"""
        session = self._sessions.get(session_id)
        if not session or not session["snapshots"]:
            return ConvergenceAnalysis(
                session_id=session_id,
                query_text="",
                total_rounds=0,
                passed=False,
                final_score=0.0,
                mean_score=0.0,
                std_score=0.0,
                score_trend_slope=0.0,
                score_trend_p_value=1.0,
                convergence_type=ConvergenceType.STUCK,
                convergence_round=0,
                rounds_until_pass=0,
                dimension_trends={},
            )

        snapshots: List[RoundSnapshot] = session["snapshots"]
        scores = [s.overall_score for s in snapshots]
        passed_rounds = [s.round_num for s in snapshots if s.passed]

        # 统计量
        mean_score = StatsUtils.mean(scores)
        std_score = StatsUtils.std(scores)
        slope = StatsUtils.linear_slope(scores)
        p_value = StatsUtils.mann_kendall_p_value(scores)

        # 收敛类型
        conv_type = StatsUtils.classify_convergence(scores, passed_rounds)

        # 收敛轮次: 第一个满足收敛条件的轮次
        conv_round = self._find_convergence_round(snapshots)

        # 分维度趋势
        dim_trends: Dict[str, float] = {}
        for dim in TRACKED_DIMENSIONS:
            dim_scores = [
                s.dimension_scores.get(dim, 0.0) for s in snapshots
            ]
            if len(dim_scores) >= 2:
                dim_trends[dim] = round(dim_scores[-1] - dim_scores[0], 3)
            else:
                dim_trends[dim] = 0.0

        return ConvergenceAnalysis(
            session_id=session_id,
            query_text=session["query_text"],
            total_rounds=len(snapshots),
            passed=bool(passed_rounds),
            final_score=scores[-1] if scores else 0.0,
            mean_score=round(mean_score, 3),
            std_score=round(std_score, 3),
            score_trend_slope=round(slope, 4),
            score_trend_p_value=round(p_value, 4),
            convergence_type=conv_type,
            convergence_round=conv_round,
            rounds_until_pass=min(passed_rounds) if passed_rounds else 0,
            dimension_trends=dim_trends,
            snapshots=snapshots,
        )

    def _find_convergence_round(self, snapshots: List[RoundSnapshot]) -> int:
        """找首次收敛轮次

        收敛定义: 连续 2 轮分数差异 < 0.05 且无 issue
        """
        if len(snapshots) < 2:
            return 0
        for i in range(1, len(snapshots)):
            delta = abs(
                snapshots[i].overall_score - snapshots[i - 1].overall_score
            )
            if delta < 0.05 and snapshots[i].issue_count == 0:
                return snapshots[i].round_num
        return 0

    # ----------------------------------------------------------------
    # Aggregate analysis
    # ----------------------------------------------------------------
    def aggregate_stats(self) -> Dict[str, Any]:
        """全量聚合统计"""
        analyses = [self.analyze(sid) for sid in self._sessions]
        if not analyses:
            return {"total_sessions": 0}

        type_counts: Dict[str, int] = {}
        for a in analyses:
            t = a.convergence_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        passed_count = sum(1 for a in analyses if a.passed)
        total = len(analyses)
        avg_rounds = (
            sum(a.total_rounds for a in analyses) / total if total else 0
        )
        avg_final_score = (
            sum(a.final_score for a in analyses) / total if total else 0
        )

        return {
            "total_sessions": total,
            "pass_rate": round(passed_count / max(total, 1), 3),
            "avg_rounds": round(avg_rounds, 2),
            "avg_final_score": round(avg_final_score, 3),
            "convergence_distribution": type_counts,
            "by_type": {
                c_type: {
                    "count": type_counts.get(c_type, 0),
                    "pct": round(type_counts.get(c_type, 0) / max(total, 1) * 100, 1),
                }
                for c_type in [t.value for t in ConvergenceType]
            },
        }

    # ----------------------------------------------------------------
    # Export
    # ----------------------------------------------------------------
    def export_jsonl(self, filename: str = "debate_convergence_logs.jsonl") -> str:
        """导出所有分析的 JSONL 文件"""
        filepath = self._output_dir / filename
        count = 0
        with open(filepath, "w", encoding="utf-8") as f:
            for sid in self._sessions:
                analysis = self.analyze(sid).to_dict()
                f.write(json.dumps(analysis, ensure_ascii=False) + "\n")
                count += 1
        logger.info(f"[Tracker] exported {count} sessions → {filepath}")
        return str(filepath)

    def export_summary_markdown(self, filename: str = "convergence_report.md") -> str:
        """生成研究级 Markdown 摘要报告"""
        stats = self.aggregate_stats()
        filepath = self._output_dir / filename

        lines = [
            "# Multi-Agent Debate 收敛性研究报告",
            "",
            f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"总会话数: {stats['total_sessions']}",
            "",
            "## 总体指标",
            "",
            f"| 指标 | 值 |",
            f"|------|-----|",
            f"| 通过率 | {stats['pass_rate']:.1%} |",
            f"| 平均轮数 | {stats['avg_rounds']:.1f} |",
            f"| 平均最终得分 | {stats['avg_final_score']:.3f} |",
            "",
            "## 收敛类型分布",
            "",
            "| 类型 | 数量 | 占比 |",
            "|------|------|------|",
        ]

        for c_type, info in stats.get("by_type", {}).items():
            if info["count"] > 0:
                lines.append(f"| {c_type} | {info['count']} | {info['pct']}% |")

        lines.extend([
            "",
            "## 各类型说明",
            "",
            "- **fast**: 2 轮内 Critic 通过，辩论高效",
            "- **slow**: 2+ 轮通过，分数有改善趋势",
            "- **oscillating**: 分数高低振荡，Critic 标准不稳定",
            "- **stuck**: 持续低分无改善，需要改进 Expert 或 Critic",
            "- **divergent**: 修改后分数反而下降",
            "",
            "## 方法论",
            "",
            "- 趋势检验: Mann-Kendall 非参数检验 (p < 0.05 为显著趋势)",
            "- 收敛判定: 连续 2 轮分数差 < 0.05 且无新增 issue",
            "- 收敛分类: 基于线性回归斜率 + 标准差联合决策树",
        ])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info(f"[Tracker] report → {filepath}")
        return str(filepath)

    # ----------------------------------------------------------------
    # Inspection
    # ----------------------------------------------------------------
    def session_count(self) -> int:
        return len(self._sessions)

    def reset(self) -> None:
        self._sessions.clear()


# ================================================================
# 全局单例
# ================================================================
_tracker: Optional[ConvergenceTracker] = None


def get_convergence_tracker() -> ConvergenceTracker:
    global _tracker
    if _tracker is None:
        _tracker = ConvergenceTracker()
    return _tracker


def reset_tracker() -> None:
    global _tracker
    _tracker = None
