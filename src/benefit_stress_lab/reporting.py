from __future__ import annotations

import io
import zipfile

import pandas as pd

from benefit_stress_lab import config, formatting
from benefit_stress_lab.recommendations import PROPOSAL_KEY
from benefit_stress_lab.scenarios import AnalysisResult
from benefit_stress_lab.schemas import Plan

PLAN_TABLE_COLUMNS: dict[str, str] = {
    "headcount": "Headcount",
    "employer_cost_total": "Employer cost",
    "employer_saving": "Employer saving",
    "employer_saving_pct": "Employer saving %",
    "employee_premium_total": "Employee premiums",
    "employee_oop_total": "Employee out-of-pocket",
    "mean_burden": "Mean employee burden",
    "median_burden": "Median employee burden",
    "median_burden_pct": "Median burden % of salary",
    "above_threshold_count": "Employees above threshold",
    "above_threshold_pct": "% above threshold",
    "above_threshold_change_pp": "Change in % above threshold (pp)",
    "mean_burden_change": "Mean burden change",
    "median_burden_change": "Median burden change",
    "better_off_count": "Better off",
    "unchanged_count": "Unchanged",
    "worse_off_count": "Worse off",
    "label": "Assessment",
}

SEGMENT_DIMENSIONS: tuple[tuple[str, ...], ...] = (
    ("salary_band",),
    ("coverage_tier",),
    ("salary_band", "coverage_tier"),
)

LIMITATIONS: tuple[str, ...] = (
    "Simplified plan rules: no co-payments, embedded family deductibles, pharmacy tiers, or "
    "network effects.",
    "Synthetic data cannot establish real-world accuracy.",
    "Healthcare use is uncertain and highly skewed; utilisation costs are labelled assumptions.",
    "Premiums do not necessarily equal underlying claims costs; fully insured and self-funded "
    "economics differ.",
    "Salary-based burden is one dimension of affordability; household income and other "
    "resources are not modelled.",
    "Group averages and medians can conceal individual hardship.",
    "Results depend on user-selected objectives and assumptions.",
)

PLAN_CHANGES: dict[str, tuple[str, str, str]] = {
    "annual_premium": ("lower premiums", "higher premiums", "different premiums"),
    "employer_contribution_pct": (
        "a smaller employer share of the premium",
        "a larger employer share of the premium",
        "a different employer share of the premium",
    ),
    "deductible": ("lower deductibles", "higher deductibles", "different deductibles"),
    "coinsurance_pct": ("lower coinsurance", "higher coinsurance", "different coinsurance"),
    "out_of_pocket_max": (
        "lower out-of-pocket maximums",
        "higher out-of-pocket maximums",
        "different out-of-pocket maximums",
    ),
    "employer_allowance": (
        "a smaller employer allowance",
        "a larger employer allowance",
        "a different employer allowance",
    ),
}


def plan_table(result: AnalysisResult) -> pd.DataFrame:
    table = result.summary[list(PLAN_TABLE_COLUMNS)].rename(columns=PLAN_TABLE_COLUMNS)
    table.index.name = "Plan"
    return table


def segment_table(result: AnalysisResult) -> pd.DataFrame:
    frames = []
    for by in SEGMENT_DIMENSIONS:
        seg = result.segments(list(by))
        segment_label = seg[list(by)].astype(str).agg(" | ".join, axis=1)
        frames.append(
            seg.drop(columns=list(by)).assign(dimension=" × ".join(by), segment=segment_label)
        )
    table = pd.concat(frames, ignore_index=True)
    leading = ["plan_name", "dimension", "segment", "headcount", "suppressed"]
    return table[leading + [c for c in table.columns if c not in leading]]


def assumptions_table(result: AnalysisResult) -> pd.DataFrame:
    s, a, c = result.settings, result.assumptions, result.costs
    rows = [
        ("Model version", result.model_version),
        ("Analysis run (UTC)", result.run_at.strftime("%Y-%m-%d %H:%M:%S")),
        ("Headcount", len(result.workforce)),
        ("Currency", s.currency),
        (
            "Affordability threshold (% of salary, scenario parameter)",
            s.affordability_threshold_pct,
        ),
        ("Unchanged tolerance (± per year)", s.unchanged_tolerance),
        ("Minimum reported group size", s.min_group_size),
        ("Employer savings target (%)", s.savings_target_pct),
        ("Material increase in share above threshold (pp)", s.material_increase_pp),
        ("Healthcare cost change (%)", a.healthcare_cost_change_pct),
        ("Cost change applied to premiums", a.apply_to_premiums),
        ("Salary growth (%)", a.salary_growth_pct),
        ("Share moved into high use (%)", a.high_use_shift_pct),
        ("Coverage-mix shift toward family (%)", a.family_shift_pct),
        ("Stress random seed", a.seed),
        ("Low-use allowed cost, employee only", c.low),
        ("Medium-use allowed cost, employee only", c.medium),
        ("High-use allowed cost, employee only", c.high),
        ("Family allowed-cost multiplier", c.family_multiplier),
    ]
    return pd.DataFrame(rows, columns=["parameter", "value"]).astype({"value": str})


def plans_table(result: AnalysisResult) -> pd.DataFrame:
    return pd.concat([plan.to_frame() for plan in result.input_plans], ignore_index=True)


def _employer_share(current: Plan, plan: Plan) -> str | None:
    before = {current.tiers[tier].employer_contribution_pct for tier in config.COVERAGE_TIERS}
    after = {plan.tiers[tier].employer_contribution_pct for tier in config.COVERAGE_TIERS}
    if len(before) == 1 and len(after) == 1:
        return f"the employer paying {after.pop():g}% of the premium instead of {before.pop():g}%"
    return None


def describe_changes(current: Plan, plan: Plan, symbol: str = "$") -> str:
    parts = []
    for field, (lower, higher, mixed) in PLAN_CHANGES.items():
        moves = [
            getattr(plan.tiers[tier], field) - getattr(current.tiers[tier], field)
            for tier in config.COVERAGE_TIERS
        ]
        if not any(moves):
            continue
        phrase = lower if max(moves) <= 0 else higher if min(moves) >= 0 else mixed
        if field == "employer_contribution_pct":
            phrase = _employer_share(current, plan) or phrase
        parts.append(phrase)
    subsidy = plan.salary_subsidy
    if subsidy != current.salary_subsidy:
        if subsidy is None:
            parts.append("no extra support for lower salaries")
        else:
            parts.append(
                f"the employer paying at least {subsidy.employer_contribution_pct:g}% of the "
                f"premium for salaries below {formatting.money(subsidy.salary_below, symbol)}"
            )
    if not parts:
        return f"Identical to {current.name}."
    listed = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
    return f"Compared with {current.name}: {listed}."


def to_csv_bytes(frame: pd.DataFrame, *, index: bool = False) -> bytes:
    return frame.to_csv(index=index).encode("utf-8")


def export_bundle(result: AnalysisResult, mitigation_table: pd.DataFrame | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plan_summary.csv", to_csv_bytes(plan_table(result), index=True))
        archive.writestr("segments.csv", to_csv_bytes(segment_table(result)))
        archive.writestr("assumptions.csv", to_csv_bytes(assumptions_table(result)))
        archive.writestr("plans.csv", to_csv_bytes(plans_table(result)))
        if mitigation_table is not None:
            archive.writestr("mitigations.csv", to_csv_bytes(mitigation_table))
        archive.writestr(
            "README.txt",
            "Benefit Design Stress Lab aggregate export.\n"
            "Contains aggregate results only; no row-level employee data.\n"
            "Segments below the minimum group size have their metrics suppressed (blank).\n"
            "Educational scenario analysis, not actuarial, legal, tax, or benefits advice.\n",
        )
    return buffer.getvalue()


def summary_markdown(
    result: AnalysisResult,
    plan_name: str,
    findings: list[str],
    mitigation_table: pd.DataFrame | None = None,
) -> str:
    s = result.settings
    sym = s.currency_symbol
    base = result.summary.iloc[0]
    alt = result.summary.loc[plan_name]

    def money(value: float, signed: bool = False) -> str:
        return formatting.money(value, sym, signed=signed)

    lines = [
        "# Benefit Design Stress Lab: advisory summary",
        "",
        f"**{plan_name}** compared with **{result.baseline_name}** · "
        f"{len(result.workforce):,} employees · run {result.run_at:%Y-%m-%d %H:%M} UTC · "
        f"model v{result.model_version}",
        "",
        "> Educational scenario analysis using synthetic or anonymised data under simplified "
        "plan rules. Not actuarial, legal, tax, or benefits advice.",
        "",
        "## Headline results",
        "",
        f"| Measure | {result.baseline_name} | {plan_name} | Change |",
        "|---|---:|---:|---:|",
        f"| Employer cost | {money(base['employer_cost_total'])} | "
        f"{money(alt['employer_cost_total'])} | {money(-alt['employer_saving'], True)} |",
        f"| Mean employee burden | {money(base['mean_burden'])} | {money(alt['mean_burden'])} | "
        f"{money(alt['mean_burden_change'], True)} |",
        f"| Median employee burden | {money(base['median_burden'])} | "
        f"{money(alt['median_burden'])} | {money(alt['median_burden_change'], True)} |",
        f"| Above {s.affordability_threshold_pct:g}% threshold | "
        f"{formatting.pct(base['above_threshold_pct'])} | "
        f"{formatting.pct(alt['above_threshold_pct'])} | "
        f"{formatting.pp(alt['above_threshold_change_pp'])} |",
        f"| Worse off / unchanged / better off | — | {int(alt['worse_off_count'])} / "
        f"{int(alt['unchanged_count'])} / {int(alt['better_off_count'])} | — |",
        "",
        f"**Assessment:** {alt['label']}",
        "",
        "## Findings",
        "",
        *[f"- {line}" for line in findings],
        "",
    ]

    if mitigation_table is not None and len(mitigation_table) > 1:
        lines += [
            "## Tested adjustments",
            "",
            "| Option | Employer saving | Saving retained | % above threshold | Assessment |",
            "|---|---:|---:|---:|---|",
        ]
        for _, row in mitigation_table.iterrows():
            retained = (
                "—" if row["key"] == PROPOSAL_KEY else formatting.pct(row["saving_retained_pct"], 0)
            )
            lines.append(
                f"| {row['title']} | {money(row['employer_saving'])} | {retained} | "
                f"{formatting.pct(row['above_threshold_pct'])} | {row['label']} |"
            )
        lines.append("")

    a = result.assumptions
    lines += [
        "## Key assumptions",
        "",
        f"- Affordability threshold: {s.affordability_threshold_pct:g}% of salary "
        "(a scenario parameter, not a legal or clinical standard).",
        f"- Savings target {s.savings_target_pct:g}%; material increase "
        f"{s.material_increase_pp:g} pp; unchanged within ±{money(s.unchanged_tolerance)}.",
        f"- Stress: healthcare costs {a.healthcare_cost_change_pct:+g}% "
        f"({'including' if a.apply_to_premiums else 'excluding'} premiums), salaries "
        f"{a.salary_growth_pct:+g}%, {a.high_use_shift_pct:g}% moved into high use, "
        f"coverage shift {a.family_shift_pct:+g}% toward family.",
        f"- Segments with fewer than {s.min_group_size} employees are not reported.",
        "",
        "## Limitations",
        "",
        *[f"- {item}" for item in LIMITATIONS],
        "",
        f"Coverage tiers modelled: {', '.join(config.COVERAGE_TIER_LABELS.values())}.",
        "",
    ]
    return "\n".join(lines)
