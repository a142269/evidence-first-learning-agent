"""One metered V2 provider smoke check; never prints prompts, keys or answers.

Run only with a private env-file/runtime secret injection and the shared Redis
evaluation budget configured. A provider failure remains a failed acceptance.
"""
from __future__ import annotations

import asyncio
import argparse
import json
import os

from backend.app.core.llm_client import LLMClient
from backend.app.services.embedding_provider import EmbeddingProviderError, get_embedding_provider


async def main(*, embedding_only: bool = False) -> int:
    required = ("V2_EVAL_BUDGET_CNY", "V2_EVAL_BUDGET_ID",
                "V2_EVAL_INPUT_CNY_PER_MILLION_UPPER",
                "V2_EVAL_OUTPUT_CNY_PER_MILLION_UPPER",
                "V2_EVAL_EMBED_CNY_PER_MILLION_UPPER", "REDIS_URL")
    if any(not os.getenv(key) for key in required):
        print(json.dumps({"status": "configuration_missing"}))
        return 2
    result = {"model": "not_started", "embedding": "not_started"}
    if not embedding_only:
        try:
            response = await LLMClient().achat_strict_with_usage(
                [{"role": "user", "content": "只回答：测试通过"}], max_tokens=32)
            result["model"] = "ok" if response["text"].strip() else "empty"
            result["model_usage"] = "actual" if response["usage"] is not None else "unknown"
        except Exception as exc:
            result["model"] = type(exc).__name__
    try:
        vectors = get_embedding_provider().embed_documents(["课程学习检索测试"])
        result["embedding"] = "ok" if len(vectors) == 1 else "invalid"
    except EmbeddingProviderError as exc:
        # Adapter errors are controlled status codes and never provider bodies.
        result["embedding"] = str(exc)
    except Exception as exc:
        result["embedding"] = type(exc).__name__
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["embedding"] == "ok" and (embedding_only or result["model"] == "ok") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(embedding_only=args.embedding_only)))
