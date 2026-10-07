from __future__ import annotations

import math

MODEL_VERSION = "0.2.0"

COVERAGE_TIERS: tuple[str, ...] = ("employee_only", "family")
COVERAGE_TIER_LABELS: dict[str, str] = {
    "employee_only": "Employee only",
    "family": "Family",
}

UTILISATION_TIERS: tuple[str, ...] = ("low", "medium", "high")

SALARY_BANDS: tuple[tuple[str, float, float], ...] = (
    ("<40k", 0, 40_000),
    ("40k-59k", 40_000, 60_000),
    ("60k-79k", 60_000, 80_000),
    ("80k-119k", 80_000, 120_000),
    ("120k+", 120_000, math.inf),
)
SALARY_BAND_LABELS: tuple[str, ...] = tuple(label for label, _, _ in SALARY_BANDS)

AGE_BANDS: tuple[str, ...] = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+")
REGIONS: tuple[str, ...] = ("Region A", "Region B", "Region C")

NOT_PROVIDED = "Not provided"

DEFAULT_AFFORDABILITY_THRESHOLD_PCT = 10.0
DEFAULT_UNCHANGED_TOLERANCE = 50.0
DEFAULT_MIN_GROUP_SIZE = 10
DEFAULT_SAVINGS_TARGET_PCT = 5.0
DEFAULT_MATERIAL_INCREASE_PP = 2.0

MAX_ALTERNATIVE_PLANS = 3

CURRENCIES: dict[str, str] = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$", "AUD": "A$"}


def salary_band_for(salary: float) -> str:
    for label, lower, upper in SALARY_BANDS:
        if lower <= salary < upper:
            return label
    raise ValueError(f"Salary {salary!r} does not fall in any configured band.")
