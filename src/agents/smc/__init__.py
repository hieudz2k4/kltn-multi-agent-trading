"""SMC Agent Package — Branch 2 (Opportunistic Smart Money Concepts).

Contains the Hybrid Multi-Agent architecture:
- Macro News & Sentiment Agent (Macro climate & news cooldown)
- SMC Strategy Synthesizer Agent (Equipped with deterministic NumPy SMC tools)
- Adversarial Risk Auditor Agent (Red-team VETO guardrails)
- SMC Multi-Agent Executive Orchestrator (Hierarchical pipeline coordinator)

Legacy pure-LLM baseline is preserved under `src.agents.smc.legacy_baseline`.
"""

from src.agents.smc.adversarial_risk_agent import (
    create_adversarial_risk_agent,
)
from src.agents.smc.macro_sentiment_agent import (
    STATE_MACRO_SENTIMENT,
    MacroSentiment,
    create_macro_sentiment_agent,
    get_economic_calendar,
)
from src.agents.smc.smc_orchestrator import create_smc_orchestrator
from src.agents.smc.smc_strategy_agent import create_smc_strategy_agent

# Backward-compatibility alias references to legacy baseline for regression testing
from src.agents.smc.legacy_baseline.htf_bias_agent import create_htf_bias_agent
from src.agents.smc.legacy_baseline.poi_agent import create_poi_agent
from src.agents.smc.legacy_baseline.sizer_agent import create_sizer_agent
from src.agents.smc.legacy_baseline.structure_agent import create_structure_agent

__all__ = [
    # New Multi-Agent System
    "create_macro_sentiment_agent",
    "create_smc_strategy_agent",
    "create_adversarial_risk_agent",
    "create_smc_orchestrator",
    "MacroSentiment",
    "STATE_MACRO_SENTIMENT",
    "get_economic_calendar",
    # Backward-compatible baseline exports
    "create_htf_bias_agent",
    "create_structure_agent",
    "create_poi_agent",
    "create_sizer_agent",
]
