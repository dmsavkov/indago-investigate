"""Minimal rules engine for offline policy replay (YAML → decision)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml

from indago_investigate.health_audit.helpers import path


def _eval_when(expr: str, *, score: float, context: dict[str, Any]) -> bool:
    local = {"score": float(score), "context": context, **context}
    try:
        return bool(eval(expr.strip(), {"__builtins__": {}}, local))  # noqa: S307
    except Exception:
        return False


def load_rules_yaml(rel: str) -> dict[str, Any]:
    with path(rel).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def rules_bundle_hash(rules: dict[str, Any]) -> str:
    blob = json.dumps(rules, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def evaluate_authorize(
    score: float,
    *,
    context: dict[str, Any] | None = None,
    rules: dict[str, Any] | None = None,
) -> tuple[str, list[str], str]:
    ctx = context or {}
    doc = rules or {}
    for rule in doc.get("pre_model") or []:
        when = str(rule.get("when", ""))
        if _eval_when(when, score=0.0, context=ctx):
            return str(rule.get("decision", "REVIEW")), [str(rule.get("id", "pre_rule"))], "pre_rules"
    fired: list[str] = []
    for rule in doc.get("post_model") or []:
        when = str(rule.get("when", ""))
        if _eval_when(when, score=score, context=ctx):
            fired.append(str(rule.get("id", "rule")))
            return str(rule.get("decision", "REVIEW")), fired, "rules"
    default = str(doc.get("default_decision", "REVIEW"))
    return default, fired, "rules_default"


def decision_rates(decisions: list[str]) -> dict[str, float]:
    n = len(decisions) or 1
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d] = counts.get(d, 0) + 1
    return {k: round(v / n, 4) for k, v in sorted(counts.items())}
