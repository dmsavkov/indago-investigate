# Investigation philosophy (agent)

> Investigate by **eliminating the healthy surface first**, then ranking what remains, then testing only survivors — never by target-fixating on the ticket metric and writing a long confirmation report.

## Why

| Bad question | Good question |
| --- | --- |
| What explains the fired metric? | Given the whole system state, what is abnormal, connected, and action-worthy? |
| Confirm the alert | Prove what is *not* broken, then isolate the few things that matter |
| Academic hypothesis essay | Elimination funnel + explicit negative space |

A case can feel “incomplete” under ticket-solving when a local concentration is real but **meaning** still requires knowing whether the rest of the system is healthy. Once orientation shows model / policy / inference healthy and companion signals collapse into one survivor slice, more tables rarely help — close with an honest localized terminal + inhibitors when origin stays unknown.

## Four capabilities (keep separate)

| Capability | Question | Primary artifact |
| --- | --- | --- |
| **Measurement** | What is happening? | Metrics, PSI, null rates, lag, hashes |
| **Orientation** | What is the state of the whole system? | Multi-plane health audit |
| **Investigation** | What explains the survivors? | Deep checks as *discriminating tests* |
| **Judgment** | What should we do / not do? | Elimination judgment ledger |

## 4-stage elimination funnel

```text
Alert (rumor, not root cause)
        ↓
Stage 1  MACRO ELIMINATION GATE     ← health_audit
        ↓  negative space: what is GREEN with numbers
Stage 2  TOP SALIENCE SHORTLIST     ← rank remaining deviations
        ↓  merge companions; demote noise
Stage 3  CAUSAL CONTRAST            ← only among survivors; falsify
        ↓
Stage 4  ACTION + INHIBITORS        ← decide; forbid unsafe globals
```

### Stage 1 — Macro elimination

Treat the alert metric as an **unverified rumor** until orientation completes.

- If Model and Decision/Policy are GREEN, **forbid** model rollback and rules change as primary (inhibitors).
- Channel-split infra: inference lag ≠ tile / store lag.
- Dual-reference nulls: train spikes that are val-aligned are not “pipeline break” by default.
- Feature alerts on the **same axis** as a population concentration are not automatically ETL failure.

### Stage 2 — Salience shortlist

Rank remaining deviations by mass / impact. Test whether co-shifts are **independent** or **companions** of the top survivor. Output KEEP / MERGE / DEMOTE; aim for a few operational survivors.

### Stage 3 — Causal contrast

Competing stories **only for survivors**. Do not invent merchant names, campaigns, or botnet certainty without evidence. Prefer slice vs rest, fixed-score policy replay, offline score parity, dual-ref nulls, lineage when change is the claim.

### Stage 4 — Judgment

State terminal, action, **inhibitors** (what NOT to do), residual uncertainty, and coverage bound.

## Cognitive contract

1. No target fixation before Stage 1.
2. Negative space first — list what is healthy with numbers.
3. Hypotheses only after Stage 2, only for survivors.
4. Respect inhibitors when model/policy planes are green.
5. If localizing a slice, prove companions and demotions.
6. “Coverage” means the audited surface — not the infinite outside world.

## Anomaly ladder

```text
ABNORMAL → LOCALIZED → EXPLAINED → CAUSALLY SUPPORTED
         → OPERATIONALLY MATERIAL → ACTIONABLE
```

Monitoring often stops at ABNORMAL. Investigation must climb. Stopping at LOCALIZED with ORIGIN UNKNOWN is legitimate when labels/domain context are absent — **if** Stages 1–2 prove what else was eliminated.

| Proposition | Need |
| --- | --- |
| Something unusual happened | Orientation + measurement |
| We know what changed | Named survivor with mass |
| We know why it changed | Discriminating causal support |
| We know it matters operationally | Labels / business impact — often absent |

## Anti-patterns

- Deep-dive the ticket metric before health audit
- Treat every co-alert as an independent root cause
- Academic H1/H2/H3 essay before negative space
- `LOCALIZED_CAUSE_UNKNOWN` without proving what was eliminated
- Claim SUPPORTED merchant/campaign/botnet without discriminating evidence
- Collapse inference lag and tile lag into one story
- Train-only null panic when val-aligned
- Global containment actions when model/policy orientation is GREEN
