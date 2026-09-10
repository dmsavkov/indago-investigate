# Minimal template (empty contact skeleton)

Copy this folder, drop evidence, author Views, then run CLIs.

```bash
cp -r examples/minimal_template my_case
# put CUR parquet/csv → evidence/live/data/
# put REF parquet/csv → evidence/ref/data/
# put model PKL     → evidence/live/models/
# edit alert.json
```

Then: peek columns → write `out/views/` (see `docs/views_contract.md` + `docs/examples/views/`) → `validate-views` → `health-audit`.

Optional: add short notes under `org-docs/` (any text; agents may read if present).

Full checklist: [`docs/minimal-pack.md`](../../docs/minimal-pack.md).  
Runnable example with data: [`../demo_case/`](../demo_case/).
