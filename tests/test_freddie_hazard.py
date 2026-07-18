"""Tests for freddie/fit_hazard.py -- SFLLD champion hazard refit (rung 3).

Speed note: the production `main()` pipeline processes the full 39.5M-row
panel_monthly.parquet (see freddie/fit_hazard.py's module docstring for the
runtime rationale of the WESML case-control subsample). Re-running that full
pipeline inside every test-suite invocation would make the suite far too
slow, so these tests exercise the SAME functions (`build_model_frame`,
`sample_case_control`, `fit_hazard`, `predict_hazard`, `score_by_year`,
`compute_auc`) on a single small vintage (2008: 2.22M loan-months / 50,000
loans, entirely pre-2017 so it has real train-window events) read straight
from the cached parquet files -- no mocking of the modeling logic itself,
just a smaller real slice of it. The full-panel run that actually produces
`outputs/freddie/hazard/*` is a separate, deliberate `python -m
freddie.fit_hazard` invocation (see MEMORY / orchestrator notes), not part
of this test file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from freddie import fit_hazard as fh
from freddie import macro as freddie_macro

TEST_VINTAGE = 2008          # smallest pre-2017-performance vintage on disk
TEST_CONTROL_RATE = 0.2      # richer than the production 0.05 -- keeps this
                              # single-vintage slice's ~4.2k events well
                              # powered without needing a huge control pool


def _require_cache(path):
    if not path.exists():
        pytest.skip(f"cache not built yet ({path}) -- run the freddie ingestion pipeline first")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def raw_subset() -> tuple[pd.DataFrame, pd.DataFrame]:
    _require_cache(fh.PANEL_PATH)
    _require_cache(fh.ORIG_PATH)

    panel = pd.read_parquet(fh.PANEL_PATH, columns=[
        "loan_sequence_number", "vintage", "monthly_reporting_period",
        "loan_age", "current_actual_upb", "d90_event",
    ])
    panel = panel.loc[panel["vintage"] == TEST_VINTAGE].drop(columns=["vintage"]).reset_index(drop=True)

    orig = pd.read_parquet(fh.ORIG_PATH, columns=[
        "loan_sequence_number", "credit_score", "dti", "occupancy_status",
        "loan_purpose", "channel", "property_state", "orig_ltv", "orig_upb",
        "first_payment_date",
    ])
    orig = orig.loc[orig["loan_sequence_number"].isin(set(panel["loan_sequence_number"]))].reset_index(drop=True)
    return panel, orig


@pytest.fixture(scope="module")
def small_frame(raw_subset) -> pd.DataFrame:
    panel, orig = raw_subset
    return fh.build_model_frame(panel=panel, orig=orig)


@pytest.fixture(scope="module")
def train_split(small_frame) -> tuple[pd.DataFrame, np.ndarray]:
    train_mask = (small_frame["monthly_reporting_period"] <= fh.TRAIN_CUTOFF).to_numpy()
    return small_frame.loc[train_mask], train_mask


@pytest.fixture(scope="module")
def fitted_a(train_split) -> fh.HazardModel:
    train_df, _ = train_split
    sample = fh.sample_case_control(train_df, rate=TEST_CONTROL_RATE, seed=fh.SEED_A)
    return fh.fit_hazard(sample, formula=fh.BASE_FORMULA, name="test_champion_a")


@pytest.fixture(scope="module")
def fitted_b(train_split) -> fh.HazardModel:
    train_df, _ = train_split
    sample = fh.sample_case_control(train_df, rate=TEST_CONTROL_RATE, seed=fh.SEED_B)
    return fh.fit_hazard(sample, formula=fh.BASE_FORMULA, name="test_champion_b")


# ---------------------------------------------------------------------------
# 1. Model frame plumbing
# ---------------------------------------------------------------------------
def test_model_frame_has_required_columns(small_frame):
    for col in fh.MODEL_FRAME_COLS:
        assert col in small_frame.columns, f"missing model-frame column: {col}"


def test_model_frame_row_count_matches_panel_subset(raw_subset, small_frame):
    panel, _ = raw_subset
    assert len(small_frame) == len(panel)


def test_covid_regime_flag_matches_documented_window(small_frame):
    perf = small_frame["monthly_reporting_period"]
    expect = ((perf >= fh.COVID_START) & (perf <= fh.COVID_END)).astype("int8")
    pd.testing.assert_series_equal(small_frame["covid_regime"], expect, check_names=False)
    # sanity: the window is non-empty in this data slice
    assert small_frame["covid_regime"].sum() > 0


# ---------------------------------------------------------------------------
# 2. No-lookahead: macro lag verified MECHANICALLY against the raw state
#    macro panel (not just trusting freddie.macro's own unit tests -- this
#    checks the WIRING inside build_model_frame reproduces the lag exactly).
# ---------------------------------------------------------------------------
def test_no_lookahead_macro_lag_mechanical(small_frame):
    state_macro = freddie_macro.load_state_macro_panel()
    lookup = state_macro.set_index(["property_state", "month"])["uer"]

    sample = small_frame.dropna(subset=["uer_lag1", "property_state"]).sample(
        n=min(200, len(small_frame)), random_state=0,
    )
    checked = 0
    for _, row in sample.iterrows():
        prior_month = (row["monthly_reporting_period"] - pd.DateOffset(months=1)).replace(day=1)
        key = (row["property_state"], prior_month)
        if key not in lookup.index:
            continue
        true_prior_uer = lookup.loc[key]
        if pd.isna(true_prior_uer):
            continue
        assert row["uer_lag1"] == pytest.approx(true_prior_uer, abs=1e-9), (
            f"uer_lag1 mismatch for {row['property_state']} at "
            f"{row['monthly_reporting_period'].date()}: wired={row['uer_lag1']}, "
            f"true prior-month uer={true_prior_uer}"
        )
        checked += 1
    assert checked > 50, "too few rows had a resolvable prior-month macro key to check"


def test_no_lookahead_current_month_never_used(small_frame):
    """uer_lag1 must differ from the CURRENT month's uer for any row where the
    state series actually moves month to month -- i.e. this is a lag, not an
    accidental same-month copy. (A same-month copy would make uer_lag1 ==
    current uer identically across the whole panel, which this rules out.)
    """
    state_macro = freddie_macro.load_state_macro_panel()
    cur_lookup = state_macro.set_index(["property_state", "month"])["uer"]

    sample = small_frame.dropna(subset=["uer_lag1", "property_state"]).sample(
        n=min(200, len(small_frame)), random_state=1,
    )
    n_diff = 0
    n_checked = 0
    for _, row in sample.iterrows():
        key = (row["property_state"], row["monthly_reporting_period"].replace(day=1))
        if key not in cur_lookup.index:
            continue
        cur_uer = cur_lookup.loc[key]
        if pd.isna(cur_uer):
            continue
        n_checked += 1
        if row["uer_lag1"] != pytest.approx(cur_uer, abs=1e-9):
            n_diff += 1
    assert n_checked > 50
    # at least some rows must show a genuine lag (current-month series moves)
    assert n_diff > 0, "uer_lag1 appears identical to current-month uer everywhere -- lookahead suspected"


# ---------------------------------------------------------------------------
# 3. Case-control (WESML) subsampling
# ---------------------------------------------------------------------------
def test_case_control_keeps_all_events(train_split):
    train_df, _ = train_split
    sample = fh.sample_case_control(train_df, rate=TEST_CONTROL_RATE, seed=fh.SEED_A)
    n_events_full = int(train_df["d90_event"].sum())
    n_events_sample = int(sample.loc[sample["d90_event"] == 1].shape[0])
    assert n_events_sample == n_events_full


def test_case_control_weights(train_split):
    train_df, _ = train_split
    sample = fh.sample_case_control(train_df, rate=TEST_CONTROL_RATE, seed=fh.SEED_A)
    events = sample.loc[sample["d90_event"] == 1, "freq_weight"]
    controls = sample.loc[sample["d90_event"] == 0, "freq_weight"]
    assert (events == 1.0).all()
    assert np.allclose(controls.to_numpy(), 1.0 / TEST_CONTROL_RATE)


# ---------------------------------------------------------------------------
# 4. Coefficient signs -- sane per the per-variable rationale table
# ---------------------------------------------------------------------------
def test_coefficient_signs_sane(fitted_a):
    params = fitted_a.params
    # higher FICO -> lower hazard
    assert params["fico_s"] < 0
    # higher (updated) LTV -> higher hazard
    assert params["ltv10"] > 0
    # higher lagged state unemployment -> higher hazard
    assert params["uer_lag1"] > 0


def test_hazard_ratios_finite_and_positive(fitted_a):
    hr = np.exp(fitted_a.params)
    assert np.isfinite(hr).all()
    assert (hr > 0).all()


# ---------------------------------------------------------------------------
# 5. Discrimination -- AUC floor
# ---------------------------------------------------------------------------
def test_auc_floor_train(fitted_a, small_frame, train_split):
    _, train_mask = train_split
    preds, _ = fh.score_by_year(fitted_a, small_frame)
    train_auc = fh.compute_auc(small_frame, preds, train_mask)
    assert train_auc > fh.AUC_FLOOR_TRAIN


# ---------------------------------------------------------------------------
# 6. Predictions are finite for well-formed rows
# ---------------------------------------------------------------------------
def test_predictions_finite_for_complete_rows(fitted_a, small_frame):
    complete = small_frame.dropna(subset=fh.REQUIRED_COLS)
    preds = fh.predict_hazard(fitted_a, complete)
    preds = preds.dropna()
    assert len(preds) > 0
    assert np.isfinite(preds.to_numpy()).all()
    # hazards are probabilities
    assert (preds >= 0).all()
    assert (preds <= 1).all()


# ---------------------------------------------------------------------------
# 7. Subsample-stability check (second seed)
# ---------------------------------------------------------------------------
def test_subsample_stability_no_sign_flips(fitted_a, fitted_b):
    common = fitted_a.params.index.intersection(fitted_b.params.index)
    a = fitted_a.params.loc[common]
    b = fitted_b.params.loc[common]
    flips = np.sign(a) != np.sign(b)
    # Intercept and near-zero coefficients can be noisy on a single small
    # vintage; require no sign flips among the substantive covariates.
    substantive = [c for c in common if c not in ("Intercept",)]
    assert not any(np.sign(a[substantive]) != np.sign(b[substantive])), (
        f"sign flip(s) between seeds: {a[substantive][np.sign(a[substantive]) != np.sign(b[substantive])]}"
    )


def test_subsample_stability_bounded_relative_difference(fitted_a, fitted_b):
    common = fitted_a.params.index.intersection(fitted_b.params.index)
    a = fitted_a.params.loc[common]
    b = fitted_b.params.loc[common]
    rel_diff = (a - b).abs() / a.abs().clip(lower=1e-6)
    # Generous bound (this is a single small vintage, not the full-population
    # champion fit) -- catches gross instability / a broken weighting scheme,
    # not fine-grained noise.
    assert rel_diff.max() < 1.0, f"largest relative coefficient swing between seeds: {rel_diff.max():.3f}"
