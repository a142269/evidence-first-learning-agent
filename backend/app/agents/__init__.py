"""多智能体模块"""
from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.agents.profile_agent import ProfileAgent
from backend.app.agents.course_expert import CourseExpertAgent
from backend.app.agents.quiz_generator import QuizGeneratorAgent
from backend.app.agents.path_planner import PathPlannerAgent
from backend.app.agents.multimodal_agent import MultimodalAgent
from backend.app.agents.tutor_agent import TutorAgent
from backend.app.agents.evaluator_agent import EvaluatorAgent
from backend.app.agents.reviewer_agent import ReviewerAgent
from backend.app.agents.critic_agent import CriticAgent
from backend.app.agents.debate_moderator import DebateModeratorAgent, orchestrate_debate, should_debate
from backend.app.agents.cov_verifier import COVVerifierAgent
from backend.app.agents.safe_decline_agent import SafeDeclineAgent  # Plan D · Review v1
from backend.app.agents.knowledge_guard import KnowledgeGuardAgent  # 知识入库审核（防幻觉源头防线）
# 注: AILecturerAgent (manim.lecturer) 延迟导入，见文件末尾 —— 它依赖 agents.base，
# 若在此处直接 import 会形成 agents/__init__ → manim.lecturer → agents.base → agents/__init__ 的循环。
from backend.app.agents.textbook_qa_agent import TextbookQAAgent
from backend.app.agents.resource_generator_agent import ResourceGeneratorAgent
from backend.app.agents.orchestrator import AgentOrchestrator

AGENT_REGISTRY = {
    "profile": ProfileAgent, "profile_agent": ProfileAgent,
    "course_expert": CourseExpertAgent,
    # 2026-07-12：过去 exercise/mindmap/video 全指向 ResourceGeneratorAgent，
    # 导致"什么都是阿匠回答"。改为让专业 Agent 各自回：
    # - 出题 → QuizGenerator（小龙）
    # - 讲解 → TutorAgent（智灵）
    # - 多模态资料/图 → MultimodalAgent（阿匠专职）
    # - 路径 → PathPlanner（智狐）
    "generate_exercise": QuizGeneratorAgent,
    "quiz_generator": QuizGeneratorAgent,
    "exercise": QuizGeneratorAgent,
    "generate_mindmap": MultimodalAgent,
    "mindmap": MultimodalAgent,
    "multimodal": MultimodalAgent,
    # 音视频必须走统一资源生成链，才能真正调用 TTS / AgentVideoService，
    # 而不是只让 MultimodalAgent 返回一段 Markdown 大纲。
    "generate_video": ResourceGeneratorAgent,
    "video": ResourceGeneratorAgent,
    "generate_audio": ResourceGeneratorAgent,
    "audio": ResourceGeneratorAgent,
    # 文档 / 阅读 / 综合资源生成仍走 ResourceGeneratorAgent（阿匠）
    "generate_doc": ResourceGeneratorAgent,
    "doc_gen": ResourceGeneratorAgent,
    "generate_reading": ResourceGeneratorAgent,
    "reading": ResourceGeneratorAgent,
    "resource_generator": ResourceGeneratorAgent,
    # 路径 / 讲解 / 评估
    "plan_path": PathPlannerAgent,
    "path_planner": PathPlannerAgent,
    "tutoring": TutorAgent,
    "tutor": TutorAgent,
    "evaluation": EvaluatorAgent,
    "evaluator": EvaluatorAgent,
    "reviewer": ReviewerAgent, "critic": CriticAgent,
    "debate_moderator": DebateModeratorAgent,
    "cov_verifier": COVVerifierAgent,
    "knowledge_guard": KnowledgeGuardAgent,
    "safe_decline": SafeDeclineAgent,
    "out_of_scope": SafeDeclineAgent,
    "ai_lecturer": None,
    "textbook_qa": TextbookQAAgent,
}

# AILecturerAgent 延迟导入 + 注册：此时 agents 包已完全初始化，
# manim.lecturer 安全导入 agents.base 不再触发循环。
try:
    from backend.app.services.multimodal.manim.lecturer import AILecturerAgent
    AGENT_REGISTRY["ai_lecturer"] = AILecturerAgent
except ImportError:
    # manim 子系统不可用时静默跳过（不影响其余 Agent）
    AGENT_REGISTRY.pop("ai_lecturer", None)

__all__ = [
    "BaseAgent", "AgentContext", "AgentResponse",
    "ProfileAgent", "CourseExpertAgent", "QuizGeneratorAgent",
    "PathPlannerAgent", "MultimodalAgent", "ResourceGeneratorAgent", "TutorAgent",
    "EvaluatorAgent", "ReviewerAgent", "CriticAgent", "DebateModeratorAgent",
    "COVVerifierAgent", "SafeDeclineAgent", "KnowledgeGuardAgent",  # Plan D · Review v1
    "AILecturerAgent", "TextbookQAAgent",
    "AgentOrchestrator", "orchestrate_debate", "should_debate",
    "AGENT_REGISTRY",
]
