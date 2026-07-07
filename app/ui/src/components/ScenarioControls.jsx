import { useState } from 'preact/hooks';
import { reweightScenarios, shockMacro } from '../api.js';
import { fmtPct } from '../format.js';

const SCENARIOS = [
  { key: 'up', label: 'Upside' },
  { key: 'base', label: 'Baseline' },
  { key: 'severe', label: 'Severely adverse' },
];

/**
 * Scenario weight sliders (normalised to sum to 1) + UER shock slider.
 * The UI only PARAMETERISES tool calls — the engine does all arithmetic;
 * normalisation here is input hygiene, not modelling.
 */
export default function ScenarioControls({ onRan }) {
  const [raw, setRaw] = useState({ up: 25, base: 50, severe: 25 });
  const [shock, setShock] = useState(0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(null); // {kind: 'ok'|'err', text}

  const sum = SCENARIOS.reduce((s, { key }) => s + raw[key], 0);
  const norm = Object.fromEntries(
    SCENARIOS.map(({ key }) => [key, sum > 0 ? raw[key] / sum : 0]),
  );

  const run = async (label, fn) => {
    setBusy(true);
    setStatus(null);
    try {
      const result = await fn();
      setStatus({
        kind: 'ok',
        text: result?.headline || `${label} — engine re-run complete.`,
      });
      onRan?.({ label, result });
    } catch (err) {
      setStatus({ kind: 'err', text: `${label} failed: ${err.message}` });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section class="panel">
      <h2>Scenario controls</h2>

      <div class="control-group">
        <div class="control-group-title">Scenario weights (normalised)</div>
        {SCENARIOS.map(({ key, label }) => (
          <label class="slider-row" key={key}>
            <span class="slider-label">{label}</span>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={raw[key]}
              disabled={busy}
              onInput={(e) =>
                setRaw((r) => ({ ...r, [key]: Number(e.currentTarget.value) }))
              }
            />
            <span class="slider-value">{fmtPct(norm[key], 0)}</span>
          </label>
        ))}
        <button
          class="btn"
          disabled={busy || sum === 0}
          onClick={() => run('Reweight scenarios', () => reweightScenarios(norm))}
        >
          Run reweight
        </button>
      </div>

      <div class="control-group">
        <div class="control-group-title">Macro shock</div>
        <label class="slider-row">
          <span class="slider-label">UER shock</span>
          <input
            type="range"
            min="0"
            max="5"
            step="0.5"
            value={shock}
            disabled={busy}
            onInput={(e) => setShock(Number(e.currentTarget.value))}
          />
          <span class="slider-value">+{shock.toFixed(1)}pp</span>
        </label>
        <button
          class="btn"
          disabled={busy}
          onClick={() => run(`UER shock +${shock.toFixed(1)}pp`, () => shockMacro(shock))}
        >
          Run shock
        </button>
      </div>

      {busy && <div class="status muted">Engine running…</div>}
      {status && (
        <div class={`status ${status.kind === 'err' ? 'status-err' : 'status-ok'}`}>
          {status.text}
        </div>
      )}
    </section>
  );
}
