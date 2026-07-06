"""Fit the MLP challenger PD model and emit the champion-challenger scorecard.

Run:  cd <repo root> && uv run --no-sync python analysis/fit_challenger.py

CHALLENGER, NEVER CHAMPION (plan section 5): the frozen Day-2 engine remains
the sole source of production PDs; this script only stress-tests the
champion's functional form. The champion cloglog hazards are REFIT here from
the frozen engine code (read-only import, identical numbers to Day 1 -- the
GLM is deterministic) so both models are scored by one harness.

Like-for-like framing: same loan-quarter at-risk rows, same one-quarter-ahead
default_event target, same covariate information set and timing convention
(challenger/mlp.py docstring). The MLP gets no spline and no hand-built
interaction -- whether the seasoning hump and the double-trigger LTV response
REAPPEAR without being specified is a scorecard question, not an input.

Exhibits written to outputs/challenger/:
  scorecard.md            the champion-challenger scorecard (all numbers)
  reliability.png         calibration curves, train + OOT, both models
  psi_scores.png          score distributions train vs OOT + PSI, both models
  perm_importance.png     challenger permutation importance (OOT), features
                          + family blocks (jointly permuted)
  pdp_grid.png            PDPs: updated_ltv, uer_lag1, fico_s, loan_age --
                          challenger vs champion overlay
  pdp_double_trigger.png  LTV PDP at calm (5%) vs stressed (10%) unemployment
  staging_swap.png        lifetime-PD ratio, champion vs challenger, with the
                          Stage-2 boundary quadrants (t=40 snapshot)
  mlp_challenger.pt       torch checkpoint (state_dict + scaler + meta)

Design choices (documented, not silent):
* Permutation importance permutes FAMILY BLOCKS jointly as well as single
  features: uer_lag1/uer_chg4_lag1 correlate at ~0.94, so single-feature
  permutation splits (and understates) the macro signal.
* PDPs average over a fixed-seed 20,000-row sample of the training fit rows
  (PDP background = training distribution, sklearn convention). The uer_lag1
  PDP moves the LEVEL holding 4q momentum fixed -- the same decomposition
  caveat as the champion's uer_lag1 coefficient (outputs/hazard/
  fit_stats.md); the double-trigger exhibit conditions on it explicitly.
* Staging swap keeps the champion PREPAYMENT hazard in the competing-risk
  survival for both variants -- only the default PD model is swapped, so the
  Stage-2 deltas isolate the PD-model difference. Probation and the (inert)
  30-DPD backstop are identical machinery on both sides and are omitted:
  the comparison is the memoryless quantitative trigger at the snapshot.
* Challenger lifetime PDs clamp loan_age at the training support (level-off
  tail, the plan's accepted default); the champion extrapolates its natural
  spline linearly. Documented asymmetry -- an MLP has no disciplined tail.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, NullFormatter
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from mpl_style import COLORS, apply_textbook_style, figsize_for  # noqa: E402
from engine.hazard import (  # noqa: E402
    REQUIRED_COLS,
    fit_default_hazard,
    fit_prepay_hazard,
    predict_hazard,
)
from engine.staging import (  # noqa: E402
    StagingConfig,
    build_macro_map,
    lifetime_pd_table,
    origination_covariates,
    quantitative_sicr,
)
from challenger.mlp import (  # noqa: E402
    CONT_FEATURES,
    FEATURE_FAMILY,
    FEATURES,
    build_features,
    cum_default_pd_mlp,
    fit_mlp_hazard,
    predict_from_features,
)

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "challenger"
SEED = 0
SNAP_T = 40                 # staging-swap snapshot (train boundary, 2010Q1)
N_PDP_SAMPLE = 20_000
N_RELI_BINS = 20
N_PSI_BINS = 10
PERM_REPEATS = 3
AUC_FLOOR = 0.60            # degenerate-model tripwire (also a unit test)

CHAMP, CHAL = "champion (cloglog GLM)", "challenger (MLP)"


def fail(msg: str) -> None:
    print(f"\n*** SANITY FAILURE: {msg}", file=sys.stderr)
    raise SystemExit(1)


def plain_log_ticks(ax, which: str = "xy") -> None:
    """Plain-number tick labels on log axes (mpl_style sets
    text.parse_math=False, which would print LogFormatter's mathtext
    literally -- learnings section 3)."""
    fmt = FuncFormatter(lambda v, _: f"{v:g}")
    for a in which:
        axis = ax.xaxis if a == "x" else ax.yaxis
        axis.set_major_formatter(fmt)
        axis.set_minor_formatter(NullFormatter())


# ---------------------------------------------------------------------------
# metric helpers
# ---------------------------------------------------------------------------

def reliability_bins(y: np.ndarray, p: np.ndarray,
                     n_bins: int = N_RELI_BINS) -> pd.DataFrame:
    """Quantile-binned mean predicted vs observed event rate."""
    q = pd.qcut(pd.Series(p), n_bins, labels=False, duplicates="drop")
    g = pd.DataFrame({"y": y, "p": p, "bin": q}).groupby("bin")
    return pd.DataFrame({"pred": g["p"].mean(), "obs": g["y"].mean(),
                         "n": g.size()})


def psi(train_scores: np.ndarray, oot_scores: np.ndarray,
        n_bins: int = N_PSI_BINS) -> tuple[float, pd.DataFrame]:
    """Population stability index of a score distribution, train -> OOT.

    Bins = train-score deciles (open-ended outer edges); PSI =
    sum (p_i - q_i) ln(p_i / q_i) with 1e-6 flooring. Rule of thumb:
    < 0.10 stable, 0.10-0.25 moderate shift, > 0.25 large shift.
    """
    edges = np.quantile(train_scores, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(train_scores, bins=edges)[0] / len(train_scores)
    q = np.histogram(oot_scores, bins=edges)[0] / len(oot_scores)
    p, q = np.clip(p, 1e-6, None), np.clip(q, 1e-6, None)
    contrib = (p - q) * np.log(p / q)
    tab = pd.DataFrame({"train_share": p, "oot_share": q, "contrib": contrib})
    return float(contrib.sum()), tab


def permutation_importance_oot(model, F_oot: pd.DataFrame, y: np.ndarray,
                               seed: int = SEED) -> pd.DataFrame:
    """AUC drop on OOT when a feature (or family block) is permuted.

    Blocks are permuted with ONE shared row permutation per repeat so
    within-block dependence is preserved (docstring: correlated macro pair).
    """
    base = roc_auc_score(y, predict_from_features(model, F_oot))
    blocks = {f: [f] for f in FEATURES}
    for fam in sorted(set(FEATURE_FAMILY.values())):
        cols = [f for f in FEATURES if FEATURE_FAMILY[f] == fam]
        blocks[f"[family] {fam}"] = cols
    rng = np.random.default_rng(seed)
    rows = []
    for name, cols in blocks.items():
        drops = []
        for _ in range(PERM_REPEATS):
            perm = rng.permutation(len(F_oot))
            Fp = F_oot.copy()
            Fp[cols] = F_oot[cols].to_numpy()[perm]
            drops.append(base - roc_auc_score(
                y, predict_from_features(model, Fp)))
        rows.append({"block": name, "family": FEATURE_FAMILY.get(name, ""),
                     "auc_drop": float(np.mean(drops)),
                     "sd": float(np.std(drops))})
    return (pd.DataFrame(rows).set_index("block")
            .sort_values("auc_drop", ascending=False)), base


def pdp_curve(sample: pd.DataFrame, raw_col: str, grid: np.ndarray,
              mlp_model, champ_model) -> pd.DataFrame:
    """Partial dependence of both models' hazards on one RAW column.

    Sets sample[raw_col] = v for each grid value and averages predictions
    (build_features re-derives fico_s / ltv10 from the raw columns, so the
    champion and challenger see identical counterfactual frames).
    """
    rows = []
    for v in grid:
        s = sample.copy()
        s[raw_col] = v
        rows.append({
            "x": v,
            "mlp": float(predict_from_features(
                mlp_model, build_features(s)).mean()),
            "champ": float(predict_hazard(champ_model, s).mean()),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    apply_textbook_style()
    OUT.mkdir(parents=True, exist_ok=True)

    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]
    oot = panel[panel["split"] == "oot"]
    train_fit = train[train["lag_warmup"] == 0]
    y_tr = train_fit["default_event"].to_numpy(dtype=float)
    y_oo = oot["default_event"].to_numpy(dtype=float)
    print(f"panel {len(panel):,} | train fit rows {len(train_fit):,} "
          f"(event rate {y_tr.mean():.4f}) | oot {len(oot):,} "
          f"(event rate {y_oo.mean():.4f})")

    # ---- champion: refit from the frozen engine (read-only) ---------------
    m_def = fit_default_hazard(train)
    m_pre = fit_prepay_hazard(train)
    p_tr_champ = predict_hazard(m_def, train_fit)
    p_oo_champ = predict_hazard(m_def, oot)
    auc_champ = {"train": roc_auc_score(y_tr, p_tr_champ),
                 "oot": roc_auc_score(y_oo, p_oo_champ)}
    print(f"champion  AUC train {auc_champ['train']:.4f} | "
          f"OOT {auc_champ['oot']:.4f}")

    # ---- challenger --------------------------------------------------------
    mlp = fit_mlp_hazard(train, seed=SEED)
    F_tr = build_features(train_fit)
    F_oo = build_features(oot)
    p_tr_mlp = predict_from_features(mlp, F_tr)
    p_oo_mlp = predict_from_features(mlp, F_oo)
    auc_mlp = {"train": roc_auc_score(y_tr, p_tr_mlp),
               "oot": roc_auc_score(y_oo, p_oo_mlp)}
    print(f"challenger AUC train {auc_mlp['train']:.4f} | "
          f"OOT {auc_mlp['oot']:.4f} | backend {mlp.meta['backend']} on "
          f"{mlp.meta['device']} | best epoch {mlp.meta['best_epoch']} "
          f"(val AUC {mlp.meta['best_val_auc']:.4f})")

    if not np.isfinite(p_tr_mlp).all() or not np.isfinite(p_oo_mlp).all():
        fail("challenger produced non-finite predictions")
    if auc_mlp["oot"] <= AUC_FLOOR:
        fail(f"challenger OOT AUC {auc_mlp['oot']:.4f} <= {AUC_FLOOR} -- "
             "degenerate model")

    # ---- reliability curves ------------------------------------------------
    reli = {("train", CHAMP): reliability_bins(y_tr, p_tr_champ),
            ("train", CHAL): reliability_bins(y_tr, p_tr_mlp),
            ("oot", CHAMP): reliability_bins(y_oo, p_oo_champ),
            ("oot", CHAL): reliability_bins(y_oo, p_oo_mlp)}
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    for ax, split, title in [(axes[0], "train", "train (t<=40)"),
                             (axes[1], "oot", "out-of-time (t=41..60)")]:
        for label, color in [(CHAMP, COLORS["accent"]), (CHAL, COLORS["warn"])]:
            b = reli[(split, label)]
            ax.plot(100 * b["pred"], 100 * b["obs"], "o-", ms=3, lw=1.2,
                    color=color, label=label)
        lim = [0.02, 30]
        ax.plot(lim, lim, ls=":", lw=1, color=COLORS["gray"],
                label="perfect calibration")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(lim); ax.set_ylim(lim)
        plain_log_ticks(ax)
        ax.set_xlabel("mean predicted hazard (%, log)")
        ax.set_title(title)
    axes[0].set_ylabel("observed default rate (%, log)")
    axes[0].legend(frameon=False, fontsize=7, loc="upper left")

    def _cal_word(p, y):
        r = p.mean() / y.mean()
        return (f"{'over' if r > 1 else 'under'}-predicts "
                f"{max(r, 1 / r):.2f}x on average")

    cal_note = (f"OOT level: champion {_cal_word(p_oo_champ, y_oo)}, "
                f"challenger {_cal_word(p_oo_mlp, y_oo)}")
    fig.suptitle(f"Reliability: {N_RELI_BINS} score-quantile bins -- "
                 f"{cal_note}", y=1.05, fontsize=11)
    fig.savefig(OUT / "reliability.png")
    plt.close(fig)
    print("wrote", OUT / "reliability.png")

    # ---- PSI ----------------------------------------------------------------
    psi_champ, _ = psi(p_tr_champ, p_oo_champ)
    psi_mlp, _ = psi(p_tr_mlp, p_oo_mlp)
    print(f"PSI train->OOT: champion {psi_champ:.4f} | "
          f"challenger {psi_mlp:.4f}")
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    for ax, p_tr, p_oo, label, val in [
            (axes[0], p_tr_champ, p_oo_champ, CHAMP, psi_champ),
            (axes[1], p_tr_mlp, p_oo_mlp, CHAL, psi_mlp)]:
        bins = np.geomspace(max(min(p_tr.min(), p_oo.min()), 1e-5), 0.5, 40)
        ax.hist(p_tr, bins=bins, density=True, alpha=0.55,
                color=COLORS["accent"], label="train")
        ax.hist(p_oo, bins=bins, density=True, alpha=0.55,
                color=COLORS["orange"], label="OOT")
        ax.set_xscale("log")
        plain_log_ticks(ax, "x")
        ax.set_title(f"{label}\nPSI = {val:.3f}")
        ax.set_xlabel("predicted quarterly hazard (log scale)")
        ax.legend(frameon=False, fontsize=7)
    axes[0].set_ylabel("density")
    fig.suptitle("Score distributions train -> OOT (PSI bins = train "
                 "deciles; <0.10 stable, 0.10-0.25 moderate, >0.25 large)",
                 y=1.05, fontsize=11)
    fig.savefig(OUT / "psi_scores.png")
    plt.close(fig)
    print("wrote", OUT / "psi_scores.png")

    # ---- permutation importance (OOT) --------------------------------------
    imp, base_auc = permutation_importance_oot(mlp, F_oo, y_oo)
    fam_rows = imp[imp.index.str.startswith("[family]")]
    single_rows = imp[~imp.index.str.startswith("[family]")]
    fam_rank = fam_rows["auc_drop"].sort_values(ascending=False)
    print("family importance (OOT AUC drop):")
    for k, v in fam_rank.items():
        print(f"  {k:28s} {v:+.4f}")

    fig, axes = plt.subplots(
        1, 2, figsize=figsize_for("twocol"),
        gridspec_kw={"width_ratios": [1.4, 1]})
    s = single_rows["auc_drop"].sort_values()
    fam_of = [FEATURE_FAMILY[f] for f in s.index]
    fam_col = {"macro": COLORS["warn"], "collateral": COLORS["orange"],
               "borrower": COLORS["accent"], "age": COLORS["purple"],
               "incentive": COLORS["good"]}
    axes[0].barh(s.index, s.values, color=[fam_col[f] for f in fam_of])
    axes[0].set_title("single features")
    f = fam_rank.sort_values()
    names = [k.replace("[family] ", "") for k in f.index]
    axes[1].barh(names, f.values, color=[fam_col[n] for n in names])
    axes[1].set_title("family blocks (jointly permuted)")
    for ax in axes:
        ax.set_xlabel("OOT AUC drop when permuted")
    fig.suptitle(f"Challenger permutation importance on OOT (base AUC "
                 f"{base_auc:.4f}, {PERM_REPEATS} repeats; families permuted "
                 "as blocks -- uer level/momentum correlate 0.94)",
                 y=1.05, fontsize=11)
    fig.savefig(OUT / "perm_importance.png")
    plt.close(fig)
    print("wrote", OUT / "perm_importance.png")

    # ---- PDPs ---------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    samp = train_fit.iloc[
        rng.choice(len(train_fit), N_PDP_SAMPLE, replace=False)].copy()
    grids = {
        "updated_ltv": np.linspace(20, 250, 24),
        "uer_lag1": np.linspace(np.quantile(train_fit["uer_lag1"], 0.01),
                                np.quantile(train_fit["uer_lag1"], 0.99), 20),
        "FICO_orig_time": np.linspace(500, 820, 20),
        "loan_age": np.arange(0, 61, 2, dtype=float),
    }
    pdps = {c: pdp_curve(samp, c, g, mlp, m_def) for c, g in grids.items()}

    titles = {"updated_ltv": "updated LTV (%)",
              "uer_lag1": "unemployment level, lag 1 (%)",
              "FICO_orig_time": "FICO at origination",
              "loan_age": "loan age (quarters on book)"}
    fig, axes = plt.subplots(2, 2, figsize=(9.0, 6.0))
    for ax, col in zip(axes.ravel(), grids):
        d = pdps[col]
        ax.plot(d["x"], 100 * d["mlp"], color=COLORS["warn"], lw=2,
                label=CHAL)
        ax.plot(d["x"], 100 * d["champ"], color=COLORS["accent"], lw=1.5,
                ls="--", label=CHAMP)
        ax.set_xlabel(titles[col])
        ax.set_ylabel("mean predicted hazard (%)")
    axes[0, 0].legend(frameon=False, fontsize=7)
    hump = pdps["loan_age"]
    hump_peak = float(hump["x"].iloc[int(np.argmax(hump["mlp"]))])
    axes[1, 1].axvline(hump_peak, color=COLORS["warn"], ls=":", lw=1)
    axes[1, 1].text(hump_peak + 1, axes[1, 1].get_ylim()[1] * 0.55,
                    f"learned peak ~{hump_peak:.0f}q", fontsize=7,
                    color=COLORS["warn"])
    fig.suptitle("Partial dependence, challenger vs champion (background: "
                 f"{N_PDP_SAMPLE:,}-row train sample; challenger was given "
                 "NO spline and NO interaction)", y=1.02, fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "pdp_grid.png")
    plt.close(fig)
    print("wrote", OUT / "pdp_grid.png")

    # double trigger: LTV PDP conditioned on calm vs stressed unemployment
    ltv_grid = grids["updated_ltv"]
    dt = {}
    for uer, tag in [(5.0, "calm"), (10.0, "stress")]:
        s_u = samp.copy()
        s_u["uer_lag1"] = uer
        dt[tag] = pdp_curve(s_u, "updated_ltv", ltv_grid, mlp, m_def)

    def slope(d, colname):
        m = (d["x"] >= 100) & (d["x"] <= 200)
        return float(np.polyfit(d.loc[m, "x"], d.loc[m, colname], 1)[0])

    steep_mlp = slope(dt["stress"], "mlp") / max(slope(dt["calm"], "mlp"),
                                                 1e-12)
    steep_ch = slope(dt["stress"], "champ") / max(slope(dt["calm"], "champ"),
                                                  1e-12)
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    for ax, key, title in [(axes[0], "mlp", CHAL), (axes[1], "champ", CHAMP)]:
        for tag, color in [("calm", COLORS["good"]), ("stress",
                                                      COLORS["warn"])]:
            ax.plot(dt[tag]["x"], 100 * dt[tag][key], lw=2, color=color,
                    label=f"{tag} UER ({5 if tag == 'calm' else 10}%)")
        ax.set_xlabel("updated LTV (%)")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=7, loc="upper left")
    axes[0].set_ylabel("mean predicted hazard (%)")
    fig.suptitle("Double trigger probe: LTV response at calm vs stressed "
                 f"unemployment (100-200 LTV slope ratio stress/calm: "
                 f"challenger {steep_mlp:.2f}x, champion {steep_ch:.2f}x)",
                 y=1.05, fontsize=11)
    fig.savefig(OUT / "pdp_double_trigger.png")
    plt.close(fig)
    print("wrote", OUT / "pdp_double_trigger.png")
    print(f"seasoning hump: challenger PDP peak at {hump_peak:.0f}q | "
          f"LTV slope ratio stress/calm: challenger {steep_mlp:.2f}x, "
          f"champion {steep_ch:.2f}x")

    # ---- staging impact at t=40 --------------------------------------------
    cfg = StagingConfig()
    hist = panel[panel["time"] <= SNAP_T]
    mm = build_macro_map(hist)
    models = {"default": m_def, "prepay": m_pre}
    tbl = lifetime_pd_table(hist, models, SNAP_T, mm, cfg)
    snap = (hist[hist["time"] == SNAP_T].sort_values("id")
            .reset_index(drop=True))
    if not (tbl["id"].to_numpy() == snap["id"].to_numpy()).all():
        fail("staging table / snapshot id misalignment")
    orig = origination_covariates(snap, mm)
    R = tbl["R"].to_numpy()
    pd_now_c = cum_default_pd_mlp(mlp, m_pre, snap, R)
    pd_orig_c = cum_default_pd_mlp(mlp, m_pre, orig, R)
    years = R / 4.0
    tbl_c = pd.DataFrame({
        "id": tbl["id"], "R": R,
        "lifetime_pd_now": pd_now_c, "lifetime_pd_orig": pd_orig_c,
        "ann_addon": (1.0 - (1.0 - pd_now_c) ** (1.0 / years))
                     - (1.0 - (1.0 - pd_orig_c) ** (1.0 / years)),
        "pd_ratio": np.where(
            pd_orig_c > 0.0,
            pd_now_c / np.where(pd_orig_c > 0.0, pd_orig_c, 1.0),
            np.where(pd_now_c > 0.0, np.inf, 1.0)),
    })
    # Stage 3 (defaults) is definitionally identical; payoff-quarter rows are
    # derecognised (same convention as outputs/staging exhibits)
    live = ((snap["default_event"].to_numpy() == 0)
            & (snap["payoff_event"].to_numpy() == 0))
    trig_champ = quantitative_sicr(tbl, cfg) & live
    trig_chal = quantitative_sicr(tbl_c, cfg) & live
    n_live = int(live.sum())
    both = int((trig_champ & trig_chal).sum())
    only_champ = int((trig_champ & ~trig_chal).sum())
    only_chal = int((~trig_champ & trig_chal).sum())
    n2_champ, n2_chal = int(trig_champ.sum()), int(trig_chal.sum())
    net = n2_chal - n2_champ
    print(f"staging swap t={SNAP_T}: live {n_live:,} | Stage 2 champion "
          f"{n2_champ:,} vs challenger {n2_chal:,} (net {net:+,}) | "
          f"agree {both:,} | champion-only {only_champ:,} | "
          f"challenger-only {only_chal:,}")

    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    r_ch = np.clip(tbl.loc[live, "pd_ratio"], 1e-2, 1e3)
    r_ml = np.clip(tbl_c.loc[live, "pd_ratio"], 1e-2, 1e3)
    agree = (trig_champ == trig_chal)[live]
    ax.scatter(r_ch[agree], r_ml[agree], s=2, alpha=0.15,
               color=COLORS["gray"], label="same stage")
    ax.scatter(r_ch[~agree], r_ml[~agree], s=3, alpha=0.4,
               color=COLORS["warn"], label="stage flips")
    ax.axvline(cfg.ratio_threshold, ls=":", lw=1, color=COLORS["accent"])
    ax.axhline(cfg.ratio_threshold, ls=":", lw=1, color=COLORS["accent"])
    ax.set_xscale("log"); ax.set_yscale("log")
    plain_log_ticks(ax)
    ax.set_xlabel("champion lifetime-PD ratio (now / at origination)")
    ax.set_ylabel("challenger lifetime-PD ratio")
    ax.set_title(f"SICR ratio, t={SNAP_T} (2010Q1) snapshot -- dotted lines "
                 f"= {cfg.ratio_threshold}x doubling trigger\n(trigger also "
                 f"requires the {100 * cfg.abs_addon:.1f}pp p.a. add-on; "
                 "flips shown for the FULL trigger)", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    fig.savefig(OUT / "staging_swap.png")
    plt.close(fig)
    print("wrote", OUT / "staging_swap.png")

    # ---- checkpoint ---------------------------------------------------------
    if mlp.backend == "torch":
        import torch

        torch.save({"state_dict": mlp.net.state_dict(),
                    "scaler_mean": mlp.scaler.mean,
                    "scaler_std": mlp.scaler.std,
                    "scaler_n_rows": mlp.scaler.n_rows,
                    "scaler_time_range": mlp.scaler.time_range,
                    "age_max": mlp.age_max,
                    "log_pos_weight": mlp.log_pos_weight,
                    "meta": mlp.meta}, OUT / "mlp_challenger.pt")
        print("wrote", OUT / "mlp_challenger.pt")

    # ---- scorecard ----------------------------------------------------------
    fam_tab = "\n".join(
        f"| {k.replace('[family] ', '')} | {v:+.4f} |"
        for k, v in fam_rank.items())
    top_single = "\n".join(
        f"| {k} | {FEATURE_FAMILY[k]} | {v:+.4f} |"
        for k, v in single_rows["auc_drop"]
        .sort_values(ascending=False).head(8).items())
    m = mlp.meta
    dominant = ", ".join(fam_rank.index[:2].str.replace("[family] ", ""))
    lines = [
        "# Champion-challenger scorecard -- MLP hazard PD model",
        "",
        "**CHALLENGER, NEVER CHAMPION** (plan section 5). The frozen Day-2 "
        "engine remains the sole source of production PDs; this scorecard "
        "documents what a flexible learner finds in the SAME data. "
        "Like-for-like by construction: identical loan-quarter at-risk rows, "
        "identical one-quarter-ahead default_event target, identical "
        "covariate information set and timing convention (all macro "
        "regressors lagged), no extra features. The MLP received NO age "
        "spline and NO hand-built LTV x unemployment interaction.",
        "",
        "## Model",
        "",
        f"| | champion | challenger |",
        f"|---|---|---|",
        f"| form | cloglog GLM, cr(age, df=5) spline, centered LTVxUER "
        f"interaction | MLP {m['hidden']}, ReLU, dropout {m['dropout']}, "
        f"AdamW weight decay {m['weight_decay']} |",
        f"| class imbalance | none needed (GLM likelihood) | "
        f"{m['class_weighting']} (pos_weight = {m['pos_weight']:.1f}) |",
        f"| early stopping | n/a (IRLS convergence) | by TIME: fit t<=32, "
        f"validate t={m['val_time_range'][0]}..{m['val_time_range'][1]} "
        f"(2008Q2..2010Q1), best epoch {m['best_epoch']} (val AUC "
        f"{m['best_val_auc']:.4f}), then refit on full train for "
        f"{m['best_epoch']} epochs |",
        f"| standardisation | n/a | z-score of continuous features, fitted "
        f"on train only (times {m['scaler_time_range'][0]}.."
        f"{m['scaler_time_range'][1]}) |",
        f"| backend | statsmodels IRLS | {m['backend']} on {m['device']}, "
        f"seed {m['seed']}, deterministic algorithms = "
        f"{m['deterministic_algorithms']} |",
        "",
        "## Discrimination (one-quarter-ahead default AUC)",
        "",
        "| model | train (t<=40) | OOT (t=41..60) |",
        "|---|---|---|",
        f"| champion | {auc_champ['train']:.4f} | {auc_champ['oot']:.4f} |",
        f"| challenger | {auc_mlp['train']:.4f} | {auc_mlp['oot']:.4f} |",
        f"| delta (challenger - champion) | "
        f"{auc_mlp['train'] - auc_champ['train']:+.4f} | "
        f"{auc_mlp['oot'] - auc_champ['oot']:+.4f} |",
        "",
        "## Calibration and stability",
        "",
        "![reliability](reliability.png)",
        "",
        f"Reliability (score-quantile bins, log-log): {cal_note} (models "
        "trained through 2008-2010Q1 stress score the 2010-2015 recovery -- "
        "any shared level gap is the macro regime shift, not an MLP "
        "artefact). Challenger predictions are prior-corrected "
        "(sigmoid(z - ln pos_weight)) so the class weighting does not "
        "inflate the hazard scale.",
        "",
        "| PSI train -> OOT (bins = train score deciles) | value | reading |",
        "|---|---|---|",
        f"| champion | {psi_champ:.3f} | "
        f"{'stable' if psi_champ < 0.10 else 'moderate' if psi_champ < 0.25 else 'large shift'} |",
        f"| challenger | {psi_mlp:.3f} | "
        f"{'stable' if psi_mlp < 0.10 else 'moderate' if psi_mlp < 0.25 else 'large shift'} |",
        "",
        "PSI context: these are POINT-IN-TIME scores whose inputs include "
        "lagged macro and HPI-indexed LTV, and the train window ends at the "
        "unemployment peak (t=40, 2010Q1) while OOT is the recovery -- a "
        "large train->OOT PSI here measures the CYCLE moving through the "
        "scores, which a PIT model is SUPPOSED to do, on top of any model "
        "instability. The champion's much larger PSI reflects its stronger "
        "macro response (its stress-quarter score mass has nowhere to go in "
        "the recovery), echoing the wiki's composition-vs-cycle caution -- "
        "it is not by itself evidence of a defect in either model.",
        "",
        "![psi](psi_scores.png)",
        "",
        "## What drives the challenger (permutation importance, OOT)",
        "",
        f"Base OOT AUC {base_auc:.4f}; drop when permuted, mean of "
        f"{PERM_REPEATS} repeats; families permuted as joint blocks "
        "(uer level/momentum correlate at 0.94 -- single-feature permutation "
        "splits that signal).",
        "",
        "| family block | OOT AUC drop |",
        "|---|---|",
        fam_tab,
        "",
        "| top single features | family | OOT AUC drop |",
        "|---|---|---|",
        top_single,
        "",
        f"Dominant families: **{dominant}**. Note the collateral family IS "
        "a macro channel in disguise: updated_ltv is the HPI-indexed "
        "collateral LTV, so the house-price cycle enters the challenger "
        "through the loan-level state variable rather than through the "
        "lagged macro aggregates -- the near-zero drop for the [macro] "
        "block means the AGGREGATE regressors add little ON TOP of the "
        "indexed LTV, not that the challenger ignores the cycle.",
        "",
        "![perm](perm_importance.png)",
        "",
        "## Learned shape vs specified shape (PDPs)",
        "",
        "![pdp](pdp_grid.png)",
        "",
        f"* **Seasoning hump: {'REAPPEARS' if 2 <= hump_peak <= 24 else 'DOES NOT REAPPEAR'}"
        f"** -- the challenger's loan_age partial dependence peaks at "
        f"{hump_peak:.0f} quarters on book with no spline supplied "
        "(champion's specified spline peaks at 12q, empirical at 10q). "
        f"Consistent with the [age] permutation drop of "
        f"{fam_rank.get('[family] age', float('nan')):+.4f} OOT: the "
        "challenger barely uses age, and its age shape is unstable across "
        "training configurations -- the spline prior the champion carries "
        "is doing real work.",
        f"* **Double trigger**: LTV slope (100-200 LTV band) at 10% vs 5% "
        f"unemployment -- challenger {steep_mlp:.2f}x, champion "
        f"{steep_ch:.2f}x. The champion's own fitted interaction was "
        "slightly NEGATIVE in-sample (slope flattens under stress; "
        "outputs/hazard/fit_stats.md), so the honest question is whether "
        "the challenger agrees with that in-sample substitution pattern, "
        "not whether it manufactures steepening.",
        "* uer_lag1 PDP moves the LEVEL holding 4q momentum fixed -- same "
        "decomposition caveat as the champion's uer_lag1 coefficient.",
        "",
        "![dt](pdp_double_trigger.png)",
        "",
        f"## Staging impact (t={SNAP_T} snapshot, 2010Q1)",
        "",
        "Challenger default PDs swapped into the frozen SICR machinery "
        "(lifetime-PD doubling trigger + 0.5pp p.a. add-on; "
        "engine/staging.py, read-only). Champion PREPAYMENT hazard kept in "
        "the competing-risk survival on both sides -- the deltas isolate the "
        "default-PD model. Memoryless quantitative trigger at the snapshot "
        "(probation and the structurally inert 30-DPD backstop are identical "
        "machinery on both sides). Stage 3 is definitionally identical.",
        "",
        f"| | count (of {n_live:,} live loans) |",
        "|---|---|",
        f"| Stage 2 -- champion | {n2_champ:,} "
        f"({100 * n2_champ / n_live:.1f}%) |",
        f"| Stage 2 -- challenger | {n2_chal:,} "
        f"({100 * n2_chal / n_live:.1f}%) |",
        f"| Stage 2 under both | {both:,} |",
        f"| champion-only (challenger DE-stages to Stage 1) | "
        f"{only_champ:,} |",
        f"| challenger-only (challenger PROMOTES to Stage 2) | "
        f"{only_chal:,} |",
        f"| net challenger effect | {net:+,} loans "
        f"({100 * net / n_live:+.1f}pp of the live book) |",
        "",
        f"Direction: the challenger {'DE-STAGES' if net < 0 else 'PROMOTES'} "
        "on net. Its now-vs-origination lifetime-PD ratios are compressed "
        "toward 1 relative to the champion's (flatter macro response plus "
        "the level-off age tail damp both legs of the relative test), so "
        "the doubling trigger fires far less often at the stress snapshot. "
        "This is a functional-form finding about the RELATIVE test, not an "
        "allowance restatement -- production staging stays with the frozen "
        "champion engine.",
        "",
        "![swap](staging_swap.png)",
        "",
        "## Documented simplifications / caveats",
        "",
        "* Challenger lifetime PDs clamp loan_age at the training support "
        f"(max {mlp.age_max:.0f}q; level-off tail, the plan's accepted "
        "default). The champion extrapolates its natural spline linearly. "
        "An MLP has no disciplined tail -- one reason it stays challenger.",
        "* Early stopping consumes the t=33..40 window for validation; the "
        "final model is REFIT on the full training window for the "
        "early-stopped epoch count to restore data parity with the "
        "champion.",
        "* Staging swap compares the memoryless quantitative trigger at the "
        "snapshot (no probation window, no backstop -- both identical "
        "machinery on both sides and inert/orthogonal to the PD swap).",
        "* Determinism: bitwise-reproducible on the same device/build "
        "(fixed seeds, deterministic algorithms, CUBLAS workspace pinned); "
        "results differ across CPU vs GPU and torch/CUDA versions.",
        "* Frozen-covariate projections on both lifetime-PD legs (rung-1 "
        "tail assumption inherited from the engine).",
    ]
    (OUT / "scorecard.md").write_text("\n".join(lines))
    print("wrote", OUT / "scorecard.md")

    print("\nKEY NUMBERS")
    print(f"  champion   AUC train {auc_champ['train']:.4f} | "
          f"OOT {auc_champ['oot']:.4f}")
    print(f"  challenger AUC train {auc_mlp['train']:.4f} | "
          f"OOT {auc_mlp['oot']:.4f}")
    print(f"  PSI champion {psi_champ:.3f} | challenger {psi_mlp:.3f}")
    print(f"  dominant families (perm importance): {dominant}")
    print(f"  seasoning hump peak {hump_peak:.0f}q | DT slope ratio "
          f"chal {steep_mlp:.2f}x champ {steep_ch:.2f}x")
    print(f"  Stage 2: champion {n2_champ:,} vs challenger {n2_chal:,} "
          f"(promote {only_chal:,}, de-stage {only_champ:,})")
    print("ALL GREEN")


if __name__ == "__main__":
    main()
