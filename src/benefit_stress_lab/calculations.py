from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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

EPSILON = 1e-9


def _tier_values(coverage: np.ndarray, plan: Plan, field: str) -> np.ndarray:
    values = np.empty(len(coverage), dtype=float)
    for tier in config.COVERAGE_TIERS:
        values[coverage == tier] = getattr(plan.tiers[tier], field)
    return values


@dataclass(frozen=True)
class PlanTerms:
    salary: np.ndarray
    annual_premium: np.ndarray
    employer_contribution_pct: np.ndarray
    employer_premium: np.ndarray
    employee_premium: np.ndarray
    deductible: np.ndarray
    coinsurance_pct: np.ndarray
    out_of_pocket_max: np.ndarray
    employer_allowance: np.ndarray


@dataclass(frozen=True)
class PlanOutcome:
    oop_before_allowance: np.ndarray
    allowance_paid: np.ndarray
    employee_oop: np.ndarray
    total_burden: np.ndarray
    burden_pct: np.ndarray
    employer_cost: np.ndarray


def plan_terms(workforce: pd.DataFrame, plan: Plan) -> PlanTerms:
    coverage = workforce["coverage_tier"].to_numpy(dtype=object)
    unsupported = set(coverage) - set(config.COVERAGE_TIERS)
    if unsupported:
        raise ValueError(f"Unsupported coverage tier(s): {', '.join(map(str, unsupported))}.")

    salary = workforce["annual_salary"].to_numpy(dtype=float)
    premium = _tier_values(coverage, plan, "annual_premium")
    employer_pct = _tier_values(coverage, plan, "employer_contribution_pct")
    if plan.salary_subsidy is not None:
        eligible = salary < plan.salary_subsidy.salary_below
        subsidy_pct = plan.salary_subsidy.employer_contribution_pct
        employer_pct = np.where(eligible, np.maximum(employer_pct, subsidy_pct), employer_pct)

    return PlanTerms(
        salary=salary,
        annual_premium=premium,
        employer_contribution_pct=employer_pct,
        employer_premium=plan_rules.employer_premium_share(premium, employer_pct),
        employee_premium=plan_rules.employee_premium_share(premium, employer_pct),
        deductible=_tier_values(coverage, plan, "deductible"),
        coinsurance_pct=_tier_values(coverage, plan, "coinsurance_pct"),
        out_of_pocket_max=_tier_values(coverage, plan, "out_of_pocket_max"),
        employer_allowance=_tier_values(coverage, plan, "employer_allowance"),
    )


def apply_terms(terms: PlanTerms, allowed_cost: np.ndarray) -> PlanOutcome:
    oop_before_allowance = plan_rules.out_of_pocket(
        allowed_cost, terms.deductible, terms.coinsurance_pct, terms.out_of_pocket_max
    )
    allowance_paid = plan_rules.apply_allowance(oop_before_allowance, terms.employer_allowance)
    employee_oop = oop_before_allowance - allowance_paid
    total_burden = plan_rules.total_employee_burden(terms.employee_premium, employee_oop)
    return PlanOutcome(
        oop_before_allowance=oop_before_allowance,
        allowance_paid=allowance_paid,
        employee_oop=employee_oop,
        total_burden=total_burden,
        burden_pct=plan_rules.burden_pct_of_salary(total_burden, terms.salary),
        employer_cost=terms.employer_premium + allowance_paid,
    )


def calculate_plan(workforce: pd.DataFrame, plan: Plan) -> pd.DataFrame:
    terms = plan_terms(workforce, plan)
    outcome = apply_terms(terms, workforce["annual_allowed_cost"].to_numpy(dtype=float))

    result = workforce[list(EMPLOYEE_COLUMNS)].reset_index(drop=True).copy()
    result.insert(0, "plan_name", plan.name)
    result["annual_premium"] = terms.annual_premium
    result["employer_contribution_pct_applied"] = terms.employer_contribution_pct
    result["employer_premium"] = terms.employer_premium
    result["employee_premium"] = terms.employee_premium
    result["oop_before_allowance"] = outcome.oop_before_allowance
    result["allowance_paid"] = outcome.allowance_paid
    result["employee_oop"] = outcome.employee_oop
    result["total_burden"] = outcome.total_burden
    result["burden_pct"] = outcome.burden_pct
    result["employer_cost"] = outcome.employer_cost
    return result


def is_above_threshold(burden_pct: pd.Series | np.ndarray, threshold_pct: float) -> np.ndarray:
    return np.asarray(burden_pct, dtype=float) > threshold_pct + EPSILON


def classify_change(burden_change: pd.Series | np.ndarray, tolerance: float) -> np.ndarray:
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
