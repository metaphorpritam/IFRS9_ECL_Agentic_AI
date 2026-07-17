"""Tests for freddie/macro.py -- the state-level macro build (rung 3).

Network-free: freddie/macro.py's cache (data/processed/freddie/macro/*.csv,
states_in_data.json, state_macro_panel.parquet) is populated once by running
`python -m freddie.macro` (network + FRED_API_KEY). Every test below reads
ONLY that cache (or local SFLLD zips, which is disk I/O, not network).
"""
import zipfile

import numpy as np
import pandas as pd
import pytest

from freddie import macro

EXPECTED_STATES = {
    "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "GU",
    "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI",
    "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY",
    "OH", "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VA",
    "VI", "VT", "WA", "WI", "WV", "WY",
}


def _require_cache(path):
    if not path.exists():
        pytest.skip(f"cache not built yet -- run `python -m freddie.macro` first ({path})")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def state_macro_panel() -> pd.DataFrame:
    _require_cache(macro.STATE_PANEL_PATH)
    return macro.load_state_macro_panel()


@pytest.fixture(scope="module")
def states_in_data() -> list[str]:
    _require_cache(macro.STATES_IN_DATA_PATH)
    return macro.get_states_in_data()


def _extract_orig_row(vintage: int, state: str) -> list[str]:
    """First orig row for `state` in the given SFLLD vintage (local zip, no network)."""
    zpath = macro.SFLLD_DIR / f"sample_{vintage}.zip"
    with zipfile.ZipFile(zpath) as z:
        orig_name = next(n for n in z.namelist() if "orig" in n)
        with z.open(orig_name) as f:
            for line in f:
                parts = line.decode().rstrip("\n").split("|")
                if parts[macro.ORIG_PROPERTY_STATE_IDX] == state:
                    return parts
    raise AssertionError(f"no {state} loan found in vintage {vintage}")


def _extract_perf_rows(vintage: int, loan_id: str, periods: set) -> dict:
    """Performance rows for `loan_id` at the requested yyyymm periods (local zip)."""
    zpath = macro.SFLLD_DIR / f"sample_{vintage}.zip"
    out = {}
    with zipfile.ZipFile(zpath) as z:
        svcg_name = next(n for n in z.namelist() if "svcg" in n)
        with z.open(svcg_name) as f:
            for line in f:
                parts = line.decode().rstrip("\n").split("|")
                if parts[0] == loan_id and parts[1] in periods:
                    out[parts[1]] = parts
                    if len(out) == len(periods):
                        break
    return out


# ---------------------------------------------------------------------------
# 1. Series coverage vs. states in the data
# ---------------------------------------------------------------------------
def test_states_in_data_matches_expected(states_in_data):
    # 50 states + DC + PR + GU + VI -- verified by direct inspection of every
    # SFLLD orig zip (see freddie.macro.get_states_in_data).
    assert set(states_in_data) == EXPECTED_STATES
    assert len(states_in_data) == 54


def test_series_coverage_vs_states_in_data(state_macro_panel, states_in_data):
    assert set(state_macro_panel["property_state"].unique()) == set(states_in_data)


def test_coverage_note_fallback_sets_are_the_documented_ones(states_in_data):
    coverage = macro.build_coverage_note(states_in_data)
    # Empirically verified against the live FRED API (module docstring
    # "COVERAGE NOTE"): GU/VI have no state UR or STHPI series; PR has UR
    # but no STHPI series.
    assert coverage["ur_fallback_states"] == sorted({"GU", "VI"})
    assert coverage["hpi_fallback_states"] == sorted({"GU", "PR", "VI"})
    assert macro.UR_NATIONAL_FALLBACK_STATES == frozenset({"GU", "VI"})
    assert macro.HPI_NATIONAL_FALLBACK_STATES == frozenset({"GU", "PR", "VI"})


def test_fallback_states_flagged_in_panel(state_macro_panel):
    for state in macro.UR_NATIONAL_FALLBACK_STATES:
        assert state_macro_panel.loc[state_macro_panel.property_state == state, "uer_is_national_fallback"].all()
    for state in macro.HPI_NATIONAL_FALLBACK_STATES:
        assert state_macro_panel.loc[state_macro_panel.property_state == state, "hpi_is_national_fallback"].all()
    # Non-fallback states must NOT be flagged.
    non_fb = state_macro_panel.loc[~state_macro_panel.property_state.isin(macro.UR_NATIONAL_FALLBACK_STATES)]
    assert not non_fb["uer_is_national_fallback"].any()


def test_coverage_note_file_on_disk_matches_constants():
    _require_cache(macro.COVERAGE_NOTE_PATH)
    import json
    coverage = json.loads(macro.COVERAGE_NOTE_PATH.read_text())
    assert coverage["ur_fallback_states"] == sorted(macro.UR_NATIONAL_FALLBACK_STATES)
    assert coverage["hpi_fallback_states"] == sorted(macro.HPI_NATIONAL_FALLBACK_STATES)


# ---------------------------------------------------------------------------
# 2. Derived-column sanity (rebase, forward-fill, timing convention)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("state", ["CA", "TX", "FL", "NV", "ND", "PR"])
def test_hpi_rebased_to_100_at_2000_01(state_macro_panel, state):
    row = state_macro_panel[(state_macro_panel.property_state == state) & (state_macro_panel.month == macro.REBASE_MONTH)]
    assert len(row) == 1
    assert row["hpi_index"].iloc[0] == pytest.approx(100.0, abs=1e-9)


def test_step_forward_fill_within_quarter(state_macro_panel):
    # A quarterly print at a quarter-start month must be held flat (not
    # interpolated) across the other two months of that quarter -- the
    # documented "no intra-quarter information" choice.
    nv = state_macro_panel[state_macro_panel.property_state == "NV"].sort_values("month").set_index("month")
    for q_start in ["2015-01-01", "2015-04-01", "2015-07-01", "2015-10-01"]:
        q_start = pd.Timestamp(q_start)
        base = nv.loc[q_start, "hpi_raw"]
        for offset in (1, 2):
            mid_month = q_start + pd.DateOffset(months=offset)
            assert nv.loc[mid_month, "hpi_raw"] == pytest.approx(base), (
                f"NV hpi_raw at {mid_month} should equal the quarter-start "
                f"print at {q_start} under forward-fill"
            )


def test_hpi_growth_zero_in_non_reporting_months(state_macro_panel):
    # Direct consequence of the step-forward-fill: hpi_growth (monthly
    # log-diff) is exactly 0 in the two non-reporting months of a quarter.
    nv = state_macro_panel[state_macro_panel.property_state == "NV"].sort_values("month").set_index("month")
    for m in ["2015-02-01", "2015-03-01", "2015-05-01", "2015-06-01"]:
        assert nv.loc[pd.Timestamp(m), "hpi_growth"] == pytest.approx(0.0, abs=1e-9)


def test_timing_convention_lags_are_truly_lagged(state_macro_panel):
    # uer_lag1(t) == uer(t-1); hpi_growth_lag1(t) == hpi_growth(t-1); mirrors
    # the DCR panel's "only past values are ever referenced" convention.
    for state in ["CA", "ND", "NV"]:
        g = state_macro_panel[state_macro_panel.property_state == state].sort_values("month").reset_index(drop=True)
        # Compare row k (k>=1) against row k-1, over a representative slice.
        sample_idx = range(50, min(200, len(g)))
        for k in sample_idx:
            prev_uer, cur_uer_lag1 = g.loc[k - 1, "uer"], g.loc[k, "uer_lag1"]
            if pd.isna(prev_uer):
                assert pd.isna(cur_uer_lag1)
            else:
                assert cur_uer_lag1 == pytest.approx(prev_uer)
            prev_growth = g.loc[k - 1, "hpi_growth"]
            cur_lag = g.loc[k, "hpi_growth_lag1"]
            if pd.isna(prev_growth):
                assert pd.isna(cur_lag)
            else:
                assert cur_lag == pytest.approx(prev_growth)


# ---------------------------------------------------------------------------
# 3. merge_macro: coverage (no NaNs on a historical sample) + schema
# ---------------------------------------------------------------------------
def _synthetic_sample_panel() -> pd.DataFrame:
    """A handful of (state, month) combos well inside the covered date range,
    spanning highlight states, ordinary states, and a fallback territory.
    """
    rows = []
    for state in ["CA", "TX", "FL", "NV", "ND", "PR", "NY", "WY"]:
        for month in [200601, 200812, 201106, 201412, 201803, 202001]:
            rows.append({"property_state": state, "monthly_reporting_period": month})
    return pd.DataFrame(rows)


def test_merge_macro_no_nans_on_historical_sample(state_macro_panel):
    panel = _synthetic_sample_panel()
    merged = macro.merge_macro(panel, macro=state_macro_panel)
    macro_cols = [
        "uer", "delta_uer", "state_hpi_now", "hpi_growth",
        "uer_lag1", "delta_uer_lag1", "hpi_growth_lag1",
    ]
    assert merged.shape[0] == panel.shape[0]
    for col in macro_cols:
        assert col in merged.columns
        assert merged[col].notna().all(), f"unexpected NaN in {col} on historical sample"


def test_merge_macro_columns_present(state_macro_panel):
    panel = _synthetic_sample_panel()
    merged = macro.merge_macro(panel, macro=state_macro_panel)
    expected = {
        "property_state", "monthly_reporting_period", "uer", "delta_uer",
        "state_hpi_now", "hpi_growth", "uer_lag1", "delta_uer_lag1",
        "hpi_growth_lag1", "uer_is_national_fallback", "hpi_is_national_fallback",
    }
    assert expected.issubset(merged.columns)
    # No updated_ltv without the LTV/UPB columns.
    assert "updated_ltv" not in merged.columns


def test_merge_macro_fallback_flags_flow_through(state_macro_panel):
    panel = pd.DataFrame({"property_state": ["GU", "PR", "CA"], "monthly_reporting_period": [201501, 201501, 201501]})
    merged = macro.merge_macro(panel, macro=state_macro_panel)
    assert merged.loc[merged.property_state == "GU", "uer_is_national_fallback"].all()
    assert merged.loc[merged.property_state == "GU", "hpi_is_national_fallback"].all()
    assert merged.loc[merged.property_state == "PR", "hpi_is_national_fallback"].all()
    assert not merged.loc[merged.property_state == "PR", "uer_is_national_fallback"].any()
    assert not merged.loc[merged.property_state == "CA", "uer_is_national_fallback"].any()
    assert not merged.loc[merged.property_state == "CA", "hpi_is_national_fallback"].any()


# ---------------------------------------------------------------------------
# 4. updated_ltv sanity, on REAL SFLLD loans + REAL cached FRED HPI
# ---------------------------------------------------------------------------
def test_updated_ltv_rises_through_the_nv_crash(state_macro_panel):
    # A real 2006-vintage NV loan (first NV loan in sample_2006.zip's orig
    # table): origination LTV 80, house prices roughly halve NV-wide by
    # 2009 (NVSTHPI), so updated_ltv must clear the origination LTV by a
    # wide margin despite ~3.5% of amortisation paydown.
    orig = _extract_orig_row(2006, "NV")
    loan_id, orig_ltv, orig_upb = orig[19], float(orig[11]), float(orig[10])
    perf = _extract_perf_rows(2006, loan_id, {"200903", "200906"})
    assert set(perf) == {"200903", "200906"}

    panel = pd.DataFrame(
        [
            {
                "property_state": "NV",
                "monthly_reporting_period": int(p[1]),
                "orig_ltv": orig_ltv,
                "orig_upb": orig_upb,
                "current_upb": float(p[2]),
                "first_payment_date": int(orig[1]),
            }
            for p in perf.values()
        ]
    )
    merged = macro.merge_macro(panel, macro=state_macro_panel)
    assert "updated_ltv" in merged.columns
    assert merged["updated_ltv"].notna().all()
    for _, row in merged.iterrows():
        assert row["updated_ltv"] > orig_ltv, (
            f"expected updated_ltv > orig_ltv ({orig_ltv}) for a 2006 NV loan "
            f"observed in 2009 (post-crash), got {row['updated_ltv']:.1f}"
        )


def test_updated_ltv_falls_as_nv_recovers():
    # 2011-2013 vintages are not in the SFLLD sample (documented coverage
    # gap, see MASTER_PLAN/shared facts) so the spec's illustrative "2012
    # loan" is stood in for by the nearest available vintage, 2010, whose
    # origination sits close to the NV HPI trough (~2010-2011). By 2019 NV
    # house prices have recovered close to their prior peak, so updated_ltv
    # must fall WELL BELOW origination LTV.
    orig = _extract_orig_row(2010, "NV")
    loan_id, orig_ltv, orig_upb = orig[19], float(orig[11]), float(orig[10])
    perf = _extract_perf_rows(2010, loan_id, {"201006", "201906"})
    assert set(perf) == {"201006", "201906"}

    macro_panel = macro.get_or_build_state_macro_panel()
    panel = pd.DataFrame(
        [
            {
                "property_state": "NV",
                "monthly_reporting_period": int(p[1]),
                "orig_ltv": orig_ltv,
                "orig_upb": orig_upb,
                "current_upb": float(p[2]),
                "first_payment_date": int(orig[1]),
            }
            for p in perf.values()
        ]
    )
    merged = macro.merge_macro(panel, macro=macro_panel).set_index("monthly_reporting_period")
    assert merged.loc[201906, "updated_ltv"] < orig_ltv, (
        f"expected updated_ltv < orig_ltv ({orig_ltv}) for a 2010 NV loan "
        f"observed in 2019 (post-recovery), got {merged.loc[201906, 'updated_ltv']:.1f}"
    )
    # And it should be materially below the near-trough (2010) reading.
    assert merged.loc[201906, "updated_ltv"] < merged.loc[201006, "updated_ltv"]


def test_updated_ltv_formula_matches_documented_derivation(state_macro_panel):
    # Direct arithmetic check of the formula in the module docstring,
    # independent of merge_macro's plumbing.
    nv = state_macro_panel[state_macro_panel.property_state == "NV"].set_index("month")["hpi_index"]
    orig_ltv, orig_upb, current_upb = 80.0, 254000.0, 245566.35
    hpi_orig = nv.loc[pd.Timestamp("2006-03-01")]
    hpi_now = nv.loc[pd.Timestamp("2009-03-01")]
    expected = orig_ltv * (current_upb / orig_upb) * (hpi_orig / hpi_now)

    panel = pd.DataFrame(
        [{
            "property_state": "NV", "monthly_reporting_period": 200903,
            "orig_ltv": orig_ltv, "orig_upb": orig_upb, "current_upb": current_upb,
            "first_payment_date": 200603,
        }]
    )
    merged = macro.merge_macro(panel, macro=state_macro_panel)
    assert merged["updated_ltv"].iloc[0] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# 5. Exhibits actually got written
# ---------------------------------------------------------------------------
def test_exhibits_exist():
    uer_path = macro.EXHIBIT_DIR / "state_uer_2000_2025.png"
    hpi_path = macro.EXHIBIT_DIR / "state_hpi_growth_2000_2025.png"
    if not uer_path.exists() or not hpi_path.exists():
        pytest.skip("exhibits not built yet -- run `python -m freddie.macro` first")
    assert uer_path.stat().st_size > 0
    assert hpi_path.stat().st_size > 0
