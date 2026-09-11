"""Peek CLIs — no IEEE filename heuristics (mvp-generality §B.5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from indago_investigate.path_jail import PathJailError, jail_resolve


def peek_frame(case_root: Path | str, *, path: str, head: int = 5) -> dict[str, Any]:
    try:
        p = jail_resolve(case_root, path)
    except PathJailError as exc:
        return {"ok": False, "error": str(exc), "exit_hint": 2}

    try:
        import pandas as pd

        df = pd.read_parquet(p)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unreadable parquet: {exc}", "path": str(p), "exit_hint": 2}

    cols = []
    n = len(df)
    for name in df.columns:
        s = df[name]
        null_frac = float(s.isna().mean()) if n else 0.0
        cols.append({"name": str(name), "dtype": str(s.dtype), "null_frac": round(null_frac, 4)})
    head_n = max(0, int(head))
    head_rows = df.head(head_n).astype(object).where(df.head(head_n).notna(), None).to_dict(orient="records")
    return {
        "ok": True,
        "path": str(p),
        "n_rows": n,
        "n_cols": len(df.columns),
        "columns": cols,
        "head_rows": head_rows,
    }


def peek_json(case_root: Path | str, *, path: str) -> dict[str, Any]:
    try:
        p = jail_resolve(case_root, path)
    except PathJailError as exc:
        return {"ok": False, "error": str(exc), "exit_hint": 2}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"unreadable json: {exc}", "path": str(p), "exit_hint": 2}

    if not isinstance(data, dict):
        return {
            "ok": True,
            "path": str(p),
            "top_keys": [],
            "root_type": type(data).__name__,
            "large_array_lens": {},
            "scalar_sample": data if isinstance(data, (str, int, float, bool)) or data is None else None,
        }

    large: dict[str, int] = {}
    sample: dict[str, Any] = {}
    for k, v in list(data.items())[:40]:
        if isinstance(v, list) and len(v) >= 20:
            large[str(k)] = len(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            sample[str(k)] = v
        elif isinstance(v, dict):
            sample[str(k)] = f"dict(n_keys={len(v)})"
    return {
        "ok": True,
        "path": str(p),
        "top_keys": list(data.keys())[:40],
        "large_array_lens": large,
        "scalar_sample": sample,
    }


def peek_model(case_root: Path | str, *, path: str) -> dict[str, Any]:
    try:
        p = jail_resolve(case_root, path)
    except PathJailError as exc:
        return {"ok": False, "error": str(exc), "exit_hint": 2}

    size = p.stat().st_size if p.is_file() else None
    out: dict[str, Any] = {"ok": True, "path": str(p), "size": size, "load_ok": False}
    try:
        from indago_investigate.model_io import load_model_artifact

        model = load_model_artifact(p)
        out["load_ok"] = True
        n_feat = None
        if hasattr(model, "n_features_in_"):
            n_feat = int(model.n_features_in_)
        elif hasattr(model, "feature_name_") and model.feature_name_ is not None:
            n_feat = len(list(model.feature_name_))
        elif hasattr(model, "base_estimator") and hasattr(model.base_estimator, "n_features_in_"):
            n_feat = int(model.base_estimator.n_features_in_)
        elif isinstance(model, dict) and "feature_cols" in model:
            n_feat = len(model["feature_cols"])
        out["n_features"] = n_feat
        out["type"] = type(model).__name__
    except Exception as exc:  # noqa: BLE001
        out["load_ok"] = False
        out["error"] = str(exc)
    return out
