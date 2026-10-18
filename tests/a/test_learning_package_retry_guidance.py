import json

import pytest

from backend.app.agent_runtime.learning_package import LearningPackageGraph, Lesson, PackageFailure


class Runtime:
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def complete_structured(self, messages, *, max_tokens):
        self.requests.append([dict(item) for item in messages])
        return {"text": self.replies.pop(0), "usage": None}


@pytest.mark.asyncio
async def test_truncated_json_retry_uses_fixed_guidance_without_echoing_output():
    secret_text = "untrusted-instruction-xyz"
    good = json.dumps({"explanation": "这是一段长度足够的示例讲解，帮助理解课程的关键概念。", "source_ids": ["c1"]}, ensure_ascii=False)
    runtime = Runtime(['{"explanation":"' + secret_text, good])
    graph = LearningPackageGraph(runtime)
    result = await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    assert result["source_ids"] == ["c1"]
    retry = runtime.requests[1][-1]["content"]
    assert "不是完整的 JSON" in retry
    assert secret_text not in retry


@pytest.mark.asyncio
async def test_schema_error_retry_never_echoes_model_field_names():
    runtime = Runtime(['{"attacker_field_987":true}', '{"attacker_field_987":true}'])
    graph = LearningPackageGraph(runtime)
    with pytest.raises(PackageFailure, match="learning_package_invalid_output"):
        await graph._ask({"message": "讲解", "budget": {}}, "Tutor", "生成讲解", {}, Lesson)
    retry = runtime.requests[1][-1]["content"]
    assert "检查字段类型" in retry
    assert "attacker_field_987" not in retry
