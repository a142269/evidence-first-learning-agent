from backend.app.core.config import _normalize_deepseek_model


def test_legacy_deepseek_names_use_current_flash_model():
    assert _normalize_deepseek_model("deepseek-chat") == "deepseek-flash"
    assert _normalize_deepseek_model("deepseek-v4-flash") == "deepseek-flash"
    assert _normalize_deepseek_model("deepseek-flash") == "deepseek-flash"
