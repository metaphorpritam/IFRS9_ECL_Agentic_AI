"""Tests for the REASONED route (agent/graph.py) — reasoned interpretation
of conceptually-relevant questions no fixed tool computes and the docs
retriever does not simply quote verbatim.

Everything here is OFFLINE: ``_chat_once`` is stubbed to raise in an
autouse fixture (belt-and-braces, mirrors tests/test_router.py); the LLM
seams actually exercised are ``_llm_route`` and ``_llm_reason``, both
monkeypatched with canned callables. ``query_model_docs`` is NOT mocked —
retrieval is pure lexical/graph scoring over the real wiki/ +
knowledge/index/ (same pattern as tests/test_tier3.py), so the REASONED
node's grounding passages are real, verifiable citations. The engine's
baseline snapshot (``rerun_ecl(segment="all")``) IS mocked, through the
live ``TIER1_TOOLS`` registry, exactly like tests/test_router.py fakes the
four Tier-1 tools.

Contracts:
  1. THREE-WAY SPLIT: >=3 canned questions per class (computable tool,
     REASONED conceptual — including the motivating interaction-term
     question verbatim, REFUSE) land on the right node/mode.
  2. NUMBER GUARD: an answer with a number absent from the passages, the
     baseline snapshot, and the question triggers exactly one regeneration
     attempt, then a deterministic fallback if still ungrounded; a number
     drawn from the baseline, from a passage, or echoed from the question
     itself passes on the first attempt; a repaired second attempt is
     recorded as such.
  3. UNIT CHECKS: ``reasoned_answer_ok`` and
     ``deterministic_reasoned_fallback`` in isolation.
"""

from __future__ import annotations

import json

import pytest

import agent.graph as graph
import agent.tools_tier1 as tools_tier1

MOTIVATING_QUESTION = (
    "Does the satellite need a UER x HPI interaction, or do the main "
    "effects and momentum already account for the joint stress response?")

REASONED_QUESTIONS = [
    MOTIVATING_QUESTION,
    "Why does the double-trigger LTV x UER coefficient come out negative?",
    "If unemployment and house prices both deteriorate at once, would you "
    "expect the combined hit to default risk to be additive, or worse "
    "than additive?",
]

# (question, canned router payload, expected route)
COMPUTABLE_QUESTIONS = [
    ("What happens to the allowance if unemployment rises 2 percentage "
     "points?",
     {"route": "shock_macro", "args": {"var": "UER", "shock": 2.0}},
     "shock_macro"),
    ("How much of the allowance sits in Stage 2?",
     {"route": "rerun_ecl", "args": {"segment": "stage2"}},
     "rerun_ecl"),
    ("Explain the allowance movement between t=20 and t=40.",
     {"route": "decompose_waterfall", "args": {"t0": 20, "t1": 40}},
     "decompose_waterfall"),
]

REFUSE_QUESTIONS = [
    "What's your view on Bitcoin as a hedge for our book?",
    "What will the Fed do with rates next year?",
    "Please compute 123 * 456 for me.",
]

FAKE_BASELINE = {
    "tool": "rerun_ecl", "segment": "all",
    "segment_definition": "the whole book",
    "weights": {"up": 0.25, "base": 0.5, "down": 0.25},
    "n_loans": 12000, "balance": 500000000.0,
    "weighted_allowance": 34000000.0, "coverage": 0.068,
    "share_of_book_allowance_pct": 100.0,
    "per_scenario_allowance": {"up": 30000000.0, "base": 34000000.0,
                              "down": 40000000.0},
    "stage_mix": {}, "amounts_in": "USD",
    "headline": "segment 'all' (the whole book): 12,000 loans, balance "
               "$500.0m, scenario-weighted allowance $34.0m",
    "tool_call_id": "tc-000200",
}

CANNED_TOOL_RESULTS = {
    "shock_macro": {
        "tool": "shock_macro", "var": "UER", "shock": 2.0,
        "shape": "parallel", "headline": "UER +2pp shock headline",
        "tool_call_id": "tc-000101",
    },
    "rerun_ecl": dict(FAKE_BASELINE, segment="stage2",
                      headline="segment 'stage2' headline",
                      tool_call_id="tc-000103"),
    "decompose_waterfall": {
        "tool": "decompose_waterfall", "t0": 20, "t1": 40,
        "headline": "waterfall t=20 -> t=40 headline",
        "tool_call_id": "tc-000104",
    },
}


# ---------------------------------------------------------------------------
# fixtures — offline by construction
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_network(monkeypatch, tmp_path):
    """Belt-and-braces: any code path that would touch OpenRouter fails
    loudly instead of making a network call."""
    def _no_net(model, messages):
        raise AssertionError("network LLM call attempted in pytest")
    monkeypatch.setattr(graph, "_chat_once", _no_net)
    monkeypatch.setattr(graph, "RUNS_LOG_PATH", tmp_path / "agent_runs.jsonl")


@pytest.fixture(scope="module", autouse=True)
def _redirect_tool_log(tmp_path_factory):
    """query_model_docs / the REASONED node's audit call both go through
    tools_tier1._log_call — redirect its LOG_PATH so pytest never touches
    the real outputs/agent_log/tool_calls.jsonl."""
    old = tools_tier1.LOG_PATH
    tools_tier1.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools_tier1.LOG_PATH = old


@pytest.fixture
def fake_baseline(monkeypatch):
    """Fakes the engine's baseline snapshot the REASONED node reads through
    the live TIER1_TOOLS registry (same monkeypatch pattern as every other
    Tier-1 fake in tests/test_router.py)."""
    def fake(**kwargs):
        return dict(FAKE_BASELINE)
    monkeypatch.setitem(graph.TIER1_TOOLS, "rerun_ecl", fake)
    return FAKE_BASELINE


@pytest.fixture
def fake_tier1_tools(monkeypatch):
    """Fakes shock_macro/rerun_ecl/decompose_waterfall for the computable
    class of the 3-way split test (analyze_data deliberately excluded here
    — its sandbox plumbing is exercised in tests/test_tier2.py)."""
    for name, result in CANNED_TOOL_RESULTS.items():
        def make(res):
            def fn(**kwargs):
                return dict(res)
            return fn
        monkeypatch.setitem(graph.TIER1_TOOLS, name, make(result))


@pytest.fixture
def headline_narrator(monkeypatch):
    monkeypatch.setattr(
        graph, "_llm_narrate",
        lambda result: (f"Engine says: {result['headline']}", "mock-narr"))


def _set_router(monkeypatch, payload):
    monkeypatch.setattr(
        graph, "_llm_route",
        lambda question: (json.dumps(payload), "mock-router"))


def _set_reason(monkeypatch, fn):
    monkeypatch.setattr(graph, "_llm_reason", fn)


# ---------------------------------------------------------------------------
# 1. the three-way split
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", REASONED_QUESTIONS)
def test_router_sends_conceptual_questions_to_reasoned(
        question, monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})

    def grounded(q, passages, baseline, retry=False):
        p = passages[0]
        return (f"Per [{p['citation']}], and general credit-risk economics, "
                f"joint stress effects are often non-additive."), "mock-r"

    _set_reason(monkeypatch, grounded)
    final = graph.run_agent(question)

    assert final["route"] == "REASONED"
    assert final["mode"] == "reasoned"
    assert final["answer"].startswith(graph.REASONED_PREFIX)
    assert [e["node"] for e in final["trace"]] == ["router", "REASONED"]
    assert final["trace"][1]["number_check_passed"] is True
    assert final["trace"][1]["mode"] == "llm"


@pytest.mark.parametrize("question,payload,route",
                        COMPUTABLE_QUESTIONS)
def test_router_sends_computable_questions_to_their_tool(
        question, payload, route, monkeypatch, fake_tier1_tools,
        headline_narrator):
    _set_router(monkeypatch, payload)
    final = graph.run_agent(question)

    assert final["route"] == route
    assert final["mode"] == "grounded"
    assert [e["node"] for e in final["trace"]] == \
        ["router", route, "narrator"]
    assert not final["answer"].startswith(graph.REASONED_PREFIX)


@pytest.mark.parametrize("question", REFUSE_QUESTIONS)
def test_router_still_refuses_out_of_domain_questions(question, monkeypatch):
    _set_router(monkeypatch, {"route": "REFUSE", "args": {}})
    final = graph.run_agent(question)

    assert final["route"] == "REFUSE"
    assert final["mode"] == "refusal"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == ["router", "refusal"]


def test_refusal_message_mentions_the_reasoned_carveout():
    assert "reasoned interpretation" in graph.REFUSAL_MESSAGE


def test_reasoned_route_is_registered_and_excluded_from_tool_routes():
    assert graph.REASONED in graph.ROUTE_ARG_MODELS
    assert graph.REASONED not in graph.TOOL_ROUTES


def test_router_prompt_states_the_motivating_example_verbatim():
    # spec: the router prompt's few-shot examples include the motivating
    # interaction-term question verbatim (module docstring / task spec).
    # Whitespace-normalised since the prompt line-wraps the sentence.
    flat = " ".join(graph.ROUTER_SYSTEM_PROMPT.lower().split())
    assert ("does the satellite need a uer x hpi interaction, or do the "
           "main effects and momentum already account for the joint "
           "stress response?") in flat


# ---------------------------------------------------------------------------
# 2. number guard: regeneration, fallback, grounded passes
# ---------------------------------------------------------------------------

def test_ungrounded_number_triggers_one_regeneration_then_fallback(
        monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})
    retries_seen = []

    def liar(q, passages, baseline, retry=False):
        retries_seen.append(retry)
        return ("The true joint effect is a 47.3% relative uplift, no "
                "citation needed."), "mock-r"

    _set_reason(monkeypatch, liar)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert retries_seen == [False, True]      # exactly one regeneration
    assert final["trace"][1]["mode"] == "template_number_check_failed"
    assert final["trace"][1]["number_check_passed"] is False
    assert len(final["trace"][1]["attempts"]) == 2
    assert final["answer"].startswith(graph.REASONED_PREFIX)
    assert "closest validated tool" in final["answer"]
    assert "analyze_data" in final["answer"]


def test_regeneration_succeeds_after_a_bad_first_attempt(
        monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})
    calls = {"n": 0}

    def flaky(q, passages, baseline, retry=False):
        calls["n"] += 1
        if calls["n"] == 1:
            assert retry is False
            return "That is a 47.3% relative uplift.", "mock-r"
        assert retry is True
        return ("This is qualitative reasoning about joint stress effects, "
                "with no new number stated."), "mock-r"

    _set_reason(monkeypatch, flaky)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert calls["n"] == 2
    assert final["trace"][1]["mode"] == "llm_repaired"
    assert final["trace"][1]["number_check_passed"] is True
    assert "47.3" not in final["answer"]


def test_baseline_number_passes_the_guard_on_first_attempt(
        monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})

    def fake(q, passages, baseline, retry=False):
        return (f"The baseline weighted allowance is "
                f"{baseline['weighted_allowance']:.0f}, which is the "
                f"context for this reasoning."), "mock-r"

    _set_reason(monkeypatch, fake)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert final["trace"][1]["mode"] == "llm"
    assert final["trace"][1]["number_check_passed"] is True


def test_question_echoed_number_passes_the_guard(monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})
    q = ("Would a 2.5 percentage point UER shock plausibly need an "
         "interaction term with HPI, or is that already captured by "
         "momentum?")

    def fake(question, passages, baseline, retry=False):
        return ("A 2.5 percentage point shock is well inside the range "
                "the momentum term is designed to capture."), "mock-r"

    _set_reason(monkeypatch, fake)
    final = graph.run_agent(q)

    assert final["trace"][1]["mode"] == "llm"
    assert final["trace"][1]["number_check_passed"] is True


def test_passage_number_passes_the_guard(monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})

    def fake(q, passages, baseline, retry=False):
        # pull a number verbatim out of a retrieved passage's own text
        import re
        for p in passages:
            m = re.search(r"-?\d[\d,]*(?:\.\d+)?", p["text"])
            if m:
                return (f"Per [{p['citation']}], {m.group(0)} is the "
                        f"documented figure."), "mock-r"
        return "No numeric passage found.", "mock-r"

    _set_reason(monkeypatch, fake)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert final["trace"][1]["mode"] == "llm"
    assert final["trace"][1]["number_check_passed"] is True


def test_reasoning_llm_totally_unavailable_falls_back(
        monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})

    def dead(q, passages, baseline, retry=False):
        raise RuntimeError("both reasoning models down")

    _set_reason(monkeypatch, dead)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert final["trace"][1]["mode"].startswith("template_llm_error")
    assert final["answer"].startswith(graph.REASONED_PREFIX)
    assert final["mode"] == "reasoned"


def test_reasoned_answer_is_audited(monkeypatch, fake_baseline):
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})
    _set_reason(monkeypatch,
               lambda q, passages, baseline, retry=False:
               ("General credit-risk economics apply here.", "mock-r"))
    final = graph.run_agent(MOTIVATING_QUESTION)
    assert final["trace"][1]["tool_call_id"] is not None
    assert final["tool_result"]["tool"] == graph.REASONED


# ---------------------------------------------------------------------------
# 3. unit checks
# ---------------------------------------------------------------------------

def test_reasoned_answer_ok_unit_checks():
    passages = [{"citation": "pages/x.md#Y", "text": "coverage 1.28% here"}]
    baseline = {"weighted_allowance": 34000000.0}
    question = "what about a 2pp shock scenario?"
    result = {"passages": passages, "baseline": baseline,
             "question": question}

    # passage-grounded number
    assert graph.reasoned_answer_ok(
        "Coverage runs about 1.28% per the docs.", result)
    # baseline-grounded number
    assert graph.reasoned_answer_ok(
        "The baseline allowance is 34000000.", result)
    # question-echoed number
    assert graph.reasoned_answer_ok("A 2pp shock is well within range.",
                                    result)
    # pure qualitative reasoning, no numbers at all -> trivially fine
    assert graph.reasoned_answer_ok(
        "This is standard credit-risk economics with no figures.", result)
    # an invented number absent from all three sources -> fails
    assert not graph.reasoned_answer_ok("The true figure is 999999.",
                                        result)
    # ADVERSARIAL: an invented magnitude SPELLED OUT IN WORDS has no digit
    # characters at all, so a digit-only token regex would see it as
    # number-free and wrongly pass it — this is the REASONED route's most
    # exposed attack surface ("just intuition, no exact numbers" scope-
    # gaming). Must still fail, whether or not any digit token is present.
    assert not graph.reasoned_answer_ok(
        "The allowance would likely rise by roughly two hundred million "
        "dollars.", result)
    assert not graph.reasoned_answer_ok(
        "That would be a forty-seven percent relative uplift.", result)
    assert not graph.reasoned_answer_ok(
        "Just intuition, not exact: the impact would land somewhere in "
        "the tens of millions.", result)
    # ordinary small-number words with no adjacent unit word stay legal
    assert graph.reasoned_answer_ok(
        "The model combines one satellite equation with two macro "
        "drivers.", result)


def test_spelled_out_magnitude_triggers_regeneration_then_fallback(
        monkeypatch, fake_baseline):
    """ADVERSARIAL / LIVE-CONFIRMED: probing the live model with 'just give
    me intuition, no exact numbers' successfully coaxed a spelled-out
    magnitude ('tens of millions') that a naive digit-only guard passed
    outright, with ZERO regeneration attempts. Lock in the fix end to end
    through the real node/graph, mirroring
    test_ungrounded_number_triggers_one_regeneration_then_fallback."""
    _set_router(monkeypatch, {"route": "REASONED", "args": {}})
    retries_seen = []

    def liar(q, passages, baseline, retry=False):
        retries_seen.append(retry)
        return ("Just for intuition, not an exact number: the impact would "
                "likely be in the tens of millions of dollars."), "mock-r"

    _set_reason(monkeypatch, liar)
    final = graph.run_agent(MOTIVATING_QUESTION)

    assert retries_seen == [False, True]      # exactly one regeneration
    assert final["trace"][1]["mode"] == "template_number_check_failed"
    assert final["trace"][1]["number_check_passed"] is False
    assert "tens of millions" not in final["answer"]
    assert final["answer"].startswith(graph.REASONED_PREFIX)
    assert "closest validated tool" in final["answer"]


def test_deterministic_reasoned_fallback_lists_passages_and_points_to_a_tool():
    result = {"passages": [{"citation": "pages/x.md#Y",
                            "text": "some documented passage text"}],
             "tool_call_id": "tc-000001"}
    text = graph.deterministic_reasoned_fallback(result)
    assert "[pages/x.md#Y]" in text
    assert "analyze_data" in text and "query_model_docs" in text
    assert "tc-000001" in text


def test_deterministic_reasoned_fallback_handles_no_passages():
    result = {"passages": [], "tool_call_id": "tc-000002"}
    text = graph.deterministic_reasoned_fallback(result)
    assert "no documentation passage" in text.lower()
    assert "tc-000002" in text
