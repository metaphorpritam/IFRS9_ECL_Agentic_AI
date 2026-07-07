/**
 * API client — the single place the endpoint CONTRACT lives.
 * All paths are relative (/api/...) so the Vite dev proxy (-> :7860) and the
 * single-origin Docker deployment both work unchanged.
 *
 * Contract (FastAPI service implements these shapes):
 *
 * GET /api/ecl/summary
 *   { "allowance_m": 34.0, "coverage": 0.0203, "jensen_ratio": 1.035,
 *     "weights": {"up": 0.25, "base": 0.5, "severe": 0.25},
 *     "scenarios": [{"name": "up", "allowance_m": 27.7, "coverage": 0.0165}, ...] }
 *
 * GET /api/ecl/waterfall
 *   { "start": {"label": "Baseline allowance", "value_m": 34.0},
 *     "steps": [{"label": "Scenario reweight", "delta_m": 1.8},
 *               {"label": "UER shock +2pp",    "delta_m": 4.6}, ...],
 *     "end":   {"label": "Reported allowance", "value_m": 40.4} }
 *
 * GET /api/exhibits/credit_cycle
 *   { "calendar": ["2000Q2", ...],
 *     "ttc": [...], "pit": [...], "hybrid": [...], "observed": [...] }   (observed optional)
 *
 * POST /api/tools/reweight_scenarios   body {"weights": {"up": w, "base": w, "severe": w}}
 * POST /api/tools/shock_macro          body {"uer_shock_pp": 2.0}
 *   -> 200 on success; UI then refetches /api/ecl/summary and /api/ecl/waterfall.
 *
 * POST /api/agent/ask                  body {"question": "..."}
 *   { "answer": "...", "refusal": false,
 *     "tool_calls": [{"tool": "reweight_scenarios", "args": {...}}] }
 *   Refusals come back with "refusal": true and an "outside my validated scope" answer.
 *
 * GET /api/agent/stream  (SSE)
 *   default `message` events, data = JSON:
 *   {"type": "router" | "tool_call" | "tool_result" | "narration" | "error",
 *    "text"?: "...", "tool"?: "...", "args"?: {...}, "result"?: {...}}
 */

const json = async (res) => {
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
  return res.json();
};

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json);

export const getSummary = () => fetch('/api/ecl/summary').then(json);
export const getWaterfall = () => fetch('/api/ecl/waterfall').then(json);
export const getCreditCycle = () => fetch('/api/exhibits/credit_cycle').then(json);

export const reweightScenarios = (weights) =>
  post('/api/tools/reweight_scenarios', { weights });

export const shockMacro = (uerShockPp) =>
  post('/api/tools/shock_macro', { uer_shock_pp: uerShockPp });

export const askAgent = (question) => post('/api/agent/ask', { question });

export const AGENT_STREAM_URL = '/api/agent/stream';
