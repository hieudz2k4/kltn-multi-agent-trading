from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from backend.strategy_export.service import generate, list_presets

router = APIRouter()


@router.get("/strategy-export/presets")
async def strategy_export_presets() -> dict[str, list[dict[str, Any]]]:
    """Return built-in strategy export presets."""
    return list_presets()


@router.post("/strategy-export/generate")
async def strategy_export_generate(
    spec: dict[str, Any] = Body(...),
    format: str = Body(...),
) -> dict[str, Any]:
    """Generate strategy code from a canonical spec."""
    try:
        return generate(spec, format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
