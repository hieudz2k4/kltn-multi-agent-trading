from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _closed(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [trade for trade in trades if trade.get("exit_price") is not None and _to_float(trade.get("pnl")) is not None]


def _stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [_to_float(trade.get("pnl")) or 0.0 for trade in trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    return {
        "trades": len(trades),
        "pnl": sum(pnls),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "expectancy": sum(pnls) / len(trades) if trades else 0.0,
    }


def _holding_days(trade: dict[str, Any]) -> float | None:
    entry = _parse_dt(trade.get("entry_date"))
    exit_ = _parse_dt(trade.get("exit_date"))
    if entry is None or exit_ is None:
        return None
    return max((exit_ - entry).total_seconds() / 86400.0, 0.0)


def _violated_rule(trade: dict[str, Any], rules: list[dict[str, Any]]) -> tuple[dict[str, Any], str] | None:
    setup = str(trade.get("setup") or "")
    emotion = str(trade.get("emotion") or "").lower()
    for rule in rules:
        rule_type = rule.get("type")
        rule_id = str(rule.get("id") or "")
        if rule_type == "avoid_setup" and rule_id == f"avoid_setup:{setup}":
            return rule, f"setup '{setup}' violates {rule_id}"
        if rule_type == "avoid_emotion" and rule_id == f"avoid_emotion:{emotion}":
            return rule, f"emotion '{emotion}' violates {rule_id}"
        if rule_type == "max_holding_days":
            try:
                max_days = float(rule_id.split(":", 1)[1])
            except (IndexError, ValueError):
                max_days = 20.0
            days = _holding_days(trade)
            if days is not None and days > max_days:
                return rule, f"holding period {days:.1f}d exceeds {max_days:.0f}d"
    return None


def shadow_backtest(trades: list[dict[str, Any]], rules: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a simple counterfactual filter backtest.

    The actual account is all closed trades. The shadow account keeps only
    trades that do not violate avoid_* or max_holding_days rules. Positive
    improvement means the rule-filtered shadow PnL exceeded actual PnL.
    money_left_on_table is the avoided loss amount: the sum of negative PnL
    from skipped trades, reported as a positive number.
    """

    actual_trades = _closed(trades)
    kept: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    for trade in actual_trades:
        violation = _violated_rule(trade, rules)
        if violation is None:
            kept.append(trade)
            continue
        rule, reason = violation
        skipped.append(trade)
        violations.append(
            {
                "rule_id": rule.get("id"),
                "symbol": trade.get("symbol"),
                "entry_date": trade.get("entry_date").isoformat() if isinstance(trade.get("entry_date"), datetime) else trade.get("entry_date"),
                "pnl": _to_float(trade.get("pnl")) or 0.0,
                "reason": reason,
            }
        )

    actual = _stats(actual_trades)
    shadow = _stats(kept)
    improvement_abs = shadow["pnl"] - actual["pnl"]
    improvement_pct = (improvement_abs / abs(actual["pnl"]) * 100.0) if actual["pnl"] else None
    avoided_losses = sum(abs(_to_float(trade.get("pnl")) or 0.0) for trade in skipped if (_to_float(trade.get("pnl")) or 0.0) < 0)
    return {
        "actual": actual,
        "shadow": shadow,
        "improvement_abs": improvement_abs,
        "improvement_pct": improvement_pct,
        "money_left_on_table": avoided_losses,
        "violations": violations,
        "counts": {
            "kept": len(kept),
            "skipped": len(skipped),
            "rules_applied": len([rule for rule in rules if rule.get("type") in {"avoid_setup", "avoid_emotion", "max_holding_days"}]),
        },
    }
