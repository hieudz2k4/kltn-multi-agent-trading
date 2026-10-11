"""TradingView ADK Tool Functions — read Pine Script labels, boxes, and indicators.

Production: Read data rendered on TradingView Desktop via Chrome DevTools Protocol (CDP).
Mock mode is delegated cleanly to MockTradingViewProvider when TV_MOCK=true.
"""

import os
from typing import Any

from src.tools.mock_providers import MockTradingViewProvider

_USE_MOCK = os.getenv("TV_MOCK", "false").lower() == "true"


def get_chart_labels(symbol: str) -> list[dict[str, Any]]:
    """Read all Pine Script chart labels currently visible on TradingView (BOS, CHoCH, OB)."""
    if _USE_MOCK:
        return MockTradingViewProvider.get_chart_labels(symbol=symbol)
    raise NotImplementedError("Production CDP JS extraction pending — set TV_MOCK=true")


def get_chart_boxes(symbol: str) -> list[dict[str, Any]]:
    """Read all Pine Script chart boxes currently visible on TradingView (Order Block, FVG)."""
    if _USE_MOCK:
        return MockTradingViewProvider.get_chart_boxes(symbol=symbol)
    raise NotImplementedError("Production CDP JS extraction pending — set TV_MOCK=true")


def get_indicator_value(symbol: str, indicator: str) -> dict[str, Any]:
    """Read technical indicator values from TradingView chart (RSI, Bollinger Bands, EMA)."""
    if _USE_MOCK:
        return MockTradingViewProvider.get_indicator_value(symbol=symbol, indicator=indicator)
    raise NotImplementedError("Production CDP JS extraction pending — set TV_MOCK=true")


def get_chart_lines(symbol: str) -> list[dict[str, Any]]:
    """Read Pine Script horizontal price lines — typically key support/resistance levels."""
    if _USE_MOCK:
        return MockTradingViewProvider.get_chart_lines(symbol=symbol)
    raise NotImplementedError("Production CDP JS extraction pending — set TV_MOCK=true")
