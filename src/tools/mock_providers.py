"""Mock Data Providers for MT5 and TradingView.

Separates test fixtures and offline simulation data completely from production
business logic and tool definitions.
"""

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger


class MockMT5Provider:
    """Mock implementation of MT5 market operations and account querying."""

    @staticmethod
    def get_account_snapshot() -> dict[str, Any]:
        return {
            "login": 999999,
            "balance": 10000.0,
            "equity": 9985.0,
            "margin": 125.0,
            "free_margin": 9860.0,
            "profit": -15.0,
            "positions_count": 1,
            "net_exposure_pct": 0.02,
        }

    @staticmethod
    def get_candles(symbol: str, count: int) -> list[dict[str, Any]]:
        base_time = datetime.now(UTC) - timedelta(minutes=15 * count)
        candles = []
        price = 2730.0
        for i in range(count):
            o = price
            h = o + random.uniform(0.5, 3.0)
            l = o - random.uniform(0.5, 3.0)
            c = random.uniform(l, h)
            candles.append({
                "time": (base_time + timedelta(minutes=15 * i)).isoformat(),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "tick_volume": random.randint(100, 1000),
            })
            price = c
        return candles

    @staticmethod
    def get_current_price(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "bid": 2735.50,
            "ask": 2735.80,
            "spread_pips": 3.0,
            "spread_points": 30,
        }

    @staticmethod
    def get_swap_rate(symbol: str, direction: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "direction": direction,
            "swap_per_lot": -2.5 if direction.upper() == "BUY" else -1.8,
            "currency": "USD",
        }

    @staticmethod
    def get_average_spread(symbol: str) -> dict[str, Any]:
        return {
            "symbol": symbol,
            "avg_spread_pips": 2.5,
            "current_spread_pips": 3.0,
            "ratio": 1.2,
        }

    @staticmethod
    def place_market_order(
        symbol: str,
        direction: str,
        volume: float,
        sl: float,
        tp: float,
        comment: str,
        magic_number: int = 2001,
    ) -> dict[str, Any]:
        ticket = int(uuid.uuid4().int % 10**9)
        logger.info(f"[MOCK] place_market_order: {direction} {volume} {symbol} ticket={ticket}")
        return {
            "success": True,
            "ticket": ticket,
            "retcode": 10009,
            "comment": f"Request executed (MOCK: {comment})",
            "volume": volume,
            "price": 2735.50,
        }

    @staticmethod
    def modify_position_sl(ticket: int, new_sl: float) -> dict[str, Any]:
        logger.info(f"[MOCK] modify_position_sl: ticket={ticket} new_sl={new_sl}")
        return {"success": True, "ticket": ticket, "new_sl": new_sl, "retcode": 10009}

    @staticmethod
    def close_position(ticket: int) -> dict[str, Any]:
        logger.info(f"[MOCK] close_position: ticket={ticket}")
        return {"success": True, "ticket": ticket, "retcode": 10009}

    @staticmethod
    def close_all_positions() -> dict[str, Any]:
        logger.warning("[MOCK] close_all_positions: Circuit Breaker triggered!")
        return {"closed_count": 1, "failed_count": 0, "tickets": [123456789]}


class MockTradingViewProvider:
    """Mock implementation of TradingView indicator and chart reading."""

    @staticmethod
    def get_chart_labels(symbol: str) -> list[dict[str, Any]]:
        return [
            {"id": "lbl_1", "text": "BOS", "price": 2740.50, "bar_index": 120, "color": "green", "style": "label_up", "tooltip": "Break of Structure"},
            {"id": "lbl_2", "text": "CHoCH", "price": 2728.00, "bar_index": 95, "color": "red", "style": "label_down", "tooltip": "Change of Character"},
            {"id": "lbl_3", "text": "OB", "price": 2731.50, "bar_index": 88, "color": "blue", "style": "label_center", "tooltip": "Order Block zone 2730.0 - 2733.0"},
            {"id": "lbl_4", "text": "FVG", "price": 2735.00, "bar_index": 105, "color": "purple", "style": "label_center", "tooltip": "Fair Value Gap 2733.5 - 2736.5"},
        ]

    @staticmethod
    def get_chart_boxes(symbol: str) -> list[dict[str, Any]]:
        return [
            {
                "id": "box_1",
                "text": "Bullish OB",
                "top": 2733.00,
                "bottom": 2730.00,
                "left_bar": 85,
                "right_bar": 130,
                "color": "rgba(0,150,255,0.2)",
            },
            {
                "id": "box_2",
                "text": "Bearish FVG",
                "top": 2736.50,
                "bottom": 2733.50,
                "left_bar": 102,
                "right_bar": 130,
                "color": "rgba(255,100,0,0.2)",
            },
        ]

    @staticmethod
    def get_indicator_value(symbol: str, indicator: str) -> dict[str, Any]:
        mock_values = {
            "RSI": 42.5,
            "BB_UPPER": 2745.00,
            "BB_LOWER": 2720.00,
            "BB_MID": 2732.50,
            "EMA_50": 2731.00,
            "EMA_200": 2715.00,
        }
        return {
            "symbol": symbol,
            "indicator": indicator,
            "value": mock_values.get(indicator.upper(), 0.0),
            "timeframe": "M15",
            "timestamp": "2026-10-11T09:00:00",
        }

    @staticmethod
    def get_chart_lines(symbol: str) -> list[dict[str, Any]]:
        return [
            {"id": "line_1", "price": 2750.00, "color": "red", "text": "Resistance", "style": "solid"},
            {"id": "line_2", "price": 2720.00, "color": "green", "text": "Support", "style": "solid"},
            {"id": "line_3", "price": 2735.00, "color": "orange", "text": "Previous High", "style": "dashed"},
        ]
