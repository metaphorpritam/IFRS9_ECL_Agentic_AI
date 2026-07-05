"""API-contract tests for engine/staging.py (IFRS 9 SICR relative staging).

Fits the real rung-1 hazards on the training split (fast: ~10s for both
cause-specific GLMs) and checks the CONTRACT, not point values:

* exactness of the vectorised age-offset fast path against the slow
  pd_term_structure reference (the module's performance strategy must be a
  factorisation, not an approximation);
* Stage 3 == default rows (shared default definition);
* the SAME-WINDOW convention (both PD legs over R = mat_time - t, floor 1);
* the ratio-AND-add-on trigger logic and the annualisation conversion;
* origination-covariate reconstruction incl. the flagged pre-window clamp
  and the missing-orig-rate proxy;
* the 30-DPD backstop hook: structurally INERT on DCR (no dpd column), but
  fires when a dpd column is supplied;
* probation via the trigger-window equivalence (t-1 trigger holds Stage 2);
* the plan's sanity gates: Stage-2 share rises sharply t=20 -> t=40, no
  Stage-1 loan with a >10x lifetime-PD ratio, threshold-sensitivity
  monotonicity.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engine.hazard import REQUIRED_COLS, fit_default_hazard, fit_prepay_hazard
from engine.staging import (
    StagingConfig,
    assign_stages,
    build_macro_map,
    crosscheck_term_structure,
    lifetime_pd_table,
    origination_covariates,
    quantitative_sicr,
)

PANEL = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel.parquet"


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL)


@pytest.fixture(scope="module")
def models(panel):
    train = panel[panel["split"] == "train"]
    return {"default": fit_default_hazard(train),
            "prepay": fit_prepay_hazard(train)}


@pytest.fixture(scope="module")
def macro_map(panel):
    return build_macro_map(panel)


@pytest.fixture(scope="module")
def staged(panel, models):
    """assign_stages at both exhibit snapshots (payoffs kept; filtered
    per-test where derecognition matters)."""
    return {t: assign_stages(panel[panel["time"] <= t], models,
                             snapshot_time=t) for t in (20, 40)}


# ---------------------------------------------------------------------------
# exactness of the fast path
# ---------------------------------------------------------------------------

def test_fast_path_is_exact_vs_pd_term_structure(panel, models):
    """Age-offset factorisation must reproduce pd_term_structure, not
    approximate it (both legs, fixed-seed loan sample)."""
    err = crosscheck_term_structure(panel[panel["time"] <= 40], models,
                                    at_time=40, n_sample=8, seed=0)
    assert err < 1e-10


# ---------------------------------------------------------------------------
# stage rule
# ---------------------------------------------------------------------------

def test_stage3_is_exactly_the_default_rows(staged):
    for t, res in staged.items():
        assert ((res["stage"] == 3) == (res["default_event"] == 1)).all()
        assert (res.loc[res["stage"] == 3, "trigger_reason"] == "default").all()


def test_same_window_and_pd_ranges(panel, staged):
    """R = mat_time - t floored at 1; PDs are probabilities; the origination
    leg uses the SAME R (one shared column -- the comparison is same-window
    by construction)."""
    for t, res in staged.items():
        snap = (panel[panel["time"] == t].sort_values("id")
                .reset_index(drop=True))
        expected_R = np.maximum((snap["mat_time"] - t).to_numpy(), 1)
        assert np.array_equal(res["R"].to_numpy(), expected_R)
        for col in ("lifetime_pd_now", "lifetime_pd_orig",
                    "ann_pd_now", "ann_pd_orig"):
            v = res[col].to_numpy()
            assert np.isfinite(v).all() and (v >= 0).all() and (v < 1).all()


def test_annualisation_conversion(staged):
    """ann = 1 - (1 - PD_life)^(4/R): R quarters = R/4 years."""
    res = staged[40]
    expect = 1.0 - (1.0 - res["lifetime_pd_now"]) ** (4.0 / res["R"])
    assert np.allclose(res["ann_pd_now"], expect, rtol=1e-12, atol=1e-15)
    # 4-quarter window: annualised PD == lifetime PD by definition
    one_year = res["R"] == 4
    if one_year.any():
        assert np.allclose(res.loc[one_year, "ann_pd_now"],
                           res.loc[one_year, "lifetime_pd_now"], rtol=1e-12)


def test_quant_trigger_requires_ratio_AND_addon():
    """The doubling trigger alone is not SICR; the add-on alone is not SICR."""
    tbl = pd.DataFrame({
        "pd_ratio": [3.0, 3.0, 1.5, 0.8, 2.01],
        "ann_addon": [0.02, 0.001, 0.02, -0.01, 0.0051],
    })
    got = quantitative_sicr(tbl, StagingConfig())
    assert got.tolist() == [True, False, False, False, True]


def test_ratio_threshold_is_configurable():
    tbl = pd.DataFrame({"pd_ratio": [2.5], "ann_addon": [0.02]})
    assert quantitative_sicr(tbl, StagingConfig(ratio_threshold=2.0))[0]
    assert not quantitative_sicr(tbl, StagingConfig(ratio_threshold=3.0))[0]


# ---------------------------------------------------------------------------
# origination covariates
# ---------------------------------------------------------------------------

def test_origination_covariates_reconstruction(panel, macro_map):
    snap = (panel[panel["time"] == 40].sort_values("id")
            .reset_index(drop=True))
    orig = origination_covariates(snap, macro_map)
    # static fields pass through; updated LTV collapses to origination LTV
    assert np.array_equal(orig["updated_ltv"], snap["LTV_orig_time"])
    assert np.array_equal(orig["FICO_orig_time"], snap["FICO_orig_time"])
    # the projection window is shared: loan_age stays the CURRENT age
    assert np.array_equal(orig["loan_age"], snap["loan_age"])
    # in-window originations use the exact time -> macro map
    ok = snap["orig_time"] >= 6
    i = ok.idxmax()
    o = int(snap.loc[i, "orig_time"])
    assert orig.loc[i, "uer_lag1"] == macro_map.loc[o - 1, "uer"]
    assert orig.loc[i, "uer_chg4_lag1"] == pytest.approx(
        macro_map.loc[o - 1, "uer"] - macro_map.loc[o - 5, "uer"])
    assert orig.loc[i, "gdp_lag1"] == macro_map.loc[o - 1, "gdp"]
    assert orig.loc[i, "hpi_growth_lag1"] == pytest.approx(
        np.log(macro_map.loc[o - 1, "hpi"]) - np.log(macro_map.loc[o - 2, "hpi"]))
    # flags: pre-window clamp and missing-orig-rate proxy
    assert np.array_equal(orig["orig_macro_approx"],
                          (snap["orig_time"] - 5) < macro_map.index.min())
    assert np.array_equal(orig["orig_rate_proxy"],
                          snap["orig_rate_missing"] == 1)
    # proxy loans use the current note rate in the incentive
    j = (snap["orig_rate_missing"] == 1).idxmax()
    oj = int(np.clip(snap.loc[j, "orig_time"], macro_map.index.min(),
                     macro_map.index.max()))
    assert orig.loc[j, "prepay_incentive"] == pytest.approx(
        snap.loc[j, "interest_rate_time"] - macro_map.loc[oj, "rate_med"])


# ---------------------------------------------------------------------------
# backstop hook: inert on DCR, live when a dpd column exists
# ---------------------------------------------------------------------------

def test_backstop_inert_without_dpd_column(staged):
    """DCR has no delinquency ladder -> the 30-DPD backstop NEVER fires."""
    for res in staged.values():
        assert (res["trigger_reason"] != "backstop_30dpd").all()


def test_backstop_fires_when_dpd_column_supplied(panel, models):
    hist = panel[panel["time"] <= 40].copy()
    hist["dpd_time"] = 0.0
    live40 = hist[(hist["time"] == 40) & (hist["default_event"] == 0)
                  & (hist["payoff_event"] == 0)]
    victims = live40["id"].head(5).to_numpy()
    hist.loc[(hist["time"] == 40) & hist["id"].isin(victims),
             "dpd_time"] = 45.0
    res = assign_stages(hist, models, snapshot_time=40)
    hit = res[res["id"].isin(victims)]
    assert (hit["stage"] == 2).all()
    assert (hit["trigger_reason"] == "backstop_30dpd").all()
    # and switching the hook off in config disables it
    res_off = assign_stages(hist, models,
                            StagingConfig(backstop_30dpd=False),
                            snapshot_time=40)
    assert (res_off["trigger_reason"] != "backstop_30dpd").all()


def test_backstop_reads_configured_dpd_col_not_default(panel, models):
    """A custom cfg.dpd_col must drive the backstop even when a stray
    default-named column ('dpd_time') is also present (regression: the
    default-named column used to shadow the configured one)."""
    hist = panel[panel["time"] <= 40].copy()
    hist["dpd_time"] = 0.0            # stray default-named column, all clean
    hist["days_late"] = 0.0
    live40 = hist[(hist["time"] == 40) & (hist["default_event"] == 0)
                  & (hist["payoff_event"] == 0)]
    victims = live40["id"].head(3).to_numpy()
    hist.loc[(hist["time"] == 40) & hist["id"].isin(victims),
             "days_late"] = 60.0
    cfg = StagingConfig(dpd_col="days_late")
    res = assign_stages(hist, models, cfg, snapshot_time=40)
    hit = res[res["id"].isin(victims)]
    assert (hit["stage"] == 2).all()
    assert (hit["trigger_reason"] == "backstop_30dpd").all()


# ---------------------------------------------------------------------------
# probation / cure
# ---------------------------------------------------------------------------

def _mini_table(t: int, ids, ratio, addon) -> pd.DataFrame:
    n = len(ids)
    return pd.DataFrame({
        "id": ids, "time": t, "loan_age": 8, "R": 20,
        "lifetime_pd_now": 0.05, "lifetime_pd_orig": 0.02,
        "ann_pd_now": 0.01, "ann_pd_orig": 0.005,
        "pd_ratio": ratio, "ann_addon": addon,
        "orig_macro_approx": False, "orig_rate_proxy": False,
        "default_event": np.zeros(n, dtype=int),
        "payoff_event": np.zeros(n, dtype=int),
    })


def test_probation_holds_stage2_for_cure_quarters(models):
    """Loan 1 triggered at t-1 but is clean at t -> held in Stage 2
    ('sicr_probation'); loan 2 clean both quarters -> Stage 1. With
    cure_quarters=1 the lookback vanishes and loan 1 returns to Stage 1."""
    t = 40
    now = _mini_table(t, [1, 2], ratio=[1.0, 1.0], addon=[0.0, 0.0])
    prev = _mini_table(t - 1, [1, 2], ratio=[3.0, 1.0], addon=[0.02, 0.0])
    dummy_panel = pd.DataFrame({"time": [t]})
    res = assign_stages(dummy_panel, models, snapshot_time=t,
                        pd_tables={t: now, t - 1: prev})
    r1 = res.set_index("id")
    assert r1.loc[1, "stage"] == 2
    assert r1.loc[1, "trigger_reason"] == "sicr_probation"
    assert r1.loc[2, "stage"] == 1
    res1 = assign_stages(dummy_panel, models, StagingConfig(cure_quarters=1),
                         snapshot_time=t, pd_tables={t: now, t - 1: prev})
    assert res1.set_index("id").loc[1, "stage"] == 1


# ---------------------------------------------------------------------------
# portfolio-level sanity gates (the plan's acceptance checks)
# ---------------------------------------------------------------------------

def test_stage2_share_rises_sharply_into_stress(staged):
    shares = {}
    for t, res in staged.items():
        live = res[res["payoff_event"] == 0]     # payoffs = derecognitions
        shares[t] = (live["stage"] == 2).mean()
    assert shares[40] > shares[20] + 0.20


def test_stage3_share_equals_default_incidence(staged):
    for t, res in staged.items():
        live = res[res["payoff_event"] == 0]
        assert (live["stage"] == 3).sum() == (live["default_event"] == 1).sum()


def test_no_stage1_loan_with_10x_pd_ratio(staged):
    for t, res in staged.items():
        live = res[res["payoff_event"] == 0]
        s1 = live[live["stage"] == 1]
        assert (s1["pd_ratio"] <= 10.0).all()


def test_stage2_share_monotone_in_ratio_threshold(panel, models, macro_map):
    tbl = lifetime_pd_table(panel[panel["time"] <= 40], models, 40, macro_map)
    live = tbl[(tbl["payoff_event"] == 0) & (tbl["default_event"] == 0)]
    shares = [quantitative_sicr(live, StagingConfig(ratio_threshold=r)).mean()
              for r in (1.5, 2.0, 3.0, 4.0)]
    assert all(a >= b for a, b in zip(shares, shares[1:]))
    assert shares[0] > shares[-1]                 # strictly informative sweep


def test_nan_covariates_raise(panel, models):
    """Lag-warm-up rows (time < 6) must fail loudly, not stage silently."""
    with pytest.raises(ValueError, match="NaN"):
        assign_stages(panel[panel["time"] <= 3], models, snapshot_time=3)
