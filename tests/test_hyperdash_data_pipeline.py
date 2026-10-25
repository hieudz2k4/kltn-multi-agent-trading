"""Unit tests for the Hyperdash & Hyperliquid Quantitative Data Pipeline."""

import json
import math
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest

from src.hyperdash_data_pipeline.coordinator import (
    build_cli_parser,
    build_discovery_config,
    build_ingestion_config,
    build_transform_config,
)
from src.hyperdash_data_pipeline.discovery import (
    evaluate_gate_zero_reasons,
    merge_discovery_candidates,
    normalize_explore_entry,
    normalize_leaderboard_entry,
    partition_by_gate_zero,
)
from src.hyperdash_data_pipeline.ingestion import (
    compute_backoff_seconds,
    load_or_init_checkpoint,
    record_task_outcome,
    run_ingestion,
    should_ingest_task,
)
from src.hyperdash_data_pipeline.schemas import (
    CheckpointTask,
    DiscoveryConfig,
    EquityPoint,
    IngestionConfig,
    QualityTier,
    SizeCohort,
    SmoothnessTier,
    StrategyTag,
    TaskStatus,
    TraderDiscoveryRecord,
    TransformConfig,
    infer_size_cohort,
)
from src.hyperdash_data_pipeline.transform import (
    classify_smoothness_tier,
    classify_strategy_tag,
    compute_effective_leverage,
    compute_equity_regression,
    detect_is_algo,
    evaluate_quality_tier,
    run_transform,
)


@pytest.fixture()
def json_parquet_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide a JSON-backed Parquet shim when pyarrow/fastparquet is absent in test env."""

    def _to_parquet(df: pd.DataFrame, path: Path | str, index: bool = False) -> None:
        target = Path(path)
        payload = {
            "columns": list(df.columns),
            "records": df.to_dict(orient="records"),
        }
        target.write_text(json.dumps(payload), encoding="utf-8")

    def _read_parquet(path: Path | str) -> pd.DataFrame:
        target = Path(path)
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not payload["records"]:
            return pd.DataFrame(columns=payload["columns"])
        return pd.DataFrame(payload["records"], columns=payload["columns"])

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _to_parquet)
    monkeypatch.setattr(pd, "read_parquet", _read_parquet)


def test_infer_size_cohort_boundaries() -> None:
    """Verify size_cohort boundaries (<1k, [1k, 10k), [10k, 100k), >=100k)."""
    assert infer_size_cohort(0.0) == SizeCohort.MICRO.value
    assert infer_size_cohort(999.99) == SizeCohort.MICRO.value
    assert infer_size_cohort(1_000.0) == SizeCohort.SMALL.value
    assert infer_size_cohort(9_999.99) == SizeCohort.SMALL.value
    assert infer_size_cohort(10_000.0) == SizeCohort.MID.value
    assert infer_size_cohort(99_999.99) == SizeCohort.MID.value
    assert infer_size_cohort(100_000.0) == SizeCohort.WHALE.value


def test_normalize_and_merge_discovery_candidates() -> None:
    """Verify Leaderboard + ExploreTraders normalization and richer-metadata merge."""
    now_ts = 1_760_000_000
    lb_raw = {
        "address": "0xAbC123",
        "rank": 4,
        "displayName": "AlphaWhale",
        "accountValue": 55_000.0,
        "copyScore": 78.5,
        "netPnl": 12_500.0,
        "grossPnl": 13_000.0,
        "fundingPnl": -500.0,
        "volume": 800_000.0,
        "tradeCount": 88,
        "winningTrades": 55,
        "losingTrades": 33,
        "lastTradeAt": now_ts - 3600,
    }
    exp_raw = {
        "address": "0xabc123",
        "perpsEquity": 56_000.0,
        "pnl": 12_500.0,
        "sizeCohort": "WHALE",
        "copyScore": 78.5,
        "totalTrades": 88,
        "portfolioGraph": [{"timestamp": now_ts - 3600, "value": 56_000.0}],
    }
    lb_rec = normalize_leaderboard_entry(lb_raw, "d30", now_ts)
    exp_rec = normalize_explore_entry(exp_raw, "d30", now_ts)
    merged = merge_discovery_candidates([lb_rec], [exp_rec])

    assert len(merged) == 1
    trader = merged[0]
    assert trader.address == "0xabc123"
    assert trader.rank == 4
    assert trader.display_name == "AlphaWhale"
    assert trader.copy_score == pytest.approx(78.5)
    assert trader.trade_count == 88
    assert trader.size_cohort == SizeCohort.WHALE.value


def test_gate_zero_screening_partition() -> None:
    """Verify Gate 0 accepts qualified traders and audits multi-reason rejections."""
    now_ts = 1_760_000_000
    config = DiscoveryConfig(
        min_copy_score=60.0,
        min_equity_usd=1_000.0,
        min_trade_count_30d=30,
        max_inactivity_days=7,
    )
    good_trader = TraderDiscoveryRecord(
        address="0xgood",
        account_value=15_000.0,
        size_cohort="MID",
        net_pnl=3_200.0,
        trade_count=45,
        copy_score=72.0,
        last_trade_at=now_ts - 86_400,
        window="d30",
        discovered_at=now_ts,
    )
    bad_trader = TraderDiscoveryRecord(
        address="0xbad",
        account_value=450.0,
        size_cohort="MICRO",
        net_pnl=-100.0,
        trade_count=12,
        copy_score=40.0,
        last_trade_at=now_ts - (10 * 86_400),
        window="d30",
        discovered_at=now_ts,
    )
    reasons = evaluate_gate_zero_reasons(bad_trader, config, now_ts)
    assert len(reasons) == 4

    accepted, rejected = partition_by_gate_zero([good_trader, bad_trader], config, now_ts)
    assert [r.address for r in accepted] == ["0xgood"]
    assert len(rejected) == 1
    assert rejected[0].address == "0xbad"
    assert len(rejected[0].rejection_reasons) == 4


def test_backoff_and_checkpoint_logic(tmp_path: Path) -> None:
    """Verify exponential backoff cap and checkpoint task state transitions."""
    assert compute_backoff_seconds(0, 30.0) == pytest.approx(1.0)
    assert compute_backoff_seconds(2, 30.0) == pytest.approx(4.0)
    assert compute_backoff_seconds(10, 30.0) == pytest.approx(30.0)

    task = CheckpointTask()
    assert should_ingest_task(task, max_retries=3) is True
    record_task_outcome(task, fills_count=None, error_msg="HTTP 429")
    assert task.status == TaskStatus.FAILED
    assert task.retry_count == 1
    assert should_ingest_task(task, max_retries=3) is True

    record_task_outcome(task, fills_count=120, error_msg=None)
    assert task.status == TaskStatus.COMPLETED
    assert task.fills_count == 120
    assert should_ingest_task(task, max_retries=3) is False

    now_ts = 1_760_000_000
    discovered_records = [
        TraderDiscoveryRecord(
            address=addr,
            account_value=5_000.0,
            size_cohort="SMALL",
            net_pnl=500.0,
            trade_count=40,
            copy_score=70.0,
            last_trade_at=now_ts,
            window="d30",
            discovered_at=now_ts,
        )
        for addr in ("0x1", "0x2")
    ]
    ckpt_file = tmp_path / "checkpoint.json"
    state = load_or_init_checkpoint(ckpt_file, discovered_records)
    assert state.total_discovered == 2
    assert set(state.tasks.keys()) == {"0x1", "0x2"}


def test_effective_leverage_formula_and_fallback() -> None:
    """Verify Effective Leverage formula, zero-position fallback, and equity<=0 guard."""
    fills_df = pd.DataFrame(
        [
            {"px": 2_000.0, "sz": 5.0},
            {"px": 3_000.0, "sz": 10.0},
        ]
    )
    # Active realtime position: total_ntl_pos=35,000 / account_value=10,000 = 3.5x (> max fill 3.0x)
    assert compute_effective_leverage(35_000.0, 10_000.0, fills_df) == pytest.approx(3.5)
    # Flat realtime position (0.0): falls back to max historical fill notional (30,000 / 10,000 = 3.0x)
    assert compute_effective_leverage(0.0, 10_000.0, fills_df) == pytest.approx(3.0)
    # Liquidated / zero equity: returns NaN
    assert math.isnan(compute_effective_leverage(10_000.0, 0.0, fills_df))


def test_equity_curve_ols_regression_and_smoothness() -> None:
    """Verify OLS R^2, slope beta, K-Ratio, and SmoothnessTier classification."""
    linear_curve = [
        EquityPoint(timestamp=1_700_000_000 + i * 86_400, equity_usd=10_000.0 + i * 500.0)
        for i in range(20)
    ]
    r2, beta, k_ratio = compute_equity_regression(linear_curve)
    assert r2 > 0.999
    assert beta == pytest.approx(500.0)
    assert k_ratio > 10.0
    assert classify_smoothness_tier(r2, beta) == SmoothnessTier.SMOOTH_LINEAR.value

    down_curve = [
        EquityPoint(timestamp=1_700_000_000 + i * 86_400, equity_usd=20_000.0 - i * 500.0)
        for i in range(20)
    ]
    r2_down, beta_down, _ = compute_equity_regression(down_curve)
    assert beta_down < 0
    assert classify_smoothness_tier(r2_down, beta_down) == SmoothnessTier.CHOPPY.value


def test_closed_interval_quality_gate_one() -> None:
    """Verify Gate 1 equity curve quality filter (portfolio_graph_len, beta, R^2)."""
    assert evaluate_quality_tier(0.95, 50.0, 29) == QualityTier.REJECT.value
    assert evaluate_quality_tier(0.95, -5.0, 30) == QualityTier.REJECT.value
    assert evaluate_quality_tier(0.95, 0.0, 30) == QualityTier.REJECT.value
    assert evaluate_quality_tier(float("nan"), 10.0, 30) == QualityTier.REJECT.value
    assert evaluate_quality_tier(0.74, 10.0, 30) == QualityTier.REJECT.value
    assert evaluate_quality_tier(0.75, 10.0, 30) == QualityTier.PASS.value
    assert evaluate_quality_tier(0.899, 10.0, 30) == QualityTier.PASS.value
    assert evaluate_quality_tier(0.90, 10.0, 30) == QualityTier.GOLD.value
    assert evaluate_quality_tier(0.98, 250.0, 30) == QualityTier.GOLD.value


def test_detect_is_algo_and_strategy_classification() -> None:
    """Verify CV(delta_t) < 0.20 + high-frequency/density bot detection and strategy tags."""
    # 60 periodic fills spaced every 60,000 ms (60s) -> CV(dt) == 0.0 < 0.20 & >50 fills/day -> True
    periodic_fills = pd.DataFrame(
        [
            {
                "tid": i,
                "coin": "ETH",
                "side": "B",
                "px": 2500.0,
                "sz": 1.0,
                "time": 1_700_000_000_000 + i * 60_000,
                "fee": 0.5,
                "closed_pnl": 10.0 if i % 2 == 0 else 0.0,
                "dir": "Open Long" if i % 2 == 0 else "Close Long",
            }
            for i in range(60)
        ]
    )
    assert detect_is_algo(periodic_fills) is True

    # Irregular human fills across several days -> is_algo False
    rng = np.random.default_rng(42)
    irregular_gaps = rng.integers(5_000_000, 45_000_000, size=12)
    timestamps = np.cumsum(irregular_gaps) + 1_700_000_000_000
    human_fills = pd.DataFrame(
        [
            {
                "tid": idx,
                "coin": "BTC",
                "side": "B" if idx % 2 == 0 else "A",
                "px": 60_000.0,
                "sz": 0.1,
                "time": int(ts),
                "fee": 1.0,
                "closed_pnl": 50.0 if idx % 2 == 1 else 0.0,
                "dir": "Open Long" if idx % 2 == 0 else "Close Long",
            }
            for idx, ts in enumerate(timestamps)
        ]
    )
    assert detect_is_algo(human_fills) is False

    # Funding carry strategy (>=50% funding PnL contribution)
    assert (
        classify_strategy_tag(human_fills, funding_pnl_pct=55.0, avg_holding_sec=36_000.0)
        == StrategyTag.FUNDING_CARRY.value
    )
    assert (
        classify_strategy_tag(human_fills, funding_pnl_pct=5.0, avg_holding_sec=20_000.0)
        == StrategyTag.TREND_DISCRETIONARY.value
    )


@pytest.mark.asyncio()
async def test_end_to_end_ingest_and_transform_pipeline(
    tmp_path: Path, json_parquet_shim: None
) -> None:
    """Verify async ingestion with mocked HTTP transport followed by transform to Parquet."""
    discovered_path = tmp_path / "traders_discovered.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    raw_fills_dir = tmp_path / "raw_fills"
    profiles_dir = tmp_path / "profiles"
    output_parquet = tmp_path / "dataset_traders.parquet"

    record = TraderDiscoveryRecord(
        address="0x111122223333444455556666777788889999aaaa",
        rank=1,
        display_name="QuantMaster",
        account_value=50_000.0,
        size_cohort="MID",
        net_pnl=18_000.0,
        funding_pnl=900.0,
        trade_count=60,
        copy_score=84.0,
        last_trade_at=1_760_000_000,
        window="d30",
        discovered_at=1_760_000_100,
    )
    discovered_path.write_text(json.dumps([record.model_dump()]), encoding="utf-8")

    def mock_http_responder(request: httpx.Request) -> httpx.Response:
        if "graphql" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {
                        "data": {
                            "getTrader": {
                                "address": record.address,
                                "displayName": "QuantMaster",
                                "perpsEquity": 50_000.0,
                                "pnl": 18_000.0,
                                "sizeCohort": "MID",
                                "totalTrades": 120,
                                "trades30d": 60,
                                "winrate30d": 0.85,
                                "winrateLifetime": 0.82,
                                "sharpe": 2.4,
                                "sharpe90d": 1.9,
                                "sortino30d": 3.2,
                                "drawdown30d": 6.5,
                                "drawdown90d": 9.0,
                                "drawdown": 12.0,
                                "copyScore": 84.0,
                                "portfolioGraph": [
                                    {
                                        "timestamp": 1_750_000_000 + i * 86_400,
                                        "value": 32_000.0 + i * 600.0,
                                    }
                                    for i in range(30)
                                ],
                            }
                        }
                    }
                ],
            )
        body = json.loads(request.content.decode("utf-8"))
        if body["type"] == "clearinghouseState":
            return httpx.Response(
                200,
                json={
                    "marginSummary": {
                        "accountValue": "50000.0",
                        "totalNtlPos": "60000.0",
                    }
                },
            )
        return httpx.Response(
            200,
            json=[
                {
                    "tid": 100 + i,
                    "coin": "BTC",
                    "side": "B" if i % 2 == 0 else "A",
                    "px": "60000.0",
                    "sz": "0.5",
                    "time": 1_750_000_000_000 + i * 3_600_000,
                    "fee": "1.5",
                    "closedPnl": "500.0" if i % 5 != 0 else "-100.0",
                    "dir": "Open Long" if i % 2 == 0 else "Close Long",
                }
                for i in range(25)
            ],
        )

    transport = httpx.MockTransport(mock_http_responder)
    ingest_cfg = IngestionConfig(
        workers=1,
        rate_limit_rps=50.0,
        discovered_input_path=discovered_path,
        checkpoint_path=checkpoint_path,
        raw_fills_dir=raw_fills_dir,
        profiles_dir=profiles_dir,
    )
    async with httpx.AsyncClient(transport=transport) as mock_client:
        state = await run_ingestion(ingest_cfg, http_client=mock_client)

    assert state.completed_count == 1
    assert (profiles_dir / f"{record.address}.json").exists()
    assert (raw_fills_dir / f"{record.address}.parquet").exists()

    transform_cfg = TransformConfig(
        min_tier=QualityTier.PASS,
        discovered_input_path=discovered_path,
        raw_fills_dir=raw_fills_dir,
        profiles_dir=profiles_dir,
        output_parquet_path=output_parquet,
    )
    retained = run_transform(transform_cfg)
    assert len(retained) == 1
    assert retained[0].quality_tier == QualityTier.GOLD.value
    assert retained[0].smoothness_tier == SmoothnessTier.SMOOTH_LINEAR.value
    assert output_parquet.exists()


def test_cli_coordinator_argument_parsing() -> None:
    """Verify CLI subcommands parse into exact Discovery, Ingestion, and Transform configs."""
    parser = build_cli_parser()

    disc_args = parser.parse_args(
        ["discover", "--window", "d30", "--min-copyscore", "65.0", "--min-equity", "2000"]
    )
    disc_cfg = build_discovery_config(disc_args)
    assert disc_cfg.window == "d30"
    assert disc_cfg.min_copy_score == pytest.approx(65.0)
    assert disc_cfg.min_equity_usd == pytest.approx(2_000.0)

    ing_args = parser.parse_args(["ingest", "--workers", "4", "--rate-limit", "5"])
    ing_cfg = build_ingestion_config(ing_args)
    assert ing_cfg.workers == 4
    assert ing_cfg.rate_limit_rps == pytest.approx(5.0)

    trans_args = parser.parse_args(
        ["transform", "--min-tier", "GOLD", "--output", "data/custom.parquet"]
    )
    trans_cfg = build_transform_config(trans_args)
    assert trans_cfg.min_tier == QualityTier.GOLD
    assert trans_cfg.output_parquet_path == Path("data/custom.parquet")
