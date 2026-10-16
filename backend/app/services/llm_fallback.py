"""
LLM 多通道降级路由增强
借鉴自: NPUYUN/LearnPath 的 fallback chain 设计

核心能力：主模型失败时自动降级到备用模型
路由链：Kimi(优先) → 星火 → 辅助模型 → Mock兜底

使用方式：
  from backend.app.services.llm_fallback import LLMFallbackRouter
  router = LLMFallbackRouter()
  result = await router.chat_with_fallback(messages)
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Dict, Optional

from backend.app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class LLMFallbackRouter:
    """
    LLM 降级路由器

    当主模型调用失败时，自动尝试备用模型。
    每个通道有独立的超时和重试策略。
    """

    # 通道优先级配置
    CHANNELS = [
        {
            "name": "kimi",
            "provider_key": "openai_compatible",
            "check_env": "KIMI_API_KEY",
            "label": "Kimi (Moonshot)",
        },
        {
            "name": "spark",
            "provider_key": "spark",
            "check_env": "SPARK_API_KEY",
            "label": "讯飞星火",
        },
        {
            "name": "modelscope",
            "provider_key": "modelscope_http",
            "check_env": "MODELSCOPE_API_KEY",
            "label": "ModelScope/SiliconFlow",
        },
        {
            "name": "auxiliary",
            "provider_key": "openai_compatible",
            "check_env": "AUX_LLM_API_KEY",
            "label": "辅助云端模型",
        },
        {
            "name": "mock",
            "provider_key": "mock",
            "check_env": None,
            "label": "Demo 模式",
        },
    ]

    def __init__(self):
        self.llm = LLMClient()

    async def chat_with_fallback(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_per_channel: int = 30,
    ) -> tuple[str, str]:
        """
        带降级链的异步聊天

        Returns:
            (content, provider_used): 回复内容和实际使用的模型名称
        """
        import os

        for channel in self.CHANNELS:
            channel_name = channel["name"]

            # Mock 通道无条件可用
            if channel_name == "mock":
                logger.info("所有模型不可用，使用 Demo 模式")
                result = self._mock_fallback(messages)
                return result, "mock"

            # 检查环境变量
            env_key = channel["check_env"]
            if env_key and not os.getenv(env_key):
                logger.debug(f"跳过 {channel['label']}: {env_key} 未配置")
                continue

            try:
                logger.info(f"尝试使用 {channel['label']}...")

                # ModelScope 走专用 HTTP 客户端（移植自老项目）
                if channel_name == "modelscope":
                    result = await asyncio.wait_for(
                        self._call_modelscope(messages, temperature, max_tokens),
                        timeout=timeout_per_channel,
                    )
                else:
                    result = await asyncio.wait_for(
                        self.llm.achat(messages, temperature, max_tokens),
                        timeout=timeout_per_channel,
                    )

                # 检查结果是否有效（非空，非错误前缀）
                if result and not result.startswith("[API_ERROR]") and not result.startswith("[ERROR]"):
                    logger.info(f"{channel['label']} 调用成功")
                    return result, channel_name
                else:
                    logger.warning(f"{channel['label']} 返回无效结果: {result[:100]}")

            except asyncio.TimeoutError:
                logger.warning(f"{channel['label']} 超时 ({timeout_per_channel}s)")
            except Exception as e:
                logger.warning(f"{channel['label']} 调用失败: {e}")

        # 所有通道都失败，最终兜底
        logger.error("所有 LLM 通道均失败")
        return self._mock_fallback(messages), "mock"

    async def _call_modelscope(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> str:
        """ModelScope HTTP 通道（移植自老项目纯标准库实现）"""
        import os

        from backend.app.services.llm_modelscope_client import ModelScopeLLMClient

        base_url = os.getenv("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1")
        api_key = os.getenv("MODELSCOPE_API_KEY", "")
        model = os.getenv("MODELSCOPE_MODEL", "qwen/Qwen2.5-72B-Instruct")
        if not api_key:
            return "[API_ERROR] ModelScope key 未配置"

        client = ModelScopeLLMClient(base_url=base_url, api_key=api_key, timeout=30)

        # 在线程池里跑同步 HTTP，避免阻塞 event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: client.chat(
                model=model,
                messages=messages,
                temperature=temperature if temperature is not None else 0.3,
                max_tokens=max_tokens if max_tokens is not None else 4096,
            ),
        )

    def _mock_fallback(self, messages: List[Dict]) -> str:
        """Demo 模式兜底回复"""
        last_msg = messages[-1]["content"] if messages else "你好"
        return (
            f"【演示模式】收到您的消息：「{last_msg[:100]}」\n\n"
            f"系统当前运行在演示模式。请配置以下任一 API 密钥以启用 AI 回复：\n"
            f"1. 在 .env 中设置 KIMI_API_KEY（推荐，效果最好）\n"
            f"2. 设置 SPARK_API_KEY（讯飞星火）\n"
            f"3. 设置 AUX_LLM_API_KEY + AUX_LLM_BASE_URL（任意 OpenAI 兼容接口）\n\n"
            f"配置后重启服务即可。"
        )


# 全局单例
_router: Optional[LLMFallbackRouter] = None


def get_fallback_router() -> LLMFallbackRouter:
    global _router
    if _router is None:
        _router = LLMFallbackRouter()
    return _router
