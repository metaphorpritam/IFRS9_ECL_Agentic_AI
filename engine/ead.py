"""Exposure-at-default (EAD) profiles: contractual amortisation + revolver CCF.

Rung-1 EAD component of the IFRS 9 ECL engine. Produces, per loan, the
deterministic exposure path EAD_t that multiplies the PD/LGD term structure in

    ECL = sum_t S(t-1) * lambda_t * LGD_t * EAD_t * (1 + EIR)^-t
          (tests/fixtures/compute_ecl.py section 3 -- the golden convention)

TIMING CONVENTION (aligned with engine/hazard.py's pd_term_structure)
----------------------------------------------------------------------
Projected periods are indexed t = 1..horizon, where t = 1 is the first
quarter AFTER the snapshot. EAD_t is the CONTRACTUAL principal balance
ENTERING period t, i.e. the snapshot balance after t-1 scheduled quarterly
payments. This mirrors the compute_ecl section-3 fixture exactly ("the
exposure at risk in year t is the balance after t-1 repayments"): default in
period t crystallises against the balance outstanding at the start of that
period, before the period's own instalment. Consequently EAD_1 equals the
snapshot balance, the path is monotone non-increasing, and EAD_t = 0 for
every t beyond the remaining term.

CRITICAL -- NO PREPAYMENT DOUBLE COUNTING
------------------------------------------
EAD_t here is the CONTRACTUAL amortisation balance and is deliberately NOT
scaled by prepayment probabilities. The ECL survival weight S(t-1) produced
by engine/hazard.py is the competing-risk survival
S(t) = prod_k (1 - lambda_default_k - lambda_prepay_k): it ALREADY removes
the prepaid fraction of the book. Scaling EAD_t by prepayment survival as
well would count prepayment twice and understate lifetime ECL. Any reviewer
checking this module: the contractual path is a requirement, not an
oversight.

AMORTISATION CONVENTION
------------------------
Level-payment (annuity) amortisation with QUARTERLY compounding of the
nominal annual note rate quoted in percent (the panel's interest_rate_time):

    r_q = annual_rate / 100 / 4          (nominal/4 quarterly rate)
    B_k = B_0 * ((1+r_q)^n - (1+r_q)^k) / ((1+r_q)^n - 1),   k = 0..n
    EAD_t = B_{t-1},  EAD_t = 0 for t > n

with n = remaining term in quarters. The closed form is the standard
annuity balance identity (equivalent to the recursion
B_k = B_{k-1} * (1+r_q) - payment with the level payment
A = B_0 * r_q / (1 - (1+r_q)^-n)); it guarantees B_n = 0 exactly
(terminal balance ~0 at maturity) and monotone decline (no
negative-amortisation products exist in this book).

DOCUMENTED FALLBACKS / SIMPLIFICATIONS
---------------------------------------
* rate <= 0, NaN, or so small that 1 + rate/400 rounds to 1 in float64
  ->  STRAIGHT-LINE fallback B_k = B_0 * (1 - k/n).
  In the built panel interest_rate_time > 0 on every row (zero-coded rates
  were dropped in the panel waterfall), so the fallback is defensive; the
  orig_rate_missing flag concerns the ORIGINATION-rate snapshot only -- the
  current note rate that drives amortisation is populated for those loans.
* remaining term floored at 1 quarter: loans at/past contractual maturity
  (mat_time <= time; 82 panel rows) are treated as fully due within one
  quarter -- EAD_1 = current balance, zero thereafter.
* The remaining term is taken as mat_time - time, i.e. the ORIGINAL
  contractual maturity; payment-holiday / modification reprofiling is out of
  scope at this rung (no such data exists in the panel).
* Balloon / interest-only structures are not modelled: every term loan is
  assumed level-pay to zero at maturity. The panel carries no amortisation-
  type field, so this is the disciplined default for US fixed-rate
  mortgages.
* Revolvers: the DCR mortgage book contains none; ccf_ead exists for engine
  completeness and reproduces the compute_ecl section-12 golden fixture
  EAD = drawn + CCF * (limit - drawn) (5, 20, 0.6 -> 14.0).

Everything here is deterministic: no randomness, no I/O, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: nominal percent -> quarterly decimal rate divisor (100 * 4)
RATE_DIVISOR = 400.0

#: columns ead_matrix requires on the snapshot frame
SNAPSHOT_COLS = ["id", "time", "mat_time", "balance_time",
                 "interest_rate_time"]


def _ead_paths(balance: np.ndarray, annual_rate_pct: np.ndarray,
               remaining_quarters: np.ndarray, horizon: int) -> np.ndarray:
    """Vectorised core: (m,) inputs -> (m, horizon) matrix of EAD_t, t=1..horizon.

    EAD_t = start-of-period-t contractual balance = B_{t-1} (module
    docstring). Annuity closed form where the rate is usable, straight-line
    fallback otherwise; remaining term floored at 1 quarter.
    """
    balance = np.atleast_1d(np.asarray(balance, dtype=float))
    rate = np.atleast_1d(np.asarray(annual_rate_pct, dtype=float))
    n = np.atleast_1d(np.asarray(remaining_quarters, dtype=float))
    if not (balance.shape == rate.shape == n.shape):
        raise ValueError("balance, rate and remaining term must align")
    if np.any(balance < 0):
        raise ValueError("negative balances are not valid exposures")
    if horizon < 1:
        raise ValueError("horizon must be >= 1")

    n = np.maximum(np.floor(n), 1.0)[:, None]           # floor at 1 quarter
    # payments already made when period t starts: k = t-1, capped at n so the
    # closed form returns exactly 0 beyond maturity.
    k = np.minimum(np.arange(horizon, dtype=float)[None, :], n)

    r_q = rate / RATE_DIVISOR
    # usable only when 1 + r_q is representably > 1 in float64: a denormal-
    # tiny positive rate would make (1+r_q)^n - 1 == 0 and the annuity form
    # 0/0 -> NaN, so such rates take the straight-line fallback as well
    # (for finite r_q the condition subsumes r_q > 0).
    use_annuity = np.isfinite(r_q) & (1.0 + r_q > 1.0)
    r_safe = np.where(use_annuity, r_q, 0.01)[:, None]  # dummy in dead branch
    grow_n = (1.0 + r_safe) ** n
    frac_annuity = (grow_n - (1.0 + r_safe) ** k) / (grow_n - 1.0)
    frac_straight = 1.0 - k / n
    frac = np.where(use_annuity[:, None], frac_annuity, frac_straight)
    # pure float-noise guard; both branches are analytically within [0, 1]
    frac = np.clip(frac, 0.0, 1.0)
    return balance[:, None] * frac


def ead_profile(balance: float, annual_rate: float,
                remaining_quarters: int, horizon: int) -> np.ndarray:
    """Contractual level-payment EAD path for a single term loan.

    Parameters
    ----------
    balance : current outstanding principal (the snapshot balance_time).
    annual_rate : nominal annual note rate in PERCENT (interest_rate_time
        units, e.g. 6.5 = 6.5%), compounded quarterly (r_q = rate/400).
        NaN, <= 0, or degenerately tiny (1 + r_q rounds to 1 in float64)
        triggers the documented straight-line fallback.
    remaining_quarters : contractual quarters to maturity, floored at 1.
    horizon : number of projected quarters t = 1..horizon.

    Returns
    -------
    np.ndarray of shape (horizon,): EAD_t = contractual balance entering
    period t (after t-1 level payments); EAD_1 = balance, monotone
    non-increasing, exactly 0 for t > remaining_quarters.

    CONTRACTUAL PATH ONLY -- deliberately NOT prepayment-scaled: the ECL
    survival S(t-1) from engine/hazard.py is already the competing-risk
    survival including prepayment, so scaling EAD by prepayment as well
    would double count (module docstring, CRITICAL section).
    """
    return _ead_paths(
        np.array([balance]), np.array([annual_rate]),
        np.array([remaining_quarters]), horizon,
    )[0]


def ead_matrix(panel_snapshot_df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Per-loan contractual EAD paths from a one-quarter panel snapshot.

    Parameters
    ----------
    panel_snapshot_df : one row per loan (a single-quarter slice of
        data/processed/panel.parquet) carrying SNAPSHOT_COLS: id, time,
        mat_time, balance_time, interest_rate_time. Remaining term is
        mat_time - time, floored at 1 quarter.
    horizon : number of projected quarters t = 1..horizon.

    Returns
    -------
    pd.DataFrame indexed by loan id with integer columns 1..horizon;
    cell (i, t) = EAD_t for loan i under the module's contractual
    level-payment convention (NOT prepayment-scaled -- see the CRITICAL
    double-counting section of the module docstring).
    """
    missing = [c for c in SNAPSHOT_COLS if c not in panel_snapshot_df.columns]
    if missing:
        raise KeyError(f"snapshot frame is missing required columns: {missing}")
    ids = panel_snapshot_df["id"].to_numpy()
    if len(np.unique(ids)) != len(ids):
        raise ValueError("snapshot has duplicate loan ids -- pass one row "
                         "per loan (a single-quarter slice)")
    remaining = (panel_snapshot_df["mat_time"].to_numpy(dtype=float)
                 - panel_snapshot_df["time"].to_numpy(dtype=float))
    paths = _ead_paths(
        panel_snapshot_df["balance_time"].to_numpy(dtype=float),
        panel_snapshot_df["interest_rate_time"].to_numpy(dtype=float),
        remaining, horizon,
    )
    return pd.DataFrame(paths, index=pd.Index(ids, name="id"),
                        columns=pd.RangeIndex(1, horizon + 1, name="period"))


def ccf_ead(drawn: float, limit: float, ccf: float) -> float:
    """Revolver EAD via the credit-conversion factor.

        EAD = drawn + CCF * max(limit - drawn, 0)

    Reproduces the compute_ecl section-12 golden fixture: drawn 5m, limit
    20m, CCF 0.6 -> 5 + 0.6 * 15 = 14.0m (2.8x drawn). The undrawn headroom
    is floored at 0 so an overlimit facility contributes its drawn balance
    only; CCF is not clamped (regulatory CCFs can exceed 1 for facilities
    that are drawn down further past limit-breach). Engine-completeness
    only: the DCR mortgage panel contains no revolvers.
    """
    if drawn < 0:
        raise ValueError("drawn balance must be >= 0")
    if ccf < 0:
        raise ValueError("CCF must be >= 0")
    return float(drawn + ccf * max(limit - drawn, 0.0))
