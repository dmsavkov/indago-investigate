"""L0–L2 investigation actions (ieee_flash). Each returns a JSON-serializable payload."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from indago_investigate.health_audit.case_io import get_case_io
from indago_investigate.health_audit.common import ks_statistic, psi, wasserstein_1d
from indago_investigate.health_audit.model_scoring import (
    feature_cols_for_version,
    get_importances,
    score_parquet,
)
from indago_investigate.health_audit.rules_eval import (
    decision_rates,
    evaluate_authorize,
    rules_bundle_hash,
)
from indago_investigate.inventory import inventory_evidence
from indago_investigate.refs import Availability
from indago_investigate.tools.runtime import load_frame, score_col


def validate_alert() -> dict[str, Any]:
    io = get_case_io()
    alert = io.load_json("alert.json")
    baseline = io.try_load_json("workspace/playground/outputs/monitor_baseline_ieee.json") or {}
    failed = alert.get("failed_checks") or []
    return {
        "status": "rumor",
        "incident_id": alert.get("incident_id"),
        "primary_metric": alert.get("metric"),
        "n_events": alert.get("n_events"),
        "window": alert.get("window"),
        "fired_at": alert.get("fired_at"),
        "co_fired": [{"id": c.get("id"), "status": c.get("status"), "message": c.get("message")} for c in failed],
        "baseline_id": alert.get("monitoring_baseline") or baseline.get("monitoring_baseline"),
        "note": "Primary metric is unverified rumor until health_audit / discriminating checks.",
    }


def profile_table(*, frame: str = "cur", top_nulls: int = 25) -> dict[str, Any]:
    df = load_frame(frame)
    n = len(df)
    null_rates = []
    for c in df.columns:
        null_n = int(df[c].isna().sum())
        if null_n:
            null_rates.append({"col": c, "null_n": null_n, "null_rate": round(null_n / n, 4)})
    null_rates.sort(key=lambda x: -x["null_rate"])
    zero_mass = []
    flag_notes: list[dict[str, Any]] = []
    for c in df.select_dtypes(include=[np.number]).columns:
        z = int((df[c] == 0).sum())
        if z / n >= 0.5:
            zero_mass.append({"col": c, "zero_n": z, "zero_rate": round(z / n, 4)})
        # Boolean-ish 0/1 flags: report mean separately (zero_rate on flags is confusing)
        if c == "online_velocity_zero_at_fetch" or (
            c.endswith("_zero_at_fetch") and set(pd.unique(df[c].dropna().astype(float))) <= {0.0, 1.0}
        ):
            flag_notes.append(
                {
                    "col": c,
                    "true_rate": round(float(df[c].fillna(0).astype(float).mean()), 4),
                    "note": "boolean flag: true_rate = share of rows with velocity-zero-at-fetch; "
                    "ignore high_zero_mass for this column",
                }
            )
    zero_mass.sort(key=lambda x: -x["zero_rate"])
    # Drop flag columns from high_zero_mass — they invert semantics
    flag_cols = {f["col"] for f in flag_notes}
    zero_mass = [z for z in zero_mass if z["col"] not in flag_cols]
    # Prefer Views roles (y_hat / score / …) over IEEE folklore column names
    score_name = None
    decision_name = None
    try:
        from indago_investigate.role_cols import role_column

        io = get_case_io()
        split = "cur" if frame == "cur" else frame
        score_name = role_column(io.case_root, "score", split=split)
        decision_name = role_column(io.case_root, "decision", split=split)
    except Exception:
        pass
    if not score_name:
        for cand in ("prediction", "y_hat", "score", "y_pred"):
            if cand in df.columns:
                score_name = cand
                break
    if not decision_name:
        decision_name = "decision" if "decision" in df.columns else None
    return {
        "frame": frame,
        "n_rows": n,
        "n_cols": len(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "top_nulls": null_rates[:top_nulls],
        "high_zero_mass": zero_mass[:top_nulls],
        "boolean_flag_rates": flag_notes,
        "has_prediction": bool(score_name and score_name in df.columns),
        "has_decision": bool(decision_name and decision_name in df.columns),
        "score_column": score_name if score_name in df.columns else None,
        "decision_column": decision_name if decision_name in df.columns else None,
        "naming_note": (
            "high_zero_mass = fraction of numeric values == 0. "
            "For online_velocity_zero_at_fetch use boolean_flag_rates.true_rate "
            "(or the monitor check), not high_zero_mass."
        ),
    }


def compare_distributions(
    *,
    frame_a: str = "cur",
    frame_b: str = "ref_val",
    columns: list[str] | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    a = load_frame(frame_a)
    b = load_frame(frame_b)
    cols = columns or [
        c
        for c in a.select_dtypes(include=[np.number]).columns
        if c in b.columns and c not in ("TransactionID",)
    ]
    rows = []
    for c in cols[:80]:
        ca = a[c].astype(float).to_numpy()
        cb = b[c].astype(float).to_numpy()
        rows.append(
            {
                "col": c,
                "psi": psi(ca, cb),
                "ks": ks_statistic(ca, cb),
                "w1": wasserstein_1d(ca, cb),
                "mean_a": float(np.nanmean(ca)) if len(ca) else None,
                "mean_b": float(np.nanmean(cb)) if len(cb) else None,
                "n_a": int(np.isfinite(ca).sum()),
                "n_b": int(np.isfinite(cb).sum()),
            }
        )
    rows.sort(key=lambda r: -(r["psi"] if r["psi"] == r["psi"] else -1))
    return {
        "frame_a": frame_a,
        "frame_b": frame_b,
        "n_a": len(a),
        "n_b": len(b),
        "caveat": "PSI/KS/W1 noisy at small n; treat as exploratory when n<100–200.",
        "top_by_psi": rows[:top_k],
    }


def parity_compare(*, frame: str = "cur") -> dict[str, Any]:
    import json
    from pathlib import Path

    df = load_frame(frame)
    live = score_col(df)
    off = score_offline(frame=frame)
    if not off.get("ok"):
        return {"ok": False, "error": off.get("error"), "live_mean": float(live.mean())}
    blob = json.loads(Path(off["scores_path"]).read_text(encoding="utf-8"))
    arr = np.array(blob.get("scores") or [], dtype=float)
    n = min(len(live), len(arr))
    if n == 0:
        return {"ok": False, "error": "empty scores"}
    delta = live.iloc[:n].to_numpy() - arr[:n]
    return {
        "ok": True,
        "frame": frame,
        "n": n,
        "live_mean": float(live.iloc[:n].mean()),
        "offline_mean": float(arr[:n].mean()),
        "mae": float(np.mean(np.abs(delta))),
        "max_abs": float(np.max(np.abs(delta))),
        "corr": float(np.corrcoef(live.iloc[:n], arr[:n])[0, 1]) if n > 2 else None,
    }


def replay_policy() -> dict[str, Any]:
    from pathlib import Path

    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.role_cols import role_column
    from indago_investigate.rules_resolve import resolve_rules_for_replay

    df = load_frame("cur")
    io = get_case_io()
    baseline = io.try_load_json("workspace/playground/outputs/monitor_baseline_ieee.json") or {}
    bundles = resolve_rules_for_replay(Path(io.case_root))
    if not bundles.get("ok"):
        return {
            "ok": False,
            "error": "rules YAML unavailable — author RulesView to INDAGO dialect or place evidence/ref/rules/*.yaml",
            "hints": [
                "Rewrite foreign live JSON → out/derived/rules_live_indago.yaml + RulesView",
                "Point rules_default View at evidence/ref/rules/rules_default.yaml",
            ],
        }
    default_hit = bundles.get("ref_default") or bundles.get("alternate")
    alt_hit = bundles.get("alternate") or bundles.get("ref_default")
    rules_default = default_hit["rules"]
    rules_alt = alt_hit["rules"]
    scores = score_col(df)

    def _replay(rules: dict[str, Any]) -> list[str]:
        out = []
        for i, s in enumerate(scores):
            row = df.iloc[i]
            ctx = {"vip": bool(row.get("vip", False)), "ofac_hit": bool(row.get("ofac_hit", False))}
            d, _, _ = evaluate_authorize(float(s), context=ctx, rules=rules)
            out.append(d)
        return out

    decision_col = role_column(io.case_root, "decision", split="cur")
    if get_bind_mode() == "caseio" and not decision_col:
        decision_col = "decision" if "decision" in df.columns else None
    observed = (
        df[decision_col].astype(str).tolist()
        if decision_col and decision_col in df.columns
        else []
    )
    default_dec = _replay(rules_default)
    alt_dec = _replay(rules_alt)
    n = len(df)
    return {
        "ok": True,
        "n_events": n,
        "score_mean": float(scores.mean()),
        "rules": {
            "default_hash": rules_bundle_hash(rules_default),
            "default_path": default_hit.get("path"),
            "default_via": default_hit.get("via"),
            "alternate_hash": rules_bundle_hash(rules_alt),
            "alternate_source": alt_hit.get("source"),
            "alternate_path": alt_hit.get("path"),
            "alternate_via": alt_hit.get("via"),
            "baseline_card_hash": baseline.get("rules_bundle_hash"),
            "live_hash": str(df["rules_bundle_hash"].iloc[0]) if "rules_bundle_hash" in df.columns else None,
        },
        "decision_rates": {
            "observed": decision_rates(observed) if observed else {},
            "replay_default": decision_rates(default_dec),
            "replay_alternate": decision_rates(alt_dec),
        },
        "match_default": observed == default_dec if observed else None,
        "match_alternate": observed == alt_dec if observed else None,
        "decision_column": decision_col,
        "note": "Scores held fixed; rules from RulesView/evidence (not ieee folklore). decision column from Views role under views bind.",
    }


def slice_summary(
    *,
    key: str | None = None,
    frame: str = "cur",
    ref: str = "ref_val",
    top_k: int = 15,
    rescore: bool = False,
    model_path: str | None = None,
    score_col_name: str | None = None,
) -> dict[str, Any]:
    if not key:
        return {"ok": False, "error": "key required (pass --key <column>); no default slice column"}
    from indago_investigate.tools.scores import resolve_scores

    cur = load_frame(frame)
    val = load_frame(ref)
    if key not in cur.columns:
        return {"ok": False, "error": f"key {key} missing on {frame}"}
    resolved = resolve_scores(
        frame,
        score_col_name=score_col_name,
        rescore=rescore,
        model_path=model_path,
        tool="slice-summary",
    )
    if not resolved.get("ok"):
        return resolved
    scores = resolved["scores"]
    if len(scores) != len(cur):
        return {
            "ok": False,
            "error_class": "model_frame_mismatch",
            "error": f"score length {len(scores)} != frame rows {len(cur)}",
            "score_source": resolved.get("score_source"),
            "frame": frame,
        }
    cur = cur.copy()
    cur["_score"] = scores.to_numpy()
    g = cur.groupby(key, dropna=False)
    rows = []
    n = len(cur)
    val_share = val[key].value_counts(normalize=True) if key in val.columns else None
    for level, part in g:
        share = len(part) / n
        vshare = float(val_share.get(level, 0.0)) if val_share is not None else None
        rows.append(
            {
                "level": str(level),
                "n": int(len(part)),
                "share": round(share, 4),
                "ref_share": round(vshare, 4) if vshare is not None else None,
                "delta_pp": round((share - (vshare or 0)) * 100, 2) if vshare is not None else None,
                "mean_score": float(part["_score"].mean()),
            }
        )
    rows.sort(key=lambda r: -r["n"])
    return {
        "ok": True,
        "key": key,
        "frame": frame,
        "ref": ref,
        "n": n,
        "top_slices": rows[:top_k],
        "score_source": resolved.get("score_source"),
        "score_column": resolved.get("score_column"),
        "model_path": resolved.get("model_path"),
    }


def topk_importance(
    *,
    k: int = 30,
    model_path: str | None = None,
    importance_path: str | None = None,
    model_view: str | None = None,
) -> dict[str, Any]:
    """Feature importance from agent-selected paths (mvp-generality §21.4).

    Prefer --importance-path artifact when provided; else compute from --model-path
    or ModelView path. No hardcoded ieee_champion under views bind.
    """
    import json
    from pathlib import Path

    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.path_jail import PathJailError, jail_resolve

    io = get_case_io()
    root = io.case_root

    if importance_path:
        try:
            ip = jail_resolve(root, importance_path)
        except PathJailError as exc:
            return {"ok": False, "error": f"importance-path jail: {exc}"}
        if not ip.is_file():
            return {"ok": False, "error": f"importance-path missing: {importance_path}"}
        try:
            raw = json.loads(ip.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "error": f"cannot parse importance file: {exc}"}
        ranked_in = raw.get("ranked") or raw.get("top_k") or raw.get("features") or []
        ranked = []
        for row in ranked_in:
            if isinstance(row, dict):
                name = row.get("feature") or row.get("name")
                imp_v = float(row.get("importance") or row.get("gain") or 0)
            else:
                continue
            if isinstance(name, str):
                ranked.append({"feature": name, "importance": imp_v})
            if len(ranked) >= k:
                break
        return {
            "ok": True,
            "source": "importance_path",
            "importance_path": importance_path,
            "top_k": ranked,
            "caveat": "Precomputed ranks — method depends on the artifact author.",
        }

    pkl: Path | None = None
    if model_path:
        try:
            pkl = jail_resolve(root, model_path)
        except PathJailError as exc:
            return {"ok": False, "error": f"model-path jail: {exc}"}
    elif model_view:
        try:
            vp = jail_resolve(root, model_view)
            data = json.loads(vp.read_text(encoding="utf-8"))
            rel = (data.get("path_or_handle") or "").strip()
            if rel:
                pkl = jail_resolve(root, rel)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"model-view load failed: {exc}"}
    else:
        # Optional ModelView at default filename
        mv = root / "out" / "views" / "model.json"
        if mv.is_file():
            try:
                data = json.loads(mv.read_text(encoding="utf-8"))
                rel = (data.get("path_or_handle") or "").strip()
                if rel:
                    pkl = jail_resolve(root, rel)
            except Exception:
                pkl = None
        if pkl is None and get_bind_mode() == "caseio":
            from indago_investigate.health_audit.helpers import champion_pkl

            pkl = champion_pkl(version=3)

    if pkl is None or not pkl.is_file():
        return {
            "ok": False,
            "error": "no model — pass --model-path / --model-view, or --importance-path",
            "hints": [
                "Pick a PKL from catalog (e.g. evidence/models/…)",
                "Or pass a precomputed ranks JSON via --importance-path",
            ],
        }

    imp = get_importances(pkl_path=pkl)
    if not imp.get("ok"):
        err = imp.get("error") or "importance extraction failed"
        out: dict[str, Any] = {
            "ok": False,
            "error": err,
            "model_path": str(pkl),
        }
        # Load/env failures are hard investigation signals (not "unsupported method")
        low = str(err).lower()
        if any(
            s in low
            for s in (
                "no module named",
                "modulenotfound",
                "cannot load",
                "failed to load",
                "unpickling",
                "joblib",
                "importerror",
            )
        ):
            out["error_class"] = "model_unloadable"
        if imp.get("unsupported"):
            out["unsupported"] = True
            out["unsupported_reason"] = imp.get("unsupported_reason") or "no_native_importance"
            out["model_family_guess"] = imp.get("model_family_guess")
            out["note"] = imp.get("note") or "Native importances only; permutation is unsupported."
        return out
    ranked = []
    for row in imp.get("ranked") or []:
        name = row.get("feature") or row.get("name")
        if isinstance(name, str):
            for p in ("num__", "cat__"):
                if name.startswith(p):
                    name = name[len(p) :]
                    break
        ranked.append({"feature": name, "importance": float(row.get("importance") or row.get("gain") or 0)})
        if len(ranked) >= k:
            break
    return {
        "ok": True,
        "source": "model",
        "model_path": str(pkl.relative_to(root)).replace("\\", "/") if root in pkl.parents or pkl.is_relative_to(root) else str(pkl),
        "top_k": ranked,
        "method": imp.get("method"),
        "model_family_guess": imp.get("model_family_guess"),
        "caveat": "Tree/split importances bias high-cardinality continuous features; linear uses |coef_|.",
    }


def score_offline(
    *,
    frame: str = "cur",
    version: int = 3,
    model_path: str | None = None,
) -> dict[str, Any]:
    import json
    from pathlib import Path

    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.path_jail import PathJailError, jail_resolve
    from indago_investigate.views_bind import resolve_frame_path

    io = get_case_io()
    root = io.case_root
    try:
        frame_path = resolve_frame_path(root, frame) if get_bind_mode() != "caseio" else None
    except Exception:
        frame_path = None
    if frame_path is None:
        frame_path = io.find_asset({"cur": "cur", "ref_val": "ref_val", "ref_train": "ref_train"}.get(frame, frame))

    pkl: Path | None = None
    if model_path:
        try:
            pkl = jail_resolve(root, model_path)
        except PathJailError as exc:
            return {"ok": False, "error": f"model-path jail: {exc}"}
    else:
        mv = root / "out" / "views" / "model.json"
        if mv.is_file():
            try:
                data = json.loads(mv.read_text(encoding="utf-8"))
                rel = (data.get("path_or_handle") or "").strip()
                if rel:
                    pkl = jail_resolve(root, rel)
            except Exception:
                pkl = None
        if pkl is None and get_bind_mode() == "caseio":
            pkl = io.champion_pkl(version=version)

    if frame_path is None or pkl is None or not Path(pkl).is_file():
        return {
            "ok": False,
            "error": "missing frame or model — author FrameView + ModelView or pass --model-path",
            "frame": frame,
        }
    # Prefer ModelView feature list under views; folklore version map is caseio-only fallback.
    cols: list[str] = []
    mv = root / "out" / "views" / "model.json"
    if mv.is_file():
        try:
            data = json.loads(mv.read_text(encoding="utf-8"))
            ref = (data.get("feature_cols_ref") or "").strip()
            if ref:
                from indago_investigate.path_jail import jail_resolve as _jr

                fp = _jr(root, ref)
                if fp.suffix.lower() == ".json":
                    cols = list(json.loads(fp.read_text(encoding="utf-8")).get("feature_cols") or [])
                else:
                    cols = [ln.strip() for ln in fp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except Exception:
            cols = []
    if not cols and get_bind_mode() == "caseio":
        cols = feature_cols_for_version(version)
    if not cols:
        return {
            "ok": False,
            "error": "no feature_cols under views bind — set ModelView.feature_cols_ref or pass cols via folklore only in caseio",
            "frame": frame,
            "pkl": str(pkl),
            "hints": [
                "Author evidence/.../feature_cols.json and ModelView.feature_cols_ref",
                "Or run with INDAGO_BIND=caseio only for lab ops",
            ],
        }
    # Views path: missing model features are a mismatch signal (not silent NaN fill).
    if get_bind_mode() != "caseio":
        try:
            from indago_investigate.table_io import load_table

            frame_df = load_table(frame_path)
            missing = [c for c in cols if c not in frame_df.columns]
        except Exception as exc:
            return {
                "ok": False,
                "error_class": "model_frame_mismatch",
                "frame": frame,
                "error": f"cannot load frame for feature check: {exc}",
                "pkl": str(pkl),
            }
        if missing:
            return {
                "ok": False,
                "error_class": "model_frame_mismatch",
                "frame": frame,
                "error": f"frame missing feature columns required by model: {missing}",
                "missing_feature_cols": missing,
                "pkl": str(pkl),
                "hints": [
                    "Feature contract vs frame columns may disagree",
                    "Treat failed rescore as evidence the model may not match this window",
                ],
            }
    result = score_parquet(
        feature_cols=cols,
        score_col="offline_score",
        pkl_abs=str(pkl),
        parquet_abs=str(frame_path),
    )
    if not result.get("ok"):
        err = result.get("error") or "score worker failed"
        low = str(err).lower()
        unloadable = any(
            s in low
            for s in (
                "no module named",
                "modulenotfound",
                "cannot load",
                "failed to load",
                "unpickling",
                "importerror",
            )
        )
        return {
            "ok": False,
            "error_class": "model_unloadable" if unloadable else "model_frame_mismatch",
            "frame": frame,
            "error": err,
            "pkl": str(pkl),
            "hints": [
                "Model artifact failed to load — fix PKL/deps before treating scores as measured"
                if unloadable
                else "Scorer/pipeline error — model may be mismatched for this frame",
            ],
        }
    scores = result.get("scores") or result.get("values") or []
    arr = np.array(scores, dtype=float) if scores else np.array([], dtype=float)
    out_path = io.out_dir / "reports" / f"offline_scores_{frame}.json"
    score_list = [float(x) for x in arr]
    out_path.write_text(
        __import__("json").dumps({"frame": frame, "scores": score_list[:5000]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "frame": frame,
        "n": int(len(arr)),
        "mean": float(np.mean(arr)) if len(arr) else None,
        "p95": float(np.quantile(arr, 0.95)) if len(arr) else None,
        "pkl": str(pkl),
        "scores_path": str(out_path),
        "scores": score_list,
        "limitations": [],
    }


def timeline_correlate() -> dict[str, Any]:
    io = get_case_io()
    queue = io.try_load_json("workspace/telemetry/queue_backlog.json") or {}
    infra = io.try_load_json("workspace/telemetry/infra_summary.json") or {}
    alert = io.load_json("alert.json")
    return {
        "alert_fired_at": alert.get("fired_at"),
        "queue": queue,
        "infra": {k: infra.get(k) for k in list(infra)[:40]},
        "note": "Channel-split lag: inference ≠ tile. Correlate manually with alert fire time.",
    }


def lineage_extract() -> dict[str, Any]:
    io = get_case_io()
    alert = io.load_json("alert.json")
    baseline = io.try_load_json("workspace/playground/outputs/monitor_baseline_ieee.json") or {}
    aliases = io.try_load_json("workspace/registry/aliases.json") or {}
    dbt = io.try_load_json("workspace/orchestration/dbt_run_summary.json") or {}
    fc = io.try_load_json("workspace/playground/outputs/ieee_feature_contract.json") or {}
    return {
        "incident_id": alert.get("incident_id"),
        "champion_version": alert.get("champion_version"),
        "git_sha": alert.get("git_sha"),
        "baseline_id": baseline.get("monitoring_baseline"),
        "baseline_rules_hash": baseline.get("rules_bundle_hash"),
        "aliases": aliases.get("aliases"),
        "silver_build_id": dbt.get("silver_build_id"),
        "feature_contract_cols": {
            "n_train": len(fc.get("train_feature_cols") or fc.get("feature_cols") or []),
            "n_serve": len(fc.get("serve_feature_cols") or []),
        },
    }


def dual_ref_null_report(*, top_k: int = 30) -> dict[str, Any]:
    cur = load_frame("cur")
    train = load_frame("ref_train")
    val = load_frame("ref_val")
    cols = [c for c in cur.columns if c in train.columns and c in val.columns]
    rows = []
    for c in cols:
        cn = float(cur[c].isna().mean())
        tn = float(train[c].isna().mean())
        vn = float(val[c].isna().mean())
        if cn - max(tn, vn) < 0.05 and cn < 0.05:
            continue
        rows.append(
            {
                "col": c,
                "cur_null": round(cn, 4),
                "train_null": round(tn, 4),
                "val_null": round(vn, 4),
                "val_aligned_spike": cn > vn + 0.1 and abs(cn - tn) > 0.1,
                "train_only_spike": cn > tn + 0.1 and abs(cn - vn) <= 0.05,
            }
        )
    rows.sort(key=lambda r: -(r["cur_null"] - max(r["train_null"], r["val_null"])))
    return {
        "n_cur": len(cur),
        "n_train": len(train),
        "n_val": len(val),
        "top": rows[:top_k],
        "note": "Train-only null spikes that match val are often sparsity, not ETL breaks.",
    }


def score_tail_report(
    *,
    frame: str = "cur",
    thr: float = 0.85,
    rescore: bool = False,
    model_path: str | None = None,
    score_col_name: str | None = None,
) -> dict[str, Any]:
    from indago_investigate.tools.scores import resolve_scores

    resolved = resolve_scores(
        frame,
        score_col_name=score_col_name,
        rescore=rescore,
        model_path=model_path,
        tool="score-tail",
    )
    if not resolved.get("ok"):
        return resolved
    s = resolved["scores"]
    n = len(s)
    tail = s >= thr
    return {
        "ok": True,
        "frame": frame,
        "n": n,
        "mean": float(s.mean()),
        "median": float(s.median()),
        "p95": float(s.quantile(0.95)),
        "tail_thr": thr,
        "tail_n": int(tail.sum()),
        "tail_rate": round(float(tail.mean()), 4),
        "mean_without_tail": float(s[~tail].mean()) if (~tail).any() else None,
        "score_source": resolved.get("score_source"),
        "score_column": resolved.get("score_column"),
        "model_path": resolved.get("model_path"),
    }


def policy_accountability() -> dict[str, Any]:
    replay = replay_policy()
    df = load_frame("cur")
    s = score_col(df)
    high = s >= 0.85
    high_approve = 0
    if "decision" in df.columns:
        high_approve = int(((df["decision"].astype(str) == "APPROVE") & high).sum())
    return {
        **replay,
        "high_score_APPROVE": high_approve,
        "interpretation": "If replay matches observed and high-score APPROVE≈0, decision plane is healthy.",
    }


def concentration_report(
    *,
    key: str | None = None,
    top_k: int = 10,
    rescore: bool = False,
    model_path: str | None = None,
    score_col_name: str | None = None,
) -> dict[str, Any]:
    if not key:
        return {"ok": False, "error": "key required (pass --key <column>); no default slice column"}
    sl = slice_summary(
        key=key,
        top_k=top_k,
        rescore=rescore,
        model_path=model_path,
        score_col_name=score_col_name,
    )
    if not sl.get("ok"):
        return sl
    top = (sl.get("top_slices") or [{}])[0]
    return {
        **sl,
        "flagged": top.get("share", 0) >= 0.25,
        "primary_slice": top,
    }


def online_vs_batch_velocity() -> dict[str, Any]:
    df = load_frame("cur")
    fc = get_case_io().try_load_json("workspace/playground/outputs/ieee_feature_contract.json") or {}
    vel_cols = [c for c in df.columns if "velocity" in c.lower() or c.startswith("online_")]
    zeros = []
    flag_rates = []
    for c in vel_cols:
        if not pd.api.types.is_numeric_dtype(df[c]):
            continue
        if c == "online_velocity_zero_at_fetch" or c.endswith("_zero_at_fetch"):
            flag_rates.append(
                {
                    "col": c,
                    "true_rate": round(float(df[c].fillna(0).astype(float).mean()), 4),
                    "note": "boolean flag — compare to monitor check zero_rate",
                }
            )
            continue
        z = float((df[c] == 0).mean())
        zeros.append({"col": c, "zero_rate": round(z, 4)})
    zeros.sort(key=lambda x: -x["zero_rate"])
    return {
        "velocity_like_cols": vel_cols[:40],
        "numeric_tile_zero_mass": zeros[:30],
        "zero_mass": zeros[:30],  # backward-compatible alias (numeric tiles only)
        "boolean_flag_rates": flag_rates,
        "feature_contract_online_in_serve": fc.get("online_in_serve_features"),
        "note": (
            "Numeric online_* tiles: high zero_rate ⇒ empty tiles / flush (F2-class). "
            "online_velocity_zero_at_fetch is a boolean flag — use boolean_flag_rates.true_rate, "
            "not zero_mass on that column."
        ),
    }


def baseline_card_diff() -> dict[str, Any]:
    io = get_case_io()
    baseline = io.try_load_json("workspace/playground/outputs/monitor_baseline_ieee.json") or {}
    alert = io.load_json("alert.json")
    cur = load_frame("cur")
    live_hash = str(cur["rules_bundle_hash"].iloc[0]) if "rules_bundle_hash" in cur.columns else None
    return {
        "baseline_id": baseline.get("monitoring_baseline") or alert.get("monitoring_baseline"),
        "pred_mean_val": baseline.get("pred_mean_val"),
        "approval_rate_val": baseline.get("approval_rate_val"),
        "n_val": baseline.get("n_val"),
        "baseline_rules_hash": baseline.get("rules_bundle_hash"),
        "live_rules_hash": live_hash,
        "hash_match": live_hash == baseline.get("rules_bundle_hash") if live_hash else None,
        "registry_version": baseline.get("registry_version"),
        "git_sha": baseline.get("git_sha"),
    }


def request_missing_evidence() -> dict[str, Any]:
    io = get_case_io()
    refs = inventory_evidence(io.case_root)
    missing = [
        {"kind": r.kind.value, "limitations": r.limitations, "tried": r.location}
        for r in refs
        if r.availability != Availability.available
    ]
    return {"case_root": str(io.case_root), "missing_or_limited": missing, "n_available": sum(1 for r in refs if r.availability == Availability.available)}


def validate_judgment() -> dict[str, Any]:
    """Validate out/judgment_struct.json — schema + closed tags; readable critique."""
    from indago_investigate.judgment_validate import critique_judgment_file

    io = get_case_io()
    struct_path = io.out_dir / "judgment_struct.json"
    md_path = io.out_dir / "judgment.md"
    result = critique_judgment_file(struct_path, case_root=io.case_root, md_path=md_path)
    result["case_root"] = str(io.case_root)
    # Persist critique as the primary report body (also written by CLI write_report).
    critique_path = io.out_dir / "reports" / "validate_judgment.md"
    critique_path.parent.mkdir(parents=True, exist_ok=True)
    critique_path.write_text(result["critique"], encoding="utf-8")
    result["critique_path"] = str(critique_path)
    return result


def validate_views(*, views_dir: str | None = None, strict: bool = False) -> dict[str, Any]:
    from pathlib import Path

    from indago_investigate.validate_views import validate_views as _validate

    io = get_case_io()
    vdir = Path(views_dir) if views_dir else None
    result = _validate(io.case_root, views_dir=vdir, strict=strict)
    result["case_root"] = str(io.case_root)
    return result


def peek_frame(*, path: str, head: int = 5) -> dict[str, Any]:
    from indago_investigate.peeks import peek_frame as _peek

    io = get_case_io()
    return {**_peek(io.case_root, path=path, head=head), "case_root": str(io.case_root)}


def peek_json(*, path: str) -> dict[str, Any]:
    from indago_investigate.peeks import peek_json as _peek

    io = get_case_io()
    return {**_peek(io.case_root, path=path), "case_root": str(io.case_root)}


def peek_model(*, path: str) -> dict[str, Any]:
    from indago_investigate.peeks import peek_model as _peek

    io = get_case_io()
    return {**_peek(io.case_root, path=path), "case_root": str(io.case_root)}


def emit_judgment_stub(*, terminal: str | None = None, action: str | None = None) -> dict[str, Any]:
    """Write a scaffold judgment_struct if missing — agent should fill claims."""
    import json

    from indago_investigate.judgment_validate import REPAIR_HINT, validate_judgment_struct

    io = get_case_io()
    struct_path = io.out_dir / "judgment_struct.json"
    md_path = io.out_dir / "judgment.md"

    if struct_path.is_file():
        try:
            existing = json.loads(struct_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "existed": True,
                "path": str(struct_path),
                "schema_errors": [f"invalid JSON: {exc}"],
                "repair_hint": REPAIR_HINT,
                "note": "file exists but is invalid JSON — fix or delete, then re-run emit-judgment / validate-judgment",
            }
        errs = validate_judgment_struct(existing)
        return {
            "ok": not errs,
            "existed": True,
            "path": str(struct_path),
            "schema_errors": errs,
            "repair_hint": REPAIR_HINT if errs else None,
            "note": "already present — not overwritten; run indago-investigate validate-judgment . for full critique",
        }

    struct = {
        "decision": {
            "terminal": terminal or "INSUFFICIENT_EVIDENCE",
            "action_class": action or "monitor_only",
            "inhibitors": [],
        },
        "claims": [],
        "anchors": [],
        "capabilities_used": ["indago-investigate"],
        "unknowns": ["scaffold — replace with evidence-backed claims"],
    }
    errs = validate_judgment_struct(struct)
    struct_path.write_text(json.dumps(struct, indent=2) + "\n", encoding="utf-8")
    if not md_path.is_file():
        md_path.write_text(
            f"# Judgment scaffold\n\nTerminal: `{struct['decision']['terminal']}` · "
            f"Action: `{struct['decision']['action_class']}`\n\n"
            "Fill claims as `{tag, status}` rows from claim_tags.json; do not invent.\n"
            "Elimination tags (model_artifact, policy_rules, …) use "
            "`falsified_as_primary`, not `supported` for “plane green”.\n\n"
            "Before closing: `indago-investigate validate-judgment .`\n",
            encoding="utf-8",
        )
    return {
        "ok": not errs,
        "existed": False,
        "struct": str(struct_path),
        "md": str(md_path),
        "schema_errors": errs,
        "note": "scaffold written — fill claims, then run validate-judgment",
    }
