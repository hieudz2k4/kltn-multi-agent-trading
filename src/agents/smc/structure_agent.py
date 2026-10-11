"""Market Structure Agent — Branch 2 (Opportunistic SMC).

Analyzes lower timeframe (M15 / H1) market structure:
- BOS (Break of Structure): price breaking swing high/low in the direction of the trend
- CHoCH (Change of Character): early signal of market structure reversal
- Swing High & Swing Low: current micro range boundaries

Emits: MarketStructure schema saved to state key 'market_structure'.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.core.schemas import MarketStructure
from src.core.state import STATE_MARKET_STRUCTURE
from src.tools.mt5_tools import get_candles, get_current_price
from src.tools.tradingview_tools import get_chart_labels

STRUCTURE_INSTRUCTION = """
You are the Market Structure Agent in the Smart Money Concepts (SMC) trading system.

Your core mission:
1. Identify lower timeframe (M15 and H1) market structure breaks and shifts.
2. Call `get_candles(symbol, timeframe="M15", count=50)` to fetch the last 50 M15 candles.
3. Call `get_chart_labels(symbol)` to read technical structure labels (BOS, CHoCH) rendered on TradingView charts.
4. Call `get_current_price(symbol)` to locate the current price relative to major structural levels.

SMC Structural Rules:
- BOS (Break of Structure): Candle body closes beyond the most recent swing high (in an uptrend) or swing low (in a downtrend). Confirms trend continuation.
- CHoCH (Change of Character): Price breaks the swing high responsible for the lowest low (in a downtrend) or the swing low responsible for the highest high (in an uptrend). Signals an early trend reversal.
- entry_direction: "BUY" if structure is bullish (bullish BOS or bullish CHoCH), "SELL" if bearish.

Output Contract:
Return structured data strictly conforming to the `MarketStructure` schema:
- symbol: asset symbol
- structure_type: "BOS" or "CHOCH"
- bos_level: price level that was broken to establish the BOS/CHoCH
- choch_level: structural invalidation level (optional)
- swing_high: most recent confirmed M15 swing high
- swing_low: most recent confirmed M15 swing low
- entry_direction: "BUY" or "SELL"
- timeframe: structure timeframe (default "M15")
"""


def create_structure_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK Market Structure Analyzer Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")
    return Agent(
        name="structure_agent",
        model=model,
        description="Analyzes M15/H1 market structure (BOS, CHoCH, and Swing Points).",
        instruction=STRUCTURE_INSTRUCTION,
        tools=[get_candles, get_chart_labels, get_current_price],
        output_schema=MarketStructure,
        output_key=STATE_MARKET_STRUCTURE,
    )
