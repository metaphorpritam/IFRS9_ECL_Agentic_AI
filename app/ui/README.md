# IFRS 9 ECL Copilot — UI (App v2)

Preact + Vite + ECharts. Hand-written scaffold, no CSS framework, no router
library (a hash-based tab switcher in `src/app.jsx`), no state-management
library. Data-viz-validated palette (categorical/status/diverging hues,
light + dark surfaces) in `src/palette.js` / `src/styles.css`.

North star: this app is a **consultant's deliverable + client's lab** — the
consultant pre-generated the analysis; the client browses specifics, runs
scenario experiments, and the LLM agent gives data-grounded interpretation,
never invented numbers.

## Run

```bash
cd app/ui
npm install
npm run dev     # dev server, /api proxied to http://localhost:7860
npm run build   # production bundle -> dist/
```

## Tabs

| Tab | File | Endpoint(s) |
|---|---|---|
| Executive Overview | `src/tabs/ExecutiveTab.jsx` | `GET /api/ecl/summary`, `/api/ecl/waterfall`, `/api/exhibits/credit_cycle` |
| The Model | `src/tabs/ModelTab.jsx` | `GET /api/model/{coefficients,variable_dictionary,lgd}`, `/api/exhibits/list` |
| Scenario Lab | `src/tabs/ScenarioLabTab.jsx` | `POST /api/tools/{shock_macro,reweight_scenarios,rerun_ecl,decompose_waterfall}`, `POST /api/agent/interpret` |
| Policy | `src/tabs/PolicyTab.jsx` | `GET /api/policy/{staging_sensitivity,weights_table}` |
| Copilot | `src/tabs/CopilotTab.jsx` | `POST /api/agent/ask`, `GET /api/agent/stream` (SSE) |

A collapsed mini-chat dock (`src/components/MiniChatDock.jsx`, reusing
`ChatPanel`) floats on tabs 1-4; Copilot has the full-page chat instead.

The full request/response **CONTRACT** (exact JSON shapes the FastAPI service
implements) is `docs/api_contract.md` — `src/api.js` is coded only against
that file, never against invented shapes.

Governing rule: the UI (like the LLM) does no business arithmetic — it only
parameterises tool calls and formats engine numbers for display. Refusals
from the agent (`route === "refusal"`) render in the amber "outside
validated scope" style by design. Auto-interpretation
(`Interpretation.jsx`) shows an "AI interpretation" vs "Engine summary"
badge depending on the contract's `grounded` bool — a fallback to the
engine's own headline, never a blank or raw-error state.
