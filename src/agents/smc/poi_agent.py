"""POI & Liquidity Detector Agent — Branch 2 (Opportunistic SMC).

Identifies high-probability Point of Interest (POI) zones and Liquidity Sweeps:
- Order Block (OB): the final opposing candle before an aggressive displacement move breaking structure
- Fair Value Gap (FVG): a 3-candle imbalance gap yet to be mitigated
- Liquidity Sweep (SWEEP): wick sweep above/below previous swing highs/lows followed by aggressive rejection

Priority Ranking: Swept OB (strength 5) > Fresh OB (strength 4) > FVG (strength 3) > Mitigated Zone (strength 1-2).

Emits: POIZone schema saved to state key 'poi_zone'.
"""

import os

from google.adk.agents.llm_agent import Agent

from src.core.schemas import POIZone
from src.core.state import STATE_POI_ZONE
from src.tools.mt5_tools import get_candles, get_current_price
from src.tools.tradingview_tools import get_chart_boxes, get_chart_labels

POI_INSTRUCTION = """
You are the Point of Interest (POI) & Liquidity Detector Agent in the Smart Money Concepts (SMC) trading system.

Your core mission:
1. Locate high-probability institutional liquidity and reaction zones (POI) on M15/H1.
2. Call `get_chart_boxes(symbol)` to inspect Order Blocks and FVGs identified by chart indicators.
3. Call `get_chart_labels(symbol)` to identify liquidity sweeps and structural marks.
4. Call `get_candles(symbol, timeframe="M15", count=30)` and `get_current_price(symbol)` to evaluate if the zone has already been mitigated.

Quality Scoring Rules (Strength 1 to 5):
- Strength 5: Order Block preceded by a clean liquidity sweep (Swept OB) that produced strong displacement.
- Strength 4: Fresh, unmitigated Order Block with clear imbalance leaving the zone.
- Strength 3: Clean Fair Value Gap (FVG) positioned in Discount (for Buys) or Premium (for Sells).
- Strength 2: Partially mitigated OB or FVG.
- Strength 1: Weak, fully mitigated, or distant zone.

Output Contract:
Return structured data strictly conforming to the `POIZone` schema:
- symbol: asset symbol
- poi_type: "OB", "FVG", or "SWEEP"
- price_high: upper boundary of the POI zone
- price_low: lower boundary of the POI zone
- strength: quality score between 1 and 5 (select zones with strength >= 3)
- is_fresh: true if price has not returned to the zone yet
- is_swept: true if the zone involved a liquidity sweep
- timeframe: timeframe analyzed (default "M15")
"""


def create_poi_agent(model_name: str | None = None) -> Agent:
    """Create the Google ADK POI & Liquidity Detector Agent."""
    model = model_name or os.getenv("SMC_LLM_MODEL", "gemini-2.5-flash")
    return Agent(
        name="poi_agent",
        model=model,
        description="Detects and scores Point of Interest zones (Order Blocks, FVGs, Liquidity Sweeps).",
        instruction=POI_INSTRUCTION,
        tools=[get_chart_boxes, get_chart_labels, get_candles, get_current_price],
        output_schema=POIZone,
        output_key=STATE_POI_ZONE,
    )
