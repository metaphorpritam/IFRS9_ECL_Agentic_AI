# IFRS 9 ECL Copilot

**An agentic "what-if" copilot for IFRS 9 expected-credit-loss reporting — built
on the rule that the LLM never does arithmetic.**

Live demo: **<https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot>**
(HF Spaces, Docker SDK, public; first load after a cold start takes ~30 s while
the engine warms).

Risk teams need to answer questions like *"what happens to the allowance if
unemployment rises 2 points?"* in minutes, with numbers they can defend to
audit. LLMs are great at the conversation and terrible at the arithmetic. This
project splits the two: a frozen, unit-tested ECL engine computes every number;
a LangGraph agent only **routes** the question to a typed tool, **parameterises**
it under pydantic validation, and **narrates** the engine's output — with a
mechanical post-check that every number in the narration appears verbatim in
the tool's JSON — plus a 5th route for documentation questions (Tier 3,
below), held to the same rule. Questions outside those five validated routes
get an explicit refusal ("outside my validated scope"). The refusal is a
governance feature, demonstrated on purpose.

## Architecture

```
Freddie Mac loan-level panel (2000Q2–2015Q1, 60 quarters)   DFAST 2026 scenarios
        │                                                          │
        ▼                                                          ▼
┌───────────────────────── FROZEN ENGINE (Day 1–2, 187 tests) ─────────────────┐
│ engine/hazard.py   cloglog default + prepay hazards (age spline, LTV×UER)    │
│ engine/lgd.py      two-part LGD (cure × loss-given-liquidation)              │
│ engine/ead.py      amortising EAD profiles          engine/staging.py  SICR  │
│ engine/ecl.py      12m/lifetime ECL + movement decomposition (identity)      │
└──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌────────────────────────── SCENARIO LAYER (Day 3, 91 tests) ──────────────────┐
│ engine/vasicek.py    Belkin Z recovery, ρ = 0.0227 (Var(Z)=1)                 │
│ engine/scenarios.py  DFAST shapes rebased to the t=60 jump-off, 40q paths,   │
│                      weights 50/25/25 (up/base/down)                         │
│ engine/satellite.py  macro → Z satellite; scenario ECL: up $27.7m /          │
│                      base $30.5m / severe $47.6m → weighted $34.0m (1.035x)  │
└──────────────────────────────────────────────────────────────────────────────┘
        │  four typed tools (pydantic, extra='forbid'; audit trail JSONL)
        ▼
┌────────────────────────── AGENT + APP (Day 4, 103 tests) ────────────────────┐
│ agent/tools_tier1.py  shock_macro · reweight_scenarios · rerun_ecl ·         │
│                       decompose_waterfall                                    │
│ agent/graph.py        LangGraph router→tool→narrator→refusal (OpenRouter:    │
│                       Gemma 4 31B primary, DeepSeek fallback, temp 0,        │
│                       verbatim-number post-check)                            │
│ app/api/main.py       FastAPI :7860 — engine views, tools, /ask, SSE trace   │
│ app/ui/               Preact + ECharts SPA (4 components + header)           │
└──────────────────────────────────────────────────────────────────────────────┘
        │  + a 5th route, no LLM in the retrieval path (41 stretch tests)
        ▼
┌────────────────────────── TIER-3 + MCP (stretch, 41 tests) ──────────────────┐
│ agent/tier3_retrieval.py  query_model_docs — deterministic lexical/graph     │
│                           retrieval over wiki/ + knowledge/corpus, cited     │
│                           passages only, zero LLM calls inside the tool      │
│ agent/mcp_server.py       the 4 Tier-1 tools over MCP (fastmcp) — same       │
│                           pydantic models, same frozen-engine numbers        │
└──────────────────────────────────────────────────────────────────────────────┘
```

**The governing rule** (enforced in review and in code): the LLM never computes.
Malformed tool arguments are rejected by pydantic before any engine code runs;
narrations that invent numbers are replaced by the engine's own deterministic
headline; every successful tool call is one line in a replayable JSONL audit
trail with a `tc-<seq>` reference quoted in the answer. The rule extends to
Tier-3 (below): the LLM never invents documentation either — only what a
retrieved passage says, citing it.

## Tier 3: knowledge questions, answered with citations

Not every good question has a number behind it — *"how is LGD split into cure
and severity?"*, *"why is ρ so far below the Basel 0.15 convention?"* are
methodology questions, not arithmetic. A 5th route, `query_model_docs`
(`agent/tier3_retrieval.py`), answers these from two on-disk sources — the
model-development wiki (`wiki/`, 19 pages) and the indexed IFRS 9 credit-risk
notes corpus (`knowledge/corpus/`, 69 nodes) — using the same deterministic
lexical + typed-graph scoring as the `llm-wiki` and `pageindex-plus` skills
(reused via `importlib`, never reimplemented). **No LLM call happens inside
retrieval** — same question, same files, same passages, every time. The
narrator may only state what a returned passage says, and every claim
carries a real, verified citation: `pages/ecl-engine.md#Headline numbers` or
`notes §9.2 p10`, never an invented heading or page number. A mechanical
post-check on the narration enforces this the same way the Tier-1
verbatim-number check does; a question with no matching passage gets an
explicit "nothing to cite" rather than a guess.

## Quickstart

Data note: the Freddie Mac loan-level files are a licensed download and are not
redistributed here (`data/` is gitignored). `data/processed/panel.parquet` is
built once by the Day-1 panel pipeline; the DFAST 2026 CSVs come from the
Federal Reserve site.

### Local (uv, Python 3.13)

```bash
uv sync
cp .env.example .env            # add OPENROUTER_API_KEY (optional — see below)
cd app/ui && npm install && npm run build && cd ../..
uv run --no-sync uvicorn app.api.main:app --port 7860
# open http://localhost:7860
```

Without an `OPENROUTER_API_KEY` the app still runs: a deterministic keyword
router answers the four tool families offline and refuses everything else.

### Docker (what the HF Space runs)

```bash
docker build -t ifrs9-ecl-copilot .
docker run -e OPENROUTER_API_KEY -p 7860:7860 ifrs9-ecl-copilot
```

No secret is ever baked into the image (`.dockerignore` excludes `.env`; the
release check greps the saved image layers for key prefixes — zero matches).
The model-fit cache (`outputs/models/tier1_models.joblib`) ships in the image,
so startup is a ~10–25 s warm load, not a ~50 s refit; tool calls answer in
seconds from in-memory state.

```bash
uv run --no-sync pytest tests/ -q          # 422 passed
```

## MCP server: the same four tools, over the Model Context Protocol

`agent/mcp_server.py` exposes the four Tier-1 tools — `shock_macro`,
`reweight_scenarios`, `rerun_ecl`, `decompose_waterfall` — as an MCP server,
so any MCP client (Claude Desktop, an IDE agent, a script using the
`fastmcp`/`mcp` SDK) can call them directly, with no HTTP layer and no
copilot UI in between. It is a **thin adapter only**: every argument schema
is the real pydantic model from `agent/tools_tier1.TIER1_ARG_MODELS`
(bounds, `extra="forbid"`, and every cross-field check — weights summing to
1, shock bounds, `t0 < t1` — run unchanged), and every number in every
response comes straight from the frozen IFRS 9 engine, exactly as it does
through the FastAPI routes or the LangGraph copilot. **One validated model,
three surfaces** (direct Python call, `POST /api/tools/{tool}`, MCP) — same
functions, same numbers, no re-implementation anywhere.

```bash
# stdio transport (default) -- what an MCP client launches as a subprocess
uv run --no-sync python -m agent.mcp_server

# equivalent, via the fastmcp CLI
uv run --no-sync fastmcp run agent/mcp_server.py:mcp
```

Register it in Claude Desktop (or any MCP client) by adding to that client's
MCP config:

```json
{
  "mcpServers": {
    "ifrs9-ecl-copilot": {
      "command": "uv",
      "args": [
        "run", "--no-sync",
        "--directory", "/absolute/path/to/IFRS9_ECL_Agentic_AI",
        "python", "-m", "agent.mcp_server"
      ]
    }
  }
}
```

Restart the client; it will list the four tools plus the
`resource://ifrs9-ecl/health` resource. `tests/test_mcp.py` calls the server
in-process (fastmcp's `Client` against the in-memory `mcp` object — no
subprocess, no network) and checks parity with a direct call, schema
fidelity against `TIER1_ARG_MODELS`, and that invalid arguments fail loud
(`fastmcp.exceptions.ToolError`) rather than crash or write to the audit
trail. First tool call in a fresh process pays the engine's warm-up cost
once (~9s joblib warm start); poll `resource://ifrs9-ecl/health` (cheap,
never triggers warm-up) to check `engine_warm` first. Full walkthrough:
`outputs/mcp/README_section.md`.

## Six-question demo script

1. **"What happens to Stage 2 ECL if unemployment rises 2%?"** → routes to
   `shock_macro(UER, +2pp, parallel)`: base allowance $30.5m → $31.7m (+4.1%),
   with the stage split and the remeasurement driver quoted from the engine.
2. **"Reweight the scenarios to 25/50/25 — what does that do?"** → routes to
   `reweight_scenarios`: weighted allowance and Jensen ratio recomputed from
   the three cached scenario books.
3. **"How much of the allowance sits in high-LTV loans?"** → routes to
   `rerun_ecl(segment=high_ltv)`.
4. **"Decompose the allowance movement between quarter 20 and quarter 40."** →
   routes to `decompose_waterfall(20, 40)`: opening + stage migration +
   remeasurement + derecognitions + new loans = closing, an identity asserted
   inside the frozen engine.
5. **"Explain the ECL movement waterfall."** → routes to `query_model_docs`
   (Tier 3, no number requested — a methodology question): the copilot
   answers from the wiki and notes corpus, every sentence cited
   (`pages/ecl-engine.md#Headline numbers`, `notes §9.2 p10`, …), no LLM
   invention.
6. **"Should I buy Tesla stock this quarter?"** → the router classifies it
   out-of-scope and the copilot **refuses**, naming the five validated
   routes. Watch the agent-trace panel: `router → refusal`, no tool call, no
   invented number.

## Key exhibits

| Exhibit | Where |
|---|---|
| Credit-cycle Z path (GFC trough 2008Q1, PIT vs TTC PD) | `outputs/vasicek/credit_cycle.png`, `z_path.csv` |
| Scenario ECL bars + the Jensen gap | `outputs/scenario_ecl/scenario_ecl_bars.png`, `jensen_gap.png` |
| Hazard fit stats (AUC, seasoning hump, LTV×UER double trigger) | `outputs/hazard/fit_stats.md` |
| Champion–challenger scorecard (MLP vs cloglog) | `outputs/challenger/scorecard.md` |
| Vasicek calibration report (ρ, anchor identity, round-trip) | `outputs/vasicek/vasicek_report.md` |
| E2E container traces (shock + refusal) | `outputs/demo/e2e_trace.json`, `e2e_refusal.json` |
| Gate reports (frozen-engine tripwire, suite counts) | `outputs/gate/` |

## Numbers that matter (honest edition)

* **Discrimination:** default hazard AUC **0.748 train / 0.661 OOT**
  (2010Q2–2015Q1 held out, fit-on-train applied read-only). An MLP challenger
  with the same information set wins in-train (+0.016) and **loses OOT
  (−0.019)** — the champion's age spline and governed macro terms carry the
  extrapolation; the challenger stays challenger.
* **Asset correlation:** ρ = **0.0227** calibrated à la Belkin (Var(Z)=1) with
  a composition-adjusted TTC anchor — deliberately far below the Basel 0.15
  convention, with the mechanism (collateral cycle absorbed by the anchor)
  demonstrated via an orig-LTV variant at ρ = 0.0633.
* **The Jensen gap, decomposed:** probability-weighted allowance $34.0m vs
  $32.9m at the averaged macro path — **1.035x** on the reported (stage-gated)
  number, but only **1.006x** on raw lifetime ECL: most of the reported gap is
  stage composition, not pure convexity. Measuring ECL on one averaged path
  understates loss — the analytical case for IFRS 9 ¶5.5.17's
  probability-weighted range.
* **Scenario ECL (t=60 book, 7,849 loans, $1.67bn):** up $27.7m / base $30.5m /
  severe $47.6m; weighted $34.0m = 2.03% coverage.
* **Test discipline:** **422 tests** (133 golden fixtures pinning engine
  values, 187 through Day 2, 91 scenario-layer, 103 agent/API, 41 stretch:
  Tier-3 doc retrieval + MCP adapter), plus a fingerprint tripwire proving
  the five frozen engine modules are byte-identical to the Day-2 gate at
  every subsequent gate.
* **Agent latency:** engine warm-up 10–25 s once (joblib cache), then 3–12 s
  per question end-to-end including the LLM round trip.

## Repository map

```
engine/        frozen five + vasicek/scenarios/satellite     agent/   tools + LangGraph + tier3 + mcp
app/api/       FastAPI service        app/ui/    Preact/ECharts SPA
analysis/      exhibit scripts        tests/     422 tests (133 golden fixtures)
wiki/          model-development wiki (19 pages)  knowledge/  indexed IFRS9 notes corpus
data/          panel pipeline + DFAST ingest (raw data gitignored)
outputs/       exhibits, reports, model cache, audit logs, gate reports
Dockerfile     multi-stage build (node UI → python:3.13-slim, port 7860)
```
