import { useEffect, useMemo, useState } from 'preact/hooks';
import { getCreditCycle } from '../api.js';
import { useECharts } from '../charts/useECharts.js';
import { COLORS, CHART_TEXT, GRID_LINE, INK_MUTED } from '../palette.js';
import { fmtPct } from '../format.js';

// Fixed series -> hue assignment (never cycled): identity is stable even if a
// series is missing from the payload.
const SERIES_SPEC = [
  { key: 'observed', name: 'Observed default rate', color: COLORS.orange, dash: 'solid', width: 1.5 },
  { key: 'ttc', name: 'TTC PD', color: COLORS.gray, dash: 'dashed', width: 2 },
  { key: 'pit', name: 'PIT PD', color: COLORS.accent, dash: 'solid', width: 2 },
  { key: 'hybrid', name: 'Hybrid PD (α=0.5)', color: COLORS.purple, dash: 'solid', width: 2 },
];

function buildOption(data) {
  const present = SERIES_SPEC.filter((s) => Array.isArray(data[s.key]));
  return {
    textStyle: CHART_TEXT,
    legend: {
      top: 0,
      icon: 'roundRect',
      itemWidth: 14,
      itemHeight: 3,
      textStyle: { color: CHART_TEXT.color, fontSize: 11 },
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
      axisLabel: { color: INK_MUTED, fontSize: 11 },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Quarterly PD',
      nameTextStyle: { color: INK_MUTED },
      axisLabel: { color: INK_MUTED, formatter: (v) => fmtPct(v, 1) },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } },
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

/** Static exhibit: the credit cycle — PIT vs TTC vs hybrid PD over calendar time. */
export default function CreditCycleChart() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getCreditCycle()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  const option = useMemo(() => (data ? buildOption(data) : null), [data]);
  const ref = useECharts(option);

  return (
    <section class="panel">
      <h2>Credit cycle — PIT vs TTC vs hybrid</h2>
      <p class="panel-sub">
        Vasicek single-factor conditioning (ρ = 0.0227) over 2000Q2–2015Q1; Z
        recovered by Belkin inversion.
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
