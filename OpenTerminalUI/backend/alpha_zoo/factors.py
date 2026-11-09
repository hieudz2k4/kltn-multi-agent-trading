from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from backend.alpha_zoo import operators as op

PanelMap = dict[str, pd.DataFrame]
FactorFn = Callable[[PanelMap], pd.DataFrame]


@dataclass(frozen=True)
class FactorDef:
    """Formulaic factor definition.

    Families: academic anomalies from the empirical asset-pricing literature,
    Alpha101 from Kakushadze (2016), and OHLCV-only GTJA191-style formula alphas.
    Yahoo daily data has no true VWAP, so the "vwap" panel is typical price
    (high + low + close) / 3.
    """

    id: str
    name: str
    zoo: str
    category: str
    description: str
    window: int
    fn: FactorFn


def _safe(fn: FactorFn) -> FactorFn:
    def wrapped(panels: PanelMap) -> pd.DataFrame:
        close = panels["close"]
        try:
            out = fn(panels)
            if not isinstance(out, pd.DataFrame):
                return pd.DataFrame(np.nan, index=close.index, columns=close.columns)
            return out.reindex(index=close.index, columns=close.columns).replace([np.inf, -np.inf], np.nan)
        except Exception:
            return pd.DataFrame(np.nan, index=close.index, columns=close.columns)

    return wrapped


def _adv(p: PanelMap, n: int) -> pd.DataFrame:
    return op.sma(p["close"] * p["volume"], n)


def _academic() -> list[FactorDef]:
    return [
        FactorDef("momentum_12_1", "Momentum 12-1", "academic", "momentum", "252-day return skipping the most recent 21 sessions.", 252, _safe(lambda p: p["close"].shift(21) / p["close"].shift(252) - 1)),
        FactorDef("reversal_5", "Reversal 5D", "academic", "reversal", "Negative five-session return.", 5, _safe(lambda p: -(p["close"] / p["close"].shift(5) - 1))),
        FactorDef("volatility_20", "Volatility 20D", "academic", "volatility", "Trailing 20-session return volatility.", 20, _safe(lambda p: op.stddev(p["returns"], 20))),
        FactorDef("amihud_illiquidity_20", "Amihud Illiquidity 20D", "academic", "liquidity", "Mean absolute return divided by dollar volume.", 20, _safe(lambda p: op.sma(p["returns"].abs() / (p["close"] * p["volume"]).replace(0, np.nan), 20))),
        FactorDef("max_return_5", "Max Return 5D", "academic", "lottery", "Maximum daily return over the trailing five sessions.", 5, _safe(lambda p: op.ts_max(p["returns"], 5))),
        FactorDef("volume_trend_20", "Volume Trend 20D", "academic", "volume", "Short volume average relative to trailing 20-session volume.", 20, _safe(lambda p: op.sma(p["volume"], 5) / op.sma(p["volume"], 20) - 1)),
        FactorDef("rsi_14", "RSI 14D", "academic", "momentum", "Classic 14-session relative strength index.", 14, _safe(lambda p: 100 - 100 / (1 + op.sma(p["close"].diff().clip(lower=0), 14) / op.sma((-p["close"].diff()).clip(lower=0), 14).replace(0, np.nan)))),
        FactorDef("dist_from_252d_high", "Distance From 252D High", "academic", "momentum", "Close divided by trailing 252-session high minus one.", 252, _safe(lambda p: p["close"] / op.ts_max(p["close"], 252) - 1)),
    ]


def _alpha101() -> list[FactorDef]:
    # Skips: Alpha101 formulas requiring industry classification, market cap, or unavailable true VWAP.
    f: list[FactorDef] = []
    add = f.append
    add(FactorDef("alpha101_001", "Alpha#1", "alpha101", "reversal", "Rank of recent price extrema adjusted by volatility.", 20, _safe(lambda p: op.rank(op.ts_argmax(op.signedpower(p["returns"].where(p["returns"] >= 0, op.stddev(p["returns"], 20)), 2), 5)) - 0.5)))
    add(FactorDef("alpha101_002", "Alpha#2", "alpha101", "volume-price", "Negative correlation of volume change and intraday return ranks.", 6, _safe(lambda p: -op.correlation(op.rank(op.delta(op.log(p["volume"]), 2)), op.rank((p["close"] - p["open"]) / p["open"]), 6))))
    add(FactorDef("alpha101_003", "Alpha#3", "alpha101", "volume-price", "Negative correlation of open and volume ranks.", 10, _safe(lambda p: -op.correlation(op.rank(p["open"]), op.rank(p["volume"]), 10))))
    add(FactorDef("alpha101_004", "Alpha#4", "alpha101", "reversal", "Negative trailing low rank.", 9, _safe(lambda p: -op.ts_rank(op.rank(p["low"]), 9))))
    add(FactorDef("alpha101_006", "Alpha#6", "alpha101", "volume-price", "Negative correlation of open and volume.", 10, _safe(lambda p: -op.correlation(p["open"], p["volume"], 10))))
    add(FactorDef("alpha101_008", "Alpha#8", "alpha101", "momentum", "Ranked change in open-return interaction.", 10, _safe(lambda p: -op.rank((op.ts_sum(p["open"], 5) * op.ts_sum(p["returns"], 5)) - (op.ts_sum(p["open"], 5).shift(10) * op.ts_sum(p["returns"], 5).shift(10))))))
    add(FactorDef("alpha101_009", "Alpha#9", "alpha101", "trend", "Signed close delta conditioned on recent delta range.", 5, _safe(lambda p: op.delta(p["close"], 1).where(op.ts_min(op.delta(p["close"], 1), 5) > 0, (-op.delta(p["close"], 1)).where(op.ts_max(op.delta(p["close"], 1), 5) < 0, -op.delta(p["close"], 1))))))
    add(FactorDef("alpha101_012", "Alpha#12", "alpha101", "volume-price", "Volume delta sign times negative close delta.", 1, _safe(lambda p: op.sign(op.delta(p["volume"], 1)) * -op.delta(p["close"], 1))))
    add(FactorDef("alpha101_013", "Alpha#13", "alpha101", "volume-price", "Negative rank of close-volume covariance.", 5, _safe(lambda p: -op.rank(op.covariance(op.rank(p["close"]), op.rank(p["volume"]), 5)))))
    add(FactorDef("alpha101_018", "Alpha#18", "alpha101", "reversal", "Ranked blend of volatility, close-open move, and close autocorrelation.", 10, _safe(lambda p: -op.rank(op.stddev((p["close"] - p["open"]).abs(), 5) + (p["close"] - p["open"]) + op.correlation(p["close"], p["open"], 10)))))
    add(FactorDef("alpha101_019", "Alpha#19", "alpha101", "reversal", "Price reversal scaled by recent return sum.", 7, _safe(lambda p: -op.sign((p["close"] - p["close"].shift(7)) + op.delta(p["close"], 7)) * (1 + op.rank(1 + op.ts_sum(p["returns"], 250))))))
    add(FactorDef("alpha101_023", "Alpha#23", "alpha101", "reversal", "Negative high delta when high is above average.", 20, _safe(lambda p: (-op.delta(p["high"], 2)).where(op.sma(p["high"], 20) < p["high"], 0.0))))
    add(FactorDef("alpha101_024", "Alpha#24", "alpha101", "trend", "Conditional long-run mean reversion.", 100, _safe(lambda p: (-(p["close"] - op.ts_min(p["close"], 100))).where(op.delta(op.sma(p["close"], 100), 100) / p["close"].shift(100) <= 0.05, -op.delta(p["close"], 3)))))
    add(FactorDef("alpha101_026", "Alpha#26", "alpha101", "volume-price", "Negative max correlation of volume rank and high rank.", 8, _safe(lambda p: -op.ts_max(op.correlation(op.ts_rank(p["volume"], 5), op.ts_rank(p["high"], 5), 5), 3))))
    add(FactorDef("alpha101_028", "Alpha#28", "alpha101", "mean-reversion", "Ranked average of volume-price correlation and price range location.", 20, _safe(lambda p: op.scale(op.correlation(_adv(p, 20), p["low"], 5) + ((p["high"] + p["low"]) / 2 - p["close"])))))
    add(FactorDef("alpha101_032", "Alpha#32", "alpha101", "mean-reversion", "Mean reversion plus price-vwap proxy correlation.", 20, _safe(lambda p: op.scale(op.sma(p["close"], 7) - p["close"]) + 20 * op.scale(op.correlation(p["vwap"], p["close"].shift(5), 230)))))
    add(FactorDef("alpha101_033", "Alpha#33", "alpha101", "reversal", "Rank of open-to-close reversal.", 1, _safe(lambda p: op.rank(-(1 - p["open"] / p["close"])))))
    add(FactorDef("alpha101_034", "Alpha#34", "alpha101", "reversal", "Ranked volatility compression and close delta reversal.", 5, _safe(lambda p: op.rank((1 - op.rank(op.stddev(p["returns"], 2) / op.stddev(p["returns"], 5).replace(0, np.nan))) + (1 - op.rank(op.delta(p["close"], 1)))))))
    add(FactorDef("alpha101_035", "Alpha#35", "alpha101", "volume-price", "Product of volume rank, price range rank, and return rank.", 32, _safe(lambda p: op.ts_rank(p["volume"], 32) * (1 - op.ts_rank(p["close"] + p["high"] - p["low"], 16)) * (1 - op.ts_rank(p["returns"], 32)))))
    add(FactorDef("alpha101_040", "Alpha#40", "alpha101", "volume-price", "Negative high-volume correlation scaled by high volatility rank.", 10, _safe(lambda p: -op.rank(op.stddev(p["high"], 10)) * op.correlation(p["high"], p["volume"], 10))))
    add(FactorDef("alpha101_043", "Alpha#43", "alpha101", "volume-price", "Volume acceleration times negative close delta rank.", 20, _safe(lambda p: op.ts_rank(p["volume"] / op.sma(p["volume"], 20), 20) * op.ts_rank(-op.delta(p["close"], 7), 8))))
    add(FactorDef("alpha101_044", "Alpha#44", "alpha101", "volume-price", "Negative low-volume correlation.", 6, _safe(lambda p: -op.correlation(p["high"], op.rank(p["volume"]), 6))))
    add(FactorDef("alpha101_045", "Alpha#45", "alpha101", "volume-price", "Negative product of price mean rank and volume-price correlation.", 15, _safe(lambda p: -op.rank(op.sma(p["close"].shift(5), 20)) * op.correlation(p["close"], p["volume"], 2) * op.rank(op.correlation(op.ts_sum(p["close"], 5), op.ts_sum(p["close"], 20), 2)))))
    add(FactorDef("alpha101_049", "Alpha#49", "alpha101", "trend", "Conditional close delta reversal.", 20, _safe(lambda p: (-op.delta(p["close"], 1)).where((op.delta(p["close"], 20) - op.delta(p["close"], 10)) / 10 < -0.1, 1.0))))
    add(FactorDef("alpha101_051", "Alpha#51", "alpha101", "trend", "Conditional close delta reversal variant.", 20, _safe(lambda p: (-op.delta(p["close"], 1)).where((op.delta(p["close"], 20) - op.delta(p["close"], 10)) / 10 < -0.05, 1.0))))
    add(FactorDef("alpha101_053", "Alpha#53", "alpha101", "intraday", "Negative change in close location value.", 9, _safe(lambda p: -op.delta(((p["close"] - p["low"]) - (p["high"] - p["close"])) / (p["close"] - p["low"]).replace(0, np.nan), 9))))
    add(FactorDef("alpha101_054", "Alpha#54", "alpha101", "intraday", "Open-close reversal normalized by range.", 1, _safe(lambda p: -((p["low"] - p["close"]) * p["open"].pow(5)) / ((p["low"] - p["high"]).replace(0, np.nan) * p["close"].pow(5)))))
    add(FactorDef("alpha101_101", "Alpha#101", "alpha101", "intraday", "Close location in daily range using typical-price VWAP proxy family data.", 1, _safe(lambda p: (p["close"] - p["open"]) / (p["high"] - p["low"]).replace(0, np.nan))))
    return f


def _gtja191() -> list[FactorDef]:
    return [
        FactorDef("gtja191_001", "GTJA#1", "gtja191", "volume-price", "Negative rank correlation between log-volume change and intraday return.", 6, _safe(lambda p: -op.correlation(op.rank(op.delta(op.log(p["volume"]), 1)), op.rank((p["close"] - p["open"]) / p["open"]), 6))),
        FactorDef("gtja191_002", "GTJA#2", "gtja191", "intraday", "Negative delta of close-location value.", 1, _safe(lambda p: -op.delta(((p["close"] - p["low"]) - (p["high"] - p["close"])) / (p["high"] - p["low"]).replace(0, np.nan), 1))),
        FactorDef("gtja191_004", "GTJA#4", "gtja191", "trend", "Close relative to trailing mean and volatility bands.", 8, _safe(lambda p: ((p["close"] > op.sma(p["close"], 8)) & (p["close"] > op.sma(p["close"], 2))).astype(float) - ((p["close"] < op.sma(p["close"], 8)) & (p["close"] < op.sma(p["close"], 2))).astype(float))),
        FactorDef("gtja191_006", "GTJA#6", "gtja191", "volume-price", "Negative open-volume correlation.", 10, _safe(lambda p: -op.correlation(p["open"], p["volume"], 10))),
        FactorDef("gtja191_012", "GTJA#12", "gtja191", "momentum", "Ranked open-vwap proxy gap times absolute close delta.", 10, _safe(lambda p: op.sign(p["vwap"] - p["open"]) * -op.rank((p["open"] - op.sma(p["vwap"], 10)).abs()) * op.rank(op.delta(p["close"], 1).abs()))),
        FactorDef("gtja191_014", "GTJA#14", "gtja191", "reversal", "Negative five-session close delta.", 5, _safe(lambda p: -op.delta(p["close"], 5))),
        FactorDef("gtja191_018", "GTJA#18", "gtja191", "momentum", "Close divided by five-session lag.", 5, _safe(lambda p: p["close"] / p["close"].shift(5))),
        FactorDef("gtja191_020", "GTJA#20", "gtja191", "momentum", "Six-session percentage price change.", 6, _safe(lambda p: (p["close"] - p["close"].shift(6)) / p["close"].shift(6) * 100)),
        FactorDef("gtja191_024", "GTJA#24", "gtja191", "trend", "Close delta relative to trailing mean.", 5, _safe(lambda p: op.sma(op.delta(p["close"], 5), 5))),
        FactorDef("gtja191_028", "GTJA#28", "gtja191", "mean-reversion", "Close location against smoothed range.", 9, _safe(lambda p: 3 * op.sma((p["close"] - op.ts_min(p["low"], 9)) / (op.ts_max(p["high"], 9) - op.ts_min(p["low"], 9)).replace(0, np.nan) * 100, 3) - 2 * op.sma(op.sma((p["close"] - op.ts_min(p["low"], 9)) / (op.ts_max(p["high"], 9) - op.ts_min(p["low"], 9)).replace(0, np.nan) * 100, 3), 3))),
        FactorDef("gtja191_031", "GTJA#31", "gtja191", "reversal", "Ranked close delta reversal.", 12, _safe(lambda p: op.rank(op.rank(op.rank(-op.rank(op.delta(p["close"], 10))))))),
        FactorDef("gtja191_034", "GTJA#34", "gtja191", "volatility", "Volatility compression rank plus return reversal rank.", 5, _safe(lambda p: op.rank(1 - op.rank(op.stddev(p["returns"], 2) / op.stddev(p["returns"], 5).replace(0, np.nan))) + op.rank(1 - op.rank(op.delta(p["close"], 1))))),
        FactorDef("gtja191_046", "GTJA#46", "gtja191", "trend", "Blend of short and medium moving averages versus close.", 24, _safe(lambda p: (op.sma(p["close"], 3) + op.sma(p["close"], 6) + op.sma(p["close"], 12) + op.sma(p["close"], 24)) / (4 * p["close"]))),
        FactorDef("gtja191_053", "GTJA#53", "gtja191", "intraday", "Count of close above prior close over trailing 12 sessions.", 12, _safe(lambda p: op.ts_sum((p["close"] > p["close"].shift(1)).astype(float), 12))),
    ]


FACTOR_REGISTRY: list[FactorDef] = _academic() + _alpha101() + _gtja191()
