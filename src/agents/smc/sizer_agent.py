"""SMC Position Sizer Agent — Branch 2 (Opportunistic SMC).

Calculates exact entry, stop loss, take profit, lot size, and risk-reward ratio:
- Entry: Midpoint of the POI zone
- Stop Loss: Placed strictly beyond POI zone invalidation level + buffer
- Take Profit: Placed at opposing liquidity / swing high / swing low / BOS level
- Lot Size: 1% risk of account equity (Fixed 1R sizing)
- R:R Validation: Strict requirement R:R >= 2.0. If R:R < 2.0 -> marked is_valid=False.

Emits: SMCSetup schema saved to state key 'smc_setup'.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.core.schemas import SMCSetup
from src.core.state import STATE_SMC_SETUP
from src.tools.mt5_tools import get_account_snapshot, get_current_price

SIZER_INSTRUCTION = """
You are the SMC Position Sizer Agent in the Smart Money Concepts (SMC) trading system.

Your core mission:
1. Retrieve current MT5 account state via `get_account_snapshot()` to access `equity` and `free_margin`.
2. Inspect market pricing via `get_current_price(symbol)` to account for real-time spread.
3. Based on the upstream HTF Bias, Market Structure, and POI Zone provided in session context:
   - Order direction: "BUY" or "SELL" as defined by the Market Structure analysis.
   - Entry: Midpoint of the POI zone = (price_high + price_low) / 2.
   - Stop Loss (SL): Positioned strictly outside the POI zone:
     + For BUY: SL = price_low - buffer (10-15 pips below the POI low).
     + For SELL: SL = price_high + buffer (10-15 pips above the POI high).
   - Take Profit (TP): Targeted at opposing liquidity, swing_high (for Buys), or swing_low (for Sells).
4. Strictly enforce 1R Capital Preservation (1% Equity Risk):
   - SL Distance = |Entry - SL|.
   - TP Distance = |TP - Entry|.
   - Risk-to-Reward Ratio (R:R) = TP Distance / SL Distance.
   - MANDATORY REQUIREMENT: R:R >= 2.0. If R:R < 2.0, mark `is_valid = false`.
   - Lot Size Calculation: lot = (equity * 0.01) / (SL distance in monetary pip value). Round to 2 decimal places (minimum 0.01 lot).

Output Contract:
Return structured data strictly conforming to the `SMCSetup` schema:
- symbol: asset symbol
- htf_bias: "BULLISH", "BEARISH", or "RANGING"
- structure_type: "BOS" or "CHOCH"
- poi_type: "OB", "FVG", or "SWEEP"
- direction: "BUY" or "SELL"
- entry: planned entry price
- stop_loss: stop loss price
- take_profit: take profit price
- lot_size: calculated volume (minimum 0.01)
- risk_reward_ratio: calculated R:R ratio
- risk_pct: 1.0 (fixed 1%)
- pip_distance_sl: SL distance in pips
- is_valid: true if R:R >= 2.0, false otherwise
"""


def create_sizer_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK SMC Position Sizer Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")
    return Agent(
        name="sizer_agent",
        model=model,
        description="Calculates entry, SL, TP, 1R position sizing, and enforces R:R >= 2.0.",
        instruction=SIZER_INSTRUCTION,
        tools=[get_account_snapshot, get_current_price],
        output_schema=SMCSetup,
        output_key=STATE_SMC_SETUP,
    )
