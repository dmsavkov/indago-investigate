"""Case path resolution for health_audit (--profile ieee_flash and pack layout).

G2a: case-local evidence only by default. Shadow overfetch requires INDAGO_ALLOW_OVERFETCH=1.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from indago_investigate.bind_mode import allow_overfetch

# Logical asset → candidate relative paths under case_root (first existing wins).
ASSET_CANDIDATES: dict[str, tuple[str, ...]] = {
    "alert": ("alert.json",),
    "cur": (
        "evidence/live/data/events_cur.parquet",
        "evidence/events_cur.parquet",
        "workspace/lake/events_sample.parquet",
    ),
    "ref_train": (
        "evidence/ref/data/train.parquet",
        "evidence/ref/ieee/reference/train_sample_50k.parquet",
        "evidence/train_sample_50k.parquet",
        "evidence/ref/train_sample_50k.parquet",
    ),
    "ref_val": (
        "evidence/ref/data/val.parquet",
        "evidence/ref/ieee/reference/val_sample_20k.parquet",
        "evidence/val_sample_20k.parquet",
        "evidence/ref/val_sample_20k.parquet",
        "evidence/ref/val.parquet",
    ),
    "baseline": (
        "evidence/monitor_baseline.json",
        "workspace/playground/outputs/monitor_baseline_ieee.json",
    ),
    "snapshot": (
        "evidence/monitor_snapshot.json",
        "workspace/playground/outputs/monitor_snapshot_ieee.json",
    ),
    "aliases": (
        "evidence/aliases.json",
        "workspace/registry/aliases.json",
    ),
    "queue": (
        "evidence/queue_backlog.json",
        "workspace/telemetry/queue_backlog.json",
    ),
    "infra": (
        "evidence/infra_summary.json",
        "workspace/telemetry/infra_summary.json",
    ),
    "k8s": (
        "evidence/k8s_events.json",
        "workspace/telemetry/k8s_events.json",
    ),
    "dbt": (
        "evidence/dbt_run_summary.json",
        "workspace/orchestration/dbt_run_summary.json",
    ),
    "labels": (
        "evidence/label_state.json",
        "workspace/labels/label_state.json",
    ),
    "champion_spec": (
        "evidence/ref/ieee/models/champion_spec.json",
        "evidence/models/champion_spec.json",
        "workspace/playground/outputs/ieee_champion_spec.json",
        "evidence/provenance/champion_spec.json",
    ),
    "models_index": (
        "evidence/models/models_index.json",
        "evidence/ref/ieee/models/models_index.json",
    ),
    "feature_contract": (
        "evidence/feature_contract.json",
        "workspace/playground/outputs/ieee_feature_contract.json",
        "evidence/ref/ieee/lineage/feature_contract.json",
    ),
    "git_snap": ("evidence/ref/ieee/lineage/git_snapshot.json", "evidence/git_snapshot.json"),
    "pipeline_spec": ("evidence/ref/ieee/models/ieee_pipeline_spec.json",),
    "train_winners": ("evidence/ref/ieee/models/train_winners_ieee.json",),
    "aliases_snapshot": ("evidence/ref/ieee/models/aliases_snapshot.json",),
    "rules_default": (
        "evidence/ref/rules/rules_default.yaml",
        "evidence/ref/rules_default.yaml",
        "evidence/ref/ieee/rules/rules_v1.yaml",
        "evidence/rules/active_rules.yaml",
    ),
    "rules_loose": (
        "evidence/ref/rules/rules_loose_ref.yaml",
        "evidence/ref/ieee/rules/rules_loose_ref.yaml",
    ),
    "pkl": (
        "evidence/live/models/ieee_champion_v3.pkl",
        "evidence/models/ieee_champion_v3.pkl",
        "evidence/ref/ieee/models/ieee_champion_v3.pkl",
    ),
}

# Legacy relative strings → asset keys (resolved under case, not shared overfetch).
FOLKLORE_MAP: dict[str, str] = {
    "alert.json": "alert",
    "workspace/lake/events_sample.parquet": "cur",
    "evidence/events_cur.parquet": "cur",
    "evidence/live/data/events_cur.parquet": "cur",
    "evidence/ref/data/val.parquet": "ref_val",
    "evidence/ref/val.parquet": "ref_val",
    "evidence/live/models/ieee_champion_v3.pkl": "pkl",
    "evidence/ref/rules/rules_default.yaml": "rules_default",
    "evidence/ref/rules_default.yaml": "rules_default",
    "overfetch/ieee/reference/train_sample_50k.parquet": "ref_train",
    "evidence/ref/ieee/reference/train_sample_50k.parquet": "ref_train",
    "overfetch/ieee/reference/val_sample_20k.parquet": "ref_val",
    "evidence/ref/ieee/reference/val_sample_20k.parquet": "ref_val",
    "workspace/playground/outputs/monitor_baseline_ieee.json": "baseline",
    "workspace/playground/outputs/monitor_snapshot_ieee.json": "snapshot",
    "workspace/registry/aliases.json": "aliases",
    "workspace/telemetry/queue_backlog.json": "queue",
    "workspace/telemetry/infra_summary.json": "infra",
    "workspace/telemetry/k8s_events.json": "k8s",
    "workspace/orchestration/dbt_run_summary.json": "dbt",
    "workspace/labels/label_state.json": "labels",
    "workspace/playground/outputs/ieee_champion_spec.json": "champion_spec",
    "ieee/models/champion_spec.json": "champion_spec",
    "ieee/models/models_index.json": "models_index",
    "workspace/playground/outputs/ieee_feature_contract.json": "feature_contract",
    "ieee/lineage/feature_contract.json": "feature_contract",
    "ieee/lineage/git_snapshot.json": "git_snap",
    "ieee/models/ieee_pipeline_spec.json": "pipeline_spec",
    "ieee/models/train_winners_ieee.json": "train_winners",
    "ieee/models/aliases_snapshot.json": "aliases_snapshot",
    "ieee/rules/rules_v1.yaml": "rules_default",
    "ieee/rules/rules_loose_ref.yaml": "rules_loose",
    "ieee/models/ieee_champion_v3.pkl": "pkl",
}


def _case_ieee_path(case_root: Path, norm: str) -> Path | None:
    """Map overfetch/ieee/... or ieee/... folklore onto evidence/ref/ieee/... under the case."""
    if norm.startswith("overfetch/ieee/"):
        rel = norm.removeprefix("overfetch/")
        p = case_root / "evidence" / "ref" / rel
        return p if p.exists() else case_root / "evidence" / rel
    if norm.startswith("ieee/"):
        p = case_root / "evidence" / "ref" / norm
        if p.exists():
            return p
        p2 = case_root / "evidence" / norm
        return p2 if p2.exists() else p
    return None


@dataclass
class CaseIO:
    case_root: Path
    profile: str = "ieee_flash"
    out_dir: Path | None = None
    overfetch_root: Path | None = None
    _cache: dict[str, Path | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.case_root = self.case_root.resolve()
        if self.out_dir is None:
            self.out_dir = self.case_root / "out"
        self.out_dir = Path(self.out_dir)
        (self.out_dir / "reports").mkdir(parents=True, exist_ok=True)
        (self.out_dir / "plots").mkdir(parents=True, exist_ok=True)
        if allow_overfetch() and self.overfetch_root is None:
            for cand in (
                self.case_root.parent / "_shared" / "overfetch",
                Path(__file__).resolve().parents[3] / "packs" / "overfetch_data",
            ):
                if cand.is_dir():
                    self.overfetch_root = cand
                    logger.warning(
                        "INDAGO_ALLOW_OVERFETCH: using shadow overfetch root={}",
                        cand,
                    )
                    break
        elif self.overfetch_root is not None and not allow_overfetch():
            logger.info("ignoring overfetch_root (case-local evidence only)")
            self.overfetch_root = None

    def find_asset(self, key: str) -> Path | None:
        if key in self._cache:
            return self._cache[key]
        for rel in ASSET_CANDIDATES.get(key, ()):
            p = self.case_root / rel
            if p.is_file():
                self._cache[key] = p
                return p
        if self.overfetch_root is not None:
            for rel in ASSET_CANDIDATES.get(key, ()):
                norm = rel.replace("\\", "/")
                if "ref/ieee/" in norm:
                    tail = norm.split("ref/ieee/", 1)[-1]
                    p = self.overfetch_root / "ieee" / tail
                    if p.is_file():
                        self._cache[key] = p
                        return p
                if norm.startswith("ieee/"):
                    p = self.overfetch_root / norm
                    if p.is_file():
                        self._cache[key] = p
                        return p
        self._cache[key] = None
        return None

    def path(self, rel: str) -> Path:
        norm = rel.replace("\\", "/")
        if norm in FOLKLORE_MAP:
            found = self.find_asset(FOLKLORE_MAP[norm])
            if found is not None:
                return found
        mapped = _case_ieee_path(self.case_root, norm)
        if mapped is not None and mapped.exists():
            return mapped
        if self.overfetch_root is not None:
            if norm.startswith("overfetch/"):
                return self.overfetch_root / norm.removeprefix("overfetch/")
            if norm.startswith("ieee/"):
                p = self.overfetch_root / norm
                if p.exists():
                    return p
        direct = self.case_root / norm
        if direct.exists():
            return direct
        ev = self.case_root / "evidence" / norm
        if ev.exists():
            return ev
        return mapped if mapped is not None else direct

    def load_json(self, rel: str) -> Any:
        with self.path(rel).open(encoding="utf-8") as f:
            return json.load(f)

    def try_load_json(self, rel: str) -> dict[str, Any] | None:
        p = self.path(rel)
        if not p.is_file():
            key = FOLKLORE_MAP.get(rel.replace("\\", "/"))
            if key:
                p2 = self.find_asset(key)
                if p2 is None or not p2.is_file():
                    return None
                p = p2
            else:
                return None
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None

    def load_parquet(self, rel: str):
        import pandas as pd

        return pd.read_parquet(self.path(rel))

    def champion_pkl(self, *, version: int | None = None) -> Path | None:
        p = self.find_asset("pkl")
        if p is not None and p.is_file():
            return p
        if self.overfetch_root is not None:
            guess = self.overfetch_root / "ieee" / "models" / f"ieee_champion_v{version or 3}.pkl"
            if guess.is_file():
                return guess
        return None


_CASE_IO: CaseIO | None = None


def set_case_io(io: CaseIO) -> None:
    global _CASE_IO
    _CASE_IO = io
    logger.info(
        "health_audit CaseIO root={} profile={} overfetch={}",
        io.case_root,
        io.profile,
        io.overfetch_root,
    )


def get_case_io() -> CaseIO:
    if _CASE_IO is None:
        raise RuntimeError("CaseIO not set — call set_case_io / bind_case first")
    return _CASE_IO


# Module-level shims (helpers.py + planes/model_scoring import these).


def path(rel: str) -> Path:
    return get_case_io().path(rel)


def load_json(rel: str) -> Any:
    return get_case_io().load_json(rel)


def try_load_json(rel: str) -> dict[str, Any] | None:
    return get_case_io().try_load_json(rel)


def load_parquet(rel: str):
    return get_case_io().load_parquet(rel)


def champion_pkl(*, version: int | None = None) -> Path | None:
    return get_case_io().champion_pkl(version=version)


def save_json(name: str, data: Any) -> Path:
    """Write JSON under case out/ (default <case>/out/<name>)."""
    io = get_case_io()
    assert io.out_dir is not None
    dest = io.out_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
        f.write("\n")
    return dest


def write_md(name: str, text: str) -> Path:
    """Write markdown under case out/ (default <case>/out/<name>)."""
    io = get_case_io()
    assert io.out_dir is not None
    dest = io.out_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return dest
