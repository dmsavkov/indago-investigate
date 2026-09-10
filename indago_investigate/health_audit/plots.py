"""Plots for health audit orientation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from indago_investigate.health_audit.case_io import get_case_io
from indago_investigate.health_audit.thresholds import THR


def write_plots(payload: dict[str, Any]) -> list[str]:
    PLOTS = get_case_io().out_dir / "plots"
    PLOTS.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    model = payload.get("planes", {}).get("model", {})
    metrics = model.get("metrics") or {}
    cur_scores = np.array(metrics.get("cur_scores") or [], dtype=float)
    val_mean = ((metrics.get("val_scores_summary") or {}).get("mean"))

    # Scorecard strip
    fig, ax = plt.subplots(figsize=(10, 1.8))
    colors = {"GREEN": "#2ca02c", "WARN": "#ff7f0e", "ALERT": "#d62728", "UNKNOWN": "#7f7f7f"}
    planes = ["lineage", "infra", "feature", "population", "model", "decision", "business", "macro"]
    for i, name in enumerate(planes):
        st = payload["planes"][name]["status"]
        ax.barh(0, 1, left=i, color=colors.get(st, "#7f7f7f"), edgecolor="white")
        ax.text(i + 0.5, 0, f"{name}\n{st}", ha="center", va="center", fontsize=7, color="white", fontweight="bold")
    ax.set_xlim(0, 8)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_title("Health scorecard")
    p = PLOTS / "health_scorecard.png"
    fig.tight_layout()
    fig.savefig(p, dpi=120)
    plt.close(fig)
    paths.append(str(p))

    if len(cur_scores):
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        bins = np.linspace(0, 1, 41)
        axes[0].hist(cur_scores, bins=bins, density=True, alpha=0.7, color="C0", label=f"CUR n={len(cur_scores)}")
        axes[0].axvline(THR["tail_score"], color="red", ls="--", lw=1, label=f"tail={THR['tail_score']}")
        if val_mean is not None:
            axes[0].axvline(val_mean, color="C1", ls=":", lw=1, label=f"val mean={val_mean:.3f}")
        axes[0].set_title("CUR score histogram")
        axes[0].legend(fontsize=8)
        axes[0].set_xlabel("score")

        xs = np.sort(cur_scores)
        ecdf = np.arange(1, len(xs) + 1) / len(xs)
        axes[1].step(xs, ecdf, where="post", label="CUR ECDF")
        axes[1].axvline(THR["tail_score"], color="red", ls="--", lw=1)
        axes[1].set_title("CUR score ECDF")
        axes[1].set_xlabel("score")
        axes[1].legend(fontsize=8)
        fig.tight_layout()
        p2 = PLOTS / "health_score_dist.png"
        fig.savefig(p2, dpi=120)
        plt.close(fig)
        paths.append(str(p2))

    # Population top entities
    pop = payload.get("planes", {}).get("population", {})
    conc = (pop.get("metrics") or {}).get("concentrations") or []
    if conc:
        top = conc[:8]
        fig, ax = plt.subplots(figsize=(9, 4))
        labels = [f"{r['feature']}={r['level']}"[:24] for r in top]
        x = np.arange(len(top))
        ax.bar(x - 0.2, [r["cur_share"] * 100 for r in top], 0.4, label="CUR %")
        ax.bar(x + 0.2, [r["val_share"] * 100 for r in top], 0.4, label="VAL %")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=7)
        ax.set_ylabel("share %")
        ax.set_title("Top entity shares CUR vs REF val")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p3 = PLOTS / "health_population_top.png"
        fig.savefig(p3, dpi=120)
        plt.close(fig)
        paths.append(str(p3))

    # Decision funnel
    dec = payload.get("planes", {}).get("decision", {})
    funnel = None
    for c in dec.get("checks") or []:
        if c["id"] == "decision_funnel":
            funnel = c.get("value") or {}
    if funnel:
        fig, ax = plt.subplots(figsize=(5, 3))
        keys = sorted(funnel.keys())
        ax.bar(keys, [funnel[k] for k in keys], color="C0")
        ax.set_title("Observed decisions")
        ax.set_ylabel("count")
        fig.tight_layout()
        p4 = PLOTS / "health_decision_funnel.png"
        fig.savefig(p4, dpi=120)
        plt.close(fig)
        paths.append(str(p4))

    return paths
