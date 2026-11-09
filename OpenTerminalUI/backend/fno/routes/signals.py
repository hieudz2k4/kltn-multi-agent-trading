from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from backend.fno.services.signals import get_option_chain_signals

router = APIRouter()


@router.get("/fno/signals/{symbol}")
async def get_fno_signals(
    symbol: str,
    market: str | None = Query(default="IN"),
    expiry: str | None = Query(default=None),
) -> dict[str, Any]:
    return await get_option_chain_signals(symbol, market=market, expiry=expiry)

