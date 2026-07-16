import { useEffect, useMemo, useState } from 'preact/hooks';
import { adaptWaterfallRows, explainPanelQuestion, getWaterfall } from '../api.js';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { buildWaterfallOption } from '../charts/waterfallOption.js';
import { colors } from '../palette.js';
import { fmtMillions, fmtSignedM, runDate } from '../format.js';
import Panel from './Panel.jsx';
import StageGuide from './StageGuide.jsx';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function recapFor(wf) {
  if (!wf) return 'no data rendered yet';
  const steps = wf.steps.map((s) => `${s.label} ${fmtSignedM(s.delta_m)}`).join(', ');
  return `opening ${fmtMillions(wf.start.value_m)}, ${steps}, closing ${fmtMillions(wf.end.value_m)}.`;
}

function WaterfallTable({ wf }) {
  const rows = [
    { label: wf.start.label, value: fmtMillions(wf.start.value_m) },
    ...wf.steps.map((s) => ({ label: s.label, value: fmtSignedM(s.delta_m) })),
    { label: wf.end.label, value: fmtMillions(wf.end.value_m) },
  ];
  return (
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Component</th>
            <th>Allowance ($m)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              <td class="num-cell">{r.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * ECharts waterfall. Three modes, resolved from `action = {tool, label, result}`:
 *  - shock_macro: result.waterfall_vs_baseline (baseline vs shocked allowance);
 *  - decompose_waterfall: result.components (its own custom t0/t1 window);
 *  - anything else (reweight_scenarios, rerun_ecl) or no action yet:
 *    the fixed historical movement between two panel snapshots (t0/t1 props).
 *
 * Historical-mode bug fix (FINAL_SPEC §0.2): the raw GET /api/ecl/waterfall
 * payload is `{components: [...], period_t0, period_t1, ...}`, NOT the
 * `{start, steps, end}` shape buildWaterfallOption expects — it must go
 * through the same adaptWaterfallRows() adapter as the tool-result modes,
 * or the default (historical) view renders empty.
 */
export default function WaterfallChart({ t0 = 59, t1 = 60, action, exhibit }) {
  const [histRaw, setHistRaw] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState('chart');

  useEffect(() => {
    let alive = true;
    getWaterfall(t0, t1)
      .then((d) => alive && (setHistRaw(d), setError(null)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [t0, t1]);

  const r = action?.result;
  const shockRows = action?.tool === 'shock_macro' ? r?.waterfall_vs_baseline : null;
  const decomposeRows = action?.tool === 'decompose_waterfall' ? r?.components : null;

  // Historical mode wraps the SAME raw payload shape through the adapter —
  // this is the fix: `hist` used to be the raw {components,...} object.
  const hist = useMemo(
    () => (histRaw ? adaptWaterfallRows(histRaw.components, 'Opening allowance', 'Closing allowance') : null),
    [histRaw],
  );

  const wf = useMemo(() => {
    if (shockRows) return adaptWaterfallRows(shockRows, 'Baseline allowance', 'Shocked allowance');
    if (decomposeRows) return adaptWaterfallRows(decomposeRows, 'Opening allowance', 'Closing allowance');
    return hist;
  }, [shockRows, decomposeRows, hist]);

  const themeV = useThemeVersion();
  const built = useMemo(
    () => (wf ? buildWaterfallOption(wf, { reducedMotion: prefersReducedMotion() }) : null),
    [wf, themeV],
  );
  const ref = useECharts(built?.option ?? null);
  const live = colors();

  const subtitle = shockRows
    ? `Effect of ${action.label} vs the baseline scenario — every bar is an engine number.`
    : decomposeRows
      ? `Movement decomposition ${r.period_t0} → ${r.period_t1} — every bar is an engine number.`
      : `Historical movement between panel snapshots ${histRaw?.period_t0 ?? '2014Q4'} → ${
          histRaw?.period_t1 ?? '2015Q1'
        } (t=${t0} → t=${t1}; fixed exhibit — scenario controls act on the reported allowance above, not on this history).`;

  const source = shockRows
    ? { endpoint: 'POST /api/tools/shock_macro', runDate: runDate() }
    : decomposeRows
      ? { endpoint: 'POST /api/tools/decompose_waterfall', runDate: runDate() }
      : { endpoint: `GET /api/ecl/waterfall?t0=${t0}&t1=${t1}`, runDate: runDate() };

  return (
    <Panel
      exhibit={exhibit}
      title="Allowance bridge"
      subtitle={subtitle}
      source={source}
      dense={false}
      explainLabel="Allowance bridge"
      actions={
        <button
          type="button"
          class="icon-btn icon-btn-square"
          aria-pressed={view === 'table'}
          aria-label="Show as table"
          data-tip="Table view"
          onClick={() => setView((v) => (v === 'chart' ? 'table' : 'chart'))}
        >
          ⊞
        </button>
      }
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'waterfall',
          params: { t0, t1 },
          exhibitLabel: exhibit != null ? `Exhibit ${exhibit}` : undefined,
          title: 'Allowance bridge',
          recap: recapFor(wf),
        })
      }
    >
      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}
      {view === 'chart' ? (
        <div ref={ref} class="chart chart-tall" />
      ) : (
        wf && <WaterfallTable wf={wf} />
      )}
      {built?.flooredAny && (
        <p class="panel-sub chart-caveat">
          Components under ~3% of range shown at a minimum visible height —
          labeled values are exact.
        </p>
      )}
      <div class="chart-legend-row">
        <span class="legend-item">
          <span class="legend-dot" style={{ background: live.levelFill }} /> Running total
        </span>
        <span class="legend-item">
          <span class="legend-dot" style={{ background: live.increase }} /> Adds to allowance
        </span>
        <span class="legend-item">
          <span class="legend-dot" style={{ background: live.decrease }} /> Reduces allowance
        </span>
      </div>
      <StageGuide />
    </Panel>
  );
}
