from __future__ import annotations

import pandas as pd
import streamlit as st
from pydantic import ValidationError

import charts
import components as ui
import theme
from benefit_stress_lab import config, formatting, reporting
from benefit_stress_lab import recommendations as rec
from benefit_stress_lab.affordability import burden_quantiles
from benefit_stress_lab.scenarios import compare_variants, contribution_sweep, sensitivity_grid
from benefit_stress_lab.schemas import SimulationSettings, format_validation_error
from benefit_stress_lab.simulation import run_simulation

PLAN_COLUMNS = {
    "Employer cost": "Employer cost",
    "Employer saving": "Saving",
    "Employer saving %": "Saving %",
    "Mean employee burden": "Mean burden",
    "% above threshold": "Above threshold",
    "Change in % above threshold (pp)": "Change",
    "Worse off": "Worse off",
    "Assessment": "Assessment",
}

SIMULATION_RUNS = (200, 500, 1_000, 2_000)

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

if state.analysis is None:
    ui.page_header("Results", "Run the stress test to see how each plan compares.")
result = ui.require_analysis()
ui.stale_notice()

pal = theme.palette()
settings = result.settings
symbol = settings.currency_symbol
summary = result.summary
colours = charts.plan_colours(result.plan_names, pal)
threshold = f"{settings.affordability_threshold_pct:g}%"
names = result.alternative_names
plan_table = reporting.plan_table(result)


def money(value: float, signed: bool = False) -> str:
    return formatting.money(value, symbol, signed=signed)


def plans_overview() -> None:
    shown = ui.display_frame(
        plan_table[list(PLAN_COLUMNS)].rename(columns=PLAN_COLUMNS).reset_index(),
        symbol=symbol,
        money=["Employer cost", "Saving", "Mean burden"],
        pct=["Saving %", "Above threshold"],
        pp=["Change"],
        whole=["Worse off"],
    )
    ui.html_table(
        shown,
        numeric=[
            "Employer cost",
            "Saving",
            "Saving %",
            "Mean burden",
            "Above threshold",
            "Change",
            "Worse off",
        ],
        badges=["Assessment"],
        strong=["Plan"],
    )


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


stress = "Baseline Assumptions" if result.assumptions.is_baseline() else "Stressed Assumptions"
meta = (
    f"{len(result.workforce):,} employees · {len(result.plans)} plans · {stress} · "
    f"run {result.run_at:%d %b %Y, %H:%M} UTC"
)

heading, picker = st.columns([3, 2], vertical_alignment="bottom", gap="medium")
with heading:
    ui.page_header("Results", meta)

if not names:
    with ui.card("plans-only"):
        ui.card_title("Current plan")
        plans_overview()
    st.info(
        "Add an alternative plan and run the stress test again to see comparisons.",
        icon=":material/tune:",
    )
    ui.page_link("plans", "Go to Plans", ":material/arrow_forward:")
    st.stop()

focus = names.index(state.focus_plan) if state.focus_plan in names else 0
plan_name = picker.selectbox("Compare with the current plan", names, index=focus)
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

ui.kpis(
    [
        ui.Kpi(
            "Employer cost per year",
            formatting.compact_money(alt["employer_cost_total"], symbol),
            money(-alt["employer_saving"], signed=True) if round(alt["employer_saving"]) else None,
            ui.tone(-alt["employer_saving"]),
            f"{formatting.pct(alt['employer_saving_pct'])} saving against the current plan",
        ),
        ui.Kpi(
            "Mean employee burden",
            money(alt["mean_burden"]),
            money(alt["mean_burden_change"], signed=True)
            if round(alt["mean_burden_change"])
            else None,
            ui.tone(alt["mean_burden_change"]),
            "Premium contribution plus out-of-pocket, per year",
        ),
        ui.Kpi(
            f"Above {threshold} of salary",
            formatting.pct(alt["above_threshold_pct"]),
            formatting.pp(alt["above_threshold_change_pp"])
            if round(alt["above_threshold_change_pp"], 1)
            else None,
            ui.tone(alt["above_threshold_change_pp"]),
            f"{int(alt['above_threshold_count']):,} of {int(alt['headcount']):,} employees",
        ),
        ui.Kpi(
            "Employees worse off",
            f"{int(alt['worse_off_count']):,}",
            note=(
                f"{int(alt['better_off_count']):,} better off · "
                f"{int(alt['unchanged_count']):,} unchanged"
            ),
        ),
    ]
)

overview_tab, people_tab, adjust_tab, sensitivity_tab, uncertainty_tab, export_tab = st.tabs(
    ["Overview", "Employees", "Adjustments", "Sensitivity", "Uncertainty", "Export"]
)

with overview_tab:
    chart_column, verdict_column = st.columns([7, 5], gap="medium")
    with chart_column, ui.card("fill-scatter"):
        ui.card_title(
            "Cost and affordability",
            f"Each point is a plan. Further left costs the employer less. Lower means fewer "
            f"employees whose burden exceeds {threshold} of salary.",
        )
        ui.plot(charts.cost_vs_affordability(summary, pal, symbol))
    with verdict_column, ui.card("fill-verdict"):
        ui.assessment(alt["label"], alt["label_rationale"])
        segment = result.most_affected(plan_name)
        if segment is not None:
            st.divider()
            ui.callout(
                "Most affected segment",
                segment["description"],
                f"{segment['headcount']} employees. Median burden rises by "
                f"{money(segment['median_burden_change'])} a year, "
                f"{formatting.pp(segment['median_burden_pct_change'])} of salary.",
            )
    with ui.card("overview-findings"):
        ui.card_title("Findings", f"{plan_name} compared with {result.baseline_name}")
        ui.bullet_list(
            line
            for line in findings
            if not line.startswith(("Assessment:", "Most affected segment:"))
        )
    with ui.card("overview-plans"):
        ui.card_title("All plans")
        plans_overview()

with people_tab:
    ranges_column, outcomes_column = st.columns(2, gap="medium")
    with ranges_column, ui.card("fill-ranges"):
        ui.card_title(
            "Burden as a share of salary",
            "The thick bar covers the middle half of employees and the thin line the 5th to "
            "95th percentile. The gap in the bar marks the median.",
        )
        quantiles = burden_quantiles(result.rows)
        ui.plot(charts.burden_ranges(quantiles, settings.affordability_threshold_pct, colours, pal))
        shown = quantiles.rename(
            columns={
                "p5": "5th percentile",
                "p25": "25th percentile",
                "median": "Median",
                "p75": "75th percentile",
                "p95": "95th percentile",
            }
        )
        ui.table_view(ui.display_frame(shown.reset_index(names="Plan"), pct=list(shown.columns)))
    with outcomes_column, ui.card("fill-outcomes"):
        ui.card_title(
            "Better off, unchanged, worse off",
            f"Employees whose yearly burden falls, stays within "
            f"±{money(settings.unchanged_tolerance)}, or rises against {result.baseline_name}.",
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

    with ui.card("people-bands"):
        bands = result.segments(["salary_band"])
        ui.card_title(
            "Median change in burden by salary band",
            f"{plan_name} against {result.baseline_name}. A similar change in money is a much "
            "larger share of a lower salary.",
        )
        ui.plot(charts.band_impact(bands, plan_name, colours[plan_name], pal, symbol))
        ui.table_view(segment_table(bands, {"salary_band": "Salary band"}, [plan_name]))

    coverage_column, segments_column = st.columns([5, 7], gap="medium")
    with coverage_column, ui.card("fill-coverage"):
        tiers = result.segments(["coverage_tier"])
        ui.card_title(
            "Above the threshold by coverage tier",
            f"Share of employees whose burden exceeds {threshold} of salary.",
        )
        ui.plot(charts.coverage_comparison(tiers, result.baseline_name, plan_name, colours, pal))
        ui.table_view(
            segment_table(
                tiers, {"coverage_tier": "Coverage tier"}, [result.baseline_name, plan_name]
            )
        )
    with segments_column, ui.card("fill-segments"):
        cells = result.segments(["salary_band", "coverage_tier"])
        ui.card_title(
            "Median change by salary band and coverage tier",
            f"Change in burden as a share of salary under {plan_name}. Groups with fewer than "
            f"{settings.min_group_size} employees are not reported.",
        )
        ui.plot(charts.segment_heatmap(cells, plan_name, pal))
        ui.table_view(
            segment_table(
                cells,
                {"salary_band": "Salary band", "coverage_tier": "Coverage tier"},
                [plan_name],
            )
        )

with adjust_tab:
    if not options:
        ui.note(
            f"{plan_name} does not cut employer contributions or raise cost sharing compared "
            f"with {result.baseline_name}, so there is nothing to soften."
        )
    else:
        with ui.card("adjust-chart"):
            ui.card_title(
                "Tested adjustments",
                f"Each adjustment softens {plan_name} and was recalculated on the same "
                "workforce. They are options to weigh, not recommendations.",
            )
            ui.plot(
                charts.mitigation_bars(
                    mitigations,
                    None if best is None else best["key"],
                    colours[plan_name],
                    pal,
                    symbol,
                )
            )
            if best is None:
                st.caption("None of the tested adjustments reduced the share above the threshold.")
            else:
                st.caption(
                    ui.escape(
                        f"Highlighted: {best['title'].lower()}. The highlight follows a fixed "
                        "rule: a Balanced option with the largest saving; otherwise the option "
                        "that meets the savings target with the fewest employees above the "
                        "threshold."
                    )
                )
        with ui.card("adjust-table"):
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
                    "employer_saving": "Saving",
                    "saving_retained_pct": "Retained",
                    "above_threshold_pct": "Above threshold",
                    "above_threshold_change_pp": "Change",
                    "label": "Assessment",
                }
            )
            ui.html_table(
                ui.display_frame(
                    shown,
                    symbol=symbol,
                    money=["Saving"],
                    pct=["Retained", "Above threshold"],
                    pp=["Change"],
                ),
                numeric=["Saving", "Retained", "Above threshold", "Change"],
                badges=["Assessment"],
                soft=["What changes"],
                strong=["Option"],
            )

        existing = {plan.name for plan in ui.all_plans()}
        addable = {option.title: option for option in options if option.plan.name not in existing}
        room = len(state.alternatives) < config.MAX_ALTERNATIVE_PLANS
        if addable:
            titles = list(addable)
            preferred = (
                titles.index(best["title"]) if best is not None and best["title"] in titles else 0
            )
            chooser, action = st.columns([3, 1], vertical_alignment="bottom", gap="small")
            choice = chooser.selectbox(
                "Add a tested adjustment as an alternative plan", titles, index=preferred
            )
            if action.button(
                "Add and re-run", disabled=not room, icon=":material/add:", width="stretch"
            ):
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
                    f"The limit is {config.MAX_ALTERNATIVE_PLANS} alternatives. Remove one on "
                    "the Plans page to add another."
                )

with sensitivity_tab:
    grid_column, curve_column = st.columns(2, gap="medium")
    with grid_column, ui.card("fill-grid"):
        ui.card_title(
            "Higher costs and more high users",
            f"Each cell reruns the full comparison of {plan_name} with {result.baseline_name}. "
            "Other stress settings stay as they were in this run.",
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
            format_func=charts.SENSITIVITY_LABELS.get,
            default="above_threshold_pct",
            required=True,
            label_visibility="collapsed",
        )
        measure, _, unit = charts.SENSITIVITY_METRICS[metric]
        st.caption(f"{measure}, {unit}")
        ui.plot(charts.sensitivity_heatmap(grid, metric, pal))
        if grid[metric].round(1).nunique() == 1:
            st.caption(
                f"{measure} is the same in every combination here, because it does not depend "
                "on how much care employees use."
            )
        else:
            same = int((grid["label"] == alt["label"]).sum())
            st.caption(
                f"The assessment stays “{alt['label']}” in {same} of {len(grid)} combinations. "
                "Deductibles and maximums stay fixed in money terms, so higher costs push more "
                "of the bill onto employees."
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
                pct=[
                    "Cost change",
                    "Moved into high use",
                    "% above threshold",
                    "Employer saving %",
                ],
                pp=["Change vs current (pp)"],
            )
        )
    with curve_column, ui.card("fill-curve"):
        ui.card_title(
            "Employer contribution trade-off",
            f"What if {plan_name} kept everything else, but the employer paid a different share "
            "of the premium? Each point applies one rate to both coverage tiers.",
        )
        sweep = ui.cached("sweep", plan_name, lambda: contribution_sweep(result, plan_name))
        marked = {50.0: "50%", 100.0: "100%"}
        own_rates = {
            result.input_plan(plan_name).tiers[tier].employer_contribution_pct
            for tier in config.COVERAGE_TIERS
        }
        current_rates = {
            result.input_plans[0].tiers[tier].employer_contribution_pct
            for tier in config.COVERAGE_TIERS
        }
        if len(current_rates) == 1:
            rate = current_rates.pop()
            marked[float(rate)] = f"{rate:g}% (current rate)"
        if len(own_rates) == 1:
            rate = own_rates.pop()
            marked[float(rate)] = f"{rate:g}% (this plan)"
        ui.plot(charts.contribution_curve(sweep, colours[plan_name], pal, symbol, marked))
        st.caption(
            "Moving right saves the employer more and puts more employees above the threshold."
        )
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

with uncertainty_tab:
    chosen = state.simulation_settings
    with st.spinner("Simulating…"):
        simulated = ui.cached(
            "simulation", chosen.model_dump_json(), lambda: run_simulation(result, chosen)
        )
    odds = simulated.summary.loc[plan_name]
    typical_saving = formatting.compact_money(odds["employer_saving_typical"], symbol)
    reshuffled = "costs dealt out again each year" if chosen.reshuffle_costs else "costs kept"
    st.caption(
        f"{chosen.runs:,} simulated years · {reshuffled} · individual variation "
        f"{chosen.individual_variation_pct:g}% · year-wide variation "
        f"{chosen.cost_level_variation_pct:g}%. Every plan faces the same simulated costs."
    )
    ui.kpis(
        [
            ui.Kpi(
                f"Above {threshold} of salary, typical year",
                formatting.pct(odds["above_threshold_pct_typical"]),
                note=(
                    f"{formatting.pct(odds['above_threshold_pct_low'])} to "
                    f"{formatting.pct(odds['above_threshold_pct_high'])} in 9 years out of 10"
                ),
            ),
            ui.Kpi(
                "Change against the current plan",
                formatting.pp(odds["above_threshold_change_pp_typical"]),
                note=(
                    f"{formatting.pp(odds['above_threshold_change_pp_low'])} to "
                    f"{formatting.pp(odds['above_threshold_change_pp_high'])} "
                    "in 9 years out of 10"
                ),
            ),
            ui.Kpi(
                "Savings target met",
                f"{odds['savings_target_met_pct']:.0f}% of years",
                note=(
                    f"Typical saving {typical_saving} against a "
                    f"{settings.savings_target_pct:g}% target"
                ),
            ),
            ui.Kpi(
                "Assessment unchanged",
                f"{odds['label_held_pct']:.0f}% of years",
                note=ui.BADGES.get(odds["label"], ("neutral", odds["label"]))[1],
            ),
        ],
        compact=True,
    )

    spread_column, chance_column = st.columns(2, gap="medium")
    with spread_column, ui.card("fill-spread"):
        ui.card_title(
            "Employees above the threshold, year by year",
            "The thick bar covers half of the simulated years and the thin line 9 years in "
            "10. The gap in the bar marks the typical year, which is the figure shown.",
        )
        spread = simulated.spread("above_threshold_pct")
        ui.plot(charts.simulated_ranges(spread, colours, pal))
        shown = spread.rename(
            columns={
                "p5": "5th percentile",
                "p25": "25th percentile",
                "median": "Typical year",
                "p75": "75th percentile",
                "p95": "95th percentile",
            }
        )
        ui.table_view(ui.display_frame(shown.reset_index(names="Plan"), pct=list(shown.columns)))
    with chance_column, ui.card("fill-chance"):
        ui.card_title(
            "Chance of being above the threshold",
            f"The share of simulated years in which an employee's burden exceeds {threshold} of "
            f"salary, by salary band. {plan_name} beside {result.baseline_name}.",
        )
        chances = simulated.segments(["salary_band"])
        ui.plot(charts.chance_by_band(chances, [result.baseline_name, plan_name], colours, pal))
        ui.table_view(
            ui.display_frame(
                chances[chances["plan_name"].isin([result.baseline_name, plan_name])].rename(
                    columns={
                        "plan_name": "Plan",
                        "salary_band": "Salary band",
                        "headcount": "Employees",
                        "chance_above_pct": "Chance above threshold",
                        "chance_change_pp": "Change vs current (pp)",
                    }
                )[
                    [
                        "Plan",
                        "Salary band",
                        "Employees",
                        "Chance above threshold",
                        "Change vs current (pp)",
                    ]
                ],
                pct=["Chance above threshold"],
                pp=["Change vs current (pp)"],
                whole=["Employees"],
            )
        )

    with ui.card("simulation-plans"):
        ui.card_title(
            "Employees above the threshold, all plans",
            "Target met is how often the saving reaches the target. Unchanged in is how often "
            "a simulated year earns the same assessment as the result on the other tabs.",
        )
        lines = []
        for name, row in simulated.summary.iterrows():
            reference = name == result.baseline_name
            lines.append(
                {
                    "Plan": name,
                    "Typical year": formatting.pct(row["above_threshold_pct_typical"]),
                    "9 years in 10": (
                        f"{formatting.pct(row['above_threshold_pct_low'])} to "
                        f"{formatting.pct(row['above_threshold_pct_high'])}"
                    ),
                    "Target met": (
                        formatting.MISSING
                        if reference
                        else f"{row['savings_target_met_pct']:.0f}% of years"
                    ),
                    "Assessment": row["label"],
                    "Unchanged in": (
                        formatting.MISSING
                        if reference
                        else f"{row['label_held_pct']:.0f}% of years"
                    ),
                }
            )
        ui.html_table(
            pd.DataFrame(lines),
            numeric=["Typical year", "9 years in 10", "Target met", "Unchanged in"],
            badges=["Assessment"],
            strong=["Plan"],
        )
        if float(odds["employer_cost_high"] - odds["employer_cost_low"]) < 1:
            st.caption(
                "The employer's cost is the same in every simulated year because it is made up "
                "of premiums, which do not depend on how much care employees use."
            )

    with ui.card("simulation-settings"):
        ui.card_title("Simulation settings", "What changes from one simulated year to the next.")
        fields = SimulationSettings.model_fields
        with st.form("simulation-settings", border=False):
            first, second, third, fourth = st.columns(4, gap="medium")
            runs = first.selectbox(
                "Simulated years",
                SIMULATION_RUNS,
                index=SIMULATION_RUNS.index(chosen.runs) if chosen.runs in SIMULATION_RUNS else 1,
                format_func=lambda value: f"{value:,}",
            )
            individual = second.number_input(
                "Individual variation (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(chosen.individual_variation_pct),
                step=5.0,
                format="%.0f",
                help=fields["individual_variation_pct"].description,
            )
            level = third.number_input(
                "Year-wide variation (%)",
                min_value=0.0,
                max_value=50.0,
                value=float(chosen.cost_level_variation_pct),
                step=1.0,
                format="%.0f",
                help=fields["cost_level_variation_pct"].description,
            )
            seed = fourth.number_input(
                "Random seed",
                min_value=0,
                value=int(chosen.seed),
                step=1,
                help="The same seed gives the same simulated years every time.",
            )
            reshuffle = st.checkbox(
                "Deal costs out again each year among employees with the same coverage",
                value=chosen.reshuffle_costs,
                help=fields["reshuffle_costs"].description,
            )
            rerun = st.form_submit_button("Run the simulation", type="primary")
        if rerun:
            try:
                state.simulation_settings = SimulationSettings(
                    runs=runs,
                    reshuffle_costs=reshuffle,
                    individual_variation_pct=individual,
                    cost_level_variation_pct=level,
                    seed=seed,
                )
            except ValidationError as error:
                for message in format_validation_error(error):
                    st.error(message, icon=":material/error:")
            else:
                st.rerun()

    ui.note(
        "The simulation shows how far results could move with different luck in who needs "
        "care. It does not turn synthetic or assumed costs into an actuarial forecast.",
        strong="Not a forecast.",
    )

with export_tab, ui.card("export"):
    ui.card_title(
        "Export",
        "Exports contain aggregate results only. No employee-level rows are included, and "
        "segments below the minimum group size are left blank.",
    )
    with st.container(horizontal=True):
        st.download_button(
            "Plan summary (CSV)",
            data=reporting.to_csv_bytes(plan_table, index=True),
            file_name="plan_summary.csv",
            mime="text/csv",
            icon=":material/download:",
            on_click="ignore",
        )
        st.download_button(
            "All aggregate tables (ZIP)",
            data=reporting.export_bundle(result, mitigations, simulated),
            file_name="benefit_stress_lab_export.zip",
            mime="application/zip",
            icon=":material/folder_zip:",
            on_click="ignore",
        )
        st.download_button(
            f"One-page summary for {plan_name} (Markdown)",
            data=reporting.summary_markdown(result, plan_name, findings, mitigations),
            file_name="advisory_summary.md",
            mime="text/markdown",
            icon=":material/description:",
            on_click="ignore",
        )
