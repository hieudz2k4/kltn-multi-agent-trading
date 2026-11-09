from __future__ import annotations

from typing import Any


def _get_actual(name: str, metrics: dict, robustness: dict, attribution: dict) -> Any:
    if name == "min_psr":
        return robustness.get("psr")
    if name == "min_alpha":
        return (attribution.get("factor_exposure") or {}).get("alpha_annual")
    metric_name = {
        "min_sharpe": "sharpe",
        "min_cagr": "cagr",
        "max_drawdown": "max_drawdown",
        "min_hit_rate": "hit_rate",
    }.get(name, name)
    return metrics.get(metric_name)


def evaluate(metrics: dict, robustness: dict, attribution: dict, acceptance: dict) -> dict:
    """Evaluate acceptance criteria and robustness into a final verdict."""

    criteria_results: list[dict] = []
    for name, target in (acceptance or {}).items():
        if target is None:
            continue
        actual = _get_actual(name, metrics or {}, robustness or {}, attribution or {})
        passed = False
        if actual is not None:
            try:
                passed = float(actual) >= float(target)
            except Exception:
                passed = False
        criteria_results.append({"name": name, "target": target, "actual": actual, "pass": bool(passed)})

    reasons: list[str] = []
    if not criteria_results:
        reasons.append("No acceptance criteria were provided.")
        return {"status": "inconclusive", "score": 0.0, "criteria_results": [], "reasons": reasons}
    if robustness.get("verdict") == "insufficient":
        reasons.extend(robustness.get("verdict_reasons") or ["Robustness engine reported insufficient evidence."])
        score = sum(1 for item in criteria_results if item["pass"]) / len(criteria_results)
        return {"status": "inconclusive", "score": score, "criteria_results": criteria_results, "reasons": reasons}

    passed_count = sum(1 for item in criteria_results if item["pass"])
    score = passed_count / len(criteria_results)
    failed = [item["name"] for item in criteria_results if not item["pass"]]
    if failed:
        reasons.append(f"Failed acceptance criteria: {', '.join(failed)}.")
        return {"status": "rejected", "score": score, "criteria_results": criteria_results, "reasons": reasons}
    reasons.append("All acceptance criteria passed.")
    return {"status": "accepted", "score": score, "criteria_results": criteria_results, "reasons": reasons}
