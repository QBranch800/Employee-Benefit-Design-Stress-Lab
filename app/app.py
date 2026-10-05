from __future__ import annotations

import html
from pathlib import Path

import streamlit as st
from PIL import Image

import components as ui

LOGO = Path(__file__).resolve().parent / "static" / "logo.png"

st.set_page_config(page_title=ui.APP_TITLE, page_icon=Image.open(LOGO), layout="wide")
st.logo(str(LOGO), size="large")
ui.init_state()
ui.apply_styles()

STEPS = (
    ("Workforce", "Generate a synthetic workforce or upload an anonymised CSV."),
    ("Plans", "Enter the current plan and up to three alternatives."),
    ("Stress test", "Choose the affordability threshold and the stress assumptions."),
    ("Results", "See savings, winners and losers, affected segments, and tested fixes."),
)

NOT_FOR = (
    "It does not price plans or replace actuarial advice.",
    "It does not predict any individual's health or healthcare use.",
    "It does not choose a plan. It shows trade-offs for a person to weigh.",
    "It must not be used to set individual premiums, deny coverage, or make employment decisions.",
)


def introduction() -> None:
    st.html(
        '<div class="bsl-hero">'
        f'<span class="bsl-eyebrow">{html.escape(ui.APP_TITLE)}</span>'
        "<h1>See who pays for a cheaper health plan.</h1>"
        "<p>An employer can cut its health-plan bill by paying less of the premium or by "
        "raising deductibles and cost sharing. Either way, employees pay part of the saving. "
        "Compare plan designs on what the employer saves and on which employees absorb the "
        "difference.</p></div>"
    )
    with st.container(horizontal=True, vertical_alignment="center"):
        if st.button("Load demonstration", type="primary", icon=":material/play_arrow:"):
            with st.spinner("Running the demonstration analysis…"):
                ui.load_demo()
            ui.switch_to("results")
        ui.page_link("workforce", "Start with your own workforce", ":material/arrow_forward:")
    st.caption(
        "The demonstration loads 500 synthetic employees, a current plan, and three alternatives."
    )

    steps = "".join(
        '<div class="bsl-step">'
        f'<div class="bsl-step-number">{number:02d}</div>'
        f'<div class="bsl-step-title">{html.escape(title)}</div>'
        f'<div class="bsl-step-text">{html.escape(text)}</div></div>'
        for number, (title, text) in enumerate(STEPS, start=1)
    )
    st.html(f'<div class="bsl-steps" style="margin-top:1.5rem">{steps}</div>')

    left, right = st.columns(2, gap="medium")
    with left, ui.card("fill-use"):
        ui.card_title("Educational use only")
        ui.bullet_list(
            (
                "Results come from synthetic data and simplified plan rules.",
                "They are not actuarial, legal, tax, or benefits advice.",
                "They are not a basis for real plan decisions.",
            )
        )
    with right, ui.card("fill-limits"):
        ui.card_title("What this tool does not do")
        ui.bullet_list(NOT_FOR)


PAGES = {
    "intro": st.Page(introduction, title="Overview", icon=":material/home:", default=True),
    "workforce": st.Page("pages/1_workforce.py", title="Workforce", icon=":material/groups:"),
    "plans": st.Page("pages/2_plan_designer.py", title="Plans", icon=":material/tune:"),
    "stress_test": st.Page(
        "pages/3_stress_test.py", title="Stress test", icon=":material/science:"
    ),
    "results": st.Page("pages/4_results.py", title="Results", icon=":material/insights:"),
    "method": st.Page("pages/5_methodology.py", title="Method", icon=":material/menu_book:"),
}

ui.register_pages(PAGES)
navigation = st.navigation(list(PAGES.values()), position="top")
navigation.run()
ui.footer()
