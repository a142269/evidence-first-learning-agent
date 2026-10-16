"""
LLM 客户端统一封装
支持讯飞星火 / OpenAI 兼容接口的统一调用
迁移自旧项目 services/reports/llm_service.py 的 ModelScopeLLMClient 设计
"""
from __future__ import annotations

import json
import logging
import hashlib
import hmac
import base64
import time
from datetime import datetime
from urllib.parse import urlencode, urlparse
from typing import List, Dict, Optional, AsyncGenerator

logger = logging.getLogger(__name__)


def create_xunfei_spark_client(*, allow_local_fallback: bool = False) -> "LLMClient":
    """创建媒体生成专用的讯飞星火客户端。

    该工厂不会继承全局 ``LLM_PROVIDER=deepseek``。PPT、视频及 Manim
    降级链统一从这里取客户端，从结构上阻止媒体生成误走 OpenAI-compatible
    接口。讯飞不可用时可选择一个纯本地 mock 客户端，让上层模板降级。
    """
    from dataclasses import replace

    from backend.app.core.config import get_config

    config = get_config().llm
    has_credentials = bool(
        config.spark_app_id
        and config.spark_api_key
        and config.spark_api_secret
    )
    spark_config = replace(config, provider_override="spark")
    if has_credentials and spark_config.provider == "spark":
        return LLMClient(config=spark_config)
    if not allow_local_fallback:
        if not has_credentials:
            raise RuntimeError("科大讯飞星火凭据未配置")
        raise RuntimeError("科大讯飞星火当前处于离线禁用状态")

    local_config = replace(
        config,
        provider_override="none",
        openai_base_url="",
        openai_api_key="",
    )
    return LLMClient(config=local_config)


def create_deepseek_outline_client(*, allow_local_fallback: bool = False) -> "LLMClient":
    """创建 PPT 叙事大纲专用的 DeepSeek 客户端。

    复用全局 DeepSeek/OpenAI-compatible 凭据，但强制 JSON 输出；只负责教学
    结构、事实边界和逐页叙事，不承担最终视觉页面文案。
    """
    from dataclasses import replace

    from backend.app.core.config import get_config

    config = get_config().llm
    available = bool(config.openai_base_url and config.openai_api_key and config.openai_model)
    if not available:
        if allow_local_fallback:
            return LLMClient(config=replace(
                config,
                provider_override="none",
                openai_base_url="",
                openai_api_key="",
                openai_model="",
            ))
        raise RuntimeError("DeepSeek 大纲服务未配置完整")

    outline_config = replace(
        config,
        provider_override="openai_compatible",
        openai_extra_body={"response_format": {"type": "json_object"}},
    )
    if outline_config.provider != "openai_compatible":
        raise RuntimeError("DeepSeek 大纲服务当前处于离线禁用状态")
    return LLMClient(config=outline_config)


def create_kimi_ppt_client(*, allow_local_fallback: bool = False) -> "LLMClient":
    """创建仅供 PPT 内容规划使用的 Kimi 客户端。

    Kimi/Moonshot 以及讯飞 MaaS 的 Kimi 模型均可通过 OpenAI-compatible
    ``/chat/completions`` 接口接入，因此不复用全局 DeepSeek 配置。未配置
    完整的 ``KIMI_API_KEY/KIMI_BASE_URL/KIMI_MODEL`` 时直接报出可操作错误，
    由 PPT 上层决定是否使用本地结构化模板兜底；绝不会静默改走 DeepSeek。
    """
    from dataclasses import replace

    from backend.app.core.config import get_config

    app_config = get_config()
    kimi = app_config.kimi
    if not kimi.available:
        if allow_local_fallback:
            local_config = replace(
                app_config.llm,
                provider_override="none",
                openai_base_url="",
                openai_api_key="",
                openai_model="",
            )
            return LLMClient(config=local_config)
        raise RuntimeError(
            "PPT 专用 Kimi 未配置完整，请设置 KIMI_API_KEY、KIMI_BASE_URL 和 KIMI_MODEL"
        )

    kimi_config = replace(
        app_config.llm,
        provider_override="openai_compatible",
        openai_base_url=kimi.base_url,
        openai_api_key=kimi.api_key,
        openai_model=kimi.model,
        openai_extra_body={
            # 开启思考模式：Kimi K2.6 会先进行链式推理再输出最终 JSON，
            # 显著提升教学内容的深度、逻辑递进和案例质量。
            # thinking tokens 计入 max_tokens 预算，调用方需相应增大。
            "thinking": {"type": "enabled"},
            "response_format": {"type": "json_object"},
        },
        timeout=kimi.timeout,
    )
    return LLMClient(config=kimi_config)


class LLMClient:
    """
    统一 LLM 客户端

    支持:
    1. 讯飞星火大模型 (WebSocket)
    2. OpenAI 兼容接口 (HTTP REST)
    """

    def __init__(self, config=None):
        from backend.app.core.config import get_config
        self.config = config or get_config().llm

    # ================================================================
    # 公共接口
    # ================================================================
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """同步聊天接口 —— 返回完整文本"""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        provider = self.config.provider
        if provider == "spark":
            return self._chat_spark(messages, temp, tokens)
        elif provider == "openai_compatible":
            return self._chat_openai(messages, temp, tokens)
        else:
            return self._mock_chat(messages)

    async def achat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """异步聊天接口 —— 内部聚合 stream 输出"""
        chunks: List[str] = []
        async for chunk in self.chat_stream(messages, temperature, max_tokens):
            chunks.append(chunk)
        text = "".join(chunks)
        if not text or text.startswith("[ERROR]") or text.startswith("[API_ERROR]"):
            # 失败时回落到 mock，确保上层永远拿到可呈现的文本
            return self._mock_chat(messages)
        return text

    async def achat_strict_with_usage(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_object: bool = False,
    ) -> dict:
        """V2-only call: never turn a provider failure into plausible mock content.

        The older ``achat`` fallback is retained for legacy media/demo flows.
        Usage is ``None`` when the provider does not report it; callers must not
        describe an output-token request limit as measured consumption.
        """
        import asyncio

        if self.config.provider != "openai_compatible":
            raise RuntimeError("v2_model_provider_unavailable")

        # Evaluation campaigns reserve a conservative upper bound before the
        # HTTP call. A failed call keeps its reservation because billing may
        # have occurred before the response was lost.
        from backend.app.agent_runtime.eval_cost_guard import reserve_model_call
        await asyncio.to_thread(reserve_model_call, messages, max_tokens)

        def request() -> dict:
            import requests

            payload = {
                "model": self.config.openai_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            extra = getattr(self.config, "openai_extra_body", None)
            if isinstance(extra, dict):
                payload.update(extra)
            if json_object:
                payload["response_format"] = {"type": "json_object"}
            # DeepSeek V4 defaults to thinking mode, where a short token cap
            # can be spent entirely on reasoning and leave content empty.
            # V2 expects a final answer; callers may explicitly opt in via
            # openai_extra_body when they also provision a larger cap.
            if (self.config.openai_model in {"deepseek-flash", "deepseek-v4-pro"}
                    and "thinking" not in payload):
                payload["thinking"] = {"type": "disabled"}
            response = requests.post(
                f"{self.config.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.config.openai_api_key}",
                         "Content-Type": "application/json"},
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty_model_response")
            raw_usage = data.get("usage")
            usage = None
            if isinstance(raw_usage, dict):
                input_tokens = raw_usage.get("prompt_tokens")
                output_tokens = raw_usage.get("completion_tokens")
                if (type(input_tokens) is int and type(output_tokens) is int
                        and input_tokens >= 0 and output_tokens >= 0):
                    usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
            return {"text": text, "model": str(data.get("model") or payload["model"]),
                    "usage": usage}

        try:
            return await asyncio.to_thread(request)
        except Exception as exc:
            # A provider exception can include the request URL or headers.
            logger.error("V2 model call failed (%s)", type(exc).__name__)
            raise RuntimeError("v2_model_request_failed") from None

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """异步流式聊天接口 —— 逐 chunk 输出"""
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        provider = self.config.provider
        if provider == "spark":
            async for chunk in self._stream_spark(messages, temp, tokens):
                yield chunk
        elif provider == "openai_compatible":
            async for chunk in self._stream_openai(messages, temp, tokens):
                yield chunk
        else:
            # Mock 模式：分块吐出演示文案，体验保持 SSE 流式效果
            mock_text = self._mock_chat(messages)
            import asyncio
            for i in range(0, len(mock_text), 24):
                yield mock_text[i: i + 24]
                await asyncio.sleep(0.02)

    # ================================================================
    # 讯飞星火实现
    # ================================================================
    def _build_spark_auth_url(self) -> str:
        """生成讯飞星火 WebSocket 鉴权 URL"""
        api_key = self.config.spark_api_key
        api_secret = self.config.spark_api_secret
        spark_url = self.config.spark_url

        parsed = urlparse(spark_url)
        host = parsed.hostname
        path = parsed.path

        now = datetime.utcnow()
        date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")

        signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature_sha = hmac.new(
            api_secret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature = base64.b64encode(signature_sha).decode("utf-8")

        authorization_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("utf-8")

        params = {
            "authorization": authorization,
            "date": date,
            "host": host,
        }

        return f"{spark_url}?{urlencode(params)}"

    def _build_spark_payload(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> dict:
        """构建讯飞星火请求体"""
        return {
            "header": {"app_id": self.config.spark_app_id},
            "parameter": {
                "chat": {
                    "domain": self.config.spark_domain,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            },
            "payload": {
                "message": {
                    "text": messages,
                }
            },
        }

    def _chat_spark(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> str:
        """讯飞星火同步调用 (WebSocket)"""
        try:
            import websocket
        except ImportError:
            return "[ERROR] 请安装 websocket-client: pip install websocket-client"

        url = self._build_spark_auth_url()
        payload = self._build_spark_payload(messages, temperature, max_tokens)

        result_chunks = []

        def on_message(ws, message):
            data = json.loads(message)
            code = data.get("header", {}).get("code", -1)
            if code != 0:
                logger.error(f"Spark API error: code={code}, msg={data}")
                result_chunks.append(f"[API_ERROR] code={code}")
                ws.close()
                return

            choices = data.get("payload", {}).get("choices", {})
            text_list = choices.get("text", [])
            for text_item in text_list:
                content = text_item.get("content", "")
                if content:
                    result_chunks.append(content)

            status = choices.get("status", 0)
            if status == 2:  # 最后一帧
                ws.close()

        def on_error(ws, error):
            logger.error(f"Spark WebSocket error: {error}")
            result_chunks.append(f"[API_ERROR] {error}")

        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_open=lambda ws: ws.send(json.dumps(payload)),
        )
        ws.run_forever()

        return "".join(result_chunks)

    async def _stream_spark(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """讯飞星火异步流式调用"""
        try:
            import websockets
        except ImportError:
            yield "[ERROR] 请安装 websockets: pip install websockets"
            return

        url = self._build_spark_auth_url()
        payload = self._build_spark_payload(messages, temperature, max_tokens)

        try:
            async with websockets.connect(url) as ws:
                await ws.send(json.dumps(payload))
                async for message in ws:
                    data = json.loads(message)
                    code = data.get("header", {}).get("code", -1)
                    if code != 0:
                        yield f"[API_ERROR] code={code}"
                        break

                    choices = data.get("payload", {}).get("choices", {})
                    for text_item in choices.get("text", []):
                        content = text_item.get("content", "")
                        if content:
                            yield content

                    if choices.get("status", 0) == 2:
                        break
        except Exception as e:
            logger.error(f"Spark stream error: {e}")
            yield f"[API_ERROR] {e}"

    # ================================================================
    # Mock 模式 —— 无 API Key 时仍能提供"看起来真的多智能体"演示
    # ================================================================
    def _mock_chat(self, messages: List[Dict[str, str]]) -> str:
        """
        无 API Key 时回退的演示生成器
        根据 system_prompt 中暴露的 Agent 身份分别返回结构化范例
        """
        sys_text = ""
        user_text = ""
        for m in messages:
            if m.get("role") == "system":
                sys_text += m.get("content", "") + "\n"
            elif m.get("role") == "user":
                user_text = m.get("content", "")
        sys_text = sys_text.lower()

        topic = (user_text or "学习").strip().splitlines()[0][:40]

        if "画像分析" in sys_text or "profile" in sys_text:
            return (
                f"很高兴和你聊天！结合你刚才提到的「{topic}」，我可以感觉到你对学习很有热情，\n"
                "也透露出你目前的一些情况。让我先把对你的初步理解整理一下：\n\n"
                "- 你目前正在系统学习相关方向，已经有一定的探索经历\n"
                "- 你愿意主动提出问题，属于"
                "**主动提问型**学习者\n"
                "- 偏好结合**视频和动手代码**的方式来加深理解\n\n"
                "我们可以继续聊聊你已经掌握的内容、想突破的难点，我会随聊随更新你的画像。\n\n"
                "```profile_update\n"
                '{"knowledge_base": {"level": "入门到中等", "known_topics": ["基础概念"]}, '
                '"learning_preference": {"preferred_format": "视频 + 代码实践"}, '
                '"cognitive_style": {"type": "视觉+动手型"}, '
                '"interaction_pattern": {"type": "主动提问型"}, '
                '"learning_goal": {"goal": "构建系统理解"}, '
                '"self_efficacy": {"level": "积极正向"}}\n'
                "```\n"
            )

        if "出题专家" in sys_text or "quiz" in sys_text:
            return (
                f"# 针对「{topic}」的练习题（演示模式）\n\n"
                "## 选择题\n"
                "**1.** 在监督学习中，下列哪个是分类任务的典型评估指标？\n"
                "- A. 均方误差 MSE  - B. F1-Score  - C. R²  - D. 余弦相似度\n"
                "**参考答案**：B。解析：分类任务关注查准查全的平衡，F1-Score = 2·P·R/(P+R)。\n\n"
                "## 填空题\n"
                "**2.** 神经网络中防止过拟合的常用正则化方法包括 `___` 和 `___`。\n"
                "**参考答案**：L1/L2 正则化、Dropout。\n\n"
                "## 编程题\n"
                "**3.** 用 NumPy 实现 softmax 函数，要求数值稳定。\n"
                "```python\nimport numpy as np\ndef softmax(x):\n    x = x - np.max(x)\n    e = np.exp(x)\n    return e / e.sum()\n```\n\n"
                "```quiz_json\n"
                '[{"id":1,"type":"choice","difficulty":"easy","question":"F1-Score 的含义","answer":"B"},'
                '{"id":2,"type":"fill","difficulty":"medium","answer":"L2 / Dropout"},'
                '{"id":3,"type":"code","difficulty":"medium","topic":"softmax"}]\n'
                "```\n"
            )

        if "思维导图" in user_text or "mindmap" in sys_text or "多模态" in sys_text:
            return (
                f"# {topic} · 思维导图（演示模式）\n\n"
                "```mermaid\nmindmap\n"
                "  root((人工智能))\n"
                "    机器学习\n"
                "      监督学习\n"
                "        分类\n"
                "        回归\n"
                "      无监督学习\n"
                "        聚类\n"
                "        降维\n"
                "      强化学习\n"
                "    深度学习\n"
                "      CNN\n"
                "      RNN/LSTM\n"
                "      Transformer\n"
                "    应用方向\n"
                "      计算机视觉\n"
                "      自然语言处理\n"
                "      多模态大模型\n"
                "```\n\n"
                "```resource_meta\n"
                '{"type":"mindmap","title":"' + topic + ' 思维导图"}\n'
                "```\n"
            )

        if "路径规划师" in sys_text or "path" in sys_text:
            return (
                f"# 个性化学习路径（演示）：{topic}\n\n"
                "结合你的画像与目标，建议分 4 个阶段推进：\n\n"
                "1. **基础奠基（第 1 周）**：Python 与数学基础回顾\n"
                "2. **核心方法（2-3 周）**：监督学习、神经网络基础\n"
                "3. **进阶专题（4-5 周）**：CNN/Transformer + 1 个项目\n"
                "4. **综合实战（第 6 周）**：自选课题 + 评估总结\n\n"
                "```learning_path\n"
                "{\"stages\": [\n"
                "  {\"id\":1,\"title\":\"基础奠基\",\"topics\":[\"Python\",\"线性代数\",\"概率\"],\"duration\":\"1周\",\"resources\":[\"文档\",\"练习\"],\"prerequisites\":[],\"assessment\":\"完成基础题 80%\"},\n"
                "  {\"id\":2,\"title\":\"机器学习核心\",\"topics\":[\"线性/逻辑回归\",\"决策树\",\"评估指标\"],\"duration\":\"2周\",\"resources\":[\"文档\",\"代码\",\"练习\"],\"prerequisites\":[1],\"assessment\":\"完成 2 个项目\"},\n"
                "  {\"id\":3,\"title\":\"深度学习入门\",\"topics\":[\"前馈网络\",\"CNN\",\"PyTorch\"],\"duration\":\"2周\",\"resources\":[\"视频\",\"代码\",\"思维导图\"],\"prerequisites\":[2],\"assessment\":\"图像分类小项目\"},\n"
                "  {\"id\":4,\"title\":\"综合实战\",\"topics\":[\"项目实战\",\"答辩准备\"],\"duration\":\"1周\",\"resources\":[\"项目\",\"PPT\"],\"prerequisites\":[3],\"assessment\":\"项目演示\"}\n"
                "]}\n"
                "```\n"
            )

        if "评估" in sys_text or "evaluator" in sys_text:
            return (
                f"# 学习效果评估（演示）：{topic}\n\n"
                "**总体评价**：你最近的学习状态稳中向好，基础概念掌握扎实，但**编程实操**和**项目应用**还有提升空间。\n\n"
                "## 强项\n- 概念理解力强\n- 学习节奏稳定\n\n"
                "## 待提升\n- 代码动手量不足\n- 综合题正确率偏低\n\n"
                "## 改进建议\n1. 每周至少完成 2 道编程题\n2. 选择 1 个小项目从头跑通\n3. 把错题做成专题复盘\n\n"
                "```evaluation_result\n"
                "{\"overall_score\":0.74,\"dimensions\":{\"知识掌握\":0.82,\"应用能力\":0.6,\"学习持续性\":0.8,\"反思深度\":0.7},"
                "\"strengths\":[\"概念扎实\"],\"weaknesses\":[\"编程实践不足\"],"
                "\"recommendations\":[\"每周 2 道编程题\",\"完成 1 个小项目\",\"错题专题复盘\"],"
                "\"path_adjustments\":{\"action\":\"add_practice\",\"focus_areas\":[\"代码实现\"]}}\n"
                "```\n"
            )

        if "质量审查" in sys_text or "reviewer" in sys_text:
            return (
                "**总体评价**：良。\n"
                "- 主题相关性：强\n- 结构完整性：良\n- 学术准确性：良\n- 可读性：好\n- 原创性：无脏数据\n\n"
                "```review_result\n"
                '{"quality":"good","score":86,"issues":[],"pass":true,"regenerate":false}\n'
                "```\n"
            )

        if "课程专家" in sys_text or "教授" in sys_text or "course_expert" in sys_text:
            return (
                f"# {topic}（演示讲解）\n\n"
                "## 一句话定义\n"
                f"**{topic}** 是当代 AI 体系中的核心概念，关注从数据中学习规律并应用于新情境。\n\n"
                "## 核心原理\n"
                "1. **任务定义**：明确输入空间 X、输出空间 Y 与目标函数 f\n"
                "2. **数据驱动**：用样本集合估计 f 的近似\n"
                "3. **优化求解**：选择损失函数并通过梯度下降迭代更新参数\n\n"
                "## 公式表达\n"
                "$$\\theta^* = \\arg\\min_\\theta \\frac{1}{N}\\sum_{i=1}^N L(f_\\theta(x_i), y_i) + \\lambda R(\\theta)$$\n\n"
                "## 代码示例\n"
                "```python\nimport numpy as np\nW = np.zeros(d)\nfor _ in range(epochs):\n    grad = (X @ W - y) @ X / N\n    W -= lr * grad\n```\n\n"
                "## 关联拓展\n- 过拟合与正则化\n- 评估指标与交叉验证\n- 实战项目：用 sklearn 跑一遍基线\n"
            )

        if "导师" in sys_text or "tutor" in sys_text:
            return (
                f"**一句话**：关于「{topic}」，可以这样理解——把它想象成一个"
                "从经验中总结规律的学习过程。\n\n"
                "## 详细展开\n1. 它**输入**的是数据/经验\n2. 它**学的是**输入到输出的映射关系\n3. 它**用**得到的模型去预测新样本\n\n"
                "## 形象类比\n就像你做了大量数学题后，会自然总结出某类题的解题套路——模型也一样，只不过它用梯度下降来"
                "自动“总结套路”。\n\n"
                "## 关联知识\n- 损失函数  - 优化器  - 评估指标\n\n"
                "## 巩固建议\n做 3 道小练习，再用代码跑一遍最小例子。需要我出题吗？\n"
            )

        # 默认通用回复
        return (
            f"【演示模式】我收到了你的请求：「{topic}」。\n\n"
            "当前系统未配置真实 LLM API Key，正在使用 Mock 回退。你可以：\n"
            "1. 在 `.env` 中填入 `SPARK_APP_ID/SPARK_API_KEY/SPARK_API_SECRET` 启用讯飞星火\n"
            "2. 或设置 `OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_MODEL` 接入 OpenAI 兼容接口（DeepSeek/通义/Kimi）\n\n"
            "在 Mock 模式下，各 Agent 仍会按真实链路被 Orchestrator 调度，便于评委查看多智能体协同效果。\n"
        )

    # ================================================================
    # OpenAI 兼容接口实现
    # ================================================================
    def _chat_openai(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> str:
        """OpenAI 兼容接口同步调用"""
        import requests

        url = f"{self.config.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.openai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        extra_body = getattr(self.config, "openai_extra_body", None)
        if isinstance(extra_body, dict):
            payload.update(extra_body)

        try:
            import time as _time
            # kimi-k2.6 过载(429)时先重试，3 次仍失败则降级到 moonshot-v1-32k
            fallback_models = ["moonshot-v1-32k", "moonshot-v1-8k"]
            models_to_try = [payload.get("model", "")] + fallback_models
            for model_name in models_to_try:
                if not model_name:
                    continue
                payload["model"] = model_name
                # 非 kimi-k2.x 模型不支持 thinking，降级时移除
                is_k2 = "k2" in model_name
                if not is_k2:
                    payload.pop("thinking", None)
                    payload["temperature"] = temperature  # 恢复原始 temperature
                else:
                    # k2 系列 thinking 模式要求 temperature=1
                    thinking_cfg = extra_body.get("thinking") if isinstance(extra_body, dict) else None
                    if isinstance(thinking_cfg, dict) and thinking_cfg.get("type") == "enabled":
                        payload["temperature"] = 1

                for attempt in range(5):
                    resp = requests.post(
                        url, headers=headers, json=payload, timeout=self.config.timeout,
                    )
                    if resp.status_code == 429 and attempt < 4:
                        wait = 2 ** (attempt + 1)  # 2s, 4s, 8s, 16s, 32s
                        logger.warning(f"Kimi 429 ({model_name}), retry in {wait}s (attempt {attempt+1}/5)")
                        _time.sleep(wait)
                        continue
                    break
                if resp.status_code == 200:
                    break
                if resp.status_code != 429:
                    break  # 非 429 错误（如 400），不降级直接跳出
                # kimi-k2.6 全部 429 后，额外等待再重试一轮，尽量不降级
                if model_name == payload.get("model", "") and "k2" in model_name:
                    logger.info(f"Kimi k2.6 exhausted 5 retries, extra wait 15s before model fallback")
                    _time.sleep(15)
                    resp = requests.post(
                        url, headers=headers, json=payload, timeout=self.config.timeout,
                    )
                    if resp.status_code == 200:
                        break

            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content", "")
            # Kimi K2.6 thinking 模式：content 可能为空，最终答案在 reasoning_content 中
            if not content and msg.get("reasoning_content"):
                content = msg["reasoning_content"]
            return content
        except Exception as e:
            logger.error(f"OpenAI compatible API error: {e}")
            return f"[API_ERROR] {e}"

    async def _stream_openai(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """OpenAI 兼容接口异步流式调用（使用 requests 规避 Windows 证书库读取问题）"""
        import requests
        import asyncio

        url = f"{self.config.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.openai_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # 流式调用也必须携带 extra_body（如 response_format / thinking），
        # 否则 Kimi K2.6 不走 JSON 模式，返回非结构化文本导致解析失败。
        extra_body = getattr(self.config, "openai_extra_body", None)
        if isinstance(extra_body, dict):
            payload.update(extra_body)
        # Kimi K2.6 thinking 模式要求 temperature=1，传其它值会 400 报错
        thinking_cfg = extra_body.get("thinking") if isinstance(extra_body, dict) else None
        if isinstance(thinking_cfg, dict) and thinking_cfg.get("type") == "enabled":
            payload["temperature"] = 1

        loop = asyncio.get_event_loop()

        def do_request():
            return requests.post(url, headers=headers, json=payload, stream=True, timeout=self.config.timeout)

        try:
            resp = await loop.run_in_executor(None, do_request)
            resp.raise_for_status()

            iterator = resp.iter_lines()
            while True:
                line = await loop.run_in_executor(None, next, iterator, None)
                if line is None:
                    break
                if line:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: ") and line_str != "data: [DONE]":
                        try:
                            chunk_data = json.loads(line_str[6:])
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            # Kimi thinking 模式：思考内容在 reasoning_content，
                            # 最终答案在 content；只输出 content 给上层
                            if content:
                                yield content
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.error(f"OpenAI stream error: {e}")
            yield f"[API_ERROR] {e}"
