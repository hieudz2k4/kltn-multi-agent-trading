from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "sma_cross": {
        "id": "sma_cross",
        "name": "SMA Crossover",
        "description": "Long when a fast simple moving average crosses above a slow average, short on the reverse cross.",
        "spec": {
            "name": "SMA Crossover",
            "timeframe": "1D",
            "indicators": [
                {"id": "fast_sma", "type": "sma", "params": {"length": 20}, "source": "close"},
                {"id": "slow_sma", "type": "sma", "params": {"length": 50}, "source": "close"},
            ],
            "entry_long": [{"left": {"kind": "indicator", "ref": "fast_sma"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "slow_sma"}}],
            "exit_long": [{"left": {"kind": "indicator", "ref": "fast_sma"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "slow_sma"}}],
            "entry_short": [{"left": {"kind": "indicator", "ref": "fast_sma"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "slow_sma"}}],
            "exit_short": [{"left": {"kind": "indicator", "ref": "fast_sma"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "slow_sma"}}],
            "risk": {"stop_pct": 3, "take_pct": 6, "qty_pct": 100},
        },
    },
    "ema_cross": {
        "id": "ema_cross",
        "name": "EMA Crossover",
        "description": "Momentum crossover using fast and slow exponential moving averages.",
        "spec": {
            "name": "EMA Crossover",
            "timeframe": "1D",
            "indicators": [
                {"id": "fast_ema", "type": "ema", "params": {"length": 12}, "source": "close"},
                {"id": "slow_ema", "type": "ema", "params": {"length": 26}, "source": "close"},
            ],
            "entry_long": [{"left": {"kind": "indicator", "ref": "fast_ema"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "slow_ema"}}],
            "exit_long": [{"left": {"kind": "indicator", "ref": "fast_ema"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "slow_ema"}}],
            "entry_short": [{"left": {"kind": "indicator", "ref": "fast_ema"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "slow_ema"}}],
            "exit_short": [{"left": {"kind": "indicator", "ref": "fast_ema"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "slow_ema"}}],
            "risk": {"stop_pct": 2.5, "take_pct": 5, "qty_pct": 100},
        },
    },
    "rsi_reversion": {
        "id": "rsi_reversion",
        "name": "RSI Mean Reversion",
        "description": "Buys when RSI recovers from oversold and shorts when RSI falls from overbought.",
        "spec": {
            "name": "RSI Mean Reversion",
            "timeframe": "1D",
            "indicators": [{"id": "rsi14", "type": "rsi", "params": {"length": 14}, "source": "close"}],
            "entry_long": [{"left": {"kind": "indicator", "ref": "rsi14"}, "op": "cross_above", "right": {"kind": "const", "value": 30}}],
            "exit_long": [{"left": {"kind": "indicator", "ref": "rsi14"}, "op": "cross_above", "right": {"kind": "const", "value": 55}}],
            "entry_short": [{"left": {"kind": "indicator", "ref": "rsi14"}, "op": "cross_below", "right": {"kind": "const", "value": 70}}],
            "exit_short": [{"left": {"kind": "indicator", "ref": "rsi14"}, "op": "cross_below", "right": {"kind": "const", "value": 45}}],
            "risk": {"stop_pct": 4, "take_pct": 4, "qty_pct": 100},
        },
    },
    "macd_signal": {
        "id": "macd_signal",
        "name": "MACD Signal Cross",
        "description": "Trades MACD line crosses against the signal line.",
        "spec": {
            "name": "MACD Signal Cross",
            "timeframe": "1D",
            "indicators": [
                {"id": "macd_line", "type": "macd", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "line"}, "source": "close"},
                {"id": "macd_signal", "type": "macd", "params": {"fast": 12, "slow": 26, "signal": 9, "component": "signal"}, "source": "close"},
            ],
            "entry_long": [{"left": {"kind": "indicator", "ref": "macd_line"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "macd_signal"}}],
            "exit_long": [{"left": {"kind": "indicator", "ref": "macd_line"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "macd_signal"}}],
            "entry_short": [{"left": {"kind": "indicator", "ref": "macd_line"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "macd_signal"}}],
            "exit_short": [{"left": {"kind": "indicator", "ref": "macd_line"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "macd_signal"}}],
            "risk": {"stop_pct": 3, "take_pct": 6, "qty_pct": 100},
        },
    },
    "bollinger_breakout": {
        "id": "bollinger_breakout",
        "name": "Bollinger Breakout",
        "description": "Follows breakouts through the upper or lower Bollinger Band.",
        "spec": {
            "name": "Bollinger Breakout",
            "timeframe": "1D",
            "indicators": [
                {"id": "bb_upper", "type": "bbands", "params": {"length": 20, "mult": 2, "component": "upper"}, "source": "close"},
                {"id": "bb_lower", "type": "bbands", "params": {"length": 20, "mult": 2, "component": "lower"}, "source": "close"},
            ],
            "entry_long": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "bb_upper"}}],
            "exit_long": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "bb_lower"}}],
            "entry_short": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "bb_lower"}}],
            "exit_short": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "bb_upper"}}],
            "risk": {"stop_pct": 4, "take_pct": 8, "qty_pct": 100},
        },
    },
    "donchian_breakout": {
        "id": "donchian_breakout",
        "name": "Donchian Breakout",
        "description": "Buys a 20-period channel breakout and exits on a 10-period opposite channel break.",
        "spec": {
            "name": "Donchian Breakout",
            "timeframe": "1D",
            "indicators": [
                {"id": "high20", "type": "highest", "params": {"length": 20}, "source": "high"},
                {"id": "low20", "type": "lowest", "params": {"length": 20}, "source": "low"},
                {"id": "high10", "type": "highest", "params": {"length": 10}, "source": "high"},
                {"id": "low10", "type": "lowest", "params": {"length": 10}, "source": "low"},
            ],
            "entry_long": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "high20"}}],
            "exit_long": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "low10"}}],
            "entry_short": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_below", "right": {"kind": "indicator", "ref": "low20"}}],
            "exit_short": [{"left": {"kind": "price", "ref": "close"}, "op": "cross_above", "right": {"kind": "indicator", "ref": "high10"}}],
            "risk": {"stop_pct": 5, "take_pct": 10, "qty_pct": 100},
        },
    },
}
