import { useEffect, useMemo, useState } from 'preact/hooks';
import { getCreditCycle } from '../api.js';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { colors, chartText, gridLine, inkMuted } from '../palette.js';
import { fmtPct } from '../format.js';

// Fixed series -> hue SLOT assignment (never cycled): identity is stable
// even if a series is missing from the payload. Hues are resolved live in
// buildOption so light/dark steps apply.
const SERIES_SPEC = [
  { key: 'observed', name: 'Observed default rate', slot: 'orange', dash: 'solid', width: 1.5 },
  { key: 'ttc', name: 'TTC PD', slot: 'gray', dash: 'dashed', width: 2 },
  { key: 'pit', name: 'PIT PD', slot: 'accent', dash: 'solid', width: 2 },
  { key: 'hybrid', name: 'Hybrid PD (α=0.5)', slot: 'purple', dash: 'solid', width: 2 },
];

function buildOption(data) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const present = SERIES_SPEC.filter((s) => Array.isArray(data[s.key])).map(
    (s) => ({ ...s, color: c[s.slot] }),
  );
  return {
    textStyle: text,
    legend: {
      top: 0,
      icon: 'roundRect',
      itemWidth: 14,
      itemHeight: 3,
      textStyle: { color: text.color, fontSize: 11 },
    },
    grid: { left: 56, right: 16, top: 36, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { show: false } },
      valueFormatter: (v) => fmtPct(v),
    },
    xAxis: {
      type: 'category',
      data: data.calendar,
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: grid } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Quarterly PD',
      nameTextStyle: { color: muted },
      axisLabel: { color: muted, formatter: (v) => fmtPct(v, 1) },
      splitLine: { lineStyle: { color: grid, type: 'dashed' } },
    },
    series: present.map((s) => ({
      name: s.name,
      type: 'line',
      data: data[s.key],
      showSymbol: false,
      lineStyle: { color: s.color, width: s.width, type: s.dash },
      itemStyle: { color: s.color },
      emphasis: { focus: 'series' },
    })),
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

/** Static exhibit: the credit cycle — PIT vs TTC PD over calendar time. */
export default function CreditCycleChart() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

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
  const option = useMemo(() => (data ? buildOption(data) : null), [data, themeV]);
  const ref = useECharts(option);

  return (
    <section class="panel">
      <h2>Credit cycle — PIT vs TTC</h2>
      <p class="panel-sub">
        Vasicek single-factor conditioning (ρ = {data ? data.rho.toFixed(4) : '0.0227'}) over
        2000Q2–2015Q1; Z recovered by Belkin inversion.
      </p>
      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}
      <div ref={ref} class="chart" />
    </section>
  );
}
