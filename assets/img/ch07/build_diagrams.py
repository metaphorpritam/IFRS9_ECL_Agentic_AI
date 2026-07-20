"""Regenerate Ch.7 (Challengers) figures.

Run: uv run --no-sync python notes/assets/img/ch07/build_diagrams.py
Exhibits 7.3-7.6 read pre-computed JSON from the scratch recompute
(scoring re-derived from the champion refit + the saved torch checkpoint
outputs/challenger/mlp_challenger.pt -- see the chapter's methodology note;
JSON copied alongside this script so the build is reproducible without
re-running the multi-minute recompute every time). Exhibits 7.1-7.2 are
conceptual box-arrow diagrams (no underlying data table).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, figsize_for, COLORS  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402
from matplotlib.ticker import FuncFormatter, NullFormatter  # noqa: E402

OUT = Path(__file__).resolve().parent


def plain_log_ticks(ax, which: str = "xy") -> None:
    """Plain-number tick labels on log axes (mpl_style sets
    text.parse_math=False, which would print LogFormatter's mathtext
    literally -- same fix as analysis/fit_challenger.py's helper)."""
    fmt = FuncFormatter(lambda v, _: f"{v:g}")
    for a in which:
        axis = ax.xaxis if a == "x" else ax.yaxis
        axis.set_major_formatter(fmt)
        axis.set_minor_formatter(NullFormatter())


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=8.6,
        textcolor="#1a1a1a", lw=1.3, zorder=3):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.35)
    return p


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>",
          connectionstyle="arc3,rad=0.0", ls="-"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                        color=color, lw=lw, linestyle=ls, zorder=2,
                        connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# =============================================================================
# Exhibit 7.1 -- the champion-challenger governance loop
# =============================================================================
def fig_lifecycle_loop():
    fig, ax = plt.subplots(figsize=(9.2, 6.0))
    ax.set_xlim(0, 10.6)
    ax.set_ylim(0, 8.4)
    ax.axis("off")

    ax.text(5.3, 8.2, "The champion-challenger governance loop -- a recurring cycle, not a one-off bake-off",
            ha="center", va="top", fontsize=9.2, style="italic", color="#4a4a4a")

    box(ax, (3.7, 6.2), 3.2, 1.15,
        "PRODUCTION CHAMPION\ncloglog GLM hazard\n(sole source of live PDs)",
        fc="#eaf3ff", ec=COLORS["accent"], fontsize=8.4)

    box(ax, (0.35, 4.35), 3.15, 1.15,
        "Periodic challenger build\nsame panel, same target,\nsame split, same features",
        fc="#f4f2fc", ec=COLORS["purple"], fontsize=8.1)

    box(ax, (7.1, 4.35), 3.15, 1.15,
        "Like-for-like scorecard\ndiscrimination / calibration /\nstability / interpretability",
        fc="#f4f2fc", ec=COLORS["purple"], fontsize=8.1)

    box(ax, (3.7, 2.5), 3.2, 1.15,
        "Model-risk governance review\nweighs the evidence\n(Exhibit 7.2's promotion bar)",
        fc="#fff7e6", ec=COLORS["orange"], fontsize=8.4)

    box(ax, (0.35, 0.4), 3.6, 1.35,
        "NO promotion evidence\n(this cycle, MLP: OOT AUC\n0.642 < champion 0.661)\n→ champion UNCHANGED",
        fc="#fdecea", ec=COLORS["warn"], fontsize=8.0)

    box(ax, (6.65, 0.4), 3.6, 1.35,
        "IF a challenger clears the bar\n→ promoted challenger BECOMES\nthe new champion; old champion\nretires to benchmark",
        fc="#ecf7ee", ec=COLORS["good"], fontsize=8.0)

    # loop arrows
    arrow(ax, (3.7, 6.75), (3.5, 5.5), connectionstyle="arc3,rad=-0.25", color=COLORS["accent"])
    arrow(ax, (6.9, 6.75), (7.1, 5.5), connectionstyle="arc3,rad=0.25", color=COLORS["accent"])
    arrow(ax, (1.9, 4.35), (3.9, 3.3), connectionstyle="arc3,rad=-0.2", color=COLORS["purple"])
    arrow(ax, (8.7, 4.35), (6.7, 3.3), connectionstyle="arc3,rad=0.2", color=COLORS["purple"])
    arrow(ax, (4.6, 2.5), (2.7, 1.75), connectionstyle="arc3,rad=0.15", color=COLORS["orange"])
    arrow(ax, (6.0, 2.5), (8.1, 1.75), connectionstyle="arc3,rad=-0.15", color=COLORS["orange"])
    # feedback loops back to the champion box (both stay within the canvas)
    arrow(ax, (1.35, 1.75), (3.75, 6.35), connectionstyle="arc3,rad=0.35", color=COLORS["warn"], ls="--")
    ax.annotate("champion re-enters\nnext cycle unchanged", xy=(1.35, 1.75), xytext=(0.05, 3.55),
                fontsize=6.9, color=COLORS["warn"], ha="center")
    arrow(ax, (8.45, 1.75), (6.75, 6.35), connectionstyle="arc3,rad=-0.3", color=COLORS["good"])
    ax.annotate("promoted model becomes\nthe production champion\n(loop restarts)", xy=(8.45, 1.75), xytext=(9.9, 3.55),
                fontsize=6.9, color=COLORS["good"], ha="center")

    ax.text(5.3, -0.55,
            "CHALLENGER NEVER CHAMPION mid-cycle: the swap only happens through this governance box, never silently.",
            ha="center", va="top", fontsize=7.6, color="#555555")

    fig.tight_layout()
    fig.savefig(OUT / "01_lifecycle_loop.png")
    plt.close(fig)
    print("wrote", OUT / "01_lifecycle_loop.png")


# =============================================================================
# Exhibit 7.2 -- like-for-like comparison checklist
# =============================================================================
def fig_like_for_like():
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    ax.set_xlim(0, 10.6)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    ax.text(5.3, 7.05, "The like-for-like law -- what must be IDENTICAL for a champion-challenger AUC gap to mean anything",
            ha="center", va="top", fontsize=9.0, style="italic", color="#4a4a4a")

    items = [
        "Same loan-quarter at-risk rows\n(identical panel slice)",
        "Same one-quarter-ahead\ndefault_event target",
        "Same train / OOT split boundary\n(t<=40 vs t=41..60)",
        "Same covariate information set\n(no extra features either side)",
        "Same timing convention\n(every macro regressor lagged)",
        "Same evaluation metric & window\n(AUC on the SAME OOT rows)",
    ]
    x0, y0, w, h, gap = 0.5, 4.55, 3.05, 1.55, 0.25
    for i, txt in enumerate(items):
        col, row = i % 3, i // 3
        x = x0 + col * (w + gap)
        y = y0 - row * (h + gap)
        box(ax, (x, y), w, h, "OK  " + txt, fc="#ecf7ee", ec=COLORS["good"], fontsize=7.7)

    box(ax, (0.5, 0.35), 9.6, 1.65,
        "Violate ANY box above and the comparison is VOIDED, not just weakened:\n"
        "extra features for one side re-attributes lift to the LEARNER that really came from EXTRA INFORMATION;\n"
        "a different split lets one model see data the other never trained on; a mismatched target silently compares\n"
        "two different prediction problems. The MLP challenger in this chapter satisfies every box: same panel,\n"
        "same target, same split, same feature set (no age spline, no hand-built interaction added FOR it).",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.9)

    fig.tight_layout()
    fig.savefig(OUT / "02_like_for_like_checklist.png")
    plt.close(fig)
    print("wrote", OUT / "02_like_for_like_checklist.png")


# =============================================================================
# Exhibit 7.3 -- reliability diagram, champion vs challenger, train + OOT
# =============================================================================
def fig_reliability():
    data = json.loads((OUT / "reliability_bins.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    for ax, split, title in [(axes[0], "train", "train (t≤40)"),
                             (axes[1], "oot", "out-of-time (t=41..60)")]:
        for label, key, color in [("champion", "champion", COLORS["accent"]),
                                  ("challenger", "challenger", COLORS["warn"])]:
            b = data[f"{split}_{key}"]
            pred = [r["pred"] for r in b]
            obs = [r["obs"] for r in b]
            ax.plot(pred, obs, "o-", ms=3, lw=1.2, color=color, label=label)
        lo, hi = 0.01, max(max(r["obs"] for r in data[f"{split}_champion"]),
                           max(r["obs"] for r in data[f"{split}_challenger"]),
                           max(r["pred"] for r in data[f"{split}_champion"]),
                           max(r["pred"] for r in data[f"{split}_challenger"])) * 1.15
        ax.plot([lo, hi], [lo, hi], "--", color="#999999", lw=1, label="perfect calibration")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        plain_log_ticks(ax)
        ax.set_xlabel("predicted hazard (%, log)")
        ax.set_ylabel("observed default rate (%, log)")
        ax.set_title(title)
        if ax is axes[0]:
            ax.legend(fontsize=7.2, loc="upper left")
    fig.suptitle("Exhibit 7.3 -- reliability (20 score-quantile bins), champion vs challenger", fontsize=9.5, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "03_reliability_oot.png")
    plt.close(fig)
    print("wrote", OUT / "03_reliability_oot.png")


# =============================================================================
# Exhibit 7.4 -- PSI score-distribution shift, train -> OOT
# =============================================================================
def fig_psi():
    data = json.loads((OUT / "psi_bands.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    x = np.arange(10)
    for ax, key, title, total in [
        (axes[0], "champion", "champion (PSI = 3.71)", data["champion"]["total"]),
        (axes[1], "challenger", "challenger (PSI = 0.76)", data["challenger"]["total"]),
    ]:
        d = data[key]
        w = 0.38
        ax.bar(x - w / 2, np.array(d["train_share"]) * 100, width=w, color=COLORS["accent"],
              label="train (t≤40)")
        ax.bar(x + w / 2, np.array(d["oot_share"]) * 100, width=w, color=COLORS["warn"],
              label="OOT (t=41..60)")
        ax.set_xlabel("score decile (train-score-defined bins)")
        ax.set_ylabel("population share (%)")
        ax.set_title(title)
        ax.set_xticks(x, [str(i + 1) for i in x])
        if ax is axes[0]:
            ax.legend(fontsize=7.5)
    fig.suptitle("Exhibit 7.4 -- score-distribution shift, train → OOT (recomputed, matches scorecard.md)",
                fontsize=9.3, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "04_psi_bins.png")
    plt.close(fig)
    print("wrote", OUT / "04_psi_bins.png")


# =============================================================================
# Exhibit 7.5 -- permutation importance, family blocks (from scorecard.md)
# =============================================================================
def fig_perm_importance():
    fams = ["collateral", "borrower", "incentive", "macro", "age"]
    drops = [0.1279, 0.0286, 0.0208, -0.0015, -0.0120]
    colors = [COLORS["good"] if d > 0 else COLORS["warn"] for d in drops]
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    y = np.arange(len(fams))
    ax.barh(y, drops, color=colors)
    ax.set_yticks(y, fams)
    ax.axvline(0, color="#555555", lw=0.9)
    ax.set_xlim(-0.045, 0.148)
    ax.set_xlabel("OOT AUC drop when family block is permuted (base AUC 0.6417)")
    ax.set_title("Exhibit 7.5 -- challenger permutation importance, family blocks (outputs/challenger/scorecard.md)")
    for yi, d in zip(y, drops):
        ax.text(d + (0.004 if d >= 0 else -0.004), yi, f"{d:+.4f}",
                ha="left" if d >= 0 else "right", va="center", fontsize=7.8)
    fig.tight_layout()
    fig.savefig(OUT / "05_perm_importance.png")
    plt.close(fig)
    print("wrote", OUT / "05_perm_importance.png")


# =============================================================================
# Exhibit 7.6 -- the seasoning hump: loan_age PDP, champion vs challenger
# =============================================================================
def fig_seasoning_hump():
    data = json.loads((OUT / "age_pdp.json").read_text())
    rows = data["age_pdp"]
    ages = [r["age"] for r in rows]
    champ = [r["champion"] for r in rows]
    chal = [r["challenger"] for r in rows]
    fig, ax = plt.subplots(figsize=(9.4, 4.6))
    ax.axvspan(37, 80, color="#999999", alpha=0.12, zorder=0)
    ax.text(58, 6.6, "thin training support\n(<1% of rows, loan_age≥40)",
           ha="center", va="top", fontsize=7.2, color="#555555", style="italic")
    ax.plot(ages, champ, "-", color=COLORS["accent"], lw=1.6, label="champion (cloglog spline)")
    ax.plot(ages, chal, "-", color=COLORS["warn"], lw=1.6, label="challenger (MLP, no age spline)")
    ax.axvline(12, color=COLORS["accent"], lw=0.8, ls=":")
    ax.annotate("champion spline hump\npeaks at 12q", xy=(12, champ[ages.index(12)]),
               xytext=(16, champ[ages.index(12)] + 2.3), fontsize=7.3, color=COLORS["accent"],
               arrowprops=dict(arrowstyle="-", color=COLORS["accent"], lw=0.7))
    ax.annotate("challenger has NO hump --\npeaks at loan_age = 0", xy=(0, chal[0]),
               xytext=(9, chal[0] - 1.9), fontsize=7.3, color=COLORS["warn"],
               arrowprops=dict(arrowstyle="-", color=COLORS["warn"], lw=0.7))
    ax.set_xlabel("loan_age (quarters on book)")
    ax.set_ylabel("PDP hazard (%, 20k-row sample)")
    ax.set_title("Exhibit 7.6 -- seasoning-hump-rediscovery check: loan_age PDP, champion vs challenger")
    ax.legend(fontsize=7.8, loc="upper left", bbox_to_anchor=(0.42, 1.0))
    ax.set_ylim(0, 11.8)
    fig.tight_layout()
    fig.savefig(OUT / "06_seasoning_hump_pdp.png")
    plt.close(fig)
    print("wrote", OUT / "06_seasoning_hump_pdp.png")


if __name__ == "__main__":
    fig_lifecycle_loop()
    fig_like_for_like()
    fig_reliability()
    fig_psi()
    fig_perm_importance()
    fig_seasoning_hump()
