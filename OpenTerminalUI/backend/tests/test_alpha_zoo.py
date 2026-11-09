from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.alpha_zoo import operators as op
from backend.alpha_zoo.evaluate import _build_panels, _evaluate_on_panels, _has_enough_rows
from backend.alpha_zoo.factors import FACTOR_REGISTRY


def _synthetic_frames(rows: int = 320, symbols: int = 6) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    index = pd.date_range("2024-01-01", periods=rows, freq="B", tz="UTC")
    frames: dict[str, pd.DataFrame] = {}
    for i in range(symbols):
        drift = 0.0002 + i * 0.00005
        ret = rng.normal(drift, 0.015, rows)
        close = 100 * np.exp(np.cumsum(ret))
        open_ = close * (1 + rng.normal(0, 0.003, rows))
        high = np.maximum(open_, close) * (1 + rng.uniform(0, 0.01, rows))
        low = np.minimum(open_, close) * (1 - rng.uniform(0, 0.01, rows))
        volume = rng.integers(100_000, 2_000_000, rows).astype(float)
        frames[f"S{i}"] = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
            index=index,
        )
    return frames


def test_core_operators_on_known_inputs() -> None:
    df = pd.DataFrame({"A": [1.0, 3.0, 2.0], "B": [2.0, 2.0, 4.0]})
    ranked = op.rank(df)
    assert ranked.loc[0, "A"] == 0.5
    assert ranked.loc[0, "B"] == 1.0
    delta = op.delta(df, 1)
    assert np.isnan(delta.loc[0, "A"])
    assert delta.loc[1, "A"] == 2.0
    ts_ranked = op.ts_rank(pd.DataFrame({"A": [3.0, 1.0, 2.0]}), 3)
    assert ts_ranked.iloc[2, 0] == pytest.approx(2 / 3)


def test_factor_registry_has_required_family_counts() -> None:
    counts = pd.Series([factor.zoo for factor in FACTOR_REGISTRY]).value_counts().to_dict()
    assert counts["academic"] >= 8
    assert counts["alpha101"] >= 18
    assert counts["gtja191"] >= 8
    assert len(FACTOR_REGISTRY) >= 34


def test_one_year_sized_frame_is_not_dropped_by_row_gate() -> None:
    frame = _synthetic_frames(rows=251, symbols=1)["S0"]

    assert _has_enough_rows(frame, forward_days=5)


def test_factors_are_lookahead_safe_under_future_append() -> None:
    panels = _build_panels(_synthetic_frames())
    cut = 260
    truncated = {key: value.iloc[:cut].copy() for key, value in panels.items()}
    for factor in FACTOR_REGISTRY:
        full_values = factor.fn(panels).iloc[cut - 1]
        truncated_values = factor.fn(truncated).iloc[cut - 1]
        pd.testing.assert_series_equal(full_values, truncated_values, check_names=False, check_exact=False, atol=1e-10, rtol=1e-10)


def test_evaluate_ic_math_on_synthetic_academic_factors() -> None:
    panels = _build_panels(_synthetic_frames())
    factors = [factor for factor in FACTOR_REGISTRY if factor.zoo == "academic"]
    results = _evaluate_on_panels(panels, factors, forward_days=5)
    assert len(results) == len(factors)
    finite = [result for result in results if result["ic"] is not None and result["ir"] is not None]
    assert len(finite) >= len(factors) - 1
    assert all(result["status"] in {"alive", "dead", "reversed", "insufficient"} for result in results)
