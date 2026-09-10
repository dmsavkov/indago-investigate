# Activation (template)

Paste **once** at the start of an isolate Cursor run. Not a repeating system message.

Docs for this run: `_shared/docs/README.md` → `tools.md`, `glossary.md`, `claim_tags.json`, `philosophy.md`, `views_contract.md`, `rewrite_views.md`, and when present `thresholds.md`.

---

## State

- Case root: `{{CASE_ROOT}}`
- Start: `{{CASE_ROOT}}/alert.json`
- Evidence: `{{CASE_ROOT}}/evidence/` (case-local only)
- Optional human docs: `{{CASE_ROOT}}/org-docs/` (if present — useful, not guaranteed complete)
- Write under `{{CASE_ROOT}}/out/` · scratch under `{{CASE_ROOT}}/playground/`
- CLI menu: `_shared/docs/tools.md`
- Views shapes: `_shared/docs/views_contract.md` (+ `examples/views/` under docs)
- **Rewrite field tables:** `_shared/docs/rewrite_views.md` (+ `examples/derived/`)

`out/` starts empty of judgments. Catalog is **not** pre-built. Flash leaves `out/views/` empty — **you author Views**. Never run ops ieee bind. `evidence_manifest.json` is a flash receipt only — discover assets from catalog paths.

## Problem

An ML monitor fired. Investigate the system, not only the ticket metric. The primary alert metric is an **unverified rumor** until orientation.

## Evidence rewrite (when shapes are ugly)

Tools do **not** JSONPath into arbitrary customer nests. If alert or rules are messy, rewrite once — full field tables in `_shared/docs/rewrite_views.md`:

1. **Alert** → `out/derived/alert_indago.json` then thin `out/views/alert.json` (`extras.derived_path` / `raw_path`).
2. **Rules (policy in scope)** → `out/derived/rules_live_indago.yaml` then `out/views/rules_live.json` pointing at it.
3. Skip derived only when raw already matches those schemas.
4. Skeletons: `_shared/docs/examples/derived/`.

Do not invent thresholds (`thresholds.md`). Do not plant role_hints.

## Constraints

- Do not invent metrics, files, merchants, or causes.
- Missing evidence → say unavailable and list what you would need.
- Cite real paths (and column/key names for slice/feature claims).
- Claim tags: only those in `_shared/docs/claim_tags.json`.
- Run only investigation CLIs in `tools.md`. Do not flash, harvest, score, or open gold.
- **Allowlist:** only CLIs in `_shared/docs/tools.md`. Ignore other `indago-*` on PATH.
- Confirm `indago-investigate --list` includes `validate-judgment` before closing; if missing, PATH is stale — stop and report to operator.
- Do **not** delete or empty `out/`. Do not browse sibling case folders for prior answers.
- **Case argument:** `.` when cwd is `{{CASE_ROOT}}`, else absolute path to that folder. Never a bare case id.
- **Slice tools:** `--key <column>` unless Views already map `slice_key`.

## Capabilities (recommended loop — not a rigid FSM)

Use tools when you need the capability. Order below is a **suggested** pedagogy; skip steps you already satisfied.

| Goal | You can… |
|------|----------|
| **Inventory** | `indago-catalog .` → read `out/catalog.md`. (`evidence_manifest.json` is a flash receipt, not the working catalog.) |
| **Rewrite ugly alert/rules** | If needed: `out/derived/alert_indago.json` and/or `out/derived/rules_live_indago.yaml` → then author Views (see **Evidence rewrite** above). |
| **First orientation (partial)** | Author **path-only** FrameViews (`path_or_handle` set; `column_roles` may be empty) from catalog paths → `validate-views` → `indago-health-audit . --profile ieee_flash`. Read UNKNOWN planes + `missing_roles` / hints in **`out/health_audit.md`**. |
| **Learn shapes** | Read `_shared/docs/views_contract.md` + `examples/views/`. |
| **Choose columns (required skill)** | `peek-frame` the CUR (and REF) table: list real column names. Prefer score-like cols (`risk_score`, `prediction`, `y_hat`, `score`, …) — do **not** assume a single folklore name. Bind `slice_key` / `product` / `amount` / `decision` / `policy_hash` from what you peeked. Optional org-docs = vocabulary only. |
| **Importances (agent-owned)** | Run `topk-importance . --model-path <catalog-pkl>` (or `--importance-path`) **before** treating feature-plane gain×PSI as authoritative. Health-audit reads `out/reports/topk_importance.json` only — it does **not** silently load the PKL for ranks. Native attrs only; `unsupported` if none. |
| **Bind roles** | Fill `column_roles` on Views → `validate-views` again. Without score/slice roles, population/model/decision planes stay UNKNOWN — that is incomplete work, not a finished case. |
| **Second orientation** | Re-run health-audit after roles filled. |
| **Discriminate** | `indago-investigate --list` → L1/L2; read results from **`out/reports/<tool>.json`**. Prefer falsification. |
| **Close** | Write `judgment*` → `validate-judgment` until OK. |

**Notes**

- Without usable FrameViews (paths), health-audit / L1 exit with `views_required`.
- Path-only Views → **partial** HA (schema-light + loud missings). Filled roles → **full** role-gated planes. Same View schema — not a second HA contract.
- Do not hardcode host paths. Pick model/importance paths from catalog or org-docs.
- **Defect with discriminating proof** (e.g. policy replay match live ≠ default) → `ROOT_CAUSE_FOUND` + fix-class action. Missing *who changed the rules* is residual, not a reason to stay LOCALIZED when the broken component is identified.

## Deliverables (end of run — not the first act)

- `out/judgment_struct.json` — machine twin for Layer A:
  - `decision.terminal`, `decision.action_class`, `decision.inhibitors` (**required** on the struct, not only in markdown)
  - `claims[]` as **one object per tag**: `{ "tag": "...", "status": "..." }`
  - Use `falsified_*` to eliminate; `supported` for the primary localization/RCA tag (not `falsified_as_primary` on the primary mix/slice). Prefer `supported` over `associated` for gold-required primary tags.
- `out/judgment.md` — human elimination ledger (soft skeleton below)
- `out/reports/validate_judgment.md` showing **OK**
- Tool notes under `out/reports/` (catalog / health_audit at `out/` root)

### Soft skeleton for `out/judgment.md`

```markdown
# Judgment — <CASE>

## Stage 1 — Macro elimination (negative space)
## Stage 2 — Salience shortlist
## Stage 3 — Causal contrast
## Stage 4 — Decision (action + inhibitors + residual)
## Funnel summary (60-second scan)
## Evidence index
```

## Disposition (pack-neutral)

- **Defect class** with discriminating proof → `ROOT_CAUSE_FOUND` + matching fix-class action.
- **Localization without causal origin** → `LOCALIZED_CAUSE_UNKNOWN` + `domain_review` (or suite synonym).
- Do not treat “any supported claim tag” as automatic `ROOT_CAUSE_FOUND`.
