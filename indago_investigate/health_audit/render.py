"""Render health_audit.md from assembled payload."""

from __future__ import annotations

from typing import Any

from indago_investigate.health_audit.vocab import gloss, markdown_glossary


def _fmt_check(c: dict[str, Any]) -> str:
    parts = [f"**[{c['status']}]** `{c['id']}` — {c['meaning']}"]
    if c.get("value") is not None:
        val = c["value"]
        # Keep check lines short; large tables go in plane detail sections
        s = str(val)
        if len(s) > 180:
            s = s[:177] + "…"
        parts.append(f"value=`{s}`")
    if c.get("n") is not None:
        parts.append(f"n=`{c['n']}`")
    if c.get("baseline") is not None:
        parts.append(f"baseline=`{c['baseline']}`")
    if c.get("delta") is not None:
        parts.append(f"Δ=`{c['delta']}`")
    if c.get("delta_direction"):
        parts.append(f"({c['delta_direction']})")
    if c.get("threshold") is not None:
        parts.append(f"thr=`{c['threshold']}`")
    if c.get("gloss_key"):
        parts.append(f"_[{c['gloss_key']}]_")
    return " · ".join(parts)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return []
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for r in rows:
        cells = [str(x).replace("|", "/") if x is not None else "—" for x in r]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _render_feature_detail(p: dict[str, Any]) -> list[str]:
    m = p.get("metrics") or {}
    lines: list[str] = []
    note = m.get("detail_note")
    if note:
        lines.append(f"_{note}_")
        lines.append("")

    scanned = m.get("scanned_set") or []
    src = m.get("scanned_source")
    if scanned:
        lines.append(f"**Scanned set** ({len(scanned)}): " + ", ".join(f"`{f}`" for f in scanned))
        if src:
            lines.append(f"_Source: {src}_")
        lines.append("")

    missing = m.get("missing_from_cur") or []
    if missing:
        lines.append("**Missing from CUR/train (skipped):** " + ", ".join(f"`{f}`" for f in missing))
        lines.append("")

    null_profile = m.get("null_profile") or []
    if null_profile:
        lines.append(f"**Null profile — all {len(null_profile)} scanned features** (tag≠ok = spike vs train):")
        lines.append("")
        lines.extend(
            _table(
                ["rank", "feature", "gain", "tag", "null_cur", "null_train", "null_val", "Δtrain", "Δval", "n_null"],
                [
                    [
                        t.get("rank"),
                        t.get("feature"),
                        t.get("gain"),
                        t.get("tag"),
                        t.get("null_cur"),
                        t.get("null_train"),
                        t.get("null_val"),
                        t.get("delta_train"),
                        t.get("delta_val"),
                        t.get("n_null"),
                    ]
                    for t in null_profile
                ],
            )
        )

    priorities = m.get("priorities") or []
    if priorities:
        lines.append(f"**Drift profile — all {len(priorities)} scanned features** (PSI on numerics; cats = —):")
        lines.append("")
        lines.extend(
            _table(
                ["rank", "feature", "kind", "gain", "gain_norm", "psi", "gain×psi"],
                [
                    [
                        r.get("rank"),
                        r.get("feature"),
                        r.get("kind"),
                        r.get("gain"),
                        r.get("gain_norm"),
                        r.get("psi"),
                        r.get("gain_x_psi"),
                    ]
                    for r in priorities
                ],
            )
        )

    zero_tags = m.get("zero_tags") or []
    if zero_tags:
        lines.append("**Zero-mass velocity spikes (subset of scanned set):**")
        lines.append("")
        lines.extend(
            _table(
                ["rank", "feature", "zero_cur", "zero_train", "velocity", "n_zero"],
                [
                    [
                        t.get("rank"),
                        t.get("feature"),
                        t.get("zero_cur"),
                        t.get("zero_train"),
                        t.get("velocity"),
                        t.get("n_zero"),
                    ]
                    for t in zero_tags
                ],
            )
        )
    return lines


def _render_population_detail(p: dict[str, Any]) -> list[str]:
    m = p.get("metrics") or {}
    lines: list[str] = []
    note = m.get("detail_note")
    if note:
        lines.append(f"_{note}_")
        lines.append("")

    mix = m.get("mix_shifts") or []
    if mix:
        lines.append("**Mix shifts (|Δpp| material):**")
        lines.append("")
        lines.extend(
            _table(
                ["feature", "level", "n_cur", "cur%", "val%", "Δpp", "ratio", "μ_score"],
                [
                    [
                        r.get("feature"),
                        r.get("level"),
                        r.get("cur_n"),
                        r.get("cur_share"),
                        r.get("val_share"),
                        r.get("delta_pp"),
                        r.get("ratio"),
                        r.get("mean_score_cur"),
                    ]
                    for r in mix
                ],
            )
        )

    clusters = m.get("clusters") or []
    if clusters:
        lines.append("**Repeat clusters (ProductCD|card1|amount, n≥2):**")
        lines.append("")
        lines.extend(
            _table(
                ["key", "n", "μ_score"],
                [[c.get("key"), c.get("n"), c.get("mean_score")] for c in clusters[:8]],
            )
        )

    sd = m.get("slice_discovery") or {}
    if sd.get("error"):
        lines.append(f"_Slice discovery skipped: {sd['error']}_")
        lines.append("")
        return lines

    if sd:
        lines.append(
            f"**Binned slice discovery** (metric=`{sd.get('metric')}`; "
            f"evaluated={sd.get('n_slices_evaluated')}; "
            f"μ_CUR={sd.get('mu_cur_all')}; μ_REF={sd.get('mu_ref_all')}):"
        )
        lines.append("")
        lines.append(f"_{sd.get('method')}_")
        lines.append("")

        by_rest = sd.get("top_by_vs_rest") or []
        if by_rest:
            lines.append("Top by `priority_vs_rest` = n × |μ_slice − μ_rest|:")
            lines.append("")
            lines.extend(
                _table(
                    ["feature", "bin", "n", "μ_slice", "μ_rest", "Δ", "priority"],
                    [
                        [
                            r.get("feature"),
                            r.get("bin"),
                            r.get("n_cur"),
                            r.get("mean_metric_cur"),
                            r.get("mean_metric_rest"),
                            r.get("delta_vs_rest"),
                            r.get("priority_vs_rest"),
                        ]
                        for r in by_rest
                    ],
                )
            )

        by_ref = sd.get("top_by_vs_ref") or []
        if by_ref:
            lines.append("Top by `priority_vs_ref` = n × |μ_CUR_bin − μ_REF_bin|:")
            lines.append("")
            lines.extend(
                _table(
                    ["feature", "bin", "n_cur", "n_ref", "μ_CUR", "μ_REF", "Δ", "priority"],
                    [
                        [
                            r.get("feature"),
                            r.get("bin"),
                            r.get("n_cur"),
                            r.get("n_ref"),
                            r.get("mean_metric_cur"),
                            r.get("mean_metric_ref_bin"),
                            r.get("delta_vs_ref_bin"),
                            r.get("priority_vs_ref"),
                        ]
                        for r in by_ref
                    ],
                )
            )
    return lines


def _render_sources(src: dict[str, Any]) -> list[str]:
    if not src:
        return []
    lines = ["## Sources / mini-lineage", ""]
    data = src.get("data") or {}
    model = src.get("model") or {}
    rules = src.get("rules") or {}
    base = src.get("baseline_card") or {}
    fc = src.get("feature_contract") or {}
    code = src.get("code") or {}

    lines.append("### Data")
    lines.append("")
    lines.append(
        f"- **CUR:** `{((data.get('cur_events') or {}).get('path'))}` (n={((data.get('cur_events') or {}).get('n'))})"
    )
    lines.append(
        f"- **REF train:** `{((data.get('ref_train') or {}).get('path'))}` (n={((data.get('ref_train') or {}).get('n'))})"
    )
    lines.append(
        f"- **REF val:** `{((data.get('ref_val') or {}).get('path'))}` (n={((data.get('ref_val') or {}).get('n'))})"
    )
    lines.append(f"- **gold_table:** `{data.get('gold_table')}` · **silver_build_id:** `{data.get('silver_build_id')}`")
    lines.append(f"- **window:** `{data.get('window_capacity')}`")
    lines.append("")

    lines.append("### Model")
    lines.append("")
    lines.append(
        f"- **{model.get('model_name')}** alias=`{model.get('alias')}` "
        f"registry_v=`{model.get('registry_version')}` run=`{model.get('run_id_label')}`"
    )
    lines.append(f"- **uri:** `{model.get('model_uri')}` · **pkl:** `{model.get('pkl')}`")
    lines.append(
        f"- **val_pr_auc:** `{model.get('val_pr_auc')}` · **val_roc_auc:** `{model.get('val_roc_auc')}` · "
        f"**selection:** `{model.get('selection_metric')}`"
    )
    exported = model.get("models_exported") or []
    if exported:
        lines.append("- **Exported aliases:** " + ", ".join(
            f"`{m.get('alias')}→v{m.get('registry_version')} ({m.get('copied_as')})`" for m in exported
        ))
    lines.append("")

    lines.append("### Rules & baseline")
    lines.append("")
    lines.append(f"- **live_hash:** `{rules.get('live_hash')}` · **baseline_hash:** `{rules.get('baseline_hash')}`")
    lines.append(
        f"- **YAML default:** `{rules.get('rules_default') or rules.get('overfetch_default')}` "
        f"· **loose:** `{rules.get('rules_loose') or rules.get('overfetch_loose')}`"
    )
    lines.append(
        f"- **baseline card:** `{base.get('id')}` · n_val=`{base.get('n_val')}` · "
        f"pred_mean_val=`{base.get('pred_mean_val')}` · approval_rate_val=`{base.get('approval_rate_val')}`"
    )
    lines.append("")

    lines.append("### Feature contract / versions")
    lines.append("")
    lines.append(
        f"- train_cols=`{fc.get('n_train_cols')}` · serve_cols=`{fc.get('n_serve_cols')}` · "
        f"online_v=`{fc.get('online_feature_version')}` · batch_v=`{fc.get('batch_feature_version')}`"
    )
    lines.append("")

    lines.append("### Code / orchestration")
    lines.append("")
    lines.append(
        f"- git_sha alert=`{code.get('git_sha_alert')}` · baseline=`{code.get('git_sha_baseline')}` · "
        f"dbt_models_ok=`{code.get('dbt_models_ok')}`"
    )
    lines.append("")

    rels = src.get("relationships") or []
    if rels:
        lines.append("### Relationships")
        lines.append("")
        for r in rels:
            lines.append(f"- {r}")
        lines.append("")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    a = payload["alert_digest"]
    lines.append("# SYSTEM HEALTH AUDIT — Orientation")
    lines.append("")
    lines.append(
        f"**Incident:** `{a.get('incident_id')}` · **Fired:** `{a.get('fired_at')}` · "
        f"**Window:** n={a.get('n_events')}/{a.get('window')} · **Labels:** `{a.get('labels')}` · "
        f"**Champion:** v{a.get('champion_version')} · **Generated:** `{payload.get('generated_at')}`"
    )
    lines.append("")
    lines.append("> Descriptive orientation only — not root cause. Deep reports remain for drill-down.")
    lines.append("")

    # Scorecard
    lines.append("## 0. Composite scorecard")
    lines.append("")
    macro = payload["planes"]["macro"]
    comp = (macro.get("metrics") or {}).get("composite")
    lines.append(f"**Composite:** `{comp}` · confidence=`{macro.get('confidence')}`")
    lines.append("")
    lines.append("| Plane | Status | Finding | Anomaly | Conf |")
    lines.append("|-------|--------|---------|---------|------|")
    for name in ("lineage", "infra", "feature", "population", "model", "decision", "business", "macro"):
        p = payload["planes"][name]
        finding = str(p.get("finding") or "").replace("|", "/")[:120]
        anomaly = str(p.get("anomaly") or "—").replace("|", "/")[:80]
        lines.append(f"| **{name}** | **{p['status']}** | {finding} | {anomaly} | {p.get('confidence')} |")
    lines.append("")
    inhibitors = (macro.get("metrics") or {}).get("inhibitors") or []
    if inhibitors:
        lines.append("**Action inhibitors:** " + ", ".join(f"`{x}`" for x in inhibitors))
        lines.append("")
    hyps = (macro.get("metrics") or {}).get("hypotheses") or []
    if hyps:
        lines.append("**Open hypotheses (not ranked winners):**")
        for h in hyps:
            lines.append(f"- `{h.get('id')}` [{h.get('plane')}] {h.get('one_line')} (conf={h.get('confidence')})")
        lines.append("")

    # Alert
    lines.append("## 1. Alert signal")
    lines.append("")
    lines.append(f"- **Primary metric:** `{a.get('metric')}`")
    lines.append(f"- **Baseline card:** `{a.get('baseline_id')}` · pred_mean_val=`{a.get('pred_mean_val')}` · n_val=`{a.get('n_val')}`")
    lines.append(f"- **git_sha:** `{a.get('git_sha')}`")
    lines.append("- **Failed / co-fired checks:**")
    for c in a.get("failed_checks") or []:
        lines.append(f"  - [{c.get('status')}] `{c.get('id')}`: {c.get('message')}")
    lines.append("")

    # Sources early so investigator knows what they are looking at
    lines.append("## 1b. Sources / mini-lineage")
    lines.append("")
    # strip the H2 from helper (it adds its own); inline body only
    src_lines = _render_sources(payload.get("sources") or {})
    lines.extend(src_lines[2:] if src_lines and src_lines[0].startswith("##") else src_lines)

    # Planes detail
    titles = {
        "lineage": "2. Change & Lineage",
        "infra": "3. Infrastructure",
        "feature": "4. Feature Health",
        "population": "5. Population Health",
        "model": "6. Model Health",
        "decision": "7. Decision / Policy Health",
        "business": "8. Business Health",
    }
    for name, title in titles.items():
        p = payload["planes"][name]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"_Plane gloss:_ {gloss(name)}")
        lines.append("")
        lines.append(f"**Status:** {p['status']} · **Finding:** {p.get('finding')}")
        lines.append("")
        # §B.14: missing-role obligation must appear in MD for UNKNOWN planes
        if str(p.get("status")) == "UNKNOWN":
            mr = p.get("missing_roles") or []
            mi = p.get("missing_inputs") or []
            hints = p.get("hints") or []
            if mr:
                lines.append("**Missing roles:** " + ", ".join(f"`{x}`" for x in mr))
            if mi:
                lines.append("**Missing inputs:** " + ", ".join(f"`{x}`" for x in mi))
            if hints:
                lines.append("**Hints:**")
                for h in hints:
                    lines.append(f"- {h}")
            if mr or mi or hints:
                lines.append("")
        for c in p.get("checks") or []:
            lines.append(f"- {_fmt_check(c)}")
        lines.append("")
        if name == "feature":
            lines.extend(_render_feature_detail(p))
        elif name == "population":
            lines.extend(_render_population_detail(p))

    lines.append("## 9. Composite synthesis")
    lines.append("")
    lines.append(f"- Composite status: `{comp}`")
    lines.append(f"- Inhibitors: `{inhibitors}`")
    lines.append("- Hypotheses listed in §0 — orientation does not pick a root cause.")
    lines.append("")

    lines.append("## 10. Evidence index")
    lines.append("")
    lines.append("| Artifact | Role |")
    lines.append("|----------|------|")
    lines.append("| `json/health_audit.json` | Full metrics / checks |")
    for pl in payload.get("plots") or []:
        lines.append(f"| `{pl}` | Plot |")
    lines.append("| Deep scripts (`policy_replay`, `score_distribution`, …) | Optional drill-down |")
    lines.append("")

    lines.append("## 11. Known limitations")
    lines.append("")
    for lim in payload.get("limitations") or []:
        lines.append(f"- {lim}")
    lines.append("")

    lines.append("## 12. Vocabulary")
    lines.append("")
    lines.append(markdown_glossary())
    lines.append("---")
    lines.append("END SYSTEM HEALTH AUDIT")
    lines.append("")
    return "\n".join(lines)
