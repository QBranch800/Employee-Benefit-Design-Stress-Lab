from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from benefit_stress_lab import config
from benefit_stress_lab.calculations import OUTCOME_BETTER, OUTCOME_UNCHANGED, OUTCOME_WORSE

DIMENSION_ORDER: dict[str, tuple[str, ...]] = {
    "salary_band": config.SALARY_BAND_LABELS,
    "coverage_tier": config.COVERAGE_TIERS,
    "utilisation_tier": config.UTILISATION_TIERS,
    "age_band": (*config.AGE_BANDS, config.NOT_PROVIDED),
}

SEGMENT_METRICS: tuple[str, ...] = (
    "employer_cost_total",
    "total_burden_total",
    "mean_burden",
    "median_burden",
    "median_burden_pct",
    "median_burden_change",
    "median_burden_pct_change",
    "above_threshold_count",
    "above_threshold_pct",
    "worse_off_count",
    "worse_off_pct",
)


def plan_names_in_order(rows: pd.DataFrame) -> list[str]:
    return list(dict.fromkeys(rows["plan_name"]))


def _with_outcome_flags(rows: pd.DataFrame) -> pd.DataFrame:
    return rows.assign(
        better_off=rows["outcome"] == OUTCOME_BETTER,
        unchanged=rows["outcome"] == OUTCOME_UNCHANGED,
        worse_off=rows["outcome"] == OUTCOME_WORSE,
    )


def plan_summary(rows: pd.DataFrame) -> pd.DataFrame:
    names = plan_names_in_order(rows)
    summary = (
        _with_outcome_flags(rows)
        .groupby("plan_name", sort=False)
        .agg(
            headcount=("employee_id", "size"),
            employer_premium_total=("employer_premium", "sum"),
            allowance_total=("allowance_paid", "sum"),
            employer_cost_total=("employer_cost", "sum"),
            employee_premium_total=("employee_premium", "sum"),
            employee_oop_total=("employee_oop", "sum"),
            total_burden_total=("total_burden", "sum"),
            mean_burden=("total_burden", "mean"),
            median_burden=("total_burden", "median"),
            mean_burden_pct=("burden_pct", "mean"),
            median_burden_pct=("burden_pct", "median"),
            above_threshold_count=("above_threshold", "sum"),
            mean_burden_change=("burden_change", "mean"),
            median_burden_change=("burden_change", "median"),
            better_off_count=("better_off", "sum"),
            unchanged_count=("unchanged", "sum"),
            worse_off_count=("worse_off", "sum"),
        )
        .reindex(names)
    )
    headcount = summary["headcount"]
    summary["above_threshold_pct"] = summary["above_threshold_count"] / headcount * 100
    for outcome in ("better_off", "unchanged", "worse_off"):
        summary[f"{outcome}_pct"] = summary[f"{outcome}_count"] / headcount * 100

    baseline = summary.iloc[0]
    summary["employer_saving"] = baseline["employer_cost_total"] - summary["employer_cost_total"]
    base_cost = baseline["employer_cost_total"]
    summary["employer_saving_pct"] = (
        summary["employer_saving"] / base_cost * 100 if base_cost > 0 else np.nan
    )
    summary["above_threshold_change_pp"] = (
        summary["above_threshold_pct"] - baseline["above_threshold_pct"]
    )
    summary.index.name = "plan_name"
    return summary


def burden_quantiles(rows: pd.DataFrame) -> pd.DataFrame:
    quantiles = (
        rows.groupby("plan_name", sort=False)["burden_pct"]
        .quantile([0.05, 0.25, 0.5, 0.75, 0.95])
        .unstack()
        .reindex(plan_names_in_order(rows))
    )
    quantiles.columns = ["p5", "p25", "median", "p75", "p95"]
    return quantiles


def _sort_segments(
    segments: pd.DataFrame, by: Sequence[str], plan_order: list[str]
) -> pd.DataFrame:
    keys = {"plan_name": {name: i for i, name in enumerate(plan_order)}}
    for dim in by:
        order = DIMENSION_ORDER.get(dim) or tuple(sorted(segments[dim].unique()))
        keys[dim] = {value: i for i, value in enumerate(order)}
    sort_cols = ["plan_name", *by]
    ranked = segments.assign(
        **{f"_{c}": segments[c].map(keys[c]).fillna(len(keys[c])) for c in sort_cols}
    )
    ranked = ranked.sort_values([f"_{c}" for c in sort_cols], kind="stable")
    return ranked.drop(columns=[f"_{c}" for c in sort_cols]).reset_index(drop=True)


def segment_summary(
    rows: pd.DataFrame, by: Sequence[str], min_group_size: int = config.DEFAULT_MIN_GROUP_SIZE
) -> pd.DataFrame:
    by = list(by)
    segments = (
        _with_outcome_flags(rows)
        .groupby(["plan_name", *by], sort=False, observed=True)
        .agg(
            headcount=("employee_id", "size"),
            employer_cost_total=("employer_cost", "sum"),
            total_burden_total=("total_burden", "sum"),
            mean_burden=("total_burden", "mean"),
            median_burden=("total_burden", "median"),
            median_burden_pct=("burden_pct", "median"),
            median_burden_change=("burden_change", "median"),
            median_burden_pct_change=("burden_pct_change", "median"),
            above_threshold_count=("above_threshold", "sum"),
            worse_off_count=("worse_off", "sum"),
        )
        .reset_index()
    )
    segments["above_threshold_pct"] = (
        segments["above_threshold_count"] / segments["headcount"] * 100
    )
    segments["worse_off_pct"] = segments["worse_off_count"] / segments["headcount"] * 100
    segments["above_threshold_count"] = segments["above_threshold_count"].astype(float)
    segments["worse_off_count"] = segments["worse_off_count"].astype(float)

    segments["suppressed"] = segments["headcount"] < min_group_size
    segments.loc[segments["suppressed"], list(SEGMENT_METRICS)] = np.nan
    return _sort_segments(segments, by, plan_names_in_order(rows))


def describe_segment(salary_band: str, coverage_tier: str) -> str:
    if salary_band.startswith("<"):
        pay = f"earning below {salary_band[1:]}"
    elif salary_band.endswith("+"):
        pay = f"earning {salary_band[:-1]} or more"
    else:
        pay = f"earning {salary_band}"
    tier = config.COVERAGE_TIER_LABELS.get(coverage_tier, coverage_tier)
    return f"{tier} coverage, {pay}"


def most_affected_segment(
    rows: pd.DataFrame, plan_name: str, min_group_size: int = config.DEFAULT_MIN_GROUP_SIZE
) -> dict[str, object] | None:
    by = ["salary_band", "coverage_tier"]
    segments = segment_summary(rows, by, min_group_size)
    candidates = segments[(segments["plan_name"] == plan_name) & ~segments["suppressed"]]
    if candidates.empty:
        return None
    top = candidates.sort_values(
        ["median_burden_pct_change", "worse_off_pct", "median_burden_change"], ascending=False
    ).iloc[0]
    if not top["median_burden_pct_change"] > 0:
        return None

    baseline_name = plan_names_in_order(rows)[0]
    baseline = segments[
        (segments["plan_name"] == baseline_name)
        & (segments["salary_band"] == top["salary_band"])
        & (segments["coverage_tier"] == top["coverage_tier"])
    ].iloc[0]
    return {
        "salary_band": top["salary_band"],
        "coverage_tier": top["coverage_tier"],
        "description": describe_segment(top["salary_band"], top["coverage_tier"]),
        "headcount": int(top["headcount"]),
        "median_burden_change": float(top["median_burden_change"]),
        "median_burden_pct_change": float(top["median_burden_pct_change"]),
        "above_threshold_pct": float(top["above_threshold_pct"]),
        "baseline_above_threshold_pct": float(baseline["above_threshold_pct"]),
        "worse_off_pct": float(top["worse_off_pct"]),
    }
