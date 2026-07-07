"""Tests for agent/tools_tier1.py — the four Tier-1 tools over the frozen engine.

Contracts:
  1. VALIDATION FIRST: pydantic rejects malformed arguments loudly BEFORE
     any engine code runs (bad vars/shapes/segments, out-of-bound shocks,
     NaN, weights that do not sum to 1, inverted snapshot order).
  2. ECONOMICS: shock_macro('UER', +2) RAISES the allowance (coherent
     co-movement convention — module docstring); an HPI boom LOWERS it;
     'peak_revert' is strictly milder than 'parallel'; a zero shock is a
     no-op.
  3. PUBLISHED-NUMBER IDENTITIES: baseline allowance and the reweight
     identity at (w_up, w_base, w_down) = (0.25, 0.5, 0.25) reproduce
     outputs/scenario_ecl/scenario_ecl_summary.csv (weighted ~ $34.0m,
     Jensen ~ 1.035x).
  4. WATERFALL IDENTITY: components sum exactly to closing - opening; the
     shock waterfall books the entire delta as remeasurement (same book,
     frozen staging).
  5. PLUMBING: every result is json.dumps-serialisable; every successful
     call appends exactly one line to the audit trail with an increasing
     seq.

The engine-backed tests share one lazily-built module state (joblib-cached
model fits), so this file is slower than the pure-unit suites on a cold
cache — same trade as tests/test_satellite.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

import agent.tools_tier1 as tools

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_CSV = ROOT / "outputs" / "scenario_ecl" / "scenario_ecl_summary.csv"

#: published per-scenario reported allowances ($m), the Day-3 exhibit
PUBLISHED = pd.read_csv(SUMMARY_CSV).set_index("scenario")["allowance_m"]


@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """Keep the real outputs/agent_log/ audit trail clean during tests."""
    old = tools.LOG_PATH
    tools.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools.LOG_PATH = old


@pytest.fixture(scope="module")
def state():
    tools.warm_up()
    return tools._state()


def _read_log() -> list[dict]:
    p = Path(tools.LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines()
            if line.strip()]


# ---------------------------------------------------------------------------
# 1. argument validation (must fail BEFORE the engine; no heavy state)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs", [
    dict(var="UER", shock=10.5),                # beyond the +-10pp bound
    dict(var="UER", shock=-12.0),
    dict(var="HPI", shock=5.1),                 # beyond the +-5pp/q bound
    dict(var="GDP", shock=-6.0),
    dict(var="FX", shock=1.0),                  # unknown variable
    dict(var="UER", shock=1.0, shape="spike"),  # unknown shape
    dict(var="UER", shock=float("nan")),        # non-finite shock
    dict(var="UER", shock=float("inf")),
])
def test_shock_macro_rejects_bad_args(kwargs):
    with pytest.raises(ValidationError):
        tools.shock_macro(**kwargs)


def test_shock_macro_accepts_boundary_shock():
    # exactly at the bound is legal (arg model only -- no engine run)
    args = tools.ShockMacroArgs(var="UER", shock=10.0)
    assert args.shock == 10.0
    assert tools.ShockMacroArgs(var="HPI", shock=-5.0).shock == -5.0


@pytest.mark.parametrize("w", [
    (0.5, 0.5, 0.5),      # sums to 1.5
    (0.2, 0.2, 0.2),      # sums to 0.6
    (-0.1, 0.6, 0.5),     # negative weight
    (1.2, -0.1, -0.1),    # out of [0, 1]
])
def test_reweight_rejects_bad_weights(w):
    with pytest.raises(ValidationError):
        tools.reweight_scenarios(*w)


def test_rerun_ecl_rejects_unknown_segment():
    with pytest.raises(ValidationError):
        tools.rerun_ecl("investors")
    with pytest.raises(ValidationError):
        tools.rerun_ecl("stage4")


@pytest.mark.parametrize("t0,t1", [
    (40, 20),    # inverted
    (20, 20),    # not strictly increasing
    (0, 40),     # below the panel clock
    (20, 61),    # beyond t=60
    (-3, 10),
])
def test_decompose_waterfall_rejects_bad_snapshots(t0, t1):
    with pytest.raises(ValidationError):
        tools.decompose_waterfall(t0, t1)


def test_extra_arguments_are_rejected():
    with pytest.raises(ValidationError):
        tools.ShockMacroArgs(var="UER", shock=1.0, sneaky=1)


# ---------------------------------------------------------------------------
# 2 + 4. shock_macro economics + waterfall vs baseline
# ---------------------------------------------------------------------------

def test_shock_uer_up_increases_allowance(state):
    r = tools.shock_macro("UER", 2.0)
    # baseline reproduces the published base-scenario allowance
    assert r["baseline_allowance"] / 1e6 == pytest.approx(
        PUBLISHED["base"], rel=1e-5)
    # an unemployment stress must RAISE the allowance
    assert r["delta"] > 0
    assert r["shocked_allowance"] > r["baseline_allowance"]
    assert r["shocked_allowance"] == pytest.approx(
        r["baseline_allowance"] + r["delta"], rel=1e-12)
    assert r["coverage"] > r["baseline_coverage"] > 0
    # coherent co-movement: UER up drags HPI growth and GDP growth DOWN
    assert r["applied_peak_deltas_pp"]["uer"] == pytest.approx(2.0)
    assert r["applied_peak_deltas_pp"]["hpi_growth"] < 0
    assert r["applied_peak_deltas_pp"]["gdp_growth"] < 0
    # result is JSON-serialisable and audit-referenced
    json.dumps(r)
    assert r["tool_call_id"].startswith("tc-")


def test_shock_waterfall_books_delta_as_remeasurement(state):
    r = tools.shock_macro("UER", 2.0)
    comp = {c["component"]: c["amount"] for c in r["waterfall_vs_baseline"]}
    # identity: opening + deltas == closing
    total = (comp["opening"] + comp["stage_migration"]
             + comp["remeasurement"] + comp["derecognitions"]
             + comp["new_loans"])
    assert total == pytest.approx(comp["closing"], rel=1e-9)
    # same book, frozen staging: the entire move is remeasurement
    assert comp["opening"] == pytest.approx(r["baseline_allowance"], rel=1e-12)
    assert comp["closing"] == pytest.approx(r["shocked_allowance"], rel=1e-12)
    assert comp["stage_migration"] == pytest.approx(0.0, abs=1e-6)
    assert comp["derecognitions"] == pytest.approx(0.0, abs=1e-6)
    assert comp["new_loans"] == pytest.approx(0.0, abs=1e-6)
    assert comp["remeasurement"] == pytest.approx(r["delta"], rel=1e-9)
    # stage mix: loan counts frozen across the shock, allowances positive
    mix = r["stage_mix"]
    assert sum(mix[s]["n_loans"] for s in mix) == len(state.books["base"])


def test_shock_hpi_boom_decreases_allowance(state):
    r = tools.shock_macro("HPI", 2.0)      # +2pp/q house-price growth
    assert r["delta"] < 0
    assert r["applied_peak_deltas_pp"]["uer"] < 0     # co-moving boom


def test_shock_peak_revert_milder_than_parallel(state):
    par = tools.shock_macro("UER", 2.0, shape="parallel")
    rev = tools.shock_macro("UER", 2.0, shape="peak_revert")
    assert 0 < rev["delta"] < par["delta"]


def test_shock_zero_is_noop(state):
    r = tools.shock_macro("GDP", 0.0)
    assert r["delta"] == pytest.approx(0.0, abs=1e-6)
    assert r["shocked_allowance"] == pytest.approx(r["baseline_allowance"],
                                                   rel=1e-12)


# ---------------------------------------------------------------------------
# 3. reweight_scenarios: published identity + Jensen
# ---------------------------------------------------------------------------

def test_reweight_identity_reproduces_published_34m(state):
    r = tools.reweight_scenarios(0.25, 0.5, 0.25)   # (w_up, w_base, w_down)
    expected_m = (0.25 * PUBLISHED["up"] + 0.5 * PUBLISHED["base"]
                  + 0.25 * PUBLISHED["down"])
    assert r["weighted_allowance"] / 1e6 == pytest.approx(expected_m,
                                                          rel=1e-5)
    # the shared-fact headline: ~ $34.0m, Jensen ~ 1.035x
    assert r["weighted_allowance"] / 1e6 == pytest.approx(34.0, abs=0.1)
    assert r["jensen_ratio"] > 1.0
    assert r["jensen_ratio"] == pytest.approx(1.035, abs=0.005)
    assert r["delta_vs_adopted_pct"] == pytest.approx(0.0, abs=1e-9)
    json.dumps(r)


def test_reweight_degenerate_single_scenario(state):
    r = tools.reweight_scenarios(1.0, 0.0, 0.0)     # all weight on upside
    assert r["weighted_allowance"] / 1e6 == pytest.approx(PUBLISHED["up"],
                                                          rel=1e-5)
    # weighted path == the upside path itself -> no Jensen gap
    assert r["jensen_ratio"] == pytest.approx(1.0, abs=1e-9)


def test_reweight_per_scenario_totals_match_books(state):
    r = tools.reweight_scenarios(0.25, 0.5, 0.25)
    for name in ("up", "base", "down"):
        assert r["per_scenario"][name]["allowance"] == pytest.approx(
            float(state.books[name]["ecl_reported"].sum()), rel=1e-12)


# ---------------------------------------------------------------------------
# rerun_ecl: segment decompositions of the weighted allowance
# ---------------------------------------------------------------------------

def test_rerun_ecl_all_matches_adopted_weighted(state):
    r_all = tools.rerun_ecl("all")
    r_w = tools.reweight_scenarios(0.25, 0.5, 0.25)
    assert r_all["weighted_allowance"] == pytest.approx(
        r_w["weighted_allowance"], rel=1e-12)
    assert r_all["n_loans"] == len(state.books["base"])
    assert r_all["share_of_book_allowance_pct"] == pytest.approx(100.0)
    json.dumps(r_all)


def test_rerun_ecl_stages_partition_the_book(state):
    r = {s: tools.rerun_ecl(s) for s in ("all", "stage1", "stage2", "stage3")}
    assert (r["stage1"]["n_loans"] + r["stage2"]["n_loans"]
            + r["stage3"]["n_loans"]) == r["all"]["n_loans"] == 7_849
    total = (r["stage1"]["weighted_allowance"]
             + r["stage2"]["weighted_allowance"]
             + r["stage3"]["weighted_allowance"])
    assert total == pytest.approx(r["all"]["weighted_allowance"], rel=1e-9)
    bal = (r["stage1"]["balance"] + r["stage2"]["balance"]
           + r["stage3"]["balance"])
    assert bal == pytest.approx(r["all"]["balance"], rel=1e-9)


def test_rerun_ecl_stage3_is_scenario_invariant(state):
    r = tools.rerun_ecl("stage3")
    vals = list(r["per_scenario_allowance"].values())
    assert vals[0] == pytest.approx(vals[1], rel=1e-9)
    assert vals[1] == pytest.approx(vals[2], rel=1e-9)
    assert r["n_loans"] == 43


def test_rerun_ecl_named_segments(state):
    inv = tools.rerun_ecl("investor")
    hl = tools.rerun_ecl("high_ltv")
    allr = tools.rerun_ecl("all")
    for seg in (inv, hl):
        assert 0 < seg["n_loans"] < allr["n_loans"]
        assert 0 < seg["weighted_allowance"] < allr["weighted_allowance"]
        assert 0 < seg["share_of_book_allowance_pct"] < 100
    # frozen-panel golden counts (t=60 non-payoff book)
    assert inv["n_loans"] == 1_077
    assert hl["n_loans"] == 3_201
    # high-LTV loans must be riskier than the book on average
    assert hl["coverage"] > allr["coverage"]


# ---------------------------------------------------------------------------
# decompose_waterfall: frozen-engine movement identity
# ---------------------------------------------------------------------------

def test_waterfall_components_sum_to_closing_minus_opening(state):
    r = tools.decompose_waterfall(20, 40)
    comp = {c["component"]: c["amount"] for c in r["components"]}
    deltas = (comp["stage_migration"] + comp["remeasurement"]
              + comp["derecognitions"] + comp["new_loans"])
    assert deltas == pytest.approx(comp["closing"] - comp["opening"],
                                   rel=1e-9)
    assert r["identity_gap"] == pytest.approx(0.0, abs=1e-3)
    assert r["opening_allowance"] > 0 and r["closing_allowance"] > 0
    # calendar anchoring: t=1 ~ 2000Q2
    assert r["period_t0"] == "2005Q1"
    assert r["period_t1"] == "2010Q1"
    kinds = {c["component"]: c["kind"] for c in r["components"]}
    assert kinds["opening"] == kinds["closing"] == "level"
    assert kinds["remeasurement"] == "delta"
    json.dumps(r)


def test_waterfall_defaults_match_explicit_call(state):
    a = tools.decompose_waterfall()
    b = tools.decompose_waterfall(20, 40)
    assert a["components"] == b["components"]
    assert (a["t0"], a["t1"]) == (20, 40)


# ---------------------------------------------------------------------------
# 5. audit trail
# ---------------------------------------------------------------------------

def test_audit_log_appends_one_line_per_call(state):
    before = _read_log()
    r1 = tools.rerun_ecl("all")
    r2 = tools.reweight_scenarios(0.25, 0.5, 0.25)
    after = _read_log()
    assert len(after) == len(before) + 2
    e1, e2 = after[-2], after[-1]
    assert set(e1) == {"seq", "ts", "tool", "args", "headline"}
    assert e1["tool"] == "rerun_ecl" and e1["args"] == {"segment": "all"}
    assert e2["tool"] == "reweight_scenarios"
    assert e2["seq"] == e1["seq"] + 1
    assert r1["tool_call_id"] == f"tc-{e1['seq']:06d}"
    assert r2["tool_call_id"] == f"tc-{e2['seq']:06d}"
    # headline carries engine numbers so the LLM never does arithmetic
    assert "$" in e2["headline"] and "Jensen" in e2["headline"]


def test_validation_failure_is_not_logged(state):
    before = _read_log()
    with pytest.raises(ValidationError):
        tools.shock_macro("UER", 99.0)
    assert _read_log() == before
