"""Plan D 2.2 — base.py 修 _acall_llm 加 fallback

兼容性：
- 真实 LLMClient（achat 是 async coroutine）走 async 路径，性能提升
- MagicMock / 旧 Mock（achat 是 sync attribute）自动 fallback 到 _call_llm
"""
import asyncio
import inspect
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\backend\app\agents\base.py")
text = p.read_text(encoding="utf-8")

OLD = '''    async def _acall_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """Plan D 2.2 异步调用 LLM

        内部委托 self.llm.achat()，避免在 async execute() 中
        同步阻塞事件循环（让 asyncio.gather 退化为串行）。
        """
        messages = self._build_messages(user_prompt, history, extra_system)
        return await self.llm.achat(messages, temperature=temperature)'''

NEW = '''    async def _acall_llm(
        self,
        user_prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        extra_system: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """Plan D 2.2 异步调用 LLM

        内部委托 self.llm.achat()。如果 self.llm.achat 不可 await（MagicMock /
        老 Mock），自动 fallback 到 _call_llm 同步版本，保证测试兼容。
        """
        achat = getattr(self.llm, "achat", None)
        if achat is None or not inspect.iscoroutinefunction(achat):
            # fallback 到同步版本（测试 / 旧 Mock 兼容）
            return self._call_llm(
                user_prompt, history=history,
                extra_system=extra_system, temperature=temperature,
            )
        messages = self._build_messages(user_prompt, history, extra_system)
        return await achat(messages, temperature=temperature)'''

if OLD not in text:
    print("[FAIL] _acall_llm block not matched")
    raise SystemExit(1)

text = text.replace(OLD, NEW, 1)
p.write_text(text, encoding="utf-8")
print(f"[OK] base.py _acall_llm with fallback ({len(text)} bytes)")
