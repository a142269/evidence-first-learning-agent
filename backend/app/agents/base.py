"""
Agent 基类 —— 所有智能体的统一接口

设计原则（迁移自旧项目 services/ 的分层设计）：
- 每个 Agent 是独立的功能单元，封装自己的 Prompt + LLM 调用 + 输出格式化
- 通过 Orchestrator 协调调用，Agent 之间不直接耦合
- 标准输入/输出协议，便于扩展新 Agent

P1-7 升级:
- 新增 reflect() 默认方法 — 调 Reflector 跑 Bloom-aware Self-Refine
- 新增 prompt_version 类属性 — 便于 prompt A/B 实验
"""
from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from backend.app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Agent 执行上下文 —— 包含画像、对话历史、课程信息等"""
    user_input: str = ""
    session_id: str = ""
    profile: dict = field(default_factory=dict)
    course_name: str = ""
    conversation_history: list = field(default_factory=list)
    rag_results: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    @property
    def user_id(self) -> str:
        """真实学生 ID（FIX-03，2026-07-17）。

        编排阶段会把登录学生 ID 注入 extra["user_id"]；查询 BKT/RealDINA 等
        认知状态必须用它，禁止直接用 session_id（同一学生换会话会读不到状态）。
        缺失时回退 session_id 以兼容旧调用。
        """
        return str((self.extra or {}).get("user_id") or self.session_id or "default")


@dataclass
class AgentResponse:
    """Agent 统一输出"""
    agent_name: str
    success: bool
    content: str = ""                      # 主要文本输出
    content_type: str = "text"             # text / markdown / json / mindmap / quiz / code
    resources: list = field(default_factory=list)  # 生成的资源列表
    profile_updates: dict = field(default_factory=dict)  # 画像更新建议
    metadata: dict = field(default_factory=dict)
    error: str = ""


class BaseAgent(ABC):
    """
    智能体基类

    每个 Agent 需实现:
    1. name: 智能体名称
    2. description: 功能描述（用于 Orchestrator 路由决策）
    3. system_prompt: 系统提示词
    4. execute(): 核心执行逻辑

    可选覆盖:
    5. prompt_version: prompt 当前版本号 (默认 "v1")
    6. reflect():     反思方法 (默认实现走 Reflector + bloom_aware 策略)
    """

    # P1-7: 子类可覆盖以标记 prompt 版本, 便于 A/B 实验和回滚
    prompt_version: str = "v1"

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    @property
    @abstractmethod
    def name(self) -> str:
        """智能体名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """功能描述"""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """系统提示词"""
        ...

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行核心逻辑"""
        ...

    # ================================================================
    # 通用工具方法
    # ================================================================
    def _build_messages(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
    ) -> List[Dict[str, str]]:
        """构建标准 messages 列表"""
        system_content = self.system_prompt
        if extra_system:
            system_content += "\n" + extra_system

        messages = [{"role": "system", "content": system_content}]

        if history:
            for h in history[-10:]:  # 最多保留5轮历史
                messages.append({"role": h["role"], "content": h["content"]})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _call_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """调用 LLM 并返回文本"""
        messages = self._build_messages(user_prompt, history, extra_system)
        return self.llm.chat(messages, temperature=temperature)

    async def _acall_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """Plan D 2.2 — 异步调用 LLM

        内部委托 self.llm.achat()，避免在 async execute() 中同步阻塞事件循环
        （让 asyncio.gather 退化为串行）。

        兼容性：如果 self.llm.achat 不是 async coroutine（MagicMock / 老 Mock），
        自动 fallback 到 _call_llm 同步版本。
        """
        achat = getattr(self.llm, "achat", None)
        if achat is None or not inspect.iscoroutinefunction(achat):
            # MagicMock / 老 Mock 兼容：fallback 到同步路径
            return self._call_llm(
                user_prompt,
                history=history,
                extra_system=extra_system,
                temperature=temperature,
            )
        messages = self._build_messages(user_prompt, history, extra_system)
        return await achat(messages, temperature=temperature)

    async def _acall_llm_stream(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ):
        """Plan D 2.2 — 异步流式 LLM 调用

        供 tutor_agent 等需要把 LLM 输出逐 chunk yield 给 SSE 的 Agent 用。
        """
        messages = self._build_messages(user_prompt, history, extra_system)
        async for chunk in self.llm.chat_stream(
            messages, temperature=temperature
        ):
            yield chunk

    def _strategy_extra_system(self, context: "AgentContext") -> str:
        """把 Orchestrator 注入的实时学情策略并入 system_prompt"""
        try:
            extra = context.extra or {}
            return str(extra.get("strategy_prompt") or "")
        except Exception:
            return ""

    def _success(self, content: str, content_type: str = "markdown", **kwargs) -> AgentResponse:
        """快捷构建成功响应"""
        return AgentResponse(
            agent_name=self.name,
            success=True,
            content=content,
            content_type=content_type,
            **kwargs,
        )

    def _error(self, error_msg: str) -> AgentResponse:
        """快捷构建错误响应"""
        return AgentResponse(
            agent_name=self.name,
            success=False,
            error=error_msg,
        )

    # ================================================================
    # P1-7: 反思 (Reflexion)
    # ================================================================
    async def reflect(
        self,
        content: str,
        context: "AgentContext",
        *,
        strategy: Optional[str] = None,
        max_iterations: int = 1,
        pass_threshold: float = 0.7,
        use_llm_revise: bool = False,
    ) -> Dict[str, Any]:
        """对 execute() 输出做一轮反思

        默认策略: bloom_aware (A3 原创, 见 reflection/strategies/bloom_aware.py)

        Args:
            content:        待反思内容 (通常是 execute() 的 content)
            context:        AgentContext (取 bloom_target / rag_results)
            strategy:       策略名 (None = 默认 bloom_aware)
            max_iterations: 最大反思轮数
            pass_threshold: 通过分数
            use_llm_revise: 是否调 LLM 重写 (False = 规则修订 + 追加建议)

        Returns:
            dict — Trace.to_dict() 输出, 兼容旧 Pipeline 期望:
                {needs_rewrite, improved_draft, issues, rounds,
                 best_score, reasoning_chain, ...}
        """
        from backend.app.agents.reflection import get_reflector

        bloom_target = (
            context.extra.get("target_bloom")
            or context.extra.get("bloom_target")
            or "understand"
        )
        rag_results = context.rag_results or []

        reflector = get_reflector()
        trace = await reflector.run(
            content=content,
            agent_name=self.name,
            prompt_version=self.prompt_version,
            bloom_target=bloom_target,
            strategy=strategy,
            max_iterations=max_iterations,
            pass_threshold=pass_threshold,
            use_llm_revise=use_llm_revise,
            rag_results=rag_results,
            llm_client=self.llm,
        )
        return trace.to_dict()
