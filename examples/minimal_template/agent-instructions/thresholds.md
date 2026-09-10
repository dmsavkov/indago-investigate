# Package thresholds (agent-facing)

**Source of truth:** `indago_investigate.health_audit.thresholds` (Python `THR` + PSI bands).  
These are **INDAGO defaults**, not customer policy cards. Do **not** invent cutoffs in judgment.

## PSI (population stability)

| PSI | Band | HA status |
|-----|------|-----------|
| &lt; 0.10 | Stable | GREEN |
| 0.10 – 0.25 | Moderate / Watch | WARN |
| &gt; 0.25 | Significant / Investigate | ALERT |

## REF-delta and rate defaults (selected)

| Key | Default | Meaning |
|-----|---------|---------|
| `null_delta_train` | 0.20 | Null-rate Δ vs REF train → spike |
| `null_val_align` | 0.05 | Val-alignment tolerance for dual-null story |
| `pred_mean_abs` | 0.015 | \|CUR − REF\| mean score |
| `concentration_share` | 0.25 | Slice share flag |
| `concentration_ratio` | 2.0 | Slice vs expected ratio |
| `ks_alert` / `w1_alert` | 0.25 / 0.08 | Score ECDF distance (noisy at small-n) |
| `parity_abs` | 1e-4 | Offline vs online score parity |
| `small_n` | 100 | Below this, treat drift stats as exploratory |

Full key list ships in HA check `threshold=` fields and package `THR` dict.

## What not to do

- Do not ask the customer for a threshold/hash “baseline card” for contact.
- Prefer REF-derived means/n when a monitor baseline JSON is absent.
- Missing infra/dbt/git evidence → plane **UNKNOWN** (not assessed), not WARN-as-broken.
