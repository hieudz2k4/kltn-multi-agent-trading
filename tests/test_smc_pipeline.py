"""Unit and integration test suite for SMC Multi-Agent Architecture (TASK-03)."""

import os
from datetime import datetime, timedelta
import pytest

from src.agents.shared.circuit_breaker import CircuitBreaker
from src.agents.shared.risk_gatekeeper import create_risk_gatekeeper
from src.agents.smc.htf_bias_agent import create_htf_bias_agent
from src.agents.smc.poi_agent import create_poi_agent
from src.agents.smc.sizer_agent import create_sizer_agent
from src.agents.smc.smc_orchestrator import create_smc_orchestrator
from src.agents.smc.structure_agent import create_structure_agent
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


def test_agent_hierarchy_and_sub_agents():
    """Verify ADK sub_agents hierarchy tree of SMC Orchestrator."""
    orchestrator = create_smc_orchestrator()
    assert orchestrator.name == "smc_orchestrator"
    assert len(orchestrator.sub_agents) == 5

    sub_names = [sub.name for sub in orchestrator.sub_agents]
    assert sub_names == [
        "htf_bias_agent",
        "structure_agent",
        "poi_agent",
        "sizer_agent",
        "risk_gatekeeper",
    ]


def test_output_schema_and_keys():
    """Verify output_schema and output_key integrity on each agent."""
    htf = create_htf_bias_agent()
    struct = create_structure_agent()
    poi = create_poi_agent()
    sizer = create_sizer_agent()
    gatekeeper = create_risk_gatekeeper()

    assert htf.output_schema == HTFBias
    assert htf.output_key == STATE_HTF_BIAS

    assert struct.output_schema == MarketStructure
    assert struct.output_key == STATE_MARKET_STRUCTURE

    assert poi.output_schema == POIZone
    assert poi.output_key == STATE_POI_ZONE

    assert sizer.output_schema == SMCSetup
    assert sizer.output_key == STATE_SMC_SETUP

    assert gatekeeper.output_schema == RiskVerdict
    assert gatekeeper.output_key == STATE_RISK_VERDICT


def test_smc_setup_rr_validation():
    """Verify automatic invalidation of trade setups with R:R < 2.0."""
    # Case 1: Compliant setup with R:R >= 2.0
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

    # Case 2: Setup violating R:R < 2.0 -> validator must force is_valid = False
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
        is_valid=True,  # Explicitly passing True to test validation override
    )
    assert invalid_setup.is_valid is False, "Setup with R:R < 2.0 must be forced to is_valid=False"


def test_circuit_breaker_drawdown_halt():
    """Verify Circuit Breaker emergency halt on daily drawdown <= -3%."""
    os.environ["MT5_MOCK"] = "true"
    import src.tools.mt5_tools
    src.tools.mt5_tools._USE_MOCK = True
    cb = CircuitBreaker(initial_daily_balance=10000.0)

    # 1. Normal equity ($9,800 = -2.0% DD) -> No halt
    state1 = cb.check_equity(current_equity=9800.0)
    assert state1.is_active is False
    assert state1.current_daily_drawdown_pct == -2.0

    # 2. Severe equity drop ($9,690 = -3.1% DD) -> TRIGGER EMERGENCY HALT
    state2 = cb.check_equity(current_equity=9690.0)
    assert state2.is_active is True
    assert state2.current_daily_drawdown_pct == -3.1
    assert "Daily Drawdown breach" in state2.halt_reason
    assert state2.cooldown_until is not None


def test_circuit_breaker_consecutive_losses():
    """Verify Circuit Breaker halt after 3 consecutive trade losses."""
    cb = CircuitBreaker(initial_daily_balance=10000.0)
    assert cb.state.consecutive_losses == 0

    cb.record_loss()
    assert cb.state.consecutive_losses == 1
    assert cb.state.is_active is False

    cb.record_loss()
    assert cb.state.consecutive_losses == 2
    assert cb.state.is_active is False

    cb.record_loss()
    assert cb.state.consecutive_losses == 3
    assert cb.state.is_active is True
    assert "3 consecutive losses reached" in cb.state.halt_reason
