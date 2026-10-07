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
    premium = _as_non_negative(annual_premium, "Annual premium")
    pct = _as_percentage(employer_pct, "Employer contribution percentage")
    return premium * pct / 100


def employee_premium_share(annual_premium: ArrayLike, employer_pct: ArrayLike) -> np.ndarray:
    premium = _as_non_negative(annual_premium, "Annual premium")
    return np.maximum(premium - employer_premium_share(premium, employer_pct), 0.0)


def out_of_pocket(
    allowed_cost: ArrayLike,
    deductible: ArrayLike,
    coinsurance_pct: ArrayLike,
    out_of_pocket_max: ArrayLike,
) -> np.ndarray:
    spend = _as_non_negative(allowed_cost, "Allowed healthcare cost")
    ded = _as_non_negative(deductible, "Deductible")
    coins = _as_percentage(coinsurance_pct, "Coinsurance percentage")
    oop_max = _as_non_negative(out_of_pocket_max, "Out-of-pocket maximum")

    deductible_part = np.minimum(spend, ded)
    remaining = np.maximum(spend - ded, 0.0)
    pre_cap = deductible_part + coins / 100 * remaining
    return np.minimum(pre_cap, oop_max)


def apply_allowance(out_of_pocket_cost: ArrayLike, allowance: ArrayLike) -> np.ndarray:
    oop = _as_non_negative(out_of_pocket_cost, "Out-of-pocket cost")
    limit = _as_non_negative(allowance, "Employer allowance")
    return np.minimum(oop, limit)


def total_employee_burden(employee_premium: ArrayLike, employee_oop: ArrayLike) -> np.ndarray:
    premium = _as_non_negative(employee_premium, "Employee premium contribution")
    oop = _as_non_negative(employee_oop, "Out-of-pocket spending")
    return premium + oop


def burden_pct_of_salary(total_burden: ArrayLike, salary: ArrayLike) -> np.ndarray:
    burden = np.asarray(total_burden, dtype=float)
    pay = np.asarray(salary, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        result = np.where(pay > 0, burden * 100 / pay, np.nan)
    return result
