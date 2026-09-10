"""Load champion PKLs for offline scoring / importances.

Runtime order (adr-scorer.md):
1. INDAGO_SCORER_PYTHON
2. Current interpreter if joblib importable (uv sync --extra score)
3. INDAGO_LAB_ROOT /.venv
4. Sibling production-ml-lab /.venv (discovery only — no hardcoded D:\\ path)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from indago_investigate.health_audit.helpers import champion_pkl, path, try_load_json

_PKG_FILE = Path(__file__).resolve()
WORKER = Path(__file__).resolve().parent / "_lab_worker.py"

IMPORTANCE_CAVEAT = (
    "LightGBM split-count importances favor high-cardinality / continuous columns "
    "because they can be split many times. Low-cardinality categoricals receive fewer "
    "splits — rank does not equal causal effect. Treat as hypothesis generators, not ground truth."
)


def _load_host_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for p in (
        Path.home() / ".indago.env",
        Path.home() / ".config" / "indago" / ".env",
    ):
        if p.is_file():
            load_dotenv(p, override=False)
    root = os.environ.get("INDAGO_ROOT")
    if root:
        env_path = Path(root) / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=False)


def _is_indago_repo(base: Path) -> bool:
    py = base / "pyproject.toml"
    if not py.is_file():
        return False
    try:
        text = py.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return 'name = "indago"' in text and (base / "package" / "indago_investigate").is_dir()


def _venv_python(lab: Path) -> Path | None:
    for p in (
        lab / ".venv" / "Scripts" / "python.exe",
        lab / ".venv" / "bin" / "python",
    ):
        if p.is_file():
            return p
    return None


def _joblib_available() -> bool:
    try:
        import joblib  # noqa: F401

        return True
    except ImportError:
        return False


def _resolve_scorer_python() -> tuple[Path | None, str]:
    """Return (python_exe, how) or (None, reason).

    Public/demo path: current interpreter + joblib is enough.
    Lab discovery only when INDAGO_SCORER_PYTHON or INDAGO_LAB_ROOT is set
    (or INDAGO_ALLOW_LAB_DISCOVERY=1 for sibling walk).
    """
    _load_host_dotenv()
    explicit = os.environ.get("INDAGO_SCORER_PYTHON")
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if p.is_file():
            return p, "INDAGO_SCORER_PYTHON"
        return None, f"INDAGO_SCORER_PYTHON not a file: {p}"

    if _joblib_available() and WORKER.is_file():
        return Path(sys.executable).resolve(), "current_interpreter+joblib"

    if os.environ.get("INDAGO_LAB_ROOT"):
        lab = Path(os.environ["INDAGO_LAB_ROOT"]).expanduser().resolve()
        py = _venv_python(lab)
        if py is not None:
            return py, "INDAGO_LAB_ROOT"
        return None, f"INDAGO_LAB_ROOT set but no .venv python under {lab}"

    allow_lab = (os.environ.get("INDAGO_ALLOW_LAB_DISCOVERY") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if not allow_lab:
        return None, (
            "no scorer python: install package with [score] (joblib/sklearn), "
            "or set INDAGO_SCORER_PYTHON / INDAGO_LAB_ROOT "
            "(optional sibling walk: INDAGO_ALLOW_LAB_DISCOVERY=1)"
        )

    if os.environ.get("INDAGO_ROOT"):
        cand = Path(os.environ["INDAGO_ROOT"]).expanduser().resolve().parent / "production-ml-lab"
        py = _venv_python(cand)
        if py is not None:
            return py, "INDAGO_ROOT_sibling"

    for base in (Path.cwd().resolve(), *Path.cwd().resolve().parents):
        direct = base / "production-ml-lab"
        py = _venv_python(direct)
        if py is not None:
            return py, "cwd_walk"
        if _is_indago_repo(base):
            sibling = (base.parent / "production-ml-lab").resolve()
            py = _venv_python(sibling)
            if py is not None:
                return py, "indago_sibling"

    for base in _PKG_FILE.parents:
        if _is_indago_repo(base):
            sibling = (base.parent / "production-ml-lab").resolve()
            py = _venv_python(sibling)
            if py is not None:
                return py, "package_sibling"

    return None, (
        "no scorer python: uv/pip install -e '.[score]', "
        "or set INDAGO_SCORER_PYTHON / INDAGO_LAB_ROOT. See context/package/adr-scorer.md"
    )


def lab_python() -> Path | None:
    py, _how = _resolve_scorer_python()
    return py


def _run_worker(payload: dict[str, Any]) -> dict[str, Any]:
    py, how = _resolve_scorer_python()
    if py is None or not WORKER.is_file():
        return {
            "ok": False,
            "error": how if py is None else f"worker missing: {WORKER}",
            "scorer_how": how,
        }
    env = dict(os.environ)
    # Optional lab train helpers on PYTHONPATH when using lab venv
    lab_root = os.environ.get("INDAGO_LAB_ROOT")
    if lab_root:
        train = Path(lab_root) / "playground" / "04_train"
        if train.is_dir():
            env["PYTHONPATH"] = str(train) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [str(py), str(WORKER)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path.cwd()),
        timeout=180,
    )
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": proc.stderr.strip() or proc.stdout.strip(),
            "scorer_how": how,
        }
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"worker json parse: {exc}; stdout={proc.stdout[:500]}",
            "scorer_how": how,
        }
    if isinstance(out, dict):
        out.setdefault("scorer_how", how)
    return out


def feature_cols_for_version(version: int | None = None) -> list[str]:
    spec = try_load_json("ieee/models/ieee_pipeline_spec.json")
    if spec and spec.get("feature_cols"):
        return list(spec["feature_cols"])
    idx = try_load_json("ieee/models/models_index.json")
    winners = try_load_json("ieee/models/train_winners_ieee.json")
    aliases_doc = try_load_json("ieee/models/aliases_snapshot.json")
    alias_list = (aliases_doc or {}).get("aliases") or []

    if version is not None:
        for m in alias_list:
            if m.get("registry_version") == version:
                cols = m.get("feature_cols")
                if cols:
                    return list(cols)
        if idx:
            for m in idx.get("models") or []:
                if m.get("registry_version") == version:
                    label = m.get("run_id_label")
                    alias = m.get("alias")
                    if winners and label:
                        for w in winners:
                            if w.get("run_id_label") == label:
                                return list(w.get("feature_cols") or [])
                    if winners and alias:
                        for w in winners:
                            if w.get("alias") == alias:
                                return list(w.get("feature_cols") or [])

    if winners:
        for w in winners:
            if w.get("alias") == "champion" or w.get("rank") == 1:
                return list(w.get("feature_cols") or [])
    baseline = try_load_json("workspace/playground/outputs/monitor_baseline_ieee.json")
    if not baseline:
        baseline = try_load_json("evidence/monitor_baseline.json")
    return list(baseline.get("feature_cols") or []) if baseline else []


def get_importances(*, pkl_rel: str | None = None, pkl_path: str | Path | None = None) -> dict[str, Any]:
    if pkl_path is not None:
        pkl = Path(pkl_path)
    elif pkl_rel:
        pkl = path(pkl_rel)
    else:
        pkl = champion_pkl()
    if pkl is None or not pkl.is_file():
        return {"ok": False, "error": "champion PKL not found — pass --model-path or author ModelView"}
    return _run_worker({"cmd": "importances", "pkl": str(pkl.resolve())})


def score_parquet(
    *,
    pkl_rel: str = "",
    parquet_rel: str = "",
    feature_cols: list[str],
    score_col: str = "offline_score",
    pkl_abs: str | Path | None = None,
    parquet_abs: str | Path | None = None,
) -> dict[str, Any]:
    pkl = Path(pkl_abs) if pkl_abs else path(pkl_rel)
    parquet = Path(parquet_abs) if parquet_abs else path(parquet_rel)
    if not pkl.is_file() or not parquet.is_file():
        return {"ok": False, "error": f"missing pkl={pkl.is_file()} parquet={parquet.is_file()}"}
    return _run_worker(
        {
            "cmd": "score",
            "pkl": str(pkl.resolve()),
            "parquet": str(parquet.resolve()),
            "feature_cols": feature_cols,
            "score_col": score_col,
        }
    )
