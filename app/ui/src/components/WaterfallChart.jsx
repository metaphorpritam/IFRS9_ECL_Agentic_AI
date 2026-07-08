import { useEffect, useMemo, useState } from 'preact/hooks';
import { adaptWaterfallRows, getWaterfall } from '../api.js';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { colors, chartText, gridLine, inkMuted, surface } from '../palette.js';
import { fmtMillions, fmtSignedM } from '../format.js';
import StageGuide from './StageGuide.jsx';

/** Build the classic floating-bar waterfall: invisible base + visible bar. */
function buildOption(wf) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const cats = [wf.start.label, ...wf.steps.map((s) => s.label), wf.end.label];
  const base = [];
  const bars = [];

  // Start total.
  base.push(0);
  bars.push({
    value: wf.start.value_m,
    kind: 'total',
    itemStyle: { color: c.accent, borderRadius: [4, 4, 0, 0] },
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
        color: s.delta_m >= 0 ? c.warn : c.good,
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
    itemStyle: { color: c.accent, borderRadius: [4, 4, 0, 0] },
  });

  return {
    textStyle: text,
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
        color: muted,
        interval: 0,
        rotate: cats.length > 5 ? 20 : 0,
        fontSize: 11,
      },
      axisLine: { lineStyle: { color: grid } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Allowance ($m)',
      nameTextStyle: { color: muted },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: grid, type: 'dashed' } },
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
        itemStyle: { borderColor: surface(), borderWidth: 1 },
        label: {
          show: true,
          position: 'top',
          color: text.color,
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

/**
 * ECharts waterfall. Three modes, resolved from `action = {tool, label, result}`:
 *  - shock_macro: result.waterfall_vs_baseline (baseline vs shocked allowance);
 *  - decompose_waterfall: result.components (its own custom t0/t1 window);
 *  - anything else (reweight_scenarios, rerun_ecl) or no action yet:
 *    the fixed historical movement between two panel snapshots (t0/t1 props).
 */
export default function WaterfallChart({ t0 = 20, t1 = 40, action }) {
  const [hist, setHist] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getWaterfall(t0, t1)
      .then((d) => alive && (setHist(d), setError(null)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [t0, t1]);

  const r = action?.result;
  const shockRows = action?.tool === 'shock_macro' ? r?.waterfall_vs_baseline : null;
  const decomposeRows = action?.tool === 'decompose_waterfall' ? r?.components : null;

  const wf = useMemo(() => {
    if (shockRows) return adaptWaterfallRows(shockRows, 'Baseline allowance', 'Shocked allowance');
    if (decomposeRows) return adaptWaterfallRows(decomposeRows, 'Opening allowance', 'Closing allowance');
    return hist;
  }, [shockRows, decomposeRows, hist]);

  const themeV = useThemeVersion();
  const option = useMemo(() => (wf ? buildOption(wf) : null), [wf, themeV]);
  const ref = useECharts(option);

  const subtitle = shockRows
    ? `Effect of ${action.label} vs the baseline scenario — every bar is an engine number.`
    : decomposeRows
      ? `Movement decomposition ${r.period_t0} → ${r.period_t1} — every bar is an engine number.`
      : `Historical movement between panel snapshots ${hist?.period_t0 ?? '2005Q2'} → ${
          hist?.period_t1 ?? '2010Q1'
        } (fixed exhibit — scenario controls act on the reported allowance above, not on this history).`;

  return (
    <section class="panel">
      <h2>ECL movement waterfall</h2>
      <p class="panel-sub">{subtitle}</p>
      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}
      <div ref={ref} class="chart chart-tall" />
      <StageGuide />
    </section>
  );
}
