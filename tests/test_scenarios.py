import numpy as np
import pandas as pd
import pytest

from benefit_stress_lab import demo
from benefit_stress_lab.calculations import OUTCOME_UNCHANGED
from benefit_stress_lab.scenarios import (
    contribution_sweep,
    run_analysis,
    sensitivity_grid,
    stress_plan,
    stress_workforce,
)
from benefit_stress_lab.schemas import StressAssumptions, UtilisationCosts

COSTS = UtilisationCosts()


def test_same_utilisation_is_used_for_every_plan(workforce, current):
    result = run_analysis(workforce, current, demo.demo_alternatives())
    costs_by_plan = result.rows.pivot(
        index="employee_id", columns="plan_name", values="annual_allowed_cost"
    )
    assert costs_by_plan.nunique(axis=1).eq(1).all()


def test_current_versus_current_shows_no_change(workforce, current):
    result = run_analysis(workforce, current, [current.renamed("Copy of current")])
    copy = result.summary.loc["Copy of current"]
    assert copy["employer_saving"] == 0
    assert copy["mean_burden_change"] == 0
    assert copy["above_threshold_change_pp"] == 0
    assert (result.rows["outcome"] == OUTCOME_UNCHANGED).all()


def test_demo_scenarios_tell_their_stories(workforce, current):
    result = run_analysis(workforce, current, demo.demo_alternatives())
    a, b, c = (result.summary.loc[name] for name in result.alternative_names)
    assert a["label"] == "Balanced"
    assert b["employer_saving"] > c["employer_saving"] > 0
    assert b["above_threshold_change_pp"] > c["above_threshold_change_pp"]
    assert result.most_affected(result.alternative_names[1])["salary_band"] == "<40k"


def test_too_many_alternatives_are_rejected(workforce, current):
    alternatives = [current.renamed(f"Alt {i}") for i in range(4)]
    with pytest.raises(ValueError, match="At most 3"):
        run_analysis(workforce, current, alternatives)


class TestStress:
    def test_no_stress_leaves_workforce_unchanged(self, workforce):
        pd.testing.assert_frame_equal(
            stress_workforce(workforce, StressAssumptions(), COSTS), workforce
        )

    def test_cost_change_scales_costs_and_premiums(self, workforce, current):
        assumptions = StressAssumptions(healthcare_cost_change_pct=10)
        stressed = stress_workforce(workforce, assumptions, COSTS)
        np.testing.assert_allclose(
            stressed["annual_allowed_cost"], workforce["annual_allowed_cost"] * 1.1
        )
        assert stress_plan(current, assumptions).tiers["family"].annual_premium == pytest.approx(
            16_500
        )
        unscaled = StressAssumptions(healthcare_cost_change_pct=10, apply_to_premiums=False)
        assert stress_plan(current, unscaled).tiers["family"].annual_premium == 15_000

    def test_high_use_shift_moves_the_right_number(self, workforce):
        stressed = stress_workforce(workforce, StressAssumptions(high_use_shift_pct=10), COSTS)
        eligible = (workforce["utilisation_tier"] != "high").sum()
        moved = (stressed["utilisation_tier"] == "high").sum() - (
            workforce["utilisation_tier"] == "high"
        ).sum()
        assert moved == round(eligible * 0.10)
        assert (stressed["annual_allowed_cost"] >= workforce["annual_allowed_cost"]).all()

    def test_larger_shift_contains_smaller_shift(self, workforce):
        small = stress_workforce(workforce, StressAssumptions(high_use_shift_pct=5), COSTS)
        large = stress_workforce(workforce, StressAssumptions(high_use_shift_pct=15), COSTS)
        small_high = set(small.loc[small["utilisation_tier"] == "high", "employee_id"])
        large_high = set(large.loc[large["utilisation_tier"] == "high", "employee_id"])
        assert small_high < large_high

    def test_coverage_shift_scales_costs(self, workforce):
        stressed = stress_workforce(workforce, StressAssumptions(family_shift_pct=20), COSTS)
        moved = (workforce["coverage_tier"] == "employee_only") & (
            stressed["coverage_tier"] == "family"
        )
        assert moved.sum() == round((workforce["coverage_tier"] == "employee_only").sum() * 0.2)
        np.testing.assert_allclose(
            stressed.loc[moved, "annual_allowed_cost"],
            workforce.loc[moved, "annual_allowed_cost"] * COSTS.family_multiplier,
        )

    def test_salary_growth_recomputes_bands(self, make_workforce):
        wf = make_workforce([{"annual_salary": 39_000}])
        stressed = stress_workforce(wf, StressAssumptions(salary_growth_pct=5), COSTS)
        assert stressed.loc[0, "annual_salary"] == pytest.approx(40_950)
        assert stressed.loc[0, "salary_band"] == "40k-59k"

    def test_stress_is_reproducible(self, workforce):
        assumptions = StressAssumptions(high_use_shift_pct=10, family_shift_pct=-10)
        pd.testing.assert_frame_equal(
            stress_workforce(workforce, assumptions, COSTS),
            stress_workforce(workforce, assumptions, COSTS),
        )


def test_sensitivity_grid_is_monotonic(workforce, current, proposed):
    grid = sensitivity_grid(
        workforce, current, proposed, cost_changes=(0, 10, 20), high_use_shifts=(0, 10, 20)
    )
    assert len(grid) == 9
    table = grid.pivot(
        index="high_use_shift_pct",
        columns="healthcare_cost_change_pct",
        values="above_threshold_pct",
    )
    assert (table.diff(axis=0).iloc[1:] >= 0).all().all()
    assert (table.diff(axis=1).iloc[:, 1:] >= 0).all().all()
    baseline_cell = grid.query("healthcare_cost_change_pct == 0 and high_use_shift_pct == 0").iloc[
        0
    ]
    direct = run_analysis(workforce, current, [proposed]).summary.iloc[1]
    assert baseline_cell["above_threshold_pct"] == pytest.approx(direct["above_threshold_pct"])


@pytest.mark.parametrize("change", [-6, 19, 44])
def test_contribution_sweep_survives_scaled_premiums(workforce, change):
    stressed = run_analysis(
        workforce,
        demo.current_plan(),
        demo.demo_alternatives(),
        assumptions=StressAssumptions(healthcare_cost_change_pct=change),
    )
    sweep = contribution_sweep(stressed, "A: Modest Adjustment")
    full = sweep[sweep["employer_contribution_pct"] == 100].iloc[0]
    assert np.isfinite(full["employer_saving"])
    assert np.isfinite(full["above_threshold_pct"])


def test_contribution_sweep_trades_saving_for_affordability(workforce, current, proposed):
    result = run_analysis(workforce, current, [proposed])
    sweep = contribution_sweep(result, proposed.name, (60, 70, 80))
    assert sweep["employer_saving"].is_monotonic_decreasing
    assert sweep["above_threshold_pct"].is_monotonic_decreasing
    at_70 = sweep.loc[sweep["employer_contribution_pct"] == 70].iloc[0]
    assert at_70["employer_saving"] == pytest.approx(
        result.summary.loc[proposed.name, "employer_saving"]
    )


def test_result_keeps_the_unstressed_workforce(workforce, current, proposed):
    assumptions = StressAssumptions(healthcare_cost_change_pct=10, high_use_shift_pct=10)
    result = run_analysis(workforce, current, [proposed], assumptions=assumptions)
    pd.testing.assert_frame_equal(result.input_workforce, workforce)
    assert result.workforce["annual_allowed_cost"].sum() > workforce["annual_allowed_cost"].sum()
