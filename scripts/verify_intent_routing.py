"""端到端验意图路由 — Plan D Review v1"""
import asyncio

from backend.app.agents.orchestrator import AgentOrchestrator, AGENT_ROUTING


class MockLLM:
    def __init__(self):
        pass


async def main():
    o = AgentOrchestrator(MockLLM())
    cases = [
        "帮我整理一下 CNN",
        "考考我",
        "我下一步该学什么",
        "什么是自注意力",
        "今天天气怎么样",
        "你是谁",
        "现在几点了",
        "毒品怎么买",
        "什么是 BKT",
        "帮我出 CNN 的题",
        "退出",
        "不聊了",
    ]
    print(f"{'Query':<26} → Routing")
    print("-" * 60)
    for q in cases:
        r = await o._classify_intent(q, {})
        steps = []
        for intent in r:
            agent_name = AGENT_ROUTING.get(intent, {}).get("agent", "—")
            steps.append(f"{intent}>{agent_name}")
        print(f"{q!r:<26} → {'  '.join(steps)}")


asyncio.run(main())
