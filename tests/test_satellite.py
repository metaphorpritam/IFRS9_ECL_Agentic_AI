"""Tests for engine/satellite.py -- satellite model + scenario-conditional ECL.

Contracts, per the Day-3 build plan:
  1. ANCHOR SANITY: the per-quarter PIT round trip pit_pd(anchor_t, Z_t,
     rho) == observed_t is exact on the recovered path, and the Gauss-
     Hermite expectation over Z ~ N(0,1) of the flat-anchor PIT PD equals
     the TTC anchor (< 1e-6); the SAMPLE mean over the recovered Z_ts is
     reported (it sits above the anchor because mean(Z) != 0 -- the
     documented level gap) and is asserted close to the observed mean rate.
  2. SATELLITE HYGIENE: driver lag construction is exact; stationarity
     verdicts behave on synthetic I(1)/I(0) series; the fitted satellite
     passes the economic-sign governance and predicts FINITE Z on all
     three scenario paths (+ the weighted path, which must equal the
     weighted combination of scenario Z paths -- linearity).
  3. CONDITIONING: pit_pd is applied to hazard LEVELS with the correct
     orientation (Z < 0 inflates hazards), off-window cells stay exactly
     0, and short Z paths extend by their final value.
  4. COMPOSITION CORRECTNESS: with no conditioning the wrapper reproduces
     the FROZEN engine.ecl.ecl_for_snapshot exactly (never edited, only
     composed).
  5. ECONOMICS: ECL ordering severe > base > upside on the reported
     allowance and the 12m ECL (severe > base on lifetime; the upside/base
     lifetime crossover is a documented mirror-payback + survivor-exposure
     feature, see outputs/scenario_ecl/scenario_ecl_report.md), and the
     JENSEN INEQUALITY: probability-weighted ECL > ECL at the probability-
     weighted (average) macro path, on both measures.

The module-scoped fixtures fit the frozen engines once on the real panel
(same calls as analysis/run_scenarios.py), so this file is slower than the
pure-unit suites -- deliberately: the contracts above are portfolio-level.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine import satellite as sat
from engine.ecl import EclConfig, ecl_for_snapshot
from engine.hazard import fit_default_hazard, fit_prepay_hazard
from engine.lgd import fit_lgd_models
from engine.scenarios import build_scenario_set, panel_macro_concepts
from engine.staging import assign_stages, build_macro_map
from engine.vasicek import pit_pd

PANEL_PATH = (Path(__file__).resolve().parents[1]
              / "data" / "processed" / "panel.parquet")
T_SNAP = 60
LIVE_LOANS = 7_806
STAGE3_LOANS = 43


# ---------------------------------------------------------------------------
# heavy shared fixtures (one fit chain for the whole module)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL_PATH)


@pytest.fixture(scope="module")
def models(panel):
    train = panel[panel["split"] == "train"]
    return {"default": fit_default_hazard(train),
            "prepay": fit_prepay_hazard(train),
            "lgd": fit_lgd_models(panel)}


@pytest.fixture(scope="module")
def zrec(panel, models):
    """(BelkinResult, observed-vs-TTC table) on the full 60-quarter panel."""
    return sat.recover_z(panel, models["default"])


@pytest.fixture(scope="module")
def concepts(panel):
    return panel_macro_concepts(build_macro_map(panel))


@pytest.fixture(scope="module")
def satm(zrec, concepts):
    res, tab = zrec
    drivers = sat.driver_frame(concepts)
    return sat.fit_satellite(pd.Series(res.z, index=tab.index), drivers)


@pytest.fixture(scope="module")
def sset():
    return build_scenario_set()


@pytest.fixture(scope="module")
def zpaths(satm, sset, concepts):
    return sat.scenario_z_paths(satm, sset, concepts)


@pytest.fixture(scope="module")
def books(panel, models, zrec, zpaths, sset):
    """Frozen-engine book + unconditioned wrapper + 4 conditioned books."""
    res, _ = zrec
    cfg = EclConfig()
    hz = {"default": models["default"], "prepay": models["prepay"]}
    staged = assign_stages(panel.loc[panel["time"] <= T_SNAP], hz,
                           cfg.staging, snapshot_time=T_SNAP)
    mm = sat.ttc_macro_means(panel)
    out = {
        "frozen": ecl_for_snapshot(panel, T_SNAP, models, cfg),
        "unconditioned": sat.scenario_ecl_for_snapshot(
            panel, T_SNAP, models, staged=staged, config=cfg),
    }
    for name in ("up", "base", "down", "weighted"):
        out[name] = sat.scenario_ecl_for_snapshot(
            panel, T_SNAP, models, z_path=zpaths[name].to_numpy(),
            rho=res.rho, macro_means=mm, staged=staged, config=cfg)
    return out


# ---------------------------------------------------------------------------
# 1. anchor sanity on the recovered Z path
# ---------------------------------------------------------------------------

def test_anchor_sanity_roundtrip_and_expectation(zrec):
    res, tab = zrec
    s = sat.anchor_sanity(tab, res)
    # exact inversion identity per quarter (fixed-conventions round trip)
    assert s["roundtrip_max_err"] < 1e-9
    # law of total probability under Z ~ N(0,1) at the flat anchor
    assert s["gh_anchor_err"] < 1e-6
    # the SAMPLE mean over recovered Z_ts approximates the observed mean
    # rate (and sits ABOVE the flat TTC anchor: mean(Z) < 0, the documented
    # level gap -- reported, not hidden)
    assert s["sample_mean_pit"] == pytest.approx(s["mean_observed"],
                                                 rel=0.30)
    assert s["sample_mean_pit"] > s["flat_ttc"]
    assert res.mean_z < 0.0


def test_recovery_matches_published_calibration(zrec):
    """rho and the Z trough must match the Day-3 vasicek rung's results."""
    res, tab = zrec
    assert res.rho == pytest.approx(0.0227, abs=5e-4)
    assert abs(float(np.var(res.z, ddof=1)) - 1.0) < 1e-6
    # trough inside the GFC window (t=31..37 ~ 2007Q4..2009Q2 +- recovery)
    t_trough = int(tab.index[np.argmin(res.z)])
    assert 30 <= t_trough <= 40


# ---------------------------------------------------------------------------
# 2. satellite hygiene
# ---------------------------------------------------------------------------

def test_driver_frame_lag_construction():
    concepts = pd.DataFrame({
        "uer": [5.0, 5.5, 6.5, 6.0, 5.0],
        "hpi_growth": [0.01, 0.02, -0.03, 0.00, 0.01],
        "gdp_growth": [0.5, 0.4, -1.0, 0.2, 0.6],
    }, index=[1, 2, 3, 4, 5])
    drv = sat.driver_frame(concepts)
    # duer_lag1 at t=3 is uer(2) - uer(1)
    assert drv.loc[3, "duer_lag1"] == pytest.approx(0.5)
    assert drv.loc[4, "duer_lag2"] == pytest.approx(0.5)
    assert drv.loc[3, "hpi_growth_lag1"] == pytest.approx(0.02)
    assert drv.loc[5, "gdp_growth_lag2"] == pytest.approx(-1.0)
    # leading rows carry NaN, never fabricated values
    assert np.isnan(drv.loc[1, "duer_lag1"])
    assert np.isnan(drv.loc[2, "duer_lag2"])


def test_stationarity_verdicts_on_synthetic_series():
    rng = np.random.default_rng(7)
    walk = pd.Series(np.cumsum(rng.standard_normal(200)))
    noise = pd.Series(rng.standard_normal(200))
    tab = sat.stationarity_table({"walk": walk, "noise": noise}) \
             .set_index("series")
    assert tab.loc["walk", "adf_p"] > 0.05          # cannot reject unit root
    assert tab.loc["walk", "kpss_p"] < 0.05         # rejects stationarity
    assert "difference" in tab.loc["walk", "verdict"]
    assert tab.loc["noise", "adf_p"] < 0.05
    assert "stationary" in tab.loc["noise", "verdict"]


def test_satellite_sign_governance_and_fit_quality(satm):
    assert satm.fit_meta["sign_valid"]
    for term in satm.terms:
        driver = term.rsplit("_lag", 1)[0]
        coef = float(satm.params[term])
        assert coef * sat.EXPECTED_SIGN[driver] > 0.0, \
            f"{term} violates economic sign: {coef}"
    # every candidate spec was scored on the common sample
    assert len(satm.selection) == 26
    assert satm.adj_r2 > 0.2                 # explains a real cycle share
    assert 1.0 < satm.dw < 3.0               # no runaway autocorrelation
    # chosen spec is the AIC minimum within the sign-admissible set
    valid = satm.selection[satm.selection["signs_ok"]]
    assert " + ".join(satm.terms) == valid.iloc[0]["spec"]


def test_scenario_z_paths_finite_and_linear(zpaths, sset):
    cols = ["base", "down", "up", "weighted"]
    vals = zpaths[cols].to_numpy(dtype=float)
    assert vals.shape == (sset.horizon, 4)
    assert np.isfinite(vals).all()
    # linear satellite => Z of the weighted macro path == weighted Z
    w = sset.weights
    combo = (w["base"] * zpaths["base"] + w["down"] * zpaths["down"]
             + w["up"] * zpaths["up"])
    np.testing.assert_allclose(zpaths["weighted"].to_numpy(),
                               combo.to_numpy(), atol=1e-10)
    # calendar anchoring: h=1 is the quarter after the 2015Q1 jump-off
    assert str(zpaths["period"].iloc[0]) == "2015Q2"
    # severe is the most negative path inside the R&S window on average
    rs = sset.rs_window
    assert zpaths["down"].iloc[:rs].mean() < zpaths["base"].iloc[:rs].mean()
    assert zpaths["down"].iloc[:rs].mean() < zpaths["up"].iloc[:rs].mean()
    # all paths share the long-run tail (macros at long-run means)
    tail = zpaths[cols].iloc[-1].to_numpy()
    np.testing.assert_allclose(tail, tail[0], atol=1e-10)


def test_predict_raises_on_missing_history(satm):
    # a bare scenario path without spliced history has NaN lags -> loud
    with pytest.raises(ValueError, match="history"):
        satm.predict(pd.DataFrame(
            {t: [np.nan, 0.1] for t in satm.terms}))


# ---------------------------------------------------------------------------
# 3. hazard-level conditioning mechanics
# ---------------------------------------------------------------------------

def test_condition_hazard_grid_orientation_and_masking():
    lam = np.array([[0.010, 0.020, 0.015],
                    [0.050, 0.030, 0.000]])
    on = np.array([[True, True, True],
                   [True, True, False]])
    rho = 0.12
    down = sat.condition_hazard_grid(lam, on, np.array([-2.0, -2.0, -2.0]),
                                     rho)
    up = sat.condition_hazard_grid(lam, on, np.array([2.0, 2.0, 2.0]), rho)
    # orientation: Z < 0 inflates hazards, Z > 0 compresses them
    assert (down[on] > lam[on]).all()
    assert (up[on] < lam[on]).all()
    # off-window cells stay exactly zero
    assert down[1, 2] == 0.0 and up[1, 2] == 0.0
    # golden fixture value through the grid: 2% at Z=-2, rho=0.12 -> 7.34%
    d = sat.condition_hazard_grid(np.array([[0.02]]),
                                  np.array([[True]]),
                                  np.array([-2.0]), rho)
    assert d[0, 0] * 100 == pytest.approx(7.34, abs=1e-2)


def test_condition_hazard_grid_extends_short_z_path():
    lam = np.full((1, 5), 0.02)
    on = np.ones((1, 5), dtype=bool)
    short = sat.condition_hazard_grid(lam, on, np.array([-1.0, -2.0]), 0.12)
    full = sat.condition_hazard_grid(
        lam, on, np.array([-1.0, -2.0, -2.0, -2.0, -2.0]), 0.12)
    np.testing.assert_allclose(short, full, atol=0)
    # and the extension holds the FINAL value
    assert short[0, 4] == pytest.approx(pit_pd(0.02, -2.0, 0.12), abs=1e-15)


def test_condition_requires_rho(panel, models):
    with pytest.raises(ValueError, match="rho"):
        sat.scenario_ecl_for_snapshot(panel, T_SNAP, models,
                                      z_path=np.zeros(40))


# ---------------------------------------------------------------------------
# 4. composition correctness: unconditioned wrapper == frozen engine
# ---------------------------------------------------------------------------

def test_unconditioned_wrapper_matches_frozen_engine(books):
    a, b = books["frozen"], books["unconditioned"]
    assert len(a) == len(b)
    assert (a["id"].to_numpy() == b["id"].to_numpy()).all()
    for col in ("stage", "ecl_12m", "ecl_lifetime", "ecl_reported"):
        np.testing.assert_allclose(a[col].to_numpy(dtype=float),
                                   b[col].to_numpy(dtype=float),
                                   rtol=0, atol=1e-9)


def test_book_population(books):
    b = books["base"]
    assert len(b) == LIVE_LOANS + STAGE3_LOANS
    assert int((b["stage"] == 3).sum()) == STAGE3_LOANS
    assert int((b["stage"] != 3).sum()) == LIVE_LOANS


def test_stage3_ecl_scenario_invariant(books):
    """Defaulted rows: ECL = LGD x balance regardless of the scenario."""
    for name in ("up", "base", "down"):
        d = books[name][books[name]["stage"] == 3]
        np.testing.assert_allclose(
            d["ecl_reported"].to_numpy(),
            (d["lgd_current"] * d["balance"]).to_numpy(),
            rtol=1e-12)
        np.testing.assert_allclose(
            d["ecl_reported"].to_numpy(),
            books["base"].loc[books["base"]["stage"] == 3,
                              "ecl_reported"].to_numpy(),
            rtol=1e-12)


# ---------------------------------------------------------------------------
# 5. economics: ordering + Jensen
# ---------------------------------------------------------------------------

def test_ecl_ordering_severe_base_upside(books):
    rep = {n: float(books[n]["ecl_reported"].sum())
           for n in ("up", "base", "down")}
    e12 = {n: float(books[n]["ecl_12m"].sum())
           for n in ("up", "base", "down")}
    life = {n: float(books[n]["ecl_lifetime"].sum())
            for n in ("up", "base", "down")}
    # the IFRS 9 allowance ordering
    assert rep["down"] > rep["base"] > rep["up"]
    assert e12["down"] > e12["base"] > e12["up"]
    # lifetime: severe strictly worst; the upside/base crossover is the
    # documented mirror-payback + survivor-exposure feature (report), so
    # only severe > base is asserted here
    assert life["down"] > life["base"]


def test_jensen_weighted_exceeds_average_path(books, sset):
    w = sset.weights
    for col in ("ecl_reported", "ecl_lifetime"):
        weighted = sum(w[n] * float(books[n][col].sum())
                       for n in ("base", "down", "up"))
        at_avg = float(books["weighted"][col].sum())
        assert weighted > at_avg, (
            f"Jensen violated on {col}: weighted {weighted:.0f} "
            f"<= at-average-path {at_avg:.0f}")


def test_conditioned_pd_moves_with_z(books):
    """Per-loan engine lifetime PDs must rank with the scenario severity
    inside the R&S window: severe >= base for (almost) every performing
    loan; tolerance covers loans whose R ends before differentiation."""
    perf = books["base"]["stage"] != 3
    pd_down = books["down"].loc[perf, "lifetime_pd_engine"].to_numpy()
    pd_base = books["base"].loc[perf, "lifetime_pd_engine"].to_numpy()
    assert (pd_down >= pd_base - 1e-12).mean() > 0.999
    assert pd_down.mean() > pd_base.mean()
