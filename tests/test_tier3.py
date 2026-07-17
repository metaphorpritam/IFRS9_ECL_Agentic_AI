"""Tests for agent/tier3_retrieval.py + its wiring into agent/graph.py.

Everything here is OFFLINE and file-driven: retrieval itself never calls an
LLM (agent/tier3_retrieval.py is pure lexical/graph scoring over wiki/ and
knowledge/index/), and the two router-integration tests monkeypatch
``_llm_route`` / ``_llm_narrate_docs`` exactly like tests/test_router.py
does for Tier-1 — no network, no OpenRouter key needed.

Contracts:
  1. DETERMINISM: the same question returns the identical passages and
     reading_list on repeated calls (only ``tool_call_id``, an audit
     sequence number, legitimately varies).
  2. REAL CITATIONS: every returned wiki citation's page file exists and
     its anchor traces back to a heading actually parsed out of that exact
     file; every returned notes citation's node_id exists in the loaded
     PageIndex tree.
  3. ROUTER WIRING: a mocked router sends a methodology question to
     ``query_model_docs`` (and the tool node ignores whatever args the
     router proposed, always retrieving on the user's own original
     question); an out-of-scope creative-writing request still REFUSEs.
  4. NARRATOR GUARD: a citation-bearing, passage-faithful narration passes;
     a poisoned narration (no citation, invented number) is discarded for
     the deterministic "here is what the documentation says" fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import agent.graph as graph
import agent.tier3_retrieval as tier3
import agent.tools_tier1 as tools_tier1

WIKI_DIR = tier3.WIKI_DIR

QUESTIONS = [
    "Explain the ECL movement waterfall",
    "How is SICR defined here",
    "Why did we choose the satellite model for PD",
    "How is LGD modelled here",
]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def _redirect_log(tmp_path_factory):
    """query_model_docs audits through tools_tier1._log_call (shared audit
    trail, per spec) — redirect its LOG_PATH so pytest never touches the
    real outputs/agent_log/tool_calls.jsonl."""
    old = tools_tier1.LOG_PATH
    tools_tier1.LOG_PATH = tmp_path_factory.mktemp("agent_log") / "tool_calls.jsonl"
    yield
    tools_tier1.LOG_PATH = old


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Belt-and-braces: any code path that would touch OpenRouter fails
    loudly instead of making a network call."""
    def _no_net(model, messages):
        raise AssertionError("network LLM call attempted in pytest")
    monkeypatch.setattr(graph, "_chat_once", _no_net)
    monkeypatch.setattr(graph, "RUNS_LOG_PATH",
                        tools_tier1.LOG_PATH.parent / "agent_runs.jsonl")


def _without_call_id(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "tool_call_id"}


# ---------------------------------------------------------------------------
# 1. determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("question", QUESTIONS)
def test_same_question_returns_the_identical_reading_list_twice(question):
    r1 = tier3.query_model_docs(question)
    r2 = tier3.query_model_docs(question)
    assert r1["reading_list"] == r2["reading_list"]
    assert r1["passages"] == r2["passages"]
    assert _without_call_id(r1) == _without_call_id(r2)
    # tool_call_id is the ONE thing allowed to differ (audit sequence)
    assert r1["tool_call_id"] != r2["tool_call_id"]


def test_empty_question_is_rejected_not_silently_guessed():
    with pytest.raises(ValueError):
        tier3.query_model_docs("   ")


# ---------------------------------------------------------------------------
# 2. every citation is a REAL, resolvable anchor
# ---------------------------------------------------------------------------

def _page_headings(rel_path: str) -> list[str]:
    graph_ = tier3._wiki_graph()
    for n in graph_["nodes"]:
        if n["path"] == rel_path:
            return [h["text"] for h in n["headings"]]
    raise AssertionError(f"{rel_path} is not a page in the wiki graph")


def _notes_node_ids() -> set[str]:
    tree, _pages = tier3._notes_index()
    ids = set()

    def rec(nodes):
        for n in nodes:
            ids.add(n["node_id"])
            rec(n.get("nodes", []))

    rec(tree["structure"])
    return ids


@pytest.mark.parametrize("question", QUESTIONS)
def test_every_wiki_citation_resolves_to_a_real_heading(question):
    result = tier3.query_model_docs(question)
    wiki_passages = [p for p in result["passages"] if p["source"] == "wiki"]
    assert wiki_passages, f"expected at least one wiki passage for {question!r}"
    for p in wiki_passages:
        # the page file itself must exist under wiki/
        page_path = WIKI_DIR / p["path"]
        assert page_path.is_file(), f"missing wiki page {p['path']}"
        # the citation's path component must match the passage's own path
        cite_path, _, anchor = p["citation"].partition("#")
        assert cite_path == p["path"]
        # the anchor must trace back to a REAL heading in that exact file
        headings = _page_headings(p["path"])
        assert p["heading"] in headings
        assert tier3._wiki_anchor(p["heading"]) == anchor
        # the passage text must appear verbatim in the source file
        assert p["text"] in page_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("question", QUESTIONS)
def test_every_notes_citation_resolves_to_a_real_node(question):
    result = tier3.query_model_docs(question)
    notes_passages = [p for p in result["passages"] if p["source"] == "notes"]
    assert notes_passages, f"expected at least one notes passage for {question!r}"
    known_ids = _notes_node_ids()
    for p in notes_passages:
        assert p["node_id"] in known_ids
        assert p["citation"].startswith("notes ")
        assert p["text"]                          # never an empty citation


def test_passages_are_json_serialisable():
    result = tier3.query_model_docs(QUESTIONS[0])
    json.dumps(result)                             # raises if not


# ---------------------------------------------------------------------------
# 3. router wiring: methodology -> query_model_docs, poem -> REFUSE
# ---------------------------------------------------------------------------

def test_router_sends_methodology_question_to_query_model_docs(monkeypatch):
    seen_questions = []

    def fake_route(question):
        return (json.dumps({"route": "query_model_docs", "args": {}}),
                "mock-router")

    def fake_narrate_docs(result):
        seen_questions.append(result["question"])
        p = result["passages"][0]
        return (f"Per {p['citation']}, that is what the documentation "
               f"says.", "mock-narrator")

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    monkeypatch.setattr(graph, "_llm_narrate_docs", fake_narrate_docs)

    q = "explain the ecl waterfall"
    final = graph.run_agent(q)

    assert final["route"] == "query_model_docs"
    assert final["tool_args"] == {}                # router args stayed empty
    assert [e["node"] for e in final["trace"]] == \
        ["router", "query_model_docs", "narrator"]
    # THE point of a dedicated tool node: retrieval used the user's OWN
    # original question, never something the router restated
    assert seen_questions == [q]
    assert final["trace"][2]["citation_check_passed"] is True
    assert final["trace"][1]["tool_call_id"] is not None


def test_router_refuses_a_poem_request(monkeypatch):
    def fake_route(question):
        return json.dumps({"route": "REFUSE", "args": {}}), "mock-router"

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    final = graph.run_agent("write me a poem about the ECL model")

    assert final["route"] == "REFUSE"
    assert final["answer"] == graph.REFUSAL_MESSAGE
    assert [e["node"] for e in final["trace"]] == ["router", "refusal"]


def test_query_model_docs_args_reject_a_sneaky_extra_key(monkeypatch):
    """The router's ONLY valid payload for this route is args={} — anything
    else (e.g. an attempted 'question' override) fails pydantic validation
    (extra='forbid') and collapses to REFUSE, never a guess."""
    def fake_route(question):
        return (json.dumps({"route": "query_model_docs",
                            "args": {"question": "something else"}}),
               "mock-router")

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    final = graph.run_agent("how is SICR defined here")

    assert final["route"] == "REFUSE"
    assert "invalid arguments for query_model_docs" in final["trace"][0]["detail"]


def test_query_model_docs_route_is_named_in_the_refusal_message():
    assert tier3.query_model_docs.__name__ in graph.REFUSAL_MESSAGE
    assert graph.TIER3_ROUTE in graph.ROUTE_ARG_MODELS


# ---------------------------------------------------------------------------
# 4. narrator guard: fallback on a poisoned (uncited / invented) answer
# ---------------------------------------------------------------------------

def test_narrator_fallback_triggers_on_answer_with_no_citation(monkeypatch):
    def fake_route(question):
        return json.dumps({"route": "query_model_docs", "args": {}}), "r"

    def poisoned(result):
        # no citation AND a number absent from every passage
        return "The allowance is exactly $999.9m, no citation needed.", "n"

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    monkeypatch.setattr(graph, "_llm_narrate_docs", poisoned)

    final = graph.run_agent("explain the ecl waterfall")
    result = tier3.query_model_docs("explain the ecl waterfall")

    assert final["trace"][-1]["mode"] == "template_citation_check_failed"
    assert final["trace"][-1]["citation_check_passed"] is False
    assert final["answer"].startswith("Here is what the documentation says:")
    for p in result["passages"]:
        assert f"[{p['citation']}]" in final["answer"]


def test_narrator_fallback_triggers_on_narrator_llm_error(monkeypatch):
    def fake_route(question):
        return json.dumps({"route": "query_model_docs", "args": {}}), "r"

    def dead(result):
        raise RuntimeError("narrator down")

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    monkeypatch.setattr(graph, "_llm_narrate_docs", dead)

    final = graph.run_agent("explain the ecl waterfall")
    assert final["trace"][-1]["mode"].startswith("template_llm_error")
    assert final["answer"].startswith("Here is what the documentation says:")


def test_faithful_citing_narration_passes_the_guard(monkeypatch):
    def fake_route(question):
        return json.dumps({"route": "query_model_docs", "args": {}}), "r"

    result_holder = {}

    def faithful(result):
        result_holder["r"] = result
        p = result["passages"][0]
        return (f"Per {p['citation']}: {p['text'].split(chr(10))[0][:60]}",
               "n")

    monkeypatch.setattr(graph, "_llm_route", fake_route)
    monkeypatch.setattr(graph, "_llm_narrate_docs", faithful)

    final = graph.run_agent("explain the ecl waterfall")
    assert final["trace"][-1]["mode"] == "llm"
    assert final["trace"][-1]["citation_check_passed"] is True
    p0 = result_holder["r"]["passages"][0]
    assert p0["citation"] in final["answer"]


def test_docs_answer_ok_unit_checks():
    passages = [{"citation": "pages/ecl-engine.md#Headline numbers",
                "text": "allowance $24.5m, coverage 1.28%."}]
    result = {"passages": passages}
    # cites the passage, only uses numbers present in it
    assert graph.docs_answer_ok(
        "Per pages/ecl-engine.md#Headline numbers, allowance is $24.5m.",
        result)
    # no citation at all -> fails
    assert not graph.docs_answer_ok("Allowance is $24.5m.", result)
    # cites, but invents a number absent from every passage -> fails
    assert not graph.docs_answer_ok(
        "Per pages/ecl-engine.md#Headline numbers, allowance is $999.9m.",
        result)
    # no passages at all -> trivially fails (nothing to cite)
    assert not graph.docs_answer_ok("anything", {"passages": []})
    # ADVERSARIAL: cites correctly, but the number is SPELLED OUT rather
    # than a digit — a digit-only token regex would miss this entirely
    # (see `_spelled_number_violation`); must still fail
    assert not graph.docs_answer_ok(
        "Per pages/ecl-engine.md#Headline numbers, allowance is roughly "
        "twenty-four point five million dollars.", result)


def test_deterministic_docs_narration_lists_every_passage_and_audit_ref():
    result = tier3.query_model_docs("explain the ecl waterfall")
    text = graph.deterministic_docs_narration(result)
    assert text.startswith("Here is what the documentation says:")
    assert result["tool_call_id"] in text
    for p in result["passages"]:
        assert f"[{p['citation']}]" in text


def test_deterministic_docs_narration_handles_no_passages():
    result = {"passages": [], "tool_call_id": "tc-000001"}
    text = graph.deterministic_docs_narration(result)
    assert "nothing" in text.lower()
    assert "tc-000001" in text
