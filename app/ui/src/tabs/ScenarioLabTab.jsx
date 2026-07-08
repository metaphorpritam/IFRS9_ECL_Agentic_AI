import { useState } from 'preact/hooks';
import {
  shockMacro,
  reweightScenarios,
  rerunEcl,
  decomposeWaterfall,
} from '../api.js';
import { fmtPct, fmtMillions, fmtRatio } from '../format.js';
import WaterfallChart from '../components/WaterfallChart.jsx';
import Interpretation from '../components/Interpretation.jsx';

const SCENARIOS = [
  { key: 'up', label: 'Upside' },
  { key: 'base', label: 'Baseline' },
  { key: 'down', label: 'Downside' },
];
const SHOCK_BOUNDS = { UER: 10, HPI: 5, GDP: 5 };
const SEGMENTS = ['all', 'stage1', 'stage2', 'stage3', 'investor', 'high_ltv'];

function ResultCard({ action }) {
  if (!action) {
    return (
      <div class="empty-note">
        Run a control on the left — the result and a grounded interpretation
        will appear here, and the waterfall below will react to it.
      </div>
    );
  }
  const r = action.result;
  const allowanceM =
    (r.shocked_allowance ?? r.weighted_allowance ?? r.closing_allowance) / 1e6;
  return (
    <div class="result-card">
      <div class="result-card-head">
        <span class="result-tool">{action.tool}</span>
        <span class="result-label">{action.label}</span>
      </div>
      <p class="result-headline">{r.headline}</p>
      <div class="result-metrics">
        {allowanceM != null && !Number.isNaN(allowanceM) && (
          <span class="metric">
            <b>{fmtMillions(allowanceM)}</b> allowance
          </span>
        )}
        {r.coverage != null && (
          <span class="metric">
            <b>{fmtPct(r.coverage)}</b> coverage
          </span>
        )}
        {r.jensen_ratio != null && (
          <span class="metric">
            <b>{fmtRatio(r.jensen_ratio)}</b> Jensen ratio
          </span>
        )}
        {r.delta_pct != null && (
          <span class="metric">
            <b>{r.delta_pct >= 0 ? '+' : ''}
              {r.delta_pct.toFixed(1)}%
            </b>{' '}
            vs baseline
          </span>
        )}
      </div>
      <Interpretation tool={action.tool} result={r} />
    </div>
  );
}

export default function ScenarioLabTab() {
  const [action, setAction] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const [weights, setWeights] = useState({ up: 25, base: 50, down: 25 });
  const [shockVar, setShockVar] = useState('UER');
  const [shockPp, setShockPp] = useState(2);
  const [shockShape, setShockShape] = useState('parallel');
  const [segment, setSegment] = useState('all');
  const [t0, setT0] = useState(20);
  const [t1, setT1] = useState(40);

  const sum = SCENARIOS.reduce((s, { key }) => s + weights[key], 0);
  const norm = Object.fromEntries(
    SCENARIOS.map(({ key }) => [key, sum > 0 ? weights[key] / sum : 0]),
  );

  const run = async (tool, label, fn) => {
    setBusy(true);
    setErr(null);
    try {
      const result = await fn();
      setAction({ tool, label, result });
    } catch (e) {
      setErr(`${label} failed: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div class="tab-body scenario-lab">
      <header class="tab-intro">
        <h1>Scenario Lab</h1>
        <p>
          Parameterise the four Tier-1 engine tools — every number is
          computed by the frozen engine; the agent only routes, validates and
          narrates. After each run, the copilot auto-interprets the result
          below, grounded in the tool's own output.
        </p>
      </header>

      <div class="scenario-grid">
        <div class="scenario-controls-col">
          <section class="panel">
            <h2>Reweight scenarios</h2>
            <p class="panel-sub">reweight_scenarios — probability weights must sum to 1.</p>
            {SCENARIOS.map(({ key, label }) => (
              <label class="slider-row" key={key}>
                <span class="slider-label">{label}</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={weights[key]}
                  disabled={busy}
                  onInput={(e) =>
                    setWeights((w) => ({ ...w, [key]: Number(e.currentTarget.value) }))
                  }
                />
                <span class="slider-value">{fmtPct(norm[key], 0)}</span>
              </label>
            ))}
            <button
              class="btn"
              disabled={busy || sum === 0}
              onClick={() =>
                run(
                  'reweight_scenarios',
                  `Reweight ${(norm.up * 100).toFixed(0)}/${(norm.base * 100).toFixed(0)}/${(norm.down * 100).toFixed(0)}`,
                  () => reweightScenarios(norm.up, norm.base, norm.down),
                )
              }
            >
              Run reweight
            </button>
          </section>

          <section class="panel">
            <h2>Macro shock</h2>
            <p class="panel-sub">shock_macro — coherent shock of the base scenario.</p>
            <div class="control-row">
              <select value={shockVar} onInput={(e) => setShockVar(e.currentTarget.value)}>
                <option value="UER">UER (unemployment level)</option>
                <option value="HPI">HPI growth</option>
                <option value="GDP">GDP growth</option>
              </select>
              <select value={shockShape} onInput={(e) => setShockShape(e.currentTarget.value)}>
                <option value="parallel">parallel</option>
                <option value="peak_revert">peak_revert</option>
              </select>
            </div>
            <label class="slider-row">
              <span class="slider-label">Shock size</span>
              <input
                type="range"
                min={-SHOCK_BOUNDS[shockVar]}
                max={SHOCK_BOUNDS[shockVar]}
                step="0.5"
                value={shockPp}
                disabled={busy}
                onInput={(e) => setShockPp(Number(e.currentTarget.value))}
              />
              <span class="slider-value">{shockPp >= 0 ? '+' : ''}{shockPp.toFixed(1)}pp</span>
            </label>
            <button
              class="btn"
              disabled={busy}
              onClick={() =>
                run(
                  'shock_macro',
                  `${shockVar} ${shockPp >= 0 ? '+' : ''}${shockPp.toFixed(1)}pp (${shockShape})`,
                  () => shockMacro(shockVar, shockPp, shockShape),
                )
              }
            >
              Run shock
            </button>
          </section>

          <section class="panel">
            <h2>Rerun by segment</h2>
            <p class="panel-sub">rerun_ecl — decomposition of the already-computed book, no refit.</p>
            <select value={segment} onInput={(e) => setSegment(e.currentTarget.value)}>
              {SEGMENTS.map((s) => (
                <option value={s} key={s}>{s}</option>
              ))}
            </select>
            <button
              class="btn"
              disabled={busy}
              style={{ marginLeft: 8 }}
              onClick={() => run('rerun_ecl', `Segment: ${segment}`, () => rerunEcl(segment))}
            >
              Run segment
            </button>
          </section>

          <section class="panel">
            <h2>Decompose waterfall</h2>
            <p class="panel-sub">decompose_waterfall — movement between two panel snapshots (t=1..60).</p>
            <div class="control-row">
              <label>
                t0
                <input
                  type="number"
                  min="1"
                  max="59"
                  value={t0}
                  onInput={(e) => setT0(Number(e.currentTarget.value))}
                />
              </label>
              <label>
                t1
                <input
                  type="number"
                  min="2"
                  max="60"
                  value={t1}
                  onInput={(e) => setT1(Number(e.currentTarget.value))}
                />
              </label>
            </div>
            <button
              class="btn"
              disabled={busy || t0 >= t1}
              onClick={() =>
                run('decompose_waterfall', `Decompose t=${t0} → t=${t1}`, () =>
                  decomposeWaterfall(t0, t1),
                )
              }
            >
              Run decomposition
            </button>
          </section>

          {busy && <div class="status muted">Engine running…</div>}
          {err && <div class="status status-err">{err}</div>}
        </div>

        <div class="scenario-result-col">
          <section class="panel">
            <h2>Result &amp; interpretation</h2>
            <ResultCard action={action} />
          </section>
          <WaterfallChart action={action} t0={t0} t1={t1} />
        </div>
      </div>
    </div>
  );
}
