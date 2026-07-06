"""Tests for data/ingest/dfast.py + engine/scenarios.py (plan section 2.6).

Contract, not point values:
* DFAST ingestion: '2026 Q1' date parsing, 13-quarter supervisory paths
  contiguous with the historic actuals, no NaNs in derived concepts, and the
  SAAR -> quarterly conversion identity;
* scenario paths finite over the full 40q extended horizon, correct calendar
  anchoring from the t=60 jump-off (2015Q1);
* the DFAST severely-adverse convention: severe UER peak minus jump-off in
  [3, 7]pp (2026 vintage: 10.0 - 4.5 = +5.5pp, preserved exactly by the
  additive-delta rebasing);
* the base path stays inside the [3, 7]pp UER band on all 40 quarters;
* quarterly hpi_growth magnitudes sane (< 8%/q) in every scenario;
* weights sum to 1 (and bad weights are rejected);
* the upside damped-mirror convention and the reversion-to-long-run tail.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data.ingest.dfast import CONCEPTS, load_dfast, saar_to_quarterly
from engine.scenarios import ScenarioSet, build_scenario_set

HORIZON = 40


@pytest.fixture(scope="module")
def dfast():
    return load_dfast()


@pytest.fixture(scope="module")
def sset() -> ScenarioSet:
    return build_scenario_set(horizon=HORIZON)


# ---------------------------------------------------------------- ingestion --

def test_dfast_paths_parse_and_align(dfast):
    assert dfast.historic.index[0] == pd.Period("1976Q1", freq="Q")
    assert dfast.historic.index[-1] == pd.Period("2025Q4", freq="Q")
    for path in (dfast.baseline, dfast.severely_adverse):
        assert len(path) == 13
        assert path.index[0] == pd.Period("2026Q1", freq="Q")
        assert path.index[-1] == pd.Period("2029Q1", freq="Q")
        # no NaNs anywhere in the supervisory concepts (first-quarter
        # hpi_growth is bridged from the last historic level)
        assert not path[list(CONCEPTS)].isna().any().any()
    # historic concepts: only the very first hpi_growth (1976Q1) may be NaN
    hist = dfast.historic[list(CONCEPTS)]
    assert hist.iloc[1:].notna().all().all()
    assert not dfast.jumpoff.isna().any()


def test_saar_to_quarterly_identity():
    # compounding a quarterly rate four times recovers the SAAR rate
    q = saar_to_quarterly(4.0)
    assert q == pytest.approx(100.0 * (1.04 ** 0.25 - 1.0))
    assert 100.0 * ((1.0 + q / 100.0) ** 4 - 1.0) == pytest.approx(4.0)
    # sign preserved for contractions
    assert saar_to_quarterly(-5.4) < 0


# ---------------------------------------------------------- scenario shapes --

def test_paths_finite_over_full_horizon(sset):
    assert set(sset.paths) == {"base", "down", "up"}
    for name, df in sset.paths.items():
        assert len(df) == HORIZON, name
        vals = df[list(CONCEPTS)].to_numpy(dtype=float)
        assert np.isfinite(vals).all(), f"{name}: non-finite path values"


def test_calendar_anchoring(sset):
    # t=60 jump-off ~ 2015Q1; path h=1 is the next calendar quarter
    assert str(sset.jumpoff_period) == "2015Q1"
    for df in sset.paths.values():
        assert str(df["period"].iloc[0]) == "2015Q2"
        assert str(df["period"].iloc[-1]) == "2025Q1"
        # contiguous quarters
        per = pd.PeriodIndex(df["period"], freq="Q")
        assert (per == pd.period_range(per[0], periods=HORIZON, freq="Q")).all()


def test_severe_uer_peak_minus_jumpoff_in_dfast_band(sset):
    # DFAST severely-adverse convention: UER rises several pp above jump-off
    peak_delta = sset.paths["down"]["uer"].max() - sset.jumpoff["uer"]
    assert 3.0 <= peak_delta <= 7.0


def test_base_uer_stays_in_band(sset):
    uer = sset.paths["base"]["uer"]
    assert (uer >= 3.0).all() and (uer <= 7.0).all()


def test_hpi_growth_quarterly_magnitude_sane(sset):
    for name, df in sset.paths.items():
        assert df["hpi_growth"].abs().max() < 0.08, name


def test_weights_sum_to_one(sset):
    assert sum(sset.weights.values()) == pytest.approx(1.0)
    assert sset.weights == {"base": 0.50, "down": 0.25, "up": 0.25}


def test_bad_weights_rejected(sset):
    with pytest.raises(ValueError, match="sum to 1"):
        ScenarioSet(paths=sset.paths,
                    weights={"base": 0.6, "down": 0.25, "up": 0.25},
                    jumpoff=sset.jumpoff, longrun=sset.longrun,
                    horizon=sset.horizon, rs_window=sset.rs_window,
                    reversion=sset.reversion, jumpoff_time=sset.jumpoff_time)
    with pytest.raises(ValueError, match="mismatch"):
        ScenarioSet(paths=sset.paths, weights={"base": 1.0},
                    jumpoff=sset.jumpoff, longrun=sset.longrun,
                    horizon=sset.horizon, rs_window=sset.rs_window,
                    reversion=sset.reversion, jumpoff_time=sset.jumpoff_time)


# ------------------------------------------------------------- conventions --

def test_rebasing_is_delta_from_jumpoff(sset, dfast):
    # additive rebasing preserves DFAST deltas exactly inside the R&S window
    rs = sset.rs_window
    dfast_delta = (dfast.severely_adverse["uer"].to_numpy()
                   - dfast.jumpoff["uer"])
    path_delta = (sset.paths["down"]["uer"].iloc[:rs].to_numpy()
                  - sset.jumpoff["uer"])
    assert np.allclose(path_delta, dfast_delta)


def test_upside_is_damped_mirror(sset, dfast):
    rs = sset.rs_window
    sev_delta = (dfast.severely_adverse[list(CONCEPTS)].to_numpy()
                 - dfast.jumpoff[list(CONCEPTS)].to_numpy(dtype=float))
    expected = sset.jumpoff.to_numpy() + (-0.35) * sev_delta
    got = sset.paths["up"][list(CONCEPTS)].iloc[:rs].to_numpy()
    # uer may additionally be floored at 3.5pp
    expected[:, 0] = np.clip(expected[:, 0], 3.5, None)
    assert np.allclose(got, expected)
    # economics: mild boom — upside UER below jump-off, HPI appreciating,
    # while the severe path deteriorates
    assert (sset.paths["up"]["uer"].iloc[:rs] < sset.jumpoff["uer"]).all()
    assert (sset.paths["up"]["uer"] >= 3.5).all()
    assert (sset.paths["up"]["hpi_growth"].iloc[:rs] > 0).all()
    assert (sset.paths["down"]["uer"].iloc[:rs] > sset.jumpoff["uer"]).all()


def test_reversion_to_longrun_tail(sset):
    # linear ramp ends at rs_window + reversion; tail holds long-run means
    tail_start = sset.rs_window + sset.reversion  # h = 21
    for name, df in sset.paths.items():
        tail = df[list(CONCEPTS)].loc[tail_start:]
        assert np.allclose(tail.to_numpy(),
                           np.tile(sset.longrun.to_numpy(), (len(tail), 1))), name
        # midpoint of the ramp sits strictly between path end and long-run
        # for a concept where they differ materially (severe uer: 9.2 -> 6.39)
    d = sset.paths["down"]["uer"]
    v13, mid, lr = d.loc[sset.rs_window], d.loc[sset.rs_window + 4], sset.longrun["uer"]
    assert min(v13, lr) < mid < max(v13, lr)


def test_weighted_path_is_convex_combination(sset):
    w = sset.weights
    manual = sum(w[n] * sset.paths[n][list(CONCEPTS)] for n in sset.paths)
    got = sset.weighted_path()
    assert np.allclose(got[list(CONCEPTS)].to_numpy(), manual.to_numpy())
    # weighted UER sits between the up and down envelopes everywhere
    lo = np.minimum.reduce([sset.paths[n]["uer"].to_numpy() for n in sset.paths])
    hi = np.maximum.reduce([sset.paths[n]["uer"].to_numpy() for n in sset.paths])
    assert ((got["uer"].to_numpy() >= lo - 1e-12)
            & (got["uer"].to_numpy() <= hi + 1e-12)).all()
