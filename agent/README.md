# Investigation docs (for you on this case)

Read these files in this folder. Do not look for other documentation trees. Do not search other repositories for CLIs.

| File | Use it for |
| --- | --- |
| `tools.md` | Every CLI you may run: what it does, how, where it writes |
| `glossary.md` | Hypothesis directions, terminals, actions, claim statuses |
| `claim_tags.json` | Only claim tags/statuses allowed in judgment |
| `philosophy.md` | Elimination mindset (negative space, inhibitors, honest terminals) |

Your case paste lives at `f-cases/<CASE>/ACTIVATION.md` (not in this folder).

**Hard rules:** run only the investigation CLIs in `tools.md`. Pass case root as `.` or an absolute path — never a bare id. Do not flash, harvest, score, or open gold. Before closing, run `indago-investigate validate-judgment .` and fix the critique until OK.
