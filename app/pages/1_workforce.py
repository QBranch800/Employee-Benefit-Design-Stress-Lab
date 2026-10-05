from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import ValidationError

import charts
import components as ui
import theme
from benefit_stress_lab import config, formatting
from benefit_stress_lab.reporting import to_csv_bytes
from benefit_stress_lab.schemas import UtilisationCosts, format_validation_error
from benefit_stress_lab.synthetic import WorkforceSettings, generate_workforce
from benefit_stress_lab.validation import (
    read_workforce_csv,
    summarise_workforce,
    workforce_template,
)

COLUMN_GUIDE = pd.DataFrame(
    [
        ("employee_id", "Yes", "EMP-0001", "Anonymous identifier, unique per row"),
        ("annual_salary", "Yes", "48000", "Used to measure affordability"),
        ("coverage_tier", "Yes", "family", "employee_only or family"),
        ("utilisation_tier", "Yes", "medium", "low, medium, or high"),
        ("annual_allowed_cost", "Yes", "3200", "Covered healthcare used in the year"),
        ("salary_band", "No", "40k-59k", "Recomputed from salary"),
        ("age_band", "No", "35-44", "Kept for reference only"),
        ("region", "No", "Region A", "Kept for reference only"),
    ],
    columns=["Column", "Required", "Example", "Notes"],
)

UPLOAD_RULES = (
    "Duplicate employee IDs are rejected.",
    "Salaries must be greater than zero and allowed costs cannot be negative.",
    "Columns the model does not use are dropped, because they may identify people.",
    "Do not upload names, diagnoses, or any other identifying or medical detail.",
)

ui.init_state()
state = st.session_state
pal = theme.palette()

st.title("Workforce")
st.write(
    "Every analysis runs on a workforce: one row per employee, with a salary, a coverage tier, "
    "and a year of healthcare use. Use synthetic data, or upload records that are already "
    "anonymised."
)

generate_tab, upload_tab = st.tabs(["Generate a synthetic workforce", "Upload a CSV"])

with generate_tab:
    saved = state.workforce_settings
    costs = state.costs
    with st.form("generate-workforce"):
        top = st.columns(4)
        headcount = top[0].number_input(
            "Headcount", min_value=10, max_value=50_000, value=saved.headcount, step=50
        )
        median_salary = top[1].number_input(
            "Median salary",
            min_value=15_000,
            max_value=500_000,
            value=int(saved.median_salary),
            step=1_000,
        )
        salary_spread = top[2].slider(
            "Salary spread",
            min_value=0.05,
            max_value=1.5,
            value=float(saved.salary_spread),
            step=0.05,
            help="How unequal salaries are. Higher values give a longer tail of high earners.",
        )
        seed = top[3].number_input(
            "Random seed",
            min_value=0,
            max_value=999_999,
            value=saved.seed,
            help="The same seed and settings always generate the same workforce.",
        )

        middle = st.columns(4)
        min_salary = middle[0].number_input(
            "Lowest salary",
            min_value=1_000,
            max_value=500_000,
            value=int(saved.min_salary),
            step=1_000,
        )
        max_salary = middle[1].number_input(
            "Highest salary",
            min_value=10_000,
            max_value=5_000_000,
            value=int(saved.max_salary),
            step=10_000,
        )
        family_share = middle[2].slider(
            "Family coverage share (%)", 0, 100, round(saved.family_share * 100)
        )

        st.markdown("**Healthcare-use mix**")
        st.caption("Shares of employees with low, medium, and high use. They must total 100%.")
        mix = st.columns(3)
        low_share = mix[0].number_input("Low use (%)", 0, 100, round(saved.low_use_share * 100))
        medium_share = mix[1].number_input(
            "Medium use (%)", 0, 100, round(saved.medium_use_share * 100)
        )
        high_share = mix[2].number_input("High use (%)", 0, 100, round(saved.high_use_share * 100))

        st.markdown("**Healthcare cost assumptions**")
        st.caption(
            "Assumed yearly allowed cost for one employee-only member at each level of use. "
            "These are labelled assumptions, not forecasts. Family coverage multiplies them."
        )
        assumed = st.columns(4)
        low_cost = assumed[0].number_input("Low use", 0, 1_000_000, int(costs.low), 100)
        medium_cost = assumed[1].number_input("Medium use", 0, 1_000_000, int(costs.medium), 100)
        high_cost = assumed[2].number_input("High use", 0, 1_000_000, int(costs.high), 500)
        family_multiplier = assumed[3].number_input(
            "Family multiplier", 1.0, 10.0, float(costs.family_multiplier), 0.1, format="%.1f"
        )
        generate = st.form_submit_button("Generate workforce", type="primary")

    if generate:
        try:
            new_settings = WorkforceSettings(
                headcount=headcount,
                median_salary=median_salary,
                salary_spread=salary_spread,
                min_salary=min_salary,
                max_salary=max_salary,
                family_share=family_share / 100,
                low_use_share=low_share / 100,
                medium_use_share=medium_share / 100,
                high_use_share=high_share / 100,
                seed=seed,
            )
            new_costs = UtilisationCosts(
                low=low_cost,
                medium=medium_cost,
                high=high_cost,
                family_multiplier=family_multiplier,
            )
        except ValidationError as error:
            for message in format_validation_error(error):
                st.error(message, icon=":material/error:")
        else:
            state.workforce_settings = new_settings
            state.costs = new_costs
            state.workforce = generate_workforce(new_settings, new_costs)
            state.workforce_source = "Synthetic"
            ui.inputs_changed()
            st.success(
                f"Generated {new_settings.headcount:,} synthetic employees.",
                icon=":material/check_circle:",
            )

with upload_tab:
    st.write(
        "Upload synthetic or anonymised records in the template layout. The file is held in "
        "memory for this session only. It is never saved, and exports contain aggregates only."
    )
    st.download_button(
        "Download the CSV template",
        data=to_csv_bytes(workforce_template()),
        file_name="workforce_upload_template.csv",
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
    )
    uploaded = st.file_uploader("Workforce CSV", type="csv")
    if uploaded is not None:
        report = read_workforce_csv(uploaded)
        for message in report.errors:
            st.error(message, icon=":material/error:")
        for message in report.warnings:
            st.warning(message, icon=":material/warning:")
        if report.ok:
            st.success(
                f"{len(report.data):,} employees passed validation.",
                icon=":material/check_circle:",
            )
            if st.button("Use this workforce", type="primary"):
                state.workforce = report.data
                state.workforce_source = "Uploaded CSV"
                ui.inputs_changed()
                st.rerun()
    with st.expander("Columns and validation rules"):
        st.dataframe(COLUMN_GUIDE, hide_index=True, width="stretch")
        st.markdown("\n".join(f"- {rule}" for rule in UPLOAD_RULES))

st.divider()
st.subheader("Current workforce")
workforce = state.workforce
if workforce is None:
    st.info(
        "No workforce yet. Generate one above, or load the demonstration from the introduction.",
        icon=":material/groups:",
    )
    st.stop()

summary = summarise_workforce(workforce)
symbol = state.settings.currency_symbol
smallest = state.settings.min_group_size
st.caption(f"Source: {state.workforce_source}")

tiles = st.columns(5)
tiles[0].metric("Employees", f"{summary['headcount']:,}")
tiles[1].metric("Median salary", formatting.money(summary["median_salary"], symbol))
tiles[2].metric("Family coverage", formatting.pct(summary["family_share"] * 100, 0))
tiles[3].metric("High healthcare use", formatting.pct(summary["high_use_share"] * 100, 0))
tiles[4].metric("Mean allowed cost", formatting.money(summary["mean_allowed_cost"], symbol))

left, right = st.columns([3, 2])
with left:
    st.markdown("**Employees by salary band**")
    ui.plot(charts.salary_band_counts(summary["by_salary_band"], pal))
with right:
    st.markdown("**Coverage tier by healthcare use**")
    counts = pd.crosstab(workforce["coverage_tier"], workforce["utilisation_tier"]).reindex(
        index=list(config.COVERAGE_TIERS), columns=list(config.UTILISATION_TIERS), fill_value=0
    )
    shown = counts.map(lambda count: f"{count:,}" if count >= smallest else f"< {smallest}")
    shown.index = [config.COVERAGE_TIER_LABELS[tier] for tier in shown.index]
    shown.columns = [f"{tier.capitalize()} use" for tier in shown.columns]
    st.dataframe(shown.reset_index(names="Coverage tier"), hide_index=True, width="stretch")
    st.caption(f"Groups with fewer than {smallest} employees are not shown exactly.")

ui.table_view(
    summary["by_salary_band"].rename_axis("Salary band").reset_index(name="Employees"),
    "Show the salary-band counts as a table",
)

if str(state.workforce_source).startswith("Synthetic"):
    st.download_button(
        "Download this synthetic workforce (CSV)",
        data=to_csv_bytes(workforce),
        file_name="synthetic_workforce.csv",
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
    )

ui.page_link("plans", "Next: design the plans", ":material/arrow_forward:")
