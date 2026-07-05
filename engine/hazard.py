"""Discrete-time cloglog hazard PD model with competing-risk prepayment.

METHODOLOGY (knowledge/sources/ifrs9_credit_risk_notes.md section 6.2)
----------------------------------------------------------------------
Grouped-duration cloglog. On a loan-quarter panel, the discrete hazard
lambda(t | x_it) = P(T_i = t | T_i >= t, x_it) is fitted as a binary GLM on
at-risk rows with the complementary log-log link:

    cloglog lambda = ln(-ln(1 - lambda)) = alpha(age) + x_it' beta + gamma' m_t

The cloglog link is the EXACT grouped-duration analogue of the continuous-time
Cox proportional-hazards model: if the underlying continuous-time hazard is
proportional (h = h0 * exp(x'beta)) and we only observe interval (quarterly)
survival, the implied discrete-time model is a binomial GLM with cloglog link
and the same beta. exp(beta) is therefore a genuine hazard ratio.

alpha(age) is the baseline age (seasoning) effect, entered as a natural cubic
spline of loan_age -- patsy cr(loan_age, df=5). df=5 gives the curve enough
flexibility to reproduce the retail "seasoning hump" (rise over the first ~2-3
years on book, then decay) without chasing noise; natural cubic splines are
LINEAR beyond the boundary knots, which is the disciplined choice for the
lifetime-PD extrapolation the term structure needs (notes section 6.2:
extrapolation is a flagged model-risk area -- the tail assumption here is
"log-hazard linear in age beyond the observed-age support", plus frozen
covariates; see pd_term_structure).

COMPETING RISKS: cause-specific hazards. Prepayment (status 2) and default
(status 1) compete for the same loan. Each cause-specific hazard is estimated
by treating the OTHER event's occurrence as censoring -- the loan's rows simply
end at the competing event; the competing-event row itself carries y = 0 for
this cause. No special weighting, subdistribution adjustment, or IPCW is
applied: with cause-specific hazards estimated on at-risk rows, the likelihood
factorises across causes and two separate binomial GLMs are the maximum-
likelihood estimator (this is what the notes mean by "estimate cause-specific
hazards"). The two hazards are recombined in pd_term_structure, where survival
requires escaping BOTH exits:  S(t) = prod_{k<=t} (1 - lambda_def_k - lambda_pre_k).

CENSORING / TRUNCATION (first-class, per the build plan):
* Right censoring (loans alive at the end of the window) is handled by
  construction -- censored loans contribute y = 0 at-risk rows and then stop;
  the binomial likelihood on at-risk rows is exactly the discrete-time
  survival likelihood under non-informative censoring.
* Left truncation (orig_time < first observation; loans enter the window
  already seasoned) is handled the same way: a loan entering at age a simply
  contributes at-risk rows from age a onward, which is the correct
  conditional-on-survival-to-entry likelihood for discrete-time hazards.
* Rows after a loan's first terminal event were removed in the panel build
  (data/panel/build_panel.py waterfall).

UNIT / TARGETS: unit = loan-quarter; y = default_event for the default hazard,
y = payoff_event for the prepayment hazard.

COVARIATES (fixed specification; scalings chosen for hazard-ratio readability):
  cr(loan_age, df=5)      baseline seasoning curve
  fico_s                  FICO_orig_time / 100  (HR per 100 FICO points)
  ltv10                   updated_ltv / 10      (HR per 10pp of current LTV;
                          updated_ltv = balance_time-amortised, HPI-indexed
                          collateral LTV built in the panel; uses the CURRENT
                          quarter's HPI -- accepted collateral indexation, see
                          TIMING CONVENTION below)
  prepay_incentive        interest_rate_time - rate_time (pp) -- the note rate
                          vs the CURRENT market rate; the star prepayment
                          driver (accepted state-variable exception, see
                          TIMING CONVENTION below)
  investor_orig_time, REtype_{CO,PU,SF}_orig_time   occupancy / property type
                          flags (baseline: owner-occupied "other" RE type; the
                          three RE flags are mutually exclusive in the data)
  uer_lag1, uer_chg4_lag1 unemployment level and its 4-quarter change, lagged
                          one quarter inside the panel (no lookahead)
  hpi_growth_lag1         lagged one-quarter log HPI growth
  gdp_lag1                lagged GDP growth
  center(ltv10):center(uer_lag1)
                          the DOUBLE-TRIGGER interaction: mortgage default
                          requires both negative equity (ability-to-sell lost)
                          and a cash-flow shock (unemployment); the interaction
                          lets the LTV slope steepen when labour markets crack.
                          The components are CENTERED (patsy stateful center(),
                          training means memorised for prediction). Centering
                          is an exact reparametrisation -- the interaction
                          coefficient itself is IDENTICAL to the uncentered
                          x*y coefficient -- but (a) it removes the near-
                          collinearity between x*y and its main effects that
                          destabilised IRLS on this data, and (b) it makes the
                          main-effect coefficients directly interpretable as
                          marginal effects AT THE TRAINING MEAN of the partner
                          variable (ltv10 = LTV slope at mean unemployment).

TIMING CONVENTION (no contemporaneous MACRO REGRESSORS; two indexed
STATE VARIABLES are deliberate exceptions):
  * All macro regressors -- uer_lag1, uer_chg4_lag1, hpi_growth_lag1,
    gdp_lag1 -- enter LAGGED (publication delay + transmission; built inside
    the panel with groupby(id).shift semantics, gap-safe, only t-k (k>=1)
    values referenced; see data/panel/build_panel.py). No contemporaneous
    macro aggregate appears anywhere in the specification.
  * updated_ltv indexes the collateral value by the CURRENT quarter's HPI.
    This is deliberate and acceptable: it is collateral indexation -- a
    loan-level STATE variable (the live collateral cover that defines the
    negative-equity trigger), not a macro regressor. The macro cycle as a
    systematic driver enters only through the lagged regressors above.
  * prepay_incentive compares the note rate to the CURRENT quarter's market
    rate (rate_time). Same class of exception: the incentive is the
    moneyness of the borrower's prepayment option, a loan-level state
    variable, and market rates -- unlike the UER/GDP/HPI aggregates -- are
    observable in real time with no publication lag, so the current-quarter
    rate is in the information set when the quarter's prepayment decision is
    made. Lagging it would misprice the option against the standard
    prepayment literature. (Residual caveat, accepted: rate_time is a
    within-quarter average, so it partially overlaps the event window.)

Rows in the lag warm-up window (lag_warmup == 1, i.e. time < 6) are dropped
at fit time because the 4-quarter unemployment change is undefined there.

DOCUMENTED DEVIATIONS / NUMERICAL SAFEGUARDS
  * LTV winsorisation: updated_ltv is capped at LTV_CAP = 300 (%) in _prepare,
    at fit AND predict time. 18 of 418,418 training rows exceed the cap (up to
    777% -- residual tiny-balance / data-noise artefacts). Justification: the
    cloglog inverse link saturates (mu -> 1) once the linear predictor passes
    ~ +1, and statsmodels' IRLS has no step-halving -- a handful of eta ~ +15
    rows sent the weights, then the whole fit, to overflow. Capping is the
    standard treatment for pathological LTVs in mortgage PD models and changes
    the economics of 0.004% of rows.
  * Warm start: IRLS is started from the same-formula LOGIT solution. For
    rare events (quarterly hazard ~ 2.7%) the two links agree to first order,
    so the logit optimum sits inside the cloglog basin of attraction; from the
    default start the cloglog IRLS diverged. Convergence is asserted --
    a non-converged fit raises rather than returning silently.

Estimation: statsmodels GLM Binomial(CLogLog), fitted by IRLS. The patsy
formula machinery memorises the spline knots and centering means from the
training data, so predictions on new frames (including ages beyond the
boundary knots) reuse the training basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

SPLINE_DF = 5   # natural-cubic-spline df for the loan-age baseline
LTV_CAP = 300.0  # winsorisation cap for updated_ltv (%), see module docstring

# Right-hand side shared by both cause-specific hazards. The prepayment model
# keeps the full set (symmetric specification): incentive is its star driver,
# while credit covariates capture the well-documented fact that impaired
# borrowers cannot refinance (negative equity / low FICO suppress prepayment).
_RHS = (
    f"cr(loan_age, df={SPLINE_DF})"
    " + fico_s + ltv10 + prepay_incentive"
    " + investor_orig_time + REtype_CO_orig_time + REtype_PU_orig_time"
    " + REtype_SF_orig_time"
    " + uer_lag1 + uer_chg4_lag1 + hpi_growth_lag1 + gdp_lag1"
    " + center(ltv10):center(uer_lag1)"
)

#: name of the double-trigger interaction term in the fitted params
DT_TERM = "center(ltv10):center(uer_lag1)"

DEFAULT_FORMULA = "default_event ~ " + _RHS
PREPAY_FORMULA = "payoff_event ~ " + _RHS

#: raw panel columns every scoring frame must carry
REQUIRED_COLS = [
    "loan_age", "FICO_orig_time", "updated_ltv", "prepay_incentive",
    "investor_orig_time", "REtype_CO_orig_time", "REtype_PU_orig_time",
    "REtype_SF_orig_time", "uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1",
    "gdp_lag1",
]


@dataclass
class HazardModel:
    """A fitted cause-specific discrete-time hazard.

    Wraps the statsmodels GLMResults together with the formula and event
    column so downstream code (term structure, validation) never has to
    re-derive the specification.
    """

    result: object                 # statsmodels GLMResultsWrapper
    formula: str
    event_col: str                 # 'default_event' or 'payoff_event'
    name: str                      # 'default' | 'prepay'
    n_obs: int = 0
    n_events: int = 0
    fit_meta: dict = field(default_factory=dict)

    @property
    def params(self) -> pd.Series:
        return self.result.params

    def mcfadden_r2(self) -> float:
        """McFadden pseudo-R2 = 1 - llf / ll(intercept-only)."""
        return float(1.0 - self.result.llf / self.result.llnull)


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add the scaled covariates the formula expects (non-destructive copy)."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"scoring frame is missing required columns: {missing}")
    out = df.copy()
    out["fico_s"] = out["FICO_orig_time"] / 100.0   # per 100 FICO points
    # per 10pp updated LTV, winsorised at LTV_CAP (module docstring)
    out["ltv10"] = out["updated_ltv"].clip(upper=LTV_CAP) / 10.0
    return out


def _fit(panel_df: pd.DataFrame, formula: str, event_col: str,
         name: str) -> HazardModel:
    d = panel_df
    if "lag_warmup" in d.columns:
        d = d[d["lag_warmup"] == 0]
    d = _prepare(d)
    need = REQUIRED_COLS + [event_col]
    n_before = len(d)
    d = d.dropna(subset=need)
    # IRLS on the cloglog link can diverge from the default start (the inverse
    # link saturates and the working weights explode). Warm-start from a logit
    # fit: for rare events logit and cloglog coefficients nearly coincide
    # (both links agree to first order as lambda -> 0), so the logit solution
    # sits inside the cloglog basin of attraction.
    warm = smf.glm(
        formula, data=d, family=sm.families.Binomial(),
    ).fit()
    model = smf.glm(
        formula, data=d,
        family=sm.families.Binomial(link=sm.families.links.CLogLog()),
    )
    res = model.fit(start_params=warm.params.to_numpy(), maxiter=200)
    if not res.converged:
        raise RuntimeError(f"{name} hazard GLM did not converge")
    return HazardModel(
        result=res, formula=formula, event_col=event_col, name=name,
        n_obs=len(d), n_events=int(d[event_col].sum()),
        fit_meta={"rows_dropped_nan": n_before - len(d),
                  "warm_start": "logit"},
    )


def fit_default_hazard(panel_df: pd.DataFrame) -> HazardModel:
    """Fit the cause-specific DEFAULT hazard on loan-quarter at-risk rows.

    Pass TRAINING rows only (split == 'train'); the function additionally
    drops lag-warm-up rows. Payoff (competing-risk) rows enter with y = 0 and
    the loan's history simply ends there -- that IS the cause-specific
    treatment (module docstring).
    """
    return _fit(panel_df, DEFAULT_FORMULA, "default_event", "default")


def fit_prepay_hazard(panel_df: pd.DataFrame) -> HazardModel:
    """Fit the cause-specific PREPAYMENT hazard (y = payoff_event).

    Same framework as the default hazard with default as the censoring
    competing risk; prepay_incentive (note rate minus current market rate)
    is the star covariate.
    """
    return _fit(panel_df, PREPAY_FORMULA, "payoff_event", "prepay")


def predict_hazard(model: HazardModel, df: pd.DataFrame) -> np.ndarray:
    """Per-row conditional hazard lambda_t = P(event in t | at risk at t).

    Uses the training-memorised spline basis; ages beyond the training
    boundary knots extrapolate linearly on the cloglog scale (natural cubic
    spline tail behaviour -- the documented tail assumption).
    """
    return np.asarray(model.result.predict(_prepare(df)))


def pd_term_structure(models: dict[str, HazardModel],
                      profile_df: pd.DataFrame,
                      horizon: int) -> pd.DataFrame:
    """Competing-risk PD term structure for one or more loan profiles.

    Parameters
    ----------
    models : {'default': HazardModel, 'prepay': HazardModel}
    profile_df : one row per profile carrying REQUIRED_COLS (loan_age is the
        age the loan will have in the FIRST projected quarter; 0 = new loan)
        and optionally a 'profile' name column.
    horizon : number of quarters to project.

    Returns a long DataFrame with, per profile and period t = 1..horizon:
        hazard_default   lambda_d(t)  conditional default hazard
        hazard_prepay    lambda_p(t)  conditional prepayment hazard
        survival         S(t) = prod_{k<=t} (1 - lambda_d(k) - lambda_p(k)),
                         i.e. probability of surviving BOTH default and
                         prepayment (in a discrete competing-risk period the
                         loan exits by at most one cause, so per-period exit
                         probability is the sum of cause-specific hazards)
        marginal_pd      S(t-1) * lambda_d(t)  (unconditional default in t)
        cum_pd           sum_{k<=t} marginal_pd(k)  = P(default by t)

    Simplifications (documented, per MASTER_PLAN rung-1 tail assumption):
    all covariates other than loan_age are FROZEN at the profile's values --
    no amortisation of updated LTV, no macro path; beyond the observed-age
    support the spline baseline extrapolates linearly on the cloglog scale.
    The scenario-conditioning of the macro path is a later rung (satellite
    models + reversion to TTC).
    """
    for key in ("default", "prepay"):
        if key not in models:
            raise KeyError(f"models dict must contain '{key}'")
    frames = []
    for i, row in profile_df.reset_index(drop=True).iterrows():
        name = row.get("profile", f"profile_{i}")
        age0 = float(row["loan_age"])
        grid = pd.DataFrame([row.drop(labels=[c for c in ["profile"]
                                              if c in row.index])] * horizon)
        grid = grid.reset_index(drop=True)
        grid["loan_age"] = age0 + np.arange(horizon, dtype=float)
        grid = grid.astype({c: float for c in REQUIRED_COLS})
        lam_d = predict_hazard(models["default"], grid)
        lam_p = predict_hazard(models["prepay"], grid)
        exit_p = np.clip(lam_d + lam_p, 0.0, 0.999999)
        surv = np.cumprod(1.0 - exit_p)
        surv_prev = np.concatenate([[1.0], surv[:-1]])
        marginal = surv_prev * lam_d
        frames.append(pd.DataFrame({
            "profile": name,
            "period": np.arange(1, horizon + 1),
            "loan_age": grid["loan_age"].to_numpy(),
            "hazard_default": lam_d,
            "hazard_prepay": lam_p,
            "survival": surv,
            "marginal_pd": marginal,
            "cum_pd": np.cumsum(marginal),
        }))
    return pd.concat(frames, ignore_index=True)
