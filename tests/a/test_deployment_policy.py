import pytest

from backend.app.core.deployment_policy import validate_deployment


def test_development_does_not_require_production_secrets():
    validate_deployment({})


def test_production_missing_values_fail_without_disclosing_secrets():
    with pytest.raises(RuntimeError) as exc:
        validate_deployment({"APP_ENV": "production", "DATABASE_URL": "sqlite:///private-secret"})
    assert "DATABASE_URL" in str(exc.value)
    assert "private-secret" not in str(exc.value)


def valid():
    return {"APP_ENV": "production", "V2_AUTH_REQUIRED": "true", "LLM_PROVIDER": "openai_compatible",
            "OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://model.test/v1", "OPENAI_MODEL": "test",
            "DATABASE_URL": "postgresql://user:unique-password@db/app", "A3_CORS_ORIGINS": "https://app.test"}


def test_complete_production_config_passes():
    validate_deployment(valid())


@pytest.mark.parametrize("change", [{"A3_CORS_ORIGINS": "*"}, {"V2_AUTH_REQUIRED": "false"},
    {"A3_OFFLINE_DEMO": "1"}, {"OPENAI_API_KEY": ""},
    {"OPENAI_API_KEY": "REPLACE_WITH_MODEL_KEY"},
    {"A3_CORS_ORIGINS": "http://app.test"},
    {"A3_CORS_ORIGINS": "https://REPLACE_WITH_YOUR_HTTPS_DOMAIN"},
    {"DATABASE_URL": "postgresql://u:123456@db/app"},
    {"DATABASE_URL": "postgresql://u:short@db/app"},
    {"DATABASE_URL": "postgresql://u:REPLACE_WITH_STRONG_PASSWORD@db/app"},
    {"DATABASE_URL": "postgresql://u:change-me-local@db/app"}])
def test_insecure_production_config_is_rejected(change):
    with pytest.raises(RuntimeError):
        validate_deployment({**valid(), **change})


def test_production_disables_implicit_demo_accounts(monkeypatch):
    from backend.app.api.v1 import auth
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(auth, "_load_persisted_account", lambda *_: None)
    monkeypatch.setattr(auth, "_REGISTERED_ACCOUNTS", {})
    assert auth._find_account(auth.DEFAULT_ACCOUNTS["student"].account) is None


def test_production_env_template_fails_closed_until_filled():
    """The shipped production template must not pass validation with placeholders."""
    from pathlib import Path
    from dotenv import dotenv_values

    template = Path(__file__).resolve().parents[2] / ".env.production.example"
    values = {key: value for key, value in dotenv_values(template).items() if value is not None}
    database_url = (f"postgresql://{values['POSTGRES_USER']}:{values['POSTGRES_PASSWORD']}"
                    f"@postgres:5432/{values['POSTGRES_DB']}")
    env = {**values, "APP_ENV": "production", "A3_OFFLINE_DEMO": "0",
           "V2_AUTH_REQUIRED": "true", "DATABASE_URL": database_url}
    with pytest.raises(RuntimeError) as exc:
        validate_deployment(env)
    message = str(exc.value)
    assert "DATABASE_URL" in message and "OPENAI_API_KEY" in message
    assert "REPLACE_WITH" not in message


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/v1/resources/list",
    "/api/v1/chat/history/demo-session",
    "/api/v1/group-chat/course-room/messages",
])
async def test_production_requires_login_for_legacy_public_routes(monkeypatch, path):
    from starlette.requests import Request

    from backend.app.main import _require_auth_for_api

    monkeypatch.setenv("APP_ENV", "production")
    request = Request({"type": "http", "method": "GET", "path": path,
                       "headers": [], "query_string": b"", "server": ("localhost", 80),
                       "scheme": "http"})

    async def reach_endpoint(_request):
        raise AssertionError("anonymous request reached a legacy endpoint")

    response = await _require_auth_for_api(request, reach_endpoint)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_development_keeps_legacy_demo_route_public(monkeypatch):
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from backend.app.main import _require_auth_for_api

    monkeypatch.setenv("APP_ENV", "development")
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/resources/list",
                       "headers": [], "query_string": b"", "server": ("localhost", 80),
                       "scheme": "http"})

    async def reach_endpoint(_request):
        return JSONResponse({"reached": True})

    response = await _require_auth_for_api(request, reach_endpoint)
    assert response.status_code == 200
