# INDAGO

**Decision-system investigation on a frozen evidence pack** — orient across data, scores, policy, and traffic; recommend inhibitors and next action class before labels arrive.

[▶ Demo video — add link when recorded]

Python **3.12+** · Install with **pip** or **uv** · License: [Apache-2.0](LICENSE)

---

## What this is (and isn’t)

**Job.** You get an alert or KPI blip. Monitors show symptoms; case tools review single entities. Between them, teams still burn hours asking: data break, serve skew, model, rules, or mix shift? INDAGO runs that triangulation **offline** on a pack you freeze.

**How it thinks.** Start with a **health audit** across decision-system planes. Every plane gets an honest status — including **UNKNOWN** when evidence is missing. Completeness means a truthful vector, not all-GREEN. The alert is a **rumor** until grounded. Disposition + **inhibitors** (e.g. don’t rollback the model when score parity is clean) are first-class outcomes.

**Loop (one line).** Catalog → bind Views (paths + column roles) → health audit → targeted checks → judgment (`UNKNOWN` is a valid close).

**Not this.** Not a real-time authorizer, not L1 case management UI, not auto-retrain, not a full lineage/CMDB product, not magic on an unlabeled lake with no map.

---

## What you need (minimal pack)

| Required | Optional |
|----------|----------|
| Alert / KPI text or JSON | Rules snapshot |
| CUR window (parquet/csv) | Labels / infra metrics |
| REF window (parquet/csv) | `org-docs/` (short notes — vocabulary only) |
| **Trained model** (joblib/PKL) | — |
| Column roles via peek → Views | — |

Layout: `evidence/live|ref/{data,models,rules}/`. Tools consume **Views**, not vendor JSON shapes.

Cohort tools: use a bound **score column**, or **`--rescore`** with the model. A failed rescore (feature/schema mismatch) is itself a useful signal (`model_frame_mismatch`).

Checklist: [`docs/minimal-pack.md`](docs/minimal-pack.md). Empty skeleton: [`examples/minimal_template/`](examples/minimal_template/). Runnable synthetic pack: [`examples/demo_case/`](examples/demo_case/).

---

## Quick start

```bash
# from this package directory (or a clone that is only this tree)
uv sync --extra score
# or: pip install -e ".[score]"

# smoke the synthetic demo (pre-bound Views)
indago-catalog examples/demo_case
indago-health-audit examples/demo_case --no-plots
indago-investigate slice-summary examples/demo_case --key entity_id
indago-investigate topk-importance examples/demo_case \
  --model-path evidence/live/models/champion.pkl
```

Your own pack:

```bash
cp -r examples/minimal_template my_case
# add CUR/REF under evidence/live|ref/data/, model under evidence/live/models/
# edit my_case/alert.json
# agent: open my_case, follow agent/ACTIVATION.md (or paste it)
indago-catalog my_case
# peek-frame → author out/views/ → validate-views → health-audit → …
```

Default bind is Views-required (`INDAGO_BIND=views`). Optional env knobs: [`.env.example`](.env.example).

---

## How it works

1. **Inventory** — `indago-catalog` lists what is on disk.  
2. **Bind** — author small View sidecars under `out/views/` (paths + `column_roles`); `validate-views`.  
3. **Orient** — `indago-health-audit` (path-only Views → partial audit + loud missings).  
4. **Discriminate** — L1/L2 tools where survivors need them (profile, drift, score-offline, slice, policy replay, …).  
5. **Close** — `out/judgment.md` + `out/judgment_struct.json`; `validate-judgment`.

| Path | Audience |
|------|----------|
| [`agent/`](agent/) | Agent protocol (ACTIVATION, tools, philosophy) |
| [`docs/`](docs/) | Views contract, thresholds, minimal-pack, examples |
| [`docs/ops-flash.md`](docs/ops-flash.md) | Lab isolate flash/harvest (monorepo operators only) |

---

## Example output

Full ledgers are long by design. Prefer a short demo recording that scrolls `out/health_audit.md` and the judgment scorecard.

On `examples/demo_case`, after smoke you should see `out/catalog.*` and `out/health_audit.*` with honest UNKNOWNs where optional evidence is absent.

---

## Feedback

- GitHub Issues on the project repo  
- Email / design-partner walkthrough on a **thin** pack welcome — we do not need your full warehouse  

---

## License

Copyright 2026 Dmitry Savkov. Licensed under the [Apache License 2.0](LICENSE).
