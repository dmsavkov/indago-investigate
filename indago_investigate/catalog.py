"""Write evidence inventory (catalog.md / catalog.json). Present files only (schema 2)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from indago_investigate.inventory import catalog_payload, list_present_files


def _inventory_md(case_root: Path, files: list) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Evidence inventory",
        "",
        f"- generated_at: `{now}`",
        f"- case_root: `{case_root}`",
        f"- catalog_schema: `2` (present files only)",
        "",
        "Case-local files that exist on disk. Bind paths via Views; do not invent missing assets.",
        "",
        "| Rel | Class | Format | Size | Rows | Cols |",
        "|-----|-------|--------|------|------|------|",
    ]
    for f in files:
        size = f.size_bytes
        size_s = f"{size:,}" if size < 10_000_000 else f"{size / 1_048_576:.1f} MiB"
        rows = "—" if f.n_rows is None else str(f.n_rows)
        cols = "—" if f.n_cols is None else str(f.n_cols)
        lines.append(
            f"| `{f.rel}` | `{f.class_}` | `{f.format}` | {size_s} | {rows} | {cols} |"
        )
    lines.append("")
    lines.append("## Next")
    lines.append("- Protocol: `agent-instructions/README.md` (then ACTIVATION / tools).")
    lines.append("- Bind Views under `out/views/` → `indago-investigate validate-views .`")
    lines.append("- Orient: `indago-health-audit . --no-plots`")
    lines.append("")
    return "\n".join(lines)


def write_catalog(
    case_root: Path | str,
    *,
    out_dir: Path | str | None = None,
    materialize: bool = False,
) -> tuple[Path, Path]:
    """Write present-file catalog. `materialize=True` is opt-in legacy helper only."""
    root = Path(case_root).resolve()
    out = Path(out_dir) if out_dir else root / "out"
    out.mkdir(parents=True, exist_ok=True)

    files = list_present_files(root)
    payload = catalog_payload(root)
    md_path = out / "catalog.md"
    json_path = out / "catalog.json"
    md_path.write_text(_inventory_md(root, files), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote inventory catalog md={} json={} n_files={}", md_path, json_path, len(files))

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
        description="Write present-file inventory to out/catalog.md + catalog.json"
    )
    p.add_argument("case_root", type=Path, help="Pack or isolate case root")
    p.add_argument("--out", type=Path, default=None, help="Output dir (default: <case>/out)")
    p.add_argument(
        "--materialize",
        action="store_true",
        help="Opt-in: also write legacy convenience out/views/bundle.json (not recommended)",
    )
    args = p.parse_args()
    write_catalog(args.case_root, out_dir=args.out, materialize=args.materialize)


if __name__ == "__main__":
    main()
