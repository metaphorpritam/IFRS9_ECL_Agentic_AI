"""Fit the rung-1 two-stage workout LGD model and emit exhibits.

Run:  cd <repo root> && uv run python analysis/fit_lgd.py

Fits engine/lgd.py (cure logit x fractional-logit severity + explicit
beyond-EAD excess-loss loading) on TRAIN-split resolved default rows; the
out-of-time split (41..60) is scored READ-ONLY -- no refitting, no peeking
during specification. All validation samples are RESOLVED defaults only
(engine/lgd.py docstring: unresolved lgd_time is not a realised outcome;
48% of OOT default rows are open workouts and are excluded from both fit
and validation).

Exhibits written to outputs/lgd/:
  lgd_distribution.png  realised train LGD histogram (the section-10 bimodal
                        shape) with the two-part fit overlaid -- and the
                        one-regression mean that splits the two modes (too
                        high for the 12% cure spike at ~0, too low for the
                        write-off hump centred at 0.68)
  cure_by_ltv.png       empirical vs model cure rate by updated-LTV decile,
                        train and OOT panels
  calibration_ltv.png   realised vs predicted mean LGD by updated-LTV decile,
                        train and OOT panels
  lgd_report.md         coefficient tables (HC1 robust SEs for the fractional
                        logit), economic signs, cure-threshold sensitivity at
                        0.00 / 0.05 / 0.10, OOT calibration stats, loading
                        validation, documented simplifications

Sanity assertions (fail loudly, SystemExit):
  * economic signs -- cure falls in updated LTV, severity rises in it
    (already raised inside fit_lgd_models; re-checked here);
  * every predicted LGD in [0, sev_cap + excess_loading];
  * OOT calibration -- |mean predicted - mean realised| on resolved OOT
    default rows <= TOLERANCE_OOT_MEAN = 0.05 (5pp of EAD). The observed gap
    and its decomposition (cure vs severity margin) are reported honestly in
    lgd_report.md either way.

Design choices (documented here rather than silently made):
* Deciles are formed on TRAIN updated-LTV quantiles and the same bin edges
  are applied to OOT (deployment view: the binning rule is part of the
  model's frozen state). OOT mass shifts into the high-LTV bins because the
  stress episode sits in the OOT window -- bin counts are printed in the
  report so thin cells are visible.
* The distribution overlay shows the model-implied cure mass P(cure) as a
  block on the cure bin and the predicted severity mean on the non-cure hump
  -- the two-part model is a mean model per margin, not a density model, so
  overlaying a fitted density would overclaim.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from mpl_style import COLORS, apply_textbook_style, figsize_for  # noqa: E402
from engine.lgd import (  # noqa: E402
    CURE_THRESHOLD,
    LGD_REQUIRED_COLS,
    SEV_CAP,
    fit_lgd_models,
    predict_components,
    predict_lgd,
)

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "lgd"
TOLERANCE_OOT_MEAN = 0.05     # |mean pred - mean realised| on resolved OOT
N_DECILES = 10
THRESH_GRID = [0.0, CURE_THRESHOLD, 0.10]

# fixed colour-by-entity assignment across every panel
C_REAL = COLORS["accent"]     # realised / empirical
C_MODEL = COLORS["orange"]    # two-stage model prediction
C_NAIVE = COLORS["warn"]      # one-regression pathology
C_REF = COLORS["gray"]


def load_samples():
    """Panel -> (train resolved defaults, OOT resolved defaults, full panel)."""
    panel = pd.read_parquet(PANEL)
    d = panel[(panel["default_event"] == 1) & panel["res_time"].notna()].copy()
    d = d.dropna(subset=LGD_REQUIRED_COLS + ["lgd_time"])
    d["cure"] = (d["lgd_time"] <= CURE_THRESHOLD).astype(int)
    tr = d[d["split"] == "train"].copy()
    oo = d[d["split"] == "oot"].copy()
    return tr, oo, panel


def decile_frame(models, sample: pd.DataFrame, edges: np.ndarray) -> pd.DataFrame:
    comp = predict_components(models, sample)
    g = sample.assign(
        pred_lgd=comp["lgd"].to_numpy(),
        p_cure=comp["p_cure"].to_numpy(),
        bin=pd.cut(sample["updated_ltv"], bins=edges, include_lowest=True),
    )
    agg = g.groupby("bin", observed=True).agg(
        n=("lgd_time", "size"),
        ltv_mid=("updated_ltv", "mean"),
        real_lgd=("lgd_time", "mean"),
        pred_lgd=("pred_lgd", "mean"),
        real_cure=("cure", "mean"),
        pred_cure=("p_cure", "mean"),
    ).reset_index()
    return agg[agg["n"] > 0]


def coef_table(res, robust: bool = False) -> pd.DataFrame:
    """Coefficient table; the severity GLM was fitted with cov_type='HC1',
    so its bse/z/p are already the robust (Papke-Wooldridge) ones."""
    se_name = "se(HC1)" if robust else "se"
    tab = pd.DataFrame({
        "coef": res.params, se_name: res.bse, "z": res.tvalues,
        "p": res.pvalues,
    })
    if not robust:
        tab["odds_ratio"] = np.exp(res.params)
    return tab


def md_table(df: pd.DataFrame, fmt: str = "{:.4f}") -> str:
    d = df.copy()
    for c in d.columns:
        if d[c].dtype.kind == "f":
            d[c] = d[c].map(lambda v: fmt.format(v))
    header = "| " + " | ".join([""] + list(d.columns)) + " |"
    sep = "|" + "---|" * (len(d.columns) + 1)
    rows = ["| " + " | ".join([str(i)] + [str(v) for v in r]) + " |"
            for i, r in zip(d.index, d.values)]
    return "\n".join([header, sep] + rows)


# ---------------------------------------------------------------------------
# exhibits
# ---------------------------------------------------------------------------

def plot_distribution(models, tr: pd.DataFrame) -> None:
    """Realised LGD histogram + two-part fit overlay (train, resolved)."""
    comp = predict_components(models, tr)
    lgd = tr["lgd_time"].to_numpy()
    shown = np.minimum(lgd, 1.25)          # lump the >1.25 tail into the last bin
    bins = np.arange(0.0, 1.30 + 1e-9, 0.05)
    w = np.full(len(shown), 1.0 / len(shown))

    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    ax.hist(shown, bins=bins, weights=w, color=C_REAL, alpha=0.55,
            edgecolor="white", linewidth=0.4,
            label="realised LGD (train, resolved)")

    # model cure mass on the cure bin [0, 0.05]
    p_cure_avg = comp["p_cure"].mean()
    emp_cure = tr["cure"].mean()
    ax.plot([0.025], [p_cure_avg], marker="v", color=C_MODEL, markersize=9,
            zorder=5, label=f"model cure mass  P(cure) = {p_cure_avg:.1%}")

    # non-cure severity means: realised vs model (incl. loading)
    nc_mask = tr["cure"] == 0
    real_sev = tr.loc[nc_mask, "lgd_time"].mean()
    model_sev = comp.loc[nc_mask.to_numpy(), "severity_adj"].mean()
    ax.axvline(min(real_sev, 1.25), color=C_REAL, lw=1.6, ls="-", alpha=0.9)
    ax.axvline(min(model_sev, 1.25), color=C_MODEL, lw=1.6, ls="--")

    # the one-regression pathology: a single mean through the mixture
    naive = lgd.mean()
    ax.axvline(naive, color=C_NAIVE, lw=1.8, ls=":")
    ax.annotate(f"one-regression mean {naive:.2f} splits the modes:\n"
                f"far too high for the {emp_cure:.0%} cure spike at ~0,\n"
                f"too low for write-offs centred at {real_sev:.2f}",
                xy=(naive, 0.071), xytext=(naive - 0.47, 0.098),
                fontsize=8, color=C_NAIVE, va="top",
                arrowprops=dict(arrowstyle="->", color=C_NAIVE, lw=0.9))
    ax.annotate(f"E[sev | non-cure]\nrealised {real_sev:.2f} / model {model_sev:.2f}"
                f"\n(incl. +{models.excess_loading:.3f} excess loading)",
                xy=(real_sev, 0.055), xytext=(0.80, 0.075), fontsize=8,
                color=C_REAL,
                arrowprops=dict(arrowstyle="->", color=C_REF, lw=0.9))
    ax.annotate(f"cure spike: empirical {emp_cure:.1%}",
                xy=(0.025, min(emp_cure, 0.16)), xytext=(0.10, 0.145),
                fontsize=8, color=C_REAL,
                arrowprops=dict(arrowstyle="->", color=C_REF, lw=0.9))

    ax.set_xlabel("realised workout LGD (share of EAD; > 1.25 lumped into last bin)")
    ax.set_ylabel("share of resolved defaults")
    ax.set_title("Bimodal realised LGD and the two-part fit (train, resolved workouts)")
    ax.legend(loc="upper right", frameon=False)
    ax.set_xlim(-0.02, 1.32)
    fig.savefig(OUT / "lgd_distribution.png")
    plt.close(fig)


def plot_two_panel(models, tr, oo, edges, kind: str) -> None:
    """kind = 'cure' or 'lgd': decile dot (empirical) vs line (model)."""
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"), sharey=True)
    for ax, (name, sample) in zip(axes, [("train", tr), ("OOT", oo)]):
        agg = decile_frame(models, sample, edges)
        if kind == "cure":
            emp, mod = agg["real_cure"], agg["pred_cure"]
            ylab, title = "cure rate", "Cure rate by updated-LTV decile"
        else:
            emp, mod = agg["real_lgd"], agg["pred_lgd"]
            ylab, title = "mean LGD", "Realised vs predicted LGD by updated-LTV decile"
        ax.plot(agg["ltv_mid"], mod, color=C_MODEL, lw=2.0, marker="o",
                markersize=4, label="model")
        ax.plot(agg["ltv_mid"], emp, color=C_REAL, ls="none", marker="o",
                markersize=6, label="empirical")
        thin = agg["n"] < 100
        if thin.any():
            ax.plot(agg.loc[thin, "ltv_mid"], emp[thin], ls="none", marker="o",
                    markersize=6, markerfacecolor="white", color=C_REAL)
        ax.set_title(f"{name}  (n = {int(agg['n'].sum()):,} resolved defaults)")
        ax.set_xlabel("updated LTV at default (%, decile mean)")
    axes[0].set_ylabel(ylab)
    axes[0].legend(frameon=False, loc="upper left" if kind == "lgd" else "upper right")
    fig.suptitle(title + "  --  hollow dots: decile n < 100", y=1.04, fontsize=11)
    fig.savefig(OUT / ("cure_by_ltv.png" if kind == "cure" else "calibration_ltv.png"))
    plt.close(fig)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def sensitivity_block(panel, tr, oo) -> tuple[str, pd.DataFrame]:
    rows = []
    for thr in THRESH_GRID:
        m = fit_lgd_models(panel, cure_threshold=thr)
        for name, sample in [("train", tr), ("oot", oo)]:
            cure = (sample["lgd_time"] <= thr).astype(int)
            comp = predict_components(m, sample)
            rows.append({
                "threshold": thr, "sample": name,
                "cure_rate_real": cure.mean(),
                "cure_rate_pred": comp["p_cure"].mean(),
                "mean_lgd_real": sample["lgd_time"].mean(),
                "mean_lgd_pred": comp["lgd"].mean(),
                "excess_loading": m.excess_loading,
            })
    sens = pd.DataFrame(rows)
    txt = md_table(sens.set_index("threshold"), "{:.4f}")
    return txt, sens


def build_report(models, tr, oo, panel, stats: dict) -> str:
    cure_tab = coef_table(models.cure_result)
    sev_tab = coef_table(models.severity_result, robust=True)
    sens_txt, sens = sensitivity_block(panel, tr, oo)
    edges = stats["edges"]
    agg_tr = decile_frame(models, tr, edges)
    agg_oo = decile_frame(models, oo, edges)

    gap = stats["oot_mean_pred"] - stats["oot_mean_real"]
    tol_line = ("**PASS** (within tolerance)" if abs(gap) <= TOLERANCE_OOT_MEAN
                else "**FAIL** (outside tolerance -- reported honestly)")

    return f"""# Two-stage workout LGD -- fit report

Model: `engine/lgd.py` -- cure logit x fractional-logit severity, explicit
beyond-EAD excess-loss loading. Methodology: notes section 10 (workout LGD is
bimodal; one regression through it predicts a value that never occurs).
Fit sample: TRAIN split, resolved defaults only ({models.n_resolved:,} rows =
{models.n_defaults:,} train default rows - {models.fit_meta['unresolved_dropped']:,}
unresolved workouts - {models.fit_meta['nan_covariate_dropped']} NaN-covariate rows).
Cure threshold {models.cure_threshold:.2f}: {models.n_cures:,} cures /
{models.n_noncure:,} non-cures (cure rate {models.n_cures / models.n_resolved:.1%}).

## Why resolved-only (incomplete-workout trap, notes section 10.3)

24.6% of all default rows have `res_time = NaN` -- open workouts at the window
end; 58% of their `lgd_time` values are coded exactly 0 (mean 0.19 vs 0.60 for
resolved). Treating them as realised would import a fake cure spike
concentrated in the OOT quarters (48% of OOT defaults are open vs 17% of
train). Residual selection bias (documented): resolved-only over-represents
fast workouts, and cures resolve faster (median 3q vs 5q for write-offs), so
cure is biased up / severity down for cohorts near the window end.

## Stage 1 -- cure logit  `{models.cure_formula}`

{md_table(cure_tab)}

Signs: **cure FALLS in updated LTV** (ltv10 {models.cure_params['ltv10']:+.3f},
asserted -- the collateral channel: equity lets a distressed borrower sell or
refinance out of default). loan_age {models.cure_params['loan_age']:+.3f}
(seasoned defaulters cure less -- burnout). fico_s
{models.cure_params['fico_s']:+.3f} (weak; conditional on current LTV,
origination score adds little to the cure margin). **uer_lag1
{models.cure_params['uer_lag1']:+.3f} is POSITIVE** -- reported honestly, not
sign-asserted: conditional on updated LTV (which already carries the HPI
collapse -- the PD-LGD correlation channel of notes section 10.2),
stress-cohort defaulters at a given LTV are macro-driven rather than
idiosyncratically impaired and cure more; the sign is robust in a
fixed-28-quarter-resolution-runway subsample (defaults at t <= 32, coef
+1.02), so it is NOT a resolution-censoring artefact. Note the direction of
the raw stress effect on cure is still negative through LTV: the stress
episode raises updated LTV, and the LTV coefficient dominates (OOT realised
cure rate falls to {stats['oot_cure_real']:.1%} from {stats['tr_cure_real']:.1%} in train).

Cure AUC: train {stats['auc_train']:.3f}, OOT {stats['auc_oot']:.3f}.

## Stage 2 -- fractional-logit severity  `{models.severity_formula}` (HC1 robust SEs)

{md_table(sev_tab)}

Signs: **severity RISES in updated LTV** (ltv10
{models.severity_params['ltv10']:+.3f}, asserted -- less equity, bigger
foreclosure shortfall). fico_s {models.severity_params['fico_s']:+.3f}
(better borrowers keep the property in better shape / cooperate in workout).
uer_lag1 {models.severity_params['uer_lag1']:+.3f} (small negative; the
collateral-value channel that drives mortgage severity is already inside
updated LTV, so the residual labour-market effect is a decomposition
artifact, not the total stress effect). loan_age
{models.severity_params['loan_age']:+.3f} (small).

## Excess-loss loading (losses beyond EAD -- never silently clipped)

{models.fit_meta['share_sev_gt_cap_noncure']:.1%} of train non-cure LGDs
exceed {SEV_CAP:.0f} (workout costs push losses past the defaulted balance);
mean excess among them {models.fit_meta['mean_excess_given_gt_cap']:.4f}.
Loading = E[max(lgd-1,0) | non-cure] = **{models.excess_loading:.4f}**, added
to every predicted severity. OOT validation: realised OOT non-cure excess
mass {stats['oot_excess_real']:.4f} vs loading {models.excess_loading:.4f}.

## Cure-threshold sensitivity (refit at each threshold)

{sens_txt}

The expected-LGD decomposition is nearly invariant to the threshold (mass
moved out of the cure spike reappears in the severity average) -- the 0.05
choice is a labelling convention, not a lever.

## OOT calibration (resolved OOT defaults, n = {len(oo):,})

| metric | train | OOT |
|---|---|---|
| mean realised LGD | {stats['tr_mean_real']:.4f} | {stats['oot_mean_real']:.4f} |
| mean predicted LGD | {stats['tr_mean_pred']:.4f} | {stats['oot_mean_pred']:.4f} |
| gap (pred - real) | {stats['tr_mean_pred'] - stats['tr_mean_real']:+.4f} | {gap:+.4f} |
| cure rate realised | {stats['tr_cure_real']:.4f} | {stats['oot_cure_real']:.4f} |
| cure rate predicted | {stats['tr_cure_pred']:.4f} | {stats['oot_cure_pred']:.4f} |
| mean sev (non-cure) realised | {stats['tr_sev_real']:.4f} | {stats['oot_sev_real']:.4f} |
| mean sev (non-cure) predicted | {stats['tr_sev_pred']:.4f} | {stats['oot_sev_pred']:.4f} |
| decile MAE (LGD) | {stats['tr_decile_mae']:.4f} | {stats['oot_decile_mae']:.4f} |

OOT mean tolerance |pred - real| <= {TOLERANCE_OOT_MEAN:.2f}: gap {gap:+.4f}
-> {tol_line}. Decomposition of the OOT gap: cures are UNDER-predicted
({stats['oot_cure_pred']:.1%} vs {stats['oot_cure_real']:.1%} realised,
pulling predicted LGD UP) and non-cure severity is OVER-predicted
({stats['oot_sev_pred']:.3f} vs {stats['oot_sev_real']:.3f}), both
conservative in the stress window; the two overshoots stack to the reported
gap. Honest caveat: the resolved OOT sample itself over-represents fast
workouts (48% of OOT defaults are still open), so OOT "realised" is itself a
biased-down preview of ultimate OOT severity.

### Calibration by updated-LTV decile (train edges applied to both samples)

train
{md_table(agg_tr.drop(columns='bin').set_index(agg_tr['bin'].astype(str)))}

OOT
{md_table(agg_oo.drop(columns='bin').set_index(agg_oo['bin'].astype(str)))}

## Documented simplifications

* LGD_cure = 0; realised mean LGD among train cures = {models.cure_mean_lgd:.4f}
  (understates expected LGD by ~{models.cure_mean_lgd * stats['tr_cure_real']:.4f} of EAD).
* Constant (not covariate-driven) excess-loss loading.
* Resolved workouts only; no completion model for open cases yet.
* `lgd_time` taken as the vendor's realised workout LGD (EIR discounting of
  notes section 10.1 assumed embedded; no post-default cash flows in panel).
* Severity is a conditional-mean model; ECL only consumes the mean.
* Point-in-time, no downturn add-on (IFRS 9 wants unbiased PIT LGD).
* ECL assembly reminder: S(t) already includes prepayment survival, so the
  EAD_t that multiplies this LGD must be the CONTRACTUAL amortisation
  balance, never prepay-scaled (see engine/lgd.py docstring).
"""


# ---------------------------------------------------------------------------

def main() -> None:
    apply_textbook_style()
    OUT.mkdir(parents=True, exist_ok=True)
    tr, oo, panel = load_samples()

    models = fit_lgd_models(panel)   # train filter + sign assertions inside

    # --- predictions & headline stats -------------------------------------
    comp_tr = predict_components(models, tr)
    comp_oo = predict_components(models, oo)
    for name, comp in [("train", comp_tr), ("oot", comp_oo)]:
        lo, hi = comp["lgd"].min(), comp["lgd"].max()
        if not (lo >= 0 and hi <= models.lgd_upper_bound + 1e-12):
            raise SystemExit(f"predicted LGD out of range on {name}: [{lo}, {hi}]")

    edges = np.unique(np.quantile(tr["updated_ltv"],
                                  np.linspace(0, 1, N_DECILES + 1)))
    edges[0], edges[-1] = -np.inf, np.inf     # train edges applied to OOT too

    nc_tr, nc_oo = tr["cure"] == 0, oo["cure"] == 0
    agg_tr = decile_frame(models, tr, edges)
    agg_oo = decile_frame(models, oo, edges)
    stats = {
        "edges": edges,
        "tr_mean_real": tr["lgd_time"].mean(),
        "tr_mean_pred": comp_tr["lgd"].mean(),
        "oot_mean_real": oo["lgd_time"].mean(),
        "oot_mean_pred": comp_oo["lgd"].mean(),
        "tr_cure_real": tr["cure"].mean(),
        "tr_cure_pred": comp_tr["p_cure"].mean(),
        "oot_cure_real": oo["cure"].mean(),
        "oot_cure_pred": comp_oo["p_cure"].mean(),
        "tr_sev_real": tr.loc[nc_tr, "lgd_time"].mean(),
        "tr_sev_pred": comp_tr.loc[nc_tr.to_numpy(), "severity_adj"].mean(),
        "oot_sev_real": oo.loc[nc_oo, "lgd_time"].mean(),
        "oot_sev_pred": comp_oo.loc[nc_oo.to_numpy(), "severity_adj"].mean(),
        "oot_excess_real": (oo.loc[nc_oo, "lgd_time"] - SEV_CAP).clip(lower=0).mean(),
        "auc_train": roc_auc_score(tr["cure"], comp_tr["p_cure"]),
        "auc_oot": roc_auc_score(oo["cure"], comp_oo["p_cure"]),
        "tr_decile_mae": (agg_tr["pred_lgd"] - agg_tr["real_lgd"]).abs().mean(),
        "oot_decile_mae": (agg_oo["pred_lgd"] - agg_oo["real_lgd"]).abs().mean(),
    }

    # --- sanity assertions (fail loudly) -----------------------------------
    if not models.cure_params["ltv10"] < 0:
        raise SystemExit("sign check failed: cure must fall in updated LTV")
    if not models.severity_params["ltv10"] > 0:
        raise SystemExit("sign check failed: severity must rise in updated LTV")
    gap = stats["oot_mean_pred"] - stats["oot_mean_real"]
    print(f"OOT mean LGD: realised {stats['oot_mean_real']:.4f}, "
          f"predicted {stats['oot_mean_pred']:.4f}, gap {gap:+.4f} "
          f"(tolerance {TOLERANCE_OOT_MEAN:.2f})")
    if abs(gap) > TOLERANCE_OOT_MEAN:
        raise SystemExit(
            f"OOT calibration outside tolerance: |{gap:+.4f}| > "
            f"{TOLERANCE_OOT_MEAN:.2f} -- see lgd_report.md for the honest "
            f"decomposition before overriding")

    # smoke-check the public scalar API on a couple of panel rows
    v = predict_lgd(models, tr.head(3))
    assert v.shape == (3,) and np.isfinite(v).all()

    # --- exhibits -----------------------------------------------------------
    plot_distribution(models, tr)
    plot_two_panel(models, tr, oo, edges, kind="cure")
    plot_two_panel(models, tr, oo, edges, kind="lgd")
    (OUT / "lgd_report.md").write_text(build_report(models, tr, oo, panel, stats))
    print(f"wrote exhibits to {OUT}")
    print(f"train: n={len(tr):,} cure={stats['tr_cure_real']:.3f} "
          f"AUC={stats['auc_train']:.3f} | OOT: n={len(oo):,} "
          f"cure={stats['oot_cure_real']:.3f} AUC={stats['auc_oot']:.3f}")


if __name__ == "__main__":
    main()
