"""Resolve INDAGO-dialect rules YAML via RulesView, then evidence fallbacks.

Decision / replay must not hardcode ieee/rules folklore when Views or
trimmed live/ref layout already point at usable YAML.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from indago_investigate.path_jail import PathJailError, jail_resolve

# View filenames agents commonly author (plus source-field scan).
_VIEW_FILES: dict[str, tuple[str, ...]] = {
    "live": ("rules_live.json",),
    "ref_default": ("rules_default.json", "rules_ref_default.json"),
    "ref_loose": ("rules_loose.json", "rules_ref_loose.json"),
}

# Prefer new live/ref template; keep legacy flat + ieee folklore as last resort.
_FALLBACK_RELS: dict[str, tuple[str, ...]] = {
    "live": (
        "out/derived/rules_live_indago.yaml",
        "evidence/live/rules/rules_live.yaml",
        "evidence/rules/active_rules.yaml",
        "workspace/rules/active_rules.yaml",
    ),
    "ref_default": (
        "evidence/ref/rules/rules_default.yaml",
        "evidence/ref/rules_default.yaml",
        "evidence/ref/ieee/rules/rules_v1.yaml",
        "ieee/rules/rules_v1.yaml",
        "evidence/rules/ieee_default.yaml",
        "workspace/rules/ieee_default.yaml",
    ),
    "ref_loose": (
        "evidence/ref/rules/rules_loose_ref.yaml",
        "evidence/ref/ieee/rules/rules_loose_ref.yaml",
        "ieee/rules/rules_loose_ref.yaml",
        "workspace/rules/ieee_loose.yaml",
    ),
}


def _views_dir(case_root: Path) -> Path:
    return Path(case_root) / "out" / "views"


def _read_rules_view(case_root: Path, name: str) -> dict[str, Any] | None:
    path = _views_dir(case_root) / name
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _path_from_view(case_root: Path, data: dict[str, Any]) -> Path | None:
    rel = (data.get("path_or_handle") or "").strip()
    if not rel:
        return None
    try:
        p = jail_resolve(Path(case_root).resolve(), rel)
    except PathJailError:
        return None
    return p if p.is_file() else None


def _load_yaml_file(abs_path: Path) -> dict[str, Any] | None:
    if abs_path.suffix.lower() not in {".yaml", ".yml"}:
        # Foreign JSON policy needs rewrite → derived YAML; do not eval as rules.
        return None
    try:
        # load_rules_yaml expects case-relative via CaseIO.path — read directly here.
        import yaml

        doc = yaml.safe_load(abs_path.read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else None
    except Exception:
        return None


def _try_rel(case_root: Path, rel: str) -> tuple[Path, dict[str, Any]] | None:
    root = Path(case_root).resolve()
    try:
        p = jail_resolve(root, rel)
    except PathJailError:
        # Some folklore paths sit outside jail in caseio; try CaseIO path()
        try:
            from indago_investigate.health_audit.helpers import path as case_path

            p = case_path(rel)
        except Exception:
            return None
    if not p.is_file():
        return None
    doc = _load_yaml_file(p)
    if doc is None:
        return None
    return p, doc


def resolve_rules_bundle(
    case_root: Path,
    source: str,
) -> dict[str, Any] | None:
    """Return {source, path, rules, via} or None if no INDAGO YAML found."""
    root = Path(case_root).resolve()
    source = str(source).strip()

    # 1) Named view files for this source
    for fname in _VIEW_FILES.get(source, ()):
        data = _read_rules_view(root, fname)
        if not data:
            continue
        p = _path_from_view(root, data)
        if p is None:
            continue
        doc = _load_yaml_file(p)
        if doc is not None:
            return {"source": source, "path": str(p), "rules": doc, "via": f"view:{fname}"}

    # 2) Any rules*.json whose source field matches
    vdir = _views_dir(root)
    if vdir.is_dir():
        for path in sorted(vdir.glob("rules*.json")):
            data = _read_rules_view(root, path.name)
            if not data or str(data.get("source") or "") != source:
                continue
            p = _path_from_view(root, data)
            if p is None:
                continue
            doc = _load_yaml_file(p)
            if doc is not None:
                return {
                    "source": source,
                    "path": str(p),
                    "rules": doc,
                    "via": f"view:{path.name}",
                }

    # 3) Evidence / folklore fallbacks
    for rel in _FALLBACK_RELS.get(source, ()):
        hit = _try_rel(root, rel)
        if hit is None:
            continue
        p, doc = hit
        return {"source": source, "path": str(p), "rules": doc, "via": f"fallback:{rel}"}

    return None


def resolve_rules_for_replay(case_root: Path) -> dict[str, Any]:
    """Bundles for policy replay: ref_default, live, ref_loose (any may be missing)."""
    root = Path(case_root).resolve()
    out: dict[str, Any] = {
        "ref_default": resolve_rules_bundle(root, "ref_default"),
        "live": resolve_rules_bundle(root, "live"),
        "ref_loose": resolve_rules_bundle(root, "ref_loose"),
    }
    # Alternate bundle for "match live/loose" check: prefer explicit loose, else live.
    alt = out["ref_loose"] or out["live"]
    out["alternate"] = alt
    out["ok"] = bool(out["ref_default"] or out["live"] or out["ref_loose"])
    return out
