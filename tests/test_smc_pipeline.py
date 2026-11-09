"""Unit and integration test suite for SMC Multi-Agent Architecture (Hybrid & Legacy Baseline)."""

import pytest

from src.agents.shared.circuit_breaker import CircuitBreaker
from src.agents.smc.adversarial_risk_agent import create_adversarial_risk_agent
from src.agents.smc.macro_sentiment_agent import (
    STATE_MACRO_SENTIMENT,
    MacroSentiment,
    create_macro_sentiment_agent,
    get_economic_calendar,
    get_intermarket_bias,
    get_macro_news_headlines,
)
from src.agents.smc.smc_orchestrator import create_smc_orchestrator
from src.agents.smc.smc_strategy_agent import create_smc_strategy_agent

# Legacy baseline imports
from src.agents.smc.legacy_baseline.htf_bias_agent import create_htf_bias_agent
from src.agents.smc.legacy_baseline.poi_agent import create_poi_agent
from src.agents.smc.legacy_baseline.sizer_agent import create_sizer_agent
from src.agents.smc.legacy_baseline.structure_agent import create_structure_agent

from src.core.schemas import (
    HTFBias,
    HTFBiasEnum,
    MarketStructure,
    OrderDirection,
    POIType,
    POIZone,
    RiskVerdict,
    SMCSetup,
    StructureType,
    VetoCode,
)
from src.core.state import (
    STATE_HTF_BIAS,
    STATE_MARKET_STRUCTURE,
    STATE_POI_ZONE,
    STATE_RISK_VERDICT,
    STATE_SMC_SETUP,
)


def test_new_hybrid_smc_orchestrator_hierarchy():
    """Verify new 3-tier cognitive Multi-Agent hierarchy under smc_orchestrator."""
    orchestrator = create_smc_orchestrator()
    assert orchestrator.name == "smc_orchestrator"
    assert len(orchestrator.sub_agents) == 3

    sub_names = [sub.name for sub in orchestrator.sub_agents]
    assert sub_names == [
        "macro_sentiment_agent",
        "smc_strategy_agent",
        "adversarial_risk_agent",
    ]


def test_new_agent_schemas_and_keys():
    """Verify contracts of the new Hybrid Multi-Agent components."""
    macro = create_macro_sentiment_agent()
    strategy = create_smc_strategy_agent()
    risk = create_adversarial_risk_agent()

    assert macro.output_schema == MacroSentiment
    assert macro.output_key == STATE_MACRO_SENTIMENT

    assert strategy.output_schema == SMCSetup
    assert strategy.output_key == STATE_SMC_SETUP

    assert risk.output_schema == RiskVerdict
    assert risk.output_key == STATE_RISK_VERDICT


def test_legacy_baseline_hierarchy():
    """Verify original baseline sub_agents remain intact for comparative studies."""
    htf = create_htf_bias_agent()
    struct = create_structure_agent()
    poi = create_poi_agent()
    sizer = create_sizer_agent()

    assert htf.output_schema == HTFBias
    assert htf.output_key == STATE_HTF_BIAS

    assert struct.output_schema == MarketStructure
    assert struct.output_key == STATE_MARKET_STRUCTURE

    assert poi.output_schema == POIZone
    assert poi.output_key == STATE_POI_ZONE

    assert sizer.output_schema == SMCSetup
    assert sizer.output_key == STATE_SMC_SETUP


def test_smc_setup_rr_validation():
    """Verify automatic invalidation of trade setups with R:R < 2.0."""
    valid_setup = SMCSetup(
        symbol="XAUUSD",
        htf_bias=HTFBiasEnum.BULLISH,
        structure_type=StructureType.BOS,
        poi_type=POIType.ORDER_BLOCK,
        direction=OrderDirection.BUY,
        entry=2731.50,
        stop_loss=2729.50,
        take_profit=2737.50,
        lot_size=0.15,
        risk_reward_ratio=3.0,
        pip_distance_sl=20.0,
        is_valid=True,
    )
    assert valid_setup.is_valid is True

    invalid_setup = SMCSetup(
        symbol="XAUUSD",
        htf_bias=HTFBiasEnum.BULLISH,
        structure_type=StructureType.BOS,
        poi_type=POIType.ORDER_BLOCK,
        direction=OrderDirection.BUY,
        entry=2731.50,
        stop_loss=2729.50,
        take_profit=2733.50,
        lot_size=0.15,
        risk_reward_ratio=1.0,
        pip_distance_sl=20.0,
        is_valid=True,
    )
    assert invalid_setup.is_valid is False


def test_agent_tool_registrations():
    """Verify exact deterministic tool bindings for Macro, Strategy, and Adversarial Risk agents."""
    macro = create_macro_sentiment_agent()
    strategy = create_smc_strategy_agent()
    risk = create_adversarial_risk_agent()

    macro_tools = [t.__name__ for t in macro.tools]
    assert set(macro_tools) == {
        "get_economic_calendar",
        "get_macro_news_headlines",
        "get_intermarket_bias",
    }

    strategy_tools = [t.__name__ for t in strategy.tools]
    assert set(strategy_tools) == {
        "get_candles",
        "get_current_price",
        "get_account_snapshot",
        "detect_market_structure",
        "detect_poi_zones",
    }

    risk_tools = [t.__name__ for t in risk.tools]
    assert set(risk_tools) == {
        "get_account_snapshot",
        "get_average_spread",
        "get_swap_rate",
        "place_market_order",
    }


def test_macro_sentiment_calendar_and_regimes():
    """Verify MacroSentiment contract across RISK_ON, RISK_OFF, and HIGH_IMPACT_NEWS_COOLDOWN."""
    events = get_economic_calendar("USD")
    assert len(events) >= 1
    assert any("impact" in e for e in events)
    assert any("minutes_until_release" in e for e in events)

    risk_on = MacroSentiment(
        risk_environment="RISK_ON",
        is_safe_to_trade=True,
        active_events=[],
        sentiment_rationale="Calm macro environment",
    )
    assert risk_on.is_safe_to_trade is True

    cooldown = MacroSentiment(
        risk_environment="HIGH_IMPACT_NEWS_COOLDOWN",
        is_safe_to_trade=False,
        active_events=["US CPI YoY"],
        sentiment_rationale="CPI release within 30m",
    )
    assert cooldown.is_safe_to_trade is False


def test_forexfactory_live_feed_parser(monkeypatch):
    """Verify live ForexFactory JSON parser filters USD high/medium events and calculates timing."""
    from src.agents.smc.macro_sentiment_agent import _fetch_forexfactory_calendar

    # Ensure live mode (mock disabled)
    monkeypatch.setenv("MT5_MOCK", "false")
    monkeypatch.setenv("CALENDAR_MOCK", "false")

    live_events = get_economic_calendar("USD")
    assert isinstance(live_events, list)
    assert len(live_events) > 0

    first_event = live_events[0]
    assert first_event["currency"] == "USD"
    assert first_event["impact"] in ["HIGH", "CRITICAL"]
    assert "minutes_until_release" in first_event
    assert isinstance(first_event["minutes_until_release"], int)


def test_macro_news_headlines_and_intermarket_bias(monkeypatch):
    """Verify live/fallback behavior for macro news headlines and inter-market bias tools."""
    # Test headlines tool
    headlines = get_macro_news_headlines()
    assert isinstance(headlines, list)
    assert len(headlines) > 0
    assert "title" in headlines[0]
    assert "source" in headlines[0]

    # Test inter-market bias tool
    monkeypatch.setenv("MT5_MOCK", "true")
    bias = get_intermarket_bias()
    assert isinstance(bias, dict)
    assert bias["dxy_bias"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert "gold_impact" in bias
    assert "status" in bias


@pytest.mark.parametrize(
    "veto_code",
    [
        VetoCode.VETO_CIRCUIT,
        VetoCode.VETO_SPREAD,
        VetoCode.VETO_SWAP,
        VetoCode.VETO_RR,
        VetoCode.VETO_EXPOSURE,
    ],
)
def test_adversarial_risk_verdict_all_veto_codes(veto_code: VetoCode):
    """Verify RiskVerdict contract across all 5 VETO codes and full approval."""
    veto_verdict = RiskVerdict(
        signal_id="sig-veto-001",
        approved=False,
        veto_reason=f"Triggered {veto_code.value}",
        veto_code=veto_code,
        recommended_volume=0.0,
        projected_net_exposure=0.0,
    )
    assert veto_verdict.approved is False
    assert veto_verdict.veto_code == veto_code
    assert veto_verdict.recommended_volume == 0.0

    approved_verdict = RiskVerdict(
        signal_id="sig-pass-001",
        approved=True,
        veto_reason=None,
        veto_code=None,
        recommended_volume=0.25,
        projected_net_exposure=0.02,
    )
    assert approved_verdict.approved is True
    assert approved_verdict.veto_code is None
    assert approved_verdict.recommended_volume == 0.25
