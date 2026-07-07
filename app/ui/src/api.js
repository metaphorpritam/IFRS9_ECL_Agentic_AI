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
 * POST /api/tools/reweight_scenarios   body {"w_up": w, "w_base": w, "w_down": w}
 * POST /api/tools/shock_macro          body {"var": "UER", "shock": 2.0, "shape": "parallel"}
 *   (canonical shapes = agent/tools_tier1.py pydantic models, extra="forbid")
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

// Adapters: map the API's canonical payloads onto the shapes the components
// consume (single seam — components stay contract-agnostic).
export const getSummary = () =>
  fetch('/api/ecl/summary').then(json).then((d) => ({
    ...d,
    allowance_m: d.weighted_allowance / 1e6,
  }));

// Shared shape for both waterfalls: the historical movement decomposition and
// a tool response's waterfall_vs_baseline (identical row schema).
export const adaptWaterfallRows = (rows, startLabel, endLabel) => {
  const level = (name) => rows.find((c) => c.component === name);
  return {
    start: { label: startLabel, value_m: (level('opening')?.amount ?? 0) / 1e6 },
    steps: rows
      .filter((c) => c.component !== 'opening' && c.component !== 'closing')
      .map((c) => ({
        label: c.component.replace(/_/g, ' '),
        delta_m: c.amount / 1e6,
      })),
    end: { label: endLabel, value_m: (level('closing')?.amount ?? 0) / 1e6 },
  };
};

export const getWaterfall = () =>
  fetch('/api/ecl/waterfall').then(json).then((d) => ({
    ...adaptWaterfallRows(d.components, 'Opening allowance', 'Closing allowance'),
    period_t0: d.period_t0,
    period_t1: d.period_t1,
  }));

export const getCreditCycle = () =>
  fetch('/api/exhibits/credit_cycle').then(json).then((d) => ({
    calendar: d.points.map((p) => p.calendar),
    ttc: d.points.map((p) => p.ttc_pd * 100),
    pit: d.points.map((p) => p.pit_pd * 100),
    observed: d.points.map((p) => p.observed_dr * 100),
  }));

export const reweightScenarios = ({ up, base, severe }) =>
  post('/api/tools/reweight_scenarios', {
    w_up: up,
    w_base: base,
    w_down: severe,
  });

export const shockMacro = (uerShockPp) =>
  post('/api/tools/shock_macro', {
    var: 'UER',
    shock: uerShockPp,
    shape: 'parallel',
  });

export const askAgent = (question) => post('/api/agent/ask', { question });

export const AGENT_STREAM_URL = '/api/agent/stream';
