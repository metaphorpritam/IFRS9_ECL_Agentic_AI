// Pure ECharts option builder for the allowance waterfall (FINAL_SPEC.md
// §8.2). Kept dependency-free of Preact/JSX so it can be exercised from a
// plain Node script (scripts/verify-waterfall.mjs) as a build-time
// regression check against the historical-mode adapter bug.
import { colors, chartText, gridLine, inkMuted, surface, baselineColor } from '../palette.js';
import { fmtMillions, fmtSignedM } from '../format.js';

// Any rendered segment below this share of the largest bar in the exhibit
// is floored to this height for legibility — the FLOOR CHANGES PIXELS,
// NEVER LABELS (§8.2). Returned alongside the option so the caller can show
// the disclosure caption only when it actually fired.
const FLOOR_SHARE = 0.03;

const LEGEND = [
  { key: 'level', label: 'Running total' },
  { key: 'up', label: 'Adds to allowance' },
  { key: 'down', label: 'Reduces allowance' },
];

/** Build the classic floating-bar waterfall: invisible base + visible bar.
 * Returns `{ option, flooredAny, legend }` — `option` feeds ECharts
 * directly, `flooredAny` gates the disclosure caption, `legend` is the
 * fixed 3-identity legend (rendered as HTML, not an ECharts legend, since
 * every bar uses per-datum itemStyle rather than named series). */
export function buildWaterfallOption(wf, { reducedMotion = false } = {}) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const base = baselineColor();
  const surf = surface();
  const cats = [wf.start.label, ...wf.steps.map((s) => s.label), wf.end.label];

  const rawMagnitudes = [
    wf.start.value_m,
    ...wf.steps.map((s) => Math.abs(s.delta_m)),
    wf.end.value_m,
  ];
  const maxVal = Math.max(...rawMagnitudes, 1e-9);
  const floor = maxVal * FLOOR_SHARE;
  let flooredAny = false;

  const baseData = [];
  const barData = [];

  // Opening level.
  baseData.push(0);
  barData.push({
    value: wf.start.value_m,
    kind: 'level',
    itemStyle: { color: c.levelFill, borderRadius: [4, 4, 0, 0] },
  });

  // Movement steps float from the running total.
  let cum = wf.start.value_m;
  for (const s of wf.steps) {
    const next = cum + s.delta_m;
    const mag = Math.abs(s.delta_m);
    let renderMag = mag;
    if (mag > 0 && mag < floor) {
      renderMag = floor;
      flooredAny = true;
    }
    baseData.push(Math.min(cum, next));
    const growingUp = s.delta_m >= 0;
    barData.push({
      value: renderMag,
      kind: growingUp ? 'up' : 'down',
      delta: s.delta_m,
      itemStyle: {
        color: growingUp ? c.increase : c.decrease,
        borderRadius: growingUp ? [4, 4, 0, 0] : [0, 0, 4, 4],
      },
    });
    cum = next;
  }

  // Closing level.
  baseData.push(0);
  barData.push({
    value: wf.end.value_m,
    kind: 'level',
    itemStyle: { color: c.levelFill, borderRadius: [4, 4, 0, 0] },
  });

  const rotate = cats.length > 5 ? 20 : 0;

  const option = {
    textStyle: text,
    backgroundColor: 'transparent',
    grid: {
      left: 56,
      right: 16,
      top: 24,
      bottom: rotate ? 56 : 40,
      containLabel: true,
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: surf,
      borderColor: base,
      borderWidth: 1,
      textStyle: { color: text.color },
      formatter: (p) => {
        if (p.seriesIndex === 0) return '';
        const d = p.data;
        const val = d.kind === 'level' ? fmtMillions(d.value) : fmtSignedM(d.delta);
        const label = LEGEND.find((l) => l.key === d.kind)?.label ?? '';
        return `<b>${val}</b><br/><span style="color:${muted}">${p.name} — ${label}</span>`;
      },
    },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: {
        color: muted,
        interval: 0,
        rotate,
        fontSize: 12,
        fontFamily: text.fontFamily,
      },
      axisLine: { lineStyle: { color: base } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Allowance ($m)',
      nameTextStyle: { color: muted, fontFamily: text.fontFamily },
      axisLabel: { color: muted, fontFamily: text.fontFamily },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: grid, type: 'solid' } },
    },
    series: [
      {
        name: 'base',
        type: 'bar',
        stack: 'wf',
        data: baseData,
        itemStyle: { color: 'transparent' },
        emphasis: { itemStyle: { color: 'transparent' } },
        tooltip: { show: false },
        silent: true,
        barMaxWidth: 24,
      },
      {
        name: 'movement',
        type: 'bar',
        stack: 'wf',
        data: barData,
        barMaxWidth: 24,
        itemStyle: { borderColor: surf, borderWidth: 2 },
        label: {
          show: true,
          position: 'top',
          color: text.color,
          fontSize: 12,
          fontFamily: text.fontFamily,
          fontVariant: 'tabular-nums',
          formatter: (p) =>
            p.data.kind === 'level' ? fmtMillions(p.data.value) : fmtSignedM(p.data.delta),
        },
        markLine: {
          silent: true,
          symbol: 'none',
          animation: false,
          lineStyle: { color: base, type: 'solid', width: 1 },
          label: { show: false },
          data: [{ yAxis: wf.start.value_m }, { yAxis: wf.end.value_m }],
        },
      },
    ],
    animationDuration: reducedMotion ? 0 : 300,
  };

  return { option, flooredAny, legend: LEGEND };
}
