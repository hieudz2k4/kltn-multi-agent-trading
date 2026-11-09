from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.model_lab.service import get_model_lab_service
from backend.robustness.schemas import RobustnessAdhocRequest, RobustnessRequest
from backend.robustness.scorecard import compute_robustness

router = APIRouter(tags=["model-lab-robustness"])


@router.post("/model-lab/runs/{run_id}/robustness")
async def compute_run_robustness(run_id: str, payload: RobustnessRequest) -> dict[str, Any]:
    report = await get_model_lab_service().get_report(run_id=run_id, force_refresh=False)
    if report.get("status") != "succeeded":
        raise HTTPException(status_code=400, detail="Run must be completed")

    series = report.get("series") or {}
    equity_curve = series.get("equity_curve") or series.get("portfolio_equity") or []
    returns = equity_curve_to_returns(equity_curve)
    if len(returns) < 2:
        raise HTTPException(status_code=400, detail="insufficient equity data")

    return {"run_id": run_id, **compute_robustness(returns, **payload.model_dump())}


@router.post("/model-lab/robustness")
async def compute_adhoc_robustness(payload: RobustnessAdhocRequest) -> dict[str, Any]:
    if payload.returns is not None:
        returns = payload.returns
    elif payload.equity_curve is not None:
        returns = equity_curve_to_returns(payload.equity_curve)
    else:
        raise HTTPException(status_code=400, detail="one of returns or equity_curve is required")

    if len(returns) < 2:
        raise HTTPException(status_code=400, detail="insufficient equity data")

    params = payload.model_dump(exclude={"returns", "equity_curve"})
    return compute_robustness(returns, **params)


def equity_curve_to_returns(equity_curve: Sequence[dict[str, Any]]) -> list[float]:
    values: list[float] = []
    for point in equity_curve:
        if not isinstance(point, dict):
            continue
        raw_value = point.get("equity", point.get("value"))
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        values.append(value)

    returns: list[float] = []
    for previous, current in zip(values, values[1:], strict=False):
        if previous == 0:
            continue
        returns.append((current / previous) - 1.0)
    return returns
