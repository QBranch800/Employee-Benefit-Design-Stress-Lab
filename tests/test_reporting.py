import io
import zipfile

import pandas as pd
import pytest

from benefit_stress_lab import demo, formatting, reporting
from benefit_stress_lab import recommendations as rec
from benefit_stress_lab.scenarios import compare_variants, run_analysis


@pytest.fixture
def result(workforce, current):
    return run_analysis(workforce, current, demo.demo_alternatives())


def test_exported_values_match_displayed_results(result):
    displayed = reporting.plan_table(result)
    exported = pd.read_csv(io.BytesIO(reporting.to_csv_bytes(displayed, index=True)), index_col=0)
    for column in ("Employer cost", "Employer saving", "% above threshold", "Worse off"):
        pd.testing.assert_series_equal(
            exported[column], displayed[column], check_names=False, check_dtype=False
        )
    assert (
        displayed.loc[result.baseline_name, "Employer cost"]
        == result.summary.iloc[0]["employer_cost_total"]
    )


def test_export_bundle_contains_aggregates_only(result):
    name = result.alternative_names[1]
    table = compare_variants(
        result, name, rec.candidate_mitigations(result.input_plans[0], result.input_plan(name))
    )
    archive = zipfile.ZipFile(io.BytesIO(reporting.export_bundle(result, table)))
    assert set(archive.namelist()) == {
        "plan_summary.csv",
        "segments.csv",
        "assumptions.csv",
        "plans.csv",
        "mitigations.csv",
        "README.txt",
    }
    everything = "".join(archive.read(n).decode() for n in archive.namelist())
    assert "EMP-0" not in everything
    assert "employee_id" not in everything


def test_segment_export_applies_suppression(result):
    segments = reporting.segment_table(result)
    suppressed = segments[segments["suppressed"]]
    assert suppressed["median_burden"].isna().all()
    assert set(segments["dimension"]) == {
        "salary_band",
        "coverage_tier",
        "salary_band × coverage_tier",
    }


def test_summary_markdown_includes_disclaimer_and_findings(result):
    name = result.alternative_names[0]
    findings = rec.findings(result, name)
    text = reporting.summary_markdown(result, name, findings)
    assert "Not actuarial, legal, tax, or benefits advice" in text
    assert findings[0] in text
    assert "## Limitations" in text


@pytest.mark.parametrize(
    "value, expected",
    [(1234.5, "$1,234"), (-1500, "−$1,500"), (0, "$0"), (float("nan"), "—")],
)
def test_money_formatting(value, expected):
    assert formatting.money(value) == expected


def test_signed_formatting():
    assert formatting.money(680, signed=True) == "+$680"
    assert formatting.pp(2.04) == "+2.0 pp"
    assert formatting.pp(-0.01) == "0.0 pp"
    assert formatting.pct(12.345) == "12.3%"


@pytest.mark.parametrize(
    "value, expected",
    [(4_833, "$4,833"), (476_220, "$476k"), (2_826_250, "$2.83M"), (-1_049_750, "−$1.05M")],
)
def test_compact_money(value, expected):
    assert formatting.compact_money(value) == expected
