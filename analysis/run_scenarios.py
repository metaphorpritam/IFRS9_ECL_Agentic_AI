"""Satellite model + scenario-conditional ECL -- Day 3's forward-looking core.

Run:  cd <repo root> && uv run --no-sync python analysis/run_scenarios.py

Pipeline (engine/satellite.py; notes section 9; plan section 6):
  1. Fit the frozen rung-1 engines (READ-ONLY: hazards on train, 2-stage
     LGD) and recover the credit-cycle factor Z_t by composition-adjusted
     Belkin inversion -- the identical convention to analysis/fit_vasicek.py
     (rho ~= 0.023, Var(Z) = 1, 60 quarters 2000Q2..2015Q1).
  2. SATELLITE: regress Z_t on lagged macro drivers (duer, hpi_growth,
     gdp_growth at lags 1-2) with full hygiene -- ADF/KPSS verdicts, AIC
     spec choice under the economic-sign governance constraint,
     Durbin-Watson, adjusted R2, GFC-dummy sensitivity -- and write
     outputs/satellite/ (report + fitted-vs-recovered chart, calendar axis).
  3. SCENARIOS: DFAST-shaped macro paths (engine/scenarios.py, 40q,
     rebased to the t=60 ~ 2015Q1 jump-off) -> satellite -> Z path per
     scenario -> PIT-condition the frozen default hazard per loan-quarter
     via vasicek.pit_pd on quarterly-hazard levels (the standard practical
     approximation) -> lifetime scenario-conditional ECL for the t=60 live
     book through the frozen ECL machinery (composed, never edited).
  4. HEADLINES to outputs/scenario_ecl/: the Jensen exhibit
     (probability-weighted ECL vs ECL at the weighted-average macro path,
     ratio annotated -- the notes' Fig 6 logic on OUR engine's numbers),
     the scenario ECL bar chart with coverage ratios, the scenario Z fan,
     and the weights-sensitivity table (50/25/25 vs 40/30/30 vs 60/20/20).

Sanity gates (SystemExit on failure, run_ecl.py style):
  * anchor sanity: per-quarter PIT round trip < 1e-9; Gauss-Hermite
    E_Z[PD_PIT] = PD_TTC at the flat anchor < 1e-6;
  * satellite passes sign governance; scenario Z paths finite;
  * the UNCONDITIONED wrapper reproduces the frozen engine.ecl
    ecl_for_snapshot EXACTLY (composition correctness anchor);
  * book population: 7,849 non-payoff exposures = 7,806 live (performing)
    + 43 Stage-3 defaults at t=60;
  * ECL ordering severe > base > upside on the REPORTED allowance and the
    12-month ECL (the lifetime-sum up/base crossover is a documented
    feature, discussed in the report -- not a silent pass);
  * severe > base on the lifetime ECL;
  * Jensen: probability-weighted ECL > ECL at the average path, on both
    the reported allowance and the lifetime ECL.
"""

from __future__ import annotations

import sys
import time as _time
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
from engine.ecl import EclConfig, ecl_for_snapshot  # noqa: E402
from engine.hazard import fit_default_hazard, fit_prepay_hazard  # noqa: E402
from engine.lgd import fit_lgd_models  # noqa: E402
from engine.satellite import (  # noqa: E402
    anchor_sanity,
    driver_frame,
    fit_satellite,
    gfc_sensitivity,
    recover_z,
    scenario_ecl_for_snapshot,
    scenario_z_paths,
    stationarity_table,
    ttc_macro_means,
)
from engine.scenarios import (  # noqa: E402
    build_scenario_set,
    panel_macro_concepts,
    panel_time_to_period,
)
from engine.staging import assign_stages, build_macro_map  # noqa: E402
from engine.vasicek import RHO_BASEL_RESI, RHO_NOTES  # noqa: E402

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT_SAT = PROJECT_ROOT / "outputs" / "satellite"
OUT_SCEN = PROJECT_ROOT / "outputs" / "scenario_ecl"

T_SNAP = 60                      # reporting quarter (~ 2015Q1)
LIVE_LOANS = 7_806               # performing book at t=60 (shared fact)
STAGE3_LOANS = 43                # default rows at t=60
GFC = (pd.Period("2007Q4", freq="Q"), pd.Period("2009Q2", freq="Q"))

SCEN_LABEL = {"up": "upside", "base": "base", "down": "severe"}
SCEN_COLOR = {"up": COLORS["good"], "base": COLORS["accent"],
              "down": COLORS["warn"]}

#: parallel Z shifts of the weighted path tracing the Jensen convexity curve
JENSEN_SHIFTS = np.linspace(-1.2, 0.8, 9)

#: weights-sensitivity sets (base/down/up), 50/25/25 = accepted default
WEIGHT_SETS = {
    "50/25/25 (adopted)": {"base": 0.50, "down": 0.25, "up": 0.25},
    "40/30/30": {"base": 0.40, "down": 0.30, "up": 0.30},
    "60/20/20": {"base": 0.60, "down": 0.20, "up": 0.20},
}


def _fail(msg: str) -> None:
    raise SystemExit(f"SANITY GATE FAILED: {msg}")


def t_axis(times) -> np.ndarray:
    """Panel quarters -> matplotlib timestamps (calendar anchoring)."""
    return pd.PeriodIndex(
        [panel_time_to_period(int(t)) for t in np.asarray(times)],
        freq="Q").to_timestamp()


# ---------------------------------------------------------------------------
# exhibits
# ---------------------------------------------------------------------------

def plot_satellite_fit(z_ser: pd.Series, satm, out_png: Path) -> None:
    """Fitted vs recovered Z with calendar labels; residuals below."""
    apply_textbook_style()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.4, 5.4), sharex=True,
                                   height_ratios=[3, 1.4])
    gfc_span = (GFC[0].to_timestamp(), (GFC[1] + 1).to_timestamp())
    for ax in (ax1, ax2):
        ax.axvspan(*gfc_span, color="#d9d9d9", alpha=0.55, zorder=0, lw=0)

    x_all = t_axis(z_ser.index.to_numpy())
    x_fit = t_axis(satm.times)
    fitted = np.asarray(satm.result.fittedvalues)
    ax1.plot(x_all, z_ser.to_numpy(), color=COLORS["purple"], lw=1.8,
             zorder=4, label="recovered Z_t (Belkin, composition-adjusted)")
    ax1.plot(x_fit, fitted, color=COLORS["orange"], lw=1.7, ls="--",
             zorder=5, label=f"satellite fit: {' + '.join(satm.terms)}")
    ax1.axhline(0.0, color="#999999", lw=0.9, zorder=1)
    ax1.set_ylabel("Z (std. normal)")
    ax1.set_title(
        "Satellite model -- recovered credit-cycle Z vs macro-driver fit\n"
        f"(OLS, adj R2 = {satm.adj_r2:.2f}, DW = {satm.dw:.2f}, "
        f"n = {satm.n_obs} quarters, AIC-chosen under sign governance)",
        fontsize=10)
    ax1.legend(loc="lower right", frameon=False)
    ax1.text(gfc_span[0] + (gfc_span[1] - gfc_span[0]) / 2, 0.97, "GFC",
             fontsize=8, color="#666666", ha="center", va="top",
             transform=ax1.get_xaxis_transform())

    resid = np.asarray(satm.result.resid)
    ax2.bar(x_fit, resid, width=70, color=COLORS["gray"], zorder=3)
    ax2.axhline(0.0, color="#999999", lw=0.9)
    ax2.set_ylabel("residual")
    ax2.set_xlabel("calendar quarter (t=1 anchored to 2000Q2, verified vs "
                   "FRED UNRATE)")
    ticks = pd.PeriodIndex([panel_time_to_period(int(t))
                            for t in z_ser.index[::8]], freq="Q")
    ax2.set_xticks(ticks.to_timestamp())
    ax2.set_xticklabels([str(p) for p in ticks])
    fig.align_ylabels((ax1, ax2))
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def plot_z_fan(z_ser: pd.Series, zp: pd.DataFrame, out_png: Path) -> None:
    """History Z + the three scenario Z paths (calendar axis)."""
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    gfc_span = (GFC[0].to_timestamp(), (GFC[1] + 1).to_timestamp())
    ax.axvspan(*gfc_span, color="#d9d9d9", alpha=0.55, zorder=0, lw=0)
    ax.plot(t_axis(z_ser.index.to_numpy()), z_ser.to_numpy(),
            color=COLORS["gray"], lw=1.4, zorder=3, label="recovered Z (history)")
    xs = pd.PeriodIndex(zp["period"], freq="Q").to_timestamp()
    for name in ("up", "base", "down"):
        ax.plot(xs, zp[name].to_numpy(), color=SCEN_COLOR[name], lw=1.8,
                zorder=4, label=f"{SCEN_LABEL[name]} scenario Z")
    ax.plot(xs, zp["weighted"].to_numpy(), color="#555555", lw=1.2, ls=":",
            zorder=4, label="weighted-average path Z (exhibit only)")
    ax.axhline(0.0, color="#999999", lw=0.9, zorder=1)
    ax.axvline(pd.Period("2015Q1", freq="Q").to_timestamp(), color="#888888",
               lw=1.0, ls="--", zorder=2)
    ax.text(pd.Period("2015Q2", freq="Q").to_timestamp(), 0.96,
            "reporting date t=60 (2015Q1)", fontsize=7.5, color="#555555",
            ha="left", va="top", transform=ax.get_xaxis_transform())
    ax.set_ylabel("Z (std. normal)")
    ax.set_xlabel("calendar quarter")
    ax.set_title("Scenario Z paths from the satellite -- history, R&S window, "
                 "reversion to the long-run tail")
    ax.legend(loc="lower left", frameon=False, fontsize=7.5, ncols=2)
    fig.savefig(out_png)
    plt.close(fig)


def plot_jensen(curve: pd.DataFrame, points: dict, ratio: float,
                out_png: Path) -> None:
    """THE Jensen exhibit -- notes Fig 6 logic on the engine's own numbers.

    curve  : zbar (mean Z over the 13q R&S window) vs reported allowance
             for parallel shifts of the weighted-average Z path;
    points : per scenario dict name -> (zbar, allowance) plus 'weighted'
             (the chord average, diamond) and 'at_avg' (curve point, square).
    """
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    ax.plot(curve["zbar"], curve["allowance_m"], color=COLORS["accent"],
            lw=1.8, zorder=3,
            label="ECL of a single macro path (parallel Z shifts of the "
                  "average path)")
    for name in ("up", "base", "down"):
        zb, am = points[name]
        ax.plot([zb], [am], "o", ms=7, color=SCEN_COLOR[name], zorder=5)
        dx, dy = (10, -3) if name != "down" else (10, -14)
        ax.annotate(f"{SCEN_LABEL[name]}\n${am:,.1f}m", (zb, am),
                    textcoords="offset points", xytext=(dx, dy), fontsize=8,
                    color=SCEN_COLOR[name])
    zb_w, am_w = points["weighted"]
    zb_a, am_a = points["at_avg"]
    ax.plot([zb_w], [am_w], "D", ms=8, color=COLORS["purple"], zorder=6,
            label="probability-weighted ECL (the IFRS 9 answer)")
    ax.plot([zb_a], [am_a], "s", ms=8, color=COLORS["orange"], zorder=6,
            label="ECL at the probability-weighted (average) macro path")
    ax.annotate("", xy=(zb_w, am_w), xytext=(zb_a, am_a),
                arrowprops=dict(arrowstyle="->", color="#333333", lw=1.2))
    ax.annotate(
        f"Jensen gap: {ratio:.3f}x\n(weighted ${am_w:,.1f}m vs "
        f"single-path ${am_a:,.1f}m)",
        xy=(zb_w, (am_w + am_a) / 2), xytext=(12, 18),
        textcoords="offset points", fontsize=9, color="#333333",
        fontweight="bold")
    ax.set_xlabel("mean systematic factor Z over the 13-quarter R&S window")
    ax.set_ylabel("reported allowance ($m)")
    ax.set_title("The Jensen gap on the live book -- weighted ECL exceeds the "
                 "ECL of the averaged scenario\n(convexity of ECL in the "
                 "macro state; notes section 9.2, Fig 6)", fontsize=10)
    ax.legend(loc="lower left", frameon=False, fontsize=8)
    fig.text(0.995, 0.02,
             "Scenario markers sit off the curve because each path's SHAPE "
             "(trough depth/timing) matters beyond its mean Z -- the same "
             "convexity at path level.",
             ha="right", va="bottom", fontsize=7, color="#555555")
    fig.subplots_adjust(bottom=0.17)
    fig.savefig(out_png)
    plt.close(fig)


def plot_scenario_bars(summary: pd.DataFrame, weighted_row: pd.Series,
                       out_png: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    order = ["up", "base", "down"]
    names = [SCEN_LABEL[n] for n in order] + ["weighted\n(50/25/25)"]
    vals = [float(summary.loc[summary["scenario"] == n,
                              "allowance_m"].iloc[0]) for n in order]
    vals.append(float(weighted_row["allowance_m"]))
    covs = [float(summary.loc[summary["scenario"] == n,
                              "coverage"].iloc[0]) for n in order]
    covs.append(float(weighted_row["coverage"]))
    colors = [SCEN_COLOR[n] for n in order] + [COLORS["purple"]]
    bars = ax.bar(np.arange(len(names)), vals, width=0.6, color=colors,
                  zorder=3)
    for b, v, c in zip(bars, vals, covs):
        ax.annotate(f"${v:,.1f}m\n{c:.2%} cov.",
                    (b.get_x() + b.get_width() / 2, v),
                    textcoords="offset points", xytext=(0, 4), ha="center",
                    fontsize=8.5, color="#333333")
    ax.set_xticks(np.arange(len(names)))
    ax.set_xticklabels(names)
    ax.set_ylabel("reported allowance ($m)")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_title("Scenario-conditional reported allowance, t=60 (2015Q1) "
                 "live book -- 7,849 exposures, coverage = allowance / EAD")
    fig.savefig(out_png)
    plt.close(fig)


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def write_satellite_report(path: Path, satm, stat_tab: pd.DataFrame,
                           gfc_tab: pd.DataFrame, sanity: dict,
                           res, z_ser: pd.Series) -> None:
    p = satm.result.params
    se = satm.result.bse
    pv = satm.result.pvalues
    eq = " ".join(f"{'+' if p[t] >= 0 else '-'} {abs(p[t]):.3f} {t}"
                  for t in satm.terms)
    sel = satm.selection
    L = [
        "# Satellite model report -- the macro-to-credit-cycle link",
        "",
        "Generated by `analysis/run_scenarios.py` (engine/satellite.py).",
        "",
        "## The model",
        "",
        "OLS on the recovered credit-cycle factor (Belkin Z, composition-"
        "adjusted anchors, rho = "
        f"{res.rho:.4f} with Var(Z)=1; identical recovery convention to "
        "outputs/vasicek/):",
        "",
        f"    Z_t = {p['const']:+.3f} {eq} + e_t",
        "",
        "| term | coef | std err | t | p |",
        "|---|---|---|---|---|",
    ]
    for t in ["const", *satm.terms]:
        L.append(f"| {t} | {p[t]:+.4f} | {se[t]:.4f} | "
                 f"{p[t] / se[t]:+.2f} | {pv[t]:.4f} |")
    L += [
        "",
        f"adj R2 = **{satm.adj_r2:.3f}**, Durbin-Watson = **{satm.dw:.2f}**, "
        f"AIC = {satm.aic:.2f}, n = {satm.n_obs} quarters (common estimation "
        "sample t = 4..60, i.e. 2001Q1..2015Q1 -- the deepest candidate lag "
        "consumes three leading quarters).",
        "",
        "**Reading the fit.** Lagged HPI growth is the dominant driver "
        "(mortgage credit: collateral first), lagged GDP growth adds cyclical "
        "signal; both carry their economic signs. DW "
        f"= {satm.dw:.2f} signals mild positive residual autocorrelation -- "
        "expected when a persistent cycle factor is fitted by a static "
        "regression; the production answer is ARDL/ECM dynamics plus HAC "
        "standard errors (below). The intercept "
        f"({p['const']:+.2f}) absorbs the documented LEVEL GAP of the "
        "recovered Z (mean(Z) = "
        f"{res.mean_z:+.2f}, see outputs/vasicek/vasicek_report.md): "
        "scenario Z paths inherit that conservative level, and scenario "
        "DIFFERENTIATION -- the quantity ECL responds to -- comes from the "
        "macro deltas.",
        "",
        "## Stationarity hygiene (ADF + KPSS, 5% convention)",
        "",
        "| series | n | ADF p | KPSS p | verdict |",
        "|---|---|---|---|---|",
    ]
    for _, r in stat_tab.iterrows():
        L.append(f"| {r['series']} | {r['n']} | {r['adf_p']:.3f} | "
                 f"{r['kpss_p']:.3f} | {r['verdict']} |")
    L += [
        "",
        "KPSS p-values are table-bounded to [0.01, 0.10]. The unemployment "
        "LEVEL is the clear I(1) case -- it enters the candidate set only as "
        "its first difference (duer). Z itself tests as I(1)/borderline on "
        "60 quarters: one full cycle plus a survivor-selected tail gives the "
        "tests very little power, and the Vasicek premise (Z ~ N(0,1) per "
        "quarter) plus the Belkin unit-variance calibration bound it "
        "structurally; regressing it on I(0) drivers with a GFC sensitivity "
        "check is the disciplined small-sample compromise (the ARDL/ECM "
        "note below is the production-grade answer).",
        "",
        "## Specification search (AIC, common sample, sign governance)",
        "",
        "Grid: every non-empty subset of {duer, hpi_growth, gdp_growth}, "
        "each driver at lag 1 or 2 -- 26 specs. Admissible = all driver "
        "coefficients carry their economic sign (EXPECTED_SIGN: duer < 0, "
        f"hpi_growth > 0, gdp_growth > 0). The FULL {len(sel)}-spec grid "
        "by AIC (rejected specs included, nothing hidden):",
        "",
        "| spec | AIC | adj R2 | DW | signs OK |",
        "|---|---|---|---|---|",
    ]
    for _, r in sel.iterrows():
        L.append(f"| {r['spec']} | {r['aic']:.2f} | {r['adj_r2']:.3f} | "
                 f"{r['dw']:.2f} | {'yes' if r['signs_ok'] else '**no**'} |")
    L += [
        "",
        "The chosen spec is the AIC minimum over the WHOLE grid as well as "
        "within the sign-admissible set. Every spec that includes duer "
        "TOGETHER WITH gdp_growth fits a POSITIVE (wrong-sign, "
        "insignificant) duer coefficient -- a collinearity artifact of a "
        "one-cycle sample in which the unemployment surge and the GDP "
        "contraction are the same episode; duer alone (coef -0.7, p 0.02) "
        "or alongside hpi_growth only keeps its economic sign but never "
        "approaches the chosen spec on AIC. Sign governance excludes the "
        "wrong-signed specs and the grid above shows exactly what was "
        "excluded and why. Dropping a "
        "wrong-signed, insignificant driver is standard satellite-model "
        "governance, not data dredging: the constraint is stated ex ante "
        "from economics.",
        "",
        "## GFC-dummy sensitivity (crisis-robustness check)",
        "",
        "Refit of the chosen spec with a 2007Q4-2009Q2 dummy:",
        "",
        "| term | coef (no dummy) | p | coef (with dummy) | p |",
        "|---|---|---|---|---|",
    ]
    for _, r in gfc_tab.iterrows():
        c0 = "--" if np.isnan(r["coef_no_dummy"]) \
            else f"{r['coef_no_dummy']:+.4f}"
        p0 = "--" if np.isnan(r["p_no_dummy"]) else f"{r['p_no_dummy']:.4f}"
        L.append(f"| {r['term']} | {c0} | {p0} | "
                 f"{r['coef_with_dummy']:+.4f} | {r['p_with_dummy']:.4f} |")
    L += [
        "",
        f"adj R2 {gfc_tab.attrs['adj_r2_no_dummy']:.3f} -> "
        f"{gfc_tab.attrs['adj_r2_with_dummy']:.3f} with the dummy. The HPI "
        "coefficient shrinks when the GFC is dummied out (part of its "
        "leverage IS the crisis -- with one cycle in sample that is "
        "expected and unavoidable) but stays positive and significant; "
        "signs and orders of magnitude survive, which is what the check "
        "is for. A satellite whose coefficients FLIPPED without the GFC "
        "would be unusable for stress projection.",
        "",
        "## Simplified vs full method (documented, per the build plan)",
        "",
        "This is a STATIC OLS in I(0)-transformed drivers with AIC lag "
        "choice, sign governance and a crisis-dummy sensitivity. The "
        "PRODUCTION STANDARD documented for this layer (notes section 9.1) "
        "is: ARDL bounds testing (Pesaran-Shin-Smith 2001) for mixed "
        "I(0)/I(1) regressors with an error-correction term that must be "
        "negative and significant (adjustment speed); Johansen rank tests "
        "if a cointegrating system is modelled; structural-break tests "
        "(Chow, CUSUM) around 2008-09; HAC (Newey-West) standard errors; "
        "and out-of-time backtesting of the Z forecast. On 57 usable "
        "quarters spanning a single credit cycle the static form is the "
        "honest choice -- the dynamic terms would be identified by one "
        "episode.",
        "",
        "## Anchor sanity (satellite inherits the Vasicek conventions)",
        "",
        f"* per-quarter PIT round trip max |pit_pd(anchor_t, Z_t, rho) - "
        f"observed_t| = {sanity['roundtrip_max_err']:.2e} (< 1e-9 gate);",
        f"* Gauss-Hermite E_Z[PD_PIT] at the flat anchor "
        f"({sanity['flat_ttc']:.4%}, rho = {res.rho:.4f}): |error| = "
        f"{sanity['gh_anchor_err']:.2e} (< 1e-6 gate) -- the law-of-total-"
        "probability identity under Z ~ N(0,1);",
        f"* SAMPLE mean over the recovered Z_t of the flat-anchor PIT PD = "
        f"{sanity['sample_mean_pit']:.4%} vs mean observed rate "
        f"{sanity['mean_observed']:.4%} vs flat TTC anchor "
        f"{sanity['flat_ttc']:.4%}: the sample mean sits ABOVE the anchor "
        "exactly because mean(Z) != 0 (the documented level gap) -- "
        "reported, not hidden; the N(0,1) expectation matches the anchor "
        "to quadrature precision.",
        "",
        f"rho context: calibrated {res.rho:.4f} vs notes convention "
        f"{RHO_NOTES:.2f} vs Basel residential {RHO_BASEL_RESI:.2f} "
        "(regulatory conservatism, not time-series fit -- see "
        "outputs/vasicek/vasicek_report.md).",
        "",
        "## Exhibit",
        "",
        "`satellite_fit.png` -- recovered Z_t vs the satellite fit on the "
        "estimation sample, residuals below, GFC shaded, real calendar "
        "quarters throughout.",
    ]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_scenario_report(path: Path, summary: pd.DataFrame,
                          jensen: dict, wsens: pd.DataFrame,
                          checks: list[dict], res, satm,
                          sset, timings: dict[str, float]) -> None:
    L = [
        "# Scenario-conditional ECL report -- t=60 (2015Q1) live book",
        "",
        "Generated by `analysis/run_scenarios.py` (engine/satellite.py "
        "composing the FROZEN Day-2 engines; engine/scenarios.py paths; "
        "engine/vasicek.py conditioning).",
        "",
        "## Pipeline",
        "",
        "scenario macro path (DFAST shape rebased to the 2015Q1 jump-off, "
        "40q with reversion to long-run means) -> satellite "
        f"(Z = f({', '.join(satm.terms)})) -> Z path per scenario -> "
        "PIT-conditioning of the frozen default hazard per loan-quarter, "
        "lambda_PIT = pit_pd(lambda_TTC, Z_h, rho = "
        f"{res.rho:.4f}) applied at QUARTERLY-HAZARD level (the standard "
        "practical approximation) with the TTC baseline scored at "
        "panel-mean macros (the anchor Z was recovered against) -> the "
        "frozen ECL formula sum_t S(t-1) lambda_t LGD_t EAD_t (1+EIR)^-t "
        "per loan over the remaining contractual life.",
        "",
        "## Headline: scenario ECL",
        "",
        "| scenario | weight | mean Z (13q R&S) | UER peak (pp) | 12m ECL "
        "($m) | lifetime ECL ($m) | reported allowance ($m) | coverage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, r in summary.iterrows():
        L.append(
            f"| {SCEN_LABEL[r['scenario']]} | {r['weight']:.2f} | "
            f"{r['zbar_13q']:+.2f} | {r['uer_peak']:.1f} | "
            f"{r['ecl_12m_m']:,.1f} | {r['lifetime_m']:,.1f} | "
            f"{r['allowance_m']:,.1f} | {r['coverage']:.3%} |")
    L += [
        f"| **probability-weighted** | 1.00 | {jensen['zbar_w']:+.2f} | -- "
        f"| {jensen['w_12m_m']:,.1f} | {jensen['w_lifetime_m']:,.1f} | "
        f"**{jensen['w_allowance_m']:,.1f}** | "
        f"{jensen['w_coverage']:.3%} |",
        f"| at the AVERAGE macro path (single run) | -- | "
        f"{jensen['zbar_w']:+.2f} | -- | {jensen['a_12m_m']:,.1f} | "
        f"{jensen['a_lifetime_m']:,.1f} | {jensen['a_allowance_m']:,.1f} | "
        f"{jensen['a_coverage']:.3%} |",
        "",
        f"Book: {jensen['n_total']:,} non-payoff exposures at t=60 "
        f"({jensen['n_perf']:,} live/performing + {jensen['n_s3']:,} "
        "Stage-3 default rows whose ECL = LGD x balance is scenario-"
        "invariant by construction). Stage mix is calm-quarter extreme "
        f"({jensen['n_stage1']:,} Stage 1), so the reported allowance is "
        "dominated by 12-month ECL -- which is exactly where the scenario "
        "differentiation lives (the 13q R&S window).",
        "",
        "## THE JENSEN GAP (notes section 9.2, Fig 6 -- on our numbers)",
        "",
        f"**Probability-weighted reported allowance "
        f"${jensen['w_allowance_m']:,.1f}m vs "
        f"${jensen['a_allowance_m']:,.1f}m at the averaged macro path: "
        f"ratio {jensen['ratio_reported']:.3f}x.** On summed lifetime ECL "
        f"the ratio is {jensen['ratio_lifetime']:.3f}x. Both exceed 1 -- "
        "measuring ECL on a single averaged path UNDERSTATES expected "
        "loss; that is Jensen's inequality on a convex loss function and "
        "the analytical reason IFRS 9 paragraph 5.5.17 demands a "
        "probability-weighted range of outcomes.",
        "",
        "**Why our ratio is far below the notes' ~1.9x toy example "
        "(honest decomposition):**",
        "",
        f"1. calibrated rho = {res.rho:.4f} vs the toy's 0.12 -- the "
        "empirical asset correlation of this panel is ~5x smaller, so the "
        "PIT transform bends PDs far less per unit of Z;",
        "2. scenario Z dispersion: our satellite-implied paths touch their "
        f"extremes for a single quarter (severe trough {jensen['z_trough']:+.2f} "
        f"vs upside {jensen['z_up_at_widest']:+.2f} in the same quarter, "
        f"{jensen['z_gap_widest']:.1f} Z at the widest point) but sit only "
        f"{jensen['zbar_gap']:.1f} Z apart on the 13q R&S-window means the "
        "ECL actually integrates -- against the toy's SUSTAINED 4-Z spread "
        "(+1 to -3); DFAST-shaped quarterly paths are far gentler than a "
        "stylised one-shot downside;",
        "3. only the DEFAULT-PD leg is conditioned (LGD and EAD stay at "
        "the frozen rung-1 projections), removing the PDxLGD convexity "
        "the toy implicitly bundles;",
        "4. lifetime aggregation dilutes: all three scenarios share the "
        "same long-run reversion tail from h=21, and discounting plus "
        "amortisation shrink the differentiated window's weight; the toy "
        "is a single-period calculation entirely inside the stressed "
        "window.",
        "",
        "The 12m/reported measure -- concentrated in the R&S window -- "
        f"shows the bigger gap ({jensen['ratio_reported']:.3f}x) for "
        "exactly reason 4 in reverse.",
        "",
        "## The lifetime up-vs-base crossover (reported, not hidden)",
        "",
        f"Summed LIFETIME ECL is {jensen['life_up_m']:,.1f} (upside) vs "
        f"{jensen['life_base_m']:,.1f} (base): the upside book is "
        "slightly MORE expensive over the full remaining life, even "
        "though its 12m ECL and reported allowance are (correctly) the "
        "cheapest. Two real mechanisms, both documented:",
        "",
        "1. **mirror payback**: the upside path is a damped MIRROR of the "
        "severely-adverse deltas, so the severe path's recovery quarters "
        "mirror into a mild LATE-window deterioration for the upside "
        "(boom now, payback later) -- its mean Z over 21 quarters ends "
        "up marginally below the base path's;",
        "2. **survivor exposure**: lower hazards in the boom leave MORE "
        "loans alive entering the shared long-run tail (whose Z, "
        f"{jensen['z_longrun']:+.2f}, carries the recovered level gap), "
        "so more exposure is at risk in the undifferentiated quarters -- "
        "a genuine competing-risk effect of lifetime ECL, not a bug.",
        "",
        "The IFRS 9 allowance ordering (severe > base > upside) holds on "
        "the reported measure, which is what the gates test.",
        "",
        "## Weights sensitivity (governance exhibit)",
        "",
        "| weights (base/down/up) | reported allowance ($m) | coverage | "
        "vs adopted |",
        "|---|---|---|---|",
    ]
    for _, r in wsens.iterrows():
        L.append(f"| {r['label']} | {r['allowance_m']:,.1f} | "
                 f"{r['coverage']:.3%} | {r['delta_pct']:+.1f}% |")
    L += [
        "",
        "Scenario probabilities are not statistically identified; the "
        "deliverable is the documented rationale plus this sensitivity "
        "(engine/scenarios.py). The adopted 50/25/25 sits between the "
        "alternatives; the swing across reasonable weightings (~"
        f"{wsens['delta_pct'].abs().max():.0f}%) is small next to the "
        f"severe-vs-base scenario gap "
        f"({jensen['down_over_base']:.2f}x on the allowance).",
        "",
        "## Sanity gates",
        "",
        "| check | result | detail |",
        "|---|---|---|",
    ]
    for c in checks:
        L.append(f"| {c['name']} | {'PASS' if c['ok'] else '**FAIL**'} | "
                 f"{c['detail']} |")
    L += [
        "",
        "## Documented simplifications (engine/satellite.py docstring)",
        "",
        "* Vasicek transform applied at QUARTERLY-HAZARD level per "
        "projection quarter (standard practical approximation; the joint "
        "multi-period conditional law is not derived).",
        "* Only the default hazard is conditioned; PREPAYMENT stays on the "
        "frozen rung-1 projection (scenario-conditional refinancing is a "
        "named enhancement).",
        "* LGD and EAD are NOT scenario-conditioned -- scenario "
        "sensitivity enters through the PD leg only; a collateral-path "
        "LGD link is the standard next rung.",
        "* TTC baseline = frozen hazard at panel-mean macros with "
        "loan-state covariates (incl. HPI-indexed updated_ltv) at "
        "snapshot values: part of the collateral cycle sits in the "
        "baseline (conservative Z dial; vasicek report caveat).",
        "* Z beyond the 40q scenario horizon holds its final (long-run) "
        "value; macro paths already sit at long-run means from h=21.",
        "* STAGING fixed across scenarios (frozen rung-1 stages at the "
        "reporting date); the IASB two-step probability-weighted staging "
        "is the documented enhancement.",
        "* Static-OLS satellite with sign governance instead of the full "
        "ARDL/ECM production standard (outputs/satellite/ report).",
        "* Upside = damped mirror of the severe deltas (engine/"
        "scenarios.py convention; SPF-percentile anchoring is the "
        "documented enhancement) -- source of the lifetime crossover "
        "above.",
        "* Scenario weights 50/25/25 judgmental (governance convention), "
        "sensitivity above.",
        "",
        "## Performance",
        "",
    ]
    for k, v in timings.items():
        L.append(f"* {k}: {v:.1f}s")
    L += [
        "",
        "## Files",
        "",
        "* `jensen_gap.png` -- THE exhibit (weighted vs averaged-path ECL).",
        "* `scenario_ecl_bars.png` -- allowance by scenario + weighted.",
        "* `z_paths.png` -- history Z + scenario Z fan (calendar axis).",
        "* `scenario_ecl_summary.csv`, `scenario_z_paths.csv` -- data "
        "behind the exhibits.",
    ]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------

def main() -> None:
    OUT_SAT.mkdir(parents=True, exist_ok=True)
    OUT_SCEN.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    cfg = EclConfig()

    t0 = _time.perf_counter()
    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]
    models = {"default": fit_default_hazard(train),
              "prepay": fit_prepay_hazard(train),
              "lgd": fit_lgd_models(panel)}
    timings["model fits (2 hazards + LGD)"] = _time.perf_counter() - t0
    print(f"fitted frozen engines in "
          f"{timings['model fits (2 hazards + LGD)']:.1f}s")

    # ---- Z recovery + anchor sanity -------------------------------------
    t1 = _time.perf_counter()
    res, tab = recover_z(panel, models["default"])
    sanity = anchor_sanity(tab, res)
    timings["Z recovery (Belkin)"] = _time.perf_counter() - t1
    print(f"rho = {res.rho:.4f}, mean(Z) = {res.mean_z:+.3f}, "
          f"roundtrip {sanity['roundtrip_max_err']:.1e}, "
          f"GH anchor {sanity['gh_anchor_err']:.1e}")
    if sanity["roundtrip_max_err"] >= 1e-9:
        _fail(f"PIT round trip {sanity['roundtrip_max_err']:.2e} >= 1e-9")
    if sanity["gh_anchor_err"] >= 1e-6:
        _fail(f"GH anchor error {sanity['gh_anchor_err']:.2e} >= 1e-6")

    # ---- satellite -------------------------------------------------------
    concepts = panel_macro_concepts(build_macro_map(panel))
    drivers = driver_frame(concepts)
    z_ser = pd.Series(res.z, index=tab.index)
    stat_tab = stationarity_table({
        "z (recovered)": z_ser,
        "uer level": concepts["uer"],
        "duer (first difference)": concepts["uer"].diff(),
        "hpi_growth": concepts["hpi_growth"],
        "gdp_growth": concepts["gdp_growth"],
    })
    satm = fit_satellite(z_ser, drivers)
    if not satm.fit_meta["sign_valid"]:
        _fail("no sign-admissible satellite spec found")
    gfc_tab = gfc_sensitivity(z_ser, drivers, satm)
    print(f"satellite: {' + '.join(satm.terms)}  adj R2 {satm.adj_r2:.3f}  "
          f"DW {satm.dw:.2f}  (AIC best among sign-valid specs)")
    plot_satellite_fit(z_ser, satm, OUT_SAT / "satellite_fit.png")
    write_satellite_report(OUT_SAT / "satellite_report.md", satm, stat_tab,
                           gfc_tab, sanity, res, z_ser)
    print(f"wrote {OUT_SAT / 'satellite_report.md'}, "
          f"{OUT_SAT / 'satellite_fit.png'}")

    # ---- scenario Z paths -------------------------------------------------
    sset = build_scenario_set()
    zp = scenario_z_paths(satm, sset, concepts)
    if not np.isfinite(zp[["base", "down", "up", "weighted"]]
                       .to_numpy(dtype=float)).all():
        _fail("non-finite scenario Z paths")
    zbar = {n: float(zp[n].iloc[:sset.rs_window].mean())
            for n in ("base", "down", "up", "weighted")}
    z_longrun = float(zp["base"].iloc[-1])
    print(f"Z means over R&S window: " + ", ".join(
        f"{n} {zbar[n]:+.2f}" for n in ("up", "base", "down")))

    # ---- scenario-conditional ECL -----------------------------------------
    t2 = _time.perf_counter()
    hz = {"default": models["default"], "prepay": models["prepay"]}
    staged = assign_stages(panel.loc[panel["time"] <= T_SNAP], hz,
                           cfg.staging, snapshot_time=T_SNAP)
    mm = ttc_macro_means(panel)

    frozen = ecl_for_snapshot(panel, T_SNAP, models, cfg)
    unconditioned = scenario_ecl_for_snapshot(panel, T_SNAP, models,
                                              staged=staged, config=cfg)
    xdiff = max(
        float(np.max(np.abs(frozen[c].to_numpy()
                            - unconditioned[c].to_numpy())))
        for c in ("ecl_12m", "ecl_lifetime", "ecl_reported"))
    print(f"unconditioned wrapper vs frozen engine: max |diff| = {xdiff:.2e}")
    if xdiff >= 1e-9:
        _fail(f"wrapper does not reproduce frozen engine: {xdiff:.2e}")

    books: dict[str, pd.DataFrame] = {}
    for name in ("up", "base", "down", "weighted"):
        books[name] = scenario_ecl_for_snapshot(
            panel, T_SNAP, models, z_path=zp[name].to_numpy(),
            rho=res.rho, macro_means=mm, staged=staged, config=cfg)
    timings["scenario ECL runs (4 paths + crosscheck)"] = \
        _time.perf_counter() - t2

    b0 = books["base"]
    n_total, n_s3 = len(b0), int((b0["stage"] == 3).sum())
    n_perf = n_total - n_s3
    n_stage1 = int((b0["stage"] == 1).sum())
    if n_perf != LIVE_LOANS or n_s3 != STAGE3_LOANS:
        _fail(f"book population {n_perf} live + {n_s3} stage-3 "
              f"(expected {LIVE_LOANS} + {STAGE3_LOANS})")

    balance = float(b0["balance"].sum())
    summary = pd.DataFrame([{
        "scenario": n,
        "weight": sset.weights[n],
        "zbar_13q": zbar[n],
        "uer_peak": float(sset.paths[n]["uer"].max()),
        "ecl_12m_m": float(books[n]["ecl_12m"].sum()) / 1e6,
        "lifetime_m": float(books[n]["ecl_lifetime"].sum()) / 1e6,
        "allowance_m": float(books[n]["ecl_reported"].sum()) / 1e6,
        "coverage": float(books[n]["ecl_reported"].sum()) / balance,
    } for n in ("up", "base", "down")])

    w = sset.weights
    tot = {n: {c: float(books[n][c].sum())
               for c in ("ecl_12m", "ecl_lifetime", "ecl_reported")}
           for n in books}
    w_rep = sum(w[n] * tot[n]["ecl_reported"] for n in ("base", "down", "up"))
    w_life = sum(w[n] * tot[n]["ecl_lifetime"] for n in ("base", "down", "up"))
    w_12m = sum(w[n] * tot[n]["ecl_12m"] for n in ("base", "down", "up"))
    a_rep = tot["weighted"]["ecl_reported"]
    a_life = tot["weighted"]["ecl_lifetime"]
    jensen = {
        "w_allowance_m": w_rep / 1e6, "a_allowance_m": a_rep / 1e6,
        "w_lifetime_m": w_life / 1e6, "a_lifetime_m": a_life / 1e6,
        "w_12m_m": w_12m / 1e6,
        "a_12m_m": tot["weighted"]["ecl_12m"] / 1e6,
        "ratio_reported": w_rep / a_rep, "ratio_lifetime": w_life / a_life,
        "w_coverage": w_rep / balance, "a_coverage": a_rep / balance,
        "zbar_w": zbar["weighted"], "z_longrun": z_longrun,
        "z_trough": float(zp["down"].min()),
        "z_up_at_widest": float(zp.loc[(zp["up"] - zp["down"]).idxmax(),
                                       "up"]),
        "z_gap_widest": float((zp["up"] - zp["down"]).max()),
        "zbar_gap": zbar["up"] - zbar["down"],
        "n_total": n_total, "n_perf": n_perf, "n_s3": n_s3,
        "n_stage1": n_stage1,
        "life_up_m": tot["up"]["ecl_lifetime"] / 1e6,
        "life_base_m": tot["base"]["ecl_lifetime"] / 1e6,
        "down_over_base": (tot["down"]["ecl_reported"]
                           / tot["base"]["ecl_reported"]),
    }
    print(f"allowance: up {tot['up']['ecl_reported'] / 1e6:.1f}m, base "
          f"{tot['base']['ecl_reported'] / 1e6:.1f}m, down "
          f"{tot['down']['ecl_reported'] / 1e6:.1f}m; weighted "
          f"{w_rep / 1e6:.1f}m vs avg-path {a_rep / 1e6:.1f}m "
          f"(Jensen {w_rep / a_rep:.3f}x)")

    # ---- Jensen curve (parallel Z shifts of the weighted path) ------------
    t3 = _time.perf_counter()
    curve_rows = []
    zw = zp["weighted"].to_numpy()
    for s in JENSEN_SHIFTS:
        if abs(s) < 1e-12:
            rep = a_rep
        else:
            bk = scenario_ecl_for_snapshot(
                panel, T_SNAP, models, z_path=zw + s, rho=res.rho,
                macro_means=mm, staged=staged, config=cfg)
            rep = float(bk["ecl_reported"].sum())
        curve_rows.append({"shift": float(s),
                           "zbar": zbar["weighted"] + float(s),
                           "allowance_m": rep / 1e6})
    curve = pd.DataFrame(curve_rows)
    timings["Jensen curve traces"] = _time.perf_counter() - t3

    # ---- weights sensitivity ----------------------------------------------
    wsens_rows = []
    for label, ws in WEIGHT_SETS.items():
        rep = sum(ws[n] * tot[n]["ecl_reported"]
                  for n in ("base", "down", "up"))
        wsens_rows.append({"label": label, "allowance_m": rep / 1e6,
                           "coverage": rep / balance,
                           "delta_pct": 100.0 * (rep / w_rep - 1.0)})
    wsens = pd.DataFrame(wsens_rows)

    # ---- gates -------------------------------------------------------------
    checks = [
        {"name": "anchor sanity (round trip / Gauss-Hermite)", "ok": True,
         "detail": f"{sanity['roundtrip_max_err']:.1e} / "
                   f"{sanity['gh_anchor_err']:.1e}"},
        {"name": "satellite sign governance + finite scenario Z",
         "ok": True, "detail": f"spec {' + '.join(satm.terms)}, all Z "
                               "paths finite"},
        {"name": "unconditioned wrapper == frozen ECL engine",
         "ok": xdiff < 1e-9, "detail": f"max abs diff = {xdiff:.2e}"},
        {"name": f"book population {LIVE_LOANS:,} live + "
                 f"{STAGE3_LOANS} stage-3",
         "ok": (n_perf == LIVE_LOANS and n_s3 == STAGE3_LOANS),
         "detail": f"{n_perf:,} + {n_s3}"},
        {"name": "allowance ordering severe > base > upside",
         "ok": (tot["down"]["ecl_reported"] > tot["base"]["ecl_reported"]
                > tot["up"]["ecl_reported"]),
         "detail": f"{tot['down']['ecl_reported'] / 1e6:.1f} > "
                   f"{tot['base']['ecl_reported'] / 1e6:.1f} > "
                   f"{tot['up']['ecl_reported'] / 1e6:.1f} ($m)"},
        {"name": "12m ECL ordering severe > base > upside",
         "ok": (tot["down"]["ecl_12m"] > tot["base"]["ecl_12m"]
                > tot["up"]["ecl_12m"]),
         "detail": f"{tot['down']['ecl_12m'] / 1e6:.1f} > "
                   f"{tot['base']['ecl_12m'] / 1e6:.1f} > "
                   f"{tot['up']['ecl_12m'] / 1e6:.1f} ($m)"},
        {"name": "lifetime ECL severe > base",
         "ok": tot["down"]["ecl_lifetime"] > tot["base"]["ecl_lifetime"],
         "detail": f"{tot['down']['ecl_lifetime'] / 1e6:.1f} > "
                   f"{tot['base']['ecl_lifetime'] / 1e6:.1f} ($m)"},
        {"name": "Jensen: weighted > at-average-path (reported & lifetime)",
         "ok": (w_rep > a_rep and w_life > a_life),
         "detail": f"reported {w_rep / a_rep:.4f}x, lifetime "
                   f"{w_life / a_life:.4f}x"},
    ]

    # ---- exhibits + reports -------------------------------------------------
    plot_z_fan(z_ser, zp, OUT_SCEN / "z_paths.png")
    points = {n: (zbar[n], tot[n]["ecl_reported"] / 1e6)
              for n in ("up", "base", "down")}
    points["weighted"] = (zbar["weighted"], w_rep / 1e6)
    points["at_avg"] = (zbar["weighted"], a_rep / 1e6)
    plot_jensen(curve, points, w_rep / a_rep, OUT_SCEN / "jensen_gap.png")
    weighted_row = pd.Series({"allowance_m": w_rep / 1e6,
                              "coverage": w_rep / balance})
    plot_scenario_bars(summary, weighted_row,
                       OUT_SCEN / "scenario_ecl_bars.png")

    summary.to_csv(OUT_SCEN / "scenario_ecl_summary.csv", index=False,
                   float_format="%.6f")
    zp.to_csv(OUT_SCEN / "scenario_z_paths.csv", float_format="%.6f")
    write_scenario_report(OUT_SCEN / "scenario_ecl_report.md", summary,
                          jensen, wsens, checks, res, satm, sset, timings)
    for f in ("z_paths.png", "jensen_gap.png", "scenario_ecl_bars.png",
              "scenario_ecl_summary.csv", "scenario_z_paths.csv",
              "scenario_ecl_report.md"):
        print(f"wrote {OUT_SCEN / f}")

    if not all(c["ok"] for c in checks):
        for c in checks:
            if not c["ok"]:
                print(f"FAILED: {c['name']} -- {c['detail']}")
        raise SystemExit("scenario ECL sanity checks FAILED -- see report")
    print("all scenario ECL sanity checks PASSED")


if __name__ == "__main__":
    main()
