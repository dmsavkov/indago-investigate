"""Portable calibrated estimator for packs that used lab ``calibrate.CalibratedProbaEstimator``.

Joblib pickles store the defining module path. Re-dump IEEE-style champions through
this module so a clean ``pip install -e ".[score]"`` env can load them without the
training lab on ``sys.path``.
"""

from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.isotonic import IsotonicRegression


class CalibratedProbaEstimator(BaseEstimator, ClassifierMixin):
    """Fit base estimator on train; fit isotonic calibrator on validation scores."""

    def __init__(self, base_estimator, *, method: str = "isotonic"):
        self.base_estimator = base_estimator
        self.method = method
        self.calibrator_: IsotonicRegression | None = None
        self.classes_ = np.array([0, 1])

    def fit(self, x, y):
        self.base_estimator.fit(x, y)
        return self

    def fit_calibrator(self, x_val, y_val) -> CalibratedProbaEstimator:
        raw = self.base_estimator.predict_proba(x_val)[:, 1]
        self.calibrator_ = IsotonicRegression(out_of_bounds="clip")
        self.calibrator_.fit(raw, y_val)
        return self

    def predict_proba(self, x) -> np.ndarray:
        raw = self.base_estimator.predict_proba(x)[:, 1]
        if self.calibrator_ is None:
            cal = raw
        else:
            cal = self.calibrator_.predict(raw)
        cal = np.clip(cal, 0.0, 1.0)
        return np.column_stack([1.0 - cal, cal])

    def predict(self, x) -> np.ndarray:
        return (self.predict_proba(x)[:, 1] >= 0.5).astype(int)
