from backend.config.settings import AppSettings
from backend.services.llm.model_router import (
    SAFETY_MODEL,
    TaskProfile,
    classify_intent,
    select_chain,
)


def _assert_safe_chain(chain: list[str]) -> None:
    assert chain
    assert chain[-1] == SAFETY_MODEL
    assert len(chain) == len(set(chain))
    assert all(model.endswith(":free") for model in chain)


def test_select_chain_uses_tool_models_for_tool_phase():
    settings = AppSettings()
    chain = select_chain(TaskProfile(phase="tool_use"), settings)
    assert chain[:2] == settings.agent_models_tool_use[:2]
    _assert_safe_chain(chain)


def test_select_chain_uses_reasoning_models_for_synthesis_and_debate_roles():
    settings = AppSettings()
    for profile in (
        TaskProfile(phase="synthesis"),
        TaskProfile(role="bull"),
        TaskProfile(role="bear"),
        TaskProfile(role="portfolio_manager"),
    ):
        chain = select_chain(profile, settings)
        assert chain[:3] == settings.agent_models_reasoning[:3]
        _assert_safe_chain(chain)


def test_select_chain_uses_general_models_for_trivial_work():
    settings = AppSettings()
    chain = select_chain(TaskProfile(mode="trivial"), settings)
    assert chain[0] == settings.agent_models_general[1]
    _assert_safe_chain(chain)


def test_classify_intent_keywords():
    assert classify_intent("Backtest a momentum rotation screen") == "quantitative"
    assert classify_intent("Explain the risk thesis and outlook") == "narrative"
    assert classify_intent("Hello") == "general"


def test_invalid_configured_models_do_not_remove_safety_net():
    settings = AppSettings(agent_models_tool_use=["paid/model", "qwen/qwen3-coder:free"])
    _assert_safe_chain(select_chain(TaskProfile(phase="tool_use"), settings))


def test_disable_model_fallbacks_uses_only_agent_model():
    settings = AppSettings(agent_model="openrouter/model", agent_disable_model_fallbacks=True)
    assert select_chain(TaskProfile(phase="tool_use"), settings) == ["openrouter/model"]
    assert select_chain(TaskProfile(phase="synthesis"), settings) == ["openrouter/model"]
