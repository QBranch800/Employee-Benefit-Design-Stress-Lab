from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import pytest

from benefit_stress_lab import config, demo
from benefit_stress_lab.schemas import Plan
from benefit_stress_lab.synthetic import generate_workforce


@pytest.fixture
def current() -> Plan:
    return demo.current_plan()


@pytest.fixture
def proposed() -> Plan:
    return demo.proposed_plan()


@pytest.fixture(scope="session")
def workforce() -> pd.DataFrame:
    return generate_workforce()


@pytest.fixture
def make_workforce() -> Callable[[list[dict]], pd.DataFrame]:
    def build(rows: list[dict]) -> pd.DataFrame:
        records = []
        for i, row in enumerate(rows, start=1):
            salary = row.get("annual_salary", 50_000)
            records.append(
                {
                    "employee_id": row.get("employee_id", f"T-{i:03d}"),
                    "annual_salary": float(salary),
                    "salary_band": config.salary_band_for(salary),
                    "coverage_tier": row.get("coverage_tier", "employee_only"),
                    "age_band": row.get("age_band", "35-44"),
                    "region": row.get("region", "Region A"),
                    "utilisation_tier": row.get("utilisation_tier", "medium"),
                    "annual_allowed_cost": float(row.get("annual_allowed_cost", 0)),
                }
            )
        return pd.DataFrame(records)

    return build
