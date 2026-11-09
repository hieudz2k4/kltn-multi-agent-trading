from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SignalSpec(BaseModel):
    """Configuration for a research signal."""

    kind: Literal["alpha_factor", "momentum"] = "alpha_factor"
    factor_id: str | None = None
    lookback_days: int = Field(default=126, ge=1, le=756)
    direction: Literal["long_only", "long_short"] = "long_short"


class AcceptanceCriteria(BaseModel):
    """Thresholds used to convert evidence into a verdict."""

    min_sharpe: float | None = None
    min_cagr: float | None = None
    max_drawdown: float | None = None
    min_psr: float | None = None
    min_hit_rate: float | None = None
    min_alpha: float | None = None


class HypothesisSpec(BaseModel):
    """Complete research hypothesis definition."""

    statement: str = Field(min_length=1, max_length=500)
    universe: list[str] = Field(max_length=25)
    benchmark: str | None = "SPY"
    signal: SignalSpec
    acceptance: AcceptanceCriteria = Field(default_factory=AcceptanceCriteria)
    range: str = "2y"
    rebalance_days: int = Field(default=5, ge=1, le=63)
    top_quantile: float = Field(default=0.3, ge=0.1, le=0.5)
    long_short: bool = True

    @field_validator("universe")
    @classmethod
    def normalize_universe(cls, value: list[str]) -> list[str]:
        symbols = [str(symbol).strip().upper() for symbol in value if str(symbol).strip()]
        deduped = list(dict.fromkeys(symbols))
        if len(deduped) > 25:
            raise ValueError("universe may contain at most 25 symbols")
        return deduped

    @field_validator("benchmark")
    @classmethod
    def normalize_benchmark(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None
