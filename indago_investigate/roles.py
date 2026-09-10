"""Closed column_roles vocabulary (mvp-generality §B.1)."""

from __future__ import annotations

from typing import Final

# Role name → expected semantic (dtype guidance for validate-views later).
COLUMN_ROLES: Final[dict[str, str]] = {
    "score": "numeric model score / risk",
    "decision": "approve/decline or equivalent",
    "slice_key": "primary entity/slice column for concentration",
    "amount": "monetary or volume amount",
    "product": "product / cohort code",
    "policy_hash": "live rules bundle fingerprint on rows",
    "timestamp": "event time if present",
    "online_velocity": "online feature(s) for serving checks",
}

COLUMN_ROLE_NAMES: Final[frozenset[str]] = frozenset(COLUMN_ROLES)


def is_known_role(name: str) -> bool:
    return name in COLUMN_ROLE_NAMES
