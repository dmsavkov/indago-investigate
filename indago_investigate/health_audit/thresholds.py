"""Package default thresholds + PSI bands (contact: no customer threshold card).

Agent-facing mirror: package/docs/thresholds.md (flashed to _shared/docs/).
"""

from __future__ import annotations

from typing import Any

# PSI industry bands (replace single hard cut at 0.20).
PSI_STABLE = 0.10
PSI_ALERT = 0.25

THR: dict[str, Any] = {
    "pred_mean_abs": 0.015,
    "tail_score": 0.85,
    "tail_rate_delta_pp": 10.0,
    # Legacy single key kept for any remaining call sites; prefer psi_status().
    "psi": PSI_ALERT,
    "psi_stable": PSI_STABLE,
    "psi_alert": PSI_ALERT,
    "null_delta_train": 0.20,
    "null_delta_warn": 0.10,
    "null_val_align": 0.05,
    "zero_mass_velocity": 3.0,
    "schema_overlap": 0.90,
    "latency_p95_ms": 500.0,
    "inference_lag": 50,
    "tile_lag_warn": 50,
    "concentration_share": 0.25,
    "concentration_ratio": 2.0,
    "min_slice_n": 5,
    "gain_x_psi_alert": 0.15,
    "ks_alert": 0.25,
    "w1_alert": 0.08,
    "parity_abs": 1e-4,
    "threshold_proximity": 0.02,
    "top_k_features": 20,
    "small_n": 100,
    "slice_n_bins": 5,
    "slice_min_n": 5,
    "slice_top_features": 12,
    "slice_report_top": 8,
    "gain_x_psi_show": 0.05,
    "delta_pp_show": 5.0,
}


def psi_band(psi: float) -> str:
    """Return stable | watch | investigate for a PSI value."""
    if psi < PSI_STABLE:
        return "stable"
    if psi <= PSI_ALERT:
        return "watch"
    return "investigate"


def psi_status(psi: float | None) -> str:
    """Map PSI to HA check status (GREEN / WARN / ALERT / UNKNOWN)."""
    if psi is None:
        return "UNKNOWN"
    try:
        v = float(psi)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if v != v:  # NaN
        return "UNKNOWN"
    return {"stable": "GREEN", "watch": "WARN", "investigate": "ALERT"}[psi_band(v)]
