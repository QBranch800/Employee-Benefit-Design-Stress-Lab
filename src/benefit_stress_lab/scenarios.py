from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from benefit_stress_lab import config
from benefit_stress_lab.affordability import most_affected_segment, plan_summary, segment_summary
from benefit_stress_lab.calculations import evaluate_plans
from benefit_stress_lab.recommendations import (
    PROPOSAL_KEY,
    Mitigation,
    add_labels,
    label_scenario,
)
from benefit_stress_lab.schemas import (
    AnalysisSettings,
    Plan,
    StressAssumptions,
    UtilisationCosts,
)

DEFAULT_COST_CHANGES: tuple[float, ...] = (0, 5, 10, 15, 20)
DEFAULT_HIGH_USE_SHIFTS: tuple[float, ...] = (0, 5, 10, 15, 20)
DEFAULT_CONTRIBUTION_SWEEP: tuple[float, ...] = tuple(range(50, 101, 5))


def _select(rng: np.random.Generator, eligible: np.ndarray, share_pct: float) -> np.ndarray:
    chosen = np.zeros(len(eligible), dtype=bool)
    candidates = np.flatnonzero(eligible)
    k = int(round(len(candidates) * share_pct / 100))
    chosen[rng.permutation(candidates)[:k]] = True
    return chosen


def stress_workforce(
    workforce: pd.DataFrame, assumptions: StressAssumptions, costs: UtilisationCosts
) -> pd.DataFrame:
    df = workforce.copy()
    if assumptions.is_baseline():
        return df

    coverage_rng, use_rng = np.random.default_rng(assumptions.seed).spawn(2)
    cost = df["annual_allowed_cost"].to_numpy(dtype=float).copy()
    coverage = df["coverage_tier"].to_numpy(dtype=object).copy()

    shift = assumptions.family_shift_pct
    if shift > 0:
        moved = _select(coverage_rng, coverage == "employee_only", shift)
        coverage[moved] = "family"
        cost[moved] *= costs.family_multiplier
    elif shift < 0:
        moved = _select(coverage_rng, coverage == "family", -shift)
        coverage[moved] = "employee_only"
        cost[moved] /= costs.family_multiplier

    utilisation = df["utilisation_tier"].to_numpy(dtype=object).copy()
    moved = _select(use_rng, utilisation != "high", assumptions.high_use_shift_pct)
    high_cost = np.array([costs.amount("high", c) for c in coverage[moved]])
    cost[moved] = np.maximum(cost[moved], high_cost)
    utilisation[moved] = "high"

    cost *= 1 + assumptions.healthcare_cost_change_pct / 100
    salary = df["annual_salary"].to_numpy(dtype=float) * (1 + assumptions.salary_growth_pct / 100)

    df["coverage_tier"] = coverage.astype(str)
    df["utilisation_tier"] = utilisation.astype(str)
    df["annual_allowed_cost"] = cost
    df["annual_salary"] = salary
    df["salary_band"] = [config.salary_band_for(s) for s in salary]
    return df


def stress_plan(plan: Plan, assumptions: StressAssumptions) -> Plan:
    change = assumptions.healthcare_cost_change_pct
    if not assumptions.apply_to_premiums or change == 0:
        return plan
    factor = 1 + change / 100
    return plan.with_tier_changes(
        **{
            tier: {"annual_premium": plan.tiers[tier].annual_premium * factor}
            for tier in config.COVERAGE_TIERS
        }
    )


@dataclass(frozen=True, eq=False)
class AnalysisResult:
    input_plans: tuple[Plan, ...]
    plans: tuple[Plan, ...]
    workforce: pd.DataFrame
    rows: pd.DataFrame
    summary: pd.DataFrame
    settings: AnalysisSettings
    assumptions: StressAssumptions
    costs: UtilisationCosts
    run_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    model_version: str = config.MODEL_VERSION

    @property
    def baseline_name(self) -> str:
        return self.plans[0].name

    @property
    def plan_names(self) -> list[str]:
        return [plan.name for plan in self.plans]

    @property
    def alternative_names(self) -> list[str]:
        return self.plan_names[1:]

    def input_plan(self, name: str) -> Plan:
        return next(plan for plan in self.input_plans if plan.name == name)

    def segments(self, by: Sequence[str]) -> pd.DataFrame:
        return segment_summary(self.rows, by, self.settings.min_group_size)

    def most_affected(self, plan_name: str) -> dict[str, object] | None:
        return most_affected_segment(self.rows, plan_name, self.settings.min_group_size)


def run_analysis(
    workforce: pd.DataFrame,
    current: Plan,
    alternatives: Sequence[Plan],
    settings: AnalysisSettings | None = None,
    assumptions: StressAssumptions | None = None,
    costs: UtilisationCosts | None = None,
) -> AnalysisResult:
    settings = settings or AnalysisSettings()
    assumptions = assumptions or StressAssumptions()
    costs = costs or UtilisationCosts()
    if len(alternatives) > config.MAX_ALTERNATIVE_PLANS:
        raise ValueError(f"At most {config.MAX_ALTERNATIVE_PLANS} alternative plans are supported.")

    input_plans = (current, *alternatives)
    plans = tuple(stress_plan(plan, assumptions) for plan in input_plans)
    stressed = stress_workforce(workforce, assumptions, costs)
    rows = evaluate_plans(
        stressed,
        plans,
        threshold_pct=settings.affordability_threshold_pct,
        unchanged_tolerance=settings.unchanged_tolerance,
    )
    summary = add_labels(plan_summary(rows), settings)
    return AnalysisResult(
        input_plans=input_plans,
        plans=plans,
        workforce=stressed,
        rows=rows,
        summary=summary,
        settings=settings,
        assumptions=assumptions,
        costs=costs,
    )


def _evaluate_against_baseline(result: AnalysisResult, plan: Plan) -> pd.Series:
    rows = evaluate_plans(
        result.workforce,
        [result.plans[0], stress_plan(plan, result.assumptions)],
        threshold_pct=result.settings.affordability_threshold_pct,
        unchanged_tolerance=result.settings.unchanged_tolerance,
    )
    return plan_summary(rows).iloc[1]


_VARIANT_COLUMNS = (
    "employer_cost_total",
    "employer_saving",
    "employer_saving_pct",
    "above_threshold_pct",
    "above_threshold_change_pp",
    "mean_burden_change",
    "median_burden_change",
    "worse_off_pct",
)


def compare_variants(
    result: AnalysisResult, proposal_name: str, variants: Iterable[Mitigation]
) -> pd.DataFrame:
    proposal = result.summary.loc[proposal_name]
    records = [
        {
            "key": PROPOSAL_KEY,
            "title": "Original proposal",
            "description": "",
            "plan_name": proposal_name,
            **{col: proposal[col] for col in _VARIANT_COLUMNS},
        }
    ]
    for variant in variants:
        row = _evaluate_against_baseline(result, variant.plan)
        records.append(
            {
                "key": variant.key,
                "title": variant.title,
                "description": variant.description,
                "plan_name": variant.plan.name,
                **{col: row[col] for col in _VARIANT_COLUMNS},
            }
        )
    table = pd.DataFrame(records)
    table["label"] = [
        label_scenario(s, c, result.settings)
        for s, c in zip(
            table["employer_saving_pct"], table["above_threshold_change_pp"], strict=True
        )
    ]
    proposal_saving = proposal["employer_saving"]
    table["saving_retained_pct"] = (
        table["employer_saving"] / proposal_saving * 100 if proposal_saving > 0 else np.nan
    )
    return table


def sensitivity_grid(
    workforce: pd.DataFrame,
    current: Plan,
    alternative: Plan,
    settings: AnalysisSettings | None = None,
    base_assumptions: StressAssumptions | None = None,
    costs: UtilisationCosts | None = None,
    cost_changes: Sequence[float] = DEFAULT_COST_CHANGES,
    high_use_shifts: Sequence[float] = DEFAULT_HIGH_USE_SHIFTS,
) -> pd.DataFrame:
    settings = settings or AnalysisSettings()
    base = (base_assumptions or StressAssumptions()).model_dump()
    records = []
    for cost_change in cost_changes:
        for high_shift in high_use_shifts:
            assumptions = StressAssumptions.model_validate(
                {
                    **base,
                    "healthcare_cost_change_pct": cost_change,
                    "high_use_shift_pct": high_shift,
                }
            )
            run = run_analysis(workforce, current, [alternative], settings, assumptions, costs)
            base_row, alt_row = run.summary.iloc[0], run.summary.iloc[1]
            records.append(
                {
                    "healthcare_cost_change_pct": cost_change,
                    "high_use_shift_pct": high_shift,
                    "baseline_above_threshold_pct": base_row["above_threshold_pct"],
                    "above_threshold_pct": alt_row["above_threshold_pct"],
                    "above_threshold_change_pp": alt_row["above_threshold_change_pp"],
                    "employer_saving": alt_row["employer_saving"],
                    "employer_saving_pct": alt_row["employer_saving_pct"],
                    "label": alt_row["label"],
                }
            )
    return pd.DataFrame(records)


def contribution_sweep(
    result: AnalysisResult,
    plan_name: str,
    contribution_pcts: Sequence[float] = DEFAULT_CONTRIBUTION_SWEEP,
) -> pd.DataFrame:
    plan = result.input_plan(plan_name)
    records = []
    for pct in contribution_pcts:
        variant = plan.with_tier_changes(
            **{tier: {"employer_contribution_pct": pct} for tier in config.COVERAGE_TIERS}
        ).renamed(f"{plan_name[:30]} @ {pct:g}%")
        row = _evaluate_against_baseline(result, variant)
        records.append(
            {
                "employer_contribution_pct": pct,
                "employer_cost_total": row["employer_cost_total"],
                "employer_saving": row["employer_saving"],
                "employer_saving_pct": row["employer_saving_pct"],
                "above_threshold_pct": row["above_threshold_pct"],
                "mean_burden_change": row["mean_burden_change"],
            }
        )
    return pd.DataFrame(records)
