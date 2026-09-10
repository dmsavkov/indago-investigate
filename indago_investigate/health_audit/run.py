"""Run system health audit — primary orientation artifact (Option C ieee_flash)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from indago_investigate.bind_mode import get_bind_mode
from indago_investigate.health_audit.case_io import CaseIO, set_case_io
from indago_investigate.health_audit.common import build_sources_meta, load_context
from indago_investigate.health_audit.helpers import save_json, write_md
from indago_investigate.health_audit.planes import build_alert_digest, build_all_planes
from indago_investigate.health_audit.plots import write_plots
from indago_investigate.health_audit.render import render_markdown


def build_payload(*, case_id: str | None = None, no_plots: bool = False) -> dict[str, Any]:
    ctx = load_context()
    planes = build_all_planes(ctx)
    alert_digest = build_alert_digest(ctx)
    limitations = [
        f"CUR n={ctx['n_cur']} — PSI/KS/W1 and rate deltas are noisy below ~100–200 events.",
        "Outcome labels absent ⇒ business impact UNKNOWN; no live fraud-rate validation.",
        "Slice discovery uses offline champion scores on REF val (labels preferred when present).",
        "Profile ieee_flash assumes flashed IEEE-like paths/fields under case evidence/ (interim bind).",
        "Thresholds are package defaults (see _shared/docs/thresholds.md) — not a customer baseline card.",
        "PSI bands: <0.10 stable (GREEN), 0.10–0.25 watch (WARN), >0.25 investigate (ALERT).",
        "Absent infra/dbt/git evidence ⇒ UNKNOWN (not assessed), not WARN-as-broken.",
    ]
    if ctx.get("baseline", {}).get("_derived_from_ref"):
        limitations.append(
            "Baseline scalars derived from REF val (DerivedBaseline) — no monitor baseline card required."
        )
    if alert_digest.get("git_sha") in (None, "unknown"):
        limitations.append("git_sha unknown — code provenance not assessed.")
    if planes["infra"].get("anomaly"):
        limitations.append("Infra: treat tile Kafka lag separately from inference lag.")
    limitations.append("Native feature importances only (trees/coef_/NB); permutation unsupported.")

    from indago_investigate.health_audit.case_io import get_case_io

    io = get_case_io()
    cid = case_id or io.case_root.name
    roles_resolved: dict[str, Any] = {}
    roles_missing: list[str] = []
    paths_opened: list[str] = []
    views_gate: dict[str, Any] | None = None
    views_dir = io.case_root / "out" / "views"
    if views_dir.is_dir():
        from indago_investigate.validate_views import validate_views

        views_gate = validate_views(io.case_root, views_dir=views_dir, strict=False)
        roles_resolved = views_gate.get("roles_resolved") or {}
        roles_missing = list(views_gate.get("roles_missing") or [])
        paths_opened = list(views_gate.get("paths_opened") or [])
        if not views_gate.get("ok"):
            limitations.append(
                "validate-views ERROR present — role-gated planes must not be trusted as GREEN "
                f"({views_gate.get('error_count')} errors)."
            )
        view_jsons = [p for p in views_dir.glob("*.json")]
        if not view_jsons:
            limitations.append(
                "out/views/ has no View JSON — author Views per views_contract.md for role binding."
            )

    # §B.14: every UNKNOWN plane must name missing_roles / inputs / hints
    _default_hints = [
        "Author or fix Views per _shared/docs/views_contract.md (or package/docs/views_contract.md)",
        "Run indago-investigate validate-views .",
        "Optional: peek-frame / peek-json / peek-model when paths exist",
    ]
    for _pname, plane in planes.items():
        if str(plane.get("status")) != "UNKNOWN":
            continue
        if not plane.get("missing_roles"):
            inferred: list[str] = []
            for tag in roles_missing:
                if ":" in str(tag):
                    inferred.append(str(tag).split(":", 1)[1])
                else:
                    inferred.append(str(tag))
            plane["missing_roles"] = inferred or ["(unspecified — see finding)"]
        if not plane.get("missing_inputs"):
            plane["missing_inputs"] = [
                f"plane={_pname}",
                f"finding={plane.get('finding')}",
            ]
        if not plane.get("hints"):
            plane["hints"] = list(_default_hints)

    payload: dict[str, Any] = {
        "case_id": cid,
        "product": "ieee",
        "profile": io.profile,
        "bind_mode": get_bind_mode(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"n_events": ctx["n_cur"], "capacity": alert_digest.get("window")},
        "alert_digest": alert_digest,
        "planes": planes,
        "roles_resolved": roles_resolved,
        "roles_missing": roles_missing,
        "paths_opened": paths_opened,
        "views_validate": {
            "ok": None if views_gate is None else views_gate.get("ok"),
            "error_count": None if views_gate is None else views_gate.get("error_count"),
        },
        "composite": (planes["macro"].get("metrics") or {}).get("composite"),
        "limitations": limitations,
        "sources": build_sources_meta(ctx),
        "plots": [],
    }
    if not no_plots:
        payload["plots"] = write_plots(payload)
    return payload


def run_health_audit(
    case_root: Path | str,
    *,
    profile: str = "ieee_flash",
    out_dir: Path | str | None = None,
    no_plots: bool = False,
    case_id: str | None = None,
    strict_roles: bool = False,
) -> dict[str, Any]:
    if profile != "ieee_flash":
        raise ValueError(f"unsupported profile {profile!r}; only ieee_flash in Phase 2")
    root = Path(case_root)
    set_case_io(CaseIO(case_root=root, profile=profile, out_dir=Path(out_dir) if out_dir else None))
    logger.info("health_audit start case_root={} profile={} bind={}", root, profile, get_bind_mode())

    from indago_investigate.validate_views import validate_views
    from indago_investigate.views_bind import ViewsRequiredError, enforce_views_or_raise

    try:
        enforce_views_or_raise(root, need_splits=("cur",))
    except ViewsRequiredError as exc:
        payload = {
            **exc.as_payload(tool="health_audit"),
            "case_id": case_id or root.name,
            "profile": profile,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "planes": {},
            "limitations": [
                "health_audit blocked: Views required under INDAGO_BIND=views (default).",
            ],
        }
        text = (
            "# SYSTEM HEALTH AUDIT — BLOCKED (Views required)\n\n"
            f"**Error:** `{exc.message}`\n\n"
            "**Hints:**\n"
            + "\n".join(f"- {h}" for h in payload["hints"])
            + "\n\nViews are the substrate for orientation and L1 tools — author them before audit.\n"
        )
        write_md("health_audit.md", text)
        save_json("health_audit.json", payload)
        logger.error("health_audit blocked: {}", exc.message)
        raise SystemExit(2) from exc

    # B1 optional: path-only OK by default; --strict-roles fails when plane roles missing
    if strict_roles:
        gate = validate_views(root, strict=True)
        if not gate.get("ok"):
            payload = {
                "ok": False,
                "error": "strict_roles",
                "message": "Views missing required roles under --strict-roles",
                "validate_views": {
                    "ok": False,
                    "errors": (gate.get("errors") or [])[:20],
                },
                "case_id": case_id or root.name,
                "profile": profile,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "planes": {},
            }
            write_md(
                "health_audit.md",
                "# SYSTEM HEALTH AUDIT — BLOCKED (--strict-roles)\n\n"
                + "\n".join(f"- {e}" for e in (gate.get("errors") or [])[:12])
                + "\n",
            )
            save_json("health_audit.json", payload)
            logger.error("health_audit blocked: strict_roles")
            raise SystemExit(2)

    payload = build_payload(case_id=case_id or root.name, no_plots=no_plots)
    text = render_markdown(payload)
    md_path = write_md("health_audit.md", text)
    json_path = save_json("health_audit.json", payload)
    logger.info("wrote {} and {}", md_path, json_path)
    return payload


def main() -> None:
    p = argparse.ArgumentParser(
        description="Stage-1 system health audit (Option C: --profile ieee_flash)"
    )
    p.add_argument("case_root", type=Path, help="Pack or isolate case root")
    p.add_argument(
        "--profile",
        default="ieee_flash",
        choices=["ieee_flash"],
        help="Path/field binding profile (required intent: ieee_flash)",
    )
    p.add_argument("--out", type=Path, default=None, help="Output dir (default: <case>/out)")
    p.add_argument("--no-plots", action="store_true")
    p.add_argument("--case-id", default=None)
    p.add_argument(
        "--strict-roles",
        action="store_true",
        help="Fail if FrameViews lack roles needed for full planes (B1 optional gate)",
    )
    args = p.parse_args()
    payload = run_health_audit(
        args.case_root,
        profile=args.profile,
        out_dir=args.out,
        no_plots=args.no_plots,
        case_id=args.case_id,
        strict_roles=bool(args.strict_roles),
    )
    print(f"composite={payload.get('composite')}")
    planes = payload.get("planes") or {}
    for name in ("lineage", "infra", "feature", "population", "model", "decision", "business", "macro"):
        pl = planes.get(name) or {}
        print(f"  {name}: {pl.get('status')}")


if __name__ == "__main__":
    main()
