from __future__ import annotations

from benefit_stress_lab.schemas import Plan, SalarySubsidy, TierRules


def current_plan() -> Plan:
    return Plan(
        name="Current plan",
        tiers={
            "employee_only": TierRules(
                annual_premium=6_000,
                employer_contribution_pct=80,
                deductible=500,
                coinsurance_pct=20,
                out_of_pocket_max=3_000,
            ),
            "family": TierRules(
                annual_premium=15_000,
                employer_contribution_pct=80,
                deductible=1_000,
                coinsurance_pct=20,
                out_of_pocket_max=6_000,
            ),
        },
    )


def proposed_plan(name: str = "Proposed plan") -> Plan:
    return Plan(
        name=name,
        tiers={
            "employee_only": TierRules(
                annual_premium=5_000,
                employer_contribution_pct=70,
                deductible=1_500,
                coinsurance_pct=30,
                out_of_pocket_max=5_000,
            ),
            "family": TierRules(
                annual_premium=12_500,
                employer_contribution_pct=70,
                deductible=3_000,
                coinsurance_pct=30,
                out_of_pocket_max=10_000,
            ),
        },
    )


def scenario_a_balanced() -> Plan:
    return (
        current_plan()
        .with_tier_changes(
            employee_only={"annual_premium": 5_640, "deductible": 750},
            family={"annual_premium": 14_100, "deductible": 1_500},
        )
        .renamed("A: Modest adjustment")
    )


def scenario_b_hidden_problem() -> Plan:
    return proposed_plan("B: Proposed cost shift")


def scenario_c_targeted_mitigation() -> Plan:
    plan = proposed_plan("C: B + low-pay subsidy")
    return plan.model_copy(
        update={"salary_subsidy": SalarySubsidy(salary_below=60_000, employer_contribution_pct=90)}
    )


def demo_alternatives() -> list[Plan]:
    return [scenario_a_balanced(), scenario_b_hidden_problem(), scenario_c_targeted_mitigation()]
