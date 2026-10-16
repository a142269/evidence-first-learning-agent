"""单 Agent 直通模式的对话门禁

背景：群聊/私聊里 @ 某位伙伴后，编排器会跳过意图识别直接把原文交给该
Agent。生成型 Agent（尤其是出题的小龙）会把任何输入都当成任务载荷——
用户发「你好」也会生成 12 道题，问讲解类问题也被硬转成练习。

门禁在直通派发前做两件事：
1. 寒暄/自我介绍类输入 → 返回该伙伴的人设介绍与用法示例，不触发生成；
2. 明显属于其他伙伴职责的请求 → 礼貌转介到正确的 @ 名称，不越权代答。

两条规则都只用确定性的关键词/正则，不调 LLM：门禁必须零延迟、可预测，
宁可放行模糊输入（由 Agent 正常处理），也不误拦真实任务。
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from backend.app.agents.base import AgentResponse

# partner_key → 对外人设。agent_name 必须取 PARTNER_TO_AGENT 的值，
# chat.py 的 _PUBLIC_AGENT_INFO 靠它把消息归到正确的公开角色名下。
PARTNER_PERSONAS: Dict[str, Dict[str, str]] = {
    "planner": {
        "agent_name": "path_planner",
        "name": "智狐",
        "role": "学习规划师",
        "skill": "根据你的目标、基础和可投入时间，规划分阶段学习路径",
        "example": "@智狐 帮我规划两周入门机器学习的学习路径",
    },
    "tutor": {
        "agent_name": "tutor",
        "name": "智灵",
        "role": "知识讲师",
        "skill": "讲解知识点、梳理概念关系、分析前置知识与易错点",
        "example": "@智灵 帮我梳理监督学习和无监督学习的区别",
    },
    "content": {
        "agent_name": "doc_gen",
        "name": "阿匠",
        "role": "内容工匠",
        "skill": "生成 PPT、文档、思维导图、讲解视频和讲解音频",
        "example": "@阿匠 做一份梯度下降的 PPT",
    },
    "quiz": {
        "agent_name": "exercise",
        "name": "小龙",
        "role": "练习伙伴",
        "skill": "围绕指定主题出分层练习题（可指定题量、题型和难度）",
        "example": "@小龙 出 12 道监督学习的练习题",
    },
    "evaluation": {
        "agent_name": "evaluator",
        "name": "团团",
        "role": "学习评估师",
        "skill": "评估你的学习情况、诊断薄弱环节并给出改进建议",
        "example": "@团团 评估一下我最近的学习情况",
    },
    "safety": {
        "agent_name": "safe_decline",
        "name": "球球",
        "role": "安全守护员",
        "skill": "守护学习边界，提示与课程无关或不适宜的内容",
        "example": "@球球 这个问题适合在课程里讨论吗",
    },
}

# 寒暄/元问题：整句匹配才算，避免误伤「你好，请出12道题」这类真任务。
_GREETING_RE = re.compile(
    r"^(?:你好|您好|哈喽|哈罗|嗨|嘿|hi|hello|hey|在吗|在不在|有人吗"
    r"|早上好|中午好|下午好|晚上好|早安|午安|晚安|谢谢|多谢|感谢|辛苦了"
    r"|你是谁|你能做什么|你会什么|你能干什么|能做啥|自我介绍|介绍一下(?:你)?自己)"
    r"[呀啊哦哟喽嘞哇~～!！。.？?，,\s]*$",
    re.IGNORECASE,
)

# 自域放行正则（宽）：命中说明请求确实属于该伙伴，直接放行。
# 宁可放宽——漏放行会把真任务错误转介，比放过一次模糊输入代价更高。
_DOMAIN_RES: Dict[str, re.Pattern] = {
    "quiz": re.compile(
        r"出.{0,30}题|出题|练习|习题|试题|题目|测验|考考|刷题|做题|错题"
        r"|quiz|[几多\d]+\s*道",
        re.IGNORECASE,
    ),
    "tutor": re.compile(
        r"讲解|讲讲|讲一下|解释|梳理|科普|什么是|是什么|为什么|怎么理解"
        r"|如何理解|区别|联系|关系|原理|推导|前置知识|易错点",
    ),
    "content": re.compile(
        r"ppt|课件|讲义|幻灯片|文档|思维导图|导图|脑图|视频|音频|朗读|录音",
        re.IGNORECASE,
    ),
    "planner": re.compile(
        r"规划|学习路径|学习计划|学习路线|学习顺序|先学什么|多久能",
    ),
    "evaluation": re.compile(
        r"评估|测评|打分|掌握(?:得|情况|程度)|水平怎么样|学得怎么样|薄弱",
    ),
}

# 转介触发正则（窄）：只有明确无歧义的强信号才把用户转给别的伙伴。
# 例如「模型评估」是学科名词，不能触发团团；「评估一下我」才算。
_REDIRECT_RES: Dict[str, re.Pattern] = {
    "quiz": re.compile(
        r"出.{0,30}题|出题|考考我|刷题|来[几多\d]+\s*道",
        re.IGNORECASE,
    ),
    "tutor": re.compile(
        r"讲解|讲讲|讲一下|解释|梳理|科普|什么是|为什么|怎么理解"
        r"|如何理解|区别|原理|推导|前置知识|易错点",
    ),
    "content": re.compile(
        r"ppt|课件|讲义|幻灯片|思维导图|导图|脑图"
        r"|(?:做|生成|制作|来)[个一份点]*.{0,12}(?:文档|视频|音频)",
        re.IGNORECASE,
    ),
    "planner": re.compile(
        r"规划|学习路径|学习计划|学习路线|学习顺序|先学什么|多久能",
    ),
    "evaluation": re.compile(
        r"评估(?:一下)?我|测评|给?我打分|我的?(?:水平|掌握|薄弱)|学得怎么样",
    ),
}

# 转介时的判定顺序：讲解类误 @ 最常见，放最前。
_REDIRECT_PRIORITY = ("tutor", "content", "planner", "quiz", "evaluation")


def _strip_mentions(text: str) -> str:
    return re.sub(r"@\S+", " ", text or "").strip(" \t\r\n，,。.！!？?：:；;")


def _greeting_response(partner_key: str) -> AgentResponse:
    p = PARTNER_PERSONAS[partner_key]
    content = (
        f"你好呀，我是{p['role']}**{p['name']}**！\n\n"
        f"我擅长：{p['skill']}。\n\n"
        f"直接把需求告诉我就行，例如：`{p['example']}`"
    )
    return AgentResponse(
        agent_name=p["agent_name"],
        success=True,
        content=content,
        content_type="markdown",
        metadata={"direct_chat_gate": "greeting"},
    )


def _redirect_response(
    partner_key: str, suggested_key: str, cleaned_input: str,
) -> AgentResponse:
    me = PARTNER_PERSONAS[partner_key]
    other = PARTNER_PERSONAS[suggested_key]
    request_preview = cleaned_input[:60]
    lines = [
        f"我是{me['role']}**{me['name']}**，这个请求更适合由"
        f"{other['role']}**{other['name']}**来处理～",
        "",
        f"你可以试试：`@{other['name']} {request_preview}`",
    ]
    if partner_key == "quiz":
        lines += [
            "",
            "如果你想先弄懂再练习，也欢迎随后回来找我："
            "`@小龙 出题：<主题>`（可指定题量与难度）。",
        ]
    return AgentResponse(
        agent_name=me["agent_name"],
        success=True,
        content="\n".join(lines),
        content_type="markdown",
        metadata={
            "direct_chat_gate": "redirect",
            "suggested_partner": suggested_key,
        },
    )


def evaluate_direct_chat_gate(
    partner_key: str, user_input: str,
) -> Optional[AgentResponse]:
    """直通派发前的门禁检查。

    Returns:
        AgentResponse — 寒暄回应或转介提示，编排器应直接返回它；
        None — 正常任务，继续交给目标 Agent 执行。
    """
    if partner_key not in PARTNER_PERSONAS:
        return None

    cleaned = _strip_mentions(user_input)

    # 规则 1：空内容或纯寒暄 → 人设自我介绍
    if not cleaned or (len(cleaned) <= 20 and _GREETING_RE.match(cleaned)):
        return _greeting_response(partner_key)

    # 规则 2：命中自己职责的强信号 → 放行
    own_re = _DOMAIN_RES.get(partner_key)
    if own_re and own_re.search(cleaned):
        return None

    # 规则 3：只命中其他伙伴职责 → 转介（安全员不参与转介判定）
    if partner_key != "safety":
        for candidate in _REDIRECT_PRIORITY:
            if candidate == partner_key:
                continue
            if _REDIRECT_RES[candidate].search(cleaned):
                return _redirect_response(partner_key, candidate, cleaned)

    # 无明确信号：放行，交由 Agent 按自身人设处理
    return None
