from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

FONT_FAMILY = "Geist, sans-serif"


@dataclass(frozen=True)
class Palette:
    mode: str
    surface: str
    card: str
    subtle: str
    border: str
    text: str
    text_secondary: str
    muted: str
    grid: str
    axis: str
    accent: str
    accent_soft: str
    good: str
    good_soft: str
    warn: str
    warn_soft: str
    bad: str
    bad_soft: str
    primary: str
    baseline: str
    context: str
    plans: tuple[str, str, str]
    better: str
    unchanged: str
    worse: str
    diverging_scale: tuple[tuple[float, str], ...]
    sequential_scale: tuple[tuple[float, str], ...]


LIGHT = Palette(
    mode="light",
    surface="#FFFFFF",
    card="#FFFFFF",
    subtle="#FAFAFA",
    border="#EAEAEA",
    text="#171717",
    text_secondary="#666666",
    muted="#8F8F8F",
    grid="#F0F0F0",
    axis="#E0E0E0",
    accent="#2167AE",
    accent_soft="#EEF4FB",
    good="#0F7B3F",
    good_soft="#E9F6EE",
    warn="#8A5A00",
    warn_soft="#FFF4D6",
    bad="#C0362C",
    bad_soft="#FDECEA",
    primary="#2167AE",
    baseline="#8F8F8F",
    context="#E2E2E2",
    plans=("#2167AE", "#E07B39", "#1F9E89"),
    better="#2167AE",
    unchanged="#E2E2E2",
    worse="#C8453B",
    diverging_scale=((0.0, "#2167AE"), (0.5, "#F3F3F3"), (1.0, "#C8453B")),
    sequential_scale=((0.0, "#EAF2FB"), (0.5, "#5495CF"), (1.0, "#17406B")),
)

DARK = Palette(
    mode="dark",
    surface="#0A0A0A",
    card="#111111",
    subtle="#161616",
    border="#2A2A2A",
    text="#EDEDED",
    text_secondary="#A1A1A1",
    muted="#7D7D7D",
    grid="#1F1F1F",
    axis="#2E2E2E",
    accent="#5B9BD9",
    accent_soft="#12233A",
    good="#3DD68C",
    good_soft="#0F2A1D",
    warn="#F5B841",
    warn_soft="#2E2408",
    bad="#FF6B62",
    bad_soft="#331514",
    primary="#4F8FD0",
    baseline="#8F8F8F",
    context="#333333",
    plans=("#4F8FD0", "#D8743A", "#27A06F"),
    better="#4F8FD0",
    unchanged="#333333",
    worse="#E0675A",
    diverging_scale=((0.0, "#4F8FD0"), (0.5, "#222222"), (1.0, "#E0675A")),
    sequential_scale=((0.0, "#14263B"), (0.5, "#2F6DB0"), (1.0, "#A9C9EC")),
)


def palette() -> Palette:
    try:
        mode = st.context.theme.type
    except Exception:
        mode = None
    return DARK if mode == "dark" else LIGHT
