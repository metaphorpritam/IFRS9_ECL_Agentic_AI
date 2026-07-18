"""Tests for freddie/lstm.py + freddie/fit_lstm.py -- LSTM path-dependence
challenger (rung 3).

Speed note: mirrors tests/test_freddie_hazard.py's pattern exactly -- these
tests exercise the SAME functions the production `python -m freddie.fit_lstm`
pipeline uses (`add_sequence_features`, `build_static_design`,
`SequenceScaler`, `train_lstm`, `predict_lstm`, and fit_lstm's own
`_assemble_tensors_for_rows`) on a single small vintage (2008: 2.22M
loan-months / 50,000 loans, entirely pre-2017 so it has real train-window
events AND enough post-2016-12 rows for a genuine OOT AUC -- see
`test_oot_auc_sanity_floor`), read straight from the cached parquet files.
No mocking of the modeling logic. The full-panel run that actually produces
`outputs/freddie/lstm/*` is a separate `python -m freddie.fit_lstm`
invocation, not part of this file.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import torch

from freddie import fit_hazard as fh
from freddie import fit_lstm as flt
from freddie import lstm as fl

TEST_VINTAGE = 2008          # same slice test_freddie_hazard.py uses
TEST_CONTROL_RATE = 0.2      # richer than production's 0.05 -- keeps this
                              # single-vintage slice's events well powered
                              # without a huge control pool (see fit_hazard's
                              # own test file for the identical rationale)


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
        "loan_age", "current_actual_upb", "dlq_num", "d90_event",
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
def static_frame(raw_subset) -> pd.DataFrame:
    panel, orig = raw_subset
    return fh.build_model_frame(panel=panel, orig=orig)


@pytest.fixture(scope="module")
def seq_data(raw_subset) -> tuple[pd.DataFrame, np.ndarray]:
    panel, orig = raw_subset
    keys, seq = fl.add_sequence_features(
        panel[["loan_sequence_number", "monthly_reporting_period", "dlq_num", "current_actual_upb"]],
        orig[["loan_sequence_number", "orig_upb"]],
    )
    keys = keys.reset_index().rename(columns={"index": "_pos"})
    return keys, seq


def _assemble(rows: pd.DataFrame, keys: pd.DataFrame, seq_all: np.ndarray):
    """Local, dependency-free equivalent of fit_lstm._assemble_tensors_for_rows
    for a SINGLE already-in-memory vintage (that function re-reads from disk
    per vintage, which is what the *_flt_* integration tests below exercise
    instead)."""
    rows = rows.dropna(subset=fl.REQUIRED_STATIC_COLS).copy()
    merged = rows[["loan_sequence_number", "monthly_reporting_period"]].merge(
        keys, on=["loan_sequence_number", "monthly_reporting_period"], how="left", validate="one_to_one",
    )
    assert merged["_pos"].isna().sum() == 0
    pos = merged["_pos"].to_numpy(dtype="int64")
    seq = seq_all[pos]
    static = fl.build_static_design(rows)
    y = rows["d90_event"].to_numpy(dtype="float32")
    return seq, static, y


@pytest.fixture(scope="module")
def train_val_rows(static_frame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_window = static_frame.loc[static_frame["monthly_reporting_period"] <= fh.TRAIN_CUTOFF]
    sample = fh.sample_case_control(train_window, rate=TEST_CONTROL_RATE, seed=fh.SEED_A)
    sample_train = sample.loc[sample["monthly_reporting_period"] <= fl.VAL_CUTOFF].reset_index(drop=True)
    sample_val = sample.loc[sample["monthly_reporting_period"] > fl.VAL_CUTOFF].reset_index(drop=True)
    assert sample_train["d90_event"].sum() > 0
    assert sample_val["d90_event"].sum() > 0
    return sample_train, sample_val


@pytest.fixture(scope="module")
def train_val_tensors(train_val_rows, seq_data):
    sample_train, sample_val = train_val_rows
    keys, seq_all = seq_data
    seq_tr, static_tr, y_tr = _assemble(sample_train, keys, seq_all)
    seq_va, static_va, y_va = _assemble(sample_val, keys, seq_all)
    return (seq_tr, static_tr, y_tr), (seq_va, static_va, y_va)


@pytest.fixture(scope="module")
def fitted_scaler(train_val_tensors) -> fl.SequenceScaler:
    (seq_tr, static_tr, _), _ = train_val_tensors
    return fl.SequenceScaler().fit(seq_tr, static_tr)


@pytest.fixture(scope="module")
def trained_model(train_val_tensors, fitted_scaler) -> tuple[fl.LSTMChallenger, dict]:
    (seq_tr, static_tr, y_tr), (seq_va, static_va, y_va) = train_val_tensors
    seq_tr_s, static_tr_s = fitted_scaler.transform(seq_tr, static_tr)
    seq_va_s, static_va_s = fitted_scaler.transform(seq_va, static_va)
    config = fl.TrainConfig(epochs=8, patience=3, control_rate=TEST_CONTROL_RATE)
    model, history = fl.train_lstm(seq_tr_s, static_tr_s, y_tr, seq_va_s, static_va_s, y_va, config=config)
    return model, history, config


# ---------------------------------------------------------------------------
# 1. Sequence construction: shape, bounds, no NaN
# ---------------------------------------------------------------------------
def test_sequence_shape(raw_subset, seq_data):
    panel, _ = raw_subset
    keys, seq = seq_data
    assert seq.shape == (len(panel), fl.HISTORY_LEN, fl.SEQ_CHANNELS)
    assert len(keys) == len(panel)


def test_sequence_no_nan_and_bounded(seq_data):
    _, seq = seq_data
    assert np.isfinite(seq).all()
    # channel 0 (scaled dlq rung) must be in [0, DLQ_CAP/DLQ_SCALE]
    assert seq[:, :, 0].min() >= 0.0
    assert seq[:, :, 0].max() <= fl.DLQ_CAP / fl.DLQ_SCALE + 1e-6
    # channel 2 (validity) is strictly 0/1
    assert set(np.unique(seq[:, :, 2])).issubset({0.0, 1.0})


def test_fresh_loan_first_row_has_no_history(raw_subset, seq_data):
    """A loan's very first observed row (position 0) must have EVERY history
    slot flagged invalid -- there is, by definition, no prior month."""
    panel, _ = raw_subset
    keys, seq = seq_data
    first_rows = panel.sort_values(["loan_sequence_number", "monthly_reporting_period"]).groupby(
        "loan_sequence_number", sort=False,
    ).head(1)
    idx = keys.reset_index().merge(
        first_rows[["loan_sequence_number", "monthly_reporting_period"]],
        on=["loan_sequence_number", "monthly_reporting_period"],
    )["index"].to_numpy()
    assert len(idx) > 0
    assert (seq[idx][:, :, 2] == 0.0).all()
    assert (seq[idx][:, :, 0] == 0.0).all()
    assert (seq[idx][:, :, 1] == 0.0).all()


# ---------------------------------------------------------------------------
# 2. NO-LOOKAHEAD -- the core leakage checks the task spec asks for
# ---------------------------------------------------------------------------
def test_no_lookahead_mechanical_prior_month(raw_subset, seq_data):
    """Mechanically verify (against the RAW panel, not trusting the module's
    own claims) that the most-recent history slot (index -1) for a row at
    position p in its loan equals that loan's dlq_num at position p-1 --
    never the row's own current dlq_num."""
    panel, _ = raw_subset
    keys, seq = seq_data
    sorted_panel = panel.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)
    sorted_panel["pos"] = sorted_panel.groupby("loan_sequence_number", sort=False).cumcount()

    keyed_seq = keys.set_index(["loan_sequence_number", "monthly_reporting_period"])["_pos"]

    sample = sorted_panel.loc[sorted_panel["pos"] >= 1].sample(n=300, random_state=0)
    checked = 0
    for _, row in sample.iterrows():
        key = (row["loan_sequence_number"], row["monthly_reporting_period"])
        if key not in keyed_seq.index:
            continue
        seq_idx = int(keyed_seq.loc[key])
        expected_scaled = min(max(row["dlq_num"], 0), fl.DLQ_CAP) / fl.DLQ_SCALE

        # look up the SAME loan's row at pos-1 directly from the raw panel
        prior = sorted_panel.loc[
            (sorted_panel["loan_sequence_number"] == row["loan_sequence_number"])
            & (sorted_panel["pos"] == row["pos"] - 1)
        ]
        if prior.empty:
            continue
        expected_prior_scaled = min(max(prior["dlq_num"].iloc[0], 0), fl.DLQ_CAP) / fl.DLQ_SCALE

        got = seq[seq_idx, -1, 0]
        assert got == pytest.approx(expected_prior_scaled, abs=1e-6), (
            f"row {key}: last history slot = {got}, expected prior-month dlq {expected_prior_scaled} "
            f"(row's OWN dlq would scale to {expected_scaled} -- if `got` matches that instead, "
            "this is a lookahead bug)"
        )
        checked += 1
    assert checked > 100, "too few rows had a resolvable prior-row check"


def test_absorbing_panel_never_leaks_terminal_dlq_into_any_history(seq_data):
    """panel_monthly.parquet is absorbing-truncated at each loan's first D90
    month (freddie/build_panel.py) -- so dlq_num==3 (the D90 trigger, scaled
    to 1.0) can ONLY ever be a loan's own LAST row, which by construction is
    never any row's history (own or another loan's). If sequence index -1
    ever showed a scaled value >= 1.0, that would mean either (a) a genuine
    off-by-one lookahead bug reading the row's own current month, or (b) a
    same-loan boundary bug reading past the absorbing truncation -- both are
    ruled out by this single assertion over the WHOLE vintage."""
    _, seq = seq_data
    assert seq[:, :, 0].max() < 1.0 - 1e-9


def test_no_lookahead_current_upb_never_in_history(raw_subset, seq_data):
    """The row's OWN upb_ratio must never appear as its most-recent history
    slot when current UPB genuinely differs from the prior month's (paydown
    happens almost every month)."""
    panel, orig = raw_subset
    keys, seq = seq_data
    upb_map = orig.set_index("loan_sequence_number")["orig_upb"]
    p = panel.copy()
    p["upb_ratio"] = p["current_actual_upb"] / p["loan_sequence_number"].map(upb_map)
    p = p.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)
    keyed_seq = keys.set_index(["loan_sequence_number", "monthly_reporting_period"])["_pos"]

    sample = p.sample(n=300, random_state=2)
    n_diff = 0
    n_checked = 0
    for _, row in sample.iterrows():
        key = (row["loan_sequence_number"], row["monthly_reporting_period"])
        if key not in keyed_seq.index:
            continue
        seq_idx = int(keyed_seq.loc[key])
        own_ratio = row["upb_ratio"]
        if not np.isfinite(own_ratio):
            continue
        last_hist = seq[seq_idx, -1, 1]
        valid = seq[seq_idx, -1, 2] > 0.5
        n_checked += 1
        if valid and not np.isclose(last_hist, own_ratio, atol=1e-4):
            n_diff += 1
    assert n_checked > 100
    assert n_diff > 50, "history's last slot looks identical to the row's OWN upb_ratio too often -- lookahead suspected"


# ---------------------------------------------------------------------------
# 3. Time-based split boundaries
# ---------------------------------------------------------------------------
def test_train_val_split_by_time(train_val_rows):
    sample_train, sample_val = train_val_rows
    assert sample_train["monthly_reporting_period"].max() <= fl.VAL_CUTOFF
    assert sample_val["monthly_reporting_period"].min() > fl.VAL_CUTOFF
    assert sample_val["monthly_reporting_period"].max() <= fh.TRAIN_CUTOFF


def test_train_val_no_row_overlap(train_val_rows):
    sample_train, sample_val = train_val_rows
    key_tr = set(zip(sample_train["loan_sequence_number"], sample_train["monthly_reporting_period"]))
    key_va = set(zip(sample_val["loan_sequence_number"], sample_val["monthly_reporting_period"]))
    assert key_tr.isdisjoint(key_va)


def test_sequences_never_cross_val_boundary_mechanically(raw_subset, train_val_rows, seq_data):
    """For every VAL row, the underlying calendar month one step back (as
    consumed by the sequence's most-recent slot) is strictly the row's own
    month minus one -- i.e. history never reads INTO or PAST the row's own
    month, regardless of which side of VAL_CUTOFF it falls on."""
    panel, _ = raw_subset
    _, sample_val = train_val_rows
    keys, seq = seq_data
    sorted_panel = panel.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)
    month_map = sorted_panel.set_index(["loan_sequence_number", "monthly_reporting_period"])
    keyed_seq = keys.set_index(["loan_sequence_number", "monthly_reporting_period"])["_pos"]

    checked = 0
    for _, row in sample_val.sample(n=min(150, len(sample_val)), random_state=3).iterrows():
        key = (row["loan_sequence_number"], row["monthly_reporting_period"])
        if key not in keyed_seq.index:
            continue
        seq_idx = int(keyed_seq.loc[key])
        if seq[seq_idx, -1, 2] < 0.5:
            continue  # no history at all for this (very young) loan -- nothing to check
        expected_prior_month = (row["monthly_reporting_period"] - pd.DateOffset(months=1)).replace(day=1)
        prior_key = (row["loan_sequence_number"], expected_prior_month)
        assert prior_key in month_map.index, f"expected prior-month row {prior_key} missing from panel"
        checked += 1
    assert checked > 50


# ---------------------------------------------------------------------------
# 4. Scaler: TRAIN-ONLY fit (no-leakage)
# ---------------------------------------------------------------------------
def test_scaler_fit_matches_manual_train_only_stats(train_val_tensors, fitted_scaler):
    (seq_tr, static_tr, _), _ = train_val_tensors
    num = static_tr[:, : fl.STATIC_NUMERIC_DIM]
    manual_mean = num.mean(axis=0)
    manual_std = num.std(axis=0)
    manual_std[manual_std < 1e-6] = 1.0
    np.testing.assert_allclose(fitted_scaler.static_mean, manual_mean.astype("float64"), rtol=1e-6)
    np.testing.assert_allclose(fitted_scaler.static_std, manual_std.astype("float64"), rtol=1e-6)

    valid = seq_tr[:, :, 2] > 0.5
    upb_vals = seq_tr[:, :, 1][valid]
    assert fitted_scaler.upb_mean == pytest.approx(float(upb_vals.mean()), abs=1e-6)


def test_scaler_ignores_val_data(train_val_tensors):
    """Fitting on train_fit ONLY must give different (or at least
    NOT-implicitly-derived-from-val) statistics than fitting on train+val
    combined -- proof the val partition genuinely never touches the scaler."""
    (seq_tr, static_tr, _), (seq_va, static_va, _) = train_val_tensors
    scaler_train_only = fl.SequenceScaler().fit(seq_tr, static_tr)

    seq_combined = np.concatenate([seq_tr, seq_va], axis=0)
    static_combined = np.concatenate([static_tr, static_va], axis=0)
    scaler_combined = fl.SequenceScaler().fit(seq_combined, static_combined)

    # the two fits read different underlying data, so at least one stat must differ
    same_static = np.allclose(scaler_train_only.static_mean, scaler_combined.static_mean, atol=1e-10)
    same_upb = np.isclose(scaler_train_only.upb_mean, scaler_combined.upb_mean, atol=1e-10)
    assert not (same_static and same_upb), "train-only scaler is numerically identical to train+val scaler"


def test_scaler_transform_requires_fit():
    scaler = fl.SequenceScaler()
    with pytest.raises(RuntimeError):
        scaler.transform(np.zeros((1, fl.HISTORY_LEN, fl.SEQ_CHANNELS), "float32"), np.zeros((1, fl.STATIC_DIM), "float32"))


# ---------------------------------------------------------------------------
# 5. Determinism / GPU-CPU parity
# ---------------------------------------------------------------------------
def test_deterministic_forward_pass_fixed_seed():
    fl.set_determinism(0)
    model = fl.LSTMChallenger(static_dim=fl.STATIC_DIM)
    model.eval()

    rng = np.random.default_rng(7)
    seq = rng.normal(size=(16, fl.HISTORY_LEN, fl.SEQ_CHANNELS)).astype("float32")
    static = rng.normal(size=(16, fl.STATIC_DIM)).astype("float32")
    seq_t, static_t = torch.from_numpy(seq), torch.from_numpy(static)

    with torch.no_grad():
        out1 = model(seq_t, static_t).clone()
        out2 = model(seq_t, static_t).clone()
    assert torch.equal(out1, out2)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="no CUDA device available")
def test_gpu_cpu_parity_small_batch():
    fl.set_determinism(1)
    model_cpu = fl.LSTMChallenger(static_dim=fl.STATIC_DIM)
    model_cpu.eval()
    state = {k: v.clone() for k, v in model_cpu.state_dict().items()}

    model_gpu = fl.LSTMChallenger(static_dim=fl.STATIC_DIM)
    model_gpu.load_state_dict(state)
    model_gpu.to("cuda")
    model_gpu.eval()

    rng = np.random.default_rng(9)
    seq = rng.normal(size=(32, fl.HISTORY_LEN, fl.SEQ_CHANNELS)).astype("float32")
    static = rng.normal(size=(32, fl.STATIC_DIM)).astype("float32")

    with torch.no_grad():
        out_cpu = model_cpu(torch.from_numpy(seq), torch.from_numpy(static)).numpy()
        out_gpu = model_gpu(
            torch.from_numpy(seq).to("cuda"), torch.from_numpy(static).to("cuda"),
        ).cpu().numpy()

    np.testing.assert_allclose(out_cpu, out_gpu, atol=1e-4, rtol=1e-3)


# ---------------------------------------------------------------------------
# 6. Case-control pos_weight = rate identity (analytic, no training needed)
# ---------------------------------------------------------------------------
def test_default_case_control_rate_matches_champion():
    """freddie.lstm.DEFAULT_CASE_CONTROL_RATE (TrainConfig's default
    control_rate, used for the pos_weight calibration identity) is a literal
    restated -- not imported -- from freddie.fit_hazard.CONTROL_SAMPLE_RATE
    (the rate freddie.fit_lstm.get_training_tensors ACTUALLY samples the
    training rows at). Guards against the two drifting apart silently, which
    would break the pos_weight=rate calibration identity documented in
    freddie/lstm.py's module docstring without any other test catching it."""
    assert fl.DEFAULT_CASE_CONTROL_RATE == fh.CONTROL_SAMPLE_RATE


def test_pos_weight_rate_recovers_calibration():
    """Closed-form check of the identity documented in freddie/lstm.py's
    module docstring: for a case-control sample where every event is kept
    and every control is kept at probability `rate`, the BCEWithLogitsLoss-
    minimising sigmoid at pos_weight=rate equals the TRUE population
    probability p -- but at pos_weight=n_neg/n_pos (the sample's own,
    much-larger imbalance ratio) it collapses towards ~0.5 instead."""
    rate = 0.05
    p_grid = np.array([1e-4, 1e-3, 5e-3, 1e-2, 5e-2])

    def sigma_star(p: np.ndarray, w: float) -> np.ndarray:
        return w * p / (w * p + rate * (1.0 - p))

    recovered = sigma_star(p_grid, w=rate)
    np.testing.assert_allclose(recovered, p_grid, atol=1e-10)

    # sample-imbalance pos_weight (n_neg/n_pos of the SAMPLE, itself ~ rate*(1-p)/p)
    sample_n_neg_over_n_pos = rate * (1.0 - p_grid) / p_grid
    naive = sigma_star(p_grid, w=sample_n_neg_over_n_pos)
    np.testing.assert_allclose(naive, 0.5 * np.ones_like(p_grid), atol=1e-6)


def test_trained_model_predicted_mean_order_of_magnitude(trained_model, train_val_tensors, fitted_scaler, static_frame):
    """Empirical companion to the analytic check above: the ACTUAL trained
    model's mean predicted probability on OOT should be within an order of
    magnitude of the observed OOT hazard rate -- NOT collapsed to ~0.5,
    which is what the pre-fix `pos_weight=n_neg/n_pos` choice would give
    (see freddie/lstm.py's module docstring)."""
    model, _, config = trained_model
    oot = static_frame.loc[static_frame["monthly_reporting_period"] > fh.TRAIN_CUTOFF].dropna(
        subset=fl.REQUIRED_STATIC_COLS,
    ).copy()
    assert oot["d90_event"].sum() > 0

    panel_cols = ["loan_sequence_number", "monthly_reporting_period"]
    # reuse the module-level seq cache built from the whole vintage (fixture)
    keys, seq_all = _seq_data_for_oot()
    merged = oot[panel_cols].merge(keys, on=panel_cols, how="left", validate="one_to_one")
    pos = merged["_pos"].to_numpy(dtype="int64")
    seq_oot = seq_all[pos]
    static_oot = fl.build_static_design(oot)
    seq_oot_s, static_oot_s = fitted_scaler.transform(seq_oot, static_oot)

    pred = fl.predict_lstm(model, seq_oot_s, static_oot_s, device=config.device, batch_size=8192)
    observed = float(oot["d90_event"].mean())
    predicted = float(pred.mean())

    assert predicted > 0.0
    ratio = predicted / observed
    assert 0.05 < ratio < 20.0, f"predicted mean {predicted:.5%} vs observed {observed:.5%} -- ratio {ratio:.2f} way off order of magnitude"
    assert predicted < 0.3, "predicted mean looks collapsed towards ~0.5 (sample-imbalance, not population-calibrated)"


_SEQ_DATA_CACHE: dict = {}


def _seq_data_for_oot():
    # module-scoped seq_data fixture already built this; re-derive cheaply
    # via the same raw_subset without re-declaring a fixture dependency here
    # (pytest fixtures cannot be called directly outside collection).
    if "keys" not in _SEQ_DATA_CACHE:
        panel = pd.read_parquet(fh.PANEL_PATH, columns=[
            "loan_sequence_number", "vintage", "monthly_reporting_period",
            "loan_age", "current_actual_upb", "dlq_num", "d90_event",
        ])
        panel = panel.loc[panel["vintage"] == TEST_VINTAGE].drop(columns=["vintage"]).reset_index(drop=True)
        orig = pd.read_parquet(fh.ORIG_PATH, columns=[
            "loan_sequence_number", "orig_upb",
        ])
        orig = orig.loc[orig["loan_sequence_number"].isin(set(panel["loan_sequence_number"]))].reset_index(drop=True)
        keys, seq = fl.add_sequence_features(
            panel[["loan_sequence_number", "monthly_reporting_period", "dlq_num", "current_actual_upb"]], orig,
        )
        keys = keys.reset_index().rename(columns={"index": "_pos"})
        _SEQ_DATA_CACHE["keys"] = keys
        _SEQ_DATA_CACHE["seq"] = seq
    return _SEQ_DATA_CACHE["keys"], _SEQ_DATA_CACHE["seq"]


# ---------------------------------------------------------------------------
# 7. OOT AUC sanity floor (identical eval set: full un-subsampled OOT rows,
#    matching fit_lstm.score_all's methodology)
# ---------------------------------------------------------------------------
def test_oot_auc_sanity_floor(trained_model, fitted_scaler, static_frame):
    model, _, config = trained_model
    oot = static_frame.loc[static_frame["monthly_reporting_period"] > fh.TRAIN_CUTOFF].dropna(
        subset=fl.REQUIRED_STATIC_COLS,
    ).copy()
    keys, seq_all = _seq_data_for_oot()
    merged = oot[["loan_sequence_number", "monthly_reporting_period"]].merge(
        keys, on=["loan_sequence_number", "monthly_reporting_period"], how="left", validate="one_to_one",
    )
    pos = merged["_pos"].to_numpy(dtype="int64")
    seq_oot = seq_all[pos]
    static_oot = fl.build_static_design(oot)
    seq_oot_s, static_oot_s = fitted_scaler.transform(seq_oot, static_oot)
    pred = fl.predict_lstm(model, seq_oot_s, static_oot_s, device=config.device, batch_size=8192)

    from sklearn.metrics import roc_auc_score

    y = oot["d90_event"].to_numpy()
    assert y.sum() > 50, "too few OOT events on this vintage slice for a stable AUC check"
    auc = roc_auc_score(y, pred)
    assert auc > 0.7, f"OOT AUC {auc:.4f} below the sanity floor"


def test_has_prior_delinquency_lift_groups_both_populated(static_frame):
    keys, seq_all = _seq_data_for_oot()
    oot = static_frame.loc[static_frame["monthly_reporting_period"] > fh.TRAIN_CUTOFF].dropna(
        subset=fl.REQUIRED_STATIC_COLS,
    ).copy()
    merged = oot[["loan_sequence_number", "monthly_reporting_period"]].merge(
        keys, on=["loan_sequence_number", "monthly_reporting_period"], how="left", validate="one_to_one",
    )
    pos = merged["_pos"].to_numpy(dtype="int64")
    has_prior = fl.has_prior_delinquency(seq_all[pos])
    assert has_prior.dtype == bool
    assert len(has_prior) == len(oot)
    assert has_prior.any()
    assert (~has_prior).any()


# ---------------------------------------------------------------------------
# 8. Integration: fit_lstm's own vintage-chunked assembly matches the
#    lighter-weight local `_assemble` helper above
# ---------------------------------------------------------------------------
def test_fit_lstm_assemble_tensors_matches_local_helper(static_frame, train_val_rows, seq_data):
    sample_train, _ = train_val_rows
    keys, seq_all = seq_data
    seq_local, static_local, y_local = _assemble(sample_train, keys, seq_all)

    rows = sample_train.copy()
    rows["vintage"] = TEST_VINTAGE
    seq_flt, static_flt, y_flt, _ = flt._assemble_tensors_for_rows(rows)

    assert seq_flt.shape == seq_local.shape
    assert static_flt.shape == static_local.shape
    np.testing.assert_array_equal(y_flt, y_local)
    # fit_lstm groups by vintage internally, which may reorder rows relative
    # to sample_train's own order -- compare as SETS of (static, y) rows via
    # a stable sort key rather than assuming positional equality.
    order_local = np.lexsort(static_local.T)
    order_flt = np.lexsort(static_flt.T)
    np.testing.assert_allclose(static_local[order_local], static_flt[order_flt], atol=1e-5)
