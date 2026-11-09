from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _json_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _date_str(value: Any) -> str:
    try:
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _empty_result(rebalance_days: int, long_short: bool) -> dict:
    return {
        "equity_curve": [],
        "daily_returns": [],
        "metrics": {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "volatility": 0.0,
            "hit_rate": 0.0,
            "turnover": 0.0,
        },
        "bars": 0,
        "rebalance_dates": [],
        "rebalance_days": int(rebalance_days),
        "long_short": bool(long_short),
    }


def _make_weights(row: pd.Series, top_quantile: float, long_short: bool) -> pd.Series:
    valid = row.replace([np.inf, -np.inf], np.nan).dropna().sort_values()
    weights = pd.Series(0.0, index=row.index, dtype=float)
    if valid.empty:
        return weights
    bucket = max(1, int(math.floor(len(valid) * float(top_quantile))))
    if long_short and len(valid) >= 2:
        bucket = max(1, min(bucket, len(valid) // 2))
        shorts = valid.index[:bucket]
        longs = valid.index[-bucket:]
        weights.loc[longs] = 1.0 / bucket
        weights.loc[shorts] = -1.0 / bucket
    else:
        longs = valid.index[-bucket:]
        weights.loc[longs] = 1.0 / bucket
    return weights


def _metrics(returns: np.ndarray, equity: np.ndarray, periods_per_year: int, turnover: float) -> dict[str, float]:
    if returns.size == 0 or equity.size == 0:
        return _empty_result(1, True)["metrics"]
    total_return = _json_float(equity[-1] - 1.0)
    years = max(returns.size / max(periods_per_year, 1), 1.0 / max(periods_per_year, 1))
    cagr = _json_float(equity[-1] ** (1.0 / years) - 1.0) if equity[-1] > 0 else -1.0
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    mean = float(np.mean(returns)) if returns.size else 0.0
    sharpe = _json_float(mean / std * math.sqrt(periods_per_year)) if std > 0 else 0.0
    downside = returns[returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if downside.size > 1 else 0.0
    sortino = _json_float(mean / downside_std * math.sqrt(periods_per_year)) if downside_std > 0 else 0.0
    peaks = np.maximum.accumulate(equity)
    drawdowns = equity / np.where(peaks == 0, 1.0, peaks) - 1.0
    volatility = _json_float(std * math.sqrt(periods_per_year))
    hit_rate = _json_float(float(np.mean(returns > 0))) if returns.size else 0.0
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": _json_float(float(np.min(drawdowns))),
        "volatility": volatility,
        "hit_rate": hit_rate,
        "turnover": _json_float(turnover),
    }


def run_backtest(
    close_panel: pd.DataFrame,
    signal_panel: pd.DataFrame,
    *,
    rebalance_days: int,
    top_quantile: float,
    long_short: bool,
    periods_per_year: int = 252,
) -> dict:
    """Run a lookahead-safe vectorized cross-sectional backtest.

    Returns on date d use weights selected after the previous close, never signal
    values from date d or later.
    """

    try:
        close = close_panel.astype(float).sort_index()
        signal = signal_panel.reindex(index=close.index, columns=close.columns).astype(float)
    except Exception:
        return _empty_result(rebalance_days, long_short)
    if close.empty or signal.empty or close.shape[1] == 0:
        return _empty_result(rebalance_days, long_short)

    daily = close.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    current_weights = pd.Series(0.0, index=close.columns, dtype=float)
    returns: list[float] = []
    equity_values: list[float] = []
    rebalance_dates: list[str] = []
    turnovers: list[float] = []
    equity = 1.0
    step = max(int(rebalance_days), 1)

    for i, date_value in enumerate(close.index):
        day_return = _json_float(float((daily.iloc[i].fillna(0.0) * current_weights).sum()))
        returns.append(day_return)
        equity *= 1.0 + day_return
        if not math.isfinite(equity) or equity <= 0:
            equity = max(equity, 0.0) if math.isfinite(equity) else 0.0
        equity_values.append(_json_float(equity))

        if i % step == 0:
            new_weights = _make_weights(signal.iloc[i], top_quantile, long_short)
            turnovers.append(_json_float(float((new_weights - current_weights).abs().sum())))
            current_weights = new_weights
            rebalance_dates.append(_date_str(date_value))

    returns_arr = np.asarray(returns, dtype=float)
    equity_arr = np.asarray(equity_values, dtype=float)
    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0
    return {
        "equity_curve": [{"date": _date_str(date), "value": _json_float(value)} for date, value in zip(close.index, equity_values)],
        "daily_returns": [_json_float(value) for value in returns],
        "metrics": _metrics(returns_arr, equity_arr, max(int(periods_per_year), 1), avg_turnover),
        "bars": int(len(close.index)),
        "rebalance_dates": rebalance_dates,
        "rebalance_days": int(rebalance_days),
        "long_short": bool(long_short),
    }
