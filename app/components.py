"""Session state, navigation, and layout helpers shared by every page.

Pages never calculate anything themselves: they collect inputs, call the
benefit_stress_lab engine, and display what it returns.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd
import streamlit as st

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
    """Fill in any missing session keys. Safe to call on every page."""
    for key, value in _defaults().items():
        if key not in st.session_state:
            st.session_state[key] = value


def demo_state() -> dict[str, Any]:
    """Inputs for the demonstration: specification plans A, B, C on 500 synthetic employees."""
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
    """Record that an input changed, so an earlier analysis is shown as out of date."""
    st.session_state.inputs_version += 1


def reset_forms() -> None:
    """Give form widgets fresh keys so they show values replaced programmatically."""
    st.session_state.form_rev += 1


def load_demo() -> None:
    st.session_state.update(demo_state())
    inputs_changed()
    reset_forms()
    run_and_store()


def run_and_store() -> AnalysisResult:
    """Run the analysis on the current inputs and keep the result in the session."""
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
    """Compute once per analysis run, plan, and kind of result."""
    key = (st.session_state.run_id, kind, plan_name)
    cache = st.session_state.result_cache
    if key not in cache:
        cache[key] = compute()
    return cache[key]


def all_plans() -> list[Plan]:
    return [st.session_state.current_plan, *st.session_state.alternatives]


# Navigation. Pages are registered by app.py; when a page runs on its own (in
# tests) there is nothing to link to, and the helpers quietly do nothing.


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
    with st.container(border=True):
        st.warning(
            "Inputs have changed since this analysis ran, so these results are out of date.",
            icon=":material/update:",
        )
        if st.button("Re-run with current inputs", icon=":material/refresh:"):
            with st.spinner("Running the analysis…"):
                run_and_store()
            st.rerun()


def sidebar_status() -> None:
    state = st.session_state
    with st.sidebar:
        st.markdown("**This session**")
        if state.workforce is None:
            st.caption("Workforce: not loaded")
        else:
            st.caption(f"Workforce: {len(state.workforce):,} employees ({state.workforce_source})")
        st.caption(f"Plans: current + {len(state.alternatives)} alternative(s)")
        if state.analysis is None:
            st.caption("Analysis: not run yet")
        elif analysis_is_stale():
            st.caption("Analysis: out of date (inputs changed)")
        else:
            st.caption(f"Analysis: run at {state.analysis.run_at:%H:%M} UTC")
        st.divider()
        st.caption(DISCLAIMER)


_ASSESSMENT_STYLE = {
    LABEL_BALANCED: (st.success, ":material/check_circle:"),
    LABEL_RISK: (st.warning, ":material/warning:"),
    LABEL_SHORTFALL: (st.info, ":material/info:"),
    LABEL_NOT_PREFERRED: (st.error, ":material/cancel:"),
    LABEL_BASELINE: (st.info, ":material/info:"),
}


def assessment(label: str, rationale: str) -> None:
    """Assessment label with an icon and its reasoning; never colour alone."""
    box, icon = _ASSESSMENT_STYLE.get(label, (st.info, ":material/info:"))
    box(f"**{label}.** {rationale}", icon=icon)


def delta_money(value: float, symbol: str) -> str:
    """Signed money for st.metric, which reads direction from a leading ASCII '-'."""
    rounded = round(value)
    sign = "-" if rounded < 0 else "+" if rounded > 0 else ""
    return f"{sign}{symbol}{abs(rounded):,}"


def delta_pp(value: float) -> str:
    rounded = round(value, 1)
    sign = "-" if rounded < 0 else "+" if rounded > 0 else ""
    return f"{sign}{abs(rounded):.1f} pp"


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
    """Copy of ``frame`` with numbers formatted as display text (blank cells stay '—')."""
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


def table_view(frame: pd.DataFrame, label: str = "Show the data behind this chart") -> None:
    """The table twin of a chart, so no value depends on colour or hover alone."""
    with st.expander(label, icon=":material/table:"):
        st.dataframe(frame, hide_index=True, width="stretch")
