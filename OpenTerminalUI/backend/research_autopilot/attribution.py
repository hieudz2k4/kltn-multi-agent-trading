from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except Exception:
        return None
    return out if math.isfinite(out) else None


def _sharpe(values: np.ndarray, periods_per_year: int = 252) -> float:
    if values.size < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    if std <= 0 or not math.isfinite(std):
        return 0.0
    return float(np.mean(values) / std * math.sqrt(periods_per_year))


def _periods(series: pd.Series, largest: bool) -> list[dict[str, float | str]]:
    selected = series.nlargest(5) if largest else series.nsmallest(5)
    return [{"date": pd.Timestamp(index).strftime("%Y-%m-%d"), "return": float(value)} for index, value in selected.items()]


def _factor_exposure(strategy: pd.Series, benchmark: pd.Series | None) -> dict[str, float | None]:
    if benchmark is None:
        return {"alpha_annual": None, "beta": None, "r_squared": None}
    joined = pd.concat([strategy.rename("strategy"), benchmark.rename("benchmark")], axis=1).dropna()
    if len(joined) < 3 or float(joined["benchmark"].var(ddof=1)) <= 0:
        return {"alpha_annual": None, "beta": None, "r_squared": None}
    x = joined["benchmark"].to_numpy(dtype=float)
    y = joined["strategy"].to_numpy(dtype=float)
    beta, intercept = np.polyfit(x, y, 1)
    pred = intercept + beta * x
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "alpha_annual": float(intercept * 252.0),
        "beta": float(beta),
        "r_squared": float(max(min(r_squared, 1.0), 0.0)),
    }


def attribute(
    strategy_daily_returns: list[float] | np.ndarray | pd.Series,
    benchmark_daily_returns: list[float] | np.ndarray | pd.Series | None,
    dates: list[Any] | pd.Index,
    *,
    permutations: int = 200,
    seed: int = 7,
) -> dict:
    """Compute regime, path significance, and benchmark exposure attribution."""

    idx = pd.to_datetime(list(dates))
    strategy = pd.Series(np.asarray(list(strategy_daily_returns), dtype=float), index=idx).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if len(strategy) == 0:
        return {
            "regime": [],
            "top_periods": [],
            "worst_periods": [],
            "permutation": {
                "trials": int(permutations),
                "observed_sharpe": 0.0,
                "p_value": 1.0,
                "better_count": 0,
                "null_hypothesis": "Random sign flips of daily returns preserve volatility but remove directional edge.",
            },
            "factor_exposure": {"alpha_annual": None, "beta": None, "r_squared": None},
        }

    benchmark = None
    if benchmark_daily_returns is not None:
        benchmark_values = np.asarray(list(benchmark_daily_returns), dtype=float)
        benchmark = pd.Series(benchmark_values[: len(strategy)], index=strategy.index[: len(benchmark_values)]).reindex(strategy.index).fillna(0.0)
    regime_source = benchmark if benchmark is not None else strategy
    trailing = (1.0 + regime_source).rolling(63, min_periods=2).apply(np.prod, raw=True) - 1.0
    labels = pd.Series("sideways", index=strategy.index)
    labels.loc[trailing > 0.02] = "bull"
    labels.loc[trailing < -0.02] = "bear"
    total_pnl = float(strategy.sum())
    regimes: list[dict[str, float | int | str]] = []
    for label in ["bull", "bear", "sideways"]:
        values = strategy.loc[labels == label]
        pnl = float(values.sum()) if len(values) else 0.0
        regimes.append(
            {
                "regime": label,
                "days": int(len(values)),
                "avg_daily_return": float(values.mean()) if len(values) else 0.0,
                "total_return": pnl,
                "contribution": float(pnl / total_pnl) if total_pnl != 0 else 0.0,
            }
        )

    trials = max(int(permutations), 0)
    rng = np.random.default_rng(seed)
    values = strategy.to_numpy(dtype=float)
    observed = _sharpe(values)
    better_count = 0
    for _ in range(trials):
        signs = rng.choice(np.array([-1.0, 1.0]), size=values.size)
        simulated = np.abs(values) * signs
        if _sharpe(simulated) >= observed:
            better_count += 1
    p_value = float(better_count / trials) if trials else 1.0
    exposure = _factor_exposure(strategy, benchmark)
    return {
        "regime": regimes,
        "top_periods": _periods(strategy, True),
        "worst_periods": _periods(strategy, False),
        "permutation": {
            "trials": trials,
            "observed_sharpe": float(observed),
            "p_value": p_value,
            "better_count": int(better_count),
            "null_hypothesis": "Random sign flips of daily returns preserve the realized absolute-return path while removing directional edge.",
        },
        "factor_exposure": {key: _safe_float(value) for key, value in exposure.items()},
    }
