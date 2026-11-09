from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import datetime

def _safe_float(val) -> float:
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return 0.0
        return round(f, 6)
    except Exception:
        return 0.0

def _equity_series(equity_curve: list[dict]) -> pd.Series:
    if not equity_curve:
        return pd.Series(dtype=float)
    df = pd.DataFrame(equity_curve)
    if "date" not in df.columns or "equity" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["equity"] = pd.to_numeric(df["equity"], errors="coerce")
    df = df.dropna(subset=["date", "equity"]).sort_values("date")
    if df.empty:
        return pd.Series(dtype=float)
    return df.set_index("date")["equity"]

def _sharpe(returns: np.ndarray, periods_per_year: int = 252) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))

def permutation_test(equity_curve: list[dict], *, n_permutations: int = 500, metric: str = "sharpe", seed: int = 42, periods_per_year: int = 252) -> dict:
    eq = _equity_series(equity_curve)
    if len(eq) < 3:
        return {
            "metric": metric, "observed": 0.0, "p_value": 1.0, "percentile": 0.0, 
            "n_permutations": 0, "null_mean": 0.0, "null_std": 0.0, 
            "distribution": [], "interpretation": "Insufficient data"
        }
    
    r = eq.pct_change().dropna().to_numpy()
    
    if metric == "total_return":
        observed = np.prod(1 + r) - 1
    else:
        observed = _sharpe(r, periods_per_year)
    
    # Sign-flip (Monte-Carlo permutation) test of H0: returns are symmetric about
    # zero (no directional edge). NOTE: simply REORDERING returns leaves mean/std —
    # and therefore Sharpe and total return — unchanged, so it tests nothing. Randomly
    # flipping the sign of each return builds a centered null the observed metric can
    # be compared against.
    rng = np.random.default_rng(seed)
    null = []
    for _ in range(n_permutations):
        signs = rng.choice(np.array([-1.0, 1.0]), size=r.size)
        perm = r * signs
        if metric == "total_return":
            m = np.prod(1 + perm) - 1
        else:
            m = _sharpe(perm, periods_per_year)
        null.append(m)
    
    null = np.array(null)
    p_value = (np.sum(null >= observed) + 1) / (n_permutations + 1)
    percentile = 100 * np.mean(null < observed)
    null_mean = np.mean(null)
    null_std = np.std(null)
    
    sorted_null = np.sort(null)
    if len(sorted_null) > 200:
        indices = np.linspace(0, len(sorted_null) - 1, 200).astype(int)
        distribution = [ _safe_float(sorted_null[i]) for i in indices ]
    else:
        distribution = [ _safe_float(x) for x in sorted_null ]
        
    interpretation = "Likely genuine edge (p<0.05)" if p_value < 0.05 else "Indistinguishable from random (p>=0.05)"
    
    return {
        "metric": metric,
        "observed": _safe_float(observed),
        "p_value": _safe_float(p_value),
        "percentile": _safe_float(percentile),
        "n_permutations": int(n_permutations),
        "null_mean": _safe_float(null_mean),
        "null_std": _safe_float(null_std),
        "distribution": distribution,
        "interpretation": interpretation
    }

def multi_window_robustness(equity_curve: list[dict], *, n_windows: int = 5, periods_per_year: int = 252) -> dict:
    eq = _equity_series(equity_curve)
    
    if len(eq) < (n_windows * 2):
        n_windows = max(2, len(eq) // 2)
        
    if len(eq) < 4:
        return {
            "n_windows": 0, "windows": [], 
            "coverage": {"profitable_pct": 0.0, "positive_sharpe_pct": 0.0},
            "consistency_score": 0.0, "interpretation": "Insufficient data"
        }
    
    # Split by position
    indices = np.array_split(np.arange(len(eq)), n_windows)
    windows = []
    
    for i, idx in enumerate(indices):
        if len(idx) < 2:
            continue
        window_eq = eq.iloc[idx]
        first = window_eq.iloc[0]
        last = window_eq.iloc[-1]
        
        tr = (last / first - 1) if first != 0 else 0.0
        
        days = (window_eq.index[-1] - window_eq.index[0]).days
        if days > 0:
            cagr = (last / first) ** (365.25 / days) - 1 if first > 0 and last > 0 else 0.0
        else:
            cagr = 0.0
            
        returns = window_eq.pct_change().dropna().to_numpy()
        sharpe = _sharpe(returns, periods_per_year)
        
        mdd = (window_eq / window_eq.cummax() - 1).min()
        
        windows.append({
            "index": i,
            "start": str(window_eq.index[0].date()),
            "end": str(window_eq.index[-1].date()),
            "total_return": _safe_float(tr),
            "cagr": _safe_float(cagr),
            "sharpe": _safe_float(sharpe),
            "max_drawdown": _safe_float(mdd)
        })
        
    if not windows:
        return {
            "n_windows": 0, "windows": [], 
            "coverage": {"profitable_pct": 0.0, "positive_sharpe_pct": 0.0},
            "consistency_score": 0.0, "interpretation": "Insufficient data"
        }
        
    total_returns = np.array([w["total_return"] for w in windows])
    sharpes = np.array([w["sharpe"] for w in windows])
    
    profitable_pct = 100 * np.mean(total_returns > 0)
    positive_sharpe_pct = 100 * np.mean(sharpes > 0)
    
    sharpe_std = np.std(sharpes)
    consistency_score = np.mean(sharpes) / sharpe_std if sharpe_std > 0 else 0.0
    
    interpretation = "Robust performance across windows" if profitable_pct >= 80 and consistency_score > 1.0 else "Inconsistent performance"
    
    return {
        "n_windows": len(windows),
        "windows": windows,
        "coverage": {
            "profitable_pct": _safe_float(profitable_pct),
            "positive_sharpe_pct": _safe_float(positive_sharpe_pct)
        },
        "consistency_score": _safe_float(consistency_score),
        "interpretation": interpretation
    }
