from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.alpha_zoo.factors import FACTOR_REGISTRY
from backend.auth.deps import get_current_user
from backend.models import User
from backend.research_autopilot.schemas import HypothesisSpec
from backend.research_autopilot.service import (
    create_hypothesis,
    get_hypothesis,
    list_hypotheses,
    run_hypothesis,
    run_pipeline,
)

router = APIRouter(prefix="/api/research-autopilot")


def _validate_factor(spec: HypothesisSpec) -> None:
    if spec.signal.kind != "alpha_factor":
        return
    factor_id = spec.signal.factor_id or "momentum_12_1"
    if not any(factor.id == factor_id for factor in FACTOR_REGISTRY):
        raise HTTPException(status_code=404, detail="unknown factor_id")


def _validate_universe(spec: HypothesisSpec) -> None:
    if len(spec.universe) < 2:
        raise HTTPException(status_code=400, detail="universe must contain at least two symbols")


@router.post("/run")
async def run_ad_hoc(spec: HypothesisSpec, current_user: User = Depends(get_current_user)) -> dict:
    _validate_factor(spec)
    _validate_universe(spec)
    return await run_pipeline(spec)


@router.post("/hypotheses")
async def create(spec: HypothesisSpec, current_user: User = Depends(get_current_user)) -> dict:
    _validate_factor(spec)
    _validate_universe(spec)
    return create_hypothesis(spec, str(current_user.id))


@router.get("/hypotheses")
async def list_for_user(current_user: User = Depends(get_current_user)) -> dict:
    return {"hypotheses": list_hypotheses(str(current_user.id))}


@router.get("/hypotheses/{hid}")
async def get_one(hid: str, current_user: User = Depends(get_current_user)) -> dict:
    return get_hypothesis(hid, str(current_user.id))


@router.post("/hypotheses/{hid}/run")
async def run_saved(hid: str, current_user: User = Depends(get_current_user)) -> dict:
    return await run_hypothesis(hid, str(current_user.id))
