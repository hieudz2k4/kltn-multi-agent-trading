from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShadowReportRequest(BaseModel):
    """Ad-hoc trade payload for shadow-account analysis."""

    trades: list[dict[str, Any]] = Field(default_factory=list)
    min_samples: int = Field(default=4, ge=1, le=100)
