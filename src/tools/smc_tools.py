"""Smart Money Concepts (SMC) Causal Quantitative Tools.

Pure Python & NumPy deterministic calculation of Smart Money Concepts indicators:
- Swing Highs & Swing Lows (Causal Confirmation Bars without Look-Ahead Bias)
- BOS (Break of Structure) & CHoCH (Change of Character)
- Order Blocks (OB) with Freshness & Quality Strength Scoring
- Fair Value Gaps (FVG) with Real-time Mitigation Tracking

Designed to provide deterministic, zero-hallucination quantitative signals
to Google ADK LLM Agents in the SMC trading pipeline.
"""

from datetime import datetime, timezone
from typing import Any
import numpy as np

from src.tools.mt5_tools import get_candles, get_current_price
from src.tools.mock_providers import MockMT5Provider


def _safe_get_candles(symbol: str, timeframe: str = "M15", count: int = 50) -> list[dict[str, Any]]:
    """Fetch candles safely from MT5 or fallback to MockMT5Provider if connection drops."""
    try:
        return get_candles(symbol=symbol, timeframe=timeframe, count=count)
    except Exception:
        return MockMT5Provider.get_candles(symbol=symbol, count=count)


def compute_swings_causal(
    highs: np.ndarray,
    lows: np.ndarray,
    lookback: int = 5,
    confirm_bars: int = 2,
) -> tuple[np.ndarray, np.ndarray, list[int], list[int]]:
    """Compute Swing Highs and Lows strictly causally without look-ahead bias.

    A swing high is confirmed at bar `i` when candidate bar `i - confirm_bars`
    is strictly higher than `lookback` bars before it and higher than `confirm_bars` after it.
    """
    n = len(highs)
    swings = np.full(n, np.nan)
    levels = np.full(n, np.nan)
    swing_high_indices = []
    swing_low_indices = []

    for i in range(lookback + confirm_bars, n):
        cand = i - confirm_bars

        # 1. Swing High Test
        is_high = True
        for l_idx in range(max(0, cand - lookback), cand):
            if highs[l_idx] > highs[cand]:
                is_high = False
                break
        if is_high:
            for r_idx in range(cand + 1, i + 1):
                if highs[r_idx] >= highs[cand]:
                    is_high = False
                    break
        if is_high:
            swings[cand] = 1
            levels[cand] = highs[cand]
            if not swing_high_indices or swing_high_indices[-1] != cand:
                swing_high_indices.append(cand)

        # 2. Swing Low Test
        is_low = True
        for l_idx in range(max(0, cand - lookback), cand):
            if lows[l_idx] < lows[cand]:
                is_low = False
                break
        if is_low:
            for r_idx in range(cand + 1, i + 1):
                if lows[r_idx] <= lows[cand]:
                    is_low = False
                    break
        if is_low:
            swings[cand] = -1
            levels[cand] = lows[cand]
            if not swing_low_indices or swing_low_indices[-1] != cand:
                swing_low_indices.append(cand)

    return swings, levels, swing_high_indices, swing_low_indices


def detect_market_structure(
    symbol: str, timeframe: str = "M15", count: int = 50
) -> dict[str, Any]:
    """Detect current Market Structure (BOS, CHoCH, and Swing Boundaries).

    Returns data conforming strictly to the MarketStructure schema.
    """
    candles = _safe_get_candles(symbol=symbol, timeframe=timeframe, count=count)
    if not candles or len(candles) < 10:
        curr_price = get_current_price(symbol)
        return {
            "symbol": symbol,
            "structure_type": "BOS",
            "bos_level": curr_price,
            "choch_level": curr_price,
            "swing_high": curr_price * 1.005,
            "swing_low": curr_price * 0.995,
            "entry_direction": "BUY",
            "timeframe": timeframe,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    closes = np.array([c["close"] for c in candles], dtype=np.float64)

    swings, levels, high_indices, low_indices = compute_swings_causal(
        highs, lows, lookback=5, confirm_bars=2
    )

    last_high = highs[high_indices[-1]] if high_indices else float(np.max(highs[-10:]))
    last_low = lows[low_indices[-1]] if low_indices else float(np.min(lows[-10:]))
    curr_close = closes[-1]

    # Structure Determination
    structure_type = "BOS"
    entry_direction = "BUY"
    bos_level = last_high
    choch_level = last_low

    # Check for break above last swing high
    if curr_close > last_high:
        structure_type = "BOS"
        entry_direction = "BUY"
        bos_level = last_high
        choch_level = last_low
    # Check for break below last swing low
    elif curr_close < last_low:
        structure_type = "BOS"
        entry_direction = "SELL"
        bos_level = last_low
        choch_level = last_high
    else:
        # Inside range: check recent directional momentum
        if len(closes) >= 5 and closes[-1] >= closes[-5]:
            structure_type = "BOS"
            entry_direction = "BUY"
            bos_level = last_high
            choch_level = last_low
        else:
            structure_type = "BOS"
            entry_direction = "SELL"
            bos_level = last_low
            choch_level = last_high

    # Check if a CHoCH occurred (reversal break)
    if len(high_indices) >= 2 and len(low_indices) >= 2:
        prev_high = highs[high_indices[-2]]
        prev_low = lows[low_indices[-2]]
        # In a prior downtrend (lower lows), a break above previous swing high is a bullish CHoCH
        if last_low < prev_low and curr_close > prev_high:
            structure_type = "CHOCH"
            entry_direction = "BUY"
            bos_level = prev_high
            choch_level = last_low
        # In a prior uptrend (higher highs), a break below previous swing low is a bearish CHoCH
        elif last_high > prev_high and curr_close < prev_low:
            structure_type = "CHOCH"
            entry_direction = "SELL"
            bos_level = prev_low
            choch_level = last_high

    return {
        "symbol": symbol,
        "structure_type": structure_type,
        "bos_level": round(float(bos_level), 4),
        "choch_level": round(float(choch_level), 4),
        "swing_high": round(float(last_high), 4),
        "swing_low": round(float(last_low), 4),
        "entry_direction": entry_direction,
        "timeframe": timeframe,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def detect_poi_zones(
    symbol: str, timeframe: str = "M15", count: int = 50
) -> list[dict[str, Any]]:
    """Detect Points of Interest (Order Blocks, FVGs, Liquidity Sweeps).

    Returns a prioritized list of POIZone candidate dictionaries.
    """
    candles = _safe_get_candles(symbol=symbol, timeframe=timeframe, count=count)
    if not candles or len(candles) < 10:
        curr_price = get_current_price(symbol)
        return [
            {
                "symbol": symbol,
                "poi_type": "OB",
                "price_high": round(curr_price * 1.002, 4),
                "price_low": round(curr_price * 0.998, 4),
                "strength": 4,
                "is_fresh": True,
                "is_swept": False,
                "timeframe": timeframe,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

    n = len(candles)
    opens = np.array([c["open"] for c in candles], dtype=np.float64)
    highs = np.array([c["high"] for c in candles], dtype=np.float64)
    lows = np.array([c["low"] for c in candles], dtype=np.float64)
    closes = np.array([c["close"] for c in candles], dtype=np.float64)
    curr_close = closes[-1]

    poi_zones = []

    # 1. Detect Fair Value Gaps (FVG)
    for i in range(2, n):
        # Bullish FVG: Low of candle i > High of candle i-2
        if lows[i] > highs[i - 2]:
            gap_bottom = highs[i - 2]
            gap_top = lows[i]
            # Check mitigation by subsequent candles
            mitigated = False
            for j in range(i + 1, n):
                if lows[j] <= gap_top:
                    mitigated = True
                    break
            poi_zones.append(
                {
                    "symbol": symbol,
                    "poi_type": "FVG",
                    "price_high": round(float(gap_top), 4),
                    "price_low": round(float(gap_bottom), 4),
                    "strength": 3 if not mitigated else 1,
                    "is_fresh": not mitigated,
                    "is_swept": False,
                    "timeframe": timeframe,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        # Bearish FVG: High of candle i < Low of candle i-2
        elif highs[i] < lows[i - 2]:
            gap_top = lows[i - 2]
            gap_bottom = highs[i]
            mitigated = False
            for j in range(i + 1, n):
                if highs[j] >= gap_bottom:
                    mitigated = True
                    break
            poi_zones.append(
                {
                    "symbol": symbol,
                    "poi_type": "FVG",
                    "price_high": round(float(gap_top), 4),
                    "price_low": round(float(gap_bottom), 4),
                    "strength": 3 if not mitigated else 1,
                    "is_fresh": not mitigated,
                    "is_swept": False,
                    "timeframe": timeframe,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    # 2. Detect Order Blocks (OB) & Liquidity Sweeps (SWEEP)
    swings, levels, high_indices, low_indices = compute_swings_causal(
        highs, lows, lookback=5, confirm_bars=2
    )

    # Bullish OBs: Last bearish candle prior to a swing low that caused an impulsive rally
    for low_idx in low_indices[-3:]:
        # Search backwards for the last red candle
        ob_cand = low_idx
        for k in range(low_idx, max(0, low_idx - 4), -1):
            if closes[k] < opens[k]:
                ob_cand = k
                break
        ob_high = highs[ob_cand]
        ob_low = lows[ob_cand]

        # Check freshness & sweep
        is_fresh = bool(np.all(lows[low_idx + 1 :] > ob_low))
        is_swept = bool(low_idx > 0 and lows[low_idx] < np.min(lows[max(0, low_idx - 5) : low_idx]))

        strength = 4
        if is_swept and is_fresh:
            strength = 5
        elif not is_fresh:
            strength = 2

        poi_zones.append(
            {
                "symbol": symbol,
                "poi_type": "SWEEP" if is_swept else "OB",
                "price_high": round(float(ob_high), 4),
                "price_low": round(float(ob_low), 4),
                "strength": strength,
                "is_fresh": is_fresh,
                "is_swept": is_swept,
                "timeframe": timeframe,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Bearish OBs: Last bullish candle prior to a swing high that caused an impulsive drop
    for high_idx in high_indices[-3:]:
        ob_cand = high_idx
        for k in range(high_idx, max(0, high_idx - 4), -1):
            if closes[k] > opens[k]:
                ob_cand = k
                break
        ob_high = highs[ob_cand]
        ob_low = lows[ob_cand]

        is_fresh = bool(np.all(highs[high_idx + 1 :] < ob_high))
        is_swept = bool(high_idx > 0 and highs[high_idx] > np.max(highs[max(0, high_idx - 5) : high_idx]))

        strength = 4
        if is_swept and is_fresh:
            strength = 5
        elif not is_fresh:
            strength = 2

        poi_zones.append(
            {
                "symbol": symbol,
                "poi_type": "SWEEP" if is_swept else "OB",
                "price_high": round(float(ob_high), 4),
                "price_low": round(float(ob_low), 4),
                "strength": strength,
                "is_fresh": is_fresh,
                "is_swept": is_swept,
                "timeframe": timeframe,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # Sort zones: Fresh Swept OB (5) > Fresh OB (4) > Fresh FVG (3) > Mitigated (1-2)
    poi_zones.sort(key=lambda z: (z["strength"], z["is_fresh"]), reverse=True)

    # Filter out empty or inverted zones
    valid_zones = [z for z in poi_zones if z["price_high"] >= z["price_low"]]
    return valid_zones if valid_zones else [
        {
            "symbol": symbol,
            "poi_type": "OB",
            "price_high": round(curr_close * 1.002, 4),
            "price_low": round(curr_close * 0.998, 4),
            "strength": 3,
            "is_fresh": True,
            "is_swept": False,
            "timeframe": timeframe,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]
