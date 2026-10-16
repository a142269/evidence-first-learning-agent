"""
画像分析师 Agent —— 对话式学习画像自主构建

对应赛题需求1：
  摒弃传统繁琐表单，支持通过自然语言对话自动抽取特征，
  构建包含不少于6个维度的动态学生画像，并支持画像的随学随新。

设计迁移自旧项目 services/portraits/ 的画像构建逻辑

B 角色升级（Day 5）：
  - 画像输出自动带 archetype_code（9 种学习者类型）
  - 集成 BKT 掌握度 snapshot 到 metadata
  - 集成 DINA 主导知识点
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse

logger = logging.getLogger(__name__)


class ProfileAgent(BaseAgent):
    """画像分析师 —— 通过对话提取学生特征，构建≥6维画像（B 升级版）"""

    @property
    def name(self) -> str:
        return "profile_agent"

    @property
    def description(self) -> str:
        return "通过自然语言对话提取学生特征，构建和更新多维学习画像（含学习者类型识别）"

    @property
    def system_prompt(self) -> str:
        return (
            "Profile output MUST follow standard-8 schema keys: knowledge_base, cognitive_style, error_pattern, learning_habit, learning_progress, interest_model, resource_preference, self_learning_ability. Legacy keys may be used only as aliases.\n\n"
            "你是一名专业的学习画像分析师。你的任务是通过自然对话提取学生的学习特征。\n\n"
            "你需要关注并提取以下8个维度的信息：\n"
            "1. 知识基础 (knowledge_base): 学生已掌握的知识点、课程基础\n"
            "2. 认知风格 (cognitive_style): 视觉型/听觉型/动手型、抽象思维/具象思维\n"
            "3. 易错倾向 (error_pattern): 易错点、知识盲区与反复出现的错因\n"
            "4. 学习习惯 (learning_habit): 学习节奏、可用时间与活跃时段\n"
            "5. 学习进度 (learning_progress): 当前阶段、已完成内容与待学习内容\n"
            "6. 兴趣目标 (interest_model): 考试/竞赛/科研/就业目标与领域兴趣\n"
            "7. 资源偏好 (resource_preference): 视频/文档/练习/项目等资源与难度偏好\n"
            "8. 自主学习能力 (self_learning_ability): 学习信心、主动性、反思与协作方式\n\n"
            "要求：\n"
            "- 用温暖、自然的语气引导对话，像朋友聊天一样\n"
            "- 不要一次问太多问题，每次聚焦1-2个维度\n"
            "- 根据学生的回答自动推断特征\n"
            "- 在回复末尾用 JSON 格式附上提取到的画像更新（用 ```profile_update``` 包裹）\n"
            "- JSON 格式示例：\n"
            '```profile_update\n'
            '{"knowledge_base": {"level": "中等", "known_topics": ["Python基础", "数据结构"]}, '
            '"resource_preference": {"preferred_format": "视频+代码实践"}, '
            '"self_learning_ability": {"initiative": "主动", "confidence": 0.7}}\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行画像提取对话 —— B 升级版"""
        # 构建画像感知的 Prompt
        profile_summary = self._summarize_profile(context.profile)
        extra = f"\n当前学生画像:\n{profile_summary}" if profile_summary else ""

        result = await self._acall_llm(
            user_prompt=context.user_input,
            history=context.conversation_history,
            extra_system=extra,
            temperature=0.7,
        )

        # 提取画像更新
        # Plan D · 2.3 — 同时取 status 一起塞到 metadata 给上游
        from backend.app.services.profile_extractor import extract_profile_updates as _ext2
        profile_updates, profile_status = _ext2(result)
        profile_status_meta = (
            "success" if profile_status == "success"
            else "no_profile_block"
            if profile_status == "no_profile_block"
            else "json_parse_failed"
        )

        # 从展示内容中移除 ```profile_update``` / ```json``` 代码块
        import re
        result = re.sub(r"```profile_update\s*\n[\s\S]*?\n```", "", result).strip()
        result = re.sub(r"```json\s*\n\{[\s\S]*?\}\s*\n```", "", result).strip()
        result = re.sub(r"\n{3,}", "\n\n", result).strip()

        # ── B 升级：计算学习者类型 ──
        archetype_code = ""
        archetype_data = {}
        try:
            # 合并当前画像 + 本次更新
            merged = {**context.profile, **profile_updates}
            # 提取数值快照
            dimensions_snapshot = self._to_numeric_snapshot(merged)
            if dimensions_snapshot:
                from backend.app.services.learner_archetype import LearnerArchetypeService
                svc = LearnerArchetypeService()
                archetype_result = svc.identify(dimensions_snapshot)
                archetype_code = archetype_result.get("code", "")
                archetype_data = archetype_result
        except Exception as exc:
            logger.warning(f"[ProfileAgent] archetype 识别失败: {exc}")

        # ── B 升级：BKT + DINA 数据 ──
        dina_snapshot = {}
        try:
            # FIX-03：用真实学生 ID（extra["user_id"]）查询认知状态，session_id 仅兜底
            user_id = context.user_id
            from backend.app.services.cognitive_diagnosis.bkt import get_bkt
            bkt = get_bkt()
            dina_snapshot = bkt.get_all_masteries(user_id)
        except Exception:
            pass

        # ── A Day 8 wire-in: RealDINAAdapter (AUC 0.8024 on ASSISTments-2009)
        # exposed via the per-user precomputed snapshot service.
        realdina_snapshot: dict[str, float] = {}
        realdina_strengths: list[tuple[str, float]] = []
        realdina_weaknesses: list[tuple[str, float]] = []
        try:
            from backend.app.services.realdina_service import get_realdina_service
            user_id = context.user_id  # FIX-03：真实学生 ID
            svc = get_realdina_service()
            realdina_snapshot = svc.snapshot_for(user_id)
            realdina_strengths = svc.top_strengths(user_id, k=3)
            realdina_weaknesses = svc.top_weaknesses(user_id, k=3)
        except Exception as exc:
            logger.warning(f"[ProfileAgent] RealDINA snapshot unavailable: {exc}")

        return self._success(
            content=result,
            content_type="markdown",
            profile_updates=profile_updates,
            metadata={
                "archetype_code": archetype_code,
                "archetype": archetype_data,
                "dina_snapshot": dina_snapshot,
                "realdina_snapshot": realdina_snapshot,
                "realdina_strengths": realdina_strengths,
                "realdina_weaknesses": realdina_weaknesses,
                # Plan D · 2.3 — 画像提取状态给前端弹 Toast
                "profile_extract_status": profile_status_meta,
                "profile_dimensions_count": len(profile_updates) if profile_updates else 0,
            },
        )

    def _to_numeric_snapshot(self, profile: dict) -> dict:
        """把非数值画像转成 0-1 评分快照（供 LearnerArchetypeService 使用）"""
        snapshot = {}
        for dim in ["knowledge_base", "cognitive_style", "learning_preference",
                     "weak_points", "learning_goal", "time_management",
                     "self_efficacy", "interaction_pattern"]:
            value = profile.get(dim)
            if isinstance(value, dict):
                score = value.get("score", value.get("confidence", 0.5))
                if isinstance(score, str) and score in {"低", "中", "高"}:
                    score = {"低": 0.3, "中": 0.6, "高": 0.85}.get(score, 0.5)
                snapshot[dim] = float(score) if score else 0.5
            elif isinstance(value, (int, float)):
                snapshot[dim] = float(value)
            elif isinstance(value, str):
                level_map = {"初级": 0.3, "中级": 0.6, "高级": 0.85, "入门": 0.2}
                snapshot[dim] = level_map.get(value, 0.5)
            else:
                snapshot[dim] = 0.5
        return snapshot

    def _summarize_profile(self, profile: dict) -> str:
        """将画像数据转为可读摘要"""
        if not profile:
            return "（尚未建立画像，这是首次对话）"

        parts = []
        dim_labels = {
            "knowledge_base": "知识基础",
            "cognitive_style": "认知风格",
            "learning_preference": "学习偏好",
            "weak_points": "薄弱环节",
            "learning_goal": "学习目标",
            "time_management": "时间管理",
            "self_efficacy": "自我效能",
            "interaction_pattern": "交互模式",
        }
        for key, label in dim_labels.items():
            value = profile.get(key)
            if value:
                parts.append(f"- {label}: {json.dumps(value, ensure_ascii=False)}")

        return "\n".join(parts) if parts else "（画像数据较少）"

    def _extract_profile_updates(self, llm_output: str) -> dict:
        """Plan D · 2.3 — 容错提取 LLM 输出中的画像更新 JSON

        通过 services.profile_extractor 替换原简单正则：
        * 支持 ```profile_update / ```json / 无标签 fence
        * 容错 JSON 注释（// 和 /* */）+ 尾逗号
        * 提供 fallback：找首个 top-level {...}
        * 返回 (profile, status) 让调用方上报 SSE

        本方法保留旧 API（仅返回 dict），但内部走容错路径。
        """
        try:
            from backend.app.services.profile_extractor import extract_profile_updates as _ext
            profile, _status = _ext(llm_output)
            return profile
        except Exception as exc:
            logger.warning(f"[ProfileAgent] 容错提取失败: {exc}")
            return {}
