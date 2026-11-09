"""Unit tests for Paper Trading Runner and Persistence."""

import json
import sqlite3
import pytest
from pathlib import Path

from src.runners.paper_trading_runner import (
    PaperTradingRunner,
    PaperTradingStorage,
    calculate_sleep_seconds_to_next_bar,
)


def test_calculate_sleep_seconds_to_next_bar():
    """Verify sleep duration lands exactly at bar close plus safety buffer."""
    # Example: timestamp 910 (which is 10s into second 15-minute bar 900..1800)
    # Remaining to 1800 is 890s + 5s buffer = 895s
    sleep_s = calculate_sleep_seconds_to_next_bar(current_timestamp=910.0, timeframe_seconds=900, buffer_seconds=5)
    assert sleep_s == 895.0

    # Timestamp exactly on bar boundary: 900.0 => 900 - 0 + 5 = 905s
    sleep_exact = calculate_sleep_seconds_to_next_bar(current_timestamp=900.0, timeframe_seconds=900, buffer_seconds=5)
    assert sleep_exact == 905.0


def test_paper_trading_storage_sqlite_and_jsonl(tmp_path: Path):
    """Verify SQLite persistence and JSONLines appending."""
    db_file = tmp_path / "test_paper.db"
    jsonl_file = tmp_path / "test_paper.jsonl"

    storage = PaperTradingStorage(db_path=db_file, jsonl_path=jsonl_file)

    payload = {
        "cycle_time": "2026-11-09T14:30:05Z",
        "symbol": "XAUUSD",
        "macro_regime": "RISK_ON",
        "dxy_bias": "BEARISH",
        "setup_direction": "BUY",
        "entry_price": 2726.50,
        "stop_loss": 2722.50,
        "take_profit": 2738.50,
        "lot_size": 0.25,
        "risk_reward_ratio": 3.0,
        "is_valid_setup": True,
        "risk_approved": True,
        "veto_code": None,
        "veto_reason": None,
        "order_ticket": 123456,
    }

    storage.record_cycle(payload)

    # Verify SQLite insertion
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, macro_regime, entry_price, risk_approved FROM paper_cycles")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "XAUUSD"
        assert row[1] == "RISK_ON"
        assert row[2] == 2726.50
        assert row[3] == 1

    # Verify JSONLines appending
    with open(jsonl_file, "r", encoding="utf-8") as f:
        line = f.readline().strip()
        record = json.loads(line)
        assert record["symbol"] == "XAUUSD"
        assert record["order_ticket"] == 123456


@pytest.mark.asyncio
async def test_paper_runner_skip_on_active_position(tmp_path: Path, monkeypatch):
    """Verify runner skips new analysis when open position is present on MT5."""
    db_file = tmp_path / "test_paper.db"
    jsonl_file = tmp_path / "test_paper.jsonl"

    runner = PaperTradingRunner(
        symbol="XAUUSD",
        db_path=db_file,
        jsonl_path=jsonl_file,
    )

    # Mock active positions count > 0
    monkeypatch.setattr(runner, "check_active_positions", lambda: True)

    cycle_result = await runner.run_single_cycle()
    assert cycle_result["status"] == "SKIPPED_ACTIVE_POSITION"

    # Verify skip record saved to DB
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT symbol, macro_regime FROM paper_cycles")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "XAUUSD"
        assert row[1] is None
