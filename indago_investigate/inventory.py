"""Inventory EvidenceRefs for a case root (lab pack or isolate flash)."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from indago_investigate.paths import discover_overfetch, load_manifest, resolve_path
from indago_investigate.refs import Availability, EvidenceFormat, EvidenceKind, EvidenceRef

# (kind, preferred relative paths to try in order, format)
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
        (
            "evidence/ref/ieee/rules/rules_loose_ref.yaml",
        ),
        EvidenceFormat.yaml,
    ),
    (
        EvidenceKind.registry_aliases,
        (
            "evidence/aliases.json",
            "workspace/registry/aliases.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.telemetry_infra,
        (
            "evidence/infra_summary.json",
            "workspace/telemetry/infra_summary.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.telemetry_queues,
        (
            "evidence/queue_backlog.json",
            "workspace/telemetry/queue_backlog.json",
        ),
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
        (
            "evidence/online_snapshot.json",
            "workspace/feature-store/online_snapshot.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.tile_schema,
        (
            "evidence/tile_schema.json",
            "workspace/feature-store/tile_schema.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.orchestration,
        (
            "evidence/dbt_run_summary.json",
            "workspace/orchestration/dbt_run_summary.json",
        ),
        EvidenceFormat.json,
    ),
    (
        EvidenceKind.lineage,
        (
            "evidence/git_snapshot.json",
            "evidence/ref/ieee/lineage/git_snapshot.json",
        ),
        EvidenceFormat.json,
    ),
]

# Always expected for Stage 1 / package MVP (user: include model + all refs).
RECOMMENDED_KINDS: tuple[EvidenceKind, ...] = (
    EvidenceKind.alert,
    EvidenceKind.events_cur,
    EvidenceKind.events_ref_val,
    EvidenceKind.events_ref_train,
    EvidenceKind.monitor_baseline,
    EvidenceKind.monitor_snapshot,
    EvidenceKind.model_artifact,
    EvidenceKind.labels,
    EvidenceKind.registry_aliases,
    EvidenceKind.telemetry_queues,
)


def inventory_evidence(case_root: Path | str) -> list[EvidenceRef]:
    """Scan case_root and return EvidenceRefs (available or unavailable). Case-local only."""
    root = Path(case_root).resolve()
    of = discover_overfetch(root)
    logger.info("inventory case_root={} overfetch_allowed={}", root, of is not None)

    refs: list[EvidenceRef] = []
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
            refs.append(
                EvidenceRef(
                    id=kind.value,
                    kind=kind,
                    availability=Availability.available,
                    location=str(found),
                    format=fmt,
                    limitations=[],
                    extras={"rel": used_rel},
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
                    extras={"tried": list(candidates)},
                )
            )
    available = sum(1 for r in refs if r.availability == Availability.available)
    # B.6: also emit unclassified files under evidence/** (+ root alert already covered)
    known_locs = {Path(r.location).resolve() for r in refs if r.location}
    evidence = root / "evidence"
    if evidence.is_dir():
        for path in sorted(evidence.rglob("*")):
            if not path.is_file():
                continue
            if path.resolve() in known_locs:
                continue
            # skip playground mirrors if any
            if "playground" in path.parts:
                continue
            suf = path.suffix.lower()
            fmt = {
                ".json": EvidenceFormat.json,
                ".parquet": EvidenceFormat.parquet,
                ".pkl": EvidenceFormat.pkl,
                ".yaml": EvidenceFormat.yaml,
                ".yml": EvidenceFormat.yaml,
            }.get(suf, EvidenceFormat.unknown)
            rel = path.relative_to(root).as_posix()
            refs.append(
                EvidenceRef(
                    id=f"unclassified:{rel}",
                    kind=EvidenceKind.other,
                    availability=Availability.available,
                    location=str(path),
                    format=fmt,
                    limitations=["kind_inferred=true; unclassified evidence walk"],
                    extras={"rel": rel, "kind_inferred": True, "unclassified": True},
                )
            )
    # Manifest kinds override note
    man = load_manifest(root)
    if man.get("files"):
        logger.info("manifest.json files[] present (n={})", len(man["files"]))
    logger.info("inventory done available={}/{}", available, len(refs))
    return refs
