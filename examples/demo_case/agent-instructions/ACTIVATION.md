# Activation (template)

Paste **once** at the start of a case run (or open this file when the host attached `agent-instructions/`). Not a repeating system message.

Docs for this run: **this folder** — `README.md`, `tools.md`, `glossary.md`, `claim_tags.json`, `philosophy.md`, `views_contract.md`, `rewrite_views.md`, `thresholds.md`, `roles.md`, `examples/`.

If investigation CLIs (`indago-catalog`, `indago-health-audit`, `indago-investigate`) are missing from PATH, **halt** and tell the operator the package is not installed; they should follow the package installation guide. Do not invent alternate host paths.

---

## State

- Case root: `{{CASE_ROOT}}`
- Start: `{{CASE_ROOT}}/alert.json`
- Evidence: `{{CASE_ROOT}}/evidence/` (case-local only)
- Optional human docs: `{{CASE_ROOT}}/org-docs/` (if present — useful, not guaranteed complete)
- Write under `{{CASE_ROOT}}/out/` · scratch under `{{CASE_ROOT}}/playground/`
- CLI menu: `tools.md` (this folder)
- Views shapes: `views_contract.md` + `examples/views/`
- Rewrite field tables: `rewrite_views.md` + `examples/derived/`

`out/` starts empty of judgments. Catalog is **not** pre-built. **You author Views**. Never run ops ieee bind. `evidence_manifest.json` is a flash receipt only — discover assets from catalog paths.

## Problem

An ML monitor fired. Investigate the system, not only the ticket metric. The primary alert metric is an **unverified rumor** until orientation.

## Evidence rewrite (when shapes are ugly)

Tools do **not** JSONPath into arbitrary customer nests. If alert or rules are messy, rewrite once — field tables in `rewrite_views.md`:

1. **Alert** → `out/derived/alert_indago.json` then thin `out/views/alert.json` (`extras.derived_path` / `raw_path`).
2. **Rules (policy in scope)** → `out/derived/rules_live_indago.yaml` then `out/views/rules_live.json` pointing at it.
3. Skip derived only when raw already matches those schemas.
4. Skeletons: `examples/derived/`.

Do not invent thresholds (`thresholds.md`). Do not plant role_hints.

## Constraints

- Do not invent metrics, files, merchants, or causes.
- Missing evidence → say unavailable and list what you would need.
- Cite real paths (and column/key names for slice/feature claims).
- Claim tags: only those in `claim_tags.json` (this folder).
- Run only investigation CLIs in `tools.md`. Do not flash, harvest, score, or open gold.
- **Allowlist:** only CLIs in `tools.md`. Ignore other `indago-*` on PATH.
- Confirm `indago-investigate --list` includes `validate-judgment` before closing; if missing, PATH is stale — stop and report to operator.
- Do **not** delete or empty `out/`. Do not browse sibling case folders for prior answers.
- **Case argument:** `.` when cwd is `{{CASE_ROOT}}`, else absolute path to that folder. Never a bare case id.
- **Slice tools:** `--key <column>` unless Views already map `slice_key`.
- **Views gate:** after authoring Views, run `validate-views` and fix ERRORs (read WARNs) before health-audit / L1. Wrong roles poison planes — especially binding amount as score.

## Capabilities (recommended loop — not a rigid FSM)

Use tools when you need the capability. Order below is a **suggested** pedagogy; skip steps you already satisfied.

| Goal | You can… |
|------|----------|
| **Inventory** | `indago-catalog .` → read `out/catalog.md`. |
| **Rewrite ugly alert/rules** | If needed: derived files → then author Views (see **Evidence rewrite**). |
| **First orientation (partial)** | Author **path-only** FrameViews → `validate-views` → `indago-health-audit . --no-plots`. Read UNKNOWN planes + missings. |
| **Learn shapes** | Read `views_contract.md` + `examples/views/`. |
| **Choose columns** | `peek-frame` tables you will bind: list real column names. Prefer score-like cols distinct from amount. Bind `slice_key` / `product` / `amount` / `decision` / `score` from what you peeked. |
| **Importances** | `topk-importance . --model-path <catalog-pkl>` (or `--importance-path`) before treating feature-plane ranks as authoritative. Importances = which inputs the model weights most (native `feature_importances_` / `|coef_|` / NB log-odds). They ground the feature plane and which columns matter for skew vs mix stories — not a causal proof alone. Rankings can carry **statistical bias** (correlated features, leakage, unstable splits); treat top-k as orientation, not sole RCA. |
| **Bind roles** | Fill `column_roles` → `validate-views` again. |
| **Second orientation** | Re-run health-audit after roles filled / topk written. |
| **Discriminate** | `indago-investigate --list` → L1/L2; read `out/reports/<tool>.json`. Prefer falsification **only with a discriminating measurement**. Failed / skipped / unloadable tool → claim `unknown` or `weakened`, never `falsified*`. |
| **Close** | Write `judgment*` → `validate-judgment` until OK. |

**Notes**

- Without usable FrameViews (paths), health-audit / L1 exit with `views_required`.
- Path-only Views → **partial** HA. Filled roles → **full** role-gated planes.
- `UNKNOWN` is a valid close when evidence is thin. Inhibitors are first-class.
- Model is required for a full pack; unloadable PKL is an ERROR — do not claim model health from a failed load; leave `model_artifact` `unknown` until peek/load succeeds.
