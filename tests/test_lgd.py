"""API-contract tests for engine/lgd.py (two-stage workout LGD).

Fits on the real panel (train split, resolved defaults -- ~9.5k rows, fast)
and checks the contract, not point values: economic signs, range guarantees,
the decomposition identity, and the fit-sample discipline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.lgd import (
    CURE_THRESHOLD,
    LGD_REQUIRED_COLS,
    fit_lgd_models,
    predict_components,
    predict_lgd,
)

PANEL = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel.parquet"


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL)


@pytest.fixture(scope="module")
def models(panel):
    return fit_lgd_models(panel)


def test_fit_sample_discipline(panel, models):
    """Train split only, resolved defaults only, counts add up."""
    tr_def = panel[(panel["split"] == "train") & (panel["default_event"] == 1)]
    assert models.n_defaults == len(tr_def)
    assert models.n_resolved <= tr_def["res_time"].notna().sum()
    assert models.n_cures + models.n_noncure == models.n_resolved


def test_economic_signs(models):
    """Collateral channel: cure falls, severity rises in updated LTV."""
    assert models.cure_params["ltv10"] < 0
    assert models.severity_params["ltv10"] > 0


def test_excess_loading_positive_and_sane(models):
    """Beyond-EAD mass is real (12.5% of resolved train LGDs exceed 1,
    14.2% of non-cures) and never clipped away."""
    assert 0.0 < models.excess_loading < 0.10
    assert models.lgd_upper_bound == models.sev_cap + models.excess_loading


def test_predict_range_and_identity(panel, models):
    """LGD in [0, cap+loading]; lgd == (1-p_cure) * severity_adj exactly."""
    sample = panel.dropna(subset=LGD_REQUIRED_COLS).head(5000)
    comp = predict_components(models, sample)
    assert np.isfinite(comp.to_numpy()).all()
    assert (comp["lgd"] >= 0).all()
    assert (comp["lgd"] <= models.lgd_upper_bound + 1e-12).all()
    assert (comp["p_cure"].between(0, 1)).all()
    assert (comp["severity_capped"].between(0, 1)).all()
    np.testing.assert_allclose(
        comp["lgd"], (1 - comp["p_cure"]) * comp["severity_adj"], rtol=1e-12)
    np.testing.assert_allclose(predict_lgd(models, sample), comp["lgd"])


def test_predict_raises_on_nan_covariates(panel, models):
    sample = panel.dropna(subset=LGD_REQUIRED_COLS).head(10).copy()
    sample.loc[sample.index[0], "updated_ltv"] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        predict_lgd(models, sample)


def test_predict_raises_on_missing_columns(models):
    with pytest.raises(KeyError, match="missing required columns"):
        predict_lgd(models, pd.DataFrame({"updated_ltv": [80.0]}))


def test_train_calibration_exact_on_cure_margin(panel, models):
    """Logit with intercept reproduces the train cure rate to ~1e-6."""
    d = panel[(panel["split"] == "train") & (panel["default_event"] == 1)]
    d = d[d["res_time"].notna()].dropna(subset=LGD_REQUIRED_COLS + ["lgd_time"])
    comp = predict_components(models, d)
    emp = (d["lgd_time"] <= CURE_THRESHOLD).mean()
    assert abs(comp["p_cure"].mean() - emp) < 1e-6


def test_threshold_sensitivity_refits(panel):
    """Refitting at 0.0 / 0.10 keeps signs and moves cure rate monotonically."""
    m0 = fit_lgd_models(panel, cure_threshold=0.0)
    m10 = fit_lgd_models(panel, cure_threshold=0.10)
    assert m0.n_cures < m10.n_cures
    for m in (m0, m10):
        assert m.cure_params["ltv10"] < 0
        assert m.severity_params["ltv10"] > 0
