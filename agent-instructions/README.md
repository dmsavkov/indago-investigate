# Investigation docs (for you on this case)

Read these files **in this folder**. Do not search other repositories for CLIs or documentation trees.

| File | Use it for |
| --- | --- |
| `ACTIVATION.md` | Start here — case state, constraints, recommended loop |
| `tools.md` | Every CLI you may run: what it does, how, where it writes |
| `glossary.md` | Hypothesis directions, terminals, actions, claim statuses |
| `claim_tags.json` | Only claim tags/statuses allowed in judgment |
| `philosophy.md` | Elimination mindset (negative space, inhibitors, honest terminals) |
| `views_contract.md` | View shapes and binding rules |
| `rewrite_views.md` | Ugly alert/rules → derived + thin Views |
| `thresholds.md` | Package defaults — do not invent thresholds |
| `roles.md` | Closed `column_roles` vocabulary |
| `examples/views/` | Example View JSON |
| `examples/derived/` | Example rewritten alert/rules |

**Hard rules:** run only the investigation CLIs in `tools.md`. Pass case root as `.` or an absolute path — never a bare id. Do not flash, harvest, score gold, or invent host paths. Before closing, run `indago-investigate validate-judgment .` and fix the critique until OK.

If `indago-catalog`, `indago-health-audit`, or `indago-investigate` are missing from PATH, **stop** and tell the operator the package is not installed — they must follow the package installation guide.
