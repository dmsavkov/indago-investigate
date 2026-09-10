# Minimal pack template

Empty skeleton for your own investigation case.

## Contents

- `alert.json` — replace with your alert / KPI blip
- `evidence/live|ref/{data,models,rules}/` — drop CUR/REF tables and **required** model PKL
- `org-docs/` — optional short vocabulary notes
- `agent-instructions/` — full agent protocol (open `agent-instructions/README.md`)
- `out/views/` — you author Views here after peek
- `playground/` — scratch

## After copy

1. Install the package (`uv sync --extra score` or `pip install -e ".[score]"` from the package root).
2. Fill evidence + model; edit `alert.json`.
3. Attach / open `agent-instructions/README.md` for the agent.
4. `indago-catalog .` → peek → author Views → `validate-views` → health-audit → …

See also `docs/minimal-pack.md` in the package repository.
