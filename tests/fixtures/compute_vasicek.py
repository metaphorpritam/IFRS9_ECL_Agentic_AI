"""Golden fixture — Vasicek one-factor PIT-from-TTC conditioning.

Source: IFRS9 credit-risk study notes, §8 "PIT vs TTC: The Vasicek One-Factor
Framework" (knowledge/sources/ifrs9_credit_risk_notes.md).

Worked example quoted from the notes: "PD_TTC = 2%, rho = 0.12
(Phi^{-1}(0.02) = -2.0537)" — the PIT PD is tabulated at marked cycle points
Z in {+2.0, +1.0, 0.0, -1.0, -2.0, -2.5}, and the notes verify that the law
of total probability holds exactly: "numerically E_Z[PD_PIT(Z)] = 0.020000
= PD_TTC".

Everything below is DERIVED from the stated inputs (PD_TTC, rho, the Z grid)
via the Vasicek conditioning formula

    PD_PIT(Z) = Phi( (Phi^{-1}(PD_TTC) - sqrt(rho) * Z) / sqrt(1 - rho) )

with scipy's exact normal CDF/PPF. The anchor property E_Z[PD_PIT] = PD_TTC
is verified numerically two independent ways: Gauss-Hermite quadrature and a
fine trapezoidal grid over the standard-normal density. Target values appear
only in TARGETS for comparison printing.
"""

import numpy as np
from scipy.stats import norm

# ----------------------------------------------------------------------------
# Inputs as stated in the notes
# ----------------------------------------------------------------------------
PD_TTC = 0.02          # through-the-cycle PD (2%)
RHO = 0.12             # asset correlation
Z_POINTS = [2.0, 1.0, 0.0, -1.0, -2.0, -2.5]   # marked cycle states


def pd_pit(z: np.ndarray | float, pd_ttc: float = PD_TTC, rho: float = RHO):
    """Vasicek conditional (point-in-time) PD given systematic factor Z."""
    return norm.cdf((norm.ppf(pd_ttc) - np.sqrt(rho) * z) / np.sqrt(1.0 - rho))


def expected_pd_gauss_hermite(pd_ttc: float = PD_TTC, rho: float = RHO,
                              n: int = 80) -> float:
    """E_Z[PD_PIT(Z)] for Z ~ N(0,1) via Gauss-Hermite quadrature.

    With physicists' Hermite nodes x_i and weights w_i:
        E[f(Z)] = (1/sqrt(pi)) * sum_i w_i * f(sqrt(2) * x_i).
    """
    nodes, weights = np.polynomial.hermite.hermgauss(n)
    return float(np.sum(weights * pd_pit(np.sqrt(2.0) * nodes, pd_ttc, rho))
                 / np.sqrt(np.pi))


def expected_pd_grid(pd_ttc: float = PD_TTC, rho: float = RHO,
                     z_max: float = 10.0, n: int = 200_001) -> float:
    """E_Z[PD_PIT(Z)] via fine trapezoidal integration against phi(z)."""
    z = np.linspace(-z_max, z_max, n)
    return float(np.trapezoid(pd_pit(z, pd_ttc, rho) * norm.pdf(z), z))


# ----------------------------------------------------------------------------
# Computed results (derived — nothing hardcoded)
# ----------------------------------------------------------------------------
RESULTS: dict[str, float] = {
    "default_threshold_ppf_002": float(norm.ppf(PD_TTC)),
    "pd_pit_pct_z_plus_2_0": float(pd_pit(2.0)) * 100.0,
    "pd_pit_pct_z_plus_1_0": float(pd_pit(1.0)) * 100.0,
    "pd_pit_pct_z_0_0": float(pd_pit(0.0)) * 100.0,
    "pd_pit_pct_z_minus_1_0": float(pd_pit(-1.0)) * 100.0,
    "pd_pit_pct_z_minus_2_0": float(pd_pit(-2.0)) * 100.0,
    "pd_pit_pct_z_minus_2_5": float(pd_pit(-2.5)) * 100.0,
    "expected_pd_pit_gauss_hermite": expected_pd_gauss_hermite(),
    "expected_pd_pit_fine_grid": expected_pd_grid(),
}

# ----------------------------------------------------------------------------
# Target values exactly as printed in the notes (comparison only)
# ----------------------------------------------------------------------------
TARGETS: dict[str, float] = {
    "default_threshold_ppf_002": -2.0537,     # Phi^{-1}(0.02)
    "pd_pit_pct_z_plus_2_0": 0.17,            # PD_PIT at Z = +2.0, in %
    "pd_pit_pct_z_plus_1_0": 0.53,            # PD_PIT at Z = +1.0, in %
    "pd_pit_pct_z_0_0": 1.43,                 # PD_PIT at Z =  0.0, in %
    "pd_pit_pct_z_minus_1_0": 3.44,           # PD_PIT at Z = -1.0, in %
    "pd_pit_pct_z_minus_2_0": 7.34,           # PD_PIT at Z = -2.0, in %
    "pd_pit_pct_z_minus_2_5": 10.27,          # PD_PIT at Z = -2.5, in %
    "expected_pd_pit_gauss_hermite": 0.020000,  # anchor: E_Z[PD_PIT] = PD_TTC
    "expected_pd_pit_fine_grid": 0.020000,      # same anchor, second method
}

# Decimal places the notes display each value to (for match-at-shown-precision)
_DISPLAY_DECIMALS: dict[str, int] = {
    "default_threshold_ppf_002": 4,
    "pd_pit_pct_z_plus_2_0": 2,
    "pd_pit_pct_z_plus_1_0": 2,
    "pd_pit_pct_z_0_0": 2,
    "pd_pit_pct_z_minus_1_0": 2,
    "pd_pit_pct_z_minus_2_0": 2,
    "pd_pit_pct_z_minus_2_5": 2,
    "expected_pd_pit_gauss_hermite": 6,
    "expected_pd_pit_fine_grid": 6,
}


if __name__ == "__main__":
    print(f"Vasicek PIT-from-TTC conditioning: PD_TTC={PD_TTC:.2%}, rho={RHO}")
    print(f"{'quantity':36s} {'computed':>14s} {'target':>10s}  match")
    print("-" * 72)
    for key, computed in RESULTS.items():
        target = TARGETS[key]
        nd = _DISPLAY_DECIMALS[key]
        match = round(computed, nd) == round(target, nd)
        print(f"{key:36s} {computed:14.6f} {target:10.4f}  "
              f"{'OK' if match else 'MISMATCH'}")
