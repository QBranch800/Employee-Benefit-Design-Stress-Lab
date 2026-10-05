from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from benefit_stress_lab import config
from benefit_stress_lab.schemas import UtilisationCosts

WORKFORCE_COLUMNS: tuple[str, ...] = (
    "employee_id",
    "annual_salary",
    "salary_band",
    "coverage_tier",
    "age_band",
    "region",
    "utilisation_tier",
    "annual_allowed_cost",
)

AGE_BAND_SHARES: dict[str, float] = {
    "18-24": 0.08,
    "25-34": 0.27,
    "35-44": 0.27,
    "45-54": 0.22,
    "55-64": 0.14,
    "65+": 0.02,
}
FAMILY_LIKELIHOOD_BY_AGE: dict[str, float] = {
    "18-24": 0.3,
    "25-34": 0.9,
    "35-44": 1.4,
    "45-54": 1.3,
    "55-64": 0.8,
    "65+": 0.4,
}
REGION_SHARES: dict[str, float] = {"Region A": 0.5, "Region B": 0.3, "Region C": 0.2}

WITHIN_TIER_SIGMA = 0.35


class WorkforceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headcount: int = Field(default=500, ge=10, le=50_000)
    median_salary: float = Field(default=58_000, ge=15_000, le=500_000)
    salary_spread: float = Field(
        default=0.45, ge=0.05, le=1.5, description="Lognormal sigma of salaries."
    )
    min_salary: float = Field(default=22_000, gt=0)
    max_salary: float = Field(default=350_000, gt=0)
    family_share: float = Field(default=0.40, ge=0, le=1)
    low_use_share: float = Field(default=0.55, ge=0, le=1)
    medium_use_share: float = Field(default=0.33, ge=0, le=1)
    high_use_share: float = Field(default=0.12, ge=0, le=1)
    seed: int = Field(default=2026, ge=0)

    @model_validator(mode="after")
    def _consistent(self) -> WorkforceSettings:
        if not self.min_salary < self.max_salary:
            raise ValueError("Minimum salary must be below maximum salary.")
        if not self.min_salary <= self.median_salary <= self.max_salary:
            raise ValueError("Median salary must lie between the minimum and maximum.")
        total = self.low_use_share + self.medium_use_share + self.high_use_share
        if abs(total - 1) > 1e-6:
            raise ValueError(f"Utilisation shares must sum to 100% (currently {total:.0%}).")
        return self

    @property
    def utilisation_shares(self) -> dict[str, float]:
        return {
            "low": self.low_use_share,
            "medium": self.medium_use_share,
            "high": self.high_use_share,
        }


def _exact_counts(shares: dict[str, float], total: int) -> dict[str, int]:
    raw = {key: share * total for key, share in shares.items()}
    counts = {key: int(np.floor(value)) for key, value in raw.items()}
    shortfall = total - sum(counts.values())
    by_remainder = sorted(raw, key=lambda key: raw[key] - counts[key], reverse=True)
    for key in by_remainder[:shortfall]:
        counts[key] += 1
    return counts


def generate_workforce(
    settings: WorkforceSettings | None = None,
    costs: UtilisationCosts | None = None,
) -> pd.DataFrame:
    settings = settings or WorkforceSettings()
    costs = costs or UtilisationCosts()
    rng = np.random.default_rng(settings.seed)
    n = settings.headcount

    salary = rng.lognormal(np.log(settings.median_salary), settings.salary_spread, n)
    salary = np.clip(salary, settings.min_salary, settings.max_salary)
    salary = np.round(salary / 100) * 100

    ages = list(AGE_BAND_SHARES)
    age_band = rng.choice(ages, size=n, p=list(AGE_BAND_SHARES.values()))

    weighted = sum(AGE_BAND_SHARES[a] * FAMILY_LIKELIHOOD_BY_AGE[a] for a in ages)
    family_prob = {
        a: min(1.0, settings.family_share * FAMILY_LIKELIHOOD_BY_AGE[a] / weighted) for a in ages
    }
    is_family = rng.random(n) < np.array([family_prob[a] for a in age_band])
    coverage_tier = np.where(is_family, "family", "employee_only")

    region = rng.choice(list(REGION_SHARES), size=n, p=list(REGION_SHARES.values()))

    use_counts = _exact_counts(settings.utilisation_shares, n)
    utilisation_tier = rng.permutation(
        np.concatenate([np.repeat(tier, count) for tier, count in use_counts.items()])
    )

    base_cost = np.array(
        [costs.amount(u, c) for u, c in zip(utilisation_tier, coverage_tier, strict=True)]
    )
    spread = rng.lognormal(-(WITHIN_TIER_SIGMA**2) / 2, WITHIN_TIER_SIGMA, n)
    allowed_cost = np.round(base_cost * spread / 10) * 10

    width = max(4, len(str(n)))
    workforce = pd.DataFrame(
        {
            "employee_id": [f"EMP-{i:0{width}d}" for i in range(1, n + 1)],
            "annual_salary": salary,
            "salary_band": [config.salary_band_for(s) for s in salary],
            "coverage_tier": coverage_tier,
            "age_band": age_band,
            "region": region,
            "utilisation_tier": utilisation_tier,
            "annual_allowed_cost": allowed_cost,
        }
    )
    return workforce[list(WORKFORCE_COLUMNS)]
