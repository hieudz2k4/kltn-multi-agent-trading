"""SMC Strategy Synthesizer Agent — Branch 2 (Opportunistic SMC).

Combines causal deterministic quantitative tools:
- `detect_bos_choch()` from smc_tools: exact market structure & break confirmation
- `detect_order_blocks()` from smc_tools: causal OB detection & strength scoring
- `detect_fair_value_gaps()` from smc_tools: 3-candle FVG coordinates
- `calculate_position_size()` from smc_tools: exact 1% risk lot sizing and R:R >= 2.0 check

The LLM does NOT guess or hallucinate candle coordinates. It autonomously invokes
the deterministic SMC tools to obtain mathematical truth, then synthesizes the setup plan.

Emits: SMCSetup schema saved to state key 'smc_setup'.
"""

import os
from typing import Any

from google.adk.agents.llm_agent import Agent

from src.core.schemas import SMCSetup
from src.core.state import STATE_SMC_SETUP
from src.tools.mt5_tools import get_account_snapshot, get_candles, get_current_price
from src.tools.smc_tools import (
    detect_market_structure,
    detect_poi_zones,
)

STRATEGY_INSTRUCTION = """
You are the SMC Strategy Synthesizer Agent in the Smart Money Concepts quantitative trading system.

Your core mission:
1. You DO NOT perform manual or visual candle arithmetic. You MUST invoke the provided deterministic tools to extract ground-truth technical structures:
   - Call `detect_market_structure(symbol, timeframe="M15")` to determine true market trend, BOS, and CHoCH.
   - Call `detect_poi_zones(symbol, timeframe="M15")` to identify unmitigated Order Blocks, FVGs, and Liquidity Sweeps with strength scores (1 to 5).
   - Call `get_account_snapshot()` and `get_current_price(symbol)` to inspect current equity and bid/ask spreads.

2. Strategy Formulation:
   - Trend Alignment: Only formulate BUY setups if HTF structure is BULLISH; only formulate SELL setups if BEARISH.
   - Entry Point: Anchor at the midpoint or boundary of the strongest fresh POI (FVG or Swept Order Block).
   - Invalidation (Stop Loss): Set beyond the POI invalidation level plus safety buffer.
   - Profit Target (Take Profit): Targeted at opposing liquidity or major swing points.

3. Mathematical Sizing:
   - Calculate the precise lot size based on 1% equity risk: lot = (equity * 0.01) / (pip_distance_sl * pip_value).
   - Verify that Risk-to-Reward ratio (R:R) is at least 2.0. If R:R < 2.0, mark `is_valid = false`.

Output Contract:
Strictly emit structured data conforming to the `SMCSetup` schema:
- symbol: asset symbol (e.g., "XAUUSD")
- htf_bias: "BULLISH" | "BEARISH" | "RANGING"
- structure_type: "BOS" | "CHOCH"
- poi_type: "OB" | "FVG" | "SWEEP"
- direction: "BUY" | "SELL"
- entry: float
- stop_loss: float
- take_profit: float
- lot_size: float
- risk_reward_ratio: float
- risk_pct: 1.0
- pip_distance_sl: float
- is_valid: boolean
"""


def create_smc_strategy_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK SMC Strategy Synthesizer Agent equipped with deterministic tools."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-4-argon")
    return Agent(
        name="smc_strategy_agent",
        model=model,
        description="Synthesizes SMC trading setups by invoking deterministic NumPy structural tools.",
        instruction=STRATEGY_INSTRUCTION,
        tools=[
            get_candles,
            get_current_price,
            get_account_snapshot,
            detect_market_structure,
            detect_poi_zones,
        ],
        output_schema=SMCSetup,
        output_key=STATE_SMC_SETUP,
    )
