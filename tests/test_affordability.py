import numpy as np
import pytest

from benefit_stress_lab.affordability import (
    burden_quantiles,
    describe_segment,
    most_affected_segment,
    plan_summary,
    segment_summary,
)
from benefit_stress_lab.calculations import evaluate_plans


@pytest.fixture
def rows(workforce, current, proposed):
    return evaluate_plans(workforce, [current, proposed], threshold_pct=10, unchanged_tolerance=50)


def test_summary_reconciles_to_employee_rows(rows, proposed):
    summary = plan_summary(rows)
    plan_rows = rows[rows["plan_name"] == proposed.name]
    totals = summary.loc[proposed.name]
    assert totals["employer_cost_total"] == pytest.approx(plan_rows["employer_cost"].sum())
    assert totals["employee_oop_total"] == pytest.approx(plan_rows["employee_oop"].sum())
    assert totals["mean_burden"] == pytest.approx(plan_rows["total_burden"].mean())
    assert totals["above_threshold_count"] == plan_rows["above_threshold"].sum()
    assert (
        totals["better_off_count"] + totals["unchanged_count"] + totals["worse_off_count"]
        == totals["headcount"]
    )


def test_saving_is_relative_to_baseline(rows, current, proposed):
    summary = plan_summary(rows)
    base = summary.loc[current.name, "employer_cost_total"]
    alt = summary.loc[proposed.name, "employer_cost_total"]
    assert summary.loc[proposed.name, "employer_saving"] == pytest.approx(base - alt)
    assert summary.loc[proposed.name, "employer_saving_pct"] == pytest.approx(
        (base - alt) / base * 100
    )
    assert summary.loc[current.name, "employer_saving"] == 0


@pytest.mark.parametrize(
    "by", [["salary_band"], ["coverage_tier"], ["salary_band", "coverage_tier"]]
)
def test_segment_totals_reconcile_to_workforce(rows, by):
    segments = segment_summary(rows, by, min_group_size=1)
    summary = plan_summary(rows)
    for plan_name, group in segments.groupby("plan_name", sort=False):
        assert group["headcount"].sum() == summary.loc[plan_name, "headcount"]
        assert group["employer_cost_total"].sum() == pytest.approx(
            summary.loc[plan_name, "employer_cost_total"]
        )
        assert (
            group["above_threshold_count"].sum() == summary.loc[plan_name, "above_threshold_count"]
        )


def test_small_segments_are_suppressed(rows):
    segments = segment_summary(rows, ["salary_band", "coverage_tier"], min_group_size=30)
    small = segments[segments["headcount"] < 30]
    assert not small.empty
    assert small["suppressed"].all()
    assert small["median_burden"].isna().all()
    assert small["above_threshold_pct"].isna().all()
    large = segments[segments["headcount"] >= 30]
    assert large["median_burden"].notna().all()


def test_segments_are_ordered(rows):
    segments = segment_summary(rows, ["salary_band"], min_group_size=1)
    first_plan = segments[segments["plan_name"] == segments["plan_name"].iloc[0]]
    assert first_plan["salary_band"].tolist() == ["<40k", "40k-59k", "60k-79k", "80k-119k", "120k+"]


def test_most_affected_segment_is_found(make_workforce, current, proposed):
    wf = make_workforce(
        [{"annual_salary": 35_000, "coverage_tier": "family", "annual_allowed_cost": 9_000}] * 10
        + [{"annual_salary": 150_000, "annual_allowed_cost": 600}] * 10
    )
    wf["employee_id"] = [f"T-{i}" for i in range(len(wf))]
    rows = evaluate_plans(wf, [current, proposed], threshold_pct=10, unchanged_tolerance=50)
    segment = most_affected_segment(rows, proposed.name, min_group_size=10)
    assert segment["salary_band"] == "<40k"
    assert segment["coverage_tier"] == "family"
    assert segment["headcount"] == 10
    assert segment["median_burden_change"] == pytest.approx(2_950)


def test_most_affected_respects_group_size(rows, proposed):
    assert most_affected_segment(rows, proposed.name, min_group_size=10_000) is None


def test_no_segment_reported_when_nobody_is_worse_off(rows, current):
    assert most_affected_segment(rows, current.name, min_group_size=1) is None


def test_describe_segment():
    assert describe_segment("<40k", "family") == "Family coverage, earning below 40k"
    assert (
        describe_segment("120k+", "employee_only") == "Employee only coverage, earning 120k or more"
    )
    assert describe_segment("40k-59k", "family") == "Family coverage, earning 40k-59k"


def test_zero_baseline_cost_gives_nan_saving(make_workforce, current):
    free = current.with_tier_changes(
        employee_only={"employer_contribution_pct": 0}, family={"employer_contribution_pct": 0}
    ).renamed("No employer contribution")
    rows = evaluate_plans(
        make_workforce([{}]), [free, current], threshold_pct=10, unchanged_tolerance=50
    )
    assert np.isnan(plan_summary(rows).iloc[1]["employer_saving_pct"])


def test_burden_quantiles_match_employee_rows(rows, proposed):
    quantiles = burden_quantiles(rows)
    plan_rows = rows[rows["plan_name"] == proposed.name]["burden_pct"]
    assert list(quantiles.columns) == ["p25", "median", "p75", "p95"]
    assert quantiles.loc[proposed.name, "median"] == pytest.approx(plan_rows.median())
    assert quantiles.loc[proposed.name, "p95"] == pytest.approx(plan_rows.quantile(0.95))
    assert (quantiles["p25"] <= quantiles["median"]).all()
