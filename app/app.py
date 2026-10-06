from __future__ import annotations

import html
from pathlib import Path

import streamlit as st
from PIL import Image

import components as ui
import theme

LOGO = Path(__file__).resolve().parent / "static" / "logo.png"
SLOGAN = "See who pays for a cheaper health plan."
RING_SCRIPT = Path(__file__).resolve().parent / "ring.js"
RING_PERIOD_SECONDS = 30

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


def spinning_ring() -> str:
    dark = theme.palette().mode == "dark"
    attributes = {
        "period": RING_PERIOD_SECONDS,
        "solid-top": "rgba(10, 123, 255, 0.97)",
        "solid-bottom": "rgba(0, 88, 252, 0.97)",
        "pale": "70, 155, 255" if dark else "0, 113, 254",
        "glass": 0.46 if dark else 0.36,
    }
    data = " ".join(f'data-{name}="{value}"' for name, value in attributes.items())
    return (
        f'<div class="bsl-emblem" aria-hidden="true"><canvas id="bsl-ring" {data}></canvas></div>'
        f"<script>{RING_SCRIPT.read_text(encoding='utf-8')}</script>"
    )


def introduction() -> None:
    words, emblem = st.columns([7, 5], vertical_alignment="center", gap="medium")
    with words:
        st.html(
            '<div class="bsl-hero">'
            f"<h1>{html.escape(ui.APP_TITLE)}</h1>"
            f"<p>{html.escape(SLOGAN)}</p></div>"
        )
        with st.container(horizontal=True, vertical_alignment="center"):
            if st.button("Load demonstration", type="primary", icon=":material/play_arrow:"):
                with st.spinner("Running the demonstration analysis…"):
                    ui.load_demo()
                ui.switch_to("results")
            ui.page_link("workforce", "Start with your own workforce", ":material/arrow_forward:")
    with emblem:
        st.html(spinning_ring(), unsafe_allow_javascript=True)

    steps = "".join(
        '<div class="bsl-step">'
        f'<div class="bsl-step-number">{number:02d}</div>'
        f'<div class="bsl-step-title">{html.escape(title)}</div>'
        f'<div class="bsl-step-text">{html.escape(text)}</div></div>'
        for number, (title, text) in enumerate(STEPS, start=1)
    )
    st.html(f'<div class="bsl-steps">{steps}</div>')


PAGES = {
    "intro": st.Page(introduction, title="Home", icon=":material/home:", default=True),
    "workforce": st.Page("pages/1_workforce.py", title="Workforce", icon=":material/groups:"),
    "plans": st.Page("pages/2_plan_designer.py", title="Plans", icon=":material/tune:"),
    "stress_test": st.Page(
        "pages/3_stress_test.py", title="Stress test", icon=":material/science:"
    ),
    "results": st.Page("pages/4_results.py", title="Results", icon=":material/insights:"),
    "method": st.Page("pages/5_methodology.py", title="Method", icon=":material/menu_book:"),
}

ui.register_pages(PAGES)
page = st.navigation(list(PAGES.values()), position="sidebar")
page.run()
if page is not PAGES["intro"]:
    ui.footer()
