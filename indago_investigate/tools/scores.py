"""Resolve cohort/tool scores from a bound column or offline rescore."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from indago_investigate.bind_mode import get_bind_mode
from indago_investigate.tools.runtime import load_frame, score_col
from indago_investigate.views_bind import ViewsRequiredError, score_column_from_view


def _mismatch(
    *,
    tool: str,
    frame: str,
    error: str,
    model_path: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "ok": False,
        "error_class": "model_frame_mismatch",
        "tool": tool,
        "score_source": "rescore",
        "frame": frame,
        "model_path": model_path,
        "error": error,
        "hints": [
            "Feature contract vs frame columns may disagree",
            "Treat failed rescore as evidence the model may not match this window — not as empty cohort",
        ],
    }
    if detail:
        payload.update(detail)
    logger.warning(
        "model_frame_mismatch tool={} frame={} model_path={} error={}",
        tool,
        frame,
        model_path,
        error,
    )
    return payload


def resolve_scores(
    frame: str = "cur",
    *,
    score_col_name: str | None = None,
    rescore: bool = False,
    model_path: str | None = None,
    tool: str = "resolve_scores",
) -> dict[str, Any]:
    """Return scores for cohort-style tools.

    Path A: bound / explicit score column on the frame.
    Path B: ``rescore=True`` → offline model predict (same worker as score-offline).

    Failures under Path B use ``error_class=model_frame_mismatch`` when the model
    cannot cleanly score the frame (missing features, scorer error, …).
    """
    from indago_investigate.health_audit.case_io import get_case_io
    from indago_investigate.tools import actions

    io = get_case_io()
    root = io.case_root

    if rescore:
        off = actions.score_offline(frame=frame, model_path=model_path)
        if not off.get("ok"):
            err = str(off.get("error") or "rescore failed")
            # Promote structural / contract failures to mismatch signal.
            cls = off.get("error_class") or "model_frame_mismatch"
            if cls != "model_frame_mismatch" and any(
                k in err.lower()
                for k in ("feature", "column", "shape", "pipeline", "predict", "missing")
            ):
                cls = "model_frame_mismatch"
            if cls == "model_frame_mismatch":
                return _mismatch(
                    tool=tool,
                    frame=frame,
                    error=err,
                    model_path=off.get("pkl") or model_path,
                    detail={k: off[k] for k in ("missing_feature_cols", "pkl") if k in off},
                )
            return {
                "ok": False,
                "error_class": cls,
                "tool": tool,
                "score_source": "rescore",
                "frame": frame,
                "error": err,
                "model_path": off.get("pkl") or model_path,
            }
        scores = off.get("scores") or []
        if not scores and off.get("scores_path"):
            import json
            from pathlib import Path

            try:
                blob = json.loads(Path(off["scores_path"]).read_text(encoding="utf-8"))
                scores = blob.get("scores") or []
            except (OSError, json.JSONDecodeError):
                scores = []
        series = pd.Series([float(x) for x in scores], dtype=float)
        return {
            "ok": True,
            "scores": series,
            "score_source": "rescore",
            "frame": frame,
            "model_path": off.get("pkl") or model_path,
            "n": int(len(series)),
            "mean": float(series.mean()) if len(series) else None,
        }

    # Path A — column
    df = load_frame(frame)
    try:
        if score_col_name:
            if score_col_name not in df.columns:
                return {
                    "ok": False,
                    "error_class": "missing_score_column",
                    "tool": tool,
                    "score_source": "column",
                    "frame": frame,
                    "error": f"score column {score_col_name!r} not on frame {frame}",
                    "hints": ["Pass a real column or use --rescore with a model"],
                }
            series = df[score_col_name].astype(float)
            source_col = score_col_name
        else:
            # Prefer Views role; score_col() enforces under views bind
            named = score_column_from_view(root, "cur" if frame == "cur" else frame)
            if named and named in df.columns:
                series = df[named].astype(float)
                source_col = named
            else:
                series = score_col(df)
                source_col = str(series.name) if series.name is not None else "score"
    except (ViewsRequiredError, KeyError) as exc:
        return {
            "ok": False,
            "error_class": "missing_score_column",
            "tool": tool,
            "score_source": "column",
            "frame": frame,
            "error": str(exc),
            "hints": [
                "Bind column_roles.score on the FrameView, pass --score-col, or use --rescore",
            ],
            "bind_mode": get_bind_mode(),
        }

    return {
        "ok": True,
        "scores": series.reset_index(drop=True),
        "score_source": "column",
        "score_column": source_col,
        "frame": frame,
        "n": int(len(series)),
        "mean": float(series.mean()) if len(series) else None,
    }
