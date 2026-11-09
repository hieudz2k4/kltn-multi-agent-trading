import numpy as np
import pandas as pd
from backend.core.backtest_robustness import permutation_test, multi_window_robustness

def test_permutation_test_trending():
    # Strongly trending curve
    rng = np.random.default_rng(11)
    returns = rng.normal(0.001, 0.01, 400) + 0.002 # Positive drift
    equity = 100 * np.cumprod(1 + returns)
    dates = pd.date_range("2020-01-01", periods=400).strftime("%Y-%m-%d").tolist()
    equity_curve = [{"date": d, "equity": e} for d, e in zip(dates, equity)]
    
    res = permutation_test(equity_curve, n_permutations=500)

    assert "metric" in res
    assert res["metric"] == "sharpe"
    # Sign-flip null is centered near zero; a strong positive drift must sit well
    # above it and be statistically significant.
    assert res["observed"] > res["null_mean"]
    assert abs(res["null_mean"]) < abs(res["observed"])
    assert res["p_value"] < 0.05  # genuine edge is detected
    assert 0 <= res["p_value"] <= 1
    assert len(res["distribution"]) <= 200
    assert "interpretation" in res

def test_permutation_test_random_walk():
    # Random walk
    rng = np.random.default_rng(11)
    returns = rng.normal(0, 0.01, 400)
    equity = 100 * np.cumprod(1 + returns)
    dates = pd.date_range("2020-01-01", periods=400).strftime("%Y-%m-%d").tolist()
    equity_curve = [{"date": d, "equity": e} for d, e in zip(dates, equity)]
    
    res = permutation_test(equity_curve, n_permutations=100)
    
    # For a random walk, p-value shouldn't be tiny (usually > 0.05)
    assert res["p_value"] > 0.05

def test_multi_window_robustness_trending():
    # Strongly trending curve
    rng = np.random.default_rng(11)
    returns = rng.normal(0.001, 0.01, 400) + 0.002
    equity = 100 * np.cumprod(1 + returns)
    dates = pd.date_range("2020-01-01", periods=400).strftime("%Y-%m-%d").tolist()
    equity_curve = [{"date": d, "equity": e} for d, e in zip(dates, equity)]
    
    n_windows = 5
    res = multi_window_robustness(equity_curve, n_windows=n_windows)
    
    assert len(res["windows"]) == n_windows
    assert 0 <= res["coverage"]["profitable_pct"] <= 100
    assert 0 <= res["coverage"]["positive_sharpe_pct"] <= 100
    assert res["coverage"]["profitable_pct"] >= 60

def test_empty_input():
    res_p = permutation_test([])
    assert res_p["n_permutations"] == 0
    assert res_p["observed"] == 0.0
    
    res_m = multi_window_robustness([])
    assert res_m["n_windows"] == 0
    assert res_m["windows"] == []
    assert res_m["consistency_score"] == 0.0

def test_degenerate_input():
    # Too few points
    equity_curve = [{"date": "2020-01-01", "equity": 100}, {"date": "2020-01-02", "equity": 105}]
    
    res_p = permutation_test(equity_curve)
    assert res_p["n_permutations"] == 0
    
    res_m = multi_window_robustness(equity_curve)
    assert res_m["n_windows"] == 0
