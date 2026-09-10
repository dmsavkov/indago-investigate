# Policy: Raw data → Views → Tools (Option C)

**Status:** frozen decision · 2026-09-05  
**Decision:** **Option C — Hybrid**  
**Canon location:** `package/docs/views_policy.md` (this file). Do not maintain a second full copy.  
**Supersedes conflicting lines in:** early `data.md` “always materialize first,” reconsideration “agent-only projection with no helpers,” and “health_audit needs Views on day one.”  
**Related:** [`views_contract.md`](views_contract.md) · [`tools.md`](tools.md) · `package/indago_investigate/views.py` · design notes in `context/package/data.md`  
**Background analysis:** `context/investigation/raw-data-view-resolution.md` (non-operative if it conflicts here).

---

## One-sentence freeze

> **Target:** tools consume typed Views (roles + paths); ieee folklore is an **ops/flash binder** only. **Interim:** `INDAGO_BIND=caseio|prefer_views|views` — CaseIO ieee path still allowed until Views-first gates pass (`mvp-generality.md`). F0–F4 remain the eval harness, not the data API.

---

## Three layers (do not conflate)

| Layer | Job | Example |
| --- | --- | --- |
| **Raw / EvidenceRef** | File exists; kind + path + availability | Fat `monitor_baseline.json` |
| **View** | Small typed contract tools trust (per kind) | `BaselineCardView`: card_id, pred_mean_val, rules hash |
| **Tool** | Plane metrics / recipes | health_audit, compare, replay |

Views differ per evidence kind. Mapping vendor names → view cores and CUR columns → `column_roles` is the hard problem — not inventing more view types.

---

## Option C — phased policy

### Phase 2 (interim — dual bind)

| Rule | Detail |
| --- | --- |
| Inventory | Raw EvidenceRef catalog only (`indago-catalog`); no gospel BaselineCard dump in catalog |
| Bind modes | `INDAGO_BIND=caseio` (legacy) · `prefer_views` (transition) · `views` (target) — see `context/package/mvp-generality.md` |
| Health audit | May still use ieee path/field folklore under `caseio`; **target** is Views + role-gated planes |
| Agent docs | Must not present ieee materialize/bind as the normal path; ops may flash-seed Views |
| Acceptance | F0–F4 remain the eval harness; **L1 proof** = renamed-column fixture + machine `manifest.json`, not F-suite alone |

### Phase 2b / 3 — toward the contract

| Rule | Detail |
| --- | --- |
| Ops ieee binder | Flash-time / `indago-ops-*` only — writes `out/views/` |
| `validate-views` | Required before trusting audit in `views` / `prefer_views` |
| Health audit | Prefer `--views-dir`; emit `roles_resolved` / `roles_missing` |
| Agent | Catalog → peek → views → validate-views → audit |
| Case evidence | Runtime must not depend on shadow `_shared/overfetch` |

Planning SoT for migration cuts and schemas: [`context/package/mvp-generality.md`](../../context/package/mvp-generality.md) Part B.

### Later — production heterogeneity

| Rule | Detail |
| --- | --- |
| Adapters / agent mapping | Foreign dumps → same View contracts |
| Tools | Consume **Views** (and frame paths + roles), not arbitrary vendor JSON |
| Rejected | Tools that only understand one customer’s raw schema forever |

---

## What we are *not* doing

| Rejected | Why |
| --- | --- |
| **A only forever** | Ships audit but lies about product generality if never followed by Views |
| **B only (must Views before any audit)** | Blocks Phase 2; unstable without helpers |
| **D (no views, prompt-only raw)** | Non-deterministic orientation; bad eval |
| **Catalog auto-dumps Views as the orientation answer** | Confuses inventory with preprocessing |
| **Agent must invent the entire schema with no contract/helpers** | Too unstable for eval and product |

---

## End-state workflow (target)

```text
Raw exports (any vendor names)
        ↓
EvidenceRef inventory (paths, kinds, availability)
        ↓
Map → typed Views (+ column_roles)   [helpers and/or agent/adapters]
        ↓  persist out/views/
Tools (health_audit, L1/L2) read Views / roles
        ↓
Reports → judgment
```

Interim bypass of the map step is allowed only under `INDAGO_BIND=caseio` (or failed prefer_views fallback with WARN). It is not the long-term agent path — see `mvp-generality.md`.

---

## Implementation checklist

- [x] `indago-health-audit --profile ieee_flash` (legacy caseio)
- [x] Agent docs: views_contract + tools list health_audit
- [ ] `validate-views` + peek-* + `INDAGO_BIND` strangler
- [ ] Ops ieee binder at flash; F3_renamed L1 fixture
- [ ] Partner/adapter path when first non-IEEE pack appears
- [x] Planning SoT: `context/package/mvp-generality.md` (rev.2 build spec)

---

## Bottom line

**Option C (updated):** Views are the tool boundary; ieee/flash binding is **interim or ops-only**, not the long-term agent path. Strangler: `prefer_views` → `views` with `validate-views`, case-local evidence, and an **F3_renamed** L1 proof. Full build plan: `context/package/mvp-generality.md`.
