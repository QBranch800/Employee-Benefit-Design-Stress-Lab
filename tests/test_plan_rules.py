import numpy as np
import pytest

from benefit_stress_lab import plan_rules
from benefit_stress_lab.calculations import is_above_threshold

DED, COINS, OOP_MAX = 500, 20, 3_000


def oop(spend, ded=DED, coins=COINS, oop_max=OOP_MAX):
    return float(plan_rules.out_of_pocket(spend, ded, coins, oop_max))


class TestOutOfPocket:
    def test_zero_use_costs_nothing(self):
        assert oop(0) == 0

    def test_spending_below_deductible_is_paid_in_full(self):
        assert oop(400) == 400

    def test_spending_equal_to_deductible(self):
        assert oop(500) == 500

    def test_coinsurance_applies_only_after_deductible(self):
        assert oop(3_000) == pytest.approx(1_000)

    def test_reaching_the_maximum_exactly(self):
        assert oop(13_000) == pytest.approx(3_000)

    def test_never_exceeds_the_maximum(self):
        spend = np.array([13_001, 50_000, 1_000_000])
        assert np.all(plan_rules.out_of_pocket(spend, DED, COINS, OOP_MAX) == OOP_MAX)

    def test_zero_coinsurance_means_only_the_deductible(self):
        assert oop(10_000, coins=0) == 500

    def test_full_coinsurance_means_employee_pays_until_cap(self):
        assert oop(2_000, coins=100) == 2_000
        assert oop(10_000, coins=100) == 3_000

    def test_vectorised_matches_scalar(self):
        spend = np.array([0, 400, 500, 3_000, 13_000, 20_000])
        expected = [oop(s) for s in spend]
        assert plan_rules.out_of_pocket(spend, DED, COINS, OOP_MAX).tolist() == pytest.approx(
            expected
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"spend": -1},
            {"spend": 100, "ded": -5},
            {"spend": 100, "coins": 101},
            {"spend": 100, "coins": -1},
            {"spend": 100, "oop_max": -1},
            {"spend": float("nan")},
        ],
    )
    def test_invalid_inputs_are_rejected(self, kwargs):
        with pytest.raises(ValueError):
            oop(**kwargs)


class TestPremiumShares:
    @pytest.mark.parametrize("pct", [0, 37.5, 80, 100])
    def test_shares_sum_to_premium(self, pct):
        employer = plan_rules.employer_premium_share(15_000, pct)
        employee = plan_rules.employee_premium_share(15_000, pct)
        assert float(employer + employee) == pytest.approx(15_000)

    def test_zero_percent_employer_contribution(self):
        assert float(plan_rules.employer_premium_share(6_000, 0)) == 0
        assert float(plan_rules.employee_premium_share(6_000, 0)) == 6_000

    def test_full_employer_contribution(self):
        assert float(plan_rules.employer_premium_share(6_000, 100)) == 6_000
        assert float(plan_rules.employee_premium_share(6_000, 100)) == 0

    @pytest.mark.parametrize("factor", [0.94, 1.19, 1.44])
    def test_full_employer_contribution_never_goes_negative(self, factor):
        premium = 5_640 * factor
        share = float(plan_rules.employee_premium_share(premium, 100))
        assert share == 0
        assert float(plan_rules.total_employee_burden(share, 0)) == 0

    @pytest.mark.parametrize("pct", [-1, 100.1])
    def test_percentage_outside_range_is_rejected(self, pct):
        with pytest.raises(ValueError):
            plan_rules.employer_premium_share(6_000, pct)

    def test_negative_premium_is_rejected(self):
        with pytest.raises(ValueError):
            plan_rules.employee_premium_share(-100, 80)


class TestBurden:
    def test_total_burden_is_premium_plus_out_of_pocket(self):
        assert float(plan_rules.total_employee_burden(1_200, 1_000)) == 2_200

    def test_allowance_reimburses_up_to_its_limit(self):
        paid = plan_rules.apply_allowance([0, 400, 2_000], 1_000)
        assert paid.tolist() == [0, 400, 1_000]

    def test_burden_percentage_uses_salary(self):
        assert float(plan_rules.burden_pct_of_salary(5_600, 38_000)) == pytest.approx(
            14.7368, abs=1e-4
        )

    def test_zero_salary_gives_nan_not_infinity(self):
        result = plan_rules.burden_pct_of_salary([1_000, 1_000], [0, 50_000])
        assert np.isnan(result[0])
        assert result[1] == 2

    def test_exactly_at_threshold_is_not_above(self):
        at_threshold = plan_rules.burden_pct_of_salary(5_000, 50_000)
        assert float(at_threshold) == 10.0
        assert not is_above_threshold(at_threshold, 10)[()]
        assert is_above_threshold(plan_rules.burden_pct_of_salary(5_000.01, 50_000), 10)[()]
