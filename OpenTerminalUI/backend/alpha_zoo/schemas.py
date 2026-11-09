from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluateRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    factor_ids: list[str] | None = None
    zoo: str | None = None
    range: str = "1y"
    forward_days: int = 5
