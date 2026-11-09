from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.alpha_zoo.evaluate import _build_panels
from backend.api.deps import get_db, get_unified_fetcher
from backend.api.routes.chart import _parse_yahoo_chart
from backend.research_autopilot.attribution import attribute
from backend.research_autopilot.backtest import run_backtest
from backend.research_autopilot.models import ResearchAutopilotHypothesis, ResearchAutopilotRun
from backend.research_autopilot.schemas import HypothesisSpec
from backend.research_autopilot.signals import build_signal_panel
from backend.research_autopilot.verdict import evaluate
from backend.robustness.scorecard import compute_robustness


def _db_session() -> Session:
    generator = get_db()
    db = next(generator)
    setattr(db, "_research_autopilot_generator", generator)
    return db


def _close_db(db: Session) -> None:
    generator = getattr(db, "_research_autopilot_generator", None)
    if generator is not None:
        try:
            next(generator)
        except StopIteration:
            pass
    else:
        db.close()


def _safe_dump(spec: HypothesisSpec) -> dict:
    return spec.model_dump(mode="json")


def _serialize_hypothesis(row: ResearchAutopilotHypothesis) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "statement": row.statement,
        "spec": row.spec_json,
        "status": row.status,
        "verdict": row.verdict_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_run(row: ResearchAutopilotRun) -> dict:
    result = dict(row.result_json or {})
    result.setdefault("run_id", row.id)
    result.setdefault("hypothesis_id", row.hypothesis_id)
    return {
        "id": row.id,
        "hypothesis_id": row.hypothesis_id,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "result": result,
    }


def _benchmark_curve(returns: pd.Series, index: pd.Index) -> list[dict[str, float | str]]:
    aligned = returns.reindex(index).fillna(0.0)
    equity = (1.0 + aligned).cumprod()
    return [{"date": pd.Timestamp(date).strftime("%Y-%m-%d"), "value": float(value)} for date, value in equity.items()]


async def _fetch_symbol(symbol: str, range_str: str) -> tuple[str, pd.DataFrame]:
    fetcher = await get_unified_fetcher()
    raw = await fetcher.fetch_history(symbol, range_str=range_str, interval="1d")
    frame = _parse_yahoo_chart(raw if isinstance(raw, dict) else {})
    return symbol, frame


def _has_enough_history(frame: pd.DataFrame) -> bool:
    return isinstance(frame, pd.DataFrame) and not frame.empty and len(frame) >= 80


async def run_pipeline(spec: HypothesisSpec) -> dict:
    """Run the full deterministic hypothesis research loop."""

    run_id = str(uuid4())
    symbols = list(dict.fromkeys([symbol.strip().upper() for symbol in spec.universe if symbol.strip()]))
    if len(symbols) < 2:
        raise HTTPException(status_code=400, detail="universe must contain at least two symbols")

    fetched = await asyncio.gather(*[_fetch_symbol(symbol, spec.range) for symbol in symbols], return_exceptions=True)
    frames: dict[str, pd.DataFrame] = {}
    missing: list[str] = []
    for item in fetched:
        if isinstance(item, Exception):
            continue
        symbol, frame = item
        if _has_enough_history(frame):
            frames[symbol] = frame
        else:
            missing.append(symbol)
    missing.extend([symbol for symbol in symbols if symbol not in frames and symbol not in missing])

    coverage = {"requested": len(symbols), "resolved": len(frames), "missing": missing}
    if len(frames) < 2:
        empty_backtest = run_backtest(pd.DataFrame(), pd.DataFrame(), rebalance_days=spec.rebalance_days, top_quantile=spec.top_quantile, long_short=spec.long_short)
        robustness = compute_robustness([], periods_per_year=252, seed=7)
        attribution = attribute([], None, [])
        verdict = evaluate(empty_backtest["metrics"], robustness, attribution, spec.acceptance.model_dump())
        return {
            "run_id": run_id,
            "hypothesis_id": None,
            "coverage": coverage,
            "backtest": {
                "as_of": None,
                "bars": 0,
                "rebalance_days": spec.rebalance_days,
                "long_short": spec.long_short,
                "metrics": empty_backtest["metrics"],
                "equity_curve": [],
                "benchmark_curve": [],
            },
            "attribution": attribution,
            "robustness": robustness,
            "verdict": verdict,
            "signal": spec.signal.model_dump(mode="json"),
            "universe": symbols,
        }

    panels = _build_panels(frames)
    signal_panel = build_signal_panel(spec.signal, panels)
    long_short = bool(spec.long_short and spec.signal.direction == "long_short")
    backtest = run_backtest(
        panels["close"],
        signal_panel,
        rebalance_days=spec.rebalance_days,
        top_quantile=spec.top_quantile,
        long_short=long_short,
    )

    benchmark_returns: pd.Series | None = None
    if spec.benchmark:
        try:
            _, benchmark_frame = await _fetch_symbol(spec.benchmark, spec.range)
            if _has_enough_history(benchmark_frame):
                benchmark_returns = benchmark_frame["Close"].astype(float).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        except Exception:
            benchmark_returns = None

    dates = panels["close"].index
    benchmark_values = benchmark_returns.reindex(dates).fillna(0.0).to_list() if benchmark_returns is not None else None
    attribution = attribute(backtest["daily_returns"], benchmark_values, dates)
    robustness = compute_robustness(backtest["daily_returns"], periods_per_year=252, seed=7)
    verdict = evaluate(backtest["metrics"], robustness, attribution, spec.acceptance.model_dump())
    benchmark_curve = _benchmark_curve(benchmark_returns, dates) if benchmark_returns is not None else []
    as_of = pd.Timestamp(dates.max()).strftime("%Y-%m-%d") if len(dates) else None
    return {
        "run_id": run_id,
        "hypothesis_id": None,
        "coverage": coverage,
        "backtest": {
            "as_of": as_of,
            "bars": int(backtest["bars"]),
            "rebalance_days": spec.rebalance_days,
            "long_short": long_short,
            "metrics": backtest["metrics"],
            "equity_curve": backtest["equity_curve"],
            "benchmark_curve": benchmark_curve,
        },
        "attribution": attribution,
        "robustness": robustness,
        "verdict": verdict,
        "signal": spec.signal.model_dump(mode="json"),
        "universe": symbols,
    }


def create_hypothesis(spec: HypothesisSpec, user_id: str) -> dict:
    """Persist a hypothesis for a user."""

    if len(spec.universe) < 2:
        raise HTTPException(status_code=400, detail="universe must contain at least two symbols")
    db = _db_session()
    try:
        row = ResearchAutopilotHypothesis(
            user_id=user_id,
            statement=spec.statement,
            spec_json=_safe_dump(spec),
            status="created",
            verdict_json={},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _serialize_hypothesis(row)
    finally:
        _close_db(db)


def list_hypotheses(user_id: str) -> list[dict]:
    """List persisted hypotheses for a user."""

    db = _db_session()
    try:
        rows = (
            db.query(ResearchAutopilotHypothesis)
            .filter(ResearchAutopilotHypothesis.user_id == user_id)
            .order_by(ResearchAutopilotHypothesis.created_at.desc())
            .all()
        )
        return [_serialize_hypothesis(row) for row in rows]
    finally:
        _close_db(db)


def get_hypothesis(hypothesis_id: str, user_id: str | None = None) -> dict:
    """Return a hypothesis with persisted runs."""

    db = _db_session()
    try:
        query = db.query(ResearchAutopilotHypothesis).filter(ResearchAutopilotHypothesis.id == hypothesis_id)
        if user_id is not None:
            query = query.filter(ResearchAutopilotHypothesis.user_id == user_id)
        row = query.first()
        if row is None:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        runs = (
            db.query(ResearchAutopilotRun)
            .filter(ResearchAutopilotRun.hypothesis_id == row.id)
            .order_by(ResearchAutopilotRun.created_at.desc())
            .all()
        )
        return {"hypothesis": _serialize_hypothesis(row), "runs": [_serialize_run(run) for run in runs]}
    finally:
        _close_db(db)


async def run_hypothesis(hypothesis_id: str, user_id: str | None = None) -> dict:
    """Run and persist a stored hypothesis."""

    db = _db_session()
    try:
        query = db.query(ResearchAutopilotHypothesis).filter(ResearchAutopilotHypothesis.id == hypothesis_id)
        if user_id is not None:
            query = query.filter(ResearchAutopilotHypothesis.user_id == user_id)
        hypothesis = query.first()
        if hypothesis is None:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        spec = HypothesisSpec(**dict(hypothesis.spec_json or {}))
    finally:
        _close_db(db)

    result = await run_pipeline(spec)
    result["hypothesis_id"] = hypothesis_id
    run_id = str(result.get("run_id") or uuid4())
    result["run_id"] = run_id

    db = _db_session()
    try:
        query = db.query(ResearchAutopilotHypothesis).filter(ResearchAutopilotHypothesis.id == hypothesis_id)
        if user_id is not None:
            query = query.filter(ResearchAutopilotHypothesis.user_id == user_id)
        hypothesis = query.first()
        if hypothesis is None:
            raise HTTPException(status_code=404, detail="hypothesis not found")
        run = ResearchAutopilotRun(
            id=run_id,
            hypothesis_id=hypothesis_id,
            user_id=hypothesis.user_id,
            status="completed",
            result_json=result,
        )
        hypothesis.status = str((result.get("verdict") or {}).get("status") or "completed")
        hypothesis.verdict_json = dict(result.get("verdict") or {})
        db.add(run)
        db.commit()
        return result
    finally:
        _close_db(db)
