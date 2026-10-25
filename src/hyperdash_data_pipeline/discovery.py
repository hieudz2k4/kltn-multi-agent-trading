"""Hyperdash GraphQL discovery client and Gate 0 screening filter."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from src.core.logger import get_logger
from src.hyperdash_data_pipeline.schemas import (
    DiscoveryConfig,
    RejectedTraderRecord,
    TraderDiscoveryRecord,
    infer_size_cohort,
)

log = get_logger("hyperdash_discovery")

HYPERDASH_GRAPHQL_URL = "https://api.hyperdash.com/graphql"

BROWSER_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://hyperdash.com",
    "Referer": "https://hyperdash.com/explore/leaderboard",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

PNL_LEADERBOARD_QUERY = """
query PnlLeaderboard(
  $category: PnlLeaderboardCategory!
  $window: PnlLeaderboardWindow!
  $address: String
  $page: Int
  $pageSize: Int!
) {
  pnlLeaderboard(
    category: $category
    window: $window
    address: $address
    page: $page
    pageSize: $pageSize
  ) {
    pagination { page pageSize totalItems totalPages __typename }
    data {
      rank
      address
      displayName
      accountValue
      copyScore
      netPnl
      grossPnl
      fundingPnl
      totalFees
      volume
      tradeCount
      winningTrades
      losingTrades
      lastTradeAt
      __typename
    }
    __typename
  }
}
"""

EXPLORE_TRADERS_QUERY = """
query ExploreTraders(
  $page: Int
  $pageSize: Int
  $timeframe: TraderTimeframe!
  $sortBy: TraderSortInput
  $filters: TraderFilterInput
) {
  exploreTraders(
    page: $page
    pageSize: $pageSize
    timeframe: $timeframe
    sortBy: $sortBy
    filters: $filters
  ) {
    pagination { page pageSize totalItems totalPages }
    data {
      address
      displayName
      copyScore: copyScoreV2
      perpsEquity
      pnl
      sizeCohort
      winrate
      totalTrades
      totalWinningTrades
      totalLosingTrades
      sharpe
      drawdown
      portfolioGraph { timestamp value }
    }
  }
}
"""


# Boundary cases: None/empty -> 0; ISO-8601 string -> epoch sec; ms (>1e11) -> sec.
def normalize_epoch_seconds(raw_timestamp: float | str | None) -> int:
    """Convert an epoch number, numeric string, or ISO-8601 string into epoch seconds."""
    if raw_timestamp is None or raw_timestamp == "":
        return 0
    if isinstance(raw_timestamp, str):
        try:
            numeric_val = float(raw_timestamp)
        except ValueError:
            iso_str = raw_timestamp.replace("Z", "+00:00")
            return int(datetime.fromisoformat(iso_str).timestamp())
    else:
        numeric_val = float(raw_timestamp)
    if numeric_val <= 0:
        return 0
    timestamp_int = int(numeric_val)
    return timestamp_int // 1_000 if timestamp_int > 100_000_000_000 else timestamp_int


def extract_latest_graph_timestamp(graph_entries: list[dict[str, Any]] | None) -> int:
    """Return the latest timestamp in seconds from a portfolioGraph array."""
    if not graph_entries:
        return 0
    raw_last_ts = graph_entries[-1].get("timestamp", 0)
    return normalize_epoch_seconds(raw_last_ts)


def normalize_leaderboard_entry(
    raw_entry: dict[str, Any],
    window: str,
    discovered_at: int,
) -> TraderDiscoveryRecord:
    """Convert a raw PnlLeaderboard entry dict into a TraderDiscoveryRecord."""
    account_value = float(raw_entry.get("accountValue") or 0.0)
    return TraderDiscoveryRecord(
        address=str(raw_entry["address"]).lower(),
        rank=int(raw_entry["rank"]) if raw_entry.get("rank") is not None else None,
        display_name=raw_entry.get("displayName"),
        account_value=account_value,
        size_cohort=infer_size_cohort(account_value),
        net_pnl=float(raw_entry.get("netPnl") or 0.0),
        gross_pnl=(
            float(raw_entry["grossPnl"]) if raw_entry.get("grossPnl") is not None else None
        ),
        funding_pnl=(
            float(raw_entry["fundingPnl"]) if raw_entry.get("fundingPnl") is not None else None
        ),
        volume=float(raw_entry["volume"]) if raw_entry.get("volume") is not None else None,
        trade_count=int(raw_entry.get("tradeCount") or 0),
        winning_trades=(
            int(raw_entry["winningTrades"])
            if raw_entry.get("winningTrades") is not None
            else None
        ),
        losing_trades=(
            int(raw_entry["losingTrades"])
            if raw_entry.get("losingTrades") is not None
            else None
        ),
        copy_score=float(raw_entry.get("copyScore") or 0.0),
        last_trade_at=normalize_epoch_seconds(raw_entry.get("lastTradeAt")),
        window=window,
        discovered_at=discovered_at,
    )


def normalize_explore_entry(
    raw_entry: dict[str, Any],
    window: str,
    discovered_at: int,
) -> TraderDiscoveryRecord:
    """Convert a raw ExploreTraders entry dict into a TraderDiscoveryRecord."""
    account_value = float(raw_entry.get("perpsEquity") or 0.0)
    raw_cohort = str(raw_entry.get("sizeCohort") or "").upper()
    cohort = raw_cohort if raw_cohort in {"SMALL", "MID", "WHALE"} else infer_size_cohort(
        account_value
    )
    proxy_last_trade = extract_latest_graph_timestamp(raw_entry.get("portfolioGraph"))
    return TraderDiscoveryRecord(
        address=str(raw_entry["address"]).lower(),
        rank=None,
        display_name=raw_entry.get("displayName"),
        account_value=account_value,
        size_cohort=cohort,
        net_pnl=float(raw_entry.get("pnl") or 0.0),
        gross_pnl=None,
        funding_pnl=None,
        volume=None,
        trade_count=int(raw_entry.get("totalTrades") or 0),
        winning_trades=(
            int(raw_entry["totalWinningTrades"])
            if raw_entry.get("totalWinningTrades") is not None
            else None
        ),
        losing_trades=(
            int(raw_entry["totalLosingTrades"])
            if raw_entry.get("totalLosingTrades") is not None
            else None
        ),
        copy_score=float(raw_entry.get("copyScore") or 0.0),
        last_trade_at=proxy_last_trade,
        window=window,
        discovered_at=discovered_at,
    )


# Boundary cases: exact thresholds (account_value == 1000, copy_score == 60.0,
# inactivity == 7 days) must pass; net_pnl == 0 fails.
# NOTE: tradeCount is NOT checked here — sufficient trading history is enforced
# at Gate 1 via len(portfolioGraph) >= 30 (Hyperdash backfills full on-chain history).
def evaluate_gate_zero_reasons(
    candidate: TraderDiscoveryRecord,
    config: DiscoveryConfig,
    reference_epoch_sec: int,
) -> list[str]:
    """Return Gate 0 rejection reasons for a candidate trader (empty if passed)."""
    reasons: list[str] = []
    max_age_sec = config.max_inactivity_days * 86_400
    if reference_epoch_sec - candidate.last_trade_at > max_age_sec:
        reasons.append("INACTIVE_OVER_7D")
    if candidate.account_value < config.min_equity_usd:
        reasons.append("BELOW_MIN_EQUITY")
    if candidate.net_pnl <= 0.0:
        reasons.append("NON_POSITIVE_NET_PNL")
    if candidate.copy_score < config.min_copy_score:
        reasons.append("BELOW_MIN_COPY_SCORE")
    return reasons


def partition_by_gate_zero(
    candidates: list[TraderDiscoveryRecord],
    config: DiscoveryConfig,
    reference_epoch_sec: int,
) -> tuple[list[TraderDiscoveryRecord], list[RejectedTraderRecord]]:
    """Split deduplicated discovery records into passed and rejected lists."""
    accepted: list[TraderDiscoveryRecord] = []
    rejected: list[RejectedTraderRecord] = []
    for candidate in candidates:
        reasons = evaluate_gate_zero_reasons(candidate, config, reference_epoch_sec)
        if not reasons:
            accepted.append(candidate)
            continue
        rejected.append(
            RejectedTraderRecord(
                address=candidate.address,
                rejection_reasons=reasons,
                account_value=candidate.account_value,
                net_pnl=candidate.net_pnl,
                trade_count=candidate.trade_count,
                copy_score=candidate.copy_score,
                last_trade_at=candidate.last_trade_at,
                discovered_at=candidate.discovered_at,
            )
        )
    return accepted, rejected


def merge_discovery_candidates(
    leaderboard_records: list[TraderDiscoveryRecord],
    explore_records: list[TraderDiscoveryRecord],
) -> list[TraderDiscoveryRecord]:
    """Merge and deduplicate candidates, enriching leaderboard records from explore."""
    merged_by_address: dict[str, TraderDiscoveryRecord] = {
        rec.address: rec for rec in explore_records
    }
    for lb_rec in leaderboard_records:
        existing = merged_by_address.get(lb_rec.address)
        if existing is None:
            merged_by_address[lb_rec.address] = lb_rec
            continue
        merged_by_address[lb_rec.address] = lb_rec.model_copy(
            update={
                "size_cohort": existing.size_cohort,
                "copy_score": existing.copy_score,
            }
        )
    return list(merged_by_address.values())


async def fetch_leaderboard_page(
    http_client: httpx.AsyncClient,
    window: str,
    page: int,
    page_size: int,
) -> list[dict[str, Any]]:
    """Query one page of PnlLeaderboard from Hyperdash GraphQL."""
    graphql_batch = [
        {
            "operationName": "PnlLeaderboard",
            "variables": {
                "category": "all",
                "window": window,
                "page": page,
                "pageSize": page_size,
                "address": None,
            },
            "query": PNL_LEADERBOARD_QUERY,
        }
    ]
    response = await http_client.post(HYPERDASH_GRAPHQL_URL, json=graphql_batch)
    response.raise_for_status()
    payload_list = response.json()
    return payload_list[0]["data"]["pnlLeaderboard"]["data"]


async def fetch_explore_page(
    http_client: httpx.AsyncClient,
    config: DiscoveryConfig,
    page: int,
) -> list[dict[str, Any]]:
    """Query one page of ExploreTraders sorted by copyScoreV2 descending."""
    graphql_batch = [
        {
            "operationName": "ExploreTraders",
            "variables": {
                "page": page,
                "pageSize": config.page_size,
                "timeframe": config.explore_timeframe,
                "sortBy": {"field": "copyScoreV2", "order": "desc"},
                "filters": {},
            },
            "query": EXPLORE_TRADERS_QUERY,
        }
    ]
    response = await http_client.post(HYPERDASH_GRAPHQL_URL, json=graphql_batch)
    response.raise_for_status()
    payload_list = response.json()
    first_node = payload_list[0] if payload_list else {}
    return ((first_node.get("data") or {}).get("exploreTraders") or {}).get("data") or []


def write_json_atomically(target_path: Path, serializable_items: list[dict[str, Any]]) -> None:
    """Write a JSON array to a temporary file and atomically replace target_path."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(serializable_items, indent=2), encoding="utf-8")
    tmp_path.replace(target_path)


async def collect_raw_candidates(
    http_client: httpx.AsyncClient,
    config: DiscoveryConfig,
    discovered_at: int,
) -> list[TraderDiscoveryRecord]:
    """Fetch and merge candidates across configured pages of Leaderboard and Explore."""
    leaderboard_records: list[TraderDiscoveryRecord] = []
    explore_records: list[TraderDiscoveryRecord] = []
    for page_num in range(1, config.max_pages + 1):
        lb_entries = await fetch_leaderboard_page(
            http_client, config.window, page_num, config.page_size
        )
        leaderboard_records.extend(
            normalize_leaderboard_entry(entry, config.window, discovered_at)
            for entry in lb_entries
            if entry.get("address")
        )
        exp_entries = await fetch_explore_page(http_client, config, page_num)
        explore_records.extend(
            normalize_explore_entry(entry, config.window, discovered_at)
            for entry in exp_entries
            if entry.get("address")
        )
    return merge_discovery_candidates(leaderboard_records, explore_records)


async def run_discovery(
    config: DiscoveryConfig,
    http_client: httpx.AsyncClient | None = None,
) -> tuple[list[TraderDiscoveryRecord], list[RejectedTraderRecord]]:
    """Execute Discovery & Gate 0 screening and persist accepted/rejected JSON files."""
    discovered_at = int(time.time())
    if http_client is not None:
        candidates = await collect_raw_candidates(http_client, config, discovered_at)
    else:
        async with httpx.AsyncClient(headers=BROWSER_HEADERS, timeout=20.0) as client:
            candidates = await collect_raw_candidates(client, config, discovered_at)
    accepted, rejected = partition_by_gate_zero(candidates, config, discovered_at)
    write_json_atomically(
        config.discovered_output_path, [rec.model_dump() for rec in accepted]
    )
    write_json_atomically(
        config.rejected_output_path, [rec.model_dump() for rec in rejected]
    )
    log.info(
        "Discovery finished: {passed} accepted, {dropped} rejected at Gate 0",
        passed=len(accepted),
        dropped=len(rejected),
    )
    return accepted, rejected
