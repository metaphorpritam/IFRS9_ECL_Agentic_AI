"""IFRS 9 SICR staging -- the RELATIVE deterioration test (notes section 2.2).

METHODOLOGY (knowledge/sources/ifrs9_credit_risk_notes.md section 2)
----------------------------------------------------------------------
SICR is a *relative deterioration* test, not an absolute credit-quality test:
compare the lifetime PD over the REMAINING life at the reporting date with the
lifetime PD expected FOR THAT SAME PERIOD at initial recognition. A loan
originated risky and still equally risky has NOT suffered SICR.

For a loan observed at reporting quarter t (end-of-quarter convention):

    R                = mat_time - t          remaining contractual life, in
                                             quarters (floored at 1: a handful
                                             of rows sit at/past scheduled
                                             maturity while still on book --
                                             they get a one-quarter window)
    lifetime_pd_now  = cumulative default PD over quarters t+1 .. t+R,
                       loan ages age_t+1 .. age_t+R, computed from the
                       competing-risk hazard engine (engine/hazard.py
                       pd_term_structure conventions) with covariates FROZEN
                       at their CURRENT (time-t) values
    lifetime_pd_orig = cumulative default PD over the SAME quarters and the
                       SAME ages, with covariates frozen at their ORIGINATION
                       values (below) -- i.e. what the model would have
                       projected for exactly this window at initial
                       recognition

Both PDs live on the identical age window and identical competing-risk
survival algebra, so their ratio isolates covariate deterioration
(collateral, macro, refinancing moneyness) from seasoning: the age baseline
is common to numerator and denominator projections.

TIMING CONVENTION (inherits engine/hazard.py's binding section): the
reporting date is the END of quarter t; the row's own event flags for quarter
t are known (a default row is Stage 3, not a projection). The first projected
quarter is t+1 at age age_t + 1, matching pd_term_structure's "loan_age is
the age in the FIRST projected quarter". All macro covariates enter as the
panel's lagged columns; no lookahead is introduced anywhere in this module --
origination covariates reference only quarters <= orig_time (up to the
flagged clamp below).

ORIGINATION-COVARIATE RECONSTRUCTION (per-loan, from panel columns)
----------------------------------------------------------------------
    updated_ltv      -> LTV_orig_time      (the contractual origination LTV.
                                            The panel's updated-LTV formula
                                            collapses to it at origination
                                            GIVEN balance_time = original
                                            balance; DCR's first observed
                                            balance deviates for ~22% of
                                            age-0 rows -- median |gap| 0.2pp,
                                            1% tail large -- so the
                                            CONTRACTUAL LTV is the initial-
                                            recognition benchmark, not the
                                            first observed panel row)
    FICO / occupancy / property flags       unchanged (origination snapshots)
    prepay_incentive -> Interest_Rate_orig_time - market_rate(orig_time)
                        where market_rate(q) is the panel's per-quarter MEDIAN
                        rate_time (rate_time varies mildly across loans within
                        a quarter, so a median map is a documented
                        approximation). If the origination note rate is
                        missing-coded (orig_rate_missing == 1) the CURRENT
                        note rate substitutes -- flagged per loan in
                        orig_rate_proxy (mostly fixed-rate loans, so the
                        current note rate is a good proxy for the origination
                        one).
    uer_lag1         -> uer(orig_time - 1)
    uer_chg4_lag1    -> uer(orig_time - 1) - uer(orig_time - 5)
    gdp_lag1         -> gdp(orig_time - 1)
    hpi_growth_lag1  -> ln hpi(orig_time - 1) - ln hpi(orig_time - 2)
  from the panel-internal time -> macro map (macros are national, verified
  constant within quarter by the panel build). FLAGGED APPROXIMATION: for
  loans originated before the macro window (orig_time - 5 < first panel
  quarter; ~2-4% of snapshot rows -- left-truncated seasoned entrants) the
  referenced quarter is clamped to the earliest available one, i.e. the
  earliest observed macro proxies the pre-window macro. Such loans carry
  orig_macro_approx = True in the output so downstream governance can
  quarantine them.

STAGE RULE (StagingConfig; defaults follow the notes' conventions)
----------------------------------------------------------------------
  Stage 3   default rows (default_event == 1 at the reporting quarter). The
            panel truncates histories at the first terminal event, so Stage-3
            share at a snapshot equals that quarter's default incidence by
            construction.
  Stage 2   quantitative SICR trigger, EBA-style doubling convention:
                lifetime_pd_now > ratio_threshold * lifetime_pd_orig   (2.0x)
            AND an absolute add-on so tiny PDs cannot flip stages on noise:
                ann_pd_now - ann_pd_orig > abs_addon    (0.5pp ANNUALISED)
            where ann_pd = 1 - (1 - lifetime_pd)^(4/R) is the per-annum
            default probability equivalent to the R-quarter lifetime PD
            (documented conversion: R quarters = R/4 years; the annualised
            basis makes one add-on threshold comparable across loans with
            different remaining lives).
            OR the 30-days-past-due backstop -- see LOUD note below.
  Stage 1   everything else.

  >>> BACKSTOP IS STRUCTURALLY INERT ON THIS DATASET <<<
  IFRS 9's rebuttable presumption of SICR at 30 DPD requires a delinquency
  ladder. The Deep Credit Risk panel's status is only performing / default /
  payoff -- NO 30/60/90 DPD states exist, so the backstop hook
  (config.backstop_30dpd, config.dpd_col) can never fire here. The hook is
  implemented and tested for the day a dpd column exists; its absence today
  is a DOCUMENTED SIMPLIFICATION, not an implementation choice: Stage-2
  populations below are quantitative-trigger-only and would be strictly
  larger with a live 30-DPD backstop.

  PROBATION / CURE: transfer back to Stage 1 requires the trigger to have
  been off for cure_quarters consecutive quarters. Because the quantitative
  trigger is a pure function of the quarter's covariates (memoryless), the
  sticky state machine is EXACTLY equivalent to the stateless window rule
  "Stage 2 iff the trigger fired at any of t, t-1, .., t-(cure_quarters-1)",
  which is what assign_stages evaluates (it scores the trigger on the
  history rows present in the input frame). Missing history rows (loan
  entered at t, within-loan gap, or a single-quarter input frame) contribute
  no trigger -- with a pure snapshot frame probation degrades gracefully to
  the raw trigger, documented behaviour.

PERFORMANCE STRATEGY (documented; exactness cross-checked)
----------------------------------------------------------------------
Naively each loan needs a pd_term_structure call over up to ~190 quarters,
twice (now / origination scenarios): O(n_loans * horizon) GLM design builds.
Because loan_age enters the hazard ONLY through the cr() spline basis and
every other covariate is frozen over the projection, the cloglog linear
predictor SEPARATES:

    eta_i(a) = s(a) + c_i,   s(a)  = spline-basis columns  @ beta_spline
                             c_i   = the loan's frozen-covariate offset

so the whole snapshot needs ONE design-matrix build per cause on the n
snapshot rows (for the offsets c_i) plus ONE on the shared integer age grid
(for s(a)) -- O(n_loans + n_ages) instead of O(n_loans * horizon). Hazards,
competing-risk survival and cumulative PD are then pure numpy on an
(n_loans x max_R) grid. This is an EXACT factorisation, not an
approximation: crosscheck_term_structure() re-computes a fixed-seed sample
of loans through pd_term_structure row-by-row and both the test suite and
the analysis harness assert agreement to ~1e-10 (observed ~6e-16). The
survival fan is chunked over loans (_CHUNK_LOANS = 8192), so peak memory is
a few (8192 x max_R) float arrays (~13 MB each at R~200) regardless of book
size; the full 49,974-loan panel benchmark runs both legs in under a second.

DOCUMENTED SIMPLIFICATIONS (also surfaced in outputs/staging/staging_report.md)
----------------------------------------------------------------------
  * Frozen-covariate projections on both legs (rung-1 tail assumption
    inherited from pd_term_structure): no macro path, no LTV amortisation.
    Scenario conditioning arrives with the satellite-model rung.
  * 30-DPD backstop inert (no delinquency ladder in DCR) -- see above.
  * No low-credit-risk (investment-grade) exemption: retail mortgage book,
    the exemption is a bond-book device and would only relabel loans the
    quantitative test already leaves in Stage 1.
  * No qualitative triggers (watchlist / forbearance flags do not exist in
    the dataset).
  * Origination macro clamp and median-market-rate approximations, flagged
    per loan (orig_macro_approx, orig_rate_proxy).
  * Loans at/past scheduled maturity while still alive (R <= 0; a handful of
    rows) get a floored one-quarter window rather than an exception.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from patsy import build_design_matrices

from engine.hazard import (
    REQUIRED_COLS,
    HazardModel,
    _prepare,
    pd_term_structure,
)

#: same per-period exit-probability cap as pd_term_structure
_EXIT_CAP = 0.999999

#: loans per numpy chunk in _cum_default_pd (memory bound; result-invariant)
_CHUNK_LOANS = 8192

#: panel columns lifetime_pd_table needs beyond REQUIRED_COLS
_PANEL_COLS = [
    "id", "time", "orig_time", "mat_time", "loan_age",
    "LTV_orig_time", "Interest_Rate_orig_time", "interest_rate_time",
    "orig_rate_missing", "default_event", "payoff_event",
]


@dataclass(frozen=True)
class StagingConfig:
    """SICR staging thresholds (module docstring for the rule they drive).

    ratio_threshold : lifetime-PD ratio trigger; 2.0 = the doubling
        convention (EBA 2018 stress-test methodology).
    abs_addon : absolute add-on on the ANNUALISED lifetime PD, decimal
        (0.005 = 0.5pp p.a.); annualisation ann = 1 - (1-PD_life)^(4/R).
    cure_quarters : consecutive trigger-free quarters required before a
        Stage-2 loan returns to Stage 1 (probation).
    backstop_30dpd / dpd_col : the 30-DPD rebuttable presumption hook.
        INERT on the DCR panel -- no delinquency ladder exists (module
        docstring, loud note). Fires only if dpd_col is present.
    max_horizon : optional cap on the remaining-life window R (quarters).
        Both PD legs use the SAME window, so a cap is SICR-neutral in the
        ratio; None (default) = full contractual remaining life.
    """

    ratio_threshold: float = 2.0
    abs_addon: float = 0.005
    cure_quarters: int = 2
    backstop_30dpd: bool = True
    dpd_col: str = "dpd_time"
    max_horizon: int | None = None


# ---------------------------------------------------------------------------
# macro map + origination covariates
# ---------------------------------------------------------------------------

def build_macro_map(panel_df: pd.DataFrame) -> pd.DataFrame:
    """Per-quarter national macro map from the panel itself.

    uer/gdp/hpi are national series, constant across loans within a quarter
    (verified in the panel build), so first() is exact. rate_time varies
    mildly across loans within a quarter; the MEDIAN defines the market-rate
    map used for the origination prepayment incentive (documented
    approximation). Index: contiguous quarters min(time)..max(time).
    """
    g = panel_df.groupby("time")
    out = pd.DataFrame({
        "uer": g["uer_time"].first(),
        "gdp": g["gdp_time"].first(),
        "hpi": g["hpi_time"].first(),
        "rate_med": g["rate_time"].median(),
    })
    full = np.arange(out.index.min(), out.index.max() + 1)
    out = out.reindex(full)
    if out.isna().any().any():
        raise ValueError("macro map has gaps: quarters missing from panel_df")
    return out


def origination_covariates(snapshot_df: pd.DataFrame,
                           macro_map: pd.DataFrame) -> pd.DataFrame:
    """Rebuild the hazard covariates as they stood at initial recognition.

    Returns a frame aligned to snapshot_df with REQUIRED_COLS (loan_age kept
    at the CURRENT age -- the projection window is the same for both legs and
    the frozen-covariate offset is age-independent) plus the two
    approximation flags orig_macro_approx / orig_rate_proxy (module
    docstring).
    """
    o = snapshot_df["orig_time"].to_numpy()
    tmin, tmax = int(macro_map.index.min()), int(macro_map.index.max())

    def series(name: str, lag: int) -> np.ndarray:
        pos = np.clip(o - lag, tmin, tmax) - tmin
        return macro_map[name].to_numpy()[pos]

    orig_rate_missing = snapshot_df["orig_rate_missing"].to_numpy() == 1
    note0 = np.where(orig_rate_missing,
                     snapshot_df["interest_rate_time"].to_numpy(),
                     snapshot_df["Interest_Rate_orig_time"].to_numpy())
    out = pd.DataFrame({
        "loan_age": snapshot_df["loan_age"].to_numpy(),
        "FICO_orig_time": snapshot_df["FICO_orig_time"].to_numpy(),
        "updated_ltv": snapshot_df["LTV_orig_time"].to_numpy(),
        "prepay_incentive": note0 - series("rate_med", 0),
        "investor_orig_time": snapshot_df["investor_orig_time"].to_numpy(),
        "REtype_CO_orig_time": snapshot_df["REtype_CO_orig_time"].to_numpy(),
        "REtype_PU_orig_time": snapshot_df["REtype_PU_orig_time"].to_numpy(),
        "REtype_SF_orig_time": snapshot_df["REtype_SF_orig_time"].to_numpy(),
        "uer_lag1": series("uer", 1),
        "uer_chg4_lag1": series("uer", 1) - series("uer", 5),
        "gdp_lag1": series("gdp", 1),
        "hpi_growth_lag1": np.log(series("hpi", 1)) - np.log(series("hpi", 2)),
        # deepest reference is orig_time - 5: clamped iff it precedes the map
        "orig_macro_approx": (o - 5) < tmin,
        "orig_rate_proxy": orig_rate_missing,
    }, index=snapshot_df.index)
    return out


# ---------------------------------------------------------------------------
# vectorised competing-risk lifetime PD (exact factorisation; module docstring)
# ---------------------------------------------------------------------------

def _design_matrix(model: HazardModel, frame: pd.DataFrame) -> np.ndarray:
    """Training design matrix for new rows; NaN-safe (raises, never drops)."""
    prep = _prepare(frame)
    bad = int(prep[REQUIRED_COLS].isna().any(axis=1).sum())
    if bad:
        raise ValueError(
            f"{bad} scoring rows carry NaN in required covariates "
            "(lag-warm-up quarter? staging needs time >= 6)")
    di = model.result.model.data.design_info
    X = np.asarray(build_design_matrices([di], prep)[0], dtype=float)
    if X.shape[0] != len(prep):   # patsy NAAction would silently drop rows
        raise RuntimeError("design matrix dropped rows; misaligned scoring")
    return X


def _spline_cols(model: HazardModel) -> list[int]:
    names = model.result.model.data.design_info.column_names
    return [i for i, c in enumerate(names) if c.startswith("cr(loan_age")]


def _age_curve(model: HazardModel, max_age: int) -> np.ndarray:
    """s(a) = spline-basis contribution to the linear predictor, a=0..max_age.

    Non-age covariates are dummies: their design columns do not touch the
    cr(loan_age) columns, so any finite values give the identical s(a).
    """
    ages = np.arange(max_age + 1, dtype=float)
    grid = pd.DataFrame({c: np.ones(len(ages)) for c in REQUIRED_COLS
                         if c != "loan_age"})
    grid["loan_age"] = ages
    X = _design_matrix(model, grid)
    idx = _spline_cols(model)
    beta = model.result.params.to_numpy()
    return X[:, idx] @ beta[idx]


def _cum_default_pd(models: dict[str, HazardModel], frame: pd.DataFrame,
                    horizons: np.ndarray) -> np.ndarray:
    """Cumulative competing-risk default PD over per-loan horizons.

    frame: one row per loan with REQUIRED_COLS; loan_age = age at the
    reporting quarter (projection starts at loan_age + 1). horizons: per-loan
    R >= 1 in quarters. Reproduces pd_term_structure's algebra exactly
    (per-period exit = lambda_d + lambda_p capped at _EXIT_CAP, survival
    cumprod, marginal = S(t-1) * lambda_d) via the linear-predictor
    factorisation in the module docstring.
    """
    ages0 = frame["loan_age"].to_numpy()
    if not np.allclose(ages0, np.round(ages0)):
        raise ValueError("loan_age must be integral quarters")
    ages0 = np.round(ages0).astype(int)
    R = np.asarray(horizons, dtype=int)
    if (R < 1).any():
        raise ValueError("horizons must be >= 1 (floor R upstream)")
    # the age matrix below indexes s[] up to ages0[i] + max(R) for EVERY loan
    # (masked cells included -- np.where evaluates both branches), so the
    # shared curve must extend to ages0.max() + R.max(), not (ages0+R).max()
    max_age = int(ages0.max() + R.max())
    offsets, curves = {}, {}
    for name in ("default", "prepay"):
        m = models[name]
        beta = m.result.params.to_numpy()
        idx = _spline_cols(m)
        X = _design_matrix(m, frame)
        offsets[name] = X @ beta - X[:, idx] @ beta[idx]  # age-free, per loan
        curves[name] = _age_curve(m, max_age)             # shared seasoning
    # chunk over loans: peak memory is a few (chunk x max_R) float arrays
    out = np.empty(len(R), dtype=float)
    for lo in range(0, len(R), _CHUNK_LOANS):
        sl = slice(lo, min(lo + _CHUNK_LOANS, len(R)))
        a0, r = ages0[sl], R[sl]
        k = np.arange(int(r.max()))
        ages = a0[:, None] + 1 + k[None, :]        # age in projected quarter
        on = k[None, :] < r[:, None]               # inside the loan's window
        lam = {}
        for name in ("default", "prepay"):
            eta = offsets[name][sl][:, None] + curves[name][ages]
            # cloglog inverse saturates: exp overflow at extrapolated ages
            # just means lambda -> 1 (then capped); silence the benign warning
            with np.errstate(over="ignore"):
                lam[name] = np.where(on, 1.0 - np.exp(-np.exp(eta)), 0.0)
        exit_p = np.clip(lam["default"] + lam["prepay"], 0.0, _EXIT_CAP)
        surv = np.cumprod(1.0 - exit_p, axis=1)
        surv_prev = np.hstack([np.ones((len(r), 1)), surv[:, :-1]])
        out[sl] = (surv_prev * lam["default"]).sum(axis=1)
    return out


# ---------------------------------------------------------------------------
# lifetime-PD table, trigger, stages
# ---------------------------------------------------------------------------

def lifetime_pd_table(panel_df: pd.DataFrame, models: dict[str, HazardModel],
                      at_time: int, macro_map: pd.DataFrame | None = None,
                      config: StagingConfig | None = None) -> pd.DataFrame:
    """Per-loan lifetime PD now vs at initial recognition, same window.

    One row per loan-quarter row of panel_df at time == at_time, in id order:
    R (effective window, floored at 1 and optionally capped), lifetime and
    annualised PDs on both legs, pd_ratio, ann_addon, approximation flags,
    and the snapshot's event flags. panel_df should carry enough history for
    the macro map (pass rows with time <= at_time; a pure snapshot frame
    degrades the origination-macro clamp, flagged per loan).
    """
    cfg = config or StagingConfig()
    snap = (panel_df.loc[panel_df["time"] == at_time]
            .sort_values("id").reset_index(drop=True))
    if snap.empty:
        raise ValueError(f"no rows at time {at_time}")
    if snap["id"].duplicated().any():
        raise ValueError(f"duplicate loan ids at time {at_time}")
    mm = macro_map if macro_map is not None else build_macro_map(panel_df)

    R = np.maximum((snap["mat_time"] - at_time).to_numpy(), 1)
    if cfg.max_horizon is not None:
        R = np.minimum(R, cfg.max_horizon)
    orig = origination_covariates(snap, mm)
    pd_now = _cum_default_pd(models, snap, R)
    pd_orig = _cum_default_pd(models, orig, R)
    years = R / 4.0
    ann_now = 1.0 - (1.0 - pd_now) ** (1.0 / years)
    ann_orig = 1.0 - (1.0 - pd_orig) ** (1.0 / years)
    out = pd.DataFrame({
        "id": snap["id"].to_numpy(),
        "time": at_time,
        "loan_age": snap["loan_age"].to_numpy(),
        "R": R,
        "lifetime_pd_now": pd_now,
        "lifetime_pd_orig": pd_orig,
        "ann_pd_now": ann_now,
        "ann_pd_orig": ann_orig,
        # ratio conventions at the boundary: x/0 -> inf (infinite relative
        # deterioration), 0/0 -> 1 (no deterioration; degenerate one-quarter
        # windows where both hazards underflow)
        "pd_ratio": np.where(pd_orig > 0.0,
                             pd_now / np.where(pd_orig > 0.0, pd_orig, 1.0),
                             np.where(pd_now > 0.0, np.inf, 1.0)),
        "ann_addon": ann_now - ann_orig,
        "orig_macro_approx": orig["orig_macro_approx"].to_numpy(),
        "orig_rate_proxy": orig["orig_rate_proxy"].to_numpy(),
        "default_event": snap["default_event"].to_numpy(),
        "payoff_event": snap["payoff_event"].to_numpy(),
    })
    # carry the backstop input: cfg.dpd_col FIRST (it is what
    # _backstop_30dpd reads under this config), plus the default-named
    # column if it also exists so a cached table restaged under the default
    # config still finds its input
    for col in dict.fromkeys([cfg.dpd_col, StagingConfig().dpd_col]):
        if col in snap.columns:
            out[col] = snap[col].to_numpy()
    return out


def quantitative_sicr(pd_table: pd.DataFrame,
                      config: StagingConfig | None = None) -> np.ndarray:
    """Ratio-AND-add-on quantitative SICR trigger (bool per table row)."""
    cfg = config or StagingConfig()
    return ((pd_table["pd_ratio"].to_numpy() > cfg.ratio_threshold)
            & (pd_table["ann_addon"].to_numpy() > cfg.abs_addon))


def _backstop_30dpd(pd_table: pd.DataFrame,
                    cfg: StagingConfig) -> np.ndarray:
    """30-DPD rebuttable-presumption hook. INERT on DCR: no dpd column
    exists (no delinquency ladder), so this returns all-False today --
    documented loudly in the module docstring."""
    if cfg.backstop_30dpd and cfg.dpd_col in pd_table.columns:
        return pd_table[cfg.dpd_col].to_numpy() >= 30
    return np.zeros(len(pd_table), dtype=bool)


def assign_stages(panel_df: pd.DataFrame, models: dict[str, HazardModel],
                  config: StagingConfig | None = None,
                  snapshot_time: int | None = None,
                  pd_tables: dict[int, pd.DataFrame] | None = None,
                  ) -> pd.DataFrame:
    """IFRS 9 stage per live loan at the reporting quarter.

    Parameters
    ----------
    panel_df : loan-quarter rows; must contain the snapshot quarter and
        should contain history (time <= snapshot) so the origination macro
        map and the probation lookback have data. NEVER uses rows after
        snapshot_time.
    models : {'default': HazardModel, 'prepay': HazardModel} (engine.hazard).
    config : StagingConfig (defaults = doubling + 0.5pp p.a. add-on,
        2-quarter probation, inert 30-DPD hook).
    snapshot_time : reporting quarter; default = max(time) in panel_df.
    pd_tables : optional {quarter: lifetime_pd_table(...)} cache so threshold
        sweeps (governance sensitivity) do not recompute the PDs.

    Returns the snapshot lifetime-PD table plus:
        stage           1 / 2 / 3
        trigger_reason  'default' | 'backstop_30dpd' | 'sicr_quantitative'
                        | 'sicr_probation' (history trigger only) | 'none'
    """
    cfg = config or StagingConfig()
    t = int(snapshot_time if snapshot_time is not None
            else panel_df["time"].max())
    hist = panel_df.loc[panel_df["time"] <= t]
    window = [t - k for k in range(max(1, cfg.cure_quarters))]
    tables: dict[int, pd.DataFrame] = dict(pd_tables or {})
    need = [u for u in window if u not in tables
            and (u == t or (hist["time"] == u).any())]
    if need:
        mm = build_macro_map(hist)
        for u in need:
            tables[u] = lifetime_pd_table(hist, models, u, mm, cfg)

    tbl = tables[t].copy()
    trig_now = quantitative_sicr(tbl, cfg)
    backstop = _backstop_30dpd(tbl, cfg)
    trig_hist = np.zeros(len(tbl), dtype=bool)
    for u in window:
        if u == t or u not in tables:
            continue
        tu = tables[u]
        fired = set(tu.loc[quantitative_sicr(tu, cfg), "id"])
        trig_hist |= tbl["id"].isin(fired).to_numpy()

    is_default = tbl["default_event"].to_numpy() == 1
    sicr = trig_now | trig_hist | backstop
    stage = np.where(is_default, 3, np.where(sicr, 2, 1))
    reason = np.select(
        [is_default, backstop, trig_now, trig_hist],
        ["default", "backstop_30dpd", "sicr_quantitative", "sicr_probation"],
        default="none")
    tbl["stage"] = stage
    tbl["trigger_reason"] = reason
    return tbl


# ---------------------------------------------------------------------------
# exactness cross-check of the factorised fast path
# ---------------------------------------------------------------------------

def crosscheck_term_structure(panel_df: pd.DataFrame,
                              models: dict[str, HazardModel], at_time: int,
                              n_sample: int = 25, seed: int = 0) -> float:
    """Max |fast-path PD - pd_term_structure PD| over a fixed-seed sample.

    Re-derives lifetime_pd_now and lifetime_pd_orig for n_sample loans by
    calling engine.hazard.pd_term_structure loan-by-loan (the slow reference
    path) and compares against lifetime_pd_table. Deterministic (fixed seed).
    Expected ~1e-12 (identical algebra; module docstring PERFORMANCE
    STRATEGY).
    """
    hist = panel_df.loc[panel_df["time"] <= at_time]
    mm = build_macro_map(hist)
    tbl = lifetime_pd_table(hist, models, at_time, mm)
    snap = (hist.loc[hist["time"] == at_time]
            .sort_values("id").reset_index(drop=True))
    orig = origination_covariates(snap, mm)
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(tbl), size=min(n_sample, len(tbl)), replace=False)
    worst = 0.0
    for i in pick:
        horizon = int(tbl.loc[i, "R"])
        for leg, frame in (("lifetime_pd_now", snap), ("lifetime_pd_orig",
                                                       orig)):
            prof = frame.iloc[[i]][REQUIRED_COLS].copy()
            prof["loan_age"] = prof["loan_age"] + 1.0   # first projected qtr
            ts = pd_term_structure(models, prof, horizon)
            ref = float(ts["cum_pd"].iloc[-1])
            worst = max(worst, abs(ref - float(tbl.loc[i, leg])))
    return worst
