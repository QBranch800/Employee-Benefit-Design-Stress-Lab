from __future__ import annotations

import streamlit as st

import components as ui
from benefit_stress_lab import config
from benefit_stress_lab.schemas import AnalysisSettings, StressAssumptions

ui.init_state()
state = st.session_state

st.title("Stress test")
workforce = ui.require_workforce()
settings = state.settings
assumptions = state.assumptions
plans = ui.all_plans()

st.write(
    "Choose what counts as unaffordable, what the employer is aiming for, and how hard to stress "
    "the assumptions. Every plan is evaluated on the same workforce with the same healthcare "
    "use, so any difference comes from plan design alone."
)
st.caption(
    f"Ready to evaluate {len(workforce):,} employees under {len(plans)} plans: "
    + ", ".join(plan.name for plan in plans)
    + "."
)
if not state.alternatives:
    st.warning(
        "There is no alternative plan yet, so there is nothing to compare with the current plan.",
        icon=":material/warning:",
    )
    ui.page_link("plans", "Add an alternative in the Plan designer", ":material/arrow_forward:")

currencies = list(config.CURRENCIES)

with st.form("stress-test"):
    st.subheader("Affordability and objectives")
    first = st.columns(3)
    threshold = first[0].slider(
        "Affordability threshold (% of salary)",
        min_value=1.0,
        max_value=30.0,
        value=float(settings.affordability_threshold_pct),
        step=0.5,
        format="%.1f",
        help=(
            "Employees whose premium contribution plus out-of-pocket spending exceeds this "
            "share of salary count as above the threshold. It is a scenario parameter you "
            "choose, not a legal, regulatory, or clinical standard."
        ),
    )
    savings_target = first[1].slider(
        "Employer savings target (%)",
        min_value=0.0,
        max_value=50.0,
        value=float(settings.savings_target_pct),
        step=0.5,
        format="%.1f",
        help="The reduction in employer cost that a plan must reach to meet the objective.",
    )
    material_increase = first[2].slider(
        "Material rise in share above threshold (pp)",
        min_value=0.0,
        max_value=20.0,
        value=float(settings.material_increase_pp),
        step=0.5,
        format="%.1f",
        help=(
            "A rise in the share of employees above the threshold larger than this, in "
            "percentage points, counts as increased employee risk."
        ),
    )
    second = st.columns(3)
    tolerance = second[0].number_input(
        "Unchanged tolerance (per year)",
        min_value=0.0,
        max_value=100_000.0,
        value=float(settings.unchanged_tolerance),
        step=10.0,
        format="%.0f",
        help="A change in an employee's yearly burden smaller than this counts as unchanged.",
    )
    min_group_size = second[1].number_input(
        "Smallest group reported",
        min_value=1,
        max_value=1_000,
        value=settings.min_group_size,
        help="Segments with fewer employees than this are not reported, to protect privacy.",
    )
    currency = second[2].selectbox(
        "Currency", currencies, index=currencies.index(settings.currency)
    )

    st.subheader("Stress assumptions")
    st.caption(
        "Leave these at zero for the baseline. Stress is applied to the workforce once, before "
        "any plan is evaluated."
    )
    left, right = st.columns(2)
    cost_change = left.slider(
        "Healthcare cost change (%)",
        min_value=-20.0,
        max_value=50.0,
        value=float(assumptions.healthcare_cost_change_pct),
        step=1.0,
        format="%.0f",
        help=(
            "Scales every employee's allowed healthcare cost. Deductibles and maximums stay "
            "fixed in money terms, so employees absorb a growing share."
        ),
    )
    apply_to_premiums = left.toggle(
        "Apply the cost change to premiums as well", value=assumptions.apply_to_premiums
    )
    salary_growth = left.slider(
        "Salary growth (%)",
        min_value=-10.0,
        max_value=20.0,
        value=float(assumptions.salary_growth_pct),
        step=0.5,
        format="%.1f",
    )
    high_use_shift = right.slider(
        "Employees moved into high use (%)",
        min_value=0.0,
        max_value=50.0,
        value=float(assumptions.high_use_shift_pct),
        step=1.0,
        format="%.0f",
        help="The share of low and medium users who become high users.",
    )
    family_shift = right.slider(
        "Shift toward family coverage (%)",
        min_value=-50.0,
        max_value=50.0,
        value=float(assumptions.family_shift_pct),
        step=1.0,
        format="%.0f",
        help=(
            "Positive values move employee-only members to family coverage. Negative values "
            "move family members to employee-only coverage."
        ),
    )
    seed = right.number_input(
        "Random seed for the stress selection",
        min_value=0,
        max_value=999_999,
        value=assumptions.seed,
        help="Fixes which employees are moved, so a run can be repeated exactly.",
    )
    run = st.form_submit_button("Run the stress test", type="primary", icon=":material/play_arrow:")

if run:
    state.settings = AnalysisSettings(
        currency=currency,
        affordability_threshold_pct=threshold,
        unchanged_tolerance=tolerance,
        min_group_size=min_group_size,
        savings_target_pct=savings_target,
        material_increase_pp=material_increase,
    )
    state.assumptions = StressAssumptions(
        healthcare_cost_change_pct=cost_change,
        apply_to_premiums=apply_to_premiums,
        salary_growth_pct=salary_growth,
        high_use_shift_pct=high_use_shift,
        family_shift_pct=family_shift,
        seed=seed,
    )
    ui.inputs_changed()
    with st.spinner("Evaluating every employee under every plan…"):
        ui.run_and_store()
    ui.switch_to("results")
    st.success("Analysis complete. Open the Results page.", icon=":material/check_circle:")
