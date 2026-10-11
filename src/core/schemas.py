"""Core data contracts and Pydantic schemas for the Multi-Agent Trading System.

Extends C4-Documentation/contracts/schemas.py with SMC-specific models:
- HTFBias, MarketStructure, POIZone, SMCSetup (Branch 2 — Opportunistic SMC)
- CSRSignal (Branch 1 — Cross-Sectional Ranking Portfolio)
- Shared: SignalPayload, RiskVerdict, OrderExecutionIntent, CircuitBreakerState
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StrategyBranch(str, Enum):
    CSR_PORTFOLIO = "CSR_PORTFOLIO"
    OPPORTUNISTIC_SMC = "OPPORTUNISTIC_SMC"


class OrderDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SystemMode(str, Enum):
    MODE_A = "A"   # Pure CSR Portfolio
    MODE_B = "B"   # Pure SMC Opportunistic
    MODE_C = "C"   # Hybrid 50/50


# ---------------------------------------------------------------------------
# Branch 2 — Multi-Asset Opportunistic SMC
# ---------------------------------------------------------------------------

class HTFBiasEnum(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"


class POIType(str, Enum):
    ORDER_BLOCK = "OB"
    FAIR_VALUE_GAP = "FVG"
    LIQUIDITY_SWEEP = "SWEEP"


class StructureType(str, Enum):
    BOS = "BOS"      # Break of Structure — trend continuation
    CHOCH = "CHOCH"  # Change of Character — trend reversal


class HTFBias(BaseModel):
    """Output of HTF Bias Analyzer Agent (H4/D1 trend analysis)."""
    symbol: str
    bias: HTFBiasEnum
    key_level: float = Field(..., description="Key S/R level defining the bias")
    swing_high: float = Field(..., description="Most recent confirmed swing high")
    swing_low: float = Field(..., description="Most recent confirmed swing low")
    reason: str = Field(..., description="Natural language explanation of bias")
    timeframe: str = Field("H4", description="Timeframe used for bias detection")
    timestamp: datetime = Field(default_factory=_utc_now)


class MarketStructure(BaseModel):
    """Output of Market Structure Agent (BOS/CHoCH detection on M15/H1)."""
    symbol: str
    structure_type: StructureType
    bos_level: float = Field(..., description="Price level of the BOS/CHoCH break")
    choch_level: float | None = Field(None, description="CHoCH invalidation level")
    swing_high: float
    swing_low: float
    entry_direction: OrderDirection = Field(..., description="Direction implied by structure")
    timeframe: str = Field("M15")
    timestamp: datetime = Field(default_factory=_utc_now)


class POIZone(BaseModel):
    """Output of POI & Liquidity Detector Agent."""
    symbol: str
    poi_type: POIType
    price_high: float = Field(..., description="Upper bound of the POI zone")
    price_low: float = Field(..., description="Lower bound of the POI zone")
    strength: int = Field(..., ge=1, le=5, description="Zone quality score 1-5")
    is_fresh: bool = Field(True, description="True if price has not yet returned to zone")
    is_swept: bool = Field(False, description="True if liquidity above/below was cleared")
    timeframe: str = Field("M15")
    timestamp: datetime = Field(default_factory=_utc_now)

    @property
    def midpoint(self) -> float:
        return (self.price_high + self.price_low) / 2


class SMCSetup(BaseModel):
    """Complete SMC trade setup assembled by the Position Sizer Agent."""
    symbol: str
    htf_bias: HTFBiasEnum
    structure_type: StructureType
    poi_type: POIType
    direction: OrderDirection
    entry: float
    stop_loss: float
    take_profit: float
    lot_size: float = Field(..., gt=0)
    risk_reward_ratio: float = Field(..., description="Must be >= 2.0 to pass VETO")
    risk_pct: float = Field(1.0, description="Risk as % of equity (fixed 1R)")
    pip_distance_sl: float = Field(..., description="Distance from entry to SL in pips")
    is_valid: bool = Field(..., description="False if R:R < 2.0 — will be auto-rejected")
    timestamp: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def validate_rr(self) -> "SMCSetup":
        if self.risk_reward_ratio < 2.0:
            self.is_valid = False
        return self


# ---------------------------------------------------------------------------
# Branch 1 — Cross-Sectional Ranking Portfolio (CSR)
# ---------------------------------------------------------------------------

class AssetScore(BaseModel):
    """Factor score for a single asset computed by Factor Scoring Engine."""
    symbol: str
    roc_score: float = Field(..., description="Z-score of Rate of Change (M15/H1/H4)")
    rsi_score: float = Field(..., description="Z-score of RSI")
    trend_score: float = Field(..., description="Z-score of EMA trend alignment")
    atr_score: float = Field(..., description="Z-score of ATR (inverted)")
    composite_score: float = Field(..., description="Weighted composite Z-score")


class CSRSignal(BaseModel):
    """Portfolio rebalancing signal from the Portfolio Allocator Agent."""
    rebalance_id: str = Field(..., description="Unique UUID for this rebalance cycle")
    long_basket: list[AssetScore] = Field(..., description="Top 10 assets to BUY")
    short_basket: list[AssetScore] = Field(..., description="Bottom 10 assets to SELL")
    weight_per_position: float = Field(0.05, description="Fixed 5% of equity per position")
    net_exposure_pct: float = Field(..., description="|long_weight - short_weight| <= 5%")
    rebalance_timeframe: str = Field("4H", description="4H or Daily 00:00 UTC")
    timestamp: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Shared — Signal Payload (inter-agent communication)
# ---------------------------------------------------------------------------

class SignalPayload(BaseModel):
    """Unified payload from either strategy branch to Risk Gatekeeper."""
    signal_id: str = Field(..., description="Unique UUID for this trading signal")
    strategy: StrategyBranch
    symbol: str
    direction: OrderDirection
    timeframe: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float = Field(..., description="Min 2.0 for SMC; N/A for CSR")
    lot_size: float
    timestamp: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared — Risk Gatekeeper Verdict
# ---------------------------------------------------------------------------

class VetoCode(str, Enum):
    VETO_SPREAD = "VETO_SPREAD"       # Spread > 1.5x avg
    VETO_SWAP = "VETO_SWAP"           # Swap cost too negative
    VETO_RR = "VETO_RR"               # R:R < 2.0 (SMC only)
    VETO_EXPOSURE = "VETO_EXPOSURE"   # Net exposure > 5% (CSR)
    VETO_CIRCUIT = "VETO_CIRCUIT"     # Circuit Breaker active


class RiskVerdict(BaseModel):
    """Verdict from the Adversarial Risk Gatekeeper Agent."""
    signal_id: str
    approved: bool
    veto_reason: str | None = None
    veto_code: VetoCode | None = None
    recommended_volume: float = Field(0.0)
    projected_net_exposure: float = Field(..., description="|Long - Short| resulting exposure")
    timestamp: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# Shared — Execution Intent
# ---------------------------------------------------------------------------

class OrderExecutionIntent(BaseModel):
    """Validated order payload dispatched to MT5 Bridge after VETO clearance."""
    intent_id: str
    signal_id: str
    symbol: str
    action: OrderDirection
    volume: float = Field(..., gt=0)
    price: float
    sl: float
    tp: float
    magic_number: int = Field(..., description="1001=CSR | 2001=SMC")
    comment: str


# ---------------------------------------------------------------------------
# Shared — Circuit Breaker State
# ---------------------------------------------------------------------------

class CircuitBreakerState(BaseModel):
    """System-wide Circuit Breaker monitor."""
    is_active: bool = Field(False, description="True = all trading suspended")
    current_daily_drawdown_pct: float = Field(..., description="Threshold: -3.0%")
    consecutive_losses: int = Field(0, description="3 consecutive losses → 24h cooldown")
    cooldown_until: datetime | None = None
    total_vetoes_today: int = 0
    halt_reason: str | None = None


# ---------------------------------------------------------------------------
# Shared — MT5 Account Snapshot
# ---------------------------------------------------------------------------

class MT5AccountSnapshot(BaseModel):
    """Real-time account state polled from MT5 via RPyC/FastMCP."""
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    positions_count: int
    net_exposure_pct: float = Field(..., description="|Long lot - Short lot| / total lot")
