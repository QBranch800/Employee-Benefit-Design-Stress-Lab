"""Colour and type tokens for the app's charts, one set per light/dark mode.

Hues follow the Zurich Insurance palette (Zurich blue and navy), matching
.streamlit/config.toml. Chart colours are assigned by the job they do: plans
are categorical identity (the current plan is a neutral reference), better and
worse outcomes are a diverging pair around a neutral midpoint, and magnitudes
use a single-hue sequential ramp. The plan colours pass colour-blindness
checks for three series; every chart also has direct labels or a data table,
so no value depends on colour alone.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

FONT_FAMILY = "Geist, sans-serif"


@dataclass(frozen=True)
class Palette:
    mode: str
    surface: str  # app background; also the 2px gap between touching marks
    text: str
    text_secondary: str
    muted: str
    grid: str
    axis: str
    primary: str  # single-series marks
    baseline: str  # the current plan: a neutral reference
    context: str  # de-emphasised marks
    plans: tuple[str, str, str]  # alternatives 1-3, assigned in order, never cycled
    better: str
    unchanged: str
    worse: str
    diverging_scale: tuple[tuple[float, str], ...]  # better → neutral → worse
    sequential_scale: tuple[tuple[float, str], ...]  # low → high magnitude


LIGHT = Palette(
    mode="light",
    surface="#FFFFFF",
    text="#23366F",
    text_secondary="#4A5876",
    muted="#7A8599",
    grid="#E3E8EF",
    axis="#C5CEDB",
    primary="#2167AE",
    baseline="#8A94A6",
    context="#C5CEDB",
    plans=("#2167AE", "#E07B39", "#1F9E89"),
    better="#2167AE",
    unchanged="#C5CEDB",
    worse="#C8453B",
    diverging_scale=((0.0, "#2167AE"), (0.5, "#EEF1F5"), (1.0, "#C8453B")),
    sequential_scale=((0.0, "#E3EEF8"), (0.5, "#5495CF"), (1.0, "#23366F")),
)

DARK = Palette(
    mode="dark",
    surface="#0F1A33",
    text="#F2F5FA",
    text_secondary="#B8C2D6",
    muted="#8793AB",
    grid="#22304F",
    axis="#34436A",
    primary="#4F8FD0",
    baseline="#8C96AA",
    context="#3A4868",
    plans=("#4F8FD0", "#D8743A", "#27A06F"),
    better="#4F8FD0",
    unchanged="#3A4868",
    worse="#E0675A",
    diverging_scale=((0.0, "#4F8FD0"), (0.5, "#2A3654"), (1.0, "#E0675A")),
    sequential_scale=((0.0, "#1B2C4F"), (0.5, "#2F6DB0"), (1.0, "#A9C9EC")),
)


def palette() -> Palette:
    """Tokens for the viewer's current Streamlit theme (light when unknown)."""
    try:
        mode = st.context.theme.type
    except Exception:  # outside a running app, e.g. in tests
        mode = None
    return DARK if mode == "dark" else LIGHT
