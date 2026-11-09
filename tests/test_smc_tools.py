"""Unit tests for SMC Causal Quantitative Tools."""

import pytest
from src.tools.smc_tools import (
    compute_swings_causal,
    detect_market_structure,
    detect_poi_zones,
)
from src.core.schemas import MarketStructure, POIZone, StructureType, OrderDirection


def test_compute_swings_causal_no_lookahead():
    """Verify swings causal produces valid swing points without negative shifts."""
    import numpy as np

    # Synthetic triangular wave: 10, 12, 14, 16, 18, 20 (high), 18, 16, 14, 12, 10 (low), 12, 14
    highs = np.array([10, 12, 14, 16, 18, 20, 18, 16, 14, 12, 11, 13, 15, 17, 19], dtype=float)
    lows = highs - 1.0

    swings, levels, high_indices, low_indices = compute_swings_causal(
        highs, lows, lookback=3, confirm_bars=2
    )

    # Candidate bar 5 (val 20) should be confirmed as high
    assert 5 in high_indices
    assert levels[5] == 20.0
    assert swings[5] == 1


def test_detect_market_structure_schema_conformance():
    """Verify detect_market_structure output validates against MarketStructure schema."""
    result = detect_market_structure("XAUUSD", "M15", count=30)
    assert isinstance(result, dict)
    ms = MarketStructure(**result)
    assert ms.symbol == "XAUUSD"
    assert ms.structure_type in (StructureType.BOS, StructureType.CHOCH)
    assert ms.entry_direction in (OrderDirection.BUY, OrderDirection.SELL)
    assert ms.swing_high >= ms.swing_low


def test_detect_poi_zones_schema_conformance():
    """Verify detect_poi_zones output validates against POIZone schema."""
    zones = detect_poi_zones("XAUUSD", "M15", count=30)
    assert isinstance(zones, list)
    assert len(zones) > 0
    top_zone = POIZone(**zones[0])
    assert top_zone.symbol == "XAUUSD"
    assert 1 <= top_zone.strength <= 5
    assert top_zone.price_high >= top_zone.price_low

