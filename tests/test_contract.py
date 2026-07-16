"""Seam test for docs/api_contract.md — the App v2 API surface.

Every endpoint documented in docs/api_contract.md is exercised here with
(as close as HTTP allows) the exact example payloads shown in that file,
asserting the documented response fields/types exist. This is the contract
seam: if a field this file checks ever disappears or changes type, the UI
(coded only against docs/api_contract.md) breaks silently in the browser
without this test also failing loudly here first.

Scope: the NEW App v2 endpoints (Sections 2-4 of the contract) get full
field-by-field coverage. The pre-existing Section 1 endpoints already have
thorough tests in tests/test_api.py (published-number identity, validation,
audit trail) — this file only smoke-checks that they still match the
contract's documented shape, without re-deriving those numbers.

The LLM is NEVER called: /api/agent/interpret's narrator seam
(agent.graph._llm_narrate / _llm_narrate_docs) is monkeypatched with canned
text, exactly like tests/test_router.py does for the live copilot.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import agent.graph as graph
import agent.tools_tier1 as tools
import app.api.main as main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """Keep the real outputs/agent_log/ audit trail clean during tests.

    /api/policy/weights_table deliberately calls the real reweight_scenarios
    tool three times per request (contract's documented governance note),
    so this redirect matters here more than in most test modules.
    """
    old = tools.LOG_PATH
    tools.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools.LOG_PATH = old


@pytest.fixture(scope="module")
def client():
    old_agent = main.AGENT_ASK
    with TestClient(main.app) as c:
        main.AGENT_ASK = None
        yield c
    main.AGENT_ASK = old_agent


# ---------------------------------------------------------------------------
# Section 1 (existing endpoints): shape smoke-check only
# ---------------------------------------------------------------------------

def test_health_shape(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["engine_warm"], bool)
    assert isinstance(body["agent"], str)


def test_summary_shape(client):
    body = client.get("/api/ecl/summary").json()
    for key in ("as_of", "n_loans", "balance", "weights",
               "weighted_allowance", "coverage", "allowance_at_average_path",
               "jensen_ratio", "stage_mix", "scenarios", "amounts_in"):
        assert key in body
    assert body["amounts_in"] == "USD"
    assert set(body["as_of"]) == {"t", "period"}
    assert {s["name"] for s in body["scenarios"]} == {"up", "base", "down"}


def test_waterfall_shape(client):
    body = client.get("/api/ecl/waterfall", params={"t0": 20, "t1": 40}).json()
    for key in ("t0", "t1", "period_t0", "period_t1", "opening_allowance",
               "closing_allowance", "components", "identity_gap",
               "amounts_in", "headline", "tool_call_id"):
        assert key in body
    assert {c["component"] for c in body["components"]} == {
        "opening", "stage_migration", "remeasurement", "derecognitions",
        "new_loans", "closing"}


def test_credit_cycle_shape(client):
    body = client.get("/api/exhibits/credit_cycle").json()
    assert set(body) == {"rho", "n_quarters", "points"}
    assert body["n_quarters"] == 60
    pt = body["points"][0]
    assert set(pt) == {"t", "calendar", "z", "observed_dr", "ttc_pd", "pit_pd"}


def test_tool_endpoints_shape(client):
    r = client.post("/api/tools/shock_macro", json={"var": "UER", "shock": 2.0})
    assert r.status_code == 200
    body = r.json()
    for key in ("tool", "var", "shock", "shape", "shock_units",
               "applied_peak_deltas_pp", "baseline_allowance",
               "shocked_allowance", "delta", "delta_pct",
               "baseline_coverage", "coverage", "stage_mix",
               "waterfall_vs_baseline", "amounts_in", "headline",
               "tool_call_id"):
        assert key in body

    r = client.post("/api/tools/reweight_scenarios",
                    json={"w_up": 0.25, "w_base": 0.5, "w_down": 0.25})
    assert r.status_code == 200
    for key in ("weights", "per_scenario", "weighted_allowance",
               "allowance_at_average_path", "jensen_ratio", "coverage",
               "adopted_weights", "adopted_weighted_allowance",
               "delta_vs_adopted_pct"):
        assert key in r.json()

    r = client.post("/api/tools/rerun_ecl", json={"segment": "stage3"})
    assert r.status_code == 200
    for key in ("segment", "segment_definition", "n_loans", "balance",
               "weighted_allowance", "coverage",
               "share_of_book_allowance_pct", "per_scenario_allowance",
               "stage_mix"):
        assert key in r.json()

    r = client.post("/api/tools/decompose_waterfall", json={"t0": 20, "t1": 40})
    assert r.status_code == 200
    assert "identity_gap" in r.json()


def test_ask_and_stream_shape(client, monkeypatch):
    def fake_router(question, emit):
        emit({"node": "router", "label": "classify", "route": "rerun_ecl"})
        emit({"node": "narrator", "label": "narrating", "answer": "ok"})
        return {"answer": "ok", "route": "rerun_ecl"}

    monkeypatch.setattr(main, "AGENT_ASK", fake_router)
    body = client.post("/api/agent/ask", json={"question": "how much allowance?"}).json()
    assert set(body) == {"answer", "route", "trace"}
    assert isinstance(body["trace"], list)
    # contract: every trace event is keyed by "node" (the SSE feed replays
    # these same dicts — the UI's AgentTrace badges key off this field)
    assert body["trace"], "trace must not be empty"
    for ev in body["trace"]:
        assert "node" in ev, f"trace event missing 'node': {ev}"


# ---------------------------------------------------------------------------
# Section 2: The Model tab
# ---------------------------------------------------------------------------

_HAZARD_COEF_FIELDS = {"variable", "family", "hazard_ratio", "ci", "p",
                      "p_display", "story"}
_HAZARD_FAMILIES = {"baseline", "borrower", "collateral", "macro",
                    "incentive"}


def test_model_coefficients_contract(client):
    body = client.get("/api/model/coefficients").json()
    assert set(body) == {"models", "fit_stats", "source_files"}
    assert body["source_files"] == ["outputs/hazard/hazard_ratios.md",
                                    "outputs/hazard/fit_stats.md"]

    models = body["models"]
    assert set(models) == {"default", "prepay"}
    for name, n_events in (("default", 11354), ("prepay", 22734)):
        m = models[name]
        assert set(m) == {"n_fit", "events", "mcfadden_r2", "coefficients"}
        assert m["n_fit"] == 418418
        assert m["events"] == n_events
        assert isinstance(m["mcfadden_r2"], float)
        assert len(m["coefficients"]) == 13
        for row in m["coefficients"]:
            assert set(row) == _HAZARD_COEF_FIELDS
            assert row["family"] in _HAZARD_FAMILIES
            assert isinstance(row["hazard_ratio"], float)
            assert len(row["ci"]) == 2
            assert row["ci"][0] <= row["ci"][1]
            assert isinstance(row["p"], float) and 0.0 <= row["p"] <= 1.0
            assert isinstance(row["story"], str) and len(row["story"]) > 0

    # a specific, checkable row (the double-trigger interaction term)
    intercept = models["default"]["coefficients"][0]
    assert intercept["variable"] == "Intercept"
    assert intercept["family"] == "baseline"
    assert intercept["hazard_ratio"] == pytest.approx(0.2658)
    assert intercept["ci"] == pytest.approx([0.1534, 0.4608])

    fs = body["fit_stats"]
    assert set(fs) >= {"default", "prepay", "seasoning_peak",
                      "net_uer_effect_note", "double_trigger_note"}
    assert fs["default"]["train_auc"] == pytest.approx(0.7476)
    assert fs["default"]["oot_auc"] == pytest.approx(0.6609)
    assert fs["prepay"]["train_auc"] == pytest.approx(0.6839)
    assert fs["seasoning_peak"] == {
        "fitted_q": 12, "empirical_q": 10, "tolerance_q": 8,
        "plausible_window_q": [4, 18]}
    assert "PD RISES in unemployment" in fs["net_uer_effect_note"]
    assert isinstance(fs["double_trigger_note"], str)


def test_model_variable_dictionary_contract(client):
    body = client.get("/api/model/variable_dictionary").json()
    assert set(body) == {"preamble", "rows", "notes"}
    assert isinstance(body["preamble"], str) and len(body["preamble"]) > 0
    assert isinstance(body["notes"], str) and len(body["notes"]) > 0
    assert len(body["rows"]) == 13

    row_fields = {"variable", "source_transformation", "lag_window",
                 "economic_rationale", "expected_sign", "fitted_verified",
                 "consumed_by"}
    for row in body["rows"]:
        assert set(row) == row_fields
        assert all(isinstance(v, str) for v in row.values())

    first = body["rows"][0]
    assert first["variable"] == "`fico_s`"
    assert first["expected_sign"] == "PD ↓"


def test_model_lgd_contract(client):
    body = client.get("/api/model/lgd").json()
    for key in ("cure_rate", "cure_auc", "excess_loss_loading",
               "oot_calibration", "cure_stage_coefficients",
               "severity_stage_coefficients", "exhibits"):
        assert key in body

    assert body["cure_rate"] == pytest.approx(0.122, abs=1e-3)
    assert body["cure_auc"]["train"] == pytest.approx(0.837)
    assert body["cure_auc"]["oot"] == pytest.approx(0.769)
    assert body["excess_loss_loading"] == pytest.approx(0.0255)

    oot = body["oot_calibration"]
    assert set(oot) == {
        "mean_realised_lgd", "mean_predicted_lgd", "gap_pred_minus_real",
        "cure_rate_realised", "cure_rate_predicted",
        "mean_sev_noncure_realised", "mean_sev_noncure_predicted",
        "decile_mae_lgd"}
    for metric in oot.values():
        assert set(metric) == {"train", "oot"}
        assert isinstance(metric["train"], float)
        assert isinstance(metric["oot"], float)
    assert oot["mean_realised_lgd"]["train"] == pytest.approx(0.5995)
    assert oot["mean_realised_lgd"]["oot"] == pytest.approx(0.6113)

    assert len(body["cure_stage_coefficients"]) == 5
    for row in body["cure_stage_coefficients"]:
        assert set(row) == {"variable", "coef", "se", "z", "p", "odds_ratio"}
    assert len(body["severity_stage_coefficients"]) == 5
    for row in body["severity_stage_coefficients"]:
        assert set(row) == {"variable", "coef", "se_hc1", "z", "p"}

    assert body["exhibits"] == [
        {"id": "lgd_calibration_ltv",
         "png_url": "/static/exhibits/lgd/calibration_ltv.png"},
        {"id": "lgd_cure_by_ltv",
         "png_url": "/static/exhibits/lgd/cure_by_ltv.png"},
        {"id": "lgd_distribution",
         "png_url": "/static/exhibits/lgd/lgd_distribution.png"},
    ]


# ---------------------------------------------------------------------------
# Section 3: The Policy tab
# ---------------------------------------------------------------------------

def test_policy_staging_sensitivity_contract(client):
    body = client.get("/api/policy/staging_sensitivity").json()
    assert set(body) == {"add_on_pp", "thresholds", "rows", "reading",
                        "image_url"}
    assert body["add_on_pp"] == pytest.approx(0.5)
    assert body["thresholds"] == ["1.5x", "2.0x", "3.0x", "4.0x"]
    assert body["image_url"] == "/static/exhibits/staging/stage2_sensitivity.png"
    assert isinstance(body["reading"], str) and len(body["reading"]) > 0

    rows = {r["t"]: r for r in body["rows"]}
    assert set(rows) == {20, 40}
    assert rows[20]["period"] == "2005Q1"
    assert rows[40]["period"] == "2010Q1"
    assert rows[20]["stage2_share_pct"] == {
        "1.5x": 0.0, "2.0x": 0.0, "3.0x": 0.0, "4.0x": 0.0}
    assert rows[40]["stage2_share_pct"] == pytest.approx(
        {"1.5x": 85.10, "2.0x": 75.76, "3.0x": 30.25, "4.0x": 3.32})
    # governance reading: threshold monotonically LOWERS the Stage-2 share
    t40 = rows[40]["stage2_share_pct"]
    assert t40["1.5x"] > t40["2.0x"] > t40["3.0x"] > t40["4.0x"]


def test_policy_weights_table_contract(client):
    n_log_before = _n_audit_lines()
    body = client.get("/api/policy/weights_table").json()
    assert set(body) == {"amounts_in", "scenario_totals", "weight_sets"}
    assert body["amounts_in"] == "USD"

    totals = {s["name"]: s for s in body["scenario_totals"]}
    assert set(totals) == {"up", "base", "down"}
    for s in totals.values():
        assert set(s) == {"name", "allowance", "coverage"}
    assert totals["down"]["allowance"] > totals["base"]["allowance"] \
        > totals["up"]["allowance"]

    sets = {w["id"]: w for w in body["weight_sets"]}
    assert set(sets) == {"adopted", "equal_thirds", "downside_tilt"}
    for w in sets.values():
        assert set(w) == {"id", "label", "weights", "weighted_allowance",
                          "coverage", "jensen_ratio", "delta_vs_adopted_pct"}
        assert set(w["weights"]) == {"up", "base", "down"}
        assert sum(w["weights"].values()) == pytest.approx(1.0)

    assert sets["adopted"]["weights"] == {"up": 0.25, "base": 0.5, "down": 0.25}
    assert sets["adopted"]["delta_vs_adopted_pct"] == pytest.approx(0.0, abs=1e-6)
    assert sets["equal_thirds"]["weights"]["up"] == pytest.approx(1 / 3)
    assert sets["downside_tilt"]["weights"] == {
        "up": 0.15, "base": 0.35, "down": 0.5}
    # downside tilt puts more weight on the worst scenario -> higher allowance
    assert sets["downside_tilt"]["weighted_allowance"] \
        > sets["adopted"]["weighted_allowance"]

    # documented governance behaviour: 3 audit lines appended (one per set)
    assert _n_audit_lines() == n_log_before + 3


def test_exhibits_list_contract(client):
    body = client.get("/api/exhibits/list").json()
    assert set(body) == {"exhibits"}
    items = body["exhibits"]
    assert len(items) == 17
    ids = [e["id"] for e in items]
    assert len(ids) == len(set(ids))          # ids are unique
    for e in items:
        assert set(e) == {"id", "title", "png_url", "caption"}
        assert e["png_url"].startswith("/static/exhibits/")
        assert e["png_url"].endswith(".png")

    by_id = {e["id"]: e for e in items}
    assert by_id["hazard_age_baseline"]["png_url"] == \
        "/static/exhibits/hazard/age_baseline.png"
    assert by_id["lgd_distribution"]["png_url"] == \
        "/static/exhibits/lgd/lgd_distribution.png"
    assert by_id["staging_stage2_sensitivity"]["png_url"] == \
        "/static/exhibits/staging/stage2_sensitivity.png"
    assert by_id["vasicek_credit_cycle"]["png_url"] == \
        "/static/exhibits/vasicek/credit_cycle.png"


def test_static_exhibits_are_actually_served(client):
    """Every png_url the previous test asserted resolves to a real file."""
    r = client.get("/static/exhibits/hazard/age_baseline.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


# ---------------------------------------------------------------------------
# Section 4: /api/agent/interpret (LLM mocked, never called for real)
# ---------------------------------------------------------------------------

_RERUN_RESULT = {
    "tool": "rerun_ecl", "segment": "all",
    "weighted_allowance": 34046377.82,
    "headline": ("segment 'all' (entire non-payoff book at the t=60 "
                "reporting date): 7,849 loans, balance $1,673.7m, "
                "scenario-weighted allowance $34.0m (100.0% of the book "
                "allowance), coverage 2.03%"),
    "tool_call_id": "tc-000123",
}

_DOCS_RESULT = {
    "tool": "query_model_docs", "question": "what is SICR?",
    "passages": [{"source": "wiki", "citation": "pages/staging-model.md#Staging Model",
                 "text": "SICR triggers a move to Stage 2 lifetime ECL."}],
    "reading_list": [],
    "headline": "1 documentation passage(s) found",
    "tool_call_id": "tc-000124",
}


def test_interpret_llm_success_is_grounded(client, monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_narrate",
        lambda result: ("The allowance is $34.0m across the book.", "mock-model"))
    r = client.post("/api/agent/interpret",
                    json={"tool": "rerun_ecl", "result": _RERUN_RESULT})
    assert r.status_code == 200
    body = r.json()
    assert body["interpretation"] == "The allowance is $34.0m across the book."
    assert body["grounded"] is True
    assert body["mode"] == "llm"


def test_interpret_llm_hallucination_falls_back_ungrounded(client, monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_narrate",
        lambda result: ("The allowance is a shocking $999.0m!", "mock-model"))
    r = client.post("/api/agent/interpret",
                    json={"tool": "rerun_ecl", "result": _RERUN_RESULT})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is False
    assert body["mode"] == "template_number_check_failed"
    assert "tc-000123" in body["interpretation"]      # deterministic fallback
    assert _RERUN_RESULT["headline"] in body["interpretation"]


def test_interpret_llm_error_falls_back_ungrounded(client, monkeypatch):
    def boom(result):
        raise RuntimeError("both models failed")

    monkeypatch.setattr(graph, "_llm_narrate", boom)
    r = client.post("/api/agent/interpret",
                    json={"tool": "rerun_ecl", "result": _RERUN_RESULT})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is False
    assert body["mode"].startswith("template_llm_error:")


def test_interpret_docs_route_uses_citation_check(client, monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_narrate_docs",
        lambda result: (
            "SICR triggers a move to Stage 2 lifetime ECL "
            "[pages/staging-model.md#Staging Model].", "mock-model"))
    r = client.post("/api/agent/interpret",
                    json={"tool": "query_model_docs", "result": _DOCS_RESULT})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is True
    assert "[pages/staging-model.md#Staging Model]" in body["interpretation"]


def test_interpret_rejects_unknown_tool(client):
    r = client.post("/api/agent/interpret",
                    json={"tool": "does_not_exist", "result": {}})
    assert r.status_code == 422


def test_interpret_rejects_result_missing_required_fields(client):
    r = client.post("/api/agent/interpret",
                    json={"tool": "rerun_ecl", "result": {"foo": 1}})
    assert r.status_code == 422
    assert "missing required field" in r.json()["detail"]

    r2 = client.post("/api/agent/interpret",
                     json={"tool": "query_model_docs",
                           "result": {"question": "x"}})
    assert r2.status_code == 422


# ---------------------------------------------------------------------------
# Section 5: UI v3 AI-explain question-prefix conventions (docs §5)
#
# Both prefixes are pure wire-text conventions on top of the EXISTING
# POST /api/agent/ask — the router must see them as ordinary free text.
# Exercised against the real agent.graph router (agent.graph.run_agent),
# exactly like tests/test_router.py and tests/test_tier3.py: the LLM seams
# (_llm_route / _llm_narrate_docs / _chat_once) are monkeypatched, the graph
# wiring is real. The point of these tests is NOT to pin one "correct"
# route — it's that a bracketed-tag, figure-recap-laden question never
# crashes the router and always lands on a sensible route: the Tier-3
# documentation tool (a real LLM would plausibly read "explain this
# exhibit" as a methodology question) or a clean refusal — never an
# unhandled exception, and never a silently wrong Tier-1 tool call the
# router wasn't told to make.
# ---------------------------------------------------------------------------

_EXPLAIN_PANEL_QUESTION = (
    "[explain:waterfall t0=59 t1=60] Exhibit 1 — Allowance bridge: opening "
    "$30.0m, stage migration +1.0m, remeasurement +2.0m, derecognitions "
    "-1.5m, new loans +0.5m, closing $32.0m. What should I take from this?"
)
_EXPLAIN_SELECTION_QUESTION = (
    "Explain, in the context of the Executive Overview tab: "
    '"scenario-weighted allowance is $34.0m"'
)


@pytest.fixture
def _no_network_llm(monkeypatch, tmp_path):
    """Guard against any real network call, and keep the audit trail clean
    (mirrors tests/test_router.py's `_offline` fixture)."""
    def _no_net(model, messages):
        raise AssertionError("network LLM call attempted in pytest")
    monkeypatch.setattr(graph, "_chat_once", _no_net)
    monkeypatch.setattr(graph, "RUNS_LOG_PATH", tmp_path / "agent_runs.jsonl")


def _mock_docs_route(monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_route",
        lambda question: (json.dumps({"route": "query_model_docs", "args": {}}),
                          "mock-router"))
    monkeypatch.setattr(
        graph, "_llm_narrate_docs",
        lambda result: (f"Per {result['passages'][0]['citation']}, that is "
                        "the documented read.", "mock-narrator"))


def _mock_refuse_route(monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_route",
        lambda question: (json.dumps({"route": "REFUSE", "args": {}}),
                          "mock-router"))


@pytest.mark.parametrize("question", [_EXPLAIN_PANEL_QUESTION, _EXPLAIN_SELECTION_QUESTION])
def test_explain_prefix_routes_to_docs_without_crashing(question, monkeypatch, _no_network_llm):
    _mock_docs_route(monkeypatch)
    final = graph.run_agent(question)          # must not raise
    assert final["route"] == "query_model_docs"
    assert [e["node"] for e in final["trace"]] == \
        ["router", "query_model_docs", "narrator"]
    assert final["answer"]                      # never blank


@pytest.mark.parametrize("question", [_EXPLAIN_PANEL_QUESTION, _EXPLAIN_SELECTION_QUESTION])
def test_explain_prefix_can_refuse_cleanly_without_crashing(question, monkeypatch, _no_network_llm):
    _mock_refuse_route(monkeypatch)
    final = graph.run_agent(question)          # must not raise
    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == ["router", "refusal"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _n_audit_lines() -> int:
    p = Path(tools.LOG_PATH)
    if not p.exists():
        return 0
    return len([ln for ln in p.read_text().splitlines() if ln.strip()])
