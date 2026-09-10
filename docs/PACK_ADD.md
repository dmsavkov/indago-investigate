# Adding / flashing an F-pack (frozen mechanism)

**Audience:** operators / engineers (not isolate agents).  
**Status:** freeze 2026-09-05.

## Required artifacts per case `FN`

| Artifact | Location | Role |
| --- | --- | --- |
| Pack workspace + `alert.json` | `packs/FN/` | Flash source |
| Manual reference judgment | `packs/FN/manual_out/inspection/0_orientation/judgment.md` | Human ledger |
| Gold Layer A | `eval/gold/v2/FN.json` | Deterministic score |
| Gold Layer B reference copy | `eval/gold/v2/refs/FN.md` | Cross-compare judge (copy of manual judgment) |
| Claim vocabulary | `eval/gold/v2/claim_tags.json` + `package/agent/claim_tags.json` | Keep tags in sync |

Agent corpus (flashed): **only** `package/agent/*` → isolate `_shared/docs/`. Never flash gold or refs.

## Flash / harvest / eval

```powershell
# Host once (PKL model plane — do not put lab paths in isolate docs):
#   uv sync --extra score
#   optional escape: ~/.indago.env → INDAGO_SCORER_PYTHON=... or INDAGO_LAB_ROOT=...

uv run python scripts/isolate/flash_case.py --case FN
uv run python scripts/isolate/verify_seal.py --case FN
# agent run on IsolateEnvironment …
uv run python scripts/isolate/harvest_run.py --case FN
uv run indago-ops-eval --results-dir results\package\FN\<stamp>
```

## PKL / model-plane (G2b)

Prefer **`uv sync --extra score`** so the current interpreter loads champion PKLs (`joblib` + `lightgbm` + `scikit-learn`).  
Escape: `INDAGO_SCORER_PYTHON` or `INDAGO_LAB_ROOT` (lab `.venv`). No hardcoded host lab path. ADR: `context/package/adr-scorer.md`.

Without a scorer, model plane → `UNKNOWN` and composites skew (e.g. F3 → `FEATURE_PLANE` instead of `LOCALIZED_POPULATION`).

## New-pack checklist

1. Pack builds; `alert.json` present; overfetch targets resolvable.
2. Manual judgment exists; copy → `eval/gold/v2/refs/FN.md`.
3. Write slim `eval/gold/v2/FN.json` (terminal, action synonyms, claims, anchors, inhibitors).
4. `pytest tests/test_package_eval_contract.py -q` green.
5. Flash + seal OK (no host-path leaks in evidence text after scrub).
6. Smoke: `indago-health-audit <case> --profile ieee_flash --no-plots` → model plane not UNKNOWN when lab env set.

## Scoring contract (Layer A)

- Hard fail: wrong terminal / forbidden primary action / forbidden overclaim (`supported` **or** `associated`).
- Missing gold `required_inhibitors` → `pass_grounding=false` → overall fail (anchors stay soft notes).
- Soft notes: claim floors, anchors, optional capabilities.
- `unknown` when gold wants `falsified_*` or `supported` → **half penalty** (0.5 note weight).
- Layer B: cross-compare gold + `refs/FN.md` + candidate; cannot override Layer A hard fails.
- Suite harvests (F0–F4, F0b): Layer C requires `out/catalog*` + `out/health_audit*`.

Optional hardness pack: **F0b** (symptom-first policy; see `context/domain/f0b-incident-spec.md`).
