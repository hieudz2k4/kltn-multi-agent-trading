"""Data Contracts and Pydantic Schemas for Multi-Agent Trading System.

These schemas define the inter-agent communication, risk verification verdicts,
and MCP bridge interfaces (MT5 & TradingView).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategyBranch(str, Enum):
    CSR_PORTFOLIO = "CSR_PORTFOLIO"
    OPPORTUNISTIC_SMC = "OPPORTUNISTIC_SMC"


class OrderDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class SignalPayload(BaseModel):
    """Payload produced by Strategy Signal Generators (CSR or SMC)."""
    signal_id: str = Field(..., description="Unique UUID for this trading signal")
    strategy: StrategyBranch = Field(..., description="Source strategy branch")
    symbol: str = Field(..., description="Asset symbol (e.g., EURUSD, XAUUSD)")
    direction: OrderDirection = Field(..., description="Direction of order")
    timeframe: str = Field(..., description="Execution timeframe (e.g., M15, H1, H4)")
    entry_price: float = Field(..., description="Proposed entry price")
    stop_loss: float = Field(..., description="Calculated Stop Loss price")
    take_profit: float = Field(..., description="Calculated Take Profit price")
    risk_reward_ratio: float = Field(..., description="Reward / Risk ratio (min 2.0 for SMC)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Strategy specific features (OB, FVG, ROC score)")


class RiskVerdict(BaseModel):
    """Verdict rendered by the Adversarial Risk Gatekeeper Agent."""
    signal_id: str = Field(..., description="Reference signal ID")
    approved: bool = Field(..., description="True if passed all gates, False if VETOED")
    veto_reason: Optional[str] = Field(None, description="Detailed explanation if vetoed")
    veto_code: Optional[str] = Field(None, description="VETO_SWAP | VETO_SPREAD | VETO_EXPOSURE | VETO_RR | VETO_CIRCUIT")
    recommended_volume: float = Field(0.0, description="Normalized Lot Size (1R or 5% equity weight)")
    projected_net_exposure: float = Field(..., description="Resulting net exposure (|Long - Short| <= 5%)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderExecutionIntent(BaseModel):
    """Validated Order Payload dispatched to MT5 Bridge."""
    intent_id: str = Field(..., description="Unique execution intent UUID")
    signal_id: str = Field(..., description="Originating signal ID")
    symbol: str = Field(...)
    action: OrderDirection = Field(...)
    volume: float = Field(..., description="Lot size verified by Risk Gatekeeper")
    price: float = Field(...)
    sl: float = Field(...)
    tp: float = Field(...)
    magic_number: int = Field(..., description="1001 for CSR, 2001 for SMC")
    comment: str = Field(..., description="Order comment for tracking")


class CircuitBreakerState(BaseModel):
    """System-wide Circuit Breaker Monitor."""
    is_active: bool = Field(False, description="True if system trading is suspended")
    current_daily_drawdown_pct: float = Field(..., description="Current drawdown (Threshold: -3.0%)")
    consecutive_losses: int = Field(0, description="Consecutive losing cycles / trades")
    cooldown_until: Optional[datetime] = Field(None, description="Resume timestamp if cooling down")
    total_vetoes_today: int = Field(0, description="Count of veto interventions")


class MT5AccountSnapshot(BaseModel):
    """Real-time account state fetched via MT5 RPyC / FastMCP."""
    login: int
    balance: float
    equity: float
    margin: float
    free_margin: float
    profit: float
    positions_count: int
    net_exposure_pct: float
