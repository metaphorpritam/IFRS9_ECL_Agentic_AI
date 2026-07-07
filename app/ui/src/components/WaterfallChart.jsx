import { useEffect, useMemo, useState } from 'preact/hooks';
import { getWaterfall } from '../api.js';
import { useECharts } from '../charts/useECharts.js';
import { COLORS, CHART_TEXT, GRID_LINE, INK_MUTED, SURFACE } from '../palette.js';
import { fmtMillions, fmtSignedM } from '../format.js';

/** Build the classic floating-bar waterfall: invisible base + visible bar. */
function buildOption(wf) {
  const cats = [wf.start.label, ...wf.steps.map((s) => s.label), wf.end.label];
  const base = [];
  const bars = [];

  // Start total.
  base.push(0);
  bars.push({
    value: wf.start.value_m,
    kind: 'total',
    itemStyle: { color: COLORS.accent, borderRadius: [4, 4, 0, 0] },
  });

  // Movement steps float from the running total.
  let cum = wf.start.value_m;
  for (const s of wf.steps) {
    const next = cum + s.delta_m;
    base.push(Math.min(cum, next));
    bars.push({
      value: Math.abs(s.delta_m),
      kind: s.delta_m >= 0 ? 'up' : 'down',
      delta: s.delta_m,
      itemStyle: {
        color: s.delta_m >= 0 ? COLORS.warn : COLORS.good,
        borderRadius: 4,
      },
    });
    cum = next;
  }

  // End total.
  base.push(0);
  bars.push({
    value: wf.end.value_m,
    kind: 'total',
    itemStyle: { color: COLORS.accent, borderRadius: [4, 4, 0, 0] },
  });

  return {
    textStyle: CHART_TEXT,
    grid: { left: 56, right: 16, top: 32, bottom: 56 },
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        if (p.seriesIndex === 0) return '';
        const d = p.data;
        const val = d.kind === 'total' ? fmtMillions(d.value) : fmtSignedM(d.delta);
        return `<b>${p.name}</b><br/>${val}`;
      },
    },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: {
        color: INK_MUTED,
        interval: 0,
        rotate: cats.length > 5 ? 20 : 0,
        fontSize: 11,
      },
      axisLine: { lineStyle: { color: GRID_LINE } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Allowance ($m)',
      nameTextStyle: { color: INK_MUTED },
      axisLabel: { color: INK_MUTED },
      splitLine: { lineStyle: { color: GRID_LINE, type: 'dashed' } },
    },
    series: [
      {
        name: 'base',
        type: 'bar',
        stack: 'wf',
        data: base,
        itemStyle: { color: 'transparent' },
        emphasis: { itemStyle: { color: 'transparent' } },
        tooltip: { show: false },
        silent: true,
        barWidth: '55%',
      },
      {
        name: 'movement',
        type: 'bar',
        stack: 'wf',
        data: bars,
        itemStyle: { borderColor: SURFACE, borderWidth: 1 },
        label: {
          show: true,
          position: 'top',
          color: CHART_TEXT.color,
          fontSize: 11,
          formatter: (p) =>
            p.data.kind === 'total'
              ? fmtMillions(p.data.value)
              : fmtSignedM(p.data.delta),
        },
      },
    ],
  };
}

/** ECharts waterfall of the ECL movement decomposition. */
export default function WaterfallChart({ rev }) {
  const [wf, setWf] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getWaterfall()
      .then((d) => alive && (setWf(d), setError(null)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [rev]);

  const option = useMemo(() => (wf ? buildOption(wf) : null), [wf]);
  const ref = useECharts(option);

  return (
    <section class="panel">
      <h2>ECL movement waterfall</h2>
      <p class="panel-sub">
        Decomposition of the reported allowance movement — every bar is an engine
        number.
      </p>
      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}
      <div ref={ref} class="chart chart-tall" />
    </section>
  );
}
