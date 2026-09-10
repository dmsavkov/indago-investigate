"""Write evidence inventory (catalog.md / catalog.json). No auto-projected views by default."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from indago_investigate.inventory import RECOMMENDED_KINDS, inventory_evidence
from indago_investigate.refs import Availability, EvidenceRef


def _inventory_md(case_root: Path, refs: list[EvidenceRef]) -> str:
    now = datetime.now(timezone.utc).isoformat()
    missing = [k.value for k in RECOMMENDED_KINDS if not any(
        r.kind == k and r.availability == Availability.available for r in refs
    )]
    lines = [
        "# Evidence inventory",
        "",
        f"- generated_at: `{now}`",
        f"- case_root: `{case_root}`",
        "",
        "Open files at `location` as needed (case-local evidence only).",
        "Do **not** expect pre-built Views here; interim tools use case evidence paths.",
        "",
        "| Kind | Status | Location | Format | Limitations |",
        "|------|--------|----------|--------|-------------|",
    ]
    for r in refs:
        loc = r.location or "—"
        if len(loc) > 72:
            loc = "…" + loc[-69:]
        lim = "; ".join(r.limitations) if r.limitations else "—"
        if len(lim) > 60:
            lim = lim[:57] + "..."
        lines.append(
            f"| `{r.kind.value}` | {r.availability.value} | `{loc}` | {r.format.value} | {lim} |"
        )
    lines.append("")
    if missing:
        lines.append("## Missing recommended kinds")
        for m in missing:
            lines.append(f"- `{m}`")
        lines.append("")
    lines.append("## Next")
    lines.append("- CLI menu: `_shared/docs/tools.md`.")
    lines.append("- Orient: `indago-health-audit --profile ieee_flash` (case evidence/).")
    lines.append("")
    return "\n".join(lines)


def write_catalog(
    case_root: Path | str,
    *,
    out_dir: Path | str | None = None,
    materialize: bool = False,
) -> tuple[Path, Path]:
    """Write inventory catalog. `materialize=True` is opt-in legacy helper only."""
    root = Path(case_root).resolve()
    out = Path(out_dir) if out_dir else root / "out"
    out.mkdir(parents=True, exist_ok=True)

    refs = inventory_evidence(root)
    md_path = out / "catalog.md"
    json_path = out / "catalog.json"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_root": str(root),
        "refs": [r.model_dump(mode="json") for r in refs],
    }
    md_path.write_text(_inventory_md(root, refs), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote inventory catalog md={} json={}", md_path, json_path)

    if materialize:
        from indago_investigate.materialize import materialize_views

        views_dir = out / "views"
        views_dir.mkdir(parents=True, exist_ok=True)
        bundle = materialize_views(root)
        views_path = views_dir / "bundle.json"
        views_path.write_text(bundle.model_dump_json(indent=2) + "\n", encoding="utf-8")
        logger.warning(
            "wrote optional materialize bundle {} — prefer agent-owned views per views_contract",
            views_path,
        )

    return md_path, json_path


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(
        description="Write raw EvidenceRef inventory to out/catalog.md (default: no view projection)"
    )
    p.add_argument("case_root", type=Path, help="Pack or isolate case root")
    p.add_argument("--out", type=Path, default=None, help="Output dir (default: <case>/out)")
    p.add_argument(
        "--materialize",
        action="store_true",
        help="Opt-in: also write legacy convenience out/views/bundle.json (not recommended for eval)",
    )
    args = p.parse_args()
    write_catalog(args.case_root, out_dir=args.out, materialize=args.materialize)


if __name__ == "__main__":
    main()
