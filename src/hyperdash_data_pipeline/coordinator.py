"""CLI coordinator entrypoint for the Hyperdash & Hyperliquid Data Pipeline."""

import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from src.hyperdash_data_pipeline.discovery import run_discovery
from src.hyperdash_data_pipeline.ingestion import run_ingestion
from src.hyperdash_data_pipeline.schemas import (
    DiscoveryConfig,
    IngestionConfig,
    QualityTier,
    TransformConfig,
)
from src.hyperdash_data_pipeline.transform import run_transform


def add_discover_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register CLI flags for the 'discover' subcommand."""
    parser = subparsers.add_parser(
        "discover",
        help="Run PnlLeaderboard + ExploreTraders discovery with Gate 0 screening.",
    )
    parser.add_argument("--window", type=str, default="d30")
    parser.add_argument("--min-copyscore", type=float, default=60.0)
    parser.add_argument("--min-equity", type=float, default=1_000.0)

    parser.add_argument("--max-inactivity-days", type=int, default=7)
    parser.add_argument(
        "--output", type=Path, default=Path("data/traders_discovered.json")
    )
    parser.add_argument(
        "--rejected-output", type=Path, default=Path("data/rejected_screening.json")
    )


def add_ingest_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register CLI flags for the 'ingest' subcommand."""
    parser = subparsers.add_parser(
        "ingest",
        help="Run async GetTrader + Hyperliquid L1 fills ingestion with checkpointing.",
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--rate-limit", type=float, default=5.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument(
        "--discovered-input", type=Path, default=Path("data/traders_discovered.json")
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("data/checkpoint.json")
    )


def add_transform_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register CLI flags for the 'transform' subcommand."""
    parser = subparsers.add_parser(
        "transform",
        help="Run OLS R^2, Effective Leverage, Quality Gate 1, and Behavioral Tagging.",
    )
    parser.add_argument(
        "--min-tier",
        type=str,
        choices=[tier.value for tier in QualityTier],
        default=QualityTier.PASS.value,
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/dataset_traders.parquet")
    )
    parser.add_argument("--profiles-dir", type=Path, default=Path("data/profiles"))
    parser.add_argument("--raw-fills-dir", type=Path, default=Path("data/raw_fills"))


def build_cli_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser for the Hyperdash Data Pipeline."""
    parser = argparse.ArgumentParser(
        prog="hyperdash_data_pipeline",
        description="Hyperdash & Hyperliquid Quantitative Data Pipeline CLI.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    add_discover_subparser(subparsers)
    add_ingest_subparser(subparsers)
    add_transform_subparser(subparsers)
    return parser


def build_discovery_config(parsed_args: argparse.Namespace) -> DiscoveryConfig:
    """Convert parsed CLI arguments into a validated DiscoveryConfig."""
    return DiscoveryConfig(
        window=parsed_args.window,
        min_copy_score=parsed_args.min_copyscore,
        min_equity_usd=parsed_args.min_equity,
        max_inactivity_days=parsed_args.max_inactivity_days,
        discovered_output_path=parsed_args.output,
        rejected_output_path=parsed_args.rejected_output,
    )


def build_ingestion_config(parsed_args: argparse.Namespace) -> IngestionConfig:
    """Convert parsed CLI arguments into a validated IngestionConfig."""
    return IngestionConfig(
        workers=parsed_args.workers,
        rate_limit_rps=parsed_args.rate_limit,
        max_retries=parsed_args.max_retries,
        discovered_input_path=parsed_args.discovered_input,
        checkpoint_path=parsed_args.checkpoint,
    )


def build_transform_config(parsed_args: argparse.Namespace) -> TransformConfig:
    """Convert parsed CLI arguments into a validated TransformConfig."""
    return TransformConfig(
        min_tier=QualityTier(parsed_args.min_tier),
        output_parquet_path=parsed_args.output,
        profiles_dir=parsed_args.profiles_dir,
        raw_fills_dir=parsed_args.raw_fills_dir,
    )


def dispatch_subcommand(parsed_args: argparse.Namespace) -> int:
    """Execute the requested pipeline stage and return an OS exit code."""
    if parsed_args.subcommand == "discover":
        asyncio.run(run_discovery(build_discovery_config(parsed_args)))
        return 0
    if parsed_args.subcommand == "ingest":
        asyncio.run(run_ingestion(build_ingestion_config(parsed_args)))
        return 0
    if parsed_args.subcommand == "transform":
        run_transform(build_transform_config(parsed_args))
        return 0
    raise ValueError(f"Unsupported pipeline subcommand: {parsed_args.subcommand}")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for python -m src.hyperdash_data_pipeline.coordinator."""
    parser = build_cli_parser()
    parsed_args = parser.parse_args(argv)
    return dispatch_subcommand(parsed_args)


if __name__ == "__main__":
    raise SystemExit(main())
