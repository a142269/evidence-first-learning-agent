from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _md_to_html(text: str) -> str:
    """将大模型返回的 Markdown 文本转换为 HTML，支持标题、加粗、列表、分隔线等。"""
    if not text or not text.strip():
        return text
    lines = text.replace("\r\n", "\n").split("\n")
    html_lines: list[str] = []
    in_ul = False
    in_ol = False

    for line in lines:
        stripped = line.strip()

        # 空行 → 段落间距
        if not stripped:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            html_lines.append("<br>")
            continue

        # 水平分隔线
        if re.match(r"^-{3,}$", stripped) or re.match(r"^\*{3,}$", stripped):
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            html_lines.append('<hr style="margin:12px 0;border:none;border-top:1px solid #cbd5e1;">')
            continue

        # 标题
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            level = len(heading_match.group(1))
            content = _inline_md(heading_match.group(2))
            tag = f"h{level + 2}"  # ## → h4, ### → h5
            html_lines.append(f'<{tag} style="margin:14px 0 6px;color:#1e3a8a;">{content}</{tag}>')
            continue

        # 有序列表 (1. xxx)
        ol_match = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
        if ol_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append('<ol style="margin:6px 0;padding-left:24px;">')
                in_ol = True
            content = _inline_md(ol_match.group(2))
            html_lines.append(f"<li>{content}</li>")
            continue

        # 无序列表 (* xxx 或 - xxx)
        ul_match = re.match(r"^[*\-+]\s+(.+)$", stripped)
        if ul_match:
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append('<ul style="margin:6px 0;padding-left:24px;">')
                in_ul = True
            content = _inline_md(ul_match.group(1))
            html_lines.append(f"<li>{content}</li>")
            continue

        # 普通段落
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False
        content = _inline_md(stripped)
        html_lines.append(f"<p style='margin:6px 0;'>{content}</p>")

    if in_ul:
        html_lines.append("</ul>")
    if in_ol:
        html_lines.append("</ol>")

    return "\n".join(html_lines)


def _inline_md(text: str) -> str:
    """处理行内 Markdown：**加粗**、*斜体*。"""
    # **加粗**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # *斜体*
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def _risk_level_display(level: str) -> str:
    value = str(level).strip().lower()
    mapping = {"high": "高风险预警", "medium": "中等关注", "low": "低风险关注"}
    if not value:
        return "待评估"
    return mapping.get(value, str(level))


def _trajectory_pattern_display(pattern: str) -> str:
    value = str(pattern).strip()
    mapping = {
        "持续稳健型": "状态整体稳定",
        "波动跃迁型": "状态波动较大需持续观察",
        "回升修复型": "状态正在逐步回升",
        "高开低走型": "近期状态下滑预警",
    }
    if not value:
        return "状态整体稳定"
    return mapping.get(value, value)


def _priority_display(priority: str) -> str:
    value = str(priority).strip().lower()
    mapping = {"urgent": "紧急处置", "high": "高优先级", "medium": "中优先级", "low": "常规跟进"}
    if not value:
        return "常规跟进"
    return mapping.get(value, str(priority))


@dataclass
class ReportExporter:
    project_root: Path

    def _templates_dir(self) -> Path:
        return self.project_root / "backend" / "app" / "templates" / "reports"

    def _render_html(self, report: dict[str, Any]) -> str:
        template_path = self._templates_dir() / "student_report.html"
        default_html = self._default_template()
        template = default_html
        if template_path.exists():
            text = template_path.read_text(encoding="utf-8")
            if text.strip():
                template = text
        mode_rows = "".join(
            [
                (
                    f"<tr><td>{item.get('mode','')}</td>"
                    f"<td>{item.get('label','')}</td>"
                    f"<td>{float(item.get('score_100', float(item.get('score', 0.0)) * 100.0)):.1f}</td>"
                    f"<td>{'优势' if float(item.get('score',0.0))>=0.75 else ('稳定' if float(item.get('score',0.0))>=0.45 else '待关注')}</td></tr>"
                )
                for item in report.get("five_mode_scores", [])
            ]
        )
        factors = "".join([f"<li>{x}</li>" for x in report.get("risk_warning", {}).get("core_factors", [])])
        plan = "".join([f"<li>{x}</li>" for x in report.get("advice", {}).get("detailed_plan", [])])
        radar = report.get("radar_chart", {})
        radar_rows = "".join(
            [
                f"<tr><td>{k}</td><td>{radar.get('student_score', {}).get(k, 0)}</td><td>{radar.get('peer_avg_score', {}).get(k, 0)}</td></tr>"
                for k in ["学习行为", "学习成果", "生活节律与运动健康", "社交生活", "选课探索"]
            ]
        )
        tags = report.get("mode_tags", {})
        tag_items = "".join([f"<li>{x}</li>" for x in tags.get("main_tags", [])])
        phrase_items = "".join([f"<li>{x}</li>" for x in tags.get("feature_phrases", [])])
        trajectory_story = report.get("trajectory_story", {})
        trajectory_presentation = report.get("trajectory_presentation", {})
        trajectory = report.get("trajectory_evolution", {})
        trajectory_nodes = "".join([f"<li>{x}</li>" for x in trajectory.get("key_nodes", [])])
        state_sequence_rows = "".join(
            [
                (
                    f"<tr><td>{str(item.get('time_label', ''))}</td>"
                    f"<td>{str(item.get('state', ''))}</td>"
                    f"<td>{float(item.get('score', 0.0)):.3f}</td>"
                    f"<td>{str(item.get('transition_reason', ''))}</td></tr>"
                )
                for item in trajectory_story.get("state_sequence", [])
            ]
        )
        turning_point_rows = "".join(
            [
                (
                    f"<tr><td>{str(item.get('time_label', ''))}</td>"
                    f"<td>{float(item.get('delta', 0.0)):+.3f}</td>"
                    f"<td>{str(item.get('from_state', ''))}→{str(item.get('to_state', ''))}</td>"
                    f"<td>{str(item.get('evidence_hint', ''))}</td></tr>"
                )
                for item in trajectory_story.get("turning_points", [])
            ]
        )
        event_chain_items = "".join(
            [
                (
                    "<li>"
                    f"{str(item.get('trigger', ''))}"
                    f" → {'；'.join(item.get('evidence', [])) if isinstance(item.get('evidence', []), list) else str(item.get('evidence', ''))}"
                    f" → {str(item.get('impact', ''))}"
                    f" → {str(item.get('suggestion', ''))}"
                    f"（观察窗口：{str(item.get('observation_window', ''))}）"
                    "</li>"
                )
                for item in trajectory_story.get("event_chain", [])
            ]
        )
        confidence = trajectory_story.get("confidence", {})
        trajectory_pattern_raw = str(confidence.get("trajectory_pattern", ""))
        trajectory_pattern_display = str(trajectory_presentation.get("trajectory_pattern_display", "")) or _trajectory_pattern_display(trajectory_pattern_raw)
        confidence_summary = (
            f"置信度={float(confidence.get('score', 0.0)):.3f}（{str(confidence.get('level', ''))}），"
            f"样本点={int(confidence.get('sample_points', 0) or 0)}，"
            f"样本充分性={str(confidence.get('sample_sufficiency', ''))}，"
            f"轨迹熵={float(confidence.get('trajectory_entropy', 0.0)):.3f}，"
            f"轨迹状态={trajectory_pattern_display}"
        )
        stage = str(trajectory_presentation.get("semester_stage", "适应期"))
        display_granularity = "学期口径" if str(trajectory_presentation.get("display_granularity", "term")) == "term" else "周口径"
        stage_progress = float(trajectory_presentation.get("semester_progress", 0.0) or 0.0)
        stage_progress_width = max(0.0, min(1.0, stage_progress)) * 100
        stage_progress_text = f"当前位于{stage}，学期进度约{stage_progress_width:.0f}%"
        future_forecast = trajectory_presentation.get("future_4w_forecast", [])
        forecast_rows = "".join(
            [
                (
                    f"<tr><td>{str(item.get('offset_label', item.get('week_offset', '')))}</td>"
                    f"<td>{float(item.get('predicted_score', 0.0)):.3f}</td>"
                    f"<td>{float(item.get('ci_low', 0.0)):.3f} ~ {float(item.get('ci_high', 0.0)):.3f}</td></tr>"
                )
                for item in future_forecast
            ]
        )
        simulation = trajectory_presentation.get("intervention_simulation", {})
        base_prob = float(report.get("risk_warning", {}).get("business_warning", {}).get("course_fail", {}).get("fused_probability", 0.0) or 0.0)
        sim_drop = float(simulation.get("best_fused_probability_drop", 0.0) or 0.0)
        after_prob = max(0.0, base_prob - sim_drop)
        simulation_summary = (
            f"方案A（维持现状）风险概率：{base_prob:.3f}；"
            f"方案B（执行干预：{str(simulation.get('best_intervention_name', '待计算'))}）风险概率：{after_prob:.3f}；"
            f"预计下降：{float(simulation.get('best_fused_probability_drop', 0.0)):.3f}；"
            f"推荐动作：{str(simulation.get('best_intervention_action', '待计算'))}"
        )
        key_insights = report.get("key_insights", [])
        key_insight_items = "".join(
            [
                f"<li><strong>{str(item.get('title', '核心洞察'))}：</strong>{str(item.get('content', ''))}</li>"
                for item in key_insights
            ]
        )
        key_behavior = report.get("key_behavior_analysis", {})
        risk_behavior_items = "".join([f"<li>{x}</li>" for x in key_behavior.get("risk_events", [])])
        positive_behavior_items = "".join([f"<li>{x}</li>" for x in key_behavior.get("positive_events", [])])
        desc_tpl = report.get("description_templates", {})
        template_rows = "".join(
            [
                f"<tr><td>学习行为描述模板</td><td>{str(desc_tpl.get('learning_behavior_template', ''))}</td></tr>",
                f"<tr><td>学习成果描述模板</td><td>{str(desc_tpl.get('learning_outcome_template', ''))}</td></tr>",
                f"<tr><td>生活节律与运动健康描述模板</td><td>{str(desc_tpl.get('lifestyle_health_template', ''))}</td></tr>",
                f"<tr><td>社交生活描述模板</td><td>{str(desc_tpl.get('social_life_template', ''))}</td></tr>",
                f"<tr><td>选课探索描述模板</td><td>{str(desc_tpl.get('course_exploration_template', ''))}</td></tr>",
                f"<tr><td>风险说明模板</td><td>{str(desc_tpl.get('risk_explanation_template', ''))}</td></tr>",
                f"<tr><td>建议模板</td><td>{str(desc_tpl.get('advice_template', {}))}</td></tr>",
            ]
        )
        llm_narrative = report.get("llm_enhanced_narrative", {})
        qa = report.get("knowledge_enhanced_qa", {})
        rag_support = report.get("rag_knowledge_support", {})
        visual_assets = report.get("visual_assets", {})
        intervention_closure = report.get("intervention_closure", {})
        student_view = report.get("student_view_enhancement", {})
        data_source_trace = report.get("data_source_trace", {})
        data_freshness = report.get("data_freshness", {})
        update_log = report.get("update_log", [])
        version_benchmark = report.get("version_benchmark", {})
        cross = report.get("cross_mode_interconnection", {})
        key_paths = cross.get("global_key_paths", {})
        energy = key_paths.get("energy_support_chain", {})
        peer = key_paths.get("peer_effect_chain", {})
        motivation = key_paths.get("motivation_drive_chain", {})
        efficiency = key_paths.get("efficiency_conversion_chain", {})
        achievements = cross.get("custom_achievements", {})
        domino = achievements.get("domino_effect_dashboard", {})
        detector = achievements.get("cross_dimension_risk_detector", {})
        student_cross = cross.get("student_view", {})
        bw = report.get("risk_warning", {}).get("business_warning", {})
        bw_course_fail = bw.get("course_fail", {})
        bw_composite = bw.get("composite", {})
        priority_reason = report.get("risk_warning", {}).get("priority_reason_card", {})
        priority_reason_items = "".join([f"<li>{x}</li>" for x in priority_reason.get("top3_reason_card", [])])
        three_sentence_items = "".join([f"<li>{x}</li>" for x in student_view.get("three_sentence_summary", [])])
        micro_plan_items = "".join([f"<li>{item.get('day','')}: {'；'.join(item.get('actions', []))}</li>" for item in student_view.get("seven_day_micro_plan", [])])
        source_rows = "".join(
            [
                (
                    f"<tr><td>{str(item.get('table_name',''))}</td>"
                    f"<td>{'、'.join(item.get('time_fields', []))}</td>"
                    f"<td>{str(item.get('primary_time_basis',''))}</td>"
                    f"<td>{int(item.get('student_record_count',0))}</td>"
                    f"<td>{str(item.get('latest_time',''))}</td></tr>"
                )
                for item in data_source_trace.get("tables", [])
            ]
        )
        update_log_items = "".join([f"<li>{str(item.get('version',''))}：{str(item.get('content',''))}</li>" for item in update_log])
        benchmark_items = "".join([f"<li>{x}</li>" for x in version_benchmark.get("highlights", [])])
        rag_reference_items = "".join(
            [
                f"<li>{str(item.get('doc_name',''))}｜score={float(item.get('score',0.0)):.3f}｜{str(item.get('excerpt',''))}</li>"
                for item in rag_support.get("references", [])
            ]
        )
        freshness_text = (
            f"最近数据时间：{str(data_freshness.get('overall_latest_time','未知'))}；"
            f"新鲜度：{str(data_freshness.get('overall_freshness_days','未知'))}天；"
            f"有记录数据源：{int(data_freshness.get('tables_with_student_data',0))}/{int(data_freshness.get('source_count',0))}"
        )
        archetype = report.get("behavior_archetype", {}) or {}
        archetype_traits = "".join([f"<li>{x}</li>" for x in archetype.get("traits", [])])
        archetype_nickname = str(archetype.get("nickname", ""))
        archetype_svg_html = ""
        if archetype_nickname:
            svg_path = self.project_root / "data" / "image" / f"{archetype_nickname}.svg"
            if svg_path.exists():
                try:
                    svg_content = svg_path.read_text(encoding="utf-8")
                    archetype_svg_html = f'<div class="archetype-svg">{svg_content}</div>'
                except Exception:
                    archetype_svg_html = ""
        deep_attr = report.get("deep_attribution", {}) or {}
        def _dim_block(key: str) -> tuple[str, str, str]:
            d = deep_attr.get(key, {}) or {}
            dim = str(d.get("dimension", key))
            evidence_items = "".join(
                [
                    f"<li><span class=\"ev-src\">{str(e.get('source',''))}</span> — {str(e.get('fact',''))}</li>"
                    for e in d.get("evidence_points", [])
                ]
            ) or "<li class=\"ev-empty\">暂时没看到明显信号</li>"
            conclusion = str(d.get("conclusion", ""))
            action = str(d.get("action", ""))
            return dim, evidence_items, f"<div class=\"ev-conclusion\">{conclusion}</div><div class=\"ev-action\">{action}</div>"
        lb_dim, lb_ev, lb_tail = _dim_block("learning_behavior")
        lo_dim, lo_ev, lo_tail = _dim_block("learning_outcome")
        rh_dim, rh_ev, rh_tail = _dim_block("rhythm_health")
        sc_dim, sc_ev, sc_tail = _dim_block("social_life")
        toolkit = report.get("counselor_toolkit", {}) or {}
        taboo_items = "".join([f"<li>{x}</li>" for x in toolkit.get("taboos", [])])
        followup_items = "".join([f"<li>{x}</li>" for x in toolkit.get("follow_up_questions", [])])
        micro_plan_rows = "".join(
            [
                f"<tr><td>{str(item.get('day',''))}</td><td>{str(item.get('focus',''))}</td><td>{'；'.join(item.get('actions', []))}</td></tr>"
                for item in (report.get("personalized_micro_plan", {}) or {}).get("plan", [])
            ]
        )
        validity = report.get("data_validity", {}) or {}
        cross_rows = "".join(
            [
                f"<tr><td>节律对学习投入影响</td><td>关联强度={energy.get('rho_rhythm_focus', 0)}</td><td>{energy.get('statement', '')}</td></tr>",
                f"<tr><td>同伴参与影响恢复速度</td><td>恢复差值（4周/8周）={peer.get('recovery_gap_4w', 0)} / {peer.get('recovery_gap_8w', 0)}</td><td>{peer.get('statement', '')}</td></tr>",
                f"<tr><td>课程探索驱动学习动力</td><td>样本量={motivation.get('sample_size', 0)}</td><td>{motivation.get('statement', '')}</td></tr>",
                f"<tr><td>学习投入转化为学习成果</td><td>转化关联={efficiency.get('rho_density_outcome', 0)}</td><td>{efficiency.get('statement', '')}</td></tr>",
            ]
        )
        attr = report.get("attribution_3d", {})
        behavior_text = "学习投入代理信号偏弱，建议先稳节律再增投入。"
        if isinstance(attr.get("behavior", {}), dict):
            behavior_text = f"学习行为代理得分{float(attr.get('behavior', {}).get('score', 0.0)):.3f}，重点证据：{'；'.join(attr.get('behavior', {}).get('evidence', [])[:3]) or '暂无显著证据'}。"
        result_text = "学业结果代理整体处于可修复区间。"
        if isinstance(attr.get("result", {}), dict):
            result_text = f"学习成果代理得分{float(attr.get('result', {}).get('score', 0.0)):.3f}，重点证据：{'；'.join(attr.get('result', {}).get('evidence', [])[:3]) or '暂无显著证据'}。"
        environment_text = "环境相关行为代理波动可控。"
        if isinstance(attr.get("environment", {}), dict):
            environment_text = f"环境代理得分{float(attr.get('environment', {}).get('score', 0.0)):.3f}，重点证据：{'；'.join(attr.get('environment', {}).get('evidence', [])[:3]) or '暂无显著证据'}。"
        replacements = {
            "{{student_id}}": str(report.get("student_profile", {}).get("student_id", "")),
            "{{major}}": str(report.get("student_profile", {}).get("major", "")),
            "{{grade}}": str(report.get("student_profile", {}).get("grade", "")),
            "{{academy}}": str(report.get("student_profile", {}).get("academy", "")),
            "{{class_name}}": str(report.get("student_profile", {}).get("class_name", "")),
            "{{risk_level}}": str(report.get("student_profile", {}).get("risk_level_display", "")) or _risk_level_display(str(report.get("student_profile", {}).get("risk_level", ""))),
            "{{risk_score}}": f"{float(report.get('student_profile', {}).get('risk_score', 0.0)):.3f}",
            "{{growth_score}}": f"{float(report.get('student_profile', {}).get('overall_growth_score', 0.0)):.3f}",
            "{{history_compare}}": str(report.get("trend_analysis", {}).get("history_compare", "")),
            "{{peer_compare}}": str(report.get("trend_analysis", {}).get("peer_compare", "")),
            "{{risk_overview}}": str(report.get("risk_warning", {}).get("overview", "")),
            "{{business_course_fail_level}}": str(bw_course_fail.get("risk_level_display", "")) or _risk_level_display(str(bw_course_fail.get("risk_level", ""))),
            "{{business_course_fail_prob}}": f"{float(bw_course_fail.get('fused_probability', 0.0)):.3f}",
            "{{business_warning_priority}}": str(bw.get("warning_priority_display", "")) or _priority_display(str(bw.get("warning_priority", ""))),
            "{{business_primary_risk_name}}": str(bw_composite.get("primary_risk_name_cn", "")),
            "{{advice_direction}}": str(report.get("advice", {}).get("direction", "")),
            "{{behavior_proxy_statement}}": str(report.get("meta", {}).get("behavior_proxy_statement", "")),
            "{{mode_rows}}": mode_rows,
            "{{core_factor_items}}": factors,
            "{{advice_plan_items}}": plan,
            "{{radar_rows}}": radar_rows,
            "{{tag_items}}": tag_items,
            "{{phrase_items}}": phrase_items,
            "{{trajectory_phase}}": str(trajectory.get("phase", "")),
            "{{trajectory_nodes}}": trajectory_nodes,
            "{{trajectory_time_note}}": str(trajectory_story.get("time_caliber_note", report.get("meta", {}).get("time_caliber_note", ""))),
            "{{trajectory_state_sequence_rows}}": state_sequence_rows,
            "{{trajectory_turning_point_rows}}": turning_point_rows,
            "{{trajectory_event_chain_items}}": event_chain_items,
            "{{trajectory_confidence_summary}}": confidence_summary,
            "{{trajectory_chart_explanation}}": str(trajectory_presentation.get("chart_explanation", "")),
            "{{trajectory_forecast_narrative}}": str(trajectory_presentation.get("forecast_narrative", "")),
            "{{trajectory_stage_progress_text}}": stage_progress_text,
            "{{trajectory_display_granularity}}": display_granularity,
            "{{trajectory_stage_progress_width}}": f"{stage_progress_width:.0f}",
            "__TRAJECTORY_STAGE_PROGRESS_WIDTH__": f"{stage_progress_width:.0f}",
            "{{forecast_rows}}": forecast_rows,
            "{{intervention_simulation_summary}}": simulation_summary,
            "{{key_insight_items}}": key_insight_items,
            "{{risk_behavior_items}}": risk_behavior_items,
            "{{positive_behavior_items}}": positive_behavior_items,
            "{{attribution_behavior}}": behavior_text,
            "{{attribution_result}}": result_text,
            "{{attribution_environment}}": environment_text,
            "{{template_rows}}": template_rows,
            "{{llm_narrative_status}}": str(llm_narrative.get("status", "")),
            "{{llm_narrative_model}}": str(llm_narrative.get("model", "")),
            "{{llm_narrative_content}}": _md_to_html(str(llm_narrative.get("content", ""))),
            "{{qa_status}}": str(qa.get("status", "")),
            "{{qa_model}}": str(qa.get("model", "")),
            "{{qa_question}}": str(qa.get("question", "")),
            "{{qa_answer}}": _md_to_html(str(qa.get("answer", ""))),
            "{{rag_suggestion}}": _md_to_html(str(rag_support.get("suggestion", ""))),
            "{{rag_reference_items}}": rag_reference_items,
            "{{cross_rows}}": cross_rows,
            "{{domino_insight}}": str(domino.get("insight", "")),
            "{{flagged_student_count}}": str(detector.get("flagged_student_count", 0)),
            "{{student_cross_flags}}": "；".join(student_cross.get("cross_dimension_flags", [])),
            "{{radar_chart_svg}}": str(visual_assets.get("radar_chart_svg", "")),
            "{{risk_timeline_svg}}": str(visual_assets.get("risk_timeline_svg", "")),
            "{{behavior_heatmap_svg}}": str(visual_assets.get("behavior_heatmap_svg", "")),
            "{{group_portrait_svg}}": str(visual_assets.get("group_portrait_svg", "")),
            "{{priority_reason_items}}": priority_reason_items,
            "{{intervention_action}}": str(intervention_closure.get("execution_record", {}).get("planned_action", "")),
            "{{intervention_date}}": str(intervention_closure.get("execution_record", {}).get("planned_execute_date", "")),
            "{{three_sentence_items}}": three_sentence_items,
            "{{one_priority_action}}": str(student_view.get("one_priority_action", "")),
            "{{micro_plan_items}}": micro_plan_items,
            "{{source_rows}}": source_rows,
            "{{freshness_text}}": freshness_text,
            "{{update_log_items}}": update_log_items,
            "{{benchmark_base}}": str(version_benchmark.get("baseline_version", "")),
            "{{benchmark_current}}": str(version_benchmark.get("current_version", "")),
            "{{benchmark_items}}": benchmark_items,
            "{{archetype_name}}": str(archetype.get("name", "")),
            "{{archetype_nickname}}": str(archetype.get("nickname", "")),
            "{{archetype_description}}": str(archetype.get("description", "")),
            "{{archetype_traits}}": archetype_traits,
            "{{archetype_svg}}": archetype_svg_html,
            "{{data_validity_mode}}": str(validity.get("mode_display", "")),
            "{{data_validity_statement}}": str(validity.get("statement", "")),
            "{{attr_lb_dim}}": lb_dim,
            "{{attr_lb_evidence}}": lb_ev,
            "{{attr_lb_tail}}": lb_tail,
            "{{attr_lo_dim}}": lo_dim,
            "{{attr_lo_evidence}}": lo_ev,
            "{{attr_lo_tail}}": lo_tail,
            "{{attr_rh_dim}}": rh_dim,
            "{{attr_rh_evidence}}": rh_ev,
            "{{attr_rh_tail}}": rh_tail,
            "{{attr_sc_dim}}": sc_dim,
            "{{attr_sc_evidence}}": sc_ev,
            "{{attr_sc_tail}}": sc_tail,
            "{{toolkit_opening}}": str(toolkit.get("opening_strategy", "")),
            "{{toolkit_script}}": str(toolkit.get("script", "")),
            "{{toolkit_taboos}}": taboo_items,
            "{{toolkit_followups}}": followup_items,
            "{{toolkit_channel}}": str(toolkit.get("channel_recommendation", "")),
            "{{personalized_micro_plan_rows}}": micro_plan_rows,
        }
        rendered = template
        for key, val in replacements.items():
            rendered = rendered.replace(key, val)
        return rendered

    def _default_template(self) -> str:
        return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>学生个性化评价报告</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 28px; color: #202124; }
    h1, h2 { margin: 10px 0; }
    table { border-collapse: collapse; width: 100%; margin: 8px 0 16px; }
    th, td { border: 1px solid #dcdfe6; padding: 8px; text-align: left; }
    .muted { color: #5f6368; font-size: 13px; }
    .card { background: #f8f9fa; padding: 12px; margin: 10px 0; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>学生个性化评价报告</h1>
  <p class="muted">{{behavior_proxy_statement}}</p>
  <h2>1. 综合诊断看板</h2>
  <div class="card">
    <div>学号：{{student_id}}</div>
    <div>专业：{{major}}</div>
    <div>年级：{{grade}}</div>
    <div>学院：{{academy}}</div>
    <div>班级：{{class_name}}</div>
    <div>风险等级：{{risk_level}}</div>
    <div>综合成长得分：{{growth_score}}</div>
  </div>
  <div class="card">{{risk_overview}}</div>
  <ul>{{key_insight_items}}</ul>
  <h2>2. 五维画像对比</h2>
  <h2>五模式结果</h2>
  <table>
    <thead><tr><th>模式</th><th>标签</th><th>得分</th><th>语义评价</th></tr></thead>
    <tbody>{{mode_rows}}</tbody>
  </table>
  <h2>五维雷达对比（0-100）</h2>
  <div class="card"><img src="{{radar_chart_svg}}" alt="五维能力雷达图" style="width:100%;max-width:620px;" /></div>
  <table>
    <thead><tr><th>维度</th><th>个人得分</th><th>同群体均值</th></tr></thead>
    <tbody>{{radar_rows}}</tbody>
  </table>
  <h2>标签体系</h2>
  <div class="card">主标签</div>
  <ul>{{tag_items}}</ul>
  <div class="card">特征短语</div>
  <ul>{{phrase_items}}</ul>
  <h2>3. 多维归因解释</h2>
  <div class="card"><strong>行为因：</strong>{{attribution_behavior}}</div>
  <div class="card"><strong>结果因：</strong>{{attribution_result}}</div>
  <div class="card"><strong>环境因：</strong>{{attribution_environment}}</div>
  <table>
    <thead><tr><th>关联路径</th><th>核心指标</th><th>结论</th></tr></thead>
    <tbody>{{cross_rows}}</tbody>
  </table>
  <h2>4. 学业轨迹演化</h2>
  <div class="card"><img src="{{risk_timeline_svg}}" alt="学业风险演化时序图" style="width:100%;max-width:760px;" /></div>
  <div class="card">当前展示口径：{{trajectory_display_granularity}}</div>
  <div class="card">时间口径说明：{{trajectory_time_note}}</div>
  <div class="card">{{trajectory_chart_explanation}}</div>
  <div class="card">
    <div>{{trajectory_stage_progress_text}}</div>
    <div style="background:#e8eaed;border-radius:8px;height:12px;margin-top:8px;">
      <div style="background:#1a73e8;height:12px;border-radius:8px;width:__TRAJECTORY_STAGE_PROGRESS_WIDTH__%;"></div>
    </div>
  </div>
  <div class="card">阶段：{{trajectory_phase}}｜{{trajectory_confidence_summary}}</div>
  <ul>{{trajectory_nodes}}</ul>
  <h2>状态序列</h2>
  <table>
    <thead><tr><th>时间</th><th>状态</th><th>得分</th><th>转移原因</th></tr></thead>
    <tbody>{{trajectory_state_sequence_rows}}</tbody>
  </table>
  <h2>关键拐点</h2>
  <table>
    <thead><tr><th>时间</th><th>变化量</th><th>状态迁移</th><th>证据提示</th></tr></thead>
    <tbody>{{trajectory_turning_point_rows}}</tbody>
  </table>
  <h2>行为归因逻辑链</h2>
  <ul>{{trajectory_event_chain_items}}</ul>
  <h2>学业状态预警演化趋势</h2>
  <div class="card">{{trajectory_forecast_narrative}}</div>
  <table>
    <thead><tr><th>未来窗口</th><th>预测轨迹分值（虚线）</th><th>置信区间</th></tr></thead>
    <tbody>{{forecast_rows}}</tbody>
  </table>
  <h2>精准干预决策支持</h2>
  <div class="card">{{intervention_simulation_summary}}</div>
  <h2>5. 知识增强式建议</h2>
  <h3>关键行为分析</h3>
  <div class="card">风险行为事件</div>
  <ul>{{risk_behavior_items}}</ul>
  <div class="card">正向行为事件</div>
  <ul>{{positive_behavior_items}}</ul>
  <h3>双对比解释</h3>
  <div class="card">
    <div><strong>与本人历史：</strong>{{history_compare}}</div>
    <div><strong>与同群体分位：</strong>{{peer_compare}}</div>
  </div>
  <h3>风险与建议</h3>
  <div class="card">挂科预警等级={{business_course_fail_level}}；融合概率={{business_course_fail_prob}}；处置优先级={{business_warning_priority}}；主风险={{business_primary_risk_name}}</div>
  <ul>{{core_factor_items}}</ul>
  <h3>成长方向与详细计划</h3>
  <div class="card">{{advice_direction}}</div>
  <ul>{{advice_plan_items}}</ul>
  <h3>描述模板输出</h3>
  <table>
    <thead><tr><th>模板类型</th><th>输出内容</th></tr></thead>
    <tbody>{{template_rows}}</tbody>
  </table>
  <h3>LLM叙事增强</h3>
  <div class="card">状态：{{llm_narrative_status}}｜模型：{{llm_narrative_model}}</div>
  <div class="card">{{llm_narrative_content}}</div>
  <h3>知识增强问答</h3>
  <div class="card">状态：{{qa_status}}｜模型：{{qa_model}}</div>
  <div class="card"><strong>问题：</strong>{{qa_question}}</div>
  <div class="card"><strong>回答：</strong>{{qa_answer}}</div>
  <h3>RAG知识建议</h3>
  <div class="card">{{rag_suggestion}}</div>
  <ul>{{rag_reference_items}}</ul>
  <h3>数据来源溯源与更新</h3>
  <div class="card">{{freshness_text}}</div>
  <table>
    <thead><tr><th>数据源</th><th>时间字段</th><th>主时间口径</th><th>该生记录数</th><th>最近时间</th></tr></thead>
    <tbody>{{source_rows}}</tbody>
  </table>
  <div class="card">版本对标：{{benchmark_base}} → {{benchmark_current}}</div>
  <ul>{{benchmark_items}}</ul>
  <ul>{{update_log_items}}</ul>
</body>
</html>
"""

    def _run_pyside6_pdf(self, html_path: Path, pdf_path: Path) -> str:
        import subprocess
        import sys
        
        script = """
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize

app = QApplication(sys.argv)
view = QWebEngineView()

html_path = sys.argv[1]
pdf_path = sys.argv[2]

def on_load_finished(ok):
    if ok:
        layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(10, 10, 10, 10))
        view.page().printToPdf(pdf_path, layout)
    else:
        app.exit(1)

def on_pdf_printed(path, success):
    if success:
        app.exit(0)
    else:
        app.exit(1)

view.loadFinished.connect(on_load_finished)
view.page().pdfPrintingFinished.connect(on_pdf_printed)

view.setUrl(QUrl.fromLocalFile(html_path))
sys.exit(app.exec())
"""
        try:
            result = subprocess.run(
                [sys.executable, "-c", script, str(html_path.resolve()), str(pdf_path.resolve())],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
                return "ok"
        except Exception:
            pass
        return "failed"

    def export(self, report: dict[str, Any], output_dir: Path) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        student_id = str(report.get("meta", {}).get("student_id", "unknown"))
        html_path = output_dir / f"student_report_{student_id}.html"
        json_path = output_dir / f"student_report_{student_id}.json"
        html_text = self._render_html(report)
        html_path.write_text(html_text, encoding="utf-8")
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        
        pdf_path = output_dir / f"student_report_{student_id}.pdf"
        
        pdf_status = self._run_pyside6_pdf(html_path, pdf_path)
        
        return {
            "student_id": student_id,
            "html_path": str(html_path),
            "json_path": str(json_path),
            "pdf_path": str(pdf_path) if pdf_status in {"ok", "fallback_ok"} else "",
            "pdf_status": pdf_status,
        }
