"""Golden fixture — §11.4 "Converting a 180-DPD definition to 90 DPD" (Route 2,
the roll-rate bridge), from the IFRS 9 credit-risk study notes.

Worked example (notes, §11.4): a delinquency-bucket transition matrix gives
monthly roll-forward/cure pairs of 0.50/0.12 (90 DPD), 0.55/0.10 (120 DPD) and
0.60/0.08 (150 DPD); the eventual roll-forward per bucket is
q_b = fwd / (fwd + cure), and the roll-through rate is R = q90 * q120 * q150
= 0.81 x 0.85 x 0.88 = 0.60. Starting from D180-calibrated PD_180 = 2.0% and
LGD_180 = 30%, the bridge PD_90 = PD_180 / R and
LGD_90 = (1 - R) * LGD_cure + R * LGD_180 reproduce the printed table
(PD 3.32%, LGD 18.1% / 19.3%, EL 0.600% / 0.640%).

Note: the notes' "0.81 x 0.85 x 0.88 = 0.60" quotes the rounded q values; the
product is carried at full precision (R = 0.602102), which is what reproduces
PD_90 = 3.32% (0.02 / 0.60 would give 3.33%).

Every RESULTS entry is derived from the stated inputs; TARGETS holds the
notes' printed values for comparison only.
"""

import numpy as np

# ---------------------------------------------------------------------------
# Stated inputs (from the notes' roll matrix and D180 calibration)
# ---------------------------------------------------------------------------

# bucket -> (monthly roll-forward, monthly cure)
ROLL_MATRIX = {
    "90dpd": (0.50, 0.12),
    "120dpd": (0.55, 0.10),
    "150dpd": (0.60, 0.08),
}

PD_180 = 0.02        # D180-calibrated probability of default
LGD_180 = 0.30       # D180-calibrated loss given default
LGD_CURE_ZERO = 0.00 # scenario 1: self-cures are loss-free
LGD_CURE_3PCT = 0.03 # scenario 2: self-cures carry a 3% loss

# ---------------------------------------------------------------------------
# Derivations
# ---------------------------------------------------------------------------

# Eventual roll-forward probability per bucket: q_b = fwd / (fwd + cure)
q = {b: fwd / (fwd + cure) for b, (fwd, cure) in ROLL_MATRIX.items()}

# Roll-through rate R = P(reach 180 | reached 90) = q90 * q120 * q150
R = float(np.prod(list(q.values())))

# PD/LGD conversion: PD_90 = PD_180 / R;  LGD_90 = (1-R)*LGD_cure + R*LGD_180
pd_90 = PD_180 / R
lgd_90_cure0 = (1 - R) * LGD_CURE_ZERO + R * LGD_180
lgd_90_cure3 = (1 - R) * LGD_CURE_3PCT + R * LGD_180

# Expected loss EL = PD x LGD under each definition
el_180 = PD_180 * LGD_180
el_90_cure0 = pd_90 * lgd_90_cure0
el_90_cure3 = pd_90 * lgd_90_cure3

RESULTS: dict[str, float] = {
    "q_eventual_rollforward_90dpd": q["90dpd"],
    "q_eventual_rollforward_120dpd": q["120dpd"],
    "q_eventual_rollforward_150dpd": q["150dpd"],
    "roll_through_rate_R": R,
    "pd_90_pct": pd_90 * 100,
    "lgd_90_cure_loss_free_pct": lgd_90_cure0 * 100,
    "lgd_90_cure_loss_3pct_pct": lgd_90_cure3 * 100,
    "el_180_pct": el_180 * 100,
    "el_90_cure_loss_free_pct": el_90_cure0 * 100,
    "el_90_cure_loss_3pct_pct": el_90_cure3 * 100,
}

# Notes' printed values (comparison only — never used in the derivation).
TARGETS: dict[str, float] = {
    "q_eventual_rollforward_90dpd": 0.81,
    "q_eventual_rollforward_120dpd": 0.85,
    "q_eventual_rollforward_150dpd": 0.88,
    "roll_through_rate_R": 0.60,
    "pd_90_pct": 3.32,
    "lgd_90_cure_loss_free_pct": 18.1,
    "lgd_90_cure_loss_3pct_pct": 19.3,
    "el_180_pct": 0.600,
    "el_90_cure_loss_free_pct": 0.600,
    "el_90_cure_loss_3pct_pct": 0.640,
}

# Decimal places at which the notes display each value.
_DISPLAY_DECIMALS: dict[str, int] = {
    "q_eventual_rollforward_90dpd": 2,
    "q_eventual_rollforward_120dpd": 2,
    "q_eventual_rollforward_150dpd": 2,
    "roll_through_rate_R": 2,
    "pd_90_pct": 2,
    "lgd_90_cure_loss_free_pct": 1,
    "lgd_90_cure_loss_3pct_pct": 1,
    "el_180_pct": 3,
    "el_90_cure_loss_free_pct": 3,
    "el_90_cure_loss_3pct_pct": 3,
}


if __name__ == "__main__":
    print(f"{'quantity':<34} {'computed':>12} {'target':>8}  match")
    print("-" * 66)
    for key, target in TARGETS.items():
        computed = RESULTS[key]
        nd = _DISPLAY_DECIMALS[key]
        ok = round(computed, nd) == round(target, nd)
        print(f"{key:<34} {computed:>12.6f} {target:>8.{nd}f}  {'OK' if ok else 'MISMATCH'}")
