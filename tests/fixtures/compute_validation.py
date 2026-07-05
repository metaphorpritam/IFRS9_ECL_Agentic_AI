"""Golden-fixture verification for the model-validation worked examples.

Source: IFRS 9 / credit-risk study notes, section 13 ("Validation, Backtesting
and Staging Effectiveness"), subsections 12.2 (calibration backtests) and 12.3
(stability).

Worked example 1 — grade-level binomial backtest: "Grade with n = 1,000,
assigned PD = 2%, observed d = 28 defaults." One-sided binomial
p = P(D >= 28) = 0.0507 narrowly fails to reject at alpha = 5% (critical count
d_crit = 29), while the Jeffreys test (posterior Beta(d + 1/2, n - d + 1/2))
gives p = P(pi <= 0.02 | data) = 0.041 and rejects.

Worked example 2 — PSI: "Five score bands, development shares
[0.10, 0.25, 0.30, 0.25, 0.10] vs current [0.06, 0.20, 0.30, 0.28, 0.16]",
giving PSI = 0.0204 + 0.0112 + 0 + 0.0034 + 0.0282 = 0.0632 — below the 0.10
threshold, so the population is formally stable.

Every value in RESULTS is derived from the stated inputs; TARGETS holds the
notes' printed numbers for comparison only.
"""

import numpy as np
from scipy import stats

# ----------------------------------------------------------------------------
# Worked example 1 — grade-level binomial backtest (section 12.2)
# ----------------------------------------------------------------------------
N_OBLIGORS = 1_000       # obligors in the grade
ASSIGNED_PD = 0.02       # assigned grade PD
OBSERVED_DEFAULTS = 28   # defaults observed over the horizon
ALPHA = 0.05             # one-sided significance level

# One-sided binomial test: reject H0 ("assigned PD adequate") if
# p = P(D >= d | n, PD) <= alpha, with D ~ Binomial(n, PD) under independence.
binomial_p = stats.binom.sf(OBSERVED_DEFAULTS - 1, N_OBLIGORS, ASSIGNED_PD)
binomial_rejects = binomial_p <= ALPHA

# Critical count: smallest d such that P(D >= d) <= alpha.
# binom.isf gives the largest k with P(D > k) > alpha ... use a direct scan
# for auditability (the grade is small enough that this is instant).
critical_count = next(
    d for d in range(N_OBLIGORS + 1)
    if stats.binom.sf(d - 1, N_OBLIGORS, ASSIGNED_PD) <= ALPHA
)

# Jeffreys test: with a Jeffreys Beta(1/2, 1/2) prior the posterior for the
# true default probability pi is Beta(d + 1/2, n - d + 1/2); the p-value is
# the posterior mass at or below the assigned PD, P(pi <= PD | data).
jeffreys_p = stats.beta.cdf(
    ASSIGNED_PD, OBSERVED_DEFAULTS + 0.5, N_OBLIGORS - OBSERVED_DEFAULTS + 0.5
)
jeffreys_rejects = jeffreys_p <= ALPHA

# ----------------------------------------------------------------------------
# Worked example 2 — Population Stability Index over five score bands (12.3)
# ----------------------------------------------------------------------------
EXPECTED_SHARES = np.array([0.10, 0.25, 0.30, 0.25, 0.10])  # development e_i
ACTUAL_SHARES = np.array([0.06, 0.20, 0.30, 0.28, 0.16])    # current a_i

# PSI = sum_i (a_i - e_i) * ln(a_i / e_i)
psi_terms = (ACTUAL_SHARES - EXPECTED_SHARES) * np.log(
    ACTUAL_SHARES / EXPECTED_SHARES
)
psi = float(psi_terms.sum())


def psi_band(value: float) -> str:
    """Standard PSI convention: <0.10 stable; 0.10-0.25 monitor; >0.25 shift."""
    if value < 0.10:
        return "stable"
    if value <= 0.25:
        return "monitor/investigate"
    return "material shift"


# ----------------------------------------------------------------------------
# Results vs the notes' printed values
# ----------------------------------------------------------------------------
RESULTS: dict[str, float] = {
    "binomial_backtest_p_value": float(binomial_p),
    "binomial_rejects_at_5pct": float(binomial_rejects),   # 0.0 = fails to reject
    "binomial_critical_count": float(critical_count),
    "jeffreys_p_value": float(jeffreys_p),
    "jeffreys_rejects_at_5pct": float(jeffreys_rejects),   # 1.0 = rejects
    "psi_term_band1": float(psi_terms[0]),
    "psi_term_band2": float(psi_terms[1]),
    "psi_term_band3": float(psi_terms[2]),
    "psi_term_band4": float(psi_terms[3]),
    "psi_term_band5": float(psi_terms[4]),
    "psi_total": psi,
    "psi_is_stable": float(psi < 0.10),                    # 1.0 = stable band
}

TARGETS: dict[str, float] = {
    "binomial_backtest_p_value": 0.0507,   # "p = P(D >= 28) = 0.0507"
    "binomial_rejects_at_5pct": 0.0,       # "narrowly fails to reject"
    "binomial_critical_count": 29.0,       # "the critical count is d_crit = 29"
    "jeffreys_p_value": 0.041,             # "p = P(pi <= 0.02 | data) = 0.041"
    "jeffreys_rejects_at_5pct": 1.0,       # "— rejects"
    "psi_term_band1": 0.0204,
    "psi_term_band2": 0.0112,
    "psi_term_band3": 0.0,
    "psi_term_band4": 0.0034,
    "psi_term_band5": 0.0282,
    "psi_total": 0.0632,                   # "PSI = ... = 0.0632"
    "psi_is_stable": 1.0,                  # "remains formally stable" (<0.10)
}


def _displayed_decimals(target: float) -> int:
    """Number of decimals the notes display for a target (min 1)."""
    text = f"{target!r}"
    return len(text.split(".")[1]) if "." in text else 1


if __name__ == "__main__":
    print(f"{'quantity':<30} {'computed':>14} {'target':>10}  match")
    print("-" * 66)
    all_ok = True
    for key, target in TARGETS.items():
        computed = RESULTS[key]
        ok = round(computed, _displayed_decimals(target)) == target
        all_ok &= ok
        print(f"{key:<30} {computed:>14.6f} {target:>10}  {'OK' if ok else 'MISMATCH'}")
    print("-" * 66)
    print(f"binomial decision : p={binomial_p:.4f} vs alpha={ALPHA} -> "
          f"{'reject' if binomial_rejects else 'fail to reject'}")
    print(f"jeffreys decision : p={jeffreys_p:.4f} vs alpha={ALPHA} -> "
          f"{'reject' if jeffreys_rejects else 'fail to reject'}")
    print(f"PSI classification: {psi:.4f} -> {psi_band(psi)}")
    print("ALL MATCH" if all_ok else "SOME MISMATCHES")
