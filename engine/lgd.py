"""Two-stage workout LGD model: cure logit x fractional-logit severity.

METHODOLOGY (knowledge/sources/ifrs9_credit_risk_notes.md section 10)
----------------------------------------------------------------------
Realised workout LGD is BIMODAL and concentrated near the [0, 1] boundary:
a cure spike near zero loss and a write-off hump at high loss (notes section
10.2, Fig. 8). One regression through that mixture predicts a central value
(~0.5-0.6 here) that almost never occurs. The workhorse fix is the two-stage
(cure) model, which mirrors the data-generating process:

    E[LGD | x] = P(cure | x) * LGD_cure + (1 - P(cure | x)) * E[sev | non-cure, x]

with LGD_cure = 0 (documented simplification below). The two stages are:

STAGE 1 -- CURE:  cure_i = 1{lgd_time <= CURE_THRESHOLD} on resolved default
rows, fitted as a logit GLM. CURE_THRESHOLD = 0.05: "cure" here means the
default resolved with (near-)full recovery -- self-cure, refinance, or a
collateral sale that cleared the exposure. The 5% headroom absorbs small
frictional costs on otherwise-full recoveries; sensitivity at 0.00 and 0.10
is reported in outputs/lgd/lgd_report.md (the expected-LGD decomposition is
close to invariant to the threshold -- mass moved out of the cure spike
reappears in the severity average).

STAGE 2 -- SEVERITY | NON-CURE:  E[min(lgd, 1) | non-cure, x] fitted as a
fractional logit -- a binomial GLM with logit link on the fractional response
capped at SEV_CAP = 1, quasi-likelihood scale (Papke-Wooldridge). This is the
"bounded regression for severity given write-off" of notes section 10.2:
the logit link keeps every prediction inside (0, 1) and is robust to the
non-normal, boundary-heavy severity distribution.

EXCESS-LOSS LOADING (losses beyond EAD are REAL, never silently clipped):
12.5% of resolved train LGDs exceed 1 (14.2% of non-cures; max 3.17) --
workout costs, accrued interest
and fees can push the loss past the defaulted balance (notes section 10.1:
costs C_k enter the workout LGD with a negative sign). Capping at 1 inside
the GLM is a numerical device for the link function only; the truncated mass
is added back explicitly as

    excess_loading = E[max(lgd - 1, 0) | non-cure]   (training estimate)

so the severity used downstream is  E[min(lgd,1)|x] + excess_loading  and the
expected severity is unbiased for the full loss including the beyond-EAD tail
(a constant loading -- the tail is thin and its covariate dependence is not
estimable with discipline at 1,186 train rows above 1; validated OOT in the
report: realised OOT excess mass 0.024 vs loading 0.025).

RESOLVED WORKOUTS ONLY (the incomplete-workout trap, notes section 10.3):
lgd_time is populated on every default row, but 24.6% of defaults have
res_time = NaN -- the workout is still OPEN at the end of the observation
window. For those rows lgd_time is not a realised outcome (58% are coded
exactly 0; their mean is 0.19 vs 0.60 for resolved) and treating it as
realised would import a massive fake cure spike concentrated in the LATE
quarters (48% of OOT defaults are unresolved vs 17% of train). The model is
therefore fitted on RESOLVED defaults (res_time not NaN) and validated on
resolved OOT defaults. Direction of the residual selection bias (notes
section 10.3): resolved-only samples over-represent fast workouts, and cures
resolve faster (median 3 quarters vs 5 for write-offs), so the fitted cure
rate is biased UP and severity DOWN for cohorts near the window end. The
disciplined completion model for open workouts is documented future work.

TIMING CONVENTION (binding; inherits engine/hazard.py):
Covariates are taken from the DEFAULT-QUARTER row. updated_ltv indexes the
collateral by the current quarter's HPI -- the accepted loan-level STATE
VARIABLE exception (collateral indexation, not a macro regressor); the macro
cycle enters only through the lagged regressor uer_lag1. No contemporaneous
macro aggregate appears in either stage.

COVARIATES (both stages share the set; scalings match engine/hazard.py):
  ltv10      updated_ltv / 10, winsorised at LTV_CAP = 300 (same cap and
             rationale as the hazard engine). THE collateral channel: equity
             determines whether a distressed borrower can sell/refinance out
             of default (cure) and, failing that, the shortfall at
             foreclosure (severity). Mandated economic signs, asserted at
             fit time: cure FALLS in updated LTV, severity RISES in it.
  uer_lag1   lagged unemployment -- the labour-market margin the notes
             require the LGD satellite to share with the PD satellite
             (PD-LGD correlation, section 10.2). Its CURE-stage coefficient
             is POSITIVE in this panel (discussed honestly in
             outputs/lgd/lgd_report.md: conditional on updated LTV -- which
             already carries the HPI collapse -- stress-cohort defaulters are
             macro-driven rather than idiosyncratically impaired, and cure
             more; robust to a fixed 28-quarter resolution runway, so not a
             censoring artefact). Not sign-asserted; the collateral channel
             carries the mandated economics.
  fico_s     FICO_orig_time / 100 -- borrower quality; strongly reduces
             severity (better upkeep / cooperation), weak in the cure stage.
  loan_age   quarters on book at default -- seasoning/burnout margin.
Justification for keeping the symmetric 4-driver set in both stages:
each driver is materially significant in at least one stage, the shared set
keeps the decomposition readable, and richer specifications (hpi_growth_lag1,
uer_chg4_lag1) leave the mandated LTV economics unchanged while adding
collinearity with the LTV/uer pair -- documented in the report.

ROLE IN THE ECL ASSEMBLY (fixture conventions, tests/fixtures/compute_ecl.py):
predict_lgd returns E[LGD | default at t], the LGD_t factor of

    ECL = sum_t S(t-1) * lambda_t * LGD_t * EAD_t * (1 + EIR)^-t.

CRITICAL double-counting rule: S(t) in that formula is the COMPETING-RISK
survival from engine/hazard.py -- it already includes prepayment survival.
EAD_t must therefore be the CONTRACTUAL amortisation balance, NOT a
prepay-scaled balance: scaling EAD by prepayment expectations on top of the
prepay-inclusive S(t) would count prepayment twice. LGD itself is a per-unit-
of-EAD quantity and is unaffected, but any consumer of this module's output
must respect that convention.

DOCUMENTED SIMPLIFICATIONS
  * LGD_cure = 0. Realised mean LGD among train cures is 0.0036, so the
    omission understates expected LGD by ~0.04pp of EAD -- reported, not
    modelled.
  * lgd_time is taken as the vendor's realised workout LGD. The panel has no
    post-default cash-flow detail, so the EIR-discounting of section 10.1 is
    assumed to be embedded in the vendor's measurement rather than recomputed.
  * The excess-loss loading is a constant, not covariate-driven.
  * Severity is a conditional-mean model, not a density; downstream ECL only
    needs the mean.
  * No downturn add-on: IFRS 9 LGD must be unbiased and point-in-time
    (section 10.1); cyclicality enters through uer_lag1 and the HPI-indexed
    updated_ltv, and scenario conditioning is a later rung.

Estimation: statsmodels GLM. Stage 1 Binomial(logit), ML. Stage 2
Binomial(logit) on the capped fraction with scale="X2" (Pearson chi2)
-- the Papke-Wooldridge quasi-likelihood estimator; coefficient tables in the
report use HC1 robust standard errors. Deterministic: no randomness anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from engine.hazard import LTV_CAP

CURE_THRESHOLD = 0.05   # cure = lgd_time <= 5% of EAD (module docstring)
SEV_CAP = 1.0           # cap for the fractional-logit response; excess mass
                        # re-added via the explicit loading, never discarded

_LGD_RHS = "ltv10 + uer_lag1 + fico_s + loan_age"
CURE_FORMULA = "cure ~ " + _LGD_RHS
SEVERITY_FORMULA = "sev_capped ~ " + _LGD_RHS

#: raw panel columns every scoring frame must carry
LGD_REQUIRED_COLS = ["updated_ltv", "uer_lag1", "FICO_orig_time", "loan_age"]

#: columns the FIT sample additionally needs
_FIT_COLS = ["default_event", "res_time", "lgd_time"]


@dataclass
class LgdModels:
    """The fitted two-stage LGD decomposition.

    cure_result / severity_result wrap the statsmodels GLMResults; the loading
    and threshold are frozen at fit time so predict_* is fully reproducible.
    """

    cure_result: object            # statsmodels GLMResultsWrapper (logit)
    severity_result: object        # statsmodels GLMResultsWrapper (frac logit)
    cure_formula: str
    severity_formula: str
    cure_threshold: float
    sev_cap: float
    excess_loading: float          # E[max(lgd-1,0) | non-cure], train
    cure_mean_lgd: float           # realised mean lgd among train cures
                                   # (reported; NOT added -- LGD_cure = 0)
    n_defaults: int = 0            # default rows seen (train split)
    n_resolved: int = 0            # resolved default rows used
    n_cures: int = 0
    n_noncure: int = 0
    fit_meta: dict = field(default_factory=dict)

    @property
    def cure_params(self) -> pd.Series:
        return self.cure_result.params

    @property
    def severity_params(self) -> pd.Series:
        return self.severity_result.params

    @property
    def lgd_upper_bound(self) -> float:
        """Hard upper bound of predict_lgd: sev_cap + excess_loading."""
        return self.sev_cap + self.excess_loading


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Add the scaled covariates the formulas expect (non-destructive copy).

    Same scalings and LTV winsorisation as engine/hazard.py so coefficient
    tables are comparable across the PD and LGD engines.
    """
    missing = [c for c in LGD_REQUIRED_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"scoring frame is missing required columns: {missing}")
    out = df.copy()
    out["fico_s"] = out["FICO_orig_time"] / 100.0
    out["ltv10"] = out["updated_ltv"].clip(upper=LTV_CAP) / 10.0
    return out


def fit_lgd_models(panel_df: pd.DataFrame,
                   cure_threshold: float = CURE_THRESHOLD) -> LgdModels:
    """Fit the two-stage LGD model on TRAIN-split resolved default rows.

    Filtering applied internally (order matters, counts kept in fit_meta):
      1. split == 'train' if a split column is present (defence in depth --
         passing the full panel cannot leak OOT rows into the fit);
      2. default_event == 1 (LGD is only observed at default);
      3. res_time not NaN -- RESOLVED workouts only (module docstring:
         unresolved lgd_time is not a realised outcome);
      4. rows with NaN in any required covariate dropped (3 train rows).

    Economic-sign assertions (fail loudly, never return a wrong-signed fit):
    cure falls in updated LTV, severity rises in updated LTV -- the collateral
    channel on both margins.
    """
    d = panel_df
    if "split" in d.columns:
        d = d[d["split"] == "train"]
    for c in _FIT_COLS:
        if c not in d.columns:
            raise KeyError(f"fit frame is missing required column: {c}")
    d = d[d["default_event"] == 1]
    n_defaults = len(d)
    d = d[d["res_time"].notna()]
    n_resolved_raw = len(d)
    d = _prepare(d)
    d = d.dropna(subset=LGD_REQUIRED_COLS + ["lgd_time"])
    if d.empty:
        raise ValueError("no resolved default rows to fit on")

    d = d.copy()
    d["cure"] = (d["lgd_time"] <= cure_threshold).astype(int)

    cure_res = smf.glm(
        CURE_FORMULA, data=d, family=sm.families.Binomial(),
    ).fit()
    if not cure_res.converged:
        raise RuntimeError("cure logit GLM did not converge")

    nc = d[d["cure"] == 0].copy()
    if nc.empty:
        raise ValueError("no non-cure rows -- severity stage cannot be fitted")
    nc["sev_capped"] = nc["lgd_time"].clip(upper=SEV_CAP)
    # Papke-Wooldridge fractional logit: quasi-likelihood scale (Pearson X2)
    # + HC1 robust covariance (coefficients are unaffected; only SEs change)
    sev_res = smf.glm(
        SEVERITY_FORMULA, data=nc, family=sm.families.Binomial(),
    ).fit(scale="X2", cov_type="HC1")
    if not sev_res.converged:
        raise RuntimeError("severity fractional-logit GLM did not converge")

    # explicit beyond-EAD loss mass, never silently clipped (module docstring)
    excess_loading = float((nc["lgd_time"] - SEV_CAP).clip(lower=0.0).mean())

    # economic signs -- the collateral channel, asserted on both margins
    b_cure_ltv = float(cure_res.params["ltv10"])
    b_sev_ltv = float(sev_res.params["ltv10"])
    if not b_cure_ltv < 0:
        raise AssertionError(
            f"economic sign violated: cure must FALL in updated LTV "
            f"(ltv10 coef = {b_cure_ltv:+.4f})")
    if not b_sev_ltv > 0:
        raise AssertionError(
            f"economic sign violated: severity must RISE in updated LTV "
            f"(ltv10 coef = {b_sev_ltv:+.4f})")

    return LgdModels(
        cure_result=cure_res,
        severity_result=sev_res,
        cure_formula=CURE_FORMULA,
        severity_formula=SEVERITY_FORMULA,
        cure_threshold=float(cure_threshold),
        sev_cap=float(SEV_CAP),
        excess_loading=excess_loading,
        cure_mean_lgd=float(d.loc[d["cure"] == 1, "lgd_time"].mean())
        if int(d["cure"].sum()) else float("nan"),
        n_defaults=n_defaults,
        n_resolved=len(d),
        n_cures=int(d["cure"].sum()),
        n_noncure=len(nc),
        fit_meta={
            "unresolved_dropped": n_defaults - n_resolved_raw,
            "nan_covariate_dropped": n_resolved_raw - len(d),
            "share_sev_gt_cap_noncure": float((nc["lgd_time"] > SEV_CAP).mean()),
            "mean_excess_given_gt_cap": float(
                (nc.loc[nc["lgd_time"] > SEV_CAP, "lgd_time"] - SEV_CAP).mean())
            if (nc["lgd_time"] > SEV_CAP).any() else 0.0,
        },
    )


def predict_components(models: LgdModels, df: pd.DataFrame) -> pd.DataFrame:
    """Per-row decomposition of expected LGD.

    Returns a DataFrame (index aligned with df) with columns
      p_cure          P(cure | x)                        (stage 1)
      severity_capped E[min(lgd, 1) | non-cure, x]       (stage 2, in (0,1))
      excess_loading  the constant beyond-EAD loading    (train estimate)
      severity_adj    severity_capped + excess_loading
      lgd             (1 - p_cure) * severity_adj  = expected LGD (LGD_cure=0)

    Raises on NaN in the required covariates: silent NaN propagation into
    an ECL sum is not acceptable.
    """
    x = _prepare(df)
    bad = x[LGD_REQUIRED_COLS].isna().any(axis=1)
    if bad.any():
        raise ValueError(
            f"{int(bad.sum())} scoring rows carry NaN in required LGD "
            f"covariates {LGD_REQUIRED_COLS}")
    p_cure = np.asarray(models.cure_result.predict(x))
    sev_capped = np.asarray(models.severity_result.predict(x))
    sev_adj = sev_capped + models.excess_loading
    lgd = (1.0 - p_cure) * sev_adj
    out = pd.DataFrame({
        "p_cure": p_cure,
        "severity_capped": sev_capped,
        "excess_loading": models.excess_loading,
        "severity_adj": sev_adj,
        "lgd": lgd,
    }, index=df.index)
    # hard range guarantee: logit link keeps both stages in (0,1), so
    # lgd in [0, sev_cap + loading] by construction -- asserted anyway
    ub = models.lgd_upper_bound + 1e-12
    if not (np.isfinite(lgd).all() and (lgd >= 0).all() and (lgd <= ub).all()):
        raise AssertionError("predicted LGD escaped [0, sev_cap + loading]")
    return out


def predict_lgd(models: LgdModels, df: pd.DataFrame) -> np.ndarray:
    """Expected LGD per row: (1 - P(cure)) * (E[min(lgd,1)|non-cure] + loading).

    This is the LGD_t of ECL = sum_t S(t-1)*lambda_t*LGD_t*EAD_t*(1+EIR)^-t.
    Reminder (module docstring): S(t) already includes prepayment survival,
    so the EAD_t it multiplies must be the CONTRACTUAL amortisation balance.
    """
    return predict_components(models, df)["lgd"].to_numpy()
