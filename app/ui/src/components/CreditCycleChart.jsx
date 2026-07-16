import { useEffect, useMemo, useState } from 'preact/hooks';
import { explainPanelQuestion, getCreditCycle } from '../api.js';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { colors, chartText, gridLine, inkMuted, surface, baselineColor } from '../palette.js';
import { fmtPct, runDate } from '../format.js';
import Panel from './Panel.jsx';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Fixed series -> hue SLOT assignment (never cycled): identity is stable
// even if a series is missing from the payload. Hues are resolved live in
// buildOption so light/dark steps apply.
const SERIES_SPEC = [
  { key: 'observed', name: 'Observed default rate', slot: 'orange', dash: 'solid', width: 1.5 },
  { key: 'ttc', name: 'TTC PD', slot: 'gray', dash: 'dashed', width: 2 },
  { key: 'pit', name: 'PIT PD', slot: 'accent', dash: 'solid', width: 2 },
  { key: 'hybrid', name: 'Hybrid PD (α=0.5)', slot: 'purple', dash: 'solid', width: 2 },
];

function buildOption(data, reducedMotion) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const base = baselineColor();
  const surf = surface();
  const present = SERIES_SPEC.filter((s) => Array.isArray(data[s.key])).map(
    (s) => ({ ...s, color: c[s.slot] }),
  );
  return {
    textStyle: text,
    backgroundColor: 'transparent',
    legend: {
      top: 0,
      icon: 'roundRect',
      itemWidth: 14,
      itemHeight: 3,
      textStyle: { color: muted, fontSize: 12, fontFamily: text.fontFamily },
    },
    grid: { left: 56, right: 16, top: 36, bottom: 36, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: base } },
      backgroundColor: surf,
      borderColor: base,
      borderWidth: 1,
      textStyle: { color: text.color },
      valueFormatter: (v) => fmtPct(v),
    },
    xAxis: {
      type: 'category',
      data: data.calendar,
      axisLabel: { color: muted, fontSize: 12, fontFamily: text.fontFamily },
      axisLine: { lineStyle: { color: base } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Quarterly PD',
      nameTextStyle: { color: muted, fontFamily: text.fontFamily },
      axisLabel: { color: muted, formatter: (v) => fmtPct(v, 1), fontFamily: text.fontFamily },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: grid, type: 'solid' } },
    },
    series: present.map((s) => ({
      name: s.name,
      type: 'line',
      data: data[s.key],
      showSymbol: false,
      lineStyle: { color: s.color, width: s.width, type: s.dash, cap: 'round', join: 'round' },
      itemStyle: { color: s.color },
      emphasis: { focus: 'series' },
    })),
    animationDuration: reducedMotion ? 0 : 300,
  };
}

// Adapt the contract's {points:[{calendar, z, observed_dr, ttc_pd, pit_pd}]}
// into parallel arrays for the line-chart option builder (chart-shape-only
// reshaping, no business arithmetic).
function adapt(payload) {
  return {
    calendar: payload.points.map((p) => p.calendar),
    ttc: payload.points.map((p) => p.ttc_pd),
    pit: payload.points.map((p) => p.pit_pd),
    observed: payload.points.map((p) => p.observed_dr),
    rho: payload.rho,
  };
}

function CreditCycleTable({ data }) {
  return (
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Quarter</th>
            <th class="num">Observed default rate (%)</th>
            <th class="num">TTC PD (%)</th>
            <th class="num">PIT PD (%)</th>
          </tr>
        </thead>
        <tbody>
          {data.calendar.map((cal, i) => (
            <tr key={cal}>
              <td>{cal}</td>
              <td class="num">{fmtPct(data.observed[i])}</td>
              <td class="num">{fmtPct(data.ttc[i])}</td>
              <td class="num">{fmtPct(data.pit[i])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Static exhibit: the credit cycle — PIT vs TTC PD over calendar time. */
export default function CreditCycleChart({ exhibit }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [view, setView] = useState('chart');

  useEffect(() => {
    let alive = true;
    getCreditCycle()
      .then((d) => alive && setData(adapt(d)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  const themeV = useThemeVersion();
  const option = useMemo(
    () => (data ? buildOption(data, prefersReducedMotion()) : null),
    [data, themeV],
  );
  const ref = useECharts(option);

  return (
    <Panel
      exhibit={exhibit}
      title="Credit cycle — PIT vs TTC"
      subtitle={`Vasicek single-factor conditioning (ρ = ${data ? data.rho.toFixed(4) : '0.0227'}) over 2000Q2–2015Q1; Z recovered by Belkin inversion.`}
      source={{ endpoint: 'GET /api/exhibits/credit_cycle', runDate: runDate() }}
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
          panelId: 'credit_cycle',
          exhibitLabel: exhibit != null ? `Exhibit ${exhibit}` : undefined,
          title: 'Credit cycle — PIT vs TTC',
          recap: data
            ? `rho = ${data.rho.toFixed(4)}; latest quarter ${data.calendar.at(-1)}: observed default rate ${fmtPct(data.observed.at(-1))}, TTC PD ${fmtPct(data.ttc.at(-1))}, PIT PD ${fmtPct(data.pit.at(-1))}.`
            : 'no data rendered yet',
        })
      }
    >
      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}
      {view === 'chart' ? <div ref={ref} class="chart" /> : data && <CreditCycleTable data={data} />}
    </Panel>
  );
}
