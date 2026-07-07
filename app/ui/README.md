# IFRS 9 ECL Copilot — UI

Preact + Vite + ECharts dashboard. Hand-written scaffold, no CSS framework, no
router/state libs. Textbook palette from `analysis/mpl_style.py`.

## Run

```bash
cd app/ui
npm install
npm run dev     # dev server, /api proxied to http://localhost:7860
npm run build   # production bundle -> dist/
```

## Components (scope-capped at 4 + header + static exhibit)

| Component | Endpoint(s) |
|---|---|
| Header stat tiles | `GET /api/ecl/summary` |
| `ScenarioControls` | `POST /api/tools/reweight_scenarios`, `POST /api/tools/shock_macro` |
| `WaterfallChart` | `GET /api/ecl/waterfall` |
| `CreditCycleChart` (static exhibit) | `GET /api/exhibits/credit_cycle` |
| `AgentTrace` | `GET /api/agent/stream` (SSE) |
| `ChatPanel` | `POST /api/agent/ask` |

The full request/response CONTRACT (exact JSON shapes the FastAPI service must
implement) is documented in `src/api.js`.

Governing rule: the UI (like the LLM) does no business arithmetic — it only
parameterises tool calls and formats engine numbers for display. Refusals from
the agent (`"refusal": true`) render in the amber "outside validated scope"
style by design.
