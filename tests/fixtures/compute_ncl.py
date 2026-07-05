"""Golden fixture — §11.3 "Discounting future values" (Net Credit Loss).

Worked example from the IFRS 9 credit-risk notes, §11.3 ("Worked example —
discounting a realised loss"): default UPB EUR 200,000 at the credit event,
EIR = 5.5%; post-default recoveries (REO sale 170k @ m20, MI 12k @ m22,
non-MI 2k @ m23) and expenses (taxes/insurance/maintenance 5k @ m10,
legal/foreclosure 4k @ m16) are each discounted to the default date with
DF(m) = (1 + EIR)^(-m/12).

The notes contrast three measures:
  * face-value loss   200,000 + 9,000 - 184,000 = 25,000  -> severity 12.5%
  * EIR-discounted    200,000 + 8,506 - 168,170 = 40,336  -> LGD 20.2%
  * agency nominal    face loss + accrued interest (note rate 5.5% on UPB
    over the ~26-month non-performing span, ~23,833) = 48,833 -> 24.4%

Every RESULTS entry is derived from the stated inputs; TARGETS holds the
values printed in the notes for comparison only.
"""

import pandas as pd

# ----------------------------------------------------------------------
# Inputs stated in the notes
# ----------------------------------------------------------------------
EAD_DEFAULT = 200_000.0          # UPB at the credit event (EUR), sits at t=0
EIR = 0.055                      # original effective interest rate
NONPERFORMING_MONTHS = 26        # span used by the agency accrued-interest proxy

# (component, kind, month, amount)
CASH_FLOWS = pd.DataFrame(
    [
        ("net_sale_proceeds_reo", "recovery", 20, 170_000.0),
        ("mi_recoveries",         "recovery", 22,  12_000.0),
        ("non_mi_recoveries",     "recovery", 23,   2_000.0),
        ("taxes_ins_maintenance", "expense",  10,   5_000.0),
        ("legal_foreclosure",     "expense",  16,   4_000.0),
    ],
    columns=["component", "kind", "month", "amount"],
)


def discount_factor(month: float, eir: float = EIR) -> float:
    """DF(m) = (1 + EIR)^(-m/12), discounting a month-m flow to the default date."""
    return (1.0 + eir) ** (-month / 12.0)


# ----------------------------------------------------------------------
# Derivations
# ----------------------------------------------------------------------
cf = CASH_FLOWS.copy()
cf["df"] = cf["month"].apply(discount_factor)
cf["pv"] = cf["amount"] * cf["df"]

recoveries = cf[cf["kind"] == "recovery"]
expenses = cf[cf["kind"] == "expense"]

face_recoveries = recoveries["amount"].sum()
face_expenses = expenses["amount"].sum()
pv_recoveries = recoveries["pv"].sum()
pv_expenses = expenses["pv"].sum()

# Face-value (timing-ignorant) loss and severity
face_loss = EAD_DEFAULT + face_expenses - face_recoveries
face_severity_pct = 100.0 * face_loss / EAD_DEFAULT

# IFRS 9 EIR-discounted loss:  NCL_PV = EAD + sum(DF*Expense) - sum(DF*Recovery)
discounted_loss = EAD_DEFAULT + pv_expenses - pv_recoveries
discounted_lgd_pct = 100.0 * discounted_loss / EAD_DEFAULT

# Agency "Actual Loss" proxy: nominal flows + delinquent accrued interest
# (note rate on UPB over the non-performing span; simple, not compounded)
accrued_interest = EAD_DEFAULT * EIR * NONPERFORMING_MONTHS / 12.0
nominal_ncl = face_loss + accrued_interest
nominal_severity_pct = 100.0 * nominal_ncl / EAD_DEFAULT

by_component = cf.set_index("component")

RESULTS: dict[str, float] = {
    "df_reo_m20": by_component.loc["net_sale_proceeds_reo", "df"],
    "pv_reo_m20": by_component.loc["net_sale_proceeds_reo", "pv"],
    "df_mi_m22": by_component.loc["mi_recoveries", "df"],
    "pv_mi_m22": by_component.loc["mi_recoveries", "pv"],
    "df_non_mi_m23": by_component.loc["non_mi_recoveries", "df"],
    "pv_non_mi_m23": by_component.loc["non_mi_recoveries", "pv"],
    "df_taxes_m10": by_component.loc["taxes_ins_maintenance", "df"],
    "pv_taxes_m10": by_component.loc["taxes_ins_maintenance", "pv"],
    "df_legal_m16": by_component.loc["legal_foreclosure", "df"],
    "pv_legal_m16": by_component.loc["legal_foreclosure", "pv"],
    "face_recoveries_eur": face_recoveries,
    "pv_recoveries_eur": pv_recoveries,
    "pv_expenses_eur": pv_expenses,
    "face_loss_eur": face_loss,
    "face_severity_pct": face_severity_pct,
    "discounted_loss_ncl_pv_eur": discounted_loss,
    "discounted_lgd_pct": discounted_lgd_pct,
    "accrued_interest_eur": accrued_interest,
    "nominal_ncl_agency_eur": nominal_ncl,
    "nominal_severity_pct": nominal_severity_pct,
}

# Values as printed in the notes (comparison only — never used in computation)
TARGETS: dict[str, float] = {
    "df_reo_m20": 0.9146,
    "pv_reo_m20": 155_487.0,
    "df_mi_m22": 0.9065,
    "pv_mi_m22": 10_878.0,
    "df_non_mi_m23": 0.9025,
    "pv_non_mi_m23": 1_805.0,
    "df_taxes_m10": 0.9564,
    "pv_taxes_m10": 4_782.0,
    "df_legal_m16": 0.9311,
    "pv_legal_m16": 3_724.0,
    "face_recoveries_eur": 184_000.0,
    "pv_recoveries_eur": 168_170.0,
    "pv_expenses_eur": 8_506.0,
    "face_loss_eur": 25_000.0,
    "face_severity_pct": 12.5,
    "discounted_loss_ncl_pv_eur": 40_336.0,
    "discounted_lgd_pct": 20.2,
    "accrued_interest_eur": 23_833.0,
    "nominal_ncl_agency_eur": 48_833.0,
    "nominal_severity_pct": 24.4,
}

# Decimal places each target is displayed at in the notes
_DISPLAY_DECIMALS: dict[str, int] = {
    key: (4 if key.startswith("df_") else 1 if key.endswith("_pct") else 0)
    for key in TARGETS
}


def _matches(key: str) -> bool:
    nd = _DISPLAY_DECIMALS[key]
    return round(RESULTS[key], nd) == round(TARGETS[key], nd)


if __name__ == "__main__":
    header = f"{'quantity':<28} {'computed':>14} {'target':>12}  match"
    print(header)
    print("-" * len(header))
    for key, target in TARGETS.items():
        nd = _DISPLAY_DECIMALS[key]
        print(
            f"{key:<28} {RESULTS[key]:>14,.{nd}f} {target:>12,.{nd}f}  "
            f"{'OK' if _matches(key) else 'MISMATCH'}"
        )
    n_bad = sum(not _matches(k) for k in TARGETS)
    print("-" * len(header))
    print("all values match" if n_bad == 0 else f"{n_bad} value(s) mismatch")
