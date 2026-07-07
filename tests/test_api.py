"""Tests for app/api/main.py — the FastAPI backend over the frozen engine.

Contracts:
  1. PUBLISHED-NUMBER IDENTITY: GET /api/ecl/summary reproduces
     outputs/scenario_ecl/scenario_ecl_summary.csv — weighted allowance
     ~$34.0m at the adopted 25/50/25 weights, Jensen ~1.035x — because the
     endpoint reads the same warm engine caches the Day-3 exhibit was built
     from.
  2. WATERFALL IDENTITY: GET /api/ecl/waterfall components ('delta' kinds)
     sum exactly to closing - opening; identity_gap ~ 0.
  3. VALIDATION FIRST: malformed bodies/params 422 BEFORE any engine code
     runs (pydantic arg models are the API schema — bad vars, out-of-bound
     shocks, weights that do not sum to 1, inverted snapshots, extra keys).
  4. AGENT PLUMBING (LLM mocked — no network anywhere in this file):
     /api/agent/ask returns {answer, route, trace} whose trace ends in a
     narrator or refusal node; the deterministic fallback router refuses
     out-of-scope questions with 'outside my validated scope' (refusal is a
     FEATURE); one-question-at-a-time gives 429; /api/agent/stream replays
     the latest trace as SSE data: lines.
  5. STATIC UI: / serves the built SPA (or the graceful 'UI not built'
     page) — either way an HTML page titled 'IFRS 9 ECL Copilot'.

The module-scoped TestClient triggers the lifespan warm-up once (joblib
warm ~9s; shared process-global state with tests/test_tools.py when run in
the same session). The audit trail is redirected to a tmp dir, mirroring
tests/test_tools.py.
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import agent.tools_tier1 as tools
import app.api.main as main

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_CSV = ROOT / "outputs" / "scenario_ecl" / "scenario_ecl_summary.csv"

#: published Day-3 exhibit: per-scenario allowance ($m) + adopted weights
PUBLISHED = pd.read_csv(SUMMARY_CSV).set_index("scenario")
PUB_WEIGHTED_USD = float(
    (PUBLISHED["weight"] * PUBLISHED["allowance_m"]).sum() * 1e6)


@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """Keep the real outputs/agent_log/ audit trail clean during tests."""
    old = tools.LOG_PATH
    tools.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools.LOG_PATH = old


@pytest.fixture(scope="module")
def client():
    """One TestClient for the module: lifespan warm-up runs exactly once.

    AGENT_ASK is forced to None so /ask exercises the deterministic
    OFFLINE fallback router unless a test monkeypatches a mock — even if a
    real LangGraph router module exists in the repo, no test here may ever
    make a network call.
    """
    old_agent = main.AGENT_ASK
    with TestClient(main.app) as c:
        main.AGENT_ASK = None
        yield c
    main.AGENT_ASK = old_agent


# ---------------------------------------------------------------------------
# health + static UI
# ---------------------------------------------------------------------------

def test_health_reports_warm_engine(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["engine_warm"] is True
    assert isinstance(body["warm_up_seconds"], (int, float))


def test_root_serves_ui_or_graceful_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "IFRS 9 ECL Copilot" in r.text


def test_unknown_api_path_is_not_swallowed_by_the_spa(client):
    assert client.get("/api/nonexistent").status_code == 404
    # POSTing an unknown tool cannot hit the engine: 404 (no mount) or 405
    # (StaticFiles mount refuses non-GET) — never 200
    assert client.post("/api/tools/does_not_exist",
                       json={}).status_code in (404, 405)


# ---------------------------------------------------------------------------
# 1. GET /api/ecl/summary — published-number identity
# ---------------------------------------------------------------------------

def test_summary_reproduces_published_numbers(client):
    body = client.get("/api/ecl/summary").json()

    # weighted allowance ~ $34.0m (CSV identity, then the headline number)
    assert body["weighted_allowance"] == pytest.approx(PUB_WEIGHTED_USD,
                                                       rel=1e-2)
    assert 33.0e6 < body["weighted_allowance"] < 35.0e6
    assert body["jensen_ratio"] == pytest.approx(1.035, abs=0.02)
    assert body["weights"] == {"up": 0.25, "base": 0.5, "down": 0.25}
    assert body["as_of"] == {"t": 60, "period": "2015Q1"}
    assert body["amounts_in"] == "USD"

    # scenario table matches the published per-scenario allowances
    scen = {s["name"]: s for s in body["scenarios"]}
    assert set(scen) == {"up", "base", "down"}
    for name in ("up", "base", "down"):
        assert scen[name]["allowance"] == pytest.approx(
            float(PUBLISHED.loc[name, "allowance_m"]) * 1e6, rel=1e-2)
        assert scen[name]["coverage"] == pytest.approx(
            scen[name]["allowance"] / body["balance"], rel=1e-9)
    assert scen["down"]["allowance"] > scen["base"]["allowance"] \
        > scen["up"]["allowance"]

    # coverage and stage mix are internally consistent
    assert body["coverage"] == pytest.approx(
        body["weighted_allowance"] / body["balance"], rel=1e-9)
    mix = body["stage_mix"]
    assert set(mix) == {"stage1", "stage2", "stage3"}
    assert sum(mix[s]["allowance"] for s in mix) == pytest.approx(
        body["weighted_allowance"], rel=1e-9)
    assert sum(mix[s]["n_loans"] for s in mix) == body["n_loans"]


# ---------------------------------------------------------------------------
# 2. GET /api/ecl/waterfall — identity + validation
# ---------------------------------------------------------------------------

def test_waterfall_components_sum_to_closing(client):
    body = client.get("/api/ecl/waterfall",
                      params={"t0": 20, "t1": 40}).json()
    assert (body["t0"], body["t1"]) == (20, 40)
    assert (body["period_t0"], body["period_t1"]) == ("2005Q1", "2010Q1")

    comp = {c["component"]: c for c in body["components"]}
    deltas = sum(c["amount"] for c in body["components"]
                 if c["kind"] == "delta")
    assert comp["opening"]["amount"] + deltas == pytest.approx(
        comp["closing"]["amount"], rel=1e-9)
    assert body["identity_gap"] == pytest.approx(0.0, abs=1e-6)
    assert body["opening_allowance"] == comp["opening"]["amount"]
    assert body["closing_allowance"] == comp["closing"]["amount"]
    assert body["tool_call_id"].startswith("tc-")


def test_waterfall_defaults_match_explicit_20_40(client):
    default = client.get("/api/ecl/waterfall").json()
    explicit = client.get("/api/ecl/waterfall",
                          params={"t0": 20, "t1": 40}).json()
    assert default["opening_allowance"] == explicit["opening_allowance"]
    assert default["closing_allowance"] == explicit["closing_allowance"]


@pytest.mark.parametrize("params", [
    {"t0": 40, "t1": 20},      # inverted
    {"t0": 20, "t1": 20},      # not strictly increasing
    {"t0": 0, "t1": 40},       # below the panel clock
    {"t0": 20, "t1": 61},      # beyond t=60
    {"t0": "abc", "t1": 40},   # not an int
])
def test_waterfall_rejects_bad_snapshots(client, params):
    assert client.get("/api/ecl/waterfall", params=params).status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /api/exhibits/credit_cycle
# ---------------------------------------------------------------------------

def test_credit_cycle_series(client):
    body = client.get("/api/exhibits/credit_cycle").json()
    assert body["n_quarters"] == 60
    assert body["rho"] == pytest.approx(0.0227, abs=0.01)
    pts = body["points"]
    assert pts[0]["calendar"] == "2000Q2"        # t=1 calendar mapping
    assert pts[-1]["calendar"] == "2015Q1"
    assert all(math.isfinite(p["z"]) for p in pts)
    assert all(0.0 < p["pit_pd"] < 1.0 for p in pts)


# ---------------------------------------------------------------------------
# 4. POST /api/tools/* — delegation + validation-first
# ---------------------------------------------------------------------------

def test_shock_macro_endpoint_economics_and_audit(client):
    n_log_before = _n_audit_lines()
    r = client.post("/api/tools/shock_macro",
                    json={"var": "UER", "shock": 2.0})
    assert r.status_code == 200
    body = r.json()
    # adverse unemployment shock RAISES the allowance (coherent co-movement)
    assert body["shocked_allowance"] > body["baseline_allowance"]
    assert body["delta"] == pytest.approx(
        body["shocked_allowance"] - body["baseline_allowance"], rel=1e-9)
    assert body["tool_call_id"].startswith("tc-")
    assert set(body["stage_mix"]) == {"stage1", "stage2", "stage3"}
    # exactly one audit line was appended, and it names the tool
    assert _n_audit_lines() == n_log_before + 1
    assert _last_audit_line()["tool"] == "shock_macro"


def test_reweight_endpoint_reproduces_adopted_weights(client):
    r = client.post("/api/tools/reweight_scenarios",
                    json={"w_up": 0.25, "w_base": 0.5, "w_down": 0.25})
    assert r.status_code == 200
    body = r.json()
    assert body["weighted_allowance"] == pytest.approx(PUB_WEIGHTED_USD,
                                                       rel=1e-2)
    assert body["delta_vs_adopted_pct"] == pytest.approx(0.0, abs=1e-9)
    assert body["jensen_ratio"] == pytest.approx(1.035, abs=0.02)


def test_rerun_ecl_endpoint_segment_shares(client):
    r = client.post("/api/tools/rerun_ecl", json={"segment": "stage3"})
    assert r.status_code == 200
    body = r.json()
    assert body["segment"] == "stage3"
    assert 0.0 <= body["share_of_book_allowance_pct"] <= 100.0
    assert body["n_loans"] == body["stage_mix"]["stage3"]["n_loans"]
    assert body["stage_mix"]["stage1"]["n_loans"] == 0


@pytest.mark.parametrize("tool,payload", [
    ("shock_macro", {"var": "FX", "shock": 1.0}),          # unknown var
    ("shock_macro", {"var": "UER", "shock": 50.0}),        # beyond bound
    ("shock_macro", {"var": "UER", "shock": 1.0,
                     "shape": "spike"}),                   # unknown shape
    ("shock_macro", {"var": "UER"}),                       # missing shock
    ("reweight_scenarios", {"w_up": 0.5, "w_base": 0.5,
                            "w_down": 0.5}),               # sums to 1.5
    ("reweight_scenarios", {"w_up": -0.1, "w_base": 0.6,
                            "w_down": 0.5}),               # negative weight
    ("rerun_ecl", {"segment": "stage4"}),                  # unknown segment
    ("decompose_waterfall", {"t0": 40, "t1": 20}),         # inverted
    ("decompose_waterfall", {"t0": 20, "t1": 40,
                             "extra": 1}),                 # extra='forbid'
])
def test_tool_endpoints_422_before_engine(client, tool, payload):
    n_log_before = _n_audit_lines()
    assert client.post(f"/api/tools/{tool}", json=payload).status_code == 422
    # validation failures never reach the engine, so never hit the audit log
    assert _n_audit_lines() == n_log_before


def test_shock_macro_rejects_nan_shock(client):
    r = client.post("/api/tools/shock_macro",
                    content='{"var": "UER", "shock": NaN}',
                    headers={"content-type": "application/json"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. POST /api/agent/ask — mocked router, fallback router, refusal, limits
# ---------------------------------------------------------------------------

def test_ask_with_mocked_router_ends_in_narrator(client, monkeypatch):
    """The LLM router is mocked: /ask returns its narration + trace."""
    def fake_router(question, emit):
        emit({"node": "router", "label": "classify", "route": "rerun_ecl"})
        emit({"node": "tool", "label": "calling rerun_ecl",
              "tool": "rerun_ecl", "args": {"segment": "all"}})
        emit({"node": "narrator", "label": "narrating engine output",
              "answer": "mocked narration of engine-computed numbers"})
        return {"answer": "mocked narration of engine-computed numbers",
                "route": "rerun_ecl"}

    monkeypatch.setattr(main, "AGENT_ASK", fake_router)
    r = client.post("/api/agent/ask",
                    json={"question": "what is the allowance?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "mocked narration of engine-computed numbers"
    assert body["route"] == "rerun_ecl"
    assert [e["node"] for e in body["trace"]] == ["router", "tool",
                                                  "narrator"]


def test_ask_with_mocked_router_refusal(client, monkeypatch):
    def fake_refuser(question, emit):
        emit({"node": "router", "label": "classify", "route": "refusal"})
        emit({"node": "refusal", "label": "out of scope",
              "answer": "outside my validated scope"})
        return {"answer": "outside my validated scope", "route": "refusal"}

    monkeypatch.setattr(main, "AGENT_ASK", fake_refuser)
    body = client.post("/api/agent/ask",
                       json={"question": "write me a poem"}).json()
    assert body["route"] == "refusal"
    assert body["trace"][-1]["node"] == "refusal"


def test_fallback_router_refuses_out_of_scope(client):
    """No LLM, no mock: the deterministic fallback refuses — a FEATURE."""
    assert main.AGENT_ASK is None                    # forced by the fixture
    body = client.post(
        "/api/agent/ask",
        json={"question": "What is the capital of France?"}).json()
    assert body["route"] == "refusal"
    assert "outside my validated scope" in body["answer"]
    assert body["trace"][-1]["node"] == "refusal"


def test_fallback_router_routes_reweight_and_narrates_engine_numbers(client):
    body = client.post(
        "/api/agent/ask",
        json={"question":
              "reweight the scenario weights to 0.25, 0.5, 0.25"}).json()
    assert body["route"] == "reweight_scenarios"
    nodes = [e["node"] for e in body["trace"]]
    assert nodes == ["router", "tool", "narrator"]
    # narration is the engine-built headline + audit ref, never LLM math
    assert "tc-" in body["answer"]
    assert "$" in body["answer"]


@pytest.mark.parametrize("payload", [
    {},                                    # question missing
    {"question": ""},                      # empty
    {"question": "x", "role": "admin"},    # extra key (extra='forbid')
])
def test_ask_rejects_malformed_bodies(client, payload):
    assert client.post("/api/agent/ask", json=payload).status_code == 422


def test_ask_naive_concurrency_limit_gives_429(client):
    assert main._ASK_SEMAPHORE.acquire(blocking=False)
    try:
        r = client.post("/api/agent/ask", json={"question": "anything"})
        assert r.status_code == 429
    finally:
        main._ASK_SEMAPHORE.release()


# ---------------------------------------------------------------------------
# 6. GET /api/agent/stream — SSE replay of the most recent trace
# ---------------------------------------------------------------------------

def test_stream_replays_latest_ask_trace(client, monkeypatch):
    """Drive the SSE route handler directly, bounded.

    The installed starlette TestClient transport runs the ASGI app to
    COMPLETION and buffers the entire body before returning any response
    (testclient.py handle_request -> portal.call(self.app, ...)), so an
    endless SSE stream consumed through client.stream() hangs the suite
    forever. The endpoint is unbounded BY DESIGN (15s keep-alives); the
    test therefore consumes the route's own generator and stops after the
    replayed trace.
    """
    def fake_router(question, emit):
        emit({"node": "router", "label": "classify", "route": "refusal"})
        emit({"node": "refusal", "label": "out of scope",
              "answer": "outside my validated scope"})
        return {"answer": "outside my validated scope", "route": "refusal"}

    monkeypatch.setattr(main, "AGENT_ASK", fake_router)
    assert client.post("/api/agent/ask",
                       json={"question": "poem please"}).status_code == 200

    async def consume_replay(n: int) -> list[dict]:
        resp = await main.agent_stream()
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        out: list[dict] = []
        agen = resp.body_iterator
        try:
            async for chunk in agen:
                if chunk.startswith("data: "):
                    out.append(json.loads(chunk[len("data: "):]))
                    if len(out) >= n:
                        break
        finally:
            await agen.aclose()          # unsubscribes from the broker
        return out

    events = asyncio.run(consume_replay(2))
    assert [e["node"] for e in events] == ["router", "refusal"]
    assert events[1]["answer"] == "outside my validated scope"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _audit_lines() -> list[dict]:
    p = Path(tools.LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines()
            if line.strip()]


def _n_audit_lines() -> int:
    return len(_audit_lines())


def _last_audit_line() -> dict:
    return _audit_lines()[-1]
