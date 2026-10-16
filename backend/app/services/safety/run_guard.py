"""Deterministic pre-retrieval guard for evidence-first learning runs.

This guard is intentionally conservative and runs before retrieval, tools or
the model.  It is not a replacement for authentication/authorization; it
prevents common prompt-injection and data-exfiltration phrasing from becoming
an alternate route into course evidence while those identity controls evolve.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class GuardDecision:
    blocked: bool
    category: str = ""


class LearningRunGuard:
    """Block unsafe requests without exposing policy details to the caller."""

    _PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "prompt_injection",
            (
                r"忽略.{0,30}(?:规则|指令|提示)",
                r"ignore\s+(?:all\s+)?(?:previous|prior).{0,40}(?:instruction|rule|prompt)",
                r"(?:不要|无需).{0,20}(?:引用|遵守).{0,30}(?:编造|虚构)",
                r"(?:系统提示词|system\s*prompt|隐藏指令)",
            ),
        ),
        (
            "data_exfiltration",
            (
                r"(?:其他|别的).{0,30}(?:教师|学生|课程).{0,30}(?:资料|文档|数据)",
                r"(?:私有资料|历史聊天记录)",
                r"(?:admin|管理员).{0,30}(?:画像|聊天|记录)",
                r"(?:展示|输出).{0,30}(?:学习画像|聊天记录)",
            ),
        ),
        (
            "unsupported_write",
            (
                r"(?:更新|修改|写入|永久保存).{0,40}(?:画像|档案|教学目标|偏好)",
                r"(?:画像|偏好|标签).{0,30}(?:更新|修改|写入|永久保存)",
                r"(?:发布|发送|通知).{0,40}(?:学生|全班|知识库|课程|计划)",
                r"(?:资料|建议|计划|通知).{0,30}(?:发布|发送)",
                r"(?:向|给).{0,20}(?:全班|所有学生).{0,20}(?:发送|通知)",
            ),
        ),
        (
            "unsafe_operation",
            (
                r"(?:未授权工具|删除).{0,40}(?:知识库|资料|文档)",
                r"(?:导出|分享).{0,40}(?:外部|邮箱)",
                r"(?:诊断).{0,30}(?:疾病|病情)|(?:处方|开药)",
                r"(?:期末|考试).{0,20}(?:答案|试卷)",
                r"20(?:2[7-9]|3\d).{0,30}诺贝尔",
            ),
        ),
    )

    def decide(self, message: str) -> GuardDecision:
        normalized = " ".join(str(message).lower().split())
        for category, patterns in self._PATTERNS:
            if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
                return GuardDecision(blocked=True, category=category)
        return GuardDecision(blocked=False)


def get_learning_run_guard() -> LearningRunGuard:
    return LearningRunGuard()
