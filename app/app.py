from __future__ import annotations

import html
import math
from pathlib import Path

import streamlit as st
from PIL import Image

import components as ui

LOGO = Path(__file__).resolve().parent / "static" / "logo.png"
SLOGAN = "See who pays for a cheaper health plan."
RING_PLANES = 12
PLANE_SPAN = 25.5
SOLID_STRIPS = 5
INNER_RADIUS = 112
OUTER_RADIUS = 138

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
    pieces = []
    for plane in range(RING_PLANES):
        centre = plane * 360 / RING_PLANES
        if plane % 2:
            width = round(2 * OUTER_RADIUS * math.tan(math.radians(PLANE_SPAN / 2)), 2)
            pieces.append(ring_piece("bsl-pale", width, centre, OUTER_RADIUS))
            continue
        span = PLANE_SPAN / SOLID_STRIPS
        width = round(2 * INNER_RADIUS * math.tan(math.radians(span / 2)) + 0.7, 2)
        for strip in range(SOLID_STRIPS):
            angle = centre + (strip - (SOLID_STRIPS - 1) / 2) * span
            pieces.append(ring_piece("bsl-solid", width, angle, INNER_RADIUS))
    return (
        '<div class="bsl-emblem" aria-hidden="true"><div class="bsl-tilt">'
        f'<div class="bsl-ring">{"".join(pieces)}</div></div></div>'
    )


def ring_piece(kind: str, width: float, angle: float, radius: int) -> str:
    return (
        f'<span class="bsl-strip {kind}" style="width:{width}px;margin-left:{-width / 2:.2f}px;'
        f'transform:rotateY({angle:g}deg) translateZ({radius}px)"></span>'
    )


def introduction() -> None:
    words, emblem = st.columns([8, 4], vertical_alignment="center", gap="large")
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
        st.html(spinning_ring())

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
