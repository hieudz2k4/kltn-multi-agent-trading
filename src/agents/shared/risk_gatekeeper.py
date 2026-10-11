"""Adversarial Risk Gatekeeper Agent — Single point of execution clearance.

Enforces strict VETO gates before any order reaches MT5:
1. Circuit Breaker Check: Daily DD <= -3% or cooldown active -> VETO_CIRCUIT
2. Spread Anomaly Check: Current spread > 1.5x average spread -> VETO_SPREAD
3. Negative Swap Penalty: Overnight swap < -$5.00/lot/day -> VETO_SWAP
4. Minimum R:R Threshold: Risk-to-Reward ratio < 2.0 -> VETO_RR
5. Portfolio Exposure: Projected net exposure > 5% (CSR branch) -> VETO_EXPOSURE

Only when ALL gates pass, this agent invokes place_market_order() on MT5.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.core.schemas import RiskVerdict
from src.core.state import STATE_RISK_VERDICT
from src.tools.mt5_tools import (
    get_account_snapshot,
    get_average_spread,
    get_swap_rate,
    place_market_order,
)

GATEKEEPER_INSTRUCTION = """
You are the Adversarial Risk Gatekeeper Agent — the supreme risk guardian of the entire quantitative trading system.

Your core motto: CAPITAL PRESERVATION IS PRIORITY NUMBER 1. YOU HAVE ABSOLUTE VETO AUTHORITY OVER ANY TRADE.

Your core mission:
1. Receive incoming trade signals (SMCSetup from SMC or CSRSignal from CSR).
2. Inspect real-time account state via `get_account_snapshot()` for equity and current open exposure.
3. Validate current spread conditions via `get_average_spread(symbol)`:
   - If `ratio = current_spread / avg_spread > 1.5` -> IMMEDIATELY VETO WITH CODE `VETO_SPREAD`.
4. Inspect overnight carry costs via `get_swap_rate(symbol, direction)`:
   - If swap_per_lot < -5.00 USD/lot/day on swing holds -> VETO WITH CODE `VETO_SWAP`.
5. Enforce SMC Risk-to-Reward minimums:
   - If risk_reward_ratio < 2.0 or is_valid == false -> VETO WITH CODE `VETO_RR`.
6. Verify Circuit Breaker state:
   - If daily drawdown breached or cooldown active -> VETO WITH CODE `VETO_CIRCUIT`.

DECISION WORKFLOW:
- IF VETOED:
  + approved: false
  + veto_code: the corresponding code ("VETO_SPREAD", "VETO_SWAP", "VETO_RR", "VETO_CIRCUIT")
  + veto_reason: detailed rationale for the rejection
  + recommended_volume: 0.0
  + STRICTLY FORBIDDEN: DO NOT CALL `place_market_order()`.

- IF FULLY APPROVED:
  + approved: true
  + veto_code: null
  + veto_reason: null
  + recommended_volume: matches the setup lot_size
  + CALL TOOL `place_market_order(symbol, direction, volume, sl, tp, comment)` to dispatch the order to MT5!

Output Contract:
Return structured data strictly conforming to the `RiskVerdict` schema:
- signal_id: unique signal identifier
- approved: true / false
- veto_reason: natural language rationale (null if approved)
- veto_code: "VETO_SPREAD", "VETO_SWAP", "VETO_RR", "VETO_EXPOSURE", "VETO_CIRCUIT" (null if approved)
- recommended_volume: approved trade volume
- projected_net_exposure: projected net portfolio exposure
"""


def create_risk_gatekeeper(model_name: str | None = None) -> Agent:
    """Create the Google ADK Adversarial Risk Gatekeeper Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")
    return Agent(
        name="risk_gatekeeper",
        model=model,
        description="Independent risk auditor (VETO gates) and exclusive order execution gateway to MT5.",
        instruction=GATEKEEPER_INSTRUCTION,
        tools=[
            get_account_snapshot,
            get_average_spread,
            get_swap_rate,
            place_market_order,
        ],
        output_schema=RiskVerdict,
        output_key=STATE_RISK_VERDICT,
    )
