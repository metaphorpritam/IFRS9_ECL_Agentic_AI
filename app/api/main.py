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
        coefficients = [{
            "variable": r["Covariate"],
            "family": r["family"],
            "hazard_ratio": float(r["HR = exp(coef)"]),
            "ci": _parse_ci(r["95% CI"]),
            "p": _parse_p(r["p"])[0],
            "p_display": _parse_p(r["p"])[1],
            "story": stories.get(r["family"], "").strip(),
        } for r in table_rows]
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
