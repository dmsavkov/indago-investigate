"""EvidenceRef — access layer for pack / isolate evidence."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Availability(str, Enum):
    available = "available"
    stale = "stale"
    permission_denied = "permission_denied"
    expensive = "expensive"
    unavailable = "unavailable"


class EvidenceKind(str, Enum):
    alert = "alert"
    events_cur = "events_cur"
    events_ref_val = "events_ref_val"
    events_ref_train = "events_ref_train"
    monitor_baseline = "monitor_baseline"
    monitor_snapshot = "monitor_snapshot"
    labels = "labels"
    maturation = "maturation"
    model_artifact = "model_artifact"
    model_meta = "model_meta"
    rules_live = "rules_live"
    rules_ref_default = "rules_ref_default"
    rules_ref_loose = "rules_ref_loose"
    registry_aliases = "registry_aliases"
    telemetry_infra = "telemetry_infra"
    telemetry_queues = "telemetry_queues"
    feature_contract = "feature_contract"
    online_store = "online_store"
    tile_schema = "tile_schema"
    lineage = "lineage"
    orchestration = "orchestration"
    other = "other"


class EvidenceFormat(str, Enum):
    json = "json"
    parquet = "parquet"
    yaml = "yaml"
    pkl = "pkl"
    unknown = "unknown"


class EvidenceRef(BaseModel):
    id: str
    kind: EvidenceKind
    availability: Availability = Availability.unavailable
    location: str = ""
    format: EvidenceFormat = EvidenceFormat.unknown
    schema_hint: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    cost_hint: str | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
