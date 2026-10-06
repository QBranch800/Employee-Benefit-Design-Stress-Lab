from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import ValidationError

import components as ui
from benefit_stress_lab import config, demo, formatting, reporting
from benefit_stress_lab.schemas import Plan, TierRules, format_validation_error

FIELDS = (
    ("annual_premium", "Annual premium", 100.0),
    ("employer_contribution_pct", "Employer contribution (%)", 1.0),
    ("deductible", "Deductible", 50.0),
    ("coinsurance_pct", "Coinsurance (%)", 1.0),
    ("out_of_pocket_max", "Out-of-pocket maximum", 100.0),
    ("employer_allowance", "Employer allowance", 50.0),
)
COST_SHARING = (
    "The employee pays the deductible in full, then the coinsurance share, up to the "
    "out-of-pocket maximum. Hover over a question mark for a definition."
)

ui.init_state()
state = st.session_state
symbol = state.settings.currency_symbol


def unique_name(base: str) -> str:
    taken = {plan.name for plan in ui.all_plans()}
    if base not in taken:
        return base
    number = 2
    while f"{base} {number}" in taken:
        number += 1
    return f"{base} {number}"


def add_alternative(plan: Plan) -> None:
    state.alternatives = [*state.alternatives, plan]
    ui.inputs_changed()
    ui.reset_forms()
    st.rerun()


def plan_form(plan: Plan, slot: int) -> None:
    rev = state.form_rev
    with st.form(f"plan-{rev}-{slot}", border=False):
        name = st.text_input("Plan name", value=plan.name, max_chars=40)
        st.caption(COST_SHARING)
        tiers = {}
        for column, tier in zip(
            st.columns(len(config.COVERAGE_TIERS), gap="medium"), config.COVERAGE_TIERS, strict=True
        ):
            rules = plan.tiers[tier]
            with column:
                st.markdown(f"**{config.COVERAGE_TIER_LABELS[tier]}**")
                tiers[tier] = {
                    field: st.number_input(
                        label,
                        min_value=0.0,
                        max_value=100.0 if field.endswith("_pct") else None,
                        value=float(getattr(rules, field)),
                        step=step,
                        format="%.1f" if field.endswith("_pct") else "%.0f",
                        help=TierRules.model_fields[field].description,
                        key=f"{rev}-{slot}-{tier}-{field}",
                    )
                    for field, label, step in FIELDS
                }

        subsidy = plan.salary_subsidy
        with st.expander("Extra support for lower salaries", expanded=subsidy is not None):
            use_subsidy = st.checkbox(
                "Give lower-paid employees a higher employer contribution",
                value=subsidy is not None,
            )
            left, right = st.columns(2, gap="medium")
            salary_below = left.number_input(
                "For salaries below",
                min_value=1.0,
                value=float(subsidy.salary_below) if subsidy else 40_000.0,
                step=1_000.0,
                format="%.0f",
            )
            subsidy_pct = right.number_input(
                "Employer contribution of at least (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(subsidy.employer_contribution_pct) if subsidy else 90.0,
                step=1.0,
                format="%.1f",
            )
        save = st.form_submit_button("Save plan", type="primary")

    if not save:
        return
    support = (
        {"salary_below": salary_below, "employer_contribution_pct": subsidy_pct}
        if use_subsidy
        else None
    )
    try:
        updated = Plan(name=name, tiers=tiers, salary_subsidy=support)
    except ValidationError as error:
        for message in format_validation_error(error):
            st.error(message, icon=":material/error:")
        return
    others = [other.name for index, other in enumerate(ui.all_plans()) if index != slot]
    if updated.name in others:
        st.error(
            "Another plan already uses that name. Plan names must be unique.",
            icon=":material/error:",
        )
        return
    if slot == 0:
        state.current_plan = updated
    else:
        alternatives = list(state.alternatives)
        alternatives[slot - 1] = updated
        state.alternatives = alternatives
    ui.inputs_changed()
    st.rerun()


def comparison_table(plans: list[Plan]) -> pd.DataFrame:
    rows = []
    for tier in config.COVERAGE_TIERS:
        for field, label, _ in FIELDS:
            row = {
                "Coverage tier": config.COVERAGE_TIER_LABELS[tier],
                "Setting": label.removesuffix(" (%)"),
            }
            for plan in plans:
                value = getattr(plan.tiers[tier], field)
                row[plan.name] = (
                    f"{value:g}%" if field.endswith("_pct") else formatting.money(value, symbol)
                )
            rows.append(row)
    support = {"Coverage tier": "All", "Setting": "Support for lower salaries"}
    for plan in plans:
        subsidy = plan.salary_subsidy
        support[plan.name] = (
            f"{subsidy.employer_contribution_pct:g}% below "
            f"{formatting.money(subsidy.salary_below, symbol)}"
            if subsidy
            else "None"
        )
    rows.append(support)
    return pd.DataFrame(rows)


ui.page_header(
    "Plans",
    "Define the current plan and up to three alternatives. Every comparison is measured against "
    "the current plan, which is the first one listed.",
)

plans = ui.all_plans()
room = len(state.alternatives) < config.MAX_ALTERNATIVE_PLANS

slot = st.segmented_control(
    "Plan to edit",
    options=list(range(len(plans))),
    format_func=lambda index: plans[index].name,
    default=0,
    required=True,
    key=f"plan-slot-{state.form_rev}",
)

with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Duplicate current plan", disabled=not room, icon=":material/content_copy:"):
        add_alternative(state.current_plan.renamed(unique_name("Alternative")))
    if st.button("Add example proposal", disabled=not room, icon=":material/add:"):
        add_alternative(demo.proposed_plan(unique_name("Proposed Plan")))
    if st.button("Remove this plan", disabled=slot == 0, icon=":material/delete:"):
        state.alternatives = [
            plan for index, plan in enumerate(state.alternatives) if index != slot - 1
        ]
        ui.inputs_changed()
        ui.reset_forms()
        st.rerun()
if not room:
    st.caption(
        f"The limit is {config.MAX_ALTERNATIVE_PLANS} alternatives. Remove one to add another."
    )

with ui.card("plan-form"):
    if slot == 0:
        ui.card_title(
            "Current plan",
            "The plan employees have today. Every alternative is compared with it.",
        )
    else:
        ui.card_title(
            f"Alternative {slot}",
            reporting.describe_changes(state.current_plan, plans[slot], symbol),
        )
    plan_form(plans[slot], slot)

with ui.card("plan-compare"):
    ui.card_title("Side by side")
    table = comparison_table(plans)
    ui.html_table(
        table,
        numeric=[plan.name for plan in plans],
        soft=["Coverage tier"],
    )

ui.page_link("stress_test", "Next: set up the stress test", ":material/arrow_forward:")
