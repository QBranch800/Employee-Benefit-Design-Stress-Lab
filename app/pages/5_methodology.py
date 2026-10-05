from __future__ import annotations

from pathlib import Path

import streamlit as st

import components as ui
from benefit_stress_lab import config, reporting

METHODOLOGY = Path(__file__).resolve().parents[2] / "METHODOLOGY.md"

ui.init_state()

if METHODOLOGY.exists():
    st.markdown(METHODOLOGY.read_text(encoding="utf-8"))
else:
    st.title("Method and limitations")
    st.warning("METHODOLOGY.md was not found next to the app.", icon=":material/warning:")

st.divider()
st.subheader("This session")
st.caption(f"Model version {config.MODEL_VERSION}")
result = st.session_state.analysis
if result is None:
    st.caption("No analysis has been run in this session yet.")
else:
    st.caption(f"Last analysis run: {result.run_at:%d %b %Y %H:%M:%S} UTC")
    st.dataframe(reporting.assumptions_table(result), hide_index=True, width="stretch")
