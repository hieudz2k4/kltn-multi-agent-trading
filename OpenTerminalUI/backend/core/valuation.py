from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class DcfStage:
    """
    Represents a discrete growth stage within a multi-stage DCF model.

    Attributes:
        years (int): Duration of the stage in years.
        discount_rate (float): Discount rate (cost of capital) as a decimal (e.g. 0.08 for 8%).
        growth_rate (float): Estimated growth rate of cash flows as a decimal (e.g. 0.05 for 5%).
    """
    years: int
    discount_rate: float
    growth_rate: float


@dataclass
class DcfInputs:
    """
    Input parameters required to run a multi-stage Free Cash Flow to Firm (FCFF) DCF valuation.

    Attributes:
        base_fcf (float): The baseline Free Cash Flow from which projections start.
        stages (list[DcfStage]): A list of growth stages describing projections over time.
        terminal_growth (float): Perpetual growth rate of FCF after final stage as a decimal.
        net_debt (float): Net debt of the firm (total debt minus cash). Defaults to 0.0.
        shares_outstanding (float | None): Number of shares outstanding to calculate value per share.
    """
    base_fcf: float
    stages: list[DcfStage]
    terminal_growth: float
    net_debt: float = 0.0
    shares_outstanding: float | None = None


def _validate_terminal(discount_rate: float, terminal_growth: float) -> None:
    """
    Validates terminal value inputs to prevent math errors or infinite valuations.
    """
    if discount_rate <= terminal_growth:
        raise ValueError("Discount rate must be greater than terminal growth.")


def multi_stage_fcff_dcf(inputs: DcfInputs) -> dict:
    """
    Computes a multi-stage Free Cash Flow to Firm (FCFF) Discounted Cash Flow valuation.

    For each stage, projects future cash flows, discounts them back to present value (PV),
    calculates the Gordon Growth terminal value, discounts it, and aggregates values.

    Args:
        inputs (DcfInputs): Complete set of parameters for the DCF model.

    Returns:
        dict: Valuation metrics containing:
            - enterprise_value (float): Total enterprise value of the firm.
            - equity_value (float): Implied equity value (enterprise value minus net debt).
            - per_share_value (float | None): Implied value per share (if shares_outstanding is provided).
            - pv_fcf_sum (float): Sum of discounted FCFs during stage projection years.
            - terminal_value (float): Terminal value at the start of terminal period.
            - pv_terminal_value (float): Present value of the terminal value.
            - projection_df (pd.DataFrame): DataFrame detailing growth and PV calculations year-by-year.
    """
    if not inputs.stages:
        raise ValueError("At least one DCF stage is required.")
    _validate_terminal(inputs.stages[-1].discount_rate, inputs.terminal_growth)

    projected_rows: list[dict] = []
    fcf = float(inputs.base_fcf)
    t = 0
    pv_sum = 0.0
    for stage in inputs.stages:
        for _ in range(stage.years):
            t += 1
            fcf = fcf * (1 + stage.growth_rate)
            discount_factor = (1 + stage.discount_rate) ** t
            pv_fcf = fcf / discount_factor
            pv_sum += pv_fcf
            projected_rows.append(
                {
                    "year": t,
                    "growth_rate": stage.growth_rate,
                    "discount_rate": stage.discount_rate,
                    "fcf": fcf,
                    "discount_factor": discount_factor,
                    "pv_fcf": pv_fcf,
                }
            )

    terminal_discount = inputs.stages[-1].discount_rate
    terminal_fcf = fcf * (1 + inputs.terminal_growth)
    terminal_value = terminal_fcf / (terminal_discount - inputs.terminal_growth)
    pv_terminal = terminal_value / ((1 + terminal_discount) ** t)

    enterprise_value = pv_sum + pv_terminal
    equity_value = enterprise_value - float(inputs.net_debt)
    per_share = equity_value / float(inputs.shares_outstanding) if inputs.shares_outstanding and inputs.shares_outstanding > 0 else None

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "per_share_value": per_share,
        "pv_fcf_sum": pv_sum,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal,
        "projection_df": pd.DataFrame(projected_rows),
    }


def build_sensitivity_table(
    base_fcf: float,
    years: int,
    growth_rate: float,
    discount_rates: Iterable[float],
    terminal_growth_rates: Iterable[float],
    net_debt: float = 0.0,
    shares_outstanding: float | None = None,
) -> pd.DataFrame:
    """
    Constructs a sensitivity matrix mapping discount rates and terminal growth rates
    to implied equity values or values per share.

    Args:
        base_fcf (float): Baseline FCF.
        years (int): Number of projection years.
        growth_rate (float): Stage 1 growth rate.
        discount_rates (Iterable[float]): List of discount rates to evaluate.
        terminal_growth_rates (Iterable[float]): List of terminal growth rates to evaluate.
        net_debt (float): Net debt. Defaults to 0.0.
        shares_outstanding (float | None): Shares outstanding. Defaults to None.

    Returns:
        pd.DataFrame: A matrix index by discount_rate, with columns for each terminal growth rate,
                      mapping to value per share or total equity value.
    """
    rows: list[dict] = []
    for disc in discount_rates:
        row: dict[str, float | str | None] = {"discount_rate": disc}
        for tg in terminal_growth_rates:
            try:
                result = multi_stage_fcff_dcf(
                    DcfInputs(
                        base_fcf=base_fcf,
                        stages=[DcfStage(years=years, growth_rate=growth_rate, discount_rate=disc)],
                        terminal_growth=tg,
                        net_debt=net_debt,
                        shares_outstanding=shares_outstanding,
                    )
                )
                row[f"tg_{tg:.3f}"] = result["per_share_value"] or result["equity_value"]
            except Exception:
                row[f"tg_{tg:.3f}"] = None
        rows.append(row)
    return pd.DataFrame(rows)


def run_dcf_scenarios(
    base_fcf: float,
    years: int,
    net_debt: float,
    shares_outstanding: float | None,
    bull: tuple[float, float, float],
    base: tuple[float, float, float],
    bear: tuple[float, float, float],
) -> pd.DataFrame:
    """
    Runs three standard valuation scenarios (Bull, Base, Bear) side-by-side.

    Args:
        base_fcf (float): Baseline FCF.
        years (int): Projection period in years.
        net_debt (float): Firm's net debt.
        shares_outstanding (float | None): Number of shares outstanding.
        bull (tuple[float, float, float]): (growth, discount_rate, terminal_growth) for Bull scenario.
        base (tuple[float, float, float]): (growth, discount_rate, terminal_growth) for Base scenario.
        bear (tuple[float, float, float]): (growth, discount_rate, terminal_growth) for Bear scenario.

    Returns:
        pd.DataFrame: Scenario comparison table containing keys: scenario, growth_rate,
                      discount_rate, terminal_growth, enterprise_value, equity_value, and per_share_value.
    """
    scenario_specs = {"bull": bull, "base": base, "bear": bear}
    rows: list[dict] = []
    for name, spec in scenario_specs.items():
        growth, discount, terminal_growth = spec
        result = multi_stage_fcff_dcf(
            DcfInputs(
                base_fcf=base_fcf,
                stages=[DcfStage(years=years, growth_rate=growth, discount_rate=discount)],
                terminal_growth=terminal_growth,
                net_debt=net_debt,
                shares_outstanding=shares_outstanding,
            )
        )
        rows.append(
            {
                "scenario": name,
                "growth_rate": growth,
                "discount_rate": discount,
                "terminal_growth": terminal_growth,
                "enterprise_value": result["enterprise_value"],
                "equity_value": result["equity_value"],
                "per_share_value": result["per_share_value"],
            }
        )
    return pd.DataFrame(rows)


def reverse_dcf_implied_growth(
    target_equity_value: float,
    base_fcf: float,
    years: int,
    discount_rate: float,
    terminal_growth: float,
    net_debt: float = 0.0,
) -> float | None:
    """
    Solves for the implied near-term growth rate that justifies a target market equity value.

    Uses binary search to iteratively converge on the growth rate that minimizes the difference
    between estimated equity value and target_equity_value.

    Args:
        target_equity_value (float): Market capitalization or target equity value.
        base_fcf (float): Baseline FCF.
        years (int): Projection years.
        discount_rate (float): Discount rate.
        terminal_growth (float): Perpetual terminal growth rate.
        net_debt (float): Net debt. Defaults to 0.0.

    Returns:
        float | None: Implied growth rate as a decimal (e.g. 0.125 for 12.5%).
    """
    low, high = -0.5, 1.0
    for _ in range(80):
        mid = (low + high) / 2
        result = multi_stage_fcff_dcf(
            DcfInputs(
                base_fcf=base_fcf,
                stages=[DcfStage(years=years, growth_rate=mid, discount_rate=discount_rate)],
                terminal_growth=terminal_growth,
                net_debt=net_debt,
                shares_outstanding=None,
            )
        )
        est_equity = float(result["equity_value"])
        if abs(est_equity - target_equity_value) / max(target_equity_value, 1e-9) < 1e-4:
            return mid
        if est_equity < target_equity_value:
            low = mid
        else:
            high = mid
    return (low + high) / 2
