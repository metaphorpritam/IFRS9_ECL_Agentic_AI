"""Regenerate Ch.11 Exhibit 11.1 (panel-construction flowchart) — QA fix.

The original render clipped the bottom "merged panel" box (its lower edge and
padding were cut off by the axes ylim not covering the full patch height).
This script reproduces the same diagram content 1:1 (same boxes, same text,
same layout/colors) with ylim extended to fully contain every box.

Run: uv run --no-sync python notes/assets/img/ch11/build_diagram_01.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon  # noqa: E402

OUT = Path(__file__).resolve().parent


def box(ax, xy, w, h, text, fc="white", ec=COLORS["accent"], fontsize=9.0,
        textcolor="#1a1a1a", lw=1.3, zorder=3):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                        linewidth=lw, edgecolor=ec, facecolor=fc, zorder=zorder)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fontsize, color=textcolor, zorder=zorder + 1, linespacing=1.4)
    return p


def diamond(ax, cx, cy, w, h, text, fc="white", ec=COLORS["warn"], fontsize=8.6, lw=1.3):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    p = Polygon(pts, closed=True, linewidth=lw, edgecolor=ec, facecolor=fc, zorder=3)
    ax.add_patch(p)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fontsize,
             color="#1a1a1a", zorder=4, linespacing=1.35)


def arrow(ax, p0, p1, color="#555555", lw=1.4, style="-|>",
          connectionstyle="arc3,rad=0.0"):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=13,
                         color=color, lw=lw, zorder=2,
                         connectionstyle=connectionstyle, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


BLUE_FILL = "#eef3fb"
GREEN_FILL = "#eaf7f1"
RED_FILL = "#fdecea"
BEIGE_FILL = "#f7f5ee"
PURPLE = COLORS["purple"]
GREEN = "#1e7e34"
RED = COLORS["warn"]
ACCENT = COLORS["accent"]

fig, ax = plt.subplots(figsize=(11.6, 8.6))
ax.set_xlim(0, 11.6)
ax.set_ylim(-0.35, 9.7)   # <-- extended so row H's box+padding is never clipped
ax.axis("off")
ax.set_title("Panel construction: raw SFLLD files -> absorbing D90 default panel -> macro merge",
              fontsize=13, fontweight="bold", pad=10)

# Row A — raw files (y ~ 8.55-9.35)
box(ax, (0.35, 8.55), 4.9, 0.85,
    "sample_orig_{YYYY}.txt\n32 fields, 1 row/loan\n17 vintage zips",
    fc="white", ec=PURPLE)
box(ax, (6.35, 8.55), 4.9, 0.85,
    "sample_svcg_{YYYY}.txt\n32 fields, 1 row/loan-month\n17 vintage zips",
    fc="white", ec=PURPLE)

# Row B — freddie.ingest (y ~ 7.35-8.05)
box(ax, (2.05, 7.35), 7.5, 0.75,
    "freddie.ingest: sentinel->NaN, dtype cast,\nfield-order assert len==32, empirical\nvalidate_orig()/validate_svcg() checks",
    fc=BLUE_FILL, ec=ACCENT)

# Row C — severe flag (y ~ 6.45-7.05)
box(ax, (2.05, 6.45), 7.5, 0.62,
    "severe[t] = (dlq_num >= 3) OR is_reo_acquisition\n(current_delinquency_status == 'RA')",
    fc=BLUE_FILL, ec=ACCENT)

# Row D — keep row iff (y ~ 5.45-6.15)
box(ax, (2.05, 5.45), 7.5, 0.72,
    "keep row iff prior_severe_count == 0\n(absorbing-D90 truncation: drop every row\nAFTER a loan's first severe month)",
    fc=BLUE_FILL, ec=ACCENT)

# Row E — tie-break diamond + branches (diamond center y ~ 4.55)
diamond(ax, 5.8, 4.55, 3.0, 1.15,
        "tie-break:\nzero_balance_code\npopulated on THIS\nsame row?", ec=RED)
box(ax, (0.35, 4.15), 3.15, 0.78,
    "NO: d90_event = 1\n(first & only D90\nrow for this loan)",
    fc=GREEN_FILL, ec=GREEN)
box(ax, (8.1, 4.15), 3.15, 0.78,
    "YES: disposition code\nWINS. d90_event\nsuppressed this row",
    fc=RED_FILL, ec=RED)

# Row F — panel_monthly.parquet (y ~ 3.15-3.85)
box(ax, (2.05, 3.15), 7.5, 0.7,
    "panel_monthly.parquet — 837,500 loans,\n39,522,565 loan-months; d90_event / prepay_event\nmutually exclusive AS MODELED",
    fc=BLUE_FILL, ec=ACCENT)

# Row G — macro / loan_orig (y ~ 2.0-2.75)
box(ax, (0.35, 2.0), 4.9, 0.75,
    "freddie.macro: FRED {ST}UR / {ST}STHPI\nby property_state x month\n(fallback: national anchor)",
    fc=GREEN_FILL, ec=GREEN)
box(ax, (6.35, 2.0), 4.9, 0.75,
    "loan_orig.parquet: FULL svcg history\n-> terminal_outcome, actual_loss_*\n(NCL / realized-LGD fields)",
    fc=GREEN_FILL, ec=GREEN)

# Row H — final merged panel (y ~ 0.0-0.85) — the box that was previously clipped
box(ax, (1.05, 0.0), 9.5, 0.85,
    "merged panel: d90_event, prepay_event,\nuer_lag1, delta_uer_lag1, hpi_growth_lag1,\nupdated_ltv -> Ch.11 EDA + Ch.12 hazard/LGD",
    fc=BEIGE_FILL, ec=ACCENT)

# Arrows
arrow(ax, (2.8, 8.55), (4.5, 8.1))
arrow(ax, (8.8, 8.55), (7.1, 8.1))
arrow(ax, (5.8, 7.35), (5.8, 7.07))
arrow(ax, (5.8, 6.45), (5.8, 6.17))
arrow(ax, (5.8, 5.45), (5.8, 5.13))
arrow(ax, (4.3, 4.55), (1.9, 4.55))
arrow(ax, (7.3, 4.55), (9.65, 4.55))
arrow(ax, (1.9, 4.15), (4.8, 3.85), connectionstyle="arc3,rad=-0.15")
arrow(ax, (9.65, 4.15), (7.05, 3.85), connectionstyle="arc3,rad=0.15")
arrow(ax, (3.7, 3.15), (2.8, 2.75))
arrow(ax, (7.9, 3.15), (8.8, 2.75))
arrow(ax, (2.8, 2.0), (4.8, 0.85), connectionstyle="arc3,rad=-0.2")
arrow(ax, (8.8, 2.0), (7.05, 0.85), connectionstyle="arc3,rad=0.2")

plt.savefig(OUT / "01_panel_construction_flowchart.png")
plt.close(fig)
print("wrote", OUT / "01_panel_construction_flowchart.png")
