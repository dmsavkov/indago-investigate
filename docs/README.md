# Package engineer docs (not flashed)

Design / policy for maintainers. **Agent corpus lives only in `package/agent/`** — do not copy or mirror those files here.

| File | Role |
| --- | --- |
| [`cli-surfaces.md`](cli-surfaces.md) | Investigation package CLI vs parent meta |
| [`views_policy.md`](views_policy.md) | Option C freeze (ieee_flash now; Views deferred) |
| [`views_contract.md`](views_contract.md) | View shapes for a future `--from-views` phase |
| [`PACK_ADD.md`](PACK_ADD.md) | **Frozen** how to add FN packs + gold/refs + lab env |

Operator how-to (lab flash): `package/docs/ops-flash.md`.  
Public package README: `package/README.md`.  
Minimal pack checklist: `package/docs/minimal-pack.md`.
Directional notes: `context/package/`.  
Flash source: `package/agent/` → isolate `f-cases/_shared/docs/`.
