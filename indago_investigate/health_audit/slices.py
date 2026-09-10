"""Binned slice discovery on important features.

Two priorities (both reported):
1. vs rest:  priority = n_cur × |μ_score(slice) − μ_score(rest)|
2. vs REF:   priority = n_cur × |μ_score(slice_CUR) − μ_score(same_bin_REF)|

Numeric bins use REF val quantile edges. Categoricals use levels.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from indago_investigate.health_audit.thresholds import THR


def _quantile_edges(ref: pd.Series, n_bins: int) -> np.ndarray:
    vals = ref.dropna().astype(float)
    if len(vals) < n_bins * 2:
        qs = np.linspace(0, 1, min(n_bins, 3) + 1)
    else:
        qs = np.linspace(0, 1, n_bins + 1)
    edges = np.unique(np.quantile(vals, qs))
    if len(edges) < 3:
        edges = np.array([float(vals.min()), float(vals.median()), float(vals.max())], dtype=float)
    edges = edges.astype(float)
    edges[0] = -np.inf
    edges[-1] = np.inf
    return edges


def _is_cat(s: pd.Series) -> bool:
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
        return True
    if pd.api.types.is_numeric_dtype(s):
        nuniq = s.nunique(dropna=True)
        return nuniq <= 12 and nuniq < max(len(s) * 0.5, 1)
    return False


def discover_slices(
    *,
    cur: pd.DataFrame,
    ref: pd.DataFrame,
    scores_cur: np.ndarray,
    scores_ref: np.ndarray,
    features: list[str],
    metric_cur: np.ndarray | None = None,
    metric_ref: np.ndarray | None = None,
    metric_name: str = "score",
) -> dict[str, Any]:
    """Return ranked slices for both priority definitions.

    Default metric = prediction score. When labels/scores exist, pass
    metric_cur/metric_ref (e.g. isFraud) and metric_name for the main metric.
    """
    n_bins = THR["slice_n_bins"]
    min_n = THR["slice_min_n"]
    top_f = THR["slice_top_features"]
    report_top = THR["slice_report_top"]

    y_cur = np.asarray(metric_cur if metric_cur is not None else scores_cur, dtype=float)
    y_ref = np.asarray(metric_ref if metric_ref is not None else scores_ref, dtype=float)

    cur = cur.copy()
    ref = ref.copy()
    cur["_y"] = y_cur
    ref["_y"] = y_ref
    mu_cur_all = float(cur["_y"].mean())
    mu_ref_all = float(ref["_y"].mean())

    rows: list[dict[str, Any]] = []
    for col in features[:top_f]:
        if col not in cur.columns or col not in ref.columns:
            continue
        c_s = cur[col]
        r_s = ref[col]
        if _is_cat(r_s):
            levels = sorted(set(c_s.dropna().astype(str)) | set(r_s.dropna().astype(str)), key=str)
            for lev in levels:
                mask_c = c_s.astype(str) == lev
                mask_r = r_s.astype(str) == lev
                n_c = int(mask_c.sum())
                n_r = int(mask_r.sum())
                if n_c < min_n:
                    continue
                mu_c = float(cur.loc[mask_c, "_y"].mean())
                mu_rest = float(cur.loc[~mask_c, "_y"].mean()) if (~mask_c).any() else mu_cur_all
                mu_r = float(ref.loc[mask_r, "_y"].mean()) if n_r else None
                d_rest = mu_c - mu_rest
                d_ref = (mu_c - mu_r) if mu_r is not None else None
                rows.append(
                    {
                        "feature": col,
                        "kind": "categorical",
                        "bin": str(lev),
                        "n_cur": n_c,
                        "n_ref": n_r,
                        "mean_metric_cur": round(mu_c, 4),
                        "mean_metric_rest": round(mu_rest, 4),
                        "mean_metric_ref_bin": round(mu_r, 4) if mu_r is not None else None,
                        "delta_vs_rest": round(d_rest, 4),
                        "delta_vs_ref_bin": round(d_ref, 4) if d_ref is not None else None,
                        "priority_vs_rest": round(n_c * abs(d_rest), 4),
                        "priority_vs_ref": round(n_c * abs(d_ref), 4) if d_ref is not None else None,
                    }
                )
        else:
            edges = _quantile_edges(r_s, n_bins)
            cur_b = pd.cut(c_s.astype(float), bins=edges, include_lowest=True)
            ref_b = pd.cut(r_s.astype(float), bins=edges, include_lowest=True)
            # include NaN as its own bin if present
            cats = list(cur_b.cat.categories) if hasattr(cur_b, "cat") else sorted(set(cur_b.dropna().unique()), key=str)
            for cat in cats:
                mask_c = cur_b == cat
                mask_r = ref_b == cat
                n_c = int(mask_c.sum())
                n_r = int(mask_r.sum())
                if n_c < min_n:
                    continue
                mu_c = float(cur.loc[mask_c, "_y"].mean())
                mu_rest = float(cur.loc[~mask_c, "_y"].mean()) if (~mask_c).any() else mu_cur_all
                mu_r = float(ref.loc[mask_r, "_y"].mean()) if n_r else None
                d_rest = mu_c - mu_rest
                d_ref = (mu_c - mu_r) if mu_r is not None else None
                rows.append(
                    {
                        "feature": col,
                        "kind": "numeric_binned",
                        "bin": str(cat),
                        "n_cur": n_c,
                        "n_ref": n_r,
                        "mean_metric_cur": round(mu_c, 4),
                        "mean_metric_rest": round(mu_rest, 4),
                        "mean_metric_ref_bin": round(mu_r, 4) if mu_r is not None else None,
                        "delta_vs_rest": round(d_rest, 4),
                        "delta_vs_ref_bin": round(d_ref, 4) if d_ref is not None else None,
                        "priority_vs_rest": round(n_c * abs(d_rest), 4),
                        "priority_vs_ref": round(n_c * abs(d_ref), 4) if d_ref is not None else None,
                    }
                )
            nan_c = int(c_s.isna().sum())
            if nan_c >= min_n:
                mask_c = c_s.isna()
                mask_r = r_s.isna()
                mu_c = float(cur.loc[mask_c, "_y"].mean())
                mu_rest = float(cur.loc[~mask_c, "_y"].mean()) if (~mask_c).any() else mu_cur_all
                n_r = int(mask_r.sum())
                mu_r = float(ref.loc[mask_r, "_y"].mean()) if n_r else None
                d_rest = mu_c - mu_rest
                d_ref = (mu_c - mu_r) if mu_r is not None else None
                rows.append(
                    {
                        "feature": col,
                        "kind": "numeric_binned",
                        "bin": "NaN",
                        "n_cur": nan_c,
                        "n_ref": n_r,
                        "mean_metric_cur": round(mu_c, 4),
                        "mean_metric_rest": round(mu_rest, 4),
                        "mean_metric_ref_bin": round(mu_r, 4) if mu_r is not None else None,
                        "delta_vs_rest": round(d_rest, 4),
                        "delta_vs_ref_bin": round(d_ref, 4) if d_ref is not None else None,
                        "priority_vs_rest": round(nan_c * abs(d_rest), 4),
                        "priority_vs_ref": round(nan_c * abs(d_ref), 4) if d_ref is not None else None,
                    }
                )

    by_rest = sorted(rows, key=lambda r: -r["priority_vs_rest"])[:report_top]
    by_ref = sorted(
        [r for r in rows if r.get("priority_vs_ref") is not None],
        key=lambda r: -(r["priority_vs_ref"] or 0),
    )[:report_top]

    return {
        "method": (
            f"Important-feature bins (val quantile edges for numerics); metric={metric_name}. "
            "priority_vs_rest = n_cur × |μ_slice − μ_rest|; "
            "priority_vs_ref = n_cur × |μ_slice_CUR − μ_same_bin_REF|."
        ),
        "metric": metric_name,
        "n_bins": n_bins,
        "min_n": min_n,
        "features_scanned": features[:top_f],
        "n_slices_evaluated": len(rows),
        "mu_cur_all": round(mu_cur_all, 4),
        "mu_ref_all": round(mu_ref_all, 4),
        "top_by_vs_rest": by_rest,
        "top_by_vs_ref": by_ref,
    }
