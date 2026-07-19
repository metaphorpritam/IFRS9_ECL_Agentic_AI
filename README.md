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
below) and a 6th route (Tier 2, below) where the LLM writes analysis code
that a locked-down sandbox actually executes, held to the same rule.
Questions outside those six validated routes get an explicit refusal
("outside my validated scope"). The refusal is a governance feature,
demonstrated on purpose.

## The honest backtest

The exhibit that anchors the whole real-data study: refit the champion
hazard spec at `2007-12`, using **only** the data and macro vintages that
actually existed then, project 36 months forward with macro frozen at
`2007-12` levels, and compare to what actually happened. Realized 36-month
cumulative D90: **8.750%**. Predicted: **0.928%**. **9.42× underprediction —
the model completely misses the GFC**, because a model fit on pre-2008 data
with macro frozen at pre-crisis levels cannot see a crisis it has never been
shown. Feed the same spec the *actual* 2008–2011 macro path instead (the
ceiling a perfect scenario overlay could reach) and the miss shrinks to
**1.90×** — still under, because the crisis's severity was itself outside
the training regime. That gap between a naive frozen-macro extrapolation and
a hindsight-perfect overlay is the analytical case, in one number, for IFRS 9
¶5.5.17's forward-looking, probability-weighted scenario requirement — a
point-in-time hazard alone is not enough. The same backtest, run at
`2019-12`, shows the mirror failure: fed the real April-2020 unemployment
print (+10.6pp in one month, ~20 standard deviations outside the training
support), the linear predictor saturates and *overshoots* to 71.5% predicted
vs 4.601% realized (0.06×) — a reminder that even a perfect macro overlay
cannot rescue a hazard whose functional form was never identified in the
regime the scenario visits. See `outputs/freddie/backtest/backtest_report.md`
and Exhibit 5 in the [Model Development Document](outputs/mdd/MDD.md) (also
served live at `/static/mdd/MDD.html` on the Space) for the full five-date
table and the connective finding with the LGD module (the realized D90 spike
in 2020 did **not** turn into a matching loss spike — forbearance resolved it
as cures, at a 97.9% modern-era OOT cure rate).

## Real data at scale: the Freddie Mac SFLLD study

Everything above (the frozen engine, App v2, the original 509-test gate) is
proven on a synthetic, DCR-style panel — deliberately, so the engine's
correctness could be pinned down against known-good fixtures first before
touching real data. Rung 3 asks the harder
question: does the same champion hazard spec hold up on the **real** Freddie
Mac Single-Family Loan-Level Dataset (SFLLD)? `freddie/` (read-only,
frozen like the engine once gated) reruns the identical hazard/LGD spec on
real loan-level history, real dates, real states, and real realized losses,
adds an LSTM path-dependence challenger, and closes the loop with the
ALFRED-vintage backtest above. The **Real Data** tab in the app surfaces all
of it live (`/api/freddie/summary`, `/hazard`, `/backtest`, `/exhibits`).

* **Scale**: 837,500 loans / 39,522,565 loan-months across 17 vintages
  (2005–2010, 2014–2016, 2018–2025 — 2011–2013/2017 are a documented,
  never-downloaded coverage gap), vs the DCR panel's 621,736 loan-quarters /
  49,974 loans.
* **Discrimination, DCR vs SFLLD** (same cloglog spec, same train/OOT
  discipline):

  | Panel | Train AUC | OOT AUC |
  |---|---:|---:|
  | DCR (synthetic) | 0.748 | 0.661 |
  | SFLLD (real) | **0.8536** | **0.6847** |

  The real panel's AUC is *higher* on both cuts — more genuine signal in real
  loan-level history than the synthetic generator injected — while the
  train→OOT degradation pattern (a model that discriminates well in-sample
  and decays out-of-time) replicates, evidence the DCR panel's stress
  behaviour wasn't a synthetic-data artifact.
* **COVID regime verdict — EXCLUDE**: the author's first-pass recommendation
  (an additive COVID dummy over 2020-04..2021-09) was **overturned on
  review** — the additive variant flips the sign of `delta_uer_lag1`, an
  economically nonsensical outcome no downstream user should inherit
  silently. The adopted treatment excludes the window entirely from
  structural/scenario use; only the exclude variant preserves
  correctly-signed macro coefficients across all three candidates tested.
* **LSTM path-dependence decomposition**: an LSTM challenger scores OOT AUC
  **0.9925** vs the champion hazard's **0.6847** on the identical split — a
  huge gap that means nothing on its own until it's decomposed. Split by
  prior-24-month delinquency history: on **clean-history loans** the LSTM is
  essentially at parity with the champion (**0.529 vs 0.539**, both
  near-random — there's no path to learn from when there's no history).
  On loans with a **prior delinquency spell**, the LSTM pulls dramatically
  ahead (**0.957 vs 0.570**). All of the LSTM's apparent edge is the
  champion's current-state-only view failing to use delinquency history it
  never sees — not a generically better model, a specific, explainable blind
  spot in the champion spec.

Every one of these numbers is quoted verbatim from `outputs/freddie/**`'s
reports (`hazard_report.md`, `lgd_report.md`, `backtest_report.md`,
`lstm_report.md`, `gate_phaseB.md`) — the API layer parses, never
recomputes, and the same discipline (a mechanical verbatim-number check on
every agent narration) applies to this tab as to the rest of the app. Full
methodology, every declared simplification, and the two found-and-fixed bugs
from this phase (a realized-outcome timing bug in the backtest, a
zero-fill bug in the LGD aggregate) are in the
[Model Development Document](outputs/mdd/MDD.md) — also served live at
`/static/mdd/MDD.html` on the Space.

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
        │  + a 6th route: the LLM WRITES the analysis, the sandbox RUNS it
        ▼
┌────────────────────────── TIER-2 SANDBOX (App v2, +87 tests) ────────────────┐
│ agent/tools_tier2.py      analyze_data — code-writer LLM emits pandas over   │
│                           the frozen t=60 scored book; AST-validated, then   │
│                           EXECUTED in a locked-down subprocess (no imports,  │
│                           no file/network I/O, RLIMIT_AS, timeout); the      │
│                           EXECUTED result — never the LLM's prose — is what  │
│                           the narrator is allowed to quote                   │
└──────────────────────────────────────────────────────────────────────────────┘
        │  App v2: same engine + same agent, a consultant's-deliverable UI
        ▼
┌────────────────────────── APP v2 — 6 TABS (Day 5+) ───────────────────────────┐
│ Executive Overview │ The Model │ Scenario Lab │ Policy │ Real Data │ Copilot │
│ every tab pairs a pre-generated exhibit with an agent-grounded              │
│ interpretation; a mini-chat dock (same copilot) rides along on every tab    │
└──────────────────────────────────────────────────────────────────────────────┘
        │  Rung 3: the same champion spec, refit on REAL loan-level data
        ▼
┌────────────────────────── REAL DATA — SFLLD (Rung 3) ─────────────────────────┐
│ freddie/    read-only, FROZEN like the engine once gated — Freddie Mac       │
│             SFLLD hazard/LGD refit + ALFRED-vintage backtest + LSTM          │
│             challenger, 837.5k real loans / 39.5M loan-months, 17 vintages   │
│ app/api/main.py  /api/freddie/{summary,hazard,backtest,exhibits} parse       │
│                  outputs/freddie/**'s reports/CSVs/JSON — never recompute    │
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
model-development wiki (`wiki/`, 20 pages) and the indexed IFRS 9 credit-risk
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

## Tier 2: long-tail analysis — the LLM writes the code, the sandbox runs it

The four Tier-1 tools cover the shocks a risk team asks for every cycle; they
don't cover *"what is the average updated LTV of stage 2 loans?"* or any of
the thousand similar one-off cuts of the book. Tier 2 (`analyze_data`,
`agent/tools_tier2.py`) answers those **without ever letting the LLM do the
arithmetic**: the model is asked to write a short pandas expression against
the frozen t=60 scored book; that code — never the model's prose — is what
actually runs, and the number shown to the user is the sandbox's own output.

The boundary is enforced twice, independently:

* **Before execution — an AST allow-list.** The generated code is parsed
  (never `eval`'d blind) and rejected before it ever reaches a process if it
  imports anything, touches a forbidden module/attribute family (`os`,
  `sys`, `subprocess`, `socket`, `ctypes`, dunder/frame/generator internals,
  raw file I/O), or hides a reach-around inside `.format()`/`.eval()`/
  `.query()` string arguments. One repair attempt is allowed on a rejected
  or erroring first try; two strikes and the tool answers with an explicit
  refusal rather than executing anything uncertain.
* **During execution — a hardened child process**, independent of the AST
  layer so a gap in one is still caught by the other: no network, no file
  writes, no reads outside Python's own import path, a memory ceiling sized
  off the process's real footprint, and a wall-clock timeout. Environment
  secrets are scrubbed before the user's code ever runs.

The generated code is always shown in the agent trace for audit — nothing
executes off-screen. `tests/test_tier2.py` (adversarially reviewed) exercises
the sandbox with real attack payloads (`os.system`, `__import__`, `.format()`
attribute reach-arounds, generator/frame introspection, oversized
allocations) as well as the happy path.

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
uv run --no-sync pytest tests/ -q          # 664 passed
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

## App v2: a consultant's deliverable + a client's lab

Day 4's dashboard was a single scrolling page; it worked, but it read like a
tool demo, not something a credit-risk consultant would actually hand a
client. App v2 is a design pass built around one governing story: **the
consultant has already run the analysis — the client browses it, experiments
with it, and asks the copilot to interpret it**, never the other way around
(the client never sees a raw number the model made up). Six tabs, one
FastAPI backend, one LangGraph agent underneath all of them:

| Tab | What it is |
|---|---|
| **Executive Overview** | The headline stats, the scenario table, the credit-cycle exhibit — the one-page version a committee reads first. |
| **The Model** | The hazard-ratio families and their fit stats, the variable dictionary, the LGD calibration exhibits — parsed straight from the consultant's own markdown reports, with a plain-language "story" for every covariate. |
| **Scenario Lab** | Run the four Tier-1 tools interactively (shock a macro variable, reweight the scenarios, rerun a segment, decompose a waterfall) and get an **automatic, grounded interpretation** under the result the moment it lands — no need to ask the copilot a follow-up question. |
| **Policy** | Every governance exhibit (the SICR-threshold sensitivity curve, the scenario-weights table) paired explicitly with the decision it's meant to inform. |
| **Real Data** | The Freddie Mac SFLLD study (Rung 3): panel scale, DCR-vs-SFLLD hazard AUC, the COVID-regime verdict, the ALFRED-vintage honest backtest, and the LSTM path-dependence decomposition — see [Real data at scale](#real-data-at-scale-the-freddie-mac-sflld-study) above. |
| **Copilot** | The agent front and centre — all six routes (four Tier-1 tools, Tier-2 `analyze_data`, Tier-3 `query_model_docs`), the live trace, the refusal path. |

A **mini-chat dock** rides along on every tab, so the copilot is never more
than one click away from whatever exhibit is on screen. The UI/API seam is
contract-first this time: `docs/api_contract.md` is the single source of
truth for every request/response shape (including the SSE trace-event
schema), exercised field-by-field by `tests/test_contract.py` — the seam
that broke silently in Day 4 now has a test.

## UI v3: a design pass judged against three directions

App v2 shipped the right information architecture; the operator judged its
look twice underwhelming — "something a consultant would proudly send a
client" was the bar, not yet cleared. UI v3 answers that with a real design
competition, not a single restyle: three full candidate directions were
built and scored on the same five criteria (north-star fit, information
hierarchy, data-ink discipline, dark/light parity, implementability) —
**editorial** (numbered exhibit apparatus, source footers), **fintech** (a
modern risk-platform look: dense KPI rows, dark/light parity), and
**terminal** (a grounding-status vocabulary — `GROUNDED` / `THINKING` / `OUT
OF SCOPE` — plus adopted-row treatment). **fintech won** (42/50 vs 39 and
37), and the losers weren't discarded: five grafts were merged in from the
runners-up (the exhibit kickers and figure-recap explain-prefix from
editorial; the grounding vocabulary, adopted-row treatment, and dock-scroll
reserve from terminal). The merged decision lives in
`outputs/design/FINAL_SPEC.md`; the three candidates are archived under
`outputs/design/{editorial,fintech,terminal}/`.

The same pass fixed two defects the judge caught on the way in:

* **A real bug, not a style note**: `WaterfallChart.jsx`'s default
  (historical) view was rendering empty. Historical mode fed the raw `GET
  /api/ecl/waterfall` payload (`{components, period_t0, ...}`) straight to
  `buildWaterfallOption`, which expects `{start, steps, end}` — the same
  `adaptWaterfallRows()` adapter the tool-result modes already used was
  missing from this one path. Fixed, and now guarded by a build-time
  regression script (`npm run verify:waterfall`, wired into `prebuild`) that
  feeds a captured payload through the adapter and asserts the option builder
  produces non-empty series — and separately proves the *un-adapted* payload
  would fail, so the check can't quietly stop testing anything.
* **A failed color-contrast floor**: the shipped categorical palette order
  put `#eb6834`/`#e87ba4` adjacent at ΔE 12.9, under the validator's
  normal-vision floor of 15. `app/ui/src/palette.js` now uses the
  judge-verified order (blue, green, magenta, yellow, aqua, orange, violet,
  red) in both themes.

On top of the winning direction, this pass also: made the default Executive
Overview waterfall show the **latest quarter** (t0=59→t1=60) rather than an
arbitrary historical window, with the Scenario Lab kept as the
user-driven drill-down; moved the AI-explain answer strip out of the panel
header (where it had been squeezed) to render **inline under the panel/tile
body**, as a shared `useExplain()` hook + `ExplainStrip`/`SparkIcon` so the
panel, tile, selection-popover, and Copilot-tab surfaces all render the same
`THINKING` / `GROUNDED` (with citation chip) / `OUT OF SCOPE` states from one
place; and added the small chrome the judge's grafts called for — hover/focus
tooltips on icon-buttons, a loading ring on the explain button, status dots on
the scenario table, and a tinted delta pill for the vs-adopted comparison.
Net effect on the shipped bundle: 78.91 kB → 77.92 kB (the shared hook
replaced three near-duplicate explain implementations).

## Eight-question demo script

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
6. **"What is the average updated LTV of stage 2 loans?"** → routes to
   `analyze_data` (Tier 2): the code-writer LLM emits one line of pandas
   (`book[book['stage']==2]['updated_ltv'].mean()`), the sandbox executes it
   against the frozen t=60 book, and the generated code is visible in the
   trace — the number in the answer is the sandbox's own output, never the
   model's arithmetic.
7. **Scenario Lab tab: shock UER +2pp and watch the interpretation appear
   under the waterfall chart with no extra question asked** — the same
   narrator + verbatim-number check the Copilot tab uses, wired to
   `POST /api/agent/interpret` and fired automatically the moment a
   Scenario Lab action returns.
8. **"Should I buy Tesla stock this quarter?"** → the router classifies it
   out-of-scope and the copilot **refuses**, naming all six validated
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
| App v2 / Tier-2 E2E traces (scenario+interpret, analyze_data, citation, refusal) | `outputs/demo/appv2_e2e.json`, `shadow_*.json` |
| Gate reports (frozen-engine tripwire, suite counts) | `outputs/gate/` |
| SFLLD vintage curves, roll-rate heatmaps (GFC/calm/COVID), state heterogeneity | `outputs/freddie/eda/` |
| ALFRED-vintage backtest panel (the 9.42x GFC miss, all five reporting dates) | `outputs/freddie/backtest/predicted_vs_realized_200712.png`, `backtest_report.md` |
| SFLLD hazard coefficients, calibration by year, COVID-regime comparison | `outputs/freddie/hazard/` |
| SFLLD severity-by-year, cure-rate-by-era | `outputs/freddie/lgd/` |
| LSTM lift-split (prior-delinquency-spell decomposition) | `outputs/freddie/lstm/lift_split.png`, `lstm_report.md` |
| Model Development Document (compiled from the wiki + every gate report) | `outputs/mdd/MDD.md`, `MDD.html` (live at `/static/mdd/MDD.html`) |

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
* **Test discipline:** **664 tests** (133 golden fixtures pinning engine
  values, 187 through Day 2, 91 scenario-layer, 103 agent/API, 41 stretch:
  Tier-3 doc retrieval + MCP adapter, 87 App v2: Tier-2 sandbox + the
  UI/API contract, 77 Rung 3: SFLLD hazard/LGD/backtest/LSTM, 5 the Real
  Data tab's UI/API contract), plus a fingerprint tripwire proving the five
  frozen engine modules are byte-identical to the Day-2 gate at every
  subsequent gate — 582/582 through Rung 3 Phase A, 659/659 through Phase B,
  **664/664 current**.
* **Agent latency:** engine warm-up 10–25 s once (joblib cache), then 3–12 s
  per question end-to-end including the LLM round trip.

## Repository map

```
engine/        frozen five + vasicek/scenarios/satellite     agent/   tools_tier1/tier2 + graph + tier3 + mcp
app/api/       FastAPI service (contract in docs/api_contract.md)
app/ui/        Preact/ECharts SPA — app/ui/src/tabs/ (6 App v2 tabs) + shared components
analysis/      exhibit scripts        tests/     664 tests (133 golden fixtures)
freddie/       Rung 3: SFLLD hazard/LGD/backtest/LSTM refit (read-only, frozen like engine/)
wiki/          model-development wiki (20 pages)  knowledge/  indexed IFRS9 notes corpus
docs/          docs/api_contract.md — UI/API contract, single source of truth
data/          panel pipeline + DFAST ingest (raw data gitignored)
outputs/       exhibits, reports, model cache, audit logs, gate reports, mdd/ (MDD.md/.html)
Dockerfile     multi-stage build (node UI → python:3.13-slim, port 7860)
```
