from __future__ import annotations

import json

import numpy as np
import pandas as pd

from backend.alpha_zoo.factors import FACTOR_REGISTRY
from backend.alpha_zoo.evaluate import _build_panels
from backend.research_autopilot.attribution import attribute
from backend.research_autopilot.backtest import run_backtest
from backend.research_autopilot.schemas import AcceptanceCriteria, SignalSpec
from backend.research_autopilot.signals import build_signal_panel
from backend.research_autopilot.verdict import evaluate


def _predictive_close(rows: int = 420, symbols: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2024-01-01", periods=rows)
    names = [f"S{i}" for i in range(symbols)]
    signal = pd.DataFrame(rng.normal(size=(rows, symbols)), index=dates, columns=names)
    returns = 0.0002 + 0.003 * signal.shift(1).fillna(0.0) + rng.normal(0.0, 0.002, size=(rows, symbols))
    close = 100.0 * (1.0 + returns).cumprod()
    return close, signal


def _random_close(rows: int = 420, symbols: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(19)
    dates = pd.bdate_range("2024-01-01", periods=rows)
    names = [f"S{i}" for i in range(symbols)]
    returns = rng.normal(0.0, 0.01, size=(rows, symbols))
    signal = pd.DataFrame(rng.normal(size=(rows, symbols)), index=dates, columns=names)
    close = pd.DataFrame(100.0 * np.cumprod(1.0 + returns, axis=0), index=dates, columns=names)
    return close, signal


def _frames_from_close(close: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frames = {}
    for symbol in close.columns:
        series = close[symbol]
        frames[symbol] = pd.DataFrame(
            {
                "Open": series.shift(1).fillna(series.iloc[0]),
                "High": series * 1.01,
                "Low": series * 0.99,
                "Close": series,
                "Volume": 1_000_000,
            },
            index=close.index,
        )
    return frames


def test_run_backtest_predictive_signal_positive_and_lookahead_safe() -> None:
    close, signal = _predictive_close()
    result = run_backtest(close, signal, rebalance_days=5, top_quantile=0.3, long_short=True)
    assert result["metrics"]["sharpe"] > 0
    assert len(result["equity_curve"]) == result["bars"] == len(close)
    json.dumps(result)

    cutoff = 220
    base = run_backtest(close.iloc[:cutoff], signal.iloc[:cutoff], rebalance_days=5, top_quantile=0.3, long_short=True)
    appended = run_backtest(close, signal, rebalance_days=5, top_quantile=0.3, long_short=True)
    assert appended["equity_curve"][cutoff - 1]["value"] == base["equity_curve"][cutoff - 1]["value"]


def test_run_backtest_random_signal_sharpe_near_zero() -> None:
    close, signal = _random_close()
    result = run_backtest(close, signal, rebalance_days=5, top_quantile=0.3, long_short=True)
    assert abs(result["metrics"]["sharpe"]) < 1.5


def test_attribute_regime_permutation_and_factor_exposure() -> None:
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2024-01-01", periods=300)
    benchmark = rng.normal(0.0002, 0.01, size=300)
    strategy = 0.0001 + 0.8 * benchmark + rng.normal(0.0, 0.005, size=300)
    result = attribute(strategy, benchmark, dates, permutations=25, seed=9)
    assert sum(item["days"] for item in result["regime"]) == len(dates)
    assert 0.0 <= result["permutation"]["p_value"] <= 1.0
    assert np.isfinite(result["factor_exposure"]["beta"])


def test_verdict_evaluate_accept_reject_inconclusive() -> None:
    metrics = {"sharpe": 1.3, "cagr": 0.2, "max_drawdown": -0.1, "hit_rate": 0.55}
    robustness = {"psr": 0.9, "verdict": "robust", "verdict_reasons": []}
    attribution = {"factor_exposure": {"alpha_annual": 0.04}}
    accepted = evaluate(metrics, robustness, attribution, AcceptanceCriteria(min_sharpe=1.0, max_drawdown=-0.2).model_dump())
    rejected = evaluate(metrics, robustness, attribution, AcceptanceCriteria(min_sharpe=2.0).model_dump())
    inconclusive = evaluate(metrics, robustness, attribution, AcceptanceCriteria().model_dump())
    assert accepted["status"] == "accepted"
    assert rejected["status"] == "rejected"
    assert inconclusive["status"] == "inconclusive"


def test_build_signal_panel_momentum_and_alpha_factor() -> None:
    close, _ = _predictive_close()
    panels = _build_panels(_frames_from_close(close))
    momentum = build_signal_panel(SignalSpec(kind="momentum", lookback_days=21), panels)
    assert isinstance(momentum, pd.DataFrame)
    assert momentum.shape == close.shape
    factor = FACTOR_REGISTRY[0]
    alpha = build_signal_panel(SignalSpec(kind="alpha_factor", factor_id=factor.id), panels)
    assert isinstance(alpha, pd.DataFrame)
    assert alpha.shape == close.shape
