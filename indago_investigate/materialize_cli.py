"""CLI: opt-in materialize raw EvidenceRefs → out/views/bundle.json (Option C Phase 2b helper)."""

from __future__ import annotations

import argparse
from pathlib import Path

from loguru import logger

from indago_investigate.catalog import write_catalog


def main() -> None:
    p = argparse.ArgumentParser(
        description="Materialize convenience Views under out/views/ (opt-in; not default inventory)"
    )
    p.add_argument("case_root", type=Path)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    md, js = write_catalog(args.case_root, out_dir=args.out, materialize=True)
    logger.info("materialize via catalog complete md={} json={}", md, js)
    print(md)
    print(Path(args.out or Path(args.case_root) / "out") / "views" / "bundle.json")


if __name__ == "__main__":
    main()
