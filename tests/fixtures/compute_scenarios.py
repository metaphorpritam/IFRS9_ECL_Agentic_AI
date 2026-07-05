"""Golden fixture — §9.2 "Multiple probability-weighted scenarios" worked example.

Source: IFRS9 credit-risk study notes, §9.2 ("the cost of single-scenario ECL",
Jensen's inequality applied to ECL). Setup quoted from the notes: "€100m EAD,
LGD 40%, PD_TTC = 2%, rho = 0.12; GDP growth maps to the cycle as
Z = (g - 2.0)/1.5" with three scenarios — Upside (g=+3.5%, w=0.25),
Base (g=+2.0%, w=0.50), Downside (g=-2.5%, w=0.25).

Every value below is DERIVED from those inputs via the one-factor Vasicek
PIT transform  PD_PIT(Z) = Phi((Phi^-1(PD_TTC) - sqrt(rho)*Z) / sqrt(1-rho))
and  ECL = PD * LGD * EAD.  The notes' printed values live only in TARGETS.

Notes' printed values reproduced exactly (to displayed precision):
scenario PDs 0.53%/1.43%/13.97%, scenario ECLs €0.21m/€0.57m/€5.59m,
weighted PD 4.34%, weighted ECL €1.74m, average path g=1.25% -> PD 2.25%,
single-path ECL €0.90m, 48% understatement, ratio ~1.9x.
"""

from scipy.stats import norm

# ----------------------------------------------------------------- inputs
EAD_EURM = 100.0          # exposure at default, EUR millions
LGD = 0.40                # loss given default
PD_TTC = 0.02             # through-the-cycle 1y PD
RHO = 0.12                # asset correlation
G_ANCHOR, G_SCALE = 2.0, 1.5   # macro link: Z = (g - 2.0) / 1.5

SCENARIOS = {              # name: (GDP growth %, probability weight)
    "upside":   (+3.5, 0.25),
    "base":     (+2.0, 0.50),
    "downside": (-2.5, 0.25),
}


def z_from_growth(g_pct: float) -> float:
    """Map GDP growth (%) to the systematic cycle factor Z."""
    return (g_pct - G_ANCHOR) / G_SCALE


def pd_pit(z: float) -> float:
    """One-factor Vasicek point-in-time PD conditional on cycle state Z."""
    return norm.cdf((norm.ppf(PD_TTC) - RHO**0.5 * z) / (1.0 - RHO) ** 0.5)


def ecl_eurm(pd: float) -> float:
    """One-year ECL in EUR millions: PD x LGD x EAD."""
    return pd * LGD * EAD_EURM


# ------------------------------------------------------------ derivation
RESULTS: dict[str, float] = {}

for name, (g, w) in SCENARIOS.items():
    z = z_from_growth(g)
    pd = pd_pit(z)
    RESULTS[f"{name}_z"] = z
    RESULTS[f"{name}_pd_pit_pct"] = 100.0 * pd
    RESULTS[f"{name}_ecl_eurm"] = ecl_eurm(pd)

weighted_pd = sum(w * pd_pit(z_from_growth(g)) for g, w in SCENARIOS.values())
weighted_ecl = sum(w * ecl_eurm(pd_pit(z_from_growth(g)))
                   for g, w in SCENARIOS.values())

# Single-scenario alternative: ECL evaluated on the weighted-average macro path.
avg_g = sum(w * g for g, w in SCENARIOS.values())
avg_path_pd = pd_pit(z_from_growth(avg_g))
avg_path_ecl = ecl_eurm(avg_path_pd)

RESULTS["weighted_pd_pct"] = 100.0 * weighted_pd
RESULTS["weighted_ecl_eurm"] = weighted_ecl
RESULTS["avg_gdp_growth_pct"] = avg_g
RESULTS["avg_path_pd_pct"] = 100.0 * avg_path_pd
RESULTS["avg_path_ecl_eurm"] = avg_path_ecl
RESULTS["understatement_pct"] = 100.0 * (1.0 - avg_path_ecl / weighted_ecl)
RESULTS["weighted_over_single_ratio"] = weighted_ecl / avg_path_ecl

# ------------------------------- notes' printed values (comparison only)
TARGETS: dict[str, float] = {
    "upside_z": 1.0,
    "upside_pd_pit_pct": 0.53,
    "upside_ecl_eurm": 0.21,
    "base_z": 0.0,
    "base_pd_pit_pct": 1.43,
    "base_ecl_eurm": 0.57,
    "downside_z": -3.0,
    "downside_pd_pit_pct": 13.97,
    "downside_ecl_eurm": 5.59,
    "weighted_pd_pct": 4.34,
    "weighted_ecl_eurm": 1.74,
    "avg_gdp_growth_pct": 1.25,
    "avg_path_pd_pct": 2.25,
    "avg_path_ecl_eurm": 0.90,
    "understatement_pct": 48.0,
    "weighted_over_single_ratio": 1.9,
}

# decimal places at which the notes display each figure
_DISPLAY_DP = {
    "understatement_pct": 0,          # "a 48% understatement"
    "weighted_over_single_ratio": 1,  # "~1.9x the single-path figure"
    "upside_z": 1, "base_z": 1, "downside_z": 1,
}   # everything else printed to 2 dp


if __name__ == "__main__":
    print(f"{'quantity':<28} {'computed':>12} {'target':>10}  match")
    print("-" * 60)
    for key, target in TARGETS.items():
        dp = _DISPLAY_DP.get(key, 2)
        computed = RESULTS[key]
        ok = round(computed, dp) == round(target, dp)
        print(f"{key:<28} {computed:>12.4f} {target:>10.{dp}f}  {'OK' if ok else 'MISMATCH'}")
