"""FastAPI backend: the frozen ECL engine, the Tier-1 agent, the built UI.

One process serves three things on port 7860 (HF Spaces Docker convention):

  1. Engine data (read-only views over agent/tools_tier1.py caches)
       GET /api/health                 liveness + warm-up timing
       GET /api/ecl/summary            headline stats + scenario table
       GET /api/ecl/waterfall          movement decomposition between snapshots
       GET /api/exhibits/credit_cycle  Z path from outputs/vasicek/z_path.csv

  2. The agent
       POST /api/tools/{tool}          the four Tier-1 tools, pydantic-guarded
       POST /api/agent/ask             {question} -> {answer, route, mode, trace}
       GET  /api/agent/stream          SSE replay/live feed of the latest trace

  3. The built SPA: StaticFiles mount of app/ui/dist at / (a graceful
     'UI not built' page when the dist is missing).

THE GOVERNING RULE (project-wide, review-enforced): the LLM never does
arithmetic. Every number in every response is computed by the engine via
agent/tools_tier1.py (or simple probability-weighted aggregation of the
engine's own per-loan outputs, done here in typed server code, never by a
model). Out-of-scope questions get an explicit refusal — a governance
feature, demonstrated on purpose.

Agent seam
----------
The Day-4 LangGraph router plugs in by either
  * exposing `ask(question: str, emit: Callable[[dict], None] | None = None)
    -> {"answer": str, "route": str, "mode": str, "trace": list[dict]}` in
    agent/graph.py or agent/router.py (resolved at lifespan startup), or
  * setting `app.api.main.AGENT_ASK` directly (what the tests do to mock it).
Until it lands, a deterministic keyword fallback router answers: it routes
to the same four Tier-1 tools, narrates ONLY the engine-built headline
strings, and refuses everything else ("outside my validated scope"). It
makes no LLM call, so the app runs fully offline.

`mode` classifies the answer for the UI's status indicator: `"grounded"`
(a numeric tool or the cited docs retriever answered), `"reasoned"` (the
REASONED route — a cited, number-disciplined LLM interpretation, never a
fresh engine number), or `"refusal"`. If the resolved agent callable
already returns a `mode`, it is passed through untouched; if it does not
(e.g. the offline fallback router, or a minimal test mock), `_run_agent`
derives it from `route` (REASONED -> "reasoned", a refusal spelling ->
"refusal", else "grounded") so the field is ALWAYS present.

Trace events are dicts {"node": router|tool|narrator|refusal, "label", ...}.
Every /ask resets an in-memory ring buffer (TraceBroker) and publishes its
events there; GET /api/agent/stream replays the buffered latest trace, then
streams live events as SSE `data:` lines with 15s keep-alive comments.

KNOWN LIMITATION (documented, accepted for the demo): TraceBroker is
in-process memory — run uvicorn with A SINGLE WORKER. Multiple workers
would each hold their own buffer and the SSE feed would only see the traces
of whichever worker the stream connection landed on. The naive
1-concurrent-question semaphore on /ask is likewise per-process.

Security posture
----------------
* Same-origin only: the SPA is served by this same app, so NO CORS
  middleware is added — browsers' default same-origin policy is the policy.
* No secret ever enters a response: this module never reads .env at all;
  key loading happens (masked) inside the agent layer, server-side only.
* Malformed tool arguments are rejected by pydantic (422) BEFORE any engine
  code runs, and validation failures are never written to the audit trail.

Startup: `warm_up()` from agent/tools_tier1.py runs once in the lifespan
(joblib warm start ~9s, cold refit ~19-50s); tool calls then answer in
seconds from in-memory state. Startup timing is logged and reported by
/api/health.

Run:  cd <repo> && uv run --no-sync uvicorn app.api.main:app --port 7860
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import math
import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import agent.graph as agent_graph
import agent.tools_tier1 as tools
from agent.tools_tier1 import (
    DecomposeWaterfallArgs,
    RerunEclArgs,
    ReweightArgs,
    ShockMacroArgs,
)
from engine.scenarios import panel_time_to_period

logger = logging.getLogger("ecl.api")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UI_DIST = PROJECT_ROOT / "app" / "ui" / "dist"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
Z_PATH_CSV = PROJECT_ROOT / "outputs" / "vasicek" / "z_path.csv"

#: seconds between SSE keep-alive comments on /api/agent/stream
SSE_KEEPALIVE_S = 15.0

#: candidate homes of the Day-4 LangGraph router (module docstring seam)
AGENT_MODULES = ("agent.graph", "agent.router")
AGENT_ATTRS = ("ask", "answer_question", "run_agent")

REFUSAL_TEXT = (
    "That question is outside my validated scope. I can only answer with "
    "numbers the frozen IFRS 9 engine computes: shock a macro variable "
    "(shock_macro), reweight the three scenarios (reweight_scenarios), "
    "break the allowance out by segment (rerun_ecl), or decompose the "
    "allowance movement between two dates (decompose_waterfall). Refusing "
    "out-of-scope questions is a deliberate governance feature of this "
    "copilot, not a failure."
)

# ---------------------------------------------------------------------------
# in-memory trace pub/sub (single-worker demo — module docstring limitation)
# ---------------------------------------------------------------------------


class TraceBroker:
    """Ring buffer of the most recent /ask trace + live asyncio fan-out.

    `publish` is called from worker threads (the agent runs in the FastAPI
    threadpool); subscribers are asyncio.Queues living on the main event
    loop, so hand-off goes through `loop.call_soon_threadsafe`. Every event
    gets a process-monotonic `_id` so the SSE generator can replay the
    buffer and then skip queue duplicates deterministically.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buffer: list[dict] = []
        self._subs: set[asyncio.Queue] = set()
        self._next_id = 0
        self.loop: asyncio.AbstractEventLoop | None = None

    def start_trace(self) -> None:
        """A new /ask begins: the buffer now holds only its events."""
        with self._lock:
            self._buffer = []

    def publish(self, event: dict) -> None:
        ev = dict(event)
        with self._lock:
            self._next_id += 1
            ev["_id"] = self._next_id
            self._buffer.append(ev)
            subs, loop = list(self._subs), self.loop
        if loop is not None:
            for q in subs:
                loop.call_soon_threadsafe(q.put_nowait, ev)

    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self._buffer)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs.discard(q)


BROKER = TraceBroker()

#: naive 1-concurrent limit on /api/agent/ask (per process, demo-grade)
_ASK_SEMAPHORE = threading.Semaphore(1)

#: resolved agent callable (Day-4 router or None -> keyword fallback);
#: tests monkeypatch this attribute to mock the LLM
AGENT_ASK: Callable | None = None


# ---------------------------------------------------------------------------
# deterministic fallback router (no LLM, offline; refusal is a feature)
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_INT_RE = re.compile(r"\b\d+\b")

_SHOCK_VARS = (
    ("UER", ("unemploy", "uer", "jobless")),
    ("HPI", ("hpi", "house", "housing", "home price", "property")),
    ("GDP", ("gdp",)),
)
_NEGATIVE_WORDS = ("fall", "drop", "decline", "contract", "crash", "slump",
                   "decrease", "lower", "down ")
_SEGMENTS = (
    ("stage3", ("stage 3", "stage3", "impaired")),
    ("stage2", ("stage 2", "stage2", "sicr")),
    ("stage1", ("stage 1", "stage1")),
    ("investor", ("investor",)),
    ("high_ltv", ("high ltv", "high-ltv", "high_ltv", "ltv")),
)


def _fallback_ask(question: str, emit: Callable[[dict], None]) -> dict:
    """Keyword router over the four Tier-1 tools; everything else refuses.

    Narration is EXCLUSIVELY the engine-built `headline` string returned by
    the tool — this function computes nothing (governing rule). It exists
    so the app demos end-to-end before/without the LangGraph router and is
    replaced by it through the module-docstring seam.
    """
    q = question.lower()
    tool_name, kwargs = _route(q)
    emit({"node": "router", "label": "classify",
          "route": tool_name or "refusal",
          "detail": "deterministic keyword fallback router (no LLM)"})

    if tool_name is None:
        emit({"node": "refusal", "label": "out of scope",
              "answer": REFUSAL_TEXT})
        return {"answer": REFUSAL_TEXT, "route": "refusal"}

    try:
        validated = tools.TIER1_ARG_MODELS[tool_name](**kwargs)
    except ValidationError as e:
        msg = (f"I routed this to {tool_name} but the arguments failed "
               f"validation before any engine code ran: "
               f"{e.errors()[0]['msg']}. Nothing was computed or logged.")
        emit({"node": "refusal", "label": "argument validation failed",
              "tool": tool_name, "answer": msg})
        return {"answer": msg, "route": "refusal"}

    emit({"node": "tool", "label": f"calling {tool_name}",
          "tool": tool_name, "args": validated.model_dump()})
    result = tools.TIER1_TOOLS[tool_name](**validated.model_dump())
    answer = (f"{result['headline']}. Every figure above was computed by "
              f"the frozen engine (audit ref {result['tool_call_id']}).")
    emit({"node": "narrator", "label": "narrating engine output",
          "tool": tool_name, "tool_call_id": result["tool_call_id"],
          "answer": answer})
    return {"answer": answer, "route": tool_name, "result": result}


def _route(q: str) -> tuple[str | None, dict]:
    """Question (lowercased) -> (tool name | None for refusal, kwargs)."""
    nums = [float(m) for m in _NUM_RE.findall(q)]

    if "weight" in q or "probabilit" in q:
        if len(nums) >= 3:
            w = nums[:3]
            if abs(sum(w) - 100.0) < 1e-6:          # "40/40/20 percent"
                w = [x / 100.0 for x in w]
            return "reweight_scenarios", dict(
                w_up=w[0], w_base=w[1], w_down=w[2])
        return "reweight_scenarios", dict(w_up=0.25, w_base=0.5, w_down=0.25)

    if any(k in q for k in ("waterfall", "movement", "decompos", "bridge")):
        ints = [int(m) for m in _INT_RE.findall(q)
                if 1 <= int(m) <= tools.T_SNAP]
        if len(ints) >= 2 and ints[0] < ints[1]:
            return "decompose_waterfall", dict(t0=ints[0], t1=ints[1])
        return "decompose_waterfall", dict()

    for var, keys in _SHOCK_VARS:
        if any(k in q for k in keys):
            shock = nums[0] if nums else 1.0
            if (shock > 0 and f"+{shock:g}" not in q
                    and any(w in q for w in _NEGATIVE_WORDS)):
                shock = -shock                       # "prices fall 2pp" -> -2
            shape = ("peak_revert"
                     if any(k in q for k in ("revert", "peak", "temporar"))
                     else "parallel")
            return "shock_macro", dict(var=var, shock=shock, shape=shape)

    for seg, keys in _SEGMENTS:
        if any(k in q for k in keys):
            return "rerun_ecl", dict(segment=seg)

    if any(k in q for k in ("allowance", "ecl", "coverage", "provision")):
        return "rerun_ecl", dict(segment="all")

    return None, {}


# ---------------------------------------------------------------------------
# agent execution (threadpool worker; publishes to the broker)
# ---------------------------------------------------------------------------


def _resolve_agent() -> Callable | None:
    """Find the Day-4 router if it exists (module docstring seam)."""
    for mod_name in AGENT_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        except Exception:                            # broken module: fallback
            logger.warning("agent module %s failed to import; using the "
                           "deterministic fallback router", mod_name,
                           exc_info=True)
            continue
        for attr in AGENT_ATTRS:
            fn = getattr(mod, attr, None)
            if callable(fn):
                logger.info("agent resolved: %s.%s", mod_name, attr)
                return fn
    logger.info("no LangGraph router found; the deterministic keyword "
                "fallback router is active (offline, refusal-capable)")
    return None


#: mirrors the UI's own `isRefusalRoute` regex (app/ui/src/components/
#: ChatPanel.jsx) so client and server never disagree on what counts as a
#: refusal: the live LangGraph router emits route "REFUSE", the offline
#: keyword fallback router emits "refusal".
_REFUSAL_ROUTE_RE = re.compile(r"^refus(e|al)$", re.IGNORECASE)


def _mode_from_route(route: str) -> str:
    """Fallback `mode` derivation for an agent callable that does not
    itself return one (the offline deterministic fallback router, or a
    minimal test mock) — "reasoned" for the REASONED route, "refusal" for
    either refusal spelling, else "grounded" (a numeric tool or the cited
    docs retriever)."""
    if _REFUSAL_ROUTE_RE.match(route or ""):
        return "refusal"
    if route == getattr(agent_graph, "REASONED", "REASONED"):
        return "reasoned"
    return "grounded"


def _run_agent(question: str) -> dict:
    """Synchronous agent run (called in the threadpool by /ask)."""
    events: list[dict] = []

    def emit(event: dict) -> None:
        events.append(dict(event))
        BROKER.publish(event)

    BROKER.start_trace()
    fn = AGENT_ASK or _fallback_ask
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):                  # builtins, mocks
        params = {}
    raw = fn(question, emit=emit) if "emit" in params else fn(question)

    if isinstance(raw, dict):
        answer = str(raw.get("answer", ""))
        route = str(raw.get("route", "unknown"))
        trace = raw.get("trace") or events
        mode = str(raw["mode"]) if raw.get("mode") else _mode_from_route(route)
    else:
        answer, route, trace = str(raw), "unknown", events
        mode = _mode_from_route(route)
    if not events and trace:          # agent returned a trace without emitting
        for ev in trace:              # -> replay it so /stream still shows it
            BROKER.publish(dict(ev))
    return {"answer": answer, "route": route, "mode": mode, "trace": trace}


# ---------------------------------------------------------------------------
# request/response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


class InterpretRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Literal["shock_macro", "reweight_scenarios", "rerun_ecl",
                 "decompose_waterfall", "query_model_docs"]
    result: dict


# ---------------------------------------------------------------------------
# app + lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.perf_counter()
    BROKER.loop = asyncio.get_running_loop()
    # warm the engine caches in a thread so the loop keeps serving
    await run_in_threadpool(tools.warm_up)
    warm_s = time.perf_counter() - t0
    global AGENT_ASK
    if AGENT_ASK is None:
        AGENT_ASK = _resolve_agent()
    app.state.warm_up_seconds = round(warm_s, 2)
    logger.info("engine state warm in %.1fs (joblib cache at "
                "outputs/models/); agent=%s", warm_s,
                "langgraph" if AGENT_ASK else "fallback")
    yield


app = FastAPI(
    title="IFRS 9 ECL Copilot API",
    description=__doc__,
    version="1.0.0",
    lifespan=lifespan,
    # same-origin only: the SPA is served by this app; no CORS middleware
)


def _json_safe(obj):
    """Recursively make a validation-error payload strictly JSON-safe.

    FastAPI's default 422 handler echoes the offending input inside
    `detail`; a NaN/inf body value (legal for python's json.loads, illegal
    for the strict encoder) would otherwise crash the 422 response into a
    500. Non-finite floats and exotic objects (e.g. the ValueError inside
    pydantic's ctx) become strings.
    """
    if isinstance(obj, float) and not math.isfinite(obj):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


@app.exception_handler(RequestValidationError)
async def _request_validation_handler(request: Request,
                                      exc: RequestValidationError):
    return JSONResponse(status_code=422,
                        content={"detail": _json_safe(exc.errors())})


# ---------------------------------------------------------------------------
# 1. engine data views (read-only; never write the audit trail)
# ---------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "engine_warm": tools._STATE is not None,
        "warm_up_seconds": getattr(app.state, "warm_up_seconds", None),
        "agent": "langgraph" if AGENT_ASK else "fallback",
    }


@app.get("/api/ecl/summary")
def ecl_summary() -> dict:
    """Headline stats + the scenario table for the dashboard header.

    All figures are read (or probability-weighted with the ADOPTED weights)
    from the per-loan books the engine built at warm-up — no model is
    invoked and nothing is appended to the audit trail by this view.
    """
    state = tools._state()
    w = {n: float(state.sset.weights[n]) for n in ("up", "base", "down")}
    tot = state.scenario_totals

    weighted = sum(w[n] * tot[n] for n in ("up", "base", "down"))
    at_avg = tot["weighted"]          # book run at the weighted-average path
    balance = state.balance

    # per-loan probability-weighted allowance -> stage mix of the REPORTED
    # number (row order is scenario-invariant, asserted at build time)
    weighted_book = state.books["base"][["stage", "balance"]].copy()
    weighted_book["ecl_reported"] = sum(
        w[n] * state.books[n]["ecl_reported"].to_numpy(dtype=float)
        for n in ("up", "base", "down"))
    stage_mix = tools._stage_mix(weighted_book)

    scenarios = []
    for name in ("up", "base", "down"):
        zbar = float(np.mean(
            state.zpaths[name].to_numpy(dtype=float)[:int(state.sset.rs_window)]))
        uer_peak = float(state.sset.paths[name]["uer"].max())
        scenarios.append({
            "name": name,
            "weight": w[name],
            "allowance": float(tot[name]),
            "coverage": float(tot[name] / balance),
            "zbar_13q": zbar,
            "uer_peak_pp": uer_peak,
        })

    return {
        "as_of": {"t": tools.T_SNAP,
                  "period": str(panel_time_to_period(tools.T_SNAP))},
        "n_loans": int(len(weighted_book)),
        "balance": float(balance),
        "weights": w,
        "weighted_allowance": float(weighted),
        "coverage": float(weighted / balance),
        "allowance_at_average_path": float(at_avg),
        "jensen_ratio": float(weighted / at_avg),
        "stage_mix": stage_mix,
        "scenarios": scenarios,
        "amounts_in": "USD",
    }


@app.get("/api/ecl/waterfall")
def ecl_waterfall(t0: int = Query(default=20),
                  t1: int = Query(default=40)) -> dict:
    """Movement decomposition between two rung-1 snapshots.

    Delegates to the Tier-1 tool (frozen-engine identity asserted inside);
    the call is therefore also visible in the audit trail like any other
    tool invocation.
    """
    try:
        return tools.decompose_waterfall(t0=t0, t1=t1)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=json.loads(e.json()))


@app.get("/api/exhibits/credit_cycle")
def credit_cycle() -> dict:
    """The recovered credit-cycle series Z_t with calendar labels.

    Serves outputs/vasicek/z_path.csv (Day-3 exhibit; t=1 ~ 2000Q2) plus the
    asset-correlation rho from the warm engine state, for the PIT-vs-TTC
    cycle chart.
    """
    if not Z_PATH_CSV.exists():
        raise HTTPException(
            status_code=503,
            detail=f"{Z_PATH_CSV} missing — run analysis/run_vasicek.py "
                   f"(Day-3 exhibit) first")
    df = pd.read_csv(Z_PATH_CSV)
    state = tools._state()
    points = [
        {
            "t": int(r["time"]),
            "calendar": str(r["calendar"]),
            "z": float(r["z_main"]),
            "observed_dr": float(r["observed"]),
            "ttc_pd": float(r["expected_ttc"]),
            "pit_pd": float(r["pit_pd_flat_anchor"]),
        }
        for _, r in df.iterrows()
    ]
    return {"rho": float(state.res.rho), "n_quarters": len(points),
            "points": points}


# ---------------------------------------------------------------------------
# App v2: The Model / Policy tabs -- read-only markdown-exhibit parsers.
#
# These views parse the consultant's already-written analysis markdown
# under outputs/ into JSON on every request (the files are small; no engine
# state is touched, nothing is appended to the audit trail). Exact response
# shapes are documented in docs/api_contract.md — THAT file is the single
# source of truth the UI author codes against, not this docstring.
# ---------------------------------------------------------------------------


def _md_table_span(lines: list[str]) -> tuple[int, int] | None:
    """First contiguous run of '|'-prefixed lines -> (start, end) exclusive."""
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return i, j
        i += 1
    return None


def _md_table_rows(block: list[str]) -> list[dict]:
    """A GFM pipe table (header, separator, data rows...) -> list of dicts."""
    header = [c.strip() for c in block[0].strip().strip("|").split("|")]
    rows = []
    for line in block[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _md_sections(text: str) -> list[tuple[str, str]]:
    """(title, body) for every '## ' section of a markdown file, in order."""
    return re.findall(r"^## (.+?)\n(.*?)(?=\n## |\Z)", text, flags=re.S | re.M)


def _num(s: str) -> float:
    return float(s.replace(",", "").replace("+", ""))


def _pct(s: str) -> float:
    return float(s.strip().rstrip("%"))


def _parse_p(s: str) -> tuple[float, str]:
    """'<1e-16' -> (1e-16, '<1e-16'); '2.35e-06' -> (2.35e-06, '2.35e-06')."""
    s = s.strip()
    return (float(s[1:]) if s.startswith("<") else float(s)), s


def _parse_ci(s: str) -> list[float]:
    lo, hi = s.strip().strip("[]").split(",")
    return [float(lo), float(hi)]


# ---------------------------------------------------------------------------
# Requirement 12 -- macro/FRED interpretation, first-class in the app.
#
# One curated, grounded fact registry (`_CONCEPTS`) keyed by a normalised
# "concept" id, joined onto each parsed coefficient/variable-dictionary row
# by a per-source label->concept lookup below. Content is transcribed from
# outputs/variable_dictionary.md, outputs/hazard/hazard_ratios.md,
# outputs/freddie/hazard/hazard_report.md + coefficients.csv +
# dcr_sign_comparison.csv, outputs/satellite/satellite_report.md and
# freddie/macro.py's docstrings -- never invented. The two NUMBERS every
# concept needs (hazard_ratio_per_unit, worked_example) are the only part
# computed here, mechanically, from the coefficient the row itself carries
# (GOVERNING RULE: the LLM never does arithmetic; here, neither does a
# human -- see _hazard_ratio_per_unit / _worked_example below).
#
# unit_kind drives the worked-example arithmetic:
#   "direct"      -- HR already reads per the stated unit (e.g. per 10pp).
#   "log1pct"     -- HR in the source table is per a FULL 1.0 log-unit
#                    (~100% growth, never observed); the economically
#                    legible unit is 1% growth (0.01 log-units), so
#                    hazard_ratio_per_unit = exp(beta * 0.01) = HR ** 0.01
#                    -- the classic "0.01 vs 1pp" misread the spec calls
#                    out, computed exactly, not eyeballed.
#   "categorical" -- a 0/1 dummy; HR reads "vs the stated reference".
#   "interaction" -- a product term; a single worked example would mislead
#                    (see fit_stats.double_trigger_note instead).
#   "spline"      -- one basis weight of a natural-cubic-spline age curve;
#                    not individually interpretable (source text is explicit
#                    about this for both DCR and SFLLD).
#   "baseline"    -- the model intercept.
# ---------------------------------------------------------------------------

_CONCEPTS: dict[str, dict] = {
    "fico": {
        "unit_meaning": "1 unit = 100 points of FICO score at origination "
            "(fico_s = FICO_orig_time / 100).",
        "transformation": "level, static at origination, scaled /100",
        "lag": "static (origination) -- no lag, not time-varying",
        "fred_series": None,
        "economic_channel": "Ability/willingness-to-pay channel: cleaner "
            "credit history at origination signals lower baseline default "
            "propensity, independent of the macro cycle.",
        "unit_kind": "direct", "unit_label": "100 FICO points",
    },
    "ltv": {
        "unit_meaning": "1 unit = 10 percentage points of updated LTV "
            "(ltv10 = updated_ltv / 10; updated_ltv winsorised at 300%).",
        "transformation": "updated_ltv = LTV_orig x (balance_t/balance_orig) "
            "x (hpi_orig/hpi_t) -- a documented CURRENT-period exception to "
            "the lag convention, because collateral value is a real-time "
            "state, not a forecast.",
        "lag": "current period (documented exception, flagged with a lightning-bolt in the variable dictionary)",
        "fred_series": None,
        "economic_channel": "Collateral / negative-equity channel: as "
            "updated LTV rises the borrower's equity cushion shrinks, "
            "removing both the option to sell out of trouble and (past "
            "100% LTV) adding a strategic-default incentive.",
        "unit_kind": "direct", "unit_label": "10pp of updated LTV",
    },
    "rate_incentive": {
        "unit_meaning": "1 unit = 1 percentage point of rate incentive "
            "(note rate minus the current market rate).",
        "transformation": "current-period state variable (option value is "
            "real-time)",
        "lag": "current period (documented exception, same as LTV)",
        "fred_series": None,
        "economic_channel": "Refinancing-incentive channel: a note rate "
            "above the market rate makes refinancing pay -- the star "
            "prepayment driver; for default it doubles as a proxy for "
            "contractual debt-service burden.",
        "unit_kind": "direct", "unit_label": "1pp of rate incentive",
    },
    "investor": {
        "unit_meaning": "binary flag: 1 if the loan is investor-owned at "
            "origination, 0 (owner-occupied) otherwise.",
        "transformation": "static origination flag", "lag": "static (origination)",
        "fred_series": None,
        "economic_channel": "Strategic-default propensity channel: an "
            "investor has no home to lose, so the same negative-equity "
            "trigger converts to default faster than for an owner-occupant.",
        "unit_kind": "categorical", "unit_label": "an investor-owned loan",
        "reference_label": "an owner-occupied loan",
    },
    "condo": {
        "unit_meaning": "binary flag: 1 if the property is a condominium.",
        "transformation": "static origination flag", "lag": "static (origination)",
        "fred_series": None,
        "economic_channel": "Property-type risk: condos carry HOA/liquidity "
            "characteristics distinct from single-family detached homes "
            "(effect not significant at 5% in the default hazard, p=0.141).",
        "unit_kind": "categorical", "unit_label": "a condominium",
        "reference_label": "the non-condo reference property type",
    },
    "pud": {
        "unit_meaning": "binary flag: 1 if the property is a planned unit "
            "development.",
        "transformation": "static origination flag", "lag": "static (origination)",
        "fred_series": None,
        "economic_channel": "Property-type risk, same family as condo.",
        "unit_kind": "categorical", "unit_label": "a planned-unit-development property",
        "reference_label": "the reference property type",
    },
    "single_family": {
        "unit_meaning": "binary flag: 1 if the property is single-family "
            "detached.",
        "transformation": "static origination flag", "lag": "static (origination)",
        "fred_series": None,
        "economic_channel": "Property-type risk, same family as condo "
            "(effect not significant at 5% in the default hazard, p=0.715).",
        "unit_kind": "categorical", "unit_label": "a single-family detached property",
        "reference_label": "the reference property type",
    },
    "uer_level_dcr": {
        "unit_meaning": "1 unit = 1 percentage point of the national "
            "unemployment rate LEVEL, lagged 1 quarter.",
        "transformation": "level (pp), within-loan 1-quarter lag -- a "
            "vendor-premerged national series on the DCR panel's own "
            "ANONYMIZED quarterly clock (data/panel/build_panel.py: "
            "\"macros pre-merged\"), not a live FRED pull. Only the "
            "clock's CALENDAR alignment to real quarters was verified, "
            "via correlation against FRED UNRATE (corr 0.996, per "
            "outputs/variable_dictionary.md's preamble) -- an anchoring "
            "check, not a sourcing claim, so no FRED series id is given.",
        "lag": "1 quarter",
        "fred_series": None,
        "economic_channel": "Cash-flow / labour-income channel: a job loss "
            "removes the income that services the mortgage, raising "
            "arrears and default risk.",
        "unit_kind": "direct", "unit_label": "1pp of national UER level",
        "net_effect_note": "Read TOGETHER with the 4-quarter change term "
            "below -- a 1pp labour-market SHOCK moves both one-for-one; "
            "see fit_stats.net_uer_effect_note for the combined hazard "
            "ratio (~1.28 per pp).",
    },
    "uer_momentum_dcr": {
        "unit_meaning": "1 unit = 1 percentage point of the 4-quarter "
            "CHANGE in the national unemployment rate, lagged 1 quarter.",
        "transformation": "4-quarter first difference of the same "
            "vendor-premerged, anonymized-clock national UER series as "
            "the level term above -- not a live FRED pull.",
        "lag": "1 quarter (over a 4-quarter window)",
        "fred_series": None,
        "economic_channel": "Labour-market momentum: a fast-deteriorating "
            "job market front-loads distress even before the level itself "
            "is high -- the level and momentum coefficients correlate at "
            "0.94 in-sample and are read TOGETHER as the net unemployment-"
            "shock effect (fit_stats.net_uer_effect_note).",
        "unit_kind": "direct", "unit_label": "1pp of the 4-quarter UER change",
    },
    "hpi_growth_dcr": {
        "unit_meaning": "dlog(HPI) -- one-quarter log-difference of the "
            "national house-price index, lagged 1 quarter. The table's HR "
            "is scaled to a FULL 1.0 log-unit (~100% quarterly growth, "
            "never observed) -- the economically legible worked example "
            "below is per 1% quarterly growth (0.01 log-units); this is "
            "the classic 0.01-vs-1pp misread.",
        "transformation": "log-growth (dlog) of the national FHFA HPI, "
            "lagged 1 quarter -- a vendor-premerged series on the DCR "
            "panel's anonymized clock, not a live FRED pull (unlike the "
            "SFLLD rung's state-level {POSTAL}STHPI, which IS a genuine "
            "live FRED pull via freddie/macro.py).",
        "lag": "1 quarter",
        "fred_series": None,
        "economic_channel": "Collateral / equity-building channel: rising "
            "house prices rebuild borrower equity and improve the odds of "
            "a profitable sale instead of default; falling prices do the "
            "reverse.",
        "unit_kind": "log1pct", "unit_label": "1% quarterly HPI growth",
    },
    "gdp_growth_dcr": {
        "unit_meaning": "1 unit = 1 percentage point of quarterly "
            "(non-annualised) real GDP growth, lagged 1 quarter.",
        "transformation": "quarterly growth rate, lagged 1 quarter -- a "
            "vendor-premerged national series on the DCR panel's "
            "anonymized clock, not a live FRED pull.",
        "lag": "1 quarter",
        "fred_series": None,
        "economic_channel": "General activity channel: a stronger economy "
            "supports employment and incomes broadly -- a second-order "
            "effect alongside the direct labour-market (UER) channel.",
        "unit_kind": "direct", "unit_label": "1pp of quarterly GDP growth",
    },
    "double_trigger": {
        "unit_meaning": "product of CENTERED updated-LTV(10pp) and "
            "CENTERED national-UER(pp) -- not a simple per-unit shift in "
            "either variable alone.",
        "transformation": "mean-centered interaction term (its UER leg is "
            "the same vendor-premerged, anonymized-clock national series "
            "as uer_level_dcr above -- not a live FRED pull).",
        "lag": "mixed (current-period LTV x lag-1 UER)",
        "fred_series": None,
        "economic_channel": "Double-trigger hypothesis: default is most "
            "likely when a borrower BOTH cannot pay (unemployment) AND "
            "cannot sell out of trouble (negative equity) at once. The "
            "fitted sign here is a documented in-sample substitution (the "
            "main effects and momentum term already carry most of the "
            "joint stress) -- see fit_stats.double_trigger_note, not "
            "evidence against the hypothesis.",
        "unit_kind": "interaction", "unit_label": None,
    },
    "intercept": {
        "unit_meaning": "reference-row hazard multiplier: every "
            "categorical at its reference level, every continuous "
            "covariate at its training mean / spline reference.",
        "transformation": "model constant", "lag": "n/a", "fred_series": None,
        "economic_channel": "Not an economic channel -- the baseline "
            "hazard level the other coefficients multiply.",
        "unit_kind": "baseline", "unit_label": None,
    },
    # -- SFLLD (Freddie rung-3, state-level, monthly panel) --------------
    "uer_level_sflld": {
        "unit_meaning": "1 unit = 1 percentage point of the property "
            "state's own unemployment rate LEVEL, lagged 1 month.",
        "transformation": "level (pp), state-level, monthly, SA, lagged 1 "
            "month; falls back to national UNRATE for GU/VI, which carry "
            "no state series",
        "lag": "1 month",
        "fred_series": "{POSTAL}UR",
        "economic_channel": "Cash-flow / labour-income channel, same "
            "mechanism as the DCR national UER level -- state resolution "
            "replaces the national anchor with the borrower's own local "
            "labour market.",
        "unit_kind": "direct", "unit_label": "1pp of state UER level",
    },
    "uer_momentum_sflld": {
        "unit_meaning": "1 unit = 1 percentage point of the state UER's "
            "1-MONTH change, lagged 1 month (the monthly-panel analogue "
            "of DCR's 4-quarter change).",
        "transformation": "1-month first difference of state UER, lagged 1 month",
        "lag": "1 month",
        "fred_series": "{POSTAL}UR",
        "economic_channel": "Labour-market momentum at monthly frequency: "
            "a fast month-on-month deterioration in the local job market "
            "front-loads distress.",
        "unit_kind": "direct", "unit_label": "1pp of the 1-month state UER change",
    },
    "hpi_growth_sflld": {
        "unit_meaning": "dlog(state HPI) -- one-month log-difference of "
            "the state house-price index (forward-filled from FRED's "
            "quarterly print), lagged 1 month. Same full-log-unit table "
            "scaling as the DCR HPI term -- read the 1%-growth worked "
            "example, not the raw table HR.",
        "transformation": "log-growth (dlog) of the FHFA all-transactions "
            "state HPI (quarterly, NSA), forward-filled to monthly, lagged "
            "1 month; falls back to national USSTHPI for GU/PR/VI",
        "lag": "1 month",
        "fred_series": "{POSTAL}STHPI",
        "economic_channel": "Collateral / equity-building channel, same "
            "as DCR's national HPI term, at state resolution.",
        "unit_kind": "log1pct",
        "unit_label": "1% monthly HPI growth (the forward-filled series "
            "concentrates each quarter's growth into its first month, so "
            "read alongside a trailing-12m view, not a single month)",
    },
    "dti": {
        "unit_meaning": "1 unit = 10 points of origination DTI "
            "(dti_s = dti / 10).",
        "transformation": "level, static at origination, scaled /10",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Debt-service cash-flow strain channel: a "
            "higher debt-to-income ratio leaves less income buffer to "
            "absorb a shock -- no DCR counterpart at this rung (the DCR "
            "panel carries no DTI field).",
        "unit_kind": "direct", "unit_label": "10 points of origination DTI",
    },
    "loan_age_spline": {
        "unit_meaning": "one basis coefficient of a 5-knot natural cubic "
            "spline in loan age -- not individually interpretable as a "
            "per-unit shift.",
        "transformation": "natural cubic spline, cr(loan_age, df=5)",
        "lag": "n/a (contemporaneous loan age)", "fred_series": None,
        "economic_channel": "Seasoning channel: underwriting-quality "
            "burn-in, then a mid-life peak in default risk, then "
            "survivor-selection decay -- the fitted CURVE, not any one "
            "basis weight, carries the story (see the seasoning exhibit).",
        "unit_kind": "spline", "unit_label": None,
    },
    "occupancy_investor": {
        "unit_meaning": "binary flag: 1 if occupancy_status = 'I' (investor).",
        "transformation": "static origination categorical, "
            "Treatment(reference='P' owner-occupied)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Strategic-default propensity -- matches the "
            "DCR investor-flag prior (HR 1.099, both fitted +).",
        "unit_kind": "categorical", "unit_label": "an investor-occupied property",
        "reference_label": "an owner-occupied (primary residence) property",
    },
    "occupancy_second_home": {
        "unit_meaning": "binary flag: 1 if occupancy_status = 'S' (second home).",
        "transformation": "static origination categorical, "
            "Treatment(reference='P' owner-occupied)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Strategic-default propensity predicted second "
            "homes to default MORE than owner-occupied (less skin in the "
            "game); this fit shows the OPPOSITE (HR 0.825) -- a "
            "documented, stated MISS (hazard_report.md Sec 2): conditional "
            "on the same FICO/DTI/LTV/macro, second-home borrowers in "
            "this sample default less -- sample composition, not a "
            "causal claim.",
        "unit_kind": "categorical", "unit_label": "a second-home property",
        "reference_label": "an owner-occupied (primary residence) property",
    },
    "purpose_cashout": {
        "unit_meaning": "binary flag: 1 if loan_purpose = 'C' (cash-out refinance).",
        "transformation": "static origination categorical, "
            "Treatment(reference='P' purchase-money)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Cash-out refinancing extracts equity, "
            "raising leverage and default risk -- matches the prior (HR "
            "1.550, the largest categorical effect in the table).",
        "unit_kind": "categorical", "unit_label": "a cash-out refinance",
        "reference_label": "a purchase-money loan",
    },
    "purpose_norefi": {
        "unit_meaning": "binary flag: 1 if loan_purpose = 'N' (no-cash-out refinance).",
        "transformation": "static origination categorical, "
            "Treatment(reference='P' purchase-money)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "No-cash-out refinancing was expected to "
            "select seasoned, improved-credit borrowers (lower risk); "
            "this fit shows the OPPOSITE (HR 1.310) -- a documented, "
            "stated MISS (hazard_report.md Sec 2).",
        "unit_kind": "categorical", "unit_label": "a no-cash-out refinance",
        "reference_label": "a purchase-money loan",
    },
    "channel_broker": {
        "unit_meaning": "binary flag: 1 if channel = 'B' (broker).",
        "transformation": "static origination categorical, "
            "Treatment(reference='R' retail)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Origination-control agency problem: "
            "broker-originated loans historically carry weaker "
            "underwriting discipline than retail -- matches the prior "
            "(HR 1.220).",
        "unit_kind": "categorical", "unit_label": "a broker-channel loan",
        "reference_label": "a retail-channel loan",
    },
    "channel_correspondent": {
        "unit_meaning": "binary flag: 1 if channel = 'C' (correspondent).",
        "transformation": "static origination categorical, "
            "Treatment(reference='R' retail)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Origination-control agency problem predicted "
            "correspondent to be riskier than retail; this fit shows the "
            "OPPOSITE (HR 0.791) -- a documented, stated MISS "
            "(hazard_report.md Sec 2): correspondent loans in this "
            "Freddie sample are not the pre-crisis wholesale book the "
            "prior describes.",
        "unit_kind": "categorical", "unit_label": "a correspondent-channel loan",
        "reference_label": "a retail-channel loan",
    },
    "channel_tpo": {
        "unit_meaning": "binary flag: 1 if channel = 'T' (third-party originator).",
        "transformation": "static origination categorical, "
            "Treatment(reference='R' retail)",
        "lag": "static (origination)", "fred_series": None,
        "economic_channel": "Origination-control agency problem, same "
            "direction as broker -- matches the prior (HR 1.360, the "
            "largest channel effect).",
        "unit_kind": "categorical", "unit_label": "a third-party-originator loan",
        "reference_label": "a retail-channel loan",
    },
    "intercept_sflld": {
        "unit_meaning": "reference-row hazard multiplier: owner-occupied "
            "/ purchase-money / retail-channel / loan-age-spline "
            "reference, all continuous covariates at 0 on their raw "
            "scale (fico_s/dti_s/ltv10/uer_lag1/... are NOT centered in "
            "this fit) -- an out-of-sample combination, so read as a pure "
            "model constant, not an achievable loan profile.",
        "transformation": "model constant", "lag": "n/a", "fred_series": None,
        "economic_channel": "Not an economic channel -- the baseline "
            "hazard level the other coefficients multiply.",
        "unit_kind": "baseline", "unit_label": None,
    },
    # -- variable-dictionary-only concepts (no single coefficient) -------
    "lgd_target": {
        "unit_meaning": "N/A -- this is the LGD target variable, not a "
            "hazard regressor.",
        "transformation": "vendor-realised workout LGD, resolved workouts only",
        "lag": "resolution window", "fred_series": None,
        "economic_channel": "Loss-given-default outcome, modelled "
            "separately by the two-stage cure/severity LGD model, not the "
            "hazard.",
        "unit_kind": "none", "unit_label": None,
    },
    "z_factor": {
        "unit_meaning": "N/A -- the recovered systematic credit-cycle "
            "factor (Vasicek/Belkin inversion), not a macro regressor "
            "itself.",
        "transformation": "Belkin inversion of observed vs "
            "composition-adjusted expected default rates", "lag": "n/a",
        "fred_series": None,
        "economic_channel": "Systematic (undiversifiable) credit-cycle "
            "risk -- the satellite model below regresses THIS on lagged "
            "macro; the PIT/TTC conditioning consumes it directly.",
        "unit_kind": "none", "unit_label": None,
    },
    "scenario_paths": {
        "unit_meaning": "N/A -- a set of forward macro PATHS, not a "
            "single regressor.",
        "transformation": "DFAST 2026 supervisory scenario CSVs (not a raw "
            "FRED pull -- see data/ingest/dfast.py): UER (pp level), HPI "
            "level -> dlog, GDP SAAR -> quarterly, mortgage rate",
        "lag": "2026Q1-2029Q1 (13q), rebased as deltas onto the 2015Q1 "
            "jump-off, reversion to panel long-run means by q21",
        "fred_series": None,
        "economic_channel": "Coherent supervisory multivariate shapes feed "
            "the scenario ECL directly; see the satellite/coherent-shock "
            "note for how a univariate agent shock is projected onto this "
            "coherent direction.",
        "unit_kind": "none", "unit_label": None,
    },
    "gdp_combined": {
        "unit_meaning": "GDP growth enters TWICE, at two different lags, "
            "for two different consumers: gdp_lag1 (1-quarter lag) drives "
            "the DCR default hazard; gdp_growth_lag2 (2-quarter lag) "
            "drives the satellite Z regression (the deeper lag won the "
            "satellite's AIC-minimising specification search).",
        "transformation": "quarterly growth rate, national -- a "
            "vendor-premerged series on the DCR panel's anonymized "
            "clock, not a live FRED pull.",
        "lag": "1 quarter (hazard) / 2 quarters (satellite)",
        "fred_series": None,
        "economic_channel": "General activity channel: a stronger economy "
            "supports employment and incomes broadly, and (with a longer "
            "transmission lag) the systematic credit cycle itself.",
        "unit_kind": "none", "unit_label": None,
    },
}


def _hazard_ratio_per_unit(concept: dict, hr: float | None,
                           coef: float | None = None) -> float | None:
    """exp(beta * unit_delta) for the concept's OWN economically-legible
    unit -- mechanical, never hand-typed (GOVERNING RULE, extended to this
    exhibit's arithmetic)."""
    if hr is None:
        return None
    kind = concept["unit_kind"]
    if kind == "log1pct":
        beta = coef if coef is not None else math.log(hr)
        return round(math.exp(beta * 0.01), 6)
    if kind in ("none", "interaction"):
        # An interaction term has no single legible "1 unit" (unit_label
        # is None for these concepts) -- reporting the raw table HR under
        # this field would silently pass off a product-term coefficient as
        # a marginal per-unit reading, exactly the misread this exhibit
        # exists to prevent. See _worked_example's "interaction" branch /
        # fit_stats.double_trigger_note for the honest marginal-effect
        # decomposition instead (docs/api_contract.md's documented null).
        return None
    return round(hr, 6)


def _worked_example(concept: dict, hr: float | None,
                    coef: float | None = None) -> str | None:
    """The numeric worked example, computed from the SAME hr/coef passed to
    _hazard_ratio_per_unit (never re-typed by hand)."""
    if hr is None:
        return None
    kind = concept["unit_kind"]
    label = concept.get("unit_label")
    if kind == "direct":
        pct = (hr - 1.0) * 100.0
        direction = "increase" if pct >= 0 else "decrease"
        return (f"+{label} => hazard x {hr:.4f} "
               f"({pct:+.1f}%, a {abs(pct):.1f}% {direction} in the "
               f"monthly/quarterly default hazard).")
    if kind == "log1pct":
        beta = coef if coef is not None else math.log(hr)
        hr1 = math.exp(beta * 0.01)
        pct = (hr1 - 1.0) * 100.0
        direction = "increase" if pct >= 0 else "decrease"
        return (f"+{label} => hazard x {hr1:.4f} "
               f"({pct:+.1f}%, a {abs(pct):.1f}% {direction}) -- NOT the "
               f"raw table HR of {hr:.4f}, which is scaled to a full "
               f"100%-log-unit move (the 0.01-vs-1pp misread this exhibit "
               f"exists to prevent).")
    if kind == "categorical":
        pct = (hr - 1.0) * 100.0
        direction = "higher" if pct >= 0 else "lower"
        ref = concept.get("reference_label", "the reference category")
        return (f"A loan that is {label} => hazard x {hr:.4f} "
               f"({abs(pct):.1f}% {direction} than {ref}).")
    if kind == "interaction":
        return ("Not a simple per-unit read (interaction term) -- see "
               "fit_stats.double_trigger_note for the marginal-effect "
               "decomposition at mean vs high UER.")
    if kind == "spline":
        return ("One of five spline basis weights -- not individually "
               "interpretable; see the seasoning-curve exhibit for the "
               "fitted age profile this basis reconstructs.")
    if kind == "baseline":
        return (f"Reference/mean-covariate baseline hazard multiplier: "
               f"x{hr:.4f} -- not a marginal per-unit effect.")
    return None


def _variable_interpretation(concept_key: str | None, hr: float | None = None,
                            coef: float | None = None) -> dict:
    """{unit_meaning, transformation, lag, fred_series, economic_channel,
    hazard_ratio_per_unit, worked_example} for one coefficient/variable row.
    `concept_key=None` (no curated match) degrades to all-null fields rather
    than raising -- additive contract, never a 500 on an unmapped row."""
    if concept_key is None or concept_key not in _CONCEPTS:
        return {"unit_meaning": None, "transformation": None, "lag": None,
                "fred_series": None, "economic_channel": None,
                "hazard_ratio_per_unit": None, "worked_example": None}
    c = _CONCEPTS[concept_key]
    return {
        "unit_meaning": c["unit_meaning"],
        "transformation": c["transformation"],
        "lag": c["lag"],
        "fred_series": c["fred_series"],
        "economic_channel": c["economic_channel"],
        "hazard_ratio_per_unit": _hazard_ratio_per_unit(c, hr, coef),
        "worked_example": _worked_example(c, hr, coef),
    }


#: DCR hazard_ratios.md "Covariate" label -> concept key (identical labels
#: in both the default and prepayment tables).
_DCR_LABEL_TO_CONCEPT = {
    "Intercept": "intercept",
    "FICO at orig. (per 100 pts)": "fico",
    "Updated LTV (per 10pp, at mean UER)": "ltv",
    "Rate incentive (pp)": "rate_incentive",
    "Investor loan": "investor",
    "Condo": "condo",
    "Planned urban dev.": "pud",
    "Single family": "single_family",
    "Unemployment level (lag 1)": "uer_level_dcr",
    "Unemployment 4q change (lag 1)": "uer_momentum_dcr",
    "HPI growth (lag 1)": "hpi_growth_dcr",
    "GDP growth (lag 1)": "gdp_growth_dcr",
    "DOUBLE TRIGGER: LTV(10pp) x UER (centered)": "double_trigger",
}

#: outputs/freddie/hazard/coefficients.csv "term" -> concept key.
_FREDDIE_TERM_TO_CONCEPT = {
    "Intercept": "intercept_sflld",
    "C(occupancy_status, Treatment(reference='P'))[T.I]": "occupancy_investor",
    "C(occupancy_status, Treatment(reference='P'))[T.S]": "occupancy_second_home",
    "C(loan_purpose, Treatment(reference='P'))[T.C]": "purpose_cashout",
    "C(loan_purpose, Treatment(reference='P'))[T.N]": "purpose_norefi",
    "C(channel, Treatment(reference='R'))[T.B]": "channel_broker",
    "C(channel, Treatment(reference='R'))[T.C]": "channel_correspondent",
    "C(channel, Treatment(reference='R'))[T.T]": "channel_tpo",
    "fico_s": "fico", "dti_s": "dti", "ltv10": "ltv",
    "uer_lag1": "uer_level_sflld", "delta_uer_lag1": "uer_momentum_sflld",
    "hpi_growth_lag1": "hpi_growth_sflld",
}


def _freddie_term_concept(term: str) -> str | None:
    if term in _FREDDIE_TERM_TO_CONCEPT:
        return _FREDDIE_TERM_TO_CONCEPT[term]
    if term.startswith("cr(loan_age"):
        return "loan_age_spline"
    return None


#: variable_dictionary.md "variable" cell (raw, backtick-quoted) -> concept
#: key. `gdp_lag1` / `gdp_growth_lag2` is a combined row (two consumers, two
#: lags) so it gets its own concept rather than reusing gdp_growth_dcr.
_VARDICT_LABEL_TO_CONCEPT = {
    "`fico_s`": "fico",
    "`ltv10` ⚡": "ltv",
    "`loan_age`": "loan_age_spline",
    "`prepay_incentive` ⚡": "rate_incentive",
    "`investor_orig_time`, RE-type flags": "investor",
    "`uer_lag1`": "uer_level_dcr",
    "`uer_chg4_lag1`": "uer_momentum_dcr",
    "`hpi_growth_lag1`": "hpi_growth_dcr",
    "`gdp_lag1` / `gdp_growth_lag2`": "gdp_combined",
    "`dt_ltv_uer`": "double_trigger",
    "`lgd_time` (target)": "lgd_target",
    "`Z_t` (recovered)": "z_factor",
    "Scenario paths": "scenario_paths",
}


#: /api/model/macro_glossary -- every macro series across DCR + SFLLD +
#: satellite, one row per (series, model) pairing where the transformation
#: or lag genuinely differs; `which_models` lists every consumer.
_MACRO_GLOSSARY = [
    {"id": "dcr_uer_level", "label": "National UER -- level",
     "fred_series": None, "geography": "US national",
     "frequency": "monthly (matched to the panel's quarterly clock)",
     "transformation": "level (pp)", "lag": "1 quarter",
     "lag_rationale": "Publication-lag realism + the model's own timing "
         "convention: only past values (t-k, k>=1) are ever referenced, "
         "so scoring never looks ahead. NOT a live FRED pull -- a "
         "vendor-premerged national series on the DCR panel's own "
         "ANONYMIZED quarterly clock (t=1..60); only the clock's "
         "CALENDAR alignment to real quarters was verified, via "
         "correlation against FRED UNRATE (corr 0.996, per "
         "outputs/variable_dictionary.md's preamble) -- an anchoring "
         "check, not a sourcing claim, so no FRED series id is given.",
     "which_models": ["DCR default hazard"]},
    {"id": "dcr_uer_momentum", "label": "National UER -- 4-quarter change",
     "fred_series": None, "geography": "US national",
     "frequency": "monthly (matched to the panel's quarterly clock)",
     "transformation": "4-quarter first difference", "lag": "1 quarter",
     "lag_rationale": "Same 1-quarter lag as the level term; the 4q window "
         "captures momentum a single lag would miss. Level and momentum "
         "correlate at 0.94 in-sample -- read their SUM as the net "
         "unemployment-shock effect, not the level term alone. Same "
         "vendor-premerged, anonymized-clock series as the level row "
         "above -- not a live FRED pull (see that row's note).",
     "which_models": ["DCR default hazard"]},
    {"id": "dcr_hpi_growth", "label": "National HPI -- log-growth",
     "fred_series": None, "geography": "US national",
     "frequency": "quarterly",
     "transformation": "dlog(HPI), one-quarter log-difference",
     "lag": "1 quarter",
     "lag_rationale": "Same publication-lag/no-lookahead convention as "
         "UER. NOT a live FRED pull -- vendor-premerged on the DCR "
         "panel's anonymized clock, same as the UER rows above (unlike "
         "the SFLLD rows below, which ARE genuine live FRED pulls).",
     "which_models": ["DCR default hazard", "DCR prepayment hazard"]},
    {"id": "dcr_gdp_growth", "label": "National real GDP -- quarterly growth",
     "fred_series": None, "geography": "US national",
     "frequency": "quarterly", "transformation": "quarterly growth rate",
     "lag": "1 quarter (hazard) / 2 quarters (satellite -- see below)",
     "lag_rationale": "Hazard: same 1-quarter convention as UER/HPI. "
         "Satellite: the 2-quarter lag won the AIC-minimising, "
         "sign-admissible specification search over the full driver grid. "
         "NOT a live FRED pull -- vendor-premerged on the DCR panel's "
         "anonymized clock, same as the UER/HPI rows above.",
     "which_models": ["DCR default hazard", "satellite (Z regression)"]},
    {"id": "sflld_uer_level", "label": "State UER -- level",
     "fred_series": "{POSTAL}UR", "geography": "US state (property state)",
     "frequency": "monthly",
     "transformation": "level (pp)", "lag": "1 month",
     "lag_rationale": "Panel-native frequency is monthly (vs DCR's "
         "quarterly), so the lag is 1 calendar month, not 1 quarter -- "
         "same no-lookahead convention, finer clock. Falls back to "
         "national UNRATE for GU/VI (no state series at FRED).",
     "which_models": ["SFLLD champion hazard"]},
    {"id": "sflld_uer_momentum", "label": "State UER -- 1-month change",
     "fred_series": "{POSTAL}UR", "geography": "US state (property state)",
     "frequency": "monthly",
     "transformation": "1-month first difference", "lag": "1 month",
     "lag_rationale": "Monthly-panel analogue of the DCR 4-quarter change "
         "-- the shortest momentum window the native frequency supports.",
     "which_models": ["SFLLD champion hazard"]},
    {"id": "sflld_hpi_growth", "label": "State HPI -- log-growth",
     "fred_series": "{POSTAL}STHPI", "geography": "US state (property state)",
     "frequency": "quarterly, forward-filled to monthly",
     "transformation": "dlog(HPI) of the forward-filled monthly series",
     "lag": "1 month",
     "lag_rationale": "FRED publishes STHPI at quarter-start dates; "
         "forward-fill (not interpolation) avoids letting month 2 of a "
         "quarter see month 3's not-yet-published print -- the 1-month "
         "lag then applies on top, same no-lookahead convention. Falls "
         "back to national USSTHPI for GU/PR/VI.",
     "which_models": ["SFLLD champion hazard"]},
    {"id": "satellite_hpi_growth", "label": "National HPI -- log-growth (satellite)",
     "fred_series": None, "geography": "US national",
     "frequency": "quarterly",
     "transformation": "dlog(HPI), one-quarter log-difference (identical "
         "series/transform to the DCR hazard's HPI term -- same "
         "vendor-premerged, anonymized-clock series, not a live FRED "
         "pull; see dcr_hpi_growth above)",
     "lag": "1 quarter",
     "lag_rationale": "Same national series as the DCR hazard term; the "
         "satellite regresses the recovered credit-cycle factor Z on it "
         "directly (OLS coefficient +13.642, not a hazard ratio).",
     "which_models": ["satellite (Z regression)"]},
    {"id": "scenario_paths", "label": "DFAST scenario paths (UER/HPI/GDP/mortgage rate)",
     "fred_series": None, "geography": "US national",
     "frequency": "quarterly, 2026Q1-2029Q1 (13 quarters)",
     "transformation": "UER: pp level. HPI: level -> dlog. GDP: SAAR -> "
         "quarterly (geometric fourth root). Mortgage rate: level. All "
         "rebased as DELTAS onto the 2015Q1 panel jump-off.",
     "lag": "n/a (a forward path, not a lagged regressor)",
     "lag_rationale": "Not a FRED pull -- DFAST 2026 supervisory scenario "
         "CSVs, chosen for coherent (jointly-plausible) multivariate "
         "shapes; reverts to panel long-run macro means by q21, held to 40q.",
     "which_models": ["scenario ECL (up/base/down)"]},
    {"id": "coherent_shock_convention",
     "label": "Coherent-shock convention (satellite has NO unemployment term)",
     "fred_series": None, "geography": "n/a", "frequency": "n/a",
     "transformation": "n/a -- a modelling-convention note, not a series",
     "lag": "n/a",
     "lag_rationale": "The sign-governed satellite is "
         "Z = f(hpi_growth_lag1, gdp_growth_lag2) -- unemployment was "
         "excluded by the AIC/sign-governance search (every spec pairing "
         "duer with gdp_growth fit a wrong-signed, collinearity-driven "
         "duer coefficient). A UNIVARIATE UER-only shock therefore cannot "
         "reach Z at all: shock_macro applies every agent shock as a "
         "co-moving move along the DFAST severe-minus-base direction "
         "(loadings normalised to the named variable) so a UER shock "
         "still moves HPI/GDP coherently and reaches Z -- without this, "
         "a UER-only shock question would return delta = 0.",
     "which_models": ["satellite (Z regression)", "shock_macro tool"]},
]


def _parse_hazard_ratios() -> dict:
    """outputs/hazard/hazard_ratios.md -> {'default': {...}, 'prepay': {...}}."""
    text = (OUTPUTS_DIR / "hazard" / "hazard_ratios.md").read_text(
        encoding="utf-8")
    out: dict = {}
    for title, body in _md_sections(text):
        m = re.match(r"(Default|Prepayment) hazard", title)
        if not m:
            continue
        key = "default" if m.group(1) == "Default" else "prepay"
        stats = re.search(
            r"n = ([\d,]+) loan-quarters, events = ([\d,]+), "
            r"McFadden pseudo-R2 = ([\d.]+)", body)
        lines = body.splitlines()
        span = _md_table_span(lines)
        table_rows = _md_table_rows(lines[span[0]:span[1]]) if span else []
        fs = re.search(r"\*\*Family stories\*\*\n\n(.*)", body, flags=re.S)
        stories = dict(re.findall(
            r"-\s*\*\*(\w+)\*\*\s*--\s*(.*?)(?=\n-\s*\*\*|\Z)",
            fs.group(1), flags=re.S)) if fs else {}
        coefficients = []
        for r in table_rows:
            hr = float(r["HR = exp(coef)"])
            row = {
                "variable": r["Covariate"],
                "family": r["family"],
                "hazard_ratio": hr,
                "ci": _parse_ci(r["95% CI"]),
                "p": _parse_p(r["p"])[0],
                "p_display": _parse_p(r["p"])[1],
                "story": stories.get(r["family"], "").strip(),
            }
            row.update(_variable_interpretation(
                _DCR_LABEL_TO_CONCEPT.get(r["Covariate"]), hr))
            coefficients.append(row)
        out[key] = {
            "n_fit": int(_num(stats.group(1))) if stats else None,
            "events": int(_num(stats.group(2))) if stats else None,
            "mcfadden_r2": float(stats.group(3)) if stats else None,
            "coefficients": coefficients,
        }
    return out


def _parse_fit_stats() -> dict:
    """outputs/hazard/fit_stats.md -> AUCs, seasoning peak, net-UER note."""
    text = (OUTPUTS_DIR / "hazard" / "fit_stats.md").read_text(
        encoding="utf-8")
    lines = text.splitlines()
    span = _md_table_span(lines)
    rows = _md_table_rows(lines[span[0]:span[1]])
    models = {
        ("default" if r["Model"] == "default" else "prepay"): {
            "n_fit": int(_num(r["n (fit)"])),
            "events": int(_num(r["events"])),
            "train_auc": float(r["train AUC"]),
            "oot_auc": float(r["OOT AUC"]),
            "mcfadden_r2": float(r["McFadden R2"]),
        } for r in rows
    }
    seasoning_m = re.search(
        r"Seasoning peak: fitted (\d+)q vs empirical (\d+)q "
        r"\(tolerance (\d+)q; plausible window \((\d+), (\d+)\)\)", text)
    seasoning = {
        "fitted_q": int(seasoning_m.group(1)),
        "empirical_q": int(seasoning_m.group(2)),
        "tolerance_q": int(seasoning_m.group(3)),
        "plausible_window_q": [int(seasoning_m.group(4)),
                               int(seasoning_m.group(5))],
    } if seasoning_m else None
    uer_m = re.search(r"Unemployment shock: (.+?)\n\n", text, flags=re.S)
    dt_m = re.search(r"Double trigger: (.+?)\n\n", text, flags=re.S)
    return {
        **models,
        "seasoning_peak": seasoning,
        "net_uer_effect_note": uer_m.group(1).strip() if uer_m else None,
        "double_trigger_note": dt_m.group(1).strip() if dt_m else None,
    }


_VARDICT_COLUMNS = {
    "Variable (model name)": "variable",
    "Source → transformation": "source_transformation",
    "Lag / window": "lag_window",
    "Economic rationale": "economic_rationale",
    "Expected sign": "expected_sign",
    "Fitted (verified)": "fitted_verified",
    "Consumed by": "consumed_by",
}


def _parse_variable_dictionary() -> dict:
    """outputs/variable_dictionary.md -> {preamble, rows, notes}."""
    lines = (OUTPUTS_DIR / "variable_dictionary.md").read_text(
        encoding="utf-8").splitlines()
    span = _md_table_span(lines)
    preamble = "\n".join(lines[1:span[0]]).strip()
    notes = "\n".join(lines[span[1]:]).strip()
    raw_rows = _md_table_rows(lines[span[0]:span[1]])
    rows = [{_VARDICT_COLUMNS.get(k, k): v for k, v in r.items()}
            for r in raw_rows]

    # Requirement 12: join the curated interpretation onto every row. The
    # hazard ratio (where one exists for this concept) is REUSED from the
    # already-parsed DCR default-hazard table -- reported here, never
    # re-derived -- via the same label->concept map the coefficients
    # endpoint uses, so the two exhibits can never silently disagree.
    default_hr_by_label = {
        c["variable"]: c["hazard_ratio"]
        for c in _parse_hazard_ratios().get("default", {}).get("coefficients", [])
    }
    concept_hr = {
        concept: default_hr_by_label[label]
        for label, concept in _DCR_LABEL_TO_CONCEPT.items()
        if label in default_hr_by_label
    }
    for row in rows:
        concept_key = _VARDICT_LABEL_TO_CONCEPT.get(row["variable"])
        row.update(_variable_interpretation(concept_key, concept_hr.get(concept_key)))

    return {"preamble": preamble, "rows": rows, "notes": notes}


_LGD_METRIC_KEYS = {
    "mean realised LGD": "mean_realised_lgd",
    "mean predicted LGD": "mean_predicted_lgd",
    "gap (pred - real)": "gap_pred_minus_real",
    "cure rate realised": "cure_rate_realised",
    "cure rate predicted": "cure_rate_predicted",
    "mean sev (non-cure) realised": "mean_sev_noncure_realised",
    "mean sev (non-cure) predicted": "mean_sev_noncure_predicted",
    "decile MAE (LGD)": "decile_mae_lgd",
}

_LGD_EXHIBITS = [
    {"id": "lgd_calibration_ltv",
     "png_url": "/static/exhibits/lgd/calibration_ltv.png"},
    {"id": "lgd_cure_by_ltv",
     "png_url": "/static/exhibits/lgd/cure_by_ltv.png"},
    {"id": "lgd_distribution",
     "png_url": "/static/exhibits/lgd/lgd_distribution.png"},
]


def _parse_lgd_report() -> dict:
    """outputs/lgd/lgd_report.md -> key numbers + the three LGD exhibits."""
    text = (OUTPUTS_DIR / "lgd" / "lgd_report.md").read_text(
        encoding="utf-8")

    def _section_rows(title_prefix: str) -> list[dict]:
        for title, body in _md_sections(text):
            if title.startswith(title_prefix):
                lines = body.splitlines()
                span = _md_table_span(lines)
                return _md_table_rows(lines[span[0]:span[1]]) if span else []
        return []

    cure_stage = [{
        "variable": r[""], "coef": float(r["coef"]), "se": float(r["se"]),
        "z": float(r["z"]), "p": float(r["p"]),
        "odds_ratio": float(r["odds_ratio"]),
    } for r in _section_rows("Stage 1")]
    severity_stage = [{
        "variable": r[""], "coef": float(r["coef"]),
        "se_hc1": float(r["se(HC1)"]), "z": float(r["z"]),
        "p": float(r["p"]),
    } for r in _section_rows("Stage 2")]
    oot_calibration = {
        _LGD_METRIC_KEYS.get(r["metric"], r["metric"]):
            {"train": float(r["train"]), "oot": float(r["OOT"])}
        for r in _section_rows("OOT calibration")
    }

    cure_rate_m = re.search(r"cure rate ([\d.]+)%", text)
    cure_auc_m = re.search(r"Cure AUC: train ([\d.]+), OOT ([\d.]+)\.", text)
    loading_m = re.search(
        r"Loading = E\[max\(lgd-1,0\) \| non-cure\] = \*\*([\d.]+)\*\*", text)

    return {
        "cure_rate": (float(cure_rate_m.group(1)) / 100.0
                     if cure_rate_m else None),
        "cure_auc": ({"train": float(cure_auc_m.group(1)),
                     "oot": float(cure_auc_m.group(2))}
                    if cure_auc_m else None),
        "excess_loss_loading": (float(loading_m.group(1))
                               if loading_m else None),
        "oot_calibration": oot_calibration,
        "cure_stage_coefficients": cure_stage,
        "severity_stage_coefficients": severity_stage,
        "exhibits": _LGD_EXHIBITS,
    }


def _parse_staging_sensitivity() -> dict:
    """outputs/staging/staging_report.md -> the threshold-vs-Stage2 table."""
    text = (OUTPUTS_DIR / "staging" / "staging_report.md").read_text(
        encoding="utf-8")
    for title, body in _md_sections(text):
        if "Governance sensitivity" not in title:
            continue
        lines = body.splitlines()
        span = _md_table_span(lines)
        rows = _md_table_rows(lines[span[0]:span[1]])
        thresholds = [c for c in rows[0] if c != "snapshot"]
        out_rows = [{
            "t": int(re.search(r"\d+", r["snapshot"]).group()),
            "period": str(panel_time_to_period(
                int(re.search(r"\d+", r["snapshot"]).group()))),
            "stage2_share_pct": {k: _pct(r[k]) for k in thresholds},
        } for r in rows]
        reading_m = re.search(r"Reading: (.+?)(?:\n\n|\Z)", body, flags=re.S)
        add_on_m = re.search(r"Add-on held at ([\d.]+)pp", body)
        return {
            "add_on_pp": float(add_on_m.group(1)) if add_on_m else None,
            "thresholds": thresholds,
            "rows": out_rows,
            "reading": reading_m.group(1).strip() if reading_m else None,
            "image_url": "/static/exhibits/staging/stage2_sensitivity.png",
        }
    raise HTTPException(status_code=503,
                        detail="Governance sensitivity table not found in "
                               "outputs/staging/staging_report.md")


@app.get("/api/model/coefficients")
def model_coefficients() -> dict:
    """Hazard-ratio families + fit stats for The Model tab (see contract)."""
    return {
        "models": _parse_hazard_ratios(),
        "fit_stats": _parse_fit_stats(),
        "source_files": ["outputs/hazard/hazard_ratios.md",
                         "outputs/hazard/fit_stats.md"],
    }


@app.get("/api/model/variable_dictionary")
def model_variable_dictionary() -> dict:
    """Every modelled variable: source, window, rationale, fitted sign."""
    return _parse_variable_dictionary()


@app.get("/api/model/macro_glossary")
def model_macro_glossary() -> dict:
    """Every macro series across DCR + SFLLD + satellite: source, geography,
    transformation, lag rationale, which models consume it (Requirement 12).
    """
    return {
        "series": _MACRO_GLOSSARY,
        "source_files": [
            "outputs/variable_dictionary.md",
            "outputs/hazard/hazard_ratios.md",
            "outputs/freddie/hazard/hazard_report.md",
            "outputs/satellite/satellite_report.md",
            "freddie/macro.py",
        ],
    }


@app.get("/api/model/lgd")
def model_lgd() -> dict:
    """Two-stage workout LGD: cure/severity coefficients + calibration."""
    return _parse_lgd_report()


@app.get("/api/policy/staging_sensitivity")
def policy_staging_sensitivity() -> dict:
    """SICR ratio-threshold vs Stage-2 share -- the governance dial."""
    return _parse_staging_sensitivity()


#: three canned scenario-weight sets for the Policy tab's weights table
CANNED_WEIGHT_SETS = [
    {"id": "adopted", "label": "Adopted (25/50/25)",
     "w_up": 0.25, "w_base": 0.50, "w_down": 0.25},
    {"id": "equal_thirds", "label": "Equal-thirds (33/33/33)",
     "w_up": 1.0 / 3.0, "w_base": 1.0 / 3.0, "w_down": 1.0 / 3.0},
    {"id": "downside_tilt", "label": "Downside-tilted (15/35/50)",
     "w_up": 0.15, "w_base": 0.35, "w_down": 0.50},
]


@app.get("/api/policy/weights_table")
def policy_weights_table() -> dict:
    """Scenario table + the weighted allowance at 3 canned weight sets.

    GOVERNANCE NOTE (deliberate): each canned weight set is computed by
    calling the real ``tools.reweight_scenarios`` tool, never re-derived —
    so every call to this endpoint appends THREE lines to
    outputs/agent_log/tool_calls.jsonl (one per canned set). That is
    treated as a feature: the audit trail is meant to record every
    reweighting the app has ever shown a user, including from this Policy
    tab convenience table, not just from the Copilot chat.
    """
    state = tools._state()
    tot = state.scenario_totals
    scenario_totals = [
        {"name": n, "allowance": float(tot[n]),
         "coverage": float(tot[n] / state.balance)}
        for n in ("up", "base", "down")
    ]
    weight_sets = []
    for spec in CANNED_WEIGHT_SETS:
        result = tools.reweight_scenarios(
            w_up=spec["w_up"], w_base=spec["w_base"], w_down=spec["w_down"])
        weight_sets.append({
            "id": spec["id"], "label": spec["label"],
            "weights": result["weights"],
            "weighted_allowance": result["weighted_allowance"],
            "coverage": result["coverage"],
            "jensen_ratio": result["jensen_ratio"],
            "delta_vs_adopted_pct": result["delta_vs_adopted_pct"],
        })
    return {"amounts_in": "USD", "scenario_totals": scenario_totals,
            "weight_sets": weight_sets}


#: servable exhibit PNGs (module memory note: the fixed, reviewed list —
#: not every PNG under outputs/, only the ones the consultant curated for
#: The Model / Policy tabs)
EXHIBITS = [
    {"id": "hazard_age_baseline", "path": "hazard/age_baseline.png",
     "title": "Seasoning (age) baseline hazard",
     "caption": "Fitted natural-cubic-spline age baseline of the default "
                "hazard."},
    {"id": "hazard_pd_term_structure", "path": "hazard/pd_term_structure.png",
     "title": "PD term structure",
     "caption": "Lifetime PD term structure implied by the fitted hazards."},
    {"id": "lgd_calibration_ltv", "path": "lgd/calibration_ltv.png",
     "title": "LGD calibration by updated LTV",
     "caption": "Realised vs predicted LGD by updated-LTV decile, train vs "
                "OOT."},
    {"id": "lgd_cure_by_ltv", "path": "lgd/cure_by_ltv.png",
     "title": "Cure rate by updated LTV",
     "caption": "Realised vs predicted cure rate by updated-LTV decile."},
    {"id": "lgd_distribution", "path": "lgd/lgd_distribution.png",
     "title": "Realised LGD distribution",
     "caption": "Bimodal shape of realised workout LGD motivating the "
                "two-stage model."},
    {"id": "staging_stage2_sensitivity",
     "path": "staging/stage2_sensitivity.png",
     "title": "Stage-2 share vs SICR threshold",
     "caption": "Stage-2 share of the book at t=20 and t=40 across SICR "
                "ratio thresholds."},
    {"id": "staging_stage_distribution",
     "path": "staging/stage_distribution.png",
     "title": "Stage distribution over time",
     "caption": "Stage 1/2/3 population shares at each reporting "
                "snapshot."},
    {"id": "scenario_jensen_gap", "path": "scenario_ecl/jensen_gap.png",
     "title": "Jensen gap",
     "caption": "Weighted-scenario allowance vs allowance at the "
                "weighted-average macro path."},
    {"id": "scenario_ecl_bars", "path": "scenario_ecl/scenario_ecl_bars.png",
     "title": "Scenario ECL comparison",
     "caption": "Reported allowance under the up / base / down scenarios."},
    {"id": "scenario_z_paths", "path": "scenario_ecl/z_paths.png",
     "title": "Scenario Z paths",
     "caption": "Recovered credit-cycle factor Z under each scenario's "
                "macro path."},
    {"id": "vasicek_credit_cycle", "path": "vasicek/credit_cycle.png",
     "title": "Credit cycle (PIT vs TTC)",
     "caption": "Recovered systematic factor Z_t and the PIT-vs-TTC PD gap "
                "through the cycle."},
    {"id": "eda_default_rate_vs_macro",
     "path": "eda/default_rate_vs_macro.png",
     "title": "Default rate vs macro",
     "caption": "Quarterly default rate against the macro series (EDA)."},
    {"id": "eda_hazard_by_loan_age", "path": "eda/hazard_by_loan_age.png",
     "title": "Hazard by loan age",
     "caption": "Empirical default hazard by loan age (EDA)."},
    {"id": "eda_lgd_realised_bimodal",
     "path": "eda/lgd_realised_bimodal.png",
     "title": "Realised LGD (EDA)",
     "caption": "Raw bimodal realised-LGD histogram, before modelling."},
    {"id": "eda_origination_quality", "path": "eda/origination_quality.png",
     "title": "Origination quality over vintages",
     "caption": "FICO / LTV origination quality drift across vintages."},
    {"id": "eda_prepay_vs_rate_incentive",
     "path": "eda/prepay_vs_rate_incentive.png",
     "title": "Prepayment vs rate incentive",
     "caption": "Empirical prepayment rate against the note-vs-market rate "
                "incentive."},
    {"id": "eda_vintage_cumulative_default",
     "path": "eda/vintage_cumulative_default.png",
     "title": "Cumulative default by vintage",
     "caption": "Cumulative default curves by origination vintage."},
]


@app.get("/api/exhibits/list")
def exhibits_list() -> dict:
    """id -> {title, png_url, caption} for every servable exhibit PNG."""
    return {"exhibits": [
        {"id": e["id"], "title": e["title"],
         "png_url": f"/static/exhibits/{e['path']}", "caption": e["caption"]}
        for e in EXHIBITS
    ]}


# ---------------------------------------------------------------------------
# App v3: The 'Real Data' tab -- Freddie Mac SFLLD Phase A/B parsers.
#
# freddie/ (read-only here; FROZEN like the engine) built a full second,
# REAL-data pipeline alongside the DCR-synthetic engine above -- a champion
# hazard/LGD refit on the real Freddie Mac SFLLD panel, an ALFRED-vintage
# backtest, and an LSTM path-dependence challenger. These views parse
# outputs/freddie/**'s already-written reports/CSVs/JSON into JSON on every
# request, exactly like the Model/Policy parsers above -- every number is
# read off those artifacts VERBATIM, never recomputed here. Exact response
# shapes are documented in docs/api_contract.md.
# ---------------------------------------------------------------------------

FREDDIE_DIR = OUTPUTS_DIR / "freddie"


def _freddie_text(*parts: str) -> str:
    return FREDDIE_DIR.joinpath(*parts).read_text(encoding="utf-8")


def _freddie_json(*parts: str) -> dict:
    return json.loads(_freddie_text(*parts))


def _parse_freddie_panel() -> dict:
    """gate_phaseA.md section 4 -> per-vintage panel stats + totals."""
    text = _freddie_text("gate_phaseA.md")
    for title, body in _md_sections(text):
        if not title.startswith("4. Per-vintage panel stats"):
            continue
        lines = body.splitlines()
        span = _md_table_span(lines)
        raw_rows = _md_table_rows(lines[span[0]:span[1]])
        vintages = [{
            "vintage": r["vintage"],
            "n_loans": int(_num(r["n_loans"])),
            "n_loan_months": int(_num(r["n_loan_months (modeled)"])),
            "d90_rate_pct": round(float(r["d90 rate"]) * 100, 2),
            "prepay_rate_pct": round(float(r["prepay rate"]) * 100, 2),
            "other_terminal_rate_pct": round(float(r["other-terminal rate"]) * 100, 2),
            "censored_rate_pct": round(float(r["censored rate"]) * 100, 2),
            "perf_window_end": r["perf. window end"],
        } for r in raw_rows]
        totals_m = re.search(
            r"\*\*Totals\*\*:\s*([\d,]+) loans,\s*([\d,]+) modeled "
            r"loan-months,\s*overall D90 rate ([\d.]+),\s*overall\s*"
            r"prepay rate ([\d.]+)\.", body)
        return {
            "n_loans": int(_num(totals_m.group(1))),
            "n_loan_months": int(_num(totals_m.group(2))),
            "n_vintages": len(vintages),
            "overall_d90_rate_pct": round(float(totals_m.group(3)) * 100, 2),
            "overall_prepay_rate_pct": round(float(totals_m.group(4)) * 100, 2),
            "vintages": vintages,
        }
    raise HTTPException(status_code=503,
                        detail="panel stats section not found in "
                               "outputs/freddie/gate_phaseA.md")


def _parse_freddie_hazard() -> dict:
    """coefficients.csv + dcr_sign_comparison.csv + metrics + COVID verdict."""
    coef_df = pd.read_csv(FREDDIE_DIR / "hazard" / "coefficients.csv")
    coefficients = []
    for _, r in coef_df.iterrows():
        coef, hr = float(r["coef"]), float(r["hazard_ratio"])
        row = {
            "term": r["term"], "coef": coef, "std_err": float(r["std_err"]),
            "z": float(r["z"]), "p_value": float(r["p_value"]),
            "ci_low": float(r["ci_low"]), "ci_high": float(r["ci_high"]),
            "hazard_ratio": hr,
        }
        row.update(_variable_interpretation(
            _freddie_term_concept(r["term"]), hr, coef))
        coefficients.append(row)

    sign_df = pd.read_csv(FREDDIE_DIR / "hazard" / "dcr_sign_comparison.csv")
    dcr_sign_comparison = [{
        "variable": r["variable"],
        "dcr_variable": (None if pd.isna(r["dcr_variable"]) else r["dcr_variable"]),
        "dcr_expected_sign": r["dcr_expected_sign"],
    } for _, r in sign_df.iterrows()]

    metrics = _freddie_json("hazard", "metrics.json")
    covid_metrics = _freddie_json("hazard", "covid_metrics.json")
    dcr_fit_stats = _parse_fit_stats()["default"]     # reused, not re-derived

    text = _freddie_text("hazard", "hazard_report.md")
    rec_m = re.search(
        r"\*\*Recommendation \(follows the numbers above\)\*\*:\s*(.+?)"
        r"(?=\n## )", text, flags=re.S)

    return {
        "coefficients": coefficients,
        "dcr_sign_comparison": dcr_sign_comparison,
        "metrics": {
            "train_auc": metrics["train_auc"], "oot_auc": metrics["oot_auc"],
            "train_n": metrics["train_n"], "train_events": metrics["train_events"],
            "oot_n": metrics["oot_n"], "oot_events": metrics["oot_events"],
            "mcfadden_r2": metrics["mcfadden_r2"],
            "dcr_train_auc": dcr_fit_stats["train_auc"],
            "dcr_oot_auc": dcr_fit_stats["oot_auc"],
        },
        "covid": {
            "verdict": "exclude",
            "window": "2020-04..2021-09",
            "naive_oot2_auc": covid_metrics["naive_oot2_auc"],
            "additive_oot2_auc": covid_metrics["additive_oot2_auc"],
            "exclude_oot2_auc": covid_metrics["exclude_oot2_auc"],
            "recommendation": rec_m.group(1).strip() if rec_m else None,
        },
        "source_files": [
            "outputs/freddie/hazard/coefficients.csv",
            "outputs/freddie/hazard/dcr_sign_comparison.csv",
            "outputs/freddie/hazard/metrics.json",
            "outputs/freddie/hazard/covid_metrics.json",
            "outputs/freddie/hazard/hazard_report.md",
            "outputs/hazard/fit_stats.md",
        ],
    }


def _parse_freddie_lgd_summary() -> dict:
    """population_lgd_summary.csv + the cure-AUC / excess-loading callouts."""
    df = pd.read_csv(FREDDIE_DIR / "lgd" / "population_lgd_summary.csv") \
        .set_index("split")
    text = _freddie_text("lgd", "lgd_report.md")
    cure_auc_m = re.search(
        r"Cure AUC: train \*\*([\d.]+)\*\*, OOT \*\*([\d.]+)\*\*", text)
    loading_m = re.search(
        r"Overall \(DCR-style\) constant loading: \*\*([\d.]+)\*\* "
        r"\(vs DCR's ([\d.]+)\)", text)
    return {
        "mean_realized_lgd_train": float(df.loc["train", "mean_realized_lgd"]),
        "mean_realized_lgd_oot": float(df.loc["oot", "mean_realized_lgd"]),
        "cure_auc_train": float(cure_auc_m.group(1)),
        "cure_auc_oot": float(cure_auc_m.group(2)),
        "excess_loading_sflld": float(loading_m.group(1)),
        "excess_loading_dcr": float(loading_m.group(2)),
    }


def _parse_freddie_backtest_rows() -> list[dict]:
    """backtest/all_metrics.json (exact floats) -> the per-asof table."""
    rows = _freddie_json("backtest", "all_metrics.json")
    return [{
        "asof": r["asof"][:7],                        # '2007-12-01' -> '2007-12'
        "fit_n": r["fit_n"], "fit_events": r["fit_events"],
        "n_active_loans": r["n_active_loans"],
        "realized_cum_d90": r["realized_cum_d90"],
        "predicted_cum_d90_frozen": r["predicted_cum_d90_frozen"],
        "miss_ratio_frozen": r["miss_ratio_frozen"],
        "predicted_cum_d90_actual": r["predicted_cum_d90_actual"],
        "miss_ratio_actual": r["miss_ratio_actual"],
    } for r in rows]


@app.get("/api/freddie/summary")
def freddie_summary() -> dict:
    """Panel scale + the headline numbers for the 'Real Data' tab hero."""
    panel = _parse_freddie_panel()
    hazard = _parse_freddie_hazard()
    lgd = _parse_freddie_lgd_summary()
    backtest_rows = _parse_freddie_backtest_rows()
    lstm = _freddie_json("lstm", "metrics.json")
    gate_text = _freddie_text("gate_phaseB.md")
    verdict_m = re.search(r"## 6\. Verdict\s*\*\*(PASS|FAIL)\.\*\*", gate_text)

    worst = max(backtest_rows, key=lambda r: r["miss_ratio_frozen"])
    saturation = min(backtest_rows, key=lambda r: r["miss_ratio_actual"])

    return {
        "panel": panel,
        "hazard": hazard["metrics"],
        "covid": hazard["covid"],
        "lgd": lgd,
        "backtest_headline": {
            "worst_asof": worst["asof"],
            "worst_miss_ratio_frozen": worst["miss_ratio_frozen"],
            "worst_miss_ratio_actual": worst["miss_ratio_actual"],
            "saturation_asof": saturation["asof"],
            "saturation_miss_ratio_actual": saturation["miss_ratio_actual"],
        },
        "lstm": {
            "oot_champion_auc": lstm["oot_champion_auc"],
            "oot_lstm_auc": lstm["oot_lstm_auc"],
            "prior_dlq_champion_auc": lstm["oot_prior_dlq_champion_auc"],
            "prior_dlq_lstm_auc": lstm["oot_prior_dlq_lstm_auc"],
            "clean_champion_auc": lstm["oot_clean_history_champion_auc"],
            "clean_lstm_auc": lstm["oot_clean_history_lstm_auc"],
        },
        "gate_verdict": verdict_m.group(1) if verdict_m else None,
        "source_files": [
            "outputs/freddie/gate_phaseA.md",
            "outputs/freddie/hazard/metrics.json",
            "outputs/freddie/hazard/covid_metrics.json",
            "outputs/freddie/hazard/hazard_report.md",
            "outputs/freddie/lgd/population_lgd_summary.csv",
            "outputs/freddie/lgd/lgd_report.md",
            "outputs/freddie/backtest/all_metrics.json",
            "outputs/freddie/lstm/metrics.json",
            "outputs/freddie/gate_phaseB.md",
        ],
    }


@app.get("/api/freddie/hazard")
def freddie_hazard() -> dict:
    """Coefficients + DCR sign comparison + AUCs + the COVID regime verdict."""
    return _parse_freddie_hazard()


@app.get("/api/freddie/backtest")
def freddie_backtest() -> dict:
    """Per-reporting-date predicted/realized/miss-ratio table -- the honesty exhibit."""
    rows = _parse_freddie_backtest_rows()
    text = _freddie_text("backtest", "backtest_report.md")
    honesty_m = re.search(
        r"\*\*2007-12 check \(spec requirement\)\*\*:\s*(.+?)(?=\n\n)",
        text, flags=re.S)
    narrative_m = re.search(
        r"## 1\. IFRS-9 narrative: PIT hazard vs forward-looking overlay\n"
        r"(.+?)(?=\n## )", text, flags=re.S)
    covid_panel_m = re.search(
        r"## 3\. The 2019-12-vs-COVID panel[^\n]*\n(.+?)(?=\n## )",
        text, flags=re.S)
    return {
        "rows": rows,
        "central_honesty_note": honesty_m.group(1).strip() if honesty_m else None,
        "overlay_narrative": narrative_m.group(1).strip() if narrative_m else None,
        "covid_panel_note": covid_panel_m.group(1).strip() if covid_panel_m else None,
        "source_files": ["outputs/freddie/backtest/all_metrics.json",
                         "outputs/freddie/backtest/backtest_report.md"],
    }


#: servable Freddie SFLLD exhibit PNGs (the consultant-curated subset for
#: the 'Real Data' tab -- captions/sources hand-authored against the
#: reports, same convention as EXHIBITS above).
FREDDIE_EXHIBITS = [
    {"id": "freddie_vintage_curves", "path": "eda/exhibit1_vintage_curves.png",
     "title": "Vintage curves -- cumulative D90 by months on book",
     "caption": "2007 vintage reaches 16.26% cumulative D90 by month 225 vs "
                "14.11% (2006) and 9.14% (2008) -- the pre-crisis-vintage "
                "hump; every 2018-2025 modern vintage tops out below 5.48%.",
     "source": "outputs/freddie/eda/eda_report.md#Exhibit 1"},
    {"id": "freddie_roll_rate_matrices", "path": "eda/exhibit2_roll_rate_matrices.png",
     "title": "Roll-rate matrices -- GFC vs calm vs COVID",
     "caption": "COVID's 60->90+ roll rate (58.25%) exceeds the GFC's "
                "(47.43%), yet 90+->liquidation collapses to 0.21% (vs "
                "2.02% GFC) -- the forbearance-accounting signature: "
                "delinquency-status escalation without loss realization.",
     "source": "outputs/freddie/eda/eda_report.md#Exhibit 2"},
    {"id": "freddie_calendar_time_series", "path": "eda/exhibit3_calendar_time_series.png",
     "title": "Calendar-time D90-entry rate",
     "caption": "The COVID spike (1.775% in 2020-06) is ~4.5x the GFC's own "
                "peak (0.396% in 2009-10) on a naive D90 count -- read "
                "alongside the roll-rate exhibit, not as evidence COVID "
                "was the worse credit event.",
     "source": "outputs/freddie/eda/eda_report.md#Exhibit 3"},
    {"id": "freddie_state_heterogeneity", "path": "eda/exhibit4_state_heterogeneity.png",
     "title": "State heterogeneity -- 2006-07 vintage default vs HPI drawdown",
     "caption": "NV (38.0%), FL (32.6%), AZ (27.9%) vs VT (4.8%), AK "
                "(5.3%), WY (6.2%); default rate vs peak-to-trough HPI "
                "drawdown fits slope 0.491, r=0.89 across 49 states.",
     "source": "outputs/freddie/eda/eda_report.md#Exhibit 4"},
    {"id": "freddie_severity_cycle", "path": "lgd/severity_by_liq_year.png",
     "title": "Realized severity by liquidation year",
     "caption": "Severity plateaus >=50% mean LGD from 2011-2016, peaking "
                "in 2016 (mean 60.8%) -- years after the GFC's default "
                "wave -- because REO/short-sale liquidation lags the "
                "origination-era credit event.",
     "source": "outputs/freddie/lgd/lgd_report.md"},
    {"id": "freddie_hazard_calibration_by_year", "path": "hazard/calibration_by_year.png",
     "title": "Hazard calibration by calendar year",
     "caption": "Observed vs predicted D90 hazard by calendar year, "
                "champion fit scored on the full panel -- includes the "
                "2020 saturation row (observed 0.357% vs predicted 4.162%).",
     "source": "outputs/freddie/hazard/hazard_report.md#4"},
    {"id": "freddie_seasoning_curve", "path": "hazard/seasoning_curve.png",
     "title": "Seasoning curve -- fitted default hazard by loan age",
     "caption": "Natural-cubic-spline age baseline; empirical hazard peaks "
                "42-48mo (0.256% monthly), consistent with the DCR "
                "champion's ~12-quarter peak.",
     "source": "outputs/freddie/hazard/hazard_report.md#4"},
    {"id": "freddie_state_uer_effect", "path": "hazard/state_uer_effect.png",
     "title": "State UER effect -- predicted vs observed hazard by UER quartile",
     "caption": "OOT-scored predicted vs observed hazard across state "
                "uer_lag1 quartiles.",
     "source": "outputs/freddie/hazard/hazard_report.md#4"},
    {"id": "freddie_covid_calibration_comparison", "path": "hazard/covid_calibration_comparison.png",
     "title": "COVID regime treatment comparison -- naive / additive / exclude",
     "caption": "Only 'exclude' preserves economically-signed macro "
                "coefficients (delta_uer_lag1 +0.774, hpi_growth_lag1 "
                "-3.307); OOT2 AUC spread (0.7553/0.7547/0.7509) is too "
                "small to override that structural argument.",
     "source": "outputs/freddie/hazard/hazard_report.md#3"},
    {"id": "freddie_backtest_200712", "path": "backtest/predicted_vs_realized_200712.png",
     "title": "Backtest honesty panel -- 2007-12 GFC miss",
     "caption": "A model refit through 2007-12 with macro frozen at "
                "then-current levels predicts 0.928% 36-month D90 vs a "
                "realized 8.750% -- a 9.42x underprediction of the GFC it "
                "could not see coming.",
     "source": "outputs/freddie/backtest/backtest_report.md#2"},
    {"id": "freddie_backtest_201912", "path": "backtest/predicted_vs_realized_201912.png",
     "title": "Backtest -- 2019-12 COVID-window miss",
     "caption": "Frozen-macro projection underpredicts 5.00x (0.920% vs "
                "realized 4.601%); fed the real April-2020 UER print, the "
                "hindsight projection saturates to 71.5% -- ~20 SDs "
                "outside training support.",
     "source": "outputs/freddie/backtest/backtest_report.md#3"},
    {"id": "freddie_lstm_calibration", "path": "lstm/calibration_comparison.png",
     "title": "LSTM vs champion calibration by calendar year",
     "caption": "Observed vs each model's predicted monthly D90 hazard by "
                "calendar year, forbearance window shaded.",
     "source": "outputs/freddie/lstm/lstm_report.md#2"},
    {"id": "freddie_lstm_lift_split", "path": "lstm/lift_split.png",
     "title": "LSTM lift decomposition -- clean history vs prior-delinquency spell",
     "caption": "OOT AUC lift concentrates almost entirely on loans with a "
                "prior delinquency spell (champion 0.5698 -> LSTM 0.9570, "
                "+0.387) vs near-zero on clean-history loans (0.5386 -> "
                "0.5287, -0.010) -- the path-dependence signature.",
     "source": "outputs/freddie/lstm/lstm_report.md#3"},
]


@app.get("/api/freddie/exhibits")
def freddie_exhibits() -> dict:
    """id -> {title, png_url, caption, source} for the curated Freddie PNGs."""
    return {"exhibits": [
        {"id": e["id"], "title": e["title"],
         "png_url": f"/static/freddie/{e['path']}", "caption": e["caption"],
         "source": e["source"]}
        for e in FREDDIE_EXHIBITS
    ]}


# ---------------------------------------------------------------------------
# 2a. Tier-1 tools (pydantic arg models double as the OpenAPI schema;
#     FastAPI 422s malformed bodies BEFORE the engine runs — governing rule)
# ---------------------------------------------------------------------------


@app.post("/api/tools/shock_macro")
def api_shock_macro(args: ShockMacroArgs) -> dict:
    return tools.shock_macro(**args.model_dump())


@app.post("/api/tools/reweight_scenarios")
def api_reweight_scenarios(args: ReweightArgs) -> dict:
    return tools.reweight_scenarios(**args.model_dump())


@app.post("/api/tools/rerun_ecl")
def api_rerun_ecl(args: RerunEclArgs) -> dict:
    return tools.rerun_ecl(**args.model_dump())


@app.post("/api/tools/decompose_waterfall")
def api_decompose_waterfall(args: DecomposeWaterfallArgs) -> dict:
    return tools.decompose_waterfall(**args.model_dump())


# ---------------------------------------------------------------------------
# 2b. agent ask + SSE trace stream
# ---------------------------------------------------------------------------


@app.post("/api/agent/ask")
async def agent_ask(req: AskRequest) -> dict:
    """Route a question through the agent; one at a time (demo limit)."""
    if not _ASK_SEMAPHORE.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="the agent is answering another question — one at a "
                   "time in this single-worker demo; retry in a moment")
    try:
        return await run_in_threadpool(_run_agent, req.question)
    finally:
        _ASK_SEMAPHORE.release()


async def _sse_events():
    """Replay the buffered latest trace, then stream live events."""
    q = BROKER.subscribe()
    try:
        last_id = 0
        for ev in BROKER.snapshot():
            last_id = max(last_id, ev.get("_id", 0))
            yield f"data: {json.dumps(ev)}\n\n"
        while True:
            try:
                ev = await asyncio.wait_for(q.get(), timeout=SSE_KEEPALIVE_S)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if ev.get("_id", 0) <= last_id:          # already replayed
                continue
            last_id = ev["_id"]
            yield f"data: {json.dumps(ev)}\n\n"
    finally:
        BROKER.unsubscribe(q)


@app.get("/api/agent/stream")
async def agent_stream() -> StreamingResponse:
    """SSE feed of the most recent /ask trace (single-worker, in-memory)."""
    return StreamingResponse(
        _sse_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 2c. auto-interpretation hook (Scenario Lab: narrate an ALREADY-COMPUTED
#     tool result) -- reuses agent/graph.py's narrator machinery verbatim,
#     no duplicated anti-hallucination logic
# ---------------------------------------------------------------------------


@app.post("/api/agent/interpret")
def agent_interpret(req: InterpretRequest) -> dict:
    """Narrate a tool's OWN result JSON; never invents a number.

    The LLM narrates ONLY the passed-in `result`; the same mechanical check
    used by the live copilot (agent/graph.py) asserts every number in the
    narration appears in that JSON — for query_model_docs, that every
    number appears in a retrieved passage AND a real citation is quoted.
    On any check failure or LLM error the response falls back to the
    engine's own deterministic text (the tool's `headline`, or the
    passage listing for query_model_docs); `grounded` reports which
    happened: True iff the LLM's own prose passed the check.
    """
    result = dict(req.result)
    result.setdefault("tool", req.tool)
    required = ("passages",) if req.tool == "query_model_docs" \
        else ("headline", "tool_call_id")
    missing = [k for k in required if k not in result]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"result is missing required field(s) {missing} for "
                   f"tool {req.tool!r}")

    if req.tool == "query_model_docs":
        try:
            text, model_used = agent_graph._llm_narrate_docs(result)
            ok = agent_graph.docs_answer_ok(text, result)
            mode = "llm" if ok else "template_citation_check_failed"
        except Exception as exc:
            text, model_used, ok = None, None, False
            mode = f"template_llm_error:{type(exc).__name__}"
        interpretation = (text.strip() if ok
                          else agent_graph.deterministic_docs_narration(result))
    else:
        try:
            text, model_used = agent_graph._llm_narrate(result)
            ok = agent_graph.narration_numbers_ok(text, result)
            mode = "llm" if ok else "template_number_check_failed"
        except Exception as exc:
            text, model_used, ok = None, None, False
            mode = f"template_llm_error:{type(exc).__name__}"
        interpretation = (text.strip() if ok
                          else agent_graph.deterministic_narration(result))

    return {"interpretation": interpretation, "grounded": bool(ok),
            "mode": mode}


# ---------------------------------------------------------------------------
# 3. the built SPA (mounted LAST so /api/* wins the route match) -- the
#    exhibits static mount goes BEFORE it so /static/exhibits/* is matched
#    first (Starlette tries routes in registration order)
# ---------------------------------------------------------------------------

if OUTPUTS_DIR.exists():
    app.mount("/static/exhibits", StaticFiles(directory=OUTPUTS_DIR),
             name="exhibits")

#: dedicated Freddie SFLLD mount (outputs/freddie/** is ALSO reachable via
#: /static/exhibits/freddie/** above since that mount covers the whole
#: outputs/ tree -- this second mount exists only so freddie png_url's read
#: as /static/freddie/... per the contract, not because the files aren't
#: already served).
if FREDDIE_DIR.exists():
    app.mount("/static/freddie", StaticFiles(directory=FREDDIE_DIR),
             name="freddie")

#: MDD (Model Development Document) mount -- guarded like the two mounts
#: above because outputs/mdd/ may not exist yet (a parallel agent's
#: deliverable); the header link is wired unconditionally regardless (see
#: app/ui/src/app.jsx), so it 404s harmlessly until that MDD lands.
MDD_DIR = OUTPUTS_DIR / "mdd"
if MDD_DIR.exists():
    app.mount("/static/mdd", StaticFiles(directory=MDD_DIR), name="mdd")

if (UI_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
else:
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def ui_not_built() -> str:
        return (
            "<!doctype html><title>IFRS 9 ECL Copilot</title>"
            "<body style='font-family:system-ui;max-width:40rem;margin:4rem "
            "auto;line-height:1.5'><h1>UI not built yet</h1><p>The API is "
            "up (see <a href='/docs'>/docs</a>), but <code>app/ui/dist</code>"
            " is missing. Build it with:</p><pre>cd app/ui && npm install && "
            "npm run build</pre><p>then restart the server.</p></body>"
        )


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=7860, workers=1)
