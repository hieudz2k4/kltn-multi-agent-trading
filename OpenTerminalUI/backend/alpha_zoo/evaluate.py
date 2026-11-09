from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd

from backend.alpha_zoo.factors import FACTOR_REGISTRY, FactorDef
from backend.alpha_zoo.schemas import EvaluateRequest
from backend.api.deps import get_unified_fetcher
from backend.api.routes.chart import _parse_yahoo_chart


def _factor_payload(factor: FactorDef) -> dict[str, Any]:
    return {
        "id": factor.id,
        "name": factor.name,
        "zoo": factor.zoo,
        "category": factor.category,
        "description": factor.description,
        "window": factor.window,
    }


async def list_factors() -> dict[str, Any]:
    zoos_meta = {
        "academic": ("Academic Factors", "Empirical asset-pricing literature"),
        "alpha101": ("101 Formulaic Alphas", "Kakushadze 2016"),
        "gtja191": ("GTJA 191 Alphas", "Guotai Junan 191 formulaic alphas"),
    }
    zoos = []
    for zoo, (name, source) in zoos_meta.items():
        zoos.append({"id": zoo, "name": name, "source": source, "count": sum(f.zoo == zoo for f in FACTOR_REGISTRY)})
    return {"zoos": zoos, "factors": [_factor_payload(factor) for factor in FACTOR_REGISTRY]}


def _zscore_row(row: pd.Series) -> pd.Series:
    valid = row.dropna()
    if len(valid) < 2:
        return row * np.nan
    std = valid.std(ddof=0)
    if not np.isfinite(std) or std == 0:
        return row * 0.0
    return (row - valid.mean()) / std


def _corr_rows(a: pd.DataFrame, b: pd.DataFrame, method: str) -> pd.Series:
    vals: list[float] = []
    idx: list[Any] = []
    for date in a.index.intersection(b.index):
        joined = pd.concat([a.loc[date], b.loc[date]], axis=1).dropna()
        idx.append(date)
        if len(joined) < 3 or joined.iloc[:, 0].nunique() < 2 or joined.iloc[:, 1].nunique() < 2:
            vals.append(np.nan)
            continue
        vals.append(float(joined.iloc[:, 0].corr(joined.iloc[:, 1], method=method)))
    return pd.Series(vals, index=idx, dtype=float)


def _round_or_none(value: float | int | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return round(float(value), 4)


def _select_factors(req: EvaluateRequest) -> list[FactorDef]:
    factors = FACTOR_REGISTRY
    if req.zoo:
        factors = [factor for factor in factors if factor.zoo == req.zoo]
    if req.factor_ids:
        selected = set(req.factor_ids)
        factors = [factor for factor in factors if factor.id in selected]
    return factors[:60]


def _min_required_rows(forward_days: int) -> int:
    return max(int(forward_days) + 30, 40)


def _has_enough_rows(frame: pd.DataFrame, forward_days: int) -> bool:
    return not frame.empty and len(frame) >= _min_required_rows(forward_days)


def _build_panels(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    fields = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    panels = {
        key: pd.concat({symbol: frame[col] for symbol, frame in frames.items()}, axis=1, join="inner").sort_index()
        for key, col in fields.items()
    }
    panels["returns"] = panels["close"].pct_change()
    panels["vwap"] = (panels["high"] + panels["low"] + panels["close"]) / 3.0
    return panels


def _evaluate_on_panels(
    panels: dict[str, pd.DataFrame],
    factors: list[FactorDef],
    forward_days: int,
) -> list[dict[str, Any]]:
    close = panels["close"]
    fwd = close.shift(-max(int(forward_days), 1)) / close - 1
    latest = close.index.max()
    results: list[dict[str, Any]] = []
    for factor in factors:
        try:
            factor_panel = factor.fn(panels)
            rank_ic_series = _corr_rows(factor_panel, fwd, "spearman").dropna()
            pearson_series = _corr_rows(factor_panel.apply(_zscore_row, axis=1), fwd.apply(_zscore_row, axis=1), "pearson").dropna()
            rank_ic = float(rank_ic_series.mean()) if len(rank_ic_series) else np.nan
            ic = float(pearson_series.mean()) if len(pearson_series) else np.nan
            std = float(rank_ic_series.std(ddof=1)) if len(rank_ic_series) > 1 else 0.0
            ir = float(rank_ic / std) if std and np.isfinite(rank_ic) else 0.0
            hit_rate = float((rank_ic_series > 0).mean()) if len(rank_ic_series) else np.nan
            if close.shape[1] < 3 or len(rank_ic_series) < 20:
                status = "insufficient"
            elif rank_ic <= -0.03:
                status = "reversed"
            elif abs(rank_ic) >= 0.03 and np.sign(rank_ic) == np.sign(ir):
                status = "alive"
            else:
                status = "dead"
            latest_values = factor_panel.loc[latest] if latest in factor_panel.index else pd.Series(index=close.columns, dtype=float)
            z_values = _zscore_row(latest_values.reindex(close.columns))
            values = {symbol: _round_or_none(z_values.get(symbol)) for symbol in close.columns}
            results.append(
                {
                    "factor_id": factor.id,
                    "name": factor.name,
                    "zoo": factor.zoo,
                    "category": factor.category,
                    "ic": _round_or_none(ic),
                    "ir": _round_or_none(ir),
                    "rank_ic": _round_or_none(rank_ic),
                    "hit_rate": _round_or_none(hit_rate),
                    "status": status,
                    "values": values,
                }
            )
        except Exception:
            results.append(
                {
                    "factor_id": factor.id,
                    "name": factor.name,
                    "zoo": factor.zoo,
                    "category": factor.category,
                    "ic": None,
                    "ir": None,
                    "rank_ic": None,
                    "hit_rate": None,
                    "status": "insufficient",
                    "values": {symbol: None for symbol in close.columns},
                }
            )
    return results


async def _fetch_symbol(symbol: str, range_str: str) -> tuple[str, pd.DataFrame]:
    fetcher = await get_unified_fetcher()
    raw = await fetcher.fetch_history(symbol, range_str=range_str, interval="1d")
    frame = _parse_yahoo_chart(raw if isinstance(raw, dict) else {})
    if frame.empty and symbol.upper().endswith((".NS", ".BO")):
        raw = await fetcher.fetch_history(symbol[:-3], range_str=range_str, interval="1d")
        frame = _parse_yahoo_chart(raw if isinstance(raw, dict) else {})
    return symbol, frame


async def evaluate(req: EvaluateRequest) -> dict[str, Any]:
    symbols = [str(symbol).strip() for symbol in req.symbols if str(symbol).strip()]
    factors = _select_factors(req)
    fetched = await asyncio.gather(*[_fetch_symbol(symbol, req.range) for symbol in symbols], return_exceptions=True)
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for item in fetched:
        if isinstance(item, Exception):
            continue
        symbol, frame = item
        if not _has_enough_rows(frame, req.forward_days):
            missing.append(symbol)
            continue
        frames[symbol] = frame
    missing.extend([symbol for symbol in symbols if symbol not in frames and symbol not in missing])
    if frames:
        panels = _build_panels(frames)
        results = _evaluate_on_panels(panels, factors, req.forward_days)
        as_of = panels["close"].index.max().strftime("%Y-%m-%d")
        resolved = list(panels["close"].columns)
    else:
        results = []
        as_of = None
        resolved = []
    return {
        "as_of": as_of,
        "symbols": resolved,
        "coverage": {"requested": len(symbols), "resolved": len(resolved), "missing": missing},
        "results": results,
    }
