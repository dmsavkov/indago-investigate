# Closed column roles (mvp-generality §B.1)

Machine SoT: `indago_investigate.roles.COLUMN_ROLES`.

| Role | Meaning |
|------|---------|
| `score` | Model score / risk |
| `decision` | Approve/decline (or equiv.) |
| `slice_key` | Primary entity/slice column |
| `amount` | Monetary / volume |
| `product` | Product / cohort code |
| `policy_hash` | Rules fingerprint on rows |
| `timestamp` | Event time |
| `online_velocity` | Online serving features |

Tools must not invent IEEE column names; use these roles (Views) or explicit `--key`.
