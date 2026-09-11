"""IEEE feature typing — numeric + categorical columns for LightGBM native splits.

Vendored into the public package so lab-trained joblib pickles that reference
top-level ``features_ieee`` (and ``_PrepTransformer``) can unpickle via
``model_io.ensure_lab_unpickle_hooks`` without a training-lab PYTHONPATH.
"""

from __future__ import annotations

from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


def split_column_types(frame: pd.DataFrame, feature_cols: list[str]) -> tuple[list[str], list[str]]:
    """Object/string columns → categorical; everything else → numeric."""
    cat: list[str] = []
    num: list[str] = []
    for col in feature_cols:
        if col not in frame.columns:
            continue
        series = frame[col]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            cat.append(col)
        elif isinstance(series.dtype, pd.CategoricalDtype):
            cat.append(col)
        else:
            num.append(col)
    return num, cat


def prepare_frame(frame: pd.DataFrame, *, num_cols: list[str], cat_cols: list[str], feature_cols: list[str]) -> pd.DataFrame:
    """Coerce dtypes without destroying categoricals (unlike pd.to_numeric on objects)."""
    out = frame.loc[:, [c for c in feature_cols if c in frame.columns]].copy()
    for col in num_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in cat_cols:
        if col in out.columns:
            out[col] = out[col].astype("string").fillna("__missing__").replace({"<NA>": "__missing__", "nan": "__missing__"})
    return out


def build_lgbm_pipeline(
    train_frame: pd.DataFrame,
    feature_cols: list[str],
    *,
    scale_pos_weight: float,
    params: dict[str, Any],
) -> tuple[Pipeline, dict[str, Any]]:
    """Sklearn pipeline: impute → ordinal-encode cats → LightGBM with categorical_feature indices."""
    num_cols, cat_cols = split_column_types(train_frame, feature_cols)
    transformers: list[tuple] = []
    if num_cols:
        transformers.append(("num", SimpleImputer(strategy="median"), num_cols))
    if cat_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imp", SimpleImputer(strategy="constant", fill_value="__missing__")),
                        (
                            "ord",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                dtype=np.int32,
                            ),
                        ),
                    ]
                ),
                cat_cols,
            )
        )
    if not transformers:
        raise ValueError("No feature columns resolved for IEEE pipeline")

    col_transform = ColumnTransformer(transformers, remainder="drop")
    # ColumnTransformer emits numeric block then categorical block (in transformer order).
    cat_feature_indices = list(range(len(num_cols), len(num_cols) + len(cat_cols))) if cat_cols else None

    clf = lgb.LGBMClassifier(
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        verbose=-1,
        categorical_feature=cat_feature_indices if cat_feature_indices else "auto",
        **params,
    )

    meta = {
        "feature_cols": feature_cols,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "categorical_feature_indices": cat_feature_indices or [],
    }

    pipe = Pipeline(
        [
            ("prep", _PrepTransformer(num_cols, cat_cols, feature_cols)),
            ("ct", col_transform),
            ("clf", clf),
        ]
    )
    return pipe, meta


class _PrepTransformer(BaseEstimator, TransformerMixin):
    """Inline preparer so sklearn Pipeline keeps categorical strings until ordinal encode."""

    def __init__(self, num_cols: list[str], cat_cols: list[str], feature_cols: list[str]):
        self.num_cols = num_cols
        self.cat_cols = cat_cols
        self.feature_cols = feature_cols

    def fit(self, x, y=None):
        return self

    def transform(self, x):
        if isinstance(x, pd.DataFrame):
            return prepare_frame(x, num_cols=self.num_cols, cat_cols=self.cat_cols, feature_cols=self.feature_cols)
        df = pd.DataFrame(x, columns=self.feature_cols)
        return prepare_frame(df, num_cols=self.num_cols, cat_cols=self.cat_cols, feature_cols=self.feature_cols)


def xy_frames(
    frame: pd.DataFrame, feature_cols: list[str], *, num_cols: list[str], cat_cols: list[str]
) -> pd.DataFrame:
    return prepare_frame(frame, num_cols=num_cols, cat_cols=cat_cols, feature_cols=feature_cols)
