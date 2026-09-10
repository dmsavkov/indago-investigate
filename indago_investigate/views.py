"""Typed Views + open extras — what tools consume (see context/package/data.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CatalogEntry(BaseModel):
    ref_id: str
    kind: str
    availability: str
    view_id: str | None = None
    roles_detected: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    location: str = ""


class CatalogView(BaseModel):
    generated_at: str
    case_id: str | None = None
    case_root: str = ""
    entries: list[CatalogEntry] = Field(default_factory=list)
    missing_recommended: list[str] = Field(default_factory=list)
    noise_warnings: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class AlertView(BaseModel):
    view_id: str = "alert_v1"
    incident_id: str | None = None
    fired_at: str | None = None
    product: str | None = None
    primary_metric: str | None = None
    primary_status: str | None = None
    window_n: int | None = None
    window_capacity: int | None = None
    co_fired_check_ids: list[str] = Field(default_factory=list)
    label_state_ticket: str | None = None
    champion_version_ticket: int | str | None = None
    baseline_card_id: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class BaselineCardView(BaseModel):
    view_id: str = "baseline_card_v1"
    card_id: str | None = None
    created_at: str | None = None
    registry_version: int | str | None = None
    model_name: str | None = None
    n_val: int | None = None
    pred_mean_val: float | None = None
    approval_rate_val: float | None = None
    rules_bundle_hash: str | None = None
    rules_bundle_id: str | None = None
    git_sha: str | None = None
    n_train_feature_cols: int | None = None
    threshold_digest: dict[str, Any] = Field(default_factory=dict)
    raw_ref_id: str = "monitor_baseline"
    extras: dict[str, Any] = Field(default_factory=dict)


class MonitorCheckRow(BaseModel):
    id: str
    status: str | None = None
    value_summary: str | None = None
    threshold: Any = None
    message: str | None = None


class MonitorSuiteView(BaseModel):
    view_id: str = "monitor_suite_v1"
    checks: list[MonitorCheckRow] = Field(default_factory=list)
    raw_ref_id: str = "monitor_snapshot"
    extras: dict[str, Any] = Field(default_factory=dict)


class FrameView(BaseModel):
    view_id: str
    frame_id: str
    split: str  # cur | ref_val | ref_train
    n_rows: int | None = None
    n_cols: int | None = None
    path_or_handle: str = ""
    column_roles: dict[str, str | list[str]] = Field(default_factory=dict)
    key_columns_present: list[str] = Field(default_factory=list)
    score_column: str | None = None
    limitations: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class LabelView(BaseModel):
    view_id: str = "label_v1"
    state: str = "unknown"
    horizon_days: int | float | None = None
    lag_days: int | float | None = None
    policy: str | None = None
    counts: dict[str, Any] = Field(default_factory=dict)
    extras: dict[str, Any] = Field(default_factory=dict)


class ModelView(BaseModel):
    view_id: str = "model_v1"
    artifact_available: bool = False
    registry_version: int | str | None = None
    alias: str | None = None
    path_or_handle: str | None = None
    feature_cols_ref: str | None = None
    limitations: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class RulesView(BaseModel):
    view_id: str
    bundle_id: str | None = None
    bundle_hash: str | None = None
    source: str  # live | ref_default | ref_loose
    path_or_handle: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)


class QueueChannel(BaseModel):
    name: str
    lag: float | int | None = None
    threshold: float | int | None = None


class QueueView(BaseModel):
    view_id: str = "queue_v1"
    channels: list[QueueChannel] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class InfraView(BaseModel):
    view_id: str = "infra_v1"
    latency_p95: float | None = None
    store_ping_ok: bool | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class FeatureContractView(BaseModel):
    view_id: str = "feature_contract_v1"
    n_train: int | None = None
    n_serve: int | None = None
    online_in_serve_features: bool | None = None
    online_feature_version: str | None = None
    batch_feature_version: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)


class MaterializedBundle(BaseModel):
    """All views produced for a case root."""

    catalog: CatalogView
    alert: AlertView | None = None
    baseline_card: BaselineCardView | None = None
    monitor_suite: MonitorSuiteView | None = None
    frames: list[FrameView] = Field(default_factory=list)
    labels: LabelView | None = None
    model: ModelView | None = None
    rules: list[RulesView] = Field(default_factory=list)
    queues: QueueView | None = None
    infra: InfraView | None = None
    feature_contract: FeatureContractView | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
