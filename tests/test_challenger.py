"""Contract tests for challenger/mlp.py (the MLP hazard challenger).

The challenger never feeds production numbers, but it must still be a sane,
leak-free, reproducible model:

* OOT AUC above a degeneracy floor (0.60) -- catches a silently collapsed
  model (all-one-class, dead ReLUs, scrambled standardisation);
* no NaN / out-of-[0,1] predictions, and NaN INPUT rows raise rather than
  silently misalign;
* the standardiser is fitted on TRAIN ONLY (asserted two ways: recorded
  provenance + recomputed moments), and predicting cannot mutate it;
* fit refuses non-train rows outright (split-enforcement contract);
* prior correction undoes the pos_weight calibration bias (mean predicted
  hazard on the training scale, not ~pos_weight x too high);
* the level-off age clamp holds beyond the training age support;
* same seed + same device => identical predictions (CPU determinism);
* cum_default_pd_mlp obeys lifetime-PD algebra (bounded, monotone in the
  horizon), mirroring the frozen engine's conventions.

Model fits here use a fixed-seed loan subsample and few epochs -- enough to
clear the degeneracy floor, small enough to keep the suite fast. The full
challenger is fitted by analysis/fit_challenger.py.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from challenger.mlp import (
    CONT_FEATURES,
    FEATURES,
    Standardiser,
    build_features,
    cum_default_pd_mlp,
    fit_mlp_hazard,
    predict_mlp_hazard,
)
from engine.hazard import fit_prepay_hazard

PANEL = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel.parquet"

SEED = 0
AUC_FLOOR = 0.60
SUB_FRAC = 0.5          # fraction of TRAIN loans used for the test fit


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL)


@pytest.fixture(scope="module")
def train_sub(panel) -> pd.DataFrame:
    train = panel[panel["split"] == "train"]
    rng = np.random.default_rng(SEED)
    ids = train["id"].unique()
    pick = rng.choice(ids, size=int(len(ids) * SUB_FRAC), replace=False)
    return train[train["id"].isin(set(pick))]


@pytest.fixture(scope="module")
def oot(panel) -> pd.DataFrame:
    return panel[panel["split"] == "oot"]


@pytest.fixture(scope="module")
def model(train_sub):
    """Reduced-budget challenger: subsampled loans, capped epochs, no
    full-train refit -- fast, but must still clear the degeneracy floor."""
    return fit_mlp_hazard(train_sub, max_epochs=25, patience=5,
                          refit_full=False, seed=SEED)


# ---------------------------------------------------------------------------
# discrimination floor / prediction hygiene
# ---------------------------------------------------------------------------

def test_oot_auc_above_degeneracy_floor(model, oot):
    from sklearn.metrics import roc_auc_score

    p = predict_mlp_hazard(model, oot)
    auc = roc_auc_score(oot["default_event"].to_numpy(), p)
    assert auc > AUC_FLOOR, f"challenger OOT AUC {auc:.4f} <= {AUC_FLOOR}"


def test_predictions_finite_and_in_unit_interval(model, oot):
    p = predict_mlp_hazard(model, oot)
    assert len(p) == len(oot)
    assert np.isfinite(p).all()
    assert (p > 0).all() and (p < 1).all()


def test_nan_input_rows_raise(model, oot):
    bad = oot.head(50).copy()
    bad.loc[bad.index[3], "updated_ltv"] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        predict_mlp_hazard(model, bad)


def test_prior_correction_keeps_hazard_scale(model, train_sub):
    """pos_weight ~ 36x would inflate uncorrected outputs by ~an order of
    magnitude; corrected mean must sit near the training event rate."""
    fit_rows = train_sub[train_sub["lag_warmup"] == 0]
    p = predict_mlp_hazard(model, fit_rows)
    rate = fit_rows["default_event"].mean()
    assert rate / 3 < p.mean() < rate * 3, (
        f"mean predicted hazard {p.mean():.4f} vs event rate {rate:.4f} -- "
        "prior correction broken?")


# ---------------------------------------------------------------------------
# standardiser: train-only, immutable
# ---------------------------------------------------------------------------

def test_standardiser_fitted_on_train_only(model, train_sub):
    # provenance: every row the scaler saw lies inside the training window
    assert model.meta["scaler_time_range"][1] <= 40
    assert model.scaler.time_range[1] <= 40
    # moments: exactly the train-subsample fit rows' moments, recomputed
    fit_rows = train_sub[train_sub["lag_warmup"] == 0]
    feats = build_features(fit_rows)[CONT_FEATURES].to_numpy(dtype=float)
    assert np.allclose(model.scaler.mean, feats.mean(axis=0))
    assert np.allclose(model.scaler.std, feats.std(axis=0, ddof=0))
    assert model.scaler.n_rows == len(fit_rows)


def test_predicting_does_not_mutate_scaler(model, oot):
    mean0 = model.scaler.mean.copy()
    std0 = model.scaler.std.copy()
    predict_mlp_hazard(model, oot.head(5000))
    assert np.array_equal(model.scaler.mean, mean0)
    assert np.array_equal(model.scaler.std, std0)
    # frozen dataclass: refitting in place is impossible by construction
    with pytest.raises(Exception):
        model.scaler.mean = mean0 * 2


def test_fit_refuses_non_train_rows(panel):
    with pytest.raises(ValueError, match="TRAINING split only"):
        fit_mlp_hazard(panel.head(50_000), max_epochs=1)


def test_standardiser_rejects_constant_feature(train_sub):
    fit_rows = train_sub[train_sub["lag_warmup"] == 0].head(1000)
    feats = build_features(fit_rows).copy()
    feats["gdp_lag1"] = 1.23
    with pytest.raises(ValueError, match="degenerate"):
        Standardiser.fit(feats, fit_rows["time"].to_numpy())


# ---------------------------------------------------------------------------
# tail clamp + determinism
# ---------------------------------------------------------------------------

def test_age_clamp_levels_off_beyond_training_support(model, oot):
    base = oot.head(200).copy()
    at_max = base.copy()
    at_max["loan_age"] = model.age_max
    beyond = base.copy()
    beyond["loan_age"] = model.age_max + 120.0
    assert np.allclose(predict_mlp_hazard(model, at_max),
                       predict_mlp_hazard(model, beyond))


def test_same_seed_same_device_is_deterministic(train_sub, oot):
    """CPU fits with identical seeds must agree bitwise-close. (Documented
    residual nondeterminism is ACROSS devices/builds, not within.)"""
    rng = np.random.default_rng(1)
    ids = train_sub["id"].unique()
    tiny = train_sub[train_sub["id"].isin(
        set(rng.choice(ids, size=len(ids) // 5, replace=False)))]
    kw = dict(max_epochs=3, patience=3, refit_full=False, seed=7,
              device="cpu")
    m1 = fit_mlp_hazard(tiny, **kw)
    m2 = fit_mlp_hazard(tiny, **kw)
    p1 = predict_mlp_hazard(m1, oot.head(20_000))
    p2 = predict_mlp_hazard(m2, oot.head(20_000))
    assert np.allclose(p1, p2, rtol=0, atol=1e-9)


# ---------------------------------------------------------------------------
# challenger lifetime PD (staging-swap machinery)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def prepay(train_sub):
    return fit_prepay_hazard(train_sub)


def test_cum_default_pd_bounded_and_monotone_in_horizon(model, prepay,
                                                        train_sub):
    snap = (train_sub[train_sub["time"] == 40]
            .sort_values("id").head(80).reset_index(drop=True))
    r4 = np.full(len(snap), 4)
    r12 = np.full(len(snap), 12)
    pd4 = cum_default_pd_mlp(model, prepay, snap, r4)
    pd12 = cum_default_pd_mlp(model, prepay, snap, r12)
    for v in (pd4, pd12):
        assert np.isfinite(v).all()
        assert (v >= 0).all() and (v < 1).all()
    assert (pd12 >= pd4 - 1e-12).all(), (
        "cumulative PD must be non-decreasing in the horizon")
    assert (pd4 > 0).all()


def test_cum_default_pd_rejects_bad_horizons(model, prepay, train_sub):
    snap = (train_sub[train_sub["time"] == 40]
            .sort_values("id").head(10).reset_index(drop=True))
    with pytest.raises(ValueError, match=">= 1"):
        cum_default_pd_mlp(model, prepay, snap, np.zeros(len(snap), int))
    with pytest.raises(ValueError, match="align"):
        cum_default_pd_mlp(model, prepay, snap, np.full(len(snap) + 3, 4))
