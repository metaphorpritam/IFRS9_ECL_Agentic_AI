"""Freddie Mac Single-Family Loan-Level Dataset (SFLLD) sample ingestion.

Rung-3 scope (see freddie/__init__.py and MASTER_PLAN.md): this module reads the
official Freddie Mac SFLLD *sample* dataset (17 vintage zips in data/SFLLD/) and
returns typed, sentinel-cleaned pandas DataFrames. It writes and imports nothing
from engine/ or data/processed/panel.parquet -- rung 3 is a fresh dataset build,
isolated on purpose.

Input :  data/SFLLD/sample_{YYYY}.zip for YYYY in
         {2005..2010, 2014..2016, 2018..2025} (17 vintages; 2011-2013 and 2017
         were never downloaded -- see MISSING_VINTAGES; documented as a coverage
         note, not an error).  Each zip holds exactly two pipe-delimited,
         header-less text files:
             sample_orig_{YYYY}.txt   -- one row per loan, 32 fields
             sample_svcg_{YYYY}.txt   -- one row per loan-month, 32 fields
Output:  nothing on disk from this module -- it is a pure reader/validator.
         freddie/build_panel.py calls into it to build the combined panel.

Layout source of truth: this module's field order, names, valid-value sets and
sentinel codes were copied from Freddie Mac's own "Single-Family Loan-Level
Dataset General User Guide" (fetched live from freddiemac.com and cross-checked
empirically against every vintage below -- see the sentinel-frequency and
delinquency-ladder checks in tests/test_freddie_ingest.py). Do not hand-edit the
column lists without re-checking both sources.

Row counts: every full-year vintage samples exactly 50,000 origination loans;
2025 is a partial year (through the Q3 origination cutoff visible in this
download) and samples a proportionately smaller 37,500 loans -- this is
Freddie Mac's own "sample" methodology (docstring in the User Guide), not a
data-quality defect, so validate_orig() only enforces the 50k floor for
non-2025 vintages.

--------------------------------------------------------------------------------
SENTINEL / MISSING-VALUE CODES (mapped to NaN by map_orig_sentinels /
map_svcg_sentinels; every one of these is empirically confirmed present in at
least one vintage in tests/test_freddie_ingest.py::test_sentinel_frequencies)
--------------------------------------------------------------------------------
Origination file:
  credit_score          9999  = Not Available
  mi_pct                 999  = Not Available   (0 is a real value: "no MI")
  num_units                99  = Not Available
  cltv                    999  = Not Available
  dti                     999  = Not Available
  orig_ltv                999  = Not Available
  num_borrowers            99  = Not Available
  first_time_homebuyer_flag "9" = Not Available / Not Applicable
  occupancy_status         "9" = Not Available
  channel                  "9" = Not Available
  loan_purpose             "9" = Not Available
  property_type           "99" = Not Available
  special_eligibility_program "9" = Not Available/Not Applicable (the default
                                for every pre-March-2015 loan -- see the User
                                Guide note; do not read this as "missing data",
                                it means the field simply doesn't apply yet)
  property_valuation_method "7" = Not Available (blank/7 for nearly all pre-2018
                                vintages -- the field was only populated for
                                loans originated on/after 2017-01-01)
  mi_cancellation_indicator "9" = Not Disclosed (NaN'd). NOTE: "7" = Not
                                Applicable (loan never had MI to cancel) is a
                                REAL, meaningful value and is deliberately left
                                alone, not NaN'd.
  msa, postal_code             blank = unknown/not an MSA (native NaN on read)
Postal code is ALSO subject to Freddie's own privacy masking (last two digits
zeroed for every row, always) -- that is not missing data, just masking; it is
left as-is and documented, not NaN'd.

Monthly performance file:
  eltv (estimated current LTV)   999 = Unknown
  net_sale_proceeds               "U" = Unknown
  current_delinquency_status     "RA" = REO Acquisition (not a numeric DPD
                                bucket -- kept in the raw string column
                                verbatim; dlq_num is NaN for RA rows, and
                                is_reo_acquisition flags them separately;
                                see current_delinquency_status below).
  All dollar-amount columns (mi_recoveries, net_sale_proceeds, ..., zero_balance
  _removal_upb, delinquent_accrued_interest) are blank/NaN on every row except
  the single terminal disposition row for a loan -- this is documented Freddie
  Mac behaviour (Actual Loss section of the User Guide), not a data defect.

Delinquency ladder (current_delinquency_status): empirically the SFLLD sample
contains every non-negative integer string ("0".."68"+ seen) plus the literal
"RA"; DELINQUENCY_STATUS_ALLOWED_NONNUMERIC pins the only non-numeric value
tolerated by validate_svcg().

Zero balance codes (Zero Balance Code, priority order in the User Guide):
    01 Prepaid or Matured (Voluntary Payoff)     -- prepay_event
    02 Third Party Sale
    03 Short Sale or Charge Off
    09 REO Disposition
    15 Whole Loan Sale
    16 Reperforming Loan (RPL) Securitization
    96 Defect prior to Property Disposition
(blank = loan still active / not yet terminated as of the performance cutoff).

NOTE on code "06" (Repurchase): older/legacy SFLLD documentation floating
around the web lists a separate "06 Repurchase prior to Property Disposition"
code. The CURRENT Freddie Mac SFLLD General User Guide (re-fetched live for
this review, "Zero Balance Codes" section) does NOT list 06 at all -- its
7-row termination-event/priority table has only the 7 codes above, with what
used to be repurchase activity folded into 96 ("Defect prior to Property
Disposition"). Empirically confirmed absent too: every one of the 17 ingested
vintages' raw zero_balance_code columns was enumerated for this review and
"06" never appears (only 01/02/03/09/15/16/96 occur, exactly ZERO_BALANCE_CODES
below). So there is nothing to "put" 06 anywhere in this build -- it is not a
live code in this dataset. If a future refresh of the sample data ever
reintroduces it, validate_svcg() will catch it as an "unexpected zero balance
code" (bad_zb_codes) rather than silently mislabeling it, since
ZERO_BALANCE_CODE_LABELS only maps the 7 known codes and _terminal_outcome()
in build_panel.py leaves any unmapped code's terminal_outcome as "censored" --
that fallback would be WRONG for a real terminal disposition, so treat a
validate_svcg() bad_zb_codes hit as a hard signal to add the new code's label
before trusting terminal_outcome again. In any case 06/repurchase, like every
other zero-balance code, is NEVER treated as the modeling default (D90 is);
it would only ever land in the competing-risk/LGD columns on loan_orig.parquet.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "SFLLD"

# Vintages actually on disk vs. the full run Freddie Mac publishes for the
# sample dataset. 2011-2013 and 2017 were never downloaded for this project --
# a coverage gap, not an ingestion error. Keep both lists in sync by hand; the
# tests assert VINTAGE_YEARS matches what's really in data/SFLLD/.
VINTAGE_YEARS: list[int] = [
    2005, 2006, 2007, 2008, 2009, 2010,
    2014, 2015, 2016,
    2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025,
]
MISSING_VINTAGES: list[int] = [2011, 2012, 2013, 2017]

# Partial-year vintage(s): sampled proportionately, so the "50,000 loans" floor
# does not apply. Extend this set if a future refresh adds another partial year.
PARTIAL_YEAR_VINTAGES: set[int] = {2025}

FULL_YEAR_LOAN_COUNT = 50_000

# --------------------------------------------------------------------------------
# Column layout -- 32 fields each, order = Freddie Mac's official column position.
# --------------------------------------------------------------------------------
ORIG_COLUMNS: list[str] = [
    "credit_score",                              # 1
    "first_payment_date",                         # 2  YYYYMM
    "first_time_homebuyer_flag",                  # 3
    "maturity_date",                              # 4  YYYYMM
    "msa",                                        # 5
    "mi_pct",                                     # 6
    "num_units",                                  # 7
    "occupancy_status",                           # 8
    "cltv",                                       # 9
    "dti",                                        # 10
    "orig_upb",                                   # 11
    "orig_ltv",                                   # 12
    "orig_interest_rate",                         # 13
    "channel",                                    # 14
    "ppm_flag",                                   # 15
    "amortization_type",                          # 16
    "property_state",                             # 17
    "property_type",                              # 18
    "postal_code",                                # 19
    "loan_sequence_number",                       # 20
    "loan_purpose",                                # 21
    "orig_loan_term",                             # 22
    "num_borrowers",                              # 23
    "seller_name",                                # 24
    "servicer_name",                              # 25
    "super_conforming_flag",                      # 26
    "pre_relief_refinance_loan_sequence_number",  # 27
    "special_eligibility_program",                # 28
    "relief_refinance_indicator",                 # 29
    "property_valuation_method",                  # 30
    "io_indicator",                                # 31
    "mi_cancellation_indicator",                  # 32
]
assert len(ORIG_COLUMNS) == 32

SVCG_COLUMNS: list[str] = [
    "loan_sequence_number",                # 1
    "monthly_reporting_period",            # 2  YYYYMM
    "current_actual_upb",                  # 3
    "current_delinquency_status",          # 4  "0".."N" or "RA"
    "loan_age",                            # 5
    "remaining_months_legal_maturity",     # 6
    "defect_settlement_date",              # 7  YYYYMM
    "modification_flag",                   # 8
    "zero_balance_code",                   # 9
    "zero_balance_effective_date",         # 10 YYYYMM
    "current_interest_rate",               # 11
    "current_non_interest_bearing_upb",    # 12
    "ddlpi",                               # 13 YYYYMM
    "mi_recoveries",                       # 14
    "net_sale_proceeds",                   # 15 "$ amount" or "U"
    "non_mi_recoveries",                   # 16
    "total_expenses",                      # 17
    "legal_costs",                         # 18
    "maintenance_preservation_costs",      # 19
    "taxes_insurance",                     # 20
    "miscellaneous_expenses",              # 21
    "actual_loss_calculation",             # 22
    "cumulative_modification_cost",        # 23
    "interest_rate_step_indicator",        # 24
    "payment_deferral_flag",               # 25
    "eltv",                                # 26
    "zero_balance_removal_upb",            # 27
    "delinquent_accrued_interest",         # 28
    "delinquency_due_to_disaster",         # 29
    "borrower_assistance_status_code",     # 30
    "current_month_modification_cost",     # 31
    "interest_bearing_upb",                # 32
]
assert len(SVCG_COLUMNS) == 32

# Read everything as string first (blank field -> NaN is pandas's own default
# and is exactly what we want -- Freddie Mac leaves fields genuinely blank, not
# zero-filled). Numeric/date conversion + sentinel mapping happens afterwards
# so we can document each conversion instead of guessing dtypes at parse time.
_STR_DTYPE = "string"

ORIG_CATEGORY_COLUMNS = [
    "first_time_homebuyer_flag", "occupancy_status", "channel", "ppm_flag",
    "amortization_type", "property_state", "property_type", "loan_purpose",
    "seller_name", "servicer_name", "special_eligibility_program",
    "property_valuation_method", "io_indicator", "mi_cancellation_indicator",
]
SVCG_CATEGORY_COLUMNS = [
    "modification_flag", "zero_balance_code", "interest_rate_step_indicator",
    "payment_deferral_flag", "delinquency_due_to_disaster",
    "borrower_assistance_status_code",
]

_ORIG_DATE_COLUMNS = ["first_payment_date", "maturity_date"]
_SVCG_DATE_COLUMNS = ["defect_settlement_date", "zero_balance_effective_date", "ddlpi"]

_ORIG_INT_COLUMNS = {
    "credit_score": "Int16", "mi_pct": "Int16", "num_units": "Int8",
    "cltv": "Int16", "dti": "Int16", "orig_ltv": "Int16",
    "orig_loan_term": "Int16", "num_borrowers": "Int8",
    "msa": "Int32", "postal_code": "Int32",
}
_ORIG_FLOAT_COLUMNS = {"orig_upb": "float32", "orig_interest_rate": "float32"}

_SVCG_FLOAT_COLUMNS = {
    "current_actual_upb": "float32", "current_interest_rate": "float32",
    "current_non_interest_bearing_upb": "float32", "mi_recoveries": "float32",
    "non_mi_recoveries": "float32", "total_expenses": "float32",
    "legal_costs": "float32", "maintenance_preservation_costs": "float32",
    "taxes_insurance": "float32", "miscellaneous_expenses": "float32",
    "actual_loss_calculation": "float32", "cumulative_modification_cost": "float32",
    "eltv": "float32", "zero_balance_removal_upb": "float32",
    "delinquent_accrued_interest": "float32", "current_month_modification_cost": "float32",
    "interest_bearing_upb": "float32",
}
_SVCG_INT_COLUMNS = {"loan_age": "Int16", "remaining_months_legal_maturity": "Int16"}

# Documented "Not Available"/"Not Applicable" sentinel codes -> NaN.
# {column: set of raw string values to null out}
ORIG_SENTINELS: dict[str, set[str]] = {
    "credit_score": {"9999"},
    "mi_pct": {"999"},
    "num_units": {"99"},
    "cltv": {"999"},
    "dti": {"999"},
    "orig_ltv": {"999"},
    "num_borrowers": {"99"},
    "first_time_homebuyer_flag": {"9"},
    "occupancy_status": {"9"},
    "channel": {"9"},
    "loan_purpose": {"9"},
    "property_type": {"99"},
    "special_eligibility_program": {"9"},
    "property_valuation_method": {"7"},
    "mi_cancellation_indicator": {"9"},  # "7" (Not Applicable) is kept, not NaN'd
}
SVCG_SENTINELS: dict[str, set[str]] = {
    "eltv": {"999"},
    "net_sale_proceeds": {"U"},
}

DELINQUENCY_STATUS_ALLOWED_NONNUMERIC = {"RA"}
ZERO_BALANCE_CODES = {"01", "02", "03", "09", "15", "16", "96"}
ZERO_BALANCE_CODE_LABELS = {
    "01": "prepaid_or_matured", "02": "third_party_sale", "03": "short_sale_or_charge_off",
    "09": "reo_disposition", "15": "whole_loan_sale", "16": "rpl_securitization",
    "96": "defect_prior_to_disposition",
}


def _zip_path(year: int) -> Path:
    return DATA_DIR / f"sample_{year}.zip"


def _read_pipe_chunks(year: int, member_prefix: str, columns: list[str],
                       chunksize: int = 500_000) -> pd.DataFrame:
    """Stream one member out of the zip (never extracted to disk) and parse it
    chunk-by-chunk with the C engine, dtype=str throughout (see _STR_DTYPE)."""
    zpath = _zip_path(year)
    member = f"{member_prefix}_{year}.txt"
    with zipfile.ZipFile(zpath) as z:
        with z.open(member) as fh:
            chunks = pd.read_csv(
                fh, sep="|", header=None, names=columns, dtype=_STR_DTYPE,
                chunksize=chunksize, engine="c",
            )
            return pd.concat(list(chunks), ignore_index=True)


def read_orig_vintage(year: int) -> pd.DataFrame:
    """Read + type + sentinel-clean one vintage's origination file."""
    df = _read_pipe_chunks(year, "sample_orig", ORIG_COLUMNS)
    df = map_orig_sentinels(df)
    sentinel_counts = df.attrs["sentinel_counts"]

    for col in _ORIG_DATE_COLUMNS:
        df[col] = pd.to_datetime(df[col], format="%Y%m", errors="coerce")
    for col, dt in _ORIG_INT_COLUMNS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(dt)
    for col, dt in _ORIG_FLOAT_COLUMNS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(dt)
    for col in ORIG_CATEGORY_COLUMNS:
        df[col] = df[col].astype("category")

    df["is_super_conforming"] = df["super_conforming_flag"].fillna("") == "Y"
    df["is_relief_refinance"] = df["relief_refinance_indicator"].fillna("") == "Y"
    df["vintage"] = np.int16(year)
    df.attrs["sentinel_counts"] = sentinel_counts
    return df


def read_svcg_vintage(year: int) -> pd.DataFrame:
    """Read + type + sentinel-clean one vintage's monthly performance file."""
    df = _read_pipe_chunks(year, "sample_svcg", SVCG_COLUMNS)
    df = map_svcg_sentinels(df)
    sentinel_counts = df.attrs["sentinel_counts"]

    for col in _SVCG_DATE_COLUMNS + ["monthly_reporting_period"]:
        df[col] = pd.to_datetime(df[col], format="%Y%m", errors="coerce")
    for col, dt in _SVCG_FLOAT_COLUMNS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(dt)
    for col, dt in _SVCG_INT_COLUMNS.items():
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(dt)
    for col in SVCG_CATEGORY_COLUMNS:
        df[col] = df[col].astype("category")

    # current_delinquency_status: keep the raw string (it is the audit trail),
    # derive a numeric DPD-bucket column with "RA" -> NaN, plus its own flag.
    raw = df["current_delinquency_status"].astype("string")
    df["is_reo_acquisition"] = raw == "RA"
    df["dlq_num"] = pd.to_numeric(raw.where(~df["is_reo_acquisition"]), errors="coerce").astype("Int16")
    df["vintage"] = np.int16(year)
    df.attrs["sentinel_counts"] = sentinel_counts
    return df


def map_orig_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    counts: dict[str, int] = {}
    for col, codes in ORIG_SENTINELS.items():
        mask = df[col].isin(codes)
        counts[col] = int(mask.sum())
        df.loc[mask, col] = pd.NA
    df.attrs["sentinel_counts"] = counts
    return df


def map_svcg_sentinels(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    counts: dict[str, int] = {}
    for col, codes in SVCG_SENTINELS.items():
        mask = df[col].isin(codes)
        counts[col] = int(mask.sum())
        df.loc[mask, col] = pd.NA
    df.attrs["sentinel_counts"] = counts
    return df


# first_payment_date is allowed to drift outside vintage+/-1 for a documented,
# low-frequency reason (User Guide footnote 3): seller-owned modified
# mortgages, converted mortgages and construction-to-permanent mortgages are
# reported with the ORIGINAL note date (which sets the vintage/quarter) but
# the MODIFIED/CONVERTED first payment date, which can be years later. This is
# real, expected SFLLD behaviour, not a parsing bug -- empirically confirmed
# at 0.01%-0.1% of loans per vintage (tests/test_freddie_ingest.py). Only flag
# ok=False if the off-vintage fraction blows past this budget, which would
# instead point at a genuine date-parsing defect.
FIRST_PAYMENT_DRIFT_FRACTION_BUDGET = 0.01


@dataclass
class OrigValidation:
    year: int
    n_loans: int
    n_expected_floor: int
    first_payment_years: set[int] = field(default_factory=set)
    n_first_payment_off_vintage: int = 0
    ok: bool = True
    messages: list[str] = field(default_factory=list)


def validate_orig(df: pd.DataFrame, year: int) -> OrigValidation:
    """Per-vintage origination checks: row count floor, first_payment_date
    within vintage year +/- 1 (budgeted -- see FIRST_PAYMENT_DRIFT_FRACTION_BUDGET),
    no duplicate loan_sequence_number."""
    v = OrigValidation(year=year, n_loans=len(df), n_expected_floor=(
        0 if year in PARTIAL_YEAR_VINTAGES else FULL_YEAR_LOAN_COUNT
    ))
    if year not in PARTIAL_YEAR_VINTAGES and len(df) != FULL_YEAR_LOAN_COUNT:
        v.ok = False
        v.messages.append(f"{year}: expected {FULL_YEAR_LOAN_COUNT} orig loans, got {len(df)}")

    fp_years = df["first_payment_date"].dt.year.dropna()
    v.first_payment_years = set(int(y) for y in fp_years.unique())
    off_vintage = (fp_years - year).abs() > 1
    v.n_first_payment_off_vintage = int(off_vintage.sum())
    off_fraction = v.n_first_payment_off_vintage / max(len(df), 1)
    if off_fraction > FIRST_PAYMENT_DRIFT_FRACTION_BUDGET:
        v.ok = False
        v.messages.append(
            f"{year}: {v.n_first_payment_off_vintage} loans ({off_fraction:.2%}) have "
            f"first_payment_date outside vintage+/-1, above the {FIRST_PAYMENT_DRIFT_FRACTION_BUDGET:.0%} "
            "budget for construction-to-perm/seller-modified loans -- investigate as a possible date-parsing defect"
        )
    elif v.n_first_payment_off_vintage:
        v.messages.append(
            f"{year}: {v.n_first_payment_off_vintage} loans have first_payment_date outside "
            "vintage+/-1 (informational -- expected construction-to-perm/seller-modified "
            "mortgages per User Guide footnote 3, within budget)"
        )

    dupes = df["loan_sequence_number"].duplicated().sum()
    if dupes:
        v.ok = False
        v.messages.append(f"{year}: {dupes} duplicate loan_sequence_number in orig file")

    return v


@dataclass
class SvcgValidation:
    year: int
    n_rows: int
    n_orphan_loans: int = 0
    n_orig_without_svcg: int = 0
    bad_dlq_values: set[str] = field(default_factory=set)
    bad_zb_codes: set[str] = field(default_factory=set)
    ok: bool = True
    messages: list[str] = field(default_factory=list)


def validate_svcg(svcg: pd.DataFrame, orig: pd.DataFrame, year: int) -> SvcgValidation:
    """Per-vintage performance checks: 1:many join with zero orphans in either
    direction, delinquency ladder values in the documented set, zero balance
    codes in the documented set."""
    v = SvcgValidation(year=year, n_rows=len(svcg))

    orig_ids = set(orig["loan_sequence_number"])
    svcg_ids = set(svcg["loan_sequence_number"])
    orphans = svcg_ids - orig_ids
    missing = orig_ids - svcg_ids
    v.n_orphan_loans = len(orphans)
    v.n_orig_without_svcg = len(missing)
    if orphans:
        v.ok = False
        v.messages.append(f"{year}: {len(orphans)} svcg loan_sequence_numbers with no orig match")
    if missing:
        v.ok = False
        v.messages.append(f"{year}: {len(missing)} orig loans with no svcg rows at all")

    raw_dlq = svcg["current_delinquency_status"].dropna().astype(str)
    bad_dlq = set(raw_dlq[~(raw_dlq.str.isdigit() | raw_dlq.isin(DELINQUENCY_STATUS_ALLOWED_NONNUMERIC))])
    v.bad_dlq_values = bad_dlq
    if bad_dlq:
        v.ok = False
        v.messages.append(f"{year}: unexpected delinquency status values: {sorted(bad_dlq)[:10]}")

    raw_zb = svcg["zero_balance_code"].dropna().astype(str)
    bad_zb = set(raw_zb[~raw_zb.isin(ZERO_BALANCE_CODES)])
    v.bad_zb_codes = bad_zb
    if bad_zb:
        v.ok = False
        v.messages.append(f"{year}: unexpected zero balance codes: {sorted(bad_zb)}")

    return v


def available_vintages() -> list[int]:
    """Vintages actually present under data/SFLLD/ (sanity check against
    VINTAGE_YEARS -- keeps the hardcoded list honest if the data dir changes)."""
    return sorted(
        int(p.stem.replace("sample_", ""))
        for p in DATA_DIR.glob("sample_*.zip")
    )
