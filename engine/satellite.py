"""Satellite macro-link model + scenario-conditional ECL (notes section 9;
plan section 6 -- Day 3's forward-looking rung).

This module NEVER modifies the frozen Day-2 engines. It composes them:
engine/{hazard,lgd,ead,staging,ecl}.py are imported READ-ONLY; the scenario-
conditional ECL below reuses their grids, survival algebra and conventions
exactly, swapping in a PIT-conditioned default-hazard grid.

--------------------------------------------------------------------------------
1. SATELLITE MODEL (notes section 9.1)
--------------------------------------------------------------------------------
Regress the recovered credit-cycle factor Z_t (Belkin inversion, engine/
vasicek.py; recovery convention identical to analysis/fit_vasicek.py's main
variant) on lagged macro drivers from the panel's own 60-quarter history:

    Z_t = c + b1 * duer_{t-l1} + b2 * hpi_growth_{t-l2} + b3 * gdp_growth_{t-l3} + e_t

Candidate drivers (all transformed to I(0) shapes BEFORE entering):
    duer        quarterly CHANGE in the unemployment rate (pp) -- the level is
                the textbook I(1) suspect, so it enters differenced;
    hpi_growth  quarterly log HPI growth (decimal) -- already a difference;
    gdp_growth  quarterly GDP growth (%) -- already a growth rate.
Each driver enters at lag 1 OR lag 2 (macro variables act on credit with a
1-2 quarter transmission lag; notes section 9.1). Specification search: AIC
over every NON-EMPTY DRIVER SUBSET x lag combination (26 specs), all
estimated on the COMMON sample (so AICs are comparable), SUBJECT TO the
ECONOMIC-SIGN GOVERNANCE CONSTRAINT (EXPECTED_SIGN): a spec is admissible
only if every fitted driver coefficient carries its economically
interpretable sign (falling unemployment / rising HPI / rising GDP cannot
worsen the credit cycle). Wrong-signed candidates -- on this panel duer,
whose conditional coefficient turns positive (and insignificant) once
hpi_growth is present, a collinearity artifact of the one-cycle sample --
are thereby excluded, WITH the full grid (including the rejected specs and
their signs) reported, not hidden. Sign restrictions on satellite-model
coefficients are standard model-governance practice for exactly this
small-sample identification problem. Hygiene emitted for the report: ADF +
KPSS per series with plain-language verdicts, Durbin-Watson, adjusted R2,
and a GFC-dummy sensitivity refit.

SIMPLIFIED vs FULL METHOD (documented): production standard is the ARDL
bounds framework (Pesaran-Shin-Smith 2001) with an error-correction term
(negative and significant = adjustment speed), Johansen cointegration ranks
for the multivariate system, structural-break tests (Chow / CUSUM) around
2008-09, and HAC standard errors. Here: a STATIC OLS in already-differenced /
growth-rate (I(0)) drivers with AIC lag choice and a GFC-dummy sensitivity --
the disciplined small-sample simplification (57 usable quarters), with the
full method named as the production standard in outputs/satellite/.

--------------------------------------------------------------------------------
2. SCENARIO-CONDITIONAL ECL (notes sections 9.2, 9.4)
--------------------------------------------------------------------------------
scenario macro path (engine/scenarios.py, 40q) -> satellite -> Z_h path ->
PIT-condition the frozen default hazard -> frozen ECL machinery.

Conditioning convention (each choice documented, none hidden):
  * TTC BASELINE: the frozen default hazard scored with its four macro
    regressors (HAZARD_MACRO_COLS) frozen at panel-period means -- the SAME
    composition-adjusted anchor convention used to recover Z_t in the first
    place (analysis/fit_vasicek.py), so pit_pd(anchor, Z_t, rho) reproduces
    the observed rate history by construction (round-trip identity).
    Loan-state covariates (age, FICO, HPI-indexed updated_ltv,
    prepay_incentive) stay at snapshot values: part of the collateral cycle
    lives in the baseline, making Z a conservative cycle dial (the vasicek
    report's documented caveat carries through).
  * HAZARD-LEVEL TRANSFORM: vasicek.pit_pd is applied to the QUARTERLY
    CONDITIONAL HAZARD levels, lambda_PIT(i,k) = pit_pd(lambda_TTC(i,k),
    Z_{h=k}, rho). Applying the one-factor transform at quarterly-hazard
    level (rather than deriving the joint multi-period conditional law) is
    the STANDARD PRACTICAL APPROXIMATION in IFRS 9 production systems: each
    projection quarter is conditioned on that quarter's systematic factor as
    if it were a one-period Vasicek portfolio.
  * PREPAYMENT hazard is NOT conditioned (stays the frozen rung-1
    projection): the Vasicek factor is a default-risk device; a
    scenario-conditional refinancing model is a named enhancement.
  * LGD and EAD are NOT scenario-conditioned: scenario sensitivity enters
    through the PD leg only (documented simplification -- a collateral-path
    LGD link is the standard next rung).
  * Z BEYOND THE 40q HORIZON: scenario macro paths hold long-run means from
    h = 21 (engine/scenarios.py reversion), so the satellite Z is constant
    there; for projection quarters beyond the supplied path, Z holds its
    final (long-run) value.
  * STAGING is assigned ONCE at the reporting date from the frozen rung-1
    staging engine and held fixed across scenarios. The IASB illustrative
    two-step approach (stage on the probability-WEIGHTED lifetime PD) is the
    documented enhancement; fixed staging isolates the pure measurement
    effect of the scenarios.
  * Stage-3 rows keep the frozen convention ECL = LGD(x_now) * balance --
    the default has happened; it is scenario-invariant by construction.

With z_path=None and macro_means=None, scenario_ecl_for_snapshot reproduces
the frozen engine.ecl.ecl_for_snapshot EXACTLY (same grids, same algebra) --
the correctness anchor gated in analysis/run_scenarios.py and unit-tested.

Deterministic throughout: no LLM, no network, no randomness.
"""

from __future__ import annotations

import itertools
import warnings
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tsa.stattools import adfuller, kpss

from engine.ecl import EclConfig, _lgd_grid, _survival_marginal
from engine.ead import RATE_DIVISOR, SNAPSHOT_COLS, ead_matrix
from engine.hazard import HazardModel, predict_hazard
from engine.lgd import predict_components
from engine.scenarios import ScenarioSet, panel_time_to_period
from engine.staging import (
    _age_curve,
    _design_matrix,
    _spline_cols,
    assign_stages,
)
from engine.vasicek import BelkinResult, calibrate_rho, pit_pd

#: the four MACRO regressors of the frozen hazard (engine/hazard.py timing
#: convention) -- mirrors analysis/fit_vasicek.py MACRO_COLS; frozen at
#: panel-period means to build the composition-adjusted TTC anchor
HAZARD_MACRO_COLS = ["uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1",
                     "gdp_lag1"]

#: candidate satellite drivers (I(0) transforms; module docstring)
DRIVERS = ("duer", "hpi_growth", "gdp_growth")

#: candidate transmission lags per driver (notes section 9.1: 1-2 quarters)
DRIVER_LAGS = (1, 2)

#: economic-sign governance (module docstring): admissible specs must have
#: rising unemployment pushing Z DOWN, rising HPI / GDP pushing Z UP
EXPECTED_SIGN = {"duer": -1.0, "hpi_growth": 1.0, "gdp_growth": 1.0}

#: NBER GFC recession window (same shading convention as fit_vasicek)
GFC_WINDOW = (pd.Period("2007Q4", freq="Q"), pd.Period("2009Q2", freq="Q"))

#: domain guard for pit_pd on hazard levels (strictly inside (0,1))
_PROB_EPS = 1e-12


# ---------------------------------------------------------------------------
# Z recovery (composition-adjusted Belkin; the fit_vasicek 'main' convention)
# ---------------------------------------------------------------------------

def ttc_macro_means(panel_df: pd.DataFrame) -> pd.Series:
    """Panel-period means of the frozen hazard's four macro regressors.

    Per-quarter national values via groupby(time).first() (constant within
    quarter; NaN in the lag warm-up), unweighted mean over quarters -- the
    IDENTICAL convention to analysis/fit_vasicek.py, so the anchor (and the
    recovered Z) match that rung's published calibration.
    """
    per_q = panel_df.groupby("time")[HAZARD_MACRO_COLS].first()
    return per_q.mean()


def observed_vs_ttc_rates(panel_df: pd.DataFrame, default_model: HazardModel,
                          macro_means: pd.Series | None = None
                          ) -> pd.DataFrame:
    """Observed vs composition-adjusted expected (TTC) default rate per quarter.

    The expected rate scores EVERY at-risk row of the quarter with the four
    macro regressors replaced by panel-period means (loan-state covariates
    stay actual) -- the composition-adjusted Belkin anchor (main variant of
    analysis/fit_vasicek.py). Index: panel time; columns: n_at_risk,
    observed, expected_ttc.
    """
    mm = macro_means if macro_means is not None else ttc_macro_means(panel_df)
    score = panel_df.copy()
    for c in HAZARD_MACRO_COLS:
        score[c] = mm[c]
    lam = predict_hazard(default_model, score)
    if not np.all(np.isfinite(lam)):
        raise ValueError("non-finite TTC hazard predictions")
    by_t = panel_df["time"]
    tab = pd.DataFrame({
        "n_at_risk": panel_df.groupby("time").size(),
        "observed": panel_df.groupby("time")["default_event"].mean(),
        "expected_ttc": pd.Series(lam, index=panel_df.index)
                          .groupby(by_t).mean(),
    })
    tab.index.name = "time"
    return tab


def recover_z(panel_df: pd.DataFrame, default_model: HazardModel
              ) -> tuple[BelkinResult, pd.DataFrame]:
    """Belkin Z recovery on the composition-adjusted rates: (result, table)."""
    tab = observed_vs_ttc_rates(panel_df, default_model)
    res = calibrate_rho(tab["observed"], tab["expected_ttc"])
    return res, tab


def anchor_sanity(tab: pd.DataFrame, res: BelkinResult) -> dict[str, float]:
    """Anchor diagnostics for the report (and the unit-test gate).

    roundtrip_max_err : max |pit_pd(anchor_t, Z_t, rho) - observed_t| -- the
        per-quarter inversion identity (should be ~1e-15);
    gh_anchor_err : Gauss-Hermite |E_Z[PD_PIT] - PD_TTC| at the flat anchor
        under Z ~ N(0,1) (the law-of-total-probability identity, < 1e-6);
    sample_mean_pit vs mean_observed : E over the RECOVERED Z_ts of the
        flat-anchor PIT PD vs the sample mean observed rate -- reported, not
        gated: the recovered Z has mean != 0 (level gap documented in
        outputs/vasicek/vasicek_report.md), so the SAMPLE mean sits above
        the TTC anchor; the N(0,1) expectation equals it exactly.
    """
    from engine.vasicek import anchor_check
    anchors = tab["expected_ttc"].to_numpy()
    recon = pit_pd(anchors, res.z, res.rho)
    flat = float(tab["expected_ttc"].mean())
    _, gh_err = anchor_check(flat, res.rho)
    return {
        "roundtrip_max_err": float(
            np.max(np.abs(recon - tab["observed"].to_numpy()))),
        "gh_anchor_err": float(gh_err),
        "flat_ttc": flat,
        "sample_mean_pit": float(np.mean(pit_pd(flat, res.z, res.rho))),
        "mean_observed": float(tab["observed"].mean()),
    }


# ---------------------------------------------------------------------------
# satellite drivers + stationarity hygiene
# ---------------------------------------------------------------------------

def driver_frame(concepts: pd.DataFrame) -> pd.DataFrame:
    """Concept history/path -> lagged satellite driver columns.

    concepts : frame ordered in time (panel history, a scenario path, or a
        splice of both) carrying uer, hpi_growth, gdp_growth. The index is
        preserved; shifts are positional in time order.
    Returns columns {driver}_lag{l} for DRIVERS x DRIVER_LAGS, where
    duer = uer.diff() (first difference of the unemployment level).
    """
    for c in ("uer", "hpi_growth", "gdp_growth"):
        if c not in concepts.columns:
            raise KeyError(f"concept frame is missing '{c}'")
    base = {
        "duer": concepts["uer"].diff(),
        "hpi_growth": concepts["hpi_growth"],
        "gdp_growth": concepts["gdp_growth"],
    }
    out = pd.DataFrame(index=concepts.index)
    for name in DRIVERS:
        for lag in DRIVER_LAGS:
            out[f"{name}_lag{lag}"] = base[name].shift(lag)
    return out


def stationarity_table(series: Mapping[str, pd.Series]) -> pd.DataFrame:
    """ADF + KPSS per series with a plain-language verdict.

    ADF null: unit root; KPSS null: stationarity -- complementary tests, run
    both (notes section 9.1). KPSS p-values are table-bounded to
    [0.01, 0.10]; the statsmodels interpolation warning outside that range
    is suppressed and the bound reported (documented behaviour).
    """
    rows = []
    for name, s in series.items():
        x = pd.Series(s).dropna().to_numpy(dtype=float)
        adf_p = float(adfuller(x, autolag="AIC")[1])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kpss_p = float(kpss(x, regression="c", nlags="auto")[1])
        adf_rej = adf_p < 0.05          # rejects unit root
        kpss_rej = kpss_p < 0.05        # rejects stationarity
        if adf_rej and not kpss_rej:
            verdict = ("stationary -- ADF rejects a unit root and KPSS "
                       "cannot reject stationarity: safe to use as-is")
        elif not adf_rej and kpss_rej:
            verdict = ("unit root -- ADF cannot reject and KPSS rejects "
                       "stationarity: I(1); difference before use")
        elif adf_rej and kpss_rej:
            verdict = ("conflicting -- both nulls rejected: near-stationary "
                       "with a possible break or long memory; use with care")
        else:
            verdict = ("inconclusive -- neither null rejected (low power on "
                       f"{len(x)} quarters); economics must decide")
        rows.append({"series": name, "n": len(x), "adf_p": adf_p,
                     "kpss_p": kpss_p, "verdict": verdict})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# satellite fit (AIC over the lag grid) + GFC sensitivity
# ---------------------------------------------------------------------------

@dataclass
class SatelliteModel:
    """Fitted satellite Z_t = c + b' drivers_t + e_t (OLS).

    result    : statsmodels RegressionResultsWrapper of the AIC-best spec
    terms     : driver columns of the chosen spec (order fixed by DRIVERS)
    selection : the full AIC grid (one row per lag combination, common
                estimation sample so AICs are comparable)
    times     : index labels (panel quarters) of the estimation sample
    """

    result: object
    terms: tuple[str, ...]
    selection: pd.DataFrame
    times: np.ndarray
    fit_meta: dict = field(default_factory=dict)

    @property
    def params(self) -> pd.Series:
        return self.result.params

    @property
    def aic(self) -> float:
        return float(self.result.aic)

    @property
    def adj_r2(self) -> float:
        return float(self.result.rsquared_adj)

    @property
    def dw(self) -> float:
        return float(durbin_watson(self.result.resid))

    @property
    def n_obs(self) -> int:
        return int(self.result.nobs)

    def predict(self, drivers: pd.DataFrame) -> np.ndarray:
        """Predict Z from a driver frame carrying the chosen term columns."""
        missing = [c for c in self.terms if c not in drivers.columns]
        if missing:
            raise KeyError(f"driver frame is missing satellite terms "
                           f"{missing}")
        X = drivers[list(self.terms)].to_numpy(dtype=float)
        if not np.isfinite(X).all():
            raise ValueError("driver frame carries NaN/inf in satellite "
                             "terms (need >= 3 quarters of history for the "
                             "lags -- splice the panel history in front of "
                             "a scenario path)")
        p = self.result.params
        return (float(p["const"])
                + X @ p[list(self.terms)].to_numpy(dtype=float))


def _estimation_sample(z: pd.Series, drivers: pd.DataFrame) -> pd.DataFrame:
    """Common estimation sample: all candidate columns + Z observed."""
    cols = [f"{d}_lag{l}" for d in DRIVERS for l in DRIVER_LAGS]
    data = drivers[cols].copy()
    data["z"] = pd.Series(z, index=drivers.index)
    return data.dropna()


def _signs_ok(res, terms: tuple[str, ...]) -> bool:
    """Economic-sign governance check on the fitted driver coefficients."""
    for term in terms:
        driver = term.rsplit("_lag", 1)[0]
        if float(res.params[term]) * EXPECTED_SIGN[driver] <= 0.0:
            return False
    return True


def fit_satellite(z: pd.Series, drivers: pd.DataFrame) -> SatelliteModel:
    """AIC-choose the driver subset + lags and fit the satellite OLS.

    z : recovered Z_t indexed like `drivers` (panel time).
    drivers : driver_frame output on the panel's concept history.

    Grid: every non-empty subset of DRIVERS, each included driver at lag 1
    or lag 2 (26 specs), all estimated on the COMMON sample (rows where
    every candidate lag exists), so AICs are comparable. Selection: min AIC
    among specs passing the EXPECTED_SIGN governance constraint (module
    docstring); the full grid -- including rejected wrong-signed specs --
    is attached as `selection` with a signs_ok column. If NO spec passes
    (degenerate history), falls back to the unconstrained AIC minimum with
    fit_meta['sign_valid'] = False.
    """
    sample = _estimation_sample(z, drivers)
    if len(sample) < 20:
        raise ValueError(f"only {len(sample)} usable quarters -- too few "
                         "to fit a satellite")
    rows, fits = [], {}
    for k in range(1, len(DRIVERS) + 1):
        for subset in itertools.combinations(DRIVERS, k):
            for lags in itertools.product(DRIVER_LAGS, repeat=k):
                terms = tuple(f"{d}_lag{l}" for d, l in zip(subset, lags))
                X = sm.add_constant(sample[list(terms)].astype(float))
                res = sm.OLS(sample["z"].astype(float), X).fit()
                fits[terms] = res
                rows.append({
                    "spec": " + ".join(terms),
                    "n_drivers": k,
                    "aic": float(res.aic),
                    "adj_r2": float(res.rsquared_adj),
                    "dw": float(durbin_watson(res.resid)),
                    "signs_ok": _signs_ok(res, terms),
                })
    selection = (pd.DataFrame(rows).sort_values("aic")
                 .reset_index(drop=True))
    valid = selection[selection["signs_ok"]]
    sign_valid = not valid.empty
    chosen = valid.iloc[0] if sign_valid else selection.iloc[0]
    best_terms = tuple(chosen["spec"].split(" + "))
    return SatelliteModel(
        result=fits[best_terms],
        terms=best_terms,
        selection=selection,
        times=sample.index.to_numpy(),
        fit_meta={"n_specs": len(rows), "n_obs": len(sample),
                  "sign_valid": sign_valid},
    )


def gfc_mask_for_times(times: np.ndarray) -> np.ndarray:
    """Boolean mask of panel quarters inside the NBER GFC window."""
    periods = [panel_time_to_period(int(t)) for t in np.asarray(times)]
    lo, hi = GFC_WINDOW
    return np.array([lo <= p <= hi for p in periods], dtype=bool)


def gfc_sensitivity(z: pd.Series, drivers: pd.DataFrame,
                    model: SatelliteModel) -> pd.DataFrame:
    """Refit the chosen spec with a GFC dummy; side-by-side coefficients.

    The crisis-dummy check from notes section 9.1: if the driver
    coefficients move materially once 2007Q4-2009Q2 is dummied out, the
    satellite is leaning on the crisis for identification (reported, not
    auto-corrected -- with one cycle in sample that lean is expected).
    """
    sample = _estimation_sample(z, drivers)
    X0 = sm.add_constant(sample[list(model.terms)].astype(float))
    base = sm.OLS(sample["z"].astype(float), X0).fit()
    X1 = X0.copy()
    X1["gfc_dummy"] = gfc_mask_for_times(sample.index.to_numpy()).astype(float)
    with_d = sm.OLS(sample["z"].astype(float), X1).fit()
    rows = []
    for term in ["const", *model.terms, "gfc_dummy"]:
        rows.append({
            "term": term,
            "coef_no_dummy": (float(base.params[term])
                              if term in base.params.index else np.nan),
            "p_no_dummy": (float(base.pvalues[term])
                           if term in base.params.index else np.nan),
            "coef_with_dummy": float(with_d.params[term]),
            "p_with_dummy": float(with_d.pvalues[term]),
        })
    out = pd.DataFrame(rows)
    out.attrs["adj_r2_no_dummy"] = float(base.rsquared_adj)
    out.attrs["adj_r2_with_dummy"] = float(with_d.rsquared_adj)
    return out


# ---------------------------------------------------------------------------
# scenario Z paths
# ---------------------------------------------------------------------------

def scenario_z_paths(model: SatelliteModel, sset: ScenarioSet,
                     history_concepts: pd.DataFrame,
                     include_weighted: bool = True) -> pd.DataFrame:
    """Satellite Z path per scenario over the ScenarioSet horizon.

    history_concepts : the panel's own concept history (engine.scenarios.
        panel_macro_concepts output, time 1..60) -- spliced IN FRONT of each
        scenario path so the h = 1, 2 driver lags reach back into observed
        history (duer at h=1 is uer_h1 - uer_t60, etc.).
    include_weighted : also predict on the probability-weighted AVERAGE
        macro path (ScenarioSet.weighted_path). Because the satellite is
        LINEAR, this equals the weighted average of the scenario Z paths --
        it exists for the Jensen exhibit ONLY and must never feed the
        reported ECL (engine/scenarios.py docstring warning).

    Returns a frame indexed h = 1..horizon with a 'period' column (real
    calendar quarters) and one Z column per scenario (+ 'weighted').
    """
    cols = ["uer", "hpi_growth", "gdp_growth"]
    hist = history_concepts[cols].reset_index(drop=True)
    runs: list[tuple[str, pd.DataFrame]] = list(sset.paths.items())
    if include_weighted:
        runs.append(("weighted", sset.weighted_path()))
    out: dict[str, np.ndarray] = {}
    for name, path_df in runs:
        fut = path_df[cols].reset_index(drop=True)
        spliced = pd.concat([hist, fut], ignore_index=True)
        drv = driver_frame(spliced).iloc[len(hist):]
        z = model.predict(drv)
        if not np.isfinite(z).all():
            raise ValueError(f"non-finite satellite Z on scenario '{name}'")
        out[name] = z
    zdf = pd.DataFrame(out, index=pd.RangeIndex(1, sset.horizon + 1,
                                                name="h"))
    zdf.insert(0, "period",
               next(iter(sset.paths.values()))["period"].to_numpy())
    return zdf


# ---------------------------------------------------------------------------
# PIT-conditioned hazard grids -> scenario-conditional ECL
# ---------------------------------------------------------------------------

def _hazard_grid(model: HazardModel, frame: pd.DataFrame,
                 R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(n, max R) conditional hazards, covariates frozen, age advancing.

    The SAME age-offset factorisation as the frozen engine.ecl.
    _marginal_pd_grid / engine.staging._cum_default_pd (elementwise-identical
    float operations, so the unconditioned wrapper reproduces the frozen
    engine bit-for-bit), but returning the raw hazard grid BEFORE the
    competing-risk survival combination -- the hook the Vasicek conditioning
    needs. Off-window cells are exactly 0. Returns (lam, on_mask).
    """
    ages0 = frame["loan_age"].to_numpy()
    if not np.allclose(ages0, np.round(ages0)):
        raise ValueError("loan_age must be integral quarters")
    ages0 = np.round(ages0).astype(int)
    R = np.asarray(R, dtype=int)
    if (R < 1).any():
        raise ValueError("horizons must be >= 1 (floor R upstream)")
    Tmax = int(R.max())
    max_age = int(ages0.max() + Tmax)
    beta = model.result.params.to_numpy()
    idx = _spline_cols(model)
    X = _design_matrix(model, frame)
    offset = X @ beta - X[:, idx] @ beta[idx]     # age-free, per loan
    curve = _age_curve(model, max_age)            # shared seasoning s(a)
    k = np.arange(Tmax)
    ages = ages0[:, None] + 1 + k[None, :]
    on = k[None, :] < R[:, None]
    eta = offset[:, None] + curve[ages]
    with np.errstate(over="ignore"):
        lam = np.where(on, 1.0 - np.exp(-np.exp(eta)), 0.0)
    return lam, on


def condition_hazard_grid(lam: np.ndarray, on: np.ndarray,
                          z_path: np.ndarray, rho: float) -> np.ndarray:
    """PIT-condition a hazard grid: lambda -> pit_pd(lambda, Z_h, rho).

    Applies engine.vasicek.pit_pd to the quarterly-hazard LEVELS, column k
    conditioned on Z at horizon h = k (the standard practical approximation
    -- module docstring). z_path shorter than the grid is extended by
    holding its final value (the scenario tail already sits at long-run
    means from h = 21, so the final Z IS the long-run Z). Hazards are
    clipped into (0, 1) by _PROB_EPS for the transform's domain (cells that
    under/overflowed the cloglog inverse link); off-window cells stay 0.
    """
    lam = np.asarray(lam, dtype=float)
    z = np.asarray(z_path, dtype=float).ravel()
    if z.size == 0 or not np.isfinite(z).all():
        raise ValueError("z_path must be non-empty and finite")
    T = lam.shape[1]
    if z.size < T:
        z = np.concatenate([z, np.full(T - z.size, z[-1])])
    else:
        z = z[:T]
    safe = np.clip(np.where(on, lam, 0.5), _PROB_EPS, 1.0 - _PROB_EPS)
    out = pit_pd(safe, np.broadcast_to(z[None, :], lam.shape), rho)
    return np.where(on, out, 0.0)


def scenario_ecl_for_snapshot(panel_df: pd.DataFrame, t: int, models: dict,
                              *, z_path: np.ndarray | None = None,
                              rho: float | None = None,
                              macro_means: pd.Series | Mapping | None = None,
                              staged: pd.DataFrame | None = None,
                              config: EclConfig | None = None
                              ) -> pd.DataFrame:
    """Scenario-conditional per-loan ECL at reporting quarter t.

    A COMPOSITION over the frozen Day-2 engines (never an edit): staging,
    EAD, LGD, survival algebra, EIR proxy, Stage-3 rule and output schema
    are engine.ecl.ecl_for_snapshot's own; only the default-hazard grid is
    (optionally) re-based to the composition-adjusted TTC anchor
    (macro_means) and PIT-conditioned on a scenario Z path (z_path, rho).

    Parameters
    ----------
    panel_df, t, models, config : exactly as engine.ecl.ecl_for_snapshot
        (models = {'default', 'prepay', 'lgd'}).
    z_path : per-horizon-quarter systematic factor Z_h (h = 1 aligned with
        the first projected quarter t+1); extended by its final value past
        its end. None = NO conditioning.
    rho : Vasicek asset correlation (the Belkin-calibrated value); required
        with z_path.
    macro_means : mapping for HAZARD_MACRO_COLS -> TTC macro state; when
        given, the DEFAULT hazard baseline is scored at these values (the
        anchor Z was recovered against). None = snapshot macros (frozen
        rung-1 behaviour). The prepay hazard always uses snapshot values.
    staged : optional precomputed engine.staging.assign_stages table for
        the snapshot (staging is scenario-invariant here -- module
        docstring), so per-scenario calls do not recompute it.

    With z_path=None, macro_means=None this reproduces the frozen
    ecl_for_snapshot exactly (gated + unit-tested).
    """
    cfg = config if config is not None else EclConfig()
    for key in ("default", "prepay", "lgd"):
        if key not in models:
            raise KeyError(f"models dict must contain '{key}'")
    if z_path is not None and rho is None:
        raise ValueError("rho is required when z_path is given")
    hz = {"default": models["default"], "prepay": models["prepay"]}
    t = int(t)
    hist = panel_df.loc[panel_df["time"] <= t]
    if not (hist["time"] == t).any():
        raise ValueError(f"no rows at time {t}")
    if staged is None:
        staged = assign_stages(hist, hz, cfg.staging, snapshot_time=t)

    snap = (hist.loc[hist["time"] == t]
            .sort_values("id").reset_index(drop=True))
    if snap["id"].duplicated().any():
        raise ValueError(f"duplicate loan ids at time {t}")
    snap = snap.loc[snap["payoff_event"] == 0].reset_index(drop=True)
    if snap.empty:
        raise ValueError(f"no stageable (non-payoff) rows at time {t}")
    snap = snap.merge(
        staged[["id", "stage", "trigger_reason", "lifetime_pd_now",
                "lifetime_pd_orig", "pd_ratio"]],
        on="id", how="left", validate="one_to_one")
    if snap["stage"].isna().any():
        raise RuntimeError("staging table did not cover every snapshot loan")

    R = np.maximum(snap["mat_time"].to_numpy(dtype=int) - t, 1)
    if cfg.max_horizon is not None:
        R = np.minimum(R, int(cfg.max_horizon))
    Tmax = int(R.max())

    frame_d = snap
    if macro_means is not None:
        frame_d = snap.copy()
        for c in HAZARD_MACRO_COLS:
            frame_d[c] = float(macro_means[c])
    lam_d, on = _hazard_grid(hz["default"], frame_d, R)
    lam_p, _ = _hazard_grid(hz["prepay"], snap, R)
    if z_path is not None:
        lam_d = condition_hazard_grid(lam_d, on, z_path, float(rho))

    surv_start, marginal = _survival_marginal(lam_d, lam_p)
    ead_g = ead_matrix(snap[SNAPSHOT_COLS], Tmax).to_numpy()   # contractual
    lgd_g = _lgd_grid(models["lgd"], snap, Tmax)               # age clock
    comp0 = predict_components(models["lgd"], snap)            # default-now

    rate = snap["interest_rate_time"].to_numpy(dtype=float)
    usable = np.isfinite(rate) & (rate > 0.0)
    eir_q = np.where(usable, rate, 0.0) / RATE_DIVISOR
    periods = np.arange(1, Tmax + 1, dtype=float)
    discount = (1.0 + eir_q)[:, None] ** -periods[None, :]

    cells = marginal * lgd_g * ead_g * discount               # THE formula
    q12 = min(int(cfg.quarters_12m), Tmax)
    ecl_12m = cells[:, :q12].sum(axis=1)
    ecl_life = cells.sum(axis=1)

    balance = snap["balance_time"].to_numpy(dtype=float)
    lgd_now = comp0["lgd"].to_numpy()
    is_def = snap["default_event"].to_numpy() == 1
    stage = snap["stage"].to_numpy().astype(int)
    if not np.array_equal(is_def, stage == 3):
        raise RuntimeError("stage-3 rows must be exactly the default rows")
    s3 = lgd_now * balance
    ecl_12m = np.where(is_def, s3, ecl_12m)
    ecl_life = np.where(is_def, s3, ecl_life)
    reported = np.where(stage == 1, ecl_12m, ecl_life)

    if not (np.all(np.isfinite(ecl_life)) and np.all(ecl_12m >= 0.0)
            and np.all(ecl_12m <= ecl_life + 1e-9 * np.maximum(ecl_life, 1))):
        raise AssertionError("ECL sanity violated: need 0 <= 12m <= lifetime")

    return pd.DataFrame({
        "id": snap["id"].to_numpy(),
        "time": t,
        "stage": stage,
        "trigger_reason": snap["trigger_reason"].to_numpy(),
        "loan_age": snap["loan_age"].to_numpy(),
        "R": R,
        "balance": balance,
        "eir_q": eir_q,
        "lgd_current": lgd_now,
        "lifetime_pd_now": snap["lifetime_pd_now"].to_numpy(),
        "lifetime_pd_engine": marginal.sum(axis=1),
        "pd_ratio": snap["pd_ratio"].to_numpy(),
        "default_event": snap["default_event"].to_numpy(),
        "ecl_12m": ecl_12m,
        "ecl_lifetime": ecl_life,
        "ecl_reported": reported,
        "coverage": np.divide(reported, balance,
                              out=np.full_like(reported, np.nan),
                              where=balance > 0.0),
    })
