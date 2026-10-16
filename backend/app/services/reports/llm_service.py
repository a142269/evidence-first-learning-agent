from __future__ import annotations

import json
import http.client as http_client
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from backend.app.services.reports.llm_runtime_config import load_llm_runtime_config

def _clean_base_url(base_url: str) -> str:
    text = str(base_url or "").strip().strip("`").strip().strip('"').strip("'")
    return text.rstrip("/")


def _safe_json_loads(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return {}
    return {}


def _extract_error_text(payload: dict[str, Any]) -> str:
    message_text = str(payload.get("message", "")).strip()
    if message_text:
        parsed = _safe_json_loads(message_text)
        if parsed:
            nested = parsed.get("error")
            if isinstance(nested, dict):
                nested_msg = str(nested.get("message", "")).strip()
                if nested_msg:
                    return nested_msg
            parsed_msg = str(parsed.get("message", "")).strip()
            if parsed_msg:
                return parsed_msg
        return message_text
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    if isinstance(err, dict):
        message = str(err.get("message", "")).strip()
        if message:
            return message
    return ""


@dataclass
class ModelScopeLLMClient:
    base_url: str
    api_key: str
    timeout: int = 60

    def __post_init__(self) -> None:
        self.base_url = _clean_base_url(self.base_url)

    @classmethod
    def from_env(cls) -> "ModelScopeLLMClient":
        cfg = load_llm_runtime_config()
        return cls(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.timeout)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
        max_retries = 2
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                    parsed = _safe_json_loads(body)
                    if parsed:
                        return parsed
                    return {"raw_text": body}
            except error.HTTPError as exc:
                text = exc.read().decode("utf-8", errors="ignore")
                return {"error": f"http_{exc.code}", "message": text}
            except http_client.IncompleteRead as exc:
                # deepseek-reasoner 思考时间长，可能导致 IncompleteRead
                partial = exc.partial.decode("utf-8", errors="ignore") if exc.partial else ""
                if partial.strip():
                    parsed = _safe_json_loads(partial)
                    if parsed:
                        return parsed
                last_exc = exc
                if attempt < max_retries:
                    import time
                    time.sleep(2)
                    # 重建 Request 对象用于重试
                    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
                    continue
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries and "timeout" in str(exc).lower():
                    import time
                    time.sleep(2)
                    req = request.Request(url=url, method=method.upper(), data=data, headers=headers)
                    continue
                return {"error": "request_failed", "message": str(exc)}
        return {"error": "request_failed", "message": str(last_exc)}

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/models")
        if payload.get("error"):
            return []
        if "data" not in payload:
            return []
        data = payload.get("data")
        names: list[str] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    name = str(item.get("id", "")).strip()
                    if name:
                        names.append(name)
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        names.append(text)
        elif isinstance(data, dict):
            for key in ["models", "items"]:
                items = data.get(key)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            name = str(item.get("id", "")).strip()
                            if name:
                                names.append(name)
                        elif isinstance(item, str):
                            text = item.strip()
                            if text:
                                names.append(text)
        return sorted(list(set(names)))

    def chat(self, model: str, messages: list[dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # deepseek-reasoner 不支持 temperature 参数
        if "reasoner" not in model:
            payload["temperature"] = temperature
        result = self._request("POST", "/chat/completions", payload=payload)
        if result.get("error"):
            message = _extract_error_text(result)
            return "[API_ERROR] {}".format(message) if message else "[API_ERROR] model call failed"
        choices = result.get("choices", [])
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
                # deepseek-reasoner 可能将内容放在 reasoning_content 中
                reasoning = msg.get("reasoning_content", "")
                if isinstance(reasoning, str) and reasoning.strip():
                    return reasoning.strip()
        if isinstance(result.get("raw_text"), str):
            raw_text = str(result["raw_text"]).strip()
            parsed_raw = _safe_json_loads(raw_text)
            if parsed_raw:
                err_text = _extract_error_text(parsed_raw)
                if err_text:
                    return "[API_ERROR] {}".format(err_text)
            return raw_text
        if "message" in result:
            return str(result.get("message", ""))
        return ""


def _extract_key_signals(report: dict[str, Any]) -> dict[str, Any]:
    deep_attr = report.get("deep_attribution", {})
    triple_linkage = deep_attr.get("triple_linkage", []) if isinstance(deep_attr, dict) else []
    return {
        "student_profile": report.get("student_profile", {}),
        "behavior_archetype": report.get("behavior_archetype", {}),
        "five_mode_scores": report.get("five_mode_scores", []),
        "deep_attribution": deep_attr,
        "triple_linkage": triple_linkage,
        "attribution_3d": report.get("attribution_3d", {}),
        "group_profile": report.get("group_profile", {}),
        "risk_warning": report.get("risk_warning", {}),
        "trajectory_evidence": report.get("trajectory_evidence", {}),
        "counterfactual_simulation": report.get("counterfactual_simulation", {}),
        "strength_highlights": report.get("strength_highlights", {}),
        "confidence_assessment": report.get("confidence_assessment", {}),
        "counselor_toolkit": report.get("counselor_toolkit", {}),
        "personalized_micro_plan": report.get("personalized_micro_plan", {}),
        "data_validity": report.get("data_validity", {}),
        "advice": report.get("advice", {}),
        "cross_mode_interconnection": report.get("cross_mode_interconnection", {}),
    }


# ---------------------------------------------------------------------------
# LLM prompt constants (kept outside f-strings for Python 3.7 compat)
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "你是一名资深高校辅导员，正在为同事撰写一份学生谈话参考材料。"
    "语气温和、具体、可执行，像经验丰富的同事在交接个案。\n"
    "【硬性禁用词】以下任何术语都不得出现：HMM、隐马尔可夫、轨迹熵、熵、"
    "概率、马尔可夫、聚类、向量、embedding、模型、算法、AUC、F1、特征工程、"
    "分位数、Z-score、标准差、正态、回归、变量。\n"
    "【替换口径】把分数/概率/系数替换成具体事实，例如：\n"
    "- 不说「学习投入 0.42」，说「本月图书馆到馆 3 次，作业按时率 60%」。\n"
    "- 不说「关联系数 0.18」，说「生活节律下滑时，成绩也跟着回落」。\n"
    "- 不说「风险概率 0.67」，说「继续这样下去，下学期两门专业课可能挂科」。\n"
    "【写作口径】先下结论（一句话），再给事实证据（引用 deep_attribution 中的具体数字与来源表），"
    "最后给辅导员可以照着做的动作（引用 counselor_toolkit 与 personalized_micro_plan）。"
    "不得臆测情感/家庭/心理健康状况，只基于提供的行为数据。"
)

_REPORT_PROMPT_TEMPLATE = (
    "请基于下方结构化数据，为这名学生生成《个性化辅导参考报告》，使用 Markdown，"
    "严格遵守系统消息中的禁用词与替换口径。\n\n"
    "【行为原型】本学生被识别为：{arche_name}（{arche_nick}）。"
    "全文必须围绕这一原型的特点展开，不要写成千篇一律的通用报告。\n"
    "【数据时效】{validity_statement}\n"
    "【结论置信度】{confidence_note}\n"
    "【优势闪光】{warmth}\n\n"
    "请采用【三幕结构】：\n"
    "## 一、结论先行（<=80字）\n"
    "用一句话说明「这个学生现在处于什么状态、最值得关心哪一件事」。"
    "即使是高风险学生，也先提一句优势闪光点再转入关注点。\n\n"
    "## 二、证据链（500-600字）\n"
    "按「学习投入 / 学业产出 / 生活节律 / 社交融入 / 环境适应」五个维度各起一个小节。"
    "每个小节**必须采用三层叙事链结构**：\n"
    "  (1) **发生了什么**：引用 deep_attribution 或 triple_linkage 中 evidence_points 的**具体数字与来源表名**；\n"
    "  (2) **为什么发生**：引用 triple_linkage 中 motivation 的解读，用辅导员能理解的语言重述；\n"
    "  (3) **会导致什么**：引用 triple_linkage 中 impact 的后果预判，给出具体影响。\n"
    "若某维度 confidence_assessment 中标注为「低置信」，在该小节末尾加注「该维度数据较薄，建议面谈补充核实」。\n\n"
    "在轨迹演化部分，如果 trajectory_evidence 中有 transition_evidence，"
    "必须引用具体的行为证据（如「深夜门禁出入 XX 次」「图书馆到馆 XX 次」），"
    "说明是什么具体行为导致了状态转变，而不是只说状态编号。\n\n"
    "## 三、行动方案（约300字）\n"
    "- **本周一次谈话**：用 counselor_toolkit.opening_strategy 起手，引用 script 中的话术，"
    "避开 taboos，按 follow_up_questions 推进。\n"
    "- **7天微计划**：把 personalized_micro_plan 的每日动作改写成对学生说的话（第二人称）。\n"
    "- **反事实参考**：从 counterfactual_simulation 中选 1 个最相关的场景，"
    "用「如果当时……可能……」的句式写一句话，帮辅导员理解关键介入窗口。\n"
    "- **升级路径**：结合 counselor_toolkit.channel_recommendation，说清楚什么信号出现要转介。\n\n"
    "全文不超过 1100 字，不要出现禁用词，不要出现任何小数概率。\n\n"
    "【输入数据】\n{context_json}"
)

_QA_PROMPT_PREFIX = (
    "你是在回答一位辅导员关于这个学生的提问。严格遵守系统消息中的禁用词。\n"
    "回答结构：先一句话结论 -> 2-3 条具体事实证据（必须引用 deep_attribution 或 triple_linkage 里的真实数字和来源表）"
    " -> 2-3 条当下就能做的动作。不要出现概率/分数/算法术语。\n"
    "回答中如果涉及轨迹变化，引用 trajectory_evidence 中的具体行为证据（如深夜门禁次数、图书馆到馆次数等）。\n"
    "如果问到原因，优先使用 triple_linkage 中的「动机逻辑」解释。\n"
    "如果问到预后，引用 triple_linkage 中的「后果预判」和 counterfactual_simulation。\n"
)


@dataclass
class LLMNarrativeService:
    client: ModelScopeLLMClient
    model_name: str

    def _system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    def _report_prompt(self, report: dict[str, Any]) -> str:
        context = _extract_key_signals(report)
        archetype = context.get("behavior_archetype", {}) or {}
        arche_name = str(archetype.get("name", ""))
        arche_nick = str(archetype.get("nickname", ""))
        validity = context.get("data_validity", {}) or {}
        confidence = context.get("confidence_assessment", {}) or {}
        strength_hl = context.get("strength_highlights", {}) or {}
        warmth = str(strength_hl.get("warmth_statement", ""))

        return _REPORT_PROMPT_TEMPLATE.format(
            arche_name=arche_name,
            arche_nick=arche_nick,
            validity_statement=validity.get("statement", ""),
            confidence_note=confidence.get("overall_note", "置信度信息暂缺"),
            warmth=warmth,
            context_json=json.dumps(context, ensure_ascii=False, indent=2),
        )

    def generate_report_markdown(self, report: dict[str, Any]) -> str:
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": self._report_prompt(report)},
        ]
        return self.client.chat(model=self.model_name, messages=messages, temperature=0.35, max_tokens=8192)

    def answer_student_question(self, report: dict[str, Any], question: str) -> str:
        context = _extract_key_signals(report)
        user_prompt = (
            _QA_PROMPT_PREFIX
            + "辅导员问题：" + question + "\n"
            + "结构化数据：\n" + json.dumps(context, ensure_ascii=False, indent=2)
        )
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user_prompt},
        ]
        return self.client.chat(model=self.model_name, messages=messages, temperature=0.25, max_tokens=8192)

    def synthesize_rag_suggestion(
        self,
        report: dict[str, Any],
        retrieved_chunks: list[dict[str, Any]],
        query: str,
    ) -> str:
        """将检索到的知识库片段 + 学生上下文发给大模型，生成个性化 RAG 建议。"""
        context = _extract_key_signals(report)
        chunks_text = "\n\n---\n\n".join(
            f"【来源: {chunk.get('doc_name', '')}】\n{chunk.get('excerpt', '')}"
            for chunk in retrieved_chunks
        )
        user_prompt = (
            "你是一名资深高校辅导员。下面给出了一名学生的行为数据摘要，以及从知识库中检索到的相关干预策略原文。\n"
            "请你**结合这名学生的具体情况**，对知识库中的通用策略进行个性化改写，生成一段 200-400 字的"
            "针对性干预建议。\n\n"
            "【要求】\n"
            "1. 不要照搬知识库原文，要根据学生实际数据进行裁剪和定制。\n"
            "2. 使用辅导员能直接执行的具体语言，不要使用任何算法/模型/概率术语。\n"
            "3. 先给一句话结论，再给 2-3 条具体可执行的行动建议。\n"
            "4. 如果知识库中有话术模板，请根据学生情况填充具体内容，不要保留插槽占位符。\n\n"
            f"【检索问题】{query}\n\n"
            f"【学生行为数据摘要】\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"【知识库检索结果（{len(retrieved_chunks)} 条）】\n{chunks_text}"
        )
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user_prompt},
        ]
        return self.client.chat(model=self.model_name, messages=messages, max_tokens=4096)
