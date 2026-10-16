"""Plan D Review v1 · safe_decline 落地：orchestrator + agents/__init__"""
import re
from pathlib import Path

ROOT = Path(r"F:\比赛\中软杯\A3")

# ============================================================
# 1) backend/app/agents/orchestrator.py
#    - 加 out_of_scope 关键词表
#    - 改 _classify_intent：当 out_of_scope 命中时，不再追加 tutoring 兜底
#    - 在 AGENT_ROUTING 加 out_of_scope
# ============================================================
orch_path = ROOT / "backend" / "app" / "agents" / "orchestrator.py"
orch = orch_path.read_text(encoding="utf-8")

# 1a) AGENT_ROUTING 加 out_of_scope（在 generation 类意图之后，evaluation 之前）
old_routing_tail = '''    # 智能辅导
    "tutoring": {
        "agent": "tutor",
        "trigger": "user_asks_question",
        "priority": 2,
    },
    # 效果评估
    "evaluation": {'''

new_routing_tail = '''    # 智能辅导
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
    "evaluation": {'''

assert old_routing_tail in orch, "AGENT_ROUTING tail not matched"
orch = orch.replace(old_routing_tail, new_routing_tail, 1)

# 1b) _classify_intent 中加 out_of_scope 关键词表 + 命中时不追加 tutoring
old_intent_tail = '''            "evaluation": [
                "诊断", "评估下", "测评", "水平",
                "学得怎么样", "掌握了吗", "薄弱", "强弱项",
            ],
        }

        matched: List[str] = []
        for intent, keywords in intent_keywords.items():
            if any(kw in user_input for kw in keywords):
                matched.append(intent)

        # 始终包含画像更新（每次对话更新画像）
        if "profile_update" not in matched:
            matched.insert(0, "profile_update")

        # 如果没有规则匹配到，由 LLM 判断意图
        if len(matched) <= 1:  # 只有 profile_update
            llm_intent = await self._llm_classify_intent(user_input)
            matched.extend(llm_intent)

        # Plan D · 3.1 — 兜底：LLM 也分类不出时仍返回 tutoring
        if matched == ["profile_update"]:
            matched.append("tutoring")

        return matched'''

new_intent_tail = '''            "evaluation": [
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

        matched: List[str] = []
        for intent, keywords in intent_keywords.items():
            if any(kw in user_input for kw in keywords):
                matched.append(intent)

        # 始终包含画像更新（每次对话更新画像）—— 但如果走 out_of_scope
        # 也不强加 profile_update，避免污染画像
        if "profile_update" not in matched and "out_of_scope" not in matched:
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

        return matched'''

assert old_intent_tail in orch, "_classify_intent tail not matched"
orch = orch.replace(old_intent_tail, new_intent_tail, 1)

orch_path.write_text(orch, encoding="utf-8")
print(f"[OK] orchestrator.py updated: {len(orch)} bytes")

# ============================================================
# 2) backend/app/agents/__init__.py
#    - 补 __all__ 加 SafeDeclineAgent
# ============================================================
init_path = ROOT / "backend" / "app" / "agents" / "__init__.py"
init_text = init_path.read_text(encoding="utf-8")
old_all = '''    "COVVerifierAgent", "AILecturerAgent", "TextbookQAAgent",'''
new_all = '''    "COVVerifierAgent", "SafeDeclineAgent",  # Plan D · Review v1
    "AILecturerAgent", "TextbookQAAgent",'''
assert old_all in init_text, "__all__ pattern not matched"
init_text = init_text.replace(old_all, new_all, 1)
init_path.write_text(init_text, encoding="utf-8")
print(f"[OK] agents/__init__.py updated: {len(init_text)} bytes")

print("[DONE]")
