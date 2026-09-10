"""Validate judgment_struct.json — schema shape + closed tags; human/agent critique."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATUS_ENUM = frozenset(
    {
        "supported",
        "associated",
        "falsified",
        "weakened",
        "unknown",
        "not_claimed",
        "falsified_as_primary",
    }
)

TERMINAL_ENUM = frozenset(
    {
        "ROOT_CAUSE_FOUND",
        "BENIGN",
        "IMPACT_CONFIRMED_CAUSE_UNKNOWN",
        "LOCALIZED_CAUSE_UNKNOWN",
        "INSUFFICIENT_EVIDENCE",
        "TOOL_LIMITATION",
    }
)

# Closed action vocabulary (glossary + F0–F4 gold synonyms). Unknown → schema hard fail.
ACTION_ENUM = frozenset(
    {
        "monitor_only",
        "domain_review",
        "hand_off_slice_review",
        "collect_labels",
        "fix_serving",
        "pipeline_fix",
        "update_runbook",
        "rollback_model",
        "restore_rules",
        "restore_baseline_rules",
        "fix_policy",
        "revert_rules_bundle",
        "restore_stream_tiles",
        "fix_online_velocity",
        "unpause_tile_consumer",
        "restore_maturation_policy",
        "fix_label_maturation",
        "restore_label_horizon",
    }
)

REPAIR_HINT = """\
Required machine twin shape:

  {
    "decision": {
      "terminal": "<TERMINAL>",
      "action_class": "<ACTION>",
      "inhibitors": ["..."]
    },
    "claims": [
      {"tag": "<closed_tag>", "status": "supported|falsified_as_primary|unknown|...", "evidence_refs": ["..."]}
    ],
    "anchors": ["..."],
    "capabilities_used": ["..."]
  }

Common failures:
  - top-level terminal/action instead of decision.{terminal,action_class}
  - claims[].tags[] arrays instead of one claims[].tag per row
  - free-text "claim" field instead of closed tag
  - tag or status not in claim_tags.json
"""


def _bundled_claim_tags() -> Path:
    """Always-available copy shipped with the installed package."""
    return Path(__file__).resolve().parent / "claim_tags.json"


def _pkg_agent_claim_tags() -> Path:
    # editable layout: package/agent/claim_tags.json
    return Path(__file__).resolve().parents[1] / "agent" / "claim_tags.json"


def resolve_claim_tags_path(case_root: Path | None = None) -> Path | None:
    """Prefer case agent-instructions, then isolate shared, then bundled package copy."""
    candidates: list[Path] = []
    if case_root is not None:
        root = Path(case_root)
        candidates.extend(
            [
                root / "agent-instructions" / "claim_tags.json",
                root / "agent" / "claim_tags.json",
                root / "_shared" / "docs" / "claim_tags.json",
                root.parent / "_shared" / "docs" / "claim_tags.json",
                root.parent.parent / "f-cases" / "_shared" / "docs" / "claim_tags.json",
            ]
        )
    candidates.append(_bundled_claim_tags())
    candidates.append(_pkg_agent_claim_tags())
    # package/agent-instructions next to installed package tree
    try:
        candidates.append(Path(__file__).resolve().parents[1] / "agent-instructions" / "claim_tags.json")
    except IndexError:
        pass
    for p in candidates:
        if p.is_file():
            return p
    return None


def load_claim_vocab(case_root: Path | None = None) -> dict[str, Any]:
    path = resolve_claim_tags_path(case_root)
    if path is None:
        return {
            "statuses": sorted(STATUS_ENUM),
            "mechanism_tags": [],
            "meta_tags": [],
            "path": None,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    data["path"] = str(path)
    return data


def validate_judgment_struct(struct: Any) -> list[str]:
    """Return schema/hard-shape errors (empty = ok). Does not check closed tags."""
    errors: list[str] = []
    if not isinstance(struct, dict):
        return ["schema: root must be a JSON object"]

    if "terminal" in struct and "decision" not in struct:
        errors.append(
            "schema: top-level terminal/action is invalid — nest under decision "
            "(decision.terminal, decision.action_class)"
        )

    decision = struct.get("decision")
    if not isinstance(decision, dict):
        errors.append("schema: missing required object decision")
    else:
        term = decision.get("terminal")
        if not isinstance(term, str) or not term:
            errors.append("schema: decision.terminal required (non-empty string)")
        elif term not in TERMINAL_ENUM:
            errors.append(
                f"schema: decision.terminal {term!r} not in closed terminal enum "
                f"({', '.join(sorted(TERMINAL_ENUM))})"
            )
        act = decision.get("action_class")
        if isinstance(act, str) and act and act not in ACTION_ENUM:
            errors.append(
                f"schema: decision.action_class {act!r} not in closed action enum "
                f"(see package/agent/glossary.md + gold synonyms)"
            )
        if not isinstance(decision.get("action_class"), str) or not decision.get("action_class"):
            if isinstance(decision.get("action"), str) and decision.get("action"):
                errors.append(
                    "schema: use decision.action_class (found decision.action only)"
                )
            else:
                errors.append("schema: decision.action_class required (non-empty string)")
        inhibitors = decision.get("inhibitors")
        if inhibitors is not None and not isinstance(inhibitors, list):
            errors.append("schema: decision.inhibitors must be an array when present")

    claims = struct.get("claims")
    if claims is None:
        return errors
    if not isinstance(claims, list):
        errors.append("schema: claims must be an array when present")
        return errors

    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            errors.append(f"schema: claims[{i}] must be an object")
            continue
        if "tags" in c and "tag" not in c:
            errors.append(
                f"schema: claims[{i}] has tags[] but missing tag — emit one object per tag"
            )
        if "claim" in c and "tag" not in c:
            errors.append(
                f"schema: claims[{i}] has free-text claim but missing tag — use closed claim_tags"
            )
        tag = c.get("tag")
        if not isinstance(tag, str) or not tag:
            if "tags" not in c and "claim" not in c:
                errors.append(f"schema: claims[{i}].tag required (non-empty string)")
        status = c.get("status")
        if not isinstance(status, str) or not status:
            errors.append(f"schema: claims[{i}].status required")
        elif status not in STATUS_ENUM:
            errors.append(f"schema: claims[{i}].status {status!r} not in allowed enum")

    for key in ("anchors", "capabilities_used", "unknowns"):
        val = struct.get(key)
        if val is not None and not isinstance(val, list):
            errors.append(f"schema: {key} must be an array when present")

    return errors


def validate_claim_vocabulary(
    struct: dict[str, Any],
    vocab: dict[str, Any],
) -> list[str]:
    """Unknown tags / bad statuses against closed claim_tags list."""
    errors: list[str] = []
    allowed_tags = set(vocab.get("mechanism_tags") or []) | set(vocab.get("meta_tags") or [])
    allowed_status = set(vocab.get("statuses") or []) or set(STATUS_ENUM)
    if not allowed_tags:
        return errors

    claims = struct.get("claims")
    if not isinstance(claims, list):
        return errors

    seen: set[str] = set()
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            continue
        tag = c.get("tag")
        if isinstance(tag, str) and tag:
            if tag not in allowed_tags:
                errors.append(
                    f"vocab: claims[{i}].tag {tag!r} is not in the closed claim_tags list"
                )
            elif tag in seen:
                errors.append(f"vocab: claims[{i}].tag {tag!r} duplicated — keep one row per tag")
            else:
                seen.add(tag)
        status = c.get("status")
        if isinstance(status, str) and status and status not in allowed_status:
            errors.append(
                f"vocab: claims[{i}].status {status!r} is not an allowed status "
                f"(allowed: {', '.join(sorted(allowed_status))})"
            )
        # tags[] entries that would never be scored
        if isinstance(c.get("tags"), list) and "tag" not in c:
            for t in c["tags"]:
                if isinstance(t, str) and t and t not in allowed_tags:
                    errors.append(
                        f"vocab: claims[{i}].tags contains unknown {t!r} — "
                        "also fix shape to one object per tag"
                    )
    return errors


def soft_warnings(struct: dict[str, Any], *, md_exists: bool) -> list[str]:
    warns: list[str] = []
    claims = struct.get("claims")
    if claims is None or (isinstance(claims, list) and len(claims) == 0):
        warns.append(
            "claims[] is empty — Layer A will treat every required gold claim as not_claimed. "
            "Add one {tag, status} row per mechanism you assert or eliminate."
        )
    if not md_exists:
        warns.append(
            "out/judgment.md is missing — write the narrative ledger as well as the machine twin."
        )
    # Polarity nudge (not a hard fail): common agent mistake
    if isinstance(claims, list):
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                continue
            tag = c.get("tag")
            status = c.get("status")
            if tag in ("model_artifact", "model_version") and status == "supported":
                warns.append(
                    f"claims[{i}] tag={tag!r} status=supported — if you mean the model plane is healthy "
                    "(eliminated as primary RCA), use falsified_as_primary / falsified instead. "
                    "Use supported only when that tag IS the root mechanism."
                )
    return warns


def claim_miss_notes(notes: list[str]) -> list[str]:
    return [n for n in notes if n.startswith("claim:")]


def grounding_miss_notes(notes: list[str]) -> list[str]:
    """Missing required inhibitors (anchors stay soft notes only)."""
    return [n for n in notes if n.startswith("missing_inhibitor:")]


def _issue_blocks(errors: list[str], warnings: list[str]) -> str:
    lines: list[str] = []
    n = 0
    for err in errors:
        n += 1
        lines.append(f"### {n}. ERROR")
        lines.append("")
        lines.extend(_explain_error(err))
        lines.append("")
    for warn in warnings:
        n += 1
        lines.append(f"### {n}. WARNING")
        lines.append("")
        lines.append(f"**Problem:** {warn}")
        lines.append("")
        lines.append("**Fix:** Address before treating the run as complete (warnings do not hard-fail).")
        lines.append("")
    return "\n".join(lines)


def _explain_error(err: str) -> list[str]:
    """Turn a machine error string into readable Problem / Fix blocks."""
    lines: list[str] = []
    if "tags[] but missing tag" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append(
            "**Why it matters:** Layer A only reads `claims[].tag` (singular). "
            "A `tags` array is ignored, so every gold claim looks `not_claimed`."
        )
        lines.append("")
        lines.append("**Fix:** Replace one object with many — one closed tag per object:")
        lines.append("")
        lines.append("```json")
        lines.append('{ "tag": "card1_slice", "status": "supported", "evidence_refs": ["out/reports/concentration.md"] }')
        lines.append('{ "tag": "slice_concentration", "status": "supported", "evidence_refs": ["out/reports/concentration.md"] }')
        lines.append("```")
        return lines
    if "free-text claim" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append(
            "**Fix:** Drop free-text `claim`. Use a closed `tag` from `agent/claim_tags.json` "
            "plus `status`. Put prose in `judgment.md` or a short `summary` field if you must."
        )
        return lines
    if "top-level terminal" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append("**Fix:** Nest decision fields:")
        lines.append("")
        lines.append("```json")
        lines.append('{ "decision": { "terminal": "ROOT_CAUSE_FOUND", "action_class": "fix_serving", "inhibitors": [] } }')
        lines.append("```")
        return lines
    if "action_class" in err and "decision.action" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append('**Fix:** Rename `decision.action` → `decision.action_class`.')
        return lines
    if err.startswith("vocab:") and "not in the closed claim_tags list" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append(
            "**Fix:** Open `agent/claim_tags.json` (shipped with this package) and "
            "pick the nearest mechanism/meta tag. Do not invent new tag strings."
        )
        return lines
    if err.startswith("vocab:") and "duplicated" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append("**Fix:** Merge into a single row for that tag (one status, combined evidence_refs).")
        return lines
    if "status" in err and "not in allowed" in err:
        lines.append(f"**Problem:** {err}")
        lines.append("")
        lines.append(
            "**Fix:** Use only: supported, associated, falsified, falsified_as_primary, "
            "weakened, unknown, not_claimed."
        )
        return lines
    lines.append(f"**Problem:** {err}")
    lines.append("")
    lines.append("**Fix:** See the required shape at the bottom of this critique, then re-run validate-judgment.")
    return lines


def build_critique(
    *,
    path: Path,
    struct: dict[str, Any] | None,
    schema_errors: list[str],
    vocab_errors: list[str],
    warnings: list[str],
    vocab: dict[str, Any],
    parse_error: str | None = None,
) -> str:
    errors = list(schema_errors) + list(vocab_errors)
    if parse_error:
        errors = [f"parse: {parse_error}", *errors]
    ok = not errors
    lines = [
        "# Judgment struct critique",
        "",
        f"**Result:** {'OK' if ok else 'FAIL'}"
        + (f" ({len(errors)} error(s), {len(warnings)} warning(s))" if (errors or warnings) else ""),
        f"**File:** `{path}`",
        f"**Claim vocab:** `{vocab.get('path') or 'MISSING — cannot check closed tags'}`",
        "",
        "This check is **not** gold scoring. It only verifies the machine twin shape and closed vocabulary "
        "so Layer A can read your judgment. Fix every ERROR before closing the investigation.",
        "",
    ]
    if ok and not warnings:
        lines.extend(
            [
                "## OK",
                "",
                "- Schema shape looks valid (`decision.terminal`, `decision.action_class`, claim rows).",
                "- Claim tags/statuses are on the closed list (when vocab was found).",
                "",
                "You may close the run. Keep `judgment.md` aligned with the struct.",
                "",
            ]
        )
    else:
        lines.append("## Findings")
        lines.append("")
        lines.append(_issue_blocks(errors, warnings))

    # Snapshot of what we saw
    lines.append("## Snapshot")
    lines.append("")
    if isinstance(struct, dict):
        decision = struct.get("decision") if isinstance(struct.get("decision"), dict) else {}
        lines.append(f"- `decision.terminal`: `{decision.get('terminal')}`")
        lines.append(f"- `decision.action_class`: `{decision.get('action_class') or decision.get('action')}`")
        claims = struct.get("claims")
        n = len(claims) if isinstance(claims, list) else 0
        lines.append(f"- `claims` count: **{n}**")
        if isinstance(claims, list):
            for i, c in enumerate(claims[:12]):
                if not isinstance(c, dict):
                    lines.append(f"  - [{i}] (not an object)")
                    continue
                if "tag" in c:
                    lines.append(f"  - [{i}] tag=`{c.get('tag')}` status=`{c.get('status')}`")
                elif "tags" in c:
                    lines.append(f"  - [{i}] tags={c.get('tags')!r} status=`{c.get('status')}`  ← invalid shape")
                else:
                    lines.append(f"  - [{i}] keys={sorted(c.keys())}")
            if n > 12:
                lines.append(f"  - … {n - 12} more")
    else:
        lines.append("- (struct not parsed)")
    lines.append("")

    lines.append("## Required shape (copy/paste)")
    lines.append("")
    lines.append("```json")
    lines.append(REPAIR_HINT.split("Common failures:")[0].replace("Required machine twin shape:\n\n", "").strip())
    lines.append("```")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    if ok:
        lines.append("1. Optional: skim warnings above.")
        lines.append("2. Ensure `out/judgment.md` matches the twin.")
    else:
        lines.append("1. Edit `out/judgment_struct.json` using each Fix above.")
        lines.append("2. Re-run: `indago-investigate validate-judgment .`")
        lines.append("3. Repeat until **Result: OK**. Do not treat the investigation as closed while FAIL.")
    lines.append("")
    lines.append("Allowed tags/statuses: `agent/claim_tags.json` (bundled with the package).")
    lines.append("")
    return "\n".join(lines)


def critique_judgment_file(
    struct_path: Path,
    *,
    case_root: Path | None = None,
    md_path: Path | None = None,
) -> dict[str, Any]:
    """Load + validate one judgment_struct.json; return payload with critique markdown."""
    path = Path(struct_path)
    root = Path(case_root) if case_root else path.parent.parent
    md = Path(md_path) if md_path else path.with_name("judgment.md")
    vocab = load_claim_vocab(root)

    parse_error: str | None = None
    struct: dict[str, Any] | None = None
    if not path.is_file():
        parse_error = f"file not found: {path}"
        schema_errors = ["schema: missing out/judgment_struct.json — write it before validate"]
        vocab_errors: list[str] = []
        warnings = []
        if not md.is_file():
            warnings.append(
                "out/judgment.md is also missing — write the narrative ledger and the machine twin."
            )
    else:
        try:
            struct = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            parse_error = str(exc)
            schema_errors = []
            vocab_errors = []
            warnings = []
        else:
            if not isinstance(struct, dict):
                parse_error = "root must be a JSON object"
                schema_errors = []
                vocab_errors = []
                warnings = []
                struct = None
            else:
                schema_errors = validate_judgment_struct(struct)
                vocab_errors = validate_claim_vocabulary(struct, vocab)
                warnings = soft_warnings(struct, md_exists=md.is_file())

    critique = build_critique(
        path=path,
        struct=struct,
        schema_errors=schema_errors,
        vocab_errors=vocab_errors,
        warnings=warnings,
        vocab=vocab,
        parse_error=parse_error,
    )
    errors = ([f"parse: {parse_error}"] if parse_error else []) + schema_errors + vocab_errors
    return {
        "ok": len(errors) == 0,
        "path": str(path),
        "case_root": str(root),
        "claim_tags_path": vocab.get("path"),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "critique": critique,
        "repair_hint": REPAIR_HINT if errors else None,
    }
