"""Bounded, durable conversational memory from completed authenticated runs."""
from sqlalchemy import select

from backend.app.agent_runtime.run_audit import RunPersistenceError
from backend.app.core.models import AgentRunRecord


def load_conversation_memory(session_factory, *, user_id: str, session_id: str,
                             course_id: str, before: float) -> tuple[list[dict], list[str]]:
    if not session_id or user_id == "anonymous":
        return [], []
    try:
        with session_factory() as db:
            rows = db.scalars(select(AgentRunRecord).where(
                AgentRunRecord.user_id == user_id,
                AgentRunRecord.session_id == session_id,
                AgentRunRecord.status == "completed",
                AgentRunRecord.created_at < before,
                AgentRunRecord.metadata_data["memory_eligible"].as_boolean().is_(True),
                AgentRunRecord.metadata_data["request"]["course_id"].as_string() == course_id,
            ).order_by(AgentRunRecord.created_at.desc(), AgentRunRecord.id.desc()).limit(3)).all()
            history, run_ids = [], []
            for row in reversed(rows):
                metadata = row.metadata_data or {}
                result = metadata.get("result", {})
                answer = result.get("answer", "")
                if not answer or "approval" in result or result.get("quality", {}).get("safety_refusal"):
                    continue
                history.extend([
                    {"role": "user", "content": str(metadata["request"]["message"])[:2000]},
                    {"role": "assistant", "content": str(answer)[:2000]},
                ])
                run_ids.append(row.id)
            return history, run_ids
    except Exception:
        raise RunPersistenceError("run_persistence_unavailable") from None
