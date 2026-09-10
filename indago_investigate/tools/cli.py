"""Investigation package CLI — full L0/L1/L2 surface.

  uv run indago-investigate <command> <case_root> [options]
  uv run indago-investigate --list
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from indago_investigate.tools import actions
from indago_investigate.tools.runtime import bind_case, write_report
from indago_investigate.views_bind import ViewsRequiredError, enforce_views_or_raise

CommandFn = Callable[..., dict[str, Any]]

# L0 helpers that must work before Views exist (authoring substrate).
_VIEWS_OPTIONAL_COMMANDS = frozenset(
    {
        "validate-alert",
        "validate-judgment",
        "validate-views",
        "peek-frame",
        "peek-json",
        "peek-model",
        "emit-judgment",
        "request-missing-evidence",
    }
)

COMMANDS: dict[str, dict[str, Any]] = {
    "validate-alert": {"fn": lambda **_: actions.validate_alert(), "level": "L0"},
    "validate-judgment": {"fn": lambda **_: actions.validate_judgment(), "level": "L0"},
    "validate-views": {
        "fn": lambda views_dir=None, strict=False, **_: actions.validate_views(
            views_dir=views_dir, strict=strict
        ),
        "level": "L0",
        "args": ["views_dir", "strict"],
    },
    "peek-frame": {
        "fn": lambda path=None, head=5, **_: actions.peek_frame(path=path, head=head),
        "level": "L0",
        "args": ["path", "head"],
    },
    "peek-json": {
        "fn": lambda path=None, **_: actions.peek_json(path=path),
        "level": "L0",
        "args": ["path"],
    },
    "peek-model": {
        "fn": lambda path=None, **_: actions.peek_model(path=path),
        "level": "L0",
        "args": ["path"],
    },
    "profile-table": {
        "fn": lambda frame="cur", **_: actions.profile_table(frame=frame),
        "level": "L1",
        "args": ["frame"],
    },
    "compare-distributions": {
        "fn": lambda frame_a="cur", frame_b="ref_val", **_: actions.compare_distributions(
            frame_a=frame_a, frame_b=frame_b
        ),
        "level": "L1",
        "args": ["frame_a", "frame_b"],
    },
    "score-offline": {
        "fn": lambda frame="cur", model_path=None, **_: actions.score_offline(
            frame=frame, model_path=model_path
        ),
        "level": "L1",
        "args": ["frame", "model_path"],
    },
    "parity-compare": {
        "fn": lambda frame="cur", **_: actions.parity_compare(frame=frame),
        "level": "L1",
        "args": ["frame"],
    },
    "replay-policy": {"fn": lambda **_: actions.replay_policy(), "level": "L1"},
    "slice-summary": {
        "fn": lambda key=None, frame="cur", ref="ref_val", rescore=False, model_path=None, score_col_name=None, **_: actions.slice_summary(
            key=key,
            frame=frame,
            ref=ref,
            rescore=rescore,
            model_path=model_path,
            score_col_name=score_col_name,
        ),
        "level": "L1",
        "args": ["key", "frame", "ref", "rescore", "model_path", "score_col_name"],
    },
    "topk-importance": {
        "fn": lambda model_path=None, importance_path=None, model_view=None, **_: actions.topk_importance(
            model_path=model_path,
            importance_path=importance_path,
            model_view=model_view,
        ),
        "level": "L1",
        "args": ["model_path", "importance_path", "model_view"],
    },
    "timeline-correlate": {"fn": lambda **_: actions.timeline_correlate(), "level": "L1"},
    "lineage-extract": {"fn": lambda **_: actions.lineage_extract(), "level": "L1"},
    "dual-ref-null": {"fn": lambda **_: actions.dual_ref_null_report(), "level": "L2"},
    "score-tail": {
        "fn": lambda frame="cur", rescore=False, model_path=None, score_col_name=None, **_: actions.score_tail_report(
            frame=frame,
            rescore=rescore,
            model_path=model_path,
            score_col_name=score_col_name,
        ),
        "level": "L2",
        "args": ["frame", "rescore", "model_path", "score_col_name"],
    },
    "policy-accountability": {"fn": lambda **_: actions.policy_accountability(), "level": "L2"},
    "concentration": {
        "fn": lambda key=None, rescore=False, model_path=None, score_col_name=None, **_: actions.concentration_report(
            key=key,
            rescore=rescore,
            model_path=model_path,
            score_col_name=score_col_name,
        ),
        "level": "L2",
        "args": ["key", "rescore", "model_path", "score_col_name"],
    },
    "online-vs-batch": {"fn": lambda **_: actions.online_vs_batch_velocity(), "level": "L2"},
    "baseline-card-diff": {"fn": lambda **_: actions.baseline_card_diff(), "level": "L2"},
    "request-missing-evidence": {"fn": lambda **_: actions.request_missing_evidence(), "level": "L0"},
    "emit-judgment": {
        "fn": lambda terminal=None, action=None, **_: actions.emit_judgment_stub(
            terminal=terminal, action=action
        ),
        "level": "L0",
        "args": ["terminal", "action"],
    },
}


def _md_for(name: str, payload: dict[str, Any]) -> str:
    if name == "validate-judgment" and isinstance(payload.get("critique"), str):
        return payload["critique"]
    lines = [
        f"# {name}",
        "",
        f"- level: `{(COMMANDS.get(name) or {}).get('level', '?')}`",
        f"- case: `{payload.get('case_root')}`",
        "",
        "## Result",
        "",
        "```json",
        json.dumps(payload, indent=2, default=str)[:12000],
        "```",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="indago-investigate",
        description="Investigation package CLI (L0–L2) for a single case root.",
    )
    p.add_argument("--list", action="store_true", help="List investigation commands")
    p.add_argument("command", nargs="?", help="Tool command (see --list)")
    p.add_argument("case_root", nargs="?", type=Path, help="Pack or isolate case root")
    p.add_argument("--profile", default="ieee_flash", choices=["ieee_flash"])
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--frame", default="cur")
    p.add_argument("--frame-a", default="cur")
    p.add_argument("--frame-b", default="ref_val")
    p.add_argument(
        "--key",
        default=None,
        help="Slice/concentration column (required for slice-summary and concentration; no default)",
    )
    p.add_argument("--ref", default="ref_val")
    p.add_argument("--terminal", default=None)
    p.add_argument("--action", default=None)
    p.add_argument("--path", default=None, help="Relative path under case (peek-*)")
    p.add_argument("--head", type=int, default=5, help="peek-frame head rows")
    p.add_argument("--views-dir", type=Path, default=None)
    p.add_argument("--strict", action="store_true", help="validate-views: WARN→ERROR")
    p.add_argument(
        "--model-path",
        default=None,
        help="Case-relative PKL for score-offline / topk-importance",
    )
    p.add_argument(
        "--importance-path",
        default=None,
        help="Case-relative precomputed importance JSON for topk-importance",
    )
    p.add_argument(
        "--model-view",
        default=None,
        help="Path to ModelView JSON (default out/views/model.json)",
    )
    p.add_argument(
        "--rescore",
        action="store_true",
        help="Cohort tools: score via model offline predict instead of score column",
    )
    p.add_argument(
        "--score-col",
        default=None,
        dest="score_col_name",
        help="Cohort tools: explicit score column (else Views column_roles.score)",
    )
    args = p.parse_args(argv)

    if args.list or not args.command:
        print("Investigation commands (use only these on a case):\n")
        for name, meta in sorted(COMMANDS.items(), key=lambda x: (x[1]["level"], x[0])):
            print(f"  {meta['level']:3}  indago-investigate {name} <case_root>")
        print("\nAlso allowed: indago-catalog | indago-health-audit")
        print("Optional (ops/dogfood only): indago-materialize — not the agent path")
        print("Do not run other indago-* binaries (ops/lab) during investigation.")
        if not args.command:
            return

    if args.command not in COMMANDS:
        raise SystemExit(f"unknown command {args.command!r}; use --list")
    if args.case_root is None:
        raise SystemExit("case_root required")

    # G3c V1: --key required unless Views provide slice_key
    if args.command in ("slice-summary", "concentration") and not args.key:
        from indago_investigate.tools.views_helpers import slice_key_from_views

        sk = slice_key_from_views(args.case_root)
        if sk:
            args.key = sk
            logger.info("{} using Views slice_key={!r}", args.command, sk)
        else:
            raise SystemExit(
                f"{args.command} requires --key <column> or out/views with slice_key role"
            )

    if args.command.startswith("peek-") and not args.path:
        raise SystemExit(f"{args.command} requires --path <relative-or-jailed-path>")

    bind_case(args.case_root, profile=args.profile, out_dir=args.out)
    meta = COMMANDS[args.command]
    fn = meta["fn"]

    if args.command not in _VIEWS_OPTIONAL_COMMANDS:
        try:
            enforce_views_or_raise(Path(args.case_root), need_splits=("cur",))
        except ViewsRequiredError as exc:
            payload = exc.as_payload(tool=args.command)
            write_report(args.command.replace("-", "_"), payload)
            print(json.dumps(payload, indent=2, default=str))
            raise SystemExit(2) from exc

    kwargs: dict[str, Any] = {}
    if "frame" in meta.get("args", []):
        kwargs["frame"] = args.frame
    if "frame_a" in meta.get("args", []):
        kwargs["frame_a"] = args.frame_a
    if "frame_b" in meta.get("args", []):
        kwargs["frame_b"] = args.frame_b
    if "key" in meta.get("args", []):
        kwargs["key"] = args.key
    if "ref" in meta.get("args", []):
        kwargs["ref"] = args.ref
    if "terminal" in meta.get("args", []):
        kwargs["terminal"] = args.terminal
    if "action" in meta.get("args", []):
        kwargs["action"] = args.action
    if "path" in meta.get("args", []):
        kwargs["path"] = args.path
    if "head" in meta.get("args", []):
        kwargs["head"] = args.head
    if "views_dir" in meta.get("args", []):
        kwargs["views_dir"] = str(args.views_dir) if args.views_dir else None
    if "strict" in meta.get("args", []):
        kwargs["strict"] = bool(args.strict)
    if "model_path" in meta.get("args", []):
        kwargs["model_path"] = args.model_path
    if "importance_path" in meta.get("args", []):
        kwargs["importance_path"] = args.importance_path
    if "model_view" in meta.get("args", []):
        kwargs["model_view"] = args.model_view
    if "rescore" in meta.get("args", []):
        kwargs["rescore"] = bool(args.rescore)
    if "score_col_name" in meta.get("args", []):
        kwargs["score_col_name"] = args.score_col_name

    logger.info("indago-investigate {} case={}", args.command, args.case_root)
    try:
        payload = fn(**kwargs)
    except ViewsRequiredError as exc:
        payload = exc.as_payload(tool=args.command)
        write_report(args.command.replace("-", "_"), payload)
        print(json.dumps(payload, indent=2, default=str))
        raise SystemExit(2) from exc
    tool_name = args.command.replace("-", "_")
    # L1/L2: JSON only under out/reports/. MD for critiques.
    also_md = args.command in ("validate-judgment", "validate-views")
    md_body = None
    if also_md and isinstance(payload.get("critique"), str):
        md_body = payload["critique"]
    elif also_md and args.command == "validate-judgment":
        md_body = _md_for(args.command, {**payload})
    write_report(
        tool_name,
        payload,
        md_body=md_body,
        write_md=also_md and md_body is not None,
    )

    # validate-judgment: print the human critique first (agent/human primary UX)
    if args.command == "validate-judgment" and isinstance(payload.get("critique"), str):
        print(payload["critique"])
        if not payload.get("ok"):
            raise SystemExit(1)
        return

    if args.command == "validate-views":
        if isinstance(payload.get("critique"), str):
            print(payload["critique"])
            print("---")
        print(json.dumps(payload, indent=2, default=str))
        if not payload.get("ok"):
            raise SystemExit(1)
        return

    if args.command.startswith("peek-"):
        print(json.dumps(payload, indent=2, default=str)[:12000])
        if payload.get("exit_hint") == 2 or payload.get("ok") is False:
            raise SystemExit(2)
        return

    # short stdout (avoid dumping full dtypes)
    skip = {"dtypes", "critique", "scores"}
    summary = {k: v for k, v in payload.items() if k not in skip}
    keys = list(summary)[:14]
    print(json.dumps({k: summary[k] for k in keys}, indent=2, default=str))

    if payload.get("ok") is False and payload.get("error_class") in (
        "model_frame_mismatch",
        "model_unloadable",
    ):
        raise SystemExit(2)
    if payload.get("ok") is False and args.command in (
        "slice-summary",
        "concentration",
        "score-tail",
        "score-offline",
        "topk-importance",
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
