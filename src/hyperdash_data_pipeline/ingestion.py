"""Ingestion worker for Hyperdash GetTrader profiles and Hyperliquid L1 fills."""

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from src.core.logger import get_logger
from src.hyperdash_data_pipeline.discovery import (
    BROWSER_HEADERS,
    HYPERDASH_GRAPHQL_URL,
    normalize_epoch_seconds,
)
from src.hyperdash_data_pipeline.schemas import (
    CheckpointState,
    CheckpointTask,
    EquityPoint,
    IngestionConfig,
    RawFillRecord,
    TaskStatus,
    TraderDiscoveryRecord,
    TraderProfileSnapshot,
    infer_size_cohort,
)

log = get_logger("hyperdash_ingestion")

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"

GET_TRADER_QUERY = """
query GetTrader($address: String!) {
  getTrader(address: $address) {
    address
    displayName
    perpsEquity
    pnl
    sizeCohort
    winrate30d
    winrate90d
    winrateLifetime
    totalTrades
    trades30d
    sharpe
    sharpe30d
    sharpe90d
    sortino30d
    sortino90d
    drawdown30d
    drawdown90d
    drawdown
    copyScore: copyScoreV2
    portfolioGraph {
      timestamp
      value
    }
  }
}
"""


class TokenBucketLimiter:
    """Async token-bucket rate limiter enforcing a maximum request rate per second."""

    def __init__(self, rate_per_sec: float) -> None:
        self._interval_sec = 1.0 / max(rate_per_sec, 0.1)
        self._next_allowed_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the next request token is available."""
        async with self._lock:
            now = time.monotonic()
            wait_sec = max(0.0, self._next_allowed_time - now)
            self._next_allowed_time = max(now, self._next_allowed_time) + self._interval_sec
        if wait_sec > 0.0:
            await asyncio.sleep(wait_sec)


# Boundary cases: retry_attempt=0 -> 1s, retry_attempt=5 -> capped at max_backoff_sec (30s).
def compute_backoff_seconds(retry_attempt: int, max_backoff_sec: float = 30.0) -> float:
    """Calculate exponential backoff duration 2^n * 1s capped at max_backoff_sec."""
    exponent = max(0, retry_attempt)
    return float(min(2**exponent, max_backoff_sec))


async def post_json_with_backoff(
    http_client: httpx.AsyncClient,
    limiter: TokenBucketLimiter,
    url: str,
    json_payload: Any,
) -> Any:
    """Send an HTTP POST request with token-bucket throttling and 429 backoff."""
    for attempt in range(4):
        await limiter.acquire()
        response = await http_client.post(url, json=json_payload)
        if response.status_code == 429 and attempt < 3:
            await asyncio.sleep(compute_backoff_seconds(attempt))
            continue
        response.raise_for_status()
        return response.json()
    raise RuntimeError(f"Exhausted rate-limit retries for {url}")


def parse_raw_fills(raw_fills_payload: list[dict[str, Any]]) -> list[RawFillRecord]:
    """Validate and convert raw L1 userFills JSON dicts into RawFillRecord objects."""
    parsed_fills: list[RawFillRecord] = []
    for raw_fill in raw_fills_payload:
        parsed_fills.append(
            RawFillRecord(
                tid=int(raw_fill.get("tid") or 0),
                coin=str(raw_fill.get("coin") or ""),
                side=str(raw_fill.get("side") or ""),
                px=float(raw_fill.get("px") or 0.0),
                sz=float(raw_fill.get("sz") or 0.0),
                time=int(raw_fill.get("time") or 0),
                fee=float(raw_fill.get("fee") or 0.0),
                closed_pnl=float(raw_fill.get("closedPnl") or 0.0),
                dir=str(raw_fill.get("dir") or ""),
            )
        )
    return parsed_fills


def parse_portfolio_graph(raw_graph: list[dict[str, Any]] | None) -> list[EquityPoint]:
    """Convert raw portfolioGraph entries into sorted EquityPoint records."""
    if not raw_graph:
        return []
    points = [
        EquityPoint(
            timestamp=normalize_epoch_seconds(point.get("timestamp")),
            equity_usd=float(point.get("value") or 0.0),
        )
        for point in raw_graph
        if point.get("timestamp") is not None and point.get("value") is not None
    ]
    return sorted(points, key=lambda pt: pt.timestamp)


def build_profile_snapshot(
    address: str,
    trader_node: dict[str, Any],
    clearinghouse_node: dict[str, Any],
    funding_pnl: float,
) -> TraderProfileSnapshot:
    """Assemble TraderProfileSnapshot from GetTrader and clearinghouseState payloads."""
    margin_summary = clearinghouse_node.get("marginSummary") or {}
    perps_equity = float(trader_node.get("perpsEquity") or 0.0)
    l1_account_val = float(margin_summary.get("accountValue") or 0.0)
    account_val = l1_account_val if l1_account_val > 0.0 else perps_equity
    raw_cohort = str(trader_node.get("sizeCohort") or "").upper()
    cohort = raw_cohort if raw_cohort in {"SMALL", "MID", "WHALE"} else infer_size_cohort(
        account_val
    )
    return TraderProfileSnapshot(
        address=address.lower(),
        display_name=trader_node.get("displayName"),
        size_cohort=cohort,
        perps_equity=perps_equity,
        net_pnl=float(trader_node.get("pnl") or 0.0),
        funding_pnl=funding_pnl,
        total_trades=int(trader_node.get("totalTrades") or 0),
        trades_30d=int(trader_node.get("trades30d") or 0),
        winrate_30d=float(trader_node.get("winrate30d") or 0.0),
        winrate_all=float(
            trader_node.get("winrateLifetime") or trader_node.get("winrate") or 0.0
        ),
        sharpe_all=float(trader_node.get("sharpe") or 0.0),
        sharpe_90d=float(trader_node.get("sharpe90d") or 0.0),
        sortino_30d=float(trader_node.get("sortino30d") or 0.0),
        drawdown_30d=float(trader_node.get("drawdown30d") or 0.0),
        drawdown_90d=float(trader_node.get("drawdown90d") or 0.0),
        drawdown_all=float(trader_node.get("drawdown") or 0.0),
        copy_score=float(trader_node.get("copyScore") or 0.0),
        account_value=account_val,
        total_ntl_pos=float(margin_summary.get("totalNtlPos") or 0.0),
        portfolio_graph=parse_portfolio_graph(trader_node.get("portfolioGraph")),
    )


def write_parquet_atomically(fills_df: pd.DataFrame, target_path: Path) -> None:
    """Write a DataFrame to a .tmp file, verify non-empty bytes, and rename to .parquet."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(".parquet.tmp")
    fills_df.to_parquet(tmp_path, index=False)
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise OSError(f"Atomic Parquet write verification failed for {target_path}")
    tmp_path.replace(target_path)


def write_profile_atomically(snapshot: TraderProfileSnapshot, target_path: Path) -> None:
    """Persist TraderProfileSnapshot atomically via a temporary JSON file."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(".json.tmp")
    tmp_path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.replace(target_path)


def load_or_init_checkpoint(
    checkpoint_path: Path,
    discovered_records: list[TraderDiscoveryRecord],
) -> CheckpointState:
    """Load existing checkpoint.json or initialize tasks for discovered traders."""
    if checkpoint_path.exists():
        raw_state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        state = CheckpointState.model_validate(raw_state)
    else:
        state = CheckpointState(
            updated_at=datetime.now(UTC).isoformat(),
            total_discovered=len(discovered_records),
            completed_count=0,
            failed_count=0,
            tasks={},
        )
    for rec in discovered_records:
        if rec.address not in state.tasks:
            state.tasks[rec.address] = CheckpointTask()
    state.total_discovered = len(state.tasks)
    return state


def save_checkpoint_atomically(state: CheckpointState, checkpoint_path: Path) -> None:
    """Recount task statuses and atomically persist checkpoint.json."""
    state.updated_at = datetime.now(UTC).isoformat()
    state.completed_count = sum(
        1 for task in state.tasks.values() if task.status == TaskStatus.COMPLETED
    )
    state.failed_count = sum(
        1 for task in state.tasks.values() if task.status == TaskStatus.FAILED
    )
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = checkpoint_path.with_suffix(".json.tmp")
    tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    tmp_path.replace(checkpoint_path)
    log.info(
        "Ingest progress: {done}/{total} completed ({failed} failed)",
        done=state.completed_count,
        total=state.total_discovered,
        failed=state.failed_count,
    )


def should_ingest_task(task: CheckpointTask, max_retries: int) -> bool:
    """Determine if a task is eligible for ingestion under resume idempotency."""
    if task.status == TaskStatus.PENDING:
        return True
    return task.status == TaskStatus.FAILED and task.retry_count < max_retries


def deduplicate_raw_fills(fills: list[RawFillRecord]) -> list[RawFillRecord]:
    """Deduplicate fills by (tid, time, coin, side) and sort chronologically."""
    seen_keys: set[tuple[int, int, str, str]] = set()
    unique_fills: list[RawFillRecord] = []
    for fill in fills:
        key = (fill.tid, fill.time, fill.coin, fill.side)
        if key not in seen_keys:
            seen_keys.add(key)
            unique_fills.append(fill)
    unique_fills.sort(key=lambda rec: rec.time)
    return unique_fills


async def fetch_paginated_user_fills(
    http_client: httpx.AsyncClient,
    limiter: TokenBucketLimiter,
    address: str,
    max_pages: int = 5,
) -> list[RawFillRecord]:
    """Fetch up to max_pages of aggregated userFills (2,000 per page, up to 10,000 fills)."""
    first_batch = await post_json_with_backoff(
        http_client,
        limiter,
        HYPERLIQUID_INFO_URL,
        {"type": "userFills", "user": address, "aggregateByTime": True},
    )
    all_fills = parse_raw_fills(first_batch if isinstance(first_batch, list) else [])
    if len(all_fills) < 2_000:
        return deduplicate_raw_fills(all_fills)
    oldest_ts = min(fill.time for fill in all_fills)
    for _ in range(max_pages - 1):
        end_ts = oldest_ts - 1
        start_ts = max(0, end_ts - 30 * 86_400_000)
        page_resp = await post_json_with_backoff(
            http_client,
            limiter,
            HYPERLIQUID_INFO_URL,
            {
                "type": "userFillsByTime",
                "user": address,
                "startTime": start_ts,
                "endTime": end_ts,
                "aggregateByTime": True,
            },
        )
        page_fills = parse_raw_fills(page_resp if isinstance(page_resp, list) else [])
        if not page_fills:
            break
        all_fills.extend(page_fills)
        new_oldest = min(fill.time for fill in page_fills)
        if len(page_fills) < 2_000 or new_oldest >= oldest_ts:
            break
        oldest_ts = new_oldest
    return deduplicate_raw_fills(all_fills)


async def fetch_wallet_bundle(
    http_client: httpx.AsyncClient,
    limiter: TokenBucketLimiter,
    address: str,
    funding_pnl: float,
) -> tuple[TraderProfileSnapshot, list[RawFillRecord]]:
    """Fetch GetTrader profile, clearinghouseState, and paginated aggregated userFills."""
    graphql_payload = [
        {"operationName": "GetTrader", "variables": {"address": address}, "query": GET_TRADER_QUERY}
    ]
    hd_resp = await post_json_with_backoff(
        http_client, limiter, HYPERDASH_GRAPHQL_URL, graphql_payload
    )
    trader_node = (hd_resp[0].get("data") or {}).get("getTrader") or {}
    ch_resp = await post_json_with_backoff(
        http_client, limiter, HYPERLIQUID_INFO_URL, {"type": "clearinghouseState", "user": address}
    )
    fills = await fetch_paginated_user_fills(http_client, limiter, address)
    snapshot = build_profile_snapshot(address, trader_node, ch_resp, funding_pnl)
    return snapshot, fills


async def ingest_single_wallet(
    record: TraderDiscoveryRecord,
    config: IngestionConfig,
    http_client: httpx.AsyncClient,
    limiter: TokenBucketLimiter,
) -> int:
    """Ingest and atomically persist profile + fills for one wallet, returning fill count."""
    snapshot, fills = await fetch_wallet_bundle(
        http_client, limiter, record.address, float(record.funding_pnl or 0.0)
    )
    fills_df = pd.DataFrame([fill.model_dump() for fill in fills])
    if fills_df.empty:
        fills_df = pd.DataFrame(
            columns=["tid", "coin", "side", "px", "sz", "time", "fee", "closed_pnl", "dir"]
        )
    parquet_path = config.raw_fills_dir / f"{record.address}.parquet"
    profile_path = config.profiles_dir / f"{record.address}.json"
    write_parquet_atomically(fills_df, parquet_path)
    write_profile_atomically(snapshot, profile_path)
    return len(fills)


def record_task_outcome(
    task: CheckpointTask,
    fills_count: int | None,
    error_msg: str | None,
) -> None:
    """Mutate CheckpointTask after a wallet ingestion attempt."""
    if error_msg is None and fills_count is not None:
        task.status = TaskStatus.COMPLETED
        task.fills_count = fills_count
        task.last_updated = int(time.time())
        task.last_error = None
        return
    task.status = TaskStatus.FAILED
    task.retry_count += 1
    task.last_updated = int(time.time())
    task.last_error = error_msg


async def ingest_pending_wallets(
    discovered: list[TraderDiscoveryRecord],
    state: CheckpointState,
    config: IngestionConfig,
    http_client: httpx.AsyncClient,
) -> None:
    """Iterate through discovered wallets and ingest eligible tasks with checkpointing."""
    limiter = TokenBucketLimiter(config.rate_limit_rps)
    for record in discovered:
        task = state.tasks[record.address]
        if not should_ingest_task(task, config.max_retries):
            continue
        try:
            count = await ingest_single_wallet(record, config, http_client, limiter)
            record_task_outcome(task, count, None)
        except (httpx.HTTPError, KeyError, ValueError, OSError, RuntimeError) as exc:
            record_task_outcome(task, None, str(exc))
        save_checkpoint_atomically(state, config.checkpoint_path)


async def run_ingestion(
    config: IngestionConfig,
    http_client: httpx.AsyncClient | None = None,
) -> CheckpointState:
    """Execute fault-tolerant queue ingestion with token-bucket rate limiting."""
    raw_discovered = json.loads(config.discovered_input_path.read_text(encoding="utf-8"))
    discovered = [TraderDiscoveryRecord.model_validate(entry) for entry in raw_discovered]
    state = load_or_init_checkpoint(config.checkpoint_path, discovered)
    if http_client is not None:
        await ingest_pending_wallets(discovered, state, config, http_client)
        return state
    async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=25.0) as client:
        await ingest_pending_wallets(discovered, state, config, client)
    return state
