"""Case-local evidence inventory — present files first (catalog schema 2)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from indago_investigate.paths import discover_overfetch, load_manifest, resolve_path
from indago_investigate.refs import Availability, EvidenceFormat, EvidenceKind, EvidenceRef

# Skip noise in walks
_SKIP_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db"}
_SKIP_SUFFIXES = {".pyc"}
_SKIP_DIR_PARTS = {"__pycache__", ".git", "playground"}

CATALOG_SCHEMA = 2

# Folklore candidates — only when INDAGO_CATALOG_FOLKLORE=1 (lab dogfood)
_CANDIDATES: list[tuple[EvidenceKind, tuple[str, ...], EvidenceFormat]] = [
    (EvidenceKind.alert, ("alert.json",), EvidenceFormat.json),
    (
        EvidenceKind.events_cur,
        (
            "evidence/live/data/events_cur.parquet",
            "evidence/events_cur.parquet",
            "workspace/lake/events_sample.parquet",
        ),
        EvidenceFormat.parquet,
    ),
    (
        EvidenceKind.events_ref_val,
        (
            "evidence/ref/data/val.parquet",
            "evidence/ref/ieee/reference/val_sample_20k.parquet",
            "evidence/val_sample_20k.parquet",
            "evidence/ref/val_sample_20k.parquet",
            "evidence/ref/val.parquet",
        ),
        EvidenceFormat.parquet,
    ),
    (
        EvidenceKind.events_ref_train,
        (
            "evidence/ref/ieee/reference/train_sample_50k.parquet",
            "evidence/train_sample_50k.parquet",
            "evidence/ref/train_sample_50k.parquet",
        ),
        EvidenceFormat.parquet,
    ),
    (
        EvidenceKind.monitor_baseline,
        (
            "evidence/monitor_baseline.json",
            "workspace/playground/outputs/monitor_baseline_ieee.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.monitor_snapshot,
        (
            "evidence/monitor_snapshot.json",
            "workspace/playground/outputs/monitor_snapshot_ieee.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.labels,
        (
            "evidence/label_state.json",
            "workspace/labels/label_state.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.maturation,
        (
            "evidence/maturation.json",
            "workspace/labels/maturation.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.model_artifact,
        (
            "evidence/live/models/champion.pkl",
            "evidence/live/models/ieee_champion_v3.pkl",
            "evidence/models/ieee_champion_v3.pkl",
            "evidence/ref/ieee/models/ieee_champion_v3.pkl",
        ),
        EvidenceFormat.pkl,
    ),
    (
        EvidenceKind.model_meta,
        (
            "evidence/models/models_index.json",
            "evidence/ref/ieee/models/models_index.json",
            "workspace/playground/outputs/ieee_champion_spec.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.rules_live,
        (
            "evidence/live/rules/live_policy.json",
            "evidence/rules/live_policy.json",
            "evidence/rules/active_rules.yaml",
            "workspace/rules/active_rules.yaml",
        ),
        EvidenceFormat.yaml,
    ),
    (
        EvidenceKind.rules_ref_default,
        (
            "evidence/ref/rules/rules_default.yaml",
            "evidence/ref/rules_default.yaml",
            "evidence/ref/ieee/rules/rules_v1.yaml",
            "evidence/rules/active_rules.yaml",
        ),
        EvidenceFormat.yaml,
    ),
    (
        EvidenceKind.rules_ref_loose,
        ("evidence/ref/ieee/rules/rules_loose_ref.yaml",),
        EvidenceFormat.yaml,
    ),
    (
        EvidenceKind.registry_aliases,
        ("evidence/aliases.json", "workspace/registry/aliases.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.telemetry_infra,
        ("evidence/infra_summary.json", "workspace/telemetry/infra_summary.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.telemetry_queues,
        ("evidence/queue_backlog.json", "workspace/telemetry/queue_backlog.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.feature_contract,
        (
            "evidence/feature_contract.json",
            "workspace/playground/outputs/ieee_feature_contract.json",
            "evidence/ref/ieee/lineage/feature_contract.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.online_store,
        ("evidence/online_snapshot.json", "workspace/feature-store/online_snapshot.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.tile_schema,
        ("evidence/tile_schema.json", "workspace/feature-store/tile_schema.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.orchestration,
        ("evidence/dbt_run_summary.json", "workspace/orchestration/dbt_run_summary.json"),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.lineage,
        ("evidence/git_snapshot.json", "evidence/ref/ieee/lineage/git_snapshot.json"),
        EvidenceFormat.json,
    ),
]

# Kept for materialize / request-missing (compat); not used by default catalog.
RECOMMENDED_KINDS: tuple[EvidenceKind, ...] = (
    EvidenceKind.alert,
    EvidenceKind.events_cur,
    EvidenceKind.events_ref_val,
    EvidenceKind.model_artifact,
)


class CatalogFile(BaseModel):
    """One present file on disk (catalog schema 2)."""

    rel: str
    class_: str = Field(alias="class")
    format: str
    size_bytes: int
    mtime: str | None = None
    n_rows: int | None = None
    n_cols: int | None = None
    kind_hint: str | None = None

    model_config = {"populate_by_name": True}


def _format_of(path: Path) -> EvidenceFormat:
    return {
        ".json": EvidenceFormat.json,
        ".parquet": EvidenceFormat.parquet,
        ".pkl": EvidenceFormat.pkl,
        ".joblib": EvidenceFormat.pkl,
        ".yaml": EvidenceFormat.yaml,
        ".yml": EvidenceFormat.yaml,
        ".csv": EvidenceFormat.unknown,
        ".md": EvidenceFormat.unknown,
    }.get(path.suffix.lower(), EvidenceFormat.unknown)


def _classify(rel: str) -> tuple[str, str | None]:
    """Return (class, optional kind_hint for legacy consumers)."""
    posix = rel.replace("\\", "/")
    low = posix.lower()
    if posix == "alert.json" or posix.endswith("/alert.json"):
        return "alert", EvidenceKind.alert.value
    if "/live/models/" in low or low.startswith("evidence/live/models/"):
        if low.endswith((".pkl", ".joblib")):
            return "model", EvidenceKind.model_artifact.value
        return "model", EvidenceKind.model_meta.value
    if "/ref/models/" in low:
        return "model", None
    if "/live/rules/" in low or "/ref/rules/" in low or "/rules/" in low:
        if low.endswith((".yaml", ".yml", ".json")):
            hint = (
                EvidenceKind.rules_live.value
                if "/live/" in low
                else EvidenceKind.rules_ref_default.value
            )
            return "rules", hint
        return "rules", None
    if "/live/data/" in low:
        return "frame_live", EvidenceKind.events_cur.value
    if "/ref/data/" in low or "/ref/" in low and low.endswith((".parquet", ".csv")):
        hint = EvidenceKind.events_ref_val.value
        if "train" in Path(posix).name.lower():
            hint = EvidenceKind.events_ref_train.value
        return "frame_ref", hint
    if posix.startswith("org-docs/") or "/org-docs/" in posix:
        return "org_doc", None
    return "other", EvidenceKind.other.value


def _table_shape(path: Path) -> tuple[int | None, int | None]:
    """Cheap parquet/csv shape; never raises to caller."""
    try:
        suf = path.suffix.lower()
        if suf == ".parquet":
            import pyarrow.parquet as pq

            pf = pq.ParquetFile(path)
            meta = pf.metadata
            n_rows = int(meta.num_rows) if meta is not None else None
            n_cols = int(meta.num_columns) if meta is not None else len(pf.schema_arrow.names)
            return n_rows, n_cols
        if suf == ".csv":
            import pandas as pd

            df = pd.read_csv(path, nrows=0)
            # row count expensive — leave None
            return None, int(len(df.columns))
    except Exception as exc:  # noqa: BLE001
        logger.debug("catalog shape skip {}: {}", path, exc)
    return None, None


def _should_skip(path: Path, root: Path) -> bool:
    if path.name in _SKIP_NAMES:
        return True
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return True
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(p in _SKIP_DIR_PARTS for p in parts)


def list_present_files(case_root: Path | str) -> list[CatalogFile]:
    """Walk alert + evidence + org-docs; return present files only."""
    root = Path(case_root).resolve()
    files: list[CatalogFile] = []
    seen: set[str] = set()

    candidates: list[Path] = []
    alert = root / "alert.json"
    if alert.is_file():
        candidates.append(alert)
    evidence = root / "evidence"
    if evidence.is_dir():
        candidates.extend(p for p in evidence.rglob("*") if p.is_file())
    org = root / "org-docs"
    if org.is_dir():
        candidates.extend(p for p in org.rglob("*") if p.is_file())

    for path in sorted(candidates, key=lambda p: p.as_posix().lower()):
        if _should_skip(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        class_, kind_hint = _classify(rel)
        fmt = _format_of(path)
        st = path.stat()
        n_rows, n_cols = (None, None)
        if fmt in (EvidenceFormat.parquet,) or path.suffix.lower() == ".csv":
            # Skip shape for huge files (>64 MiB) — size is enough
            if st.st_size <= 64 * 1024 * 1024:
                n_rows, n_cols = _table_shape(path)
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        files.append(
            CatalogFile(
                rel=rel,
                class_=class_,
                format=fmt.value,
                size_bytes=int(st.st_size),
                mtime=mtime,
                n_rows=n_rows,
                n_cols=n_cols,
                kind_hint=kind_hint,
            )
        )
    logger.info("catalog present files n={} case_root={}", len(files), root)
    return files


def _folklore_enabled() -> bool:
    return os.environ.get("INDAGO_CATALOG_FOLKLORE", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def inventory_evidence(case_root: Path | str) -> list[EvidenceRef]:
    """
    EvidenceRefs for tools/materialize.

    Default: one available ref per present file (no unavailable stubs).
    If INDAGO_CATALOG_FOLKLORE=1: also emit unavailable folklore probes (lab).
    """
    root = Path(case_root).resolve()
    of = discover_overfetch(root)
    logger.info("inventory case_root={} folklore={}", root, _folklore_enabled())

    present = list_present_files(root)
    refs: list[EvidenceRef] = []
    for f in present:
        kind = EvidenceKind.other
        if f.kind_hint:
            try:
                kind = EvidenceKind(f.kind_hint)
            except ValueError:
                kind = EvidenceKind.other
        loc = str((root / f.rel).resolve())
        try:
            fmt = EvidenceFormat(f.format)
        except ValueError:
            fmt = EvidenceFormat.unknown
        refs.append(
            EvidenceRef(
                id=f"{kind.value}:{f.rel}",
                kind=kind,
                availability=Availability.available,
                location=loc,
                format=fmt,
                limitations=[],
                extras={
                    "rel": f.rel,
                    "class": f.class_,
                    "size_bytes": f.size_bytes,
                    "n_rows": f.n_rows,
                    "n_cols": f.n_cols,
                },
            )
        )

    if _folklore_enabled():
        known_rels = {f.rel for f in present}
        for kind, candidates, fmt in _CANDIDATES:
            found: Path | None = None
            used_rel = candidates[0]
            for rel in candidates:
                p = resolve_path(root, rel, overfetch=of)
                if p.is_file():
                    found = p
                    used_rel = rel
                    break
            if found is not None:
                if used_rel in known_rels:
                    continue
                refs.append(
                    EvidenceRef(
                        id=kind.value,
                        kind=kind,
                        availability=Availability.available,
                        location=str(found),
                        format=fmt,
                        limitations=["folklore_probe=true"],
                        extras={"rel": used_rel, "folklore": True},
                    )
                )
            else:
                refs.append(
                    EvidenceRef(
                        id=kind.value,
                        kind=kind,
                        availability=Availability.unavailable,
                        location="",
                        format=fmt,
                        limitations=[f"not found; tried {list(candidates)}"],
                        extras={"tried": list(candidates), "folklore": True},
                    )
                )

    man = load_manifest(root)
    if man.get("files") or man.get("copied"):
        logger.info("evidence_manifest present (receipt only; catalog does not depend on it)")
    available = sum(1 for r in refs if r.availability == Availability.available)
    logger.info("inventory done available={}/{}", available, len(refs))
    return refs


def catalog_payload(case_root: Path | str) -> dict[str, Any]:
    """JSON payload for out/catalog.json (schema 2)."""
    root = Path(case_root).resolve()
    files = list_present_files(root)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_root": str(root),
        "catalog_schema": CATALOG_SCHEMA,
        "files": [f.model_dump(by_alias=True) for f in files],
    }
