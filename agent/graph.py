"""LangGraph orchestration for the IFRS 9 ECL copilot (Day 4).

Graph shape (deliberately small — five kinds of node, one loop-free pass):

    START -> router -+-> shock_macro ---------+
                     +-> reweight_scenarios --+-> narrator -> END
                     +-> rerun_ecl -----------+
                     +-> decompose_waterfall -+
                     +-> refusal ----------------------------> END

THE GOVERNING RULE (non-negotiable): the LLM never does arithmetic. Every
number in every answer comes from the frozen engine via the four Tier-1
tools in agent/tools_tier1.py. The LLM only (a) ROUTES the question to one
tool and parameterises it, and (b) NARRATES the tool's returned numbers.
Both LLM outputs are distrusted mechanically:

  * The router must emit ONLY JSON ``{"route": ..., "args": {...}}``. Its
    args are validated against the tool's pydantic model (extra='forbid');
    any parse or validation failure routes to REFUSAL — the agent never
    guesses arguments.
  * The narrator receives ONLY the tool's returned JSON and must reference
    its numbers verbatim. A post-check extracts every number token from the
    narration and asserts it appears in (or is a plain rounding of) the
    tool result; on any miss — or any narrator API failure — the answer
    falls back to the tool's own deterministic ``headline``, which is
    engine-generated text.

The REFUSAL path is a feature, not an error state: out-of-scope questions
get a fixed message naming the four validated tool families and offering to
extend the toolset. Nothing is invented.

LLM plumbing: OpenRouter via the openai SDK (base_url
https://openrouter.ai/api/v1), temperature 0, primary model PRIMARY_MODEL
with automatic fallback to FALLBACK_MODEL on ANY API error. The key comes
from OPENROUTER_API_KEY in the environment (.env via python-dotenv); it is
never logged, printed, or embedded in traces.

Audit: every node appends an event to ``state["trace"]``; ``run_agent``
writes the full trace as one line of outputs/agent_log/agent_runs.jsonl
(RUNS_LOG_PATH is a module global so tests can redirect it). The tool call
itself is additionally audited by tools_tier1 into tool_calls.jsonl.

Offline tests (tests/test_router.py) monkeypatch ``_llm_route`` /
``_llm_narrate`` / ``_chat_once`` and the TIER1_TOOLS registry entries —
pytest never touches the network or the heavy engine state.
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import ValidationError

from agent.tools_tier1 import TIER1_ARG_MODELS, TIER1_TOOLS

import operator

from langgraph.graph import END, START, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_LOG_PATH = PROJECT_ROOT / "outputs" / "agent_log" / "agent_runs.jsonl"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = "google/gemma-4-31b-it"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"

#: the four supported tool families, in the order the refusal message cites
TOOL_ROUTES = tuple(TIER1_TOOLS)          # registry order from tools_tier1
REFUSE = "REFUSE"

REFUSAL_MESSAGE = (
    "That question is outside my validated scope, so I will not answer it "
    "with made-up numbers. Every figure I report is computed by the frozen "
    "IFRS 9 ECL engine through four validated tool families: "
    "(1) shock_macro — coherent macro shocks (UER / HPI / GDP, parallel or "
    "peak-and-revert) applied to the base scenario; "
    "(2) reweight_scenarios — scenario-weight sensitivity of the weighted "
    "allowance and the Jensen gap; "
    "(3) rerun_ecl — allowance for a book segment (all, stage1, stage2, "
    "stage3, investor, high_ltv); "
    "(4) decompose_waterfall — the allowance movement decomposition between "
    "two reporting snapshots. "
    "Rephrase your question into one of those, or ask the model owners to "
    "extend the validated toolset."
)

ROUTER_SYSTEM_PROMPT = """\
You are the ROUTER of a validated IFRS 9 ECL model agent. You never compute
numbers. Your only job is to classify the user's question into EXACTLY ONE
of four engine tools — or REFUSE — and emit the tool's arguments.

Tools (args must satisfy these contracts exactly):

1. shock_macro — "what if the economy moves" questions.
   args: {"var": "UER"|"HPI"|"GDP", "shock": <float, pp units>,
          "shape": "parallel"|"peak_revert"}
   Units: UER = percentage points on the unemployment LEVEL (|shock|<=10);
   HPI / GDP = percentage points per QUARTER on the growth rate
   (|shock|<=5). "parallel" = sustained shift (default); "peak_revert" =
   ramp up, hold, decay back. A rise/stress is positive, a fall negative.

2. reweight_scenarios — "what if we weighted the scenarios differently".
   args: {"w_up": <float>, "w_base": <float>, "w_down": <float>},
   each in [0,1], summing to 1.

3. rerun_ecl — "how much allowance sits in segment X".
   args: {"segment": "all"|"stage1"|"stage2"|"stage3"|"investor"|"high_ltv"}

4. decompose_waterfall — "why did the allowance move between two dates".
   args: {"t0": <int 1..60>, "t1": <int 1..60>, t0 < t1}; defaults 20, 40.

REFUSE anything else: general knowledge, market or rate predictions,
opinions, advice, arithmetic requests, model methodology debates, other
portfolios, anything needing data or computation outside these four tools.
When in doubt, REFUSE — never guess.

Respond with ONLY a JSON object, no prose, no code fences:
  {"route": "<tool name or REFUSE>", "args": {...}}
For REFUSE use {"route": "REFUSE", "args": {}}.
"""

NARRATOR_SYSTEM_PROMPT = """\
You are the NARRATOR for a validated IFRS 9 ECL engine. You will receive a
JSON object of numbers computed by the engine, including a 'headline'
sentence. Write a short answer (2-4 sentences) for a bank risk executive.

HARD RULES — violations are discarded by an automated check:
- Repeat numbers EXACTLY as they appear in the JSON (the headline's
  formatting is safe to reuse). Never compute, add, subtract, rescale,
  re-round, or otherwise derive any number yourself.
- Prefer the formatted renderings already present in the JSON strings
  (e.g. '$31.7m', '+4.1%') over long raw floats; quote raw values only
  when no formatted rendering exists.
- Use ONLY numbers present in the JSON. No outside figures, no dates, no
  standard names with digits (write 'the accounting standard', not a
  numbered standard).
- No speculation beyond what the JSON states. Plain factual tone.
"""


# ---------------------------------------------------------------------------
# LLM plumbing (OpenRouter via openai SDK; offline tests monkeypatch these)
# ---------------------------------------------------------------------------

_CLIENT = None
_CLIENT_LOCK = threading.Lock()


def _client():
    """Lazy singleton OpenAI client pointed at OpenRouter (key from env)."""
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                try:                              # .env if present; no-op else
                    from dotenv import load_dotenv
                    load_dotenv(PROJECT_ROOT / ".env")
                except ImportError:               # pragma: no cover
                    pass
                key = os.environ.get("OPENROUTER_API_KEY")
                if not key:
                    raise RuntimeError(
                        "OPENROUTER_API_KEY is not set (expected in .env)")
                from openai import OpenAI
                _CLIENT = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)
    return _CLIENT


def _chat_once(model: str, messages: list[dict]) -> str:
    """One temperature-0 chat completion against one model."""
    resp = _client().chat.completions.create(
        model=model, messages=messages, temperature=0.0)
    content = resp.choices[0].message.content
    if not content:
        raise RuntimeError(f"empty completion from {model}")
    return content


def _call_llm(messages: list[dict]) -> tuple[str, str]:
    """Primary model, then FALLBACK_MODEL on ANY error; (text, model_used).

    Raises the fallback's exception if both models fail — callers decide
    what failure means (router -> refusal, narrator -> deterministic text).
    """
    try:
        return _chat_once(PRIMARY_MODEL, messages), PRIMARY_MODEL
    except Exception:
        return _chat_once(FALLBACK_MODEL, messages), FALLBACK_MODEL


def _llm_route(question: str) -> tuple[str, str]:
    """Raw router completion for a question; (text, model_used)."""
    return _call_llm([
        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ])


def _llm_narrate(tool_result: dict) -> tuple[str, str]:
    """Raw narrator completion over ONLY the tool's returned JSON."""
    return _call_llm([
        {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(tool_result)},
    ])


# ---------------------------------------------------------------------------
# router output parsing + validation (failure == refusal, never a guess)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Parse the router's JSON object, tolerating code fences / prose tails."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", s).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        if start < 0:
            raise ValueError("router output contains no JSON object")
        depth = 0
        for i, ch in enumerate(s[start:], start):
            depth += ch == "{"
            depth -= ch == "}"
            if depth == 0:
                obj = json.loads(s[start:i + 1])
                break
        else:
            raise ValueError("router output contains unbalanced JSON")
    if not isinstance(obj, dict):
        raise ValueError("router output is not a JSON object")
    return obj


def decide_route(question: str) -> dict:
    """Classify a question -> {route, args, detail} with hard validation.

    route is one of TOOL_ROUTES or REFUSE. args are the pydantic-validated
    tool arguments (model_dump, so defaults are materialised). Any LLM
    failure, unparseable output, unknown route, or argument-validation
    failure collapses to REFUSE with a diagnostic detail string.
    """
    try:
        raw, model_used = _llm_route(question)
    except Exception as exc:                      # both models failed
        return {"route": REFUSE, "args": {}, "model": None,
                "detail": f"router LLM unavailable: {type(exc).__name__}"}
    try:
        parsed = _extract_json(raw)
    except ValueError as exc:
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": f"unparseable router output: {exc}"}
    route = parsed.get("route")
    if route == REFUSE:
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": "router classified the question as out of scope"}
    if route not in TIER1_TOOLS:
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": f"unknown route {route!r}"}
    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": "router args are not an object"}
    try:
        validated = TIER1_ARG_MODELS[route](**args)
    except ValidationError as exc:
        first = exc.errors()[0]
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": (f"invalid arguments for {route}: "
                           f"{first.get('msg', 'validation error')}")}
    return {"route": route, "args": validated.model_dump(),
            "model": model_used, "detail": "ok"}


# ---------------------------------------------------------------------------
# narration number check (the mechanical anti-arithmetic guard)
# ---------------------------------------------------------------------------

_NUM_TOKEN_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _number_tokens(text: str) -> list[str]:
    return _NUM_TOKEN_RE.findall(text)


def _allowed_numbers(tool_result: dict) -> list[float]:
    """Every number a faithful narration may contain.

    Numeric leaves of the result plus their two legitimate DISPLAY
    transforms ($ -> $m, fraction -> %), and every number token appearing
    anywhere in the serialised JSON (headline strings, period labels,
    tool_call_id, keys like 'stage2'). Display transforms are fixed unit
    conventions, not arithmetic the LLM performs.
    """
    allowed: list[float] = []

    def walk(v) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            f = float(v)
            if math.isfinite(f):
                allowed.extend((f, f / 1e6, f * 100.0))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(tool_result)
    for tok in _number_tokens(json.dumps(tool_result)):
        try:
            allowed.append(float(tok.replace(",", "")))
        except ValueError:                        # pragma: no cover
            pass
    return allowed


def narration_numbers_ok(text: str, tool_result: dict) -> bool:
    """True iff EVERY number token in the narration appears in the result.

    A token matches if it equals — or is a plain rounding at its own
    printed precision of — an allowed number (sign-insensitive, so 'fell
    by $2.8m' matches a delta of -2.8). One miss fails the whole text.
    """
    allowed = _allowed_numbers(tool_result)
    for tok in _number_tokens(text):
        n = float(tok.replace(",", ""))
        decimals = len(tok.split(".")[1]) if "." in tok else 0
        tol = 0.5 * 10.0 ** (-decimals) + 1e-9
        if not any(abs(n - a) <= tol or abs(abs(n) - abs(a)) <= tol
                   for a in allowed):
            return False
    return True


def deterministic_narration(tool_result: dict) -> str:
    """Engine-authored fallback answer: the tool's own headline, verbatim."""
    return (f"{tool_result['headline']} "
            f"[engine-computed; audit ref {tool_result['tool_call_id']}]")


# ---------------------------------------------------------------------------
# graph state + nodes
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    question: str
    route: str
    tool_args: dict
    tool_result: dict
    answer: str
    trace: Annotated[list, operator.add]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _router_node(state: AgentState) -> dict:
    decision = decide_route(state["question"])
    return {
        "route": decision["route"],
        "tool_args": decision["args"],
        "trace": [{"node": "router", "ts": _now(),
                   "route": decision["route"], "args": decision["args"],
                   "model": decision["model"], "detail": decision["detail"]}],
    }


def _make_tool_node(name: str):
    """Node that executes ONE registry tool with already-validated args."""

    def node(state: AgentState) -> dict:
        try:
            result = TIER1_TOOLS[name](**state["tool_args"])
            event = {"node": name, "ts": _now(), "status": "ok",
                     "tool_call_id": result.get("tool_call_id"),
                     "headline": result.get("headline")}
        except Exception as exc:      # engine failure: honest, no numbers
            result = {"error": f"{type(exc).__name__}: {exc}", "tool": name}
            event = {"node": name, "ts": _now(), "status": "error",
                     "detail": result["error"]}
        return {"tool_result": result, "trace": [event]}

    node.__name__ = f"{name}_node"
    return node


def _narrator_node(state: AgentState) -> dict:
    result = state["tool_result"]
    if "error" in result:
        answer = (f"The {result.get('tool', 'requested')} engine call "
                  f"failed ({result['error']}); no numbers were produced, "
                  f"so I have none to report. Please retry or contact the "
                  f"model owners.")
        return {"answer": answer,
                "trace": [{"node": "narrator", "ts": _now(),
                           "mode": "tool_error"}]}
    try:
        text, model_used = _llm_narrate(result)
        ok = narration_numbers_ok(text, result)
        mode = "llm" if ok else "template_number_check_failed"
    except Exception as exc:
        text, model_used, ok = None, None, False
        mode = f"template_llm_error:{type(exc).__name__}"
    answer = text.strip() if ok else deterministic_narration(result)
    return {"answer": answer,
            "trace": [{"node": "narrator", "ts": _now(), "mode": mode,
                       "model": model_used,
                       "number_check_passed": bool(ok)}]}


def _refusal_node(state: AgentState) -> dict:
    return {"answer": REFUSAL_MESSAGE, "tool_result": {},
            "trace": [{"node": "refusal", "ts": _now(),
                       "message": "fixed refusal issued"}]}


def build_graph():
    """Compile the StateGraph (router -> tool -> narrator | refusal)."""
    g = StateGraph(AgentState)
    g.add_node("router", _router_node)
    for name in TOOL_ROUTES:
        g.add_node(name, _make_tool_node(name))
        g.add_edge(name, "narrator")
    g.add_node("narrator", _narrator_node)
    g.add_node("refusal", _refusal_node)
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router", lambda s: s["route"],
        {**{name: name for name in TOOL_ROUTES}, REFUSE: "refusal"})
    g.add_edge("narrator", END)
    g.add_edge("refusal", END)
    return g.compile()


_GRAPH = None
_GRAPH_LOCK = threading.Lock()


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        with _GRAPH_LOCK:
            if _GRAPH is None:
                _GRAPH = build_graph()
    return _GRAPH


# ---------------------------------------------------------------------------
# entry point + run audit trail
# ---------------------------------------------------------------------------

_RUNS_LOCK = threading.Lock()


def _log_run(record: dict) -> None:
    with _RUNS_LOCK:
        path = Path(RUNS_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def run_agent(question: str) -> dict:
    """Answer one question through the graph; audit the full trace.

    Returns the final state dict (question, route, tool_args, tool_result,
    answer, trace) and appends {ts, question, route, answer, trace} to
    outputs/agent_log/agent_runs.jsonl.
    """
    final = get_graph().invoke({
        "question": question, "route": "", "tool_args": {},
        "tool_result": {}, "answer": "", "trace": [],
    })
    _log_run({"ts": _now(), "question": question, "route": final["route"],
              "answer": final["answer"], "trace": final["trace"]})
    return final
