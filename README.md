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
the tool's JSON. Questions outside the four validated tool families get an
explicit refusal ("outside my validated scope"). The refusal is a governance
feature, demonstrated on purpose.

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
```

**The governing rule** (enforced in review and in code): the LLM never computes.
Malformed tool arguments are rejected by pydantic before any engine code runs;
narrations that invent numbers are replaced by the engine's own deterministic
headline; every successful tool call is one line in a replayable JSONL audit
trail with a `tc-<seq>` reference quoted in the answer.

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
uv run --no-sync pytest tests/ -q          # 381 passed
```

## Five-question demo script

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
5. **"Should I buy Tesla stock this quarter?"** → the router classifies it
   out-of-scope and the copilot **refuses**, naming the four validated tool
   families. Watch the agent-trace panel: `router → refusal`, no tool call, no
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
* **Test discipline:** **381 tests** (133 golden fixtures pinning engine
  values, 187 through Day 2, 91 scenario-layer, 103 agent/API), plus a
  fingerprint tripwire proving the five frozen engine modules are
  byte-identical to the Day-2 gate at every subsequent gate.
* **Agent latency:** engine warm-up 10–25 s once (joblib cache), then 3–12 s
  per question end-to-end including the LLM round trip.

## Repository map

```
engine/        frozen five + vasicek/scenarios/satellite     agent/   tools + LangGraph
app/api/       FastAPI service        app/ui/    Preact/ECharts SPA
analysis/      exhibit scripts        tests/     381 tests (133 golden fixtures)
data/          panel pipeline + DFAST ingest (raw data gitignored)
outputs/       exhibits, reports, model cache, audit logs, gate reports
Dockerfile     multi-stage build (node UI → python:3.13-slim, port 7860)
```
