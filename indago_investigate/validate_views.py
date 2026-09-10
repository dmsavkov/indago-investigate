"""validate-views — schema, roles, path jail (mvp-generality §B.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from indago_investigate.path_jail import PathJailError, jail_resolve
from indago_investigate.roles import COLUMN_ROLE_NAMES
from indago_investigate.views import FrameView, MaterializedBundle, ModelView

# Planes that need these roles to leave UNKNOWN (WARN unless --strict).
_PLANE_REQUIRED: dict[str, frozenset[str]] = {
    "population": frozenset({"slice_key", "product"}),  # either
    "business": frozenset({"amount"}),
    "model": frozenset({"score"}),
}


def _views_dir(case_root: Path, views_dir: Path | None) -> Path:
    return Path(views_dir) if views_dir is not None else case_root / "out" / "views"


def load_views_bundle(case_root: Path, views_dir: Path | None = None) -> dict[str, Any] | None:
    """Load out/views/bundle.json if present."""
    p = _views_dir(case_root, views_dir) / "bundle.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _iter_view_files(vdir: Path) -> list[Path]:
    if not vdir.is_dir():
        return []
    return sorted(p for p in vdir.glob("*.json") if p.name != "bundle.json" or True)


def _check_roles(roles: dict[str, Any], *, where: str) -> list[str]:
    errs: list[str] = []
    for role in roles:
        if role not in COLUMN_ROLE_NAMES:
            errs.append(f"ERROR unknown role {role!r} in {where}")
    return errs


def _check_frame_file(
    case_root: Path,
    data: dict[str, Any],
    *,
    strict: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    try:
        fv = FrameView.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return [f"ERROR frame schema: {exc}"], []

    errors.extend(_check_roles(fv.column_roles, where=fv.view_id))
    if not fv.path_or_handle:
        errors.append(f"ERROR {fv.view_id}: empty path_or_handle")
        return errors, warns

    try:
        path = jail_resolve(case_root, fv.path_or_handle)
    except PathJailError as exc:
        errors.append(f"ERROR {fv.view_id}: {exc}")
        return errors, warns

    cols: set[str] = set()
    try:
        from indago_investigate.table_io import load_table

        cols = set(load_table(path).columns.astype(str))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"ERROR {fv.view_id}: cannot read table schema: {exc}")
        return errors, warns

    for role, col in fv.column_roles.items():
        names = [col] if isinstance(col, str) else list(col)
        for name in names:
            if name not in cols:
                errors.append(
                    f"ERROR {fv.view_id}: role {role!r} column {name!r} not in frame schema"
                )

    if fv.split in ("cur", "ref_val", "ref_train"):
        have = set(fv.column_roles)
        if not (have & _PLANE_REQUIRED["population"]):
            msg = f"{fv.view_id}: missing slice_key/product — population plane will UNKNOWN"
            (errors if strict else warns).append(("ERROR " if strict else "WARN ") + msg)
        if "amount" not in have:
            msg = f"{fv.view_id}: missing amount — business plane may UNKNOWN"
            (errors if strict else warns).append(("ERROR " if strict else "WARN ") + msg)
        if "score" not in have and not fv.score_column:
            msg = f"{fv.view_id}: missing score role — model plane may UNKNOWN"
            (errors if strict else warns).append(("ERROR " if strict else "WARN ") + msg)

    return errors, warns


def _check_model_file(case_root: Path, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        mv = ModelView.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return [f"ERROR model schema: {exc}"]
    if mv.path_or_handle:
        try:
            jail_resolve(case_root, mv.path_or_handle)
        except PathJailError as exc:
            errors.append(f"ERROR model: {exc}")
    return errors


def validate_views(
    case_root: Path | str,
    *,
    views_dir: Path | None = None,
    strict: bool = False,
) -> dict[str, Any]:
    """Validate Views under case. Exit non-zero when errors present."""
    root = Path(case_root).resolve()
    vdir = _views_dir(root, views_dir)
    errors: list[str] = []
    warnings: list[str] = []
    roles_resolved: dict[str, Any] = {}
    paths_opened: list[str] = []

    if not vdir.is_dir():
        errors.append(f"ERROR views dir missing: {vdir}")
        return _result(root, vdir, errors, warnings, roles_resolved, paths_opened, strict)

    view_jsons = sorted(vdir.glob("*.json"))
    if not view_jsons:
        # Empty flash seed is intentional; claiming validate-views OK without files is not.
        errors.append(
            "ERROR no View JSON under out/views/ — author files per views_contract.md "
            "(empty seed is not a pass)"
        )
        return _result(root, vdir, errors, warnings, roles_resolved, paths_opened, strict)

    bundle_path = vdir / "bundle.json"
    if bundle_path.is_file():
        try:
            raw = json.loads(bundle_path.read_text(encoding="utf-8"))
            MaterializedBundle.model_validate(raw)
            paths_opened.append(str(bundle_path.relative_to(root)))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ERROR bundle.json schema: {exc}")

    for path in view_jsons:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"ERROR cannot parse {path.name}: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"ERROR {path.name}: root must be object")
            continue
        rel = path.relative_to(root).as_posix()
        paths_opened.append(rel)

        # Frame views
        if "split" in data and "column_roles" in data:
            e, w = _check_frame_file(root, data, strict=strict)
            errors.extend(e)
            warnings.extend(w)
            roles_resolved[data.get("view_id") or path.stem] = data.get("column_roles") or {}
        elif data.get("view_id", "").startswith("model") or "artifact_available" in data:
            errors.extend(_check_model_file(root, data))
        elif path.name == "bundle.json":
            # already checked
            frames = data.get("frames") or []
            for fr in frames:
                if isinstance(fr, dict):
                    e, w = _check_frame_file(root, fr, strict=strict)
                    errors.extend(e)
                    warnings.extend(w)
                    roles_resolved[fr.get("view_id") or "frame"] = fr.get("column_roles") or {}
            model = data.get("model")
            if isinstance(model, dict):
                errors.extend(_check_model_file(root, model))

    return _result(root, vdir, errors, warnings, roles_resolved, paths_opened, strict)


def _result(
    root: Path,
    vdir: Path,
    errors: list[str],
    warnings: list[str],
    roles_resolved: dict[str, Any],
    paths_opened: list[str],
    strict: bool,
) -> dict[str, Any]:
    ok = len(errors) == 0
    payload = {
        "ok": ok,
        "strict": strict,
        "case_root": str(root),
        "views_dir": str(vdir),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "roles_resolved": roles_resolved,
        "roles_missing": [],
        "paths_opened": sorted(set(paths_opened)),
    }
    # Aggregate missing plane roles across cur frames
    missing: list[str] = []
    for _vid, roles in roles_resolved.items():
        have = set(roles) if isinstance(roles, dict) else set()
        if not (have & {"slice_key", "product"}):
            missing.append("population:slice_key|product")
        if "amount" not in have:
            missing.append("business:amount")
        if "score" not in have:
            missing.append("model:score")
    payload["roles_missing"] = sorted(set(missing))
    logger.info(
        "validate-views ok={} errors={} warnings={} views={}",
        ok,
        len(errors),
        len(warnings),
        vdir,
    )
    return payload
