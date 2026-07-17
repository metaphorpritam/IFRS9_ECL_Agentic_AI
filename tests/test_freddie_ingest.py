"""Tests for freddie/ingest.py + freddie/build_panel.py -- SFLLD ingestion and
the combined monthly loan panel (rung 3, isolated from the frozen DCR engine).

Runtime note: most tests read the smallest vintage on disk (2025, a partial
year: 37,500 loans / ~153k loan-months) to keep the suite fast while still
exercising the real zip-stream reader end to end. Two tests deliberately read
the 2007 vintage (50k loans / ~3.0M loan-months) because the hand-checked
loans used to pin the absorbing-D90 property live in that vintage.
"""
from __future__ import annotations

import pandas as pd
import pytest

from freddie import build_panel, ingest

SMALL_YEAR = 2025          # smallest vintage on disk -- used for fast checks
TRACE_YEAR = 2007          # vintage holding the two hand-checked loans below

# Hand-checked loans (traced by direct zipfile inspection -- see the
# orchestrator transcript / freddie/build_panel.py docstring):
#   F07Q10000023: 25 clean months, current_delinquency_status==0 throughout,
#                 terminal row 2009-01 zero_balance_code=='01' (prepaid),
#                 zero_balance_removal_upb == 190582.28.
#   F07Q10000581: reaches current_delinquency_status>=3, later CURES back
#                 below 3 in the raw servicing data, and is not terminated
#                 by a zero-balance code within the performance window --
#                 the absorbing-D90 modeling panel must stop at the first
#                 severe month regardless of the later cure.
TRACE_PREPAY_LOAN = "F07Q10000023"
TRACE_CURE_LOAN = "F07Q10000581"


@pytest.fixture(scope="module")
def small_orig() -> pd.DataFrame:
    return ingest.read_orig_vintage(SMALL_YEAR)


@pytest.fixture(scope="module")
def small_svcg() -> pd.DataFrame:
    return ingest.read_svcg_vintage(SMALL_YEAR)


@pytest.fixture(scope="module")
def trace_vintage():
    monthly, loan_level, orig_dq, svcg_dq, _ = build_panel.build_vintage(TRACE_YEAR)
    return monthly, loan_level, orig_dq, svcg_dq


# ---------------------------------------------------------------------------
# Field-count assertions (32 fields each, matching Freddie Mac's own layout)
# ---------------------------------------------------------------------------

def test_field_counts_match_official_layout():
    assert len(ingest.ORIG_COLUMNS) == 32
    assert len(ingest.SVCG_COLUMNS) == 32


def test_raw_rows_have_32_fields_every_vintage():
    for year in ingest.VINTAGE_YEARS:
        with __import__("zipfile").ZipFile(ingest._zip_path(year)) as z:
            with z.open(f"sample_orig_{year}.txt") as f:
                n = len(f.readline().decode().rstrip("\n").split("|"))
            assert n == 32, f"{year} orig: expected 32 fields, got {n}"
            with z.open(f"sample_svcg_{year}.txt") as f:
                n = len(f.readline().decode().rstrip("\n").split("|"))
            assert n == 32, f"{year} svcg: expected 32 fields, got {n}"


def test_available_vintages_matches_hardcoded_list():
    assert ingest.available_vintages() == ingest.VINTAGE_YEARS


def test_coverage_gap_is_documented_not_silently_missing():
    all_years = set(ingest.VINTAGE_YEARS) | set(ingest.MISSING_VINTAGES)
    assert all_years == set(range(2005, 2026))
    assert set(ingest.VINTAGE_YEARS).isdisjoint(ingest.MISSING_VINTAGES)


# ---------------------------------------------------------------------------
# Sentinel mapping
# ---------------------------------------------------------------------------

def test_sentinel_frequencies_present_in_real_vintages():
    """Every documented sentinel actually fires at least once across the
    vintages where it's known to occur (empirically confirmed via direct
    zip inspection before writing this module)."""
    df05 = ingest.read_orig_vintage(2005)
    assert df05.attrs["sentinel_counts"]["credit_score"] > 0
    df10 = ingest.read_orig_vintage(2010)
    assert df10.attrs["sentinel_counts"]["dti"] > 0

    orig_small = ingest.read_orig_vintage(SMALL_YEAR)
    assert orig_small.attrs["sentinel_counts"]["credit_score"] > 0
    # special_eligibility_program's "9" (Not Available/Not Applicable) is the
    # majority value in every vintage -- most loans simply don't participate
    # in Home Possible/HFA Advantage/Refi Possible -- so it fires everywhere.
    assert orig_small.attrs["sentinel_counts"]["special_eligibility_program"] > 0

    svcg_small = ingest.read_svcg_vintage(SMALL_YEAR)
    assert svcg_small.attrs["sentinel_counts"]["eltv"] > 0


def test_sentinel_values_become_nan(small_orig, small_svcg):
    raw_had_9999 = ingest.read_orig_vintage(SMALL_YEAR).attrs["sentinel_counts"]["credit_score"]
    assert raw_had_9999 > 0
    assert not (small_orig["credit_score"] == 9999).any()

    assert not (small_svcg["eltv"] == 999).any()


def test_mi_cancellation_not_applicable_is_kept_not_nulled(small_orig):
    """'7' (Not Applicable -- loan never had MI) is a real value and must
    survive sentinel mapping; only '9' (Not Disclosed) is NaN'd. '7' is only
    populated from the 2015 vintage onward (User Guide field note) -- earlier
    vintages (e.g. 2007) are all '9' and would be a bad pick for this check."""
    assert (small_orig["mi_cancellation_indicator"] == "7").any()


# ---------------------------------------------------------------------------
# Per-vintage validation (join orphans, delinquency ladder, row counts)
# ---------------------------------------------------------------------------

def test_join_has_zero_orphans(small_orig, small_svcg):
    v = ingest.validate_svcg(small_svcg, small_orig, SMALL_YEAR)
    assert v.n_orphan_loans == 0
    assert v.n_orig_without_svcg == 0
    assert v.ok


def test_delinquency_ladder_values_in_documented_set(small_svcg):
    v = ingest.validate_svcg(small_svcg, ingest.read_orig_vintage(SMALL_YEAR), SMALL_YEAR)
    assert not v.bad_dlq_values
    assert not v.bad_zb_codes


def test_full_year_vintage_has_50k_loans():
    v = ingest.validate_orig(ingest.read_orig_vintage(TRACE_YEAR), TRACE_YEAR)
    assert v.n_loans == 50_000
    assert v.ok


def test_partial_year_2025_is_not_held_to_50k_floor(small_orig):
    v = ingest.validate_orig(small_orig, SMALL_YEAR)
    assert v.n_loans < 50_000
    assert v.ok


# ---------------------------------------------------------------------------
# D90 absorbing property + hand-checked loan trace
# ---------------------------------------------------------------------------

def test_d90_absorbing_no_post_default_rows_in_modeling_panel(trace_vintage):
    """Vectorized invariant over all ~50k loans in the 2007 vintage: at most
    one d90_event per loan, and when it fires it is the loan's LAST row in
    the modeling panel (nothing kept after it)."""
    monthly, _, _, _ = trace_vintage
    grp = monthly.groupby("loan_sequence_number", observed=True, sort=False)

    events_per_loan = grp["d90_event"].sum()
    assert events_per_loan.max() <= 1

    event_rows = monthly[monthly["d90_event"] == 1]
    assert event_rows["is_terminal_row"].all(), "a d90_event row must be its loan's last panel row"

    max_period_per_loan = grp["monthly_reporting_period"].transform("max")
    assert (monthly.loc[monthly["d90_event"] == 1, "monthly_reporting_period"]
            == max_period_per_loan.loc[monthly["d90_event"] == 1]).all()


def test_absorbing_d90_censors_post_event_rows_cure_loan(trace_vintage):
    """F07Q10000581 (2007) cures back below D90 in the raw servicing data;
    the modeling panel must stop at the first severe month regardless."""
    monthly, _, _, _ = trace_vintage
    raw_svcg = ingest.read_svcg_vintage(TRACE_YEAR)
    raw_rows = raw_svcg[raw_svcg["loan_sequence_number"] == TRACE_CURE_LOAN]
    panel_rows = monthly[monthly["loan_sequence_number"] == TRACE_CURE_LOAN]

    assert len(panel_rows) < len(raw_rows), "panel should be truncated relative to raw history"
    assert panel_rows["d90_event"].sum() == 1
    assert panel_rows.iloc[-1]["d90_event"] == 1
    assert panel_rows.iloc[-1]["is_terminal_row"]

    # the raw data really does cure after the truncation point (proves this
    # is a real absorbing-censoring effect, not just "loan happened to end")
    last_kept_period = panel_rows["monthly_reporting_period"].max()
    post_event_raw = raw_rows[raw_rows["monthly_reporting_period"] > last_kept_period]
    assert (post_event_raw["dlq_num"].fillna(99) < 3).any()


def test_hand_checked_loan_prepay_trace(trace_vintage):
    """F07Q10000023 (2007): 25 clean months, prepays 2009-01, never delinquent."""
    monthly, loan_level, _, _ = trace_vintage
    panel_rows = monthly[monthly["loan_sequence_number"] == TRACE_PREPAY_LOAN]
    assert len(panel_rows) == 25
    assert (panel_rows["dlq_num"].fillna(0) == 0).all()
    assert panel_rows["d90_event"].sum() == 0
    assert panel_rows.iloc[-1]["prepay_event"] == 1
    assert panel_rows.iloc[-1]["monthly_reporting_period"] == pd.Timestamp("2009-01-01")

    loan_row = loan_level[loan_level["loan_sequence_number"] == TRACE_PREPAY_LOAN].iloc[0]
    assert loan_row["terminal_outcome"] == "prepaid_or_matured"
    assert not loan_row["had_d90_event"]
    assert loan_row["zero_balance_removal_upb"] == pytest.approx(190582.28, abs=0.01)
    assert loan_row["months_observed"] == 25


def test_hand_checked_loan_d90_trace(trace_vintage):
    """F07Q10000581 (2007): reaches D90 in 2016-11 and is labeled d90_default
    on the loan-level table even though it ALSO records a zero_balance_code
    (voluntary payoff, '01') years later in its full servicing history --
    the D90 label takes precedence per the documented default definition
    (freddie/build_panel.py docstring: D90 is the modeled event, the terminal
    zero-balance code is preserved alongside it, not instead of it)."""
    monthly, loan_level, _, _ = trace_vintage
    loan_row = loan_level[loan_level["loan_sequence_number"] == TRACE_CURE_LOAN].iloc[0]
    assert loan_row["terminal_outcome"] == "d90_default"
    assert loan_row["had_d90_event"]
    assert loan_row["zero_balance_code"] == "01"

    panel_rows = monthly[monthly["loan_sequence_number"] == TRACE_CURE_LOAN]
    assert panel_rows.iloc[-1]["monthly_reporting_period"] == pd.Timestamp("2016-11-01")


# ---------------------------------------------------------------------------
# Prepay / default mutual exclusivity (as modeled)
# ---------------------------------------------------------------------------

def test_prepay_and_default_mutually_exclusive_as_modeled(trace_vintage):
    monthly, _, _, _ = trace_vintage
    both = monthly[(monthly["d90_event"] == 1) & (monthly["prepay_event"] == 1)]
    assert both.empty

    any_zb_and_d90 = monthly[(monthly["d90_event"] == 1) & monthly["zero_balance_code"].notna()]
    assert any_zb_and_d90.empty, "a terminal zero_balance_code must suppress d90_event on that row"


def test_same_row_terminal_tiebreak_suppresses_d90(trace_vintage):
    """F07Q10009844 (2007) hits dlq_num==3 in the exact same reporting month
    its zero_balance_code is set to '01' -- the disposition code must win."""
    monthly, loan_level, _, _ = trace_vintage
    row = monthly[monthly["loan_sequence_number"] == "F07Q10009844"].iloc[-1]
    assert row["dlq_num"] >= 3
    assert row["zero_balance_code"] == "01"
    assert row["d90_event"] == 0
    assert row["prepay_event"] == 1

    loan_row = loan_level[loan_level["loan_sequence_number"] == "F07Q10009844"].iloc[0]
    assert loan_row["terminal_outcome"] == "prepaid_or_matured"
    assert not loan_row["had_d90_event"]


def test_terminal_outcome_categories_partition_all_loans(trace_vintage):
    _, loan_level, _, _ = trace_vintage
    assert loan_level["terminal_outcome"].notna().all()
    counts = loan_level["terminal_outcome"].value_counts()
    assert counts.sum() == len(loan_level)


# ---------------------------------------------------------------------------
# Data-quality validation wiring (soft vs hard failures)
# ---------------------------------------------------------------------------

def test_construction_to_perm_drift_is_informational_not_a_hard_failure(trace_vintage):
    _, _, orig_dq, _ = trace_vintage
    assert orig_dq.ok
    assert orig_dq.n_first_payment_off_vintage > 0
    assert any("informational" in m for m in orig_dq.messages)
