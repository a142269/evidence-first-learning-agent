"""
Intent Classifier — LLM 驱动的意图分类兜底服务

设计:
- 仅当 Orchestrator 关键词匹配失败时调用
- 轻量 prompt：单次 LLM 调用，不做多轮
- 2 秒超时 + 失败静默降级（返回空列表）
- 输出严格校验：只允许已知 intent 名

集成点:
    orchestrator._llm_classify_intent() → IntentClassifier.classify()

Phase 2 计划: 用标注数据训练轻量分类器（BERT-tiny），替代 LLM 调用
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 已知意图及其描述（给 LLM 做 few-shot）
INTENT_DESCRIPTIONS: Dict[str, str] = {
    "generate_doc":       "用户想学习某个知识点/概念，期望得到讲解文档",
    "generate_mindmap":   "用户想要思维导图/知识图谱/脑图",
    "generate_exercise":  "用户想要练习题/测试/习题",
    "generate_reading":   "用户想要拓展阅读/延伸材料/参考文献",
    "plan_path":          "用户想要学习计划/学习路径/下一步学什么",
    "tutoring":           "用户在提问/不懂/需要答疑解惑",
    "evaluation":         "用户想评估水平/测试掌握度/了解进度",
}

CLASSIFY_PROMPT = """你是一个教育系统的意图分类器。

用户输入: "{user_input}"

请判断用户意图属于以下哪几类（可多选，只输出 JSON 数组）:

1. generate_doc       - 想学某个知识点，需要讲解文档
2. generate_mindmap   - 想要思维导图/脑图
3. generate_exercise  - 想要练习题/测试/习题
4. generate_reading   - 想要拓展阅读/延伸材料
5. plan_path          - 想要学习计划/路径/下一步
6. tutoring           - 在提问/不懂/需要答疑
7. evaluation         - 想评估水平/测试掌握度

如果用户输入与学习无关（聊天/天气/闲聊），返回空数组 []。

只输出 JSON 数组，不要其他文字:
例如: ["generate_doc", "generate_exercise"]
或: []"""


class IntentClassifier:
    """LLM 意图分类器

    用法:
        classifier = IntentClassifier(llm_client)
        intents = await classifier.classify("给我讲解CNN然后出几道题")
        # → ["generate_doc", "generate_exercise"]
    """

    def __init__(self, llm_client: Any):
        self._llm = llm_client
        self._valid_intents = set(INTENT_DESCRIPTIONS.keys())

    async def classify(
        self,
        user_input: str,
        *,
        timeout: float = 3.0,
    ) -> List[str]:
        """分类用户意图

        Args:
            user_input: 用户原始输入
            timeout: LLM 调用超时（秒）

        Returns:
            意图列表（已过滤无效值），LLM 失败时返回 []
        """
        if not user_input or not user_input.strip():
            return []

        prompt = CLASSIFY_PROMPT.format(user_input=user_input.strip()[:500])

        try:
            raw = await asyncio.wait_for(
                self._call_llm(prompt),
                timeout=timeout,
            )
            intents = self._parse(raw)
            logger.info(
                f"[IntentClassifier] input={user_input[:40]}... → {intents}"
            )
            return intents
        except asyncio.TimeoutError:
            logger.warning(
                f"[IntentClassifier] timeout after {timeout}s "
                f"for: {user_input[:40]}..."
            )
            return []
        except Exception as exc:
            logger.warning(
                f"[IntentClassifier] LLM call failed: {exc} "
                f"for: {user_input[:40]}..."
            )
            return []

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（兼容同步/异步两种 LLMClient 接口）"""
        messages = [
            {"role": "system", "content": "你是一个精确的 JSON 输出器。只输出 JSON 数组，不说其他话。"},
            {"role": "user", "content": prompt},
        ]

        # 尝试异步接口
        if hasattr(self._llm, "achat"):
            return await self._llm.achat(messages, temperature=0.1, max_tokens=128)
        # 退化到同步接口
        if hasattr(self._llm, "chat"):
            return self._llm.chat(messages, temperature=0.1, max_tokens=128)
        # 无 LLM → 回退到关键词规则
        return "[]"

    def _parse(self, raw: str) -> List[str]:
        """解析 LLM 输出为意图列表

        处理常见 LLM 输出格式:
        - ["generate_doc"]
        - ```json\n["generate_doc"]\n```
        - 纯文本中提取 JSON 数组
        """
        if not raw:
            return []

        raw = raw.strip()

        # 去掉 markdown 代码块包裹
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
        if code_block:
            raw = code_block.group(1).strip()

        # 尝试直接解析
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return self._validate(result)
        except json.JSONDecodeError:
            pass

        # 尝试从文本中提取 JSON 数组
        array_match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if array_match:
            try:
                result = json.loads(array_match.group(0))
                if isinstance(result, list):
                    return self._validate(result)
            except json.JSONDecodeError:
                pass

        logger.debug(f"[IntentClassifier] 无法解析 LLM 输出: {raw[:200]}")
        return []

    def _validate(self, intents: List[Any]) -> List[str]:
        """过滤无效意图，去重"""
        valid: List[str] = []
        seen: set = set()
        for item in intents:
            if not isinstance(item, str):
                continue
            item = item.strip().lower()
            if item in self._valid_intents and item not in seen:
                valid.append(item)
                seen.add(item)
        return valid


# ================================================================
# 全局单例
# ================================================================
_classifier: Optional[IntentClassifier] = None


def get_intent_classifier(llm_client: Any = None) -> IntentClassifier:
    """获取 IntentClassifier 单例"""
    global _classifier
    if _classifier is None:
        if llm_client is None:
            from backend.app.core.llm_client import LLMClient
            llm_client = LLMClient()
        _classifier = IntentClassifier(llm_client)
    return _classifier


def reset_classifier() -> None:
    """测试用：重置单例"""
    global _classifier
    _classifier = None
