"""
输出侧 2 阶段 (6-7): 聚合 / 持久化
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from backend.app.agents.base import AgentResponse
from backend.app.agents.reviewer_agent import quick_quality_score
from backend.app.api.v1.chat_pipeline.pipeline import PipelineContext, Stage
from backend.app.api.v1.chat_pipeline.session import SessionStore
from backend.app.api.v1.chat_pipeline.stages._shared import get_shared_safety
from backend.app.services.safety.content_filter import FilterLevel

logger = logging.getLogger(__name__)


# ================================================================
# Stage 6: 聚合 + 安全过滤 + 质量评分
# ================================================================
class AggregationStage(Stage):
    """阶段 6: 选 primary Agent + 合并辅助 Agent + 安全过滤 + 质量评分"""

    name = "aggregation"
    timeout_seconds = 5.0
    fatal_on_fail = False

    PROFILE_AGENT_NAMES = frozenset({"profile_agent", "profile"})
    META_AGENT_NAMES = frozenset({
        "reviewer", "critic_agent", "critic", "debate_moderator",
    })

    async def run(self, ctx: PipelineContext) -> None:
        primary, profile_resp, others, agg_text = self._select_primary(
            ctx.agent_results,
        )
        ctx.primary_response = primary
        ctx.profile_response = profile_resp
        ctx.other_resources = others

        if primary is None:
            primary = profile_resp or AgentResponse(
                agent_name="tutor_agent", success=False,
                content="Sorry, no response generated.",
                error="no_agent_response",
            )
            ctx.primary_response = primary

        full_text = (primary.content or "") + (
            "".join(agg_text) if agg_text else ""
        )

        await self._apply_safety(ctx, full_text)
        full_text = ctx.aggregated_text or full_text

        # 集中式清洗：移除所有结构化 JSON 代码块，避免聊天界面显示原始 JSON
        full_text = self._strip_structured_blocks(full_text)

        ctx.quality = quick_quality_score(
            full_text, primary.content_type or "document",
        )
        ctx.aggregated_text = full_text

    @staticmethod
    def _strip_structured_blocks(text: str) -> str:
        """移除 Agent 输出中的结构化 JSON 代码块。"""
        import re
        # 1. 移除 ```evaluation_result ... ```
        text = re.sub(r"```evaluation_result\s*\n[\s\S]*?\n```", "", text)
        # 2. 移除 ```profile_update ... ```
        text = re.sub(r"```profile_update\s*\n[\s\S]*?\n```", "", text)
        # 2.5 移除仅供程序解析的题库/路径结构块
        text = re.sub(
            r"```(?:quiz_json|learning_path)\s*\n[\s\S]*?\n```",
            "", text, flags=re.IGNORECASE,
        )
        # 3. 移除 ```json ... ``` 包裹的 JSON（仅含结构化标记字段时）
        text = re.sub(
            r"```(?:json|JSON)?\s*\n(\{[\s\S]*?\})\s*\n```",
            lambda m: "" if any(
                k in m.group(1) for k in
                ("overall_score", "dimensions", "strengths", "weaknesses",
                 "path_adjustments", "profile_updates", "knowledge_base",
                 "learning_preference")
            ) else m.group(0),
            text,
        )
        # 结构块删除后不保留“结构化数据 (JSON)”这类孤立标题。
        text = re.sub(
            r"(?im)^\s{0,3}(?:#{1,6}\s*)?(?:\*\*)?"
            r"(?:结构化数据(?:\s*[（(]?JSON[）)]?)?|路径\s*JSON|JSON\s*数据)"
            r"(?:\*\*)?\s*[:：]?\s*$",
            "",
            text,
        )
        # 4. 清理多余空行
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def _select_primary(
        self, agent_results: Dict[str, AgentResponse],
    ) -> Tuple[
        Optional[AgentResponse],
        Optional[AgentResponse],
        List[Dict[str, Any]],
        List[str],
    ]:
        primary: Optional[AgentResponse] = None
        profile: Optional[AgentResponse] = None
        others: List[Dict[str, Any]] = []
        agg_parts: List[str] = []

        for resp in agent_results.values():
            if resp.agent_name in self.PROFILE_AGENT_NAMES:
                profile = resp
                continue
            if resp.agent_name in self.META_AGENT_NAMES:
                continue
            if not resp.success:
                continue
            if primary is None:
                primary = resp
            else:
                others.extend(resp.resources or [])
                agg_parts.append(
                    f"\n\n---\n\n## {resp.agent_name} co-generated\n\n"
                    f"{resp.content}"
                )
        return primary, profile, others, agg_parts

    async def _apply_safety(
        self, ctx: PipelineContext, full_text: str,
    ) -> None:
        safety = ctx.services.get("safety") or get_shared_safety()
        ctx.safety_flag = "pass"
        ctx.safety_reason = ""
        try:
            result = await safety.validate(full_text)
            if result and result.level == FilterLevel.BLOCK:
                ctx.safety_flag = "block"
                ctx.safety_reason = result.reason
                ctx.aggregated_text = "Content blocked for safety."
            elif result and result.level == FilterLevel.WARN:
                ctx.safety_flag = "warn"
                ctx.safety_reason = result.reason
                ctx.aggregated_text = full_text
            else:
                ctx.aggregated_text = full_text
        except Exception as exc:
            logger.warning(f"[Pipeline] safety check error: {exc}")
            ctx.aggregated_text = full_text

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        if ctx.primary_response is None:
            ctx.primary_response = AgentResponse(
                agent_name="tutor_agent", success=False,
                content="Sorry, aggregation failed.",
                error=str(error),
            )
        ctx.aggregated_text = ctx.primary_response.content or ""
        ctx.quality = {}
        return True


# ================================================================
# Stage 7: 持久化 (资源 / 评估 / 历史)
# ================================================================
class PersistStage(Stage):
    """阶段 7: 持久化 - 失败不致命"""

    name = "persist"
    timeout_seconds = 3.0
    fatal_on_fail = False

    async def run(self, ctx: PipelineContext) -> None:
        store: SessionStore = ctx.services["session_store"]
        session = ctx.session

        self._merge_profile(ctx, store, session)
        self._save_primary_resources(ctx, session)
        self._save_other_results(ctx, session)
        self._maybe_record_primary_assessment(ctx, session)
        # 2026-07-12 修复：过去 chat 从不写入 RealDINA，导致「问助手学情为 0」。
        # 现在每轮对话按 RAG 命中的 kp_ids 做一次 BKT 在线更新——
        # 学生问的方向被视为「正在学」（correct=False 的软负反馈），
        # 教学概览与学情面板即会随对话缓慢变化。
        self._maybe_update_learner_state(ctx, session)

        store.append_history(session, "user", ctx.user_input)
        # 多 Agent 群聊要逐条保存每位伙伴自己的正文与身份；否则刷新后又会
        # 退化成一条 primary Agent 聚合消息，看起来像所有内容都由同一人回答。
        public_agent_names = {
            "path_planner", "path_planner_agent", "tutor", "tutor_agent",
            "doc_gen", "resource_generator", "resource_generator_agent",
            "mindmap", "reading", "video", "audio", "exercise", "quiz_generator",
            "evaluator", "evaluator_agent", "safe_decline",
        }
        public_responses = [
            response for response in ctx.agent_results.values()
            if response.agent_name in public_agent_names
            and (response.content or "").strip()
        ]
        public_order = {
            "path_planner": 0, "path_planner_agent": 0,
            "tutor": 1, "tutor_agent": 1,
            "doc_gen": 2, "resource_generator": 2, "resource_generator_agent": 2,
            "mindmap": 2, "reading": 2, "video": 2, "audio": 2,
            "exercise": 3, "quiz_generator": 3,
            "evaluator": 4, "evaluator_agent": 4, "safe_decline": 5,
        }
        public_responses.sort(key=lambda response: public_order.get(response.agent_name, 99))
        if len(public_responses) > 1:
            for response in public_responses:
                store.append_history(
                    session,
                    "assistant",
                    response.content,
                    agent_name=response.agent_name,
                    resources=list(response.resources or []),
                )
        else:
            # 记录主导 Agent 名称，前端刷新后可据此恢复正确头像
            primary_agent_name = (
                ctx.primary_response.agent_name if ctx.primary_response else ""
            )
            store.append_history(
                session, "assistant", ctx.aggregated_text,
                agent_name=primary_agent_name,
                resources=list(
                    ctx.primary_response.resources or []
                    if ctx.primary_response else []
                ),
            )

    def _merge_profile(
        self,
        ctx: PipelineContext,
        store: SessionStore,
        session: Dict[str, Any],
    ) -> None:
        # 单 Agent 模式: 不把主 Agent 的 profile_updates 合并进画像
        if ctx.single_agent_mode:
            return
        if ctx.profile_response and ctx.profile_response.profile_updates:
            store.merge_profile(session, ctx.profile_response.profile_updates)
        elif ctx.primary_response and ctx.primary_response.profile_updates:
            store.merge_profile(session, ctx.primary_response.profile_updates)
        # 2026-07-12 修复：即使 Agent 没显式写 profile_updates，也把本轮
        # 涉及的主题/知识点写入 recent_topics 与 last_interaction_at，
        # 学习画像与规划面板才能"随对话变化"。
        self._touch_activity_traces(ctx, store, session)

    @staticmethod
    def _touch_activity_traces(
        ctx: PipelineContext,
        store: SessionStore,
        session: Dict[str, Any],
    ) -> None:
        try:
            trace_updates: Dict[str, Any] = {"last_interaction_at": time.time()}
            existing = (session.get("profile") or {}).get("recent_topics") or []
            recent: List[str] = [str(x) for x in existing if isinstance(x, (str, int))]
            new_topic = (ctx.user_input or "").strip().replace("\n", " ")[:60]
            if new_topic and new_topic not in recent:
                recent.insert(0, new_topic)
            for hit in ctx.rag_results[:3]:
                if not isinstance(hit, dict):
                    continue
                meta = hit.get("metadata") or {}
                kp = meta.get("kp_id") or hit.get("kp_id") or ""
                if kp and str(kp) not in recent:
                    recent.insert(0, str(kp))
            trace_updates["recent_topics"] = recent[:12]
            store.merge_profile(session, trace_updates)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Pipeline] touch activity traces failed: {exc}")

    def _save_primary_resources(
        self, ctx: PipelineContext, session: Dict[str, Any],
    ) -> None:
        if ctx.primary_response and ctx.primary_response.resources:
            ctx.saved_resources.extend(
                self._save_resources(
                    session["user_id"],
                    ctx.primary_response.agent_name,
                    ctx.primary_response,
                )
            )

    def _save_other_results(
        self, ctx: PipelineContext, session: Dict[str, Any],
    ) -> None:
        for resp in ctx.agent_results.values():
            if resp is ctx.primary_response:
                continue
            if resp.agent_name in {"profile_agent", "reviewer"}:
                continue
            if resp.success and resp.resources:
                ctx.saved_resources.extend(
                    self._save_resources(
                        session["user_id"], resp.agent_name, resp,
                    )
                )
            if resp.success and resp.agent_name == "evaluator_agent":
                self._record_assessment(session["user_id"], resp)

    def _maybe_record_primary_assessment(
        self, ctx: PipelineContext, session: Dict[str, Any],
    ) -> None:
        if (
            ctx.primary_response
            and ctx.primary_response.agent_name == "evaluator_agent"
        ):
            self._record_assessment(
                session["user_id"], ctx.primary_response,
            )

    @staticmethod
    def _save_resources(
        user_id: str, agent_name: str, response: AgentResponse,
    ) -> List[Dict[str, Any]]:
        """保存 Agent 生成的资源到资源库。

        注意：只保存有实际产物（文件/题库/路径）的资源元数据，
        不把 AI 的文字回复内容（response.content）存为资源。
        聊天回复文本由 SessionStore.append_history 持久化到 chat_history 表。
        """
        saved: List[Dict[str, Any]] = []
        if not response.resources:
            return saved
        try:
            from backend.app.api.v1 import resources as resources_api
            for res in response.resources:
                rid = f"res_{uuid.uuid4().hex[:10]}"
                rtype = res.get("type", "document")
                if rtype == "learning_path":
                    PersistStage._save_learning_path(user_id, response, res)
                    continue
                # 只保存资源元数据，不把 AI 回复文本存为资源 content
                record = {
                    "id": rid,
                    "user_id": user_id,
                    "type": rtype,
                    "title": res.get("title") or f"{agent_name} generated",
                    "content": "",  # 不存聊天回复文本
                    "content_type": response.content_type,
                    "agent_name": agent_name,
                    # source=chat：资源库前端据此归入「聊天存档」而非「学习资源」
                    "metadata": {**res, **(response.metadata or {}), "source": "chat"},
                    "created_at": time.time(),
                    "tags": [agent_name, rtype],
                }
                resources_api.persist_resource(record)  # 内存 + SQLite 双写，重启不丢
                saved.append(
                    {"id": rid, "type": rtype, "title": record["title"]}
                )
        except Exception as exc:
            logger.warning(f"[Pipeline] save resource failed: {exc}")
        return saved

    @staticmethod
    def _save_learning_path(
        user_id: str, response: AgentResponse, res_meta: Dict[str, Any],
    ) -> None:
        try:
            from backend.app.api.v1 import learning_path as lp_api
            path_data = (response.metadata or {}).get("path_data") or {}
            stages = path_data.get("stages") or []
            if not stages:
                return
            pid = f"path_{uuid.uuid4().hex[:10]}"
            record = {
                "id": pid,
                "user_id": user_id,
                "title": res_meta.get("title") or "learning path",
                "stages": stages,
                "current_stage": 0,
                "progress": 0.0,
                "created_at": time.time(),
                "source": "chat",
                "agent_name": response.agent_name,
            }
            # FIX-01（2026-07-17）：优先写入 LearningPathRepository，
            # 保证 /learning-path/list 等标准接口可读且重启后仍存在；
            # 内存字典仅作为 repository 不可用时的降级路径。
            repository = getattr(lp_api, "_repository", None)
            if repository is not None:
                repository.save(record)
            else:
                lp_api._paths[pid] = record
        except Exception as exc:
            logger.warning(f"[Pipeline] save path failed: {exc}")

    @staticmethod
    def _maybe_update_learner_state(
        ctx: PipelineContext, session: Dict[str, Any],
    ) -> None:
        """把每轮对话涉及到的知识点写入 RealDINA/BKT 掌握度快照。

        当前策略：
        - 从 ctx.rag_results 前 3 条命中，取 metadata.kp_id
        - 命中的 kp_id 视为学生「已接触」，按弱正反馈更新（correct=False 但 bayes_step 会
          把掌握度向 0 拖，只是幅度小；这符合"提问=还没掌握"的假设，避免把无
          证据的对话当成"答对"）
        - 一轮对话最多更新 3 个 kp，避免带偏所有掌握度
        """
        try:
            user_id = str(session.get("user_id", "")).strip()
            if not user_id:
                return
            kp_ids: List[str] = []
            for hit in ctx.rag_results[:3]:
                meta = hit.get("metadata") if isinstance(hit, dict) else None
                if isinstance(meta, dict):
                    kp = meta.get("kp_id") or meta.get("knowledge_point")
                    if kp:
                        kp_ids.append(str(kp))
                        continue
                # 兼容形如 {"kp_id": "AI_003"} 的扁平结构
                if isinstance(hit, dict):
                    kp = hit.get("kp_id")
                    if kp:
                        kp_ids.append(str(kp))
            kp_ids = list(dict.fromkeys(kp_ids))[:3]
            if not kp_ids:
                return
            from backend.app.services.realdina_service import get_realdina_service
            # 提问视为"接触"，按 correct=False 让掌握度以极小步长下探；
            # 后续做题的显式反馈会以 correct=True 上拉。用户能明显看到面板动。
            get_realdina_service().record_response(user_id, kp_ids, correct=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Pipeline] realdina record failed: {exc}")

    @staticmethod
    def _record_assessment(user_id: str, response: AgentResponse) -> None:
        if not response.metadata or "evaluation_data" not in response.metadata:
            return
        try:
            eval_data = response.metadata["evaluation_data"]
            record = {
                "external_id": (response.metadata or {}).get("evaluation_id"),
                "type": "evaluation",
                "score": eval_data.get("overall_score", 0) * 100,
                "topic": str(eval_data.get("topic") or "assessment"),
                "duration": 0,
                "timestamp": time.time(),
                "metadata": eval_data,
            }
            # FIX-02（2026-07-17）：优先写入 AssessmentRepository（SQLite），
            # 让团团的评估进入正式评估接口 / LearnerState / 学习时间线；
            # 内存字典仅作为数据库不可用时的降级路径。
            try:
                from backend.app.repositories.assessment_repo import AssessmentRepository

                AssessmentRepository().add(user_id, record)
            except Exception as repo_exc:  # noqa: BLE001
                logger.warning(f"[Pipeline] assessment repo failed, fallback memory: {repo_exc}")
                from backend.app.api.v1 import assessment as assessment_api

                assessment_api._assessments.setdefault(user_id, []).append(record)
        except Exception as exc:
            logger.warning(f"[Pipeline] assessment persist failed: {exc}")

    async def fallback(self, ctx: PipelineContext, error: Exception) -> bool:
        logger.warning(f"[Pipeline] persist fallback: {error}")
        return True
