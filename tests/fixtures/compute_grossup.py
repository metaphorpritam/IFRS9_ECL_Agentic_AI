"""Golden fixture — gross-up from a short-horizon PD/ECL to lifetime.

Source: IFRS9 credit-risk study notes, §9 "Forward-looking conditioning"
(knowledge/sources/ifrs9_credit_risk_notes.md), definition "The gross-up
factor" and worked example "grossing up to lifetime (compute_grossup.py)".

Worked example quoted from the notes: "A 7-year loan whose annual hazard is
PIT-elevated for the first three years (the R&S window) then reverts to a
1.5% TTC level. Cumulative PD and the implied gross-up to the 84-month
lifetime" — with ECL "simplified to cumulative-PD x LGD x EAD to isolate the
horizon effect (no within-horizon discounting)", EAD 100, LGD 30%.

The notes state the hazard path only qualitatively; the exact annual hazards
are recovered from the printed cumulative PDs. The unique clean path that
reproduces all four printed rows (2.50%, 6.46%, 9.43%, 12.12%) is a linear
PIT decay inside the 3-year R&S window from 2.5% (the 12-month PIT PD) in
steps of 0.3pp — [2.5%, 2.2%, 1.9%] — followed by a single mean-reversion
year at the midpoint 1.7%, then the 1.5% TTC hazard to maturity. That path
is constructed below from those stated ingredients (h1, TTC level, window
length); every downstream number is derived:

    S(n)   = prod_{i<=n} (1 - h_i)          (annual survival product)
    CPD(n) = 1 - S(n)                       (cumulative PD to year n)
    GU(H -> life) = CPD(life) / CPD(H)      (gross-up factor)
    ECL(H) ~= CPD(H) * LGD * EAD            (undiscounted, per the notes)

Target values appear only in TARGETS for comparison printing.
"""

import numpy as np

# ----------------------------------------------------------------------------
# Inputs as stated in the notes
# ----------------------------------------------------------------------------
MATURITY_YEARS = 7          # 7-year loan (84-month lifetime)
RS_WINDOW_YEARS = 3         # reasonable-and-supportable (R&S) forecast window
H1_PIT = 0.025              # year-1 PIT hazard = 12-month PIT PD (2.50%)
RS_DECAY_STEP = 0.003       # linear PIT decay inside the R&S window (0.3pp/yr)
H_TTC = 0.015               # long-run TTC hazard the curve reverts to (1.5%)
EAD = 100.0
LGD = 0.30

HORIZON_MONTHS = [12, 36, 60, 84]   # the table's horizons (years 1, 3, 5, 7)


def hazard_path() -> np.ndarray:
    """Annual hazard vector: linear PIT decay in the R&S window, one
    mean-reversion year at the midpoint between the last R&S hazard and the
    TTC level, then flat TTC to maturity."""
    rs = H1_PIT - RS_DECAY_STEP * np.arange(RS_WINDOW_YEARS)   # 2.5, 2.2, 1.9%
    reversion = np.array([(rs[-1] + H_TTC) / 2.0])             # 1.7%
    n_ttc = MATURITY_YEARS - RS_WINDOW_YEARS - len(reversion)  # 3 years
    return np.concatenate([rs, reversion, np.full(n_ttc, H_TTC)])


def cumulative_pd(hazards: np.ndarray) -> np.ndarray:
    """CPD(n) = 1 - prod_{i<=n} (1 - h_i) for each year n."""
    return 1.0 - np.cumprod(1.0 - hazards)


# ----------------------------------------------------------------------------
# Computed results (derived — nothing hardcoded)
# ----------------------------------------------------------------------------
_hazards = hazard_path()
_cpd = cumulative_pd(_hazards)                 # indexed by year-1
_cpd_life = _cpd[MATURITY_YEARS - 1]

RESULTS: dict[str, float] = {}
for _m in HORIZON_MONTHS:
    _c = float(_cpd[_m // 12 - 1])
    RESULTS[f"cum_pd_{_m}m_pct"] = 100.0 * _c
    RESULTS[f"gross_up_{_m}m_to_life"] = float(_cpd_life) / _c
    RESULTS[f"ecl_{_m}m"] = _c * LGD * EAD

# ----------------------------------------------------------------------------
# Targets: the values printed in the notes' table (comparison only)
# ----------------------------------------------------------------------------
TARGETS: dict[str, float] = {
    "cum_pd_12m_pct": 2.50,  "gross_up_12m_to_life": 4.85, "ecl_12m": 0.75,
    "cum_pd_36m_pct": 6.46,  "gross_up_36m_to_life": 1.88, "ecl_36m": 1.94,
    "cum_pd_60m_pct": 9.43,  "gross_up_60m_to_life": 1.29, "ecl_60m": 2.83,
    "cum_pd_84m_pct": 12.12, "gross_up_84m_to_life": 1.00, "ecl_84m": 3.64,
}

if __name__ == "__main__":
    print("Annual hazard path (%):",
          "  ".join(f"{h * 100:.1f}" for h in _hazards))
    print()
    header = f"{'quantity':<24}{'computed':>12}{'target':>10}{'match':>8}"
    print(header)
    print("-" * len(header))
    for key, target in TARGETS.items():
        computed = RESULTS[key]
        ok = round(computed, 2) == target
        print(f"{key:<24}{computed:>12.4f}{target:>10.2f}"
              f"{'OK' if ok else 'MISMATCH':>8}")
