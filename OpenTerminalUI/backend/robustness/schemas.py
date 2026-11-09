from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class RobustnessRequest(BaseModel):
    num_trials: int = Field(default=1, ge=1, le=10000)
    bootstrap_paths: int = Field(default=2000, ge=100, le=20000)
    block_size: int = Field(default=10, ge=1, le=252)
    benchmark_sharpe: float = 0.0
    periods_per_year: int = Field(default=252, ge=1, le=366)
    seed: int | None = None


class RobustnessAdhocRequest(RobustnessRequest):
    returns: list[float] | None = None
    equity_curve: list[dict] | None = None

    @model_validator(mode="after")
    def require_returns_or_equity_curve(self) -> "RobustnessAdhocRequest":
        if self.returns is None and self.equity_curve is None:
            raise ValueError("one of returns or equity_curve is required")
        return self
