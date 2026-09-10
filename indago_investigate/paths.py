"""Resolve case roots: lab packs/FN or isolate f-cases/FN layouts.

Default: case-local only. Shared overfetch only if INDAGO_ALLOW_OVERFETCH=1.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from indago_investigate.bind_mode import allow_overfetch


def discover_overfetch(case_root: Path) -> Path | None:
    """Shared overfetch pool — disabled unless INDAGO_ALLOW_OVERFETCH=1."""
    if not allow_overfetch():
        return None
    case_root = case_root.resolve()
    shared = case_root.parent / "_shared" / "overfetch"
    if shared.is_dir():
        return shared
    packs_root = case_root.parent
    pool = packs_root / "overfetch_data"
    if pool.is_dir():
        return pool
    local = case_root / "overfetch"
    if local.is_dir():
        return local
    return None


def load_manifest(case_root: Path) -> dict[str, Any]:
    for name in ("manifest.json", "evidence_manifest.json"):
        p = case_root / name
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    return {}


def resolve_path(case_root: Path, rel: str, *, overfetch: Path | None = None) -> Path:
    """Resolve relative path under case_root; optional legacy overfetch."""
    norm = rel.replace("\\", "/").lstrip("/")
    root = case_root.resolve()
    of = overfetch if overfetch is not None else discover_overfetch(root)

    # Prefer case-local mirrors of ieee/overfetch folklore.
    if norm.startswith("overfetch/ieee/"):
        ieee_rel = norm.removeprefix("overfetch/")
        cand = root / "evidence" / "ref" / ieee_rel
        if cand.exists():
            return cand
    if norm.startswith("ieee/"):
        cand = root / "evidence" / "ref" / norm
        if cand.exists():
            return cand
        cand2 = root / "evidence" / norm
        if cand2.exists():
            return cand2

    if of is not None:
        if norm.startswith("overfetch/"):
            return of / norm.removeprefix("overfetch/")
        if norm.startswith("ieee/"):
            p = of / norm
            if p.exists():
                return p
            return of / "ieee" / norm.removeprefix("ieee/")

    return root / norm


def try_load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
