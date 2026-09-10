"""Load tabular evidence (parquet / csv / feather) for Views paths."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_table(path: Path | str) -> pd.DataFrame:
    """Read a frame file by suffix. Parquet preferred; csv/feather supported for contact."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".parquet":
        return pd.read_parquet(p)
    if suf == ".csv":
        return pd.read_csv(p)
    if suf in {".feather", ".ft"}:
        return pd.read_feather(p)
    # Default try parquet then csv
    try:
        return pd.read_parquet(p)
    except Exception:
        return pd.read_csv(p)
