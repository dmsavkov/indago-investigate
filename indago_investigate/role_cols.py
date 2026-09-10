"""Resolve FrameView column_roles → physical column names (mvp-generality §21 A2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from indago_investigate.views_bind import load_frame_view_dict, score_column_from_view


def role_column(case_root: Path | str, role: str, *, split: str = "cur") -> str | None:
    """Single column name for a closed role, or None if unbound."""
    root = Path(case_root)
    if role == "score":
        return score_column_from_view(root, split)
    data = load_frame_view_dict(root, split)
    if not data:
        return None
    roles = data.get("column_roles") or {}
    val = roles.get(role)
    if isinstance(val, str) and val.strip():
        return val.strip()
    if isinstance(val, list) and val:
        return str(val[0]).strip() or None
    return None


def role_columns(case_root: Path | str, role: str, *, split: str = "cur") -> list[str]:
    """All column names for a role (supports multi-col roles like online_velocity)."""
    root = Path(case_root)
    data = load_frame_view_dict(root, split)
    if not data:
        return []
    roles = data.get("column_roles") or {}
    val = roles.get(role)
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if role == "score":
        sc = score_column_from_view(root, split)
        return [sc] if sc else []
    return []


def roles_map(case_root: Path | str, *, split: str = "cur") -> dict[str, str | list[str]]:
    """Raw column_roles dict from FrameView (may be empty)."""
    data = load_frame_view_dict(Path(case_root), split)
    if not data:
        return {}
    raw = data.get("column_roles") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def col_or_none(df: Any, name: str | None) -> Any:
    """Return series if name in df else None."""
    if not name or name not in getattr(df, "columns", []):
        return None
    return df[name]
