from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from benefit_stress_lab.affordability import sort_segments
from benefit_stress_lab.calculations import EPSILON, apply_terms, is_above_threshold, plan_terms
from benefit_stress_lab.recommendations import label_scenario
from benefit_stress_lab.scenarios import AnalysisResult
from benefit_stress_lab.schemas import SimulationSettings

BATCH_CELLS = 2_000_000
RANGE_POINTS: dict[str, float] = {"low": 5, "typical": 50, "high": 95}
YEAR_METRICS: tuple[str, ...] = (
    "employer_cost",
    "employer_saving",
    "employer_saving_pct",
    "above_threshold_pct",
    "above_threshold_change_pp",
    "mean_burden",
)


@dataclass(frozen=True, eq=False)
class SimulationResult:
    settings: SimulationSettings
    plan_names: tuple[str, ...]
    years: pd.DataFrame
    summary: pd.DataFrame
    chances: pd.DataFrame
    min_group_size: int

    @property
    def baseline_name(self) -> str:
        return self.plan_names[0]

    def segments(self, by: Sequence[str]) -> pd.DataFrame:
        by = list(by)
        segments = (
            self.chances.groupby(["plan_name", *by], sort=False, observed=True)
            .agg(
                headcount=("chance_above_pct", "size"),
                chance_above_pct=("chance_above_pct", "mean"),
            )
            .reset_index()
        )
        baseline = segments.loc[
            segments["plan_name"] == self.baseline_name, [*by, "chance_above_pct"]
        ]
        baseline = baseline.rename(columns={"chance_above_pct": "baseline_chance_above_pct"})
        segments = segments.merge(baseline, on=by, how="left", validate="many_to_one")
        segments["chance_change_pp"] = (
            segments["chance_above_pct"] - segments["baseline_chance_above_pct"]
        )
        segments["suppressed"] = segments["headcount"] < self.min_group_size
        hidden = ["chance_above_pct", "baseline_chance_above_pct", "chance_change_pp"]
        segments.loc[segments["suppressed"], hidden] = np.nan
        return sort_segments(segments, by, list(self.plan_names))


def _factors(
    rng: np.random.Generator, shape: tuple[int, int], variation_pct: float
) -> np.ndarray | float:
    if variation_pct == 0:
        return 1.0
    sigma = math.sqrt(math.log1p((variation_pct / 100) ** 2))
    return np.exp(rng.standard_normal(shape) * sigma - sigma**2 / 2)


def _pools(coverage: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    order = np.argsort(coverage, kind="stable")
    _, first, counts = np.unique(coverage[order], return_index=True, return_counts=True)
    start = np.empty(len(coverage), dtype=int)
    size = np.empty(len(coverage), dtype=int)
    for begin, count in zip(first, counts, strict=True):
        members = order[begin : begin + count]
        start[members] = begin
        size[members] = count
    return order, start, size


def cost_batches(workforce: pd.DataFrame, settings: SimulationSettings) -> Iterator[np.ndarray]:
    cost = workforce["annual_allowed_cost"].to_numpy(dtype=float)
    coverage = workforce["coverage_tier"].to_numpy(dtype=str)
    headcount = len(cost)
    draw_rng, person_rng, year_rng = np.random.default_rng(settings.seed).spawn(3)
    order, start, size = _pools(coverage)
    rows_per_batch = max(1, BATCH_CELLS // max(headcount, 1))
    for begin in range(0, settings.runs, rows_per_batch):
        rows = min(rows_per_batch, settings.runs - begin)
        if settings.reshuffle_costs:
            draws = draw_rng.random((rows, headcount))
            position = np.minimum((draws * size).astype(int), size - 1)
            batch = cost[order[start + position]]
        else:
            batch = np.tile(cost, (rows, 1))
        batch = batch * _factors(person_rng, (rows, headcount), settings.individual_variation_pct)
        yield batch * _factors(year_rng, (rows, 1), settings.cost_level_variation_pct)


def simulate_costs(workforce: pd.DataFrame, settings: SimulationSettings) -> np.ndarray:
    return np.concatenate(list(cost_batches(workforce, settings)), axis=0)


def _year_table(
    result: AnalysisResult,
    employer_cost: np.ndarray,
    above_pct: np.ndarray,
    mean_burden: np.ndarray,
) -> pd.DataFrame:
    runs, plans = employer_cost.shape
    base_cost = employer_cost[:, [0]]
    saving = base_cost - employer_cost
    with np.errstate(divide="ignore", invalid="ignore"):
        saving_pct = np.where(base_cost > 0, saving * 100 / base_cost, np.nan)
    change_pp = above_pct - above_pct[:, [0]]
    years = pd.DataFrame(
        {
            "year": np.repeat(np.arange(1, runs + 1), plans),
            "plan_name": np.tile(np.array(result.plan_names, dtype=object), runs),
            "employer_cost": employer_cost.ravel(),
            "employer_saving": saving.ravel(),
            "employer_saving_pct": saving_pct.ravel(),
            "above_threshold_pct": above_pct.ravel(),
            "above_threshold_change_pp": change_pp.ravel(),
            "mean_burden": mean_burden.ravel(),
        }
    )
    baseline_label = result.summary.iloc[0]["label"]
    years["label"] = [
        baseline_label if name == result.baseline_name else label_scenario(pct, pp, result.settings)
        for name, pct, pp in zip(
            years["plan_name"],
            years["employer_saving_pct"],
            years["above_threshold_change_pp"],
            strict=True,
        )
    ]
    return years


def _summarise(years: pd.DataFrame, result: AnalysisResult) -> pd.DataFrame:
    settings = result.settings
    records = []
    for name, group in years.groupby("plan_name", sort=False):
        single = result.summary.loc[name]
        record: dict[str, object] = {"plan_name": name}
        for metric in YEAR_METRICS:
            for point, percentile in RANGE_POINTS.items():
                record[f"{metric}_{point}"] = float(np.nanpercentile(group[metric], percentile))
        is_baseline = name == result.baseline_name
        target_met = group["employer_saving_pct"] >= settings.savings_target_pct - EPSILON
        material = group["above_threshold_change_pp"] > settings.material_increase_pp + EPSILON
        record["savings_target_met_pct"] = np.nan if is_baseline else float(target_met.mean() * 100)
        record["material_increase_pct"] = np.nan if is_baseline else float(material.mean() * 100)
        record["label"] = single["label"]
        record["label_held_pct"] = float((group["label"] == single["label"]).mean() * 100)
        record["single_employer_cost"] = float(single["employer_cost_total"])
        record["single_employer_saving"] = float(single["employer_saving"])
        record["single_above_threshold_pct"] = float(single["above_threshold_pct"])
        records.append(record)
    return pd.DataFrame(records).set_index("plan_name")


def run_simulation(
    result: AnalysisResult, settings: SimulationSettings | None = None
) -> SimulationResult:
    settings = settings or SimulationSettings()
    workforce = result.workforce
    terms = [plan_terms(workforce, plan) for plan in result.plans]
    threshold = result.settings.affordability_threshold_pct
    shape = (settings.runs, len(terms))
    employer_cost, above_pct, mean_burden = np.empty(shape), np.empty(shape), np.empty(shape)
    years_above = np.zeros((len(terms), len(workforce)))

    done = 0
    for batch in cost_batches(workforce, settings):
        rows = slice(done, done + len(batch))
        for index, plan in enumerate(terms):
            outcome = apply_terms(plan, batch)
            above = is_above_threshold(outcome.burden_pct, threshold)
            employer_cost[rows, index] = outcome.employer_cost.sum(axis=1)
            above_pct[rows, index] = above.mean(axis=1) * 100
            mean_burden[rows, index] = outcome.total_burden.mean(axis=1)
            years_above[index] += above.sum(axis=0)
        done += len(batch)

    years = _year_table(result, employer_cost, above_pct, mean_burden)
    people = workforce[["salary_band", "coverage_tier"]].reset_index(drop=True)
    chances = pd.concat(
        [
            people.assign(plan_name=name, chance_above_pct=years_above[index] / settings.runs * 100)
            for index, name in enumerate(result.plan_names)
        ],
        ignore_index=True,
    )
    return SimulationResult(
        settings=settings,
        plan_names=tuple(result.plan_names),
        years=years,
        summary=_summarise(years, result),
        chances=chances,
        min_group_size=result.settings.min_group_size,
    )
