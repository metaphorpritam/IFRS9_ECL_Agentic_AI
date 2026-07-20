"""Regenerated exhibits for notes/cv_dossier.html.

Run:
    cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
    uv run --no-sync python notes/assets/img/dossier/build_diagrams.py

Every number plotted here is pasted from the cited source report, never
hand-typed independently of it — see the inline citations on each figure.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / ".claude/skills/pageindex-plus/assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT = Path(__file__).resolve().parent
apply_textbook_style()

# ---------------------------------------------------------------------------
# Exhibit D.1 -- DCR vs SFLLD hazard discrimination (train vs OOT AUC)
# Source: outputs/hazard/fit_stats.md (DCR: train 0.7476/OOT 0.6609 for the
# default hazard -- displayed at the report's own 3dp rounding, 0.748/0.661);
# outputs/freddie/hazard/metrics.json (SFLLD: train_auc 0.8535911902958723,
# oot_auc 0.6847251436480823).
# ---------------------------------------------------------------------------
models = ["DCR champion\n(621,736 rows, 49,974 loans)", "SFLLD champion\n(39.5M loan-months, 837,500 loans)"]
train_auc = [0.7476, 0.8535911902958723]
oot_auc = [0.6609, 0.6847251436480823]

fig, ax = plt.subplots(figsize=(7.2, 4.4))
x = np.arange(len(models))
w = 0.32
b1 = ax.bar(x - w / 2, train_auc, w, label="Train AUC", color=COLORS["accent"])
b2 = ax.bar(x + w / 2, oot_auc, w, label="OOT AUC", color=COLORS["warn"])
for bars in (b1, b2):
    for rect in bars:
        h = rect.get_height()
        ax.annotate(f"{h:.3f}" if h < 0.8 else f"{h:.4f}", (rect.get_x() + rect.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8.5)
ax.axhline(0.5, color=COLORS["gray"], linestyle=":", linewidth=1, label="random (AUC=0.5)")
ax.set_ylim(0.45, 0.95)
ax.set_xticks(x)
ax.set_xticklabels(models)
ax.set_ylabel("AUC (one-quarter/one-month-ahead default hazard)")
ax.set_title("The 0.68 headline in context: DCR vs SFLLD, train vs OOT")
ax.legend(loc="upper left", framealpha=0.9)
fig.tight_layout()
fig.savefig(OUT / "01_dcr_vs_sflld_auc.png")
plt.close(fig)

print("wrote", OUT / "01_dcr_vs_sflld_auc.png")
