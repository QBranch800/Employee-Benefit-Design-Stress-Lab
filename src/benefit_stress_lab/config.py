"""Fixed vocabulary and default settings shared across the engine and the app.

Everything a user might reasonably want to change (thresholds, costs, mixes) is a
default here and an editable field elsewhere. Nothing in this file is a legal,
regulatory, or clinical standard.
"""

from __future__ import annotations

import math

MODEL_VERSION = "0.1.0"

# Coverage tiers supported by the MVP. Richer tiers (employee + spouse, etc.) are V2.
COVERAGE_TIERS: tuple[str, ...] = ("employee_only", "family")
COVERAGE_TIER_LABELS: dict[str, str] = {
    "employee_only": "Employee only",
    "family": "Family",
}

UTILISATION_TIERS: tuple[str, ...] = ("low", "medium", "high")

# Salary bands as (label, lower bound inclusive, upper bound exclusive).
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

# Analysis defaults. All are scenario parameters, not standards.
DEFAULT_AFFORDABILITY_THRESHOLD_PCT = 10.0
DEFAULT_UNCHANGED_TOLERANCE = 50.0
DEFAULT_MIN_GROUP_SIZE = 10
DEFAULT_SAVINGS_TARGET_PCT = 5.0
DEFAULT_MATERIAL_INCREASE_PP = 2.0

MAX_ALTERNATIVE_PLANS = 3

CURRENCIES: dict[str, str] = {"USD": "$", "GBP": "£", "EUR": "€", "CAD": "C$", "AUD": "A$"}


def salary_band_for(salary: float) -> str:
    """Return the salary-band label for a single salary."""
    for label, lower, upper in SALARY_BANDS:
        if lower <= salary < upper:
            return label
    raise ValueError(f"Salary {salary!r} does not fall in any configured band.")
