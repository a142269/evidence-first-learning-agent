"""
多智能体协同编排器
设计迁移自:
- 旧项目 services/ 层的分层服务调用模式
- 旧项目 rules/base_rule_engine.py 的规则驱动决策引擎
- 旧项目多个 service 之间的数据流转设计 (schemas → service → repository)

核心创新: 用"规则路由 + LLM决策"替代旧项目的纯规则引擎
"""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field, replace

from backend.app.agents.base import AgentContext, AgentResponse

logger = logging.getLogger(__name__)


# ================================================================
# 单 Agent 模式: 前端 partner.key → 后端 AGENT_REGISTRY key 映射
# ================================================================
PARTNER_TO_AGENT: Dict[str, str] = {
    "planner": "path_planner",
    "tutor": "tutor",
    "content": "doc_gen",
    "quiz": "exercise",
    "evaluation": "evaluator",
    "safety": "safe_decline",
}

# 合法的前端 partner.key 集合
VALID_AGENT_KEYS = frozenset(PARTNER_TO_AGENT.keys())

# 群聊里每个公开角色对应的 @ 名称。多 Agent 请求会先按角色拆成子任务，
# 避免五位伙伴都拿到整段总指令后重复回答、越权回答或误判资源类型。
AGENT_MENTION_NAMES: Dict[str, str] = {
    "path_planner": "智狐",
    "tutor": "智灵",
    "doc_gen": "阿匠",
    "mindmap": "阿匠",
    "reading": "阿匠",
    "video": "阿匠",
    "audio": "阿匠",
    "exercise": "小龙",
    "evaluator": "团团",
    # 球球（刺猬守护）人设统摄三个安全类 Agent：
    # 边界守门 safe_decline + 知识入库审核 knowledge_guard + 生成验证链 cov_verifier
    "safe_decline": "球球",
    "knowledge_guard": "球球",
    "cov_verifier": "球球",
}


def resolve_target_agent(partner_key: str) -> Optional[str]:
    """将前端 partner.key 映射为后端 AGENT_REGISTRY key。

    Returns:
        后端 agent name, 或 None (非法 key)
    """
    return PARTNER_TO_AGENT.get(partner_key)


# ================================================================
# Agent 通信协议 —— 借鉴旧项目 service 间通过 Schema 通信的模式
# ================================================================
class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentTask:
    """Agent 任务定义 —— 类似旧项目 feature 计算任务"""
    task_id: str
    agent_name: str
    action: str                  # 具体动作: generate_doc, create_mindmap 等
    input_data: dict             # 输入参数
    priority: int = 0            # 优先级
    depends_on: List[str] = field(default_factory=list)  # 依赖任务ID


@dataclass
class AgentResult:
    """Agent 执行结果"""
    task_id: str
    agent_name: str
    status: AgentStatus
    output: Optional[Any] = None
    error: Optional[str] = None
    tokens_used: int = 0


# ================================================================
# Agent 路由规则 —— 对应旧项目 rules/pattern_rules.yaml 的规则体系
# ================================================================
AGENT_ROUTING = {
    # 画像构建：任何对话都先经过 profile agent
    "profile_update": {
        "agent": "profile",
        "trigger": "every_conversation",  # 每次对话触发
        "priority": 1,
    },
    # 资源生成：按用户意图路由到对应的生成Agent
    "generate_doc": {
        "agent": "doc_gen",
        "trigger": "user_requests_document",
        "priority": 2,
    },
    "generate_ppt": {
        "agent": "doc_gen",
        "trigger": "user_requests_presentation",
        "priority": 2,
    },
    "generate_mindmap": {
        "agent": "mindmap",
        "trigger": "user_requests_mindmap",
        "priority": 2,
    },
    "generate_exercise": {
        "agent": "exercise",
        "trigger": "user_requests_exercise",
        "priority": 2,
    },
    "generate_reading": {
        "agent": "reading",
        "trigger": "user_requests_reading",
        "priority": 2,
    },
    "generate_video": {
        "agent": "video",
        "trigger": "user_requests_video",
        "priority": 2,
    },
    "generate_audio": {
        "agent": "audio",
        "trigger": "user_requests_audio",
        "priority": 2,
    },
    # 路径规划
    "plan_path": {
        "agent": "path_planner",
        "trigger": "user_requests_plan OR profile_significantly_changed",
        "priority": 3,
    },
    # 智能辅导
    "tutoring": {
        "agent": "tutor",
        "trigger": "user_asks_question",
        "priority": 2,
    },
    # Plan D · Review v1 — 教学边界守门
    "out_of_scope": {
        "agent": "safe_decline",
        "trigger": "chitchat_or_sensitive",
        "priority": 0,
    },
    # 效果评估
    "evaluation": {
        "agent": "evaluator",
        "trigger": "learning_session_completed OR user_requests_evaluation",
        "priority": 3,
    },
}


class AgentOrchestrator:
    """
    多智能体协同编排器

    设计说明（评审答辩要点）:
    1. 借鉴旧项目 services/ 层的分层设计，将每个功能拆分为独立 Agent
    2. 借鉴旧项目 rule_engine 的规则驱动决策，路由表决定 Agent 调用顺序
    3. 借鉴旧项目并行服务调用经验，独立任务并行执行
    4. 新增 LLM 辅助决策：当路由规则无法判断时，由 LLM 决定下一步
    """

    def __init__(self, llm_client, agent_registry: Optional[Dict[str, Any]] = None):
        """
        Args:
            llm_client: 共享 LLM 客户端（节省连接开销）
            agent_registry: name -> Agent 类 的映射；不传则惰性导入
        """
        self.llm = llm_client
        self.routing = AGENT_ROUTING
        self.task_history: List[AgentResult] = []
        if agent_registry is None:
            # 延迟导入避免循环依赖
            from backend.app.agents import AGENT_REGISTRY
            agent_registry = AGENT_REGISTRY
        self.agent_registry = agent_registry
        # Agent 实例缓存（按需懒加载，共享同一 LLMClient）
        self._agent_instances: Dict[str, Any] = {}

    async def process_turn(
        self,
        user_input: str,
        profile: dict,
        context: dict,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_results: Optional[List[Dict[str, Any]]] = None,
        course_name: str = "artificial_intelligence",
        session_id: str = "",
        target_agent: Optional[str] = None,
    ) -> Dict[str, AgentResponse]:
        """
        处理一轮对话/请求 —— 多 Agent 协同入口

        Args:
            target_agent: 若指定合法 partner.key (planner/tutor/content/quiz/
                          evaluation/safety)，跳过多 Agent 编排，直接路由到该 Agent。
                          非法值会被静默忽略，回退为普通群聊模式。

        Returns:
            task_id -> AgentResponse  (Agent 返回的完整结构化响应)
        """
        # ===== 配置型 Agent 模式: @教师新增的 Agent 优先命中 =====
        cfg_result = await self._try_configurable_agent(
            user_input=user_input,
            profile=profile,
            context=context,
            conversation_history=conversation_history,
            rag_results=rag_results,
            course_name=course_name,
            session_id=session_id,
        )
        if cfg_result is not None:
            return cfg_result

        # ===== 单 Agent 模式: 直接路由到目标 Agent =====
        resolved = resolve_target_agent(target_agent) if target_agent else None
        if resolved:
            logger.info(
                f"[Orchestrator] 单 Agent 模式: target={target_agent} → agent={resolved}"
            )
            # 门禁：寒暄只做自我介绍；明显问错伙伴时礼貌转介，
            # 避免出题等生成型 Agent 把任意输入都当成任务载荷。
            from backend.app.agents.direct_chat_gate import (
                evaluate_direct_chat_gate,
            )
            gate_response = evaluate_direct_chat_gate(target_agent, user_input)
            if gate_response is not None:
                logger.info(
                    "[Orchestrator] 直通门禁命中: %s",
                    gate_response.metadata.get("direct_chat_gate"),
                )
                return {"dm_0": gate_response}
            agent_context = AgentContext(
                user_input=user_input,
                session_id=session_id,
                profile=profile,
                course_name=course_name,
                conversation_history=conversation_history or [],
                rag_results=rag_results or [],
                extra={**context, "action": "direct_message", "task_id": "dm_0"},
            )
            task = AgentTask(
                task_id="dm_0",
                agent_name=resolved,
                action="direct_message",
                input_data={"profile_snapshot": profile},
                priority=0,
            )
            result = await self._run_agent(task, agent_context)
            return {"dm_0": result}

        # ===== 群聊模式: 原有多 Agent 编排流程 =====
        # Step 1: 意图识别（规则 + 兜底）
        intents = await self._classify_intent(user_input, context)

        # Step 2: 生成任务计划（含优先级/并行性）
        tasks = self._plan_tasks(intents, profile)
        logger.info(f"[Orchestrator] 编排任务: {[t.action for t in tasks]}")

        # Step 3: 构造共享上下文
        agent_context = AgentContext(
            user_input=user_input,
            session_id=session_id,
            profile=profile,
            course_name=course_name,
            conversation_history=conversation_history or [],
            rag_results=rag_results or [],
            extra=context or {},
        )

        # Step 4: 按优先级分批执行
        results: Dict[str, AgentResponse] = {}
        priority_groups: Dict[int, List[AgentTask]] = {}
        for task in tasks:
            priority_groups.setdefault(task.priority, []).append(task)

        for priority in sorted(priority_groups.keys()):
            group = priority_groups[priority]
            coroutines = [self._run_agent(t, agent_context) for t in group]
            outputs = await asyncio.gather(*coroutines, return_exceptions=True)
            for task, output in zip(group, outputs):
                if isinstance(output, Exception):
                    logger.exception(f"[Orchestrator] Agent {task.agent_name} 异常: {output}")
                    results[task.task_id] = AgentResponse(
                        agent_name=task.agent_name,
                        success=False,
                        error=str(output),
                    )
                else:
                    results[task.task_id] = output

        return results

    async def _try_configurable_agent(
        self,
        user_input: str,
        profile: dict,
        context: dict,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rag_results: Optional[List[Dict[str, Any]]] = None,
        course_name: str = "artificial_intelligence",
        session_id: str = "",
    ) -> Optional[Dict[str, AgentResponse]]:
        """识别 @配置型Agent（教师在管理台新增的），命中则由 ConfigurableAgent 直接回复。

        - 命中且启用: 跳过多 Agent 编排，单 Agent 回复。
        - 命中但被禁用: 返回系统提示，不调用 LLM。
        - 未命中: 返回 None，继续原编排流程。
        """
        try:
            from backend.app.services.agent_config_service import (
                get_agent_config_service,
                strip_mention,
            )
            config = get_agent_config_service().find_mentioned(user_input)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Orchestrator] 配置型 Agent 识别失败: {exc}")
            return None

        if config is None:
            return None

        if not config.get("enabled", True):
            logger.info(f"[Orchestrator] 配置型 Agent 已禁用: {config['name']}")
            return {
                "cfg_0": AgentResponse(
                    agent_name=config.get("key", "configurable"),
                    success=True,
                    content=(
                        f"「{config['name']}」当前已被教师停用，暂时无法回复。"
                        "你可以直接提问，由系统内置 Agent 团队为你解答。"
                    ),
                    content_type="markdown",
                    metadata={"configurable": True, "disabled": True},
                )
            }

        logger.info(f"[Orchestrator] 配置型 Agent 命中: @{config['name']} ({config['key']})")
        from backend.app.agents.configurable_agent import ConfigurableAgent

        agent = ConfigurableAgent(config, llm_client=self.llm)
        agent_context = AgentContext(
            user_input=strip_mention(user_input, config["name"]) or user_input,
            session_id=session_id,
            profile=profile,
            course_name=course_name,
            conversation_history=conversation_history or [],
            rag_results=rag_results or [],
            extra={**(context or {}), "action": "configurable_reply", "task_id": "cfg_0"},
        )
        try:
            response = await agent.execute(agent_context)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[Orchestrator] ConfigurableAgent 异常: {exc}")
            response = AgentResponse(
                agent_name=config.get("key", "configurable"),
                success=False,
                error=str(exc),
            )
        return {"cfg_0": response}

    async def _classify_intent(self, user_input: str, context: dict) -> List[str]:
        """意图分类：显式@ + 规则匹配 + LLM 兜底

        Plan D · 3.1 — 关键词扩充 + 兜底 fallback 到 tutoring
        """
        matched: List[str] = []

        # 1. 显式 @ 提及路由（最高优先级）
        mentions = {
            "@智狐": "plan_path",
            "@智灵": "tutoring",
            "@小龙": "generate_exercise",
            "@团团": "evaluation",
            "@球球": "out_of_scope",  # 球球负责安全，用户直接@他闲聊走 safe_decline
        }
        # 阿匠是多模态资源伙伴，不能把所有 @阿匠 请求都先压成“文档”。
        # 显式资源词优先决定动作；没有资源词时才回退到通用讲义。
        if "@阿匠" in user_input:
            ajiang_intents = [
                ("generate_ppt", ("ppt", "PPT", "课件", "幻灯片", "演示文稿")),
                ("generate_mindmap", ("思维导图", "脑图", "知识图谱", "关系图")),
                ("generate_video", ("视频", "动画", "mp4")),
                ("generate_audio", ("语音", "音频", "配音", "tts")),
            ]
            explicit = [
                intent
                for intent, tokens in ajiang_intents
                if any(token in user_input for token in tokens)
            ]
            matched.extend(explicit or ["generate_doc"])
        for mention, intent in mentions.items():
            if mention in user_input:
                matched.append(intent)

        # 2. 规则快速匹配（每意图扩 5-12 个同义词）
        if not matched:
            intent_keywords = {
                "generate_ppt": [
                    "ppt", "PPT", "课件", "幻灯片", "演示文稿",
                ],
                "generate_doc": [
                    "讲解", "文档", "课程笔记", "知识点说明",
                    "整理", "总结", "归纳", "笔记", "复习材料",
                    "梳理", "汇总", "概览", "大纲", "讲义", "资料", "代码",
                ],
                "generate_mindmap": [
                    "思维导图", "知识图谱", "脑图",
                    "画个图", "整理图", "结构图", "关系图",
                ],
                "generate_exercise": [
                    "题目", "练习", "测试", "习题", "出题",
                    "考考我", "检验", "做几道", "巩固",
                    "刷题", "演练", "来一题", "出几道", "测评卷", "考卷",
                ],
                "generate_reading": [
                    "扩展", "拓展阅读", "参考资料",
                    "推荐阅读", "延伸材料", "更多材料", "论文", "导读",
                ],
                "generate_video": [
                    "视频", "动画", "演示",
                    "录个视频", "可视化讲解", "可不可以展示", "做个动图",
                ],
                "generate_audio": [
                    "语音", "音频", "朗读", "配音", "播客", "tts",
                    "读给我听", "语音导学", "音频讲解",
                ],
                "plan_path": [
                    "学习计划", "路径", "下一步", "怎么学",
                    "我下一步", "学什么", "该怎么走", "制定计划",
                    "帮我规划", "生成路线", "推荐路线", "学习路线", "学习路径",
                ],
                "tutoring": [
                    "为什么", "怎么办", "解释下", "不太懂",
                    "什么是", "区别是", "原理是", "怎么理解",
                    "教我", "帮我理解", "展开说", "细说", "举个例子",
                ],
                "evaluation": [
                    "诊断", "评估下", "测评", "水平",
                    "学得怎么样", "掌握了吗", "薄弱", "强弱项",
                ],
                # Plan D · Review v1 — 教学边界守门关键词
                # 命中时不追加 tutoring，直接路由到 safe_decline
                "out_of_scope": [
                    # —— 闲聊 ——（常见试探句）
                    "今天天气", "明天天气", "几点了", "现在几点",
                    "你是谁", "你叫什么", "你多大了", "你家几口人",
                    "你爱", "你喜欢", "你好棒", "你好可爱",
                    "退出", "关闭", "结束对话", "不学了", "不聊了",
                    # —— 越界敏感词 ——（演示现场抽测）
                    "邪教", "法轮", "颠覆", "色情", "裸聊", "约炮",
                    "自残", "自杀", "想死", "毒品",
                ],
            }

            for intent, keywords in intent_keywords.items():
                if any(kw in user_input for kw in keywords):
                    matched.append(intent)

        # 学生对话才更新个人画像。教师工作台传入的是班级/学生诊断快照，
        # 不应把教师指令误写入任何学生画像。
        is_teacher_request = (context or {}).get("role_view") == "teacher"
        if (
            not is_teacher_request
            and "profile_update" not in matched
            and "out_of_scope" not in matched
        ):
            matched.insert(0, "profile_update")

        # 如果没有规则匹配到，由 LLM 判断意图
        if len(matched) <= 1 or (
            len(matched) == 2 and "profile_update" in matched and "out_of_scope" in matched
        ):
            llm_intent = await self._llm_classify_intent(user_input)
            matched.extend(llm_intent)

        # Plan D · Review v1 — out_of_scope 主导时，**不再追加 tutoring 兜底**
        if "out_of_scope" in matched:
            matched = [m for m in matched if m != "tutoring"]
            # 如果原本只 profile_update + out_of_scope，去掉 profile_update
            if matched == ["profile_update", "out_of_scope"]:
                matched = ["out_of_scope"]
            if not matched:
                matched = ["out_of_scope"]
            return matched

        # Plan D · 3.1 — tutoring 兜底
        if matched == ["profile_update"]:
            matched.append("tutoring")

        return matched

    async def _llm_classify_intent(self, user_input: str) -> List[str]:
        """LLM 意图兜底 —— 当规则覆盖不到时调用 IntentClassifier

        Phase 1: 通过 services/intent_classifier.py 调用 LLM（2s 超时）
        Phase 2: 用标注数据训练 BERT-tiny 分类器替代

        Plan D · 3.1 — 异常时 fallback 到 ["tutoring"] 而非 []
        避免 orchestrator 不调度任何 Agent、返回空白。
        """
        try:
            from backend.app.services.intent_classifier import get_intent_classifier
            classifier = get_intent_classifier(self.llm)
            return await classifier.classify(user_input)
        except Exception as exc:
            logger.warning(
                f"[Orchestrator] IntentClassifier 失败: {exc}，fallback 到 tutoring"
            )
            return ["tutoring"]

    def _plan_tasks(self, intents: List[str], profile: dict) -> List[AgentTask]:
        """
        任务编排 —— 将意图列表转化为带依赖的任务DAG

        借鉴旧项目模式:
        - features/ 的依赖计算：先算 common_features → 再算 mode_features
        - 此处：先算 profile → 再根据结果决定生成哪些资源
        """
        tasks = []
        task_id = 0
        public_roles_seen: set[str] = set()
        tasks_by_public_role: Dict[str, AgentTask] = {}
        resource_actions = {
            "generate_doc", "generate_ppt", "generate_mindmap",
            "generate_video", "generate_audio", "generate_reading",
        }

        for intent in intents:
            if intent not in self.routing:
                continue

            route = self.routing[intent]
            public_role = AGENT_MENTION_NAMES.get(route["agent"], "")
            # 同一位公开伙伴只创建一个子任务。尤其是“思维导图 + 代码”会同时
            # 命中 generate_doc 与 generate_mindmap；过去因此生成两个阿匠任务，
            # 且其中一个可能只返回正文。保留首个综合资源任务，由阿匠一次交付
            # 所有明确请求的资源类型。
            if public_role and public_role in public_roles_seen:
                existing = tasks_by_public_role.get(public_role)
                # 同一位阿匠需要多种明确资源时合并为通用资源动作；
                # ResourceGeneratorAgent 会再次解析原文，得到 PPT+视频等完整子集。
                if (
                    existing
                    and public_role == "阿匠"
                    and existing.action in resource_actions
                    and intent in resource_actions
                ):
                    existing.action = "generate_doc"
                continue
            if public_role:
                public_roles_seen.add(public_role)
            task = AgentTask(
                task_id=f"task_{task_id}",
                agent_name=route["agent"],
                action=intent,
                input_data={"profile_snapshot": profile},
                priority=route["priority"],
            )
            tasks.append(task)
            if public_role:
                tasks_by_public_role[public_role] = task
            task_id += 1

        # 按优先级排序
        tasks.sort(key=lambda t: t.priority)
        return tasks

    def _get_or_create_agent(self, agent_name: str):
        """从注册表懒加载 Agent 实例，共享 LLMClient"""
        if agent_name not in self._agent_instances:
            agent_cls = self.agent_registry.get(agent_name)
            if not agent_cls:
                logger.warning(f"[Orchestrator] 未注册 Agent: {agent_name}，回退到 tutor")
                agent_cls = self.agent_registry.get("tutor")
            self._agent_instances[agent_name] = agent_cls(llm_client=self.llm)
        return self._agent_instances[agent_name]

    async def _run_agent(self, task: AgentTask, base_context: AgentContext) -> AgentResponse:
        """真实调用 Agent 的 execute() 方法"""
        agent = self._get_or_create_agent(task.agent_name)

        role_request = self._extract_role_request(
            base_context.user_input, task.agent_name,
        )

        # 复制一份上下文，避免不同 Agent 互相污染
        ctx = AgentContext(
            user_input=role_request or base_context.user_input,
            session_id=base_context.session_id,
            profile=dict(base_context.profile or {}),
            course_name=base_context.course_name,
            conversation_history=list(base_context.conversation_history or []),
            rag_results=list(base_context.rag_results or []),
            extra={
                **(base_context.extra or {}),
                "action": task.action,
                "task_id": task.task_id,
                "collaboration_request": base_context.user_input,
                "role_request": role_request,
            },
        )

        logger.info(f"[Orchestrator] Agent[{agent.name}] 执行 action={task.action}")
        try:
            response = await agent.execute(ctx)
            response = replace(response)
            # 强制用 task 中的路由角色名覆盖底层的类名，方便前端根据意图区分头像 (例如阿匠 vs 小龙)
            if response.agent_name == agent.name:
                response.agent_name = task.agent_name
            return response
        except Exception as exc:
            logger.exception(f"[Orchestrator] Agent[{agent.name}] 异常: {exc}")
            return AgentResponse(
                agent_name=task.agent_name,
                success=False,
                error=str(exc),
            )

    @staticmethod
    def _extract_role_request(user_input: str, agent_name: str) -> str:
        """从多 @ 总指令中提取当前 Agent 自己的那一项。

        支持比赛演示里常见的 ``1. @智狐 ...`` / ``2、@智灵 ...`` 格式。
        只有一处 @ 时也会去掉称呼后直接返回正文；画像 Agent 始终保留完整输入。
        """
        text = (user_input or "").strip()
        mention_name = AGENT_MENTION_NAMES.get(agent_name)
        if not text or not mention_name:
            return text

        mention = f"@{mention_name}"
        numbered = re.compile(
            rf"(?:^|\n)\s*(?:[-*+]\s*)?(?:\*\*)?\d+\s*[.、)]\s*"
            rf"(?:\*\*)?{re.escape(mention)}(?:\*\*)?\s*[-—:：]?\s*"
            rf"(.*?)(?=\n\s*(?:[-*+]\s*)?(?:\*\*)?\d+\s*[.、)]\s*(?:\*\*)?@|\Z)",
            flags=re.DOTALL,
        )
        match = numbered.search(text)
        if match:
            return match.group(1).strip(" \t\r\n：:；;")

        # 非编号格式：优先找一行中只提及当前角色的指令，跳过包含多个人名的总述。
        for line in text.splitlines():
            if mention not in line or line.count("@") != 1:
                continue
            directive = line.split(mention, 1)[1].strip(" \t*_-—：:；;，,")
            if directive:
                return directive

        # Markdown 列表也常把所有分工写在同一段。总述中的 @ 集群一般位于
        # 开头，而真正的角色指令会再次提及角色；取最后一次提及，再截到下一
        # 个公开角色，可避免智灵收到阿匠的导图/代码任务。
        occurrences = [match.start() for match in re.finditer(re.escape(mention), text)]
        if len(occurrences) >= 2:
            start = occurrences[-1] + len(mention)
            next_mentions = [
                pos
                for public_name in set(AGENT_MENTION_NAMES.values())
                for pos in [text.find(f"@{public_name}", start)]
                if pos >= 0
            ]
            end = min(next_mentions) if next_mentions else len(text)
            directive = text[start:end].strip(" \t\r\n*#_-—：:；;，,")
            directive = re.sub(r"\s*(?:\*\*)?\s*$", "", directive).strip()
            if directive:
                return directive

        # 单 Agent 明确 @ 时允许整段作为该角色任务；多 @ 时宁可保留总请求，
        # 也不截取开场白里的半句。
        if text.count("@") == 1 and mention in text:
            return text.split(mention, 1)[1].strip(" \t\r\n*_-—：:；;，,")
        return text
