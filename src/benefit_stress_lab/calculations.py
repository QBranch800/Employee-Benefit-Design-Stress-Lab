"""Apply plans to a workforce and compare every employee with the baseline plan.

Each employee keeps the same allowed healthcare cost under every plan, so any
difference between plans is caused by plan design alone.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from benefit_stress_lab import config, plan_rules
from benefit_stress_lab.schemas import Plan

EMPLOYEE_COLUMNS: tuple[str, ...] = (
    "employee_id",
    "annual_salary",
    "salary_band",
    "coverage_tier",
    "age_band",
    "region",
    "utilisation_tier",
    "annual_allowed_cost",
)

OUTCOME_BETTER = "Better off"
OUTCOME_UNCHANGED = "Unchanged"
OUTCOME_WORSE = "Worse off"
OUTCOMES: tuple[str, ...] = (OUTCOME_BETTER, OUTCOME_UNCHANGED, OUTCOME_WORSE)

# Guards threshold comparisons against floating-point noise.
EPSILON = 1e-9


def _tier_values(coverage: np.ndarray, plan: Plan, field: str) -> np.ndarray:
    values = np.empty(len(coverage), dtype=float)
    for tier in config.COVERAGE_TIERS:
        values[coverage == tier] = getattr(plan.tiers[tier], field)
    return values


def calculate_plan(workforce: pd.DataFrame, plan: Plan) -> pd.DataFrame:
    """Employer and employee costs for every employee under one plan."""
    coverage = workforce["coverage_tier"].to_numpy(dtype=object)
    unsupported = set(coverage) - set(config.COVERAGE_TIERS)
    if unsupported:
        raise ValueError(f"Unsupported coverage tier(s): {', '.join(map(str, unsupported))}.")

    salary = workforce["annual_salary"].to_numpy(dtype=float)
    allowed_cost = workforce["annual_allowed_cost"].to_numpy(dtype=float)

    premium = _tier_values(coverage, plan, "annual_premium")
    employer_pct = _tier_values(coverage, plan, "employer_contribution_pct")
    if plan.salary_subsidy is not None:
        eligible = salary < plan.salary_subsidy.salary_below
        subsidy_pct = plan.salary_subsidy.employer_contribution_pct
        employer_pct = np.where(eligible, np.maximum(employer_pct, subsidy_pct), employer_pct)

    employer_premium = plan_rules.employer_premium_share(premium, employer_pct)
    employee_premium = plan_rules.employee_premium_share(premium, employer_pct)
    oop_before_allowance = plan_rules.out_of_pocket(
        allowed_cost,
        _tier_values(coverage, plan, "deductible"),
        _tier_values(coverage, plan, "coinsurance_pct"),
        _tier_values(coverage, plan, "out_of_pocket_max"),
    )
    allowance_paid = plan_rules.apply_allowance(
        oop_before_allowance, _tier_values(coverage, plan, "employer_allowance")
    )
    employee_oop = oop_before_allowance - allowance_paid
    total_burden = plan_rules.total_employee_burden(employee_premium, employee_oop)

    result = workforce[list(EMPLOYEE_COLUMNS)].reset_index(drop=True).copy()
    result.insert(0, "plan_name", plan.name)
    result["annual_premium"] = premium
    result["employer_contribution_pct_applied"] = employer_pct
    result["employer_premium"] = employer_premium
    result["employee_premium"] = employee_premium
    result["oop_before_allowance"] = oop_before_allowance
    result["allowance_paid"] = allowance_paid
    result["employee_oop"] = employee_oop
    result["total_burden"] = total_burden
    result["burden_pct"] = plan_rules.burden_pct_of_salary(total_burden, salary)
    # An allowance is employer money too, so it counts toward employer cost.
    result["employer_cost"] = employer_premium + allowance_paid
    return result


def is_above_threshold(burden_pct: pd.Series | np.ndarray, threshold_pct: float) -> np.ndarray:
    """True where burden is strictly above the threshold; exactly at it is not above."""
    return np.asarray(burden_pct, dtype=float) > threshold_pct + EPSILON


def classify_change(burden_change: pd.Series | np.ndarray, tolerance: float) -> np.ndarray:
    """Label each change as better off, unchanged (within ± tolerance), or worse off."""
    change = np.asarray(burden_change, dtype=float)
    return np.select(
        [change < -tolerance - EPSILON, change > tolerance + EPSILON],
        [OUTCOME_BETTER, OUTCOME_WORSE],
        default=OUTCOME_UNCHANGED,
    )


def evaluate_plans(
    workforce: pd.DataFrame,
    plans: Sequence[Plan],
    *,
    threshold_pct: float,
    unchanged_tolerance: float,
) -> pd.DataFrame:
    """Row-level results for every employee under every plan.

    The first plan is the baseline. Changes are measured per employee against
    their own baseline result.
    """
    if not plans:
        raise ValueError("At least one plan is required.")
    names = [plan.name for plan in plans]
    if len(set(names)) != len(names):
        raise ValueError("Plan names must be unique.")

    rows = pd.concat([calculate_plan(workforce, plan) for plan in plans], ignore_index=True)
    rows["above_threshold"] = is_above_threshold(rows["burden_pct"], threshold_pct)

    baseline = rows.loc[
        rows["plan_name"] == names[0], ["employee_id", "total_burden", "burden_pct"]
    ]
    baseline = baseline.rename(
        columns={"total_burden": "baseline_total_burden", "burden_pct": "baseline_burden_pct"}
    )
    rows = rows.merge(baseline, on="employee_id", how="left", validate="many_to_one")
    rows["burden_change"] = rows["total_burden"] - rows["baseline_total_burden"]
    rows["burden_pct_change"] = rows["burden_pct"] - rows["baseline_burden_pct"]
    rows["outcome"] = classify_change(rows["burden_change"], unchanged_tolerance)
    return rows
