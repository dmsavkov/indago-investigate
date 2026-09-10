"""Flash Views seed modes (§B.13): empty | templates | ops."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

# Default filenames ↔ kind (§B.12.2)
_FRAME_TEMPLATES: list[dict[str, Any]] = [
    {
        "file": "frame_cur.json",
        "body": {
            "view_id": "frame_cur_v1",
            "frame_id": "events_cur",
            "split": "cur",
            "n_rows": None,
            "n_cols": None,
            "path_or_handle": "",
            "column_roles": {},
            "key_columns_present": [],
            "score_column": None,
            "limitations": ["template — set path_or_handle and column_roles"],
            "extras": {},
        },
    },
    {
        "file": "frame_ref_val.json",
        "body": {
            "view_id": "frame_ref_val_v1",
            "frame_id": "events_ref_val",
            "split": "ref_val",
            "n_rows": None,
            "n_cols": None,
            "path_or_handle": "",
            "column_roles": {},
            "key_columns_present": [],
            "score_column": None,
            "limitations": ["template — set path_or_handle and column_roles"],
            "extras": {},
        },
    },
    {
        "file": "frame_ref_train.json",
        "body": {
            "view_id": "frame_ref_train_v1",
            "frame_id": "events_ref_train",
            "split": "ref_train",
            "n_rows": None,
            "n_cols": None,
            "path_or_handle": "",
            "column_roles": {},
            "key_columns_present": [],
            "score_column": None,
            "limitations": ["template — set path_or_handle and column_roles"],
            "extras": {},
        },
    },
]

_OTHER_TEMPLATES: list[dict[str, Any]] = [
    {
        "file": "alert.json",
        "body": {
            "view_id": "alert_v1",
            "incident_id": None,
            "fired_at": None,
            "product": None,
            "primary_metric": None,
            "primary_status": None,
            "window_n": None,
            "window_capacity": None,
            "co_fired_check_ids": [],
            "extras": {"raw_path": "alert.json"},
        },
    },
    {
        "file": "baseline_card.json",
        "body": {
            "view_id": "baseline_card_v1",
            "card_id": None,
            "pred_mean_val": None,
            "rules_bundle_hash": None,
            "raw_ref_id": "monitor_baseline",
            "threshold_digest": {},
            "extras": {},
        },
    },
    {
        "file": "monitor_suite.json",
        "body": {
            "view_id": "monitor_suite_v1",
            "checks": [],
            "raw_ref_id": "monitor_snapshot",
            "extras": {},
        },
    },
    {
        "file": "labels.json",
        "body": {
            "view_id": "label_v1",
            "state": "unknown",
            "horizon_days": None,
            "lag_days": None,
            "policy": None,
            "counts": {},
            "extras": {},
        },
    },
    {
        "file": "model.json",
        "body": {
            "view_id": "model_v1",
            "artifact_available": False,
            "registry_version": None,
            "alias": None,
            "path_or_handle": None,
            "feature_cols_ref": None,
            "limitations": ["template — set path when model exists"],
            "extras": {},
        },
    },
    {
        "file": "rules_live.json",
        "body": {
            "view_id": "rules_live_v1",
            "bundle_id": None,
            "bundle_hash": None,
            "source": "live",
            "path_or_handle": "",
            "extras": {},
        },
    },
    {
        "file": "queue.json",
        "body": {"view_id": "queue_v1", "channels": [], "extras": {}},
    },
    {
        "file": "infra.json",
        "body": {
            "view_id": "infra_v1",
            "latency_p95": None,
            "store_ping_ok": None,
            "extras": {},
        },
    },
    {
        "file": "feature_contract.json",
        "body": {
            "view_id": "feature_contract_v1",
            "n_train": None,
            "n_serve": None,
            "online_in_serve_features": None,
            "extras": {},
        },
    },
]


def seed_views_empty(case_root: Path) -> list[str]:
    """No filled Views — remove prior ops seed if present."""
    vdir = case_root / "out" / "views"
    written: list[str] = []
    if vdir.is_dir():
        import shutil

        shutil.rmtree(vdir)
        written.append("removed:out/views")
    # leave empty dir so agents know the slot exists
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / ".gitkeep").write_text("", encoding="utf-8")
    written.append("out/views/.gitkeep")
    logger.info("views-seed=empty under {}", vdir)
    return written


def seed_views_templates(case_root: Path) -> list[str]:
    """Skeleton JSON with empty paths/roles — no IEEE column guesses."""
    vdir = case_root / "out" / "views"
    vdir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for item in _FRAME_TEMPLATES + _OTHER_TEMPLATES:
        dest = vdir / item["file"]
        dest.write_text(json.dumps(item["body"], indent=2) + "\n", encoding="utf-8")
        written.append(str(dest.relative_to(case_root)))
    logger.info("views-seed=templates wrote {} files under {}", len(written), vdir)
    return written


def seed_views(case_root: Path, mode: str) -> list[str]:
    mode = (mode or "empty").strip().lower()
    if mode == "empty":
        return seed_views_empty(case_root)
    if mode == "templates":
        return seed_views_templates(case_root)
    if mode == "ops":
        from indago_investigate.ops_bind import bind_ieee_views

        out = bind_ieee_views(case_root)
        return list(out.get("written") or [])
    raise ValueError(f"unknown views-seed mode {mode!r}; use empty|templates|ops")
