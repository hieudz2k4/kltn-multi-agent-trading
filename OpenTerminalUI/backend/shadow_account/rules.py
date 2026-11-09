from __future__ import annotations

from typing import Any


Rule = dict[str, Any]


def _rule(rule_id: str, rule_type: str, description: str, rationale: str, impact_hint: str) -> Rule:
    return {
        "id": rule_id,
        "type": rule_type,
        "description": description,
        "rationale": rationale,
        "impact_hint": impact_hint,
    }


def extract_rules(profile: dict[str, Any], trades: list[dict[str, Any]], *, min_samples: int = 4) -> list[Rule]:
    """Extract deterministic behavior rules from a profile and its trades."""

    rules: list[Rule] = []
    breakdowns = profile.get("breakdowns", {})
    by_setup = breakdowns.get("by_setup", {})
    by_strategy = breakdowns.get("by_strategy", {})

    for setup, stats in sorted(by_setup.items()):
        if stats.get("count", 0) >= min_samples and (stats.get("expectancy") or 0.0) < 0:
            rules.append(
                _rule(
                    f"avoid_setup:{setup}",
                    "avoid_setup",
                    f"Avoid setup '{setup}' until it is reworked.",
                    f"{stats['count']} trades show expectancy {stats['expectancy']:.2f}.",
                    f"Skipping this setup would avoid its {stats['total_pnl']:.2f} total PnL drag if the pattern persists.",
                )
            )

    positive_setups = [
        (setup, stats)
        for setup, stats in by_setup.items()
        if stats.get("count", 0) >= min_samples and (stats.get("expectancy") or 0.0) > 0
    ]
    positive_setups.sort(key=lambda item: (-(item[1].get("expectancy") or 0.0), item[0]))
    if positive_setups:
        names = ", ".join(setup for setup, _ in positive_setups[:3])
        rules.append(
            _rule(
                f"focus_setups:{'|'.join(setup for setup, _ in positive_setups[:3])}",
                "focus_setups",
                f"Prioritize positive-expectancy setup(s): {names}.",
                "These setups have the strongest observed expectancy with enough samples.",
                "Use this as allocation guidance; the shadow backtest does not remove trades for focus-only rules.",
            )
        )

    negative_emotions = profile.get("biases", {}).get("emotion_leakage", {}).get("evidence", {}).get("negative_emotions", {})
    for emotion, stats in sorted(negative_emotions.items()):
        if stats.get("count", 0) >= min_samples:
            rules.append(
                _rule(
                    f"avoid_emotion:{emotion}",
                    "avoid_emotion",
                    f"Avoid entering trades when emotion is '{emotion}'.",
                    f"{stats['count']} trades with this emotion show expectancy {stats['expectancy']:.2f}.",
                    "Use as a pre-trade circuit breaker when this emotion is present.",
                )
            )

    holding_buckets = breakdowns.get("holding_bucket", {})
    long_bucket = holding_buckets.get(">20d")
    if long_bucket and long_bucket.get("count", 0) >= min_samples and (long_bucket.get("expectancy") or 0.0) < 0:
        rules.append(
            _rule(
                "max_holding_days:20",
                "max_holding_days",
                "Review or exit trades that remain open beyond 20 days.",
                f">20d trades show expectancy {long_bucket['expectancy']:.2f}.",
                "The shadow backtest skips historical closed trades that exceeded this holding window.",
            )
        )

    biases = profile.get("biases", {})
    if biases.get("disposition_effect", {}).get("severity") == "high":
        rules.append(
            _rule(
                "cut_losers",
                "cut_losers",
                "Cut losing trades faster instead of extending holding time.",
                biases["disposition_effect"].get("detail", "Losers are held longer than winners."),
                "Targets the holding-time gap between winners and losers.",
            )
        )

    if biases.get("overtrading", {}).get("severity") == "high":
        rules.append(
            _rule(
                "reduce_frequency",
                "reduce_frequency",
                "Reduce trade frequency and filter low-conviction scratch trades.",
                biases["overtrading"].get("detail", "Trade frequency appears elevated."),
                "Fewer marginal entries should reduce commission drag and noisy scratches.",
            )
        )

    return rules
