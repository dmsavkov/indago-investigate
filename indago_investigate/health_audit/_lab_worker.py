"""Subprocess worker: PKL importances + batch scoring. Run from production-ml-lab cwd."""

from __future__ import annotations

import json
import sys

import joblib
import numpy as np
import pandas as pd

from indago_investigate.model_io import load_model_artifact


def _unwrap_estimator(model):
    pipe = model.base_estimator if hasattr(model, "base_estimator") else model
    if hasattr(pipe, "named_steps"):
        for key in ("clf", "classifier", "model", "estimator"):
            if key in pipe.named_steps:
                return pipe, pipe.named_steps[key]
        # last step often the estimator
        steps = list(pipe.named_steps.values())
        return pipe, steps[-1] if steps else pipe
    return pipe, pipe


def _feature_names(pipe, n: int) -> list[str]:
    ct = pipe.named_steps.get("ct") if hasattr(pipe, "named_steps") else None
    if ct is not None and hasattr(ct, "get_feature_names_out"):
        try:
            return list(ct.get_feature_names_out())
        except Exception:
            pass
    return [f"f{i}" for i in range(n)]


def _coef_importances(clf) -> list[float] | None:
    if not hasattr(clf, "coef_"):
        return None
    coef = np.asarray(clf.coef_)
    if coef.ndim == 1:
        return [float(x) for x in np.abs(coef)]
    # multiclass / multioutput: mean abs across rows
    return [float(x) for x in np.mean(np.abs(coef), axis=0)]


def _nb_importances(clf) -> list[float] | None:
    if not hasattr(clf, "feature_log_prob_"):
        return None
    flp = np.asarray(clf.feature_log_prob_)
    if flp.ndim != 2 or flp.shape[0] < 2:
        return None
    # |log-odds| proxy between class 0 and 1 (or max pairwise span)
    if flp.shape[0] == 2:
        diff = np.abs(flp[1] - flp[0])
    else:
        diff = np.max(flp, axis=0) - np.min(flp, axis=0)
    return [float(x) for x in diff]


def _extract_importances(model) -> dict:
    """Native importances only — no permutation.

    Returns ok payload fields or unsupported reason.
    """
    pipe, clf = _unwrap_estimator(model)
    family = type(clf).__name__ if clf is not None else type(model).__name__

    # Unfitted / empty
    if clf is not None and hasattr(clf, "n_features_in_") is False and not hasattr(
        clf, "feature_importances_"
    ):
        # still try attributes below
        pass

    if clf is not None and hasattr(clf, "feature_importances_"):
        try:
            imp = list(clf.feature_importances_)
            if len(imp) == 0:
                return {
                    "ok": False,
                    "unsupported": True,
                    "unsupported_reason": "unfitted",
                    "model_family_guess": family,
                }
            names = _feature_names(pipe, len(imp))
            return {
                "ok": True,
                "method": "feature_importances_",
                "model_family_guess": family,
                "names": names,
                "importances": [float(x) for x in imp],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "unsupported": True,
                "unsupported_reason": "unfitted",
                "model_family_guess": family,
                "error": str(exc),
            }

    coef_imp = _coef_importances(clf) if clf is not None else None
    if coef_imp is not None and len(coef_imp) > 0:
        names = _feature_names(pipe, len(coef_imp))
        return {
            "ok": True,
            "method": "coef_abs",
            "model_family_guess": family,
            "names": names,
            "importances": coef_imp,
        }

    nb_imp = _nb_importances(clf) if clf is not None else None
    if nb_imp is not None and len(nb_imp) > 0:
        names = _feature_names(pipe, len(nb_imp))
        return {
            "ok": True,
            "method": "feature_log_prob_odds",
            "model_family_guess": family,
            "names": names,
            "importances": nb_imp,
        }

    return {
        "ok": False,
        "unsupported": True,
        "unsupported_reason": "no_native_importance",
        "model_family_guess": family,
        "note": "permutation_importance is unsupported (no_permutation)",
    }


def _pipeline_kind(pipe) -> str:
    if hasattr(pipe, "named_steps"):
        steps = set(pipe.named_steps.keys())
        if "prep" in steps and "ct" in steps:
            return "v3_lgbm_categorical"
        if "imputer" in steps:
            return "v2_legacy_numeric"
    return "unknown"


def _prepare_v2_numeric_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Match training-time data.xy(): coerce objects to numeric; fill missing cols."""
    frame = df.copy()
    for c in cols:
        if c not in frame.columns:
            frame[c] = np.nan
    x = frame.loc[:, cols].copy()
    for col in x.columns:
        if pd.api.types.is_integer_dtype(x[col]) or pd.api.types.is_bool_dtype(x[col]):
            x[col] = x[col].astype("float64")
        elif pd.api.types.is_object_dtype(x[col]) or pd.api.types.is_string_dtype(x[col]):
            x[col] = pd.to_numeric(x[col], errors="coerce")
    return x


def cmd_importances(payload: dict) -> dict:
    if payload.get("method") == "permutation" or payload.get("permutation"):
        return {
            "ok": False,
            "unsupported": True,
            "unsupported_reason": "no_permutation",
            "model_family_guess": None,
        }
    model = load_model_artifact(payload["pkl"])
    extracted = _extract_importances(model)
    if not extracted.get("ok"):
        return extracted
    names = extracted["names"]
    imp = extracted["importances"]
    order = np.argsort(imp)[::-1]
    ranked = [
        {"feature": names[i], "importance": imp[i], "rank": r + 1}
        for r, i in enumerate(order)
    ]
    return {
        "ok": True,
        "n_features": len(names),
        "ranked": ranked,
        "method": extracted.get("method"),
        "model_family_guess": extracted.get("model_family_guess"),
    }


def cmd_score(payload: dict) -> dict:
    model = load_model_artifact(payload["pkl"])
    pipe = model.base_estimator if hasattr(model, "base_estimator") else model
    cal = model if hasattr(model, "base_estimator") else None
    df = pd.read_parquet(payload["parquet"])
    cols = payload["feature_cols"]
    missing = [c for c in cols if c not in df.columns]
    kind = _pipeline_kind(pipe)

    if kind == "v2_legacy_numeric":
        frame = _prepare_v2_numeric_frame(df, cols)
        estimator = cal if cal is not None else pipe
        proba = estimator.predict_proba(frame)[:, 1]
        v2_note = (
            "v2 XGB pipeline uses median imputer on numeric-coerced columns; string categoricals "
            "(ProductCD, M*, id_*, email) become NaN and may be dropped at impute — counterfactual "
            "is approximate, not apples-to-apples with v3."
        )
    else:
        frame = df.reindex(columns=cols)
        estimator = cal if cal is not None else pipe
        proba = estimator.predict_proba(frame)[:, 1]
        v2_note = None

    stored = None
    if "prediction" in df.columns:
        stored = df["prediction"].astype(float).tolist()
    elif "risk_score" in df.columns:
        stored = df["risk_score"].astype(float).tolist()
    scores = [float(x) for x in proba]
    diffs = None
    if stored is not None:
        diffs = [round(s - o, 8) for s, o in zip(scores, stored)]
    out = {
        "ok": True,
        "pipeline_kind": kind,
        "n_rows": len(scores),
        "mean_score": float(np.mean(scores)),
        "p95_score": float(np.quantile(scores, 0.95)),
        "scores": scores,
        "stored_scores": stored,
        "score_diffs": diffs,
        "max_abs_diff": max((abs(d) for d in diffs), default=0.0) if diffs else None,
        "missing_cols_filled_nan": missing,
    }
    if v2_note:
        out["v2_scoring_note"] = v2_note
    return out


def cmd_explain(payload: dict) -> dict:
    """Local LGBM pred_contrib (TreeSHAP-equivalent) for selected row indices."""
    model = load_model_artifact(payload["pkl"])
    pipe = model.base_estimator if hasattr(model, "base_estimator") else model
    if _pipeline_kind(pipe) != "v3_lgbm_categorical":
        return {"ok": False, "error": "explain only supported for v3_lgbm_categorical pipeline"}
    prep = pipe.named_steps["prep"]
    ct = pipe.named_steps["ct"]
    clf = pipe.named_steps["clf"]
    df = pd.read_parquet(payload["parquet"])
    cols = payload["feature_cols"]
    indices = payload.get("row_indices") or list(range(min(5, len(df))))
    top_k = int(payload.get("top_k") or 8)
    names = list(ct.get_feature_names_out()) + ["bias"]
    rows_out: list[dict] = []
    for idx in indices:
        if idx < 0 or idx >= len(df):
            continue
        row = df.iloc[idx : idx + 1].reindex(columns=cols)
        x = ct.transform(prep.transform(row))
        contrib = clf.booster_.predict(x, pred_contrib=True)[0]
        order = np.argsort(np.abs(contrib))[::-1][:top_k]
        top_feats = [
            {"feature": names[i], "contribution": round(float(contrib[i]), 4)} for i in order if i < len(names)
        ]
        meta = {}
        for c in ("transaction_id", "prediction", "ProductCD", "TransactionAmt", "card1", "decision"):
            if c in df.columns:
                v = df.iloc[idx][c]
                meta[c] = v.item() if hasattr(v, "item") else v
        rows_out.append({"row_index": int(idx), "meta": meta, "top_contributions": top_feats})
    return {"ok": True, "method": "lightgbm pred_contrib (TreeSHAP-equivalent)", "rows": rows_out}


def cmd_ablate(payload: dict) -> dict:
    """Knock out one feature per row and re-score. Modes: zero, median_val."""
    model = load_model_artifact(payload["pkl"])
    pipe = model.base_estimator if hasattr(model, "base_estimator") else model
    cal = model if hasattr(model, "base_estimator") else None
    df = pd.read_parquet(payload["parquet"])
    cols = payload["feature_cols"]
    indices = payload.get("row_indices") or [0]
    ablate_cols = payload.get("ablate_cols") or []
    mode = payload.get("knockout_mode") or "zero"
    min_delta = float(payload.get("min_report_delta") or 0.0)
    auto_top_k = int(payload.get("auto_top_k") or 0)
    ref_path = payload.get("ref_parquet")
    if _pipeline_kind(pipe) != "v3_lgbm_categorical":
        return {"ok": False, "error": "ablate only supported for v3_lgbm_categorical pipeline"}
    estimator = cal if cal is not None else pipe
    prep = pipe.named_steps["prep"]
    ct = pipe.named_steps["ct"]
    clf = pipe.named_steps["clf"]

    medians: dict[str, Any] = {}
    if mode == "median_val" and ref_path:
        ref = pd.read_parquet(ref_path)
        for c in cols:
            if c not in ref.columns:
                continue
            s = ref[c]
            if pd.api.types.is_numeric_dtype(s):
                medians[c] = float(s.median()) if s.notna().any() else 0.0
            else:
                m = s.mode(dropna=True)
                medians[c] = m.iloc[0] if len(m) else "__missing__"

    def _strip_feat(name: str) -> str:
        for p in ("num__", "cat__"):
            if name.startswith(p):
                return name[len(p) :]
        return name

    def _cols_for_row(idx: int) -> list[str]:
        if auto_top_k <= 0:
            return ablate_cols
        row = df.iloc[idx : idx + 1].reindex(columns=cols)
        x = ct.transform(prep.transform(row))
        contrib = clf.booster_.predict(x, pred_contrib=True)[0]
        names = list(ct.get_feature_names_out())
        order = np.argsort(np.abs(contrib))[::-1]
        picked: list[str] = []
        for i in order:
            if i >= len(names):
                continue
            raw = _strip_feat(names[i])
            if raw == "bias" or raw in picked:
                continue
            picked.append(raw)
            if len(picked) >= auto_top_k:
                break
        return picked

    def _knockout_val(col: str, base: pd.DataFrame) -> Any:
        if mode == "median_val" and col in medians:
            return medians[col]
        if pd.api.types.is_numeric_dtype(base[col]):
            return 0
        return "__missing__"

    results: list[dict] = []
    for idx in indices:
        if idx < 0 or idx >= len(df):
            continue
        base_row = df.iloc[idx : idx + 1].reindex(columns=cols)
        base_score = float(estimator.predict_proba(base_row)[0, 1])
        meta = {}
        for c in ("transaction_id", "prediction", "ProductCD", "TransactionAmt", "card1"):
            if c in df.columns:
                v = df.iloc[idx][c]
                meta[c] = v.item() if hasattr(v, "item") else v
        cols_to_ablate = _cols_for_row(idx) if auto_top_k > 0 else ablate_cols
        row_out = {
            "row_index": int(idx),
            "base_score": round(base_score, 6),
            "meta": meta,
            "ablated_features": cols_to_ablate,
            "ablations": [],
            "n_no_effect": 0,
        }
        for col in cols_to_ablate:
            if col not in cols:
                continue
            knocked = base_row.copy()
            knocked[col] = _knockout_val(col, base_row)
            new_score = float(estimator.predict_proba(knocked)[0, 1])
            delta = round(new_score - base_score, 6)
            if abs(delta) < min_delta:
                row_out["n_no_effect"] += 1
                continue
            row_out["ablations"].append(
                {
                    "feature": col,
                    "knockout_mode": mode,
                    "knockout_value": knocked[col].iloc[0] if hasattr(knocked[col], "iloc") else knocked[col],
                    "score_after": round(new_score, 6),
                    "score_delta": delta,
                }
            )
        results.append(row_out)
    note = (
        "auto_top_k uses per-row pred_contrib features; only |Δ|≥min_report_delta shown. "
        "median_val replaces with REF val median/mode — more meaningful than zero for trees."
        if auto_top_k > 0
        else "fixed feature list knockout"
    )
    return {
        "ok": True,
        "method": f"single-feature knockout ({mode})",
        "note": note,
        "rows": results,
    }


def main() -> None:
    payload = json.loads(sys.stdin.read())
    cmd = payload.get("cmd")
    if cmd == "importances":
        out = cmd_importances(payload)
    elif cmd == "score":
        try:
            out = cmd_score(payload)
        except Exception as exc:
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    elif cmd == "explain":
        try:
            out = cmd_explain(payload)
        except Exception as exc:
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    elif cmd == "ablate":
        try:
            out = cmd_ablate(payload)
        except Exception as exc:
            out = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        out = {"ok": False, "error": f"unknown cmd {cmd}"}
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
