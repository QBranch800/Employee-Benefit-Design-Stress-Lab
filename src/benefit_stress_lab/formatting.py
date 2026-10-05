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


def compact_money(value: float | None, symbol: str = "$") -> str:
    if _is_missing(value):
        return MISSING
    amount = abs(float(value))
    if amount < 100_000:
        return money(value, symbol)
    sign = _MINUS if value < 0 else ""
    if amount < 999_500:
        return f"{sign}{symbol}{amount / 1_000:.0f}k"
    return f"{sign}{symbol}{amount / 1_000_000:.2f}M"


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
