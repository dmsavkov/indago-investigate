"""Shared helpers for health-audit planes (package port)."""

from __future__ import annotations

from typing import Any

import json

import numpy as np
import pandas as pd

from indago_investigate.health_audit.helpers import (  # noqa: E402
    load_json,
    load_parquet,
    try_load_json,
)
from indago_investigate.health_audit.report_fmt import (  # noqa: E402
    delta_direction,
    delta_direction_pp,
    rate_with_n,
)
from indago_investigate.health_audit.thresholds import THR
from indago_investigate.table_io import load_table

CUR = "workspace/lake/events_sample.parquet"
REF_TRAIN = "evidence/ref/ieee/reference/train_sample_50k.parquet"
REF_VAL = "evidence/ref/ieee/reference/val_sample_20k.parquet"
BASELINE = "workspace/playground/outputs/monitor_baseline_ieee.json"
SNAPSHOT = "workspace/playground/outputs/monitor_snapshot_ieee.json"
ALERT = "alert.json"


def check(
    *,
    id: str,
    meaning: str,
    status: str,
    value: Any = None,
    n: Any = None,
    baseline: Any = None,
    threshold: Any = None,
    delta: Any = None,
    delta_direction: str | None = None,
    gloss_key: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "meaning": meaning,
        "status": status,
        "value": value,
        "n": n,
        "baseline": baseline,
        "threshold": threshold,
        "delta": delta,
        "delta_direction": delta_direction,
        "gloss_key": gloss_key,
    }


def plane_result(
    name: str,
    status: str,
    *,
    finding: str,
    anomaly: str | None = None,
    confidence: str = "MED",
    checks: list[dict[str, Any]] | None = None,
    metrics: dict[str, Any] | None = None,
    missing_roles: list[str] | None = None,
    missing_inputs: list[str] | None = None,
    hints: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "plane": name,
        "status": status,
        "finding": finding,
        "anomaly": anomaly,
        "confidence": confidence,
        "checks": checks or [],
        "metrics": metrics or {},
    }
    if missing_roles:
        out["missing_roles"] = list(missing_roles)
    if missing_inputs:
        out["missing_inputs"] = list(missing_inputs)
    if hints:
        out["hints"] = list(hints)
    return out


def worst_status(statuses: list[str]) -> str:
    order = {"UNKNOWN": 0, "GREEN": 1, "WARN": 2, "ALERT": 3}
    return max(statuses, key=lambda s: order.get(s, 0)) if statuses else "UNKNOWN"


def confidence_for_n(n: int) -> str:
    if n >= 200:
        return "HIGH"
    if n >= THR["small_n"]:
        return "MED"
    return "LOW"


def score_series(df: pd.DataFrame, *, score_col: str | None = None) -> pd.Series:
    """Resolve score column: explicit name, else Views role, else CaseIO folklore names."""
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.health_audit.case_io import get_case_io
    from indago_investigate.role_cols import role_column

    if score_col and score_col in df.columns:
        return df[score_col].astype(float)
    try:
        io = get_case_io()
        named = role_column(io.case_root, "score", split="cur")
        if named and named in df.columns:
            return df[named].astype(float)
    except RuntimeError:
        pass
    if get_bind_mode() == "caseio":
        if "prediction" in df.columns:
            return df["prediction"].astype(float)
        if "risk_score" in df.columns:
            return df["risk_score"].astype(float)
    raise KeyError(
        "no score column — bind column_roles.score on FrameView "
        "(or CaseIO folklore under INDAGO_BIND=caseio)"
    )


def psi(cur: np.ndarray, ref: np.ndarray, bins: int = 10) -> float:
    cur = cur[np.isfinite(cur)]
    ref = ref[np.isfinite(ref)]
    if len(cur) < 5 or len(ref) < 5:
        return float("nan")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return float("nan")
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    c_hist, _ = np.histogram(cur, bins=edges)
    r_hist, _ = np.histogram(ref, bins=edges)
    c_p = c_hist.astype(float) + 1e-6
    r_p = r_hist.astype(float) + 1e-6
    c_p /= c_p.sum()
    r_p /= r_p.sum()
    return float(np.sum((c_p - r_p) * np.log(c_p / r_p)))


def ks_statistic(cur: np.ndarray, ref: np.ndarray) -> float:
    cur = np.sort(cur[np.isfinite(cur)])
    ref = np.sort(ref[np.isfinite(ref)])
    if len(cur) < 5 or len(ref) < 5:
        return float("nan")
    grid = np.unique(np.concatenate([cur, ref]))
    cdf_c = np.searchsorted(cur, grid, side="right") / len(cur)
    cdf_r = np.searchsorted(ref, grid, side="right") / len(ref)
    return float(np.max(np.abs(cdf_c - cdf_r)))


def wasserstein_1d(cur: np.ndarray, ref: np.ndarray) -> float:
    cur = cur[np.isfinite(cur)]
    ref = ref[np.isfinite(ref)]
    if len(cur) < 5 or len(ref) < 5:
        return float("nan")
    qs = np.linspace(0, 1, 101)
    return float(np.mean(np.abs(np.quantile(cur, qs) - np.quantile(ref, qs))))


def _read_split_frame(split: str) -> tuple[Any, str | None]:
    """Load frame for split: Views path under views/prefer_views; CaseIO under caseio."""
    import pandas as pd

    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.health_audit.case_io import get_case_io
    from indago_investigate.table_io import load_table
    from indago_investigate.views_bind import ViewsRequiredError, resolve_frame_path

    io = get_case_io()
    mode = get_bind_mode()
    if mode != "caseio":
        try:
            p = resolve_frame_path(io.case_root, split)
            return load_table(p), str(p.relative_to(io.case_root)).replace("\\", "/")
        except ViewsRequiredError:
            if mode == "views" and split == "cur":
                raise
            if mode == "views":
                return pd.DataFrame(), None
    asset = {"cur": "cur", "ref_val": "ref_val", "ref_train": "ref_train"}[split]
    found = io.find_asset(asset)
    if found is not None and found.is_file():
        return load_table(found), str(found.relative_to(io.case_root)).replace("\\", "/")
    folklore = {"cur": CUR, "ref_val": REF_VAL, "ref_train": REF_TRAIN}[split]
    try:
        return load_parquet(folklore), folklore
    except Exception:
        return pd.DataFrame(), None


def _enrich_baseline_from_ref(
    baseline: dict[str, Any],
    ref_val: Any,
    roles: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing card scalars from REF val (DerivedBaseline). No customer card ask."""
    out = dict(baseline or {})
    score_col = roles.get("score") if isinstance(roles, dict) else None
    if isinstance(score_col, list):
        score_col = score_col[0] if score_col else None
    derived_fields: list[str] = []
    try:
        n_val = len(ref_val) if ref_val is not None else 0
    except TypeError:
        n_val = 0
    if n_val and score_col and hasattr(ref_val, "columns") and score_col in ref_val.columns:
        if out.get("pred_mean_val") is None:
            try:
                out["pred_mean_val"] = float(ref_val[score_col].mean())
                derived_fields.append("pred_mean_val")
            except Exception:
                pass
        if out.get("n_val") is None:
            out["n_val"] = int(n_val)
            derived_fields.append("n_val")
    if derived_fields:
        out["_derived_from_ref"] = True
        out["_derived_fields"] = derived_fields
    return out


def load_context() -> dict[str, Any]:
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.health_audit.case_io import get_case_io
    from indago_investigate.role_cols import roles_map

    cur, cur_path = _read_split_frame("cur")
    ref_train, train_path = _read_split_frame("ref_train")
    ref_val, val_path = _read_split_frame("ref_val")
    try:
        baseline = load_json(BASELINE)
    except Exception:
        baseline = try_load_json("evidence/monitor_baseline.json") or {}
    try:
        alert = load_json(ALERT)
    except Exception:
        alert = {}
    # Prefer thin AlertView when present (contact path); keep raw alert as fallback.
    io = get_case_io()
    alert_view_path = io.case_root / "out" / "views" / "alert.json"
    if alert_view_path.is_file():
        try:
            av = json.loads(alert_view_path.read_text(encoding="utf-8"))
            # Merge View rumor fields onto alert digest without dropping raw keys.
            if av.get("primary_metric") and not alert.get("metric"):
                alert = {**alert, "metric": av.get("primary_metric")}
            if av.get("incident_id") and not alert.get("incident_id"):
                alert["incident_id"] = av.get("incident_id")
            if av.get("window_n") and not alert.get("n_events"):
                alert["n_events"] = av.get("window_n")
            alert["_from_alert_view"] = True
        except Exception:
            pass
    snap = try_load_json(SNAPSHOT) or try_load_json("evidence/monitor_snapshot.json") or {}
    aliases = try_load_json("workspace/registry/aliases.json") or try_load_json("evidence/aliases.json") or {}
    queue = (
        try_load_json("workspace/telemetry/queue_backlog.json")
        or try_load_json("evidence/queue_backlog.json")
        or {}
    )
    infra = (
        try_load_json("workspace/telemetry/infra_summary.json")
        or try_load_json("evidence/infra_summary.json")
        or {}
    )
    k8s = try_load_json("workspace/telemetry/k8s_events.json") or {}
    dbt = (
        try_load_json("workspace/orchestration/dbt_run_summary.json")
        or try_load_json("evidence/dbt_run_summary.json")
        or {}
    )
    labels = (
        try_load_json("workspace/labels/label_state.json")
        or try_load_json("evidence/label_state.json")
        or {}
    )
    champion_spec = (
        try_load_json("workspace/playground/outputs/ieee_champion_spec.json")
        or try_load_json("ieee/models/champion_spec.json")
        or try_load_json("evidence/models/champion_spec.json")
        or {}
    )
    models_index = (
        try_load_json("ieee/models/models_index.json")
        or try_load_json("evidence/models/models_index.json")
        or {}
    )
    feature_contract = (
        try_load_json("workspace/playground/outputs/ieee_feature_contract.json")
        or try_load_json("ieee/lineage/feature_contract.json")
        or try_load_json("evidence/feature_contract.json")
        or {}
    )
    git_snap = try_load_json("ieee/lineage/git_snapshot.json") or {}
    roles = roles_map(io.case_root, split="cur")
    baseline = _enrich_baseline_from_ref(baseline, ref_val, roles)
    # Policy expected hash: prefer card; else hash REF/default rules we can load (no customer card).
    if not baseline.get("rules_bundle_hash"):
        from indago_investigate.health_audit.rules_eval import load_rules_yaml, rules_bundle_hash

        for rel in (
            "evidence/ref/rules/rules_default.yaml",
            "evidence/ref/rules_default.yaml",
            "evidence/ref/ieee/rules/rules_v1.yaml",
            "ieee/rules/rules_v1.yaml",
            "evidence/rules/ieee_default.yaml",
            "workspace/rules/ieee_default.yaml",
        ):
            try:
                rules = load_rules_yaml(rel)
                baseline = {
                    **baseline,
                    "rules_bundle_hash": rules_bundle_hash(rules),
                    "_rules_hash_from_ref_default": True,
                }
                break
            except Exception:
                continue
    return {
        "cur": cur,
        "ref_train": ref_train,
        "ref_val": ref_val,
        "baseline": baseline,
        "alert": alert,
        "snap": snap,
        "aliases": aliases,
        "queue": queue,
        "infra": infra,
        "k8s": k8s,
        "dbt": dbt,
        "labels": labels,
        "champion_spec": champion_spec,
        "models_index": models_index,
        "feature_contract": feature_contract,
        "git_snap": git_snap,
        "n_cur": len(cur),
        "n_train": len(ref_train),
        "n_val": len(ref_val),
        "bind_mode": get_bind_mode(),
        "case_root": io.case_root,
        "roles": roles,
        "frame_paths": {"cur": cur_path, "ref_train": train_path, "ref_val": val_path},
    }


def build_sources_meta(ctx: dict[str, Any]) -> dict[str, Any]:
    from indago_investigate.health_audit.case_io import get_case_io

    alert = ctx["alert"]
    baseline = ctx["baseline"]
    aliases = ctx["aliases"]
    champ = (aliases.get("aliases") or {}).get("champion") or {}
    cur = ctx["cur"]
    live_hash = None
    if "rules_bundle_hash" in cur.columns and len(cur):
        live_hash = str(cur["rules_bundle_hash"].iloc[0])
    online_v = None
    batch_v = None
    if "online_feature_version" in cur.columns and len(cur):
        online_v = str(cur["online_feature_version"].iloc[0])
    if "batch_feature_version" in cur.columns and len(cur):
        batch_v = str(cur["batch_feature_version"].iloc[0])
    fc = ctx.get("feature_contract") or {}
    cs = ctx.get("champion_spec") or {}
    mi = ctx.get("models_index") or {}
    models = mi.get("models") or []
    io = get_case_io()
    return {
        "product": alert.get("product") or "ieee",
        "incident_id": alert.get("incident_id"),
        "profile": io.profile,
        "case_root": str(io.case_root),
        "data": {
            "cur_events": {"path": str(io.find_asset("cur") or CUR), "n": ctx["n_cur"]},
            "ref_train": {"path": str(io.find_asset("ref_train") or REF_TRAIN), "n": ctx["n_train"]},
            "ref_val": {"path": str(io.find_asset("ref_val") or REF_VAL), "n": ctx["n_val"]},
            "gold_table": alert.get("gold_table") or baseline.get("gold_table"),
            "silver_build_id": (ctx.get("dbt") or {}).get("silver_build_id"),
            "window_capacity": alert.get("window"),
        },
        "model": {
            "model_name": alert.get("model_name") or champ.get("model_name"),
            "alias": champ.get("alias") or "champion",
            "registry_version": champ.get("registry_version") or alert.get("champion_version"),
            "run_id_label": alert.get("run_id_label") or champ.get("run_id_label"),
            "model_uri": champ.get("model_uri"),
            "val_pr_auc": champ.get("val_pr_auc"),
            "val_roc_auc": champ.get("val_roc_auc"),
            "champion_spec": cs.get("champion"),
            "selection_metric": cs.get("selection_metric"),
            "models_exported": [
                {
                    "alias": m.get("alias"),
                    "registry_version": m.get("registry_version"),
                    "copied_as": m.get("copied_as"),
                }
                for m in models
            ],
            "pkl": str(io.champion_pkl() or "ieee/models/ieee_champion_v3.pkl"),
        },
        "rules": {
            "live_hash": live_hash,
            "baseline_hash": baseline.get("rules_bundle_hash") or alert.get("rules_bundle_hash_baseline"),
            "baseline_bundle_id": baseline.get("rules_bundle_id"),
            "rules_default": "evidence/ref/rules/rules_default.yaml",
            "rules_loose": "evidence/ref/rules/rules_loose_ref.yaml",
        },
        "baseline_card": {
            "id": baseline.get("monitoring_baseline") or alert.get("monitoring_baseline"),
            "n_val": baseline.get("n_val"),
            "pred_mean_val": baseline.get("pred_mean_val"),
            "approval_rate_val": baseline.get("approval_rate_val"),
            "created_at": baseline.get("created_at"),
            "registry_version": baseline.get("registry_version"),
        },
        "feature_contract": {
            "n_train_cols": len(fc.get("train_feature_cols") or fc.get("feature_cols") or []),
            "n_serve_cols": len(fc.get("serve_feature_cols") or []),
            "online_feature_version": online_v
            or fc.get("online_feature_version")
            or baseline.get("online_feature_version"),
            "batch_feature_version": batch_v
            or fc.get("batch_feature_version")
            or baseline.get("batch_feature_version"),
        },
        "code": {
            "git_sha_alert": alert.get("git_sha"),
            "git_sha_baseline": baseline.get("git_sha"),
            "git_snapshot": ctx.get("git_snap") or {},
            "dbt_models_ok": (ctx.get("dbt") or {}).get("models_ok"),
        },
        "relationships": [
            "CUR events scored by champion PKL under live rules_bundle_hash",
            "Monitor compares live metrics to baseline card",
            "Feature health uses REF train for null spikes and REF val for PSI",
            "Policy replay re-applies rules YAML to fixed CUR scores",
            "Population / slice discovery compares CUR shares and scores to REF val",
        ],
    }


# re-export for type checkers
__all__ = [
    "ALERT",
    "BASELINE",
    "CUR",
    "REF_TRAIN",
    "REF_VAL",
    "SNAPSHOT",
    "build_sources_meta",
    "check",
    "confidence_for_n",
    "delta_direction",
    "delta_direction_pp",
    "ks_statistic",
    "load_context",
    "plane_result",
    "psi",
    "rate_with_n",
    "score_series",
    "wasserstein_1d",
    "worst_status",
]
