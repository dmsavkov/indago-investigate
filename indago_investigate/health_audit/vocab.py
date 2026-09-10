"""Measure and status vocabulary for the orientation health audit."""

from __future__ import annotations

# Short glosses — also rendered into health_audit.md § Vocabulary.
MEASURES: dict[str, str] = {
    "n_support": "Row/cell count behind a rate. Always report as n_a/n_total with the percentage.",
    "delta": "CUR minus REF. Positive means CUR is higher than the named reference.",
    "delta_pp": "Difference in percentage points between two shares (CUR% − REF%).",
    "psi": (
        "Population Stability Index — drift of a numeric feature’s binned histogram vs REF. "
        "Higher = more shift. Unreliable at small n."
    ),
    "tv": "Total variation — categorical drift (½ L1 between level-share vectors).",
    "gain": (
        "Tree split-count importance. Favors high-cardinality continuous columns; "
        "use as a priority list, not causal ranking."
    ),
    "gain_x_psi": "gain × PSI — features that both matter to the model and drifted.",
    "null_rate": "Fraction missing. Compare to train (monitor) and val (holdout sparsity).",
    "train_spike_val_aligned": (
        "Much more null than train but similar to val → likely known sparsity, not a new break."
    ),
    "zero_mass": "Fraction of zeros on count/velocity features; spikes can mean fill-defaults or idle entities.",
    "schema_overlap": "Share of expected feature columns present on the live window.",
    "score_mean": "Mean risk score — pulled up by a high-score tail.",
    "score_median": "Median risk score — describes typical rows better than the mean.",
    "score_tail_mass": "Share of scores ≥ high threshold (default 0.85).",
    "counterfactual_mean": "Mean after removing/capping the high-score tail — tests if μ is tail-driven.",
    "ecdf": "Empirical CDF of scores — full distribution shape.",
    "ks_d": "Kolmogorov–Smirnov D — max gap between CUR and REF ECDFs.",
    "wasserstein_1": "Earth-mover distance between score distributions (avg absolute mass shift).",
    "offline_parity": "max |live_score − offline_recompute|; ~0 means serve matches champion PKL.",
    "rules_bundle_hash": "Fingerprint of active YAML rules; mismatch vs baseline = policy drift.",
    "policy_replay": "Re-run rules on fixed stored scores — isolates policy from score changes.",
    "decision_conflict": "High model score with APPROVE (or low score with DECLINE) under active rules.",
    "slice_concentration": "One entity’s share of CUR traffic vs REF (e.g. a single card1).",
    "cluster_key": "Repeated ProductCD|card1|amount (or similar) — replay / test / burst smell.",
    "slice_priority": (
        "n × |Δmetric| on an important-feature bin. "
        "vs_rest compares slice to other CUR rows; vs_ref compares same bin CUR vs REF val. "
        "Metric = score unless labels exist."
    ),
    "inference_lag": "Scoring/request consumer lag (authorize path).",
    "tile_lag": "Feature-tile updater Kafka lag — side channel, not inference backlog.",
    "latency_p95": "95th percentile authorize latency in ms.",
    "exposure_usd": "Sum of TransactionAmt on window or slice — rough $ size when labels absent.",
    "composite": "Overall posture from all planes (e.g. POLICY_DRIFT) — not a root cause.",
    "inhibitor": "Gate forbidding a global action/conclusion when green planes contradict it.",
}

PLANE_GLOSS: dict[str, str] = {
    "lineage": "What code, model, rules, and baseline card are active — provenance.",
    "infra": "Serving path health: lag channels, latency, online store, k8s noise.",
    "feature": "Schema, nulls, drift on important features, zero-mass velocity.",
    "population": "Traffic mix / concentration / repeat clusters / binned score slices vs REF val.",
    "model": "Score distribution, tail, offline parity, distance vs REF.",
    "decision": "Approve/decline mix, rules hash, fixed-score policy replay, conflicts.",
    "business": "Rough $ exposure and operational load when labels are absent.",
    "macro": "Composite posture + inhibitors + open hypotheses.",
}


def gloss(key: str) -> str:
    return MEASURES.get(key) or PLANE_GLOSS.get(key) or key


def markdown_glossary() -> str:
    lines = ["### Vocabulary (major measures)", ""]
    lines.append("| Measure | Meaning |")
    lines.append("|--------|---------|")
    for k, v in MEASURES.items():
        lines.append(f"| `{k}` | {v} |")
    lines.append("")
    lines.append("### Plane gloss")
    lines.append("")
    lines.append("| Plane | Meaning |")
    lines.append("|-------|---------|")
    for k, v in PLANE_GLOSS.items():
        lines.append(f"| **{k}** | {v} |")
    lines.append("")
    return "\n".join(lines)
