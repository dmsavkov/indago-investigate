# Evidence rewrite — ugly customer shapes → INDAGO derived + Views

Tools do **not** JSONPath into arbitrary customer nests. When alert or rules are messy, rewrite once into `out/derived/`, then author thin Views. Skeletons: `_shared/docs/examples/derived/`.

Skip derived only when raw is already loadable / already maps to the View field names below.

Do **not** invent thresholds (use `_shared/docs/thresholds.md`). Do **not** plant `manifest.json` role_hints. `evidence_manifest.json` is a flash **receipt** only — discover models/frames via catalog paths, not receipt flags.

**Trimmed contact layout (humans):** `evidence/live/{data,models,rules}/` vs `evidence/ref/{data,models,rules}/`. Views still bind concrete paths (e.g. `evidence/live/data/events_cur.parquet`). Foreign live rules JSON → `out/derived/rules_live_indago.yaml` before RulesView.

---

## Alert

### Target A — `out/derived/alert_indago.json` (`indago_alert_v1`)

| Field | Type | Required? | Meaning |
|-------|------|-----------|---------|
| `schema` | string | yes | `"indago_alert_v1"` |
| `primary_metric` | string | **yes** | Rumor metric id to falsify |
| `primary_status` | string | yes | e.g. `ALERT` / `WARN` |
| `window_n` | int \| null | high | Events in window |
| `window_capacity` | int \| null | high | Window capacity |
| `co_fired` | array | high | Companion checks (detail lives here) |
| `co_fired[].id` | string | yes per row | Check id |
| `co_fired[].status` | string \| null | no | alert/warn/… |
| `co_fired[].message` | string \| null | no | Short text |
| `incident_id` | string \| null | nice | |
| `fired_at` | string \| null | nice | ISO time |
| `product` | string \| null | nice | |
| `decision_counts` | object | no | e.g. `{"APPROVE": n}` |
| `raw_path` | string | yes | Path to original ticket |
| `extras` | object | no | Non-contract bag |

**Do not put on derived (unless present and useful):** git_sha, registry maps, full monitor suite, coaching notes.

### Target B — thin `out/views/alert.json` (AlertView)

| Field | From derived |
|-------|----------------|
| `primary_metric` / `primary_status` | copy |
| `window_n` / `window_capacity` | copy |
| `co_fired_check_ids` | `[c.id for c in co_fired]` |
| `incident_id` / `fired_at` / `product` | copy if known |
| `extras.raw_path` | original |
| `extras.derived_path` | `out/derived/alert_indago.json` |

Customer tickets may use other names (`metric_key`, `severity`, `also_firing`, `observation_window`, …). Map them — do not expect ieee `alert.json` keys.

---

## Rules (when policy plane is in scope)

### Target A — `out/derived/rules_live_indago.yaml` (INDAGO dialect)

```yaml
version: <optional string>
pre_model:                 # optional
  - id: <str>
    when: "<python expr over context / score>"
    decision: APPROVE|DECLINE|REVIEW|...
post_model:                # optional
  - id: <str>
    when: "<python expr>"
    decision: <str>
default_decision: APPROVE  # required fallback
```

`when` expressions are evaluated by the package rules engine (`score`, `context`, …). Map vendor fields (`prechecks`, `score_gates`, `else_outcome`, nested policy JSON, …) into this shape. **Do not** leave the live rules as a YAML string inside JSON — produce a real `.yaml` file.

### Target B — `out/views/rules_live.json` (RulesView)

| Field | Meaning |
|-------|---------|
| `source` | `live` (or `ref_default` / `ref_loose` for contrast files) |
| `path_or_handle` | Prefer `out/derived/rules_live_indago.yaml` |
| `bundle_hash` | optional; tools may compute |
| `extras.raw_path` | original customer rules file |

If raw is **already** this YAML dialect, RulesView may point at the raw path (skip derived).

REF default rules (when present for contrast) stay as a separate file — do not confuse with live.

---

## Frames / models (no derived rewrite)

| Asset | What to do |
|-------|------------|
| Tables | FrameView `path_or_handle` + `column_roles` after peek. Formats: **parquet, csv, feather**. |
| Model | ModelView → jailed path to trained joblib PKL. Native importances: `feature_importances_`, `|coef_|`, NB log-odds. Else `unsupported` (no permutation). |
| Offline score | Currently expects **parquet** + joblib pipeline the scorer can run. |

---

## Suggested order

1. Catalog → find raw alert / rules / frames / model paths.  
2. If alert/rules ugly → write `out/derived/*` then Views.  
3. Path-only FrameViews → validate-views → health-audit → peek → fill roles → re-audit.

Examples: `examples/derived/alert_indago.json`, `examples/derived/rules_live_indago.yaml`, `examples/views/`.
