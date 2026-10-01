"""Engine results compared with hand calculations (specification section 22)."""

import pytest

from benefit_stress_lab.calculations import (
    OUTCOME_BETTER,
    OUTCOME_UNCHANGED,
    OUTCOME_WORSE,
    calculate_plan,
    classify_change,
    evaluate_plans,
)
from benefit_stress_lab.schemas import SalarySubsidy

# Five employees worked by hand under the current and proposed plans.
#   Current  EO: premium 6,000 @80%, ded 500,  coins 20%, max 3,000
#   Current  FA: premium 15,000 @80%, ded 1,000, coins 20%, max 6,000
#   Proposed EO: premium 5,000 @70%, ded 1,500, coins 30%, max 5,000
#   Proposed FA: premium 12,500 @70%, ded 3,000, coins 30%, max 10,000
HAND_CALCULATED = [
    # (tier, salary, spend, current: employer, employee premium, oop, burden;
    #                       proposed: employer, employee premium, oop, burden)
    ("employee_only", 50_000, 0, (4_800, 1_200, 0, 1_200), (3_500, 1_500, 0, 1_500)),
    ("employee_only", 45_000, 400, (4_800, 1_200, 400, 1_600), (3_500, 1_500, 400, 1_900)),
    # Current: 500 + 20% × 2,500. Proposed: 1,500 + 30% × 1,500.
    ("employee_only", 60_000, 3_000, (4_800, 1_200, 1_000, 2_200), (3_500, 1_500, 1_950, 3_450)),
    # Pre-cap 4,400 → capped at 3,000. Proposed pre-cap 7,050 → capped at 5,000.
    ("employee_only", 30_000, 20_000, (4_800, 1_200, 3_000, 4_200), (3_500, 1_500, 5_000, 6_500)),
    # Current: 1,000 + 20% × 8,000. Proposed: 3,000 + 30% × 6,000.
    ("family", 38_000, 9_000, (12_000, 3_000, 2_600, 5_600), (8_750, 3_750, 4_800, 8_550)),
]


@pytest.fixture
def hand_workforce(make_workforce):
    return make_workforce(
        [
            {"coverage_tier": tier, "annual_salary": salary, "annual_allowed_cost": spend}
            for tier, salary, spend, _, _ in HAND_CALCULATED
        ]
    )


@pytest.mark.parametrize("plan_fixture, position", [("current", 3), ("proposed", 4)])
def test_engine_matches_hand_calculations(request, hand_workforce, plan_fixture, position):
    plan = request.getfixturevalue(plan_fixture)
    result = calculate_plan(hand_workforce, plan)
    for i, case in enumerate(HAND_CALCULATED):
        employer, employee, oop, burden = case[position]
        salary = case[1]
        row = result.iloc[i]
        assert row["employer_premium"] == pytest.approx(employer)
        assert row["employee_premium"] == pytest.approx(employee)
        assert row["employee_oop"] == pytest.approx(oop)
        assert row["total_burden"] == pytest.approx(burden)
        assert row["burden_pct"] == pytest.approx(burden / salary * 100)
        assert row["employer_cost"] == pytest.approx(employer)


def test_family_example_from_walkthrough(hand_workforce, current, proposed):
    rows = evaluate_plans(
        hand_workforce, [current, proposed], threshold_pct=10, unchanged_tolerance=50
    )
    family = rows[(rows["plan_name"] == proposed.name) & (rows["coverage_tier"] == "family")].iloc[
        0
    ]
    assert family["burden_change"] == pytest.approx(2_950)
    assert family["burden_pct"] == pytest.approx(22.5)
    assert family["outcome"] == OUTCOME_WORSE
    assert family["above_threshold"]


def test_salary_subsidy_applies_only_below_threshold(make_workforce, proposed):
    plan = proposed.model_copy(
        update={"salary_subsidy": SalarySubsidy(salary_below=40_000, employer_contribution_pct=90)}
    )
    wf = make_workforce([{"annual_salary": 39_999}, {"annual_salary": 40_000}])
    result = calculate_plan(wf, plan)
    assert result["employer_contribution_pct_applied"].tolist() == [90, 70]
    assert result["employee_premium"].tolist() == pytest.approx([500, 1_500])


def test_subsidy_never_lowers_contribution(make_workforce, current):
    plan = current.model_copy(
        update={"salary_subsidy": SalarySubsidy(salary_below=40_000, employer_contribution_pct=50)}
    )
    result = calculate_plan(make_workforce([{"annual_salary": 30_000}]), plan)
    assert result["employer_contribution_pct_applied"].iloc[0] == 80


def test_allowance_is_employer_cost_and_reduces_employee_oop(make_workforce, current):
    plan = current.with_tier_changes(employee_only={"employer_allowance": 300})
    wf = make_workforce([{"annual_allowed_cost": 3_000}, {"annual_allowed_cost": 100}])
    result = calculate_plan(wf, plan)
    assert result["allowance_paid"].tolist() == [300, 100]
    assert result["employee_oop"].tolist() == pytest.approx([700, 0])
    assert result["employer_cost"].tolist() == pytest.approx([5_100, 4_900])


def test_unsupported_coverage_tier_is_rejected(make_workforce, current):
    wf = make_workforce([{"coverage_tier": "employee_plus_spouse"}])
    with pytest.raises(ValueError, match="Unsupported coverage tier"):
        calculate_plan(wf, current)


def test_duplicate_plan_names_are_rejected(hand_workforce, current):
    with pytest.raises(ValueError, match="unique"):
        evaluate_plans(hand_workforce, [current, current], threshold_pct=10, unchanged_tolerance=50)


def test_change_classification_respects_tolerance():
    labels = classify_change([-50.01, -50, 0, 50, 50.01], tolerance=50)
    assert labels.tolist() == [
        OUTCOME_BETTER,
        OUTCOME_UNCHANGED,
        OUTCOME_UNCHANGED,
        OUTCOME_UNCHANGED,
        OUTCOME_WORSE,
    ]
