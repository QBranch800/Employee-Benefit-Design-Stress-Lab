"""Validation for uploaded workforce files.

Documented rules:

* Required columns must be present and complete; the file must contain rows.
* Duplicate ``employee_id`` values are rejected, never silently dropped.
* Salaries must be positive and allowed costs non-negative.
* Coverage and utilisation tiers must be supported values. Case, spaces, and
  hyphens are normalised (``Employee-Only`` becomes ``employee_only``).
* ``salary_band`` is always recomputed from salary so bands stay consistent.
* Unrecognised columns are dropped with a warning. The model does not need them,
  and they may contain identifying or sensitive information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO

import numpy as np
import pandas as pd

from benefit_stress_lab import config
from benefit_stress_lab.synthetic import WORKFORCE_COLUMNS

REQUIRED_COLUMNS: tuple[str, ...] = (
    "employee_id",
    "annual_salary",
    "coverage_tier",
    "utilisation_tier",
    "annual_allowed_cost",
)
OPTIONAL_COLUMNS: tuple[str, ...] = ("salary_band", "age_band", "region")
MAX_ROWS = 100_000
_EXAMPLES_SHOWN = 5


@dataclass
class ValidationReport:
    """Outcome of validating a workforce. ``data`` is set only when there are no errors."""

    data: pd.DataFrame | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.data is not None and not self.errors


def _csv_lines(mask: pd.Series) -> str:
    """Spreadsheet-style line numbers (header is line 1) for the first few flagged rows."""
    lines = [str(i + 2) for i in mask[mask].index[:_EXAMPLES_SHOWN]]
    more = " …" if mask.sum() > _EXAMPLES_SHOWN else ""
    return ", ".join(lines) + more


def _normalise_category(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower().str.replace(r"[\s\-]+", "_", regex=True)


def _check_numeric(
    df: pd.DataFrame, column: str, errors: list[str], *, allow_zero: bool
) -> pd.Series:
    raw = df[column]
    values = pd.to_numeric(raw, errors="coerce").astype(float)
    missing = raw.isna() | (raw.astype("string").str.strip() == "")
    non_numeric = values.isna() & ~missing
    if missing.any():
        errors.append(
            f"`{column}` is missing on {missing.sum()} row(s) (CSV line {_csv_lines(missing)})."
        )
    if non_numeric.any():
        errors.append(
            f"`{column}` is not a number on {non_numeric.sum()} row(s) "
            f"(CSV line {_csv_lines(non_numeric)})."
        )
    infinite = np.isinf(values)
    bad = (values < 0) if allow_zero else (values <= 0)
    bad = bad | infinite
    if bad.any():
        rule = "cannot be negative" if allow_zero else "must be greater than zero"
        errors.append(f"`{column}` {rule} (CSV line {_csv_lines(bad)}).")
    return values


def validate_workforce(raw: pd.DataFrame | None) -> ValidationReport:
    """Validate and clean a workforce table. Never modifies ``raw``."""
    report = ValidationReport()
    if raw is None or raw.shape[0] == 0:
        report.errors.append("The file contains no employee rows.")
        return report

    df = raw.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        report.errors.append(
            "Missing required column(s): " + ", ".join(f"`{c}`" for c in missing_cols) + ". "
            "Download the template to see the expected layout."
        )
        return report

    if len(df) > MAX_ROWS:
        report.errors.append(f"The file has {len(df):,} rows; the limit is {MAX_ROWS:,}.")
        return report

    extra = [c for c in df.columns if c not in REQUIRED_COLUMNS + OPTIONAL_COLUMNS]
    if extra:
        report.warnings.append(
            "Dropped unrecognised column(s): " + ", ".join(f"`{c}`" for c in extra) + ". "
            "The model does not use them, and they may contain identifying or sensitive data."
        )
        df = df.drop(columns=extra)

    errors = report.errors

    ids = df["employee_id"].astype("string").str.strip()
    missing_id = ids.isna() | (ids == "")
    if missing_id.any():
        errors.append(
            f"`employee_id` is missing on {missing_id.sum()} row(s) "
            f"(CSV line {_csv_lines(missing_id)})."
        )
    duplicated = ids.duplicated(keep=False) & ~missing_id
    if duplicated.any():
        examples = ", ".join(ids[duplicated].drop_duplicates().head(_EXAMPLES_SHOWN))
        errors.append(
            f"Duplicate `employee_id` values on {duplicated.sum()} rows (e.g. {examples}). "
            "Each row must be one unique employee; remove or merge duplicates and upload again."
        )

    salary = _check_numeric(df, "annual_salary", errors, allow_zero=False)
    allowed_cost = _check_numeric(df, "annual_allowed_cost", errors, allow_zero=True)

    coverage = _normalise_category(df["coverage_tier"])
    bad_coverage = ~coverage.isin(config.COVERAGE_TIERS)
    if bad_coverage.any():
        values = ", ".join(sorted(df.loc[bad_coverage, "coverage_tier"].astype(str).unique())[:5])
        errors.append(
            f"Unsupported `coverage_tier` value(s): {values}. "
            f"Supported: {', '.join(config.COVERAGE_TIERS)}."
        )

    utilisation = _normalise_category(df["utilisation_tier"])
    bad_use = ~utilisation.isin(config.UTILISATION_TIERS)
    if bad_use.any():
        values = ", ".join(sorted(df.loc[bad_use, "utilisation_tier"].astype(str).unique())[:5])
        errors.append(
            f"Unsupported `utilisation_tier` value(s): {values}. "
            f"Supported: {', '.join(config.UTILISATION_TIERS)}."
        )

    if errors:
        return report

    bands = [config.salary_band_for(s) for s in salary]
    if "salary_band" in df.columns:
        supplied = df["salary_band"].astype("string").str.strip()
        mismatched = (supplied != pd.Series(bands, index=df.index)).fillna(True)
        if mismatched.any():
            report.warnings.append(
                f"`salary_band` was recomputed from `annual_salary` on {mismatched.sum()} row(s) "
                "so bands are consistent with the model's definitions."
            )

    if "age_band" in df.columns:
        age = (
            df["age_band"]
            .astype("string")
            .str.strip()
            .str.replace("–", "-", regex=False)
            .str.replace(" ", "", regex=False)
        )
        unknown_age = ~age.isin(config.AGE_BANDS)
        if unknown_age.any():
            report.warnings.append(
                f"{unknown_age.sum()} row(s) have a missing or unrecognised `age_band`; "
                f"they are reported as '{config.NOT_PROVIDED}'."
            )
        age = age.where(~unknown_age, config.NOT_PROVIDED)
    else:
        age = pd.Series(config.NOT_PROVIDED, index=df.index)

    if "region" in df.columns:
        region = df["region"].astype("string").str.strip().str.slice(0, 40)
        region = region.where(region.notna() & (region != ""), config.NOT_PROVIDED)
    else:
        region = pd.Series(config.NOT_PROVIDED, index=df.index)

    clean = pd.DataFrame(
        {
            "employee_id": ids.astype(str),
            "annual_salary": salary,
            "salary_band": bands,
            "coverage_tier": coverage.astype(str),
            "age_band": age.astype(str),
            "region": region.astype(str),
            "utilisation_tier": utilisation.astype(str),
            "annual_allowed_cost": allowed_cost,
        }
    )
    report.data = clean[list(WORKFORCE_COLUMNS)].reset_index(drop=True)
    return report


def read_workforce_csv(source: str | IO) -> ValidationReport:
    """Read a CSV and validate it, turning parse failures into readable errors."""
    try:
        raw = pd.read_csv(source, dtype={"employee_id": "string"})
    except pd.errors.EmptyDataError:
        return ValidationReport(errors=["The file is empty."])
    except (pd.errors.ParserError, UnicodeDecodeError) as exc:
        return ValidationReport(errors=[f"The file could not be read as a CSV: {exc}"])
    return validate_workforce(raw)


def workforce_template() -> pd.DataFrame:
    """A small example of the upload layout, using synthetic values only."""
    return pd.DataFrame(
        {
            "employee_id": ["EMP-0001", "EMP-0002", "EMP-0003"],
            "annual_salary": [38_000, 64_500, 121_000],
            "salary_band": ["<40k", "60k-79k", "120k+"],
            "coverage_tier": ["family", "employee_only", "family"],
            "age_band": ["35-44", "25-34", "45-54"],
            "region": ["Region A", "Region B", "Region A"],
            "utilisation_tier": ["medium", "low", "high"],
            "annual_allowed_cost": [9_100, 600, 46_800],
        }
    )


def summarise_workforce(workforce: pd.DataFrame) -> dict[str, object]:
    """Headline facts shown after a workforce is generated or uploaded."""
    salary = workforce["annual_salary"]
    return {
        "headcount": len(workforce),
        "median_salary": float(salary.median()),
        "mean_salary": float(salary.mean()),
        "family_share": float((workforce["coverage_tier"] == "family").mean()),
        "high_use_share": float((workforce["utilisation_tier"] == "high").mean()),
        "mean_allowed_cost": float(workforce["annual_allowed_cost"].mean()),
        "by_salary_band": workforce["salary_band"]
        .value_counts()
        .reindex(config.SALARY_BAND_LABELS, fill_value=0),
        "by_coverage_tier": workforce["coverage_tier"]
        .value_counts()
        .reindex(config.COVERAGE_TIERS, fill_value=0),
        "by_utilisation_tier": workforce["utilisation_tier"]
        .value_counts()
        .reindex(config.UTILISATION_TIERS, fill_value=0),
    }
