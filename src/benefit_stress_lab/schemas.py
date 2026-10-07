from __future__ import annotations

from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from benefit_stress_lab import config

CoverageTier = Literal["employee_only", "family"]


class TierRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_premium: float = Field(
        ge=0, description="Total annual premium for this tier (employer + employee share)."
    )
    employer_contribution_pct: float = Field(
        ge=0, le=100, description="Percentage of the premium paid by the employer."
    )
    deductible: float = Field(
        ge=0, description="Allowed cost the employee pays in full before coinsurance starts."
    )
    coinsurance_pct: float = Field(
        ge=0,
        le=100,
        description="Employee's percentage share of allowed cost after the deductible.",
    )
    out_of_pocket_max: float = Field(
        ge=0, description="Cap on the employee's deductible + coinsurance in a year."
    )
    employer_allowance: float = Field(
        default=0,
        ge=0,
        description=(
            "Optional employer-funded allowance that reimburses the employee's "
            "out-of-pocket spending up to this amount (similar to an HRA)."
        ),
    )

    @model_validator(mode="after")
    def _oop_max_not_below_deductible(self) -> TierRules:
        if self.out_of_pocket_max < self.deductible:
            raise ValueError(
                "Out-of-pocket maximum must be at least the deductible: under the simplified "
                "rules the deductible counts toward the out-of-pocket maximum."
            )
        return self


class SalarySubsidy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salary_below: float = Field(
        gt=0, description="Employees earning below this receive the subsidy."
    )
    employer_contribution_pct: float = Field(
        ge=0,
        le=100,
        description=(
            "Minimum employer contribution for eligible employees. The higher of this and the "
            "tier's normal contribution applies, so a subsidy can never reduce support."
        ),
    )


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    tiers: dict[CoverageTier, TierRules]
    salary_subsidy: SalarySubsidy | None = None

    @model_validator(mode="after")
    def _all_tiers_present(self) -> Plan:
        missing = [t for t in config.COVERAGE_TIERS if t not in self.tiers]
        if missing:
            raise ValueError(f"Plan is missing rules for coverage tier(s): {', '.join(missing)}.")
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("Plan name cannot be blank.")
        return self

    def renamed(self, name: str) -> Plan:
        return self.model_copy(update={"name": name}, deep=True)

    def with_tier_changes(self, **changes_by_tier: dict) -> Plan:
        data = self.model_dump()
        for tier, changes in changes_by_tier.items():
            data["tiers"][tier].update(changes)
        return Plan.model_validate(data)

    def to_frame(self) -> pd.DataFrame:
        rows = []
        for tier in config.COVERAGE_TIERS:
            rules = self.tiers[tier]
            rows.append(
                {
                    "plan_name": self.name,
                    "coverage_tier": tier,
                    **rules.model_dump(),
                    "salary_subsidy_below": (
                        self.salary_subsidy.salary_below if self.salary_subsidy else None
                    ),
                    "salary_subsidy_employer_pct": (
                        self.salary_subsidy.employer_contribution_pct
                        if self.salary_subsidy
                        else None
                    ),
                }
            )
        return pd.DataFrame(rows)


class UtilisationCosts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: float = Field(default=600, ge=0)
    medium: float = Field(default=3_500, ge=0)
    high: float = Field(default=18_000, ge=0)
    family_multiplier: float = Field(default=2.6, ge=1, le=10)

    @model_validator(mode="after")
    def _ordered(self) -> UtilisationCosts:
        if not (self.low <= self.medium <= self.high):
            raise ValueError("Utilisation costs must satisfy low ≤ medium ≤ high.")
        return self

    def amount(self, utilisation_tier: str, coverage_tier: str) -> float:
        base = getattr(self, utilisation_tier)
        return base * (self.family_multiplier if coverage_tier == "family" else 1.0)


class AnalysisSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="USD")
    affordability_threshold_pct: float = Field(
        default=config.DEFAULT_AFFORDABILITY_THRESHOLD_PCT, gt=0, le=100
    )
    unchanged_tolerance: float = Field(default=config.DEFAULT_UNCHANGED_TOLERANCE, ge=0)
    min_group_size: int = Field(default=config.DEFAULT_MIN_GROUP_SIZE, ge=1)
    savings_target_pct: float = Field(default=config.DEFAULT_SAVINGS_TARGET_PCT, ge=0, le=100)
    material_increase_pp: float = Field(default=config.DEFAULT_MATERIAL_INCREASE_PP, ge=0, le=100)

    @property
    def currency_symbol(self) -> str:
        return config.CURRENCIES.get(self.currency, self.currency + " ")


class StressAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    healthcare_cost_change_pct: float = Field(default=0, ge=-50, le=200)
    apply_to_premiums: bool = Field(
        default=True, description="Also scale every plan's premiums by the healthcare cost change."
    )
    salary_growth_pct: float = Field(default=0, ge=-50, le=100)
    high_use_shift_pct: float = Field(
        default=0, ge=0, le=100, description="Share of non-high-use employees moved into high use."
    )
    family_shift_pct: float = Field(
        default=0,
        ge=-100,
        le=100,
        description=(
            "Positive: share of employee-only members moved to family coverage. "
            "Negative: share of family members moved to employee-only coverage."
        ),
    )
    seed: int = Field(default=2026, ge=0)

    def is_baseline(self) -> bool:
        return (
            self.healthcare_cost_change_pct == 0
            and self.salary_growth_pct == 0
            and self.high_use_shift_pct == 0
            and self.family_shift_pct == 0
        )


class SimulationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs: int = Field(default=500, ge=50, le=5_000)
    reshuffle_costs: bool = Field(
        default=True,
        description=(
            "Each simulated year, every employee draws a cost from employees with the same "
            "coverage tier. When off, everyone keeps their own cost."
        ),
    )
    individual_variation_pct: float = Field(
        default=25,
        ge=0,
        le=100,
        description="Typical random movement of one employee's cost in a simulated year.",
    )
    cost_level_variation_pct: float = Field(
        default=8,
        ge=0,
        le=50,
        description="Typical random movement of every employee's cost together in a year.",
    )
    seed: int = Field(default=2026, ge=0)

    def is_fixed(self) -> bool:
        return (
            not self.reshuffle_costs
            and self.individual_variation_pct == 0
            and self.cost_level_variation_pct == 0
        )


def format_validation_error(error: ValidationError) -> list[str]:
    messages = []
    for item in error.errors():
        location = " → ".join(str(part) for part in item["loc"] if part != "tiers")
        message = item["msg"].removeprefix("Value error, ")
        messages.append(f"{location}: {message}" if location else message)
    return messages
