from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from backend.services.fixed_income_service import FixedIncomeService, get_fixed_income_service

router = APIRouter(prefix="/api/fixed-income", tags=["fixed-income"])


class BondAnalyticsRequest(BaseModel):
    coupon_rate: float = Field(..., description="Annual coupon as decimal, e.g. 0.05")
    years_to_maturity: float = Field(..., gt=0)
    frequency: int = Field(2, ge=1, le=12)
    face_value: float = Field(100.0, gt=0)
    ytm: float | None = None
    price: float | None = None


@router.post("/bond-analytics")
async def bond_analytics(req: BondAnalyticsRequest):
    """Yield/price, duration, convexity, DV01 for a fixed-coupon bond."""
    from backend.core.bond_analytics import BondSpec, analytics
    if (req.ytm is None) == (req.price is None):
        raise HTTPException(status_code=422, detail="Provide exactly one of ytm or price.")
    spec = BondSpec(coupon_rate=req.coupon_rate, years_to_maturity=req.years_to_maturity,
                    frequency=req.frequency, face_value=req.face_value)
    try:
        return analytics(spec, ytm=req.ytm, price=req.price)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/yield-curve", response_model=Dict[str, Any])
async def get_yield_curve(
    service: FixedIncomeService = Depends(get_fixed_income_service)
):
    """Fetch current US Treasury yields."""
    data = await service.get_yield_curve()
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data

@router.get("/yield-curve/historical", response_model=Dict[str, Any])
async def get_historical_yield_curve(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    service: FixedIncomeService = Depends(get_fixed_income_service)
):
    """Fetch historical US Treasury yields for a specific date."""
    data = await service.get_historical_yield_curve(date)
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data

@router.get("/2s10s-spread-history", response_model=Dict[str, Any])
async def get_2s10s_history(
    service: FixedIncomeService = Depends(get_fixed_income_service)
):
    """Fetch 2-year vs 10-year Treasury yield spread history."""
    data = await service.get_2s10s_history()
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data
