"""Quantitative metrics computation, Quality Gate 1 filtering, and strategy tagging."""

import json
import math

import numpy as np
import pandas as pd

from src.core.logger import get_logger
from src.hyperdash_data_pipeline.ingestion import write_parquet_atomically
from src.hyperdash_data_pipeline.schemas import (
    EnrichedTraderRecord,
    EquityPoint,
    QualityTier,
    SmoothnessTier,
    StrategyTag,
    TraderProfileSnapshot,
    TransformConfig,
    infer_size_cohort,
)

log = get_logger("hyperdash_transform")

ROUND_INTERVAL_BASES_SEC = (60.0, 300.0, 900.0, 3600.0)


# Boundary cases: account_value <= 0 -> NaN; empty fills_df -> NaN;
# supports either explicit 'notional' column or 'px' * 'sz'.
def compute_effective_leverage(
    total_ntl_pos: float,
    account_value: float,
    fills_df: pd.DataFrame,
) -> float:
    """Compute effective leverage combining realtime L1 margin and historical max fill."""
    if account_value <= 0.0 or fills_df.empty:
        return float("nan")
    realtime_lev = total_ntl_pos / account_value
    if "notional" in fills_df.columns:
        max_notional = float(fills_df["notional"].astype(float).max())
    else:
        notional_series = fills_df["px"].astype(float) * fills_df["sz"].astype(float)
        max_notional = float(notional_series.max())
    historical_max_lev = max_notional / account_value
    return float(max(realtime_lev, historical_max_lev))


# Boundary cases: <3 points -> (0, 0, 0); flat equity (ss_tot==0) -> (0, 0, 0);
# zero residuals (ss_res==0) -> R2=1.0, high K-ratio.
def compute_equity_regression(
    portfolio_graph: list[EquityPoint],
) -> tuple[float, float, float]:
    """Fit OLS line on portfolioGraph and return (equity_r2, equity_beta, k_ratio)."""
    if len(portfolio_graph) < 3:
        return 0.0, 0.0, 0.0
    equities = np.array([pt.equity_usd for pt in portfolio_graph], dtype=np.float64)
    num_pts = len(equities)
    time_idx = np.arange(num_pts, dtype=np.float64)
    x_centered = time_idx - time_idx.mean()
    y_centered = equities - equities.mean()
    ss_xx = float(np.dot(x_centered, x_centered))
    ss_tot = float(np.dot(y_centered, y_centered))
    if ss_xx <= 0.0 or ss_tot <= 0.0:
        return 0.0, 0.0, 0.0
    beta = float(np.dot(x_centered, y_centered) / ss_xx)
    residuals = y_centered - beta * x_centered
    ss_res = float(np.dot(residuals, residuals))
    r_squared = float(np.clip(1.0 - (ss_res / ss_tot), 0.0, 1.0))
    dof = max(1, num_pts - 2)
    se_beta = math.sqrt(max(ss_res / (dof * ss_xx), 1e-12))
    k_ratio = float(beta / (se_beta * math.sqrt(num_pts)))
    return r_squared, beta, k_ratio


# Boundary cases: no closed trades -> (fallback_winrate, 0.0);
# zero gross loss with positive profit -> PF = 99.0.
def compute_winrate_and_pf(
    fills_df: pd.DataFrame,
    fallback_winrate_pct: float,
) -> tuple[float, float]:
    """Calculate win rate in [0, 1] and profit factor from closed fill PnLs."""
    normalized_fallback = (
        fallback_winrate_pct / 100.0 if fallback_winrate_pct > 1.0 else fallback_winrate_pct
    )
    if fills_df.empty or "closed_pnl" not in fills_df.columns:
        return float(normalized_fallback), 0.0
    closed_pnls = fills_df["closed_pnl"].astype(float)
    non_zero = closed_pnls[closed_pnls != 0.0]
    if non_zero.empty:
        return float(normalized_fallback), 0.0
    wins = non_zero[non_zero > 0.0]
    losses = non_zero[non_zero < 0.0]
    win_rate = float(len(wins) / len(non_zero))
    gross_profit = float(wins.sum())
    gross_loss = float(abs(losses.sum()))
    if gross_loss == 0.0:
        return win_rate, (99.0 if gross_profit > 0.0 else 0.0)
    return win_rate, float(gross_profit / gross_loss)


def compute_calmar_ratio(
    portfolio_graph: list[EquityPoint],
    max_drawdown_all_pct: float,
) -> float:
    """Compute Annualized Return (%) divided by All-Time Max Drawdown (%)."""
    if len(portfolio_graph) < 2 or max_drawdown_all_pct <= 0.0:
        return 0.0
    start_eq = max(portfolio_graph[0].equity_usd, 1.0)
    end_eq = portfolio_graph[-1].equity_usd
    elapsed_days = max((portfolio_graph[-1].timestamp - portfolio_graph[0].timestamp) / 86_400.0, 1.0)
    total_return_pct = ((end_eq - start_eq) / start_eq) * 100.0
    annualized_return_pct = total_return_pct * (365.0 / elapsed_days)
    return float(annualized_return_pct / max_drawdown_all_pct)


def compute_avg_holding_seconds(fills_df: pd.DataFrame) -> float:
    """Estimate median position holding duration in seconds between Open and Close cycles."""
    if len(fills_df) < 2 or "time" not in fills_df.columns:
        return 0.0
    sorted_df = fills_df.sort_values("time")
    if not {"coin", "dir"}.issubset(sorted_df.columns):
        intervals = np.diff(sorted_df["time"].astype(float).to_numpy() / 1_000.0)
        pos = intervals[intervals > 0.0]
        return float(np.median(pos)) if len(pos) > 0 else 0.0
    open_ts_by_coin: dict[str, float] = {}
    durations: list[float] = []
    for coin, direction, ts_ms in zip(
        sorted_df["coin"].astype(str),
        sorted_df["dir"].astype(str),
        sorted_df["time"].astype(float),
        strict=False,
    ):
        ts_sec = ts_ms / 1_000.0
        if "Open" in direction and coin not in open_ts_by_coin:
            open_ts_by_coin[coin] = ts_sec
        elif "Close" in direction and coin in open_ts_by_coin:
            hold_sec = ts_sec - open_ts_by_coin.pop(coin)
            if hold_sec > 0.0:
                durations.append(hold_sec)
    return float(np.median(durations)) if durations else 0.0


def classify_smoothness_tier(equity_r2: float, equity_beta: float) -> str:
    """Map (R², β) into SMOOTH_LINEAR, MODERATE, or CHOPPY."""
    if equity_beta <= 0.0 or equity_r2 < 0.75:
        return SmoothnessTier.CHOPPY.value
    if equity_r2 >= 0.90:
        return SmoothnessTier.SMOOTH_LINEAR.value
    return SmoothnessTier.MODERATE.value


# Gate 1 — Equity Curve Quality Filter (Spec Muc 5.1)
# Boundary cases: len < 3 -> (0, 0, 0) da xu ly trong compute_equity_regression.
# portfolio_graph_len = 0 -> REJECT; equity_beta <= 0 -> REJECT; r2 < 0.75 -> REJECT.
def evaluate_quality_tier(
    equity_r2: float,
    equity_beta: float,
    portfolio_graph_len: int,
) -> str:
    """Return GOLD, PASS, or REJECT based solely on equity curve quality (Spec 5.1)."""
    if portfolio_graph_len < 30:
        return QualityTier.REJECT.value
    if equity_beta <= 0.0 or math.isnan(equity_r2):
        return QualityTier.REJECT.value
    if equity_r2 >= 0.90:
        return QualityTier.GOLD.value
    if equity_r2 >= 0.75:
        return QualityTier.PASS.value
    return QualityTier.REJECT.value


def check_activity_density(timestamps_sec: np.ndarray) -> bool:
    """Return True if >= 70% of 6-hour windows in up to 14 days contain at least 1 fill."""
    if len(timestamps_sec) < 10:
        return False
    end_ts = float(timestamps_sec[-1])
    start_ts = max(float(timestamps_sec[0]), end_ts - 14.0 * 86_400.0)
    total_buckets = max(1, math.ceil((end_ts - start_ts) / 21_600.0))
    if total_buckets < 4:
        return False
    recent_ts = timestamps_sec[timestamps_sec >= start_ts]
    occupied_buckets = len(np.unique(((recent_ts - start_ts) // 21_600.0).astype(int)))
    return (occupied_buckets / total_buckets) >= 0.70


def is_near_round_interval(delta_sec: float, tolerance_sec: float = 3.0) -> bool:
    """Return True if delta_sec is within tolerance of a multiple of 60/300/900/3600s."""
    for base in ROUND_INTERVAL_BASES_SEC:
        if delta_sec >= base * 0.8:
            remainder = delta_sec % base
            if remainder <= tolerance_sec or (base - remainder) <= tolerance_sec:
                return True
    return False


def check_periodic_clustering(timestamps_sec: np.ndarray) -> bool:
    """Return True if CV(Δt) < 0.20 or >= 60% of intervals cluster at round periods."""
    if len(timestamps_sec) < 5:
        return False
    deltas = np.diff(timestamps_sec)
    positive_deltas = deltas[deltas > 0.0]
    if len(positive_deltas) < 4:
        return False
    mean_dt = float(positive_deltas.mean())
    std_dt = float(positive_deltas.std(ddof=1))
    if mean_dt > 0.0 and (std_dt / mean_dt) < 0.20:
        return True
    round_matches = sum(1 for dt in positive_deltas if is_near_round_interval(float(dt)))
    return (round_matches / len(positive_deltas)) >= 0.60


def check_high_frequency(timestamps_sec: np.ndarray) -> bool:
    """Return True if average daily fills over the observed window exceed 50 fills/day."""
    if len(timestamps_sec) < 50:
        return False
    span_days = max(( float(timestamps_sec[-1]) - float(timestamps_sec[0]) ) / 86_400.0, 1.0)
    return (len(timestamps_sec) / span_days) > 50.0


def detect_is_algo(fills_df: pd.DataFrame) -> bool:
    """Classify trader as algorithmic if at least 2 of 3 temporal criteria hold."""
    if len(fills_df) < 5 or "time" not in fills_df.columns:
        return False
    timestamps_sec = np.sort(fills_df["time"].astype(float).to_numpy() / 1_000.0)
    criteria_passed = sum(
        [
            check_activity_density(timestamps_sec),
            check_periodic_clustering(timestamps_sec),
            check_high_frequency(timestamps_sec),
        ]
    )
    return criteria_passed >= 2


def collapse_partial_fills(fills_df: pd.DataFrame) -> pd.DataFrame:
    """Collapse CLOB partial fills occurring within 2000ms on the same coin and side."""
    if len(fills_df) < 2 or not {"time", "side", "px", "sz"}.issubset(fills_df.columns):
        return fills_df
    sorted_df = fills_df.sort_values("time").reset_index(drop=True)
    has_coin = "coin" in sorted_df.columns
    same_coin = sorted_df["coin"] == sorted_df["coin"].shift(1) if has_coin else True
    same_side = sorted_df["side"] == sorted_df["side"].shift(1)
    within_window = (sorted_df["time"].astype(float) - sorted_df["time"].astype(float).shift(1)) <= 2_000.0
    order_group = (~(same_coin & same_side & within_window)).cumsum()
    agg_spec: dict[str, str] = {"time": "min", "side": "first", "px": "mean", "sz": "sum"}
    if has_coin:
        agg_spec["coin"] = "first"
    return sorted_df.groupby(order_group, as_index=False).agg(agg_spec)


def detect_grid_martingale_pattern(fills_df: pd.DataFrame) -> bool:
    """Detect consecutive same-coin adverse DCA entries with strictly increasing size."""
    orders_df = collapse_partial_fills(fills_df)
    if len(orders_df) < 6 or not {"side", "px", "sz"}.issubset(orders_df.columns):
        return False
    coins = (
        orders_df["coin"].astype(str).to_numpy()
        if "coin" in orders_df.columns
        else np.repeat("ALL", len(orders_df))
    )
    sides = orders_df["side"].astype(str).to_numpy()
    sizes = orders_df["sz"].astype(float).to_numpy()
    prices = orders_df["px"].astype(float).to_numpy()
    streak = 0
    for idx in range(1, len(orders_df)):
        same_leg = (coins[idx] == coins[idx - 1]) and (sides[idx] == sides[idx - 1])
        adverse_px = (sides[idx] == "B" and prices[idx] < prices[idx - 1]) or (
            sides[idx] == "A" and prices[idx] > prices[idx - 1]
        )
        if same_leg and adverse_px and sizes[idx] > sizes[idx - 1] * 1.05:
            streak += 1
            if streak >= 4:
                return True
        else:
            streak = 0
    return False


def classify_strategy_tag(
    fills_df: pd.DataFrame,
    funding_pnl_pct: float,
    avg_holding_sec: float,
) -> str:
    """Classify wallet trading behavior into one of the four canonical strategy tags."""
    if funding_pnl_pct >= 50.0:
        return StrategyTag.FUNDING_CARRY.value
    if detect_grid_martingale_pattern(fills_df):
        return StrategyTag.GRID_MARTINGALE.value
    if avg_holding_sec > 0.0 and avg_holding_sec < 14_400.0:
        return StrategyTag.BREAKOUT_MOMENTUM.value
    return StrategyTag.TREND_DISCRETIONARY.value


def enrich_single_trader(
    snapshot: TraderProfileSnapshot,
    fills_df: pd.DataFrame,
) -> EnrichedTraderRecord:
    """Compute all quantitative ratios, tiers, and tags for a single trader."""
    win_rate, profit_factor = compute_winrate_and_pf(fills_df, snapshot.winrate_30d)
    r_squared, beta, k_ratio = compute_equity_regression(snapshot.portfolio_graph)
    effective_equity = max(snapshot.account_value, snapshot.perps_equity)
    eff_lev = compute_effective_leverage(
        snapshot.total_ntl_pos, effective_equity, fills_df
    )
    calmar = compute_calmar_ratio(snapshot.portfolio_graph, snapshot.drawdown_all)
    avg_hold_sec = compute_avg_holding_seconds(fills_df)
    funding_pct = (
        (abs(snapshot.funding_pnl) / abs(snapshot.net_pnl)) * 100.0
        if snapshot.net_pnl != 0.0
        else 0.0
    )
    # Gate 1: quality_tier determined solely by equity curve quality (Spec 5.1)
    quality_tier = evaluate_quality_tier(r_squared, beta, len(snapshot.portfolio_graph))
    cohort = (
        infer_size_cohort(effective_equity)
        if snapshot.size_cohort == "MICRO"
        else snapshot.size_cohort
    )
    return EnrichedTraderRecord(
        address=snapshot.address,
        size_cohort=cohort,
        total_trades=snapshot.total_trades,
        trades_30d=snapshot.trades_30d,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_drawdown_30d=snapshot.drawdown_30d,
        max_drawdown_90d=snapshot.drawdown_90d,
        max_drawdown_all=snapshot.drawdown_all,
        sharpe_ratio_all=snapshot.sharpe_all,
        sharpe_ratio_90d=snapshot.sharpe_90d,
        sortino_ratio_30d=snapshot.sortino_30d,
        calmar_ratio=calmar,
        equity_r2=r_squared,
        equity_beta=beta,
        k_ratio=k_ratio,
        effective_leverage=eff_lev,
        avg_holding_sec=avg_hold_sec,
        funding_pnl_pct=funding_pct,
        quality_tier=quality_tier,
        smoothness_tier=classify_smoothness_tier(r_squared, beta),
        is_algo=detect_is_algo(fills_df),
        strategy_tag=classify_strategy_tag(fills_df, funding_pct, avg_hold_sec),
    )


def passes_minimum_tier(record_tier: str, min_tier: QualityTier) -> bool:
    """Return True if record_tier meets or exceeds the configured minimum QualityTier."""
    tier_rank = {
        QualityTier.REJECT.value: 0,
        QualityTier.PASS.value: 1,
        QualityTier.GOLD.value: 2,
    }
    return tier_rank.get(record_tier, 0) >= tier_rank[min_tier.value]


def collect_enriched_traders(config: TransformConfig) -> list[EnrichedTraderRecord]:
    """Load ingested snapshots and fills, returning enriched records that pass min_tier."""
    retained_records: list[EnrichedTraderRecord] = []
    for profile_file in sorted(config.profiles_dir.glob("*.json")):
        raw_profile = json.loads(profile_file.read_text(encoding="utf-8"))
        snapshot = TraderProfileSnapshot.model_validate(raw_profile)
        parquet_file = config.raw_fills_dir / f"{snapshot.address}.parquet"
        if not parquet_file.exists():
            continue
        fills_df = pd.read_parquet(parquet_file)
        enriched = enrich_single_trader(snapshot, fills_df)
        if passes_minimum_tier(enriched.quality_tier, config.min_tier):
            retained_records.append(enriched)
    return retained_records


def run_transform(config: TransformConfig) -> list[EnrichedTraderRecord]:
    """Transform ingested profiles + fills, filter by Quality Gate 1, and export Parquet."""
    retained_records = collect_enriched_traders(config)
    dataset_df = pd.DataFrame([rec.model_dump() for rec in retained_records])
    if dataset_df.empty:
        dataset_df = pd.DataFrame(columns=list(EnrichedTraderRecord.model_fields.keys()))
    write_parquet_atomically(dataset_df, config.output_parquet_path)
    log.info(
        "Transform finished: {count} traders exported to {path}",
        count=len(retained_records),
        path=str(config.output_parquet_path),
    )
    return retained_records
