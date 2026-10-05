from __future__ import annotations

from pathlib import Path

import streamlit as st

import components as ui
from benefit_stress_lab import config, reporting

METHODOLOGY = Path(__file__).resolve().parents[2] / "METHODOLOGY.md"

ui.init_state()

with st.container(key="prose-method"):
    if METHODOLOGY.exists():
        st.markdown(METHODOLOGY.read_text(encoding="utf-8"))
    else:
        ui.page_header("Method and limitations")
        st.warning("METHODOLOGY.md was not found next to the app.", icon=":material/warning:")

    with ui.card("method-session"):
        result = st.session_state.analysis
        if result is None:
            ui.card_title(
                "This session",
                f"Model version {config.MODEL_VERSION}. No analysis has been run yet.",
            )
        else:
            ui.card_title(
                "This session",
                f"Model version {config.MODEL_VERSION}. Last analysis run "
                f"{result.run_at:%d %b %Y, %H:%M:%S} UTC.",
            )
            table = reporting.assumptions_table(result).rename(
                columns={"parameter": "Setting", "value": "Value"}
            )
            ui.html_table(table, numeric=["Value"])
