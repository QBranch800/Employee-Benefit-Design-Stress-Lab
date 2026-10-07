import numpy as np
import pytest
from pydantic import ValidationError

from benefit_stress_lab import demo, simulation
from benefit_stress_lab.scenarios import run_analysis
from benefit_stress_lab.schemas import AnalysisSettings, SimulationSettings
from benefit_stress_lab.simulation import run_simulation, simulate_costs

FIXED = {"reshuffle_costs": False, "individual_variation_pct": 0, "cost_level_variation_pct": 0}


@pytest.fixture(scope="module")
def result(workforce):
    return run_analysis(workforce, demo.current_plan(), demo.demo_alternatives())


@pytest.fixture(scope="module")
def simulated(result):
    return run_simulation(result, SimulationSettings(runs=300))


def test_without_variation_every_year_matches_the_single_run(result):
    fixed = run_simulation(result, SimulationSettings(runs=50, **FIXED))
    single = result.summary
    for point in simulation.RANGE_POINTS:
        np.testing.assert_allclose(
            fixed.summary[f"above_threshold_pct_{point}"], single["above_threshold_pct"]
        )
        np.testing.assert_allclose(
            fixed.summary[f"employer_cost_{point}"], single["employer_cost_total"]
        )
        np.testing.assert_allclose(fixed.summary[f"mean_burden_{point}"], single["mean_burden"])
    assert (fixed.summary["label_held_pct"] == 100).all()
    assert (fixed.years["label"] == fixed.years["plan_name"].map(single["label"])).all()


def test_same_seed_gives_the_same_years(result):
    settings = SimulationSettings(runs=80, seed=7)
    first, second = run_simulation(result, settings), run_simulation(result, settings)
    assert first.years.equals(second.years)
    assert first.chances.equals(second.chances)


def test_a_different_seed_gives_different_years(result):
    first = run_simulation(result, SimulationSettings(runs=80, seed=7))
    second = run_simulation(result, SimulationSettings(runs=80, seed=8))
    assert not first.years["above_threshold_pct"].equals(second.years["above_threshold_pct"])


def test_batch_size_does_not_change_the_result(result, monkeypatch):
    settings = SimulationSettings(runs=60)
    whole = run_simulation(result, settings)
    monkeypatch.setattr(simulation, "BATCH_CELLS", len(result.workforce) * 7)
    batched = run_simulation(result, settings)
    np.testing.assert_allclose(
        batched.years["above_threshold_pct"], whole.years["above_threshold_pct"]
    )
    np.testing.assert_allclose(
        batched.chances["chance_above_pct"], whole.chances["chance_above_pct"]
    )


def test_costs_are_only_swapped_within_a_coverage_tier(make_workforce):
    workforce = make_workforce(
        [{"coverage_tier": "employee_only", "annual_allowed_cost": 100}] * 6
        + [{"coverage_tier": "family", "annual_allowed_cost": 900}] * 4
    )
    settings = SimulationSettings(runs=50, individual_variation_pct=0, cost_level_variation_pct=0)
    costs = simulate_costs(workforce, settings)
    assert costs.shape == (50, 10)
    assert (costs[:, :6] == 100).all()
    assert (costs[:, 6:] == 900).all()


def test_reshuffling_draws_from_colleagues_costs(make_workforce):
    workforce = make_workforce([{"annual_allowed_cost": cost} for cost in (0, 0, 0, 8_000)])
    settings = SimulationSettings(
        runs=2_000, individual_variation_pct=0, cost_level_variation_pct=0
    )
    costs = simulate_costs(workforce, settings)
    assert set(np.unique(costs)) == {0.0, 8_000.0}
    assert (costs == 8_000).mean() == pytest.approx(0.25, abs=0.02)


def test_individual_variation_averages_out(workforce):
    settings = SimulationSettings(
        runs=400, reshuffle_costs=False, individual_variation_pct=40, cost_level_variation_pct=0
    )
    costs = simulate_costs(workforce, settings)
    base = workforce["annual_allowed_cost"].to_numpy()
    assert (costs != base).any()
    assert costs.mean() == pytest.approx(base.mean(), rel=0.01)


def test_cost_level_moves_everyone_together(workforce):
    settings = SimulationSettings(
        runs=200, reshuffle_costs=False, individual_variation_pct=0, cost_level_variation_pct=10
    )
    costs = simulate_costs(workforce, settings)
    ratios = costs / workforce["annual_allowed_cost"].to_numpy()
    np.testing.assert_allclose(ratios, np.broadcast_to(ratios[:, [0]], ratios.shape))
    yearly = ratios[:, 0]
    assert yearly.std() == pytest.approx(0.10, abs=0.02)
    assert yearly.mean() == pytest.approx(1.0, abs=0.02)


def test_known_chance_of_exceeding_the_threshold(make_workforce):
    workforce = make_workforce(
        [
            {"annual_salary": 40_000, "annual_allowed_cost": cost}
            for cost in [0] * 10 + [20_000] * 10
        ]
    )
    analysis = run_analysis(workforce, demo.current_plan(), [demo.proposed_plan()])
    assert analysis.summary.iloc[0]["above_threshold_pct"] == 50
    settings = SimulationSettings(
        runs=2_000, individual_variation_pct=0, cost_level_variation_pct=0
    )
    simulated = run_simulation(analysis, settings)
    current = simulated.chances[simulated.chances["plan_name"] == "Current Plan"]
    assert current["chance_above_pct"].to_numpy() == pytest.approx(50, abs=4)
    assert simulated.summary.loc["Current Plan", "above_threshold_pct_typical"] == pytest.approx(
        50, abs=5
    )
    assert simulated.summary.loc["Current Plan", "above_threshold_pct_low"] < 50
    assert simulated.summary.loc["Current Plan", "above_threshold_pct_high"] > 50


def test_ranges_are_ordered(simulated):
    for metric in simulation.YEAR_METRICS:
        low, typical, high = (
            simulated.summary[f"{metric}_{point}"] for point in simulation.RANGE_POINTS
        )
        assert (low <= typical + 1e-9).all()
        assert (typical <= high + 1e-9).all()


def test_spread_table_matches_the_summary(simulated, result):
    spread = simulated.spread("above_threshold_pct")
    assert list(spread.index) == result.plan_names
    assert list(spread.columns) == ["p5", "p25", "median", "p75", "p95"]
    assert (spread.diff(axis=1).iloc[:, 1:] >= -1e-9).all().all()
    np.testing.assert_allclose(spread["median"], simulated.summary["above_threshold_pct_typical"])
    np.testing.assert_allclose(spread["p5"], simulated.summary["above_threshold_pct_low"])
    np.testing.assert_allclose(spread["p95"], simulated.summary["above_threshold_pct_high"])


def test_baseline_has_no_saving_and_no_verdict_odds(simulated):
    baseline = simulated.summary.iloc[0]
    assert baseline["employer_saving_typical"] == 0
    assert baseline["above_threshold_change_pp_high"] == 0
    assert np.isnan(baseline["savings_target_met_pct"])
    assert baseline["label_held_pct"] == 100


def test_premium_only_plans_cost_the_employer_the_same_every_year(simulated, result):
    summary = simulated.summary
    np.testing.assert_allclose(summary["employer_cost_low"], summary["employer_cost_high"])
    np.testing.assert_allclose(
        summary["employer_cost_typical"], result.summary["employer_cost_total"]
    )


def test_an_allowance_makes_the_employer_cost_uncertain(workforce):
    with_allowance = demo.proposed_plan("With Allowance").with_tier_changes(
        employee_only={"employer_allowance": 1_000}, family={"employer_allowance": 2_000}
    )
    analysis = run_analysis(workforce, demo.current_plan(), [with_allowance])
    row = run_simulation(analysis, SimulationSettings(runs=200)).summary.loc["With Allowance"]
    assert row["employer_cost_low"] < row["employer_cost_typical"] < row["employer_cost_high"]


def test_saving_target_odds_follow_the_target(workforce):
    settings = AnalysisSettings(savings_target_pct=50)
    analysis = run_analysis(workforce, demo.current_plan(), [demo.proposed_plan()], settings)
    row = run_simulation(analysis, SimulationSettings(runs=100)).summary.loc["Proposed Plan"]
    assert row["savings_target_met_pct"] == 0
    assert 0 <= row["material_increase_pct"] <= 100


def test_segment_chances_hide_small_groups(simulated, result):
    segments = simulated.segments(["salary_band", "coverage_tier"])
    assert set(segments["plan_name"]) == set(result.plan_names)
    small = segments[segments["headcount"] < result.settings.min_group_size]
    assert small["suppressed"].all()
    assert small["chance_above_pct"].isna().all()
    shown = segments[~segments["suppressed"]]
    assert shown["chance_above_pct"].between(0, 100).all()
    per_plan = segments.groupby("plan_name")["headcount"].sum()
    assert (per_plan == len(result.workforce)).all()


def test_segment_chances_average_to_the_simulated_share(simulated):
    bands = simulated.segments(["salary_band"])
    for name, group in bands.groupby("plan_name"):
        weighted = (group["chance_above_pct"] * group["headcount"]).sum() / group["headcount"].sum()
        years = simulated.years[simulated.years["plan_name"] == name]
        assert weighted == pytest.approx(years["above_threshold_pct"].mean())


@pytest.mark.parametrize("bad", [{"runs": 10}, {"runs": 10_000}, {"individual_variation_pct": -1}])
def test_settings_are_validated(bad):
    with pytest.raises(ValidationError):
        SimulationSettings(**bad)


def test_fixed_settings_are_recognised():
    assert SimulationSettings(**FIXED).is_fixed()
    assert not SimulationSettings().is_fixed()
