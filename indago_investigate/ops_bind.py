"""Ops-only IEEE → Views binder (mvp-generality §B.7). Not an agent tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

from indago_investigate.materialize import materialize_views
from indago_investigate.path_jail import case_relative
from indago_investigate.views import MaterializedBundle


def _relpath(case_root: Path, handle: str | None) -> str | None:
    if not handle:
        return handle
    p = Path(handle)
    if p.exists():
        return case_relative(case_root, p)
    # already relative?
    return handle.replace("\\", "/")


def _rewrite_bundle_paths(case_root: Path, bundle: MaterializedBundle) -> MaterializedBundle:
    data = bundle.model_dump()
    for fr in data.get("frames") or []:
        if isinstance(fr, dict) and fr.get("path_or_handle"):
            fr["path_or_handle"] = _relpath(case_root, fr["path_or_handle"]) or ""
    model = data.get("model")
    if isinstance(model, dict) and model.get("path_or_handle"):
        model["path_or_handle"] = _relpath(case_root, model["path_or_handle"])
    for rv in data.get("rules") or []:
        if isinstance(rv, dict) and rv.get("path_or_handle"):
            rv["path_or_handle"] = _relpath(case_root, rv["path_or_handle"]) or ""
    return MaterializedBundle.model_validate(data)


def bind_ieee_views(case_root: Path | str, *, views_dir: Path | str | None = None) -> dict[str, Any]:
    """Materialize IEEE folklore into out/views/ (ops flash path)."""
    root = Path(case_root).resolve()
    vdir = Path(views_dir) if views_dir else root / "out" / "views"
    vdir.mkdir(parents=True, exist_ok=True)

    bundle = _rewrite_bundle_paths(root, materialize_views(root))
    written: list[str] = []

    bundle_path = vdir / "bundle.json"
    bundle_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
    written.append(str(bundle_path.relative_to(root)))

    for fr in bundle.frames:
        name = {
            "cur": "frame_cur.json",
            "ref_val": "frame_ref_val.json",
            "ref_train": "frame_ref_train.json",
        }.get(fr.split, f"frame_{fr.split}.json")
        dest = vdir / name
        dest.write_text(fr.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    if bundle.alert is not None:
        dest = vdir / "alert.json"
        dest.write_text(bundle.alert.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    if bundle.baseline_card is not None:
        dest = vdir / "baseline_card.json"
        dest.write_text(bundle.baseline_card.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    if bundle.model is not None:
        dest = vdir / "model.json"
        dest.write_text(bundle.model.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    for i, rv in enumerate(bundle.rules):
        dest = vdir / f"rules_{rv.source}.json"
        dest.write_text(rv.model_dump_json(indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(root)))

    # Optional machine manifest role hints (contact-ready sidecar seed)
    role_hints: dict[str, Any] = {}
    for fr in bundle.frames:
        if fr.split == "cur":
            role_hints = dict(fr.column_roles)
            break
    man = {
        "case_id": root.name,
        "schema_version": 1,
        "role_hints": role_hints,
        "views_dir": "out/views",
        "binder": "ops_ieee",
    }
    man_path = root / "manifest.json"
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    written.append("manifest.json")

    logger.info("ops bind-ieee wrote {} files under {}", len(written), vdir)
    return {
        "ok": True,
        "case_root": str(root),
        "views_dir": str(vdir),
        "written": written,
        "n_frames": len(bundle.frames),
        "roles_cur": role_hints,
    }


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Ops-only: bind IEEE case layout → out/views/*.json (not an agent tool)"
    )
    p.add_argument("case_root", type=Path)
    p.add_argument("--views-dir", type=Path, default=None)
    args = p.parse_args()
    out = bind_ieee_views(args.case_root, views_dir=args.views_dir)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
