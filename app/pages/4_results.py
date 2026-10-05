from __future__ import annotations

import pandas as pd
import streamlit as st

import charts
import components as ui
import theme
from benefit_stress_lab import config, formatting, reporting
from benefit_stress_lab import recommendations as rec
from benefit_stress_lab.affordability import burden_quantiles
from benefit_stress_lab.scenarios import compare_variants, contribution_sweep, sensitivity_grid

OVERVIEW_COLUMNS = {
    "Employer cost": "Employer cost",
    "Employer saving": "Employer saving",
    "Employer saving %": "Saving %",
    "Mean employee burden": "Mean burden",
    "% above threshold": "Above threshold",
    "Change in % above threshold (pp)": "Change",
    "Worse off": "Worse off",
    "Assessment": "Assessment",
}

SEGMENT_COLUMNS = {
    "headcount": "Employees",
    "median_burden": "Median burden",
    "median_burden_change": "Median change",
    "median_burden_pct_change": "Median change (pp of salary)",
    "above_threshold_pct": "% above threshold",
    "worse_off_pct": "% worse off",
}

ui.init_state()
state = st.session_state

st.title("Results")
result = ui.require_analysis()
ui.stale_notice()

pal = theme.palette()
settings = result.settings
symbol = settings.currency_symbol
summary = result.summary
colours = charts.plan_colours(result.plan_names, pal)
threshold = f"{settings.affordability_threshold_pct:g}%"


def money(value: float, signed: bool = False) -> str:
    return formatting.money(value, symbol, signed=signed)


def segment_table(
    segments: pd.DataFrame, by: dict[str, str], plan_names: list[str]
) -> pd.DataFrame:
    chosen = segments[segments["plan_name"].isin(plan_names)]
    table = chosen[["plan_name", *by, *SEGMENT_COLUMNS]].rename(
        columns={"plan_name": "Plan", **by, **SEGMENT_COLUMNS}
    )
    if "Coverage tier" in table:
        table["Coverage tier"] = table["Coverage tier"].map(config.COVERAGE_TIER_LABELS)
    return ui.display_frame(
        table,
        symbol=symbol,
        money=["Median burden"],
        signed_money=["Median change"],
        pp=["Median change (pp of salary)"],
        pct=["% above threshold", "% worse off"],
    )


stress = "baseline assumptions" if result.assumptions.is_baseline() else "stressed assumptions"
st.caption(
    f"{len(result.workforce):,} employees · {len(result.plans)} plans · {stress} · "
    f"run {result.run_at:%d %b %Y %H:%M} UTC · model v{result.model_version}"
)

st.subheader("All plans at a glance")
st.write(
    f"Each point is a plan. Further left costs the employer less. Lower means fewer employees "
    f"whose healthcare burden exceeds {threshold} of salary."
)
ui.plot(charts.cost_vs_affordability(summary, pal, symbol))

plan_table = reporting.plan_table(result)
ui.summary_table(
    ui.display_frame(
        plan_table[list(OVERVIEW_COLUMNS)].rename(columns=OVERVIEW_COLUMNS).reset_index(),
        symbol=symbol,
        money=["Employer cost", "Employer saving", "Mean burden"],
        pct=["Saving %", "Above threshold"],
        pp=["Change"],
        whole=["Worse off"],
    )
)

if not result.alternative_names:
    st.info(
        "Add an alternative plan and run the stress test again to see comparisons.",
        icon=":material/tune:",
    )
    ui.page_link("plans", "Go to the Plan designer", ":material/arrow_forward:")
    st.stop()

st.subheader("Compare an alternative with the current plan")
names = result.alternative_names
focus = names.index(state.focus_plan) if state.focus_plan in names else 0
plan_name = st.selectbox("Alternative plan", names, index=focus)
state.focus_plan = plan_name
base = summary.iloc[0]
alt = summary.loc[plan_name]


def build_mitigations() -> tuple[list[rec.Mitigation], pd.DataFrame]:
    options = rec.candidate_mitigations(
        result.input_plans[0], result.input_plan(plan_name), currency_symbol=symbol
    )
    return options, compare_variants(result, plan_name, options)


options, mitigations = ui.cached("mitigations", plan_name, build_mitigations)
best = rec.best_mitigation(mitigations, settings)
findings = rec.findings(result, plan_name, mitigations)

tiles = st.columns(5)
tiles[0].metric(
    "Employer cost per year",
    formatting.compact_money(alt["employer_cost_total"], symbol),
    ui.delta_money(-alt["employer_saving"], symbol),
    delta_color="inverse",
    help=ui.escape(
        f"{money(alt['employer_cost_total'])}: premium contributions plus any employer-funded "
        "allowance. The change is against the current plan."
    ),
)
tiles[1].metric(
    "Mean employee burden",
    money(alt["mean_burden"]),
    ui.delta_money(alt["mean_burden_change"], symbol),
    delta_color="inverse",
    help="Premium contribution plus modelled out-of-pocket spending, per employee per year.",
)
tiles[2].metric(
    "Median employee burden",
    money(alt["median_burden"]),
    ui.delta_money(alt["median_burden"] - base["median_burden"], symbol),
    delta_color="inverse",
    help="The change shown is the difference between the two plans' medians. The findings "
    "quote the median of each employee's own change.",
)
tiles[3].metric(
    f"Above {threshold} of salary",
    formatting.pct(alt["above_threshold_pct"]),
    ui.delta_pp(alt["above_threshold_change_pp"]),
    delta_color="inverse",
    help=f"{int(alt['above_threshold_count']):,} of {int(alt['headcount']):,} employees. The "
    "threshold is a scenario parameter, not a legal or clinical standard.",
)
tiles[4].metric(
    "Employees worse off",
    f"{int(alt['worse_off_count']):,}",
    help=ui.escape(
        f"Burden rises by more than {money(settings.unchanged_tolerance)} a year. "
        f"{int(alt['better_off_count']):,} are better off and "
        f"{int(alt['unchanged_count']):,} are within the tolerance."
    ),
)

ui.assessment(alt["label"], alt["label_rationale"])
st.markdown("**Findings**")
st.markdown(
    ui.escape("\n".join(f"- {line}" for line in findings if not line.startswith("Assessment:")))
)

distribution_tab, bands_tab, coverage_tab, segments_tab, outcomes_tab = st.tabs(
    ["Burden distribution", "Salary bands", "Coverage tiers", "Segments", "Winners and losers"]
)

with distribution_tab:
    st.caption(
        f"Total employee burden as a share of salary under each plan. Each box spans the middle "
        f"half of employees and the line inside is the median. The dashed line is the "
        f"{threshold} threshold, a scenario parameter."
    )
    ui.plot(
        charts.burden_distribution(
            result.rows, result.plan_names, settings.affordability_threshold_pct, pal
        )
    )
    quantiles = burden_quantiles(result.rows).rename(
        columns={
            "p25": "25th percentile",
            "median": "Median",
            "p75": "75th percentile",
            "p95": "95th percentile",
        }
    )
    quantiles["% above threshold"] = summary["above_threshold_pct"]
    ui.table_view(
        ui.display_frame(quantiles.reset_index(names="Plan"), pct=list(quantiles.columns))
    )

with bands_tab:
    bands = result.segments(["salary_band"])
    st.caption(
        f"Median change in burden under {plan_name} compared with {result.baseline_name}. A "
        "similar change in money is a much larger share of a lower salary."
    )
    ui.plot(charts.band_impact(bands, plan_name, colours[plan_name], pal, symbol))
    ui.table_view(segment_table(bands, {"salary_band": "Salary band"}, [plan_name]))

with coverage_tab:
    tiers = result.segments(["coverage_tier"])
    st.caption(
        f"Share of employees in each coverage tier whose burden exceeds {threshold} of salary."
    )
    ui.plot(charts.coverage_comparison(tiers, result.baseline_name, plan_name, colours, pal))
    ui.table_view(
        segment_table(tiers, {"coverage_tier": "Coverage tier"}, [result.baseline_name, plan_name])
    )

with segments_tab:
    cells = result.segments(["salary_band", "coverage_tier"])
    st.caption(
        f"Median change in burden as a share of salary under {plan_name}, by salary band and "
        f"coverage tier. Groups with fewer than {settings.min_group_size} employees are not "
        "reported."
    )
    ui.plot(charts.segment_heatmap(cells, plan_name, pal))
    segment = result.most_affected(plan_name)
    if segment is not None:
        st.info(
            ui.escape(
                f"**Most affected segment:** {segment['description']} "
                f"({segment['headcount']} employees). Median burden rises by "
                f"{money(segment['median_burden_change'])} a year, "
                f"{formatting.pp(segment['median_burden_pct_change'])} of salary."
            ),
            icon=":material/priority_high:",
        )
    ui.table_view(
        segment_table(
            cells, {"salary_band": "Salary band", "coverage_tier": "Coverage tier"}, [plan_name]
        )
    )

with outcomes_tab:
    st.caption(
        ui.escape(
            f"Employees whose yearly burden falls, stays within "
            f"±{money(settings.unchanged_tolerance)}, or rises under each alternative, compared "
            f"with {result.baseline_name}."
        )
    )
    ui.plot(charts.winners_losers(summary, pal))
    outcomes = summary.iloc[1:][
        ["better_off_count", "unchanged_count", "worse_off_count", "worse_off_pct"]
    ].rename(
        columns={
            "better_off_count": "Better off",
            "unchanged_count": "Unchanged",
            "worse_off_count": "Worse off",
            "worse_off_pct": "% worse off",
        }
    )
    ui.table_view(
        ui.display_frame(
            outcomes.reset_index(names="Plan"),
            whole=["Better off", "Unchanged", "Worse off"],
            pct=["% worse off"],
        )
    )

st.subheader("Tested adjustments")
if not options:
    st.info(
        f"{plan_name} does not cut employer contributions or raise cost sharing compared with "
        f"{result.baseline_name}, so there is nothing to soften.",
        icon=":material/info:",
    )
else:
    st.write(
        f"Each adjustment softens {plan_name} and was recalculated on the same workforce. They "
        "are options to weigh, not recommendations."
    )
    ui.plot(
        charts.mitigation_bars(
            mitigations, None if best is None else best["key"], colours[plan_name], pal, symbol
        )
    )
    if best is None:
        st.caption("None of the tested adjustments reduced the share above the threshold.")
    else:
        st.caption(
            ui.escape(
                f"Highlighted: {best['title'].lower()}. {best['description']} The highlight "
                "follows a fixed rule: a Balanced option with the largest saving; otherwise the "
                "option that meets the savings target with the fewest employees above the "
                "threshold."
            )
        )
    shown = mitigations[
        [
            "title",
            "description",
            "employer_saving",
            "saving_retained_pct",
            "above_threshold_pct",
            "above_threshold_change_pp",
            "label",
        ]
    ].rename(
        columns={
            "title": "Option",
            "description": "What changes",
            "employer_saving": "Employer saving",
            "saving_retained_pct": "Saving retained",
            "above_threshold_pct": "Above threshold",
            "above_threshold_change_pp": "Change vs current",
            "label": "Assessment",
        }
    )
    ui.summary_table(
        ui.display_frame(
            shown,
            symbol=symbol,
            money=["Employer saving"],
            pct=["Saving retained", "Above threshold"],
            pp=["Change vs current"],
        )
    )

    existing = {plan.name for plan in ui.all_plans()}
    addable = {option.title: option for option in options if option.plan.name not in existing}
    room = len(state.alternatives) < config.MAX_ALTERNATIVE_PLANS
    if addable:
        titles = list(addable)
        preferred = (
            titles.index(best["title"]) if best is not None and best["title"] in titles else 0
        )
        choice = st.selectbox(
            "Add a tested adjustment as an alternative plan", titles, index=preferred
        )
        if st.button("Add it and re-run", disabled=not room, icon=":material/add:"):
            added = addable[choice].plan
            state.alternatives = [*state.alternatives, added]
            state.focus_plan = added.name
            ui.inputs_changed()
            ui.reset_forms()
            with st.spinner("Running the analysis…"):
                ui.run_and_store()
            st.rerun()
        if not room:
            st.caption(
                f"The limit is {config.MAX_ALTERNATIVE_PLANS} alternatives. Remove one in the "
                "Plan designer to add another."
            )

st.subheader("Sensitivity")
st.write(
    "Does the picture hold if healthcare costs rise or more employees need significant care? "
    f"Each cell reruns the full comparison of {plan_name} with {result.baseline_name} under "
    "that combination. Other stress settings stay as they were in this run."
)
grid = ui.cached(
    "sensitivity",
    plan_name,
    lambda: sensitivity_grid(
        result.input_workforce,
        result.input_plans[0],
        result.input_plan(plan_name),
        settings,
        result.assumptions,
        result.costs,
    ),
)
metric = st.segmented_control(
    "Measure",
    options=list(charts.SENSITIVITY_METRICS),
    format_func=lambda key: charts.SENSITIVITY_METRICS[key][0],
    default="above_threshold_pct",
    required=True,
)
ui.plot(charts.sensitivity_heatmap(grid, metric, pal))
same = int((grid["label"] == alt["label"]).sum())
st.caption(
    f"The assessment stays “{alt['label']}” in {same} of {len(grid)} combinations. Deductibles "
    "and maximums stay fixed in money terms, so higher costs push more of the bill onto employees."
)
ui.table_view(
    ui.display_frame(
        grid.rename(
            columns={
                "healthcare_cost_change_pct": "Cost change",
                "high_use_shift_pct": "Moved into high use",
                "above_threshold_pct": "% above threshold",
                "above_threshold_change_pp": "Change vs current (pp)",
                "employer_saving_pct": "Employer saving %",
                "label": "Assessment",
            }
        )[
            [
                "Cost change",
                "Moved into high use",
                "% above threshold",
                "Change vs current (pp)",
                "Employer saving %",
                "Assessment",
            ]
        ],
        pct=["Cost change", "Moved into high use", "% above threshold", "Employer saving %"],
        pp=["Change vs current (pp)"],
    )
)

st.markdown("**Employer contribution trade-off**")
st.write(
    f"What if {plan_name} kept everything else, but the employer paid a different share of the "
    "premium? Each point applies one contribution rate to both coverage tiers. Moving right "
    "saves the employer more and puts more employees above the threshold."
)
sweep = ui.cached("sweep", plan_name, lambda: contribution_sweep(result, plan_name))
marked = {50.0: "50%", 100.0: "100%"}
own_rates = {
    result.input_plan(plan_name).tiers[tier].employer_contribution_pct
    for tier in config.COVERAGE_TIERS
}
current_rates = {
    result.input_plans[0].tiers[tier].employer_contribution_pct for tier in config.COVERAGE_TIERS
}
if len(current_rates) == 1:
    rate = current_rates.pop()
    marked[float(rate)] = f"{rate:g}% (current plan's rate)"
if len(own_rates) == 1:
    rate = own_rates.pop()
    marked[float(rate)] = f"{rate:g}% (this plan)"
ui.plot(charts.contribution_curve(sweep, colours[plan_name], pal, symbol, marked))
ui.table_view(
    ui.display_frame(
        sweep.rename(
            columns={
                "employer_contribution_pct": "Employer contribution",
                "employer_saving": "Employer saving",
                "employer_saving_pct": "Employer saving %",
                "above_threshold_pct": "% above threshold",
                "mean_burden_change": "Mean burden change",
            }
        ).drop(columns=["employer_cost_total"]),
        symbol=symbol,
        money=["Employer saving"],
        signed_money=["Mean burden change"],
        pct=["Employer contribution", "Employer saving %", "% above threshold"],
    )
)

st.subheader("Export")
st.write(
    "Exports contain aggregate results only. No employee-level rows are included, and segments "
    "below the minimum group size are left blank."
)
downloads = st.columns(3)
downloads[0].download_button(
    "Plan summary (CSV)",
    data=reporting.to_csv_bytes(plan_table, index=True),
    file_name="plan_summary.csv",
    mime="text/csv",
    icon=":material/download:",
    on_click="ignore",
)
downloads[1].download_button(
    "All aggregate tables (ZIP)",
    data=reporting.export_bundle(result, mitigations),
    file_name="benefit_stress_lab_export.zip",
    mime="application/zip",
    icon=":material/folder_zip:",
    on_click="ignore",
)
downloads[2].download_button(
    f"One-page summary for {plan_name} (Markdown)",
    data=reporting.summary_markdown(result, plan_name, findings, mitigations),
    file_name="advisory_summary.md",
    mime="text/markdown",
    icon=":material/description:",
    on_click="ignore",
)

st.divider()
st.caption(
    f"{ui.DISCLAIMER} Results describe modelled burden under the stated assumptions. They say "
    "nothing about any real person's health or circumstances."
)
ui.page_link("method", "Read the method and limitations", ":material/menu_book:")
