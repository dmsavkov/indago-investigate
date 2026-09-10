"""Shared report formatting: delta direction labels and count helpers."""

from __future__ import annotations


def delta_direction(*, delta: float, cur_label: str = "CUR", ref_label: str = "REF val") -> str:
    """Human-readable direction: which side is higher."""
    if delta > 0:
        return f"{cur_label} higher than {ref_label} by {abs(delta):.4g}"
    if delta < 0:
        return f"{cur_label} lower than {ref_label} by {abs(delta):.4g}"
    return f"{cur_label} equals {ref_label}"


def delta_direction_pp(delta_pp: float, *, cur_label: str = "CUR", ref_label: str = "REF val") -> str:
    if delta_pp > 0:
        return f"{cur_label} share higher than {ref_label} by {abs(delta_pp):.2f}pp"
    if delta_pp < 0:
        return f"{cur_label} share lower than {ref_label} by {abs(delta_pp):.2f}pp"
    return f"{cur_label} share equals {ref_label}"


def rate_with_n(count: int, total: int) -> str:
    if total <= 0:
        return f"0 (n=0/{total})"
    pct = 100.0 * count / total
    return f"{pct:.1f}% (n={count}/{total})"
