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
  - ../agent/graph.py
  - ../agent/tier3_retrieval.py
  - ../agent/mcp_server.py
  - ../app/api/main.py
  - ../scripts/demo_agent.py
  - ../tests/test_tools.py
  - ../tests/test_router.py
  - ../tests/test_api.py
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

## Known caveats

Narrations may quote unrounded floats (verbatim-number check is strict); single-worker SSE demo
limitation documented; torch pruned from the Docker image (challenger-only, would add ~5GB);
HF cold start may refit (~50s) if the cache fingerprint mismatches — observed warm-up 24.9s.
