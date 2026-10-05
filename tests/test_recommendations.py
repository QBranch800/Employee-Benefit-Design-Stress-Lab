import pytest

from benefit_stress_lab import recommendations as rec
from benefit_stress_lab.scenarios import compare_variants, run_analysis
from benefit_stress_lab.schemas import AnalysisSettings

SETTINGS = AnalysisSettings(savings_target_pct=5, material_increase_pp=2)


@pytest.mark.parametrize(
    "saving, change, expected",
    [
        (5.0, 2.0, rec.LABEL_BALANCED),
        (10, -1, rec.LABEL_BALANCED),
        (10, 2.1, rec.LABEL_RISK),
        (4.9, 0, rec.LABEL_SHORTFALL),
        (4.9, 3, rec.LABEL_NOT_PREFERRED),
        (-3, 5, rec.LABEL_NOT_PREFERRED),
    ],
)
def test_label_rules(saving, change, expected):
    assert rec.label_scenario(saving, change, SETTINGS) == expected


def test_rationale_states_the_thresholds():
    text = rec.label_rationale(10, 3, SETTINGS)
    assert "5.0% target" in text and "2 pp" in text and "exceeds" in text


def test_no_mitigations_when_proposal_matches_current(current):
    assert rec.candidate_mitigations(current, current.renamed("Same")) == []


def test_all_mitigations_built_for_the_spec_proposal(current, proposed):
    options = rec.candidate_mitigations(current, proposed)
    assert [o.key for o in options] == [
        "low_pay_subsidy",
        "deductible_allowance",
        "family_contribution",
        "lower_oop_max",
        "smaller_cut",
    ]
    by_key = {o.key: o.plan for o in options}
    assert by_key["deductible_allowance"].tiers["family"].employer_allowance == 2_000
    assert by_key["smaller_cut"].tiers["employee_only"].employer_contribution_pct == 75
    assert by_key["lower_oop_max"].tiers["employee_only"].out_of_pocket_max == 3_000
    assert all(len(o.plan.name) <= 40 for o in options)


def test_every_mitigation_improves_affordability(workforce, current, proposed):
    result = run_analysis(workforce, current, [proposed])
    table = compare_variants(result, proposed.name, rec.candidate_mitigations(current, proposed))
    proposal = table.iloc[0]
    assert proposal["key"] == rec.PROPOSAL_KEY
    assert (table.iloc[1:]["above_threshold_pct"] <= proposal["above_threshold_pct"]).all()
    assert (table.iloc[1:]["employer_saving"] <= proposal["employer_saving"] + 1e-6).all()
    best = rec.best_mitigation(table, result.settings)
    assert best is not None and best["key"] != rec.PROPOSAL_KEY


def test_best_mitigation_prefers_balanced_with_largest_saving(workforce, current, proposed):
    result = run_analysis(workforce, current, [proposed])
    table = compare_variants(result, proposed.name, rec.candidate_mitigations(current, proposed))
    table.loc[1, "label"] = rec.LABEL_BALANCED
    table.loc[2, "label"] = rec.LABEL_BALANCED
    table.loc[1, "above_threshold_pct"] = 0.0
    table.loc[2, "above_threshold_pct"] = 0.0
    expected = table.loc[[1, 2], "employer_saving"].idxmax()
    assert rec.best_mitigation(table, result.settings)["key"] == table.loc[expected, "key"]


def test_findings_use_responsible_language(workforce, current, proposed):
    result = run_analysis(workforce, current, [proposed])
    table = compare_variants(result, proposed.name, rec.candidate_mitigations(current, proposed))
    text = " ".join(rec.findings(result, proposed.name, table))
    assert "not a legal, regulatory, or clinical standard" in text
    assert "Tested adjustment" in text
    for word in ("unhealthy", "sick", "irresponsible", "diagnos"):
        assert word not in text.lower()
