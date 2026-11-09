from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

IndicatorType = Literal[
    "sma",
    "ema",
    "rsi",
    "macd",
    "bbands",
    "atr",
    "stdev",
    "highest",
    "lowest",
    "supertrend",
]
OperandKind = Literal["indicator", "price", "const"]
RuleOp = Literal[
    "cross_above",
    "cross_below",
    ">",
    "<",
    ">=",
    "<=",
    "==",
    "rising",
    "falling",
]
PriceRef = Literal["open", "high", "low", "close", "hl2", "hlc3"]


class Operand(BaseModel):
    """A value used by a strategy rule."""

    kind: OperandKind
    ref: str = ""
    value: float | None = None

    @model_validator(mode="after")
    def validate_operand(self) -> Operand:
        """Ensure each operand kind has enough data to be rendered."""
        if self.kind == "price" and self.ref not in {"open", "high", "low", "close", "hl2", "hlc3"}:
            raise ValueError("price operand ref must be one of open/high/low/close/hl2/hlc3")
        if self.kind == "indicator" and not self.ref:
            raise ValueError("indicator operand requires ref")
        if self.kind == "const" and self.value is None:
            raise ValueError("const operand requires value")
        return self


class Rule(BaseModel):
    """A boolean rule. Rules in the same list are AND-combined."""

    left: Operand
    op: RuleOp
    right: Operand | None = None

    @model_validator(mode="after")
    def validate_rule(self) -> Rule:
        """Require a right operand except for unary trend checks."""
        if self.op not in {"rising", "falling"} and self.right is None:
            raise ValueError(f"rule op {self.op!r} requires right operand")
        return self


class Indicator(BaseModel):
    """Indicator declaration available to operands by id."""

    id: str
    type: IndicatorType
    params: dict[str, Any] = Field(default_factory=dict)
    source: str = "close"

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        """Limit sources to price series supported by the exporters."""
        if value not in {"open", "high", "low", "close", "hl2", "hlc3"}:
            raise ValueError("indicator source must be one of open/high/low/close/hl2/hlc3")
        return value


class Risk(BaseModel):
    """Position sizing and bracket risk controls."""

    stop_pct: float | None = None
    take_pct: float | None = None
    qty_pct: float = 100


class StrategySpec(BaseModel):
    """Canonical strategy definition used by all code exporters."""

    name: str
    timeframe: str = "1D"
    indicators: list[Indicator]
    entry_long: list[Rule]
    exit_long: list[Rule] = Field(default_factory=list)
    entry_short: list[Rule] = Field(default_factory=list)
    exit_short: list[Rule] = Field(default_factory=list)
    risk: Risk = Field(default_factory=Risk)
    notes: str = ""

    @field_validator("indicators")
    @classmethod
    def validate_unique_indicator_ids(cls, indicators: list[Indicator]) -> list[Indicator]:
        """Reject duplicate indicator ids before rules bind to them."""
        ids = [indicator.id for indicator in indicators]
        duplicates = sorted({indicator_id for indicator_id in ids if ids.count(indicator_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate indicator id(s): {', '.join(duplicates)}")
        return indicators

    @model_validator(mode="after")
    def validate_indicator_references(self, info: ValidationInfo) -> StrategySpec:
        """Ensure indicator operands reference declared ids."""
        known = {indicator.id for indicator in self.indicators}
        missing: list[str] = []
        for rules in (self.entry_long, self.exit_long, self.entry_short, self.exit_short):
            for rule in rules:
                for operand in (rule.left, rule.right):
                    if operand and operand.kind == "indicator" and operand.ref not in known:
                        missing.append(operand.ref)
        if missing:
            missing_ids = ", ".join(sorted(set(missing)))
            raise ValueError(f"operand references unknown indicator id(s): {missing_ids}")
        return self
