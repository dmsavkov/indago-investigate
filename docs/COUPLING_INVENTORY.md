# Package coupling inventory

**Updated:** 2026-09-10 (Stages 2–4)  
**SoT:** `context/package/public-package-plan.md` §F  

---

## Boundary status

| Check | Result |
|-------|--------|
| `import agent\|eval\|scripts` from package | **None** |
| Install unit | ✅ `package/pyproject.toml` (`indago-investigate`) — ops CLIs not included |
| Isolated install smoke | ✅ `test_isolated_package_install` |
| Demo without lab env | ✅ scorer uses current interpreter; lab walk only if `INDAGO_LAB_*` / `INDAGO_ALLOW_LAB_DISCOVERY` |
| Views path rename smoke | ✅ `test_synthetic_rename_smoke` |
| Python floor (package) | ✅ `>=3.12` proven on 3.12 venv + 3.13 lab |

---

## Classes

| ID | Class | Status |
|----|-------|--------|
| C1 | Install | **Mitigated** — package pyproject; root still fat for lab |
| C2 | Ops entry points | **Mitigated** on package install; remain on root |
| C3 | CaseIO path folklore | Still in CaseIO/inventory candidates; views path does not need them for demo |
| C4 | Column folklore | **Gated** in `planes.py` behind `caseio`; grep test; rename smoke |
| C5 | `ieee_flash` profile name | Open (Stage 5+ rename) |
| C6 | Lab scorer | **Mitigated** — no silent sibling walk |
| C7 | Overfetch | Default off |
| C8 | Playground digests | Soft miss → empty/UNKNOWN |
| C9 | `_shared/` docs paths | Open (Stage 5) |
| C10 | Example claim tags | Cosmetic |

---

## Env (public path)

| Var | Public |
|-----|--------|
| `INDAGO_BIND=views` | default |
| `INDAGO_LAB_ROOT` / `INDAGO_ALLOW_LAB_DISCOVERY` | unset |
| `INDAGO_ALLOW_OVERFETCH` | unset |
