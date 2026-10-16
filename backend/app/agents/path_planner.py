"""
路径规划师 Agent —— 个性化学习路径规划和资源推送

对应赛题需求3：
  依托多智能体协同工作机制，结合大模型对学生专业、学习进度、
  知识掌握情况及学习偏好的深度分析，为学生规划科学、动态的个性化学习路径

B 角色升级（Day 5）：
  - 接入知识图谱拓扑排序（prerequisite 约束）
  - ε-greedy Bandit 策略选择下一步知识点
  - ZPD 最近发展区优先推送
  - 输出 confidence_score + zpd_kps 到 metadata
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.cognitive_diagnosis.bkt import get_bkt
from backend.app.services.cognitive_diagnosis.bloom_taxonomy import BloomTaxonomy
from backend.app.services.spaced_repetition.sm2 import get_sm2

logger = logging.getLogger(__name__)


class PathPlannerAgent(BaseAgent):
    """路径规划师 —— 基于画像 + KG + Bandit + ZPD 规划个性化学习路径"""

    @property
    def name(self) -> str:
        return "path_planner"

    @property
    def description(self) -> str:
        return "基于学习画像、知识图谱和 ZPD 理论规划个性化学习路径"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名资深的学习规划师，擅长为学生制定个性化学习计划。\n\n"
            "你的任务是根据学生画像和课程知识体系，规划科学的学习路径。\n\n"
            "要求：\n"
            "1. 分析学生当前水平和目标差距\n"
            "2. 将学习目标拆解为阶段性里程碑\n"
            "3. 每个阶段包含：学习内容、预计时长、推荐资源类型、评估方式\n"
            "4. 考虑知识点之间的依赖关系（先修知识）\n"
            "5. 根据学生时间安排调整节奏\n"
            "6. 提供灵活的调整建议\n"
            "7. 若用户给出固定天数/题量/目标数，必须严格遵守；短期计划用 Markdown 表格逐日展示\n"
            "8. 每日目标必须可验收，并同时写明时间预算、先修依赖、动手产物、检查点和跟不上时的降级方案\n\n"
            "输出格式：\n"
            "- 先用自然语言给出路径概述\n"
            "- 然后用结构化数据描述路径节点\n"
            "- 在末尾用 ```learning_path``` 包裹路径 JSON\n\n"
            "路径 JSON 格式：\n"
            '```learning_path\n'
            '{"stages": [{"id": 1, "title": "...", "topics": ["..."], '
            '"duration": "1周", "resources": ["文档", "练习"], '
            '"prerequisites": [], "assessment": "完成练习题"}]}\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """规划学习路径 —— B 升级版"""
        user_prompt = self._build_prompt(context)

        # ── B 升级：先跑 Bandit + ZPD 计算 ──
        zpd_kps, bandit_choice, confidence, arm_pulls = self._compute_zpd_bandit(context)

        # 把 ZPD + Bandit 结果注入 prompt
        if zpd_kps:
            zpd_hint = "\n\n## 算法推荐（最近发展区 ZPD + Thompson Sampling）\n"
            zpd_hint += f"建议优先学习以下知识点（ZPD 区，mastery 0.5-0.8）：\n"
            for kp_name in zpd_kps[:5]:
                zpd_hint += f"  - {kp_name}\n"
            if bandit_choice:
                zpd_hint += f"\nBandit 推荐下一步：{bandit_choice}（confidence={confidence:.2f}）\n"
            user_prompt += zpd_hint

        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=self._strategy_extra_system(context),
            temperature=0.5,
        )

        path_data = self._extract_path_data(result)
        readable_result = self._strip_path_block(result)

        return self._success(
            content=readable_result,
            content_type="learning_path",
            resources=[{
                "type": "learning_path",
                "title": "个性化学习路径",
                "stages_count": len(path_data.get("stages", [])),
            }],
            metadata={
                "path_data": path_data,
                "zpd_kps": zpd_kps,
                "bandit_choice": bandit_choice,
                "confidence_score": confidence,
                "arm_pulls": arm_pulls,
            },
        )

    # ── ZPD + Bandit 核心算法（Thompson Sampling 升级）───
    def _compute_zpd_bandit(self, context: AgentContext) -> tuple:
        """计算 ZPD 候选知识点 + Thompson Sampling 选择。

        ZPD (Vygotsky 1978): mastery 0.5-0.8 + 前置已掌握的下一知识点
        Thompson Sampling (Thompson 1933):
          对每个候选构建 Beta(α, β) 后验，抽样选最高分。
          比 ε-greedy 更精细：探索/利用自动平衡，不确定性高的候选自然被多试。
          多目标奖励：mastery_gain × bloom_weight × interest × time_fit

        Returns:
            (zpd_kps, bandit_choice, confidence_score, arm_pulls)
        """
        bkt = get_bkt()
        user_id = context.user_id  # FIX-03：真实学生 ID（extra["user_id"]），session_id 仅兜底
        masteries = bkt.get_all_masteries(user_id)

        if not masteries:
            profile = context.profile or {}
            kb = profile.get("knowledge_base", {})
            topics = kb.get("topics", []) if isinstance(kb, dict) else []
            masteries = {t: 0.7 for t in topics}

        # ZPD 区 + 前置邻居
        zpd_candidates = {kp: m for kp, m in masteries.items() if 0.5 <= m <= 0.8}
        next_candidates: Dict[str, float] = {}
        try:
            from backend.app.services.knowledge_graph.store import get_kg_store
            kg = get_kg_store()
            for kp_name, mastery in masteries.items():
                if mastery >= 0.7:
                    kps = kg.find_by_name(kp_name)
                    for kp in kps:
                        for nb in kg.get_neighbors(kp.id, direction="out"):
                            nb_kp = kg.get_kp(nb["kp_id"])
                            if nb_kp and nb_kp.name not in masteries:
                                next_candidates[nb_kp.name] = 0.3
        except Exception as exc:
            logger.warning("[PathPlanner] knowledge graph candidates unavailable: %s", exc)

        all_candidates = {**zpd_candidates, **next_candidates}
        candidate_list = list(all_candidates.items())

        if not candidate_list:
            return [], "", 0.0, []

        # Thompson Sampling: 对每个候选构建 Beta(α, β) 后验
        # α = mastery × n_pulls + 1, β = (1 - mastery) × n_pulls + 1
        bloom = BloomTaxonomy()
        arm_pulls = []
        best_kp = None
        best_sample = -1.0

        for kp_name, mastery in candidate_list:
            # 奖励因子
            gain = 1.0 - mastery
            bloom_weight = bloom.level_difficulty_weight("apply")
            interest = 0.8  # 默认中性兴趣（未来可从 profile 取）
            time_fit = 0.9
            reward = gain * bloom_weight * interest * time_fit

            # Beta 后验：α = reward × n_priors + 1
            n_priors = 3.0  # 先验伪计数
            alpha = reward * n_priors + 1.0
            beta = (1.0 - reward) * n_priors + 1.0

            # Thompson 抽样
            sample = random.betavariate(alpha, beta)
            arm_pulls.append({
                "kp_name": kp_name,
                "mastery": round(mastery, 3),
                "reward": round(reward, 4),
                "alpha": round(alpha, 2),
                "beta": round(beta, 2),
                "sample": round(sample, 4),
            })
            if sample > best_sample:
                best_sample = sample
                best_kp = kp_name

        bandit_choice = best_kp or ""
        confidence = round(min(best_sample, 1.0), 3)
        zpd_kps = list(zpd_candidates.keys()) + list(next_candidates.keys())

        return zpd_kps, bandit_choice, confidence, arm_pulls

    # ── 原有逻辑（保持兼容）─────────────────────────────
    def _build_prompt(self, context: AgentContext) -> str:
        parts = [f"学生需求：{context.user_input}\n"]

        if context.profile:
            parts.append("## 学生画像")
            parts.append(json.dumps(context.profile, ensure_ascii=False, indent=2))

        if context.course_name:
            parts.append(f"\n课程：{context.course_name}")

        if context.rag_results:
            parts.append("\n## 课程知识体系参考")
            for doc in context.rag_results[:3]:
                parts.append(doc.get("content", "")[:300])

        # DINA snapshot（如果有）
        dina = context.extra.get("dina_snapshot", {})
        if dina:
            parts.append(f"\n## DINA 认知诊断\n{json.dumps(dina, ensure_ascii=False)}")

        parts.append(
            "\n请严格按需求中的时间范围规划；若未指定，再分为 3-6 个阶段。"
            "先给出高密度 Markdown 表格，再给路径说明与结构化数据。"
        )
        return "\n".join(parts)

    def _extract_path_data(self, llm_output: str) -> dict:
        import re
        pattern = r"```learning_path\s*\n(.*?)\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return {"stages": []}

    @staticmethod
    def _strip_path_block(text: str) -> str:
        """Hide the machine-readable path payload and its orphan heading."""
        import re
        cleaned = re.sub(
            r"```learning_path\s*\n[\s\S]*?\n```",
            "",
            str(text or ""),
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"(?im)^\s{0,3}(?:#{1,6}\s*)?(?:\*\*)?"
            r"(?:结构化数据(?:\s*[（(]?JSON[）)]?)?|路径\s*JSON|JSON\s*数据)"
            r"(?:\*\*)?\s*[:：]?\s*$",
            "",
            cleaned,
        )
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
