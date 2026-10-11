"""HTF Bias Analyzer Agent — Branch 2 (Opportunistic SMC).

Analyzes Higher Timeframe (H4 / D1) candles to identify macro trend:
- BULLISH: Consecutive Higher Highs (HH) and Higher Lows (HL)
- BEARISH: Consecutive Lower Highs (LH) and Lower Lows (LL)
- RANGING: Choppy consolidation without clear direction

Emits: HTFBias schema saved to state key 'htf_bias'.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.core.schemas import HTFBias
from src.core.state import STATE_HTF_BIAS
from src.tools.mt5_tools import get_candles, get_current_price

HTF_BIAS_INSTRUCTION = """
You are the Higher Timeframe (HTF) Bias Analyzer Agent in the Smart Money Concepts (SMC) trading system.

Your core mission:
1. Determine the macro trend (H4 and D1) for the requested asset symbol.
2. Call `get_candles(symbol, timeframe="H4", count=50)` to fetch the last 50 H4 candles.
3. If daily trend confirmation is needed, call `get_candles(symbol, timeframe="D1", count=20)`.
4. Call `get_current_price(symbol)` to observe current market pricing and spread.

SMC Market Structure Principles:
- BULLISH: Successive swing points forming Higher Highs (HH) and Higher Lows (HL). Price remains above the most recent major swing low.
- BEARISH: Successive swing points forming Lower Highs (LH) and Lower Lows (LL). Price remains below the most recent major swing high.
- RANGING: Consolidation within a tight range with alternating, non-trending swing points.

Output Contract:
Return structured data strictly conforming to the `HTFBias` schema:
- symbol: asset symbol (e.g., "XAUUSD")
- bias: "BULLISH", "BEARISH", or "RANGING"
- key_level: critical support/resistance level defining the bias
- swing_high: most recent confirmed H4 swing high
- swing_low: most recent confirmed H4 swing low
- reason: concise rationale detailing how the bias was derived
- timeframe: timeframe analyzed (default "H4")
"""


def create_htf_bias_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK HTF Bias Analyzer Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")
    return Agent(
        name="htf_bias_agent",
        model=model,
        description="Analyzes higher timeframe (H4/D1) macro trends using Smart Money Concepts.",
        instruction=HTF_BIAS_INSTRUCTION,
        tools=[get_candles, get_current_price],
        output_schema=HTFBias,
        output_key=STATE_HTF_BIAS,
    )
