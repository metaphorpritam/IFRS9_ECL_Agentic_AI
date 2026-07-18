"""Realized-loss workout LGD on real SFLLD D90 defaults (rung 3).

THE UPGRADE OVER DCR (engine/lgd.py, wiki/pages/lgd-model.md): the DCR engine
fits on the CoreLogic vendor's PRE-COMPUTED `lgd_time` field -- a number
handed to us with no visible construction. Freddie Mac's own servicing tape
instead reports the individual CASH COMPONENTS of every liquidation
(`net_sale_proceeds`, `mi_recoveries`, `non_mi_recoveries`, `total_expenses`,
`delinquent_accrued_interest`, `zero_balance_removal_upb`), so this module
RECONSTRUCTS realized loss from first principles and locks the sign
convention with a fixture loan traced from the raw servicing history
(tests/test_freddie_lgd.py) rather than trusting an opaque vendor column.

--------------------------------------------------------------------------
SIGN CONVENTION (empirically verified, not assumed -- see the fixture test)
--------------------------------------------------------------------------
Freddie's `actual_loss_calculation` reconciles EXACTLY (to sub-dollar
rounding) to

    actual_loss_calculation = net_sale_proceeds + mi_recoveries
                               + non_mi_recoveries + total_expenses
                               - zero_balance_removal_upb
                               - delinquent_accrued_interest

with `total_expenses` (and its sub-components legal_costs /
maintenance_preservation_costs / taxes_insurance / miscellaneous_expenses)
already reported NEGATIVE by Freddie (a cost reduces the recovery). A
liquidation that fully recovers the removal UPB nets to ~0; a shortfall
therefore makes `actual_loss_calculation` NEGATIVE. This module defines

    realized_loss = -actual_loss_calculation

so realized_loss > 0 is an economic LOSS (the common-sense direction) and
realized_loss < 0 is a net GAIN (MI/proceeds exceeded UPB + costs + accrued
interest -- empirically ~1.9% of liquidations, floored at 0 in `severity`,
never in `realized_loss` itself, so the floor mass is visible and reported).

--------------------------------------------------------------------------
OUTCOME PARTITION (had_d90_event loans; exhaustive + disjoint by construction)
--------------------------------------------------------------------------
loan_orig.parquet's `terminal_outcome` column is NOT usable here: build_panel
._terminal_outcome() always labels a had_d90_event loan "d90_default"
regardless of what happened afterward (that label answers "did this loan
ever go 90+ DPD", not "how did the D90 episode resolve") -- see
build_panel.py's `_terminal_outcome`. This module partitions the SAME
population by its own logic, keyed off the terminal zero_balance_code (from
the FULL un-truncated servicing tape, already on loan_orig.parquet) plus,
for loans that never got a terminal code, a fresh look at the raw
post-truncation delinquency path (panel_monthly.parquet stops at the first
D90 row -- absorbing censoring -- so whether a loan later CURED is not
visible there; see `resolve_reverted_status`, which re-reads
ingest.read_svcg_vintage for just that subset):

  CURE         zero_balance_code in {01, 16}
                 01 prepaid_or_matured -- paid off despite the D90 episode.
                 16 RPL securitization -- Freddie's own label for a
                 REPERFORMING loan pooled for sale: by definition the loan
                 stopped being distressed before this exit, so it is coded
                 a cure (documented judgement call, not a vendor label).
               OR zero_balance_code is NaN (no terminal code -- the loan is
                 still on Freddie's book as of the 2025-09 performance
                 cutoff) AND the raw servicing history's LAST observed row
                 shows delinquency reverted below 90 DPD, not REO
                 (`resolve_reverted_status`).
  LIQUIDATION  zero_balance_code in {02, 03, 09} -- third-party sale, short
               sale/charge-off, REO disposition. These are the only three
               codes with a populated `actual_loss_calculation` on >90% of
               rows (verified empirically -- see LIQUIDATION_ZB_CODES) --
               PLUS zero_balance_code == 15 (whole loan sale) WHEN
               `actual_loss_calculation` is populated (853 of 922 D90 code-15
               rows, 92.5%). This is a deliberate CORRECTION of a prior draft
               of this module, which lumped every code-15 row into
               "unresolved" on the assumption that a whole-loan sale's
               ultimate resolution is unobservable. It is not: empirically,
               loss-bearing code-15 rows load overwhelmingly onto
               zero_balance_effective_date 2014-2025 (853-row loss subset:
               96% in 2015+) and carry severities (mean 0.459, median 0.390
               on realized_loss / upb_at_default) statistically
               indistinguishable from third-party sale (mean 0.445) and REO
               (mean 0.584) -- i.e. these are Freddie's NON-PERFORMING LOAN
               (NPL) SALE program disposals (seasoned GFC-vintage defaults
               sold to note investors at a Freddie-computed realized loss),
               a genuine liquidation-equivalent economic event, not a
               "resolution unobserved" censoring case. See
               tests/test_freddie_lgd.py::test_npl_sale_code15_split_by_loss_data
               for the empirical lock. The remaining 69 code-15 rows with NO
               loss field (7.5%, concentrated in 2005-2008 vintages, pre-NPL-
               program) genuinely have an unobservable ultimate resolution
               and stay UNRESOLVED below. disposition_type for this subset
               labels as "whole_loan_sale" (ZERO_BALANCE_CODE_LABELS), fed
               into stage 2 alongside the other three disposition types.
  UNRESOLVED   zero_balance_code == 96, OR zero_balance_code == 15 with NO
               populated actual_loss_calculation, OR the NaN case above when
               the last observed row is still 90+ DPD / REO.
                 96 defect prior to disposition -- a repurchase-like removal
                 BEFORE any disposition; `actual_loss_calculation` is NaN on
                 every single one of these rows (checked, not assumed) --
                 whoever repurchased the loan bears the eventual loss, not
                 Freddie, so there is nothing to observe.
                 15 whole loan sale, no loss field -- sold to another
                 investor with no Freddie-computed loss recorded (pre-2015
                 vintages overwhelmingly); the ultimate resolution (cure or
                 liquidation) is UNOBSERVED here, unlike the loss-bearing
                 NPL-sale subset above.
               All are excluded from the fit exactly like DCR's resolved-
               workouts-only rule (engine/lgd.py: "unresolved lgd_time is
               not a realised outcome") -- and carry the SAME documented
               selection-bias direction: loans that resolve fast are over-
               represented in the observed (cure/liquidation) population,
               so fitted cure is biased up / severity down for cohorts near
               the panel's own window end (2025-09) or for anything that
               exited Freddie's book before a final disposition.

COVID CAVEAT (Phase-A finding, recorded in shared facts): D90 entries spike
to 8,698 in 2020 alone (vs ~1-6k/year elsewhere) -- forbearance-driven, NOT a
loss event (90+DPD->liquidation collapsed >10x in 2020-21). Those loans
overwhelmingly resolve CURE (deferral/reinstatement), which is exactly what
this partition shows -- not a modeling correction, an honest consequence of
the D90 flag capturing forbearance administration in 2020, reported in
lgd_report.md rather than patched.

--------------------------------------------------------------------------
SEVERITY DENOMINATOR: UPB AT DEFAULT vs zero_balance_removal_upb
--------------------------------------------------------------------------
`severity = max(realized_loss, 0) / upb_at_default` where upb_at_default is
current_actual_upb on panel_monthly's own first-D90-event row (the EAD-at-
default convention used throughout this project, e.g. engine/ead.py) -- NOT
`zero_balance_removal_upb` (the UPB at the FINAL liquidation row, which can
differ from continued interest capitalization / negative amortization /
partial curtailments during the workout). Reconciliation (see
freddie/fit_lgd.py's diagnostics, reported in lgd_report.md): the two are
essentially the same loan-level number (correlation 0.997, mean ratio
zero_balance_removal_upb / upb_at_default = 1.002), so the choice moves
severities by ~0pp on average -- but upb_at_default is the theoretically
correct EAD base (observable AT the default date, not years later at
resolution) and is what any ECL assembly multiplying LGD x EAD must use.

--------------------------------------------------------------------------
SEVERITY > 1 / < 0 TAIL (mirrors engine/lgd.py's excess-loss loading, but
see freddie/fit_lgd.py's honest verdict on whether a CONSTANT loading is
still defensible here)
--------------------------------------------------------------------------
6.6% of liquidations have severity > 1 (workout costs + accrued interest
push the loss past upb_at_default); 1.9% are < 0 (net recoveries). Both are
real, not data errors. `sev_capped = severity.clip(0, SEV_CAP)` feeds the
fractional-logit link (Papke-Wooldridge, matching engine/lgd.py); the
floored-negative mass and the beyond-cap excess mass are both reported
separately, never silently discarded. Unlike DCR's single national panel,
the SFLLD liquidation-year cycle here spans the full 2006-2025 GFC-through-
modern era with a clearly visible severity hump (peak ~0.53-0.58 in
2011-2016, well below 0.2 before 2008 and after 2019) -- freddie/fit_lgd.py
checks whether a CONSTANT excess-loss loading (DCR's convention, +0.0255)
still holds up once the liquidation-year covariate is already in the
regression, or whether the beyond-cap tail itself is cycle-dependent enough
that a constant loading would misstate stress-period severity.

--------------------------------------------------------------------------
STAGE 1 -- CURE (logit, resolved rows: cure ∪ liquidation, i.e. NOT unresolved)
--------------------------------------------------------------------------
Drivers: updated_ltv at default (via state HPI -- freddie.macro.merge_macro,
the geographic-resolution upgrade over DCR's national-only LTV), fico
(credit_score / 100, matches DCR's fico_s naming), loan_age at default,
property_state (fixed effects -- the regional/foreclosure-process
heterogeneity that stage 2's judicial/non-judicial dummy only partially
explains), and era (ERA_OF_VINTAGE from freddie/eda.py -- vintage cohort,
NOT the calendar/liquidation-year cycle used in stage 2).

STAGE 2 -- SEVERITY | LIQUIDATION (fractional logit, liquidation rows with a
populated actual_loss_calculation only -- "loss not yet finalized" rows,
concentrated in the most recent 1-2 liquidation years and a handful of early
vintages, are additionally excluded here, documented and counted in
fit_meta; they still count as "liquidation" for stage 1's cure target)
--------------------------------------------------------------------------
Drivers: updated_ltv at default, liquidation-year (bucketed cycle phase --
LIQ_YEAR_BUCKETS), judicial-vs-non-judicial state (JUDICIAL_STATES, a
documented static classification -- state foreclosure regimes rarely change
within 2005-2025, but this IS a point-in-time simplification), disposition
type (zero_balance_code label: third_party_sale / short_sale_or_charge_off /
reo_disposition / whole_loan_sale -- the loss-bearing NPL-sale code-15 subset,
see the outcome-partition section above).

TRAIN/OOT SPLIT (mirrors DCR: split by CALENDAR time, here the D90 default
month, not vintage/origination) -- SPLIT_CUTOFF = 2019-01: train = defaults
before 2019, OOT = 2019 onward. OOT is calendar-time out-of-sample by
construction but is NOT a clean regime test: 53% of OOT D90 events are the
2020 COVID spike (see caveat above), so OOT cure rates are pulled up by
forbearance administration, not by the model's own extrapolation -- reported
honestly in lgd_report.md, decomposed 2019 / 2020-21 COVID / 2022-25.

DOCUMENTED SIMPLIFICATIONS (kept in sync with fit_lgd.py's report):
  * JUDICIAL_STATES is a single static classification (no within-sample
    regime changes modeled).
  * zero_balance_code == 16 (RPL securitization) is treated as a CURE by
    judgement, not a vendor label -- it never carries a realized loss field.
  * zero_balance_code == 96 has NO observable loss (100% NaN
    actual_loss_calculation) and is folded into "unresolved" alongside the
    small (69-row, pre-2015) no-loss-field subset of code 15; the 853-row
    loss-bearing code-15 (NPL sale) subset is treated as LIQUIDATION, not
    unresolved (see outcome-partition section above -- a correction versus a
    prior draft of this module that lumped ALL of code 15 into unresolved).
  * Liquidations with actual_loss_calculation still NaN ("not yet
    finalized") are excluded from the severity fit only, not from the cure
    stage's liquidation outcome.
  * No downturn add-on; LGD is point-in-time (matches engine/lgd.py).
  * EX-POST severity covariates (liquidation-year bucket, disposition type)
    are only known once a loan actually liquidates -- unlike DCR's severity
    stage (uer_lag1/ltv10/fico_s/loan_age, all available forward via a
    macro-scenario path), `predict_components`/`predict_lgd` here are
    calibration/diagnostic tools scored on ALREADY-RESOLVED history (train
    or OOT, exactly like engine/lgd.py's own OOT sample), NOT a
    forward-scoring API for a still-performing loan of unknown eventual
    liquidation date/type. Wiring this into a live ECL assembly would need a
    projected liquidation-year (e.g. default date + an expected workout-lag
    distribution) substituted for the realized one -- documented future
    work, not built here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from freddie import ingest
from freddie.eda import ERA_OF_VINTAGE
from freddie.macro import merge_macro

# --------------------------------------------------------------------------
# Outcome-partition constants
# --------------------------------------------------------------------------
CURE_ZB_CODES = frozenset({"01", "16"})
LIQUIDATION_ZB_CODES = frozenset({"02", "03", "09"})
# zero_balance_code == "15" (whole loan sale) is NOT a static membership call:
# it is "liquidation" only when actual_loss_calculation is populated (the NPL
# -sale subset, see module docstring); otherwise "unresolved". Handled
# explicitly in partition_outcomes(), not via a frozenset like the other codes.
NPL_SALE_ZB_CODE = "15"
UNRESOLVED_EXIT_ZB_CODES = frozenset({"96"})
REVERT_DLQ_THRESHOLD = 3   # dlq_num < 3 == below 90 DPD (module docstring)

SEV_CAP = 1.0

# Liquidation-year cycle buckets (module docstring: coarser than raw calendar
# year so small-n tails -- e.g. 10 liquidations in 2006 -- don't destabilize
# the severity regression; the by-year exhibit still uses the raw year).
LIQ_YEAR_BUCKETS: list[tuple[int, int, str]] = [
    (0, 2007, "pre-2008"),
    (2008, 2009, "2008-09 crash"),
    (2010, 2012, "2010-12 peak workout"),
    (2013, 2016, "2013-16 recovery"),
    (2017, 2019, "2017-19 calm"),
    (2020, 9999, "2020+ covid-modern"),
]
LIQ_YEAR_BUCKET_ORDER = [b[2] for b in LIQ_YEAR_BUCKETS]

# Documented, static judicial-foreclosure-state classification (compiled from
# widely published foreclosure-law summaries; current as of the mid-2020s).
# Simplification, stated plainly: some states are "hybrid" (permit both
# judicial and non-judicial routes depending on instrument/lender choice --
# e.g. FL is judicial-dominant, TX is essentially non-judicial-only) and this
# is a single point-in-time classification with no within-sample (2005-2025)
# regime changes modeled.
JUDICIAL_STATES = frozenset({
    "CT", "DE", "FL", "IL", "IN", "KS", "KY", "LA", "ME", "NE",
    "NJ", "NM", "NY", "ND", "OH", "OK", "PA", "SC", "SD", "VT",
    "WI", "DC",
})

SPLIT_CUTOFF = pd.Timestamp("2019-01-01")  # default_month >= this -> OOT

_LGD_RHS_CURE = "ltv10 + fico_s + loan_age_at_default + C(era) + C(property_state)"
_LGD_RHS_SEV = "ltv10 + C(liq_year_bucket) + is_judicial + C(disposition_type)"
CURE_FORMULA = "cure ~ " + _LGD_RHS_CURE
SEVERITY_FORMULA = "sev_capped ~ " + _LGD_RHS_SEV

LOAN_ORIG_REQUIRED_COLS = [
    "loan_sequence_number", "vintage", "property_state", "credit_score",
    "orig_ltv", "orig_upb", "first_payment_date", "had_d90_event",
    "zero_balance_code", "zero_balance_effective_date",
    "actual_loss_calculation",
]
PANEL_MONTHLY_REQUIRED_COLS = [
    "loan_sequence_number", "d90_event", "current_actual_upb",
    "loan_age", "monthly_reporting_period",
]


def _yyyymm(dt: pd.Series) -> pd.Series:
    """datetime64 -> int YYYYMM (the format freddie.macro.merge_macro expects
    for both its month_col and first_payment_date -- see module docstring)."""
    return (dt.dt.year * 100 + dt.dt.month).astype("Int64")


def liq_year_bucket(year: pd.Series) -> pd.Categorical:
    out = pd.Series(pd.NA, index=year.index, dtype="object")
    for lo, hi, label in LIQ_YEAR_BUCKETS:
        out.loc[year.between(lo, hi)] = label
    return pd.Categorical(out, categories=LIQ_YEAR_BUCKET_ORDER, ordered=True)


# --------------------------------------------------------------------------
# Outcome partition
# --------------------------------------------------------------------------
def resolve_reverted_status(nan_zb_d90: pd.DataFrame) -> pd.Series:
    """For D90 loans with zero_balance_code NaN (never reached a terminal
    disposition on the full servicing tape), re-read the RAW servicing
    history (ingest.read_svcg_vintage) -- panel_monthly.parquet's absorbing-
    D90 truncation hides everything after the first D90 row, so whether the
    loan later reverted below 90 DPD is only visible in the raw tape.

    Groups internally by `vintage` so callers can restrict to a subset of
    vintages (tests use a couple of small ones; freddie/fit_lgd.py uses all
    17). Returns a bool Series aligned to nan_zb_d90.index (True = reverted
    below 90 DPD and not REO by its last observed row -- a cure via
    reversion; False = still 90+ DPD / REO -- unresolved).
    """
    if nan_zb_d90.empty:
        return pd.Series([], dtype=bool)
    out = pd.Series(False, index=nan_zb_d90.index)
    for year, grp in nan_zb_d90.groupby("vintage", observed=True):
        svcg = ingest.read_svcg_vintage(int(year))
        ids = set(grp["loan_sequence_number"])
        sub = svcg[svcg["loan_sequence_number"].isin(ids)]
        if sub.empty:
            continue
        idx = sub.groupby("loan_sequence_number", observed=True)["monthly_reporting_period"].idxmax()
        term = sub.loc[idx].set_index("loan_sequence_number")
        reverted = (term["dlq_num"].fillna(99) < REVERT_DLQ_THRESHOLD) & ~term["is_reo_acquisition"]
        out.loc[grp.index] = grp["loan_sequence_number"].map(reverted).fillna(False).to_numpy()
    return out


def partition_outcomes(d90: pd.DataFrame) -> pd.Series:
    """Exhaustive + disjoint {cure, liquidation, unresolved} label per D90
    loan (module docstring). `d90` must be already filtered to
    had_d90_event == True and carry zero_balance_code + loan_sequence_number
    + vintage."""
    zb = d90["zero_balance_code"]
    has_loss = d90["actual_loss_calculation"].notna()
    outcome = pd.Series(pd.NA, index=d90.index, dtype="object")
    outcome.loc[zb.isin(LIQUIDATION_ZB_CODES)] = "liquidation"
    outcome.loc[zb.isin(CURE_ZB_CODES)] = "cure"
    outcome.loc[zb.isin(UNRESOLVED_EXIT_ZB_CODES)] = "unresolved"
    # code 15 (whole loan sale): liquidation-equivalent (NPL sale) IFF a loss
    # was actually calculated; otherwise its ultimate resolution is
    # unobserved (module docstring's outcome-partition section).
    outcome.loc[(zb == NPL_SALE_ZB_CODE) & has_loss] = "liquidation"
    outcome.loc[(zb == NPL_SALE_ZB_CODE) & ~has_loss] = "unresolved"

    nan_mask = zb.isna()
    if nan_mask.any():
        reverted = resolve_reverted_status(d90.loc[nan_mask])
        outcome.loc[nan_mask] = np.where(reverted.reindex(d90.index[nan_mask]).to_numpy(), "cure", "unresolved")

    if outcome.isna().any():
        bad = zb[outcome.isna()].unique().tolist()
        raise AssertionError(f"unclassified zero_balance_code(s) left over: {bad}")
    return outcome.astype("category")


# --------------------------------------------------------------------------
# Sample build
# --------------------------------------------------------------------------
def build_lgd_sample(loan_orig: pd.DataFrame, panel_monthly: pd.DataFrame,
                      macro_panel: pd.DataFrame | None = None) -> pd.DataFrame:
    """loan_orig (had_d90_event subset) x panel_monthly's first-D90-event row
    -> one row per D90 loan with the outcome partition, updated_ltv (state-
    HPI, via freddie.macro.merge_macro), and every covariate stage 1 / 2 need.

    `loan_orig` may be pre-filtered to a subset of vintages (tests do this to
    keep resolve_reverted_status's raw re-read cheap); panel_monthly may be
    the full panel or pre-filtered to d90_event == 1 rows (cheap either way --
    the d90-only subset is 44,593 rows regardless of panel size).
    """
    missing = [c for c in LOAN_ORIG_REQUIRED_COLS if c not in loan_orig.columns]
    if missing:
        raise KeyError(f"loan_orig is missing required columns: {missing}")
    missing = [c for c in PANEL_MONTHLY_REQUIRED_COLS if c not in panel_monthly.columns]
    if missing:
        raise KeyError(f"panel_monthly is missing required columns: {missing}")

    d90 = loan_orig[loan_orig["had_d90_event"]].copy()
    if d90.empty:
        raise ValueError("no had_d90_event rows in loan_orig")

    d90_rows = panel_monthly.loc[
        (panel_monthly["d90_event"] == 1)
        & panel_monthly["loan_sequence_number"].isin(set(d90["loan_sequence_number"])),
        PANEL_MONTHLY_REQUIRED_COLS,
    ].rename(columns={
        "current_actual_upb": "upb_at_default",
        "loan_age": "loan_age_at_default",
        "monthly_reporting_period": "default_month",
    })
    d90 = d90.merge(d90_rows, on="loan_sequence_number", how="left", validate="one_to_one")
    missing_upb = d90["upb_at_default"].isna().sum()
    if missing_upb:
        raise AssertionError(
            f"{missing_upb} had_d90_event loans have no first-D90-event row in "
            "panel_monthly -- the two Phase-A tables should agree exactly")

    d90["lgd_outcome"] = partition_outcomes(d90)
    d90["era"] = d90["vintage"].map(ERA_OF_VINTAGE)
    d90["fico_s"] = d90["credit_score"] / 100.0
    d90["is_judicial"] = d90["property_state"].isin(JUDICIAL_STATES)
    d90["liq_year"] = d90["zero_balance_effective_date"].dt.year
    d90["liq_year_bucket"] = liq_year_bucket(d90["liq_year"])
    d90["disposition_type"] = d90["zero_balance_code"].map(ingest.ZERO_BALANCE_CODE_LABELS)
    d90["split"] = np.where(d90["default_month"] >= SPLIT_CUTOFF, "oot", "train")

    # updated_ltv at default, via state HPI (freddie.macro.merge_macro)
    ltv_frame = d90[["property_state", "orig_ltv", "orig_upb", "first_payment_date"]].copy()
    ltv_frame["current_upb"] = d90["upb_at_default"]
    ltv_frame["monthly_reporting_period"] = _yyyymm(d90["default_month"])
    ltv_frame["first_payment_date"] = _yyyymm(d90["first_payment_date"])
    merged = merge_macro(ltv_frame, macro=macro_panel,
                          state_col="property_state", month_col="monthly_reporting_period")
    d90["updated_ltv"] = merged["updated_ltv"].to_numpy()
    d90["ltv10"] = d90["updated_ltv"] / 10.0

    # realized loss + severity (liquidation rows only; NaN elsewhere)
    d90["realized_loss"] = -d90["actual_loss_calculation"]
    d90["severity"] = d90["realized_loss"] / d90["upb_at_default"]
    d90["has_loss_data"] = d90["actual_loss_calculation"].notna()

    return d90


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
@dataclass
class LgdModels:
    cure_result: object
    severity_result: object
    cure_formula: str
    severity_formula: str
    sev_cap: float
    excess_loading: float          # E[max(severity-1, 0) | liquidation, has_loss_data]
    floor_mass: float               # share of liquidation severities < 0 (floored to 0)
    n_resolved: int = 0
    n_cure: int = 0
    n_liquidation: int = 0
    n_severity_fit: int = 0
    fit_meta: dict = field(default_factory=dict)

    @property
    def lgd_upper_bound(self) -> float:
        return self.sev_cap + self.excess_loading


def fit_cure_model(sample: pd.DataFrame, split: str = "train") -> object:
    """Stage 1: cure logit on RESOLVED rows (cure or liquidation; unresolved
    excluded -- module docstring, DCR's resolved-only convention)."""
    d = sample[sample["lgd_outcome"] != "unresolved"].copy()
    if split is not None and "split" in d.columns:
        d = d[d["split"] == split]
    d["cure"] = (d["lgd_outcome"] == "cure").astype(int)
    d = d.dropna(subset=["ltv10", "fico_s", "loan_age_at_default", "era", "property_state", "cure"])
    if d.empty:
        raise ValueError("no resolved rows to fit the cure stage on")
    res = smf.glm(CURE_FORMULA, data=d, family=sm.families.Binomial()).fit()
    if not res.converged:
        raise RuntimeError("cure logit GLM did not converge")
    return res


def fit_severity_model(sample: pd.DataFrame, split: str = "train") -> tuple[object, dict]:
    """Stage 2: fractional-logit severity on LIQUIDATION rows with a
    populated actual_loss_calculation (module docstring: "loss not yet
    finalized" rows are excluded here only, not from the cure stage)."""
    d = sample[(sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"]].copy()
    if split is not None and "split" in d.columns:
        d = d[d["split"] == split]
    d = d.dropna(subset=["ltv10", "liq_year_bucket", "is_judicial", "disposition_type", "severity"])
    if d.empty:
        raise ValueError("no liquidation rows with usable severity to fit the severity stage on")
    floor_mass = float((d["severity"] < 0).mean())
    d["sev_capped"] = d["severity"].clip(lower=0.0, upper=SEV_CAP)
    res = smf.glm(SEVERITY_FORMULA, data=d, family=sm.families.Binomial()).fit(scale="X2", cov_type="HC1")
    if not res.converged:
        raise RuntimeError("severity fractional-logit GLM did not converge")
    excess_loading = float((d["severity"] - SEV_CAP).clip(lower=0.0).mean())
    meta = {
        "n_severity_fit": len(d),
        "floor_mass": floor_mass,
        "excess_loading": excess_loading,
        "share_gt_cap": float((d["severity"] > SEV_CAP).mean()),
    }
    return res, meta


def fit_lgd_models(sample: pd.DataFrame, split: str = "train") -> LgdModels:
    cure_res = fit_cure_model(sample, split=split)
    sev_res, sev_meta = fit_severity_model(sample, split=split)
    # n_resolved/n_cure/n_liquidation are read back off cure_res's OWN fitted
    # frame (its .dropna(subset=[...]) inside fit_cure_model can drop a
    # handful of resolved rows with a missing covariate, e.g. NaN
    # credit_score -> NaN fico_s) rather than independently re-filtering
    # `sample`, so these counts always match what the GLM actually saw --
    # a prior version double-counted those dropped rows (26,909 vs the
    # cure model's actual 26,896 on the full production sample), producing
    # an internally inconsistent n_resolved between this dataclass and
    # freddie/fit_lgd.py's population_lgd_summary (which already applied
    # the same dropna and reported 26,896).
    d_resolved = sample.loc[cure_res.model.data.frame.index]

    b_cure_ltv = float(cure_res.params["ltv10"])
    b_sev_ltv = float(sev_res.params["ltv10"])
    if not b_cure_ltv < 0:
        raise AssertionError(
            f"economic sign violated: cure must FALL in updated LTV (ltv10 coef = {b_cure_ltv:+.4f})")
    if not b_sev_ltv > 0:
        raise AssertionError(
            f"economic sign violated: severity must RISE in updated LTV (ltv10 coef = {b_sev_ltv:+.4f})")

    return LgdModels(
        cure_result=cure_res,
        severity_result=sev_res,
        cure_formula=CURE_FORMULA,
        severity_formula=SEVERITY_FORMULA,
        sev_cap=SEV_CAP,
        excess_loading=sev_meta["excess_loading"],
        floor_mass=sev_meta["floor_mass"],
        n_resolved=len(d_resolved),
        n_cure=int((d_resolved["lgd_outcome"] == "cure").sum()),
        n_liquidation=int((d_resolved["lgd_outcome"] == "liquidation").sum()),
        n_severity_fit=sev_meta["n_severity_fit"],
        fit_meta=sev_meta,
    )


def predict_components(models: LgdModels, df: pd.DataFrame) -> pd.DataFrame:
    """Per-row expected-LGD decomposition, same contract as engine/lgd.py's
    predict_components: p_cure, severity_capped, excess_loading,
    severity_adj, lgd = (1 - p_cure) * severity_adj.

    `df` must carry LIQUIDATION-outcome rows only (disposition_type one of
    the four liquidation labels the severity stage was actually fit on --
    third_party_sale / short_sale_or_charge_off / reo_disposition /
    whole_loan_sale). A cure-outcome row's disposition_type is a CURE label
    (prepaid_or_matured / rpl_securitization, from the SAME
    ZERO_BALANCE_CODE_LABELS map build_lgd_sample uses for every D90 loan)
    -- not NaN, so the `required`-columns NaN check below does not catch it,
    but it is a category the severity GLM never saw during fitting, so
    statsmodels raises a PatsyError on an unseen categorical level. This is
    intentional, not a bug to work around: the severity stage's covariates
    (liq_year_bucket, disposition_type) are only meaningful/observable for a
    loan that actually liquidated (module docstring), so there is no
    well-defined severity prediction for a cured loan's row in the first
    place. Callers (e.g. freddie/fit_lgd.py's population_lgd_summary)
    filter to `lgd_outcome == "liquidation"` before calling this."""
    required = ["ltv10", "fico_s", "loan_age_at_default", "era", "property_state",
                "liq_year_bucket", "is_judicial", "disposition_type"]
    bad = df[required].isna().any(axis=1)
    if bad.any():
        raise ValueError(f"{int(bad.sum())} scoring rows carry NaN in required covariates {required}")
    p_cure = np.asarray(models.cure_result.predict(df))
    sev_capped = np.asarray(models.severity_result.predict(df))
    sev_adj = sev_capped + models.excess_loading
    lgd = (1.0 - p_cure) * sev_adj
    out = pd.DataFrame({
        "p_cure": p_cure, "severity_capped": sev_capped,
        "excess_loading": models.excess_loading, "severity_adj": sev_adj, "lgd": lgd,
    }, index=df.index)
    ub = models.lgd_upper_bound + 1e-9
    if not (np.isfinite(lgd).all() and (lgd >= -1e-9).all() and (lgd <= ub).all()):
        raise AssertionError("predicted LGD escaped [0, sev_cap + loading]")
    return out


def predict_lgd(models: LgdModels, df: pd.DataFrame) -> np.ndarray:
    return predict_components(models, df)["lgd"].to_numpy()
