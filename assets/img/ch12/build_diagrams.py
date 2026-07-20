"""
Ch.12 custom diagrams — run with:
  uv run --no-project notes/assets/img/ch12/build_diagrams.py
(PEP-723 header below pins matplotlib/numpy/scipy for an isolated ephemeral env,
same --no-project pattern as notes/assets/data/build_data_pack.py.)

Three new diagrams for Chapter 12 (Freddie Models, Backtest & LSTM):
  06_merton_payoff_threshold.png   — firm-value GBM path + lognormal V_T distribution,
                                      default region V_T < D shaded (D-4 closure)
  12_asof_t_timeline.png           — as-of-T information-set timeline for the ALFRED backtest
  15_lstm_lift_decomposition.png   — AUC-by-group + event-share-by-group, the honest lift split
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8", "numpy>=1.26", "scipy>=1.11"]
# ///
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import COLORS, apply_textbook_style, figsize_for  # noqa: E402

apply_textbook_style()
OUT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# 06 — Merton payoff/threshold sketch
# ---------------------------------------------------------------------------
rng = np.random.default_rng(42)
V0, D, mu, sigma_A, T = 120.0, 100.0, 0.08, 0.20, 1.0
n_steps, n_paths = 252, 14
dt = T / n_steps
t_grid = np.linspace(0, T, n_steps + 1)

fig = plt.figure(figsize=figsize_for("wide"))
gs = fig.add_gridspec(1, 2, width_ratios=[2.1, 1], wspace=0.16)
ax0 = fig.add_subplot(gs[0])
ax1 = fig.add_subplot(gs[1], sharey=ax0)

paths = np.zeros((n_paths, n_steps + 1))
paths[:, 0] = V0
for i in range(n_paths):
    z = rng.standard_normal(n_steps)
    log_incr = (mu - 0.5 * sigma_A**2) * dt + sigma_A * np.sqrt(dt) * z
    paths[i, 1:] = V0 * np.exp(np.cumsum(log_incr))

defaulted = paths[:, -1] < D
for i in range(n_paths):
    c = COLORS["warn"] if defaulted[i] else COLORS["accent"]
    ax0.plot(t_grid, paths[i], color=c, lw=0.9, alpha=0.55)

ax0.axhline(D, color="black", lw=1.4, ls="-")
ax0.text(0.01, D - 9, "default barrier D = €100m", fontsize=8.5, va="top")
ax0.axhline(V0, color=COLORS["gray"], lw=0.8, ls=":")
ax0.text(0.55, V0 + 3, "V₀ = €120m", fontsize=8.5, color=COLORS["gray"], va="bottom")
ax0.set_xlim(0, T)
ax0.set_ylim(40, 220)
ax0.set_xlabel("time t (years)")
ax0.set_ylabel("firm asset value V(t) (€m)")
ax0.set_title("Simulated GBM asset-value paths", loc="left")
ax0.plot([], [], color=COLORS["accent"], lw=1.5, label="V(T) ≥ D  (survives)")
ax0.plot([], [], color=COLORS["warn"], lw=1.5, label="V(T) < D  (default)")
ax0.legend(loc="upper left", frameon=False)

# lognormal density of V_T at the right, shaded default region
v_range = np.linspace(40, 220, 600)
mean_logv = np.log(V0) + (mu - 0.5 * sigma_A**2) * T
sd_logv = sigma_A * np.sqrt(T)
density = norm.pdf(np.log(v_range), mean_logv, sd_logv) / v_range
ax1.plot(density, v_range, color=COLORS["accent"], lw=1.6)
mask = v_range < D
ax1.fill_betweenx(v_range[mask], 0, density[mask], color=COLORS["warn"], alpha=0.35)
dd = (np.log(V0 / D) + (mu - 0.5 * sigma_A**2) * T) / (sigma_A * np.sqrt(T))
pd_pct = norm.cdf(-dd) * 100
ax1.axhline(D, color="black", lw=1.4)
ax1.text(density.max() * 0.32, D - 30, f"P(V(T)<D)\n= Φ(-DD)\n= {pd_pct:.2f}%",
          fontsize=8.5, color=COLORS["warn"], ha="left")
ax1.set_xlabel("density of V(T)")
ax1.set_title("Lognormal V(T)", loc="left")
ax1.tick_params(labelleft=False)
ax1.set_xlim(left=0)

fig.suptitle("Merton (1974): firm-value GBM, default barrier, and the lognormal terminal distribution", y=1.02, fontsize=11)
fig.savefig(OUT / "06_merton_payoff_threshold.png")
plt.close(fig)
print("wrote 06_merton_payoff_threshold.png, DD=%.4f PD=%.2f%%" % (dd, pd_pct))

# ---------------------------------------------------------------------------
# 12 — as-of-T information-set timeline
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(9.0, 6.4))
ax.set_xlim(-65, 42)
ax.set_ylim(0, 11.5)
ax.axis("off")

T0 = 0  # reporting date, months
train_start = -60
proj_end = 36
axis_y = 6.0

# main timeline axis — xlim MUST cover train_start (-60) so the fit-window
# rectangle below is not clipped into an invisible sliver (bug found in
# render QA: the old xlim(-2, 62) cut off everything left of -2, leaving only
# a 2-month-wide fragment of the -60..0 fit window visible).
ax.annotate("", xy=(41, axis_y), xytext=(-64, axis_y), arrowprops=dict(arrowstyle="-|>", color="black", lw=1.3))
ax.text(39.5, axis_y + 0.3, "calendar time", fontsize=8.5, ha="right")

# fit window (history available at T)
ax.add_patch(plt.Rectangle((train_start, axis_y - 0.35), T0 - train_start, 0.7, color=COLORS["accent"], alpha=0.55))
ax.text((train_start + T0) / 2, axis_y + 1.9,
        "FIT window: refit champion spec on\ndata + macro known-as-of T\n(tail months w/ unpublished macro dropped)",
        fontsize=7.6, ha="center", va="bottom")
ax.annotate("", xy=((train_start + T0) / 2, axis_y + 1.75), xytext=((train_start + T0) / 2, axis_y + 0.4),
            arrowprops=dict(arrowstyle="-", color=COLORS["gray"], lw=0.8))

# reporting date T
ax.plot([T0, T0], [axis_y - 0.9, axis_y + 0.9], color="black", lw=1.6)
ax.text(T0, axis_y - 1.15, "T\n(reporting date,\ne.g. 2007-12)", fontsize=8, ha="center", va="top", fontweight="bold")

# publication lag annotation, ABOVE the fit-window label so it never collides
ax.annotate("", xy=(T0, axis_y + 3.3), xytext=(T0 - 5, axis_y + 3.3),
            arrowprops=dict(arrowstyle="<|-|>", color=COLORS["gray"], lw=1.1))
ax.text(T0 - 2.5, axis_y + 3.55, "HPI publication lag\n(5 months, ALFRED-FHFA STHPI)",
        fontsize=7.2, ha="center", color=COLORS["gray"])

# projection window, split into two scenario bands (well below the axis)
frozen_y = axis_y - 2.3
actual_y = axis_y - 3.5
ax.add_patch(plt.Rectangle((T0, frozen_y - 0.3), proj_end, 0.6, color=COLORS["warn"], alpha=0.5, zorder=2))
ax.text(T0 + proj_end / 2, frozen_y,
        "PROJECT 36mo forward -- scenario (a) FROZEN\n(macro + delta-momentum held at last known-at-T)",
        fontsize=7.4, ha="center", va="center", zorder=4)

ax.add_patch(plt.Rectangle((T0, actual_y - 0.3), proj_end, 0.6, color=COLORS["purple"], alpha=0.5, zorder=2))
ax.text(T0 + proj_end / 2, actual_y,
        "PROJECT 36mo forward -- scenario (b) ACTUAL (hindsight)\n(macro path as it truly unfolded, T..T+36mo)",
        fontsize=7.4, ha="center", va="center", zorder=4)

# outcome comparison at T+36 -- zorder=1 (below the scenario-band boxes/text at
# zorder 2/4) so the dashed line does not slice through the FROZEN/ACTUAL
# label text where it crosses x=T0+proj_end (render QA finding: previously
# drawn last/on-top, cutting through the "N" of FROZEN and "T)" of known-at-T).
ax.plot([T0 + proj_end, T0 + proj_end], [actual_y - 0.9, axis_y + 0.5], color="black", lw=1.0, ls="--", zorder=1)
ax.text(T0 + proj_end, actual_y - 1.1, "T+36mo:\nrealized D90 rate\n(what actually happened)",
        fontsize=7.6, ha="center", va="top")

# miss-ratio arrow, below both scenario bands
mr_y = actual_y - 2.1
ax.annotate("", xy=(T0 + proj_end, mr_y), xytext=(T0, mr_y),
            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.0))
ax.text(T0 + proj_end / 2, mr_y - 0.35, "miss ratio = realized / predicted, computed separately for each scenario",
        fontsize=7.6, ha="center")

ax.set_title("The ALFRED-vintage backtest information set: refit-in-time at T, project forward, compare to realized",
              fontsize=10.5, loc="left")
fig.subplots_adjust(top=0.90, bottom=0.03)
fig.savefig(OUT / "12_asof_t_timeline.png")
plt.close(fig)
print("wrote 12_asof_t_timeline.png")

# ---------------------------------------------------------------------------
# 15 — LSTM lift decomposition (AUC by group + event-share by group)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))

groups = ["Clean history\n(n=19,643,934)", "Prior delinquency\nspell (n=977,978)"]
champion_auc = [0.5386, 0.5698]
lstm_auc = [0.5287, 0.9570]
x = np.arange(2)
w = 0.32
axes[0].bar(x - w / 2, champion_auc, width=w, color=COLORS["accent"], label="Champion (GLM)")
axes[0].bar(x + w / 2, lstm_auc, width=w, color=COLORS["warn"], label="LSTM challenger")
axes[0].axhline(0.5, color=COLORS["gray"], lw=0.8, ls=":")
axes[0].set_xticks(x)
axes[0].set_xticklabels(groups, fontsize=8)
axes[0].set_ylabel("OOT AUC")
axes[0].set_ylim(0.45, 1.0)
axes[0].set_title("(a) AUC by delinquency-history group", loc="left", fontsize=9.5)
for i in range(2):
    axes[0].annotate(f"{lstm_auc[i]-champion_auc[i]:+.3f}", xy=(x[i], max(champion_auc[i], lstm_auc[i]) + 0.02),
                      ha="center", fontsize=7.6, color=COLORS["warn"] if i == 1 else COLORS["gray"])
axes[0].legend(loc="upper left", frameon=False, fontsize=7.6)

events = [40, 16792]
n_pop = [19643934, 977978]
labels2 = ["Clean history", "Prior delinquency\nspell"]
event_share = [100 * e / sum(events) for e in events]
pop_share = [100 * n / sum(n_pop) for n in n_pop]
xx = np.arange(2)
axes[1].bar(xx - w / 2, pop_share, width=w, color=COLORS["blue2"], label="share of OOT loans")
axes[1].bar(xx + w / 2, event_share, width=w, color=COLORS["warn"], label="share of OOT D90 events")
axes[1].set_xticks(xx)
axes[1].set_xticklabels(labels2, fontsize=8)
axes[1].set_ylabel("% of OOT population / events")
axes[1].set_title("(b) Where the outcome mass sits", loc="left", fontsize=9.5)
for i in range(2):
    axes[1].annotate(f"{event_share[i]:.1f}%", xy=(xx[i] + w / 2, event_share[i] + 1.5), ha="center", fontsize=7.6)
    axes[1].annotate(f"{pop_share[i]:.1f}%", xy=(xx[i] - w / 2, pop_share[i] + 1.5), ha="center", fontsize=7.6)
axes[1].legend(loc="center left", frameon=False, fontsize=7.6)
axes[1].set_ylim(0, 108)

fig.suptitle("LSTM lift decomposition: the +0.3078 headline OOT delta is concentrated where 99.8% of events already sit", fontsize=10, y=1.03)
fig.tight_layout()
fig.savefig(OUT / "15_lstm_lift_decomposition.png")
plt.close(fig)
print("wrote 15_lstm_lift_decomposition.png")
