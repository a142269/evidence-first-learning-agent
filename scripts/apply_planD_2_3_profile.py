"""Plan D 2.3 — profile_agent.py 用新 extractor 替换 inline 正则"""
import re
from pathlib import Path

p = Path(r"F:\比赛\中软杯\A3\backend\app\agents\profile_agent.py")
text = p.read_text(encoding="utf-8")

OLD = '''    def _extract_profile_updates(self, llm_output: str) -> dict:
        """从 LLM 输出中提取 profile_update JSON"""
        import re
        pattern = r"```profile_update\\s*\\n(.*?)\\n```"
        match = re.search(pattern, llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                logger.warning("Failed to parse profile_update JSON from LLM output")
        return {}'''

NEW = '''    def _extract_profile_updates(self, llm_output: str) -> dict:
        """Plan D · 2.3 — 容错提取 LLM 输出中的画像更新 JSON

        通过 services.profile_extractor 替换原简单正则：
        * 支持 ```profile_update / ```json / 无标签 fence
        * 容错 JSON 注释（// 和 /* */）+ 尾逗号
        * 提供 fallback：找首个 top-level {...}
        * 返回 (profile, status) 让调用方上报 SSE

        本方法保留旧 API（仅返回 dict），但内部走容错路径。
        """
        try:
            from backend.app.services.profile_extractor import extract_profile_updates as _ext
            profile, _status = _ext(llm_output)
            return profile
        except Exception as exc:
            logger.warning(f"[ProfileAgent] 容错提取失败: {exc}")
            return {}'''

if OLD not in text:
    print("[FAIL] _extract_profile_updates block not matched")
    raise SystemExit(1)

text = text.replace(OLD, NEW, 1)

# 在 execute() 内追加 profile_status 输出到 AgentResponse.metadata（供 SSE 透传）
old_extract_call = "        profile_updates = self._extract_profile_updates(result)"
new_extract_call = '''        # Plan D · 2.3 — 同时取 status 一起塞到 metadata 给上游
        from backend.app.services.profile_extractor import extract_profile_updates as _ext2
        profile_updates, profile_status = _ext2(result)
        profile_status_meta = (
            "success" if profile_status == "success"
            else "no_profile_block"
            if profile_status == "no_profile_block"
            else "json_parse_failed"
        )'''
if old_extract_call in text:
    text = text.replace(old_extract_call, new_extract_call, 1)
    print("[OK] inline profile_extract call upgraded")
else:
    print("[SKIP] inline call already updated, double-check idempotent")

p.write_text(text, encoding="utf-8")
print(f"[OK] profile_agent.py updated ({len(text)} bytes)")
