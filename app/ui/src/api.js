/**
 * API client — coded ONLY against docs/api_contract.md (the seam contract).
 * Every function below returns the exact JSON the contract documents; the
 * only "adapters" here reshape a contract payload into a chart-friendly
 * array (e.g. waterfall rows -> {start, steps, end}), never invent a field.
 * All money fields are raw USD floats; components divide by 1e6 themselves.
 */

const json = async (res) => {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`HTTP ${res.status}: ${detail}`);
  }
  return res.json();
};

const get = (url) => fetch(url).then(json);

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(json);

// --------------------------------------------------------------- 1. engine

export const getHealth = () => get('/api/health');

export const getSummary = () => get('/api/ecl/summary');

export const getWaterfall = (t0 = 20, t1 = 40) =>
  get(`/api/ecl/waterfall?t0=${t0}&t1=${t1}`);

export const getCreditCycle = () => get('/api/exhibits/credit_cycle');

/** Shared row shape for /api/ecl/waterfall and a tool's waterfall_vs_baseline
 * (identical 6-row schema: opening, stage_migration, remeasurement,
 * derecognitions, new_loans, closing). */
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

// -------------------------------------------------------------- tier-1 tools

export const shockMacro = (v, shock, shape = 'parallel') =>
  post('/api/tools/shock_macro', { var: v, shock, shape });

export const reweightScenarios = (w_up, w_base, w_down) =>
  post('/api/tools/reweight_scenarios', { w_up, w_base, w_down });

export const rerunEcl = (segment = 'all') =>
  post('/api/tools/rerun_ecl', { segment });

export const decomposeWaterfall = (t0, t1) =>
  post('/api/tools/decompose_waterfall', { t0, t1 });

export const TOOL_FN = {
  shock_macro: shockMacro,
  reweight_scenarios: reweightScenarios,
  rerun_ecl: rerunEcl,
  decompose_waterfall: decomposeWaterfall,
};

// -------------------------------------------------------------------- agent

export const askAgent = (question) => post('/api/agent/ask', { question });

// ---------------------------------------------------- explain-prefix conventions
// docs/api_contract.md §"AI-explain question prefixes" — both conventions
// REUSE POST /api/agent/ask (never a bespoke endpoint) so every explain
// click passes the same tools/Tier-2/Tier-3/refusal governance
// (FINAL_SPEC.md §7.5). Keep these two builders as the single source of the
// exact wire text so the UI and the contract-test stay byte-identical.

/** Panel/tile explain convention (FINAL_SPEC §7.5, graft 4): a bracketed
 * routing tag with live params, an Exhibit label, and a CODE-GENERATED recap
 * of the exact figures the panel/tile is rendering right now (built from the
 * same payload that drew it — never free text). */
export const explainPanelQuestion = ({ panelId, params = {}, exhibitLabel, title, recap }) => {
  const paramStr = Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join(' ');
  const tag = `[explain:${panelId}${paramStr ? ` ${paramStr}` : ''}]`;
  const label = exhibitLabel ? `${exhibitLabel} — ${title}` : title;
  return `${tag} ${label}: ${recap} What should I take from this?`;
};

/** Selection-explain convention: the user highlighted text anywhere in the
 * main area; ground the question in which tab they were reading. */
export const explainSelectionQuestion = (tabLabel, selectedText) => {
  const trimmed = String(selectedText || '').trim().slice(0, 300);
  return `Explain, in the context of the ${tabLabel} tab: "${trimmed}"`;
};

export const AGENT_STREAM_URL = '/api/agent/stream';

/** Auto-interpretation: {tool, result} -> {interpretation, grounded, mode}. */
export const interpretResult = (tool, result) =>
  post('/api/agent/interpret', { tool, result });

// ------------------------------------------------------------ The Model tab

export const getModelCoefficients = () => get('/api/model/coefficients');

export const getVariableDictionary = () => get('/api/model/variable_dictionary');

export const getLgd = () => get('/api/model/lgd');

// ----------------------------------------------------------- The Policy tab

export const getStagingSensitivity = () => get('/api/policy/staging_sensitivity');

export const getWeightsTable = () => get('/api/policy/weights_table');

export const getExhibitsList = () => get('/api/exhibits/list');

// ------------------------------------------------------ The Real Data tab

export const getFreddieSummary = () => get('/api/freddie/summary');

export const getFreddieHazard = () => get('/api/freddie/hazard');

export const getFreddieBacktest = () => get('/api/freddie/backtest');

export const getFreddieExhibits = () => get('/api/freddie/exhibits');
