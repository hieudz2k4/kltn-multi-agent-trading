from __future__ import annotations

import numpy as np
import pandas as pd


def rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional percentile rank by date."""
    return df.rank(axis=1, pct=True)


def scale(df: pd.DataFrame, a: float = 1) -> pd.DataFrame:
    denom = df.abs().sum(axis=1).replace(0, np.nan)
    return df.div(denom, axis=0) * a


def delay(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.shift(max(int(n), 0))


def delta(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df - delay(df, n)


def ts_sum(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).sum()


def sma(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).mean()


def stddev(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).std()


def ts_min(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).min()


def ts_max(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).max()


def _rolling_arg(values: np.ndarray, func: str) -> float:
    if np.isnan(values).any():
        return np.nan
    idx = np.argmin(values) if func == "min" else np.argmax(values)
    return float(idx + 1)


def ts_argmin(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).apply(lambda x: _rolling_arg(x, "min"), raw=True)


def ts_argmax(df: pd.DataFrame, n: int) -> pd.DataFrame:
    return df.rolling(int(n), min_periods=int(n)).apply(lambda x: _rolling_arg(x, "max"), raw=True)


def ts_rank(df: pd.DataFrame, n: int) -> pd.DataFrame:
    def _rank_last(values: np.ndarray) -> float:
        if np.isnan(values).any():
            return np.nan
        return float(pd.Series(values).rank(pct=True).iloc[-1])

    return df.rolling(int(n), min_periods=int(n)).apply(_rank_last, raw=True)


def correlation(a: pd.DataFrame, b: pd.DataFrame, n: int) -> pd.DataFrame:
    return a.rolling(int(n), min_periods=int(n)).corr(b)


def covariance(a: pd.DataFrame, b: pd.DataFrame, n: int) -> pd.DataFrame:
    return a.rolling(int(n), min_periods=int(n)).cov(b)


def decay_linear(df: pd.DataFrame, n: int) -> pd.DataFrame:
    window = int(n)
    weights = np.arange(1, window + 1, dtype=float)
    weights = weights / weights.sum()

    def _apply(values: np.ndarray) -> float:
        if np.isnan(values).any():
            return np.nan
        return float(np.dot(values, weights))

    return df.rolling(window, min_periods=window).apply(_apply, raw=True)


def signedpower(df: pd.DataFrame, e: float) -> pd.DataFrame:
    return np.sign(df) * (df.abs() ** e)


def log(df: pd.DataFrame) -> pd.DataFrame:
    return np.log(df.where(df > 0))


def abs_(df: pd.DataFrame) -> pd.DataFrame:
    return df.abs()


def sign(df: pd.DataFrame) -> pd.DataFrame:
    return np.sign(df)
