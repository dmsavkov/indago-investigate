# Two surfaces (do not conflate)

**Status:** frozen · 2026-09-05 (vocabulary fix)  
**Why:** The investigation package CLI and parent meta orchestration are different products. Do not flatten them into one tool list for the coordinator.

**Names (use these):**

| Surface | Call it | Not |
| --- | --- | --- |
| **1** | **Investigation package CLI** | “operator”, “ops”, “Surface B” |
| **2** | **Parent meta** (scripts / `indago-ops-*`) | “the package”, “agent tools” |

---

## Surface 1 — Investigation package CLI

**Who:** coordinating agent on a pack or isolate case.  
**Home:** `package/indago_investigate/` · entrypoints `indago-*` (analysis).  
**Job:** inventory → orient → L1/L2 checks → judgment artifacts under `case/out/`.  
**Menu:** `package/agent/tools.md` (flashed to `_shared/docs/tools.md`) — `indago-catalog` / `indago-health-audit` / `indago-investigate <cmd>` (materialize optional, unused by ieee_flash path).  
**Must not:** read gold, flash cases, harvest results, or score runs.

This is the product the coordinator runs during F-case investigation.

---

## Surface 2 — Parent meta

**Who:** you / CI on the main repo, outside the isolate sandbox.  
**Home:** `scripts/isolate/`, `scripts/eval/`, entrypoint `indago-ops-eval`.  
**Job:** flash sealed INPUT, verify seal, harvest OUTPUT, Layer A score, claim-by-claim judge.

| Mechanism | Role |
| --- | --- |
| `scripts/isolate/flash_case.py` | Pack → sealed isolate INPUT |
| `scripts/isolate/verify_seal.py` | Denylist / seal |
| `scripts/isolate/harvest_run.py` | Recall-all → `results/package/FN/ts/` |
| `scripts/isolate/score_isolate.py` | Deterministic Layer A |
| `indago-ops-eval` | Layer A + LLM/mock judge → `<harvest>/eval/<UTC>/report.json` |

How-to (contact): main repo `package/README.md`. Lab flash: `package/docs/ops-flash.md`. Agent corpus: `package/agent/` (flashed).

Legacy lab (`indago-run`, `indago-score`, tournament) is also parent/lab — not the investigation package menu.

---

## Rule of thumb

| Question | Surface |
| --- | --- |
| “What does the Cursor agent invoke on a case?” | **1** only |
| “How do I prepare F3 / score a harvested run?” | **2** only |
| Materialize / compare / replay on a case? | **1** |
| Flash / harvest / gold / judge? | **2** |
