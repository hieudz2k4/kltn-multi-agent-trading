import backend.config.settings as settings_mod


def _fresh_settings():
    settings_mod.get_settings.cache_clear()
    try:
        return settings_mod.get_settings()
    finally:
        settings_mod.get_settings.cache_clear()


def test_agent_defaults(monkeypatch):
    for var in [
        "OPENTERMINALUI_OPENROUTER_API_KEY", "OPENROUTER_API_KEY",
        "OPENTERMINALUI_OPENROUTER_BASE_URL", "OPENROUTER_BASE_URL",
        "OPENTERMINALUI_AGENT_PROVIDER", "AGENT_PROVIDER",
        "OPENTERMINALUI_AGENT_MODEL", "AGENT_MODEL",
        "OPENTERMINALUI_AGENT_DISABLE_MODEL_FALLBACKS", "AGENT_DISABLE_MODEL_FALLBACKS",
        "OPENTERMINALUI_AGENT_MODELS_TOOL_USE", "AGENT_MODELS_TOOL_USE",
        "OPENTERMINALUI_AGENT_MODELS_REASONING", "AGENT_MODELS_REASONING",
        "OPENTERMINALUI_AGENT_MODELS_GENERAL", "AGENT_MODELS_GENERAL",
        "OPENTERMINALUI_AGENT_MAX_STEPS", "OPENTERMINALUI_AGENT_TIMEOUT_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)
    s = _fresh_settings()
    assert s.agent_provider == "openrouter"
    # Default is a free OpenRouter model (the key may be restricted to free tier).
    assert s.agent_model == "openai/gpt-oss-20b:free"
    assert s.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert s.openrouter_api_key is None
    assert s.agent_max_steps == 12
    assert s.agent_deep_max_steps == 24
    assert s.agent_timeout_seconds == 120.0
    assert s.agent_disable_model_fallbacks is False
    assert s.agent_models_tool_use[0] == "meta-llama/llama-3.3-70b-instruct:free"
    assert s.agent_models_reasoning[0] == "deepseek/deepseek-r1:free"
    assert s.agent_models_general[-1] == "google/gemini-2.0-flash-exp:free"


def test_agent_env_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENTERMINALUI_AGENT_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("AGENT_DISABLE_MODEL_FALLBACKS", "true")
    s = _fresh_settings()
    assert s.openrouter_api_key == "sk-or-test"
    assert s.agent_model == "openai/gpt-4o"
    assert s.agent_disable_model_fallbacks is True
