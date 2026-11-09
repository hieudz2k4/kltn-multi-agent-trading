from __future__ import annotations

import json
from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from backend.shadow_account.profiler import build_profile
from backend.shadow_account.rules import extract_rules
from backend.shadow_account.service import build_report
from backend.shadow_account.shadow import shadow_backtest


def _trade(
    index: int,
    pnl: float,
    *,
    days: int,
    setup: str = "breakout",
    emotion: str = "calm",
    strategy: str = "momentum",
) -> dict[str, Any]:
    entry = datetime(2026, 1, 1) + timedelta(days=index * 3)
    return {
        "symbol": f"T{index}",
        "direction": "LONG",
        "entry_date": entry.isoformat(),
        "exit_date": (entry + timedelta(days=days)).isoformat(),
        "entry_price": 100.0,
        "exit_price": 101.0 if pnl >= 0 else 99.0,
        "quantity": 10,
        "pnl": pnl,
        "pnl_pct": pnl / 1000.0 * 100.0,
        "fees": 0.0,
        "strategy": strategy,
        "setup": setup,
        "emotion": emotion,
        "rating": 3,
        "tags": [],
    }


def _walk_numbers(value: Any) -> list[float]:
    if isinstance(value, dict):
        numbers: list[float] = []
        for item in value.values():
            numbers.extend(_walk_numbers(item))
        return numbers
    if isinstance(value, list):
        numbers = []
        for item in value:
            numbers.extend(_walk_numbers(item))
        return numbers
    if isinstance(value, float):
        return [value]
    return []


def _assert_flat_profile(profile: dict[str, Any]) -> None:
    assert {
        "win_rate",
        "profit_factor",
        "expectancy",
        "avg_holding_winners",
        "avg_holding_losers",
        "biases",
        "by_setup",
        "by_strategy",
        "holding_bucket",
    } <= set(profile)


def test_disposition_effect_high_and_cut_losers_rule() -> None:
    trades = [
        _trade(0, 100, days=2),
        _trade(1, 120, days=2),
        _trade(2, 90, days=2),
        _trade(3, -180, days=7),
        _trade(4, -160, days=7),
        _trade(5, -140, days=7),
    ]

    profile = build_profile(trades)
    rules = extract_rules(profile, trades, min_samples=3)

    assert profile["biases"]["disposition_effect"]["severity"] == "high"
    assert any(rule["type"] == "cut_losers" for rule in rules)


def test_emotion_leakage_extracts_avoid_emotion_and_shadow_improves() -> None:
    trades = [
        _trade(0, -100, days=4, emotion="fear"),
        _trade(1, -120, days=5, emotion="fear"),
        _trade(2, -80, days=4, emotion="fear"),
        _trade(3, -90, days=6, emotion="fear"),
        _trade(4, 150, days=2, emotion="calm"),
        _trade(5, 130, days=2, emotion="calm"),
        _trade(6, 110, days=1, emotion="calm"),
        _trade(7, 140, days=2, emotion="calm"),
    ]

    profile = build_profile(trades)
    rules = extract_rules(profile, trades, min_samples=4)
    result = shadow_backtest(trades, rules)

    assert "fear" in profile["biases"]["emotion_leakage"]["evidence"]["negative_emotions"]
    assert any(rule["id"] == "avoid_emotion:fear" for rule in rules)
    assert result["shadow"]["pnl"] > result["actual"]["pnl"]
    assert {violation["rule_id"] for violation in result["violations"]} >= {"avoid_emotion:fear"}


def test_negative_setup_rule_removes_setup() -> None:
    trades = [
        _trade(0, -100, days=2, setup="chase", emotion="calm"),
        _trade(1, -80, days=2, setup="chase", emotion="calm"),
        _trade(2, -120, days=2, setup="chase", emotion="calm"),
        _trade(3, -60, days=2, setup="chase", emotion="calm"),
        _trade(4, 200, days=2, setup="pullback", emotion="calm"),
        _trade(5, 180, days=2, setup="pullback", emotion="calm"),
    ]

    report = build_report(trades, min_samples=4)
    rules = report["rules"]

    assert report["insufficient_data"] is False
    _assert_flat_profile(report["profile"])
    assert report["profile"]["avg_holding_losers"] == 2.0
    assert any(row["setup"] == "chase" for row in report["profile"]["by_setup"])
    assert any(row["strategy"] == "momentum" for row in report["profile"]["by_strategy"])
    assert report["profile"]["holding_bucket"]
    assert any(rule["id"] == "avoid_setup:chase" for rule in rules)
    assert report["shadow"]["counts"]["skipped"] == 4
    assert all(violation["rule_id"] == "avoid_setup:chase" for violation in report["shadow"]["violations"])


def test_empty_and_two_trade_inputs_do_not_crash() -> None:
    empty = build_report([])
    tiny = build_report([_trade(0, 100, days=1), _trade(1, -100, days=2)])

    assert empty["insufficient_data"] is True
    assert tiny["insufficient_data"] is True
    assert empty["summary"]["insufficient_data"] is True
    assert tiny["summary"]["insufficient_data"] is True
    assert empty["message"]
    assert tiny["message"]
    _assert_flat_profile(empty["profile"])
    _assert_flat_profile(tiny["profile"])
    assert empty["meta"]["closed_trades"] == 0
    assert tiny["meta"]["closed_trades"] == 2


def test_healthy_report_has_top_level_sufficiency_and_flat_profile() -> None:
    report = build_report(
        [
            _trade(0, 100, days=1, setup="a", strategy="swing"),
            _trade(1, 120, days=1, setup="a", strategy="swing"),
            _trade(2, -50, days=4, setup="b", strategy="mean-reversion"),
        ],
        min_samples=2,
    )

    assert report["insufficient_data"] is False
    assert "message" not in report
    _assert_flat_profile(report["profile"])
    assert report["profile"]["win_rate"] == report["profile"]["counts"]["win_rate"]
    assert report["profile"]["profit_factor"] == report["profile"]["counts"]["profit_factor"]
    assert report["profile"]["expectancy"] == report["profile"]["counts"]["expectancy"]
    assert report["profile"]["avg_holding_winners"] == report["profile"]["holding_days"]["avg_holding_winners"]
    assert report["profile"]["avg_holding_losers"] == report["profile"]["holding_days"]["avg_holding_losers"]
    assert {row["setup"] for row in report["profile"]["by_setup"]} == {"a", "b"}
    assert {row["strategy"] for row in report["profile"]["by_strategy"]} == {"swing", "mean-reversion"}
    assert {row["bucket"] for row in report["profile"]["holding_bucket"]} == {"<=1d", "2-5d"}


def test_report_is_json_serializable_without_nan_or_inf() -> None:
    report = build_report(
        [
            _trade(0, 100, days=1, setup="a"),
            _trade(1, 120, days=1, setup="a"),
            _trade(2, -50, days=4, setup="b"),
            _trade(3, -70, days=4, setup="b"),
        ],
        min_samples=2,
    )

    assert report["insufficient_data"] is False
    _assert_flat_profile(report["profile"])
    encoded = json.dumps(report, allow_nan=False)
    assert encoded
    assert all(isfinite(number) for number in _walk_numbers(report))
