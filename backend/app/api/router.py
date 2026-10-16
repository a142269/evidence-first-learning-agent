from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.profile import router as profile_router
from backend.app.api.v1.resources import router as resources_router
from backend.app.api.v1.learning_path import router as learning_path_router
from backend.app.api.v1.assessment import router as assessment_router
from backend.app.api.v1.knowledge import router as knowledge_router
# -- A 拥有的新路由 --
from backend.app.api.v1.artifacts import router as artifacts_router
from backend.app.api.v1.metrics import router as metrics_router
from backend.app.api.v1.system import router as system_router
from backend.app.api.v1.insights import router as insights_router
from backend.app.api.v1.safety import router as safety_router
from backend.app.api.v1.learner_state import router as learner_state_router
from backend.app.api.v1.agent_tools import router as agent_tools_router
# -- B 拥有的新路由 --
from backend.app.api.v1.mistakes import router as mistakes_router
from backend.app.api.v1.cognitive import router as cognitive_router
from backend.app.api.v1.knowledge_graph import router as knowledge_graph_router
from backend.app.api.v1.gamification import router as gamification_router
from backend.app.api.v1.social import router as social_router
# -- A+B 聚合路由（6/24 加） --
from backend.app.api.v1.cockpit import router as cockpit_router
# -- 师生协作（7/9 加）：教师管理端 + 课程群聊 --
from backend.app.api.v1.teacher import router as teacher_router
# -- 知识库平台化（7/16 加）：教师端知识库管理（建课/上传/审核/命中测试） --
from backend.app.api.v1.knowledge_admin import router as knowledge_admin_router
from backend.app.api.v1.group_chat import router as group_chat_router
from backend.app.api.v1.mobile import router as mobile_router
# -- learner 视角查询（7/9 加）：补齐 GraphView 既有调用 --
from backend.app.api.v1.learner import router as learner_router

# -- Plan D · 3.3 间隔重复端点 --
from backend.app.api.v1.spaced_repetition import router as spaced_repetition_router
from backend.app.api.v1.smart_tutor import router as smart_tutor_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(profile_router)
api_router.include_router(resources_router)
api_router.include_router(learning_path_router)
api_router.include_router(assessment_router)
api_router.include_router(knowledge_router)
# -- A 路由 --
api_router.include_router(artifacts_router)
api_router.include_router(metrics_router)
api_router.include_router(system_router)
api_router.include_router(insights_router)
api_router.include_router(safety_router)
api_router.include_router(learner_state_router)
api_router.include_router(agent_tools_router)
# -- B 路由 --
api_router.include_router(mistakes_router)
api_router.include_router(cognitive_router)
api_router.include_router(knowledge_graph_router)
api_router.include_router(gamification_router)
api_router.include_router(social_router)
# -- A+B 聚合 --
api_router.include_router(cockpit_router)
# -- 师生协作 --
api_router.include_router(teacher_router)
api_router.include_router(knowledge_admin_router)
api_router.include_router(group_chat_router)
api_router.include_router(mobile_router)
# -- learner 视角查询 --
api_router.include_router(learner_router)

# -- Plan D · 3.3 --
api_router.include_router(spaced_repetition_router)
api_router.include_router(smart_tutor_router)
