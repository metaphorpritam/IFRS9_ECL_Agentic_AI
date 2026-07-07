import { useEffect, useMemo, useState } from 'preact/hooks';
import { adaptWaterfallRows, getWaterfall } from '../api.js';
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

function StageGuide() {
  return (
    <details class="stage-guide">
      <summary>What do the stages and horizons mean?</summary>
      <ul>
        <li>
          <b>Stage 1 — performing</b> (no significant deterioration since
          origination): allowance = <b>12-month ECL</b> — expected loss from
          defaults possible in the <i>next 4 quarters</i> only:
          Σ S(t−1)·λ<sub>t</sub>·LGD<sub>t</sub>·EAD<sub>t</sub>·(1+EIR)<sup>−t</sup>, t ≤ 4.
        </li>
        <li>
          <b>Stage 2 — significant increase in credit risk</b> (lifetime PD now
          &gt; 2× its at-origination level + 0.5pp add-on): the same sum over the
          <b> full remaining contractual life</b> (up to 40 quarters here) —
          same loan, longer horizon, bigger allowance.
        </li>
        <li>
          <b>Stage 3 — credit-impaired</b> (defaulted): lifetime ECL collapses
          to LGD × current exposure — scenario-invariant by construction.
        </li>
      </ul>
      <p>
        The stage decides the <i>horizon</i>; the engine always computes both
        12-month and lifetime ECL for every loan and reports the one the stage
        prescribes. This book (2015Q1 reporting date) is a calm-quarter book:
        7,803 loans in Stage 1, none in Stage 2, 43 in Stage 3 — so the
        reported allowance is dominated by 12-month ECL, which is exactly where
        scenario weights and macro shocks act.
      </p>
    </details>
  );
}

/**
 * ECharts waterfall. Two modes:
 *  - action mode: the last shock's engine waterfall vs baseline;
 *  - historical mode: the fixed movement decomposition between two panel
 *    snapshots (independent of the scenario controls by design).
 */
export default function WaterfallChart({ rev, action }) {
  const [hist, setHist] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getWaterfall()
      .then((d) => alive && (setHist(d), setError(null)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  const actionRows = action?.result?.waterfall_vs_baseline;
  const wf = useMemo(
    () =>
      actionRows
        ? adaptWaterfallRows(actionRows, 'Baseline allowance', 'Shocked allowance')
        : hist,
    [actionRows, hist],
  );

  const option = useMemo(() => (wf ? buildOption(wf) : null), [wf]);
  const ref = useECharts(option);

  const subtitle = actionRows
    ? `Effect of ${action.label} vs the baseline scenario — every bar is an engine number.`
    : `Historical movement between panel snapshots ${hist?.period_t0 ?? '2005Q2'} → ${
        hist?.period_t1 ?? '2010Q1'
      } (fixed exhibit — scenario controls act on the reported allowance above, not on this history). Run a shock to see its effect decomposed here.`;

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
