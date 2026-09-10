"""Eight health-plane builders for F3 orientation audit."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from indago_investigate.health_audit.common import (
    check,
    confidence_for_n,
    ks_statistic,
    plane_result,
    psi,
    score_series,
    wasserstein_1d,
    worst_status,
)
from indago_investigate.health_audit.thresholds import THR, psi_band, psi_status

from indago_investigate.health_audit.helpers import try_load_json  # noqa: E402
from indago_investigate.health_audit.model_scoring import (  # noqa: E402
    feature_cols_for_version,
    score_parquet,
)
from indago_investigate.health_audit.report_fmt import delta_direction, delta_direction_pp  # noqa: E402
from indago_investigate.health_audit.rules_eval import (  # noqa: E402
    decision_rates,
    evaluate_authorize,
    rules_bundle_hash,
)


def _strip_imp(name: str) -> str:
    for p in ("num__", "cat__"):
        if name.startswith(p):
            return name[len(p) :]
    return name


def _top_gain_features(k: int) -> list[tuple[str, float]]:
    """Ranked features for feature-plane scans — agent-authored only.

    Prefer `out/reports/topk_importance.json` from `topk-importance`.
    Do **not** silently load the champion PKL inside health-audit (that hid
    the agent skill of choosing model/importance paths).
    """
    from indago_investigate.health_audit.case_io import get_case_io

    try:
        root = Path(get_case_io().case_root)
    except Exception:
        return []
    report = root / "out" / "reports" / "topk_importance.json"
    if not report.is_file():
        return []
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not data.get("ok"):
        return []
    out: list[tuple[str, float]] = []
    for row in data.get("top_k") or data.get("ranked") or []:
        if not isinstance(row, dict):
            continue
        name = _strip_imp(str(row.get("feature") or ""))
        if not name or name in {x[0] for x in out}:
            continue
        try:
            imp = float(row.get("importance") if row.get("importance") is not None else row.get("gain") or 0.0)
        except (TypeError, ValueError):
            continue
        out.append((name, imp))
        if len(out) >= k:
            break
    return out


def build_alert_digest(ctx: dict[str, Any]) -> dict[str, Any]:
    alert = ctx["alert"]
    baseline = ctx["baseline"]
    failed = alert.get("failed_checks") or []
    metric = alert.get("metric")
    return {
        "incident_id": alert.get("incident_id"),
        "fired_at": alert.get("fired_at"),
        "metric": metric,
        "n_events": alert.get("n_events") or ctx["n_cur"],
        "window": alert.get("window"),
        "failed_checks": [{"id": c.get("id"), "status": c.get("status"), "message": c.get("message")} for c in failed],
        "baseline_id": alert.get("monitoring_baseline") or baseline.get("monitoring_baseline"),
        "pred_mean_val": baseline.get("pred_mean_val"),
        "n_val": baseline.get("n_val"),
        "labels": alert.get("label_state") or (ctx["labels"] or {}).get("label_availability"),
        "champion_version": alert.get("champion_version"),
        "git_sha": alert.get("git_sha"),
    }


def plane_lineage(ctx: dict[str, Any]) -> dict[str, Any]:
    alert = ctx["alert"]
    baseline = ctx["baseline"]
    cur = ctx["cur"]
    aliases = ctx["aliases"]
    dbt = ctx["dbt"]
    checks: list[dict[str, Any]] = []

    champ = (aliases.get("aliases") or {}).get("champion") or {}
    reg_counts = alert.get("registry_version_counts") or {}
    champ_v = champ.get("registry_version") or alert.get("champion_version")
    if not reg_counts and champ_v is None:
        reg_status = "UNKNOWN"
        mix_ok = None
    else:
        mix_ok = len(reg_counts) == 1 and str(champ_v) in {str(k) for k in reg_counts}
        reg_status = "GREEN" if mix_ok else "ALERT"
    checks.append(
        check(
            id="registry_stable",
            meaning="All CUR events use champion registry_version",
            status=reg_status,
            value=reg_counts or None,
            baseline=champ_v,
            gloss_key="offline_parity",
        )
    )

    live_hash = None
    if "rules_bundle_hash" in cur.columns and len(cur):
        live_hash = str(cur["rules_bundle_hash"].iloc[0])
    base_hash = baseline.get("rules_bundle_hash") or alert.get("rules_bundle_hash_baseline")
    hash_ok = live_hash is not None and base_hash is not None and live_hash == base_hash
    checks.append(
        check(
            id="rules_bundle_hash",
            meaning="Live rules fingerprint matches baseline card",
            status="GREEN" if hash_ok else ("ALERT" if live_hash and base_hash else "UNKNOWN"),
            value=live_hash,
            baseline=base_hash,
            gloss_key="rules_bundle_hash",
        )
    )

    git = alert.get("git_sha") or baseline.get("git_sha")
    checks.append(
        check(
            id="git_sha",
            meaning="Code revision recorded on alert/baseline (absent → not assessed)",
            status="UNKNOWN" if git in (None, "unknown", "") else "GREEN",
            value=git,
        )
    )

    feats = list(baseline.get("feature_cols") or baseline.get("train_feature_cols") or [])
    present = [c for c in feats if c in cur.columns]
    overlap = len(present) / len(feats) if feats else 0.0
    checks.append(
        check(
            id="feature_contract_overlap",
            meaning="Baseline feature cols present on CUR",
            status="GREEN" if overlap >= THR["schema_overlap"] else ("UNKNOWN" if not feats else "ALERT"),
            value=round(overlap, 4),
            n={"present": len(present), "expected": len(feats)},
            threshold=THR["schema_overlap"],
            gloss_key="schema_overlap",
        )
    )

    checks.append(
        check(
            id="baseline_card",
            meaning="Monitor baseline card (optional; REF-derived scalars OK)",
            status="GREEN"
            if baseline.get("monitoring_baseline") or baseline.get("_derived_from_ref")
            else "UNKNOWN",
            value=baseline.get("monitoring_baseline")
            or ("derived_from_ref" if baseline.get("_derived_from_ref") else None),
            n=baseline.get("n_val"),
        )
    )
    checks.append(
        check(
            id="silver_build",
            meaning="dbt silver build fingerprint (absent → not assessed)",
            status="GREEN" if dbt.get("silver_build_id") else "UNKNOWN",
            value={"silver_build_id": dbt.get("silver_build_id"), "models_ok": dbt.get("models_ok")},
        )
    )

    st = worst_status([c["status"] for c in checks])
    finding = f"rules_hash live={live_hash} baseline={base_hash}; champion v={champ_v}; schema_overlap={overlap:.3f}"
    return plane_result(
        "lineage",
        st,
        finding=finding,
        anomaly="rules_bundle_hash mismatch" if not hash_ok and live_hash and base_hash else None,
        confidence=confidence_for_n(ctx["n_cur"]),
        checks=checks,
        metrics={"live_hash": live_hash, "baseline_hash": base_hash, "schema_overlap": overlap},
    )


def plane_infra(ctx: dict[str, Any]) -> dict[str, Any]:
    queue = ctx["queue"]
    infra = ctx["infra"]
    snap = ctx["snap"]
    cur = ctx["cur"]
    k8s = ctx["k8s"]
    checks: list[dict[str, Any]] = []

    inf_lag = queue.get("consumer_lag")
    kafka_check = next((c for c in (snap.get("checks") or []) if c.get("id") == "kafka_consumer_lag"), None)
    tile_lag = kafka_check.get("value") if kafka_check else None

    inf_ok = inf_lag is not None and int(inf_lag) <= THR["inference_lag"]
    checks.append(
        check(
            id="inference_lag",
            meaning="Authorize/inference queue consumer lag",
            status="GREEN" if inf_ok else ("ALERT" if inf_lag is not None else "UNKNOWN"),
            value=inf_lag,
            threshold=THR["inference_lag"],
            gloss_key="inference_lag",
        )
    )
    if tile_lag is not None:
        tile_st = "WARN" if int(tile_lag) > THR["tile_lag_warn"] and inf_ok else ("GREEN" if int(tile_lag) <= THR["tile_lag_warn"] else "ALERT")
        if int(tile_lag) > THR["tile_lag_warn"] and inf_ok:
            tile_st = "WARN"
        checks.append(
            check(
                id="tile_kafka_lag",
                meaning="Feature-tile updater Kafka lag (side channel)",
                status=tile_st,
                value=tile_lag,
                threshold=THR["tile_lag_warn"],
                gloss_key="tile_lag",
            )
        )

    p95 = None
    if "latency_ms" in cur.columns and len(cur):
        p95 = float(cur["latency_ms"].astype(float).quantile(0.95))
    infra_p95 = infra.get("serving_latency_p95_ms")
    use_p95 = p95 if p95 is not None else infra_p95
    checks.append(
        check(
            id="latency_p95",
            meaning="Authorize latency p95 (ms)",
            status="GREEN" if use_p95 is not None and float(use_p95) <= THR["latency_p95_ms"] else ("UNKNOWN" if use_p95 is None else "ALERT"),
            value=use_p95,
            baseline=infra_p95,
            threshold=THR["latency_p95_ms"],
            n=ctx["n_cur"],
            gloss_key="latency_p95",
        )
    )

    redis = next((c for c in (snap.get("checks") or []) if c.get("id") == "redis_feature_store_ok"), None)
    if redis:
        checks.append(
            check(
                id="online_store",
                meaning="Online feature store ping / health check",
                status="GREEN" if redis.get("status") == "pass" else "ALERT",
                value=redis.get("message") or redis.get("value"),
            )
        )

    restarts = 0
    if isinstance(k8s, dict):
        events = k8s.get("events") or k8s.get("items") or []
        if isinstance(events, list):
            restarts = sum(1 for e in events if "OOM" in str(e).upper() or "BackOff" in str(e))
    checks.append(
        check(
            id="k8s_noise",
            meaning="K8s OOM/BackOff-like events in pack telemetry",
            status="WARN" if restarts else "GREEN",
            value=restarts,
        )
    )

    st = worst_status([c["status"] for c in checks])
    finding = f"inference_lag={inf_lag}; tile_lag={tile_lag}; latency_p95={use_p95}"
    anomaly = None
    if tile_lag is not None and inf_lag == 0 and int(tile_lag) > THR["tile_lag_warn"]:
        anomaly = "tile lag elevated while inference lag=0 (side channel)"
    return plane_result("infra", st, finding=finding, anomaly=anomaly, confidence=confidence_for_n(ctx["n_cur"]), checks=checks)


def plane_feature(ctx: dict[str, Any]) -> dict[str, Any]:
    cur, train, val = ctx["cur"], ctx["ref_train"], ctx["ref_val"]
    baseline = ctx["baseline"]
    ranked = _top_gain_features(THR["top_k_features"])
    feats = [f for f, _ in ranked]
    checks: list[dict[str, Any]] = []
    gain_map = dict(ranked)
    if not gain_map:
        return plane_result(
            "feature",
            "UNKNOWN",
            finding="no feature importances — run topk-importance then re-audit",
            confidence="LOW",
            missing_roles=[],
            missing_inputs=["out/reports/topk_importance.json"],
            hints=[
                "Run: indago-investigate topk-importance . --model-path <catalog-pkl>",
                "Or --importance-path to a precomputed ranks JSON",
                "Health-audit does not silently load the model for importances",
            ],
        )
    max_gain = max(gain_map.values()) or 1.0

    schema_feats = list(baseline.get("feature_cols") or baseline.get("train_feature_cols") or feats)
    present = [c for c in schema_feats if c in cur.columns]
    overlap = len(present) / len(schema_feats) if schema_feats else 0.0
    checks.append(
        check(
            id="schema_overlap",
            meaning="Monitor/baseline feature cols present on CUR",
            status="GREEN" if overlap >= THR["schema_overlap"] else "ALERT",
            value=round(overlap, 4),
            n={"present": len(present), "expected": len(schema_feats)},
            threshold=THR["schema_overlap"],
            gloss_key="schema_overlap",
        )
    )

    # Full top-K profiles (always recorded — MD shows entire scanned set, not only alerts)
    null_profile: list[dict[str, Any]] = []
    priorities: list[dict[str, Any]] = []
    null_tags: list[dict[str, Any]] = []
    zero_tags: list[dict[str, Any]] = []
    missing_from_cur: list[str] = []

    for rank, col in enumerate(feats, start=1):
        if col not in cur.columns or col not in train.columns:
            missing_from_cur.append(col)
            continue
        g_raw = float(gain_map.get(col, 0.0))
        g_norm = g_raw / max_gain
        nr_c = float(cur[col].isna().mean())
        nr_t = float(train[col].isna().mean())
        nr_v = float(val[col].isna().mean()) if col in val.columns else None
        d_tr = nr_c - nr_t
        d_va = (nr_c - nr_v) if nr_v is not None else None
        tag = "ok"
        if d_tr > THR["null_delta_train"]:
            tag = "null_spike_vs_train"
            if d_va is not None and abs(d_va) <= THR["null_val_align"]:
                tag = "train_spike_val_aligned"
            null_tags.append(col)

        row_null = {
            "rank": rank,
            "feature": col,
            "gain": round(g_raw, 2),
            "gain_norm": round(g_norm, 4),
            "tag": tag,
            "null_cur": round(nr_c, 4),
            "null_train": round(nr_t, 4),
            "null_val": round(nr_v, 4) if nr_v is not None else None,
            "delta_train": round(d_tr, 4),
            "delta_val": round(d_va, 4) if d_va is not None else None,
            "n_null": int(cur[col].isna().sum()),
            "n": ctx["n_cur"],
        }
        null_profile.append(row_null)

        psi_v = None
        gxp = None
        kind = "numeric" if pd.api.types.is_numeric_dtype(cur[col]) else "categorical"
        if kind == "numeric" and col in val.columns:
            p = psi(cur[col].dropna().astype(float).to_numpy(), val[col].dropna().astype(float).to_numpy())
            if p == p:
                psi_v = round(float(p), 4)
                gxp = round(g_norm * float(p), 4)
        priorities.append(
            {
                "rank": rank,
                "feature": col,
                "kind": kind,
                "gain": round(g_raw, 2),
                "gain_norm": round(g_norm, 4),
                "psi": psi_v,
                "psi_band": psi_band(psi_v) if psi_v is not None else None,
                "gain_x_psi": gxp,
            }
        )

        if kind == "numeric":
            zc = float((cur[col].fillna(0) == 0).mean())
            zt = float((train[col].fillna(0) == 0).mean())
            if zt > 0 and zc / zt >= THR["zero_mass_velocity"]:
                zero_tags.append(
                    {
                        "rank": rank,
                        "feature": col,
                        "zero_cur": round(zc, 4),
                        "zero_train": round(zt, 4),
                        "velocity": round(zc / zt, 3),
                        "n_zero": int((cur[col].fillna(0) == 0).sum()),
                        "n": ctx["n_cur"],
                    }
                )

    by_gxp = sorted(priorities, key=lambda r: (r["gain_x_psi"] is None, -(r["gain_x_psi"] or 0)))
    top_gxp = by_gxp[0] if by_gxp else None
    gxp_alert = top_gxp and top_gxp["gain_x_psi"] is not None and top_gxp["gain_x_psi"] >= THR["gain_x_psi_alert"]
    by_psi = sorted(
        [r for r in priorities if r.get("psi") is not None],
        key=lambda r: -(r["psi"] or 0),
    )
    top_psi = by_psi[0] if by_psi else None
    max_psi = (top_psi or {}).get("psi")
    psi_st = psi_status(max_psi)

    n_aligned = sum(1 for r in null_profile if r["tag"] == "train_spike_val_aligned")
    n_spike = sum(1 for r in null_profile if r["tag"] != "ok")
    if n_spike and n_aligned == n_spike:
        null_st = "WARN"
    elif n_spike:
        null_st = "WARN" if n_aligned >= n_spike / 2 else "ALERT"
    else:
        null_st = "GREEN"

    # Compact check values — full tables live in metrics / MD (avoid duplicating blobs)
    checks.append(
        check(
            id="dual_null_top_k",
            meaning=f"Null Δ vs train/val on top-{len(feats)} gain features (see table)",
            status=null_st,
            value={"n_scanned": len(null_profile), "n_spike": n_spike, "n_val_aligned": n_aligned},
            threshold=THR["null_delta_train"],
            gloss_key="train_spike_val_aligned",
        )
    )
    checks.append(
        check(
            id="gain_x_psi_top",
            meaning=f"gain×PSI on top-{len(feats)} gain features vs REF val (see table)",
            status="ALERT" if gxp_alert else "GREEN",
            value={
                "max_feature": (top_gxp or {}).get("feature"),
                "max_gain_x_psi": (top_gxp or {}).get("gain_x_psi"),
                "n_scanned": len(priorities),
            },
            threshold=THR["gain_x_psi_alert"],
            gloss_key="gain_x_psi",
        )
    )
    checks.append(
        check(
            id="psi_max_top_k",
            meaning=(
                f"Max PSI vs REF val on scanned numerics "
                f"(bands: <{THR['psi_stable']} stable, ≤{THR['psi_alert']} watch)"
            ),
            status=psi_st if max_psi is not None else "UNKNOWN",
            value={
                "max_feature": (top_psi or {}).get("feature"),
                "max_psi": max_psi,
                "band": (top_psi or {}).get("psi_band"),
            },
            threshold={"psi_stable": THR["psi_stable"], "psi_alert": THR["psi_alert"]},
            gloss_key="psi",
        )
    )
    checks.append(
        check(
            id="zero_mass_velocity",
            meaning="Zero-rate ≥3× train on numeric top-K cols (see table if any)",
            status="ALERT" if zero_tags else "GREEN",
            value={"n_flagged": len(zero_tags)},
            gloss_key="zero_mass",
        )
    )

    st = worst_status([c["status"] for c in checks])
    finding = (
        f"scanned top-{len(feats)} by tree-gain; "
        f"null_spikes={n_spike}/{len(null_profile)} (val_aligned={n_aligned}); "
        f"max gain×PSI={(top_gxp or {}).get('feature')}={(top_gxp or {}).get('gain_x_psi')}; "
        f"zero_mass={len(zero_tags)}"
    )
    return plane_result(
        "feature",
        st,
        finding=finding,
        anomaly="gain×PSI spike" if gxp_alert else ("null spikes (check val-alignment)" if n_spike else None),
        confidence=confidence_for_n(ctx["n_cur"]),
        checks=checks,
        metrics={
            "scanned_set": feats,
            "scanned_source": "agent topk_importance.json (not silent model load)",
            "null_profile": null_profile,
            "priorities": priorities,
            "priorities_by_gxp": by_gxp,
            "null_tags": null_tags,
            "zero_tags": zero_tags,
            "missing_from_cur": missing_from_cur,
            "detail_note": (
                f"Full top-{len(feats)} gain set below (rank = importance order). "
                f"Null spike thr Δtrain>{THR['null_delta_train']}; "
                f"ALERT gain×PSI≥{THR['gain_x_psi_alert']}. "
                "Monitor may flag more cols outside this set — those are not omitted as 'healthy', they were not scanned here."
            ),
        },
    )


def plane_population(ctx: dict[str, Any]) -> dict[str, Any]:
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.role_cols import role_column

    cur, val = ctx["cur"], ctx["ref_val"]
    n_cur, n_val = ctx["n_cur"], ctx["n_val"]
    checks: list[dict[str, Any]] = []
    root = ctx.get("case_root")
    roles = ctx.get("roles") or {}
    mode = ctx.get("bind_mode") or get_bind_mode()

    # Role-driven categoricals under views; CaseIO may scan IEEE folklore cats
    cats: list[str] = []
    if root is not None:
        for role in ("product", "slice_key"):
            col = role_column(root, role, split="cur")
            if col and col in cur.columns and (n_val == 0 or col in val.columns):
                if col not in cats:
                    cats.append(col)
    if mode == "caseio":
        for c in ("ProductCD", "card1", "addr1", "card4", "card6"):
            if c in cur.columns and c in val.columns and c not in cats:
                cats.append(c)
    if not cats and mode != "caseio":
        return plane_result(
            "population",
            "UNKNOWN",
            finding="no slice_key/product roles bound — path-only Views",
            confidence="LOW",
            missing_roles=["slice_key", "product"],
            missing_inputs=["frame_cur.column_roles.slice_key", "frame_cur.column_roles.product"],
            hints=[
                "Set column_roles.slice_key and/or product on out/views/frame_cur.json",
                "Re-run health-audit after binding",
            ],
        )
    concentrations: list[dict[str, Any]] = []
    scores_cur = ctx.get("scores_cur")
    if scores_cur is None:
        try:
            scores_cur = score_series(cur).to_numpy()
        except KeyError:
            scores_cur = np.zeros(max(n_cur, 1), dtype=float)
    for col in cats:
        if n_val == 0 or col not in val.columns:
            # Path-only / missing REF: still report CUR concentrations without ratio
            vc = cur[col].astype(str).value_counts()
            for level, cnt in vc.head(10).items():
                share = cnt / n_cur
                mask = cur[col].astype(str) == str(level)
                mean_sc = float(np.asarray(scores_cur)[mask.to_numpy()].mean()) if mask.any() else None
                concentrations.append(
                    {
                        "feature": col,
                        "level": level,
                        "cur_n": int(cnt),
                        "cur_share": round(share, 4),
                        "val_n": None,
                        "val_share": None,
                        "ratio": None,
                        "delta_pp": None,
                        "mean_score_cur": round(mean_sc, 4) if mean_sc is not None else None,
                    }
                )
            continue
        vc = cur[col].astype(str).value_counts()
        for level, cnt in vc.head(10).items():
            share = cnt / n_cur
            val_n = int((val[col].astype(str) == level).sum())
            val_share = val_n / n_val if n_val else 0
            ratio = (share / val_share) if val_share > 0 else float("inf")
            mask = cur[col].astype(str) == str(level)
            mean_sc = float(np.asarray(scores_cur)[mask.to_numpy()].mean()) if mask.any() else None
            concentrations.append(
                {
                    "feature": col,
                    "level": level,
                    "cur_n": int(cnt),
                    "cur_share": round(share, 4),
                    "val_n": val_n,
                    "val_share": round(val_share, 4),
                    "ratio": round(ratio, 3) if ratio != float("inf") else None,
                    "delta_pp": round(100 * (share - val_share), 2),
                    "mean_score_cur": round(mean_sc, 4) if mean_sc is not None else None,
                }
            )
    concentrations.sort(key=lambda r: -r["cur_share"])
    flagged = [
        r
        for r in concentrations
        if r["cur_n"] >= THR["min_slice_n"]
        and r["cur_share"] >= THR["concentration_share"]
        and (r["ratio"] is None or r["ratio"] >= THR["concentration_ratio"])
    ]
    # also surface material mix shifts even if below ALERT thr
    mix_shifts = [
        r
        for r in concentrations
        if r["cur_n"] >= THR["min_slice_n"] and abs(r["delta_pp"]) >= THR["delta_pp_show"]
    ][:10]
    checks.append(
        check(
            id="slice_concentration",
            meaning="Entity share in CUR vs REF val (top categoricals)",
            status="ALERT" if flagged else "GREEN",
            value={"top": concentrations[:8], "flagged": flagged[:5]},
            threshold={"share": THR["concentration_share"], "ratio": THR["concentration_ratio"]},
            gloss_key="slice_concentration",
        )
    )

    clusters: list[dict[str, Any]] = []
    product_col = role_column(root, "product", split="cur") if root is not None else None
    slice_col = role_column(root, "slice_key", split="cur") if root is not None else None
    amount_col = role_column(root, "amount", split="cur") if root is not None else None
    if mode == "caseio":
        product_col = product_col or ("ProductCD" if "ProductCD" in cur.columns else None)
        slice_col = slice_col or ("card1" if "card1" in cur.columns else None)
        amount_col = amount_col or ("TransactionAmt" if "TransactionAmt" in cur.columns else None)
    if product_col and slice_col and amount_col and {product_col, slice_col, amount_col}.issubset(cur.columns):
        key = (
            cur[product_col].astype(str)
            + "|"
            + cur[slice_col].astype(str)
            + "|"
            + cur[amount_col].astype(float).round(2).astype(str)
        )
        for kv, cnt in key.value_counts().items():
            if cnt < 2:
                continue
            mask = key == kv
            sc = np.asarray(scores_cur)[mask.to_numpy()]
            clusters.append(
                {
                    "key": kv,
                    "n": int(cnt),
                    "mean_score": round(float(sc.mean()), 4),
                    "txns": cur.loc[mask, "transaction_id"].astype(str).head(6).tolist() if "transaction_id" in cur.columns else [],
                }
            )
        clusters.sort(key=lambda r: (-r["n"], -(r["mean_score"] or 0)))
    checks.append(
        check(
            id="combinatorial_clusters",
            meaning="Repeated product|slice_key|amount keys (n≥2)",
            status="WARN" if any(c["n"] >= 3 and (c["mean_score"] or 0) >= 0.5 for c in clusters) else "GREEN",
            value=clusters[:10],
            gloss_key="cluster_key",
        )
    )

    # Binned slice discovery on important features
    from indago_investigate.health_audit.slices import discover_slices

    feats = [f for f, _ in _top_gain_features(THR["slice_top_features"])]
    scores_ref = ctx.get("scores_val")
    slice_disc: dict[str, Any] = {"error": "REF val scores unavailable"}
    if scores_ref is not None:
        metric_name = "score"
        metric_cur = None
        metric_ref = None
        # Prefer label metric when present on both CUR and REF
        for lab in ("isFraud", "label", "y"):
            if lab in cur.columns and lab in val.columns:
                metric_name = lab
                metric_cur = pd.to_numeric(cur[lab], errors="coerce").to_numpy(dtype=float)
                metric_ref = pd.to_numeric(val[lab], errors="coerce").to_numpy(dtype=float)
                break
        slice_disc = discover_slices(
            cur=cur,
            ref=val,
            scores_cur=np.asarray(scores_cur, dtype=float),
            scores_ref=np.asarray(scores_ref, dtype=float),
            features=feats,
            metric_cur=metric_cur,
            metric_ref=metric_ref,
            metric_name=metric_name,
        )
        top_rest = (slice_disc.get("top_by_vs_rest") or [])[:3]
        top_ref = (slice_disc.get("top_by_vs_ref") or [])[:3]
        checks.append(
            check(
                id="binned_slice_discovery",
                meaning="Important-feature bins ranked by n×|Δscore| (vs rest and vs REF bin)",
                status="WARN"
                if (top_rest and top_rest[0]["priority_vs_rest"] >= 0.5)
                or (top_ref and (top_ref[0].get("priority_vs_ref") or 0) >= 0.5)
                else "GREEN",
                value={
                    "top_vs_rest": top_rest,
                    "top_vs_ref": top_ref,
                    "n_evaluated": slice_disc.get("n_slices_evaluated"),
                },
                gloss_key="slice_priority",
            )
        )

    st = worst_status([c["status"] for c in checks])
    top = flagged[0] if flagged else (concentrations[0] if concentrations else None)
    finding = (
        f"flagged_slices={len(flagged)}; mix_shifts≥{THR['delta_pp_show']}pp={len(mix_shifts)}; "
        f"clusters_n≥2={len(clusters)}; binned_slices={slice_disc.get('n_slices_evaluated')}"
    )
    return plane_result(
        "population",
        st,
        finding=finding,
        anomaly=str(top) if flagged else None,
        confidence=confidence_for_n(n_cur),
        checks=checks,
        metrics={
            "concentrations": concentrations[:20],
            "mix_shifts": mix_shifts,
            "clusters": clusters[:15],
            "slice_discovery": slice_disc,
            "detail_note": (
                "Show mix shifts with |Δpp|≥threshold, repeat clusters, and top binned slices "
                "(priority = n×|Δscore| vs rest and vs same REF bin)."
            ),
        },
    )


def attach_offline_scores(ctx: dict[str, Any]) -> None:
    """Score CUR + REF val once; reuse for model plane and slice discovery."""
    if ctx.get("scores_cur") is not None and ctx.get("scores_val") is not None:
        return
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.path_jail import jail_resolve

    root = ctx.get("case_root")
    frame_paths = ctx.get("frame_paths") or {}
    mode = get_bind_mode()

    cols: list[str] = []
    pkl_abs = None
    mv: dict[str, Any] | None = None
    if root is not None:
        p = Path(root) / "out" / "views" / "model.json"
        if p.is_file():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                mv = raw if isinstance(raw, dict) else None
            except (OSError, json.JSONDecodeError):
                mv = None
        if isinstance(mv, dict) and mv.get("path_or_handle"):
            try:
                pkl_abs = jail_resolve(Path(root), str(mv["path_or_handle"]))
            except Exception:
                pkl_abs = None
        if isinstance(mv, dict):
            ref = (mv.get("feature_cols_ref") or "").strip()
            if ref:
                try:
                    fp = jail_resolve(Path(root), ref)
                    if fp.suffix.lower() == ".json":
                        cols = list(json.loads(fp.read_text(encoding="utf-8")).get("feature_cols") or [])
                    else:
                        cols = [
                            ln.strip()
                            for ln in fp.read_text(encoding="utf-8").splitlines()
                            if ln.strip()
                        ]
                except Exception:
                    cols = []
    if not cols and mode == "caseio":
        cols = feature_cols_for_version(3)

    def _abs_frame(rel: str | None) -> Path | None:
        if not rel or root is None:
            return None
        cand = Path(rel)
        if cand.is_file():
            return cand
        return Path(root) / rel

    if pkl_abs is not None and pkl_abs.is_file() and cols and frame_paths.get("cur"):
        cur_path = _abs_frame(frame_paths.get("cur"))
        cur_sc = score_parquet(
            pkl_rel="",
            parquet_rel="",
            feature_cols=cols,
            pkl_abs=str(pkl_abs),
            parquet_abs=str(cur_path) if cur_path else None,
        )
        val_sc = {"ok": False, "error": "no ref_val path"}
        if frame_paths.get("ref_val"):
            val_path = _abs_frame(frame_paths.get("ref_val"))
            if val_path and val_path.is_file():
                val_sc = score_parquet(
                    pkl_rel="",
                    parquet_rel="",
                    feature_cols=cols,
                    pkl_abs=str(pkl_abs),
                    parquet_abs=str(val_path),
                )
    elif mode == "caseio":
        cols = cols or feature_cols_for_version(3)
        pkl = "ieee/models/ieee_champion_v3.pkl"
        cur_sc = score_parquet(
            pkl_rel=pkl, parquet_rel="workspace/lake/events_sample.parquet", feature_cols=cols
        )
        val_sc = score_parquet(
            pkl_rel=pkl,
            parquet_rel="evidence/ref/ieee/reference/val_sample_20k.parquet",
            feature_cols=cols,
        )
    else:
        cur_sc = {
            "ok": False,
            "error": (
                "no ModelView path_or_handle/feature_cols — author out/views/model.json "
                "or bind score column on the frame"
            ),
        }
        val_sc = cur_sc
    ctx["offline_cur"] = cur_sc
    ctx["offline_val"] = val_sc
    if cur_sc.get("ok"):
        ctx["scores_cur"] = np.array(cur_sc["scores"], dtype=float)
    if val_sc.get("ok"):
        ctx["scores_val"] = np.array(val_sc["scores"], dtype=float)


def plane_model(ctx: dict[str, Any]) -> dict[str, Any]:
    cur, val, train = ctx["cur"], ctx["ref_val"], ctx["ref_train"]
    baseline = ctx["baseline"]
    n_cur = ctx["n_cur"]
    checks: list[dict[str, Any]] = []
    attach_offline_scores(ctx)
    cur_sc = ctx.get("offline_cur") or {}
    if not cur_sc.get("ok"):
        # Prefer live score column from roles when offline ModelView scoring unavailable
        try:
            live = score_series(cur)
            ctx["scores_cur"] = live.to_numpy(dtype=float)
            cur_sc = {"ok": True, "source": "frame_score_role"}
            ctx["offline_cur"] = cur_sc
            try:
                ctx["scores_val"] = score_series(val).to_numpy(dtype=float)
            except Exception:
                ctx["scores_val"] = None
        except KeyError:
            return plane_result(
                "model",
                "UNKNOWN",
                finding=f"score failed: {cur_sc.get('error')}",
                confidence="LOW",
                missing_roles=["score"],
                missing_inputs=["frame_cur.score_column", "model.path_or_handle"],
                hints=[
                    "Set score_column or column_roles.score on frame_cur View",
                    "Author model View path if offline scorer needed",
                    "Optional: peek-model when artifact exists",
                ],
            )

    cur_s = np.asarray(ctx["scores_cur"], dtype=float)
    val_s = np.asarray(ctx.get("scores_val") if ctx.get("scores_val") is not None else [], dtype=float)
    thr = THR["tail_score"]
    mu = float(cur_s.mean())
    med = float(np.median(cur_s))
    # Missing score baseline → UNKNOWN (never invent baseline=0 and ALERT).
    pred_base = baseline.get("pred_mean_val")
    if pred_base is not None:
        mu_base: float | None = float(pred_base)
    elif len(val_s):
        mu_base = float(val_s.mean())
    else:
        mu_base = None
    d_mu = (mu - mu_base) if mu_base is not None else None
    n_hi = int((cur_s >= thr).sum())
    n_lo = int((cur_s < 0.20).sum())
    rest = cur_s[cur_s < thr]
    mu_wo = float(rest.mean()) if len(rest) else None

    if mu_base is None or d_mu is None:
        checks.append(
            check(
                id="pred_mean_vs_baseline",
                meaning="CUR mean score vs baseline card / REF val mean",
                status="UNKNOWN",
                value=round(mu, 6),
                baseline=None,
                delta=None,
                n=n_cur,
                threshold=THR["pred_mean_abs"],
                gloss_key="score_mean",
            )
        )
    else:
        checks.append(
            check(
                id="pred_mean_vs_baseline",
                meaning="CUR mean score vs baseline card / REF val mean",
                status="ALERT" if abs(d_mu) > THR["pred_mean_abs"] else "GREEN",
                value=round(mu, 6),
                baseline=mu_base,
                delta=round(d_mu, 6),
                delta_direction=delta_direction(delta=d_mu, cur_label="CUR mean", ref_label="baseline/val mean"),
                n=n_cur,
                threshold=THR["pred_mean_abs"],
                gloss_key="score_mean",
            )
        )
    checks.append(
        check(
            id="score_median",
            meaning="CUR median score (typical row)",
            status="GREEN",
            value=round(med, 6),
            n=n_cur,
            gloss_key="score_median",
        )
    )

    cur_hi_rate = n_hi / n_cur if n_cur else 0.0
    if len(val_s):
        val_hi_rate = float((val_s >= thr).mean())
        d_pp = 100 * (cur_hi_rate - val_hi_rate)
        tail_st = "ALERT" if abs(d_pp) >= THR["tail_rate_delta_pp"] and n_hi >= 3 else "GREEN"
        checks.append(
            check(
                id="tail_mass",
                meaning=f"Share of scores ≥{thr} vs REF val",
                status=tail_st,
                value={"pct": round(100 * cur_hi_rate, 2), "n_hi": n_hi, "n": n_cur},
                baseline={"pct": round(100 * val_hi_rate, 2), "n_val": len(val_s)},
                delta=round(d_pp, 2),
                delta_direction=delta_direction_pp(d_pp),
                gloss_key="score_tail_mass",
            )
        )
    else:
        d_pp = None
        checks.append(
            check(
                id="tail_mass",
                meaning=f"Share of scores ≥{thr} vs REF val",
                status="UNKNOWN",
                value={"pct": round(100 * cur_hi_rate, 2), "n_hi": n_hi, "n": n_cur},
                baseline=None,
                delta=None,
                gloss_key="score_tail_mass",
            )
        )
    checks.append(
        check(
            id="counterfactual_mean_without_tail",
            meaning="Mean score after removing rows with score≥tail thr",
            status="GREEN",
            value=round(mu_wo, 6) if mu_wo is not None else None,
            n=int(len(rest)),
            gloss_key="counterfactual_mean",
        )
    )

    parity = cur_sc.get("max_abs_diff")
    checks.append(
        check(
            id="offline_parity",
            meaning="max |live prediction − offline v3 recompute|",
            status="GREEN" if parity is not None and parity <= THR["parity_abs"] else ("WARN" if parity is None else "ALERT"),
            value=parity,
            threshold=THR["parity_abs"],
            n=n_cur,
            gloss_key="offline_parity",
        )
    )

    ks = ks_statistic(cur_s, val_s) if len(val_s) else float("nan")
    w1 = wasserstein_1d(cur_s, val_s) if len(val_s) else float("nan")
    # Small-n: report but only ALERT if extreme
    ks_st = "UNKNOWN" if ks != ks else ("ALERT" if ks >= THR["ks_alert"] and n_cur >= 100 else ("WARN" if ks >= THR["ks_alert"] else "GREEN"))
    w1_st = "UNKNOWN" if w1 != w1 else ("ALERT" if w1 >= THR["w1_alert"] and n_cur >= 100 else ("WARN" if w1 >= THR["w1_alert"] else "GREEN"))
    checks.append(check(id="ks_vs_val", meaning="KS D between CUR and REF val score ECDFs", status=ks_st, value=None if ks != ks else round(ks, 4), threshold=THR["ks_alert"], gloss_key="ks_d"))
    checks.append(check(id="wasserstein_vs_val", meaning="Approx W1 between CUR and REF val scores", status=w1_st, value=None if w1 != w1 else round(w1, 4), threshold=THR["w1_alert"], gloss_key="wasserstein_1"))

    st = worst_status([c["status"] for c in checks])
    base_s = f"{mu_base:.4f}" if mu_base is not None else "absent"
    finding = f"μ={mu:.4f} (base {base_s}); median={med:.4f}; tail≥{thr}: {n_hi}/{n_cur}; μ_without_tail={mu_wo}; parity={parity}"
    mean_shift = d_mu is not None and abs(d_mu) > THR["pred_mean_abs"]
    tail_shift = d_pp is not None and abs(d_pp) >= THR["tail_rate_delta_pp"]
    return plane_result(
        "model",
        st,
        finding=finding,
        anomaly="score mean/tail shift" if mean_shift or tail_shift else None,
        confidence=confidence_for_n(n_cur),
        checks=checks,
        metrics={
            "cur_scores": cur_s.tolist(),
            "val_scores_summary": {"n": len(val_s), "mean": float(val_s.mean()) if len(val_s) else None},
            "n_hi": n_hi,
            "n_lo": n_lo,
            "mu_without_tail": mu_wo,
        },
    )


def plane_decision(ctx: dict[str, Any]) -> dict[str, Any]:
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.role_cols import role_column

    cur = ctx["cur"]
    baseline = ctx["baseline"]
    n = ctx["n_cur"]
    checks: list[dict[str, Any]] = []
    root = ctx.get("case_root")
    mode = ctx.get("bind_mode") or get_bind_mode()
    decision_col = role_column(root, "decision", split="cur") if root is not None else None
    if mode == "caseio" and not decision_col:
        decision_col = "decision" if "decision" in cur.columns else None
    if not decision_col or decision_col not in cur.columns:
        return plane_result(
            "decision",
            "UNKNOWN",
            finding="no decision column (role decision unbound)",
            confidence="LOW",
            missing_roles=["decision"],
            missing_inputs=["frame_cur.column_roles.decision"],
            hints=[
                "Set column_roles.decision in out/views/frame_cur.json",
                "Optional: peek-frame to find approve/decline column",
            ],
        )

    observed = cur[decision_col].astype(str).tolist()
    try:
        scores = score_series(cur)
    except KeyError:
        return plane_result(
            "decision",
            "UNKNOWN",
            finding="decision column bound but no score for policy replay",
            confidence="LOW",
            missing_roles=["score"],
            missing_inputs=["frame_cur.column_roles.score"],
            hints=["Bind score role to replay rules against fixed scores"],
        )

    from indago_investigate.rules_resolve import resolve_rules_for_replay

    case_root = Path(root) if root is not None else Path(".")
    bundles = resolve_rules_for_replay(case_root)
    default_hit = bundles.get("ref_default")
    alt_hit = bundles.get("alternate")  # ref_loose or live
    if not default_hit and not alt_hit:
        obs_counts = dict(Counter(observed))
        return plane_result(
            "decision",
            "UNKNOWN",
            finding=f"rules YAML unavailable for replay; observed={obs_counts}",
            confidence=confidence_for_n(n),
            missing_inputs=["rules path (RulesView / evidence rules YAML)"],
            hints=[
                "Author RulesView path_or_handle to INDAGO-dialect YAML (often out/derived/…)",
                "Or place REF default under evidence/ref/rules/rules_default.yaml",
                "Observed decision mix is available once rules are present for replay",
            ],
            metrics={"observed_rates": decision_rates(observed)},
        )

    rules_default = (default_hit or alt_hit)["rules"]
    rules_alt = (alt_hit or default_hit)["rules"]
    default_path = (default_hit or alt_hit)["path"]
    alt_path = (alt_hit or default_hit)["path"]
    alt_source = (alt_hit or default_hit)["source"]

    def _replay(rules: dict) -> list[str]:
        out = []
        for i, sc in enumerate(scores):
            row = cur.iloc[i]
            ctx_r = {"vip": bool(row.get("vip", False)), "ofac_hit": bool(row.get("ofac_hit", False))}
            d, _, _ = evaluate_authorize(float(sc), context=ctx_r, rules=rules)
            out.append(d)
        return out

    def_dec = _replay(rules_default)
    alt_dec = _replay(rules_alt)
    obs_counts = dict(Counter(observed))
    match_alt = observed == alt_dec
    match_def = observed == def_dec

    live_hash = str(cur["rules_bundle_hash"].iloc[0]) if "rules_bundle_hash" in cur.columns else None
    base_hash = baseline.get("rules_bundle_hash")
    alt_hash = rules_bundle_hash(rules_alt)
    def_hash = rules_bundle_hash(rules_default)

    checks.append(
        check(
            id="decision_funnel",
            meaning="Observed APPROVE/DECLINE/REVIEW counts",
            status="GREEN",
            value=obs_counts,
            n=n,
        )
    )
    checks.append(
        check(
            id="policy_replay_loose",
            meaning=f"Observed decisions match {alt_source} rules on fixed scores",
            status="GREEN" if match_alt else "WARN",
            value={
                "match": match_alt,
                "alt_hash": alt_hash,
                "alt_source": alt_source,
                "alt_path": alt_path,
                "live_hash": live_hash,
            },
            gloss_key="policy_replay",
        )
    )
    checks.append(
        check(
            id="policy_replay_default",
            meaning="Observed decisions match default REF rules on fixed scores",
            status="GREEN" if match_def else ("ALERT" if live_hash != base_hash else "WARN"),
            value={
                "match": match_def,
                "default_hash": def_hash,
                "default_path": default_path,
                "rates_default": decision_rates(def_dec),
            },
            gloss_key="policy_replay",
        )
    )

    # conflict: score >= 0.85 but APPROVE
    n_conflict = sum(1 for sc, d in zip(scores, observed) if float(sc) >= THR["tail_score"] and d == "APPROVE")
    checks.append(
        check(
            id="high_score_approve_conflict",
            meaning="Rows with score≥0.85 decided APPROVE",
            status="WARN" if n_conflict else "GREEN",
            value={"n": n_conflict, "n_total": n},
            gloss_key="decision_conflict",
        )
    )

    # proximity to 0.20 / 0.85 / 0.99
    cutoffs = [0.20, 0.85, 0.99]
    near = sum(1 for sc in scores if any(abs(float(sc) - c) <= THR["threshold_proximity"] for c in cutoffs))
    checks.append(
        check(
            id="threshold_proximity",
            meaning="Share of scores within ±ε of common policy cutoffs",
            status="WARN" if near / n >= 0.15 else "GREEN",
            value={"n_near": near, "pct": round(100 * near / n, 2)},
            threshold=THR["threshold_proximity"],
        )
    )

    hash_mismatch = live_hash and base_hash and live_hash != base_hash
    st = "ALERT" if hash_mismatch else worst_status([c["status"] for c in checks])
    finding = (
        f"obs={obs_counts}; match_{alt_source}={match_alt}; match_default={match_def}; "
        f"high_score_APPROVE={n_conflict}"
    )
    return plane_result(
        "decision",
        st,
        finding=finding,
        anomaly="rules hash ≠ baseline" if hash_mismatch else None,
        confidence=confidence_for_n(n),
        checks=checks,
        metrics={
            "observed_rates": decision_rates(observed),
            "default_replay_rates": decision_rates(def_dec),
            "rules_via": {
                "default": (default_hit or {}).get("via"),
                "alternate": (alt_hit or {}).get("via"),
            },
        },
    )


def plane_business(ctx: dict[str, Any]) -> dict[str, Any]:
    from indago_investigate.bind_mode import get_bind_mode
    from indago_investigate.role_cols import role_column

    cur = ctx["cur"]
    labels = ctx["labels"]
    n = ctx["n_cur"]
    checks: list[dict[str, Any]] = []
    label_state = ctx["alert"].get("label_state") or labels.get("label_availability")
    root = ctx.get("case_root")
    mode = ctx.get("bind_mode") or get_bind_mode()
    amount_col = role_column(root, "amount", split="cur") if root is not None else None
    if mode == "caseio" and not amount_col:
        amount_col = "TransactionAmt" if "TransactionAmt" in cur.columns else None
    if not amount_col or amount_col not in cur.columns:
        return plane_result(
            "business",
            "UNKNOWN",
            finding="no amount column on CUR (role amount unbound)",
            confidence="LOW",
            missing_roles=["amount"],
            missing_inputs=["frame_cur.column_roles.amount"],
            hints=[
                "Set column_roles.amount in out/views/frame_cur.json",
                "Or ensure an amount-like column on the CUR frame",
                "Optional: peek-frame on CUR path",
            ],
        )

    amt = cur[amount_col].astype(float)
    total = float(amt.sum())
    amt_vc = amt.round(2).value_counts()
    top_amt = [{"amount": float(a), "n": int(c)} for a, c in amt_vc.head(8).items()]
    checks.append(
        check(
            id="gross_exposure",
            meaning=f"Sum {amount_col} over CUR window",
            status="GREEN",
            value=round(total, 2),
            n=n,
            gloss_key="exposure_usd",
        )
    )
    checks.append(
        check(
            id="repetitive_amounts",
            meaning="Most common exact amounts in window",
            status="WARN" if any(x["n"] >= 5 for x in top_amt) else "GREEN",
            value=top_amt,
        )
    )
    checks.append(
        check(
            id="labels_for_impact",
            meaning="Outcome labels available for live supervised impact",
            status="UNKNOWN" if label_state in (None, "absent") else "GREEN",
            value=label_state,
        )
    )

    # I_sev components — top entity share via slice_key role (or CaseIO folklore)
    share = 0.0
    slice_col = role_column(root, "slice_key", split="cur") if root is not None else None
    if mode == "caseio" and not slice_col:
        slice_col = "card1" if "card1" in cur.columns else None
    if slice_col and slice_col in cur.columns:
        share = float(cur[slice_col].astype(str).value_counts().iloc[0] / n)
    try:
        scores = score_series(cur)
    except KeyError:
        scores = pd.Series([0.0] * n)
    tail_rate = float((scores >= THR["tail_score"]).mean())
    components = {
        "traffic_share_top_entity": round(share, 4),
        "gross_usd": round(total, 2),
        "tail_rate": round(tail_rate, 4),
        "labels": label_state,
        "note": "I_sev components only — impact UNKNOWN without labels",
    }
    checks.append(check(id="i_sev_components", meaning="Severity components (share × $ × tail); not a single score", status="UNKNOWN" if label_state == "absent" else "WARN", value=components, gloss_key="exposure_usd"))

    st = "UNKNOWN" if label_state == "absent" else worst_status([c["status"] for c in checks])
    return plane_result(
        "business",
        st,
        finding=f"gross=${total:.2f}; top_amounts={top_amt[:3]}; labels={label_state}",
        anomaly=None,
        confidence="LOW" if label_state == "absent" else confidence_for_n(n),
        checks=checks,
        metrics=components,
        missing_roles=["(labels)"] if label_state == "absent" else None,
        missing_inputs=["labels.state=ready"] if label_state == "absent" else None,
        hints=(
            [
                "Business impact stays UNKNOWN until outcome labels exist",
                "Use gross_exposure / repetitive_amounts as orientation only",
            ]
            if label_state == "absent"
            else None
        ),
    )


def plane_macro(planes: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    st = {k: planes[k]["status"] for k in planes}
    inhibitors: list[str] = []
    hypotheses: list[dict[str, Any]] = []

    if st.get("model") in ("GREEN", "WARN") and st.get("feature") in ("GREEN", "WARN"):
        inhibitors.append("no_model_rollback_as_primary")
        inhibitors.append("no_silver_rebuild_as_primary")
    # Population concentration can mark Feature ALERT via gain×PSI on the same axis
    # (e.g. card1). Model GREEN still forbids rollback / silver rebuild as primary.
    if st.get("model") == "GREEN" and st.get("population") == "ALERT":
        inhibitors.append("no_model_rollback_as_primary")
        inhibitors.append("no_silver_rebuild_as_primary")
    if st.get("lineage") in ("GREEN", "WARN") and st.get("decision") == "GREEN":
        inhibitors.append("no_rules_bundle_change_as_primary")
    if st.get("infra") == "WARN" and "side channel" in str(planes.get("infra", {}).get("anomaly") or ""):
        inhibitors.append("no_serving_outage_primary_from_tile_lag_alone")
    # de-dupe preserve order
    inhibitors = list(dict.fromkeys(inhibitors))

    # composite — prefer real population/slice ALERT over lineage noise when both fire
    if st.get("model") == "ALERT" and st.get("lineage") == "ALERT":
        composite = "SCORE_AND_POLICY"
    elif st.get("population") == "ALERT" and st.get("model") in ("GREEN", "WARN", "UNKNOWN"):
        composite = "LOCALIZED_POPULATION"
    elif st.get("lineage") == "ALERT" and st.get("model") in ("GREEN", "WARN"):
        composite = "POLICY_DRIFT"
    elif st.get("model") == "ALERT":
        composite = "SCORE_TAIL_OR_DISTRIBUTION"
    elif st.get("feature") == "ALERT" and st.get("model") != "ALERT":
        composite = "FEATURE_PLANE"
    elif st.get("infra") == "ALERT":
        composite = "SYSTEMIC_INFRA"
    elif sum(1 for v in st.values() if v == "UNKNOWN") >= 3:
        composite = "INCONCLUSIVE"
    else:
        composite = "MIXED_WARN" if "ALERT" not in st.values() and "WARN" in st.values() else "STABLE"

    if planes.get("lineage", {}).get("anomaly"):
        hypotheses.append({"id": "H_policy", "plane": "lineage/decision", "one_line": planes["lineage"]["anomaly"], "confidence": planes["lineage"]["confidence"]})
    if planes.get("model", {}).get("anomaly"):
        hypotheses.append({"id": "H_scores", "plane": "model", "one_line": planes["model"]["anomaly"], "confidence": planes["model"]["confidence"]})
    if planes.get("population", {}).get("anomaly"):
        hypotheses.append({"id": "H_population", "plane": "population", "one_line": str(planes["population"]["anomaly"])[:200], "confidence": planes["population"]["confidence"]})
    if planes.get("feature", {}).get("anomaly"):
        hypotheses.append({"id": "H_features", "plane": "feature", "one_line": planes["feature"]["anomaly"], "confidence": planes["feature"]["confidence"]})
    if planes.get("infra", {}).get("anomaly"):
        hypotheses.append({"id": "H_infra", "plane": "infra", "one_line": planes["infra"]["anomaly"], "confidence": planes["infra"]["confidence"]})

    checks = [
        check(id="composite_status", meaning="Deterministic posture from plane vector", status="ALERT" if "ALERT" in st.values() else "WARN" if "WARN" in st.values() else "GREEN", value=composite, gloss_key="composite"),
        check(id="inhibitors", meaning="Global conclusions forbidden by green planes", status="GREEN", value=inhibitors, gloss_key="inhibitor"),
    ]
    finding = f"composite={composite}; inhibitors={inhibitors}; open_hypotheses={len(hypotheses)}"
    return plane_result(
        "macro",
        "ALERT" if "ALERT" in st.values() else worst_status(list(st.values())),
        finding=finding,
        anomaly=composite,
        confidence=confidence_for_n(ctx["n_cur"]),
        checks=checks,
        metrics={"plane_statuses": st, "inhibitors": inhibitors, "hypotheses": hypotheses[:5], "composite": composite},
    )


def build_all_planes(ctx: dict[str, Any]) -> dict[str, Any]:
    attach_offline_scores(ctx)
    planes = {
        "lineage": plane_lineage(ctx),
        "infra": plane_infra(ctx),
        "feature": plane_feature(ctx),
        "population": plane_population(ctx),
        "model": plane_model(ctx),
        "decision": plane_decision(ctx),
        "business": plane_business(ctx),
    }
    planes["macro"] = plane_macro(planes, ctx)
    return planes
