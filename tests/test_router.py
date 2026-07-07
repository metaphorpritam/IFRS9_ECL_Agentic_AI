"""Tests for agent/graph.py — the LangGraph router with the refusal path.

Everything here is OFFLINE: ``_chat_once`` is stubbed to raise in an
autouse fixture, so any code path that would touch OpenRouter fails the
test loudly instead of making a network call. The LLM seams
(``_llm_route`` / ``_llm_narrate``) are monkeypatched with canned outputs,
and the four TIER1_TOOLS registry entries are monkeypatched with recording
fakes returning realistic canned results — the graph wiring is real, the
heavy engine never builds.

Contracts:
  1. ROUTING: twelve canned questions land on the right node — nine on the
     four tools (with pydantic-validated, default-materialised args), three
     MUST refuse. Trace records the node sequence.
  2. NEVER GUESS: unparseable router JSON, unknown routes, argument
     validation failures (out-of-bound shock, missing required arg) and a
     dead router LLM all collapse to the fixed refusal — the tool is never
     called.
  3. NARRATION GUARD: a narration containing any number absent from the
     tool result is discarded for the deterministic engine headline; a
     faithful narration passes; a narrator API failure also falls back.
  4. FALLBACK MODEL: the primary model erroring routes the same messages to
     FALLBACK_MODEL.
  5. AUDIT: every run appends {ts, question, route, answer, trace} to
     agent_runs.jsonl (redirected here).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import agent.graph as graph

MOCK_ROUTER_MODEL = "mock-router"
MOCK_NARRATOR_MODEL = "mock-narrator"


# ---------------------------------------------------------------------------
# canned tool results (realistic shapes; numbers are arbitrary but coherent)
# ---------------------------------------------------------------------------

CANNED_RESULTS = {
    "shock_macro": {
        "tool": "shock_macro", "var": "UER", "shock": 2.0,
        "shape": "parallel",
        "baseline_allowance": 30489000.0, "shocked_allowance": 41210000.0,
        "delta": 10721000.0, "delta_pct": 35.2,
        "baseline_coverage": 0.0116, "coverage": 0.0157,
        "amounts_in": "USD",
        "headline": ("UER +2pp (parallel) coherent shock of the base "
                     "scenario: reported allowance $30.5m -> $41.2m "
                     "(delta +10.7m, +35.2%), shocked coverage 1.57%"),
        "tool_call_id": "tc-000101",
    },
    "reweight_scenarios": {
        "tool": "reweight_scenarios",
        "weights": {"up": 0.34, "base": 0.33, "down": 0.33},
        "weighted_allowance": 34600000.0,
        "allowance_at_average_path": 33400000.0,
        "jensen_ratio": 1.036, "coverage": 0.0131,
        "adopted_weighted_allowance": 34000000.0,
        "delta_vs_adopted_pct": 1.8, "amounts_in": "USD",
        "headline": ("weights up/base/down = 0.34/0.33/0.33: weighted "
                     "allowance $34.6m (+1.8% vs adopted 25/50/25 $34.0m); "
                     "Jensen ratio 1.036x vs $33.4m at the averaged path"),
        "tool_call_id": "tc-000102",
    },
    "rerun_ecl": {
        "tool": "rerun_ecl", "segment": "stage2", "n_loans": 812,
        "balance": 98000000.0, "weighted_allowance": 12300000.0,
        "coverage": 0.1255, "share_of_book_allowance_pct": 36.2,
        "amounts_in": "USD",
        "headline": ("segment 'stage2' (Stage 2 loans): 812 loans, balance "
                     "$98.0m, scenario-weighted allowance $12.3m (36.2% of "
                     "the book allowance), coverage 12.55%"),
        "tool_call_id": "tc-000103",
    },
    "decompose_waterfall": {
        "tool": "decompose_waterfall", "t0": 20, "t1": 40,
        "period_t0": "2005Q1", "period_t1": "2010Q1",
        "opening_allowance": 8100000.0, "closing_allowance": 52400000.0,
        "components": [
            {"component": "opening", "amount": 8100000.0,
             "n_loans": 4093, "kind": "level"},
            {"component": "remeasurement", "amount": 39600000.0,
             "n_loans": 3512, "kind": "delta"},
            {"component": "closing", "amount": 52400000.0,
             "n_loans": 6120, "kind": "level"},
        ],
        "identity_gap": 0.0, "amounts_in": "USD",
        "headline": ("allowance waterfall t=20 (2005Q1) -> t=40 (2010Q1): "
                     "opening $8.1m, remeasurement +39.6m, closing $52.4m"),
        "tool_call_id": "tc-000104",
    },
}


# ---------------------------------------------------------------------------
# the twelve canned questions: what the (mocked) router says, what must run
# ---------------------------------------------------------------------------

# question -> (router JSON payload, expected route, expected VALIDATED args)
CANNED = {
    "What happens to the allowance if unemployment rises 2 percentage "
    "points?": (
        {"route": "shock_macro", "args": {"var": "UER", "shock": 2.0}},
        "shock_macro",
        {"var": "UER", "shock": 2.0, "shape": "parallel"}),
    "Shock quarterly house-price growth up 1pp but let it revert.": (
        {"route": "shock_macro",
         "args": {"var": "HPI", "shock": 1.0, "shape": "peak_revert"}},
        "shock_macro",
        {"var": "HPI", "shock": 1.0, "shape": "peak_revert"}),
    "GDP growth falls 1.5pp per quarter — what does it do to the ECL?": (
        {"route": "shock_macro", "args": {"var": "GDP", "shock": -1.5}},
        "shock_macro",
        {"var": "GDP", "shock": -1.5, "shape": "parallel"}),
    "Reweight the scenarios to 40% up, 40% base, 20% downside.": (
        {"route": "reweight_scenarios",
         "args": {"w_up": 0.4, "w_base": 0.4, "w_down": 0.2}},
        "reweight_scenarios",
        {"w_up": 0.4, "w_base": 0.4, "w_down": 0.2}),
    "What if we put roughly equal weight on all three scenarios?": (
        {"route": "reweight_scenarios",
         "args": {"w_up": 0.34, "w_base": 0.33, "w_down": 0.33}},
        "reweight_scenarios",
        {"w_up": 0.34, "w_base": 0.33, "w_down": 0.33}),
    "How much of the allowance sits in Stage 2?": (
        {"route": "rerun_ecl", "args": {"segment": "stage2"}},
        "rerun_ecl", {"segment": "stage2"}),
    "Show me the ECL for the high-LTV loans.": (
        {"route": "rerun_ecl", "args": {"segment": "high_ltv"}},
        "rerun_ecl", {"segment": "high_ltv"}),
    "Explain the allowance movement between t=20 and t=40.": (
        {"route": "decompose_waterfall", "args": {"t0": 20, "t1": 40}},
        "decompose_waterfall", {"t0": 20, "t1": 40}),
    "Walk me through the allowance waterfall.": (
        {"route": "decompose_waterfall", "args": {}},
        "decompose_waterfall", {"t0": 20, "t1": 40}),   # defaults filled
    # ---- the three that MUST refuse -------------------------------------
    "What's your view on Bitcoin as a hedge for our book?": (
        {"route": "REFUSE", "args": {}}, "REFUSE", {}),
    "What will the Fed do with rates next year?": (
        {"route": "REFUSE", "args": {}}, "REFUSE", {}),
    "Please compute 123 * 456 for me.": (
        {"route": "REFUSE", "args": {}}, "REFUSE", {}),
}

TOOL_QUESTIONS = [(q, v[1], v[2]) for q, v in CANNED.items()
                  if v[1] != "REFUSE"]
REFUSE_QUESTIONS = [q for q, v in CANNED.items() if v[1] == "REFUSE"]

assert len(CANNED) == 12 and len(REFUSE_QUESTIONS) == 3


# ---------------------------------------------------------------------------
# fixtures — offline by construction
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _offline(monkeypatch, tmp_path):
    """No network, no real audit files, ever."""
    def _no_net(model, messages):
        raise AssertionError("network LLM call attempted in pytest")
    monkeypatch.setattr(graph, "_chat_once", _no_net)
    monkeypatch.setattr(graph, "RUNS_LOG_PATH",
                        tmp_path / "agent_runs.jsonl")


@pytest.fixture
def fake_tools(monkeypatch):
    """Replace the four registry tools with recording fakes."""
    calls: dict[str, list[dict]] = {n: [] for n in CANNED_RESULTS}

    def make(name):
        def fake(**kwargs):
            calls[name].append(kwargs)
            return dict(CANNED_RESULTS[name])
        return fake

    for name in CANNED_RESULTS:
        monkeypatch.setitem(graph.TIER1_TOOLS, name, make(name))
    return calls


@pytest.fixture
def canned_router(monkeypatch):
    """Router LLM answering the twelve canned questions with strict JSON."""
    def fake(question):
        return json.dumps(CANNED[question][0]), MOCK_ROUTER_MODEL
    monkeypatch.setattr(graph, "_llm_route", fake)


@pytest.fixture
def headline_narrator(monkeypatch):
    """Narrator LLM that echoes the engine headline (all numbers legal)."""
    def fake(result):
        return f"Engine verdict: {result['headline']}", MOCK_NARRATOR_MODEL
    monkeypatch.setattr(graph, "_llm_narrate", fake)


def _set_router(monkeypatch, payload):
    """Router seam returning a fixed payload (str) or raising (Exception)."""
    def fake(question):
        if isinstance(payload, Exception):
            raise payload
        return payload, MOCK_ROUTER_MODEL
    monkeypatch.setattr(graph, "_llm_route", fake)


def _runs_log() -> list[dict]:
    p = Path(graph.RUNS_LOG_PATH)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


# ---------------------------------------------------------------------------
# 1. routing: nine tool questions, three refusals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question,route,expected_args", TOOL_QUESTIONS)
def test_tool_questions_route_and_execute(question, route, expected_args,
                                          fake_tools, canned_router,
                                          headline_narrator):
    final = graph.run_agent(question)
    assert final["route"] == route
    # pydantic-validated args (defaults materialised) hit the tool verbatim
    assert fake_tools[route] == [expected_args]
    assert final["tool_args"] == expected_args
    # narrator ran on the tool result and its numbers passed the check
    assert final["answer"] == \
        f"Engine verdict: {CANNED_RESULTS[route]['headline']}"
    assert [e["node"] for e in final["trace"]] == ["router", route,
                                                   "narrator"]
    assert final["trace"][1]["tool_call_id"] == \
        CANNED_RESULTS[route]["tool_call_id"]
    assert final["trace"][2]["number_check_passed"] is True
    # no other tool fired
    assert sum(len(v) for v in fake_tools.values()) == 1


@pytest.mark.parametrize("question", REFUSE_QUESTIONS)
def test_out_of_scope_questions_refuse(question, fake_tools, canned_router,
                                       headline_narrator):
    final = graph.run_agent(question)
    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == ["router", "refusal"]
    # THE point: no engine tool ever ran
    assert all(v == [] for v in fake_tools.values())


def test_refusal_message_names_all_four_families_and_offers_extension():
    for name in graph.TOOL_ROUTES:
        assert name in graph.REFUSAL_MESSAGE
    assert "outside my validated scope" in graph.REFUSAL_MESSAGE
    assert "extend" in graph.REFUSAL_MESSAGE


# ---------------------------------------------------------------------------
# 2. never guess: malformed router output / args collapse to refusal
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,detail_fragment", [
    # out-of-bound shock (pydantic bound: |UER| <= 10pp)
    (json.dumps({"route": "shock_macro",
                 "args": {"var": "UER", "shock": 99.0}}),
     "invalid arguments for shock_macro"),
    # missing required argument
    (json.dumps({"route": "shock_macro", "args": {"var": "UER"}}),
     "invalid arguments for shock_macro"),
    # extra argument (extra='forbid')
    (json.dumps({"route": "rerun_ecl",
                 "args": {"segment": "all", "sneaky": 1}}),
     "invalid arguments for rerun_ecl"),
    # weights that do not sum to 1
    (json.dumps({"route": "reweight_scenarios",
                 "args": {"w_up": 0.5, "w_base": 0.5, "w_down": 0.5}}),
     "invalid arguments for reweight_scenarios"),
    # inverted waterfall snapshots
    (json.dumps({"route": "decompose_waterfall",
                 "args": {"t0": 40, "t1": 20}}),
     "invalid arguments for decompose_waterfall"),
    # unknown route name
    (json.dumps({"route": "run_dfast", "args": {}}), "unknown route"),
    # args not an object
    (json.dumps({"route": "rerun_ecl", "args": [1, 2]}), "not an object"),
    # non-JSON prose
    ("I think you should call shock_macro with a big shock.",
     "unparseable router output"),
    # truncated JSON
    ('{"route": "shock_macro", "args": {"var": "UER"',
     "unparseable router output"),
])
def test_bad_router_output_refuses_without_touching_tools(
        payload, detail_fragment, fake_tools, headline_narrator,
        monkeypatch):
    _set_router(monkeypatch, payload)
    final = graph.run_agent("any question")
    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert detail_fragment in final["trace"][0]["detail"]
    assert all(v == [] for v in fake_tools.values())


def test_router_llm_unavailable_refuses(fake_tools, headline_narrator,
                                        monkeypatch):
    _set_router(monkeypatch, RuntimeError("both models down"))
    final = graph.run_agent("What if unemployment rises 2pp?")
    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert "router LLM unavailable" in final["trace"][0]["detail"]
    assert all(v == [] for v in fake_tools.values())


def test_router_json_in_code_fence_is_parsed(fake_tools, headline_narrator,
                                             monkeypatch):
    fenced = ('```json\n'
              + json.dumps({"route": "rerun_ecl",
                            "args": {"segment": "stage3"}})
              + '\n```')
    _set_router(monkeypatch, fenced)
    final = graph.run_agent("stage 3 allowance?")
    assert final["route"] == "rerun_ecl"
    assert fake_tools["rerun_ecl"] == [{"segment": "stage3"}]


# ---------------------------------------------------------------------------
# 3. narration guard: foreign numbers are discarded for the engine headline
# ---------------------------------------------------------------------------

def test_narration_with_foreign_number_falls_back_to_headline(
        fake_tools, canned_router, monkeypatch):
    def liar(result):
        return ("The allowance rises to $999.9m, a catastrophic move.",
                MOCK_NARRATOR_MODEL)
    monkeypatch.setattr(graph, "_llm_narrate", liar)
    q = ("What happens to the allowance if unemployment rises 2 "
         "percentage points?")
    final = graph.run_agent(q)
    res = CANNED_RESULTS["shock_macro"]
    assert final["answer"] == graph.deterministic_narration(res)
    assert res["headline"] in final["answer"]
    assert final["trace"][2]["mode"] == "template_number_check_failed"
    assert final["trace"][2]["number_check_passed"] is False


def test_faithful_narration_passes_the_number_check(
        fake_tools, canned_router, monkeypatch):
    text = ("Under a +2pp unemployment shock the reported allowance rises "
            "from $30.5m to $41.2m (+35.2%); coverage moves from 1.16% "
            "to 1.57%.")
    monkeypatch.setattr(graph, "_llm_narrate",
                        lambda result: (text, MOCK_NARRATOR_MODEL))
    q = ("What happens to the allowance if unemployment rises 2 "
         "percentage points?")
    final = graph.run_agent(q)
    assert final["answer"] == text
    assert final["trace"][2]["mode"] == "llm"


def test_narrator_llm_error_falls_back_to_headline(fake_tools,
                                                   canned_router,
                                                   monkeypatch):
    def dead(result):
        raise RuntimeError("narrator down")
    monkeypatch.setattr(graph, "_llm_narrate", dead)
    final = graph.run_agent("How much of the allowance sits in Stage 2?")
    assert final["answer"] == \
        graph.deterministic_narration(CANNED_RESULTS["rerun_ecl"])
    assert final["trace"][2]["mode"].startswith("template_llm_error")


def test_tool_exception_yields_honest_no_numbers_answer(canned_router,
                                                        headline_narrator,
                                                        monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("engine exploded")
    monkeypatch.setitem(graph.TIER1_TOOLS, "rerun_ecl", boom)
    final = graph.run_agent("How much of the allowance sits in Stage 2?")
    assert final["trace"][1]["status"] == "error"
    assert "failed" in final["answer"]
    assert "no numbers" in final["answer"]
    assert final["trace"][2]["mode"] == "tool_error"


# unit tests of the guard itself ---------------------------------------------

def test_number_check_accepts_display_transforms():
    res = CANNED_RESULTS["shock_macro"]
    # $m rendering of a USD leaf, % rendering of a fraction, exact leaves
    assert graph.narration_numbers_ok(
        "allowance $41.2m, delta +35.2%, coverage 1.57%", res)
    # sign-insensitive: 'fell by $2.8m' vs a negative delta leaf
    assert graph.narration_numbers_ok(
        "the allowance fell by $2.8m",
        {"delta": -2800000.0, "headline": "h", "tool_call_id": "tc-1"})
    # period labels quoted from result strings
    assert graph.narration_numbers_ok(
        "between 2005Q1 and 2010Q1",
        CANNED_RESULTS["decompose_waterfall"])
    # a no-number narration is trivially fine
    assert graph.narration_numbers_ok("the allowance barely moved", res)


def test_number_check_rejects_foreign_or_recomputed_numbers():
    res = CANNED_RESULTS["shock_macro"]
    assert not graph.narration_numbers_ok("allowance hits $999.9m", res)
    # LLM 'arithmetic': a made-up ratio not present in the result
    assert not graph.narration_numbers_ok(
        "that is a 1.351x increase", res)


# ---------------------------------------------------------------------------
# 4. model fallback: primary API error -> FALLBACK_MODEL, same messages
# ---------------------------------------------------------------------------

def test_call_llm_falls_back_to_secondary_model(monkeypatch):
    attempted = []

    def flaky(model, messages):
        attempted.append(model)
        if model == graph.PRIMARY_MODEL:
            raise RuntimeError("primary 502")
        return json.dumps({"route": "rerun_ecl", "args": {"segment": "all"}})

    monkeypatch.setattr(graph, "_chat_once", flaky)
    decision = graph.decide_route("whole-book allowance?")
    assert attempted == [graph.PRIMARY_MODEL, graph.FALLBACK_MODEL]
    assert decision["route"] == "rerun_ecl"
    assert decision["model"] == graph.FALLBACK_MODEL


def test_call_llm_raises_when_both_models_fail(monkeypatch):
    def dead(model, messages):
        raise RuntimeError(f"{model} down")
    monkeypatch.setattr(graph, "_chat_once", dead)
    with pytest.raises(RuntimeError):
        graph._call_llm([{"role": "user", "content": "x"}])
    # and decide_route turns that into a refusal, not a crash
    assert graph.decide_route("anything")["route"] == "REFUSE"


# ---------------------------------------------------------------------------
# 5. audit: agent_runs.jsonl gets one full-trace line per run
# ---------------------------------------------------------------------------

def test_every_run_is_audited_with_full_trace(fake_tools, canned_router,
                                              headline_narrator):
    q_tool = "How much of the allowance sits in Stage 2?"
    q_refuse = "Please compute 123 * 456 for me."
    graph.run_agent(q_tool)
    graph.run_agent(q_refuse)
    log = _runs_log()
    assert len(log) == 2
    for entry in log:
        assert set(entry) == {"ts", "question", "route", "answer", "trace"}
    assert log[0]["question"] == q_tool
    assert log[0]["route"] == "rerun_ecl"
    assert [e["node"] for e in log[0]["trace"]] == ["router", "rerun_ecl",
                                                    "narrator"]
    assert log[1]["route"] == "REFUSE"
    assert log[1]["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in log[1]["trace"]] == ["router", "refusal"]
