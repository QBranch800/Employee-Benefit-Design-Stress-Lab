import io
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from benefit_stress_lab import config
from benefit_stress_lab.schemas import Plan, TierRules, UtilisationCosts, format_validation_error
from benefit_stress_lab.synthetic import WORKFORCE_COLUMNS, WorkforceSettings, generate_workforce
from benefit_stress_lab.validation import (
    read_workforce_csv,
    validate_workforce,
    workforce_template,
)


def csv(text: str):
    return io.StringIO(text)


class TestWorkforceValidation:
    def test_template_is_valid(self):
        report = validate_workforce(workforce_template())
        assert report.ok, report.errors
        assert not report.warnings
        assert list(report.data.columns) == list(WORKFORCE_COLUMNS)

    def test_generated_workforce_is_valid(self, workforce):
        assert validate_workforce(workforce).ok

    def test_missing_columns_are_reported_clearly(self):
        report = validate_workforce(workforce_template().drop(columns=["annual_salary"]))
        assert not report.ok
        assert "annual_salary" in report.errors[0]

    def test_duplicate_ids_are_rejected(self):
        df = workforce_template()
        df.loc[1, "employee_id"] = "EMP-0001"
        report = validate_workforce(df)
        assert not report.ok
        assert any("Duplicate" in e and "EMP-0001" in e for e in report.errors)

    @pytest.mark.parametrize(
        "column, value, phrase",
        [
            ("annual_salary", -1, "greater than zero"),
            ("annual_salary", 0, "greater than zero"),
            ("annual_allowed_cost", -10, "cannot be negative"),
            ("annual_salary", "lots", "not a number"),
            ("annual_allowed_cost", None, "missing"),
        ],
    )
    def test_nonsensical_values_are_rejected(self, column, value, phrase):
        df = workforce_template().astype({column: object})
        df.loc[0, column] = value
        report = validate_workforce(df)
        assert not report.ok
        assert any(column in e and phrase in e for e in report.errors), report.errors
        assert any("line 2" in e for e in report.errors)

    def test_unsupported_categories_are_reported(self):
        df = workforce_template()
        df.loc[0, "coverage_tier"] = "employee_plus_spouse"
        df.loc[1, "utilisation_tier"] = "extreme"
        report = validate_workforce(df)
        assert any("employee_plus_spouse" in e for e in report.errors)
        assert any("extreme" in e for e in report.errors)

    def test_category_formatting_is_normalised(self):
        df = workforce_template()
        df["coverage_tier"] = ["Family", " employee-only ", "FAMILY"]
        df["utilisation_tier"] = ["Medium", "LOW", "high"]
        report = validate_workforce(df)
        assert report.ok, report.errors
        assert report.data["coverage_tier"].tolist() == ["family", "employee_only", "family"]

    def test_extra_columns_are_dropped_with_warning(self):
        df = workforce_template().assign(name="Jane Doe", diagnosis="x")
        report = validate_workforce(df)
        assert report.ok
        assert "name" not in report.data.columns and "diagnosis" not in report.data.columns
        assert any("diagnosis" in w for w in report.warnings)

    def test_salary_band_is_recomputed(self):
        df = workforce_template()
        df.loc[0, "salary_band"] = "120k+"
        report = validate_workforce(df)
        assert report.ok
        assert report.data.loc[0, "salary_band"] == "<40k"
        assert any("recomputed" in w for w in report.warnings)

    def test_optional_columns_may_be_absent(self):
        df = workforce_template().drop(columns=["salary_band", "age_band", "region"])
        report = validate_workforce(df)
        assert report.ok
        assert set(report.data["age_band"]) == {config.NOT_PROVIDED}

    def test_unknown_age_band_becomes_not_provided(self):
        df = workforce_template()
        df.loc[0, "age_band"] = "unknown"
        report = validate_workforce(df)
        assert report.data.loc[0, "age_band"] == config.NOT_PROVIDED
        assert report.warnings

    def test_empty_file_fails_gracefully(self):
        report = read_workforce_csv(csv(""))
        assert not report.ok and "empty" in report.errors[0]

    def test_header_only_file_fails_gracefully(self):
        header = ",".join(WORKFORCE_COLUMNS) + "\n"
        report = read_workforce_csv(csv(header))
        assert not report.ok and "no employee rows" in report.errors[0]

    def test_csv_round_trip(self):
        buffer = io.StringIO()
        workforce_template().to_csv(buffer, index=False)
        buffer.seek(0)
        report = read_workforce_csv(buffer)
        assert report.ok
        pd.testing.assert_frame_equal(report.data, validate_workforce(workforce_template()).data)


class TestPlanSchemas:
    def tier(self, **overrides):
        values = {
            "annual_premium": 6_000,
            "employer_contribution_pct": 80,
            "deductible": 500,
            "coinsurance_pct": 20,
            "out_of_pocket_max": 3_000,
        }
        return TierRules(**{**values, **overrides})

    @pytest.mark.parametrize(
        "overrides",
        [
            {"annual_premium": -1},
            {"employer_contribution_pct": 101},
            {"employer_contribution_pct": -1},
            {"coinsurance_pct": 120},
            {"deductible": -100},
            {"out_of_pocket_max": 400},
        ],
    )
    def test_invalid_tier_rules_are_rejected(self, overrides):
        with pytest.raises(ValidationError):
            self.tier(**overrides)

    def test_missing_tier_is_rejected(self):
        with pytest.raises(ValidationError, match="family"):
            Plan(name="Incomplete", tiers={"employee_only": self.tier()})

    def test_blank_name_is_rejected(self):
        with pytest.raises(ValidationError):
            Plan(name="   ", tiers={"employee_only": self.tier(), "family": self.tier()})

    def test_errors_are_readable(self):
        with pytest.raises(ValidationError) as caught:
            self.tier(out_of_pocket_max=100)
        messages = format_validation_error(caught.value)
        assert messages and "at least the deductible" in messages[0]

    def test_utilisation_costs_must_be_ordered(self):
        with pytest.raises(ValidationError):
            UtilisationCosts(low=5_000, medium=1_000, high=20_000)


class TestSyntheticWorkforce:
    def test_fixed_seed_is_reproducible(self):
        pd.testing.assert_frame_equal(generate_workforce(), generate_workforce())

    def test_different_seed_differs(self):
        a = generate_workforce(WorkforceSettings(seed=1))
        b = generate_workforce(WorkforceSettings(seed=2))
        assert not a["annual_salary"].equals(b["annual_salary"])

    def test_settings_are_respected(self):
        settings = WorkforceSettings(
            headcount=1_000, low_use_share=0.5, medium_use_share=0.3, high_use_share=0.2
        )
        wf = generate_workforce(settings)
        assert len(wf) == 1_000
        assert wf["employee_id"].is_unique
        assert (wf["utilisation_tier"] == "high").sum() == 200
        assert wf["annual_salary"].between(settings.min_salary, settings.max_salary).all()
        assert (wf["annual_allowed_cost"] >= 0).all()

    def test_utilisation_shares_must_sum_to_one(self):
        with pytest.raises(ValidationError):
            WorkforceSettings(low_use_share=0.5, medium_use_share=0.5, high_use_share=0.5)


class TestBundledData:
    ROOT = Path(__file__).resolve().parents[1] / "data"

    def test_example_workforce_is_valid(self):
        report = read_workforce_csv(self.ROOT / "examples" / "synthetic_workforce.csv")
        assert report.ok, report.errors
        assert not report.warnings
        assert len(report.data) == 500

    def test_upload_template_matches_the_code(self):
        report = read_workforce_csv(self.ROOT / "templates" / "workforce_upload_template.csv")
        assert report.ok, report.errors
        pd.testing.assert_frame_equal(report.data, validate_workforce(workforce_template()).data)
