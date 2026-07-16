---
title: Agent Layer
type: module
status: active
aliases: [copilot, tier-1 tools, langgraph router, the app]
tags: [agent, day4, deploy]
sources:
  - ../MASTER_PLAN.md
  - ../outputs/gate/day4_gate_report.md
code:
  - ../agent/__init__.py
  - ../agent/tools_tier1.py
  - ../agent/tools_tier2.py
  - ../agent/graph.py
  - ../agent/tier3_retrieval.py
  - ../agent/mcp_server.py
  - ../app/api/main.py
  - ../scripts/demo_agent.py
  - ../tests/test_tools.py
  - ../tests/test_router.py
  - ../tests/test_api.py
  - ../tests/test_contract.py
  - ../tests/test_tier2.py
  - ../tests/test_tier3.py
  - ../tests/test_mcp.py
links:
  uses: [ECL Engine, Scenario Layer, Staging Model]
  implements: [Master Plan]
---

# Agent Layer

Day-4 build, **deployed public**: https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot
(Docker SDK, port 7860, OPENROUTER_API_KEY as Space secret only; user-authorized public
2026-07-05). Suite 381/381; frozen five NONE; agent-layer review verdict *fixed* (caught a pytest
suite-deadlocking SSE test + the NaN-422 FastAPI edge).

## Architecture

LangGraph StateGraph: router (Gemma 4 31B via OpenRouter, temp 0, fallback DeepSeek V4 Flash) →
one of 4 pydantic-validated Tier-1 tools → narrator (numbers verbatim from tool result, post-check
+ deterministic template fallback) → END; validation failure or out-of-scope → **refusal node**
(names the supported families). Every run appends to `outputs/agent_log/*.jsonl` — the replayable
audit trail. **The LLM never does arithmetic** — review-verified with a poisoned-narration test.

## Tools (agent/tools_tier1.py)

`shock_macro` / `reweight_scenarios` / `rerun_ecl` / `decompose_waterfall`. Key numbers:
UER +2pp → allowance $30.5m → $31.7m (+4.1%); reweight identity reproduces $34.0m / Jensen 1.035×;
waterfall matches the published Day-2 exhibit exactly; warm start 9s (joblib cache slimmed
777MB → 88.7MB, warm-vs-fresh bit-identical).

## THE COHERENT-SHOCK CONVENTION (load-bearing)

The sign-governed satellite is Z = f(hpi_growth_lag1, gdp_growth_lag2) — no unemployment term — so
a univariate UER-only shock cannot reach Z. `shock_macro` therefore applies every shock as a
co-moving move along the **DFAST severe-minus-base direction** (loadings normalised to the named
variable, applied per-concept deltas returned in `applied_peak_deltas_pp`). Without this the
flagship demo question would return delta = 0.

## App v2 additions (Day 5+)

The API grew 7 read-only exhibit/model endpoints (`/api/model/*`,
`/api/policy/*`, `/api/exhibits/list`) parsing the consultant's markdown
under `outputs/` into JSON, a `/static/exhibits` mount, and
`POST /api/agent/interpret` — Scenario Lab auto-interpretation that REUSES
graph.py's narrator + verbatim-number/citation checks (never duplicated;
falls back to the tool's own headline when the check fails). The UI/API
seam is contract-first: `docs/api_contract.md` is the single source of
truth, exercised field-by-field by `tests/test_contract.py` (SSE trace
events are `{"node": ...}` dicts — documented there). Tier-2
`analyze_data` (agent/tools_tier2.py): the LLM writes pandas, the sandbox
EXECUTES it (AST-validated, one repair attempt, else refusal); tests in
`tests/test_tier2.py`. Suite 481/481 green at review time.

## UI v3 AI-explain prefixes (contract §5)

Two UI-side wire-text conventions on top of the EXISTING `POST
/api/agent/ask` (zero new endpoints, FINAL_SPEC §7.5): the panel/tile
explain prefix `[explain:<panel_id> <params>] <Exhibit label> — <title>:
<code-generated figure recap> What should I take from this?` and the
selection-explain prefix `Explain, in the context of the <tab> tab:
"<selection, ≤300 chars>"`. Single source of the wire text:
`app/ui/src/api.js` (`explainPanelQuestion` / `explainSelectionQuestion`);
documented in `docs/api_contract.md` §5 and exercised by 4
`tests/test_contract.py` router-wiring tests (both prefixes × docs-route
and clean-refusal, LLM seams mocked, graph wiring real — never a crash,
never an unrequested Tier-1 call).

## Known caveats

Narrations may quote unrounded floats (verbatim-number check is strict); single-worker SSE demo
limitation documented; torch pruned from the Docker image (challenger-only, would add ~5GB);
HF cold start may refit (~50s) if the cache fingerprint mismatches — observed warm-up 24.9s.
