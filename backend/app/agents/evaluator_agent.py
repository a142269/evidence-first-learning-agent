"""
学习评估师 Agent —— 学习效果评估（加分项）

对应赛题需求5：
  通过实时跟踪学生的学习行为、练习测试情况、资源使用反馈等数据，
  依托大模型的数据分析能力实现对学生学习效果的多维度精准评估；
  并根据评估结果动态调整学习资源推送策略和学习计划

B 角色升级（Day 5）：
  - 引用 DINA 掌握状态 + BKT 趋势（不再用均值拍脑袋）
  - 集成 NarrativeGenerator 模板化叙事（省 90% LLM 调用）
  - 集成 SVGVisualizer 生成评估图表 data URI
  - LLM 仅补充个性化建议，失败时报告仍完整
"""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
from backend.app.services.downloadable_artifacts import register_markdown_artifact

logger = logging.getLogger(__name__)


class EvaluatorAgent(BaseAgent):
    """学习评估师 —— 多维度评估学习效果，动态调整策略（B 升级版）"""

    @property
    def name(self) -> str:
        return "evaluator_agent"

    @property
    def description(self) -> str:
        return "多维度评估学习效果（DINA+BKT+叙事+SVG），动态调整学习策略"

    @property
    def system_prompt(self) -> str:
        return (
            "你是一名专业的学习评估专家，擅长通过数据分析评估学生的学习效果。\n\n"
            "你的任务：\n"
            "1. 分析学生的学习行为数据（访问频率、学习时长、练习完成率等）\n"
            "2. 评估知识掌握程度（练习正确率、进度完成度等）\n"
            "3. 识别学习瓶颈（哪些知识点薄弱、哪些题型错误率高）\n"
            "4. 生成改进建议（调整难度、增加练习、回顾基础等）\n"
            "5. 提出路径调整建议（是否需要放慢/加快节奏）\n\n"
            "输出要求：\n"
            "- 所有判断必须绑定画像/BKT/DINA/练习记录中的证据；数据缺失时明确写『证据不足』，不得编造\n"
            "- 对短期计划给出完成概率区间、主要风险、短板优先级和触发式调整规则\n"
            "- 先用自然语言给出评估总结（鼓励性语气）\n"
            "- 列出具体的强项和弱项\n"
            "- 给出 3-5 条可执行的改进建议\n"
            "- 在末尾用 ```evaluation_result``` 包裹结构化评估数据\n\n"
            "评估 JSON 格式：\n"
            '```evaluation_result\n'
            '{"overall_score": 0.75, "dimensions": {"知识掌握": 0.8, "应用能力": 0.6, "学习持续性": 0.85}, '
            '"strengths": ["基础知识扎实"], "weaknesses": ["编程实践不足"], '
            '"recommendations": ["增加代码实操练习", "每周完成2道编程题"], '
            '"path_adjustments": {"action": "slow_down", "focus_areas": ["面向对象编程"]}}\n'
            '```\n'
        )

    async def execute(self, context: AgentContext) -> AgentResponse:
        """执行学习评估 —— B 升级版"""
        # session_id 只标识一次聊天，不是学习者 ID。BKT/DINA/画像必须按真实
        # user_id 查询，否则每次新会话都会被误判为“没有证据”。
        user_id = str(context.extra.get("user_id") or context.session_id or "default")

        # ── B 升级 1：DINA + BKT 数据收集 ──
        bkt_data = self._gather_bkt_data(user_id)
        dina_data = context.extra.get("dina_snapshot", {})

        # ── B 升级 2：NarrativeGenerator 模板化叙事（省 90% LLM）──
        narrative = ""
        svg_assets: dict[str, str] = {}
        visualizations: list[dict[str, str]] = []
        try:
            from backend.app.services.narrative_generator import get_narrative_generator
            from backend.app.services.svg_visualization import get_svg_visualizer

            ng = get_narrative_generator()
            profile = context.profile or {}
            # 构造类似老项目的 row 结构
            row = {
                "user_id": user_id,
                **profile,
                "bkt_masteries": bkt_data,
                "dina_snapshot": dina_data,
            }
            narrative_summary = ng.build_summary(row)
            narrative = narrative_summary.get("statement", "")
            # 把 narrative 注入 context.extra 供 A 的 ChatView 使用
            if not context.extra.get("narrative_summary"):
                context.extra["narrative_summary"] = narrative_summary

            # SVG 图表生成。旧代码把 profile/bkt/dina 当作三个关键字参数传给
            # build_assessment_assets，但服务实际需要四组已经整形的数据，调用
            # 一直抛 TypeError 并被静默降级。这里按“有证据才画图”逐张构建。
            viz = get_svg_visualizer()
            radar_keys = (
                "knowledge_base", "learning_preference", "weak_points", "time_management",
                "self_efficacy", "cognitive_style", "learning_goal", "interaction_pattern",
            )
            radar_scores = {key: profile.get(key) for key in radar_keys if profile.get(key) not in (None, "", {})}
            if radar_scores:
                radar_svg = viz.profile_radar({
                    "student_score": radar_scores,
                    "title": "当前学习画像 · 证据维度",
                })
                data_uri = viz.to_data_uri(radar_svg)
                svg_assets["profile_radar_svg"] = data_uri
                visualizations.append({
                    "title": "学习画像雷达图",
                    "data_uri": data_uri,
                    "alt": "学习者在知识基础、学习偏好、薄弱识别、时间管理等维度的雷达图",
                    "description": "蓝色区域表示当前画像中已有证据支持的维度；接近中心的维度可能是分数较低，也可能是数据尚不完整，需结合正文证据判断。",
                })

            mastery_snapshot = {
                str(kp): float(values.get("p_learned", 0.0))
                for kp, values in bkt_data.items()
                if isinstance(values, dict) and values.get("p_learned") is not None
            }
            if mastery_snapshot:
                trend_svg = viz.mastery_trend(
                    mastery_snapshot,
                    chart_type="bar",
                    title="BKT 知识点掌握度快照",
                )
                data_uri = viz.to_data_uri(trend_svg)
                svg_assets["mastery_snapshot_svg"] = data_uri
                visualizations.append({
                    "title": "知识点掌握度快照",
                    "data_uri": data_uri,
                    "alt": "依据 BKT 记录绘制的各知识点当前掌握度柱状图",
                    "description": "柱高来自已有 BKT 掌握概率，用于比较知识点间相对短板；它不是考试分数，也不代表没有记录的知识点。",
                })
            if not context.extra.get("svg_assets"):
                context.extra["svg_assets"] = svg_assets
        except Exception as exc:
            logger.warning(f"[EvaluatorAgent] 叙事/SVG 生成失败（降级）: {exc}")

        # ── 构造 prompt（含算法数据）──
        user_prompt = self._build_prompt(context, bkt_data, dina_data, narrative)

        # ── B 升级 3：LLM 仅补充个性化建议，叙事已由模板生成 ──
        result = await self._acall_llm(
            user_prompt=user_prompt,
            history=context.conversation_history,
            extra_system=self._strategy_extra_system(context),
            temperature=0.5,
        )

        eval_data = self._extract_evaluation_data(result)

        # 从展示内容中移除结构化 JSON 代码块，避免聊天界面显示原始 JSON
        result = self._strip_evaluation_block(result)

        # 把叙事和 SVG 塞进 evaluation_data 供前端渲染
        if narrative:
            eval_data["narrative"] = narrative
        if svg_assets:
            eval_data["svg_assets"] = {k: v for k, v in svg_assets.items()}
        if visualizations:
            eval_data["visualizations"] = visualizations

        scored_profile_dimensions = sum(
            1
            for value in (context.profile or {}).values()
            if isinstance(value, dict) and value.get("score") is not None
        )
        evidence_status = (
            "sufficient"
            if scored_profile_dimensions >= 3 or bool(bkt_data) or bool(dina_data)
            else "insufficient"
        )
        if not result.strip():
            result = narrative or "当前可用学习证据不足，暂不输出确定性能力判断；建议先完成一次基线测验。"

        report_title = "学习可行性与风险评估"
        download = register_markdown_artifact(
            artifact_type="evaluation_report",
            title=report_title,
            content=self._render_report_download(result, eval_data, evidence_status),
            session_id=context.session_id,
            metadata={
                "overall_score": eval_data.get("overall_score", 0),
                "evidence_status": evidence_status,
            },
        )

        return self._success(
            content=result,
            content_type="evaluation",
            resources=[{
                "type": "evaluation_report",
                "title": report_title,
                "overall_score": eval_data.get("overall_score", 0),
                "downloads": [download] if download else [],
                "metadata": {
                    "title": "学习可行性与风险评估",
                    "overall_score": eval_data.get("overall_score", 0),
                    "dimensions": eval_data.get("dimensions", {}),
                    "visualizations": visualizations,
                    "evidence_status": evidence_status,
                    "narrative": narrative,
                },
            }],
            metadata={
                "evaluation_data": eval_data,
                "narrative_summary": context.extra.get("narrative_summary", {}),
                "svg_assets": svg_assets,
            },
            profile_updates=eval_data.get("profile_updates", {}),
        )

    @staticmethod
    def _render_report_download(result: str, eval_data: dict, evidence_status: str) -> str:
        """Build a compact human-readable report without raw JSON/data URIs."""
        lines = ["# 学习可行性与风险评估", "", result.strip(), "", "## 评估摘要", ""]
        lines.append(
            f"- 证据状态：{'已有学习证据' if evidence_status == 'sufficient' else '证据待补充'}"
        )
        overall = eval_data.get("overall_score")
        if isinstance(overall, (int, float)):
            score = overall * 100 if overall <= 1 else overall
            lines.append(f"- 综合参考值：{score:.0f}%")
        dimensions = eval_data.get("dimensions")
        if isinstance(dimensions, dict) and dimensions:
            lines.extend(["", "## 维度参考", ""])
            for label, value in dimensions.items():
                if isinstance(value, (int, float)):
                    score = value * 100 if value <= 1 else value
                    lines.append(f"- {label}：{score:.0f}%")
                else:
                    lines.append(f"- {label}：{value}")
        return "\n".join(lines).strip()

    # ── BKT 数据收集 ────────────────────────────────────
    def _gather_bkt_data(self, user_id: str) -> dict:
        try:
            from backend.app.services.cognitive_diagnosis.bkt import get_bkt
            bkt = get_bkt()
            masteries = bkt.get_all_masteries(user_id)
            return {
                kp: {
                    "p_learned": round(m, 4),
                    "trend": bkt.trend(user_id, kp),
                }
                for kp, m in masteries.items()
            }
        except Exception:
            return {}

    def _build_prompt(
        self, context: AgentContext,
        bkt_data: dict, dina_data: dict,
        narrative: str,
    ) -> str:
        parts = [f"评估请求：{context.user_input}\n"]

        if context.profile:
            parts.append("## 学生当前画像")
            parts.append(json.dumps(context.profile, ensure_ascii=False, indent=2))

        if bkt_data:
            parts.append(f"\n## BKT 知识追踪数据\n{json.dumps(bkt_data, ensure_ascii=False)}")
        if dina_data:
            parts.append(f"\n## DINA 认知诊断\n{json.dumps(dina_data, ensure_ascii=False)}")

        parts.append(f"\n## 模板化叙事（供参考，请在此基础上补充个性化建议）\n{narrative}")

        if context.extra.get("quiz_scores"):
            parts.append(f"\n## 练习成绩\n{json.dumps(context.extra['quiz_scores'], ensure_ascii=False)}")

        if context.extra.get("learning_activity"):
            parts.append(f"\n## 学习行为\n{json.dumps(context.extra['learning_activity'], ensure_ascii=False)}")

        parts.append("\n请给出全面的学习效果评估和个性化改进建议。")
        return "\n".join(parts)

    def _extract_evaluation_data(self, llm_output: str) -> dict:
        import re
        pattern = r"```evaluation_result\s*\n(.*?)\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        return {}

    @staticmethod
    def _strip_evaluation_block(text: str) -> str:
        """从 LLM 输出中移除 ```evaluation_result ... ``` 代码块，
        同时兜底移除裸 JSON 对象（以 {"overall_score" 开头）。"""
        import re
        # 1. 移除 ```evaluation_result ... ``` 包裹块
        text = re.sub(r"```evaluation_result\s*\n.*?\n```", "", text, flags=re.DOTALL)
        # 2. 移除其他常见代码块包裹的 JSON（```json ... ``` 等）
        text = re.sub(r"```(?:json|JSON)?\s*\n\{[\s\S]*?\}\s*\n```", "", text)
        # 3. 兜底：移除裸 JSON 对象（整行以 { 开头并以 } 结尾，且包含 overall_score 或 dimensions）
        lines = text.split("\n")
        cleaned: list[str] = []
        in_json = False
        brace_depth = 0
        for line in lines:
            stripped = line.strip()
            if not in_json and stripped.startswith("{") and (
                "overall_score" in stripped or "dimensions" in stripped
                or "strengths" in stripped or "path_adjustments" in stripped
            ):
                in_json = True
                brace_depth = stripped.count("{") - stripped.count("}")
                if brace_depth <= 0:
                    in_json = False
                continue
            if in_json:
                brace_depth += stripped.count("{") - stripped.count("}")
                if brace_depth <= 0:
                    in_json = False
                continue
            cleaned.append(line)
        text = "\n".join(cleaned)
        # 清理多余空行
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text
