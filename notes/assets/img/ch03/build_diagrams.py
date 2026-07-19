"""Regenerate Ch.3 (Hazard Modelling) figures.

Run: uv run --no-sync python notes/assets/img/ch03/build_diagrams.py
Source data cited inline per figure. Uses the shared textbook matplotlib
style (.claude/skills/pageindex-plus/assets/matplotlib_setup.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, figsize_for, COLORS  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402

OUT = Path(__file__).resolve().parent


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=8.6, textcolor="#1a1a1a", lw=1.3, zorder=3):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.35)
    return p


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>", connectionstyle="arc3,rad=0.0", ls="-"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                         color=color, lw=lw, linestyle=ls, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# =============================================================================
# Exhibit 3.1 — competing-risks state diagram
# =============================================================================
def fig_competing_risks():
    fig, ax = plt.subplots(figsize=(8.8, 5.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.4)
    ax.axis("off")

    ax.text(5.0, 7.2,
            "Each row exits by AT MOST ONE cause. The other event's occurrence censors that row for this cause\n"
            "(no special weighting needed) => two independent binomial GLMs ARE the max-likelihood\n"
            "cause-specific hazards (engine/hazard.py docstring).",
            ha="center", va="top", fontsize=7.7, style="italic", color="#4a4a4a")

    # PERFORMING state (center-left)
    box(ax, (0.7, 3.15), 2.7, 1.4,
        "PERFORMING\n(loan-quarter, at risk)\nP(in state | survived to t-1)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=8.3)

    # self-loop (continue performing)
    ax.annotate("", xy=(0.78, 4.4), xytext=(0.78, 3.3),
                arrowprops=dict(arrowstyle="-|>", color=COLORS["accent"],
                                 connectionstyle="arc3,rad=-1.8", lw=1.3))
    ax.text(0.15, 3.85, "survive both:\n1-λ_d(t)-λ_p(t)",
            fontsize=7.6, ha="center", va="center", color=COLORS["accent"])

    # DEFAULT (absorbing, top right)
    box(ax, (6.3, 4.85), 3.15, 1.4,
        "DEFAULT (absorbing)\ncause-specific hazard\nλ_d(t) = P(default in t | at risk)",
        fc="#fdecea", ec=COLORS["warn"], fontsize=8.3)
    arrow(ax, (3.45, 4.25), (6.25, 5.3), color=COLORS["warn"], connectionstyle="arc3,rad=0.12")
    ax.text(4.75, 5.2, "λ_d(t)", fontsize=9.5, color=COLORS["warn"])

    # PREPAID (absorbing, bottom right)
    box(ax, (6.3, 2.2), 3.15, 1.4,
        "PREPAID (absorbing)\ncause-specific hazard\nλ_p(t) = P(prepay in t | at risk)",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=8.3)
    arrow(ax, (3.45, 3.55), (6.25, 3.05), color=COLORS["good"], connectionstyle="arc3,rad=-0.12")
    ax.text(4.5, 2.9, "λ_p(t)", fontsize=9.5, color=COLORS["good"])

    # CENSORED (bottom-left, dashed - not an exit, window boundary)
    box(ax, (0.5, 0.35), 2.2, 1.1,
        "CENSORED\n(window ends,\nloan still alive)",
        fc="#f7f5ee", ec=COLORS["gray"], fontsize=7.9, lw=1.1)
    arrow(ax, (1.6, 3.1), (1.6, 1.5), color=COLORS["gray"], ls="--", lw=1.1)

    # bottom-right formula panel, clear of every box
    ax.text(6.9, 0.95,
            "S(t) = prod_(k<=t) [1 - λ_d(k) - λ_p(k)]\n\n"
            "marginal default PD at t  =  S(t-1) x λ_d(t)",
            ha="center", va="center", fontsize=9.6, color="#1a1a1a", linespacing=1.7)

    ax.set_title("Cause-specific competing risks: default vs prepayment, one loan-quarter row at a time",
                 fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "01_competing_risks_state_diagram.png")
    plt.close(fig)
    print("wrote 01_competing_risks_state_diagram.png")


# =============================================================================
# Exhibit 3.2 — panel-construction flowchart (real DCR waterfall numbers)
# =============================================================================
def fig_panel_flowchart():
    fig, ax = plt.subplots(figsize=(8.6, 6.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.6)
    ax.axis("off")

    box(ax, (3.1, 11.1), 3.8, 1.15,
        "RAW dcr_full.csv\n622,489 rows / 50,000 loans\n15,158 default rows, 26,589 payoff rows",
        fc="#f7f5ee", ec=COLORS["gray"], fontsize=8.0)

    steps = [
        "1. exact duplicate rows   -305",
        "2. id-collision loans   -108",
        "3. same-quarter status conflicts   -7  (keep terminal row)",
        "4. post-terminal truncation guard   -0  (audit only)",
        "5. balance_orig_time <= 0 loans   -270",
        "6. zero-balance live rows   -38",
        "7. interest_rate_time <= 0 rows   -25",
    ]
    box(ax, (2.3, 8.5), 5.4, 2.15, "ELIGIBILITY WATERFALL (7 steps, order matters)\n" + "\n".join(steps),
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.3)
    arrow(ax, (5.0, 11.1), (5.0, 10.65))

    box(ax, (2.7, 6.9), 4.6, 1.15,
        "ELIGIBLE PANEL\n621,736 rows / 49,974 loans\n15,147 defaults, 26,580 payoffs, 8,247 censored",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=8.0)
    arrow(ax, (5.0, 8.5), (5.0, 8.05))

    box(ax, (2.5, 5.0), 5.0, 1.3,
        "loan-quarter AT-RISK ROWS\nrow exists for $t$ iff loan survived to start of $t$\n"
        "row carries event flags: default_event, payoff_event, terminal_event, is_last_obs",
        fc="#fff7e6", ec="#d39e00", fontsize=7.6)
    arrow(ax, (5.0, 6.9), (5.0, 6.3))

    arrow(ax, (5.0, 5.0), (2.6, 3.5), connectionstyle="arc3,rad=-0.15")
    arrow(ax, (5.0, 5.0), (7.4, 3.5), connectionstyle="arc3,rad=0.15")

    box(ax, (0.5, 2.55), 4.1, 1.05,
        "TRAIN split = time <= 40\n421,761 rows",
        fc="white", ec=COLORS["accent"], fontsize=8.0)
    box(ax, (5.4, 2.55), 4.1, 1.05,
        "OOT split = 41 <= time <= 60\n199,975 rows (stress window)",
        fc="white", ec=COLORS["warn"], fontsize=8.0)

    box(ax, (2.5, 0.9), 5.0, 1.15,
        "LEFT TRUNCATION: 41,831 / 49,974 loans (83.7%)\nenter with loan‐age > 0 at first observation\n"
        "(already seasoned when the observation window opens)",
        fc="#fdecea", ec=COLORS["warn"], fontsize=7.6)
    arrow(ax, (2.7, 2.55), (4.2, 2.05), color=COLORS["gray"], ls="--", lw=1.0)
    arrow(ax, (7.5, 2.55), (5.8, 2.05), color=COLORS["gray"], ls="--", lw=1.0)

    ax.set_title("From raw vendor file to loan-quarter at-risk panel (outputs/panel/waterfall.md)",
                 fontsize=10.5)
    fig.tight_layout()
    fig.savefig(OUT / "02_panel_construction_flowchart.png")
    plt.close(fig)
    print("wrote 02_panel_construction_flowchart.png")


# =============================================================================
# Exhibit — discrimination: train vs OOT AUC (default & prepay hazards)
# =============================================================================
def fig_auc_train_oot():
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    models = ["default hazard\n(DCR)", "prepay hazard\n(DCR)", "default hazard\n(SFLLD Phase B)"]
    train = [0.7476, 0.6839, 0.8536]
    oot = [0.6609, 0.5841, 0.6847]
    x = range(len(models))
    w = 0.32
    ax.bar([i - w / 2 for i in x], train, width=w, color=COLORS["accent"], label="train AUC")
    ax.bar([i + w / 2 for i in x], oot, width=w, color=COLORS["warn"], label="OOT AUC")
    for i, (a, b) in enumerate(zip(train, oot)):
        ax.text(i - w / 2, a + 0.012, f"{a:.3f}", ha="center", fontsize=8)
        ax.text(i + w / 2, b + 0.012, f"{b:.3f}", ha="center", fontsize=8)
    ax.axhline(0.5, color=COLORS["gray"], lw=1, ls=":")
    ax.text(2.55, 0.505, "AUC = 0.50 (coin flip)", fontsize=7, color=COLORS["gray"], ha="right")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, fontsize=8.5)
    ax.set_ylabel("AUC (one-quarter-ahead / one-month-ahead event)")
    ax.set_ylim(0.45, 0.95)
    ax.set_title("Discrimination survives the OOT stress window (honest degradation, no refit)")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT / "07_auc_train_oot.png")
    plt.close(fig)
    print("wrote 07_auc_train_oot.png")


# =============================================================================
# Exhibit — PSI band-by-band (tests/fixtures/compute_validation.py worked example)
# =============================================================================
def fig_psi_bands():
    import numpy as np
    expected = np.array([0.10, 0.25, 0.30, 0.25, 0.10])
    actual = np.array([0.06, 0.20, 0.30, 0.28, 0.16])
    terms = (actual - expected) * np.log(actual / expected)
    bands = ["band 1", "band 2", "band 3", "band 4", "band 5"]

    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    x = range(len(bands))
    w = 0.35
    axes[0].bar([i - w / 2 for i in x], expected, width=w, color=COLORS["accent"], label="expected (development)")
    axes[0].bar([i + w / 2 for i in x], actual, width=w, color=COLORS["warn"], label="actual (current)")
    axes[0].set_xticks(list(x)); axes[0].set_xticklabels(bands, fontsize=8)
    axes[0].set_ylabel("population share")
    axes[0].set_title("Score-band shares, development vs current")
    axes[0].legend(frameon=False, fontsize=7.5)

    colors = [COLORS["good"] if t >= 0 else COLORS["blue2"] for t in terms]
    axes[1].bar(bands, terms, color=colors)
    for i, t in enumerate(terms):
        axes[1].text(i, t + (0.0008 if t >= 0 else -0.0018), f"{t:.4f}", ha="center", fontsize=7.5)
    axes[1].axhline(0, color="#888888", lw=0.8)
    axes[1].set_ylabel("PSI term (a_i - e_i) x ln(a_i / e_i)")
    axes[1].set_title(f"PSI band terms, summing to {terms.sum():.4f} (< 0.10, stable)")
    fig.tight_layout()
    fig.savefig(OUT / "08_psi_bands.png")
    plt.close(fig)
    print("wrote 08_psi_bands.png")


if __name__ == "__main__":
    fig_competing_risks()
    fig_panel_flowchart()
    fig_auc_train_oot()
    fig_psi_bands()
