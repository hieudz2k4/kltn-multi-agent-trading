from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Insight:
    symbol: str
    direction: int            # +1 up, -1 down, 0 flat
    confidence: float = 0.5   # 0..1
    magnitude: float = 0.0    # expected return estimate (decimal)
    weight: float | None = None
    period_days: int = 21
