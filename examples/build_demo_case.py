"""Regenerate package/examples/demo_case (synthetic CUR/REF + sklearn PKL + Views)."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent / "demo_case"


def main() -> None:
    for p in [
        ROOT / "evidence/live/data",
        ROOT / "evidence/live/models",
        ROOT / "evidence/live/rules",
        ROOT / "evidence/ref/data",
        ROOT / "evidence/ref/models",
        ROOT / "evidence/ref/rules",
        ROOT / "out/views",
        ROOT / "org-docs",
    ]:
        p.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(42)
    n_cur, n_ref = 40, 60

    def make_df(n: int, shift: float = 0.0) -> pd.DataFrame:
        entity = rng.choice(["E1", "E2", "E3", "E4"], size=n)
        amt = rng.uniform(5, 200, size=n) + shift
        x1 = rng.normal(0, 1, size=n) + shift * 0.01
        z = 0.02 * amt + 0.8 * x1 + rng.normal(0, 0.3, size=n)
        score = 1 / (1 + np.exp(-z))
        decision = np.where(score > 0.55, "DECLINE", "APPROVE")
        return pd.DataFrame(
            {
                "event_id": [f"c{i}" for i in range(n)],
                "entity_id": entity,
                "amt": amt.round(2),
                "x1": x1.round(4),
                "product_code": rng.choice(["W", "C", "H"], size=n),
                "y_hat": score.round(6),
                "decision": decision,
            }
        )

    cur = make_df(n_cur, shift=2.0)
    ref = make_df(n_ref, shift=0.0)
    cur.to_parquet(ROOT / "evidence/live/data/events_cur.parquet", index=False)
    ref.to_parquet(ROOT / "evidence/ref/data/val.parquet", index=False)

    clf = LogisticRegression(max_iter=500, random_state=42)
    clf.fit(ref[["amt", "x1"]], (ref["y_hat"] > 0.5).astype(int))
    joblib.dump(clf, ROOT / "evidence/live/models/champion.pkl")
    (ROOT / "evidence/live/models/feature_cols.json").write_text(
        json.dumps({"feature_cols": ["amt", "x1"]}, indent=2) + "\n",
        encoding="utf-8",
    )

    alert = {
        "schema": "indago_alert_v1",
        "incident_id": "demo-001",
        "primary_metric": "decline_rate",
        "primary_status": "ALERT",
        "window_n": int(n_cur),
        "window_capacity": 100,
        "message": "Demo rumor: decline rate up — investigate before acting.",
        "co_fired": [
            {
                "id": "score_mean_shift",
                "status": "WARN",
                "message": "mean score higher than ref",
            }
        ],
    }
    (ROOT / "alert.json").write_text(json.dumps(alert, indent=2) + "\n", encoding="utf-8")
    (ROOT / "org-docs" / "MANIFEST.md").write_text(
        "# Demo org docs\n\nSynthetic pack. Columns: entity_id, amt, x1, y_hat, decision.\n",
        encoding="utf-8",
    )

    roles = {
        "score": "y_hat",
        "decision": "decision",
        "slice_key": "entity_id",
        "amount": "amt",
        "product": "product_code",
    }
    views = {
        "frame_cur.json": {
            "view_id": "frame_cur_v1",
            "frame_id": "events_cur",
            "split": "cur",
            "n_rows": n_cur,
            "path_or_handle": "evidence/live/data/events_cur.parquet",
            "column_roles": roles,
            "score_column": "y_hat",
            "limitations": ["synthetic demo"],
            "extras": {},
        },
        "frame_ref_val.json": {
            "view_id": "frame_ref_val_v1",
            "frame_id": "events_ref_val",
            "split": "ref_val",
            "n_rows": n_ref,
            "path_or_handle": "evidence/ref/data/val.parquet",
            "column_roles": roles,
            "score_column": "y_hat",
            "limitations": ["synthetic demo"],
            "extras": {},
        },
        "model.json": {
            "view_id": "model_v1",
            "artifact_available": True,
            "registry_version": 1,
            "alias": "champion",
            "path_or_handle": "evidence/live/models/champion.pkl",
            "feature_cols_ref": "evidence/live/models/feature_cols.json",
            "limitations": ["sklearn LogisticRegression synthetic"],
            "extras": {},
        },
        "alert.json": {
            "view_id": "alert_v1",
            "path_or_handle": "alert.json",
            "limitations": [],
            "extras": {},
        },
    }
    for name, data in views.items():
        (ROOT / "out/views" / name).write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )

    (ROOT / "README.md").write_text(
        "# demo_case\n\nSynthetic CUR/REF + LogisticRegression PKL for package CLI smoke.\n"
        "Pre-bound Views under `out/views/`.\n\n"
        "Regenerate: `uv run python package/examples/build_demo_case.py`\n",
        encoding="utf-8",
    )
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
