"""Data contracts and Pydantic schemas for the Hyperdash Data Pipeline."""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class SizeCohort(str, Enum):
    MICRO = "MICRO"
    SMALL = "SMALL"
    MID = "MID"
    WHALE = "WHALE"


class QualityTier(str, Enum):
    GOLD = "GOLD"
    PASS = "PASS"
    REJECT = "REJECT"


class SmoothnessTier(str, Enum):
    SMOOTH_LINEAR = "SMOOTH_LINEAR"
    MODERATE = "MODERATE"
    CHOPPY = "CHOPPY"


class StrategyTag(str, Enum):
    FUNDING_CARRY = "FUNDING_CARRY"
    GRID_MARTINGALE = "GRID_MARTINGALE"
    BREAKOUT_MOMENTUM = "BREAKOUT_MOMENTUM"
    TREND_DISCRETIONARY = "TREND_DISCRETIONARY"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Boundary cases: negative/zero (<1000 -> MICRO), [1000, 10000) -> SMALL,
# [10000, 100000) -> MID, >=100000 -> WHALE.
def infer_size_cohort(account_value: float) -> str:
    """Map account equity in USDC to its canonical Hyperdash size cohort."""
    if account_value < 1_000.0:
        return SizeCohort.MICRO.value
    if account_value < 10_000.0:
        return SizeCohort.SMALL.value
    if account_value < 100_000.0:
        return SizeCohort.MID.value
    return SizeCohort.WHALE.value


class TraderDiscoveryRecord(BaseModel):
    """Normalized trader discovery record persisted after Gate 0 screening."""

    address: str
    rank: int | None = None
    display_name: str | None = None
    account_value: float
    size_cohort: str
    net_pnl: float
    gross_pnl: float | None = None
    funding_pnl: float | None = None
    volume: float | None = None
    trade_count: int
    winning_trades: int | None = None
    losing_trades: int | None = None
    copy_score: float
    last_trade_at: int
    window: str
    discovered_at: int


class RejectedTraderRecord(BaseModel):
    """Audit record for a trader filtered out during Gate 0 screening."""

    address: str
    rejection_reasons: list[str]
    account_value: float
    net_pnl: float
    trade_count: int
    copy_score: float
    last_trade_at: int
    discovered_at: int


class RawFillRecord(BaseModel):
    """Single fill execution record from Hyperliquid L1 RPC userFills."""

    tid: int
    coin: str
    side: str
    px: float
    sz: float
    time: int
    fee: float
    closed_pnl: float
    dir: str


class EquityPoint(BaseModel):
    """Single timestamped equity observation from Hyperdash portfolioGraph."""

    timestamp: int
    equity_usd: float


class TraderProfileSnapshot(BaseModel):
    """Off-chain quantitative profile and L1 margin state for a single trader."""

    address: str
    display_name: str | None = None
    size_cohort: str
    perps_equity: float
    net_pnl: float
    funding_pnl: float = 0.0
    total_trades: int
    trades_30d: int
    winrate_30d: float
    winrate_all: float
    sharpe_all: float
    sharpe_90d: float
    sortino_30d: float
    drawdown_30d: float
    drawdown_90d: float
    drawdown_all: float
    copy_score: float
    account_value: float
    total_ntl_pos: float
    portfolio_graph: list[EquityPoint] = Field(default_factory=list)


class EnrichedTraderRecord(BaseModel):
    """Final enriched trader record exported to dataset_traders.parquet."""

    address: str
    size_cohort: str
    total_trades: int
    trades_30d: int
    win_rate: float
    profit_factor: float
    max_drawdown_30d: float
    max_drawdown_90d: float
    max_drawdown_all: float
    sharpe_ratio_all: float
    sharpe_ratio_90d: float
    sortino_ratio_30d: float
    calmar_ratio: float
    equity_r2: float
    equity_beta: float
    k_ratio: float
    effective_leverage: float
    avg_holding_sec: float
    funding_pnl_pct: float
    quality_tier: str
    smoothness_tier: str
    is_algo: bool
    strategy_tag: str


class CheckpointTask(BaseModel):
    """Per-wallet ingestion checkpoint status."""

    status: TaskStatus = TaskStatus.PENDING
    fills_count: int = 0
    retry_count: int = 0
    last_updated: int | None = None
    last_error: str | None = None


class CheckpointState(BaseModel):
    """Global ingestion queue checkpoint state persisted to checkpoint.json."""

    updated_at: str
    total_discovered: int
    completed_count: int
    failed_count: int
    tasks: dict[str, CheckpointTask] = Field(default_factory=dict)


class DiscoveryConfig(BaseModel):
    """Configuration parameters for the Discovery & Gate 0 worker."""

    window: str = "d30"
    explore_timeframe: str = "all"
    page_size: int = 50
    max_pages: int = 2
    min_copy_score: float = 60.0
    min_equity_usd: float = 1_000.0

    max_inactivity_days: int = 7
    discovered_output_path: Path = Path("data/traders_discovered.json")
    rejected_output_path: Path = Path("data/rejected_screening.json")


class IngestionConfig(BaseModel):
    """Configuration parameters for the Ingestion & Checkpoint worker."""

    workers: int = 3
    rate_limit_rps: float = 5.0
    max_retries: int = 3
    max_backoff_sec: float = 30.0
    discovered_input_path: Path = Path("data/traders_discovered.json")
    checkpoint_path: Path = Path("data/checkpoint.json")
    raw_fills_dir: Path = Path("data/raw_fills")
    profiles_dir: Path = Path("data/profiles")


class TransformConfig(BaseModel):
    """Configuration parameters for the Transform & Quality Gate worker."""

    min_tier: QualityTier = QualityTier.PASS
    discovered_input_path: Path = Path("data/traders_discovered.json")
    raw_fills_dir: Path = Path("data/raw_fills")
    profiles_dir: Path = Path("data/profiles")
    output_parquet_path: Path = Path("data/dataset_traders.parquet")
