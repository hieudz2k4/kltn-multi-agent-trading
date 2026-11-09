from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.shadow_account.profiler import build_profile
from backend.shadow_account.rules import extract_rules
from backend.shadow_account.shadow import shadow_backtest


def trade_from_journal(row: Any) -> dict[str, Any]:
    """Map a JournalEntry ORM row into the canonical trade dictionary."""

    return {
        "symbol": row.symbol,
        "direction": row.direction,
        "entry_date": row.entry_date.isoformat() if getattr(row, "entry_date", None) else None,
        "exit_date": row.exit_date.isoformat() if getattr(row, "exit_date", None) else None,
        "entry_price": row.entry_price,
        "exit_price": row.exit_price,
        "quantity": row.quantity,
        "pnl": row.pnl,
        "pnl_pct": row.pnl_pct,
        "fees": row.fees,
        "strategy": row.strategy,
        "setup": row.setup,
        "emotion": row.emotion,
        "rating": row.rating,
        "tags": list(row.tags or []),
    }


def _closed_count(trades: list[dict[str, Any]]) -> int:
    return sum(1 for trade in trades if trade.get("exit_price") is not None and trade.get("pnl") is not None)


def _breakdown_rows(rows: Any, label_key: str) -> list[dict[str, Any]]:
    if isinstance(rows, list):
        return rows
    if not isinstance(rows, dict):
        return []
    return [{label_key: label, **values} for label, values in rows.items() if isinstance(values, dict)]


def _report_profile(profile: dict[str, Any]) -> dict[str, Any]:
    counts = profile.get("counts") if isinstance(profile.get("counts"), dict) else {}
    holding_days = profile.get("holding_days") if isinstance(profile.get("holding_days"), dict) else {}
    breakdowns = profile.get("breakdowns") if isinstance(profile.get("breakdowns"), dict) else {}

    return {
        **profile,
        "win_rate": counts.get("win_rate"),
        "profit_factor": counts.get("profit_factor"),
        "expectancy": counts.get("expectancy"),
        "avg_holding_winners": holding_days.get("avg_holding_winners"),
        "avg_holding_losers": holding_days.get("avg_holding_losers"),
        "biases": profile.get("biases") if isinstance(profile.get("biases"), dict) else {},
        "by_setup": _breakdown_rows(breakdowns.get("by_setup"), "setup"),
        "by_strategy": _breakdown_rows(breakdowns.get("by_strategy"), "strategy"),
        "holding_bucket": _breakdown_rows(breakdowns.get("holding_bucket"), "bucket"),
    }


def build_report(trades: list[dict[str, Any]], *, min_samples: int = 4) -> dict[str, Any]:
    """Build the full shadow-account report for canonical trades."""

    closed_trades = _closed_count(trades)
    generated_at = datetime.now(timezone.utc).isoformat()
    profile = build_profile(trades)
    if closed_trades < 3:
        message = "At least 3 closed trades are required for a shadow-account behavioral report."
        return {
            "summary": {
                "insufficient_data": True,
                "message": message,
            },
            "profile": _report_profile(profile),
            "rules": [],
            "shadow": shadow_backtest(trades, []),
            "meta": {"closed_trades": closed_trades, "generated_at": generated_at},
            "insufficient_data": True,
            "message": message,
        }

    rules = extract_rules(profile, trades, min_samples=min_samples)
    shadow = shadow_backtest(trades, rules)
    return {
        "summary": {
            "insufficient_data": False,
            "message": "Shadow-account behavioral report generated.",
            "rules_found": len(rules),
            "money_left_on_table": shadow["money_left_on_table"],
            "improvement_abs": shadow["improvement_abs"],
        },
        "profile": _report_profile(profile),
        "rules": rules,
        "shadow": shadow,
        "meta": {"closed_trades": closed_trades, "generated_at": generated_at},
        "insufficient_data": False,
    }
