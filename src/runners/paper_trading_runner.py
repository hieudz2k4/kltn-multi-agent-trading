"""Paper Trading Runtime Runner for SMC Multi-Agent Trading System.

Operates on M15 bar-close schedule with MT5 Demo Broker integration.
Persists execution telemetry to SQLite and JSONLines logs.
"""

import asyncio
import json
import os
import signal
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types
from loguru import logger

from src.agents.smc.smc_orchestrator import create_smc_orchestrator
from src.core.schemas import RiskVerdict, SMCSetup
from src.core.state import STATE_MACRO_SENTIMENT, STATE_RISK_VERDICT, STATE_SMC_SETUP
from src.tools.mt5_tools import get_account_snapshot


def calculate_sleep_seconds_to_next_bar(current_timestamp: float, timeframe_seconds: int = 900, buffer_seconds: int = 5) -> float:
    """Calculate remaining seconds until the next timeframe bar close.

    Formula: timeframe_seconds - (current_timestamp % timeframe_seconds) + buffer_seconds.
    """
    elapsed_in_bar = current_timestamp % timeframe_seconds
    remaining = timeframe_seconds - elapsed_in_bar + buffer_seconds
    return float(remaining)


class PaperTradingStorage:
    """SQLite and JSONLines persistence manager for paper trading telemetry."""

    def __init__(self, db_path: Path, jsonl_path: Path):
        self.db_path = db_path
        self.jsonl_path = jsonl_path
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_cycles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cycle_time TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    macro_regime TEXT,
                    dxy_bias TEXT,
                    setup_direction TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    lot_size REAL,
                    risk_reward_ratio REAL,
                    is_valid_setup INTEGER,
                    risk_approved INTEGER,
                    veto_code TEXT,
                    veto_reason TEXT,
                    order_ticket INTEGER
                )
                """
            )
            conn.commit()

    def record_cycle(self, cycle_payload: dict[str, Any]) -> None:
        """Write execution record to SQLite and append structured JSONLine."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO paper_cycles (
                    cycle_time, symbol, macro_regime, dxy_bias, setup_direction,
                    entry_price, stop_loss, take_profit, lot_size, risk_reward_ratio,
                    is_valid_setup, risk_approved, veto_code, veto_reason, order_ticket
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cycle_payload.get("cycle_time"),
                    cycle_payload.get("symbol"),
                    cycle_payload.get("macro_regime"),
                    cycle_payload.get("dxy_bias"),
                    cycle_payload.get("setup_direction"),
                    cycle_payload.get("entry_price"),
                    cycle_payload.get("stop_loss"),
                    cycle_payload.get("take_profit"),
                    cycle_payload.get("lot_size"),
                    cycle_payload.get("risk_reward_ratio"),
                    1 if cycle_payload.get("is_valid_setup") else 0,
                    1 if cycle_payload.get("risk_approved") else 0,
                    cycle_payload.get("veto_code"),
                    cycle_payload.get("veto_reason"),
                    cycle_payload.get("order_ticket"),
                ),
            )
            conn.commit()

        with open(self.jsonl_path, "a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(cycle_payload, ensure_ascii=False) + "\n")


class PaperTradingRunner:
    """Coordinates M15 bar-close execution cycle with Google ADK InMemoryRunner."""

    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframe_seconds: int = 900,
        db_path: Path | None = None,
        jsonl_path: Path | None = None,
    ):
        self.symbol = symbol
        self.timeframe_seconds = timeframe_seconds
        project_root = Path(__file__).resolve().parent.parent.parent
        self.storage = PaperTradingStorage(
            db_path=db_path or (project_root / "data" / "paper_trading.db"),
            jsonl_path=jsonl_path or (project_root / "logs" / "paper_trading.jsonl"),
        )
        self.is_running = True

    def check_active_positions(self) -> bool:
        """Query MT5 account snapshot to inspect if any open positions exist."""
        snapshot = get_account_snapshot()
        active_count = snapshot.get("positions_count", 0)
        return bool(active_count > 0)

    async def run_single_cycle(self) -> dict[str, Any]:
        """Execute one complete cognitive cycle across the 3 SMC agents."""
        cycle_start_time = datetime.now(UTC).isoformat()
        logger.info(f"[{self.symbol}] Starting paper trading cycle at {cycle_start_time}")

        # Guard Rule: Strict 1 Active Trade
        if self.check_active_positions():
            logger.info(f"[{self.symbol}] Active position detected on MT5. Skipping analysis cycle.")
            cycle_payload = {
                "cycle_time": cycle_start_time,
                "symbol": self.symbol,
                "status": "SKIPPED_ACTIVE_POSITION",
            }
            self.storage.record_cycle(cycle_payload)
            return cycle_payload

        # Initialize Orchestrator and Runner Session
        orchestrator = create_smc_orchestrator()
        runner = InMemoryRunner(agent=orchestrator, app_name="smc_paper_trading")
        session = runner.session_service.create_session_sync(
            app_name=runner.app_name,
            user_id="paper_trader",
            state={"symbol": self.symbol},
        )

        prompt_text = (
            f"Execute SMC quantitative trading workflow for symbol '{self.symbol}' on timeframe M15: "
            f"1. Delegate to macro_sentiment_agent to evaluate tier-1 calendar and breaking headlines. "
            f"2. Delegate to smc_strategy_agent to extract structural BOS/CHOCH and POI zones. "
            f"3. Delegate to adversarial_risk_agent to audit risk rules and place market order if approved."
        )
        message = types.Content(
            parts=[types.Part.from_text(text=prompt_text)],
            role="user",
        )

        events = runner.run(
            user_id="paper_trader",
            session_id=session.id,
            new_message=message,
        )

        # Retrieve structured outputs from session state
        updated_session = runner.session_service.get_session_sync(
            app_name=runner.app_name,
            user_id="paper_trader",
            session_id=session.id,
        )
        session_state = updated_session.state if updated_session else {}

        macro_data = session_state.get(STATE_MACRO_SENTIMENT, {})
        setup_data = session_state.get(STATE_SMC_SETUP, {})
        verdict_data = session_state.get(STATE_RISK_VERDICT, {})

        cycle_payload = {
            "cycle_time": cycle_start_time,
            "symbol": self.symbol,
            "macro_regime": macro_data.get("risk_environment"),
            "dxy_bias": macro_data.get("dxy_bias"),
            "setup_direction": setup_data.get("direction"),
            "entry_price": setup_data.get("entry"),
            "stop_loss": setup_data.get("stop_loss"),
            "take_profit": setup_data.get("take_profit"),
            "lot_size": setup_data.get("lot_size"),
            "risk_reward_ratio": setup_data.get("risk_reward_ratio"),
            "is_valid_setup": setup_data.get("is_valid", False),
            "risk_approved": verdict_data.get("approved", False),
            "veto_code": verdict_data.get("veto_code"),
            "veto_reason": verdict_data.get("veto_reason"),
            "order_ticket": None,
        }

        self.storage.record_cycle(cycle_payload)
        logger.info(
            f"[{self.symbol}] Cycle completed: Macro={cycle_payload['macro_regime']}, "
            f"Approved={cycle_payload['risk_approved']}, Veto={cycle_payload['veto_code']}"
        )
        return cycle_payload

    async def start(self) -> None:
        """Start async bar-close event loop until interrupted."""
        logger.info(f"[{self.symbol}] Paper Trading Service initiated.")
        while self.is_running:
            sleep_duration = calculate_sleep_seconds_to_next_bar(
                current_timestamp=time.time(),
                timeframe_seconds=self.timeframe_seconds,
            )
            logger.info(f"[{self.symbol}] Sleeping {sleep_duration:.1f}s until next M15 bar close.")
            try:
                await asyncio.sleep(sleep_duration)
                if not self.is_running:
                    break
                await self.run_single_cycle()
            except asyncio.CancelledError:
                logger.info(f"[{self.symbol}] Async task cancelled. Shutting down runner.")
                break
            except Exception as exc:
                logger.error(f"[{self.symbol}] Error during paper cycle: {exc}", exc_info=True)
                await asyncio.sleep(10.0)

    def stop(self) -> None:
        """Signal runner to terminate gracefully."""
        self.is_running = False


def main() -> None:
    """CLI Entrypoint to launch the Paper Trading Runner service."""
    import argparse

    parser = argparse.ArgumentParser(description="SMC Multi-Agent Paper Trading Runner")
    parser.add_argument("--symbol", default="XAUUSD", help="Symbol to trade (default: XAUUSD)")
    parser.add_argument("--timeframe-seconds", type=int, default=900, help="Bar period in seconds (default: 900 for M15)")
    parser.add_argument("--once", action="store_true", help="Execute single cycle immediately and exit")
    args = parser.parse_args()

    runner = PaperTradingRunner(
        symbol=args.symbol,
        timeframe_seconds=args.timeframe_seconds,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, runner.stop)
        except NotImplementedError:
            # Signal handlers not implemented on Windows event loops
            pass

    try:
        if args.once:
            loop.run_until_complete(runner.run_single_cycle())
        else:
            loop.run_until_complete(runner.start())
    finally:
        loop.close()
        logger.info(f"[{args.symbol}] Paper Trading Service terminated.")


if __name__ == "__main__":
    main()
