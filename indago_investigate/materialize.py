"""Materialize typed Views from EvidenceRefs / raw files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from indago_investigate.inventory import RECOMMENDED_KINDS, inventory_evidence
from indago_investigate.paths import try_load_json
from indago_investigate.refs import Availability, EvidenceKind, EvidenceRef
from indago_investigate.views import (
    AlertView,
    BaselineCardView,
    CatalogEntry,
    CatalogView,
    FeatureContractView,
    FrameView,
    InfraView,
    LabelView,
    MaterializedBundle,
    ModelView,
    MonitorCheckRow,
    MonitorSuiteView,
    QueueChannel,
    QueueView,
    RulesView,
)

_ROLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "decision": ("decision",),
    # Live CUR often stores model output as prediction/risk_score, not "score".
    "score": ("prediction", "risk_score", "offline_score", "score", "pred", "y_pred", "fraud_score"),
    "policy_hash": ("rules_bundle_hash",),
    "slice_key": ("card1",),
    # Prefer numeric tile features; boolean flag is documented separately in extras.
    "online_velocity": (
        "online_card1_txn_count_day",
        "online_uid_txn_count_day",
        "online_velocity_zero_at_fetch",
    ),
    "product": ("ProductCD",),
    "amount": ("TransactionAmt",),
    "timestamp": ("TransactionDT", "event_time", "timestamp", "ts"),
}


def _ref_map(refs: list[EvidenceRef]) -> dict[EvidenceKind, EvidenceRef]:
    return {r.kind: r for r in refs}


def _summarize_value(value: Any, *, max_len: int = 120) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float, bool, str)):
        s = str(value)
        return s if len(s) <= max_len else s[: max_len - 3] + "..."
    if isinstance(value, dict):
        keys = list(value.keys())[:8]
        return f"dict(keys={keys})"
    if isinstance(value, list):
        return f"list(n={len(value)})"
    return type(value).__name__


def _materialize_alert(ref: EvidenceRef) -> AlertView | None:
    data = try_load_json(Path(ref.location))
    if not data:
        return None
    failed = data.get("failed_checks") or []
    primary = data.get("metric")
    primary_status = None
    co_ids: list[str] = []
    for ch in failed:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "")
        if cid:
            co_ids.append(cid)
        if cid == primary:
            primary_status = ch.get("status")
    # keep full failed_checks only in extras (toxic raw)
    extras = {
        "failed_checks": failed,
        "raw_keys": sorted(data.keys()),
    }
    return AlertView(
        incident_id=data.get("incident_id"),
        fired_at=data.get("fired_at"),
        product=data.get("product"),
        primary_metric=primary,
        primary_status=primary_status or ("alert" if failed else None),
        window_n=data.get("n_events"),
        window_capacity=data.get("window"),
        co_fired_check_ids=co_ids,
        label_state_ticket=data.get("label_state"),
        champion_version_ticket=data.get("champion_version"),
        baseline_card_id=data.get("monitoring_baseline"),
        extras=extras,
    )


def _materialize_baseline(ref: EvidenceRef) -> BaselineCardView | None:
    data = try_load_json(Path(ref.location))
    if not data:
        return None
    train_cols = data.get("train_feature_cols") or data.get("feature_cols") or []
    thresholds = data.get("thresholds") if isinstance(data.get("thresholds"), dict) else {}
    # strip huge lists from default projection
    digest = {k: thresholds[k] for k in list(thresholds)[:20]} if thresholds else {}
    return BaselineCardView(
        card_id=data.get("monitoring_baseline") or data.get("baseline_id") or data.get("product"),
        created_at=data.get("created_at"),
        registry_version=data.get("registry_version"),
        model_name=data.get("model_name"),
        n_val=data.get("n_val"),
        pred_mean_val=data.get("pred_mean_val"),
        approval_rate_val=data.get("approval_rate_val"),
        rules_bundle_hash=data.get("rules_bundle_hash"),
        rules_bundle_id=data.get("rules_bundle_id"),
        git_sha=data.get("git_sha"),
        n_train_feature_cols=len(train_cols) if isinstance(train_cols, list) else None,
        threshold_digest=digest,
        raw_ref_id=ref.id,
        extras={"raw_byte_hint": Path(ref.location).stat().st_size if Path(ref.location).is_file() else None},
    )


def _materialize_suite(ref: EvidenceRef) -> MonitorSuiteView | None:
    data = try_load_json(Path(ref.location))
    if not data:
        return None
    checks_raw = data.get("checks") or data.get("failed_checks") or data.get("results") or []
    if isinstance(data.get("suite"), list):
        checks_raw = data["suite"]
    rows: list[MonitorCheckRow] = []
    if isinstance(checks_raw, dict):
        for cid, payload in checks_raw.items():
            if isinstance(payload, dict):
                rows.append(
                    MonitorCheckRow(
                        id=str(cid),
                        status=payload.get("status"),
                        value_summary=_summarize_value(payload.get("value")),
                        threshold=payload.get("threshold"),
                        message=payload.get("message"),
                    )
                )
            else:
                rows.append(MonitorCheckRow(id=str(cid), value_summary=_summarize_value(payload)))
    elif isinstance(checks_raw, list):
        for ch in checks_raw:
            if not isinstance(ch, dict):
                continue
            rows.append(
                MonitorCheckRow(
                    id=str(ch.get("id") or ch.get("name") or ""),
                    status=ch.get("status"),
                    value_summary=_summarize_value(ch.get("value")),
                    threshold=ch.get("threshold"),
                    message=ch.get("message"),
                )
            )
    return MonitorSuiteView(checks=rows, raw_ref_id=ref.id, extras={"n_checks": len(rows)})


def _materialize_frame(ref: EvidenceRef, *, split: str, view_id: str) -> FrameView:
    path = Path(ref.location)
    n_rows = n_cols = None
    roles: dict[str, str | list[str]] = {}
    keys_present: list[str] = []
    limitations: list[str] = []
    extras: dict[str, Any] = {}
    score_col = None
    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        n_rows = pf.metadata.num_rows if pf.metadata else None
        schema_names = [f.name for f in pf.schema_arrow]
        n_cols = len(schema_names)
        name_set = set(schema_names)
        for role, cols in _ROLE_COLUMNS.items():
            hit = [c for c in cols if c in name_set]
            if not hit:
                continue
            if role == "online_velocity":
                # Prefer numeric tiles; keep flag as companion note
                numeric = [c for c in hit if c != "online_velocity_zero_at_fetch"]
                flag = "online_velocity_zero_at_fetch" if "online_velocity_zero_at_fetch" in hit else None
                if numeric:
                    roles[role] = numeric[0] if len(numeric) == 1 else numeric
                elif flag:
                    roles[role] = flag
                if flag:
                    extras["online_velocity_zero_flag"] = flag
                    limitations.append(
                        "online_velocity_zero_at_fetch is a boolean flag "
                        "(1=velocity was zero at fetch); do not use profile zero_rate on it "
                        "as the monitor metric — use mean(flag) or the monitor check zero_rate"
                    )
            else:
                roles[role] = hit[0] if len(hit) == 1 else hit
            if role in ("slice_key", "product", "decision", "policy_hash", "timestamp"):
                for h in hit:
                    if h not in keys_present:
                        keys_present.append(h)
        for c in ("card1", "ProductCD", "decision", "rules_bundle_hash"):
            if c in name_set and c not in keys_present:
                keys_present.append(c)
        for c in (
            "prediction",
            "risk_score",
            "offline_score",
            "score",
            "pred",
            "y_pred",
            "fraud_score",
        ):
            if c in name_set:
                score_col = c
                if "score" not in roles:
                    roles["score"] = c
                break
        if score_col:
            extras["score_column_source"] = score_col
        # Small schema sample for peek-less orientation (names only)
        extras["column_sample"] = schema_names[:24]
        if n_rows is not None and n_rows < 500:
            limitations.append(f"small-n={n_rows}")
    except Exception as exc:  # noqa: BLE001 — soft frame meta
        limitations.append(f"parquet_meta_failed: {exc}")
    return FrameView(
        view_id=view_id,
        frame_id=ref.id,
        split=split,
        n_rows=n_rows,
        n_cols=n_cols,
        path_or_handle=str(path),
        column_roles=roles,
        key_columns_present=keys_present,
        score_column=score_col,
        limitations=limitations,
        extras=extras,
    )


def _materialize_labels(ref: EvidenceRef) -> LabelView:
    data = try_load_json(Path(ref.location)) or {}
    state = str(data.get("state") or data.get("label_state") or data.get("status") or "unknown")
    return LabelView(
        state=state,
        horizon_days=data.get("horizon_days") or data.get("horizon"),
        lag_days=data.get("lag_days") or data.get("label_lag_days"),
        policy=data.get("policy") or data.get("maturation_policy"),
        counts={k: data[k] for k in ("awaiting", "ready", "n_ready", "n_awaiting") if k in data},
        extras={"raw_keys": sorted(data.keys())},
    )


def _materialize_model(artifact: EvidenceRef | None, meta: EvidenceRef | None) -> ModelView:
    available = bool(artifact and artifact.availability == Availability.available)
    registry = alias = None
    if meta and meta.availability == Availability.available:
        data = try_load_json(Path(meta.location)) or {}
        models = data.get("models") or []
        if models and isinstance(models[0], dict):
            registry = models[0].get("registry_version")
            alias = models[0].get("alias")
        registry = registry or data.get("registry_version")
        alias = alias or data.get("alias")
    limitations: list[str] = []
    if not available:
        limitations.append("model artifact unavailable — offline score blocked")
    return ModelView(
        artifact_available=available,
        registry_version=registry,
        alias=alias,
        path_or_handle=artifact.location if artifact and available else None,
        limitations=limitations,
    )


def _materialize_rules(ref: EvidenceRef, source: str) -> RulesView:
    return RulesView(
        view_id=f"rules_{source}",
        source=source,
        path_or_handle=ref.location,
        extras={},
    )


def _materialize_queues(ref: EvidenceRef) -> QueueView:
    data = try_load_json(Path(ref.location)) or {}
    channels: list[QueueChannel] = []
    # common lab shapes
    mapping = [
        ("inference", ("inference_lag", "inference_consumer_lag", "scoring_lag")),
        ("tile", ("tile_lag", "tile_kafka_lag", "kafka_consumer_lag", "stream_lag")),
    ]
    for name, keys in mapping:
        for k in keys:
            if k in data:
                channels.append(QueueChannel(name=name, lag=data.get(k), threshold=data.get(f"{k}_threshold")))
                break
    if not channels and isinstance(data.get("channels"), list):
        for ch in data["channels"]:
            if isinstance(ch, dict):
                channels.append(
                    QueueChannel(
                        name=str(ch.get("name") or "unknown"),
                        lag=ch.get("lag"),
                        threshold=ch.get("threshold"),
                    )
                )
    if len(channels) < 2:
        # still expose raw keys so agent sees unsplit risk
        pass
    return QueueView(channels=channels, extras={"raw_keys": sorted(data.keys())})


def _materialize_infra(ref: EvidenceRef) -> InfraView:
    data = try_load_json(Path(ref.location)) or {}
    p95 = data.get("latency_p95") or data.get("p95") or data.get("authorize_p95_ms")
    ping = data.get("redis_ping_ok") or data.get("store_ping_ok") or data.get("redis_ok")
    if isinstance(ping, str):
        ping = ping.lower() in ("ok", "true", "1", "yes")
    return InfraView(latency_p95=p95, store_ping_ok=ping if isinstance(ping, bool) else None, extras={"raw_keys": sorted(data.keys())})


def _materialize_feature_contract(ref: EvidenceRef) -> FeatureContractView:
    data = try_load_json(Path(ref.location)) or {}
    train = data.get("train_feature_cols") or data.get("feature_cols") or []
    serve = data.get("serve_feature_cols") or []
    return FeatureContractView(
        n_train=len(train) if isinstance(train, list) else data.get("n_train"),
        n_serve=len(serve) if isinstance(serve, list) else data.get("n_serve"),
        online_in_serve_features=data.get("online_in_serve_features"),
        online_feature_version=data.get("online_feature_version"),
        batch_feature_version=data.get("batch_feature_version"),
        extras={"raw_keys": sorted(data.keys())},
    )


def materialize_views(
    case_root: Path | str,
    *,
    refs: list[EvidenceRef] | None = None,
) -> MaterializedBundle:
    root = Path(case_root).resolve()
    refs = refs if refs is not None else inventory_evidence(root)
    by = _ref_map(refs)
    logger.info("materialize_views case_root={}", root)

    alert = baseline = suite = labels = model = queues = infra = fc = None
    frames: list[FrameView] = []
    rules: list[RulesView] = []
    noise: list[str] = []
    view_ids: dict[str, str] = {}

    if (r := by.get(EvidenceKind.alert)) and r.availability == Availability.available:
        alert = _materialize_alert(r)
        if alert:
            view_ids[r.id] = alert.view_id
            noise.append("alert failed_checks also kept in extras; primary_metric remains rumor until oriented")

    if (r := by.get(EvidenceKind.monitor_baseline)) and r.availability == Availability.available:
        baseline = _materialize_baseline(r)
        if baseline:
            view_ids[r.id] = baseline.view_id
            noise.append("optional BaselineCardView projected; raw baseline JSON remains readable at EvidenceRef location")

    if (r := by.get(EvidenceKind.monitor_snapshot)) and r.availability == Availability.available:
        suite = _materialize_suite(r)
        if suite:
            view_ids[r.id] = suite.view_id
            noise.append("optional MonitorSuiteView summaries; raw snapshot remains readable")

    for kind, split, vid in (
        (EvidenceKind.events_cur, "cur", "frame_cur"),
        (EvidenceKind.events_ref_val, "ref_val", "frame_val"),
        (EvidenceKind.events_ref_train, "ref_train", "frame_train"),
    ):
        r = by.get(kind)
        if r and r.availability == Availability.available:
            fv = _materialize_frame(r, split=split, view_id=vid)
            frames.append(fv)
            view_ids[r.id] = fv.view_id

    if (r := by.get(EvidenceKind.labels)) and r.availability == Availability.available:
        labels = _materialize_labels(r)
        view_ids[r.id] = labels.view_id

    art = by.get(EvidenceKind.model_artifact)
    meta = by.get(EvidenceKind.model_meta)
    if art or meta:
        model = _materialize_model(art, meta)
        view_ids["model"] = model.view_id

    for kind, source in (
        (EvidenceKind.rules_live, "live"),
        (EvidenceKind.rules_ref_default, "ref_default"),
        (EvidenceKind.rules_ref_loose, "ref_loose"),
    ):
        r = by.get(kind)
        if r and r.availability == Availability.available:
            rv = _materialize_rules(r, source)
            rules.append(rv)
            view_ids[r.id] = rv.view_id

    if (r := by.get(EvidenceKind.telemetry_queues)) and r.availability == Availability.available:
        queues = _materialize_queues(r)
        view_ids[r.id] = queues.view_id
        if len(queues.channels) < 2:
            noise.append("queue telemetry may be unsplit — verify inference vs tile channels")

    if (r := by.get(EvidenceKind.telemetry_infra)) and r.availability == Availability.available:
        infra = _materialize_infra(r)
        view_ids[r.id] = infra.view_id

    if (r := by.get(EvidenceKind.feature_contract)) and r.availability == Availability.available:
        fc = _materialize_feature_contract(r)
        view_ids[r.id] = fc.view_id

    missing = [
        k.value
        for k in RECOMMENDED_KINDS
        if by.get(k) is None or by[k].availability != Availability.available
    ]

    case_id = None
    if alert and alert.incident_id:
        case_id = alert.incident_id
    if (root / "evidence_manifest.json").is_file():
        try:
            case_id = json.loads((root / "evidence_manifest.json").read_text(encoding="utf-8")).get("case_id") or case_id
        except json.JSONDecodeError:
            pass

    entries: list[CatalogEntry] = []
    for r in refs:
        vid = view_ids.get(r.id)
        if r.kind in (EvidenceKind.model_artifact, EvidenceKind.model_meta) and model:
            vid = model.view_id
        roles: list[str] = []
        fv = next((f for f in frames if f.frame_id == r.id), None)
        if fv:
            roles = list(fv.column_roles.keys())
        entries.append(
            CatalogEntry(
                ref_id=r.id,
                kind=r.kind.value,
                availability=r.availability.value,
                view_id=vid,
                roles_detected=roles,
                limitations=list(r.limitations),
                location=r.location,
            )
        )

    catalog = CatalogView(
        generated_at=datetime.now(timezone.utc).isoformat(),
        case_id=case_id,
        case_root=str(root),
        entries=entries,
        missing_recommended=missing,
        noise_warnings=noise,
    )

    return MaterializedBundle(
        catalog=catalog,
        alert=alert,
        baseline_card=baseline,
        monitor_suite=suite,
        frames=frames,
        labels=labels,
        model=model,
        rules=rules,
        queues=queues,
        infra=infra,
        feature_contract=fc,
    )
