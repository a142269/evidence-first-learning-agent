import logging
import re
from typing import List, Dict, Any

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.agent_tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

class ResourceGeneratorAgent(BaseAgent):
    """统一多模态资源生成 Agent（调用 multi-with-fallback 真实 API）"""

    @property
    def name(self) -> str:
        return "resource_generator"

    @property
    def description(self) -> str:
        return "根据用户需求统一生成资料、PPT、题集、代码、语音与视频等可用学习资源。"

    @property
    def system_prompt(self) -> str:
        return ""

    async def execute(self, context: AgentContext) -> AgentResponse:
        logger.info(f"[ResourceGeneratorAgent] 处理请求: {context.user_input}")

        requested_types = _requested_resource_types(
            context.user_input,
            action=str(context.extra.get("action") or ""),
        )

        if not requested_types:
            # 兜底
            if context.extra.get("action") == "direct_message":
                # 单 Agent 私聊模式：学生未提及资源关键词时，不强制生成文档，
                # 改为用 LLM 做对话式回答，避免误触发资源生成。
                return await self._dm_conversational_reply(context)
            else:
                requested_types = ["document"]

        # 去重
        requested_types = list(dict.fromkeys(requested_types))

        # 调用 registry 中的 Tool
        registry = get_tool_registry()
        tool_handler = None
        for tr in registry.list_a_tools():
            if tr.schema.name == "generate_learning_materials":
                tool_handler = tr.handler
                break

        if not tool_handler:
            return self._success("后端工具未找到", "markdown")

        # 从用户消息中提取真正的主题词，而不是粗暴截取前 30 个字符
        topic = _extract_topic(context.user_input, context.course_name)
        pptx_template = _extract_pptx_template(context.user_input)
        result_dict = await tool_handler(
            topic=topic,
            types=requested_types,
            description=_compact_resource_description(context.user_input),
            user_id=str(context.extra.get("user_id") or ""),
            pptx_template=pptx_template or None,
            __session_id__=context.session_id
        )

        type_label = {
            "pptx": "PPT 课件", "mermaid": "思维导图", "quiz": "练习题",
            "document": "讲义文档", "manim": "讲解视频", "tts": "语音导学",
            "code": "代码案例",
        }

        # 解析返回的 MultiResourceResponse 并组装到 resources 中
        if not result_dict.get("success", True) and "error" in result_dict:
            logger.warning("[ResourceGeneratorAgent] resource tool failed: %s", result_dict.get("error"))
            readable = "、".join(type_label.get(t, t) for t in requested_types)
            return self._success(
                f"这次{readable}生成未完成。我已经保留了主题，请稍后重试。",
                "markdown",
            )

        generated_resources = []
        failure_notes: List[str] = []
        results = result_dict.get("results", {})
        # 下游即便意外返回了额外类型，也只向用户展示本次明确请求的资源。
        for rtype in requested_types:
            env = results.get(rtype) or {}
            # 2026-07-12 放宽判据：过去只用 env.get('success')，一旦 PNG 渲染
            # 或 sandbox exit code 有小瑕疵就整个丢弃。改为「只要有可用内容
            # （metadata 里的 code / mermaid_code / quiz_data 或 filepath 非空）
            # 就算成功」，避免把 LLM 已经生成的产物又滤掉。
            env_meta = env.get("metadata") or {}
            if rtype == "manim":
                # 视频必须有真实可播放的 MP4。脚本、说明文字或 success=True
                # 都不能替代视频，否则资源库会出现“视频变文档”的假成功。
                filepath = str(env.get("filepath") or "").lower()
                usable_download = any(
                    bool(download.get("exists", True))
                    and (
                        str(download.get("filename") or "").lower().endswith(".mp4")
                        or any(token in str(download.get("type") or "").lower()
                               for token in ("video", "manim", "mp4"))
                    )
                    for download in (env.get("downloads") or [])
                    if isinstance(download, dict)
                )
                has_content = bool(
                    env.get("success")
                    and (filepath.endswith(".mp4") or usable_download)
                    and env_meta.get("playback_status", "ready") == "ready"
                )
            else:
                has_content = bool(
                    env.get("success")
                    or env.get("filepath")
                    or env_meta.get("code")
                    or env_meta.get("mermaid_code")
                    or env_meta.get("quiz_data")
                    or env_meta.get("data_uri")
                )
            if has_content:
                generated_resources.append({
                    "id": f"res_{rtype}",
                    "type": rtype,
                    "title": env_meta.get("title") or f"生成的 {rtype} 资源",
                    "content": env.get("content", ""),
                    "filepath": env.get("filepath", ""),
                    "downloads": env.get("downloads", []),
                    "evidence": env.get("evidence", []),
                    "cov": env.get("cov", []),
                    "safety": env.get("safety", {}),
                    "metadata": env_meta,
                })
            else:
                err = str(env.get("error") or "生成引擎未返回内容").strip()
                failure_notes.append(
                    f"{type_label.get(rtype, rtype)}：{_user_readable_failure(err)}"
                )
                logger.warning(f"[ResourceGeneratorAgent] {rtype} failed, env={env}")
                
        # 聊天气泡只负责说明与交付入口。导图源码、代码全文和 PPT 大纲都
        # 属于文件内容，不在正文中重复铺开，避免一个 Agent 气泡挤占整页。
        readable = "、".join(type_label.get(t, t) for t in requested_types)
        topic_label = topic or "本次主题"
        preview_lines: List[str] = []
        for res in generated_resources[:3]:
            title = str(res.get("title") or type_label.get(res.get("type", ""), res.get("type", "资源"))).strip()
            preview_lines.append(f"- **{type_label.get(res.get('type', ''), res.get('type', ''))}** · {title}")
        preview_block = "\n".join(preview_lines) if preview_lines else ""

        if generated_resources:
            content_msg = (
                f"好的，我已按「{topic_label}」生成{readable}。"
                "每份文件都基于当前主题、你的学习画像和课程知识库生成；"
                "请点击下方对应的下载链接获取完整内容。\n\n"
                f"{preview_block}\n\n"
                "聊天中不再重复展开思维导图源码、代码全文或 PPT 大纲。"
                "如需调整难度、示例或章节结构，告诉我具体文件即可。"
            )
        else:
            # 用真正的失败原因替代"知识库没有切片"的通用兜话
            detail = "\n".join(f"- {note}" for note in failure_notes) or "- 后端未返回任何 envelope"
            content_msg = (
                f"我尝试为「{topic_label}」生成{readable}，但底层引擎没能产出内容。\n\n"
                f"具体失败原因：\n{detail}\n\n"
                "常见原因是后端 LLM 未连通或本地渲染依赖缺失。你可以先在设置中心检查后端服务连接，"
                "或者告诉我更具体的主题词我再试一次。"
            )

        return self._success(
            content=content_msg,
            content_type="markdown",
            resources=generated_resources
        )

    async def _dm_conversational_reply(self, context: AgentContext) -> AgentResponse:
        """单 Agent 私聊模式下，学生未请求资源生成时的对话式回答。

        使用 LLM 根据学生问题做知识性回答，而非强制生成文档。
        """
        system_prompt = (
            "你是一位学习资源助手。学生正在实验场和你对话。"
            "如果学生的问题与学习内容相关，请正常回答。"
            "如果学生想生成资源（文档、PPT、思维导图、代码、练习题），"
            "请提示他们在消息中明确说明需要什么类型的资源。"
        )
        try:
            reply = await self._acall_llm(
                context.user_input,
                history=context.conversation_history,
                extra_system=system_prompt,
            )
            return self._success(
                content=reply or "请告诉我你需要什么帮助，或者想生成什么类型的学习资源。",
                content_type="markdown",
            )
        except Exception as exc:
            logger.warning(f"[ResourceGeneratorAgent] DM conversational reply failed: {exc}")
            return self._success(
                content=(
                    "我可以帮你生成学习资源（文档、PPT 课件、思维导图、代码案例、练习题）。"
                    "请告诉我你需要什么类型的内容。"
                ),
                content_type="markdown",
            )


# ================================================================
# 主题词提取 —— 从用户自然语言消息中抽取真正的学习主题
# ================================================================

# 常见请求动词短语，提取主题时需要去掉
_STOP_PHRASES = [
    "请围绕", "请生成", "请帮我", "帮我生成", "生成一份", "生成一个",
    "制作一份", "制作一个", "做一个", "做一份",
    "课程资料", "练习题", "可加入学习路径的资源清单",
    "资源清单", "学习路径",
]

# 资源类型关键词（提取主题时排除）
_RESOURCE_KEYWORDS = {
    "ppt", "课件", "幻灯片", "思维导图", "脑图", "导图", "关系图",
    "练习题", "测验", "试卷", "资料", "文档", "笔记", "讲义", "材料", "讲解",
    "视频", "动画", "演示", "代码", "实例", "案例",
}

# 前置动词
_LEADING_VERBS = re.compile(r"^(请|帮我|麻烦|可以)?(生成|制作|做|给|来|弄|创建)(一)?(个|份)?")

# "关于X的Y" 模式
_ABOUT_PATTERN = re.compile(r"关于(.+?)的")

# 尾部资源类型词
_TRAILING_RES = re.compile(
    r"(的|了)?(ppt|PPT|课件|幻灯片|思维导图|脑图|导图|关系图|"
    r"练习题|测验|试卷|资料|文档|笔记|讲义|材料|讲解|"
    r"视频|动画|演示|代码|实例|案例)$"
)


def _extract_topic(user_input: str, course_name: str = "") -> str:
    """从用户自然语言消息中提取真正的学习主题词。

    策略:
    1. 去掉 @ 提及
    2. 去掉前置动词（请生成/帮我做/...）
    3. 去掉常见请求短语
    4. 尝试 "关于X的Y" 模式提取 X
    5. 去掉尾部资源类型词
    6. 按标点分割取最长有意义段
    7. 兜底: course_name 或截断
    """
    text = user_input.strip()

    # 1. 去掉 @ 提及
    text = re.sub(r"@\S+\s*", "", text)

    # PPT 高频口语请求优先解析。旧正则会把“二分查找的PPT”整体作为主题，
    # 于是模型反复输出“学习二分查找的PPT”，而不是讲二分查找本身。
    # 这里先截取资源类型之前的文本，再清理请求动词与尾部结构助词。
    ppt_pos = re.search(r"(?:ppt|课件|幻灯片)", text, flags=re.IGNORECASE)
    if ppt_pos:
        candidate = text[:ppt_pos.start()].strip()
        candidate = re.sub(
            r"^(?:请|麻烦|可以)?\s*(?:帮我|给我)?\s*"
            r"(?:我想要|我想学习|我需要|想要|需要)?\s*"
            r"(?:生成|制作|创建|做)?\s*(?:一份|一个)?\s*",
            "",
            candidate,
        ).strip()
        candidate = re.sub(r"(?:的|相关的|主题的)\s*$", "", candidate).strip()
        if 2 <= len(candidate) <= 80:
            return candidate[:50]

    # 2. 去掉前置动词
    text = _LEADING_VERBS.sub("", text).strip()

    # 3. 去掉常见请求短语
    for phrase in _STOP_PHRASES:
        text = text.replace(phrase, " ")
    text = text.strip()

    # 3.5 明确引号主题优先，例如：围绕「Transformer 架构」生成导图。
    quoted = re.search(r"[「“\"]([^」”\"]{2,60})[」”\"]", text)
    if quoted:
        candidate = quoted.group(1).strip()
        if candidate:
            return candidate[:50]

    # 4. 尝试 "关于X的Y" 模式
    m = _ABOUT_PATTERN.search(text)
    if m:
        candidate = m.group(1).strip()
        if candidate and len(candidate) >= 2:
            return candidate[:50]

    # 5. 去掉尾部资源类型词（反复去除）
    cleaned = text
    for _ in range(3):
        new_cleaned = _TRAILING_RES.sub("", cleaned).strip()
        if new_cleaned == cleaned:
            break
        cleaned = new_cleaned

    # 6. 按标点分割，取最长有意义段
    segments = re.split(r"[，,。、；;！!？?（()）\s]+", cleaned)
    segments = [s.strip() for s in segments if s.strip() and len(s.strip()) >= 2]

    # 过滤掉纯资源关键词
    meaningful = [
        s for s in segments
        if s.lower() not in _RESOURCE_KEYWORDS
    ]

    if meaningful:
        topic = max(meaningful, key=len).strip("的了是")
        if topic and len(topic) >= 2:
            return topic[:50]

    # 7. 兜底
    if course_name and course_name != "artificial_intelligence":
        return course_name
    return user_input.strip()[:20]


_ACTION_RESOURCE_TYPES = {
    "generate_ppt": "pptx",
    "generate_doc": "document",
    "generate_exercise": "quiz",
    "generate_mindmap": "mermaid",
    "generate_video": "manim",
    "generate_audio": "tts",
}

_RESOURCE_TYPE_TOKENS = (
    ("pptx", ("ppt", "课件", "幻灯片", "演示文稿")),
    ("mermaid", ("脑图", "思维导图", "导图", "关系图", "知识图谱", "mermaid")),
    ("quiz", ("练习题", "习题", "题目", "题库", "测验", "试卷", "出题")),
    ("document", ("资料", "文档", "笔记", "讲义", "材料")),
    ("manim", ("视频", "动画", "讲解视频", "教学视频", "mp4")),
    ("tts", ("语音", "音频", "朗读", "配音", "播客", "tts")),
    ("code", ("代码", "编程", "实战")),
)


def _requested_resource_types(text: str, action: str = "") -> List[str]:
    """把自然语言请求解析为资源类型，尊重单类型编排动作和“只生成”语义。"""
    action_type = _ACTION_RESOURCE_TYPES.get(str(action or "").strip())
    lowered = str(text or "").lower()
    detected = [
        resource_type
        for resource_type, tokens in _RESOURCE_TYPE_TOKENS
        if any(token in lowered for token in tokens)
    ]
    detected = list(dict.fromkeys(detected))

    exclusive_prefix = re.search(r"(?:只需要|只要|仅(?:需|生成|制作)?|单独(?:生成|制作)?|只生成|只制作)\s*([^，。；;！!？?]*)", lowered)
    if exclusive_prefix:
        exclusive_text = exclusive_prefix.group(1)
        exclusive_types = [
            resource_type
            for resource_type, tokens in _RESOURCE_TYPE_TOKENS
            if any(token in exclusive_text for token in tokens)
        ]
        if exclusive_types:
            return list(dict.fromkeys(exclusive_types))

    # generate_doc 曾经是 @阿匠 的通用入口，不能覆盖文本里更明确的 PPT、
    # 视频或思维导图。其它专用动作仍保持单类型，避免编排阶段意外扩大产物。
    if action_type and action_type == "document" and detected:
        return detected
    if action_type:
        return [action_type]

    return detected


def _compact_resource_description(text: str, limit: int = 400) -> str:
    """把协作子任务压缩到 MultiResourceRequest 的稳定协议范围内。"""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:300].rstrip()} … {cleaned[-96:].lstrip()}"[:limit]


def _extract_pptx_template(text: str) -> str:
    """从 Agent 自然语言中提取受控模板名，避免把绝对路径传给下游。"""
    match = re.search(
        r"(?:使用|采用|套用|模板(?:名)?|template)\s*[:：]?\s*([A-Za-z0-9_-]{2,60})",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _user_readable_failure(error: str) -> str:
    """把底层异常归一为可操作说明，不把 Pydantic/堆栈/供应商信息回显给学生。"""
    lowered = str(error or "").lower()
    if any(token in lowered for token in ("timeout", "timed out", "超时")):
        return "生成耗时超过限制，可稍后重试或只生成这一类资源"
    if any(token in lowered for token in ("validationerror", "string_too_long", "pydantic")):
        return "请求内容较复杂，系统已自动精简；建议单独重试这一类资源"
    if any(token in lowered for token in ("ffmpeg", "manim", "renderer", "render")):
        return "本地渲染组件暂不可用，文字内容仍可继续生成"
    if any(token in lowered for token in ("tts", "audio", "voice", "语音", "音频")):
        return "语音服务暂不可用，可先查看文字讲解后再重试"
    return "生成服务暂未返回可用内容，可稍后重试"
