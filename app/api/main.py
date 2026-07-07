"""FastAPI backend: the frozen ECL engine, the Tier-1 agent, the built UI.

One process serves three things on port 7860 (HF Spaces Docker convention):

  1. Engine data (read-only views over agent/tools_tier1.py caches)
       GET /api/health                 liveness + warm-up timing
       GET /api/ecl/summary            headline stats + scenario table
       GET /api/ecl/waterfall          movement decomposition between snapshots
       GET /api/exhibits/credit_cycle  Z path from outputs/vasicek/z_path.csv

  2. The agent
       POST /api/tools/{tool}          the four Tier-1 tools, pydantic-guarded
       POST /api/agent/ask             {question} -> {answer, route, trace}
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
    -> {"answer": str, "route": str, "trace": list[dict]}` in agent/graph.py
    or agent/router.py (resolved at lifespan startup), or
  * setting `app.api.main.AGENT_ASK` directly (what the tests do to mock it).
Until it lands, a deterministic keyword fallback router answers: it routes
to the same four Tier-1 tools, narrates ONLY the engine-built headline
strings, and refuses everything else ("outside my validated scope"). It
makes no LLM call, so the app runs fully offline.

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
    else:
        answer, route, trace = str(raw), "unknown", events
    if not events and trace:          # agent returned a trace without emitting
        for ev in trace:              # -> replay it so /stream still shows it
            BROKER.publish(dict(ev))
    return {"answer": answer, "route": route, "trace": trace}


# ---------------------------------------------------------------------------
# request/response models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)


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
# 3. the built SPA (mounted LAST so /api/* wins the route match)
# ---------------------------------------------------------------------------

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
