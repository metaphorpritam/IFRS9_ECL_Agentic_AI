"""Regenerate Ch.13 (Governance, MDD & Closing Synthesis) figures.

Run: uv run --no-sync python notes/assets/img/ch13/build_diagrams.py
Sources: outputs/gate/*.md, wiki/memory/log.md, outputs/mdd/MDD.md §4.2/§4.4/§6,
tests/fixtures/compute_pd.py (WOE/IV), the scratch structural-LGD calculation
(this chapter's own worked example, §13.4). Uses the shared textbook
matplotlib style (.claude/skills/pageindex-plus/assets/matplotlib_setup.py).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402

apply_textbook_style()
import numpy as np  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

OUT = Path(__file__).resolve().parent


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=8.6,
        textcolor="#1a1a1a", lw=1.3, zorder=3, ls="-"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder, linestyle=ls)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.32)
    return p


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>",
          connectionstyle="arc3,rad=0.0", ls="-"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                         color=color, lw=lw, linestyle=ls, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# =============================================================================
# Exhibit 13.1 -- the governance loop
# =============================================================================
def fig_governance_loop():
    fig, ax = plt.subplots(figsize=(10.2, 8.4))
    ax.set_xlim(0, 11.3)
    ax.set_ylim(-0.3, 11.6)
    ax.axis("off")
    ax.text(5.65, 11.35, "The recurring governance loop, every layer of this project",
            ha="center", va="top", fontsize=9.8, style="italic", color="#4a4a4a")

    stages = [
        (3.2, 9.3, "AUTHOR\nbuilds/fits, writes\nRESULTS + rationale", "#eef3fb", COLORS["accent"]),
        (6.5, 9.3, "ADVERSARIAL REVIEW\nindependent agent,\nsame numbers, no\nauthor assumptions", "#fdf1e3", COLORS["orange"]),
        (8.15, 6.2, "FIX or OVERTURN\nreport's own\nnumbers decide,\nnot seniority", "#fdecea", COLORS["warn"]),
        (6.5, 3.1, "GATE\nfull pytest suite,\nfingerprint tripwire,\nzero regressions", "#eaf7f1", COLORS["good"]),
        (3.2, 3.1, "DECISION REGISTER\nwiki/memory/\ndecisions.md,\nappend-only", "#f4f2fc", "#6c4fb5"),
        (1.55, 6.2, "SHIP / NEXT CYCLE\ncommit, live-Space\nverify, session log", "#f0f0f0", "#555555"),
    ]
    w, h = 2.85, 1.75
    centers = []
    for x0, y0, text, fc, ec in stages:
        box(ax, (x0, y0), w, h, text, fc=fc, ec=ec, fontsize=8.1)
        centers.append((x0 + w / 2, y0 + h / 2))

    # explicit boundary anchor points (not centers) so arrows are visible in
    # the gap between boxes, with a clear arrowhead, rather than hidden under
    # the next box (zorder=3 boxes drawn over zorder=2 arrows).
    anchors = {
        # (from_idx, to_idx): (point_on_from_box, point_on_to_box)
        (0, 1): ((3.2 + w, 9.3 + h / 2), (6.5, 9.3 + h / 2)),
        (1, 2): ((6.5 + w * 0.82, 9.3), (8.15 + w * 0.55, 6.2 + h)),
        (2, 3): ((8.15 + w * 0.55, 6.2), (6.5 + w * 0.82, 3.1 + h)),
        (3, 4): ((6.5, 3.1 + h / 2), (3.2 + w, 3.1 + h / 2)),
        (4, 5): ((3.2 + w * 0.18, 3.1 + h), (1.55 + w * 0.45, 6.2)),
        (5, 0): ((1.55 + w * 0.45, 6.2 + h), (3.2 + w * 0.18, 9.3)),
    }
    for (i, j), (p0, p1) in anchors.items():
        arrow(ax, p0, p1, connectionstyle="arc3,rad=0.12", color="#666666", lw=1.6)

    ax.text(5.3, 6.2, "loop", ha="center", va="center", fontsize=9.5, color="#999999", style="italic")
    ax.text(5.65, 0.9,
            "Every stage is evidence-producing: RESULTS, a review verdict, a test count, a decision-register entry\n"
            "or a session-log line. Section 13.11 walks two real turns of this loop end to end (the COVID overturn,\n"
            "the FRED-badge honesty catch) where the review stage genuinely changed the shipped answer.",
            ha="center", va="center", fontsize=8.1, color="#4a4a4a")

    fig.savefig(OUT / "01_governance_loop.png")
    plt.close(fig)


# =============================================================================
# Exhibit 13.2 -- the freeze / fingerprint-tripwire mechanism
# =============================================================================
def fig_freeze_tripwire():
    fig, ax = plt.subplots(figsize=(11.6, 6.0))
    ax.set_xlim(0, 13.4)
    ax.set_ylim(0, 6.6)
    ax.axis("off")
    ax.text(6.7, 6.42, "Frozen-engine gate + fingerprint tripwire (engine/{hazard,lgd,ead,staging,ecl}.py, frozen 2026-07-05)",
            ha="center", va="top", fontsize=9.4, style="italic", color="#4a4a4a")

    box(ax, (0.2, 4.55), 2.9, 1.15, "133 golden fixtures\n(tests/fixtures/\ncompute_*.py)\nagreement to last\ndisplayed digit",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=8.0)
    box(ax, (3.5, 4.55), 2.9, 1.15, "full pytest suite\n(engine + panel +\nagent + Freddie, as\neach layer ships)",
        fc="#eef3fb", ec=COLORS["accent"], fontsize=8.0)
    box(ax, (6.8, 4.55), 3.0, 1.15, "GATE = 0 failures\n->\nengine/ FROZEN\n(first freeze:\n187/187, 2026-07-05)",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=8.2)
    arrow(ax, (3.1, 5.13), (3.5, 5.13))
    arrow(ax, (6.4, 5.13), (6.8, 5.13))

    box(ax, (10.3, 4.55), 2.9, 1.15, "data/processed/\npanel.parquet\nsha256-pinned,\nchecked every gate",
        fc="#f0f0f0", ec="#555555", fontsize=8.0)

    box(ax, (0.2, 2.55), 4.3, 1.35,
        "EVERY later gate re-scans the 5 frozen files:\nscan_code.py --fingerprints\nknowledge/code_fp.json\nclassifies each file NONE/COSMETIC/STRUCTURAL",
        fc="#fff7e6", ec=COLORS["orange"], fontsize=7.5)
    arrow(ax, (8.3, 4.55), (5.5, 3.9), connectionstyle="arc3,rad=-0.2", color=COLORS["orange"])

    box(ax, (4.7, 0.35), 3.9, 1.5,
        "NONE\nbyte-identical (git-blob\nsha256 belt-and-braces\ncross-check) ->\nfingerprint tripwire silent,\ngate proceeds",
        fc="#eaf7f1", ec=COLORS["good"], fontsize=8.0)
    box(ax, (8.9, 0.35), 3.9, 1.5,
        "COSMETIC / STRUCTURAL\nfingerprint FIRES ->\ngate BLOCKS until a\ndecision-register entry\njustifies the change",
        fc="#fdecea", ec=COLORS["warn"], fontsize=8.0)
    arrow(ax, (5.8, 2.55), (6.4, 1.85))
    arrow(ax, (7.6, 2.55), (10.4, 1.85))

    box(ax, (0.2, 0.35), 4.0, 1.5,
        "ISOLATION CONTRACT\n(rung-3 stretch, any future\ndataset): engine stays\nfrozen + stateless -- no\ncross-dataset coefficient\ninheritance is even possible",
        fc="#f4f2fc", ec="#6c4fb5", fontsize=7.7)

    fig.savefig(OUT / "02_freeze_tripwire.png")
    plt.close(fig)


# =============================================================================
# Exhibit 13.3 -- gate-history timeline
# =============================================================================
def fig_gate_timeline():
    gates = [
        ("Engine\nfreeze", "2026-07-05", 187, "engine/ frozen: 133 fixtures\n+ 54 EAD/LGD/staging/ECL"),
        ("Day-3\nscenarios", "2026-07-07", 278, "Vasicek, DFAST scenarios,\nsatellite, Jensen, challenger"),
        ("Day-4\nship", "2026-07-07", 381, "LangGraph Tier-1 + refusal,\nFastAPI+Preact, Docker, HF Space"),
        ("Stretch\nTier-3+MCP", "2026-07-08", 422, "query_model_docs retrieval,\nMCP server"),
        ("App v2 +\nTier-2", "2026-07-08", 509, "5-tab north-star app,\nanalyze_data sandbox"),
        ("UI v3", "2026-07-16", 513, "fintech design pass,\nwaterfall regression script"),
        ("SFLLD\nPhase A", "2026-07-17", 553, "837k-loan real panel,\nstate macro merge, EDA"),
        ("REASONED\nroute", "2026-07-17", 582, "3-way router split,\nspelled-number guard fix"),
        ("SFLLD\nPhase B", "2026-07-18", 659, "hazard/LGD refit, ALFRED\nbacktest, LSTM challenger"),
        ("MDD +\nFreddie tab", "2026-07-19", 664, "MDD.md/.html, Real Data\ntab, .dockerignore fix"),
        ("Macro/FRED\ninterp.", "2026-07-19", 665, "hazard-ratio fields,\nFRED-badge honesty fix"),
    ]
    n = len(gates)
    fig, ax = plt.subplots(figsize=(13.2, 4.6))
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text((n - 1) / 2, 9.75, "Gate history -- zero regressions across every gate (187 -> 665, 2026-07-05 to 2026-07-19)",
            ha="center", va="top", fontsize=9.8, style="italic", color="#4a4a4a")

    xs = np.arange(n)
    y_line = 5.6
    ax.plot([xs[0] - 0.3, xs[-1] + 0.3], [y_line, y_line], color="#999999", lw=1.6, zorder=1)
    for i, (name, date, tests, added) in enumerate(gates):
        x = xs[i]
        ax.scatter([x], [y_line], s=70, color=COLORS["accent"], zorder=3, edgecolor="white", linewidth=0.8)
        ax.text(x, y_line + 0.35, f"{tests}", ha="center", va="bottom", fontsize=8.6, fontweight="bold",
                color=COLORS["accent"])
        above = (i % 2 == 0)
        if above:
            ax.text(x, y_line + 1.0, name, ha="center", va="bottom", fontsize=7.6, fontweight="bold")
            ax.text(x, y_line + 2.55, added, ha="center", va="top", fontsize=6.7, color="#4a4a4a", linespacing=1.25)
            ax.plot([x, x], [y_line + 0.55, y_line + 0.95], color="#cccccc", lw=0.8, zorder=1)
        else:
            ax.text(x, y_line - 0.5, name, ha="center", va="top", fontsize=7.6, fontweight="bold")
            ax.text(x, y_line - 1.75, date, ha="center", va="top", fontsize=6.6, color="#888888")
            ax.text(x, y_line - 2.25, added, ha="center", va="top", fontsize=6.7, color="#4a4a4a", linespacing=1.25)
            ax.plot([x, x], [y_line - 0.1, y_line - 0.45], color="#cccccc", lw=0.8, zorder=1)

    fig.savefig(OUT / "03_gate_timeline.png")
    plt.close(fig)


# =============================================================================
# Exhibit 13.4 -- WOE / IV worked example (native-chart, from compute_pd.py)
# =============================================================================
def fig_woe_iv():
    import importlib.util
    fx_path = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "compute_pd.py"
    spec = importlib.util.spec_from_file_location("compute_pd", fx_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    labels = ["≤60%", "60–80%", "80–90%", ">90%"]
    woe = [m.RESULTS[f"woe_{b}"] for b in m.BIN_LABELS]
    iv = [m.RESULTS[f"iv_contrib_{b}"] for b in m.BIN_LABELS]
    bad_rate = [m.RESULTS[f"bad_rate_pct_{b}"] for b in m.BIN_LABELS]

    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.3))

    ax = axes[0]
    colors = [COLORS["good"] if v >= 0 else COLORS["warn"] for v in bad_rate]
    ax.bar(labels, bad_rate, color=COLORS["accent"])
    ax.set_title("Bad rate by LTV bin")
    ax.set_ylabel("bad rate (%)")

    ax = axes[1]
    colors = [COLORS["good"] if v >= 0 else COLORS["warn"] for v in woe]
    ax.bar(labels, woe, color=colors)
    ax.axhline(0, color="#888888", lw=0.9)
    ax.set_title("WOE by LTV bin")
    ax.set_ylabel("WOE_i = ln(good share / bad share)")

    ax = axes[2]
    ax.bar(labels, iv, color=COLORS["purple"])
    ax.set_title(f"IV contribution by bin\n(total IV = {m.RESULTS['iv_total_ltv']:.4f})")
    ax.set_ylabel("(good share - bad share) x WOE_i")

    for ax in axes:
        ax.tick_params(axis="x", labelsize=8)

    fig.suptitle("Origination-LTV scorecard: 10,000 applications, 500 bads (tests/fixtures/compute_pd.py)",
                  fontsize=9.4, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "04_woe_iv_bars.png", bbox_inches="tight")
    plt.close(fig)


# =============================================================================
# Exhibit 13.5 -- mortgage structural-LGD flowchart (secured lending, s10.3)
# =============================================================================
def fig_structural_lgd():
    fig, ax = plt.subplots(figsize=(11.6, 3.9))
    ax.set_xlim(0, 13.6)
    ax.set_ylim(0, 4.4)
    ax.axis("off")
    ax.text(6.8, 4.25, "Mortgage structural LGD (s10.3): indexed collateral value to loss",
            ha="center", va="top", fontsize=9.6, style="italic", color="#4a4a4a")

    steps = [
        (0.2, "Indexed collateral\nvalue\n(HPI-indexed\nappraisal)\n€195,000", "#eef3fb", COLORS["accent"]),
        (2.9, "x (1 - forced-sale\ndiscount)\ndistressed vs\nmarket value\n€171,600", "#fff7e6", COLORS["orange"]),
        (5.6, "- selling costs\n- prior charges\n(senior liens)\n€156,304", "#fdf1e3", COLORS["orange"]),
        (8.3, "discount to default\ndate @ EIR over\ntime-to-repossession\n€142,215 PV", "#f4f2fc", "#6c4fb5"),
        (11.0, "loss = shortfall\nvs exposure\nLGD = 1 - PV/EAD\n= 35.36%", "#fdecea", COLORS["warn"]),
    ]
    w, h = 2.4, 2.9
    y0 = 0.65
    centers = []
    for x0, text, fc, ec in steps:
        box(ax, (x0, y0), w, h, text, fc=fc, ec=ec, fontsize=8.1)
        centers.append((x0 + w, y0 + h / 2))
    for i in range(len(centers) - 1):
        x1 = centers[i][0]
        x2 = steps[i + 1][0]
        arrow(ax, (x1, y0 + h / 2), (x2, y0 + h / 2))

    fig.savefig(OUT / "05_lgd_structural_flowchart.png")
    plt.close(fig)


# =============================================================================
# Exhibit 13.6 -- ALFRED-vintage honest backtest, headline panel
# =============================================================================
def fig_alfred_backtest():
    dates = ["2007-12", "2009-12", "2015-12", "2019-12", "2021-12"]
    realised = [8.750, 6.569, 1.397, 4.601, 1.161]
    frozen = [0.928, 5.554, 1.857, 0.920, 1.734]
    hindsight = [4.613, 4.658, 1.855, 71.519, 1.229]

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.0), gridspec_kw={"width_ratios": [1.35, 1]})

    ax = axes[0]
    x = np.arange(len(dates))
    w = 0.27
    ax.bar(x - w, realised, width=w, label="realised (36mo cum. D90)", color=COLORS["good"])
    ax.bar(x, frozen, width=w, label="predicted, frozen macro", color=COLORS["warn"])
    ax.bar(x + w, np.clip(hindsight, 0, 12), width=w, label="predicted, hindsight macro\n(2019-12 truncated: 71.5%)",
           color=COLORS["accent"])
    ax.set_xticks(x)
    ax.set_xticklabels(dates)
    ax.set_ylabel("36-month cumulative D90 rate (%)")
    ax.set_title("Realised vs frozen- vs hindsight-macro projection")
    ax.legend(fontsize=6.6, loc="upper right")

    ax = axes[1]
    miss_frozen = [9.42, 1.18, 0.75, 5.00, 0.67]
    miss_hindsight = [1.90, 1.41, 0.75, 0.06, 0.94]
    ax.plot(dates, miss_frozen, marker="o", color=COLORS["warn"], label="frozen miss ratio")
    ax.plot(dates, miss_hindsight, marker="s", color=COLORS["accent"], label="hindsight miss ratio")
    ax.axhline(1.0, color="#888888", lw=0.9, ls="--")
    ax.set_ylabel("realised / predicted (miss ratio, x)")
    ax.set_title("Miss ratio: >1 = model underpredicted")
    ax.legend(fontsize=7)
    ax.tick_params(axis="x", labelrotation=25)

    fig.suptitle("ALFRED-vintage honest backtest (outputs/freddie/backtest/backtest_report.md)",
                  fontsize=9.4, y=1.03)
    fig.tight_layout()
    fig.savefig(OUT / "06_alfred_backtest_panel.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_governance_loop()
    fig_freeze_tripwire()
    fig_gate_timeline()
    fig_woe_iv()
    fig_structural_lgd()
    fig_alfred_backtest()
    print("Ch.13 figures written to", OUT)
