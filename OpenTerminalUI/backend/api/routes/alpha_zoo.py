from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.alpha_zoo.evaluate import evaluate, list_factors
from backend.alpha_zoo.schemas import EvaluateRequest

router = APIRouter()


@router.get("/alpha-zoo/factors")
async def factors_route() -> dict:
    return await list_factors()


@router.post("/alpha-zoo/evaluate")
async def evaluate_route(req: EvaluateRequest) -> dict:
    symbols = [str(symbol).strip() for symbol in req.symbols if str(symbol).strip()]
    if not symbols or len(symbols) > 25:
        raise HTTPException(status_code=400, detail="symbols must contain 1 to 25 entries")
    if req.factor_ids and len(req.factor_ids) > 60:
        raise HTTPException(status_code=400, detail="factor_ids is capped at 60 entries")
    req.symbols = symbols
    return await evaluate(req)
