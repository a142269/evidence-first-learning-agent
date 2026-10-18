"""Fail-closed configuration checks for explicitly production deployments."""
from __future__ import annotations

import os
from collections.abc import Mapping
from urllib.parse import urlsplit, unquote


def production_mode(env: Mapping[str, str] | None = None) -> bool:
    values = os.environ if env is None else env
    return values.get("APP_ENV", "development").strip().lower() == "production"


def validate_deployment(env: Mapping[str, str] | None = None) -> None:
    values = os.environ if env is None else env
    if not production_mode(values):
        return
    errors: list[str] = []
    if values.get("V2_AUTH_REQUIRED", "").lower() not in {"true", "1"}:
        errors.append("V2_AUTH_REQUIRED")
    if values.get("A3_OFFLINE_DEMO", "").lower() in {"true", "1"}:
        errors.append("A3_OFFLINE_DEMO")
    provider = values.get("LLM_PROVIDER", "").lower()
    required = ("SPARK_APP_ID", "SPARK_API_KEY", "SPARK_API_SECRET") if provider == "spark" else (
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
    )
    if provider not in {"spark", "deepseek", "openai_compatible"}:
        errors.append("LLM_PROVIDER")
    for key in required:
        value = values.get(key, "").strip()
        lowered = value.lower()
        if (not value or "replace" in lowered or "change-me" in lowered
                or "example" in lowered):
            errors.append(key)
    try:
        database = urlsplit(values.get("DATABASE_URL", ""))
        password = unquote(database.password or "")
        lowered = password.lower()
        placeholder = any(marker in lowered for marker in
                          ("change-me", "changeme", "replace", "example", "placeholder"))
        if (not database.scheme.startswith("postgresql") or not password
                or len(password) < 12 or lowered in {"123456", "password", "postgres"}
                or placeholder):
            errors.append("DATABASE_URL")
    except ValueError:
        errors.append("DATABASE_URL")
    origins = [item.strip() for item in values.get("A3_CORS_ORIGINS", "").split(",") if item.strip()]
    if not origins or any(
        item in {"*", "null"}
        or not item.startswith("https://")
        or any(marker in item.lower() for marker in ("replace_with", "change-me", "your-domain"))
        for item in origins
    ):
        errors.append("A3_CORS_ORIGINS")
    if errors:
        # Variable names only, never their values or a database URL.
        raise RuntimeError("invalid_production_configuration: " + ", ".join(sorted(set(errors))))
