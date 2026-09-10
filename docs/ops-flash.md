# INDAGO investigation package — lab operator how-to (flash / isolate)

> **Audience:** monorepo operators only. Public/contact docs: [`../README.md`](../README.md).  
> Parent-meta guide: flash → agent investigates → harvest → eval.

**Agent CLI semantics:** `package/agent/` (flashed to isolate `_shared/docs/`).  
**Engineer design (Option C, surfaces):** `package/docs/` — not flashed.

```text
Main repo (indago)                         IsolateEnvironment\indago
─────────────────                          ─────────────────────────
packs/F3          ──flash──►               f-cases/F3/  (evidence + ACTIVATION)
package/agent     ──flash──►               f-cases/_shared/docs/
package CLI (indago-*)  ──►                agent runs tools on case
scripts/isolate + eval  meta ◄──           harvest out/ + playground/
eval/gold/v2                               scored on parent only
```

---

## One-time setup

```powershell
cd D:\Coding\VSCFiles\IndependentProjects\AI\indago
# One-time (Windows): live package path for editable installs
if (-not (Test-Path .\indago_investigate)) { cmd /c mklink /J indago_investigate package\indago_investigate }
uv sync
# Project venv:
uv pip install -e . --force-reinstall --no-deps

# PATH for IsolateEnvironment / Cursor agent (REQUIRED after package CLI changes):
uv tool uninstall indago  # if upgrading from a stale force-include snapshot
uv tool install -e ".[score]" --python 3.13 --force
# Verify:  where.exe indago-investigate
#          indago-investigate --list
# Default bind is Views-required (INDAGO_BIND=views). Ops rollback: $env:INDAGO_BIND="caseio"
```

**Why two installs?** `uv pip install -e .` refreshes `.venv`. Agents call bare `indago-*` from PATH, which comes from `uv tool install` → typically `~\.local\bin\`. Reinstalling only the venv leaves a **stale** PATH CLI (e.g. missing `validate-judgment`).

Isolate root default: `D:\Coding\VSCFiles\IsolateEnvironment\indago`  
Agent workspace: open **only** the isolate root; paste `f-cases/<CASE>/ACTIVATION.md`. CLIs come from PATH, not from that tree.

---

## Parent meta scripts

| What it does | Command | Key flags |
| --- | --- | --- |
| Copies pack evidence into a sealed isolate case and refreshes agent docs (**wipes** case `out/`; operator salvage → `results/flash_salvage/` — **not** under `f-cases/`) | `uv run python scripts/isolate/flash_case.py --case F3` | `--isolate-root`, `--dry-run`, `--views-seed empty\|templates\|ops` (default **empty**), `--sync-package` (discouraged). Also seeds optional `org-docs/` (pack copy or F-pack feature dictionary — not gold). Flashes `views_contract.md`, `thresholds.md`, `examples/views/` + `examples/derived/`. Cases ending `_trimmed` use Tier-0 leaf lists. |
| Checks isolate INPUT for denylist / contamination | `uv run python scripts/isolate/verify_seal.py --case F3` | `--post-run` allows `out/judgment*` after a real close |
| Copies `out/` + `playground/` to a dated results stamp | `uv run python scripts/isolate/harvest_run.py --case F3` | `--stamp`, `--notes`, `--model-or-agent` |
| Deterministic Layer A score vs gold v2 | `uv run python scripts/isolate/score_isolate.py --case F3 --results-dir results\package\F3\<stamp>` | `--struct`, `--judgment-md` |
| Layer A + mock/LLM claim judge; auto-loads `out/judgment*` | `uv run indago-ops-eval --results-dir results\package\F3\<stamp>` | `--mock-judge`, `--case`, `--out`; default model `gemini-3.5-flash-lite` |

Eval writes: `<harvest>/eval/<UTC>/report.json` and `eval/latest.json`.

Offline DEMO (seeds fixture harvest, no isolate):

```powershell
uv run indago-ops-eval --case DEMO --mock-judge
```

Export latest judgments for LLM upload (copies + concatenated bundles → `data/cache/llm_upload/`):

```powershell
uv run python scripts/eval/export_judgments_media.py F0 F0b F2 F3
```

Optional hardness (symptom-first policy, same physics as F0):

```powershell
uv run python scripts/isolate/flash_case.py --case F0b
# Contact generality (ugly alert/rules, thin leaf set):
uv run python scripts/isolate/build_trimmed_pack.py --force
uv run python scripts/isolate/flash_case.py --case F0_trimmed
uv run python scripts/isolate/verify_seal.py --case F0b
```

---

## Quickstart (F3)

```powershell
uv run python scripts/isolate/flash_case.py --case F3
uv run python scripts/isolate/verify_seal.py --case F3

# Agent: open IsolateEnvironment\indago, paste f-cases\F3\ACTIVATION.md once.
# From the case folder (CLIs on PATH via `uv tool install -e .` from main):
cd D:\Coding\VSCFiles\IsolateEnvironment\indago\f-cases\F3
indago-catalog .
indago-health-audit . --profile ieee_flash --no-plots

uv run python scripts/isolate/harvest_run.py --case F3
uv run indago-ops-eval --results-dir results\package\F3\<stamp> --mock-judge
```

Agent close artifacts (end of run): `out/judgment.md` + `out/judgment_struct.json`.

---

## Glossary (operator)

| Term | Meaning |
| --- | --- |
| **case_root** | Directory with `alert.json` + `evidence/` |
| **flash** | Pack → sealed isolate INPUT; wipe `out/`/`playground/`; write `ACTIVATION.md`; copy `package/agent/` → `_shared/docs/` |
| **harvest** | Agent outputs → `results/package/<CASE>/<stamp>/` |
| **judgment_struct** | Agent machine twin for Layer A |
| **Layer A / B** | Exact gold match / claim-by-claim judge (B capped by A hard fails) |

---

## Doc map

| Path | Audience |
| --- | --- |
| `package/agent/` | Agent — flashed |
| `package/docs/` | Engineer — not flashed |
| `package/docs/ops-flash.md` | You / CI (this file — lab flash/harvest) |
| `package/README.md` | Public / contact package how-to |
| `context/package/` | Directional notes |

---

## Smoke (after package edits)

```powershell
uv pip install -e . --force-reinstall --no-deps
uv tool install -e . --force
indago-investigate --list   # must list validate-judgment
uv run python scripts/isolate/flash_case.py --case F3
cd D:\Coding\VSCFiles\IsolateEnvironment\indago\f-cases\F3
indago-catalog .
indago-investigate validate-alert .
# validate-judgment FAILs on fresh flash (no judgment yet) — expected
cd D:\Coding\VSCFiles\IndependentProjects\AI\indago
uv run indago-ops-eval --case DEMO --mock-judge
```
