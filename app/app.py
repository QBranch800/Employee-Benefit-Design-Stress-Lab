from __future__ import annotations

import streamlit as st

import components as ui

st.set_page_config(page_title=ui.APP_TITLE, page_icon=":material/health_and_safety:", layout="wide")
ui.init_state()

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
    st.title(ui.APP_TITLE)
    st.subheader("Stress-test employee health-plan changes before they become employee problems.")
    st.write(
        "An employer can cut its health-plan bill by paying less of the premium or by raising "
        "deductibles and cost sharing. Either way, employees pay part of the saving. This app "
        "shows how much the employer saves and which employees pay for it."
    )
    st.warning(
        "**Educational use only.** Results come from synthetic data and simplified plan rules. "
        "They are not actuarial, legal, tax, or benefits advice, and they are not a basis for "
        "real plan decisions.",
        icon=":material/school:",
    )

    st.subheader("How it works")
    for column, (number, (title, text)) in zip(
        st.columns(len(STEPS)), enumerate(STEPS, start=1), strict=True
    ):
        with column.container(border=True):
            st.markdown(f"**{number}. {title}**")
            st.caption(text)

    st.subheader("Try the demonstration")
    st.write(
        "The demonstration loads 500 synthetic employees, a current plan, and three alternatives: "
        "a balanced adjustment, a proposal with a hidden affordability problem, and the same "
        "proposal with targeted support for lower-paid employees."
    )
    if st.button("Load demonstration scenario", type="primary", icon=":material/play_arrow:"):
        with st.spinner("Running the demonstration analysis…"):
            ui.load_demo()
        ui.switch_to("results")
    ui.page_link("workforce", "Or start with your own workforce", ":material/arrow_forward:")

    st.subheader("What this tool does not do")
    st.markdown("\n".join(f"- {item}" for item in NOT_FOR))


PAGES = {
    "intro": st.Page(introduction, title="Introduction", icon=":material/home:", default=True),
    "workforce": st.Page("pages/1_workforce.py", title="Workforce", icon=":material/groups:"),
    "plans": st.Page("pages/2_plan_designer.py", title="Plan designer", icon=":material/tune:"),
    "stress_test": st.Page(
        "pages/3_stress_test.py", title="Stress test", icon=":material/science:"
    ),
    "results": st.Page("pages/4_results.py", title="Results", icon=":material/insights:"),
    "method": st.Page(
        "pages/5_methodology.py", title="Method and limitations", icon=":material/menu_book:"
    ),
}

ui.register_pages(PAGES)
navigation = st.navigation(list(PAGES.values()))
ui.sidebar_status()
navigation.run()
