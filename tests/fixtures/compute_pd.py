"""Golden-value fixture for the PD worked examples in the IFRS9 study notes.

Covers the two worked examples that cite ``compute_pd.py``:

* Section 6.1 (Retail scorecards — WOE/IV): "Worked example — WOE/IV for
  origination LTV (10,000 applications, 500 bads)". Four coarse-classed LTV
  bins with goods {2850, 3800, 1900, 950} and bads {60, 150, 140, 150};
  the notes report per-bin bad rates, good/bad distributions, WOE, IV
  contributions, and a total IV of 0.4403 (a "strong" characteristic).

* Section 7.2 (Merton structural model): "Worked example — distance to
  default. V = EUR 120m, D = EUR 100m, sigma_A = 20%, mu = 8%, T = 1y",
  giving DD = (ln 1.2 + 0.06)/0.20 = 1.2116 and PD = Phi(-DD) = 11.28%.

Every value in RESULTS is derived from the stated inputs; TARGETS holds the
numbers as printed in the notes and is used only for comparison.
"""

from decimal import Decimal

import numpy as np
from scipy.stats import norm

# ----------------------------------------------------------------------------
# Section 6.1 — WOE / IV for origination LTV
# ----------------------------------------------------------------------------
# 10,000 applications, 500 bads => 9,500 goods.
BIN_LABELS = ["ltv_le_60", "ltv_60_80", "ltv_80_90", "ltv_gt_90"]
GOODS = np.array([2850, 3800, 1900, 950], dtype=float)
BADS = np.array([60, 150, 140, 150], dtype=float)

G, B = GOODS.sum(), BADS.sum()          # 9,500 goods and 500 bads
assert G + B == 10_000 and B == 500

bad_rate = BADS / (GOODS + BADS)        # per-bin observed default rate
dist_good = GOODS / G                   # Dist^G_i = g_i / G
dist_bad = BADS / B                     # Dist^B_i = b_i / B
woe = np.log(dist_good / dist_bad)      # WOE_i = ln(Dist^G_i / Dist^B_i)
iv_contrib = (dist_good - dist_bad) * woe
iv_total = iv_contrib.sum()             # IV = sum_i (Dist^G_i - Dist^B_i) WOE_i

# ----------------------------------------------------------------------------
# Section 7.2 — Merton distance to default
# ----------------------------------------------------------------------------
V = 120.0        # firm asset value, EUR m
D = 100.0        # face value of debt (default barrier), EUR m
SIGMA_A = 0.20   # asset volatility
MU = 0.08        # asset drift
T = 1.0          # horizon, years

dd = (np.log(V / D) + (MU - 0.5 * SIGMA_A**2) * T) / (SIGMA_A * np.sqrt(T))
merton_pd = norm.cdf(-dd)               # PD = Phi(-DD)

# ----------------------------------------------------------------------------
# Results vs. the values printed in the notes
# ----------------------------------------------------------------------------
RESULTS: dict[str, float] = {}
for i, lbl in enumerate(BIN_LABELS):
    RESULTS[f"bad_rate_pct_{lbl}"] = float(bad_rate[i] * 100)
    RESULTS[f"dist_good_{lbl}"] = float(dist_good[i])
    RESULTS[f"dist_bad_{lbl}"] = float(dist_bad[i])
    RESULTS[f"woe_{lbl}"] = float(woe[i])
    RESULTS[f"iv_contrib_{lbl}"] = float(iv_contrib[i])
RESULTS["iv_total_ltv"] = float(iv_total)
RESULTS["merton_dd"] = float(dd)
RESULTS["merton_pd_pct"] = float(merton_pd * 100)

TARGETS: dict[str, float] = {
    # | LTV bin | bad rate | Dist^G | Dist^B |    WOE   | IV contrib |
    "bad_rate_pct_ltv_le_60": 2.06,
    "dist_good_ltv_le_60": 0.30,
    "dist_bad_ltv_le_60": 0.12,
    "woe_ltv_le_60": 0.9163,
    "iv_contrib_ltv_le_60": 0.1649,
    "bad_rate_pct_ltv_60_80": 3.80,
    "dist_good_ltv_60_80": 0.40,
    "dist_bad_ltv_60_80": 0.30,
    "woe_ltv_60_80": 0.2877,
    "iv_contrib_ltv_60_80": 0.0288,
    "bad_rate_pct_ltv_80_90": 6.86,
    "dist_good_ltv_80_90": 0.20,
    "dist_bad_ltv_80_90": 0.28,
    "woe_ltv_80_90": -0.3365,
    "iv_contrib_ltv_80_90": 0.0269,
    "bad_rate_pct_ltv_gt_90": 13.64,
    "dist_good_ltv_gt_90": 0.10,
    "dist_bad_ltv_gt_90": 0.30,
    "woe_ltv_gt_90": -1.0986,
    "iv_contrib_ltv_gt_90": 0.2197,
    "iv_total_ltv": 0.4403,
    # Merton worked example
    "merton_dd": 1.2116,
    "merton_pd_pct": 11.28,
}


def _display_decimals(x: float) -> int:
    """Decimals the notes display for a target value (e.g. 0.4403 -> 4)."""
    exponent = Decimal(str(x)).as_tuple().exponent
    return max(-exponent, 0)


def matches(key: str) -> bool:
    """True if the computed value rounds to the notes' printed value."""
    nd = _display_decimals(TARGETS[key])
    return round(RESULTS[key], nd) == round(TARGETS[key], nd)


if __name__ == "__main__":
    width = max(len(k) for k in TARGETS)
    print(f"{'quantity':<{width}}  {'computed':>12}  {'target':>10}  match")
    print("-" * (width + 36))
    for key, target in TARGETS.items():
        print(
            f"{key:<{width}}  {RESULTS[key]:>12.6f}  {target:>10}  "
            f"{'OK' if matches(key) else 'MISMATCH'}"
        )
    n_ok = sum(matches(k) for k in TARGETS)
    print(f"\n{n_ok}/{len(TARGETS)} values match the notes' printed figures.")
