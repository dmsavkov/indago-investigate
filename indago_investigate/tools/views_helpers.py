"""Helpers: resolve slice_key from Views when --key omitted (G3c V1)."""

from __future__ import annotations

import json
from pathlib import Path


def slice_key_from_views(case_root: Path) -> str | None:
    """Return slice_key column from out/views/frame_cur.json or bundle frames."""
    root = Path(case_root)
    candidates = [
        root / "out" / "views" / "frame_cur.json",
        root / "out" / "views" / "bundle.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if path.name == "frame_cur.json":
            roles = data.get("column_roles") or {}
            sk = roles.get("slice_key")
            if isinstance(sk, str):
                return sk
            if isinstance(sk, list) and sk:
                return str(sk[0])
        for fr in data.get("frames") or []:
            if not isinstance(fr, dict) or fr.get("split") != "cur":
                continue
            roles = fr.get("column_roles") or {}
            sk = roles.get("slice_key")
            if isinstance(sk, str):
                return sk
            if isinstance(sk, list) and sk:
                return str(sk[0])
    return None
