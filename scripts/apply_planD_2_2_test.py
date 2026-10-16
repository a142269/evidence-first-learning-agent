"""Plan D 2.2 — test_base_agent.py 追加 TestAsyncLLMCall"""
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\tests\a\test_base_agent.py")
text = p.read_text(encoding="utf-8")

if "TestAsyncLLMCall" in text:
    print("[SKIP] TestAsyncLLMCall already present, idempotent")
    raise SystemExit(0)

ADDITION = '''

# ============================================================
# Plan D · 2.2 — 异步 LLM 调用验证
# ============================================================
class TestAsyncLLMCall:
    """Plan D · 2.2 验证 BaseAgent 的 _acall_llm 异步路径"""

    def test_acall_llm_method_exists(self, test_agent):
        """BaseAgent 必须暴露 _acall_llm 异步方法（且为 coroutinefunction）"""
        assert hasattr(test_agent, "_acall_llm")
        assert callable(test_agent._acall_llm)
        import inspect
        assert inspect.iscoroutinefunction(test_agent._acall_llm)

    def test_acall_llm_stream_method_exists(self, test_agent):
        """BaseAgent 必须暴露 _acall_llm_stream 异步生成器方法"""
        import inspect
        assert inspect.isasyncgenfunction(test_agent._acall_llm_stream)

    @pytest.mark.asyncio
    async def test_acall_llm_delegates_to_llm_achat(self):
        """_acall_llm 内部委托给 self.llm.achat()，不调用同步 .chat()"""
        from backend.app.agents.base import BaseAgent, AgentContext, AgentResponse
        from backend.app.core.llm_client import LLMClient

        class _Probe(BaseAgent):
            @property
            def name(self):
                return "probe"

            @property
            def description(self):
                return "probe"

            @property
            def system_prompt(self):
                return "probe"

            async def execute(self, context):
                return AgentResponse(agent_name="probe", success=True, content="ok")

        class _MockLLM:
            def __init__(self):
                self.chat_called = 0
                self.achat_called = 0

            def chat(self, messages, temperature=None):
                self.chat_called += 1
                return "sync-fallback"

            async def achat(self, messages, temperature=None):
                self.achat_called += 1
                return "async-result"

        mock = _MockLLM()
        agent = _Probe(llm_client=mock)
        result = await agent._acall_llm("user prompt")
        assert result == "async-result"
        assert mock.achat_called == 1
        assert mock.chat_called == 0  # 关键：异步方法不能调同步 .chat

    @pytest.mark.asyncio
    async def test_concurrent_acall_llm_is_concurrent(self):
        """并发 3 个 _acall_llm 应聚集在 ~1 个 mock 耗时，而不是 3 倍"""
        import asyncio
        import time
        from backend.app.agents.base import BaseAgent
        from backend.app.core.llm_client import LLMClient

        class _Slow(BaseAgent):
            @property
            def name(self):
                return "slow"

            @property
            def description(self):
                return "slow"

            @property
            def system_prompt(self):
                return "slow"

            async def execute(self, context):
                return None

        llm = LLMClient()

        async def patched_achat(messages, temperature=None, max_tokens=None):
            await asyncio.sleep(0.05)
            return "ok"

        llm.achat = patched_achat
        agent = _Slow(llm_client=llm)

        t0 = time.perf_counter()
        results = await asyncio.gather(
            agent._acall_llm("q1"),
            agent._acall_llm("q2"),
            agent._acall_llm("q3"),
        )
        elapsed = time.perf_counter() - t0

        assert results == ["ok", "ok", "ok"]
        # 串行需 3 * 0.05 = 0.15s；并发应 < 0.12s
        assert elapsed < 0.12, f"并发应 < 0.12s, got {elapsed:.3f}s"
'''

# Append
text = text.rstrip() + ADDITION
p.write_text(text, encoding="utf-8")
print(f"[OK] appended, total {len(text)} bytes")
