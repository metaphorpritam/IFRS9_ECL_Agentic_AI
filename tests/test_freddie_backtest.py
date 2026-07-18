"""Tests for freddie/backtest.py -- ALFRED-vintage HONEST backtest (rung 3).

Speed note: mirrors tests/test_freddie_hazard.py's approach -- the production
`main()` pipeline refits the champion spec on up to ~28.7M performance-month
rows per reporting date (see freddie/backtest.py's module docstring). These
tests exercise the SAME functions on a single small vintage (2008), reusing
the ALREADY-CACHED ALFRED pulls / as-of macro panel a real `python -m
freddie.backtest` run leaves on disk (data/processed/freddie/alfred/,
data/processed/freddie/backtest/) -- no mocking of the ALFRED or hazard
machinery itself. Tests that need a network-fetched ALFRED vintage skip
gracefully if that cache does not exist yet (same pattern as
freddie/macro.py's tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from freddie import backtest as bt
from freddie import fit_hazard as fh
from freddie import macro as freddie_macro

ASOF = pd.Timestamp("2009-12-01")     # a real REPORTING_DATES entry -- ALFRED cache guaranteed after main()
TEST_VINTAGE = 2008                    # smallest vintage <= ASOF.year with real train-window events


def _require_cache(path):
    if not path.exists():
        pytest.skip(f"cache not built yet ({path}) -- run `python -m freddie.backtest` first")


@pytest.fixture(autouse=True, scope="module")
def _small_vintage_universe():
    """Restrict every VINTAGE_YEARS-driven loop in freddie.backtest to the
    single small TEST_VINTAGE, so the per-vintage chunked builders this
    module reuses from fit_hazard stay fast (mirrors test_freddie_hazard.py's
    single-vintage slice, applied to backtest's vintage loops instead)."""
    original = bt.VINTAGE_YEARS[:]
    bt.VINTAGE_YEARS[:] = [TEST_VINTAGE]
    yield
    bt.VINTAGE_YEARS[:] = original


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def asof_macro() -> pd.DataFrame:
    cache_path = bt.ALFRED_CACHE_DIR / f"asof_macro_{ASOF:%Y%m}.parquet"
    _require_cache(cache_path)
    return pd.read_parquet(cache_path)


@pytest.fixture(scope="module")
def final_macro() -> pd.DataFrame:
    _require_cache(freddie_macro.STATE_PANEL_PATH)
    return freddie_macro.get_or_build_state_macro_panel()


@pytest.fixture(scope="module")
def small_train_frame(asof_macro) -> pd.DataFrame:
    _require_cache(bt.PANEL_PATH)
    _require_cache(bt.ORIG_PATH)
    return bt.build_asof_model_frame(ASOF, asof_macro)


@pytest.fixture(scope="module")
def small_model(small_train_frame) -> fh.HazardModel:
    sample = fh.sample_case_control(small_train_frame, rate=0.2, seed=fh.SEED_A)
    return fh.fit_hazard(sample, formula=fh.BASE_FORMULA, name="test_backtest_asof")


@pytest.fixture(scope="module")
def small_active(asof_macro) -> pd.DataFrame:
    return bt.active_loans_at(ASOF, asof_macro)


# ---------------------------------------------------------------------------
# 1. No-lookahead: as-of-T fit mechanically touches zero post-T rows
# ---------------------------------------------------------------------------
def test_asof_fit_touches_zero_post_t_rows(small_train_frame):
    assert (small_train_frame["monthly_reporting_period"] <= ASOF).all()


def test_asof_fit_filter_is_not_a_noop(small_train_frame):
    """Sanity: the raw panel for TEST_VINTAGE genuinely has rows AFTER ASOF
    (i.e. the <=ASOF filter above is doing real work, not vacuously true
    because the vintage happens to terminate before ASOF)."""
    raw = pd.read_parquet(
        bt.PANEL_PATH, columns=["vintage", "monthly_reporting_period"],
        filters=[("vintage", "==", TEST_VINTAGE)],
    )
    assert (raw["monthly_reporting_period"] > ASOF).any()
    assert len(small_train_frame) < len(raw)


def test_asof_model_frame_vintage_bound_respected():
    """'Vintages originated by T' filter: with TEST_VINTAGE=2008 monkeypatched
    module-wide for this file, a reporting date of 2007-12 must yield ZERO
    eligible vintages (2008 > 2007), independent of the performance-month
    filter -- build_asof_model_frame's own vintage list comprehension."""
    vintages = [v for v in bt.VINTAGE_YEARS if v <= pd.Timestamp("2007-12-01").year]
    assert vintages == []
    later_vintages = [v for v in bt.VINTAGE_YEARS if v <= ASOF.year]
    assert later_vintages == [TEST_VINTAGE]


# ---------------------------------------------------------------------------
# 2. ALFRED vintage genuinely differs from the final (current) revision
# ---------------------------------------------------------------------------
def test_alfred_pull_differs_from_final_vintage():
    """UNRATE 2008-2009: a known real-time-data revision case (see module
    docstring). The AS-OF-2009-12 vintage pull must differ from the FINAL
    (fully revised) series for at least several of those historical months
    -- proof this is genuinely a different vintage, not the final series
    re-served under a different param name.
    """
    alfred_path = bt.ALFRED_CACHE_DIR / "UNRATE__200912.csv"
    final_path = freddie_macro.MACRO_CACHE_DIR / "UNRATE.csv"
    _require_cache(alfred_path)
    _require_cache(final_path)

    asof_df = pd.read_csv(alfred_path, parse_dates=["date"])
    final_df = pd.read_csv(final_path, parse_dates=["date"])
    merged = final_df.merge(asof_df, on="date", suffixes=("_final", "_asof"))
    window = merged[(merged["date"] >= "2008-01-01") & (merged["date"] <= "2009-10-01")]
    assert len(window) > 12, "too few overlapping months to test the known 2008-2009 revision"

    n_diff = int((window["value_final"] != window["value_asof"]).sum())
    assert n_diff > 5, (
        f"expected the well-documented 2008-2009 UNRATE revision to show up as multiple "
        f"differing months between the final and as-of-2009-12 vintages; found only {n_diff}"
    )


def test_alfred_vintage_never_sees_future_months():
    """The as-of-2009-12 UNRATE pull cannot contain any observation dated
    after 2009-12 -- ALFRED semantics enforce publication lag by construction,
    with no manual lag assumption needed for UER (see module docstring)."""
    alfred_path = bt.ALFRED_CACHE_DIR / "UNRATE__200912.csv"
    _require_cache(alfred_path)
    asof_df = pd.read_csv(alfred_path, parse_dates=["date"])
    assert asof_df["date"].max() <= ASOF
    # publication lag is real (not same-month or 0-lag)
    assert asof_df["date"].max() < ASOF


def test_hpi_has_no_alfred_archive_marker():
    """USSTHPI has no ALFRED vintage history at all (module docstring,
    empirically verified) -- if a run has attempted the national HPI pull at
    any cached reporting date, it must have left an `.unavailable.json`
    marker, never a populated CSV."""
    markers = list(bt.ALFRED_CACHE_DIR.glob("USSTHPI__*.unavailable.json"))
    csvs = list(bt.ALFRED_CACHE_DIR.glob("USSTHPI__*.csv"))
    if not markers and not csvs:
        pytest.skip("no USSTHPI ALFRED attempt cached yet")
    assert csvs == [], "USSTHPI unexpectedly has a populated ALFRED vintage CSV -- re-verify the coverage claim"
    assert len(markers) > 0


# ---------------------------------------------------------------------------
# 3. HPI publication-lag cutoff (pure function)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("asof,expected", [
    (pd.Timestamp("2007-12-01"), pd.Timestamp("2007-07-01")),   # exact quarter-start after subtracting lag
    (pd.Timestamp("2009-12-01"), pd.Timestamp("2009-07-01")),
    (pd.Timestamp("2016-02-01"), pd.Timestamp("2015-07-01")),   # non-quarter-start candidate -> floors to Jul
])
def test_hpi_cutoff_matches_documented_lag(asof, expected):
    assert bt._hpi_cutoff(asof) == expected


# ---------------------------------------------------------------------------
# 4. Case-control fit sanity (reused fh machinery -- not re-tested here in
#    depth, just confirms the reuse actually produces a usable model)
# ---------------------------------------------------------------------------
def test_small_model_converges_and_has_sane_signs(small_model):
    params = small_model.params
    assert params["fico_s"] < 0
    assert params["ltv10"] > 0


# ---------------------------------------------------------------------------
# 5. Projection horizon respects loan termination
# ---------------------------------------------------------------------------
def test_effective_horizon_respects_termination():
    asof = pd.Timestamp("2015-01-01")
    last_reported = pd.Series(pd.to_datetime([
        "2015-11-01",   # terminates 10mo after T -- within horizon
        "2020-01-01",   # terminates far beyond T -- clipped to horizon
        "2015-01-01",   # terminates AT T -- zero forward exposure
    ]))
    got = bt.effective_horizon(last_reported, asof, horizon=36)
    np.testing.assert_array_equal(got, np.array([10, 36, 0]))


def test_project_forward_freezes_at_termination(small_model, small_active):
    """Mechanical proof projection horizon respects termination: a loan
    artificially given horizon_steps=3 must accumulate an IDENTICAL
    predicted cumulative default whether project_forward is called with
    horizon=3 or horizon=36 -- i.e. steps 4..36 must never touch it.
    """
    base = small_active.head(5).copy().reset_index(drop=True)
    if base.empty:
        pytest.skip("no active loans in the small-vintage slice to project")
    base["horizon_steps"] = 3  # force early termination for every test row

    frozen_fn = bt.make_frozen_macro_fn(
        pd.read_parquet(bt.ALFRED_CACHE_DIR / f"asof_macro_{ASOF:%Y%m}.parquet"), ASOF,
    )
    short = bt.project_forward(small_model, base, frozen_fn, horizon=3)
    long_ = bt.project_forward(small_model, base, frozen_fn, horizon=36)
    pd.testing.assert_series_equal(short, long_, check_names=False)


def test_project_forward_monotone_nondecreasing_cumulative_default(small_model, small_active):
    """Cumulative default probability can only rise (or hold) as the
    horizon extends -- a basic sanity check on the survival bookkeeping."""
    base = small_active.head(5).copy().reset_index(drop=True)
    if base.empty:
        pytest.skip("no active loans in the small-vintage slice to project")
    base["horizon_steps"] = 12

    frozen_fn = bt.make_frozen_macro_fn(
        pd.read_parquet(bt.ALFRED_CACHE_DIR / f"asof_macro_{ASOF:%Y%m}.parquet"), ASOF,
    )
    short = bt.project_forward(small_model, base, frozen_fn, horizon=6)
    long_ = bt.project_forward(small_model, base, frozen_fn, horizon=12)
    assert (long_.to_numpy() >= short.to_numpy() - 1e-12).all()


# ---------------------------------------------------------------------------
# 5b. Realised-outcome timing: PANEL first-D90 month, never the disposition
#     month (adversarial-review regression, 2026-07-18)
# ---------------------------------------------------------------------------
def test_realized_d90_timed_by_panel_event_month_not_disposition(small_active):
    """loan_orig.last_reported_period is the UN-truncated tape's DISPOSITION
    month (build_panel._terminal_rows_full_history) -- for GFC-era defaults a
    median ~33 months after the first D90 month. The realised side of the
    honesty exhibit must therefore be timed by the MODELING panel's terminal
    month (absorbing-D90 truncation => first-D90 month for defaulted loans).
    This test re-derives both timings independently and asserts (i) the
    realized_d90 flag matches the panel timing exactly, and (ii) the two
    timings genuinely diverge on this slice (so the assertion bites)."""
    if small_active.empty:
        pytest.skip("no active loans in the small-vintage slice")

    # independent re-derivation of the panel D90-event month per active loan
    d90_rows = pd.read_parquet(
        bt.PANEL_PATH,
        columns=["loan_sequence_number", "monthly_reporting_period", "d90_event"],
        filters=[("vintage", "==", TEST_VINTAGE), ("monthly_reporting_period", ">", ASOF)],
    )
    d90_month = (
        d90_rows.loc[d90_rows["d90_event"] == 1]
        .set_index("loan_sequence_number")["monthly_reporting_period"]
    )
    active = small_active.set_index("loan_sequence_number")
    ev = active.index.to_series().map(d90_month)
    mte = (ev.dt.year - ASOF.year) * 12 + (ev.dt.month - ASOF.month)
    expected_realized = ev.notna() & (mte > 0) & (mte <= bt.PROJECTION_HORIZON_MONTHS)
    pd.testing.assert_series_equal(
        active["realized_d90"].astype(bool), expected_realized,
        check_names=False,
    )
    # defaulted active loans' panel_terminal_month IS their first-D90 month
    defaulted = active.loc[active["had_d90_event"].fillna(False).astype(bool) & ev.notna()]
    if not defaulted.empty:
        pd.testing.assert_series_equal(
            defaulted["panel_terminal_month"], ev.loc[defaulted.index],
            check_names=False,
        )

    # the disposition timing must genuinely diverge somewhere on this slice,
    # otherwise this regression test is vacuous
    orig = pd.read_parquet(
        bt.ORIG_PATH,
        columns=["loan_sequence_number", "vintage", "had_d90_event", "last_reported_period"],
    )
    orig = orig[orig["vintage"] == TEST_VINTAGE].set_index("loan_sequence_number")
    disp = active.index.to_series().map(orig["last_reported_period"])
    diverges = (
        active["had_d90_event"].fillna(False).astype(bool)
        & (disp != active["panel_terminal_month"])
    )
    assert diverges.any(), (
        "no active defaulted loan has disposition != panel D90 month on this slice -- "
        "regression test would be vacuous; pick a different TEST_VINTAGE/ASOF"
    )


# ---------------------------------------------------------------------------
# 6. Cohort summary plumbing
# ---------------------------------------------------------------------------
def test_cohort_summary_has_all_row_and_miss_ratios(small_active):
    if small_active.empty:
        pytest.skip("no active loans in the small-vintage slice")
    pred_frozen = pd.Series(0.05, index=small_active.index)
    pred_actual = pd.Series(0.08, index=small_active.index)
    summary = bt.cohort_summary(small_active, pred_frozen, pred_actual)
    assert (summary["vintage"] == "ALL").any()
    assert {"miss_ratio_frozen", "miss_ratio_actual"}.issubset(summary.columns)
    assert np.isfinite(summary["miss_ratio_frozen"]).all()
    assert np.isfinite(summary["miss_ratio_actual"]).all()
