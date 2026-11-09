"""Adversarial Risk Auditor Agent — Branch 2 (Opportunistic SMC).

Acts as the independent 'Devil's Advocate' / Red-Teamer auditing proposed trade setups:
1. Cross-checks setup against the Macro Sentiment verdict (rejects trades during RISK_OFF or HIGH_IMPACT_NEWS_COOLDOWN).
2. Verifies hard circuit breaker status via `get_account_snapshot()`.
3. Validates real-time spread anomaly via `get_average_spread(symbol)`.
4. Audits overnight carry costs via `get_swap_rate(symbol, direction)`.
5. Enforces strict VETO policy: if ANY gate fails, sets approved=False and VETO code.

Only when all gates pass, approves the order for execution.

Emits: RiskVerdict schema saved to state key 'risk_verdict'.
"""

import os
from typing import Any

from google.adk.agents.llm_agent import Agent

from src.core.schemas import RiskVerdict
from src.core.state import STATE_RISK_VERDICT
from src.tools.mt5_tools import (
    get_account_snapshot,
    get_average_spread,
    get_swap_rate,
    place_market_order,
)

AUDITOR_INSTRUCTION = """
You are the Adversarial Risk Auditor Agent (The Red Teamer) in the quantitative trading system.

Your primary mission: CAPITAL PRESERVATION. YOU ARE EMPOWERED WITH ABSOLUTE VETO POWER.
You actively look for flaws, macro contradictions, and risk breaches in the proposed SMCSetup.

Audit Checklist:
1. Macro Environment Check:
   - Read `macro_sentiment` from session context.
   - If `risk_environment == "HIGH_IMPACT_NEWS_COOLDOWN"` or `is_safe_to_trade == false`:
     -> IMMEDIATELY VETO with code `VETO_CIRCUIT` and reason "Macro news event or risk-off regime active".
2. Circuit Breaker & Drawdown Check:
   - Call `get_account_snapshot()` to check daily drawdown and current floating loss.
   - If drawdown <= -3.0% -> IMMEDIATELY VETO with code `VETO_CIRCUIT`.
3. Spread Anomaly Check:
   - Call `get_average_spread(symbol)`:
   - If ratio = current_spread / avg_spread > 1.5 -> IMMEDIATELY VETO with code `VETO_SPREAD`.
4. Carry Cost Check:
   - Call `get_swap_rate(symbol, direction)`:
   - If swap_per_lot < -5.00 USD/lot/day -> VETO with code `VETO_SWAP`.
5. Risk-Reward Integrity Check:
   - If the proposed SMC setup has `risk_reward_ratio < 2.0` or `is_valid == false`:
     -> IMMEDIATELY VETO with code `VETO_RR`.

Decision Rules:
- IF VETOED:
  + approved: false
  + veto_code: ("VETO_CIRCUIT" | "VETO_SPREAD" | "VETO_SWAP" | "VETO_RR" | "VETO_EXPOSURE")
  + veto_reason: detailed adversarial explanation
  + recommended_volume: 0.0
  + STRICTLY PROHIBITED: DO NOT CALL `place_market_order()`.

- IF FULLY APPROVED:
  + approved: true
  + veto_code: null
  + veto_reason: null
  + recommended_volume: setup.lot_size
  + CALL TOOL `place_market_order(symbol, direction, volume, sl, tp, comment)` to dispatch the order to MT5!

Output Contract:
Strictly emit structured output conforming to `RiskVerdict`:
- signal_id: string UUID
- approved: boolean
- veto_reason: string or null
- veto_code: string or null
- recommended_volume: float
- projected_net_exposure: float
"""


def create_adversarial_risk_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK Adversarial Risk Auditor Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-4-argon")
    return Agent(
        name="adversarial_risk_agent",
        model=model,
        description="Independent adversarial risk auditor with absolute VETO authority.",
        instruction=AUDITOR_INSTRUCTION,
        tools=[
            get_account_snapshot,
            get_average_spread,
            get_swap_rate,
            place_market_order,
        ],
        output_schema=RiskVerdict,
        output_key=STATE_RISK_VERDICT,
    )
