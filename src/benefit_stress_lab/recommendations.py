from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from benefit_stress_lab import config, formatting
from benefit_stress_lab.calculations import EPSILON
from benefit_stress_lab.schemas import AnalysisSettings, Plan

if TYPE_CHECKING:
    from benefit_stress_lab.scenarios import AnalysisResult

LABEL_BASELINE = "Baseline"
LABEL_BALANCED = "Balanced"
LABEL_RISK = "Savings achieved; employee risk increased"
LABEL_NOT_PREFERRED = "Not preferred under selected objectives"
LABEL_SHORTFALL = "Affordability maintained; savings below target"
LABELS: tuple[str, ...] = (LABEL_BALANCED, LABEL_RISK, LABEL_SHORTFALL, LABEL_NOT_PREFERRED)

PROPOSAL_KEY = "proposal"
DEFAULT_LOW_PAY_THRESHOLD = 60_000


def label_scenario(
    employer_saving_pct: float, above_threshold_change_pp: float, settings: AnalysisSettings
) -> str:
    savings_met = employer_saving_pct >= settings.savings_target_pct - EPSILON
    material_increase = above_threshold_change_pp > settings.material_increase_pp + EPSILON
    if savings_met:
        return LABEL_RISK if material_increase else LABEL_BALANCED
    return LABEL_NOT_PREFERRED if material_increase else LABEL_SHORTFALL


def label_rationale(
    employer_saving_pct: float, above_threshold_change_pp: float, settings: AnalysisSettings
) -> str:
    met = employer_saving_pct >= settings.savings_target_pct - EPSILON
    material = above_threshold_change_pp > settings.material_increase_pp + EPSILON
    return (
        f"Employer saving of {formatting.pct(employer_saving_pct)} "
        f"{'meets' if met else 'misses'} the {formatting.pct(settings.savings_target_pct)} target; "
        f"the share above the affordability threshold changes by "
        f"{formatting.pp(above_threshold_change_pp)}, which "
        f"{'exceeds' if material else 'is within'} the "
        f"{settings.material_increase_pp:g} pp materiality limit."
    )


def add_labels(summary: pd.DataFrame, settings: AnalysisSettings) -> pd.DataFrame:
    labelled = summary.copy()
    labels, reasons = [LABEL_BASELINE], ["Reference plan for all comparisons."]
    for _, row in labelled.iloc[1:].iterrows():
        args = (row["employer_saving_pct"], row["above_threshold_change_pp"], settings)
        labels.append(label_scenario(*args))
        reasons.append(label_rationale(*args))
    labelled["label"] = labels
    labelled["label_rationale"] = reasons
    return labelled


@dataclass(frozen=True)
class Mitigation:
    key: str
    title: str
    description: str
    plan: Plan


def _variant(proposal: Plan, suffix: str, **updates: object) -> Plan:
    base = proposal.name[: 40 - len(suffix) - 3].rstrip()
    data = proposal.model_dump()
    data["name"] = f"{base} + {suffix}"
    tier_changes = updates.pop("tiers", {})
    for tier, changes in tier_changes.items():
        data["tiers"][tier].update(changes)
    data.update(updates)
    return Plan.model_validate(data)


def candidate_mitigations(
    current: Plan,
    proposal: Plan,
    *,
    low_pay_threshold: float = DEFAULT_LOW_PAY_THRESHOLD,
    currency_symbol: str = "$",
) -> list[Mitigation]:
    tiers = config.COVERAGE_TIERS
    cur = current.tiers
    prop = proposal.tiers
    options: list[Mitigation] = []

    def money(value: float) -> str:
        return formatting.money(value, currency_symbol)

    current_max_pct = max(cur[t].employer_contribution_pct for t in tiers)
    if proposal.salary_subsidy is None and any(
        prop[t].employer_contribution_pct < current_max_pct for t in tiers
    ):
        options.append(
            Mitigation(
                key="low_pay_subsidy",
                title="Higher employer contribution for lower salaries",
                description=(
                    f"Employees earning below {money(low_pay_threshold)} receive at least the "
                    f"current plan's {current_max_pct:g}% employer premium contribution."
                ),
                plan=_variant(
                    proposal,
                    "Low-Pay Subsidy",
                    salary_subsidy={
                        "salary_below": low_pay_threshold,
                        "employer_contribution_pct": current_max_pct,
                    },
                ),
            )
        )

    increases = {t: max(0.0, prop[t].deductible - cur[t].deductible) for t in tiers}
    if any(increases.values()):
        options.append(
            Mitigation(
                key="deductible_allowance",
                title="Employer-funded deductible allowance",
                description=(
                    "The employer reimburses out-of-pocket costs up to the size of the deductible "
                    "increase ("
                    + "; ".join(
                        f"{money(increases[t])} {config.COVERAGE_TIER_LABELS[t].lower()}"
                        for t in tiers
                    )
                    + ")."
                ),
                plan=_variant(
                    proposal,
                    "Deductible Allowance",
                    tiers={
                        t: {"employer_allowance": prop[t].employer_allowance + increases[t]}
                        for t in tiers
                    },
                ),
            )
        )

    if prop["family"].employer_contribution_pct < cur["family"].employer_contribution_pct:
        pct = cur["family"].employer_contribution_pct
        options.append(
            Mitigation(
                key="family_contribution",
                title="Lower family-coverage contribution rate",
                description=(
                    f"Family coverage keeps the current {pct:g}% employer premium contribution."
                ),
                plan=_variant(
                    proposal, "Family Support", tiers={"family": {"employer_contribution_pct": pct}}
                ),
            )
        )

    if any(prop[t].out_of_pocket_max > cur[t].out_of_pocket_max for t in tiers):
        new_max = {
            t: max(min(prop[t].out_of_pocket_max, cur[t].out_of_pocket_max), prop[t].deductible)
            for t in tiers
        }
        options.append(
            Mitigation(
                key="lower_oop_max",
                title="Lower out-of-pocket maximum",
                description=(
                    "The out-of-pocket maximum stays at the current level ("
                    + "; ".join(
                        f"{money(new_max[t])} {config.COVERAGE_TIER_LABELS[t].lower()}"
                        for t in tiers
                    )
                    + "), or at the new deductible if that is higher."
                ),
                plan=_variant(
                    proposal,
                    "Current OOP Max",
                    tiers={t: {"out_of_pocket_max": new_max[t]} for t in tiers},
                ),
            )
        )

    cuts = {t: cur[t].employer_contribution_pct - prop[t].employer_contribution_pct for t in tiers}
    if any(cut > 0 for cut in cuts.values()):
        midpoint = {t: prop[t].employer_contribution_pct + max(cuts[t], 0) / 2 for t in tiers}
        options.append(
            Mitigation(
                key="smaller_cut",
                title="Smaller reduction in employer contribution",
                description=(
                    "The employer contribution falls only halfway to the proposal ("
                    + "; ".join(
                        f"{midpoint[t]:g}% {config.COVERAGE_TIER_LABELS[t].lower()}" for t in tiers
                    )
                    + ")."
                ),
                plan=_variant(
                    proposal,
                    "Smaller Cut",
                    tiers={t: {"employer_contribution_pct": midpoint[t]} for t in tiers},
                ),
            )
        )

    return options


def best_mitigation(table: pd.DataFrame, settings: AnalysisSettings) -> pd.Series | None:
    proposal = table.loc[table["key"] == PROPOSAL_KEY].iloc[0]
    options = table.loc[
        (table["key"] != PROPOSAL_KEY)
        & (table["above_threshold_pct"] < proposal["above_threshold_pct"] - EPSILON)
    ]
    if options.empty:
        return None
    balanced = options[options["label"] == LABEL_BALANCED]
    if not balanced.empty:
        return balanced.sort_values("employer_saving", ascending=False).iloc[0]
    meets = options[options["employer_saving_pct"] >= settings.savings_target_pct - EPSILON]
    pool = meets if not meets.empty else options
    return pool.sort_values(
        ["above_threshold_pct", "employer_saving"], ascending=[True, False]
    ).iloc[0]


def findings(
    result: AnalysisResult, plan_name: str, mitigation_table: pd.DataFrame | None = None
) -> list[str]:
    settings = result.settings
    summary = result.summary
    base = summary.iloc[0]
    alt = summary.loc[plan_name]
    pct, pp = formatting.pct, formatting.pp

    def money(value: float, signed: bool = False) -> str:
        return formatting.money(value, settings.currency_symbol, signed=signed)

    tol = money(settings.unchanged_tolerance)
    threshold = f"{settings.affordability_threshold_pct:g}%"

    saving = alt["employer_saving"]
    direction = "falls" if saving >= 0 else "rises"
    change_word = "saving" if saving >= 0 else "increase"
    lines = [
        f"Employer cost {direction} from {money(base['employer_cost_total'])} to "
        f"{money(alt['employer_cost_total'])} a year: a {change_word} of "
        f"{money(abs(saving))} ({pct(abs(alt['employer_saving_pct']))}).",
        f"Average modelled employee burden changes by {money(alt['mean_burden_change'], True)} "
        f"a year (median {money(alt['median_burden_change'], True)}).",
        f"{int(alt['worse_off_count'])} employees ({pct(alt['worse_off_pct'])}) are worse off by "
        f"more than {tol}; {int(alt['better_off_count'])} ({pct(alt['better_off_pct'])}) are "
        f"better off; {int(alt['unchanged_count'])} are within ±{tol}.",
        f"The share of employees whose modelled burden exceeds {threshold} of salary moves from "
        f"{pct(base['above_threshold_pct'])} to {pct(alt['above_threshold_pct'])} "
        f"({pp(alt['above_threshold_change_pp'])}). The {threshold} threshold is a "
        "scenario parameter, not a legal, regulatory, or clinical standard.",
    ]

    segment = result.most_affected(plan_name)
    if segment is not None:
        lines.append(
            f"Most affected segment: {segment['description']} ({segment['headcount']} employees). "
            f"Median burden rises by {money(segment['median_burden_change'])} a year, "
            f"{pp(segment['median_burden_pct_change'])} of salary; "
            f"{pct(segment['above_threshold_pct'])} of this group are above the threshold "
            f"(vs {pct(segment['baseline_above_threshold_pct'])} under {result.baseline_name})."
        )
    else:
        lines.append(
            "No salary-band and coverage-tier segment large enough to report has a higher median "
            "burden as a share of salary."
        )

    lines.append(f"Assessment: {alt['label']}. {alt['label_rationale']}")

    if mitigation_table is not None:
        best = best_mitigation(mitigation_table, settings)
        proposal_row = mitigation_table.loc[mitigation_table["key"] == PROPOSAL_KEY].iloc[0]
        if best is None:
            lines.append(
                "None of the tested adjustments reduced the share of employees above the threshold."
            )
        else:
            retained = best["saving_retained_pct"]
            retained_text = (
                f" ({pct(retained, 0)} of the proposal's saving)" if pd.notna(retained) else ""
            )
            lines.append(
                f"Tested adjustment: {best['title'].lower()}. {best['description']} It retains a "
                f"saving of {money(best['employer_saving'])}{retained_text} and changes the share "
                f"above the threshold from {pct(proposal_row['above_threshold_pct'])} to "
                f"{pct(best['above_threshold_pct'])}."
            )
    return lines
