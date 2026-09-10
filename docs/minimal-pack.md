# Minimal evidence pack (Tier 0)

What a contact / new case must bring so INDAGO can run orientation under `INDAGO_BIND=views`.

## Layout

```text
my_case/
  alert.json                 # rumor / KPI blip (JSON or rewrite into out/derived/)
  evidence/
    live/
      data/                  # CUR window (.parquet or .csv)
      models/                # trained joblib/PKL (+ optional feature_cols.json)
      rules/                 # optional live policy
    ref/
      data/                  # REF window (val and/or train)
      models/                # optional
      rules/                 # optional default/loose rules YAML
  org-docs/                  # optional human notes (no hardcoded filenames)
  out/
    views/                   # you author these (paths + column_roles)
  playground/                # optional scratch
```

Copy [`examples/minimal_template/`](../examples/minimal_template/) to start.

## Required vs optional

| Required | Optional |
|----------|----------|
| `alert.json` (or derived alert) | Rules snapshots |
| CUR table | Labels / infra / queue telemetry |
| REF table | `org-docs/` |
| Model PKL for importances / offline rescore / parity | Precomputed importance ranks |
| Views with jailed paths; roles for planes you care about | — |

## Views (binding)

Tools read **Views**, not folklore filenames. See [`views_contract.md`](views_contract.md) and [`examples/views/`](examples/views/).

Minimum for a useful health audit:

- `out/views/frame_cur.json` — `path_or_handle` + roles you need (`score`, `slice_key`, `amount`, …)
- `out/views/frame_ref_val.json` — REF path
- `out/views/model.json` — model path + `feature_cols_ref` when scoring/importances matter

Path-only Frames (empty roles) → **partial** HA with loud `missing_roles`.

## Score sources for cohort tools

- **Column:** bind `column_roles.score` or pass `--score-col`
- **Rescore:** `--rescore --model-path …` — failed predict/feature mismatch → `model_frame_mismatch` (investigation signal)

## Commands (after `pip`/`uv` install)

```bash
indago-catalog my_case
indago-investigate peek-frame my_case --path evidence/live/data/<file> --head 3
indago-investigate validate-views my_case
indago-health-audit my_case --no-plots
indago-investigate topk-importance my_case --model-path evidence/live/models/<model>.pkl
```

## Honesty

UNKNOWN on a plane is success when evidence is missing. Do not invent columns or RCA from the alert text alone.
