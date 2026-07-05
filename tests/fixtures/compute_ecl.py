"""Golden fixture — core ECL engine: PD term structure, workout LGD, CCF EAD.

Source: IFRS9 credit-risk study notes (knowledge/sources/
ifrs9_credit_risk_notes.md), three worked examples citing compute_ecl.py:

* §3 "12-month vs lifetime ECL": "5-year amortising loan, principal
  EUR 1,000,000 repaid EUR 200,000 at each year-end, EIR = 6%, constant
  LGD = 35%, default losses crystallising at year-end. Annual hazards
  lambda_t follow a mild seasoning hump" (lambda = 1.5%, 2.0%, 2.2%, 2.0%,
  1.8%). Targets: 12m ECL EUR 4,952.83; lifetime ECL EUR 16,571.39 ("a
  3.35x jump"); 5-year cumulative PD 9.15%.

* §10 "Workout LGD": "EAD = EUR 100,000 at default, EIR = 7%. Recoveries:
  EUR 30,000 at 12m, EUR 35,000 at 24m, collateral sale EUR 20,000 at 30m.
  Direct costs: EUR 4,000 at 6m, EUR 3,000 at 24m." Targets: PV(rec)
  75,495; PV(cost) 6,487; RR 69.0% -> LGD 31.0% (22% undiscounted).

* §12 "Revolvers and the credit-conversion factor": "drawn EUR 5m, limit
  EUR 20m, estimated CCF = 60% -> EAD = 5 + 0.6 x 15 = 14.0 (EUR 14.0m) —
  2.8x the current drawn balance."

Everything below is DERIVED from the stated inputs via
    ECL_t   = S(t-1) * lambda_t * LGD * EAD_t * (1+EIR)^-t
    LGD     = 1 - (sum PV(recoveries) - sum PV(costs)) / EAD_default
    EAD_rev = Drawn + CCF * (Limit - Drawn)
The notes' printed values appear only in TARGETS for comparison printing.
"""

import numpy as np

# ----------------------------------------------------------------------------
# §3 inputs — 5-year amortising loan
# ----------------------------------------------------------------------------
PRINCIPAL = 1_000_000.0            # EUR, repaid in five equal instalments
REPAYMENT = 200_000.0              # EUR, at each year-end
EIR_LOAN = 0.06                    # effective interest rate
LGD_LOAN = 0.35                    # constant LGD
HAZARDS = np.array([0.015, 0.020, 0.022, 0.020, 0.018])   # lambda_t, t=1..5

_years = np.arange(1, HAZARDS.size + 1)
# S(t-1): probability of surviving to the start of year t
_survival_start = np.concatenate(([1.0], np.cumprod(1.0 - HAZARDS)[:-1]))
_marginal_pd = _survival_start * HAZARDS
# Losses crystallise at year-end, before that year's repayment: the exposure
# at risk in year t is the balance after t-1 repayments.
_ead = PRINCIPAL - REPAYMENT * (_years - 1)
_df = (1.0 + EIR_LOAN) ** -_years
_ecl_by_year = _marginal_pd * LGD_LOAN * _ead * _df

ECL_12M = float(_ecl_by_year[0])
ECL_LIFETIME = float(_ecl_by_year.sum())
CUM_PD_5Y = float(1.0 - np.prod(1.0 - HAZARDS))

# ----------------------------------------------------------------------------
# §10 inputs — workout LGD with EIR discounting
# ----------------------------------------------------------------------------
WORKOUT_EAD = 100_000.0            # EUR at default
WORKOUT_EIR = 0.07
RECOVERIES = [(12, 30_000.0), (24, 35_000.0), (30, 20_000.0)]  # (month, EUR)
COSTS = [(6, 4_000.0), (24, 3_000.0)]                          # (month, EUR)


def present_value(cashflows: list[tuple[int, float]], rate: float) -> float:
    """PV at the default date: DF(m) = (1+rate)^-(m/12) for a flow at month m."""
    return float(sum(a * (1.0 + rate) ** (-m / 12.0) for m, a in cashflows))


PV_REC = present_value(RECOVERIES, WORKOUT_EIR)
PV_COST = present_value(COSTS, WORKOUT_EIR)
RECOVERY_RATE = (PV_REC - PV_COST) / WORKOUT_EAD
WORKOUT_LGD = 1.0 - RECOVERY_RATE
_face_rec = sum(a for _, a in RECOVERIES)
_face_cost = sum(a for _, a in COSTS)
WORKOUT_LGD_UNDISC = 1.0 - (_face_rec - _face_cost) / WORKOUT_EAD

# ----------------------------------------------------------------------------
# §12 inputs — revolver EAD via CCF
# ----------------------------------------------------------------------------
DRAWN_M = 5.0                      # EUR m
LIMIT_M = 20.0                     # EUR m
CCF = 0.60

REVOLVER_EAD_M = DRAWN_M + CCF * (LIMIT_M - DRAWN_M)
REVOLVER_EAD_MULTIPLE = REVOLVER_EAD_M / DRAWN_M

# ----------------------------------------------------------------------------
# Computed results (derived — nothing hardcoded)
# ----------------------------------------------------------------------------
RESULTS: dict[str, float] = {
    # §3 term-structure table, row by row
    **{f"survival_start_year_{t}": float(_survival_start[t - 1])
       for t in _years},
    **{f"marginal_pd_year_{t}": float(_marginal_pd[t - 1]) for t in _years},
    **{f"discount_factor_year_{t}": float(_df[t - 1]) for t in _years},
    **{f"ecl_year_{t}_eur": float(_ecl_by_year[t - 1]) for t in _years},
    "ecl_12m_eur": ECL_12M,
    "ecl_lifetime_eur": ECL_LIFETIME,
    "lifetime_over_12m_ratio": ECL_LIFETIME / ECL_12M,
    "cumulative_pd_5y_pct": CUM_PD_5Y * 100.0,
    # §10 workout LGD
    "workout_pv_recoveries_eur": PV_REC,
    "workout_pv_costs_eur": PV_COST,
    "workout_recovery_rate_pct": RECOVERY_RATE * 100.0,
    "workout_lgd_pct": WORKOUT_LGD * 100.0,
    "workout_lgd_undiscounted_pct": WORKOUT_LGD_UNDISC * 100.0,
    # §12 revolver EAD
    "revolver_ead_eur_m": REVOLVER_EAD_M,
    "revolver_ead_over_drawn": REVOLVER_EAD_MULTIPLE,
}

# ----------------------------------------------------------------------------
# Target values exactly as printed in the notes (comparison only)
# ----------------------------------------------------------------------------
TARGETS: dict[str, float] = {
    "survival_start_year_1": 1.00000,
    "survival_start_year_2": 0.98500,
    "survival_start_year_3": 0.96530,
    "survival_start_year_4": 0.94406,
    "survival_start_year_5": 0.92518,
    "marginal_pd_year_1": 0.01500,
    "marginal_pd_year_2": 0.01970,
    "marginal_pd_year_3": 0.02124,
    "marginal_pd_year_4": 0.01888,
    "marginal_pd_year_5": 0.01665,
    "discount_factor_year_1": 0.9434,
    "discount_factor_year_2": 0.8900,
    "discount_factor_year_3": 0.8396,
    "discount_factor_year_4": 0.7921,
    "discount_factor_year_5": 0.7473,
    "ecl_year_1_eur": 4_952.83,
    "ecl_year_2_eur": 4_909.22,
    "ecl_year_3_eur": 3_744.44,
    "ecl_year_4_eur": 2_093.80,
    "ecl_year_5_eur": 871.10,
    "ecl_12m_eur": 4_952.83,          # "12-month ECL = EUR 4,952.83"
    "ecl_lifetime_eur": 16_571.39,    # "Lifetime ECL = EUR 16,571.39"
    "lifetime_over_12m_ratio": 3.35,  # "a 3.35x jump on Stage 2 transfer"
    "cumulative_pd_5y_pct": 9.15,     # "5-year cumulative PD is only 9.15%"
    "workout_pv_recoveries_eur": 75_495.0,
    "workout_pv_costs_eur": 6_487.0,
    "workout_recovery_rate_pct": 69.0,
    "workout_lgd_pct": 31.0,
    "workout_lgd_undiscounted_pct": 22.0,
    "revolver_ead_eur_m": 14.0,
    "revolver_ead_over_drawn": 2.8,
}

# Decimal places the notes display each value to (for match-at-shown-precision)
_DISPLAY_DECIMALS: dict[str, int] = {
    **{f"survival_start_year_{t}": 5 for t in _years},
    **{f"marginal_pd_year_{t}": 5 for t in _years},
    **{f"discount_factor_year_{t}": 4 for t in _years},
    **{f"ecl_year_{t}_eur": 2 for t in _years},
    "ecl_12m_eur": 2,
    "ecl_lifetime_eur": 2,
    "lifetime_over_12m_ratio": 2,
    "cumulative_pd_5y_pct": 2,
    "workout_pv_recoveries_eur": 0,
    "workout_pv_costs_eur": 0,
    "workout_recovery_rate_pct": 1,
    "workout_lgd_pct": 1,
    "workout_lgd_undiscounted_pct": 0,
    "revolver_ead_eur_m": 1,
    "revolver_ead_over_drawn": 1,
}


if __name__ == "__main__":
    print("ECL engine golden fixtures — notes §3 (term structure), "
          "§10 (workout LGD), §12 (CCF EAD)")
    print(f"{'quantity':30s} {'computed':>16s} {'target':>12s}  match")
    print("-" * 68)
    for key, computed in RESULTS.items():
        target = TARGETS[key]
        nd = _DISPLAY_DECIMALS[key]
        match = round(computed, nd) == round(target, nd)
        print(f"{key:30s} {computed:16.6f} {target:12.4f}  "
              f"{'OK' if match else 'MISMATCH'}")
