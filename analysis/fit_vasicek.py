"""Recover the credit-cycle factor Z_t from the panel (Belkin Z-shift) and
emit the credit-cycle exhibit + calibration report.

Run:  cd <repo root> && uv run --no-sync python analysis/fit_vasicek.py

Method (notes section 8; engine/vasicek.py):
  1. Fit the frozen rung-1 default hazard (engine/hazard.py, READ-ONLY API)
     on the TRAINING split (t <= 40).
  2. For each panel quarter t = 1..60 compute, over the SAME at-risk rows:
       observed_t = mean(default_event)            -- the raw quarterly rate
       expected_t = mean(predicted hazard with the four MACRO regressors
                    frozen at their panel-period means)  -- the composition-
                    adjusted TTC anchor for that quarter's book
  3. Invert the Vasicek formula per quarter, Z_t = invert_z(observed_t,
     expected_t, rho), and calibrate rho so Var(Z_t) = 1 (Belkin).
  4. Exhibit: Z_t-implied portfolio PIT PD path vs the flat TTC anchor on
     REAL calendar quarters (t=1 ~ 2000Q2 ... t=60 ~ 2015Q1; anchoring
     empirically verified against FRED UNRATE, corr 0.9963), GFC shaded,
     damped hybrid (alpha = 0.5) overlaid; second panel: the Z_t path.

WHY COMPOSITION-ADJUSTED (the vintage caution recorded in the wiki): the DCR
book GROWS toward mid-panel -- raw portfolio default COUNTS (and even the raw
rate) mix the credit cycle with vintage composition (age mix, FICO/LTV mix).
Inverting observed-vs-expected RATES where the expectation reprices EACH
quarter's actual at-risk book under cycle-neutral macros nets composition out
of the numerator: what is left in Z_t is (approximately) the systematic
surprise. This is the loan-level generalisation of Belkin's grade-level
inversion -- the TTC anchor varies by quarter because the book does.

DOCUMENTED CHOICES / LIMITS (also in the report):
  * Macro covariates frozen at panel-period means = uer_lag1, uer_chg4_lag1,
    hpi_growth_lag1, gdp_lag1 (unweighted mean of the 60 quarterly national
    values, so row counts do not weight the "cycle-neutral" macro state).
  * Loan-STATE covariates stay actual -- including updated_ltv, which itself
    carries the cycle through HPI indexation. The main Z is therefore a
    conservative (damped) cycle read: part of the 2008-10 stress is already
    inside the anchor via collateral marks. A variant freezing updated_ltv at
    ORIGINATION LTV (pure-TTC collateral) is computed and reported; its Z
    swings wider and its calibrated rho is larger.
  * prepay_incentive also stays actual (loan-state exception per the frozen
    hazard's timing convention; only the DEFAULT hazard is used here).
  * The hazard is fit on train (t <= 40) and applied read-only to all 60
    quarters; OOT quarters test the recovery, they never touch the fit.
  * Early quarters are thin (283 at-risk loans at t = 1), so sampling noise
    inflates |Z_t| there; no smoothing is applied (documented, not hidden).
  * Identifying the finite-portfolio quarterly rate with PD_PIT is the ASRF
    infinite-granularity approximation.

Outputs (outputs/vasicek/):
  credit_cycle.png    THE exhibit: PIT PD path vs flat TTC anchor + hybrid;
                      recovered Z_t path below; GFC shaded; calendar axis
  z_path.csv          per-quarter table behind the exhibit
  vasicek_report.md   method, rho calibration vs conventions, anchor check,
                      composition story, variant comparison, limits

Sanity gates (SystemExit on failure, like analysis/fit_hazard.py):
  * Gauss-Hermite anchor error < 1e-6 at the calibrated (flat_ttc, rho);
  * PIT <-> Z round trip on the recovered path < 1e-9;
  * Var(Z) = 1 at the calibrated rho (solver tolerance);
  * the Z trough / PIT PD hump lands in calendar 2008-2010.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from mpl_style import COLORS, apply_textbook_style  # noqa: E402
from engine.hazard import fit_default_hazard, predict_hazard  # noqa: E402
from engine.vasicek import (  # noqa: E402
    RHO_BASEL_RESI,
    RHO_NOTES,
    anchor_check,
    calibrate_rho,
    hybrid_pd,
    invert_z,
    pit_pd,
)

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "vasicek"

#: the four MACRO regressors of the frozen hazard (its docstring's timing
#: convention); loan-state covariates are NOT in this list on purpose
MACRO_COLS = ["uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1", "gdp_lag1"]

#: calendar anchoring: quarter t <-> 2000Q2 + (t-1)  (verified vs FRED UNRATE)
T0 = pd.Period("2000Q2", freq="Q")

#: NBER GFC recession window for shading: 2007Q4 .. 2009Q2
GFC = (pd.Period("2007Q4", freq="Q"), pd.Period("2009Q2", freq="Q"))

ALPHA_HYBRID = 0.5   # damping for the hybrid overlay
HUMP_YEARS = (2008, 2009, 2010)   # the trough/hump must land here


def t_to_period(t) -> pd.PeriodIndex | pd.Period:
    """Panel quarter index -> real calendar quarter (t = 1 ~ 2000Q2)."""
    if np.ndim(t) == 0:
        return T0 + (int(t) - 1)
    return pd.PeriodIndex([T0 + (int(k) - 1) for k in np.asarray(t)],
                          freq="Q")


def _fail(msg: str) -> None:
    raise SystemExit(f"SANITY GATE FAILED: {msg}")


def quarterly_rates(panel: pd.DataFrame, model) -> pd.DataFrame:
    """Observed vs composition-adjusted expected TTC rate per quarter.

    Expected rates score EVERY at-risk row with the four macro regressors
    replaced by their panel-period means (constants), in two variants:
      expected_ttc       loan-state covariates actual (main)
      expected_ttc_oltv  updated_ltv additionally frozen at origination LTV
    """
    per_q = panel.groupby("time")[MACRO_COLS].first()   # national by quarter
    macro_means = per_q.mean()                          # unweighted over t

    score = panel.copy()
    for c in MACRO_COLS:
        score[c] = macro_means[c]
    lam_main = predict_hazard(model, score)
    score["updated_ltv"] = panel["LTV_orig_time"].to_numpy()
    lam_oltv = predict_hazard(model, score)
    if not (np.all(np.isfinite(lam_main)) and np.all(np.isfinite(lam_oltv))):
        _fail("non-finite TTC hazard predictions")

    by_t = panel["time"]
    tab = pd.DataFrame({
        "n_at_risk": panel.groupby("time").size(),
        "defaults": panel.groupby("time")["default_event"].sum().astype(int),
        "observed": panel.groupby("time")["default_event"].mean(),
        "expected_ttc": pd.Series(lam_main, index=panel.index)
                          .groupby(by_t).mean(),
        "expected_ttc_oltv": pd.Series(lam_oltv, index=panel.index)
                               .groupby(by_t).mean(),
    })
    tab.index.name = "time"
    tab["calendar"] = [str(p) for p in t_to_period(tab.index.to_numpy())]
    tab["macro_means_used"] = ", ".join(
        f"{c}={macro_means[c]:.4f}" for c in MACRO_COLS)
    return tab


def build_exhibit(tab: pd.DataFrame, res, flat_ttc: float,
                  z_oltv: np.ndarray, out_png: Path) -> dict:
    """Two-panel centerpiece: PIT PD path vs flat TTC + hybrid; Z_t below."""
    apply_textbook_style()
    periods = t_to_period(tab.index.to_numpy())
    x = periods.to_timestamp()

    pit_path = pit_pd(flat_ttc, res.z, res.rho) * 100.0
    hyb_path = hybrid_pd(flat_ttc, res.z, res.rho, alpha=ALPHA_HYBRID) * 100.0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(8.4, 5.8), sharex=True, height_ratios=[3, 2])
    gfc_span = (GFC[0].to_timestamp(), (GFC[1] + 1).to_timestamp())
    for ax in (ax1, ax2):
        ax.axvspan(*gfc_span, color="#d9d9d9", alpha=0.55, zorder=0, lw=0)

    # --- panel 1: portfolio PIT PD path vs the flat TTC anchor ------------
    ax1.plot(x, pit_path, color=COLORS["accent"], lw=1.9, zorder=4,
             label=f"PIT PD from recovered Z (rho={res.rho:.3f})")
    ax1.plot(x, hyb_path, color=COLORS["orange"], lw=1.7, ls="--", zorder=3,
             label=f"damped hybrid (alpha={ALPHA_HYBRID:g})")
    ax1.axhline(flat_ttc * 100.0, color=COLORS["gray"], lw=1.4, ls=":",
                zorder=2, label=f"flat TTC anchor {flat_ttc * 100:.2f}%")
    # selective direct labels (identity never color-alone)
    i_pk = int(np.argmax(pit_path))
    ax1.annotate(f"{periods[i_pk]}: {pit_path[i_pk]:.2f}%",
                 xy=(x[i_pk], pit_path[i_pk]),
                 xytext=(-72, 6), textcoords="offset points", fontsize=8,
                 color=COLORS["accent"],
                 arrowprops=dict(arrowstyle="-", color=COLORS["accent"],
                                 lw=0.7))
    ax1.plot([x[i_pk]], [pit_path[i_pk]], "o", ms=4.5,
             color=COLORS["accent"], zorder=5)
    ax1.text(x[36], flat_ttc * 100.0 - 0.09, "TTC anchor", fontsize=8,
             color=COLORS["gray"], ha="center", va="top")
    gfc_mid = gfc_span[0] + (gfc_span[1] - gfc_span[0]) / 2
    ax2.text(gfc_mid, 0.97, "GFC", fontsize=8, color="#666666",
             ha="center", va="top",
             transform=ax2.get_xaxis_transform())
    ax1.set_ylabel("quarterly default rate (%)")
    ax1.set_title(
        "The credit cycle through the Vasicek lens - portfolio PIT PD vs "
        "TTC anchor\n(composition-adjusted Belkin Z recovery on the 50k-loan "
        "mortgage panel)", fontsize=10)
    ax1.legend(loc="upper left", frameon=False)

    # --- panel 2: the recovered Z_t path itself ---------------------------
    ax2.plot(x, res.z, color=COLORS["purple"], lw=1.8, zorder=4,
             label="recovered Z_t (main: composition-adjusted)")
    ax2.plot(x, z_oltv, color=COLORS["gray"], lw=1.2, ls="--", zorder=3,
             label="variant: updated_ltv frozen at origination")
    ax2.axhline(0.0, color="#999999", lw=0.9, zorder=1)
    i_tr = int(np.argmin(res.z))
    ax2.annotate(f"trough {periods[i_tr]}: Z={res.z[i_tr]:.2f}",
                 xy=(x[i_tr], res.z[i_tr]),
                 xytext=(8, -2), textcoords="offset points",
                 fontsize=8, color=COLORS["purple"])
    ax2.plot([x[i_tr]], [res.z[i_tr]], "o", ms=4.5, color=COLORS["purple"],
             zorder=5)
    ax2.set_ylabel("Z (std. normal)")
    ax2.set_xlabel("calendar quarter (t=1 anchored to 2000Q2, verified vs "
                   "FRED UNRATE)")
    ax2.legend(loc="upper right", frameon=False, fontsize=7.5)

    # calendar ticks every 8 quarters
    ticks = periods[::8]
    ax2.set_xticks(ticks.to_timestamp())
    ax2.set_xticklabels([str(p) for p in ticks])
    fig.align_ylabels((ax1, ax2))
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)
    return {"peak_idx": i_pk, "trough_idx": i_tr,
            "pit_path_pct": pit_path, "hybrid_path_pct": hyb_path}


def write_report(path: Path, tab: pd.DataFrame, res, res_oltv,
                 flat_ttc: float, anchor_err: float, roundtrip_err: float,
                 exhibit: dict, model) -> None:
    periods = t_to_period(tab.index.to_numpy())
    i_pk, i_tr = exhibit["peak_idx"], exhibit["trough_idx"]
    calm = tab["macro_means_used"].iloc[0]
    lines = [
        "# Vasicek / Belkin Z conditioning - calibration report",
        "",
        "## Method (notes section 8; engine/vasicek.py)",
        "",
        "One-factor conditioning `PD_PIT(Z) = Phi((Phi^-1(PD_TTC) - "
        "sqrt(rho) Z)/sqrt(1-rho))`; per-quarter inversion "
        "`Z_t = invert_z(observed_t, expected_t, rho)`; rho calibrated so "
        "`Var(Z_t) = 1` (Belkin), sample variance (ddof=1) over all 60 "
        "panel quarters, 2000Q2..2015Q1.",
        "",
        "**Composition adjustment (the vintage caution).** The book grows "
        "toward mid-panel, so raw default COUNTS (and the raw rate) mix "
        "vintage composition with the cycle. The TTC anchor is therefore "
        "recomputed EVERY quarter as the mean predicted hazard of that "
        "quarter's actual at-risk rows under cycle-neutral macros - the "
        "frozen rung-1 default hazard (fit on train, t<=40, applied "
        "read-only to all 60 quarters) scored with the four macro "
        "regressors held at panel-period means:",
        "",
        f"    {calm}",
        "",
        "Loan-state covariates (age, FICO, updated_ltv, prepay_incentive, "
        "occupancy/property flags) stay ACTUAL, so the anchor reprices the "
        "live book, not a synthetic one. Observed-vs-expected then isolates "
        "the systematic surprise.",
        "",
        "## Calibration",
        "",
        "| quantity | main | variant (orig-LTV) |",
        "|---|---|---|",
        f"| calibrated rho (Var(Z)=1) | **{res.rho:.4f}** | "
        f"{res_oltv.rho:.4f} |",
        f"| mean(Z_t) | {res.mean_z:+.3f} | {res_oltv.mean_z:+.3f} |",
        f"| Var(Z_t) (ddof=1) | {res.var_z:.6f} | {res_oltv.var_z:.6f} |",
        f"| quarters used | {res.n_periods} | {res_oltv.n_periods} |",
        f"| Z trough | {periods[int(np.argmin(res.z))]} "
        f"(Z={res.z.min():.2f}) | {periods[int(np.argmin(res_oltv.z))]} "
        f"(Z={res_oltv.z.min():.2f}) |",
        "",
        f"**rho vs conventions:** calibrated rho = {res.rho:.4f} sits well "
        f"below both the notes' worked-example convention rho = "
        f"{RHO_NOTES:.2f} and the Basel IRB residential-mortgage supervisory "
        f"value rho = {RHO_BASEL_RESI:.2f} (CRE31.10). That ordering is the "
        "expected one: empirical asset correlations estimated from default-"
        "rate time series are routinely a fraction of the regulatory "
        "convention (the Basel figures are calibrated to capital "
        "conservatism, not to time-series fit), and composition-adjusting "
        "the anchor absorbs part of the systematic variance into the "
        "quarter-specific TTC rate, damping Z further. The orig-LTV variant "
        f"(rho = {res_oltv.rho:.4f}) shows exactly this mechanism in "
        "reverse: freezing collateral at origination pushes the HPI cycle "
        "OUT of the anchor and INTO Z, so the recovered factor swings "
        "wider and needs a larger rho to standardise.",
        "",
        "## Anchor + round-trip checks",
        "",
        f"* Gauss-Hermite anchor `E_Z[PD_PIT] = PD_TTC` at (flat TTC = "
        f"{flat_ttc:.6f}, rho = {res.rho:.4f}): |error| = {anchor_err:.2e} "
        "( < 1e-6 gate; the golden fixture pins the same identity at "
        "(2%, 0.12) ).",
        f"* PIT <-> Z round trip on the recovered path: max |error| = "
        f"{roundtrip_err:.2e} ( < 1e-9 gate; fixed-conventions answer to "
        "the Basson & van Vuuren caveat).",
        f"* Hump timing: PIT PD peaks {periods[i_pk]} "
        f"({exhibit['pit_path_pct'][i_pk]:.2f}% quarterly vs "
        f"{flat_ttc * 100:.2f}% anchor), Z troughs {periods[i_tr]} - inside "
        "the required 2008-10 window, i.e. the recovered cycle lands the "
        "GFC where history put it.",
        "",
        "## Exhibit",
        "",
        "`credit_cycle.png`: top panel shows the Z-implied portfolio PIT PD "
        f"path `pit_pd(flat_ttc, Z_t, rho)` against the flat TTC anchor "
        f"({flat_ttc * 100:.2f}%, the unweighted mean of the 60 "
        "composition-adjusted quarterly anchors) with the damped hybrid "
        f"(alpha = {ALPHA_HYBRID:g}, Z scaled by alpha - the Aguais/Forest "
        "PIT-ness dial; note alpha < 1 is Jensen-biased slightly below the "
        "anchor on average, a presentation device, not an ECL input). "
        "Bottom panel: the recovered Z_t itself, with the orig-LTV variant "
        "dashed. GFC (NBER 2007Q4-2009Q2) shaded. Calendar axis anchored "
        "t=1 ~ 2000Q2 (verified vs FRED UNRATE, corr 0.9963).",
        "",
        "## Limits (documented, not hidden)",
        "",
        "* **updated_ltv carries the cycle** (HPI indexation), so the main "
        "anchor is only approximately TTC: part of the 2008-10 stress is "
        "absorbed into collateral marks, making the main Z a conservative "
        "(damped) cycle read. The orig-LTV variant brackets the effect "
        "from the other side (pure-TTC collateral, but then the anchor "
        "ignores genuine amortisation and equity build-up). Truth lies "
        "between; both are reported.",
        "* prepay_incentive stays actual in both variants (loan-state "
        "exception per the frozen hazard's timing convention; it prices "
        "the borrower's option, and only the DEFAULT hazard is used here).",
        "* Macro means are unweighted over the 60 quarters - a panel-period "
        "average, not a true long-run TTC macro state (the window is one "
        "cycle plus a boom tail).",
        f"* **mean(Z) = {res.mean_z:+.3f} is NOT forced to zero** (Belkin "
        "calibrates the VARIANCE only, and sample variance is mean-"
        "invariant). The negative mean is a LEVEL gap - observed rates "
        f"average {100 * float(tab['observed'].mean()):.2f}% vs "
        f"{flat_ttc * 100:.2f}% for the frozen-macro anchor - with three "
        "identifiable causes: (i) Jensen/convexity of the cloglog inverse "
        "link: the hazard AT mean macros is below the macro-AVERAGED "
        "hazard, so freezing macros at means biases the anchor low; "
        "(ii) a small structural inversion offset (even obs == anchor "
        "maps to Z < 0 because sqrt(1-rho) < 1); (iii) OOT calibration "
        "drift plus adverse survivor selection - post-2010 at-risk loans "
        "are the ones that could not refinance, and they default above "
        "the anchor even in recovery, holding Z near -1.7 through 2013. "
        "The CYCLE read is the SHAPE (trough in the GFC, monotone climb "
        "after 2010); the satellite model (next rung) regresses Z_t "
        "as-is, so the level piece is absorbed by its intercept.",
        "* Early quarters are thin (283 at-risk loans at t=1), inflating "
        "|Z_t| noise there; no smoothing applied.",
        "* Identifying the finite-portfolio quarterly rate with PD_PIT is "
        "the ASRF infinite-granularity approximation.",
        "",
        "## Model provenance",
        "",
        f"* Default hazard: engine/hazard.py (FROZEN), fit on train rows, "
        f"n_obs = {model.n_obs:,}, events = {model.n_events:,}; scored "
        "read-only over all 621,736 panel rows per variant.",
        "* Data behind the exhibit: `z_path.csv` (per-quarter n, defaults, "
        "observed rate, both anchors, both Z paths, PIT/hybrid paths).",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]
    print(f"panel rows {len(panel):,}; fitting frozen default hazard on "
          f"{len(train):,} train rows ...")
    model = fit_default_hazard(train)

    tab = quarterly_rates(panel, model)
    print(tab[["calendar", "n_at_risk", "defaults", "observed",
               "expected_ttc"]].head(3).to_string())

    res = calibrate_rho(tab["observed"], tab["expected_ttc"])
    res_oltv = calibrate_rho(tab["observed"], tab["expected_ttc_oltv"])
    print(f"calibrated rho: main={res.rho:.4f}  orig-LTV variant="
          f"{res_oltv.rho:.4f}  (notes {RHO_NOTES}, Basel resi "
          f"{RHO_BASEL_RESI})")
    print(f"mean(Z): main={res.mean_z:+.3f}  variant={res_oltv.mean_z:+.3f}")

    # ---- sanity gates ------------------------------------------------------
    if abs(res.var_z - 1.0) > 1e-8:
        _fail(f"Var(Z) != 1 after calibration: {res.var_z}")
    flat_ttc = float(tab["expected_ttc"].mean())
    _, anchor_err = anchor_check(flat_ttc, res.rho)
    if anchor_err >= 1e-6:
        _fail(f"Gauss-Hermite anchor error {anchor_err:.2e} >= 1e-6")
    z_back = invert_z(
        pit_pd(tab["expected_ttc"].to_numpy(), res.z, res.rho),
        tab["expected_ttc"].to_numpy(), res.rho)
    roundtrip_err = float(np.max(np.abs(z_back - res.z)))
    if roundtrip_err >= 1e-9:
        _fail(f"PIT<->Z round trip error {roundtrip_err:.2e} >= 1e-9")

    exhibit = build_exhibit(tab, res, flat_ttc, res_oltv.z,
                            OUT / "credit_cycle.png")
    periods = t_to_period(tab.index.to_numpy())
    trough_year = periods[exhibit["trough_idx"]].year
    peak_year = periods[exhibit["peak_idx"]].year
    if trough_year not in HUMP_YEARS or peak_year not in HUMP_YEARS:
        _fail(f"2008-10 hump misplaced: Z trough {periods[exhibit['trough_idx']]}, "
              f"PIT peak {periods[exhibit['peak_idx']]}")

    out_tab = tab.drop(columns=["macro_means_used"]).copy()
    out_tab["z_main"] = res.z
    out_tab["z_orig_ltv"] = res_oltv.z
    out_tab["pit_pd_flat_anchor"] = exhibit["pit_path_pct"] / 100.0
    out_tab["hybrid_pd_alpha05"] = exhibit["hybrid_path_pct"] / 100.0
    out_tab.to_csv(OUT / "z_path.csv", float_format="%.8f")

    write_report(OUT / "vasicek_report.md", tab, res, res_oltv, flat_ttc,
                 anchor_err, roundtrip_err, exhibit, model)
    print(f"wrote {OUT / 'credit_cycle.png'}, {OUT / 'z_path.csv'}, "
          f"{OUT / 'vasicek_report.md'}")
    print(f"PIT peak {periods[exhibit['peak_idx']]} "
          f"({exhibit['pit_path_pct'][exhibit['peak_idx']]:.2f}%), "
          f"Z trough {periods[exhibit['trough_idx']]} "
          f"(Z={res.z.min():.2f}) - all sanity gates passed")


if __name__ == "__main__":
    main()
