from __future__ import annotations

import math

MISSING = "—"
_MINUS = "−"


def _is_missing(value: float | None) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def money(value: float | None, symbol: str = "$", *, signed: bool = False) -> str:
    if _is_missing(value):
        return MISSING
    rounded = round(float(value))
    sign = _MINUS if rounded < 0 else ("+" if signed and rounded > 0 else "")
    return f"{sign}{symbol}{abs(rounded):,}"


def pct(value: float | None, decimals: int = 1, *, signed: bool = False) -> str:
    if _is_missing(value):
        return MISSING
    text = f"{abs(value):.{decimals}f}%"
    if round(value, decimals) < 0:
        return _MINUS + text
    return ("+" + text) if signed and round(value, decimals) > 0 else text


def pp(value: float | None, decimals: int = 1) -> str:
    if _is_missing(value):
        return MISSING
    text = f"{abs(value):.{decimals}f} pp"
    if round(value, decimals) < 0:
        return _MINUS + text
    return ("+" + text) if round(value, decimals) > 0 else text
