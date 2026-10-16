"""Plan D 2.2 — base.py 加 _acall_llm + _acall_llm_stream
幂等：跑多次结果一致。
"""
from pathlib import Path
import sys

p = Path(r"F:\比赛\中软杯\A3\backend\app\agents\base.py")
text = p.read_text(encoding="utf-8")

OLD = '''    def _call_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """调用 LLM 并返回文本"""
        messages = self._build_messages(user_prompt, history, extra_system)
        return self.llm.chat(messages, temperature=temperature)'''

NEW = OLD + '''

    async def _acall_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """Plan D 2.2 — 异步调用 LLM

        内部委托 self.llm.achat()，避免在 async execute() 中
        同步阻塞事件循环（让 asyncio.gather 退化为串行）。
        """
        messages = self._build_messages(user_prompt, history, extra_system)
        return await self.llm.achat(messages, temperature=temperature)

    async def _acall_llm_stream(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ):
        """Plan D 2.2 — 异步流式 LLM 调用

        供 tutor_agent 等需要把 LLM 输出逐 chunk yield 给 SSE 的 Agent 用。
        """
        messages = self._build_messages(user_prompt, history, extra_system)
        async for chunk in self.llm.chat_stream(
            messages, temperature=temperature
        ):
            yield chunk'''

if OLD not in text:
    print("[FAIL] _call_llm pattern not found - might already be patched or has trailing newline variance")
    print("---first 200 chars around 'def _call_llm'---")
    idx = text.find("def _call_llm")
    if idx > 0:
        print(text[idx-50:idx+800])
    sys.exit(1)

# 已经包含 _acall_llm 的话跳过
if "async def _acall_llm" in text:
    print("[SKIP] _acall_llm already present, no-op")
else:
    text = text.replace(OLD, NEW, 1)
    p.write_text(text, encoding="utf-8")
    print(f"[OK] base.py updated ({len(text)} bytes)")
