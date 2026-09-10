"""Views binding gate — enforce authored Views when INDAGO_BIND=views (default).

CaseIO ieee folklore remains available only under INDAGO_BIND=caseio (ops rollback).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from indago_investigate.bind_mode import get_bind_mode
from indago_investigate.path_jail import PathJailError, jail_resolve

# Default filenames ↔ split (§B.12.2)
_FRAME_FILES: dict[str, str] = {
    "cur": "frame_cur.json",
    "ref_val": "frame_ref_val.json",
    "ref_train": "frame_ref_train.json",
}

HINTS = (
    "Author out/views/ from _shared/docs/views_contract.md (or package/docs/views_contract.md).",
    "Run: indago-investigate validate-views .",
    "Then re-run this tool. Ops escape hatch only: INDAGO_BIND=caseio (lab, not agent path).",
)


class ViewsRequiredError(Exception):
    """Raised when bind_mode=views and Views are missing or unusable."""

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def as_payload(self, *, tool: str | None = None) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "views_required",
            "message": self.message,
            "hints": list(HINTS),
            "views_contract": "_shared/docs/views_contract.md",
            "bind_mode": get_bind_mode(),
            "tool": tool,
            **self.detail,
        }


def views_dir(case_root: Path) -> Path:
    return Path(case_root) / "out" / "views"


def load_frame_view_dict(case_root: Path, split: str) -> dict[str, Any] | None:
    """Load FrameView JSON for split, or None if file absent."""
    split = {"val": "ref_val", "train": "ref_train"}.get(split, split)
    name = _FRAME_FILES.get(split)
    if not name:
        return None
    path = views_dir(case_root) / name
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_frame_path(case_root: Path, split: str) -> Path:
    """Resolve jailed parquet path from FrameView. Raises ViewsRequiredError."""
    root = Path(case_root).resolve()
    split = {"val": "ref_val", "train": "ref_train"}.get(split, split)
    data = load_frame_view_dict(root, split)
    fname = _FRAME_FILES.get(split, f"frame_{split}.json")
    if data is None:
        raise ViewsRequiredError(
            f"Missing View `{fname}` under out/views/ — cannot load frame `{split}` without it.",
            detail={"missing_view": fname, "split": split},
        )
    rel = (data.get("path_or_handle") or "").strip()
    if not rel:
        raise ViewsRequiredError(
            f"View `{fname}` has empty path_or_handle — set a case-relative table path "
            f"(.parquet / .csv / .feather; see views_contract FrameView).",
            detail={"missing_view": fname, "split": split, "field": "path_or_handle"},
        )
    try:
        path = jail_resolve(root, rel)
    except PathJailError as exc:
        raise ViewsRequiredError(
            f"View `{fname}` path_or_handle failed path jail: {exc}",
            detail={"missing_view": fname, "split": split, "path_or_handle": rel},
        ) from exc
    if not path.is_file():
        raise ViewsRequiredError(
            f"View `{fname}` points to missing file `{rel}` — fix path or copy evidence.",
            detail={"missing_view": fname, "split": split, "path_or_handle": rel},
        )
    return path


def score_column_from_view(case_root: Path, split: str = "cur") -> str | None:
    data = load_frame_view_dict(case_root, split)
    if not data:
        return None
    roles = data.get("column_roles") or {}
    sc = roles.get("score")
    if isinstance(sc, str) and sc:
        return sc
    if isinstance(sc, list) and sc:
        return str(sc[0])
    legacy = data.get("score_column")
    return str(legacy) if legacy else None


def assert_views_ready(case_root: Path, *, need_splits: tuple[str, ...] = ("cur",)) -> dict[str, Any]:
    """Validate Views exist and required frame splits resolve. Raises ViewsRequiredError."""
    from indago_investigate.validate_views import validate_views

    root = Path(case_root).resolve()
    gate = validate_views(root, strict=False)
    if not gate.get("ok"):
        errs = gate.get("errors") or ["validate-views failed"]
        raise ViewsRequiredError(
            "Views failed validate-views — fix shape/roles/paths before using audit or L1 tools. "
            f"First error: {errs[0]}",
            detail={
                "validate_views": {
                    "ok": False,
                    "error_count": gate.get("error_count"),
                    "errors": errs[:12],
                }
            },
        )
    opened: list[str] = []
    for split in need_splits:
        path = resolve_frame_path(root, split)
        opened.append(str(path.relative_to(root)).replace("\\", "/"))
    return {"ok": True, "paths_opened": opened, "validate_views_ok": True}


def enforce_views_or_raise(case_root: Path, *, need_splits: tuple[str, ...] = ("cur",)) -> dict[str, Any] | None:
    """If bind_mode=views, require Views. prefer_views tries Views then returns None (caller may CaseIO).
    caseio skips. Returns assert payload when Views enforced successfully.
    """
    mode = get_bind_mode()
    if mode == "caseio":
        return None
    if mode == "prefer_views":
        try:
            return assert_views_ready(case_root, need_splits=need_splits)
        except ViewsRequiredError:
            return None
    # views (default)
    return assert_views_ready(case_root, need_splits=need_splits)
