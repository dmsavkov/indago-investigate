# Views contract (agent-facing)

**Policy:** [`views_policy.md`](views_policy.md) — Option C.  
**Types SoT:** `package/indago_investigate/views.py`.  
**Closed roles:** §B.1 / `package/indago_investigate/roles.py` (`COLUMN_ROLE_NAMES`).  
**Spec tables:** `context/package/mvp-generality.md` §B.12 (this file is the flashed copy agents use).

Flash copies this file to isolate `_shared/docs/views_contract.md`. Example JSON also lives under `package/docs/examples/views/` (docs only — not live case `out/views/`).

## Workflow

1. **Inventory** — `indago-catalog .` → read `out/catalog.md` (raw EvidenceRefs). `evidence_manifest.json` is a flash receipt, not the working catalog.
2. **Author Views** — write `out/views/<default filename>.json` using the kinds below. Paths are **relative to case root** and path-jailed.
3. **Validate** — `indago-investigate validate-views .` before trusting role-gated planes.
4. **Orient** — `indago-health-audit . --profile ieee_flash`. If a plane is `UNKNOWN` with `missing_roles`, bind those roles and re-run — do not invent metrics.
5. Open raw evidence whenever useful. Inventory does not ban raw reads.

Do **not** run ops ieee bind / `indago-ops-bind-ieee` / `indago-materialize` from the agent allowlist.

**Ugly alert / rules:** do not JSONPath from tools into customer nests. Rewrite once into `out/derived/` (see ACTIVATION + `examples/derived/`), then author thin Views that point at derived (and `extras.raw_path`).

---

## Fixed kinds vs expandable instances

| Fixed (versioned) | Open |
|-------------------|------|
| Kind schemas below | How many FrameViews; which files map to which kind |
| Role vocabulary (`COLUMN_ROLE_NAMES`) | Which physical column fills a role |

Do **not** invent new kinds ad hoc. New kind = version bump + tool support. Extra tables = extra FrameView files with distinct `view_id`.

---

## Default filenames under `out/views/`

| File | Kind | Logical id |
|------|------|------------|
| `frame_cur.json` | FrameView | `cur` |
| `frame_ref_val.json` | FrameView | `ref_val` |
| `frame_ref_train.json` | FrameView | `ref_train` |
| `alert.json` | AlertView | `alert` |
| `baseline_card.json` | BaselineCardView | `baseline` |
| `monitor_suite.json` | MonitorSuiteView | `monitor` |
| `labels.json` | LabelView | `labels` |
| `model.json` | ModelView | `model` |
| `rules_live.json` / `rules_default.json` / `rules_loose.json` | RulesView | by `source` |
| `queue.json` | QueueView | `queue` |
| `infra.json` | InfraView | `infra` |
| `feature_contract.json` | FeatureContractView | `feature_contract` |
| `bundle.json` | MaterializedBundle index (optional) | — |

Tools resolve by: `--view <path>`, or `--frame cur|ref_val|ref_train`, or default filename under `--views-dir` (default `out/views`).

---

## `column_roles` (on FrameView)

Keys ⊆ closed vocabulary: `score`, `decision`, `slice_key`, `amount`, `product`, `policy_hash`, `timestamp`, `online_velocity`.

Value = `string` (column name) or `string[]` (multi-col roles, e.g. `online_velocity`).  
Unknown key → validate-views ERROR.

Prefer roles in `column_roles`. `score_column` is a legacy alias for `column_roles.score` — set **both** consistently or only `column_roles.score` (validators accept either; tools prefer `column_roles.score` then `score_column`).

---

## Field tables

Required? = for a *useful* view of that kind. Empty `column_roles` is allowed; role-gated planes stay UNKNOWN until filled.

### FrameView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | yes | Stable id, e.g. `frame_cur_v1` |
| `frame_id` | string | yes | EvidenceRef id or logical name |
| `split` | string | yes | `cur` \| `ref_val` \| `ref_train` |
| `n_rows` | int \| null | no | Row count if known |
| `n_cols` | int \| null | no | Column count if known |
| `path_or_handle` | string | yes | Path relative to case root (jailed); **parquet / csv / feather** |
| `column_roles` | object | no* | Role → column name(s); *empty → planes UNKNOWN |
| `key_columns_present` | string[] | no | Convenience list |
| `score_column` | string \| null | no | Legacy; prefer `column_roles.score` |
| `limitations` | string[] | no | e.g. `small-n` |
| `extras` | object | no | Non-contract bag |

**Example:** see `examples/views/frame_cur.json`.

### AlertView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `alert_v1` |
| `incident_id` | string \| null | no | |
| `fired_at` | string \| null | no | ISO time |
| `product` | string \| null | no | |
| `primary_metric` | string \| null | no | Ticket metric id |
| `primary_status` | string \| null | no | |
| `window_n` | int \| null | no | |
| `window_capacity` | int \| null | no | |
| `co_fired_check_ids` | string[] | no | |
| `label_state_ticket` | string \| null | no | |
| `champion_version_ticket` | int\|string\|null | no | |
| `baseline_card_id` | string \| null | no | |
| `extras` | object | no | May hold `raw_path`, `derived_path` (`out/derived/alert_indago.json`) |

When raw alert is nested/ugly: write `examples/derived/alert_indago.json`-shaped file under `out/derived/`, then this thin View. Co-fire **detail** (status/message) lives on derived; View keeps id list.

**Example:** `examples/views/alert.json`.

### BaselineCardView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `baseline_card_v1` |
| `card_id` | string \| null | no | |
| `created_at` | string \| null | no | |
| `registry_version` | int\|string\|null | no | |
| `model_name` | string \| null | no | |
| `n_val` | int \| null | no | |
| `pred_mean_val` | float \| null | no | |
| `approval_rate_val` | float \| null | no | |
| `rules_bundle_hash` | string \| null | no | |
| `rules_bundle_id` | string \| null | no | |
| `git_sha` | string \| null | no | |
| `n_train_feature_cols` | int \| null | no | |
| `threshold_digest` | object | no | Short digest only |
| `raw_ref_id` | string | no | default `monitor_baseline` |
| `extras` | object | no | Prefer `raw_path` here |

**Example:** `examples/views/baseline_card.json`.

### MonitorSuiteView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `monitor_suite_v1` |
| `checks` | array of `{id, status, value_summary, threshold, message}` | no | Short rows only |
| `raw_ref_id` | string | no | |
| `extras` | object | no | |

**Example:** `examples/views/monitor_suite.json`.

### LabelView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `label_v1` |
| `state` | string | yes | `absent` \| `partial` \| `immature` \| `ready` \| `unknown` \| … |
| `horizon_days` | number \| null | no | |
| `lag_days` | number \| null | no | |
| `policy` | string \| null | no | |
| `counts` | object | no | |
| `extras` | object | no | |

**Example:** `examples/views/labels.json`.

### ModelView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `model_v1` |
| `artifact_available` | bool | yes | |
| `registry_version` | int\|string\|null | no | |
| `alias` | string \| null | no | |
| `path_or_handle` | string \| null | yes if available | Jailed path to PKL/ONNX/etc. |
| `feature_cols_ref` | string \| null | no | Path or id of feature list |
| `limitations` | string[] | no | |
| `extras` | object | no | |

**Example:** `examples/views/model.json`.

### RulesView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | yes | e.g. `rules_live_v1` |
| `bundle_id` | string \| null | no | |
| `bundle_hash` | string \| null | no | |
| `source` | string | yes | `live` \| `ref_default` \| `ref_loose` |
| `path_or_handle` | string | yes | Prefer `out/derived/rules_live_indago.yaml` when raw is foreign |
| `extras` | object | no | May hold `raw_path`, `rewrite` |

Ugly/foreign rules → rewrite to INDAGO dialect (`examples/derived/rules_live_indago.yaml`), then point here.

**Example:** `examples/views/rules_live.json`.

### QueueView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `queue_v1` |
| `channels` | `{name, lag, threshold}[]` | no | Never collapse tile vs inference |
| `extras` | object | no | |

**Example:** `examples/views/queue.json`.

### InfraView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `infra_v1` |
| `latency_p95` | float \| null | no | |
| `store_ping_ok` | bool \| null | no | |
| `extras` | object | no | |

**Example:** `examples/views/infra.json`.

### FeatureContractView

| Field | Type | Req? | Meaning |
|-------|------|-------|---------|
| `view_id` | string | no | default `feature_contract_v1` |
| `n_train` | int \| null | no | |
| `n_serve` | int \| null | no | |
| `online_in_serve_features` | bool \| null | no | |
| `online_feature_version` | string \| null | no | |
| `batch_feature_version` | string \| null | no | |
| `extras` | object | no | |

**Example:** `examples/views/feature_contract.json`.

---

## Minimal Views for a full health_audit attempt

| View | If missing |
|------|------------|
| `frame_cur` with path | Cannot orient event window → hard limitation |
| `frame_ref_val` and/or `frame_ref_train` | Dual-ref / PSI sections UNKNOWN |
| Roles on frames (slice_key/product, amount, score) | Named plane UNKNOWN + missing-role message |
| `model` or precomputed scores | Model plane UNKNOWN |
| `rules_*` | Decision/policy plane degraded |
| `alert` / `baseline_card` | Useful digests; not all checks blocked |

---

## Health_audit missing-role shape

When a plane cannot run, JSON includes:

```json
{
  "status": "UNKNOWN",
  "finding": "short human summary",
  "missing_roles": ["slice_key", "product"],
  "missing_inputs": ["frame_cur.column_roles.slice_key"],
  "hints": ["Set column_roles in out/views/frame_cur.json", "Or pass --key to slice tools"]
}
```

`health_audit.md` prints `missing_roles` / `hints` under each UNKNOWN plane.

---

## Package defaults

- Do **not** auto-dump BaselineCard / MonitorSuite into the inventory catalog.
- Do **not** claim vendor column names are universal without an explicit bind.
- Flash default Views seed is **empty** (or templates) — not ops-filled IEEE maps. Ops seed is lab dogfood only.
