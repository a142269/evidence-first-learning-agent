"""SafeDeclineAgent — 教学边界守门 Agent (Plan D · Review 修复 v1)

场景：当 Orchestrator 识别到学生问的是"闲聊 / 越界 / 与学习无关"的问题时，
不要把请求扔进 tutoring Agent 浪费 LLM token + 让学生得到跑题回答。

策略
=====
1. **不调用 LLM** —— 这是个模板化降级，回复固定礼貌文案 + 引导回学习
2. **不更新画像** —— 闲聊不污染 profile
3. **不进入辩论 / 反思** —— priority=0，跳过 Orchestrator 重量级流程

设计依据
=========
* 评审现场被调戏"今天天气怎么样" / "你叫什么"时不会翻车
* Phase 2 可让 LLM 生成"委婉话术"应对敏感话题；但教学边界通常是机械判定，没必要调 LLM
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict

from backend.app.agents.base import AgentContext, AgentResponse, BaseAgent

logger = logging.getLogger(__name__)


# 礼貌拒绝话术池 — 随机抽 1 条避免重复
_DECLINE_PHRASES = [
    "这是个好问题，不过它不在我们 A3 的学习范围里。要不要换个 AI / 课程相关的话题？例如「什么是自注意力」或「给我出一题 CNN 练习」？",
    "这个问题我没法帮上忙——A3 是你的 AI 学习伙伴，专注在课程和练习方向。试试问我一个学习相关的问题，比如「帮我整理一下 CNN 的笔记」？",
    "聊点别的吧。这个问题超出了 A3 的学习范围，我可以帮你：① 梳理章节笔记 ② 出练习题 ③ 规划今日学习路径。你想先做哪个？",
    "A3 这边不回答这个问题。你可以换个跟 AI / 数据科学 / 课程相关的问题，例如「什么是 BKT」「评估下我今天的学习」。",
    "我注意到这是个非学习类问题。A3 的任务是陪你学好 AI，不适合这场对话。重新发一句跟学习相关的提问吧，我很乐意帮忙。",
]

# 若 out_of_scope 同时含敏感词（涉政 / 涉黄 / 自残），用更短的强拒
_HARD_DECLINE_PHRASES = [
    "这条问题我没法回应。",
    "这个问题不在 A3 的应答范围内。",
    "抱歉，这个方向 A3 不接受。",
]

# Plan D · Review v1 — 敏感词表（演示时常见试探）
_HARD_KEYWORDS = [
    "邪教", "法轮", "政权", "颠覆", "色情", "裸聊", "约炮",
    "自残", "自杀", "想死", "毒品", "冰毒", "海洛因",
]


class SafeDeclineAgent(BaseAgent):
    """教学边界守门 Agent — 模板化礼貌拒绝 + 引导回学习

    name : "safe_decline"
    description : "处理 out_of_scope / 越界 / 闲聊 请求，礼貌拒绝并引导学生回到学习"
    """

    name = "safe_decline"
    description = (
        "教学边界守门 Agent — 识别 out_of_scope / 闲聊 / 越界类问题，"
        "礼貌拒绝并引导学生回到课程或练习相关的提问"
    )

    # Plan D · Review v1 — 不调 LLM，使用 prompt_version 锁定未来 A/B
    prompt_version = "v1"

    @property
    def system_prompt(self) -> str:
        return ""

    async def execute(self, ctx: AgentContext) -> AgentResponse:
        text = (ctx.user_input or "").strip()
        lowered = text.lower()

        # 1) 敏感词命中 → 硬拒（最短回复）
        if any(bad in text for bad in _HARD_KEYWORDS):
            reply = random.choice(_HARD_DECLINE_PHRASES)
            tone = "hard_decline"
        else:
            reply = random.choice(_DECLINE_PHRASES)
            tone = "soft_decline"

        logger.info(
            f"[SafeDeclineAgent] decline user_input_len={len(text)} tone={tone}"
        )

        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=reply,
            content_type="text",
            resources=[],
            profile_updates={},  # 不污染画像
            metadata={
                "decline_tone": tone,
                "agent": self.name,
                "prompt_version": self.prompt_version,
                "rationale": "out_of_scope detected by orchestrator routing",
            },
        )

    async def reflect(  # noqa: D401 — FIX-12：与 BaseAgent.reflect 异步签名保持一致
        self,
        content: str,
        context: "AgentContext",
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        """SafeDeclineAgent 永远不参与反思 — 模板回复不需要质量审查。

        FIX-12（2026-07-17）：旧签名 ``def reflect(self, ctx)`` 与基类
        ``async def reflect(self, content, context, ...)`` 不兼容，反思阶段
        调用会抛 TypeError；改为同签名异步空操作，返回兼容 Pipeline 的结构。
        """
        return {
            "skipped": True,
            "needs_rewrite": False,
            "improved_draft": content,
            "issues": [],
            "rounds": 0,
            "best_score": 1.0,
            "reason": "safe_decline templates need no reflection",
        }
