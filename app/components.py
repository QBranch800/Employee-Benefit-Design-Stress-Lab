from __future__ import annotations

import html
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import theme
from benefit_stress_lab import demo, formatting
from benefit_stress_lab.recommendations import (
    LABEL_BALANCED,
    LABEL_BASELINE,
    LABEL_NOT_PREFERRED,
    LABEL_RISK,
    LABEL_SHORTFALL,
)
from benefit_stress_lab.scenarios import AnalysisResult, run_analysis
from benefit_stress_lab.schemas import AnalysisSettings, Plan, StressAssumptions, UtilisationCosts
from benefit_stress_lab.synthetic import WorkforceSettings, generate_workforce

APP_TITLE = "Benefit Design Stress Lab"
DISCLAIMER = (
    "Educational scenario analysis on synthetic data under simplified plan rules. "
    "Not actuarial, legal, tax, or benefits advice."
)
STYLES = Path(__file__).resolve().parent / "styles.css"

BADGES = {
    LABEL_BALANCED: ("good", "Balanced"),
    LABEL_RISK: ("warn", "Employee risk increased"),
    LABEL_SHORTFALL: ("info", "Savings below target"),
    LABEL_NOT_PREFERRED: ("bad", "Not preferred"),
    LABEL_BASELINE: ("neutral", "Baseline"),
}


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    delta: str | None = None
    tone: str = "neutral"
    note: str | None = None


def _defaults() -> dict[str, Any]:
    return {
        "workforce": None,
        "workforce_source": None,
        "workforce_settings": WorkforceSettings(),
        "costs": UtilisationCosts(),
        "current_plan": demo.current_plan(),
        "alternatives": [demo.proposed_plan()],
        "settings": AnalysisSettings(),
        "assumptions": StressAssumptions(),
        "analysis": None,
        "focus_plan": None,
        "inputs_version": 0,
        "analysis_inputs_version": -1,
        "form_rev": 0,
        "run_id": 0,
        "result_cache": {},
    }


def init_state() -> None:
    for key, value in _defaults().items():
        if key not in st.session_state:
            st.session_state[key] = value


def demo_state() -> dict[str, Any]:
    settings, costs = WorkforceSettings(), UtilisationCosts()
    return {
        "workforce": generate_workforce(settings, costs),
        "workforce_source": "Synthetic demonstration",
        "workforce_settings": settings,
        "costs": costs,
        "current_plan": demo.current_plan(),
        "alternatives": demo.demo_alternatives(),
        "settings": AnalysisSettings(),
        "assumptions": StressAssumptions(),
        "focus_plan": demo.scenario_b_hidden_problem().name,
    }


def inputs_changed() -> None:
    st.session_state.inputs_version += 1


def reset_forms() -> None:
    st.session_state.form_rev += 1


def load_demo() -> None:
    st.session_state.update(demo_state())
    inputs_changed()
    reset_forms()
    run_and_store()


def run_and_store() -> AnalysisResult:
    state = st.session_state
    result = run_analysis(
        state.workforce,
        state.current_plan,
        state.alternatives,
        state.settings,
        state.assumptions,
        state.costs,
    )
    state.analysis = result
    state.analysis_inputs_version = state.inputs_version
    state.run_id += 1
    state.result_cache = {}
    return result


def analysis_is_stale() -> bool:
    state = st.session_state
    return state.analysis is not None and state.analysis_inputs_version != state.inputs_version


def cached(kind: str, plan_name: str, compute: Callable[[], Any]) -> Any:
    key = (st.session_state.run_id, kind, plan_name)
    cache = st.session_state.result_cache
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def all_plans() -> list[Plan]:
    return [st.session_state.current_plan, *st.session_state.alternatives]


def register_pages(pages: dict[str, Any]) -> None:
    st.session_state["_pages"] = pages


def page_link(key: str, label: str, icon: str | None = None) -> None:
    page = st.session_state.get("_pages", {}).get(key)
    if page is not None:
        st.page_link(page, label=label, icon=icon)


def switch_to(key: str) -> None:
    page = st.session_state.get("_pages", {}).get(key)
    if page is not None:
        st.switch_page(page)


def apply_styles() -> None:
    pal = theme.palette()
    dark = pal.mode == "dark"
    tokens = {
        "surface": pal.surface,
        "card": pal.card,
        "subtle": pal.subtle,
        "border": pal.border,
        "text": pal.text,
        "secondary": pal.text_secondary,
        "muted": pal.muted,
        "accent": pal.accent,
        "accent-soft": pal.accent_soft,
        "good": pal.good,
        "good-soft": pal.good_soft,
        "warn": pal.warn,
        "warn-soft": pal.warn_soft,
        "bad": pal.bad,
        "bad-soft": pal.bad_soft,
        "glass-top": "rgba(90, 165, 255, 0.58)" if dark else "rgba(133, 189, 253, 0.62)",
        "glass-bottom": "rgba(60, 140, 255, 0.4)" if dark else "rgba(178, 211, 252, 0.5)",
    }
    variables = "".join(f"--bsl-{name}:{value};" for name, value in tokens.items())
    st.html(f"<style>:root{{{variables}}}\n{STYLES.read_text(encoding='utf-8')}</style>")


def escape(text: str) -> str:
    return text.replace("$", "\\$")


def page_header(title: str, caption: str | None = None) -> None:
    body = f'<h1 class="bsl-page-title">{html.escape(title)}</h1>'
    if caption:
        body += f'<p class="bsl-page-caption">{html.escape(caption)}</p>'
    st.html(body)


def card(key: str) -> Any:
    return st.container(key=f"card-{key}")


def card_title(title: str, caption: str | None = None) -> None:
    body = f'<p class="bsl-card-title">{html.escape(title)}</p>'
    if caption:
        body += f'<p class="bsl-card-caption">{html.escape(caption)}</p>'
    st.html(body)


def note(text: str, strong: str | None = None) -> None:
    lead = f"<strong>{html.escape(strong)}</strong> " if strong else ""
    st.html(f'<div class="bsl-note">{lead}{html.escape(text)}</div>')


def footer(extra: str = "") -> None:
    st.html(f'<div class="bsl-footer">{html.escape(f"{DISCLAIMER} {extra}".strip())}</div>')


def tone(change: float, *, lower_is_better: bool = True) -> str:
    if round(change, 1) == 0:
        return "neutral"
    improved = change < 0 if lower_is_better else change > 0
    return "good" if improved else "bad"


def kpis(items: Sequence[Kpi], *, compact: bool = False) -> None:
    tiles = []
    for item in items:
        parts = [
            f'<span class="bsl-kpi-label">{html.escape(item.label)}</span>',
            f'<span class="bsl-kpi-value">{html.escape(item.value)}</span>',
        ]
        if item.delta:
            arrow = "↑ " if item.delta.startswith("+") else "↓ " if item.delta[0] in "-−" else ""
            change = html.escape(f"{arrow}{item.delta}")
            parts.append(f'<span class="bsl-kpi-delta bsl-{item.tone}">{change}</span>')
        if item.note:
            parts.append(f'<span class="bsl-kpi-note">{html.escape(item.note)}</span>')
        tiles.append(f'<div class="bsl-kpi">{"".join(parts)}</div>')
    style = "bsl-kpis bsl-compact" if compact else "bsl-kpis"
    st.html(f'<div class="{style}">{"".join(tiles)}</div>')


def badge(label: str) -> str:
    kind, short = BADGES.get(label, ("neutral", label))
    return f'<span class="bsl-badge bsl-{kind}">{html.escape(short)}</span>'


def callout(eyebrow: str, title: str, text: str, tone: str | None = None) -> None:
    dot = f'<span class="bsl-dot bsl-{tone}"></span>' if tone else ""
    st.html(
        f'<div class="bsl-eyebrow">{html.escape(eyebrow)}</div>'
        f'<p class="bsl-assessment-title">{dot}{html.escape(title)}</p>'
        f'<p class="bsl-assessment-text">{html.escape(text)}</p>'
    )


def assessment(label: str, rationale: str) -> None:
    callout("Assessment", label, rationale, tone=BADGES.get(label, ("neutral", label))[0])


def bullet_list(lines: Iterable[str]) -> None:
    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    st.html(f'<ul class="bsl-list">{items}</ul>')


def html_table(
    frame: pd.DataFrame,
    *,
    numeric: Iterable[str] = (),
    badges: Iterable[str] = (),
    soft: Iterable[str] = (),
    strong: Iterable[str] = (),
) -> None:
    numeric, badges, soft, strong = set(numeric), set(badges), set(soft), set(strong)

    def classes(column: str) -> str:
        names = [
            name
            for name, group in (("bsl-num", numeric), ("bsl-soft", soft), ("bsl-strong", strong))
            if column in group
        ]
        return f' class="{" ".join(names)}"' if names else ""

    head = "".join(f"<th{classes(column)}>{html.escape(str(column))}</th>" for column in frame)
    rows = []
    for _, row in frame.iterrows():
        cells = []
        for column in frame:
            value = str(row[column])
            content = badge(value) if column in badges else html.escape(value)
            cells.append(f"<td{classes(column)}>{content}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    st.html(
        '<div class="bsl-table-wrap"><table class="bsl-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def require_workforce() -> pd.DataFrame:
    workforce = st.session_state.workforce
    if workforce is None:
        st.info("Start by generating or uploading a workforce.", icon=":material/groups:")
        page_link("workforce", "Go to Workforce", ":material/arrow_forward:")
        st.stop()
    return workforce


def require_analysis() -> AnalysisResult:
    result = st.session_state.analysis
    if result is None:
        st.info(
            "No analysis yet. Set your assumptions and run the stress test, or load the "
            "demonstration scenario.",
            icon=":material/insights:",
        )
        if st.button("Load demonstration scenario", type="primary", icon=":material/play_arrow:"):
            with st.spinner("Running the demonstration analysis…"):
                load_demo()
            st.rerun()
        page_link("stress_test", "Go to Stress test", ":material/arrow_forward:")
        st.stop()
    return result


def stale_notice() -> None:
    if not analysis_is_stale():
        return
    st.warning(
        "Inputs have changed since this analysis ran, so these results are out of date.",
        icon=":material/update:",
    )
    if st.button("Re-run with current inputs", icon=":material/refresh:"):
        with st.spinner("Running the analysis…"):
            run_and_store()
        st.rerun()


def plot(figure: Any) -> None:
    st.plotly_chart(figure, theme=None, config={"displayModeBar": False})


def display_frame(
    frame: pd.DataFrame,
    *,
    symbol: str = "$",
    money: Iterable[str] = (),
    signed_money: Iterable[str] = (),
    pct: Iterable[str] = (),
    pp: Iterable[str] = (),
    whole: Iterable[str] = (),
) -> pd.DataFrame:
    shown = frame.copy()
    for col in money:
        shown[col] = [formatting.money(v, symbol) for v in frame[col]]
    for col in signed_money:
        shown[col] = [formatting.money(v, symbol, signed=True) for v in frame[col]]
    for col in pct:
        shown[col] = [formatting.pct(v) for v in frame[col]]
    for col in pp:
        shown[col] = [formatting.pp(v) for v in frame[col]]
    for col in whole:
        shown[col] = [formatting.MISSING if pd.isna(v) else f"{int(v):,}" for v in frame[col]]
    return shown


def table_view(frame: pd.DataFrame, label: str = "Data table") -> None:
    with st.expander(label, icon=":material/table:"):
        st.dataframe(frame, hide_index=True, width="stretch", height="content")
