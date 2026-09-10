# Investigation package CLI

**Hard rules**

1. Call tools as `indago-*` from **any** working directory (they must be on PATH). Do not `cd` into other repos to find CLIs. Do not invent host project paths.
2. The first path argument is always the **case root** (folder with `alert.json`). Prefer `.` when your shell is already in that folder; otherwise use an **absolute** path. Never pass a bare case id.
3. Catalog / reports are **computed** by these CLIs into `out/` — nothing is pre-built at flash except evidence + docs.
4. **Allowlist only.** The tables below are the _only_ investigation commands you may run. If another `indago-*` binary exists on PATH (`indago-ops-eval`, `indago-validate-pack`, `indago-score`, `indago-run`, `indago-tournament`, `indago-view`, …), **ignore it** — those are parent/lab tools, not for this case. Do not search the host for “more tools.”
5. Confirm the live menu with `indago-investigate --list`. It must include `validate-judgment`, `validate-views`, and `peek-frame`. If it does not, stop and tell the operator the PATH CLI is stale (package not installed or wrong env — follow the package installation guide).
6. **Never delete `out/judgment*`.** Investigation CLIs only _create_ files under `out/` — they do **not** wipe `out/`. Do not browse other case folders for prior runs.

You only need the investigation tools below. Evidence is **case-local** under `evidence/`. Optional `org-docs/` is human vocabulary (read if present — useful, not complete). Author Views from `views_contract.md` (this folder) before audit/L1. Path-only Frames → **partial** HA; filled `column_roles` → full planes. Catalog / peek / validate-alert work first. **Never** run ops bind. After authoring Views, run `validate-views` and clear ERRORs before HA/L1.

**Suggested capability loop:** catalog → rewrite ugly alert/rules into `out/derived/` when needed (see ACTIVATION) → path-only Views + validate-views → health-audit (read missings) → peek-frame (real column names) → topk-importance --model-path … → fill `column_roles` → validate-views → re-audit → L1/L2 → validate-judgment.

Skeletons: `examples/derived/` and `examples/views/` (this folder). Field tables: `rewrite_views.md`. Thresholds: `thresholds.md` (do not invent).

**What to open:** `out/catalog.md` and `out/health_audit.md` for orientation. After an L1/L2 tool, open **`out/reports/<tool>.json`**. Close twin remains `judgment.md` + `judgment_struct.json`.

```powershell
# From the case folder:
indago-investigate --list
indago-catalog .
indago-investigate peek-frame . --path evidence/live/data/events_cur.parquet --head 3
indago-investigate validate-views .
indago-health-audit . --profile ieee_flash
indago-investigate topk-importance . --model-path <path-from-catalog>
```

## Close gate (mandatory)

After writing `out/judgment.md` + `out/judgment_struct.json`:

```powershell
indago-investigate validate-judgment .
```

- Reads the twin, checks schema shape + closed tags from `claim_tags.json`.
- Prints a self-contained critique (Problem / Why / Fix). Also writes `out/reports/validate_judgment.md`.
- Exit code **0** = OK to close; **non-zero** = fix the struct and re-run until OK.
- This is **not** gold scoring and **not** `indago-validate-pack` (that validates lab packs — never use it here).

## Where outputs land

| Path                                            | What                                                                                                    |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `out/catalog.md` + `out/catalog.json`           | Evidence inventory (written by `indago-catalog`) — **read the `.md`**                                   |
| `out/health_audit.md` + `out/health_audit.json` | Orientation audit — **read the `.md`**                                                                  |
| `out/reports/<tool>.json`                       | L0–L2 tool results (**JSON only**; no parallel `.md`)                                                   |
| `out/reports/validate_judgment.md`              | Close-gate critique (exception: human MD)                                                               |
| `out/judgment.md` + `out/judgment_struct.json`  | End-of-run close only (not first act)                                                                   |
| `out/views/`                                    | Agent-authored Views (flash default empty) — follow `views_contract.md`; validate with `validate-views` |
| `out/derived/`                                  | Agent rewrite of ugly alert/rules (`alert_indago.json`, `rules_live_indago.yaml`) — see ACTIVATION      |
| `org-docs/`                                     | Optional human/org docs (flash may seed); no hardcoded filenames in tools                               |

---

## L0 — orientation

| What it does                                                                     | Command                                                              | Writes                                         |
| -------------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------- |
| Lists available evidence refs and paths                                          | `indago-catalog $CASE`                                               | `out/catalog.*`                                |
| Checks alert.json shape and required fields                                      | `indago-investigate validate-alert $CASE`                            | `out/reports/validate_alert.*`                 |
| Validates Views (roles + path jail)                                              | `indago-investigate validate-views $CASE`                            | `out/reports/validate_views.*`                 |
| Peek parquet schema/head                                                         | `indago-investigate peek-frame $CASE --path <rel>`                   | `out/reports/peek_frame.*`                     |
| Peek JSON keys                                                                   | `indago-investigate peek-json $CASE --path <rel>`                    | `out/reports/peek_json.*`                      |
| Peek model PKL load                                                              | `indago-investigate peek-model $CASE --path <rel>`                   | `out/reports/peek_model.*`                     |
| **Validates judgment twin** (schema + closed tags) — **run before close**        | `indago-investigate validate-judgment $CASE`                         | `out/reports/validate_judgment.md` (+ `.json`) |
| Stage-1 multi-plane orientation (path-only → partial; `--strict-roles` optional) | `indago-health-audit $CASE --profile ieee_flash`                     | `out/health_audit.*`                           |
| Records what evidence is missing for a needed check                              | `indago-investigate request-missing-evidence $CASE`                  | `out/reports/request_missing_evidence.*`       |
| Scaffolds empty judgment files if missing (you must fill claims)                 | `indago-investigate emit-judgment $CASE [--terminal T] [--action A]` | `out/judgment*`                                |
| Rewrites catalog / views bundle — **ops only; skip**                             | `indago-materialize $CASE`                                           | `out/views/bundle.json`                        |

`$CASE` = `.` (cwd = case root) or absolute path to the case root.  
Optional audit flag: `--no-plots` skips plot files under `out/plots/`.

---

## L1 — primitives

| What it does                                                  | Command                                          | Key flags                                                        | Writes                                                                                                                                              |
| ------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Profiles columns/nulls on a frame                             | `indago-investigate profile-table $CASE`         | `--frame cur`                                                    | `out/reports/profile_table.*`                                                                                                                       |
| Compares distributions between two frames                     | `indago-investigate compare-distributions $CASE` | `--frame-a cur --frame-b ref_val`                                | `out/reports/compare_distributions.*`                                                                                                               |
| Offline-rescores a frame with a case PKL                      | `indago-investigate score-offline $CASE`         | `--frame cur` `--model-path <rel>` (or ModelView)                | `out/reports/score_offline.*`                                                                                                                       |
| Compares online vs offline score/feature parity signals       | `indago-investigate parity-compare $CASE`        |                                                                  | `out/reports/parity_compare.*`                                                                                                                      |
| Replays fixed scores through active rules                     | `indago-investigate replay-policy $CASE`         |                                                                  | `out/reports/replay_policy.*`                                                                                                                       |
| Summarizes a named slice vs rest                              | `indago-investigate slice-summary $CASE`         | `--key <column>` (**required** unless Views `slice_key`)         | `out/reports/slice_summary.*`                                                                                                                       |
| Top feature importances (**required for full feature plane**) | `indago-investigate topk-importance $CASE`       | `--model-path` / `--importance-path` / `--model-view`            | `out/reports/topk_importance.*` — HA feature plane reads this file; no silent PKL load                                                              |
| Slice vs rest (cohort)                                        | `indago-investigate slice-summary $CASE`         | `--key` · optional `--score-col` **or** `--rescore --model-path` | `out/reports/slice_summary.*` — Path A = bound score column; Path B = offline predict. Failed rescore → `error_class=model_frame_mismatch` (signal) |
| Correlates alert window with timeline/telemetry signals       | `indago-investigate timeline-correlate $CASE`    |                                                                  | `out/reports/timeline_correlate.*`                                                                                                                  |
| Extracts lineage / contract pointers from evidence            | `indago-investigate lineage-extract $CASE`       |                                                                  | `out/reports/lineage_extract.*`                                                                                                                     |

---

## L2 — thin recipes

| What it does                                 | Command                                          | Key flags                       | Writes                                |
| -------------------------------------------- | ------------------------------------------------ | ------------------------------- | ------------------------------------- |
| Dual-reference null/zero check (train + val) | `indago-investigate dual-ref-null $CASE`         | `--ref ref_val`                 | `out/reports/dual_ref_null.*`         |
| Score-tail concentration vs reference        | `indago-investigate score-tail $CASE`            |                                 | `out/reports/score_tail.*`            |
| Attributes decisions to policy/rules changes | `indago-investigate policy-accountability $CASE` |                                 | `out/reports/policy_accountability.*` |
| Concentration of volume/risk on a slice key  | `indago-investigate concentration $CASE`         | `--key <column>` (**required**) | `out/reports/concentration.*`         |
| Online feature velocity vs batch/offline     | `indago-investigate online-vs-batch $CASE`       |                                 | `out/reports/online_vs_batch.*`       |
| Diffs live baseline card vs backup/prior     | `indago-investigate baseline-card-diff $CASE`    |                                 | `out/reports/baseline_card_diff.*`    |

---

## Rules

1. Prefer these CLIs over inventing playground pipelines.
2. Do not invent report files for tools you did not run.
3. If evidence is missing, say so and/or run `request-missing-evidence`.
4. Containment actions (`rollback_model`, …) are judgment recommendations — not CLIs.
5. Close only at the end: `out/judgment.md` + `out/judgment_struct.json` with tags from `claim_tags.json`.
6. **Before declaring done:** run `indago-investigate validate-judgment $CASE`. Fix every ERROR in the critique until Result is **OK**. Exit code is non-zero while FAIL.

## `judgment_struct` claim rows (Layer A)

```json
{
  "tag": "model_artifact",
  "status": "falsified_as_primary",
  "evidence_refs": ["out/reports/parity_compare.md"]
}
```

| Rule                  | Do                                                                                               | Don't                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| Shape                 | One claim object per `tag`                                                                       | `tags: ["a","b"]` on one object; free-text `claim` without `tag` |
| Decision              | `decision.terminal` + `decision.action_class`                                                    | Top-level `terminal` / `action`                                  |
| Elimination           | `falsified` / `falsified_as_primary` when a mechanism is **not** the primary RCA                 | `supported` meaning “plane is healthy / green”                   |
| Support               | `supported` / `associated` when that tag **is** the mechanism (both hard-fail on forbidden tags) | —                                                                |
| Inhibitors            | Required gold inhibitors → `pass_grounding`                                                      | Soft anchors only                                                |
| Orientation artifacts | Suite harvests need `out/catalog*` + `out/health_audit*` (Layer C)                               | —                                                                |
| Origin unknown        | `unknown` (e.g. traffic origin)                                                                  | Invent merchants/botnets                                         |

## Terminals vs disposition

- **Defect class** (discriminating proof of wrong rules / serving-tile break / wrong model / pipeline break) → `ROOT_CAUSE_FOUND` + fix-class action, even if a deeper upstream “why” is open.
- **Localization without causal origin** (mix / slice / traffic pattern; model/policy eliminated) → `LOCALIZED_CAUSE_UNKNOWN` + `domain_review`.
- Do not treat every supported claim tag as automatic `ROOT_CAUSE_FOUND`.
