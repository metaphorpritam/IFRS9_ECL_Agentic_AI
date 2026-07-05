"""ECL assembly + allowance movement decomposition -- the deterministic engine.

THE FORMULA (tests/fixtures/compute_ecl.py section 3 -- the golden convention)
------------------------------------------------------------------------------
Per exposure, over projected periods t = 1..T:

    ECL = sum_t  S(t-1) * lambda_t * LGD_t * EAD_t * (1 + EIR)^-t

  S(t-1)    competing-risk survival to the START of period t,
            S(t) = prod_{k<=t} (1 - lambda_default_k - lambda_prepay_k)
            (engine/hazard.py pd_term_structure algebra, reproduced exactly)
  lambda_t  conditional default hazard in period t
  LGD_t     expected loss-given-default for a default in period t
  EAD_t     CONTRACTUAL amortisation balance entering period t
  EIR       per-period effective interest rate; losses crystallise at the
            END of period t, hence the (1+EIR)^-t discount factor.

The period is ABSTRACT in the kernel (ecl_schedule): the section-3 fixture
uses ANNUAL periods (hazards 1.5/2.0/2.2/2.0/1.8%, LGD 35%, EIR 6%,
straight-line EUR 200k repayments -> 12m ECL 4,952.83 / lifetime 16,571.39),
while the panel path (ecl_for_snapshot) uses QUARTERS. "12-month ECL" is the
sum of the first `periods_12m` periods (1 annual period for the fixture,
4 quarters on the panel).

CRITICAL -- NO PREPAYMENT DOUBLE COUNTING (restated; a reviewer will check)
------------------------------------------------------------------------------
S(t) above ALREADY includes prepayment survival (competing risk). EAD_t must
therefore be the CONTRACTUAL amortisation balance from engine/ead.py --
deliberately NOT prepay-scaled. Scaling EAD by prepayment expectations on top
of the prepay-inclusive S(t) would count prepayment twice and understate
lifetime ECL. ecl_for_snapshot consumes engine.ead.ead_matrix unmodified.

EIR / DISCOUNTING CONVENTION (documented)
------------------------------------------------------------------------------
IFRS 9 discounts at the ORIGINATION effective interest rate. The panel's live
per-quarter rate is the current note rate interest_rate_time (nominal annual
%, quarterly compounding) and the book is US fixed-rate mortgages, so the
current note rate is the disciplined EIR proxy:  eir_q = rate / 400 -- the
same RATE_DIVISOR convention that drives the engine/ead.py annuity. The
orig_rate_missing flag concerns the ORIGINATION-rate snapshot only (see
engine/ead.py) -- the current note rate is populated on every panel row.
Defensive fallback, mirroring ead.py's straight-line branch: a NaN or
non-positive rate discounts at eir_q = 0 (undiscounted); no panel row
triggers it.

STAGE MAPPING (IFRS 9) AND THE STAGE-3 RULE
------------------------------------------------------------------------------
Both 12-month and lifetime ECL are ALWAYS computed per loan; the REPORTED
allowance is 12m for Stage 1 and lifetime for Stage 2/3 (reported_allowance).
Stages come from engine/staging.py (relative SICR test; Stage 3 = the
snapshot quarter's default rows).

Stage 3 (credit-impaired, default has HAPPENED):  ECL = LGD(x_now) * EAD_now
with EAD_now = balance_time and LGD from engine/lgd.py at the default-quarter
covariates. No PD (the default is an event, not a probability) and no
further discounting: the loss crystallises now, and the workout-recovery
discounting is embedded in the vendor's realised lgd_time that the LGD model
is fitted on (engine/lgd.py documented simplification). ecl_12m =
ecl_lifetime = that value for Stage-3 rows.

PROJECTION CONVENTIONS (inherit engine/staging.py's rung-1 choices)
------------------------------------------------------------------------------
* Horizon: R = mat_time - t remaining contractual quarters, floored at 1
  (at/past-maturity loans due within one quarter), optionally capped by
  EclConfig.max_horizon.
* Hazards: the exact age-offset factorisation of engine/staging.py -- all
  covariates FROZEN at their snapshot values, only the loan-age spline
  advances along the projection (rung-1 tail assumption; no macro path,
  no LTV amortisation; scenario conditioning is a later rung).
* LGD_t: same clock. A default in projected quarter k happens at age
  age0 + k; the LGD model's loan_age covariate advances with that clock
  (exact within the fitted logit-linear stages -- eta(k) = eta0 +
  beta_age * k -- cross-checked against predict_components in
  crosscheck_lgd_grid), all other LGD covariates frozen at the snapshot.
  LGD can exceed 1 by the excess-loss loading (beyond-EAD workout costs are
  real data, never silently clipped -- engine/lgd.py).
* Population: panel rows at time t EXCLUDING payoff_event == 1 rows
  (payoff quarter = derecognition, not a stageable exposure -- same
  convention as the staging exhibits). Default rows stay (Stage 3).

MOVEMENT DECOMPOSITION (movement_decomposition)
------------------------------------------------------------------------------
Waterfall between two allowance snapshots, SEQUENTIAL attribution on a
documented ordering (attribution is ORDER-DEPENDENT: each step is measured
holding the previous steps' state; a different order allocates the
interaction terms differently -- stated here, not hidden):

  opening           sum of reported allowance at t0
  1. stage_migration  surviving (common) loans: reported allowance at t0
                      MARKS under the t1 STAGE minus under the t0 stage --
                      the pure effect of 12m <-> lifetime re-classification
                      at frozen parameters (computable because both ECLs are
                      always carried per loan)
  2. remeasurement    surviving loans, already at the t1 stage: t1 marks
                      minus t0 marks -- macro / parameter / amortisation /
                      discount-unwind re-measurement, i.e. "same loans,
                      re-marked"
  3. derecognitions   loans present at t0 only (prepaid, matured, or t0
                      defaults resolved out of the panel): minus their
                      opening reported allowance
  4. new_loans        loans present at t1 only (post-t0 originations /
                      first observations): plus their closing reported
                      allowance
  closing           sum of reported allowance at t1

The five components sum EXACTLY to closing - opening (algebraic identity,
asserted; unit-tested in tests/test_ecl.py).

DOCUMENTED SIMPLIFICATIONS
------------------------------------------------------------------------------
* EIR proxy = current note rate / 400 per quarter (fixed-rate book; IFRS 9's
  origination EIR coincides up to repricing, which is out of scope).
* Frozen covariates over the projection on both the hazard and LGD legs;
  only the loan-age clock advances (hazard spline + LGD loan_age term).
* Stage-3 ECL = LGD * current balance, undiscounted (loss crystallised;
  workout discounting embedded in the vendor lgd_time).
* 12-month ECL = first 4 projected quarters (EclConfig.quarters_12m).
* Movement attribution is sequential and order-dependent (ordering above).
* Payoff-quarter rows are derecognitions, excluded from the ECL book.

Deterministic throughout: no LLM, no network, no randomness (the only RNG,
in crosscheck_lgd_grid, is fixed-seed sampling for a numerical cross-check).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from patsy import build_design_matrices
from scipy.special import expit

from engine.ead import RATE_DIVISOR, SNAPSHOT_COLS, ead_matrix
from engine.hazard import HazardModel
from engine.lgd import LGD_REQUIRED_COLS, LgdModels, predict_components
from engine.lgd import _prepare as _lgd_prepare
from engine.staging import (
    _CHUNK_LOANS,
    _EXIT_CAP,
    StagingConfig,
    _age_curve,
    _design_matrix,
    _spline_cols,
    assign_stages,
)

#: quarters that make up the 12-month ECL window on the quarterly panel
QUARTERS_12M = 4

#: columns movement_decomposition requires on each allowance frame
ALLOWANCE_COLS = ["id", "stage", "ecl_12m", "ecl_lifetime"]

#: components of the movement waterfall, in attribution order
WATERFALL_COMPONENTS = ["opening", "stage_migration", "remeasurement",
                        "derecognitions", "new_loans", "closing"]


@dataclass(frozen=True)
class EclConfig:
    """ECL assembly configuration.

    staging : StagingConfig driving the Stage-1/2/3 assignment
        (engine/staging.py; defaults = doubling + 0.5pp p.a. add-on).
    quarters_12m : projected quarters in the "12-month" ECL window (4).
    max_horizon : optional cap on the lifetime projection horizon R
        (quarters); None = full contractual remaining life.
    """

    staging: StagingConfig = StagingConfig()
    quarters_12m: int = QUARTERS_12M
    max_horizon: int | None = None


# ---------------------------------------------------------------------------
# the shared survival / marginal-PD algebra (one implementation, two callers)
# ---------------------------------------------------------------------------

def _survival_marginal(lam_d: np.ndarray,
                       lam_p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(n, T) hazards -> (survival entering t, marginal PD in t), both (n, T).

    survival_start[:, t-1] = S(t-1) = prod_{k<t} (1 - lam_d_k - lam_p_k);
    marginal[:, t-1] = S(t-1) * lam_d_t.  Identical algebra (including the
    per-period exit-probability cap) to engine.hazard.pd_term_structure.
    """
    if lam_d.shape != lam_p.shape or lam_d.ndim != 2:
        raise ValueError("hazard grids must be equal-shape 2-D arrays")
    exit_p = np.clip(lam_d + lam_p, 0.0, _EXIT_CAP)
    surv = np.cumprod(1.0 - exit_p, axis=1)
    surv_start = np.hstack([np.ones((surv.shape[0], 1)), surv[:, :-1]])
    return surv_start, surv_start * lam_d


# ---------------------------------------------------------------------------
# the ECL kernel (single exposure; fixture-facing)
# ---------------------------------------------------------------------------

def _as_period_vector(x, T: int, name: str) -> np.ndarray:
    v = np.asarray(x, dtype=float)
    if v.ndim == 0:
        v = np.full(T, float(v))
    v = v.ravel()
    if v.size != T:
        raise ValueError(f"{name} must be scalar or length {T}, got {v.size}")
    return v


def ecl_schedule(hazard_default, lgd, ead, eir,
                 hazard_prepay=None) -> pd.DataFrame:
    """Per-period ECL table for ONE exposure -- the compute_ecl section-3 kernel.

    Parameters
    ----------
    hazard_default : per-period conditional default hazards lambda_t,
        t = 1..T (the length defines T). Periods are abstract: annual for
        the fixture, quarterly on the panel.
    lgd : LGD_t, scalar or length-T (may exceed 1 -- beyond-EAD workout
        costs; engine/lgd.py).
    ead : EAD_t, scalar or length-T -- the CONTRACTUAL balance entering
        period t (never prepay-scaled; module docstring, CRITICAL section).
    eir : per-period effective interest rate; discount = (1+eir)^-t
        (end-of-period loss crystallisation).
    hazard_prepay : optional per-period competing prepayment hazards;
        default all-zero. Survival is S(t) = prod (1 - lam_d - lam_p).

    Returns
    -------
    DataFrame, one row per period t = 1..T:
        period, hazard_default, hazard_prepay, survival_start (= S(t-1)),
        marginal_pd (= S(t-1)*lambda_t), lgd, ead, discount, ecl.
    Sum the `ecl` column (ecl_totals) for 12m / lifetime ECL.
    """
    lam_d = np.asarray(hazard_default, dtype=float).ravel()
    T = lam_d.size
    if T == 0:
        raise ValueError("need at least one projection period")
    lam_p = (np.zeros(T) if hazard_prepay is None
             else _as_period_vector(hazard_prepay, T, "hazard_prepay"))
    lgd_v = _as_period_vector(lgd, T, "lgd")
    ead_v = _as_period_vector(ead, T, "ead")
    eir = float(eir)
    if not (np.all(np.isfinite(lam_d)) and np.all(np.isfinite(lam_p))
            and np.all(np.isfinite(lgd_v)) and np.all(np.isfinite(ead_v))
            and np.isfinite(eir)):
        raise ValueError("non-finite inputs")
    if np.any(lam_d < 0) or np.any(lam_d > 1) or np.any(lam_p < 0) \
            or np.any(lam_p > 1):
        raise ValueError("hazards must lie in [0, 1]")
    if np.any(lgd_v < 0) or np.any(ead_v < 0):
        raise ValueError("lgd and ead must be non-negative")
    if eir <= -1.0:
        raise ValueError("eir must exceed -100%")

    surv_start, marginal = _survival_marginal(lam_d[None, :], lam_p[None, :])
    periods = np.arange(1, T + 1)
    discount = (1.0 + eir) ** -periods.astype(float)
    ecl = marginal[0] * lgd_v * ead_v * discount
    return pd.DataFrame({
        "period": periods,
        "hazard_default": lam_d,
        "hazard_prepay": lam_p,
        "survival_start": surv_start[0],
        "marginal_pd": marginal[0],
        "lgd": lgd_v,
        "ead": ead_v,
        "discount": discount,
        "ecl": ecl,
    })


def ecl_totals(schedule: pd.DataFrame,
               periods_12m: int) -> tuple[float, float]:
    """(12-month ECL, lifetime ECL) from an ecl_schedule table.

    periods_12m: leading periods that span 12 months -- 1 for the annual
    fixture convention, QUARTERS_12M = 4 on the quarterly panel.
    """
    if periods_12m < 1:
        raise ValueError("periods_12m must be >= 1")
    e = schedule["ecl"].to_numpy()
    return float(e[:periods_12m].sum()), float(e.sum())


# ---------------------------------------------------------------------------
# vectorised per-loan grids (snapshot path)
# ---------------------------------------------------------------------------

def _marginal_pd_grid(models: dict[str, HazardModel], frame: pd.DataFrame,
                      R: np.ndarray) -> np.ndarray:
    """(n, max R) unconditional default probabilities S(t-1)*lambda_d(t).

    Same exact age-offset factorisation as engine.staging._cum_default_pd
    (whose row sums this grid reproduces to float noise -- gated in
    analysis/run_ecl.py), but keeping the per-period marginals the ECL sum
    needs instead of collapsing to the cumulative PD. Cells beyond a loan's
    R are exactly 0 (off-window hazards are set to 0).
    """
    ages0 = frame["loan_age"].to_numpy()
    if not np.allclose(ages0, np.round(ages0)):
        raise ValueError("loan_age must be integral quarters")
    ages0 = np.round(ages0).astype(int)
    R = np.asarray(R, dtype=int)
    if (R < 1).any():
        raise ValueError("horizons must be >= 1 (floor R upstream)")
    n, Tmax = len(R), int(R.max())
    max_age = int(ages0.max() + Tmax)
    offsets, curves = {}, {}
    for name in ("default", "prepay"):
        m = models[name]
        beta = m.result.params.to_numpy()
        idx = _spline_cols(m)
        X = _design_matrix(m, frame)
        offsets[name] = X @ beta - X[:, idx] @ beta[idx]
        curves[name] = _age_curve(m, max_age)
    marginal = np.zeros((n, Tmax))
    for lo in range(0, n, _CHUNK_LOANS):
        sl = slice(lo, min(lo + _CHUNK_LOANS, n))
        a0, r = ages0[sl], R[sl]
        k = np.arange(int(r.max()))
        ages = a0[:, None] + 1 + k[None, :]
        on = k[None, :] < r[:, None]
        lam = {}
        for name in ("default", "prepay"):
            eta = offsets[name][sl][:, None] + curves[name][ages]
            with np.errstate(over="ignore"):
                lam[name] = np.where(on, 1.0 - np.exp(-np.exp(eta)), 0.0)
        _, marg = _survival_marginal(lam["default"], lam["prepay"])
        marginal[sl, :marg.shape[1]] = marg
    return marginal


def _lgd_eta0(result, frame: pd.DataFrame) -> np.ndarray:
    """Linear predictor of one LGD stage at the snapshot covariates."""
    prep = _lgd_prepare(frame)
    bad = int(prep[LGD_REQUIRED_COLS].isna().any(axis=1).sum())
    if bad:
        raise ValueError(f"{bad} rows carry NaN in required LGD covariates")
    di = result.model.data.design_info
    X = np.asarray(build_design_matrices([di], prep)[0], dtype=float)
    if X.shape[0] != len(prep):
        raise RuntimeError("LGD design matrix dropped rows; misaligned")
    return X @ result.params.to_numpy()


def _lgd_grid(models: LgdModels, frame: pd.DataFrame,
              Tmax: int) -> np.ndarray:
    """(n, Tmax) expected LGD for a default in projected quarter k = 1..Tmax.

    Both LGD stages are logit-linear, so advancing ONLY the loan_age clock
    (default in quarter k -> age age0 + k; every other covariate frozen at
    the snapshot -- module docstring) is the exact shift
    eta(k) = eta0 + beta_age * k on each stage:

        lgd(k) = (1 - expit(eta_cure(k))) * (expit(eta_sev(k)) + loading)

    identical to engine.lgd.predict_components on a frame with
    loan_age = age0 + k (cross-checked by crosscheck_lgd_grid).
    """
    k = np.arange(1, Tmax + 1, dtype=float)[None, :]
    eta_c = _lgd_eta0(models.cure_result, frame)[:, None] \
        + float(models.cure_result.params["loan_age"]) * k
    eta_s = _lgd_eta0(models.severity_result, frame)[:, None] \
        + float(models.severity_result.params["loan_age"]) * k
    return (1.0 - expit(eta_c)) * (expit(eta_s) + models.excess_loading)


def crosscheck_lgd_grid(models: LgdModels, snapshot_df: pd.DataFrame,
                        n_sample: int = 20, k_max: int = 40,
                        seed: int = 0) -> float:
    """Max |_lgd_grid - predict_components| over a fixed-seed loan sample.

    Rebuilds, for each sampled loan, the k = 1..k_max default-quarter frames
    with loan_age = age0 + k and scores them through the public
    engine.lgd.predict_components (the slow reference path). Expected ~1e-15
    (identical linear predictors). Deterministic (fixed seed).
    """
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(snapshot_df), size=min(n_sample, len(snapshot_df)),
                      replace=False)
    sample = snapshot_df.iloc[pick].reset_index(drop=True)
    fast = _lgd_grid(models, sample, k_max)
    worst = 0.0
    for i in range(len(sample)):
        rep = pd.DataFrame([sample.iloc[i][LGD_REQUIRED_COLS]] * k_max)
        rep = rep.reset_index(drop=True).astype(float)
        rep["loan_age"] = rep["loan_age"] + np.arange(1, k_max + 1)
        ref = predict_components(models, rep)["lgd"].to_numpy()
        worst = max(worst, float(np.abs(fast[i] - ref).max()))
    return worst


# ---------------------------------------------------------------------------
# per-loan ECL at a reporting snapshot
# ---------------------------------------------------------------------------

def ecl_for_snapshot(panel_df: pd.DataFrame, t: int, models: dict,
                     config: EclConfig | None = None) -> pd.DataFrame:
    """Stage + 12-month ECL + lifetime ECL per loan at reporting quarter t.

    Parameters
    ----------
    panel_df : loan-quarter rows containing quarter t AND history
        (time <= t rows feed the staging origination-macro map and the
        probation lookback; rows after t are never used).
    t : reporting quarter (end-of-quarter convention).
    models : {'default': HazardModel, 'prepay': HazardModel,
              'lgd': LgdModels} -- the fitted rung-1 engines.
    config : EclConfig (module docstring for every convention).

    Returns
    -------
    One row per NON-PAYOFF loan at t (payoff rows are derecognitions):
        id, time, stage, trigger_reason, loan_age, R, balance, eir_q,
        lgd_current, lifetime_pd_now, lifetime_pd_engine (the ECL grid's own
        cumulative PD -- cross-check column), pd_ratio, default_event,
        ecl_12m, ecl_lifetime, ecl_reported, coverage.

    ecl_12m and ecl_lifetime are BOTH always populated; ecl_reported is the
    IFRS 9 allowance (12m for Stage 1, lifetime for Stage 2/3). Stage-3 rows
    carry ecl_12m = ecl_lifetime = LGD(x_now) * balance (module docstring).
    EAD paths are CONTRACTUAL (engine/ead.py) -- never prepay-scaled: the
    survival weights already carry prepayment (CRITICAL section).
    """
    cfg = config if config is not None else EclConfig()
    for key in ("default", "prepay", "lgd"):
        if key not in models:
            raise KeyError(f"models dict must contain '{key}'")
    hz = {"default": models["default"], "prepay": models["prepay"]}
    t = int(t)
    hist = panel_df.loc[panel_df["time"] <= t]
    if not (hist["time"] == t).any():
        raise ValueError(f"no rows at time {t}")

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

    marginal = _marginal_pd_grid(hz, snap, R)                # S(t-1)*lambda_t
    ead_g = ead_matrix(snap[SNAPSHOT_COLS], Tmax).to_numpy()  # contractual
    lgd_g = _lgd_grid(models["lgd"], snap, Tmax)             # age clock only
    comp0 = predict_components(models["lgd"], snap)          # default-now LGD

    rate = snap["interest_rate_time"].to_numpy(dtype=float)
    usable = np.isfinite(rate) & (rate > 0.0)
    eir_q = np.where(usable, rate, 0.0) / RATE_DIVISOR       # documented proxy
    periods = np.arange(1, Tmax + 1, dtype=float)
    discount = (1.0 + eir_q)[:, None] ** -periods[None, :]

    cells = marginal * lgd_g * ead_g * discount              # THE formula
    q12 = min(int(cfg.quarters_12m), Tmax)
    ecl_12m = cells[:, :q12].sum(axis=1)
    ecl_life = cells.sum(axis=1)

    # Stage 3: default happened this quarter -- LGD-based loss on current EAD
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


# ---------------------------------------------------------------------------
# allowance movement decomposition
# ---------------------------------------------------------------------------

def reported_allowance(allowance_df: pd.DataFrame) -> np.ndarray:
    """IFRS 9 reported allowance per row: 12m if Stage 1, else lifetime."""
    missing = [c for c in ALLOWANCE_COLS if c not in allowance_df.columns]
    if missing:
        raise KeyError(f"allowance frame is missing columns: {missing}")
    return np.where(allowance_df["stage"].to_numpy() == 1,
                    allowance_df["ecl_12m"].to_numpy(dtype=float),
                    allowance_df["ecl_lifetime"].to_numpy(dtype=float))


def _pick(df: pd.DataFrame, stage: np.ndarray, suffix: str) -> np.ndarray:
    """Reported allowance from `suffix` marks under an arbitrary stage."""
    return np.where(stage == 1,
                    df[f"ecl_12m{suffix}"].to_numpy(dtype=float),
                    df[f"ecl_lifetime{suffix}"].to_numpy(dtype=float))


def movement_decomposition(allowance_t0_df: pd.DataFrame,
                           allowance_t1_df: pd.DataFrame,
                           label_t0: str = "t0",
                           label_t1: str = "t1") -> pd.DataFrame:
    """Allowance waterfall between two ecl_for_snapshot outputs.

    Sequential attribution, ORDER-DEPENDENT by construction (module
    docstring states the convention): on surviving loans, (1) stage
    migration is measured FIRST, at frozen t0 marks (t0's own 12m/lifetime
    ECLs re-picked under the t1 stage); (2) re-measurement second, at the
    already-migrated stage (t1 marks minus t0 marks under the t1 stage);
    portfolio change enters as (3) derecognitions at their t0 reported
    allowance and (4) new loans at their t1 reported allowance.

    Input frames need ALLOWANCE_COLS = [id, stage, ecl_12m, ecl_lifetime]
    with unique ids (any ecl_reported column is ignored and re-derived).

    Returns a DataFrame with one row per WATERFALL_COMPONENTS entry:
        component | amount | n_loans | kind ('level' or 'delta')
    where amount sums EXACTLY (asserted) as
        closing = opening + stage_migration + remeasurement
                          + derecognitions + new_loans.
    """
    frames = {}
    for name, df in (("t0", allowance_t0_df), ("t1", allowance_t1_df)):
        missing = [c for c in ALLOWANCE_COLS if c not in df.columns]
        if missing:
            raise KeyError(f"{name} frame is missing columns: {missing}")
        if df["id"].duplicated().any():
            raise ValueError(f"{name} frame has duplicate loan ids")
        frames[name] = df[ALLOWANCE_COLS]

    a0, a1 = frames["t0"], frames["t1"]
    opening = float(reported_allowance(a0).sum())
    closing = float(reported_allowance(a1).sum())

    m = a0.merge(a1, on="id", how="outer", suffixes=("_0", "_1"),
                 indicator=True)
    gone = m["_merge"] == "left_only"
    born = m["_merge"] == "right_only"
    both = m["_merge"] == "both"

    derecognitions = -float(_pick(m[gone], m.loc[gone, "stage_0"].to_numpy(),
                                  "_0").sum())
    new_loans = float(_pick(m[born], m.loc[born, "stage_1"].to_numpy(),
                            "_1").sum())

    c = m[both]
    st0 = c["stage_0"].to_numpy().astype(int)
    st1 = c["stage_1"].to_numpy().astype(int)
    at_t0_old_stage = _pick(c, st0, "_0")
    at_t0_new_stage = _pick(c, st1, "_0")
    at_t1_new_stage = _pick(c, st1, "_1")
    stage_migration = float((at_t0_new_stage - at_t0_old_stage).sum())
    remeasurement = float((at_t1_new_stage - at_t0_new_stage).sum())

    total = (opening + stage_migration + remeasurement + derecognitions
             + new_loans)
    if abs(total - closing) > 1e-6 * max(abs(closing), 1.0):
        raise AssertionError(
            f"waterfall identity violated: components give {total:.6f}, "
            f"closing is {closing:.6f}")

    out = pd.DataFrame({
        "component": WATERFALL_COMPONENTS,
        "amount": [opening, stage_migration, remeasurement, derecognitions,
                   new_loans, closing],
        "n_loans": [len(a0), int((st0 != st1).sum()), int(both.sum()),
                    int(gone.sum()), int(born.sum()), len(a1)],
        "kind": ["level", "delta", "delta", "delta", "delta", "level"],
    })
    out.attrs["label_t0"] = label_t0
    out.attrs["label_t1"] = label_t1
    return out
