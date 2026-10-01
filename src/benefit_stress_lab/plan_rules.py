"""Simplified cost-sharing rules.

These functions implement the formulas in METHODOLOGY.md. They accept scalars or
NumPy arrays so the same code serves a hand-checked single employee and a whole
workforce. Real plans have co-payments, embedded family deductibles, pharmacy
tiers, and network rules; none of those are modelled here.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike


def _as_non_negative(values: ArrayLike, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if np.any(np.isnan(array)):
        raise ValueError(f"{name} contains missing values.")
    if np.any(array < 0):
        raise ValueError(f"{name} cannot be negative.")
    return array


def _as_percentage(values: ArrayLike, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if np.any(np.isnan(array)) or np.any((array < 0) | (array > 100)):
        raise ValueError(f"{name} must be between 0 and 100.")
    return array


def employer_premium_share(annual_premium: ArrayLike, employer_pct: ArrayLike) -> np.ndarray:
    """Employer premium contribution = premium × employer contribution %."""
    premium = _as_non_negative(annual_premium, "Annual premium")
    pct = _as_percentage(employer_pct, "Employer contribution percentage")
    return premium * pct / 100


def employee_premium_share(annual_premium: ArrayLike, employer_pct: ArrayLike) -> np.ndarray:
    """Employee premium contribution = premium − employer share.

    Computed by subtraction so the two shares always sum exactly to the premium.
    """
    premium = _as_non_negative(annual_premium, "Annual premium")
    return premium - employer_premium_share(premium, employer_pct)


def out_of_pocket(
    allowed_cost: ArrayLike,
    deductible: ArrayLike,
    coinsurance_pct: ArrayLike,
    out_of_pocket_max: ArrayLike,
) -> np.ndarray:
    """Employee cost sharing for a year of allowed healthcare spending.

    spending subject to deductible = min(S, deductible)
    remaining spending             = max(S − deductible, 0)
    pre-cap cost sharing           = deductible part + coinsurance % × remaining
    out-of-pocket                  = min(pre-cap cost sharing, out-of-pocket maximum)
    """
    spend = _as_non_negative(allowed_cost, "Allowed healthcare cost")
    ded = _as_non_negative(deductible, "Deductible")
    coins = _as_percentage(coinsurance_pct, "Coinsurance percentage")
    oop_max = _as_non_negative(out_of_pocket_max, "Out-of-pocket maximum")

    deductible_part = np.minimum(spend, ded)
    remaining = np.maximum(spend - ded, 0.0)
    pre_cap = deductible_part + coins / 100 * remaining
    return np.minimum(pre_cap, oop_max)


def apply_allowance(out_of_pocket_cost: ArrayLike, allowance: ArrayLike) -> np.ndarray:
    """Portion of out-of-pocket cost reimbursed by an employer-funded allowance."""
    oop = _as_non_negative(out_of_pocket_cost, "Out-of-pocket cost")
    limit = _as_non_negative(allowance, "Employer allowance")
    return np.minimum(oop, limit)


def total_employee_burden(employee_premium: ArrayLike, employee_oop: ArrayLike) -> np.ndarray:
    """Total employee burden = employee premium contribution + out-of-pocket spending."""
    premium = _as_non_negative(employee_premium, "Employee premium contribution")
    oop = _as_non_negative(employee_oop, "Out-of-pocket spending")
    return premium + oop


def burden_pct_of_salary(total_burden: ArrayLike, salary: ArrayLike) -> np.ndarray:
    """Burden as a percentage of salary. Returns NaN where salary is zero or missing.

    Validation rejects zero salaries before they reach the engine; NaN here is a
    safety net so a bad value can never produce an infinite or misleading result.
    Multiplying before dividing keeps round cases exact (5,000 on 50,000 is 10.0).
    """
    burden = np.asarray(total_burden, dtype=float)
    pay = np.asarray(salary, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(pay > 0, burden * 100 / pay, np.nan)
    return result
