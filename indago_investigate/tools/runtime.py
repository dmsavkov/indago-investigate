"""Shared runtime for investigation package tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from indago_investigate.bind_mode import get_bind_mode
from indago_investigate.health_audit.case_io import CaseIO, get_case_io, set_case_io
from indago_investigate.table_io import load_table
from indago_investigate.views_bind import (
    ViewsRequiredError,
    resolve_frame_path,
    score_column_from_view,
)


FRAME_KEYS = {
    "cur": "cur",
    "ref_val": "ref_val",
    "ref_train": "ref_train",
    "val": "ref_val",
    "train": "ref_train",
}


def bind_case(case_root: Path | str, *, profile: str = "ieee_flash", out_dir: Path | str | None = None) -> CaseIO:
    if profile != "ieee_flash":
        raise ValueError(f"unsupported profile {profile!r}; only ieee_flash today")
    io = CaseIO(case_root=Path(case_root), profile=profile, out_dir=Path(out_dir) if out_dir else None)
    set_case_io(io)
    (io.out_dir / "reports").mkdir(parents=True, exist_ok=True)
    return io


def load_frame(name: str) -> pd.DataFrame:
    key = FRAME_KEYS.get(name, name)
    io = get_case_io()
    mode = get_bind_mode()

    if mode == "views":
        path = resolve_frame_path(io.case_root, key)
        return load_table(path)

    if mode == "prefer_views":
        try:
            path = resolve_frame_path(io.case_root, key)
            return load_table(path)
        except ViewsRequiredError:
            logger.warning("prefer_views: falling back to CaseIO for frame {}", key)

    path = io.find_asset(key)
    if path is None or not path.is_file():
        if mode != "caseio":
            raise ViewsRequiredError(
                f"frame {name!r} unavailable — author FrameView for split `{key}` "
                f"(out/views/frame_{key if key != 'cur' else 'cur'}.json) or set INDAGO_BIND=caseio.",
                detail={"split": key, "frame": name},
            )
        raise FileNotFoundError(f"frame {name!r} unavailable under {io.case_root}")
    return load_table(path)


def score_col(df: pd.DataFrame) -> pd.Series:
    io = get_case_io()
    mode = get_bind_mode()
    if mode != "caseio":
        named = score_column_from_view(io.case_root, "cur")
        if named and named in df.columns:
            return df[named].astype(float)
        if mode == "views":
            raise ViewsRequiredError(
                "No score column bound — set column_roles.score (or score_column) on "
                "out/views/frame_cur.json per views_contract.md.",
                detail={"missing_role": "score"},
            )
    for c in ("prediction", "risk_score", "offline_score", "score", "pred", "y_pred", "fraud_score"):
        if c in df.columns:
            return df[c].astype(float)
    raise KeyError("no prediction/risk_score/offline_score/score column")


def write_report(
    tool: str,
    payload: dict[str, Any],
    *,
    md_body: str | None = None,
    write_md: bool = False,
) -> tuple[Path, Path | None]:
    """Persist tool payload as JSON. Markdown only when write_md=True (e.g. validate-judgment)."""
    io = get_case_io()
    payload = {
        **payload,
        "tool": tool,
        "profile": io.profile,
        "bind_mode": get_bind_mode(),
        "case_root": str(io.case_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    json_path = io.out_dir / "reports" / f"{tool}.json"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path: Path | None = None
    if write_md:
        md_path = io.out_dir / "reports" / f"{tool}.md"
        if md_body is None:
            md_body = f"# {tool}\n\n```json\n{json.dumps(payload, indent=2, default=str)[:8000]}\n```\n"
        md_path.write_text(md_body, encoding="utf-8")
        logger.info("wrote {} {}", json_path, md_path)
    else:
        logger.info("wrote {}", json_path)
    return json_path, md_path
