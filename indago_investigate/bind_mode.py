"""Binding mode for CaseIO vs Views strangler (mvp-generality §14).

Default is **views** (agent path): tools require authored out/views/.
Ops rollback: INDAGO_BIND=caseio. Transition: INDAGO_BIND=prefer_views.
"""

from __future__ import annotations

import os
from typing import Literal

BindMode = Literal["caseio", "prefer_views", "views"]

_VALID = frozenset({"caseio", "prefer_views", "views"})


def get_bind_mode() -> BindMode:
    raw = (os.environ.get("INDAGO_BIND") or "views").strip().lower()
    if raw not in _VALID:
        return "views"
    return raw  # type: ignore[return-value]


def allow_overfetch() -> bool:
    """Shadow overfetch reads are off by default (G2a). Opt-in for legacy only."""
    return (os.environ.get("INDAGO_ALLOW_OVERFETCH") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
