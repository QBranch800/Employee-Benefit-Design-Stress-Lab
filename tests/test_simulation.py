import numpy as np
import pytest
from pydantic import ValidationError

from benefit_stress_lab import demo, simulation
from benefit_stress_lab.calculations import EPSILON
from benefit_stress_lab.scenarios import run_analysis
from benefit_stress_lab.schemas import AnalysisSettings, SimulationSettings, StressAssumptions
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


def test_segment_chances_hide_small_groups(workforce):
    settings = AnalysisSettings(min_group_size=40)
    analysis = run_analysis(workforce, demo.current_plan(), demo.demo_alternatives(), settings)
    simulated = run_simulation(analysis, SimulationSettings(runs=60))
    segments = simulated.segments(["salary_band"])
    assert set(segments["plan_name"]) == set(analysis.plan_names)
    small = segments[segments["headcount"] < 40]
    assert len(small) >= len(analysis.plan_names)
    assert small["suppressed"].all()
    for column in ("chance_above_pct", "baseline_chance_above_pct", "chance_change_pp"):
        assert small[column].isna().all()
    shown = segments[~segments["suppressed"]]
    assert len(shown) > 0
    assert shown["chance_above_pct"].between(0, 100).all()
    per_plan = segments.groupby("plan_name")["headcount"].sum()
    assert (per_plan == len(analysis.workforce)).all()


@pytest.fixture(scope="module")
def stressed(workforce):
    with_allowance = demo.proposed_plan("With Allowance").with_tier_changes(
        employee_only={"employer_allowance": 500}, family={"employer_allowance": 1_000}
    )
    return run_analysis(
        workforce,
        demo.current_plan(),
        [demo.scenario_a_balanced(), with_allowance],
        AnalysisSettings(
            affordability_threshold_pct=7.5, savings_target_pct=12, material_increase_pp=1
        ),
        StressAssumptions(
            healthcare_cost_change_pct=12, high_use_shift_pct=10, salary_growth_pct=3
        ),
    )


def test_fixed_simulation_matches_a_stressed_single_run(stressed):
    fixed = run_simulation(stressed, SimulationSettings(runs=50, **FIXED))
    single = stressed.summary
    pairs = {
        "above_threshold_pct": "above_threshold_pct",
        "above_threshold_change_pp": "above_threshold_change_pp",
        "employer_cost": "employer_cost_total",
        "employer_saving": "employer_saving",
        "employer_saving_pct": "employer_saving_pct",
        "mean_burden": "mean_burden",
    }
    for metric, column in pairs.items():
        for point in simulation.RANGE_POINTS:
            np.testing.assert_allclose(fixed.summary[f"{metric}_{point}"], single[column])
    np.testing.assert_allclose(fixed.summary["single_employer_cost"], single["employer_cost_total"])
    np.testing.assert_allclose(fixed.summary["single_employer_saving"], single["employer_saving"])
    np.testing.assert_allclose(
        fixed.summary["single_above_threshold_pct"], single["above_threshold_pct"]
    )
    assert (fixed.summary["label"] == single["label"]).all()
    assert (fixed.summary["label_held_pct"] == 100).all()

    alternatives = single.iloc[1:]
    target_met = alternatives["employer_saving_pct"] >= stressed.settings.savings_target_pct
    material = alternatives["above_threshold_change_pp"] > stressed.settings.material_increase_pp
    assert target_met.any() and not target_met.all()
    np.testing.assert_allclose(
        fixed.summary["savings_target_met_pct"].iloc[1:], target_met.astype(float) * 100
    )
    np.testing.assert_allclose(
        fixed.summary["material_increase_pct"].iloc[1:], material.astype(float) * 100
    )


def test_fixed_simulation_matches_single_run_segments(stressed):
    fixed = run_simulation(stressed, SimulationSettings(runs=50, **FIXED))
    keys = ["plan_name", "salary_band"]
    chances = fixed.segments(["salary_band"]).set_index(keys)
    single = stressed.segments(["salary_band"]).set_index(keys)
    shown = chances[~chances["suppressed"]]
    assert len(shown) > 0
    np.testing.assert_allclose(
        shown["chance_above_pct"], single.loc[shown.index, "above_threshold_pct"]
    )
    baseline = single.loc[stressed.baseline_name, "above_threshold_pct"]
    for name in stressed.alternative_names:
        expected = single.loc[name, "above_threshold_pct"] - baseline
        got = chances.loc[name, "chance_change_pp"]
        np.testing.assert_allclose(got.dropna(), expected.loc[got.dropna().index])
        assert (got.dropna() != 0).any()


def test_year_table_is_internally_consistent(simulated, result):
    years = simulated.years
    base = years[years["plan_name"] == result.baseline_name].set_index("year")
    settings = result.settings
    for name in result.alternative_names:
        plan = years[years["plan_name"] == name].set_index("year")
        np.testing.assert_allclose(
            plan["employer_saving"], base["employer_cost"] - plan["employer_cost"]
        )
        np.testing.assert_allclose(
            plan["employer_saving_pct"], plan["employer_saving"] / base["employer_cost"] * 100
        )
        np.testing.assert_allclose(
            plan["above_threshold_change_pp"],
            plan["above_threshold_pct"] - base["above_threshold_pct"],
        )
        row = simulated.summary.loc[name]
        material = plan["above_threshold_change_pp"] > settings.material_increase_pp + EPSILON
        assert row["material_increase_pct"] == pytest.approx(material.mean() * 100)
        met = plan["employer_saving_pct"] >= settings.savings_target_pct - EPSILON
        assert row["savings_target_met_pct"] == pytest.approx(met.mean() * 100)
        held = plan["label"] == result.summary.loc[name, "label"]
        assert row["label_held_pct"] == pytest.approx(held.mean() * 100)
    odds = simulated.summary["material_increase_pct"].iloc[1:]
    assert ((odds > 0) & (odds < 100)).any()
    assert (simulated.summary["label_held_pct"].iloc[1:] < 100).any()


def test_zero_cost_baseline_gives_missing_saving_share_without_warnings(workforce, recwarn):
    free = demo.current_plan().with_tier_changes(
        employee_only={"employer_contribution_pct": 0}, family={"employer_contribution_pct": 0}
    )
    analysis = run_analysis(workforce, free, [demo.proposed_plan()])
    row = run_simulation(analysis, SimulationSettings(runs=50)).summary.loc["Proposed Plan"]
    assert np.isnan(row["employer_saving_pct_typical"])
    assert np.isfinite(row["above_threshold_pct_typical"])
    assert not [warning for warning in recwarn if issubclass(warning.category, RuntimeWarning)]


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
