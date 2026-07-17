"""LangGraph orchestration for the IFRS 9 ECL copilot (Day 4 + Tier-3 + Tier-2
+ REASONED).

Graph shape (deliberately small — eight kinds of node, one loop-free pass):

    START -> router -+-> shock_macro ------------+
                     +-> reweight_scenarios ------+
                     +-> rerun_ecl ----------------+-> narrator -> END
                     +-> decompose_waterfall ------+
                     +-> query_model_docs ---------+
                     +-> analyze_data -+-> narrator ------------------> END
                     |                 +-> refusal (repair also failed) -> END
                     +-> REASONED -------------------------------------> END
                     +-> refusal --------------------------------------> END

THE GOVERNING RULE (non-negotiable): the LLM never does arithmetic and never
states a fact from its own memory. Every NUMBER in every Tier-1 answer comes
from the frozen engine via the four Tier-1 tools in agent/tools_tier1.py.
Every CLAIM in a Tier-3 (``query_model_docs``, agent/tier3_retrieval.py)
answer comes from a retrieved wiki/knowledge-corpus passage, cited. Every
NUMBER in a Tier-2 (``analyze_data``, agent/tools_tier2.py) answer comes from
EXECUTING LLM-written pandas code in the sandbox — the LLM may write the
CODE, never the number. The LLM only (a) ROUTES the question to one tool
(parameterising it, for Tier-1 — Tier-3 and Tier-2 always reuse the user's
own original question, never a router paraphrase), (b) for Tier-2 only,
WRITES the pandas code the sandbox then executes, and (c) NARRATES the
result. Every LLM output is distrusted mechanically:

  * The router must emit ONLY JSON ``{"route": ..., "args": {...}}``. Its
    args are validated against the tool's pydantic model (extra='forbid');
    any parse or validation failure routes to REFUSAL — the agent never
    guesses arguments.
  * The Tier-1 narrator receives ONLY the tool's returned JSON and must
    reference its numbers verbatim. A post-check extracts every number
    token from the narration and asserts it appears in (or is a plain
    rounding of) the tool result; on any miss — or any narrator API
    failure — the answer falls back to the tool's own deterministic
    ``headline``, which is engine-generated text.
  * The Tier-3 narrator receives ONLY the retrieved ``passages`` and must
    cite one for every claim. A post-check (``docs_answer_ok``) requires at
    least one passage's ``citation`` string to appear verbatim in the
    answer AND every number in the answer to appear in some passage's own
    text; on any miss — or any narrator API failure — the answer falls back
    to a deterministic "here is what the documentation says" listing of the
    retrieved passages (``deterministic_docs_narration``).
  * The Tier-2 code-writer's code is AST-validated and then actually
    EXECUTED (agent/tools_tier2.run_sandboxed) before the narrator ever
    sees a number — the same verbatim-number post-check used for Tier-1
    then runs over the EXECUTED ``result_preview``, not anything the LLM
    claimed. A code-gen failure or a sandboxed rejection/error gets exactly
    ONE repair attempt (the failing code + its error handed back to the
    code-writer); still failing, the question falls through to REFUSAL —
    never a guessed number. Every successful run's code (and a hash of its
    executed result) is shown in the trace and audited.
  * REASONED answers a CONCEPTUAL question none of the six tools/retriever
    above computes or simply quotes verbatim — model-design rationale,
    interaction-term / joint-effect reasoning, "why is X modeled this way",
    standard credit-risk economic intuition. The node (a) retrieves Tier-3
    passages for grounding, (b) reads the engine's own baseline snapshot
    (``rerun_ecl(segment="all")``) as a second validated number source, then
    (c) an LLM reasons from both plus ordinary credit-risk economics, citing
    passages where used. A post-check (``reasoned_answer_ok``) — the same
    verbatim-number discipline as Tier-1/Tier-3, extended with a third
    legal source (the user's own question) — requires every number in the
    answer to appear in a passage, the baseline snapshot, or the question;
    on a miss the node makes ONE regeneration attempt with an explicit
    no-new-numerics instruction, then falls back to a deterministic
    qualitative template pointing at the closest validated tool. Every
    verbatim-number guard in this module (Tier-1's ``narration_numbers_ok``,
    Tier-3's ``docs_answer_ok``, and this route's ``reasoned_answer_ok``)
    ALSO rejects a number spelled out in words ("two hundred million
    dollars", "forty-seven percent") via ``_spelled_number_violation`` — a
    digit-only token regex is blind to word-form numbers, which an
    adversarial probe confirmed is otherwise a live way to state an
    invented magnitude while passing every check that only looks at
    digits. Every REASONED answer is prefixed with a machine-readable mode
    marker (``REASONED_PREFIX``) so the API/UI can label it distinctly from
    a grounded engine/documentation answer.

The REFUSAL path is a feature, not an error state: out-of-scope questions
get a fixed message naming the validated tool families and offering to
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
``_llm_narrate`` / ``_chat_once`` and the TIER1_TOOLS registry entries;
tests/test_tier3.py does the same for ``query_model_docs`` / ``_llm_narrate_
docs`` — pytest never touches the network or the heavy engine state.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, ValidationError

from agent.tier3_retrieval import TIER3_ARG_MODELS, query_model_docs
from agent.tools_tier1 import TIER1_ARG_MODELS, TIER1_TOOLS, _log_call
from agent.tools_tier2 import TIER2_ARG_MODELS, run_sandboxed

import operator

from langgraph.graph import END, START, StateGraph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_LOG_PATH = PROJECT_ROOT / "outputs" / "agent_log" / "agent_runs.jsonl"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = "google/gemma-4-31b-it"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"

#: the four Tier-1 (numbers) tool families, in the order the refusal message
#: cites them — unchanged by Tier-3 (kept exactly as the live router defines
#: it, so existing tests/behaviour are untouched)
TOOL_ROUTES = tuple(TIER1_TOOLS)          # registry order from tools_tier1

#: the one Tier-3 (documentation) route, kept separate from TOOL_ROUTES so
#: Tier-1-only call sites (e.g. TOOL_ROUTES-based refusal-message checks)
#: are unaffected
TIER3_ROUTE = "query_model_docs"

#: the one Tier-2 (sandboxed code interpreter) route, additive alongside
#: TOOL_ROUTES/TIER3_ROUTE for the same reason
TIER2_ROUTE = "analyze_data"

REFUSE = "REFUSE"

#: the reasoned-interpretation route: conceptually-relevant questions this
#: model's fixed tools/documentation retriever cannot directly compute or
#: quote verbatim, but that a grounded, cited, number-disciplined LLM answer
#: CAN responsibly address (model-design rationale, interaction-term /
#: economic-intuition questions, "why is X modeled this way", what-if
#: REASONING that needs no new number). Kept as its own uppercase sentinel
#: alongside REFUSE — it has no registry tool to execute, only a grounded
#: reasoning pass (see _reasoned_node), so it is NOT added to TOOL_ROUTES.
REASONED = "REASONED"


class ReasonedArgs(BaseModel):
    """Deliberately EMPTY (extra='forbid') — same contract as Tier-3's
    QueryModelDocsArgs: the router only classifies; _reasoned_node always
    reasons over the user's own original question text, never a
    router-authored paraphrase."""

    model_config = ConfigDict(extra="forbid")


#: every valid non-REFUSE route -> its pydantic argument model
ROUTE_ARG_MODELS = {**TIER1_ARG_MODELS, **TIER3_ARG_MODELS, **TIER2_ARG_MODELS,
                    REASONED: ReasonedArgs}

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
    "two reporting snapshots; "
    "(5) analyze_data — long-tail analytical questions (rankings, filters, "
    "group-bys, ...) answered by generating pandas code that is EXECUTED in "
    "a validated sandbox against the scored book, never by LLM arithmetic; "
    "and one documentation tool, (6) query_model_docs — methodology / "
    "definition questions answered strictly from the model-development wiki "
    "and the IFRS 9 knowledge corpus, every claim cited to a real page or "
    "note section. "
    "Rephrase your question into one of those, or ask the model owners to "
    "extend the validated toolset. Conceptually-related questions about "
    "this model's methodology or design get a reasoned interpretation "
    "automatically, so rephrasing your question toward the model or its "
    "methodology may help."
)

ROUTER_SYSTEM_PROMPT = """\
You are the ROUTER of a validated IFRS 9 ECL model agent. You never compute
numbers and you never state facts yourself. Your only job is to classify
the user's question into EXACTLY ONE of three CLASSES:
  (a) COMPUTABLE — one of six engine tools that returns a fresh number;
  (b) REASONED — a conceptually relevant question about credit risk, IFRS 9,
      or this model's own methodology that NO tool computes or the
      documentation retriever simply quotes verbatim, but that a grounded,
      cited, number-disciplined reasoning pass can responsibly address;
  (c) REFUSE — everything else (no connection to this model or credit
      risk, or a request for a fresh number/fact with no tool for it).
and emit that route's arguments.

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

5. analyze_data — long-tail ANALYTICAL questions over the scored loan book
   that the four fixed tools above cannot answer because there is no fixed
   parameter for them: rankings ("top 10 loans by allowance"), specific
   filters/averages ("average LTV of Stage 2 loans", "how many investor
   loans are in Stage 3"), cross-cuts ("which FICO band drives the most
   allowance"), or anything else that needs an ad-hoc query over the book.
   args: {} always (the question text itself drives a separate code-writer
   step — never restate or rephrase it in args).
   Disambiguation: if the question is EXACTLY one of the four fixed tools'
   own jobs (a named macro shock, a scenario reweight, a named segment's
   allowance, or a between-two-dates waterfall), route to THAT tool instead
   — it is simpler and does not need generated code. Use analyze_data only
   when none of tools 1-4 fit.

6. query_model_docs — FACTUAL "what does our documentation say" methodology
   questions: "explain X", "how is Y defined here", "why did we choose Z",
   requests to define/explain a concept (SICR, PD, LGD, staging, the
   standard's mechanics, ...) using THIS project's own model-development
   wiki and its IFRS 9 knowledge corpus. args: {} always (the question text
   itself is reused verbatim by the tool — never restate or rephrase it in
   args).
   Disambiguation: a request to SEE, show, or walk through the book's
   actual allowance movement or waterfall NUMBERS (e.g. "walk me through
   the allowance waterfall") is decompose_waterfall (tool 4), never this
   route. Use this route only for what the documentation SAYS — definitions,
   methodology, rationale ALREADY written down, quotable near-verbatim.

7. REASONED — relevant CONCEPTUAL questions about credit risk, IFRS 9, or
   this model's own methodology that NONE of tools 1-6 computes or simply
   quotes: model-design rationale ("does the satellite need a UER x HPI
   interaction, or do the main effects and momentum already account for
   the joint stress response?"), "why is X modeled this way" / "why
   does coefficient Y come out negative" questions, standard credit-risk
   economic intuition, and what-if REASONING that needs no new NUMBER (as
   opposed to analyze_data's what-if COMPUTATION, or shock_macro/
   reweight_scenarios's what-if RE-RUN). args: {} always (the question text
   itself is reused verbatim by a grounded reasoning pass — never restate
   or rephrase it in args).
   Disambiguation vs query_model_docs (6): route to 6 ONLY when the answer
   is a plain lookup the documentation already states outright (a
   definition, a stated methodology fact). Route to REASONED when the
   question needs REASONING — combining what's documented with ordinary
   credit-risk logic (interaction/joint-effect judgment, a "does X already
   cover Y" synthesis, a "why" that isn't just a quoted rationale). When
   genuinely torn between the two, prefer REASONED — it still cites its
   sources and never invents a number, so it is never the unsafe choice.
   Disambiguation vs REFUSE: REASONED is for questions ABOUT this model or
   IFRS 9 / credit risk generally, even ones with no fixed tool or exact
   documented answer. REFUSE is for questions with NO connection to either.

REFUSE anything else: general knowledge unrelated to credit risk or this
project, market or rate predictions, opinions/advice unconnected to this
model, arithmetic requests, poems or other creative writing, other
portfolios, anything needing data or computation outside these seven
routes. When in doubt between REASONED and REFUSE for a question that IS
at least about credit risk / IFRS 9 / this model, prefer REASONED — never
invent a number, but do not refuse a legitimate conceptual question either.
When a question has no connection at all to this model or credit risk,
REFUSE. Never guess an argument.

Respond with ONLY a JSON object, no prose, no code fences:
  {"route": "<tool name, REASONED, or REFUSE>", "args": {...}}
For REFUSE use {"route": "REFUSE", "args": {}}.
For REASONED use {"route": "REASONED", "args": {}}.

EXAMPLES (three per class — study the PATTERN, not just these questions):

-- COMPUTABLE (a tool route; a fresh engine number is needed) --
Q: "What happens to the allowance if unemployment rises 2 percentage
    points?"
A: {"route": "shock_macro", "args": {"var": "UER", "shock": 2.0, "shape":
    "parallel"}}
Q: "How much of the allowance sits in Stage 2?"
A: {"route": "rerun_ecl", "args": {"segment": "stage2"}}
Q: "What are the top 5 loans by weighted allowance?"
A: {"route": "analyze_data", "args": {}}

-- REASONED (conceptually relevant; no tool computes or quotes it) --
Q: "Does the satellite need a UER x HPI interaction, or do the main
    effects and momentum already account for the joint stress response?"
A: {"route": "REASONED", "args": {}}
Q: "Why does the double-trigger LTV x UER coefficient come out negative?"
A: {"route": "REASONED", "args": {}}
Q: "If unemployment and house prices both deteriorate at once, would you
    expect the combined hit to default risk to be additive, or worse than
    additive?"
A: {"route": "REASONED", "args": {}}

-- REFUSE (no connection to this model or credit risk) --
Q: "What's your view on Bitcoin as a hedge for our book?"
A: {"route": "REFUSE", "args": {}}
Q: "What will the Fed do with rates next year?"
A: {"route": "REFUSE", "args": {}}
Q: "Please compute 123 * 456 for me."
A: {"route": "REFUSE", "args": {}}
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

NARRATOR_DOCS_SYSTEM_PROMPT = """\
You are the NARRATOR for a documentation-retrieval tool over an IFRS 9 ECL
model's own wiki and knowledge corpus. You will receive a JSON object with
"question" and a list of "passages", each {"source", "citation", "text"}.

HARD RULES — violations are discarded by an automated check:
- Answer ONLY using the given passages. Never use outside knowledge, even
  if you believe it is correct — if the passages do not cover something,
  say so honestly instead of filling the gap.
- Every factual claim must be immediately followed by the citation of the
  passage it came from, in square brackets, EXACTLY as given (e.g.
  '... 12-month ECL for Stage 1 [pages/staging-model.md#Staging Model].').
  Use at least one citation; if you draw on more than one passage, cite
  each of the claims it supports.
- Do not invent, compute, or rescale any number. Only use a number if it
  appears verbatim in one of the passages' text.
- Short answer (2-5 sentences), plain factual tone, for a bank risk analyst.
"""

REASONED_SYSTEM_PROMPT = """\
You are the REASONING narrator for a validated IFRS 9 ECL model agent,
answering a CONCEPTUAL question this model's fixed tools do not compute and
its documentation retriever does not simply quote verbatim: model-design
rationale, interaction-term / joint-effect reasoning, "why is X modeled
this way" questions, and standard credit-risk economic intuition. You will
receive a JSON object with "question", a list of "passages" (each
{"source", "citation", "text"}, retrieved from this project's own wiki and
IFRS 9 knowledge corpus), and a "baseline" object (the engine's own
validated whole-book snapshot — numbers you may quote VERBATIM, never
rescale or recompute).

HARD RULES — violations are discarded by an automated check:
- Reason from the retrieved passages plus ordinary credit-risk economics.
  When a claim is this project's own documented design or data, cite the
  exact passage citation string, in square brackets, that supports it. It
  is fine to reason WITHOUT a citation when explaining general credit-risk
  economics rather than this project's own specifics — but never present
  something as this project's own finding without a citation backing it.
- State a number ONLY if it appears verbatim in a passage's text, in the
  "baseline" object, or in the "question" text itself. NEVER compute,
  estimate, rescale, or recall a number from your own general knowledge —
  if no grounded number is available, answer qualitatively and say so
  honestly rather than inventing one. This applies EQUALLY to a number
  spelled out in words ("two hundred million dollars", "forty-seven
  percent", "tens of millions") — an automated check treats a word-form
  estimate exactly like a digit one, so never use one to work around the
  no-new-numbers rule; if you are asked for "just intuition, no exact
  numbers," give a qualitative answer with no magnitude words at all.
- If the documentation is silent or ambiguous on the specific question,
  say that honestly; general credit-risk economic reasoning is welcome, but
  label it as general reasoning, not this project's own documented result.
- Short answer (2-5 sentences), plain factual tone, for a bank risk analyst
  who wants an honest, informed opinion — not a hedge-everything non-answer.
"""

#: prefix every REASONED answer with this machine-readable marker (spec:
#: "answer is prefixed with a machine-readable mode marker so the API/UI
#: can label it") — belt-and-suspenders alongside the API's own top-level
#: `mode` field (see app/api/main.py), never the ONLY signal the UI relies
#: on, since a template fallback answer carries it too.
REASONED_PREFIX = "[REASONED — interpretation, not engine output] "

CODE_WRITER_SYSTEM_PROMPT = """\
You are the CODE-WRITER for a sandboxed pandas analysis tool over the
frozen IFRS 9 ECL engine's t=60 scored book (Tier-2, agent/tools_tier2.py).
You never state a number yourself — you write pandas CODE that is then
EXECUTED in a validated sandbox, and only the EXECUTED result is ever shown
to the user.

Three read-only pandas DataFrames are already loaded for you — `pd` and
`np` are already imported, do not re-import them:

  book       one row per non-payoff loan at the t=60 reporting date:
             id (int), stage (int, 1/2/3), balance (float USD),
             updated_ltv (float, percent, may be NaN),
             fico (float, origination FICO score, may be NaN),
             investor (bool), allowance_up / allowance_base /
             allowance_down (float USD, per-scenario reported allowance for
             this loan), allowance_weighted (float USD, 50/25/25-weighted),
             coverage (float, allowance_weighted / balance).

  scenarios  one row per scenario ('up', 'base', 'down', 'weighted'):
             scenario (str), weight (float), allowance (float USD, total
             book allowance under that scenario), coverage (float).

  z_path     one row per panel quarter, time = 1..60 (reporting-date
             HISTORY): time (int), calendar (str, e.g. '2000Q2'),
             n_at_risk (int), z (float, recovered systematic factor),
             observed_default_rate (float), ttc_default_rate (float),
             pit_default_rate (float).

HARD RULES — violations are rejected before anything runs:
- Only pandas/numpy operations on `book`, `scenarios`, `z_path`. No other
  imports of any kind.
- Never use exec, eval, compile, open, input, getattr, setattr, delattr,
  globals, locals, vars, breakpoint, or any dunder attribute
  (`__class__`, `__mro__`, ...).
- Never call a `read_*` method (file I/O) or a `to_*` method other than
  `to_dict`/`to_list`/`to_numpy`/`to_frame`/`to_series` (no `to_csv`,
  `to_pickle`, ...).
- Assign your final answer to a variable named EXACTLY `result` — a
  DataFrame, Series, numpy array, dict, list, or plain scalar. This is the
  only thing that is returned; nothing else you write is ever shown.
- Output ONLY the Python code. No prose, no markdown code fences, no
  explanation before or after it.
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


def _llm_narrate_docs(tool_result: dict) -> tuple[str, str]:
    """Raw narrator completion over ONLY the retrieved passages (Tier-3)."""
    payload = {"question": tool_result.get("question"),
              "passages": tool_result.get("passages", [])}
    return _call_llm([
        {"role": "system", "content": NARRATOR_DOCS_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload)},
    ])


def _llm_reason(question: str, passages: list[dict], baseline: dict,
                *, retry: bool = False) -> tuple[str, str]:
    """Raw REASONED-narrator completion; (text, model_used).

    First attempt: the question + retrieved passages + baseline whitelist.
    Retry (only after a numeric-guard miss on the first attempt): an
    explicit no-new-numerics instruction is appended so the model reasons
    over the SAME grounding material again, rather than guess blind.
    """
    payload = {"question": question, "passages": passages,
              "baseline": baseline}
    user = json.dumps(payload)
    if retry:
        user += (
            "\n\nYour previous answer stated at least one number — digit or "
            "SPELLED OUT IN WORDS (e.g. 'two hundred million', 'forty-seven "
            "percent') — that does not appear verbatim in the passages, the "
            "baseline object, or the question above. Regenerate your answer "
            "WITHOUT stating any new number in EITHER form — reason "
            "qualitatively with no magnitude words at all, or quote a "
            "number only if it is verbatim in the material given.")
    return _call_llm([
        {"role": "system", "content": REASONED_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


def _llm_codegen(question: str, *, error: str | None = None,
                 previous_code: str | None = None) -> tuple[str, str]:
    """Raw code-writer completion (Tier-2); (text, model_used).

    First attempt: just the question. Repair attempt (``error`` given):
    the failing code and its error are handed back verbatim so the model
    can fix the SAME approach rather than guess blind.
    """
    if error is None:
        user = question
    else:
        user = (f"Original question: {question}\n\n"
               f"Your previous code:\n{previous_code}\n\n"
               f"That code FAILED with this error:\n{error}\n\n"
               f"Fix it and try again. Output ONLY the corrected code.")
    return _call_llm([
        {"role": "system", "content": CODE_WRITER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])


def _extract_code(text: str) -> str:
    """Strip a markdown code fence off the code-writer's output, if any."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", s).strip()
    return s


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

    route is one of TOOL_ROUTES, TIER3_ROUTE, or REFUSE. args are the
    pydantic-validated tool arguments (model_dump, so defaults are
    materialised). Any LLM failure, unparseable output, unknown route, or
    argument-validation failure collapses to REFUSE with a diagnostic
    detail string.
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
    if route not in ROUTE_ARG_MODELS:
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": f"unknown route {route!r}"}
    args = parsed.get("args") or {}
    if not isinstance(args, dict):
        return {"route": REFUSE, "args": {}, "model": model_used,
                "detail": "router args are not an object"}
    try:
        validated = ROUTE_ARG_MODELS[route](**args)
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


#: SPELLED-OUT numbers are a digit-blind hole in the guard above: a token
#: regex can only ever see digit characters, so "two hundred million
#: dollars" or "forty-seven percent" sail through `_number_tokens` with
#: ZERO tokens to check — an adversarially-probed, LIVE-confirmed way to
#: state an entirely invented magnitude while still passing every guard
#: that only inspects `_number_tokens`. This is a SEPARATE, word-level
#: check, applied alongside (never instead of) the digit check above by
#: every narration guard in this module.
_MAGNITUDE_WORDS = {
    "hundred", "hundreds", "thousand", "thousands", "million", "millions",
    "billion", "billions", "trillion", "trillions", "dozen", "dozens",
    "score", "scores",
}
_SMALL_NUMBER_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
    "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
}
_UNIT_WORDS = {
    "percent", "percentage", "pp", "bps", "dollars", "dollar", "usd",
    "cents", "cent", "basis",
}
_ALPHA_WORD_RE = re.compile(r"[A-Za-z]+")
_SPELLED_NUMBER_WINDOW = 4      # tokens either side to look for a unit word


def _spelled_number_violation(text: str) -> bool:
    """True iff TEXT states a spelled-out numeric magnitude the digit-only
    `_number_tokens` check cannot see.

    Two independently sufficient triggers, both case-insensitive:
      1. any MAGNITUDE noun (hundred/thousand/million/billion/trillion/
         dozen/score, singular or plural) appears at all — these words are
         essentially never used non-numerically in this financial domain,
         so their mere presence already states a magnitude ("tens of
         millions" is itself an estimate, with no digit and no leading
         number word);
      2. a small cardinal word (zero..ninety) appears within
         ``_SPELLED_NUMBER_WINDOW`` tokens of a unit word (percent/pp/bps/
         dollars/cents/basis) — catches "forty-seven percent" while NOT
         flagging ordinary prose uses of small number words elsewhere
         ("one interaction term", "the two main effects").
    """
    words = _ALPHA_WORD_RE.findall(text.lower())
    if any(w in _MAGNITUDE_WORDS for w in words):
        return True
    for i, w in enumerate(words):
        if w not in _SMALL_NUMBER_WORDS:
            continue
        lo = max(0, i - _SPELLED_NUMBER_WINDOW)
        hi = min(len(words), i + _SPELLED_NUMBER_WINDOW + 1)
        if any(words[j] in _UNIT_WORDS for j in range(lo, hi) if j != i):
            return True
    return False


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
    by $2.8m' matches a delta of -2.8). One miss fails the whole text. A
    SPELLED-OUT magnitude ("two hundred million dollars") is also a miss
    — see `_spelled_number_violation` — since the narrator's only legal
    numbers are the tool JSON's own digits, never a word-form estimate.
    """
    if _spelled_number_violation(text):
        return False
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
# docs narration check (the mechanical anti-hallucination guard, Tier-3)
# ---------------------------------------------------------------------------

def _numbers_in_passages(passages: list[dict]) -> list[float]:
    """Every number appearing verbatim in ANY retrieved passage's text."""
    allowed: list[float] = []
    for p in passages:
        for tok in _number_tokens(p.get("text", "")):
            try:
                allowed.append(float(tok.replace(",", "")))
            except ValueError:                    # pragma: no cover
                pass
    return allowed


def docs_answer_ok(text: str, tool_result: dict) -> bool:
    """True iff the narration cites a real passage AND invents no numbers.

    Three checks, all required (a single miss fails the whole text):
      1. at least one passage's `citation` string appears verbatim in the
         answer (the narrator must show its work);
      2. no SPELLED-OUT magnitude ("two hundred million dollars") — see
         `_spelled_number_violation`; a word-form estimate is exactly as
         invented as a digit one the passages never state;
      3. every number token in the answer equals — or is a plain rounding
         of — a number that appears somewhere in the passages' own text (a
         number is only legitimate if it was actually IN the documentation
         quoted back, never computed or recalled from the model's memory).
    """
    passages = tool_result.get("passages") or []
    if not passages:
        return False
    citations = [p["citation"] for p in passages if p.get("citation")]
    if not any(c and c in text for c in citations):
        return False
    if _spelled_number_violation(text):
        return False
    allowed = _numbers_in_passages(passages)
    for tok in _number_tokens(text):
        n = float(tok.replace(",", ""))
        decimals = len(tok.split(".")[1]) if "." in tok else 0
        tol = 0.5 * 10.0 ** (-decimals) + 1e-9
        if not any(abs(n - a) <= tol or abs(abs(n) - abs(a)) <= tol
                  for a in allowed):
            return False
    return True


def deterministic_docs_narration(tool_result: dict) -> str:
    """Fallback answer: list each retrieved passage under its citation.

    Used whenever the LLM narration fails the citation/number check above
    (or the narrator LLM itself errors) — never silently invents an answer.
    """
    passages = tool_result.get("passages") or []
    ref = tool_result.get("tool_call_id")
    if not passages:
        return ("The wiki and the IFRS 9 knowledge corpus have nothing that "
                f"directly addresses this question, so I have nothing to "
                f"cite. [engine-computed; audit ref {ref}]")
    lines = ["Here is what the documentation says:"]
    for p in passages:
        snippet = " ".join(p.get("text", "").split())
        if len(snippet) > 240:
            snippet = snippet[:240].rsplit(" ", 1)[0] + "…"
        lines.append(f"- [{p['citation']}] {snippet}")
    lines.append(f"[engine-computed; audit ref {ref}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# REASONED-route guard (the mechanical anti-hallucination guard, extended
# with a THIRD legal number source — the user's own question text — on top
# of the Tier-3 guard's two: retrieved passages and the engine's baseline)
# ---------------------------------------------------------------------------

def _question_numbers(question: str) -> list[float]:
    """Numbers the user's own question already contains verbatim — legal
    for the REASONED narrator to echo back (e.g. a rate the user names),
    never a number it computed or recalled itself."""
    out: list[float] = []
    for tok in _number_tokens(question or ""):
        try:
            out.append(float(tok.replace(",", "")))
        except ValueError:                        # pragma: no cover
            pass
    return out


def reasoned_answer_ok(text: str, tool_result: dict) -> bool:
    """True iff EVERY number in a REASONED answer is grounded.

    A number is legal iff it appears verbatim (or as a plain rounding at
    its own printed precision, sign-insensitive — the same tolerance rule
    as the Tier-1/Tier-3 guards) in one of three places: a retrieved
    passage's own text, the engine's baseline snapshot
    (``tool_result["baseline"]``, e.g. ``rerun_ecl(segment="all")``), or the
    user's own question. No citation is required (unlike the Tier-3 guard)
    — a REASONED answer may legitimately be pure credit-risk economic
    reasoning with nothing to cite — only the numeric discipline is a hard
    gate. One miss fails the whole text.

    A SPELLED-OUT magnitude ("two hundred million dollars", "forty-seven
    percent", "tens of millions") is ALSO a hard miss, unconditionally —
    see `_spelled_number_violation`. This route is the one most exposed to
    "just give me intuition, no exact numbers" scope-gaming, and a
    word-form estimate is exactly as invented as a digit one when it
    doesn't come from the passages/baseline/question; it is not whitelisted
    against an echoed question number either, deliberately, to close off
    the whole class rather than special-case it.
    """
    if _spelled_number_violation(text):
        return False
    passages = tool_result.get("passages") or []
    baseline = tool_result.get("baseline") or {}
    question = tool_result.get("question") or ""
    allowed = (_numbers_in_passages(passages) + _allowed_numbers(baseline)
              + _question_numbers(question))
    for tok in _number_tokens(text):
        n = float(tok.replace(",", ""))
        decimals = len(tok.split(".")[1]) if "." in tok else 0
        tol = 0.5 * 10.0 ** (-decimals) + 1e-9
        if not any(abs(n - a) <= tol or abs(abs(n) - abs(a)) <= tol
                  for a in allowed):
            return False
    return True


def deterministic_reasoned_fallback(tool_result: dict) -> str:
    """Engine-authored fallback: a qualitative passage listing (never a new
    number) plus a pointer to the closest validated tool — used whenever
    the REASONED narrator's own prose fails the numeric guard on both
    attempts, or the reasoning LLM itself errors both times."""
    passages = tool_result.get("passages") or []
    ref = tool_result.get("tool_call_id")
    if passages:
        lines = ["I can offer a qualitative interpretation grounded in the "
                 "retrieved documentation, without stating a new number:"]
        for p in passages[:3]:
            snippet = " ".join(p.get("text", "").split())
            if len(snippet) > 220:
                snippet = snippet[:220].rsplit(" ", 1)[0] + "…"
            lines.append(f"- [{p['citation']}] {snippet}")
    else:
        lines = ["I have no documentation passage directly on point, so I "
                 "will not speculate with numbers."]
    lines.append(
        "For an exact figure, the closest validated tool is analyze_data "
        "(an ad-hoc query over the scored book) or query_model_docs (a "
        "cited documentation lookup) — ask me to run one of those.")
    lines.append(f"[engine-computed; audit ref {ref}]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# graph state + nodes
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    question: str
    route: str
    tool_args: dict
    tool_result: dict
    answer: str
    #: top-level API-facing classification of `answer` — "grounded" (a tool/
    #: docs answer), "reasoned" (the REASONED route), or "refusal". Set by
    #: whichever terminal node (narrator/REASONED/refusal) produces `answer`
    #: — never inferred elsewhere, so it always matches what actually ran.
    mode: str
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


def _query_model_docs_node(state: AgentState) -> dict:
    """Tier-3 tool node: ALWAYS retrieves on the user's own original
    question — never a router-authored paraphrase (state["tool_args"] is
    empty by construction, see QueryModelDocsArgs)."""
    try:
        result = query_model_docs(question=state["question"])
        event = {"node": TIER3_ROUTE, "ts": _now(), "status": "ok",
                 "tool_call_id": result.get("tool_call_id"),
                 "headline": result.get("headline")}
    except Exception as exc:          # retrieval failure: honest, no answer
        result = {"error": f"{type(exc).__name__}: {exc}",
                  "tool": TIER3_ROUTE}
        event = {"node": TIER3_ROUTE, "ts": _now(), "status": "error",
                 "detail": result["error"]}
    return {"tool_result": result, "trace": [event]}


def _reasoned_node(state: AgentState) -> dict:
    """REASONED route: a conceptual question no tool computes and the docs
    retriever does not simply quote. Self-contained — unlike the Tier-1/
    Tier-3 tool nodes it does NOT hand off to ``_narrator_node``; it
    produces the final ``answer`` (and ``mode: "reasoned"``) itself, then
    the graph edges straight to END (see build_graph()), mirroring how
    ``_refusal_node`` also produces a final answer directly.

    Grounding sources: (a) Tier-3 retrieval on the user's own original
    question (never a router paraphrase — same discipline as
    ``_query_model_docs_node``), and (b) the engine's own baseline snapshot
    (``rerun_ecl(segment="all")``, read through the live TIER1_TOOLS
    registry so offline tests can monkeypatch it exactly like every other
    Tier-1 call). Either source failing is honest, not fatal — an empty
    passages list / empty baseline just narrows what the reasoning LLM may
    legally state a number about; it never blocks the qualitative answer.
    """
    question = state["question"]
    try:
        passages = query_model_docs(question=question).get("passages", [])
    except Exception:                          # retrieval failure: honest
        passages = []
    try:
        baseline = TIER1_TOOLS["rerun_ecl"](segment="all")
    except Exception:                          # engine failure: honest
        baseline = {}

    tool_result = {"tool": REASONED, "question": question,
                   "passages": passages, "baseline": baseline}

    def _attempt(retry: bool) -> tuple[str | None, str | None, bool, str]:
        try:
            text, model_used = _llm_reason(question, passages, baseline,
                                           retry=retry)
        except Exception as exc:
            return (None, None, False,
                    f"template_llm_error:{type(exc).__name__}")
        ok = reasoned_answer_ok(text, tool_result)
        return text, model_used, ok, ("llm" if ok
                                      else "template_number_check_failed")

    text, model_used, ok, mode = _attempt(retry=False)
    attempts = [{"attempt": 1, "ok": ok, "mode": mode}]
    if not ok:
        text2, model_used2, ok2, mode2 = _attempt(retry=True)
        attempts.append({"attempt": 2, "ok": ok2, "mode": mode2})
        if ok2:
            text, model_used, ok, mode = text2, model_used2, True, \
                "llm_repaired"
        else:
            mode = mode2

    headline = (f"reasoned interpretation grounded in {len(passages)} "
               f"documentation passage(s) and the baseline engine snapshot "
               f"for {question!r} — no new number was stated.")
    tool_call_id = _log_call(
        REASONED, {"question": question, "n_passages": len(passages)},
        headline)
    tool_result["headline"] = headline
    tool_result["tool_call_id"] = tool_call_id

    body = text.strip() if ok else deterministic_reasoned_fallback(tool_result)
    answer = f"{REASONED_PREFIX}{body}"
    return {
        "answer": answer,
        "tool_result": tool_result,
        "mode": "reasoned",
        "trace": [{"node": REASONED, "ts": _now(), "mode": mode,
                   "model": model_used, "number_check_passed": bool(ok),
                   "attempts": attempts, "tool_call_id": tool_call_id,
                   "headline": headline}],
    }


def _analyze_data_node(state: AgentState) -> dict:
    """Tier-2 tool node: code-writer LLM -> sandbox -> ONE repair attempt ->
    else the question falls through to REFUSAL (module docstring; the
    conditional edge out of this node in build_graph() reads
    ``"error" in tool_result`` to make that call — never the narrator's
    generic honest-failure path used by Tier-1/Tier-3).

    ALWAYS codes against the user's own original question — never a
    router-authored paraphrase (state["tool_args"] is empty by
    construction, see agent.tools_tier2.AnalyzeDataArgs)."""
    question = state["question"]
    attempts: list[dict] = []

    try:
        raw, model_used = _llm_codegen(question)
        code = _extract_code(raw)
    except Exception as exc:                  # both code-gen models failed
        detail = f"code-gen LLM unavailable: {type(exc).__name__}: {exc}"
        return {"tool_result": {"error": detail, "tool": TIER2_ROUTE},
                "trace": [{"node": TIER2_ROUTE, "ts": _now(),
                           "status": "error", "detail": detail,
                           "attempts": attempts}]}

    sb = run_sandboxed(code)
    attempts.append({"attempt": 1, "code": code, "ok": sb["ok"],
                     "error": sb["error"]})

    if not sb["ok"]:
        try:
            raw2, model_used2 = _llm_codegen(question, error=sb["error"],
                                             previous_code=code)
            code2 = _extract_code(raw2)
            sb2 = run_sandboxed(code2)
            attempts.append({"attempt": 2, "code": code2, "ok": sb2["ok"],
                             "error": sb2["error"]})
            if sb2["ok"]:
                code, sb, model_used = code2, sb2, model_used2
        except Exception as exc:              # repair LLM unavailable
            attempts.append({
                "attempt": 2, "code": None, "ok": False,
                "error": f"repair LLM unavailable: {type(exc).__name__}: "
                        f"{exc}"})

    if not sb["ok"]:
        detail = sb["error"]
        return {"tool_result": {"error": detail, "tool": TIER2_ROUTE,
                                "code": code},
                "trace": [{"node": TIER2_ROUTE, "ts": _now(),
                           "status": "error", "detail": detail,
                           "attempts": attempts}]}

    result_hash = hashlib.sha256(
        json.dumps(sb["result_preview"], default=str,
                   sort_keys=True).encode()).hexdigest()[:16]
    headline = (f"analyze_data executed generated pandas code against the "
               f"t=60 scored book (result shape {sb['result_shape']}); "
               f"full code in the audit trail (result hash {result_hash}).")
    tool_call_id = _log_call(
        TIER2_ROUTE, {"question": question, "code": code,
                     "result_hash": result_hash}, headline)
    result = {"tool": TIER2_ROUTE, "question": question, "code": code,
             "result_preview": sb["result_preview"],
             "result_shape": sb["result_shape"], "result_hash": result_hash,
             "headline": headline, "tool_call_id": tool_call_id}
    return {"tool_result": result,
            "trace": [{"node": TIER2_ROUTE, "ts": _now(), "status": "ok",
                       "tool_call_id": tool_call_id, "headline": headline,
                       "model": model_used, "attempts": attempts}]}


def _narrator_node(state: AgentState) -> dict:
    result = state["tool_result"]
    if "error" in result:
        answer = (f"The {result.get('tool', 'requested')} engine call "
                  f"failed ({result['error']}); no numbers were produced, "
                  f"so I have none to report. Please retry or contact the "
                  f"model owners.")
        return {"answer": answer, "mode": "grounded",
                "trace": [{"node": "narrator", "ts": _now(),
                           "mode": "tool_error"}]}
    if result.get("tool") == TIER3_ROUTE:
        out = _narrate_docs(result)
        out["mode"] = "grounded"
        return out
    try:
        text, model_used = _llm_narrate(result)
        ok = narration_numbers_ok(text, result)
        mode = "llm" if ok else "template_number_check_failed"
    except Exception as exc:
        text, model_used, ok = None, None, False
        mode = f"template_llm_error:{type(exc).__name__}"
    answer = text.strip() if ok else deterministic_narration(result)
    return {"answer": answer, "mode": "grounded",
            "trace": [{"node": "narrator", "ts": _now(), "mode": mode,
                       "model": model_used,
                       "number_check_passed": bool(ok)}]}


def _narrate_docs(result: dict) -> dict:
    """Tier-3 narration branch: cite-and-quote only, or the deterministic
    'here is what the documentation says' passage listing on any failure."""
    try:
        text, model_used = _llm_narrate_docs(result)
        ok = docs_answer_ok(text, result)
        mode = "llm" if ok else "template_citation_check_failed"
    except Exception as exc:
        text, model_used, ok = None, None, False
        mode = f"template_llm_error:{type(exc).__name__}"
    answer = text.strip() if ok else deterministic_docs_narration(result)
    return {"answer": answer,
            "trace": [{"node": "narrator", "ts": _now(), "mode": mode,
                       "model": model_used,
                       "citation_check_passed": bool(ok)}]}


def _refusal_node(state: AgentState) -> dict:
    return {"answer": REFUSAL_MESSAGE, "tool_result": {}, "mode": "refusal",
            "trace": [{"node": "refusal", "ts": _now(),
                       "message": "fixed refusal issued"}]}


def build_graph():
    """Compile the StateGraph (router -> tool -> narrator | REASONED | refusal).

        START -> router -+-> shock_macro ------------+
                         +-> reweight_scenarios ------+
                         +-> rerun_ecl ----------------+-> narrator -> END
                         +-> decompose_waterfall ------+
                         +-> query_model_docs ---------+
                         +-> analyze_data -+-> narrator ------------------> END
                         |                 +-> refusal (repair failed) ----> END
                         +-> REASONED -------------------------------------> END
                         +-> refusal --------------------------------------> END
    """
    g = StateGraph(AgentState)
    g.add_node("router", _router_node)
    for name in TOOL_ROUTES:
        g.add_node(name, _make_tool_node(name))
        g.add_edge(name, "narrator")
    g.add_node(TIER3_ROUTE, _query_model_docs_node)
    g.add_edge(TIER3_ROUTE, "narrator")
    g.add_node(TIER2_ROUTE, _analyze_data_node)
    g.add_conditional_edges(
        TIER2_ROUTE,
        lambda s: "refusal" if "error" in s["tool_result"] else "narrator",
        {"refusal": "refusal", "narrator": "narrator"})
    g.add_node("narrator", _narrator_node)
    g.add_node(REASONED, _reasoned_node)
    g.add_edge(REASONED, END)
    g.add_node("refusal", _refusal_node)
    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router", lambda s: s["route"],
        {**{name: name for name in TOOL_ROUTES}, TIER3_ROUTE: TIER3_ROUTE,
         TIER2_ROUTE: TIER2_ROUTE, REASONED: REASONED, REFUSE: "refusal"})
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
    answer, mode, trace) and appends {ts, question, route, answer, trace} to
    outputs/agent_log/agent_runs.jsonl (mode is intentionally NOT added to
    the on-disk audit record — it is redundant with route there and adding
    it would be a breaking change to that log's schema).
    """
    final = get_graph().invoke({
        "question": question, "route": "", "tool_args": {},
        "tool_result": {}, "answer": "", "mode": "", "trace": [],
    })
    _log_run({"ts": _now(), "question": question, "route": final["route"],
              "answer": final["answer"], "trace": final["trace"]})
    return final
