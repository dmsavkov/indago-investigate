# Glossary (hypotheses + terminals)

Short reference. Not a routing FSM.

## Hypothesis directions

| Direction | Meaning | Typical evidence | Often confused with |
| --- | --- | --- | --- |
| **Monitor / baseline reference** | Wrong/stale baseline card or threshold drift | Baseline card id/time, split hash, thresholds vs live | Real metric shifts that match a bad card |
| **Population / mix shift** | Input mix changed; model mapping may still be fine | Slice vs rest, concentration, mix vs REF | Feature ETL break on one slice |
| **Data transform / corruption** | Upstream nulls, zero-fills, unit/schema bugs | Dual-ref null/zero (train **and** val) | Population concentration that also moves nulls |
| **Train–serve skew** | Online feature path ≠ offline/batch | Online vs batch cols, velocity zeros, feature_contract | Pure infra lag with healthy features |
| **Model artifact / promotion** | Wrong binary, bad deploy, score-path defect | Offline rescore on REF; registry vs live | Policy/rules that move decisions only |
| **Policy / rules** | Decision layer changed | Rules hash, fixed-score replay | Score shift with stable rules |
| **Infra / runtime / stream** | Lag, consumer stall, store/serving fault | Channel-split queues (inference ≠ tile) | Tile lag explaining score changes |
| **Label evaluation / maturation** | Eval/KPI illusion; labels absent/immature | `label_state`, maturation, recon | Blaming champion for label-policy alert |
| **Insufficient evidence / small-n** | Cannot safely decide | Missing refs, tiny window n | Forcing `ROOT_CAUSE_FOUND` |

## Terminals

| Terminal | Meaning | Typical action |
| --- | --- | --- |
| `ROOT_CAUSE_FOUND` | Mechanism identified with discriminating support | Fix-class (`fix_serving`, …) |
| `BENIGN` | Not action-worthy as a break | `monitor_only` |
| `LOCALIZED_CAUSE_UNKNOWN` | Localized real pattern; **mechanism/origin** unknown | `domain_review` |
| `IMPACT_CONFIRMED_CAUSE_UNKNOWN` | Impact real; cause open | `domain_review` / collect more |
| `INSUFFICIENT_EVIDENCE` | Missing data blocks a call | request / stop |
| `TOOL_LIMITATION` | Tools cannot measure what is needed | escalate tooling |

**Disposition:** Defect class with discriminating proof → `ROOT_CAUSE_FOUND`. Localization without causal origin (mix/slice/traffic) → `LOCALIZED_CAUSE_UNKNOWN`. Do not treat every supported claim tag as automatic FOUND.

## Claim statuses (Layer A twin)

| Status | Use when |
| --- | --- |
| `supported` / `associated` | This tag **is** (part of) the primary mechanism. On **forbidden** tags, both statuses are Layer A **hard fails** (same as overclaim). |
| `falsified` / `falsified_as_primary` | This tag is **eliminated** as primary RCA (e.g. healthy model plane) |
| `unknown` | Cannot decide this tag from evidence |
| `weakened` / `not_claimed` | Soft / absent |

Wrong polarity example: marking `model_artifact` as `supported` because “model is green” — gold usually wants `falsified_as_primary`.

**Closed enums:** `decision.terminal` and `decision.action_class` must be glossary/gold vocabulary. Unknown values → schema hard fail (`validate-judgment` / Layer A).

**Inhibitors:** gold `required_inhibitors` missing → `pass_grounding=false` → overall fail (anchors stay soft).

## Online velocity naming (avoid false alarms)

| Name | What it is | How to read |
| --- | --- | --- |
| `online_card1_txn_count_day` / `online_uid_*` | **Numeric tile values** (serving features) | High **zero_rate** ⇒ tiles empty / flush / consumer pause (F2-class) |
| `online_velocity_zero_at_fetch` | **Boolean flag** on CUR (1/True = “velocity was zero at fetch”) | Rate of True ≈ monitor check “% zero at fetch”. Do **not** treat profile-table `zero_rate` on this flag as the monitor metric — `zero_rate` means “fraction of values equal to 0”, which inverts a 0/1 flag. |
| Monitor check id `online_velocity_zero_at_fetch` | Suite metric with its own `zero_rate` in the snapshot | Prefer this (or mean of the flag) over `profile-table` high_zero_mass for this column |

Role `online_velocity` in Views should prefer the **numeric tile columns**; the flag is a companion signal, not the score/amount.
## Actions (pairing hints)

| Action | Usually with |
| --- | --- |
| `monitor_only` | `BENIGN` |
| `domain_review` | `LOCALIZED_CAUSE_UNKNOWN` (mix / slice / traffic origin unknown) |
| `collect_labels` | Label/maturation gap |
| `fix_policy` / `update_runbook` / `restore_rules` | Policy hash / live≠baseline rules → `ROOT_CAUSE_FOUND` |
| `fix_serving` / `restore_stream_tiles` | Empty/stale online tiles with healthy inference → `ROOT_CAUSE_FOUND` |
| `pipeline_fix` | Generic pipeline break only — **not** a synonym for policy drift |
| `rollback_model` | Only if model plane implicated — **inhibited** when model orientation is healthy |

Put required inhibitors on `judgment_struct.json` → `decision.inhibitors` (not only in markdown). Primary mechanism tags use `supported` (or `associated` only when truly secondary — gold often requires `supported` for the named slice/mix).
