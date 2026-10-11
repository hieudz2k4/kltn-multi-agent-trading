"""MT5 ADK Tool Functions — production tool interfaces for MetaTrader 5.

All functions are plain callables compatible with Google ADK tool specifications.
Mock mode is delegated cleanly to MockMT5Provider when MT5_MOCK=true.
"""

import os
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from src.core.schemas import OrderExecutionIntent
from src.tools.mock_providers import MockMT5Provider

_USE_MOCK = os.getenv("MT5_MOCK", "false").lower() == "true"
_TF_MAP = {"M1": 1, "M5": 5, "M15": 15, "H1": 16385, "H4": 16388, "D1": 16408}


def get_account_snapshot() -> dict[str, Any]:
    """Get current MT5 account snapshot (balance, equity, free margin, exposure)."""
    if _USE_MOCK:
        return MockMT5Provider.get_account_snapshot()

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        info = mt5.account_info()
        positions = mt5.positions_get() or []
        long_lots = sum(p.volume for p in positions if p.type == 0)
        short_lots = sum(p.volume for p in positions if p.type == 1)
        total_lots = long_lots + short_lots
        net_exp = abs(long_lots - short_lots) / total_lots if total_lots > 0 else 0.0
        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin": info.margin,
            "free_margin": info.margin_free,
            "profit": info.profit,
            "positions_count": len(positions),
            "net_exposure_pct": round(net_exp, 4),
        }


def get_candles(symbol: str, timeframe: str = "M15", count: int = 50) -> list[dict[str, Any]]:
    """Fetch OHLCV candlestick data from MT5."""
    if _USE_MOCK:
        return MockMT5Provider.get_candles(symbol=symbol, count=count)

    tf_id = _TF_MAP.get(timeframe.upper(), 15)
    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        bars = mt5.copy_rates_from_pos(symbol, tf_id, 0, count) or []
        return [
            {
                "time": datetime.fromtimestamp(b[0], tz=UTC).isoformat(),
                "open": float(b[1]),
                "high": float(b[2]),
                "low": float(b[3]),
                "close": float(b[4]),
                "tick_volume": int(b[5]),
            }
            for b in bars
        ]


def get_current_price(symbol: str) -> dict[str, Any]:
    """Get current bid/ask prices and spread for a symbol."""
    if _USE_MOCK:
        return MockMT5Provider.get_current_price(symbol=symbol)

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        spread_points = tick.ask - tick.bid
        spread_pips = spread_points / (10 ** -(info.digits - 1)) if info.digits > 0 else spread_points
        return {
            "symbol": symbol,
            "bid": round(tick.bid, info.digits),
            "ask": round(tick.ask, info.digits),
            "spread_pips": round(spread_pips, 1),
            "spread_points": round(spread_points, info.digits),
        }


def get_swap_rate(symbol: str, direction: str) -> dict[str, Any]:
    """Get overnight swap rate for a symbol by trading direction."""
    if _USE_MOCK:
        return MockMT5Provider.get_swap_rate(symbol=symbol, direction=direction)

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        info = mt5.symbol_info(symbol)
        swap = info.swap_long if direction.upper() == "BUY" else info.swap_short
        return {
            "symbol": symbol,
            "direction": direction,
            "swap_per_lot": round(swap, 4),
            "currency": info.currency_profit,
        }


def get_average_spread(symbol: str, bars: int = 50) -> dict[str, Any]:
    """Calculate average spread based on recent tick data."""
    if _USE_MOCK:
        return MockMT5Provider.get_average_spread(symbol=symbol)

    current = get_current_price(symbol)
    return {
        "symbol": symbol,
        "avg_spread_pips": current["spread_pips"],
        "current_spread_pips": current["spread_pips"],
        "ratio": 1.0,
    }


def place_market_order(
    symbol: str = "",
    direction: str = "BUY",
    volume: float = 0.01,
    sl: float = 0.0,
    tp: float = 0.0,
    comment: str = "",
    magic_number: int = 2001,
    intent: OrderExecutionIntent | None = None,
) -> dict[str, Any]:
    """Place a market order on MT5 with SL and TP.

    Accepts an OrderExecutionIntent DTO or individual parameter arguments from ADK tool calls.
    """
    if intent:
        symbol = intent.symbol
        direction = intent.action.value if hasattr(intent.action, "value") else str(intent.action)
        volume = intent.volume
        sl = intent.sl
        tp = intent.tp
        comment = intent.comment
        magic_number = intent.magic_number

    if _USE_MOCK:
        return MockMT5Provider.place_market_order(
            symbol=symbol,
            direction=direction,
            volume=volume,
            sl=sl,
            tp=tp,
            comment=comment,
            magic_number=magic_number,
        )

    import MetaTrader5 as mt5_lib

    from src.bridges.mt5_bridge import get_mt5_connection

    order_type = mt5_lib.ORDER_TYPE_BUY if direction.upper() == "BUY" else mt5_lib.ORDER_TYPE_SELL
    with get_mt5_connection() as mt5:
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if direction.upper() == "BUY" else tick.bid
        request = {
            "action": mt5_lib.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": magic_number,
            "comment": comment,
            "type_time": mt5_lib.ORDER_TIME_GTC,
            "type_filling": mt5_lib.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return {
            "success": result.retcode == mt5_lib.TRADE_RETCODE_DONE,
            "ticket": result.order,
            "retcode": result.retcode,
            "comment": result.comment,
            "volume": result.volume,
            "price": result.price,
        }


def modify_position_sl(ticket: int, new_sl: float) -> dict[str, Any]:
    """Modify Stop Loss of an open position (used for breakeven or trailing stop)."""
    if _USE_MOCK:
        return MockMT5Provider.modify_position_sl(ticket=ticket, new_sl=new_sl)

    import MetaTrader5 as mt5_lib

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        positions = mt5.positions_get(ticket=ticket) or []
        if not positions:
            return {"success": False, "ticket": ticket, "error": "Position not found"}
        pos = positions[0]
        request = {
            "action": mt5_lib.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": pos.symbol,
            "sl": new_sl,
            "tp": pos.tp,
        }
        result = mt5.order_send(request)
        return {
            "success": result.retcode == mt5_lib.TRADE_RETCODE_DONE,
            "ticket": ticket,
            "new_sl": new_sl,
            "retcode": result.retcode,
        }


def close_position(ticket: int) -> dict[str, Any]:
    """Close a specific open position by ticket."""
    if _USE_MOCK:
        return MockMT5Provider.close_position(ticket=ticket)

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        positions = mt5.positions_get(ticket=ticket) or []
        if not positions:
            return {"success": False, "ticket": ticket, "retcode": -1}
        pos = positions[0]
        close_type = 1 if pos.type == 0 else 0
        tick = mt5.symbol_info_tick(pos.symbol)
        price = tick.bid if close_type == 1 else tick.ask
        request = {
            "action": 1,
            "position": ticket,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "price": price,
        }
        result = mt5.order_send(request)
        return {"success": result.retcode == 10009, "ticket": ticket, "retcode": result.retcode}


def close_all_positions() -> dict[str, Any]:
    """Close all open positions — triggered by Circuit Breaker emergency shutdown."""
    if _USE_MOCK:
        return MockMT5Provider.close_all_positions()

    from src.bridges.mt5_bridge import get_mt5_connection

    with get_mt5_connection() as mt5:
        positions = mt5.positions_get() or []
        closed, failed, tickets = 0, 0, []
        for pos in positions:
            result = close_position(pos.ticket)
            if result["success"]:
                closed += 1
                tickets.append(pos.ticket)
            else:
                failed += 1
        logger.warning(f"Circuit Breaker: closed {closed} positions, {failed} failed")
        return {"closed_count": closed, "failed_count": failed, "tickets": tickets}
