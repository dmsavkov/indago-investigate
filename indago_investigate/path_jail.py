"""Path jail: resolve handles only under case_root (mvp-generality §B.3)."""

from __future__ import annotations

from pathlib import Path


class PathJailError(ValueError):
    """Path missing, unreadable, or escapes case_root."""


def jail_resolve(case_root: Path | str, path_or_handle: str | Path) -> Path:
    """Resolve path_or_handle to a real file under case_root.

    Rejects ``..`` escapes and absolute paths outside the case.
    Relative paths are joined to case_root. Absolute paths must still
    realpath-contain under case_root.
    """
    root = Path(case_root).resolve()
    raw = str(path_or_handle).strip().replace("\\", "/")
    if not raw:
        raise PathJailError("empty path_or_handle")

    cand = Path(raw)
    if not cand.is_absolute():
        # Strip leading ./ and reject early ".." segments before resolve
        parts = [p for p in Path(raw).parts if p not in (".",)]
        if ".." in parts:
            # Still allow resolve to prove containment after join
            pass
        cand = (root / raw).resolve()
    else:
        cand = cand.resolve()

    try:
        cand.relative_to(root)
    except ValueError as exc:
        raise PathJailError(f"path escapes case_root: {path_or_handle!r}") from exc

    if not cand.exists():
        raise PathJailError(f"path missing under case: {path_or_handle!r} → {cand}")
    return cand


def case_relative(case_root: Path | str, path: Path | str) -> str:
    """Return POSIX-ish relative path under case_root when possible."""
    root = Path(case_root).resolve()
    p = Path(path).resolve()
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return str(p)
