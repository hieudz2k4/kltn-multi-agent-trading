from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from math import isfinite
from typing import Any


Trade = dict[str, Any]


def _json_number(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    numeric = float(value)
    if not isfinite(numeric):
        return None
    return numeric


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
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def _closed_trades(trades: list[Trade]) -> list[Trade]:
    return [trade for trade in trades if trade.get("exit_price") is not None and _to_float(trade.get("pnl")) is not None]


def _holding_days(trade: Trade) -> float | None:
    entry = _parse_dt(trade.get("entry_date"))
    exit_ = _parse_dt(trade.get("exit_date"))
    if entry is None or exit_ is None:
        return None
    days = (exit_ - entry).total_seconds() / 86400.0
    return max(days, 0.0)


def _severity(score: float) -> str:
    if score >= 0.7:
        return "high"
    if score >= 0.35:
        return "moderate"
    return "low"


def _bias(score: float, detail: str, evidence: dict[str, Any]) -> dict[str, Any]:
    score = max(0.0, min(1.0, float(score)))
    return {
        "score": _json_number(score),
        "severity": _severity(score),
        "detail": detail,
        "evidence": _json_safe(evidence),
    }


def _stats(closed: list[Trade]) -> dict[str, Any]:
    pnls = [_to_float(trade.get("pnl")) or 0.0 for trade in closed]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    return {
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(closed) if closed else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss else (None if gross_win else 0.0),
        "expectancy": sum(pnls) / len(closed) if closed else 0.0,
        "payoff_ratio": avg_win / abs(avg_loss) if avg_loss else None,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "total_pnl": sum(pnls),
    }


def _group_breakdown(closed: list[Trade], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[Trade]] = defaultdict(list)
    for trade in closed:
        raw = trade.get(key)
        label = str(raw).strip() if raw is not None else ""
        if label:
            groups[label].append(trade)
    return {
        label: {
            "count": stats["trades"],
            "win_rate": stats["win_rate"],
            "expectancy": stats["expectancy"],
            "total_pnl": stats["total_pnl"],
        }
        for label, stats in ((label, _stats(rows)) for label, rows in sorted(groups.items()))
    }


def _holding_bucket(days: float | None) -> str:
    if days is None:
        return "unknown"
    if days <= 1:
        return "<=1d"
    if days <= 5:
        return "2-5d"
    if days <= 20:
        return "6-20d"
    return ">20d"


def _holding_breakdown(closed: list[Trade]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[Trade]] = defaultdict(list)
    for trade in closed:
        buckets[_holding_bucket(_holding_days(trade))].append(trade)
    order = ["<=1d", "2-5d", "6-20d", ">20d", "unknown"]
    output: dict[str, dict[str, Any]] = {}
    for bucket in order:
        rows = buckets.get(bucket, [])
        if not rows:
            continue
        stats = _stats(rows)
        output[bucket] = {
            "count": stats["trades"],
            "win_rate": stats["win_rate"],
            "expectancy": stats["expectancy"],
            "total_pnl": stats["total_pnl"],
        }
    return output


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, float):
        return value if isfinite(value) else None
    return value


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _disposition_bias(winner_days: list[float], loser_days: list[float]) -> dict[str, Any]:
    avg_winners = _mean(winner_days)
    avg_losers = _mean(loser_days)
    ratio = avg_losers / avg_winners if avg_winners > 0 else (None if not avg_losers else 999.0)
    score = 0.0 if ratio is None or ratio <= 1 else min(1.0, (ratio - 1.0) / 2.0)
    return _bias(
        score,
        "Losers are held longer than winners." if score else "No clear evidence that losers are held longer than winners.",
        {"avg_holding_winners": avg_winners, "avg_holding_losers": avg_losers, "ratio": ratio},
    )


def _overtrading_bias(closed: list[Trade]) -> dict[str, Any]:
    dates = [_parse_dt(trade.get("entry_date")) for trade in closed]
    dates = [date for date in dates if date is not None]
    if len(dates) < 2:
        return _bias(0.0, "Not enough dated trades to estimate active-week frequency.", {"trades_per_active_week": 0.0, "scratch_rate": 0.0})
    span_days = max((max(dates) - min(dates)).days + 1, 1)
    active_weeks = max(span_days / 7.0, 1.0)
    frequency = len(closed) / active_weeks
    pnls = [abs(_to_float(trade.get("pnl")) or 0.0) for trade in closed]
    avg_abs = _mean(pnls)
    scratch_threshold = max(avg_abs * 0.25, 1.0)
    scratch_rate = sum(1 for pnl in pnls if pnl <= scratch_threshold) / len(pnls) if pnls else 0.0
    frequency_score = max(0.0, min(1.0, (frequency - 5.0) / 10.0))
    score = max(0.0, min(1.0, (frequency_score * 0.7) + (scratch_rate * 0.3 if frequency > 5 else 0.0)))
    return _bias(
        score,
        "Trade frequency is elevated and includes many low-PnL scratch trades." if score >= 0.35 else "No strong overtrading signal from frequency and scratches.",
        {"trades_per_active_week": frequency, "scratch_rate": scratch_rate, "scratch_threshold": scratch_threshold},
    )


def _revenge_bias(closed: list[Trade], overall_expectancy: float) -> dict[str, Any]:
    ordered = sorted(closed, key=lambda trade: _parse_dt(trade.get("entry_date")) or datetime.min)
    losing_exits = [
        _parse_dt(trade.get("exit_date"))
        for trade in ordered
        if (_to_float(trade.get("pnl")) or 0.0) < 0 and _parse_dt(trade.get("exit_date")) is not None
    ]
    revenge: list[Trade] = []
    for trade in ordered:
        entry = _parse_dt(trade.get("entry_date"))
        if entry is None:
            continue
        if any(0 < (entry - exit_).total_seconds() <= 3 * 86400 for exit_ in losing_exits if exit_ is not None):
            revenge.append(trade)
    revenge_expectancy = _stats(revenge)["expectancy"] if revenge else 0.0
    gap = overall_expectancy - revenge_expectancy
    scale = max(abs(overall_expectancy), 1.0)
    score = min(1.0, max(0.0, gap / scale)) if revenge else 0.0
    return _bias(
        score,
        "Trades entered soon after losses underperform the overall journal." if score else "No clear underperformance after losing exits.",
        {"revenge_trades": len(revenge), "revenge_expectancy": revenge_expectancy, "overall_expectancy": overall_expectancy},
    )


def _loss_aversion_bias(avg_win: float, avg_loss: float, winner_days: list[float], loser_days: list[float]) -> dict[str, Any]:
    avg_winner_days = _mean(winner_days)
    avg_loser_days = _mean(loser_days)
    holding_ratio = avg_loser_days / avg_winner_days if avg_winner_days > 0 else 0.0
    loss_size_ratio = abs(avg_loss) / avg_win if avg_win > 0 else 0.0
    score = 0.0
    if holding_ratio > 1 and loss_size_ratio > 1:
        score = min(1.0, ((holding_ratio - 1.0) / 2.0 * 0.55) + (min(loss_size_ratio - 1.0, 2.0) / 2.0 * 0.45))
    return _bias(
        score,
        "Winners are cut earlier while average losses exceed average wins." if score else "No strong cut-winners-early/loss-aversion pattern.",
        {"avg_holding_winners": avg_winner_days, "avg_holding_losers": avg_loser_days, "avg_win": avg_win, "avg_loss": avg_loss},
    )


def _emotion_bias(closed: list[Trade]) -> dict[str, Any]:
    groups: dict[str, list[Trade]] = defaultdict(list)
    for trade in closed:
        emotion = str(trade.get("emotion") or "").strip().lower()
        if emotion:
            groups[emotion].append(trade)
    negative: dict[str, dict[str, Any]] = {}
    for emotion, rows in sorted(groups.items()):
        stats = _stats(rows)
        if stats["expectancy"] < 0:
            negative[emotion] = {"count": stats["trades"], "expectancy": stats["expectancy"], "total_pnl": stats["total_pnl"]}
    if not groups:
        score = 0.0
        detail = "Emotion field is not populated enough to assess leakage."
    else:
        score = min(1.0, len(negative) / max(len(groups), 1))
        detail = "Some emotional states have negative expectancy." if negative else "No negative-expectancy emotion buckets found."
    return _bias(score, detail, {"negative_emotions": negative, "emotion_groups": len(groups)})


def build_profile(trades: list[Trade]) -> dict[str, Any]:
    """Build a behavioral profile from canonical trade dictionaries.

    Performance and bias calculations use closed trades only. Counts include
    open trades so callers can explain sample size.
    """

    closed = _closed_trades(trades)
    stats = _stats(closed)
    holding = [(_holding_days(trade), _to_float(trade.get("pnl")) or 0.0) for trade in closed]
    winner_days = [days for days, pnl in holding if days is not None and pnl > 0]
    loser_days = [days for days, pnl in holding if days is not None and pnl < 0]
    all_days = [days for days, _ in holding if days is not None]

    loss_aversion = _loss_aversion_bias(stats["avg_win"], stats["avg_loss"], winner_days, loser_days)
    profile = {
        "counts": {
            "total": len(trades),
            "closed": len(closed),
            "open": max(len(trades) - len(closed), 0),
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_rate": stats["win_rate"],
            "profit_factor": stats["profit_factor"],
            "expectancy": stats["expectancy"],
            "payoff_ratio": stats["payoff_ratio"],
            "avg_win": stats["avg_win"],
            "avg_loss": stats["avg_loss"],
        },
        "holding_days": {
            "avg_holding_all": _mean(all_days),
            "avg_holding_winners": _mean(winner_days),
            "avg_holding_losers": _mean(loser_days),
        },
        "biases": {
            "disposition_effect": _disposition_bias(winner_days, loser_days),
            "overtrading": _overtrading_bias(closed),
            "revenge_trading": _revenge_bias(closed, stats["expectancy"]),
            "loss_aversion": loss_aversion,
            "cut_winners_early": loss_aversion,
            "emotion_leakage": _emotion_bias(closed),
        },
        "breakdowns": {
            "by_setup": _group_breakdown(closed, "setup"),
            "by_strategy": _group_breakdown(closed, "strategy"),
            "holding_bucket": _holding_breakdown(closed),
        },
    }
    return _json_safe(profile)
