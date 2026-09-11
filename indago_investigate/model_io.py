"""Load sklearn / joblib model artifacts, including Indago portable calibrate bundles."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from loguru import logger

BUNDLE_FORMAT = "indago_calibrated_bundle_v1"


def ensure_lab_unpickle_hooks() -> None:
    """Register module aliases so lab-trained pickles resolve without a lab PYTHONPATH.

    IEEE champion pickles reference top-level ``calibrate`` and ``features_ieee``.
    Public installs vendor those under ``indago_investigate`` and alias them here
    before ``joblib.load``.
    """
    from indago_investigate import features_ieee as features_mod
    from indago_investigate import portable_calibrate as calibrate_mod

    sys.modules.setdefault("calibrate", calibrate_mod)
    sys.modules.setdefault("features_ieee", features_mod)


def load_model_artifact(path: Path | str) -> Any:
    """Load a model file; unwrap ``indago_calibrated_bundle_v1`` if present."""
    ensure_lab_unpickle_hooks()
    import joblib
    import numpy as np

    obj = joblib.load(Path(path))
    if isinstance(obj, dict) and obj.get("format") == BUNDLE_FORMAT:
        from indago_investigate.portable_calibrate import CalibratedProbaEstimator

        logger.info("Unwrapping {} from {}", BUNDLE_FORMAT, path)
        est = CalibratedProbaEstimator(
            obj["base_estimator"],
            method=str(obj.get("method") or "isotonic"),
        )
        est.calibrator_ = obj.get("calibrator")
        classes = obj.get("classes")
        if classes is not None:
            est.classes_ = np.asarray(classes)
        return est
    return obj
