"""ADK Session State Keys — shared constants for all agents.

All agents read/write to the ADK session state using these keys to avoid
string typos and ensure a single source of truth for state management.
"""

from typing import Final

# HTF Bias Analyzer output
STATE_HTF_BIAS: Final[str] = "htf_bias"                  # HTFBias model (JSON dict)

# Market Structure Agent output
STATE_MARKET_STRUCTURE: Final[str] = "market_structure"  # MarketStructure model (JSON dict)

# POI & Liquidity Detector output
STATE_POI_ZONE: Final[str] = "poi_zone"                  # POIZone model (JSON dict)

# SMC Position Sizer output
STATE_SMC_SETUP: Final[str] = "smc_setup"                # SMCSetup model (JSON dict)

# CSR Portfolio output
STATE_CSR_SIGNAL: Final[str] = "csr_signal"              # CSRSignal model (JSON dict)

# Risk Gatekeeper output
STATE_RISK_VERDICT: Final[str] = "risk_verdict"          # RiskVerdict model (JSON dict)
STATE_EXECUTION_INTENT: Final[str] = "execution_intent"  # OrderExecutionIntent model (JSON dict)

# Circuit Breaker (global, persisted across agents)
STATE_CIRCUIT_BREAKER: Final[str] = "circuit_breaker"    # CircuitBreakerState model (JSON dict)

# Account snapshot (refreshed each cycle)
STATE_ACCOUNT: Final[str] = "account_snapshot"           # MT5AccountSnapshot model (JSON dict)

# System metadata
STATE_SYMBOL: Final[str] = "symbol"                      # str: active symbol being processed
STATE_MODE: Final[str] = "system_mode"                   # SystemMode enum value: A | B | C
STATE_CYCLE_ID: Final[str] = "cycle_id"                  # str: UUID for current execution cycle
