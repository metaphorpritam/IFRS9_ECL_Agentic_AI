"""Vasicek one-factor PIT/TTC conditioning and Belkin Z-shift recovery.

METHODOLOGY (knowledge/sources/ifrs9_credit_risk_notes.md section 8)
---------------------------------------------------------------------
ASRF / Vasicek conditioning. Standardised asset return

    X_i = sqrt(rho) * Z + sqrt(1 - rho) * eps_i,   Z, eps_i ~ N(0,1) iid,

with asset correlation rho; default iff X_i < Phi^{-1}(PD_TTC). Conditioning
on the systematic factor Z gives the point-in-time PD

    PD_PIT(Z) = Phi( (Phi^{-1}(PD_TTC) - sqrt(rho) * Z) / sqrt(1 - rho) ).

Good times (Z > 0) compress PDs; recessions (Z < 0) inflate them more than
proportionally. The law of total probability guarantees the TTC anchor
E_Z[PD_PIT(Z)] = PD_TTC exactly; ``anchor_check`` proves it numerically by
Gauss-Hermite quadrature (the same two-method verification as the golden
fixture tests/fixtures/compute_vasicek.py: PD_TTC = 2%, rho = 0.12 gives
PD_PIT = 7.34% at Z = -2, 1.43% at Z = 0, 0.17% at Z = +2).

Z-SHIFT / BELKIN RECOVERY (notes section 8, "Estimating Z and rho")
---------------------------------------------------------------------
From a history of period default RATES, invert the conditioning formula each
period to recover the systematic factor path:

    Z_t = ( Phi^{-1}(PD_TTC,t) - sqrt(1 - rho) * Phi^{-1}(DR_t) ) / sqrt(rho)

then calibrate rho so that Var(Z_t) = 1, consistent with the model's premise
Z ~ N(0,1) (Belkin, Suchower & Forest 1998). ``calibrate_rho`` solves
Var(Z_t(rho)) = 1 by bracketed root finding: as rho -> 0 the 1/sqrt(rho)
factor blows the variance up, as rho -> 1 the variance collapses toward the
(small) variance of the anchor thresholds, so the crossing is unique in
practice. The per-period anchor PD_TTC,t may vary (composition-adjusted
expected rates from a loan-level model -- see analysis/fit_vasicek.py); with
a constant anchor the formula reduces to the classic grade-level Belkin
inversion.

Documented caveat carried from the notes (Basson & van Vuuren 2023): naive
TTC<->PIT round-trips are inconsistent if rho, the default definition, or the
cycle index differ between legs -- conventions here are fixed once (this
module is the single implementation of both legs) and the round trip
invert_z(pit_pd(p, z, rho), p, rho) == z is unit-tested.

Reference rho conventions for comparison in reports:
  * RHO_NOTES = 0.12      -- the study-notes convention for the worked example;
  * RHO_BASEL_RESI = 0.15 -- the Basel IRB supervisory asset correlation for
                             residential mortgages (CRE31.10), a regulatory
                             convention rather than an empirical estimate.

All functions broadcast over numpy arrays and validate domains loudly
(probabilities strictly inside (0,1), rho strictly inside (0,1)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

#: study-notes convention for the worked example (section 8)
RHO_NOTES = 0.12
#: Basel IRB supervisory asset correlation, residential mortgages (CRE31.10)
RHO_BASEL_RESI = 0.15

_GH_NODES_DEFAULT = 80  # Gauss-Hermite order for the anchor integral


def _check_rho(rho: float) -> float:
    rho = float(rho)
    if not 0.0 < rho < 1.0:
        raise ValueError(f"rho must be strictly inside (0, 1); got {rho}")
    return rho


def _check_prob(p, name: str) -> np.ndarray:
    arr = np.asarray(p, dtype=float)
    if arr.size == 0:
        raise ValueError(f"{name} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite values")
    if np.any(arr <= 0.0) or np.any(arr >= 1.0):
        raise ValueError(f"{name} must be strictly inside (0, 1); "
                         f"got range [{arr.min()}, {arr.max()}]")
    return arr


def pit_pd(pd_ttc, z, rho):
    """Vasicek conditional (point-in-time) PD given systematic factor Z.

    PD_PIT(Z) = Phi( (Phi^{-1}(pd_ttc) - sqrt(rho) * z) / sqrt(1 - rho) ).

    Broadcasts over ``pd_ttc`` and ``z``; returns a scalar float when both
    are scalars, else an ndarray. Z > 0 is a GOOD state (PD below TTC),
    Z < 0 a downturn (PD above TTC) -- the notes' sign convention.
    """
    rho = _check_rho(rho)
    p = _check_prob(pd_ttc, "pd_ttc")
    z_arr = np.asarray(z, dtype=float)
    out = norm.cdf((norm.ppf(p) - np.sqrt(rho) * z_arr) / np.sqrt(1.0 - rho))
    if np.ndim(pd_ttc) == 0 and np.ndim(z) == 0:
        return float(out)
    return out


def hybrid_pd(pd_ttc, z, rho, alpha: float = 0.5):
    """Damped PIT/TTC hybrid: condition on alpha * Z instead of Z.

    alpha in [0, 1] is the PIT-ness weight (Aguais/Forest dual-ratings
    convention): alpha = 1 is the fully point-in-time PD; alpha = 0 is the
    cycle-NEUTRAL PD, i.e. pit_pd at Z = 0 -- which sits slightly BELOW the
    TTC mean anchor because PD_PIT is convex in Z (Jensen: the notes' 2%/0.12
    example has a Z = 0 conditional PD of 1.43% vs the 2% anchor). Damping
    therefore trades cycle pass-through for a small downward bias relative to
    the E_Z anchor -- a philosophy/presentation device, not an unbiased ECL
    input; the anchor property holds exactly only at alpha = 1.
    """
    if not 0.0 <= float(alpha) <= 1.0:
        raise ValueError(f"alpha must lie in [0, 1]; got {alpha}")
    return pit_pd(pd_ttc, np.asarray(z, dtype=float) * float(alpha), rho)


def invert_z(observed_rate, ttc_anchor, rho):
    """Recover the systematic factor Z from an observed default rate.

    Exact inversion of ``pit_pd`` (identifying the period default rate with
    PD_PIT, the infinite-granularity ASRF limit):

        Z = ( Phi^{-1}(ttc_anchor) - sqrt(1 - rho) * Phi^{-1}(observed_rate) )
            / sqrt(rho)

    Round trip: invert_z(pit_pd(p, z, rho), p, rho) == z (unit-tested).
    An observed rate ABOVE the anchor yields Z < 0 (downturn). Broadcasts;
    scalar in -> scalar out.
    """
    rho = _check_rho(rho)
    obs = _check_prob(observed_rate, "observed_rate")
    anchor = _check_prob(ttc_anchor, "ttc_anchor")
    out = (norm.ppf(anchor) - np.sqrt(1.0 - rho) * norm.ppf(obs)) \
        / np.sqrt(rho)
    if np.ndim(observed_rate) == 0 and np.ndim(ttc_anchor) == 0:
        return float(out)
    return out


def anchor_check(pd_ttc: float, rho: float,
                 n: int = _GH_NODES_DEFAULT) -> tuple[float, float]:
    """Verify the TTC anchor E_Z[PD_PIT(Z)] = PD_TTC by Gauss-Hermite.

    With physicists' Hermite nodes x_i / weights w_i and Z ~ N(0,1):
        E[f(Z)] = (1/sqrt(pi)) * sum_i w_i * f(sqrt(2) * x_i).

    Returns ``(expected_pd, abs_error)`` where abs_error =
    |expected_pd - pd_ttc|. The law of total probability makes the identity
    exact; at n = 80 nodes the numerical error is far below 1e-6 for any
    portfolio-relevant (pd_ttc, rho).
    """
    nodes, weights = np.polynomial.hermite.hermgauss(int(n))
    vals = pit_pd(float(pd_ttc), np.sqrt(2.0) * nodes, rho)
    expected = float(np.sum(weights * vals) / np.sqrt(np.pi))
    return expected, abs(expected - float(pd_ttc))


@dataclass(frozen=True)
class BelkinResult:
    """Output of ``calibrate_rho`` (Belkin Z-shift calibration).

    Attributes
    ----------
    rho        : calibrated asset correlation with Var(z) = 1
    z          : recovered systematic-factor path at the calibrated rho
    mean_z     : sample mean of z -- NOT forced to 0; a material non-zero
                 mean says the TTC anchors sit off the sample's cycle centre
                 (report it, don't hide it)
    var_z      : sample variance of z at rho (== 1.0 up to solver tolerance)
    n_periods  : number of periods used
    ddof       : degrees-of-freedom convention used for the variance
    """

    rho: float
    z: np.ndarray
    mean_z: float
    var_z: float
    n_periods: int
    ddof: int


def calibrate_rho(observed_rates, ttc_anchors,
                  rho_bounds: tuple[float, float] = (1e-4, 0.95),
                  ddof: int = 1) -> BelkinResult:
    """Belkin calibration: find rho such that Var(Z_t(rho)) = 1.

    Parameters
    ----------
    observed_rates : per-period observed default rates, strictly in (0, 1).
    ttc_anchors : per-period TTC anchor rates (scalar broadcast allowed) --
        composition-adjusted expected rates, or a constant grade-level TTC.
    rho_bounds : bracket for the root search.
    ddof : variance convention (1 = sample variance about the sample mean,
        the default; Var is computed about the mean, so a non-zero mean_z
        does not inflate it).

    Solves Var(Z_t(rho)) - 1 = 0 by ``brentq``. The variance is strictly
    decreasing in rho wherever the numerator variance is positive
    (d/drho of [a - sqrt(1-rho) b] / sqrt(rho) shrinks every deviation),
    so the bracketed root is unique. Raises ValueError with a diagnostic if
    the bracket does not straddle 1 (e.g. default rates so flat that even
    rho -> 0 cannot push Var(Z) up to 1).
    """
    obs = np.atleast_1d(_check_prob(observed_rates, "observed_rates"))
    anchors = np.broadcast_to(
        np.atleast_1d(_check_prob(ttc_anchors, "ttc_anchors")), obs.shape
    ).astype(float)
    if obs.ndim != 1:
        raise ValueError("observed_rates must be one-dimensional")
    if len(obs) < 3:
        raise ValueError(f"need >= 3 periods to calibrate rho; got {len(obs)}")

    ppf_obs = norm.ppf(obs)
    ppf_anchor = norm.ppf(anchors)

    def z_at(rho: float) -> np.ndarray:
        return (ppf_anchor - np.sqrt(1.0 - rho) * ppf_obs) / np.sqrt(rho)

    def excess_var(rho: float) -> float:
        return float(np.var(z_at(rho), ddof=ddof)) - 1.0

    lo, hi = rho_bounds
    _check_rho(lo), _check_rho(hi)
    f_lo, f_hi = excess_var(lo), excess_var(hi)
    if not (f_lo > 0.0 > f_hi):
        raise ValueError(
            "cannot bracket Var(Z)=1: Var(Z) - 1 is "
            f"{f_lo:+.4f} at rho={lo} and {f_hi:+.4f} at rho={hi}. "
            "Default-rate history too flat (widen the low bound) or too "
            "wild (widen the high bound) for a unit-variance Z."
        )
    rho_hat = float(brentq(excess_var, lo, hi, xtol=1e-12, rtol=1e-14))
    z = z_at(rho_hat)
    return BelkinResult(
        rho=rho_hat,
        z=z,
        mean_z=float(z.mean()),
        var_z=float(np.var(z, ddof=ddof)),
        n_periods=len(obs),
        ddof=int(ddof),
    )
